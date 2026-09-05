from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/v1/bootstrap")
def get_bootstrap(request: Request):  # type: ignore[no-untyped-def]
    return request.app.state.platform.bootstrap()


@router.get("/v1/openapi.json", include_in_schema=False)
def get_openapi(request: Request):  # type: ignore[no-untyped-def]
    return request.app.openapi()
