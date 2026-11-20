import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    reached_at: datetime | None
    contributions: list[Contribution]
    feed: list[FeedItem]


@dataclass(frozen=True)
class _Progress:
    by_member: dict[uuid.UUID, int]
    reached_at: datetime | None


async def _progress(session: AsyncSession, goal: Goal) -> _Progress:
    # Момент достижения выводится из журнала, а не хранится: это первая запись,
    # на которой сумма дошла до цели. Всё, что записано позже, включая отмены,
    # прогресс достигнутой цели уже не меняет, поэтому цель не переоткрывается
    by_member: dict[uuid.UUID, int] = {}
    total = 0
    for entry in await ledger.family_earnings_timeline(session, goal.family_id, goal.created_at):
        by_member[entry.member_id] = by_member.get(entry.member_id, 0) + entry.amount
        total += entry.amount
        if total >= goal.target:
            return _Progress(by_member, entry.created_at)
    return _Progress(by_member, None)


async def create_goal(
    session: AsyncSession, family_id: uuid.UUID, title: str, icon: GoalIcon, target: int
) -> uuid.UUID:
    """Создаёт активную цель семьи, если прежняя достигнута или её нет."""
    active = await session.scalar(
        select(Goal).where(Goal.family_id == family_id, Goal.is_active).with_for_update()
    )
    if active is not None:
        if (await _progress(session, active)).reached_at is None:
            raise ActiveGoalExistsError("Сначала семья должна накопить на текущую цель")
        active.is_active = False
    goal = Goal(
        family_id=family_id, title=title, icon=GoalIcon(icon), target=target, is_active=True
    )
    try:
        # Две одновременные попытки создать первую цель упираются в уникальный
        # индекс активной цели; вторая должна получить понятный отказ, а не 500
        async with session.begin_nested():
            session.add(goal)
    except IntegrityError as error:
        if "uq_goals_active_family" not in str(error.orig):
            raise
        raise ActiveGoalExistsError("Сначала семья должна накопить на текущую цель") from None
    return goal.id


async def get_active_goal(session: AsyncSession, family_id: uuid.UUID) -> GoalView:
    """Возвращает активную цель с прогрессом, вкладом каждого участника и лентой начислений."""
    goal = await session.scalar(select(Goal).where(Goal.family_id == family_id, Goal.is_active))
    if goal is None:
        raise NoActiveGoalError("У семьи пока нет общей цели")
    members = await families.list_members(session, family_id)
    progress = await _progress(session, goal)
    recent = await ledger.recent_family_earnings(session, family_id, goal.created_at)
    titles = await tasks.task_titles(session, family_id, [e.task_id for e in recent if e.task_id])
    by_id = {m.id: m for m in members}
    contributions = [
        Contribution(m.id, m.name, m.avatar, m.role, progress.by_member.get(m.id, 0))
        for m in members
    ]
    return GoalView(
        id=goal.id,
        title=goal.title,
        icon=goal.icon,
        target=goal.target,
        progress=sum(c.points for c in contributions),
        reached=progress.reached_at is not None,
        reached_at=progress.reached_at,
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
