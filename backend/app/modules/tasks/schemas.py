import uuid

from pydantic import BaseModel

from app.modules.tasks.enums import TaskStatus


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: str
    points: int
    status: TaskStatus
    assignee_member_id: uuid.UUID | None
    created_by_member_id: uuid.UUID
    reject_reason: str | None
