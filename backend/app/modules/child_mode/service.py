import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.errors import ConflictError, InvalidInputError, UnauthorizedError
from app.modules.child_mode.models import ChildSession
from app.modules.families import service as families
from app.modules.families.enums import MemberRole
from app.modules.users import service as users
from app.modules.users.service import TokenPair


class NotAChildError(InvalidInputError):
    pass


class PinNotSetError(ConflictError):
    pass


class ChildSessionEndedError(UnauthorizedError):
    pass


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


async def start(
    session: AsyncSession,
    family_id: uuid.UUID,
    adult_member_id: uuid.UUID,
    child_member_id: uuid.UUID,
) -> TokenPair:
    """Открывает детскую сессию и выдаёт токены с правами только этого ребёнка."""
    child = await families.get_member(session, family_id, child_member_id)
    if child.role is not MemberRole.CHILD:
        raise NotAChildError("Детский режим включается только для ребёнка")
    # Без PIN из детского режима нельзя было бы вернуться иначе как по паролю
    if not await families.has_pin(session, family_id):
        raise PinNotSetError("Сначала задайте PIN-код детского режима")
    child_session = ChildSession(child_member_id=child.id, started_by_member_id=adult_member_id)
    session.add(child_session)
    await session.flush()
    return await users.issue_tokens(
        session, child.id, family_id, MemberRole.CHILD, child_session.id
    )


async def _end(session: AsyncSession, child_session_id: uuid.UUID) -> uuid.UUID:
    child_session = await session.scalar(
        select(ChildSession)
        .where(ChildSession.id == child_session_id, ChildSession.ended_at.is_(None))
        .with_for_update()
    )
    if child_session is None:
        raise ChildSessionEndedError("Детский режим уже завершён")
    child_session.ended_at = now_utc()
    await users.revoke_child_session_tokens(session, child_session_id)
    return child_session.started_by_member_id


async def _started_by(session: AsyncSession, child_session_id: uuid.UUID) -> uuid.UUID:
    started_by = await session.scalar(
        select(ChildSession.started_by_member_id).where(
            ChildSession.id == child_session_id, ChildSession.ended_at.is_(None)
        )
    )
    if started_by is None:
        raise ChildSessionEndedError("Детский режим уже завершён")
    return started_by


async def exit_with_pin(
    session: AsyncSession, family_id: uuid.UUID, child_session_id: uuid.UUID, pin: str
) -> TokenPair:
    """Завершает детскую сессию по PIN и возвращает токены взрослого, который её открыл."""
    await families.check_pin(session, family_id, pin)
    adult_id = await _end(session, child_session_id)
    return await users.issue_tokens(session, adult_id, family_id, MemberRole.ADULT)


async def exit_with_password(
    session: AsyncSession, family_id: uuid.UUID, child_session_id: uuid.UUID, password: str
) -> TokenPair:
    """Завершает детскую сессию по паролю взрослого, который её открыл, и снимает блокировку PIN."""
    adult_id = await _started_by(session, child_session_id)
    user_id = await families.get_adult_user_id(session, family_id, adult_id)
    await users.check_password(session, user_id, password)
    await families.unlock_pin(session, family_id)
    await _end(session, child_session_id)
    return await users.issue_tokens(session, adult_id, family_id, MemberRole.ADULT)
