from fastapi import APIRouter, Request
from pydantic import ValidationError
from review_core.domain.errors import InvalidRequest

from review_api.dto import CreateReviewProfileDTO

router = APIRouter(prefix="/v1/workspaces/{workspace_id}")


@router.get("/profiles")
def list_profiles(request: Request, workspace_id: str):  # type: ignore[no-untyped-def]
    return request.app.state.platform.list_profiles(workspace_id)


@router.post("/profiles", status_code=201)
async def create_profile(request: Request, workspace_id: str):  # type: ignore[no-untyped-def]
    import anyio

    try:
        body = CreateReviewProfileDTO.model_validate(await request.json()).model_dump(mode="json")
    except (ValidationError, ValueError) as error:
        raise InvalidRequest("invalid_profile", "Review profile body is invalid.") from error
    if len(body["checks"]) != len(set(body["checks"])):
        raise InvalidRequest("invalid_profile", "Profile checks must be unique.")
    return await anyio.to_thread.run_sync(
        request.app.state.platform.create_profile, workspace_id, body
    )


@router.get("/model-profiles")
def list_model_profiles(request: Request, workspace_id: str):  # type: ignore[no-untyped-def]
    method = getattr(request.app.state.platform, "list_model_profiles", None)
    if callable(method):
        return method(workspace_id)
    request.app.state.platform._workspace(workspace_id)
    return {"items": [request.app.state.platform.model_profile]}
