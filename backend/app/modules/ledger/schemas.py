import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.modules.ledger.enums import EntryKind


class BalanceOut(BaseModel):
    balance: int
    reserved: int
    # Сколько можно потратить прямо сейчас: баланс минус отложенное под покупки
    available: int


class EntryOut(BaseModel):
    id: uuid.UUID
    kind: EntryKind
    amount: int
    # Как запись изменила баланс для трат; сумма по всей истории равна ему
    available_delta: int
    label: str
    # Почему взрослый отменил подтверждение или списал минус; у остальных записей пусто
    reason: str | None
    created_at: datetime


class MemberBalanceOut(BalanceOut):
    member_id: uuid.UUID


class WriteOffIn(BaseModel):
    # Причина остаётся в журнале: потом по ней видно, почему минус простили
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
