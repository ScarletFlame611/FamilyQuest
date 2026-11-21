import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.exports.enums import ExportStatus
from app.modules.jobs.enums import JobStatus


class ExportOut(BaseModel):
    id: uuid.UUID
    # По нему воркер и команда статуса находят задание в очереди
    job_id: uuid.UUID
    status: ExportStatus
    # Состояние задания в очереди: ждёт воркера или уже собирается
    job_status: JobStatus | None
    attempts: int
    max_attempts: int
    file_size: int | None
    error: str | None
    created_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None
