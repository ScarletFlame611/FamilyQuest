import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.modules.tasks.enums import TaskIcon, TaskStatus


class TaskCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    description: str | None = Field(default=None, max_length=500)
    icon: TaskIcon
    points: int = Field(gt=0, le=1000)
    # Без исполнителя задача попадает на общую доску
    assignee_id: uuid.UUID | None = None


class ConfirmAllIn(BaseModel):
    # Список приходит с экрана: подтверждаются только те дела, что взрослый видел
    task_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)


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


class SkippedTaskOut(BaseModel):
    task_id: uuid.UUID
    title: str
    # Почему дело не засчитано в этой пачке, например его уже подтвердил другой взрослый
    reason: str


class ConfirmAllOut(BaseModel):
    confirmed: list[TaskOut]
    skipped: list[SkippedTaskOut]


class RevokeIn(BaseModel):
    # Причина видна ребёнку и попадает в журнал, поэтому пустой она быть не может
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class RevokeOut(BaseModel):
    task: TaskOut
    # Названия покупок, отменённых потому, что баллов на них больше не хватает
    cancelled_purchases: list[str]
