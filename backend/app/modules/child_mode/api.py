from fastapi import APIRouter

from app.core.errors import InvalidInputError, TooManyAttemptsError, UnauthorizedError
from app.deps import AdultDep, ChildDep, SessionDep
from app.modules.child_mode import service
from app.modules.child_mode.schemas import PasswordIn, PinErrorOut, PinIn, StartIn
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
    except (UnauthorizedError, TooManyAttemptsError):
        # Счётчик неверных попыток должен сохраниться, хотя запрос завершится ошибкой
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
