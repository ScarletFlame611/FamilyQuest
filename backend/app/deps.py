import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.modules.child_mode import service as child_mode
from app.modules.families.enums import MemberRole

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentMember:
    member_id: uuid.UUID
    family_id: uuid.UUID
    role: MemberRole
    child_session_id: uuid.UUID | None


async def current_member(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentMember:
    if credentials is None:
        raise UnauthorizedError("Нужно войти")
    claims = decode_access_token(credentials.credentials)
    if claims is None or claims.role not in set(MemberRole):
        raise UnauthorizedError("Нужно войти заново")
    member = CurrentMember(
        member_id=claims.member_id,
        family_id=claims.family_id,
        role=MemberRole(claims.role),
        child_session_id=claims.child_session_id,
    )
    if member.role is MemberRole.CHILD and not (
        member.child_session_id
        and await child_mode.is_session_active(session, member.child_session_id, member.member_id)
    ):
        raise UnauthorizedError("Детский режим завершён")
    return member


MemberDep = Annotated[CurrentMember, Depends(current_member)]


async def require_adult(member: MemberDep) -> CurrentMember:
    if member.role is not MemberRole.ADULT:
        raise ForbiddenError("Это действие доступно только взрослым")
    return member


async def require_child(member: MemberDep) -> CurrentMember:
    if member.role is not MemberRole.CHILD:
        raise ForbiddenError("Это действие доступно только в детском режиме")
    return member


AdultDep = Annotated[CurrentMember, Depends(require_adult)]
ChildDep = Annotated[CurrentMember, Depends(require_child)]
