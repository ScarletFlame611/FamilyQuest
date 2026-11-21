import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.errors import ConflictError, NotFoundError
from app.core.ids import new_id
from app.modules.families import service as families
from app.modules.families.enums import MemberRole
from app.modules.ledger import service as ledger
from app.modules.rewards import service as rewards
from app.modules.tasks.enums import TaskAction, TaskIcon, TaskStatus
from app.modules.tasks.models import Task


class TaskNotFoundError(NotFoundError):
    pass


class TaskTransitionError(ConflictError):
    pass


@dataclass(frozen=True)
class TaskView:
    id: uuid.UUID
    title: str
    description: str | None
    icon: str
    points: int
    status: TaskStatus
    assignee_member_id: uuid.UUID | None
    assignee_name: str | None
    created_by_member_id: uuid.UUID
    created_by_name: str
    reject_reason: str | None
    marked_at: datetime | None
    confirmed_at: datetime | None


# Переход проверяется по действию, а не только по паре статусов: «взять» и «отклонить»
# оба ведут в assigned, но допустимы из разных состояний
TRANSITIONS = {
    TaskAction.TAKE: (TaskStatus.OPEN, TaskStatus.ASSIGNED),
    TaskAction.MARK: (TaskStatus.ASSIGNED, TaskStatus.MARKED),
    TaskAction.CONFIRM: (TaskStatus.MARKED, TaskStatus.CONFIRMED),
    TaskAction.REJECT: (TaskStatus.MARKED, TaskStatus.ASSIGNED),
    TaskAction.REVOKE: (TaskStatus.CONFIRMED, TaskStatus.ASSIGNED),
}

TRANSITION_ERRORS = {
    TaskStatus.OPEN: "Дело лежит на общей доске, его сначала нужно взять",
    TaskStatus.ASSIGNED: "Дело ещё не отмечено выполненным",
    TaskStatus.MARKED: "Дело уже отмечено и ждёт проверки",
    TaskStatus.CONFIRMED: "Дело уже засчитано",
}


def _transition(task: Task, action: TaskAction) -> None:
    source, target = TRANSITIONS[action]
    if task.status is not source:
        message = TRANSITION_ERRORS[task.status]
        if action is TaskAction.TAKE and task.status is not TaskStatus.OPEN:
            message = "Это дело уже кто-то взял"
        if action is TaskAction.REVOKE:
            message = "Отменить можно только засчитанное дело"
        raise TaskTransitionError(message)
    task.status = target


async def _views(session: AsyncSession, family_id: uuid.UUID, tasks: list[Task]) -> list[TaskView]:
    names = {m.id: m.name for m in await families.list_members(session, family_id)}
    return [
        TaskView(
            id=task.id,
            title=task.title,
            description=task.description,
            icon=task.icon,
            points=task.points,
            status=task.status,
            assignee_member_id=task.assignee_member_id,
            assignee_name=names.get(task.assignee_member_id) if task.assignee_member_id else None,
            created_by_member_id=task.created_by_member_id,
            created_by_name=names.get(task.created_by_member_id, ""),
            reject_reason=task.reject_reason,
            marked_at=task.marked_at,
            confirmed_at=task.confirmed_at,
        )
        for task in tasks
    ]


async def _view(session: AsyncSession, family_id: uuid.UUID, task: Task) -> TaskView:
    return (await _views(session, family_id, [task]))[0]


async def _lock_task(session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID) -> Task:
    task = await session.scalar(
        select(Task).where(Task.id == task_id, Task.family_id == family_id).with_for_update()
    )
    if task is None:
        raise TaskNotFoundError("Задача не найдена")
    return task


async def create_task(
    session: AsyncSession,
    family_id: uuid.UUID,
    created_by_member_id: uuid.UUID,
    title: str,
    icon: TaskIcon,
    points: int,
    assignee_member_id: uuid.UUID | None,
    description: str | None = None,
) -> TaskView:
    """Создаёт задачу на участника своей семьи или, без исполнителя, на общей доске."""
    if assignee_member_id:
        await families.get_member(session, family_id, assignee_member_id)
    task = Task(
        family_id=family_id,
        created_by_member_id=created_by_member_id,
        title=title,
        description=description,
        icon=TaskIcon(icon),
        points=points,
        assignee_member_id=assignee_member_id,
        status=TaskStatus.ASSIGNED if assignee_member_id else TaskStatus.OPEN,
    )
    session.add(task)
    await session.flush()
    return await _view(session, family_id, task)


async def record_completed_task(
    session: AsyncSession,
    family_id: uuid.UUID,
    created_by_member_id: uuid.UUID,
    assignee_member_id: uuid.UUID,
    title: str,
    icon: TaskIcon,
    points: int,
) -> uuid.UUID:
    """Записывает уже засчитанное дело вместе с начислением, для истории семьи."""
    now = now_utc()
    task = Task(
        family_id=family_id,
        created_by_member_id=created_by_member_id,
        assignee_member_id=assignee_member_id,
        title=title,
        icon=TaskIcon(icon),
        points=points,
        status=TaskStatus.CONFIRMED,
        marked_at=now,
        confirmed_at=now,
    )
    session.add(task)
    await session.flush()
    await ledger.accrue(
        session, assignee_member_id, points, task_id=task.id, task_attempt=task.attempt
    )
    return task.id


async def get_task(session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID) -> TaskView:
    """Возвращает задачу своей семьи; чужая задача неотличима от несуществующей."""
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.family_id == family_id))
    if task is None:
        raise TaskNotFoundError("Задача не найдена")
    return await _view(session, family_id, task)


async def _family_day_start(session: AsyncSession, family_id: uuid.UUID) -> datetime:
    family = await families.get_family(session, family_id)
    # «Сегодня» считается в часовом поясе семьи, а не сервера
    zone = ZoneInfo(family.timezone)
    return datetime.combine(now_utc().astimezone(zone).date(), time.min, tzinfo=zone)


async def list_my_tasks(
    session: AsyncSession, family_id: uuid.UUID, member_id: uuid.UUID
) -> list[TaskView]:
    """Возвращает дела участника: сначала невыполненные, потом засчитанные сегодня."""
    day_start = await _family_day_start(session, family_id)
    tasks = list(
        await session.scalars(
            select(Task)
            .where(
                Task.family_id == family_id,
                Task.assignee_member_id == member_id,
                or_(Task.status != TaskStatus.CONFIRMED, Task.confirmed_at >= day_start),
            )
            .order_by(Task.created_at)
        )
    )
    tasks.sort(key=lambda task: task.status is TaskStatus.CONFIRMED)
    return await _views(session, family_id, tasks)


async def list_family_tasks(session: AsyncSession, family_id: uuid.UUID) -> list[TaskView]:
    """Возвращает все дела семьи для общей доски: незавершённые и засчитанные сегодня."""
    day_start = await _family_day_start(session, family_id)
    tasks = await session.scalars(
        select(Task)
        .where(
            Task.family_id == family_id,
            or_(Task.status != TaskStatus.CONFIRMED, Task.confirmed_at >= day_start),
        )
        .order_by(Task.created_at)
    )
    return await _views(session, family_id, list(tasks))


async def list_all_tasks(session: AsyncSession, family_id: uuid.UUID) -> list[TaskView]:
    """Возвращает все дела семьи за всё время, старые сверху."""
    tasks = await session.scalars(
        select(Task).where(Task.family_id == family_id).order_by(Task.created_at)
    )
    return await _views(session, family_id, list(tasks))


async def list_board(session: AsyncSession, family_id: uuid.UUID) -> list[TaskView]:
    """Возвращает дела на общей доске семьи, которые ещё никто не взял."""
    tasks = await session.scalars(
        select(Task)
        .where(Task.family_id == family_id, Task.status == TaskStatus.OPEN)
        .order_by(Task.created_at)
    )
    return await _views(session, family_id, list(tasks))


async def list_pending(session: AsyncSession, family_id: uuid.UUID) -> list[TaskView]:
    """Возвращает дела детей, которые ждут подтверждения взрослого."""
    tasks = await session.scalars(
        select(Task)
        .where(Task.family_id == family_id, Task.status == TaskStatus.MARKED)
        .order_by(Task.marked_at)
    )
    return await _views(session, family_id, list(tasks))


async def take(
    session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID, member_id: uuid.UUID
) -> TaskView:
    """Берёт дело с общей доски; из одновременных запросов успешен только первый."""
    task = await _lock_task(session, family_id, task_id)
    _transition(task, TaskAction.TAKE)
    task.assignee_member_id = member_id
    await session.flush()
    return await _view(session, family_id, task)


async def mark(
    session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID, member_id: uuid.UUID
) -> TaskView:
    """Отмечает своё дело: дело ребёнка ждёт взрослого, дело взрослого засчитывается сразу."""
    task = await _lock_task(session, family_id, task_id)
    if task.assignee_member_id != member_id:
        # Чужое дело выглядит так же, как несуществующее
        raise TaskNotFoundError("Задача не найдена")
    _transition(task, TaskAction.MARK)
    task.marked_at = now_utc()
    task.reject_reason = None
    assignee = await families.get_member(session, family_id, member_id)
    if assignee.role is MemberRole.ADULT:
        _transition(task, TaskAction.CONFIRM)
        task.confirmed_at = task.marked_at
        await ledger.accrue(
            session, member_id, task.points, task_id=task.id, task_attempt=task.attempt
        )
    await session.flush()
    return await _view(session, family_id, task)


async def reject(
    session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID, reason: str
) -> TaskView:
    """Возвращает отмеченное дело исполнителю с причиной, без баллов."""
    task = await _lock_task(session, family_id, task_id)
    _transition(task, TaskAction.REJECT)
    task.reject_reason = reason
    task.marked_at = None
    await session.flush()
    return await _view(session, family_id, task)


async def confirm(session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID) -> TaskView:
    """Засчитывает отмеченное дело: статус и начисление меняются в одной транзакции."""
    task = await _lock_task(session, family_id, task_id)
    _transition(task, TaskAction.CONFIRM)
    task.confirmed_at = now_utc()
    if task.assignee_member_id is None:
        raise TaskTransitionError("У дела нет исполнителя")
    await ledger.accrue(
        session,
        task.assignee_member_id,
        task.points,
        task_id=task.id,
        task_attempt=task.attempt,
    )
    await session.flush()
    return await _view(session, family_id, task)


@dataclass(frozen=True)
class RevokeResult:
    task: TaskView
    cancelled_purchases: list[str]


async def revoke(
    session: AsyncSession,
    family_id: uuid.UUID,
    task_id: uuid.UUID,
    reason: str,
    adult_member_id: uuid.UUID,
) -> RevokeResult:
    """Отменяет подтверждение: сторно в журнале, дело возвращается исполнителю с причиной."""
    task = await _lock_task(session, family_id, task_id)
    _transition(task, TaskAction.REVOKE)
    window = (await families.get_family(session, family_id)).revoke_window_days
    if task.confirmed_at and now_utc() - task.confirmed_at > timedelta(days=window):
        raise TaskTransitionError(f"Подтверждение можно отменить только в течение {window} дней")
    if task.assignee_member_id is None:
        raise TaskTransitionError("У дела нет исполнителя")
    assignee = task.assignee_member_id
    # Порядок блокировок: задача, затем счёт (внутри сторно), затем покупки
    await ledger.reverse_task_accrual(
        session, assignee, task.id, task.attempt, reason, adult_member_id
    )
    task.attempt += 1
    task.reject_reason = reason
    task.marked_at = None
    task.confirmed_at = None
    cancelled = await rewards.cancel_unaffordable_purchases(
        session,
        family_id,
        assignee,
        f"Покупка отменена, потому что отменено дело «{task.title}»",
    )
    await session.flush()
    return RevokeResult(await _view(session, family_id, task), [p.title for p in cancelled])


@dataclass(frozen=True)
class SkippedTask:
    task_id: uuid.UUID
    title: str
    reason: str


@dataclass(frozen=True)
class ConfirmManyResult:
    confirmed: list[TaskView]
    skipped: list[SkippedTask]


async def confirm_many(
    session: AsyncSession, family_id: uuid.UUID, task_ids: list[uuid.UUID]
) -> ConfirmManyResult:
    """Засчитывает пачку отмеченных дел одной транзакцией; уже засчитанные пропускает."""
    ids = sorted(set(task_ids))
    # Задачи блокируются в порядке идентификатора, а счета — после них и тоже по порядку:
    # так одновременные пачки двух взрослых не ждут друг друга по кругу
    tasks = list(
        await session.scalars(
            select(Task)
            .where(Task.id.in_(ids), Task.family_id == family_id)
            .order_by(Task.id)
            .with_for_update()
        )
    )
    if len(tasks) != len(ids):
        # Чужая или несуществующая задача в пачке — так же, как и по одной
        raise TaskNotFoundError("Задача не найдена")
    ready = [t for t in tasks if t.status is TaskStatus.MARKED and t.assignee_member_id]
    skipped = [
        SkippedTask(t.id, t.title, TRANSITION_ERRORS[t.status]) for t in tasks if t not in ready
    ]
    await ledger.lock_accounts(session, [t.assignee_member_id for t in ready])
    now = now_utc()
    for task in ready:
        _transition(task, TaskAction.CONFIRM)
        task.confirmed_at = now
        await ledger.accrue(
            session,
            task.assignee_member_id,
            task.points,
            task_id=task.id,
            task_attempt=task.attempt,
        )
    await session.flush()
    return ConfirmManyResult(await _views(session, family_id, ready), skipped)


async def task_titles(
    session: AsyncSession, family_id: uuid.UUID, task_ids: list[uuid.UUID]
) -> dict[uuid.UUID, str]:
    """Возвращает названия задач своей семьи по идентификаторам."""
    rows = await session.execute(
        select(Task.id, Task.title).where(Task.family_id == family_id, Task.id.in_(task_ids))
    )
    return {row.id: row.title for row in rows}


async def create_assigned_tasks(
    session: AsyncSession,
    family_id: uuid.UUID,
    created_by_member_id: uuid.UUID,
    assignee_member_id: uuid.UUID,
    tasks: list[tuple[str, TaskIcon, int]],
) -> None:
    """Создаёт пачку назначенных дел одной вставкой, для подготовки нагрузочных данных."""
    await session.execute(
        insert(Task),
        [
            {
                "id": new_id(),
                "family_id": family_id,
                "created_by_member_id": created_by_member_id,
                "assignee_member_id": assignee_member_id,
                "title": title,
                "icon": TaskIcon(icon),
                "points": points,
                "status": TaskStatus.ASSIGNED,
                "created_at": now_utc(),
            }
            for title, icon, points in tasks
        ],
    )
