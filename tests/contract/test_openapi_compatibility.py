from httpx import ASGITransport, AsyncClient
from review_api.app import create_app


async def test_served_openapi_is_canonical_and_no_auth() -> None:
    app = create_app(composition="fixture")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        canonical_response = await client.get("/v1/openapi.json")
        root_response = await client.get("/openapi.json")
        docs_response = await client.get("/docs/")
        schema = canonical_response.json()

    assert canonical_response.status_code == 200
    assert root_response.status_code == 200
    assert root_response.json() == schema
    assert docs_response.status_code == 200
    assert 'url: "../v1/openapi.json"' in docs_response.text
    assert schema["info"]["version"] == "1.2.0"
    assert schema["security"] == []
    assert "securitySchemes" not in schema.get("components", {})
