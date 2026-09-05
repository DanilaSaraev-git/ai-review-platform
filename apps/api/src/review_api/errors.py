from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from review_core.domain.errors import DomainError


async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=error.status,
        media_type="application/problem+json",
        content={
            "type": f"/problems/{error.code.replace('_', '-')}",
            "title": error.title,
            "status": error.status,
            "detail": error.detail,
            "instance": request.url.path,
            "code": error.code,
            "request_id": request_id,
            "errors": error.errors,
        },
    )
