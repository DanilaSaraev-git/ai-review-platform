from __future__ import annotations

from pathlib import Path

import yaml
from httpx import AsyncClient

from tests.contract.contract_helpers import validate_schema

ROOT = Path(__file__).parents[2]
OPENAPI = yaml.safe_load((ROOT / "contracts/review-platform/v1/openapi.yaml").read_text())


def validate_component(name: str, value: object) -> None:
    validate_schema(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": f"#/components/schemas/{name}",
            "components": OPENAPI["components"],
        },
        value,
    )


async def test_bootstrap_and_document_runtime_values_match_canonical_schemas(client: AsyncClient) -> None:
    bootstrap = (await client.get("/v1/bootstrap")).json()
    validate_component("Bootstrap", bootstrap)
    workspace = bootstrap["workspace"]["id"]
    response = await client.post(
        f"/v1/workspaces/{workspace}/documents", files={"file": ("a.md", b"# A", "text/markdown")}
    )
    validate_component("Document", response.json())
