import uuid

from pydantic import BaseModel, Field

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


class SetPinIn(BaseModel):
    current_password: str = Field(max_length=200)
    pin: str = Field(max_length=8)
