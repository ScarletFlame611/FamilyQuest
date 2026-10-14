import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.child_mode.enums import ChildEventType


class StartIn(BaseModel):
    child_id: uuid.UUID
    # Refresh-токен взрослого отзывается сразу: вернуть права взрослого
    # можно только ответом сервера на правильный PIN
    adult_refresh_token: str | None = Field(default=None, max_length=200)


class PinIn(BaseModel):
    pin: str = Field(max_length=8)


class PasswordIn(BaseModel):
    password: str = Field(max_length=200)


class PinErrorOut(BaseModel):
    detail: str
    attempts_left: int | None = None


class ClientEventIn(BaseModel):
    type: ChildEventType
    detail: str | None = Field(default=None, max_length=200)
    ago_ms: int = Field(ge=0, le=24 * 60 * 60 * 1000)


class EventsIn(BaseModel):
    events: list[ClientEventIn] = Field(max_length=200)


class ChildSessionOut(BaseModel):
    id: uuid.UUID
    child_member_id: uuid.UUID
    child_name: str
    started_by_name: str
    started_at: datetime
    ended_at: datetime | None
    events: int


class ChildEventOut(BaseModel):
    type: ChildEventType
    detail: str | None
    occurred_at: datetime
    seconds_from_start: float


class SessionEventsOut(BaseModel):
    session: ChildSessionOut
    events: list[ChildEventOut]
