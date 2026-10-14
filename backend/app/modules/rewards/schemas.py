import uuid

from pydantic import BaseModel


class RewardOut(BaseModel):
    id: uuid.UUID
    title: str
    icon: str
    price: int
