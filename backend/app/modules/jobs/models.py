import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base, str_enum
from app.core.ids import new_id
from app.modules.jobs.enums import JobKind, JobStatus


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint("attempts >= 0", name="attempts_not_negative"),
        CheckConstraint("process_count >= 0", name="process_count_not_negative"),
        # Захват ищет только незавершённые задания, поэтому индекс частичный
        Index(
            "ix_jobs_pending",
            "run_after",
            postgresql_where=text(f"status IN ('{JobStatus.QUEUED}', '{JobStatus.RUNNING}')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    kind: Mapped[JobKind] = mapped_column(str_enum(JobKind, "job_kind"))
    # Только идентификаторы, по которым обработчик сам загрузит данные: задание
    # не хранит копию бизнес-данных, которая могла бы устареть
    payload: Mapped[dict[str, str]] = mapped_column(JSONB)
    status: Mapped[JobStatus] = mapped_column(
        str_enum(JobStatus, "job_status"), default=JobStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    claim_token: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    # Сколько раз результат задания был записан; больше одного быть не должно
    process_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
