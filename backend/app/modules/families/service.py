import uuid
from dataclasses import dataclass
from itertools import pairwise

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInputError, NotFoundError
from app.core.security import hash_secret
from app.modules.families.enums import MemberRole
from app.modules.families.models import Family, Member
from app.modules.ledger import service as ledger


class MemberNotFoundError(NotFoundError):
    pass


@dataclass(frozen=True)
class Membership:
    member_id: uuid.UUID
    family_id: uuid.UUID


@dataclass(frozen=True)
class MemberInfo:
    id: uuid.UUID
    name: str
    role: MemberRole
    avatar: str


@dataclass(frozen=True)
class FamilyInfo:
    id: uuid.UUID
    name: str
    timezone: str


def _info(member: Member) -> MemberInfo:
    return MemberInfo(id=member.id, name=member.name, role=member.role, avatar=member.avatar)


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


async def get_adult_membership(session: AsyncSession, user_id: uuid.UUID) -> Membership:
    """Возвращает участника и семью взрослого аккаунта."""
    row = (
        await session.execute(select(Member.id, Member.family_id).where(Member.user_id == user_id))
    ).one_or_none()
    if row is None:
        raise MemberNotFoundError("Аккаунт не состоит в семье")
    return Membership(member_id=row.id, family_id=row.family_id)


async def get_family(session: AsyncSession, family_id: uuid.UUID) -> FamilyInfo:
    """Возвращает название и часовой пояс семьи."""
    family = await session.get_one(Family, family_id)
    return FamilyInfo(id=family.id, name=family.name, timezone=family.timezone)


async def get_member(
    session: AsyncSession, family_id: uuid.UUID, member_id: uuid.UUID
) -> MemberInfo:
    """Возвращает участника своей семьи; чужой участник неотличим от несуществующего."""
    member = await session.scalar(
        select(Member).where(Member.id == member_id, Member.family_id == family_id)
    )
    if member is None:
        raise MemberNotFoundError("Участник не найден")
    return _info(member)


async def list_members(session: AsyncSession, family_id: uuid.UUID) -> list[MemberInfo]:
    """Возвращает участников семьи: сначала взрослых, потом детей."""
    members = await session.scalars(
        select(Member).where(Member.family_id == family_id).order_by(Member.role, Member.created_at)
    )
    return [_info(member) for member in members]
