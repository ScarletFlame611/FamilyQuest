import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.errors import TooManyAttemptsError, UnauthorizedError
from app.core.security import (
    AccessClaims,
    create_access_token,
    hash_refresh_token,
    hash_secret,
    new_refresh_token,
    verify_secret,
)
from app.modules.families import service as families
from app.modules.families.enums import MemberRole
from app.modules.users.models import RefreshToken, User

MAX_FAILED_LOGINS = 10
LOGIN_LOCK = timedelta(minutes=15)
# Хеш считается и для несуществующей почты, чтобы по времени ответа
# нельзя было узнать, зарегистрирована ли она
_DUMMY_HASH = hash_secret("no-such-user")


class InvalidCredentialsError(UnauthorizedError):
    pass


class LoginLockedError(TooManyAttemptsError):
    pass


class InvalidRefreshTokenError(UnauthorizedError):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


async def create_user(session: AsyncSession, email: str, password: str, name: str) -> uuid.UUID:
    """Создаёт взрослый аккаунт и возвращает его идентификатор."""
    user = User(
        email=email.strip(), password_hash=hash_secret(password), name=name, failed_logins=0
    )
    session.add(user)
    await session.flush()
    return user.id


async def find_user_id_by_email(session: AsyncSession, email: str) -> uuid.UUID | None:
    """Ищет аккаунт по почте без учёта регистра."""
    return await session.scalar(
        select(User.id).where(func.lower(User.email) == email.strip().lower())
    )


async def delete_users(session: AsyncSession, user_ids: list[uuid.UUID]) -> None:
    """Удаляет аккаунты вместе с их участием в семьях."""
    await session.execute(delete(User).where(User.id.in_(user_ids)))


async def verify_password(session: AsyncSession, user_id: uuid.UUID, password: str) -> bool:
    """Проверяет пароль аккаунта без учёта блокировки входа."""
    password_hash = await session.scalar(select(User.password_hash).where(User.id == user_id))
    return password_hash is not None and verify_secret(password_hash, password)


async def issue_tokens(
    session: AsyncSession,
    member_id: uuid.UUID,
    family_id: uuid.UUID,
    role: MemberRole,
    child_session_id: uuid.UUID | None = None,
) -> TokenPair:
    """Выдаёт access-токен и сохраняет хеш нового refresh-токена."""
    refresh = new_refresh_token()
    session.add(
        RefreshToken(
            token_hash=hash_refresh_token(refresh),
            member_id=member_id,
            family_id=family_id,
            role=role,
            child_session_id=child_session_id,
            expires_at=now_utc() + timedelta(days=get_settings().refresh_token_ttl_days),
        )
    )
    await session.flush()
    access = create_access_token(AccessClaims(member_id, family_id, role, child_session_id))
    return TokenPair(access_token=access, refresh_token=refresh)


async def login(session: AsyncSession, email: str, password: str) -> TokenPair:
    """Входит по почте и паролю; после 10 неудач подряд вход закрывается на 15 минут."""
    user = await session.scalar(
        select(User).where(func.lower(User.email) == email.strip().lower()).with_for_update()
    )
    if user is None:
        verify_secret(_DUMMY_HASH, password)
        raise InvalidCredentialsError("Неверная почта или пароль")
    now = now_utc()
    if user.login_locked_until and user.login_locked_until > now:
        raise LoginLockedError("Слишком много неудачных попыток. Попробуйте через 15 минут")
    if not verify_secret(user.password_hash, password):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.failed_logins = 0
            user.login_locked_until = now + LOGIN_LOCK
        await session.flush()
        raise InvalidCredentialsError("Неверная почта или пароль")
    user.failed_logins = 0
    user.login_locked_until = None
    membership = await families.get_adult_membership(session, user.id)
    return await issue_tokens(session, membership.member_id, membership.family_id, MemberRole.ADULT)


async def refresh(session: AsyncSession, refresh_token: str) -> TokenPair:
    """Меняет refresh-токен на новую пару; старый токен больше не действует."""
    token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(refresh_token))
        .with_for_update()
    )
    if token is None or token.revoked_at is not None or token.expires_at <= now_utc():
        raise InvalidRefreshTokenError("Сессия истекла, войдите заново")
    token.revoked_at = now_utc()
    return await issue_tokens(
        session, token.member_id, token.family_id, token.role, token.child_session_id
    )


async def logout(session: AsyncSession, refresh_token: str) -> None:
    """Отзывает refresh-токен на сервере."""
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == hash_refresh_token(refresh_token),
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now_utc())
    )


async def revoke_child_session_tokens(session: AsyncSession, child_session_id: uuid.UUID) -> None:
    """Отзывает все refresh-токены завершённой детской сессии."""
    await session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.child_session_id == child_session_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now_utc())
    )
