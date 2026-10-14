import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

import anyio.to_thread
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.clock import now_utc
from app.core.config import get_settings

_hasher = PasswordHasher()


def _verify_sync(secret_hash: str, secret: str) -> bool:
    try:
        return _hasher.verify(secret_hash, secret)
    except (VerificationError, InvalidHashError):
        return False


# argon2 нарочно медленный; в потоке он не останавливает обработку других запросов
async def hash_secret(secret: str) -> str:
    return await anyio.to_thread.run_sync(_hasher.hash, secret)


async def verify_secret(secret_hash: str, secret: str) -> bool:
    return await anyio.to_thread.run_sync(_verify_sync, secret_hash, secret)


@dataclass(frozen=True)
class AccessClaims:
    member_id: uuid.UUID
    family_id: uuid.UUID
    role: str
    child_session_id: uuid.UUID | None


def create_access_token(claims: AccessClaims) -> str:
    settings = get_settings()
    now = now_utc()
    payload = {
        "sub": str(claims.member_id),
        "fam": str(claims.family_id),
        "role": claims.role,
        "csid": str(claims.child_session_id) if claims.child_session_id else None,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access_token(token: str) -> AccessClaims | None:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["sub", "fam", "role", "exp"]},
        )
        return AccessClaims(
            member_id=uuid.UUID(payload["sub"]),
            family_id=uuid.UUID(payload["fam"]),
            role=payload["role"],
            child_session_id=uuid.UUID(payload["csid"]) if payload.get("csid") else None,
        )
    except (jwt.InvalidTokenError, ValueError, KeyError):
        return None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # У refresh-токена 256 бит случайности, перебор не грозит: медленный argon2 не нужен,
    # а быстрый SHA-256 позволяет искать токен по хешу через индекс
    return hashlib.sha256(token.encode()).hexdigest()
