import uuid

from fastapi import APIRouter

from app.deps import MemberDep, SessionDep
from app.modules.families import service
from app.modules.families.schemas import FamilyBriefOut, FamilyOut, MemberOut, MeOut

router = APIRouter(prefix="/api", tags=["family"])


@router.get("/me")
async def me(member: MemberDep, session: SessionDep) -> MeOut:
    info = await service.get_member(session, member.family_id, member.member_id)
    family = await service.get_family(session, member.family_id)
    return MeOut(
        id=info.id,
        name=info.name,
        role=info.role,
        avatar=info.avatar,
        family=FamilyBriefOut(id=family.id, name=family.name),
    )


@router.get("/family")
async def family(member: MemberDep, session: SessionDep) -> FamilyOut:
    info = await service.get_family(session, member.family_id)
    members = await service.list_members(session, member.family_id)
    return FamilyOut(
        id=info.id,
        name=info.name,
        members=[MemberOut(id=m.id, name=m.name, role=m.role, avatar=m.avatar) for m in members],
    )


@router.get("/family/members/{member_id}")
async def family_member(member_id: uuid.UUID, member: MemberDep, session: SessionDep) -> MemberOut:
    info = await service.get_member(session, member.family_id, member_id)
    return MemberOut(id=info.id, name=info.name, role=info.role, avatar=info.avatar)
