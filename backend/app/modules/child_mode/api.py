import uuid
from dataclasses import asdict

from fastapi import APIRouter, Response, status

from app.core.errors import InvalidInputError, TooManyAttemptsError, UnauthorizedError
from app.deps import AdultDep, ChildDep, SessionDep
from app.modules.child_mode import service
from app.modules.child_mode.enums import ChildEventType
from app.modules.child_mode.schemas import (
    ChildEventOut,
    ChildSessionOut,
    EventsIn,
    PasswordIn,
    PinErrorOut,
    PinIn,
    SessionEventsOut,
    StartIn,
)
from app.modules.families.service import PinLockedError, WrongPinError
from app.modules.users import service as users
from app.modules.users.schemas import TokenOut

router = APIRouter(prefix="/api/child-mode", tags=["child-mode"])

ATTEMPT_ERRORS = {
    401: {"model": PinErrorOut},
    422: {"model": PinErrorOut},
    429: {"model": PinErrorOut},
}


@router.post("/start")
async def start(body: StartIn, adult: AdultDep, session: SessionDep) -> TokenOut:
    tokens = await service.start(session, adult.family_id, adult.member_id, body.child_id)
    if body.adult_refresh_token:
        await users.logout(session, body.adult_refresh_token)
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/exit", responses=ATTEMPT_ERRORS)
async def exit_with_pin(body: PinIn, child: ChildDep, session: SessionDep) -> TokenOut:
    try:
        tokens = await service.exit_with_pin(
            session, child.family_id, child.child_session_id, body.pin
        )
    except (UnauthorizedError, TooManyAttemptsError) as error:
        # Счётчик неверных попыток должен сохраниться, хотя запрос завершится ошибкой
        if isinstance(error, WrongPinError | PinLockedError):
            locked = isinstance(error, PinLockedError)
            event = ChildEventType.PIN_LOCKED if locked else ChildEventType.WRONG_PIN
            await service.record_event(session, child.child_session_id, event)
        await session.commit()
        raise
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/exit-with-password", responses=ATTEMPT_ERRORS)
async def exit_with_password(body: PasswordIn, child: ChildDep, session: SessionDep) -> TokenOut:
    try:
        tokens = await service.exit_with_password(
            session, child.family_id, child.child_session_id, body.password
        )
    except (InvalidInputError, TooManyAttemptsError):
        await session.commit()
        raise
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
async def post_events(body: EventsIn, child: ChildDep, session: SessionDep) -> None:
    await service.record_client_events(
        session,
        child.child_session_id,
        [service.ClientEvent(e.type, e.detail, e.ago_ms) for e in body.events],
    )
    await session.commit()


@router.get("/sessions")
async def sessions(adult: AdultDep, session: SessionDep) -> list[ChildSessionOut]:
    return [
        ChildSessionOut(**asdict(v)) for v in await service.list_sessions(session, adult.family_id)
    ]


@router.get("/sessions/{session_id}/events")
async def session_events(
    session_id: uuid.UUID, adult: AdultDep, session: SessionDep
) -> SessionEventsOut:
    view, events = await service.session_events(session, adult.family_id, session_id)
    return SessionEventsOut(
        session=ChildSessionOut(**asdict(view)),
        events=[ChildEventOut(**asdict(e)) for e in events],
    )


@router.get(
    "/sessions/{session_id}/events.csv",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
async def session_events_csv(
    session_id: uuid.UUID, adult: AdultDep, session: SessionDep
) -> Response:
    view, events = await service.session_events(session, adult.family_id, session_id)
    filename = f"child-session-{view.started_at:%Y%m%d-%H%M%S}.csv"
    return Response(
        service.events_csv(events),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
