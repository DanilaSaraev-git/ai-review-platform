from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from review_api.app import create_app
from review_runtime.postgres.platform import PostgresReviewPlatform


def test_durable_composition_uses_normalized_postgres_platform(durable_app) -> None:  # type: ignore[no-untyped-def]
    assert isinstance(durable_app.state.platform, PostgresReviewPlatform)


def test_readiness_checks_mvp_dependencies_only(durable_client) -> None:  # type: ignore[no-untyped-def]
    response = durable_client.get("/health/ready")

    assert response.status_code == 200
    value = response.json()
    assert value["status"] == "ready"
    assert value["checks"] == {
        "database": True,
        "business_schema": True,
        "exact_seed": True,
        "artifact_store": True,
    }


@pytest.mark.parametrize("mutation", ["drift", "missing"])
def test_readiness_rejects_unavailable_exact_expected_output(
    mutation: str,
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    config_path = tmp_path / "runtime-config.json"
    config_path.write_bytes(
        (root / "deploy/compose/config/runtime-config.synthetic.v1.json").read_bytes()
    )
    expected_output_path = tmp_path / "expected-output.json"
    expected_output = (
        root / "deploy/compose/config/trusted-fixture-output.synthetic.v1.json"
    ).read_bytes()
    expected_output_path.write_bytes(expected_output)
    for field, value in operator_settings.model_dump().items():
        monkeypatch.setenv(f"REVIEW_{field.upper()}", str(value))
    monkeypatch.setenv("REVIEW_RUNTIME_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("REVIEW_EXPECTED_OUTPUT_PATH", str(expected_output_path))
    app = create_app(composition="durable")
    client = TestClient(app)
    assert client.get("/health/ready").status_code == 200

    if mutation == "drift":
        expected_output_path.write_bytes(expected_output + b"\n")
    else:
        expected_output_path.unlink()

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["exact_seed"] is False


def test_readiness_rejects_runtime_config_without_release_fixture_binding(
    monkeypatch: pytest.MonkeyPatch,
    operator_settings,  # type: ignore[no-untyped-def]
    tmp_path: Path,
) -> None:
    root = Path(__file__).parents[2]
    config = json.loads(
        (root / "deploy/compose/config/runtime-config.synthetic.v1.json").read_text()
    )
    config["deterministic_gateway"]["trusted_fixture_bindings"][0][
        "primary_document_sha256"
    ] = "0" * 64
    config_path = tmp_path / "runtime-config.json"
    config_path.write_text(json.dumps(config))
    for field, value in operator_settings.model_dump().items():
        monkeypatch.setenv(f"REVIEW_{field.upper()}", str(value))
    monkeypatch.setenv("REVIEW_RUNTIME_CONFIG_PATH", str(config_path))
    app = create_app(composition="durable")

    response = TestClient(app).get("/health/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["exact_seed"] is False
