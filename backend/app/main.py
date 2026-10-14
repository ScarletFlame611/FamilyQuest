from typing import Annotated, Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session

app = FastAPI(title="FamilyQuest API", openapi_url="/api/openapi.json", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
