from __future__ import annotations

import os

import httpx
import pytest


@pytest.mark.local_model
def test_optional_existing_local_endpoint_or_safe_skip() -> None:
    endpoint = os.environ.get("REVIEW_LOCAL_MODEL_ENDPOINT", "http://127.0.0.1:11434")
    try:
        response = httpx.get(f"{endpoint}/api/tags", timeout=2, follow_redirects=False)
    except httpx.HTTPError:
        pytest.skip("no pre-existing local model endpoint; nothing was installed or downloaded")
    assert response.status_code == 200
