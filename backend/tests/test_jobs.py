from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_utc
from app.modules.jobs import service as jobs
from app.modules.jobs.enums import JobKind, JobStatus

pytestmark = [pytest.mark.anyio, pytest.mark.risk]

LEASE = timedelta(seconds=30)


async def queued(session: AsyncSession) -> None:
    await jobs.enqueue(session, JobKind.FAMILY_EXPORT, {"export_id": "test"})
    await session.commit()


async def test_claimed_job_is_not_given_twice_until_lease_expires(session: AsyncSession):
    await queued(session)
    start = now_utc()
    first = await jobs.claim(session, start, LEASE)
    assert first is not None and first.attempt == 1
    assert await jobs.claim(session, start + LEASE / 2, LEASE) is None

    again = await jobs.claim(session, start + LEASE + timedelta(seconds=1), LEASE)
    assert again is not None
    assert again.id == first.id
    assert again.attempt == 2
    assert again.claim_token != first.claim_token


async def test_old_owner_cannot_complete_after_job_was_reissued(session: AsyncSession):
    await queued(session)
    start = now_utc()
    old = await jobs.claim(session, start, LEASE)
    new = await jobs.claim(session, start + LEASE + timedelta(seconds=1), LEASE)
    assert old is not None and new is not None
    await jobs.complete(session, new, start)
    await session.commit()

    with pytest.raises(jobs.StaleOwnerError):
        await jobs.complete(session, old, start)
    await session.rollback()
    state = await jobs.get_job(session, new.id)
    assert state.status is JobStatus.DONE
    assert state.process_count == 1


async def test_job_runs_out_of_attempts(session: AsyncSession):
    await queued(session)
    moment = now_utc()
    for _ in range(jobs.MAX_ATTEMPTS):
        claimed = await jobs.claim(session, moment, LEASE)
        assert claimed is not None and not jobs.exhausted(claimed)
        moment += LEASE + timedelta(seconds=1)
    last = await jobs.claim(session, moment, LEASE)
    assert last is not None and jobs.exhausted(last)

    await jobs.give_up(session, last, moment, "Попытки закончились")
    await session.commit()
    assert (await jobs.get_job(session, last.id)).status is JobStatus.FAILED
    assert await jobs.claim(session, moment + LEASE * 10, LEASE) is None


async def test_failed_attempt_returns_to_queue_after_pause(session: AsyncSession):
    await queued(session)
    start = now_utc()
    claimed = await jobs.claim(session, start, LEASE)
    assert claimed is not None
    await jobs.retry_later(session, claimed, start, "сбой")
    await session.commit()

    assert await jobs.claim(session, start + timedelta(seconds=1), LEASE) is None
    retried = await jobs.claim(session, start + jobs.RETRY_DELAY, LEASE)
    assert retried is not None and retried.id == claimed.id and retried.attempt == 2
