from typing import Any

from fastapi import APIRouter, Header, Request, Response
from pydantic import ValidationError
from review_core.domain.errors import InvalidRequest

from review_api.dto import CreateDialogueTurnDTO, PutFindingDecisionDTO, RetryDialogueTurnDTO

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/review-runs/{run_id}/findings/{finding_id}")


@router.get("/dialogue")
def get_dialogue(request: Request, workspace_id: str, run_id: str, finding_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.platform.get_dialogue(workspace_id, run_id, finding_id)


@router.post("/dialogue/turns", status_code=202)
async def create_turn(
    request: Request,
    response: Response,
    workspace_id: str,
    run_id: str,
    finding_id: str,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    if idempotency_key is None:
        raise InvalidRequest("missing_idempotency_key", "Idempotency-Key is required.")
    try:
        body = CreateDialogueTurnDTO.model_validate(await request.json()).model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        raise InvalidRequest("invalid_dialogue_turn", "Dialogue turn body is invalid.") from error
    runtime = request.app.state.ml_runtime
    if runtime is None:
        import anyio

        value = await anyio.to_thread.run_sync(
            request.app.state.platform.create_dialogue_turn,
            workspace_id,
            run_id,
            finding_id,
            body,
            idempotency_key,
        )
    else:
        value = await runtime.create_dialogue_turn(
            workspace_id, run_id, finding_id, body, idempotency_key
        )
    response.headers["Location"] = (
        f"/v1/workspaces/{workspace_id}/review-runs/{run_id}/findings/{finding_id}/dialogue"
    )
    return value


@router.post("/dialogue/turns/{turn_id}/retry", status_code=202)
async def retry_turn(
    request: Request,
    workspace_id: str,
    run_id: str,
    finding_id: str,
    turn_id: str,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> Any:
    if idempotency_key is None:
        raise InvalidRequest("missing_idempotency_key", "Idempotency-Key is required.")
    try:
        body = RetryDialogueTurnDTO.model_validate(await request.json()).model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        raise InvalidRequest("invalid_dialogue_retry", "Dialogue retry body is invalid.") from error
    runtime = request.app.state.ml_runtime
    if runtime is None:
        import anyio

        return await anyio.to_thread.run_sync(
            request.app.state.platform.retry_dialogue_turn,
            workspace_id,
            run_id,
            finding_id,
            turn_id,
            body,
            idempotency_key,
        )
    return await runtime.retry_dialogue_turn(
        workspace_id, run_id, finding_id, turn_id, body, idempotency_key
    )


@router.put("/decision")
async def put_decision(request: Request, workspace_id: str, run_id: str, finding_id: str):  # type: ignore[no-untyped-def]
    import anyio

    try:
        body = PutFindingDecisionDTO.model_validate(await request.json()).model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        raise InvalidRequest("invalid_decision", "Human Decision body is invalid.") from error
    return await anyio.to_thread.run_sync(
        request.app.state.platform.put_decision, workspace_id, run_id, finding_id, body
    )
