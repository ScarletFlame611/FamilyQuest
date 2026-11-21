import uuid
from dataclasses import asdict
from urllib.parse import quote

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse

from app.core.idempotency import IdempotencyKeyHeader, run_idempotent
from app.deps import AdultDep, SessionDep
from app.modules.exports import service
from app.modules.exports.schemas import ExportOut

router = APIRouter(prefix="/api/family/exports", tags=["exports"])


@router.post("", status_code=202, response_model=ExportOut)
async def request_export(
    adult: AdultDep, session: SessionDep, key: IdempotencyKeyHeader = None
) -> JSONResponse:
    async def action() -> ExportOut:
        view = await service.request_export(session, adult.family_id, adult.member_id)
        return ExportOut(**asdict(view))

    return await run_idempotent(
        session, adult.member_id, key, "family-export", action, status_code=202
    )


@router.get("")
async def list_exports(adult: AdultDep, session: SessionDep) -> list[ExportOut]:
    return [ExportOut(**asdict(v)) for v in await service.list_exports(session, adult.family_id)]


@router.get(
    "/{export_id}/file",
    response_class=Response,
    responses={200: {"content": {"application/zip": {}}}},
)
async def export_file(export_id: uuid.UUID, adult: AdultDep, session: SessionDep) -> Response:
    file = await service.get_file(session, adult.family_id, export_id)
    return Response(
        file.content,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(file.name)}"},
    )
