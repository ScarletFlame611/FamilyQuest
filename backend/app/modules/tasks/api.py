import uuid
from dataclasses import asdict

from fastapi import APIRouter

from app.deps import MemberDep, SessionDep
from app.modules.tasks import service
from app.modules.tasks.schemas import TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: uuid.UUID, member: MemberDep, session: SessionDep) -> TaskOut:
    return TaskOut(**asdict(await service.get_task(session, member.family_id, task_id)))
