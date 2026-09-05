from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_default_compose_has_no_model_egress() -> None:
    compose = yaml.safe_load((ROOT / "deploy/compose/compose.yaml").read_text())

    assert compose["networks"]["internal"]["internal"] is True
    assert compose["services"]["api"]["networks"] == ["internal"]
    assert "model-egress" not in compose["networks"]


def test_external_model_override_is_explicit_and_secret_value_is_not_tracked() -> None:
    override_path = ROOT / "deploy/compose/compose.external-model.yaml"
    override = yaml.safe_load(override_path.read_text())
    api = override["services"]["api"]

    assert api["environment"]["REVIEW_COMPOSITION"] == "ml"
    assert api["environment"]["REVIEW_MODEL_CREDENTIAL_PATH"] == "/run/secrets/model-api-key"
    assert api["environment"]["REVIEW_SKILL_PACKAGE_PATH"] == "/app/skills/review-data-spec"
    assert api["networks"] == ["internal", "model-egress"]
    assert api["secrets"] == ["model-api-key"]
    assert override["secrets"]["model-api-key"]["file"].startswith(
        "${REVIEW_MODEL_CREDENTIAL_FILE:"
    )
    assert override["networks"]["model-egress"]["internal"] is False
    assert "api_key" not in override_path.read_text().lower()


def test_proxy_wait_budget_exceeds_review_deadline_and_finalization() -> None:
    nginx = (ROOT / "deploy/compose/nginx.conf").read_text()

    assert nginx.count("proxy_read_timeout 330s;") == 2
    assert nginx.count("proxy_send_timeout 330s;") == 2
