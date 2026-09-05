from typing import Any

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import Response
from review_core.canonical import strong_etag

router = APIRouter(prefix="/v1/workspaces/{workspace_id}")


@router.get("/documents")
def list_documents(
    request: Request, workspace_id: str, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)
) -> Any:
    return request.app.state.platform.list_documents(workspace_id, cursor, limit)


@router.post("/documents", status_code=201)
async def upload_document(request: Request, workspace_id: str, file: UploadFile = File(...)):  # type: ignore[no-untyped-def]
    content = await file.read()
    return request.app.state.platform.upload(
        workspace_id, file.filename or "document", file.content_type or "application/octet-stream", content
    )


@router.get("/documents/{document_id}")
def get_document(request: Request, workspace_id: str, document_id: str):  # type: ignore[no-untyped-def]
    platform = request.app.state.platform
    return platform.document_value(platform.get_document(workspace_id, document_id))


@router.get("/documents/{document_id}/content")
def download_document(request: Request, workspace_id: str, document_id: str):  # type: ignore[no-untyped-def]
    record = request.app.state.platform.get_document(workspace_id, document_id)
    return Response(
        content=record.content,
        media_type="application/octet-stream",
        headers={
            "ETag": strong_etag(record.content),
            "Content-Disposition": f'attachment; filename="{record.filename}"',
        },
    )
