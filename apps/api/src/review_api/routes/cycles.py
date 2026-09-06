"""Additive document-family, review-cycle and export endpoints."""

from __future__ import annotations

from functools import partial
from typing import Any, Literal
from urllib.parse import quote
from uuid import UUID

import anyio
from fastapi import APIRouter, File, Header, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from review_core.domain.errors import InvalidRequest, PayloadTooLarge

router = APIRouter(prefix="/v1/workspaces/{workspace_id}")


class CompareDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: int = Field(ge=0)


class LinkDTO(CompareDTO):
    previous_issue_id: UUID | None


class ResolutionDTO(CompareDTO):
    status: Literal["open", "resolved"]
    reason: str = Field(min_length=1, max_length=4000)


async def parsed(request: Request, model: type[BaseModel]) -> dict[str, Any]:
    try:
        value = model.model_validate_json(await request.body()).model_dump(mode="json")
        if "reason" in value and not value["reason"].strip():
            raise ValueError("Reason cannot be blank")
        return value
    except (ValidationError, ValueError) as error:
        raise InvalidRequest("invalid_review_cycle", "Review cycle request is invalid.") from error


@router.get("/document-families")
def list_families(
    request: Request, workspace_id: str, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)
) -> Any:
    return request.state.platform.cycles.list_families(workspace_id, cursor, limit)


@router.get("/document-families/{family_id}")
def get_family(request: Request, workspace_id: str, family_id: str) -> Any:
    return request.state.platform.cycles.family(workspace_id, family_id)


@router.get("/document-families/{family_id}/versions")
def list_versions(
    request: Request,
    workspace_id: str,
    family_id: str,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> Any:
    return request.state.platform.cycles.list_versions(workspace_id, family_id, cursor, limit)


@router.get("/document-families/{family_id}/review-runs")
def list_family_runs(
    request: Request,
    workspace_id: str,
    family_id: str,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=100),
) -> Any:
    return request.state.platform.cycles.list_runs(workspace_id, family_id, cursor, limit)


@router.get("/documents/{document_id}/family")
def get_version_family(request: Request, workspace_id: str, document_id: str) -> Any:
    return request.state.platform.cycles.version(workspace_id, document_id)


@router.post("/document-families/{family_id}/versions", status_code=201)
async def upload_version(
    request: Request,
    workspace_id: str,
    family_id: str,
    file: UploadFile = File(...),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    if idempotency_key is None:
        raise InvalidRequest("missing_idempotency_key", "Idempotency-Key is required.")
    platform = request.state.platform
    await anyio.to_thread.run_sync(platform.cycles.family, workspace_id, family_id)
    content = bytearray()
    limit = platform.max_upload_bytes
    while len(content) <= limit:
        chunk = await file.read(min(1024 * 1024, limit + 1 - len(content)))
        if not chunk:
            break
        content.extend(chunk)
    if len(content) > limit:
        raise PayloadTooLarge("Document exceeds configured byte limit.")
    filename, media = file.filename or "document", file.content_type or "application/octet-stream"
    if request.app.state.guest_access:
        from review_runtime.security.guest_storage import upload_with_guest_limits

        uploaded = await anyio.to_thread.run_sync(
            partial(
                upload_with_guest_limits,
                platform,
                request.app.state.guest_storage_limits,
                workspace_id,
                filename,
                media,
                bytes(content),
                family_id=family_id,
                version_key=idempotency_key,
            )
        )
        return await anyio.to_thread.run_sync(platform.cycles.version, workspace_id, uploaded["id"])
    return await anyio.to_thread.run_sync(
        platform.cycles.upload_version,
        workspace_id,
        family_id,
        filename,
        media,
        bytes(content),
        idempotency_key,
    )


@router.get("/review-runs/{run_id}/review-cycle")
def get_cycle(request: Request, workspace_id: str, run_id: str) -> Any:
    return request.state.platform.cycles.get(workspace_id, run_id)


@router.post("/review-runs/{run_id}/review-cycle/compare")
async def compare_cycle(request: Request, workspace_id: str, run_id: str) -> Any:
    body = await parsed(request, CompareDTO)
    return await anyio.to_thread.run_sync(
        request.state.platform.cycles.compare, workspace_id, run_id, body["expected_revision"]
    )


@router.put("/review-runs/{run_id}/review-cycle/links/{finding_id}")
async def link_cycle(request: Request, workspace_id: str, run_id: str, finding_id: str) -> Any:
    body = await parsed(request, LinkDTO)
    return await anyio.to_thread.run_sync(
        partial(request.state.platform.cycles.mutate, workspace_id, run_id, finding_id, body, link=True)
    )


@router.put("/review-runs/{run_id}/review-cycle/issues/{issue_id}/resolution")
async def resolve_issue(request: Request, workspace_id: str, run_id: str, issue_id: str) -> Any:
    body = await parsed(request, ResolutionDTO)
    return await anyio.to_thread.run_sync(
        partial(request.state.platform.cycles.mutate, workspace_id, run_id, issue_id, body, link=False)
    )


@router.get("/review-runs/{run_id}/report.pdf")
def export_pdf(request: Request, workspace_id: str, run_id: str) -> Response:
    from review_runtime.report_export import render_review_pdf

    snapshot = request.state.platform.cycles.export_snapshot(workspace_id, run_id)
    name = f"{snapshot['family']['name']}-v{snapshot['version']['version_number']}.pdf"
    return Response(
        content=render_review_pdf(snapshot),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(name, safe='')}",
            "Cache-Control": "no-store",
        },
    )
