import hashlib
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any

from fastapi import Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import DateTime, ForeignKey, Integer, String, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_utc
from app.core.db import Base
from app.core.errors import InvalidInputError


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    # Any: сохраняется произвольный JSON-ответ эндпоинта, его форма зависит от эндпоинта
    response_body: Mapped[Any] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class IdempotencyKeyReusedError(InvalidInputError):
    pass


IdempotencyKeyHeader = Annotated[
    str | None, Header(alias="Idempotency-Key", min_length=8, max_length=100)
]


async def run_idempotent(
    session: AsyncSession,
    member_id: uuid.UUID,
    key: str | None,
    request: str,
    action: Callable[[], Awaitable[BaseModel]],
    status_code: int = 200,
) -> JSONResponse:
    if key is None:
        result = await action()
        await session.commit()
        return JSONResponse(result.model_dump(mode="json"), status_code=status_code)

    # Повтор с тем же ключом, пришедший параллельно, ждёт здесь окончания первого
    # запроса и затем получает его сохранённый ответ, а не выполняет действие второй раз
    lock_id = func.hashtextextended(f"{member_id}:{key}", 0)
    await session.execute(select(func.pg_advisory_xact_lock(lock_id)))
    request_hash = hashlib.sha256(request.encode()).hexdigest()
    stored = await session.get(IdempotencyKey, (member_id, key))
    if stored is not None:
        if stored.request_hash != request_hash:
            raise IdempotencyKeyReusedError(
                "Этот Idempotency-Key уже использован для другого запроса"
            )
        return JSONResponse(stored.response_body, status_code=stored.response_status)

    result = await action()
    body = result.model_dump(mode="json")
    session.add(
        IdempotencyKey(
            member_id=member_id,
            key=key,
            request_hash=request_hash,
            response_status=status_code,
            response_body=body,
        )
    )
    await session.commit()
    return JSONResponse(body, status_code=status_code)
