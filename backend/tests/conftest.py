import asyncio
from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.db import get_session, make_engine
from app.main import app
from app.seed import DemoFamily
from tests.factories import seed


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def test_database_url() -> str:
    url = get_settings().test_database_url
    if not url:
        pytest.exit("Не задан TEST_DATABASE_URL: тесты идут только против отдельной базы")
    return url


async def create_database_if_missing(url: str) -> None:
    target = make_url(url)
    server = make_engine(target.set(database="postgres").render_as_string(hide_password=False))
    async with server.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": target.database}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    await server.dispose()


@pytest.fixture(scope="session")
def migrated_database() -> str:
    url = test_database_url()
    asyncio.run(create_database_if_missing(url))
    config = Config("alembic.ini")
    config.attributes["database_url"] = url
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return url


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = make_engine(migrated_database)
    yield engine
    async with engine.begin() as conn:
        tables = await conn.scalars(
            text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        )
        names = ", ".join(f'"{name}"' for name in tables)
        if names:
            await conn.execute(text(f"TRUNCATE {names} RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        yield session


@pytest.fixture
async def client(engine: AsyncEngine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def demo(session: AsyncSession) -> DemoFamily:
    return await seed(session)
