import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base, str_enum
from app.core.ids import new_id
from app.modules.rewards.enums import PurchaseStatus


class Reward(Base):
    __tablename__ = "rewards"
    __table_args__ = (CheckConstraint("price > 0", name="price_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    icon: Mapped[str] = mapped_column(String(32))
    price: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RewardPurchase(Base):
    __tablename__ = "reward_purchases"
    __table_args__ = (CheckConstraint("price > 0", name="price_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    reward_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("rewards.id", ondelete="CASCADE"))
    child_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), index=True
    )
    # Цена на момент покупки: если взрослый потом изменит цену награды,
    # резерв и списание должны остаться равными
    price: Mapped[int] = mapped_column(Integer)
    status: Mapped[PurchaseStatus] = mapped_column(str_enum(PurchaseStatus, "purchase_status"))
    cancel_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
