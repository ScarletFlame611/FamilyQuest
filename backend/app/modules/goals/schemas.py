import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.families.enums import MemberRole
from app.modules.goals.enums import GoalIcon


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
    contributions: list[ContributionOut]
    feed: list[FeedItemOut]
