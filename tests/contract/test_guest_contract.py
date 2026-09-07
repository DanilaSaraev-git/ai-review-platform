from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tools.contracts.build_guest_contract import guest_contract

ROOT = Path(__file__).parents[2]
METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
PROBLEM = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/Problem"}}}


def _load(family: str) -> dict[str, Any]:
    return yaml.safe_load((ROOT / f"contracts/review-platform/{family}/openapi.yaml").read_text())


def test_committed_guest_contract_matches_the_generator() -> None:
    assert _load("guest-v1") == guest_contract()


def test_every_guest_workspace_operation_requires_cookie_and_documents_auth_errors() -> None:
    schema = _load("guest-v1")
    assert schema["components"]["securitySchemes"] == {
        "GuestSession": {"type": "apiKey", "in": "cookie", "name": "review_guest"}
    }
    assert schema["security"] == [{"GuestSession": []}]
    count = 0
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method not in METHODS:
                continue
            assert operation["responses"]["403"]["content"] == PROBLEM, (method, path)
            if path == "/v1/bootstrap":
                assert operation["security"] == []
                cookie = operation["responses"]["200"]["headers"]["Set-Cookie"]
                for flag in ("review_guest", "HttpOnly", "Secure", "SameSite=Lax", "Max-Age=2592000"):
                    assert flag in cookie["description"]
            else:
                count += 1
                assert operation.get("security", schema["security"]) == [{"GuestSession": []}], (method, path)
                assert operation["responses"]["401"]["content"] == PROBLEM, (method, path)
    assert count > 0


def test_guest_contract_reuses_trusted_payloads_and_keeps_the_trusted_boundary_unchanged() -> None:
    guest, trusted = _load("guest-v1"), _load("v1")
    assert trusted["info"]["version"] == "1.2.0"
    assert trusted["security"] == []
    assert "securitySchemes" not in trusted["components"]
    assert guest["components"]["schemas"] == trusted["components"]["schemas"]
    assert guest["components"]["parameters"] == trusted["components"]["parameters"]
    assert guest["paths"].keys() == trusted["paths"].keys()
    for path, item in trusted["paths"].items():
        assert guest["paths"][path].keys() == item.keys()
        for method, operation in item.items():
            if method not in METHODS:
                assert guest["paths"][path][method] == operation
                continue
            candidate = guest["paths"][path][method]
            for field in ("operationId", "parameters", "requestBody"):
                assert candidate.get(field) == operation.get(field), (method, path, field)
            assert "401" not in operation["responses"]
            assert "403" not in operation["responses"]
            for status, response in operation["responses"].items():
                if status.startswith("2"):
                    assert candidate["responses"][status].get("content") == response.get("content"), (
                        method,
                        path,
                        status,
                    )


def test_guest_upload_contract_distinguishes_personal_quota_and_server_capacity() -> None:
    responses = _load("guest-v1")["paths"]["/v1/workspaces/{workspaceId}/documents"]["post"]["responses"]
    assert responses["413"]["content"] == PROBLEM
    assert "guest_storage_limit" in responses["413"]["description"]
    assert responses["503"]["content"] == PROBLEM
    assert "storage_unavailable" in responses["503"]["description"]
    assert "Existing files remain readable" in responses["503"]["description"]
