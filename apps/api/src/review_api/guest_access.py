"""Resolve an opaque browser session before any workspace operation."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import anyio
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from review_runtime.security.guest_sessions import COOKIE_NAME, SESSION_TTL_SECONDS, GuestSessionStore


def guest_access_enabled(value: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError("REVIEW_GUEST_ACCESS must be true or false")
    return value == "true"


def _problem(request: Request, status: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"/problems/{code.replace('_', '-')}",
            "title": "Guest access",
            "status": status,
            "detail": detail,
            "instance": request.url.path,
            "code": code,
            "request_id": getattr(request.state, "request_id", "guest-access"),
            "errors": [],
        },
        headers={"Cache-Control": "no-store"},
    )


async def guest_access_context(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    request.state.platform = request.app.state.platform
    request.state.ml_runtime = request.app.state.ml_runtime
    if (
        not request.app.state.guest_access
        or not request.url.path.startswith("/v1/")
        or request.url.path == "/v1/openapi.json"
    ):
        return await call_next(request)

    origin = request.headers.get("origin")
    host = request.headers.get("host", "")
    # The gateway and inner proxy preserve Host and overwrite forwarded headers.
    # Reject browser cross-origin requests, including bootstrap/session creation.
    allowed_origins = {f"https://{host}"}
    if request.url.scheme == "http":
        allowed_origins.add(f"http://{host}")
    if origin is not None and origin not in allowed_origins:
        return _problem(request, 403, "cross_origin_forbidden", "Use this site's own browser session.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        return _problem(request, 403, "cross_origin_forbidden", "Cross-site requests are not allowed.")

    store: GuestSessionStore = request.app.state.guest_sessions
    token = request.cookies.get(COOKIE_NAME)
    session = await anyio.to_thread.run_sync(store.resolve, token)
    if session is None:
        if request.url.path != "/v1/bootstrap" or request.method != "GET":
            return _problem(
                request, 401, "guest_session_required", "Open the site to start or restore a guest session."
            )
        token, session = await anyio.to_thread.run_sync(store.create)

    assert session is not None
    async with request.app.state.guest_contexts.use(session.workspace_id, session.actor_id) as context:
        request.state.platform = context.platform
        request.state.ml_runtime = context.runtime
        response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Cookie"
    assert token is not None
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return response
