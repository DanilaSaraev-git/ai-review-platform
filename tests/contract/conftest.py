from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from review_api.app import create_app


@pytest.fixture
async def client() -> AsyncClient:
    app = create_app(composition="fixture")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as value:
        yield value
