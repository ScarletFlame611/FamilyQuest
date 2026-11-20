import uuid

from fastapi import APIRouter, Response

from app.core.idempotency import IdempotencyKeyHeader, run_idempotent
from app.deps import AdultDep, MemberDep, SessionDep
from app.modules.families import service as families
from app.modules.ledger import service
from app.modules.ledger.enums import EntryKind
from app.modules.ledger.schemas import BalanceOut, EntryOut, MemberBalanceOut, WriteOffIn
from app.modules.rewards import service as rewards
from app.modules.tasks import service as tasks

router = APIRouter(prefix="/api", tags=["ledger"])

# У этих записей в заметке лежит причина, которую взрослый написал для ребёнка
REASONED_KINDS = (EntryKind.REVERSAL, EntryKind.WRITE_OFF)


def _balance(current: service.Balance) -> BalanceOut:
    return BalanceOut(
        balance=current.balance, reserved=current.reserved, available=current.available
    )


@router.get("/balance")
async def balance(member: MemberDep, session: SessionDep) -> BalanceOut:
    return _balance(await service.get_balance(session, member.member_id))


@router.get("/balances")
async def family_balances(adult: AdultDep, session: SessionDep) -> list[MemberBalanceOut]:
    balances = await service.family_balances(session, adult.family_id)
    return [
        MemberBalanceOut(member_id=member_id, **_balance(current).model_dump())
        for member_id, current in balances.items()
    ]


@router.post("/members/{member_id}/write-off", response_model=BalanceOut)
async def write_off(
    member_id: uuid.UUID,
    body: WriteOffIn,
    adult: AdultDep,
    session: SessionDep,
    key: IdempotencyKeyHeader = None,
) -> Response:
    async def action() -> BalanceOut:
        # Участник чужой семьи неотличим от несуществующего
        await families.get_member(session, adult.family_id, member_id)
        return _balance(
            await service.write_off_negative(session, member_id, body.reason, adult.member_id)
        )

    return await run_idempotent(
        session, adult.member_id, key, f"write-off:{member_id}:{body.reason}", action
    )


@router.get("/ledger")
async def ledger(member: MemberDep, session: SessionDep) -> list[EntryOut]:
    entries = await service.list_entries(session, member.member_id)
    titles = await tasks.task_titles(
        session, member.family_id, [e.task_id for e in entries if e.task_id]
    )
    purchases = await rewards.purchase_titles(
        session, member.family_id, [e.purchase_id for e in entries if e.purchase_id]
    )
    return [
        EntryOut(
            kind=entry.kind,
            amount=entry.amount,
            label=(titles.get(entry.task_id) if entry.task_id else None)
            or (purchases.get(entry.purchase_id) if entry.purchase_id else None)
            or entry.note
            or "",
            reason=entry.note if entry.kind in REASONED_KINDS else None,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
