from __future__ import annotations

from pathlib import Path

import pytest

from tests.contract.contract_helpers import (
    load_json_no_duplicates,
    materialize_defaults,
    validate_runtime_config,
)

ROOT = Path(__file__).parents[2]
SCHEMA = load_json_no_duplicates(
    ROOT / "specs/003-backend-implementation/contracts/runtime-config.v1.schema.json"
)


def test_root_default_materializes_to_valid_unbound_policy() -> None:
    value = materialize_defaults(SCHEMA, {})
    validate_runtime_config(SCHEMA, value)
    assert value["deterministic_gateway"]["trusted_fixture_bindings"] == []
    assert value["model_gateway"]["optional_openai_compatible"]["auto_download"] is False


def test_cross_field_lease_invariant() -> None:
    value = materialize_defaults(SCHEMA, {})
    value["leases"]["extraction"] = {"lease_seconds": 20, "heartbeat_seconds": 10}
    with pytest.raises(ValueError, match="heartbeat"):
        validate_runtime_config(SCHEMA, value)


def _binding(binding_id: str = "binding-1", fill: str = "a") -> dict[str, str]:
    return {
        "binding_id": binding_id,
        "primary_document_sha256": fill * 64,
        "review_profile_semantic_digest": "b" * 64,
        "skill_package_sha256": "c" * 64,
        "parser_settings_digest": "d" * 64,
        "engine_version": "1.0.0",
        "expected_output_resource_id": f"resource-{fill}",
        "expected_output_sha256": "e" * 64,
    }


def test_binding_ids_and_selector_tuples_are_independently_unique() -> None:
    value = materialize_defaults(SCHEMA, {})
    value["deterministic_gateway"]["trusted_fixture_bindings"] = [_binding(), _binding(fill="f")]
    with pytest.raises(ValueError, match="binding_id"):
        validate_runtime_config(SCHEMA, value)

    value["deterministic_gateway"]["trusted_fixture_bindings"] = [_binding(), _binding("binding-2")]
    with pytest.raises(ValueError, match="selector"):
        validate_runtime_config(SCHEMA, value)
