from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from review_core.ports.models import ModelProfileSnapshot
from review_core.review.engine import MappingContext, ReviewEngine, ReviewFragment
from review_core.review.prompt import PromptBudgetExceeded
from review_runtime.reports import CanonicalReportValidator, ModelReviewOutputValidator

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/ml-integration"
SCHEMA_PATH = ROOT / "specs/004-llm-review-integration/contracts/model-output.review.v1.schema.json"


def _compact() -> dict:
    return json.loads((FIXTURES / "review-response.json").read_text())


def _context() -> MappingContext:
    primary_text = (FIXTURES / "primary.md").read_text()
    context_text = (FIXTURES / "context.md").read_text()
    return MappingContext(
        run_id="11111111-1111-4111-8111-111111111111",
        report_id="22222222-2222-4222-8222-222222222222",
        created_at="2026-09-05T12:00:00.000000Z",
        primary_source_id="source-main",
        target_fragment_ids=("source-main-lines-1-2",),
        fragments={
            "source-main-lines-1-2": ReviewFragment(
                id="source-main-lines-1-2",
                source_id="source-main",
                document_id="33333333-3333-4333-8333-333333333333",
                source_name="synthetic-primary.md",
                text=primary_text,
                location={
                    "kind": "text",
                    "line_start": 1,
                    "line_end": 2,
                    "char_start": 0,
                    "char_end": len(primary_text),
                },
            ),
            "source-context-1-lines-1-1": ReviewFragment(
                id="source-context-1-lines-1-1",
                source_id="source-context-1",
                document_id="44444444-4444-4444-8444-444444444444",
                source_name="synthetic-context.md",
                text=context_text,
                location={
                    "kind": "text",
                    "line_start": 1,
                    "line_end": 1,
                    "char_start": 0,
                    "char_end": len(context_text),
                },
            ),
        },
        provenance={
            "execution_snapshot": {
                "profile": {
                    "id": "77777777-7777-4777-8777-777777777777",
                    "version": "1.0.0",
                    "digest": "a" * 64,
                },
                "skill": {"id": "synthetic", "version": "1.0.0", "package_sha256": "b" * 64},
                "model_profile": {
                    "id": "synthetic",
                    "version": "1.0.0",
                    "config_sha256": "c" * 64,
                },
                "engine_version": "1.0.0",
                "dialogue_policy": {
                    "id": "default",
                    "version": "1.0.0",
                    "digest": "d" * 64,
                    "max_member_turns": None,
                },
            },
            "model": {
                "provider": "synthetic",
                "model": "fixture",
                "model_version": "test-only",
                "safe_parameters": {},
                "usage": {"input_tokens": None, "output_tokens": None},
            },
            "sources": [
                {
                    "source_id": "source-main",
                    "document_id": "33333333-3333-4333-8333-333333333333",
                    "role": "document",
                    "filename": "synthetic-primary.md",
                    "sha256": "e" * 64,
                    "status": "available",
                    "diagnostics": [],
                },
                {
                    "source_id": "source-context-1",
                    "document_id": "44444444-4444-4444-8444-444444444444",
                    "role": "context",
                    "filename": "synthetic-context.md",
                    "sha256": "f" * 64,
                    "status": "available",
                    "diagnostics": [],
                },
            ],
        },
    )


def _ids() -> Iterator[str]:
    yield "55555555-5555-4555-8555-555555555555"
    yield "66666666-6666-4666-8666-666666666666"


def test_compact_fixture_satisfies_model_output_schema() -> None:
    schema = json.loads(SCHEMA_PATH.read_text())
    Draft202012Validator.check_schema(schema)

    Draft202012Validator(schema).validate(_compact())


def test_runtime_pipeline_parses_and_validates_only_a_compact_json_object() -> None:
    validator = ModelReviewOutputValidator(SCHEMA_PATH)

    assert validator.parse_and_validate(json.dumps(_compact())) == _compact()
    with pytest.raises(ValueError, match="compact review model output"):
        validator.parse_and_validate('{"summary":"first","summary":"duplicate"}')


@pytest.mark.parametrize(
    ("path", "field", "value"),
    [
        ((), "run_id", "service-run"),
        (("findings", 0), "id", "service-finding"),
        (("findings", 0), "ordinal", 1),
        (("findings", 0, "anchors", 0), "quote_start", 0),
        (("findings", 0, "anchors", 0), "provenance", {}),
    ],
)
def test_model_output_rejects_service_owned_fields(path: tuple, field: str, value: object) -> None:
    value_under_test = _compact()
    target: object = value_under_test
    for part in path:
        target = target[part]  # type: ignore[index]
    assert isinstance(target, dict)
    target[field] = value

    errors = list(Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).iter_errors(value_under_test))

    assert errors


def test_mapping_assigns_ids_ordinals_offsets_and_factual_provenance() -> None:
    identifiers = _ids()

    report = ReviewEngine().map_model_output(
        _compact(),
        context=_context(),
        new_finding_id=lambda: next(identifiers),
    )

    assert report["id"] == "22222222-2222-4222-8222-222222222222"
    assert report["run_id"] == "11111111-1111-4111-8111-111111111111"
    assert report["findings"][0]["id"] == "55555555-5555-4555-8555-555555555555"
    assert report["findings"][0]["ordinal"] == 1
    assert report["findings"][0]["anchors"][0]["quote_start"] == 0
    assert report["findings"][0]["anchors"][0]["quote_end"] == 23
    assert report["provenance"] == _context().provenance
    CanonicalReportValidator(ROOT / "contracts/review-platform/v1/openapi.yaml").validate(report)


def test_context_anchor_is_allowed_when_finding_keeps_primary_basis() -> None:
    compact = _compact()
    compact["findings"][0]["anchors"].append(
        {
            "source_id": "source-context-1",
            "fragment_id": "source-context-1-lines-1-1",
            "quote": "Use UTC for refresh schedules.",
        }
    )

    report = ReviewEngine().map_model_output(compact, context=_context())

    assert report["findings"][0]["anchors"][1]["source_id"] == "source-context-1"
    assert report["findings"][0]["anchors"][1]["quote_start"] == 0


def test_context_only_finding_is_rejected_without_primary_basis() -> None:
    compact = _compact()
    compact["findings"][0]["anchors"] = [
        {
            "source_id": "source-context-1",
            "fragment_id": "source-context-1-lines-1-1",
            "quote": "Use UTC for refresh schedules.",
        }
    ]

    with pytest.raises(ValueError, match="primary-document basis"):
        ReviewEngine().map_model_output(compact, context=_context())


def test_missing_finding_requires_reviewed_primary_scope() -> None:
    compact = _compact()
    compact["findings"][0] |= {"kind": "missing", "anchors": [], "scope": []}

    with pytest.raises(ValueError, match="scope"):
        ReviewEngine().map_model_output(compact, context=_context())


def test_ambiguous_exact_quote_is_rejected() -> None:
    compact = _compact()
    compact["findings"][0]["anchors"][0]["quote"] = "r"

    with pytest.raises(ValueError, match="ambiguous"):
        ReviewEngine().map_model_output(compact, context=_context())


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["coverage"]["unreviewed"].append(
            {"fragment_id": "source-main-lines-1-2", "reason": "not reviewed"}
        ),
        lambda value: value["coverage"].update(reviewed_fragment_ids=[]),
        lambda value: value["coverage"].update(reviewed_fragment_ids=["unknown-fragment"]),
    ],
)
def test_mapping_requires_an_exact_primary_coverage_partition(mutate: object) -> None:
    compact = copy.deepcopy(_compact())
    mutate(compact)  # type: ignore[operator]

    with pytest.raises(ValueError, match="coverage"):
        ReviewEngine().map_model_output(compact, context=_context())


def test_prepare_generation_request_preserves_the_complete_immutable_review_input() -> None:
    review_input = {
        "contract_version": "review-input.v1",
        "sources": [
            {
                "id": "source-main",
                "role": "document",
                "fragments": [{"id": "f1", "text": "CANARY_FULL_DOCUMENT"}],
            },
            {
                "id": "source-context-1",
                "role": "context",
                "fragments": [{"id": "c1", "text": "CANARY_FULL_CONTEXT"}],
            },
        ],
        "review_scope": {"target_fragment_ids": ["f1"]},
    }

    request = ReviewEngine().prepare_generation_request(
        review_input=review_input,
        skill_instructions="Use the verified synthetic review instructions.",
        request_id="attempt-1",
        work_item_id="whole-document",
        response_schema=json.loads(SCHEMA_PATH.read_text()),
        model_profile=ModelProfileSnapshot(
            id="synthetic", version="1.0.0", config_sha256="a" * 64
        ),
        max_input_utf8_bytes=100_000,
        max_output_tokens=512,
        timeout_seconds=300.0,
    )
    review_input["sources"][0]["fragments"][0]["text"] = "MUTATED"  # type: ignore[index]

    assert "CANARY_FULL_DOCUMENT" in request.untrusted_input
    assert "CANARY_FULL_CONTEXT" in request.untrusted_input
    assert "MUTATED" not in request.untrusted_input
    assert request.max_output_tokens == 512
    assert request.response_schema["$id"].endswith("model-output.review.v1.schema.json")


def test_prepare_generation_request_rejects_the_full_prompt_without_truncation() -> None:
    with pytest.raises(PromptBudgetExceeded, match="budget"):
        ReviewEngine().prepare_generation_request(
            review_input={"primary_document": "document that must not be truncated"},
            skill_instructions="verified instructions that also count against the complete budget",
            request_id="attempt-oversize",
            work_item_id="whole-document",
            response_schema=json.loads(SCHEMA_PATH.read_text()),
            model_profile=ModelProfileSnapshot(
                id="synthetic", version="1.0.0", config_sha256="a" * 64
            ),
            max_input_utf8_bytes=64,
            max_output_tokens=512,
            timeout_seconds=300.0,
        )
