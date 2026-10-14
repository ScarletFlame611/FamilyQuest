import uuid
from itertools import pairwise

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInputError
from app.core.security import hash_secret
from app.modules.families.enums import MemberRole
from app.modules.families.models import Family, Member
from app.modules.ledger import service as ledger


class WeakPinError(InvalidInputError):
    pass


def _is_weak_pin(pin: str) -> bool:
    if len(set(pin)) == 1:
        return True
    steps = {int(b) - int(a) for a, b in pairwise(pin)}
    # Подряд идущие цифры вверх или вниз (1234, 4321, 6789) подбираются первыми
    return steps in ({1}, {-1})


async def create_family(session: AsyncSession, name: str, timezone: str) -> uuid.UUID:
    """Создаёт семью без участников и без PIN."""
    family = Family(name=name, timezone=timezone, pin_failed_attempts=0, pin_locked=False)
    session.add(family)
    await session.flush()
    return family.id


async def set_pin(session: AsyncSession, family_id: uuid.UUID, pin: str) -> None:
    """Устанавливает PIN детского режима и снимает блокировку."""
    if len(pin) != 4 or not pin.isdigit():
        raise InvalidInputError("PIN-код должен состоять из 4 цифр")
    if _is_weak_pin(pin):
        raise WeakPinError(
            "Такой PIN-код легко угадать. Не используйте одинаковые цифры "
            "и цифры подряд, например 1111 или 1234"
        )
    family = await session.get_one(Family, family_id)
    family.pin_hash = hash_secret(pin)
    family.pin_failed_attempts = 0
    family.pin_locked = False
    await session.flush()


async def _add_member(
    session: AsyncSession,
    family_id: uuid.UUID,
    role: MemberRole,
    name: str,
    avatar: str,
    user_id: uuid.UUID | None,
) -> uuid.UUID:
    member = Member(family_id=family_id, role=role, name=name, avatar=avatar, user_id=user_id)
    session.add(member)
    await session.flush()
    await ledger.open_account(session, family_id, member.id)
    return member.id


async def add_adult(
    session: AsyncSession, family_id: uuid.UUID, user_id: uuid.UUID, name: str, avatar: str
) -> uuid.UUID:
    """Добавляет в семью взрослого с аккаунтом и заводит ему счёт."""
    return await _add_member(session, family_id, MemberRole.ADULT, name, avatar, user_id)


async def add_child(
    session: AsyncSession, family_id: uuid.UUID, name: str, avatar: str
) -> uuid.UUID:
    """Добавляет в семью ребёнка без почты и телефона и заводит ему счёт."""
    return await _add_member(session, family_id, MemberRole.CHILD, name, avatar, None)


async def find_family_id_by_user(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID | None:
    """Возвращает семью, в которой состоит взрослый аккаунт."""
    return await session.scalar(select(Member.family_id).where(Member.user_id == user_id))


async def delete_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    """Удаляет семью вместе со всеми её данными."""
    await session.execute(delete(Family).where(Family.id == family_id))
