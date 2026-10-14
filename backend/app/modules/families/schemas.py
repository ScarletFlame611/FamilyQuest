import uuid

from pydantic import BaseModel

from app.modules.families.enums import MemberRole


class MemberOut(BaseModel):
    id: uuid.UUID
    name: str
    role: MemberRole
    avatar: str


class FamilyBriefOut(BaseModel):
    id: uuid.UUID
    name: str


class MeOut(MemberOut):
    family: FamilyBriefOut


class FamilyOut(FamilyBriefOut):
    members: list[MemberOut]
