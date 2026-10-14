import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.errors import NotFoundError
from app.modules.ledger import service as ledger
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task


class TaskNotFoundError(NotFoundError):
    pass


@dataclass(frozen=True)
class TaskInfo:
    id: uuid.UUID
    title: str
    icon: str
    points: int
    status: TaskStatus
    assignee_member_id: uuid.UUID | None
    created_by_member_id: uuid.UUID
    reject_reason: str | None


def _info(task: Task) -> TaskInfo:
    return TaskInfo(
        id=task.id,
        title=task.title,
        icon=task.icon,
        points=task.points,
        status=task.status,
        assignee_member_id=task.assignee_member_id,
        created_by_member_id=task.created_by_member_id,
        reject_reason=task.reject_reason,
    )


async def create_task(
    session: AsyncSession,
    family_id: uuid.UUID,
    created_by_member_id: uuid.UUID,
    title: str,
    icon: str,
    points: int,
    assignee_member_id: uuid.UUID | None,
) -> uuid.UUID:
    """Создаёт задачу на участника или, без исполнителя, на общей доске."""
    task = Task(
        family_id=family_id,
        created_by_member_id=created_by_member_id,
        title=title,
        icon=icon,
        points=points,
        assignee_member_id=assignee_member_id,
        status=TaskStatus.ASSIGNED if assignee_member_id else TaskStatus.OPEN,
    )
    session.add(task)
    await session.flush()
    return task.id


async def record_completed_task(
    session: AsyncSession,
    family_id: uuid.UUID,
    created_by_member_id: uuid.UUID,
    assignee_member_id: uuid.UUID,
    title: str,
    icon: str,
    points: int,
) -> uuid.UUID:
    """Записывает уже засчитанное дело вместе с начислением, для истории семьи."""
    now = now_utc()
    task = Task(
        family_id=family_id,
        created_by_member_id=created_by_member_id,
        assignee_member_id=assignee_member_id,
        title=title,
        icon=icon,
        points=points,
        status=TaskStatus.CONFIRMED,
        marked_at=now,
        confirmed_at=now,
    )
    session.add(task)
    await session.flush()
    await ledger.accrue(session, assignee_member_id, points, task_id=task.id)
    return task.id


async def get_task(session: AsyncSession, family_id: uuid.UUID, task_id: uuid.UUID) -> TaskInfo:
    """Возвращает задачу своей семьи; чужая задача неотличима от несуществующей."""
    task = await session.scalar(select(Task).where(Task.id == task_id, Task.family_id == family_id))
    if task is None:
        raise TaskNotFoundError("Задача не найдена")
    return _info(task)
