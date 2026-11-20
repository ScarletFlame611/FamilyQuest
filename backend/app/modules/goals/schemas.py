import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.modules.families.enums import MemberRole
from app.modules.goals.enums import GoalIcon


class GoalCreateIn(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    icon: GoalIcon
    target: int = Field(gt=0, le=100000)


class ContributionOut(BaseModel):
    member_id: uuid.UUID
    name: str
    avatar: str
    role: MemberRole
    points: int


class FeedItemOut(BaseModel):
    member_id: uuid.UUID
    name: str
    avatar: str
    title: str
    points: int
    created_at: datetime


class GoalOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: GoalIcon
    target: int
    # Сколько баллов семья заработала с момента создания цели; траты его не уменьшают
    progress: int
    reached: bool
    # Когда семья дошла до цели; после этого момента прогресс уже не меняется
    reached_at: datetime | None
    contributions: list[ContributionOut]
    feed: list[FeedItemOut]
