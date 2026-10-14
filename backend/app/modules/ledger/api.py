from fastapi import APIRouter

from app.deps import MemberDep, SessionDep
from app.modules.ledger import service
from app.modules.ledger.schemas import BalanceOut, EntryOut
from app.modules.rewards import service as rewards
from app.modules.tasks import service as tasks

router = APIRouter(prefix="/api", tags=["ledger"])


@router.get("/balance")
async def balance(member: MemberDep, session: SessionDep) -> BalanceOut:
    current = await service.get_balance(session, member.member_id)
    return BalanceOut(
        balance=current.balance, reserved=current.reserved, available=current.available
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
            created_at=entry.created_at,
        )
        for entry in entries
    ]
