import uuid

from pydantic import BaseModel, Field


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
