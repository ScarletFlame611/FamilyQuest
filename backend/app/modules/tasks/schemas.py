import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.tasks.enums import TaskIcon, TaskStatus


class TaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    icon: TaskIcon
    points: int = Field(gt=0, le=1000)
    # Без исполнителя задача попадает на общую доску
    assignee_id: uuid.UUID | None = None


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=300)


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    icon: TaskIcon
    points: int
    status: TaskStatus
    assignee_member_id: uuid.UUID | None
    assignee_name: str | None
    created_by_member_id: uuid.UUID
    created_by_name: str
    reject_reason: str | None
    marked_at: datetime | None
    confirmed_at: datetime | None
