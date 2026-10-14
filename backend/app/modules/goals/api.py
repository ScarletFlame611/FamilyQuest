from dataclasses import asdict

from fastapi import APIRouter

from app.deps import MemberDep, SessionDep
from app.modules.goals import service
from app.modules.goals.schemas import GoalOut

router = APIRouter(prefix="/api", tags=["goal"])


@router.get("/goal")
async def goal(member: MemberDep, session: SessionDep) -> GoalOut:
    return GoalOut(**asdict(await service.get_active_goal(session, member.family_id)))
