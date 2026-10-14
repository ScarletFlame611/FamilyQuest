import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.rewards.enums import PurchaseStatus, RewardIcon


class RewardOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: RewardIcon
    price: int


class RewardOfferOut(RewardOut):
    affordable: bool
    # Сколько баллов не хватает до покупки; 0, если хватает
    missing: int
    # У участника уже есть покупка этой награды, которую ещё не выдали
    waiting: bool


class PurchaseOut(BaseModel):
    id: uuid.UUID
    reward_id: uuid.UUID
    title: str
    icon: RewardIcon
    price: int
    status: PurchaseStatus
    child_member_id: uuid.UUID
    child_name: str
    cancel_reason: str | None
    created_at: datetime


class CancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class NotEnoughOut(BaseModel):
    detail: str
    missing: int
