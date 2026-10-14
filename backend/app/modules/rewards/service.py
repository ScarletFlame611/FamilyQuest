import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rewards.models import Reward


async def create_reward(
    session: AsyncSession, family_id: uuid.UUID, title: str, icon: str, price: int
) -> uuid.UUID:
    """Создаёт награду семьи с ценой в баллах."""
    reward = Reward(family_id=family_id, title=title, icon=icon, price=price)
    session.add(reward)
    await session.flush()
    return reward.id
