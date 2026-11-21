import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.ids import new_id
from app.modules.jobs.enums import JobKind, JobStatus
from app.modules.jobs.models import Job


class JobNotFoundError(NotFoundError):
    pass


class StaleOwnerError(ConflictError):
    pass


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    kind: JobKind
    payload: dict[str, str]
    attempt: int
    claim_token: uuid.UUID
    lease_until: datetime


@dataclass(frozen=True)
class JobView:
    id: uuid.UUID
    kind: JobKind
    status: JobStatus
    attempts: int
    max_attempts: int
    process_count: int
    lease_until: datetime | None
    last_error: str | None
    created_at: datetime
    finished_at: datetime | None


MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(seconds=10)


def _view(job: Job) -> JobView:
    return JobView(
        id=job.id,
        kind=job.kind,
        status=job.status,
        attempts=job.attempts,
        max_attempts=MAX_ATTEMPTS,
        process_count=job.process_count,
        lease_until=job.lease_until,
        last_error=job.last_error,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


async def enqueue(session: AsyncSession, kind: JobKind, payload: dict[str, str]) -> uuid.UUID:
    """Ставит задание в очередь в транзакции вызывающего, без отдельного коммита."""
    job = Job(kind=kind, payload=payload)
    session.add(job)
    await session.flush()
    return job.id


async def claim(session: AsyncSession, now: datetime, lease: timedelta) -> ClaimedJob | None:
    """Забирает одно готовое задание или задание с истёкшей арендой и закрепляет его за собой."""
    # SKIP LOCKED: два воркера не ждут друг друга на одной строке, а берут разные
    candidate = (
        select(Job.id)
        .where(
            or_(
                and_(Job.status == JobStatus.QUEUED, Job.run_after <= now),
                and_(Job.status == JobStatus.RUNNING, Job.lease_until < now),
            )
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
        .scalar_subquery()
    )
    # Новый токен при каждой выдаче: по нему воркер, у которого аренда истекла,
    # узнаёт, что задание уже отдано другому
    row = await session.execute(
        update(Job)
        .where(Job.id == candidate)
        .values(
            status=JobStatus.RUNNING,
            attempts=Job.attempts + 1,
            claim_token=new_id(),
            lease_until=now + lease,
        )
        .returning(Job.id, Job.kind, Job.payload, Job.attempts, Job.claim_token, Job.lease_until)
    )
    found = row.one_or_none()
    if found is None:
        return None
    job_id, kind, payload, attempt, token, lease_until = found
    return ClaimedJob(job_id, JobKind(kind), payload, attempt, token, lease_until)


def exhausted(job: ClaimedJob) -> bool:
    """Проверяет, что попытки кончились и задание пора закрыть как неудачное."""
    return job.attempt > MAX_ATTEMPTS


async def _owned_update(session: AsyncSession, job: ClaimedJob, **values: object) -> None:
    result = await session.execute(
        update(Job)
        .where(
            Job.id == job.id,
            Job.claim_token == job.claim_token,
            Job.status == JobStatus.RUNNING,
        )
        .values(**values)
    )
    if result.rowcount == 0:
        raise StaleOwnerError("Задание уже закреплено за другим воркером")


async def complete(session: AsyncSession, job: ClaimedJob, now: datetime) -> None:
    """Отмечает задание выполненным, только если оно всё ещё закреплено за этим воркером."""
    await _owned_update(
        session,
        job,
        status=JobStatus.DONE,
        process_count=Job.process_count + 1,
        claim_token=None,
        lease_until=None,
        last_error=None,
        finished_at=now,
    )


async def retry_later(session: AsyncSession, job: ClaimedJob, now: datetime, error: str) -> None:
    """Возвращает задание в очередь после ошибки обработчика, с паузой перед новой попыткой."""
    await _owned_update(
        session,
        job,
        status=JobStatus.QUEUED,
        claim_token=None,
        lease_until=None,
        run_after=now + RETRY_DELAY * job.attempt,
        last_error=error[:500],
    )


async def give_up(session: AsyncSession, job: ClaimedJob, now: datetime, error: str) -> None:
    """Закрывает задание как окончательно неудачное."""
    await _owned_update(
        session,
        job,
        status=JobStatus.FAILED,
        claim_token=None,
        lease_until=None,
        last_error=error[:500],
        finished_at=now,
    )


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> JobView:
    """Возвращает состояние задания по идентификатору."""
    job = await session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError("Задание не найдено")
    return _view(job)


async def get_jobs(session: AsyncSession, job_ids: list[uuid.UUID]) -> dict[uuid.UUID, JobView]:
    """Возвращает состояния нескольких заданий одним запросом."""
    jobs = await session.scalars(select(Job).where(Job.id.in_(job_ids)))
    return {job.id: _view(job) for job in jobs}
