import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.modules.families import service as families
from app.modules.families.enums import MemberRole
from app.modules.goals.enums import GoalIcon
from app.modules.goals.models import Goal
from app.modules.ledger import service as ledger
from app.modules.tasks import service as tasks


class ActiveGoalExistsError(ConflictError):
    pass


class NoActiveGoalError(NotFoundError):
    pass


@dataclass(frozen=True)
class Contribution:
    member_id: uuid.UUID
    name: str
    avatar: str
    role: MemberRole
    points: int


@dataclass(frozen=True)
class FeedItem:
    member_id: uuid.UUID
    name: str
    avatar: str
    title: str
    points: int
    created_at: datetime


@dataclass(frozen=True)
class GoalView:
    id: uuid.UUID
    title: str
    icon: str
    target: int
    progress: int
    reached: bool
    contributions: list[Contribution]
    feed: list[FeedItem]


async def create_goal(
    session: AsyncSession, family_id: uuid.UUID, title: str, icon: GoalIcon, target: int
) -> uuid.UUID:
    """Создаёт активную цель семьи; в PoC активная цель может быть только одна."""
    active = await session.scalar(
        select(Goal.id).where(Goal.family_id == family_id, Goal.is_active)
    )
    if active:
        raise ActiveGoalExistsError("У семьи уже есть активная цель")
    goal = Goal(
        family_id=family_id, title=title, icon=GoalIcon(icon), target=target, is_active=True
    )
    session.add(goal)
    await session.flush()
    return goal.id


async def get_active_goal(session: AsyncSession, family_id: uuid.UUID) -> GoalView:
    """Возвращает активную цель с прогрессом, вкладом каждого участника и лентой начислений."""
    goal = await session.scalar(select(Goal).where(Goal.family_id == family_id, Goal.is_active))
    if goal is None:
        raise NoActiveGoalError("У семьи пока нет общей цели")
    members = await families.list_members(session, family_id)
    earned = await ledger.family_earnings_since(session, family_id, goal.created_at)
    recent = await ledger.recent_family_earnings(session, family_id, goal.created_at)
    titles = await tasks.task_titles(session, family_id, [e.task_id for e in recent if e.task_id])
    by_id = {m.id: m for m in members}
    contributions = [
        Contribution(m.id, m.name, m.avatar, m.role, earned.get(m.id, 0)) for m in members
    ]
    progress = sum(c.points for c in contributions)
    return GoalView(
        id=goal.id,
        title=goal.title,
        icon=goal.icon,
        target=goal.target,
        progress=progress,
        reached=progress >= goal.target,
        contributions=contributions,
        feed=[
            FeedItem(
                member_id=e.member_id,
                name=by_id[e.member_id].name,
                avatar=by_id[e.member_id].avatar,
                title=(titles.get(e.task_id) if e.task_id else None) or e.note or "",
                points=e.amount,
                created_at=e.created_at,
            )
            for e in recent
            if e.member_id in by_id
        ],
    )
