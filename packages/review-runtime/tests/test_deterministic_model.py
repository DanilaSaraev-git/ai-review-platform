from pathlib import Path

from review_runtime.models.deterministic import DeterministicModelGateway

ROOT = Path(__file__).parents[3]


def test_gateway_selects_expected_resource_only_by_full_exact_tuple() -> None:
    gateway = DeterministicModelGateway.from_manifest(
        ROOT / "tests/fixtures/synthetic-review/trusted-manifest.v1.json"
    )
    manifest = gateway.bindings[0]
    assert gateway.match(**gateway.selector(manifest)) is manifest
    changed = gateway.selector(manifest) | {"engine_version": "1.0.1"}
    assert gateway.match(**changed) is None


def test_gateway_has_no_network_or_marker_fallback() -> None:
    gateway = DeterministicModelGateway.from_manifest(
        ROOT / "tests/fixtures/synthetic-review/trusted-manifest.v1.json"
    )
    assert gateway.external_connection_attempts == []
    assert (
        gateway.match(
            primary_document_sha256="0" * 64,
            review_profile_semantic_digest="1" * 64,
            skill_package_sha256="2" * 64,
            parser_settings_digest="3" * 64,
            engine_version="1.0.0",
        )
        is None
    )
