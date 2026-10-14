import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.child_mode.models import ChildSession


async def is_session_active(
    session: AsyncSession, child_session_id: uuid.UUID, child_member_id: uuid.UUID
) -> bool:
    """Проверяет, что детская сессия этого ребёнка не завершена на сервере."""
    found = await session.scalar(
        select(ChildSession.id).where(
            ChildSession.id == child_session_id,
            ChildSession.child_member_id == child_member_id,
            ChildSession.ended_at.is_(None),
        )
    )
    return found is not None
