from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator
from review_core.dialogue.engine import DialogueEngine, DialogueMappingContext
from review_core.ports.models import (
    FinishReason,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    ModelCapabilities,
    ModelProfileSnapshot,
    TokenUsage,
)
from review_core.review.engine import ReviewFragment

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/ml-integration"
SCHEMA_PATH = ROOT / "specs/004-llm-review-integration/contracts/model-output.dialogue.v1.schema.json"


def _compact() -> dict:
    return json.loads((FIXTURES / "dialogue-response.json").read_text())


def _context() -> DialogueMappingContext:
    primary = (FIXTURES / "primary.md").read_text()
    supporting = (FIXTURES / "context.md").read_text()
    return DialogueMappingContext(
        fragments={
            "source-main-lines-1-2": ReviewFragment(
                id="source-main-lines-1-2",
                source_id="source-main",
                document_id="33333333-3333-4333-8333-333333333333",
                source_name="synthetic-primary.md",
                text=primary,
                location={
                    "kind": "text",
                    "line_start": 1,
                    "line_end": 2,
                    "char_start": 0,
                    "char_end": len(primary),
                },
            ),
            "source-context-1-lines-1-1": ReviewFragment(
                id="source-context-1-lines-1-1",
                source_id="source-context-1",
                document_id="44444444-4444-4444-8444-444444444444",
                source_name="synthetic-context.md",
                text=supporting,
                location={
                    "kind": "text",
                    "line_start": 1,
                    "line_end": 1,
                    "char_start": 0,
                    "char_end": len(supporting),
                },
            ),
        },
        provenance={
            "skill": {"id": "synthetic", "version": "1.0.0", "package_sha256": "a" * 64},
            "model": {
                "provider": "synthetic",
                "model": "fixture",
                "model_version": "test-only",
                "safe_parameters": {},
                "usage": {"input_tokens": None, "output_tokens": None},
            },
        },
    )


def _assistant_schema() -> dict:
    openapi = yaml.safe_load((ROOT / "contracts/review-platform/v1/openapi.yaml").read_text())
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": "#/components/schemas/AssistantResponse",
        "components": openapi["components"],
    }


def test_compact_dialogue_fixture_satisfies_model_output_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)

    Draft202012Validator(schema).validate(_compact())


@pytest.mark.parametrize(
    ("path", "field", "value"),
    [
        ((), "run_id", "service-run"),
        ((), "turn_id", "service-turn"),
        ((), "provenance", {}),
        ((), "human_decision", {"status": "confirmed"}),
        (("anchors", 0), "quote_start", 0),
        (("anchors", 0), "document_id", "service-document"),
    ],
)
def test_compact_dialogue_rejects_service_and_human_fields(
    path: tuple, field: str, value: object
) -> None:
    output = _compact()
    target: object = output
    for part in path:
        target = target[part]  # type: ignore[index]
    assert isinstance(target, dict)
    target[field] = value

    errors = list(Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(output))

    assert errors


def test_mapping_resolves_exact_evidence_and_attaches_only_factual_provenance() -> None:
    response = DialogueEngine().map_model_output(_compact(), context=_context())

    assert response["anchors"][0]["quote_start"] == 0
    assert response["anchors"][0]["quote_end"] == 23
    assert response["anchors"][1]["source_id"] == "source-context-1"
    assert response["provenance"] == _context().provenance
    Draft202012Validator(_assistant_schema()).validate(response)


def test_dialogue_mapping_rejects_ambiguous_evidence() -> None:
    output = _compact()
    output["anchors"][0]["quote"] = "r"

    with pytest.raises(ValueError, match="ambiguous"):
        DialogueEngine().map_model_output(output, context=_context())


def test_model_output_cannot_change_a_human_decision() -> None:
    decision = {"status": "confirmed", "reason": "Verified by an analyst", "revision": 4}
    before = copy.deepcopy(decision)

    response = DialogueEngine().map_model_output(_compact(), context=_context())

    assert decision == before
    assert not ({"human_decision", "decision", "decision_status"} & response.keys())


def test_dialogue_mapping_rejects_noncanonical_or_raw_provenance() -> None:
    provenance = copy.deepcopy(_context().provenance)
    provenance["model"]["raw_error"] = "provider body"

    with pytest.raises(ValueError, match="provenance"):
        DialogueMappingContext(fragments=_context().fragments, provenance=provenance)


async def test_dialogue_engine_executes_one_attempt_and_uses_actual_model_provenance() -> None:
    class SyntheticAdapter:
        calls = 0

        async def capabilities(self) -> ModelCapabilities:
            return ModelCapabilities(True, False, False, 4096, frozenset())

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            self.calls += 1
            return GenerationResult(
                request_id=request.request_id,
                text=json.dumps(_compact()),
                provider="actual-provider",
                model="actual-model",
                model_version="actual-version",
                finish_reason=FinishReason.STOP,
                usage=TokenUsage(input_tokens=101, output_tokens=37),
                provider_request_id="provider-request-1",
                latency_ms=12,
                safe_parameters={"temperature": 0},
            )

    adapter = SyntheticAdapter()
    request = GenerationRequest(
        request_id="attempt-1",
        purpose=GenerationPurpose.DIALOGUE,
        work_item_id="turn-1",
        trusted_instructions="Use the verified dialogue skill.",
        untrusted_input="{}",
        response_schema=json.loads(SCHEMA_PATH.read_text()),
        model_profile=ModelProfileSnapshot(
            id="synthetic", version="1.0.0", config_sha256="a" * 64
        ),
        max_output_tokens=256,
        timeout_seconds=60.0,
    )
    validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))

    response = await DialogueEngine().execute(
        adapter=adapter,
        request=request,
        parse_and_validate=lambda text: validator.validate(json.loads(text)) or json.loads(text),
        fragments=_context().fragments,
        skill_snapshot=_context().provenance["skill"],
    )

    assert adapter.calls == 1
    assert response["provenance"]["model"] == {
        "provider": "actual-provider",
        "model": "actual-model",
        "model_version": "actual-version",
        "safe_parameters": {"temperature": 0},
        "usage": {"input_tokens": 101, "output_tokens": 37},
    }
