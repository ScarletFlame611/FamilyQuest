import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.errors import ConflictError, NotFoundError
from app.modules.families import service as families
from app.modules.ledger import service as ledger
from app.modules.rewards.enums import PurchaseStatus, RewardIcon
from app.modules.rewards.models import Reward, RewardPurchase


class RewardNotFoundError(NotFoundError):
    pass


class PurchaseNotFoundError(NotFoundError):
    pass


class PurchaseAlreadyResolvedError(ConflictError):
    pass


@dataclass(frozen=True)
class RewardInfo:
    id: uuid.UUID
    title: str
    icon: str
    price: int


@dataclass(frozen=True)
class RewardOffer:
    id: uuid.UUID
    title: str
    icon: str
    price: int
    affordable: bool
    missing: int
    waiting: bool


@dataclass(frozen=True)
class PurchaseView:
    id: uuid.UUID
    reward_id: uuid.UUID
    title: str
    icon: str
    price: int
    status: PurchaseStatus
    child_member_id: uuid.UUID
    child_name: str
    cancel_reason: str | None
    created_at: datetime


async def _purchase_views(
    session: AsyncSession, family_id: uuid.UUID, purchases: list[RewardPurchase]
) -> list[PurchaseView]:
    names = {m.id: m.name for m in await families.list_members(session, family_id)}
    rewards = {
        r.id: r
        for r in await session.scalars(
            select(Reward).where(Reward.id.in_([p.reward_id for p in purchases]))
        )
    }
    return [
        PurchaseView(
            id=p.id,
            reward_id=p.reward_id,
            title=rewards[p.reward_id].title,
            icon=rewards[p.reward_id].icon,
            price=p.price,
            status=p.status,
            child_member_id=p.child_member_id,
            child_name=names.get(p.child_member_id, ""),
            cancel_reason=p.cancel_reason,
            created_at=p.created_at,
        )
        for p in purchases
    ]


async def create_reward(
    session: AsyncSession, family_id: uuid.UUID, title: str, icon: RewardIcon, price: int
) -> uuid.UUID:
    """Создаёт награду семьи с ценой в баллах."""
    reward = Reward(family_id=family_id, title=title, icon=RewardIcon(icon), price=price)
    session.add(reward)
    await session.flush()
    return reward.id


async def get_reward(
    session: AsyncSession, family_id: uuid.UUID, reward_id: uuid.UUID
) -> RewardInfo:
    """Возвращает награду своей семьи; чужая награда неотличима от несуществующей."""
    reward = await session.scalar(
        select(Reward).where(Reward.id == reward_id, Reward.family_id == family_id)
    )
    if reward is None:
        raise RewardNotFoundError("Награда не найдена")
    return RewardInfo(id=reward.id, title=reward.title, icon=reward.icon, price=reward.price)


async def list_offers(
    session: AsyncSession, family_id: uuid.UUID, member_id: uuid.UUID
) -> list[RewardOffer]:
    """Возвращает награды семьи с тем, хватает ли участнику баллов и сколько не хватает."""
    available = (await ledger.get_balance(session, member_id)).available
    waiting = set(
        await session.scalars(
            select(RewardPurchase.reward_id).where(
                RewardPurchase.child_member_id == member_id,
                RewardPurchase.status == PurchaseStatus.PENDING,
            )
        )
    )
    rewards = await session.scalars(
        select(Reward).where(Reward.family_id == family_id).order_by(Reward.price, Reward.title)
    )
    return [
        RewardOffer(
            id=r.id,
            title=r.title,
            icon=r.icon,
            price=r.price,
            affordable=available >= r.price,
            missing=max(0, r.price - available),
            waiting=r.id in waiting,
        )
        for r in rewards
    ]


async def buy(
    session: AsyncSession, family_id: uuid.UUID, reward_id: uuid.UUID, child_member_id: uuid.UUID
) -> PurchaseView:
    """Покупает награду: баллы откладываются под блокировкой счёта до выдачи взрослым."""
    reward = await get_reward(session, family_id, reward_id)
    purchase = RewardPurchase(
        family_id=family_id,
        reward_id=reward.id,
        child_member_id=child_member_id,
        price=reward.price,
        status=PurchaseStatus.PENDING,
    )
    session.add(purchase)
    await session.flush()
    await ledger.reserve(session, child_member_id, reward.price, purchase.id)
    return (await _purchase_views(session, family_id, [purchase]))[0]


async def list_pending_purchases(session: AsyncSession, family_id: uuid.UUID) -> list[PurchaseView]:
    """Возвращает купленные награды, которые взрослые ещё не выдали."""
    purchases = await session.scalars(
        select(RewardPurchase)
        .where(
            RewardPurchase.family_id == family_id,
            RewardPurchase.status == PurchaseStatus.PENDING,
        )
        .order_by(RewardPurchase.created_at)
    )
    return await _purchase_views(session, family_id, list(purchases))


async def _lock_pending(
    session: AsyncSession, family_id: uuid.UUID, purchase_id: uuid.UUID
) -> RewardPurchase:
    purchase = await session.scalar(
        select(RewardPurchase)
        .where(RewardPurchase.id == purchase_id, RewardPurchase.family_id == family_id)
        .with_for_update()
    )
    if purchase is None:
        raise PurchaseNotFoundError("Покупка не найдена")
    if purchase.status is not PurchaseStatus.PENDING:
        raise PurchaseAlreadyResolvedError(
            "Награда уже выдана"
            if purchase.status is PurchaseStatus.GIVEN
            else "Покупка уже отменена"
        )
    return purchase


async def give(session: AsyncSession, family_id: uuid.UUID, purchase_id: uuid.UUID) -> PurchaseView:
    """Отмечает награду выданной: резерв превращается в окончательное списание."""
    purchase = await _lock_pending(session, family_id, purchase_id)
    purchase.status = PurchaseStatus.GIVEN
    purchase.resolved_at = now_utc()
    await ledger.spend(session, purchase.child_member_id, purchase.price, purchase.id)
    return (await _purchase_views(session, family_id, [purchase]))[0]


async def cancel(
    session: AsyncSession, family_id: uuid.UUID, purchase_id: uuid.UUID, reason: str
) -> PurchaseView:
    """Отменяет покупку с причиной: отложенные баллы снова можно тратить."""
    purchase = await _lock_pending(session, family_id, purchase_id)
    purchase.status = PurchaseStatus.CANCELLED
    purchase.cancel_reason = reason
    purchase.resolved_at = now_utc()
    await ledger.release(session, purchase.child_member_id, purchase.price, purchase.id)
    return (await _purchase_views(session, family_id, [purchase]))[0]


async def purchase_titles(
    session: AsyncSession, family_id: uuid.UUID, purchase_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Возвращает названия купленных наград по идентификаторам покупок."""
    rows = await session.execute(
        select(RewardPurchase.id, Reward.title)
        .join(Reward, Reward.id == RewardPurchase.reward_id)
        .where(RewardPurchase.family_id == family_id, RewardPurchase.id.in_(purchase_ids))
    )
    return {row.id: row.title for row in rows}
