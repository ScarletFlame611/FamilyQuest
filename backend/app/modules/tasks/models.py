import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base, str_enum
from app.core.ids import new_id
from app.modules.tasks.enums import TaskStatus


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint("points > 0", name="points_positive"),
        # Без исполнителя задача может быть только на общей доске
        CheckConstraint(
            f"(status = '{TaskStatus.OPEN}') = (assignee_member_id IS NULL)",
            name="open_has_no_assignee",
        ),
        # Общая доска и список «ждут проверки» выбирают задачи семьи по статусу
        Index("ix_tasks_family_id_status", "family_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    icon: Mapped[str] = mapped_column(String(32))
    points: Mapped[int] = mapped_column(Integer)
    assignee_member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), index=True
    )
    created_by_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE")
    )
    status: Mapped[TaskStatus] = mapped_column(str_enum(TaskStatus, "task_status"))
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    # Номер выполнения: растёт при отмене подтверждения, чтобы повторное
    # подтверждение дало новое начисление, а не упёрлось в прежнее
    attempt: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
