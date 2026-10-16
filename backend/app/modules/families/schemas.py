import uuid

from pydantic import BaseModel, Field

from app.modules.families.enums import AgeGroup, MemberRole


class MemberOut(BaseModel):
    id: uuid.UUID
    name: str
    role: MemberRole
    avatar: str
    age_group: AgeGroup | None


class ChildCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    avatar: str = Field(min_length=1, max_length=32)
    age_group: AgeGroup
    # Взрослый явно подтверждает согласие на обработку данных ребёнка
    parent_consent: bool


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
