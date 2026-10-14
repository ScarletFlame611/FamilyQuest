import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.modules.ledger import service as ledger
from app.modules.tasks.enums import TaskStatus
from app.modules.tasks.models import Task


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
