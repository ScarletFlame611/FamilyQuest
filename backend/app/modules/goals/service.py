import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.modules.goals.models import Goal


class ActiveGoalExistsError(ConflictError):
    pass


async def create_goal(
    session: AsyncSession, family_id: uuid.UUID, title: str, icon: str, target: int
) -> uuid.UUID:
    """Создаёт активную цель семьи; в PoC активная цель может быть только одна."""
    active = await session.scalar(
        select(Goal.id).where(Goal.family_id == family_id, Goal.is_active)
    )
    if active:
        raise ActiveGoalExistsError("У семьи уже есть активная цель")
    goal = Goal(family_id=family_id, title=title, icon=icon, target=target, is_active=True)
    session.add(goal)
    await session.flush()
    return goal.id
