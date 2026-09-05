from __future__ import annotations

from uuid import uuid4

from fastapi import Request


async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    request.state.request_id = request.headers.get("X-Request-ID", str(uuid4()))[:128]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response
