from datetime import datetime

from pydantic import BaseModel

from app.modules.ledger.enums import EntryKind


class BalanceOut(BaseModel):
    balance: int
    reserved: int
    # Сколько можно потратить прямо сейчас: баланс минус отложенное под покупки
    available: int


class EntryOut(BaseModel):
    kind: EntryKind
    amount: int
    label: str
    created_at: datetime
