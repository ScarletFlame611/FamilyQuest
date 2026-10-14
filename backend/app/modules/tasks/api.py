import uuid
from dataclasses import asdict

from fastapi import APIRouter, Response, status

from app.core.idempotency import IdempotencyKeyHeader, run_idempotent
from app.deps import AdultDep, MemberDep, SessionDep
from app.modules.tasks import service
from app.modules.tasks.schemas import RejectIn, TaskCreateIn, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _out(view: service.TaskView) -> TaskOut:
    return TaskOut(**asdict(view))


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_task(
    body: TaskCreateIn, adult: AdultDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> Response:
    async def action() -> TaskOut:
        return _out(
            await service.create_task(
                session,
                adult.family_id,
                adult.member_id,
                body.title,
                body.icon,
                body.points,
                body.assignee_id,
            )
        )

    return await run_idempotent(
        session, adult.member_id, key, f"create:{body.model_dump_json()}", action, 201
    )


@router.get("/my")
async def my_tasks(member: MemberDep, session: SessionDep) -> list[TaskOut]:
    views = await service.list_my_tasks(session, member.family_id, member.member_id)
    return [_out(view) for view in views]


@router.get("/board")
async def board(member: MemberDep, session: SessionDep) -> list[TaskOut]:
    return [_out(view) for view in await service.list_board(session, member.family_id)]


@router.get("/pending")
async def pending(adult: AdultDep, session: SessionDep) -> list[TaskOut]:
    return [_out(view) for view in await service.list_pending(session, adult.family_id)]


@router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, member: MemberDep, session: SessionDep) -> TaskOut:
    return _out(await service.get_task(session, member.family_id, task_id))


@router.post("/{task_id}/take", response_model=TaskOut)
async def take(
    task_id: uuid.UUID, member: MemberDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> Response:
    async def action() -> TaskOut:
        return _out(await service.take(session, member.family_id, task_id, member.member_id))

    return await run_idempotent(session, member.member_id, key, f"take:{task_id}", action)


@router.post("/{task_id}/mark", response_model=TaskOut)
async def mark(
    task_id: uuid.UUID, member: MemberDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> Response:
    async def action() -> TaskOut:
        return _out(await service.mark(session, member.family_id, task_id, member.member_id))

    return await run_idempotent(session, member.member_id, key, f"mark:{task_id}", action)


@router.post("/{task_id}/reject", response_model=TaskOut)
async def reject(
    task_id: uuid.UUID,
    body: RejectIn,
    adult: AdultDep,
    session: SessionDep,
    key: IdempotencyKeyHeader = None,
) -> Response:
    async def action() -> TaskOut:
        return _out(await service.reject(session, adult.family_id, task_id, body.reason))

    return await run_idempotent(
        session, adult.member_id, key, f"reject:{task_id}:{body.reason}", action
    )
