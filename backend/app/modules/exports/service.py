import csv
import io
import uuid
import zipfile
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.ids import new_id
from app.modules.child_mode import service as child_mode
from app.modules.exports.enums import ExportStatus
from app.modules.exports.models import FamilyExport
from app.modules.families import service as families
from app.modules.families.enums import MemberRole
from app.modules.goals import service as goals
from app.modules.jobs import service as jobs
from app.modules.jobs.enums import JobKind, JobStatus
from app.modules.ledger import service as ledger
from app.modules.rewards import service as rewards
from app.modules.rewards.enums import PurchaseStatus
from app.modules.tasks import service as tasks
from app.modules.tasks.enums import TaskStatus


class ExportNotFoundError(NotFoundError):
    pass


class ExportNotReadyError(ConflictError):
    pass


@dataclass(frozen=True)
class ExportView:
    id: uuid.UUID
    job_id: uuid.UUID
    status: ExportStatus
    job_status: JobStatus | None
    attempts: int
    max_attempts: int
    file_size: int | None
    error: str | None
    created_at: datetime
    ready_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True)
class ExportFile:
    name: str
    content: bytes


KEEP_FOR = timedelta(days=7)
FAILED_MESSAGE = "Не удалось собрать выгрузку. Попробуйте ещё раз"

ROLE_LABELS = {MemberRole.ADULT: "Взрослый", MemberRole.CHILD: "Ребёнок"}
TASK_STATUS_LABELS = {
    TaskStatus.OPEN: "На общей доске",
    TaskStatus.ASSIGNED: "Назначено",
    TaskStatus.MARKED: "Ждёт проверки",
    TaskStatus.CONFIRMED: "Засчитано",
}
PURCHASE_STATUS_LABELS = {
    PurchaseStatus.PENDING: "Ждёт выдачи",
    PurchaseStatus.GIVEN: "Выдана",
    PurchaseStatus.CANCELLED: "Отменена",
}


async def _views(session: AsyncSession, exports: list[FamilyExport]) -> list[ExportView]:
    states = await jobs.get_jobs(session, [e.job_id for e in exports])
    views = []
    for export in exports:
        job = states.get(export.job_id)
        views.append(
            ExportView(
                id=export.id,
                job_id=export.job_id,
                status=export.status,
                job_status=job.status if job else None,
                attempts=job.attempts if job else 0,
                max_attempts=job.max_attempts if job else 0,
                file_size=export.file_size,
                error=export.error,
                created_at=export.created_at,
                ready_at=export.ready_at,
                expires_at=export.expires_at,
            )
        )
    return views


async def request_export(
    session: AsyncSession, family_id: uuid.UUID, member_id: uuid.UUID
) -> ExportView:
    """Ставит выгрузку данных семьи в очередь или возвращает ту, что уже готовится."""
    # Блокировка семьи: два одновременных нажатия не создадут двух заданий
    await families.lock_family(session, family_id)
    pending = await session.scalar(
        select(FamilyExport).where(
            FamilyExport.family_id == family_id, FamilyExport.status == ExportStatus.PENDING
        )
    )
    if pending is None:
        # Запись выгрузки и задание создаются одной транзакцией: при откате не останется
        # ни задания без выгрузки, ни выгрузки, которую никто не соберёт
        export_id = new_id()
        job_id = await jobs.enqueue(session, JobKind.FAMILY_EXPORT, {"export_id": str(export_id)})
        pending = FamilyExport(
            id=export_id, family_id=family_id, requested_by_member_id=member_id, job_id=job_id
        )
        session.add(pending)
        await session.flush()
    return (await _views(session, [pending]))[0]


async def list_exports(session: AsyncSession, family_id: uuid.UUID) -> list[ExportView]:
    """Возвращает последние выгрузки семьи, новые сверху."""
    exports = await session.scalars(
        select(FamilyExport)
        .where(FamilyExport.family_id == family_id)
        .order_by(FamilyExport.created_at.desc())
        .limit(10)
    )
    return await _views(session, list(exports))


async def get_file(session: AsyncSession, family_id: uuid.UUID, export_id: uuid.UUID) -> ExportFile:
    """Отдаёт готовый архив выгрузки своей семьи."""
    export = await session.scalar(
        select(FamilyExport).where(
            FamilyExport.id == export_id, FamilyExport.family_id == family_id
        )
    )
    if export is None:
        raise ExportNotFoundError("Выгрузка не найдена")
    if export.status is not ExportStatus.READY or export.file is None:
        raise ExportNotReadyError(
            "Срок хранения файла истёк, подготовьте новую выгрузку"
            if export.status is ExportStatus.EXPIRED
            else "Файл ещё не готов"
        )
    return ExportFile(f"familyquest-{export.created_at:%Y-%m-%d}.zip", export.file)


def _csv(header: list[str], rows: list[list[object]]) -> str:
    buffer = io.StringIO()
    # Точка с запятой и BOM, как в истории баллов: Excel с русскими настройками открывает сразу
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    return "﻿" + buffer.getvalue()


async def build_archive(session: AsyncSession, family_id: uuid.UUID, now: datetime) -> bytes:
    """Собирает архив CSV со всеми данными семьи; пароли, PIN и токены в него не входят."""
    family = await families.get_family(session, family_id)
    zone = ZoneInfo(family.timezone)

    def when(moment: datetime | None) -> str:
        return f"{moment.astimezone(zone):%d.%m.%Y %H:%M}" if moment else ""

    members = await families.list_members(session, family_id)
    files = {
        "участники.csv": _csv(
            ["Имя", "Роль", "Возраст"],
            [[m.name, ROLE_LABELS[m.role], m.age_group or ""] for m in members],
        ),
        "дела.csv": _csv(
            [
                "Дело",
                "Описание",
                "Баллы",
                "Состояние",
                "Исполнитель",
                "Создал",
                "Отмечено",
                "Засчитано",
                "Причина возврата",
            ],
            [
                [
                    t.title,
                    t.description or "",
                    t.points,
                    TASK_STATUS_LABELS[t.status],
                    t.assignee_name or "",
                    t.created_by_name,
                    when(t.marked_at),
                    when(t.confirmed_at),
                    t.reject_reason or "",
                ]
                for t in await tasks.list_all_tasks(session, family_id)
            ],
        ),
    }

    history = []
    for member in members:
        entries = await ledger.list_entries(session, member.id, 100_000)
        titles = await tasks.task_titles(
            session, family_id, [e.task_id for e in entries if e.task_id]
        )
        bought = await rewards.purchase_titles(
            session, family_id, [e.purchase_id for e in entries if e.purchase_id]
        )
        for e in reversed(entries):
            label = (
                (titles.get(e.task_id) if e.task_id else None)
                or (bought.get(e.purchase_id) if e.purchase_id else None)
                or e.note
                or ""
            )
            history.append(
                [
                    member.name,
                    when(e.created_at),
                    ledger.ENTRY_LABELS[e.kind],
                    label,
                    ledger.available_effect(e.kind, e.amount),
                    e.note if e.kind in ledger.REASONED_KINDS else "",
                ]
            )
    files["история баллов.csv"] = _csv(
        ["Участник", "Дата и время", "Что произошло", "Дело или награда", "Баллы", "Причина"],
        history,
    )
    files["награды.csv"] = _csv(
        ["Награда", "Цена", "Скрыта от детей"],
        [
            [r.title, r.price, "да" if r.hidden else "нет"]
            for r in await rewards.list_rewards(session, family_id)
        ],
    )
    files["покупки.csv"] = _csv(
        ["Награда", "Цена", "Кто купил", "Когда", "Состояние", "Причина отмены"],
        [
            [
                p.title,
                p.price,
                p.child_name,
                when(p.created_at),
                PURCHASE_STATUS_LABELS[p.status],
                p.cancel_reason or "",
            ]
            for p in await rewards.list_purchases(session, family_id)
        ],
    )
    files["цели.csv"] = _csv(
        ["Цель", "Сумма", "Накоплено", "Активная", "Создана", "Достигнута"],
        [
            [
                g.title,
                g.target,
                g.progress,
                "да" if g.is_active else "нет",
                when(g.created_at),
                when(g.reached_at),
            ]
            for g in await goals.list_goals(session, family_id)
        ],
    )
    sessions = []
    for child_session in await child_mode.list_sessions(session, family_id):
        _, events = await child_mode.session_events(session, family_id, child_session.id)
        for event in events:
            sessions.append(
                [
                    child_session.child_name,
                    child_session.started_by_name,
                    when(child_session.started_at),
                    when(child_session.ended_at),
                    event.type,
                    event.detail or "",
                    event.seconds_from_start,
                ]
            )
    files["детский режим.csv"] = _csv(
        ["Ребёнок", "Кто включил", "Начало", "Конец", "Событие", "Подробности", "Секунд от начала"],
        sessions,
    )
    readme = (
        f"Данные семьи «{family.name}» из FamilyQuest на {when(now)}.\n"
        "Каждый файл открывается в Excel. Время указано в часовом поясе семьи.\n"
        "Пароли, PIN-код и ключи входа в выгрузку не входят.\n"
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("прочитай меня.txt", readme)
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


async def run_export_job(
    session: AsyncSession,
    payload: dict[str, str],
    now: datetime,
    finish: Callable[[], Awaitable[None]],
) -> None:
    """Собирает архив по заданию очереди и сохраняет его вместе с отметкой о выполнении."""
    export = await session.get(FamilyExport, uuid.UUID(payload["export_id"]))
    if export is None or export.status is not ExportStatus.PENDING:
        # Семью удалили или выгрузку уже закрыли: делать нечего, задание просто завершается
        await finish()
        return
    content = await build_archive(session, export.family_id, now)
    # finish проверяет, что задание всё ещё за этим воркером; если нет, транзакция
    # откатится и файл старого воркера не перезапишет результат нового
    await finish()
    export.status = ExportStatus.READY
    export.file = content
    export.file_size = len(content)
    export.ready_at = now
    export.expires_at = now + KEEP_FOR


async def fail_export_job(session: AsyncSession, payload: dict[str, str]) -> None:
    """Отмечает выгрузку неудачной, когда очередь исчерпала попытки."""
    await session.execute(
        update(FamilyExport)
        .where(
            FamilyExport.id == uuid.UUID(payload["export_id"]),
            FamilyExport.status == ExportStatus.PENDING,
        )
        .values(status=ExportStatus.FAILED, error=FAILED_MESSAGE)
    )


async def purge_expired(session: AsyncSession, now: datetime) -> int:
    """Удаляет файлы выгрузок, срок хранения которых истёк, и возвращает их число."""
    result = await session.execute(
        update(FamilyExport)
        .where(FamilyExport.status == ExportStatus.READY, FamilyExport.expires_at < now)
        .values(status=ExportStatus.EXPIRED, file=None)
    )
    return result.rowcount
