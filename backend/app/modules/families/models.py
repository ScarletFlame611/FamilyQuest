import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base, str_enum
from app.core.ids import new_id
from app.modules.families.enums import AgeGroup, MemberRole


class Family(Base):
    __tablename__ = "families"
    __table_args__ = (CheckConstraint("revoke_window_days > 0", name="revoke_window_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    # Сколько дней после подтверждения взрослый может его отменить
    revoke_window_days: Mapped[int] = mapped_column(Integer, default=7, server_default="7")
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    pin_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    pin_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Member(Base):
    __tablename__ = "members"
    __table_args__ = (
        # У взрослого всегда есть аккаунт, у ребёнка аккаунта нет
        CheckConstraint(
            f"(role = '{MemberRole.ADULT}') = (user_id IS NOT NULL)", name="adult_has_user"
        ),
        # Профиль ребёнка без возрастной группы и согласия взрослого не существует
        CheckConstraint(
            f"role <> '{MemberRole.CHILD}' "
            "OR (age_group IS NOT NULL AND parent_consent_at IS NOT NULL)",
            name="child_profile_complete",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MemberRole] = mapped_column(str_enum(MemberRole, "member_role"))
    name: Mapped[str] = mapped_column(String(100))
    avatar: Mapped[str] = mapped_column(String(32))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    # Вместо даты рождения хранится только возрастная группа: точный возраст ребёнка
    # сервису не нужен
    age_group: Mapped[AgeGroup | None] = mapped_column(str_enum(AgeGroup, "age_group"))
    parent_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    # Сам токен знает только тот, кому отправили ссылку; в базе лишь его SHA-256
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
