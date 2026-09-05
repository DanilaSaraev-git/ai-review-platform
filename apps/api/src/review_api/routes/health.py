from __future__ import annotations

from typing import Any

import psycopg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
def ready(request: Request) -> Any:
    if not hasattr(request.app.state.platform, "database_url"):
        return {"status": "ready", "composition": "fixture"}
    checks: dict[str, bool] = {}
    try:
        with psycopg.connect(request.app.state.platform.database_url, connect_timeout=2) as connection:
            checks["database"] = connection.execute("SELECT 1").fetchone() == (1,)
            checks["business_schema"] = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("20260905_0001",)
    except Exception:
        checks["database"] = False
        checks["business_schema"] = False
    try:
        checks["exact_seed"] = request.app.state.platform.check_seed()
    except Exception:
        checks["exact_seed"] = False
    try:
        checks["artifact_store"] = request.app.state.platform.artifacts.probe_writable()
    except Exception:
        checks["artifact_store"] = False
    if not all(checks.values()):
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})
    return {"status": "ready", "composition": "durable", "checks": checks}
