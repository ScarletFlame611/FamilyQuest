import uuid
from dataclasses import asdict

from fastapi import APIRouter, Response

from app.core.idempotency import IdempotencyKeyHeader, run_idempotent
from app.deps import AdultDep, ChildDep, MemberDep, SessionDep
from app.modules.rewards import service
from app.modules.rewards.schemas import (
    CancelIn,
    NotEnoughOut,
    PurchaseOut,
    RewardOfferOut,
    RewardOut,
)

router = APIRouter(prefix="/api/rewards", tags=["rewards"])
purchases_router = APIRouter(prefix="/api/purchases", tags=["rewards"])


def _purchase(view: service.PurchaseView) -> PurchaseOut:
    return PurchaseOut(**asdict(view))


@router.get("")
async def list_rewards(member: MemberDep, session: SessionDep) -> list[RewardOfferOut]:
    offers = await service.list_offers(session, member.family_id, member.member_id)
    return [RewardOfferOut(**asdict(offer)) for offer in offers]


@router.get("/{reward_id}")
async def get_reward(reward_id: uuid.UUID, member: MemberDep, session: SessionDep) -> RewardOut:
    return RewardOut(**asdict(await service.get_reward(session, member.family_id, reward_id)))


@router.post(
    "/{reward_id}/buy", response_model=PurchaseOut, responses={409: {"model": NotEnoughOut}}
)
async def buy(
    reward_id: uuid.UUID, child: ChildDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> Response:
    async def action() -> PurchaseOut:
        return _purchase(await service.buy(session, child.family_id, reward_id, child.member_id))

    return await run_idempotent(session, child.member_id, key, f"buy:{reward_id}", action)


@purchases_router.get("/pending")
async def pending_purchases(adult: AdultDep, session: SessionDep) -> list[PurchaseOut]:
    views = await service.list_pending_purchases(session, adult.family_id)
    return [_purchase(view) for view in views]


@purchases_router.post("/{purchase_id}/give", response_model=PurchaseOut)
async def give(
    purchase_id: uuid.UUID, adult: AdultDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> Response:
    async def action() -> PurchaseOut:
        return _purchase(await service.give(session, adult.family_id, purchase_id))

    return await run_idempotent(session, adult.member_id, key, f"give:{purchase_id}", action)


@purchases_router.post("/{purchase_id}/cancel", response_model=PurchaseOut)
async def cancel(
    purchase_id: uuid.UUID,
    body: CancelIn,
    adult: AdultDep,
    session: SessionDep,
    key: IdempotencyKeyHeader = None,
) -> Response:
    async def action() -> PurchaseOut:
        return _purchase(await service.cancel(session, adult.family_id, purchase_id, body.reason))

    return await run_idempotent(
        session, adult.member_id, key, f"cancel:{purchase_id}:{body.reason}", action
    )
