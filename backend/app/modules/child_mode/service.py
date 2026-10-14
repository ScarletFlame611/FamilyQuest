import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.errors import ConflictError, InvalidInputError, NotFoundError, UnauthorizedError
from app.modules.child_mode.enums import SERVER_EVENTS, ChildEventType
from app.modules.child_mode.models import ChildEvent, ChildSession
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


class ChildSessionNotFoundError(NotFoundError):
    pass


class ServerOnlyEventError(InvalidInputError):
    pass


@dataclass(frozen=True)
class ClientEvent:
    type: ChildEventType
    detail: str | None
    # Сколько миллисекунд назад по часам телефона случилось событие. Абсолютное
    # время телефона не берём: часы на нём могут спешить или отставать
    ago_ms: int


@dataclass(frozen=True)
class SessionView:
    id: uuid.UUID
    child_member_id: uuid.UUID
    child_name: str
    started_by_name: str
    started_at: datetime
    ended_at: datetime | None
    events: int


@dataclass(frozen=True)
class EventView:
    type: ChildEventType
    detail: str | None
    occurred_at: datetime
    seconds_from_start: float


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
    await record_event(session, child_session_id, ChildEventType.PIN_EXIT)
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
    await record_event(session, child_session_id, ChildEventType.PASSWORD_EXIT)
    await _end(session, child_session_id)
    return await users.issue_tokens(session, adult_id, family_id, MemberRole.ADULT)


async def record_event(
    session: AsyncSession,
    child_session_id: uuid.UUID,
    event_type: ChildEventType,
    detail: str | None = None,
) -> None:
    """Записывает событие детской сессии, которое сервер видит сам."""
    session.add(
        ChildEvent(
            child_session_id=child_session_id,
            type=event_type,
            detail=detail[:200] if detail else None,
            occurred_at=now_utc(),
        )
    )
    await session.flush()


async def record_client_events(
    session: AsyncSession, child_session_id: uuid.UUID, events: list[ClientEvent]
) -> None:
    """Записывает пачку событий экранов, присланную детским режимом."""
    if any(event.type in SERVER_EVENTS for event in events):
        raise ServerOnlyEventError("Такие события сервер записывает сам")
    started_at = await session.scalar(
        select(ChildSession.created_at).where(ChildSession.id == child_session_id)
    )
    if started_at is None:
        raise ChildSessionNotFoundError("Детская сессия не найдена")
    now = now_utc()
    for event in events:
        occurred = now - timedelta(milliseconds=max(0, event.ago_ms))
        session.add(
            ChildEvent(
                child_session_id=child_session_id,
                type=event.type,
                detail=event.detail[:200] if event.detail else None,
                occurred_at=max(occurred, started_at),
            )
        )
    await session.flush()


async def list_sessions(session: AsyncSession, family_id: uuid.UUID) -> list[SessionView]:
    """Возвращает детские сессии семьи, новые сверху, с числом событий."""
    names = {m.id: m.name for m in await families.list_members(session, family_id)}
    counts = (
        select(ChildEvent.child_session_id, func.count().label("n"))
        .group_by(ChildEvent.child_session_id)
        .subquery()
    )
    rows = await session.execute(
        select(ChildSession, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.child_session_id == ChildSession.id)
        .where(ChildSession.child_member_id.in_(list(names)))
        .order_by(ChildSession.created_at.desc())
    )
    return [
        SessionView(
            id=child_session.id,
            child_member_id=child_session.child_member_id,
            child_name=names.get(child_session.child_member_id, ""),
            started_by_name=names.get(child_session.started_by_member_id, ""),
            started_at=child_session.created_at,
            ended_at=child_session.ended_at,
            events=int(n),
        )
        for child_session, n in rows.tuples()
    ]


async def session_events(
    session: AsyncSession, family_id: uuid.UUID, child_session_id: uuid.UUID
) -> tuple[SessionView, list[EventView]]:
    """Возвращает события детской сессии своей семьи со временем от её начала."""
    view = next(
        (s for s in await list_sessions(session, family_id) if s.id == child_session_id), None
    )
    if view is None:
        raise ChildSessionNotFoundError("Детская сессия не найдена")
    events = await session.scalars(
        select(ChildEvent)
        .where(ChildEvent.child_session_id == child_session_id)
        .order_by(ChildEvent.occurred_at, ChildEvent.id)
    )
    return view, [
        EventView(
            type=event.type,
            detail=event.detail,
            occurred_at=event.occurred_at,
            seconds_from_start=round((event.occurred_at - view.started_at).total_seconds(), 1),
        )
        for event in events
    ]
