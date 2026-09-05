from httpx import ASGITransport, AsyncClient
from review_api.app import create_app


async def test_served_openapi_is_canonical_and_no_auth() -> None:
    app = create_app(composition="fixture")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        schema = (await client.get("/v1/openapi.json")).json()
    assert schema["info"]["version"] == "1.0.2"
    assert schema["security"] == []
    assert "securitySchemes" not in schema.get("components", {})
