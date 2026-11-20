from dataclasses import asdict

from fastapi import APIRouter, Response, status

from app.core.idempotency import IdempotencyKeyHeader, run_idempotent
from app.deps import AdultDep, MemberDep, SessionDep
from app.modules.goals import service
from app.modules.goals.schemas import GoalCreateIn, GoalOut

router = APIRouter(prefix="/api", tags=["goal"])


@router.get("/goal")
async def goal(member: MemberDep, session: SessionDep) -> GoalOut:
    return GoalOut(**asdict(await service.get_active_goal(session, member.family_id)))


@router.post("/goal", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreateIn, adult: AdultDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> Response:
    async def action() -> GoalOut:
        await service.create_goal(session, adult.family_id, body.title, body.icon, body.target)
        return GoalOut(**asdict(await service.get_active_goal(session, adult.family_id)))

    return await run_idempotent(
        session, adult.member_id, key, f"goal:{body.model_dump_json()}", action, 201
    )
