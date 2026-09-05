from typing import Any

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import Response
from pydantic import ValidationError
from review_core.domain.errors import InvalidRequest

from review_api.dto import CreateReviewRunDTO

router = APIRouter(prefix="/v1/workspaces/{workspace_id}")


@router.get("/review-runs")
def list_runs(
    request: Request, workspace_id: str, cursor: str | None = None, limit: int = Query(20, ge=1, le=100)
) -> Any:
    return request.app.state.platform.list_runs(workspace_id, cursor, limit)


@router.post("/review-runs", status_code=202)
async def create_run(
    request: Request,
    response: Response,
    workspace_id: str,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    if idempotency_key is None:
        raise InvalidRequest("missing_idempotency_key", "Idempotency-Key is required.")
    try:
        body = CreateReviewRunDTO.model_validate(await request.json()).model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        raise InvalidRequest("invalid_review_run", "Review run body is invalid.") from error
    runtime = request.app.state.ml_runtime
    if runtime is None:
        import anyio

        value = await anyio.to_thread.run_sync(
            request.app.state.platform.create_run, workspace_id, body, idempotency_key
        )
    else:
        value = await runtime.create_run(workspace_id, body, idempotency_key)
    response.headers["Location"] = f"/v1/workspaces/{workspace_id}/review-runs/{value['id']}"
    return value


@router.get("/review-runs/{run_id}")
def get_run(request: Request, workspace_id: str, run_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.platform.get_run(workspace_id, run_id).value


@router.post("/review-runs/{run_id}/cancel", status_code=202)
def cancel_run(request: Request, workspace_id: str, run_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.platform.cancel_run(workspace_id, run_id)


@router.get("/review-runs/{run_id}/report")
def get_report(request: Request, workspace_id: str, run_id: str):  # type: ignore[no-untyped-def]
    body, etag = request.app.state.platform.report(workspace_id, run_id)
    return Response(content=body, media_type="application/json", headers={"ETag": etag})


@router.get("/review-runs/{run_id}/finding-states")
def list_finding_states(request: Request, workspace_id: str, run_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.platform.states(workspace_id, run_id)
