from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.core.errors import (
    ConflictError,
    DomainError,
    ForbiddenError,
    InvalidInputError,
    NotFoundError,
    TooManyAttemptsError,
    UnauthorizedError,
)
from app.modules.child_mode.api import router as child_mode_router
from app.modules.families.api import router as families_router
from app.modules.ledger.api import router as ledger_router
from app.modules.rewards.api import router as rewards_router
from app.modules.tasks.api import router as tasks_router
from app.modules.users.api import router as users_router

app = FastAPI(title="FamilyQuest API", openapi_url="/api/openapi.json", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    users_router,
    families_router,
    child_mode_router,
    tasks_router,
    ledger_router,
    rewards_router,
):
    app.include_router(router)

STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (UnauthorizedError, 401),
    (ForbiddenError, 403),
    (NotFoundError, 404),
    (ConflictError, 409),
    (InvalidInputError, 422),
    (TooManyAttemptsError, 429),
]


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
    status = next(code for cls, code in STATUS_BY_ERROR if isinstance(error, cls))
    return JSONResponse(status_code=status, content={"detail": error.message, **error.extra})


class HealthOut(BaseModel):
    status: Literal["ok", "unavailable"]


@app.get("/api/health", response_model=HealthOut, responses={503: {"model": HealthOut}})
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthOut | JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except (OSError, SQLAlchemyError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return HealthOut(status="ok")
