from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from review_runtime.config.model_profiles import (
    ModelProfile,
    ModelProfileSet,
    load_model_profiles,
    profile_config_digest,
)
from review_runtime.models.config import EndpointPolicy
from review_runtime.skills.executor import SkillExecutor
from review_runtime.skills.registry import SkillRegistry

ROOT = Path(__file__).parents[3]
PROFILE_SCHEMA = ROOT / "specs/004-llm-review-integration/contracts/model-profile.v1.schema.json"
EXTERNAL_EXAMPLE = ROOT / "deploy/compose/config/model-profile.external.example.json"
SKILL_SCHEMA = ROOT / "contracts/review-platform/v1/schemas/skill-manifest.schema.json"
SKILL_FIXTURE = ROOT / "tests/fixtures/ml-integration/skill"


def _profile(**overrides: object) -> ModelProfile:
    value: dict[str, object] = {
        "schema_version": "model-profile.v1",
        "id": "synthetic-http",
        "version": "1.0.0",
        "adapter_kind": "openai_compatible",
        "provider": "synthetic",
        "model": "synthetic-model",
        "checkpoint": None,
        "chat_url": "http://127.0.0.1:9999/chat/completions",
        "secret_ref": "REVIEW_SYNTHETIC_TOKEN",
        "capabilities": ["text_generation"],
        "context_window_tokens": 8192,
        "max_input_utf8_bytes": 12000,
        "max_output_tokens": 1024,
        "structured_output": "plain_json",
        "supported_parameters": ["max_tokens"],
        "request_options": {},
        "probe": None,
    }
    value.update(overrides)
    return ModelProfile.model_validate(value)


def test_model_profile_is_exact_immutable_and_matches_its_schema() -> None:
    profile = _profile()
    schema = json.loads(PROFILE_SCHEMA.read_text())

    Draft202012Validator(schema).validate(profile.model_dump(mode="json"))
    with pytest.raises(ValidationError):
        profile.version = "2.0.0"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        _profile(**{"secret": "raw-token"})
    with pytest.raises(TypeError, match="immutable"):
        profile.request_options["seed"] = 2048


def test_external_example_is_schema_valid_secret_free_and_matches_runtime_model() -> None:
    schema = json.loads(PROFILE_SCHEMA.read_text())
    value = json.loads(EXTERNAL_EXAMPLE.read_text())

    Draft202012Validator(schema).validate(value)
    profile = ModelProfile.model_validate(value)
    assert profile.model_dump(mode="json") == value
    assert profile.secret_ref == value["secret_ref"]
    assert profile.secret_ref is not None and profile.secret_ref.endswith("_TOKEN")
    assert "synthetic-secret" not in EXTERNAL_EXAMPLE.read_text()


def test_profile_digest_changes_for_semantics_but_not_environment_secret_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profile = _profile()
    first = profile_config_digest(profile)
    monkeypatch.setenv("REVIEW_SYNTHETIC_TOKEN", "first-secret")
    second = profile_config_digest(profile)
    monkeypatch.setenv("REVIEW_SYNTHETIC_TOKEN", "different-secret")

    assert first == second == profile_config_digest(profile)
    assert first != profile_config_digest(_profile(model="another-checkpoint"))


def test_profile_rejects_undeclared_options_and_duplicate_identity() -> None:
    with pytest.raises(ValidationError, match="supported"):
        _profile(request_options={"temperature": 0})
    with pytest.raises(ValidationError, match="secret"):
        _profile(request_options={"api_key": "do-not-store-this"}, supported_parameters=["api_key"])

    with pytest.raises(ValidationError, match="identity"):
        ModelProfileSet(profiles=(_profile(), _profile(model="different")))


def test_profile_loader_supports_existing_single_profile_and_explicit_set(tmp_path: Path) -> None:
    path = tmp_path / "profiles.json"
    first = _profile()
    second = _profile(id="synthetic-other", model="synthetic-other-model")
    path.write_text(first.model_dump_json())
    assert load_model_profiles(path) == (first,)
    values = [profile.model_dump(mode="json") for profile in (first, second)]
    path.write_text(json.dumps({"profiles": values}))
    assert load_model_profiles(path) == (first, second)


@pytest.mark.parametrize(
    "invalid",
    [
        {"profiles": []},
        {"profiles": [_profile().model_dump(mode="json")] * 2},
        {"profiles": [_profile().model_dump(mode="json")], "secret": "CANARY_SECRET"},
        {
            "profiles": [
                _profile().model_dump(mode="json"),
                _profile(id="other", provider="different-provider").model_dump(mode="json"),
            ]
        },
    ],
)
def test_profile_loader_rejects_ambiguous_sets_and_mixed_credentials(tmp_path: Path, invalid: object) -> None:
    path = tmp_path / "profiles.json"
    path.write_text(json.dumps(invalid))
    with pytest.raises(ValueError):
        load_model_profiles(path)


@pytest.mark.parametrize("name", ["yandex-deepseek", "yandex-qwen35b", "yandex-gpt-oss20b"])
def test_yandex_model_templates_follow_the_existing_profile_contract(name: str) -> None:
    value = json.loads((ROOT / f"deploy/compose/config/model-profile.{name}.json").read_text())
    Draft202012Validator(json.loads(PROFILE_SCHEMA.read_text())).validate(value)
    profile = ModelProfile.model_validate(value)
    assert profile.secret_ref == "YANDEX_API_KEY"  # noqa: S105 - this is a secret name, not a value
    assert profile.provider == "yandex"
    assert "${YANDEX_FOLDER_ID}" in profile.model
    assert profile.max_output_tokens == 16384


def test_gpt_oss_uses_provider_json_mode() -> None:
    value = json.loads(
        (ROOT / "deploy/compose/config/model-profile.yandex-gpt-oss20b.json").read_text()
    )

    assert value["structured_output"] == "native_json_object"
    assert value["version"] == "1.0.1"


def test_review_skill_requests_the_runtime_supplied_compact_schema() -> None:
    instructions = (ROOT / "skills/review-data-spec/SKILL.md").read_text()
    manifest = json.loads((ROOT / "skills/review-data-spec/manifest.json").read_text())

    assert "response schema supplied by the engine" in instructions
    assert "return only `review-output.v1`" not in instructions.lower()
    assert manifest["version"] == "1.0.2"


def test_profile_validation_performs_no_dns_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_dns(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("configuration validation must not resolve DNS")

    monkeypatch.setattr("socket.getaddrinfo", unexpected_dns)
    assert EndpointPolicy("https://models.invalid/exact/chat").validate() == (
        "https://models.invalid/exact/chat"
    )
    assert _profile(chat_url="https://models.invalid/exact/chat").model == "synthetic-model"


def test_skill_digest_covers_manifest_semantics_and_recognizes_legacy_snapshot(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    shutil.copytree(SKILL_FIXTURE, package)
    registry = SkillRegistry(SKILL_SCHEMA, engine_version="0.1.0", model_capabilities={"text_generation"})
    original = registry.resolve(package)
    original_manifest = json.loads((package / "manifest.json").read_text())
    legacy_digest = registry.legacy_package_digest(package, original_manifest)

    original_manifest["description"] = "Changed semantic description"
    (package / "manifest.json").write_text(json.dumps(original_manifest))
    changed_registry = SkillRegistry(
        SKILL_SCHEMA, engine_version="0.1.0", model_capabilities={"text_generation"}
    )
    changed = changed_registry.resolve(package)

    assert changed.package_digest != original.package_digest
    assert changed_registry.legacy_package_digest(package, changed.manifest) == legacy_digest
    assert changed_registry.matches_snapshot(package, changed.manifest, legacy_digest)
    with pytest.raises(ValueError, match="identity drift"):
        registry.resolve(package)


def test_skill_requirements_and_trusted_instruction_inventory_are_enforced(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    shutil.copytree(SKILL_FIXTURE, package)
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["requires"] = {"engine": ">=99.0.0", "model_capabilities": ["vision"]}
    manifest_path.write_text(json.dumps(manifest))

    registry = SkillRegistry(SKILL_SCHEMA, engine_version="0.1.0", model_capabilities={"text_generation"})
    with pytest.raises(ValueError, match="engine requirement"):
        registry.resolve(package)

    manifest["requires"]["engine"] = ">=0.1.0"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="model capabilities"):
        registry.resolve(package)

    resolved = SkillRegistry(
        SKILL_SCHEMA, engine_version="0.1.0", model_capabilities={"text_generation", "vision"}
    ).resolve(package)
    executor = SkillExecutor({}, package=resolved)
    review_instructions = executor.trusted_instructions("review")
    assert review_instructions.primary.startswith("# Synthetic review operation")
    assert [reference.path for reference in review_instructions.references] == ["references/test-boundary.md"]


def test_skill_rejects_an_undeclared_file_even_when_declared_hashes_match(tmp_path: Path) -> None:
    package = tmp_path / "skill"
    shutil.copytree(SKILL_FIXTURE, package)
    (package / "undeclared-instructions.md").write_text("Do something outside the package contract")

    registry = SkillRegistry(SKILL_SCHEMA, engine_version="0.1.0", model_capabilities={"text_generation"})
    with pytest.raises(ValueError, match="inventory is not exact"):
        registry.resolve(package)
