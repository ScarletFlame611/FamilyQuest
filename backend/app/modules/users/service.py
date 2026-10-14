import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_secret
from app.modules.users.models import User


async def create_user(session: AsyncSession, email: str, password: str, name: str) -> uuid.UUID:
    """Создаёт взрослый аккаунт и возвращает его идентификатор."""
    user = User(email=email.strip(), password_hash=hash_secret(password), name=name)
    session.add(user)
    await session.flush()
    return user.id


async def find_user_id_by_email(session: AsyncSession, email: str) -> uuid.UUID | None:
    """Ищет аккаунт по почте без учёта регистра."""
    return await session.scalar(
        select(User.id).where(func.lower(User.email) == email.strip().lower())
    )


async def delete_users(session: AsyncSession, user_ids: list[uuid.UUID]) -> None:
    """Удаляет аккаунты; участников семьи нужно удалить раньше."""
    await session.execute(delete(User).where(User.id.in_(user_ids)))
