import uuid
from dataclasses import asdict

from fastapi import APIRouter

from app.deps import MemberDep, SessionDep
from app.modules.rewards import service
from app.modules.rewards.schemas import RewardOut

router = APIRouter(prefix="/api/rewards", tags=["rewards"])


@router.get("/{reward_id}")
async def get_reward(reward_id: uuid.UUID, member: MemberDep, session: SessionDep) -> RewardOut:
    return RewardOut(**asdict(await service.get_reward(session, member.family_id, reward_id)))
