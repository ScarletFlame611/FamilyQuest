import argparse
import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.clock import now_utc
from app.core.config import get_settings
from app.core.db import session_factory
from app.modules.exports import service as exports
from app.modules.families import service as families
from app.modules.jobs import service as jobs
from app.modules.jobs.enums import JobKind
from app.modules.users import service as users

log = logging.getLogger("worker")


@dataclass(frozen=True)
class Handler:
    # Обработчик сам решает, что записать; finish нужно вызвать в той же транзакции
    # перед записью результата, он проверяет, что задание ещё закреплено за воркером
    run: Callable[
        [AsyncSession, dict[str, str], datetime, Callable[[], Awaitable[None]]], Awaitable[None]
    ]
    give_up: Callable[[AsyncSession, dict[str, str]], Awaitable[None]]


HANDLERS = {
    JobKind.FAMILY_EXPORT: Handler(exports.run_export_job, exports.fail_export_job),
}

PURGE_EVERY = timedelta(hours=1)


@dataclass(frozen=True)
class Faults:
    # Учебные сбои для проверки восстановления, на рабочем стенде не включаются
    crash_after_claim: bool = False
    sleep_after_claim: float = 0


NO_FAULTS = Faults()


def _tag(job: jobs.ClaimedJob) -> str:
    return f"job={job.id} attempt={job.attempt} token={str(job.claim_token)[:8]}"


async def process_one(
    factory: async_sessionmaker[AsyncSession], lease: timedelta, faults: Faults = NO_FAULTS
) -> bool:
    """Обрабатывает одно задание из очереди и сообщает, нашлось ли оно."""
    async with factory() as session:
        job = await jobs.claim(session, now_utc(), lease)
        await session.commit()
    if job is None:
        return False
    log.info("%s claimed kind=%s lease_until=%s", _tag(job), job.kind, job.lease_until)
    handler = HANDLERS[job.kind]

    if jobs.exhausted(job):
        async with factory() as session:
            await jobs.give_up(session, job, now_utc(), "Попытки закончились")
            await handler.give_up(session, job.payload)
            await session.commit()
        log.warning("%s failed: no attempts left", _tag(job))
        return True

    if faults.crash_after_claim:
        log.warning("%s crash after claim", _tag(job))
        # Без закрытия соединений и коммитов, как при настоящем падении процесса
        os._exit(1)
    if faults.sleep_after_claim:
        log.info("%s sleeping %ss after claim", _tag(job), faults.sleep_after_claim)
        await asyncio.sleep(faults.sleep_after_claim)

    try:
        async with factory() as session:
            now = now_utc()
            await handler.run(session, job.payload, now, lambda: jobs.complete(session, job, now))
            await session.commit()
        log.info("%s done", _tag(job))
    except jobs.StaleOwnerError:
        # Пока этот воркер спал, аренда истекла и задание выполнил другой: результат
        # этого воркера отброшен вместе с откатом его транзакции
        log.warning("%s stale_owner: result discarded", _tag(job))
    except Exception as error:
        # Любая ошибка обработчика возвращает задание в очередь, иначе оно зависнет
        # до конца аренды; после последней попытки его закроет следующий захват
        log.exception("%s error", _tag(job))
        async with factory() as session:
            try:
                await jobs.retry_later(session, job, now_utc(), repr(error))
                await session.commit()
            except jobs.StaleOwnerError:
                log.warning("%s stale_owner: retry skipped", _tag(job))
    return True


async def run_worker(once: bool, lease: timedelta, faults: Faults) -> None:
    settings = get_settings()
    last_purge: datetime | None = None
    log.info("worker started lease=%ss", lease.total_seconds())
    while True:
        if await process_one(session_factory, lease, faults):
            if once:
                return
            continue
        if last_purge is None or now_utc() - last_purge > PURGE_EVERY:
            async with session_factory() as session:
                purged = await exports.purge_expired(session, now_utc())
                await session.commit()
            last_purge = now_utc()
            if purged:
                log.info("purged %s expired export files", purged)
        await asyncio.sleep(settings.worker_poll_seconds)


async def show_status(job_id: uuid.UUID) -> None:
    async with session_factory() as session:
        job = await jobs.get_job(session, job_id)
    print(
        f"job={job.id} kind={job.kind} status={job.status} "
        f"attempts={job.attempts}/{job.max_attempts} process_count={job.process_count} "
        f"lease_until={job.lease_until} finished_at={job.finished_at} "
        f"last_error={job.last_error}"
    )


async def enqueue_export(email: str) -> None:
    async with session_factory() as session:
        user_id = await users.find_user_id_by_email(session, email)
        if user_id is None:
            raise SystemExit(f"Нет взрослого с почтой {email}")
        membership = await families.get_adult_membership(session, user_id)
        export = await exports.request_export(session, membership.family_id, membership.member_id)
        await session.commit()
    print(f"export={export.id} job={export.job_id} status={export.status}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Фоновый обработчик заданий FamilyQuest")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="обрабатывать задания из очереди")
    run.add_argument("--once", action="store_true", help="выйти после одного задания")
    run.add_argument("--lease-seconds", type=int, default=get_settings().job_lease_seconds)
    run.add_argument("--crash-after-claim", action="store_true")
    run.add_argument("--sleep-after-claim", type=float, default=0)
    status = commands.add_parser("status", help="показать состояние задания")
    status.add_argument("job_id", type=uuid.UUID)
    enqueue = commands.add_parser("enqueue-export", help="поставить выгрузку данных семьи")
    enqueue.add_argument("email")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.command == "run":
        faults = Faults(args.crash_after_claim, args.sleep_after_claim)
        asyncio.run(run_worker(args.once, timedelta(seconds=args.lease_seconds), faults))
    elif args.command == "status":
        asyncio.run(show_status(args.job_id))
    else:
        asyncio.run(enqueue_export(args.email))


if __name__ == "__main__":
    main()
