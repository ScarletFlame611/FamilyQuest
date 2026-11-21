import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, LargeBinary, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base, str_enum
from app.core.ids import new_id
from app.modules.exports.enums import ExportStatus


class FamilyExport(Base):
    __tablename__ = "family_exports"
    __table_args__ = (
        # Одна выгрузка семьи в работе за раз: повторное нажатие не плодит заданий
        Index(
            "uq_family_exports_pending_family",
            "family_id",
            unique=True,
            postgresql_where=text(f"status = '{ExportStatus.PENDING}'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    family_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("families.id", ondelete="CASCADE"), index=True
    )
    requested_by_member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    status: Mapped[ExportStatus] = mapped_column(
        str_enum(ExportStatus, "export_status"), default=ExportStatus.PENDING
    )
    # Файл хранится в базе: его видят все экземпляры API и он попадает в резервные копии.
    # Когда появится объектное хранилище, сюда переедет только ссылка на файл
    file: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
