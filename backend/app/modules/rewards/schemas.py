import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.modules.rewards.enums import PurchaseStatus, RewardIcon

# Название из одних пробелов ребёнок увидит пустой карточкой
RewardTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
RewardPrice = Annotated[int, Field(gt=0, le=10000)]


class RewardCreateIn(BaseModel):
    title: RewardTitle
    icon: RewardIcon
    price: RewardPrice


class RewardUpdateIn(BaseModel):
    title: RewardTitle | None = None
    price: RewardPrice | None = None
    # Скрытая награда пропадает из каталога ребёнка, но не из уже сделанных покупок
    hidden: bool | None = None


class RewardOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: RewardIcon
    price: int


class RewardAdminOut(RewardOut):
    hidden: bool


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
