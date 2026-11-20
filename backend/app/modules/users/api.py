from typing import Annotated

from fastapi import APIRouter, Path, status

from app.deps import SessionDep
from app.modules.families import service as families
from app.modules.users import service
from app.modules.users.schemas import (
    AcceptInviteIn,
    InviteInfoOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenOut,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, session: SessionDep) -> TokenOut:
    tokens = await service.register(
        session,
        body.email,
        body.password,
        body.name.strip(),
        body.avatar,
        body.family_name.strip(),
    )
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/login")
async def login(body: LoginIn, session: SessionDep) -> TokenOut:
    try:
        tokens = await service.login(session, body.email, body.password)
    except service.InvalidCredentialsError:
        # Счётчик неудачных попыток должен сохраниться, хотя запрос завершится ошибкой
        await session.commit()
        raise
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/refresh")
async def refresh(body: RefreshIn, session: SessionDep) -> TokenOut:
    tokens = await service.refresh(session, body.refresh_token)
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: RefreshIn, session: SessionDep) -> None:
    await service.logout(session, body.refresh_token)
    await session.commit()


InviteToken = Annotated[str, Path(min_length=16, max_length=100)]


@router.get("/invites/{token}")
async def invite(token: InviteToken, session: SessionDep) -> InviteInfoOut:
    info = await families.get_invite(session, token)
    return InviteInfoOut(
        family_name=info.family_name, invited_by=info.invited_by, expires_at=info.expires_at
    )


@router.post("/invites/{token}/accept", status_code=status.HTTP_201_CREATED)
async def accept_invite(token: InviteToken, body: AcceptInviteIn, session: SessionDep) -> TokenOut:
    tokens = await service.accept_invite(
        session, token, body.email, body.password, body.name.strip(), body.avatar
    )
    await session.commit()
    return TokenOut(access_token=tokens.access_token, refresh_token=tokens.refresh_token)
