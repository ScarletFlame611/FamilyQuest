from collections.abc import AsyncIterator
from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

# Явные имена ограничений нужны, чтобы автогенерация Alembic давала стабильный diff
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def str_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    # Строка с CHECK вместо типа ENUM в PostgreSQL: новое значение добавляется
    # обычной миграцией ограничения, без ALTER TYPE
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda members: [m.value for m in members],
    )


def make_engine(url: str) -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        url,
        pool_pre_ping=True,
        connect_args={"timeout": settings.db_connect_timeout_seconds},
    )


engine = make_engine(get_settings().database_url)
session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
