import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.core import idempotency  # noqa: F401
from app.core.config import get_settings
from app.core.db import Base
from app.modules.child_mode import models as child_mode_models  # noqa: F401
from app.modules.families import models as families_models  # noqa: F401
from app.modules.goals import models as goals_models  # noqa: F401
from app.modules.ledger import models as ledger_models  # noqa: F401
from app.modules.rewards import models as rewards_models  # noqa: F401
from app.modules.tasks import models as tasks_models  # noqa: F401
from app.modules.users import models as users_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    # Тесты передают адрес тестовой базы через атрибуты конфига
    return config.attributes.get("database_url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(database_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
