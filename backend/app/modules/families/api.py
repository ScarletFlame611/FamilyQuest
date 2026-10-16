import uuid
from dataclasses import asdict

from fastapi import APIRouter, status

from app.core.errors import InvalidInputError, TooManyAttemptsError
from app.deps import AdultDep, MemberDep, SessionDep
from app.modules.families import service
from app.modules.families.schemas import (
    ChildCreateIn,
    FamilyBriefOut,
    FamilyOut,
    MemberOut,
    MeOut,
    SetPinIn,
)
from app.modules.users import service as users

router = APIRouter(prefix="/api", tags=["family"])


@router.get("/me")
async def me(member: MemberDep, session: SessionDep) -> MeOut:
    info = await service.get_member(session, member.family_id, member.member_id)
    family = await service.get_family(session, member.family_id)
    return MeOut(**asdict(info), family=FamilyBriefOut(id=family.id, name=family.name))


@router.get("/family")
async def family(member: MemberDep, session: SessionDep) -> FamilyOut:
    info = await service.get_family(session, member.family_id)
    members = await service.list_members(session, member.family_id)
    return FamilyOut(
        id=info.id,
        name=info.name,
        members=[MemberOut(**asdict(m)) for m in members],
    )


@router.get("/family/members/{member_id}")
async def family_member(member_id: uuid.UUID, member: MemberDep, session: SessionDep) -> MemberOut:
    info = await service.get_member(session, member.family_id, member_id)
    return MemberOut(**asdict(info))


@router.post("/family/children", status_code=status.HTTP_201_CREATED)
async def add_child(body: ChildCreateIn, adult: AdultDep, session: SessionDep) -> MemberOut:
    child_id = await service.add_child(
        session,
        adult.family_id,
        body.name.strip(),
        body.avatar,
        body.age_group,
        body.parent_consent,
    )
    await session.commit()
    return MemberOut(**asdict(await service.get_member(session, adult.family_id, child_id)))


@router.put("/family/pin", status_code=status.HTTP_204_NO_CONTENT)
async def set_pin(body: SetPinIn, adult: AdultDep, session: SessionDep) -> None:
    user_id = await service.get_adult_user_id(session, adult.family_id, adult.member_id)
    try:
        await users.check_password(session, user_id, body.current_password)
    except (InvalidInputError, TooManyAttemptsError):
        # Неудачная попытка пароля считается так же, как при входе
        await session.commit()
        raise
    await service.set_pin(session, adult.family_id, body.pin)
    await session.commit()
