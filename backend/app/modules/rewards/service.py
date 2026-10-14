import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.modules.rewards.models import Reward


class RewardNotFoundError(NotFoundError):
    pass


@dataclass(frozen=True)
class RewardInfo:
    id: uuid.UUID
    title: str
    icon: str
    price: int


async def create_reward(
    session: AsyncSession, family_id: uuid.UUID, title: str, icon: str, price: int
) -> uuid.UUID:
    """Создаёт награду семьи с ценой в баллах."""
    reward = Reward(family_id=family_id, title=title, icon=icon, price=price)
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
