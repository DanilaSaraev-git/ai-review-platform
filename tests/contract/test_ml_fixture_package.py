from __future__ import annotations

from pathlib import Path

from review_core.dialogue.validation import validate_dialogue_output
from review_core.review.validation import validate_report
from review_runtime.skills.registry import SkillRegistry

from tests.contract.contract_helpers import load_json_no_duplicates, validate_schema

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/ml-integration"
SCHEMAS = ROOT / "contracts/review-platform/v1/schemas"


def test_synthetic_skill_package_loads_with_both_canonical_operations() -> None:
    manifest = SkillRegistry(SCHEMAS / "skill-manifest.schema.json").load(FIXTURES / "skill")

    assert manifest["id"] == "synthetic-ml-integration"
    assert manifest["operations"]["review"]["output"] == "review-output.v1"
    assert manifest["operations"]["finding_dialogue"]["output"] == "finding-dialogue-output.v1"
    assert manifest["requires"]["model_capabilities"] == ["text_generation"]


def test_compact_review_fixture_maps_to_canonical_output_with_literal_evidence() -> None:
    compact = load_json_no_duplicates(FIXTURES / "review-response.json")
    primary_text = (FIXTURES / "primary.md").read_text()
    finding = compact["findings"][0]
    anchor = finding["anchors"][0]

    assert set(compact) == {"summary", "coverage", "findings", "limitations"}
    assert set(anchor) == {"source_id", "fragment_id", "quote"}
    assert primary_text[0:23] == anchor["quote"] == "Refresh runs regularly."
    assert primary_text.count(anchor["quote"]) == 1
    assert compact["coverage"]["unreviewed"] == []
    assert compact["coverage"]["source_gaps"] == []

    # Authored offsets and service IDs are a test envelope, not the future engine mapper.
    skill_anchor = anchor | {"quote_start": 0, "quote_end": 23}
    skill_finding = finding | {"local_id": "F-001", "anchors": [skill_anchor]}
    skill_output = compact | {
        "contract_version": "review-output.v1",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "findings": [skill_finding],
    }
    validate_schema(load_json_no_duplicates(SCHEMAS / "review-output.schema.json"), skill_output)

    document_id = "20000000-0000-4000-8000-000000000001"
    report_finding = finding | {
        "id": "30000000-0000-4000-8000-000000000001",
        "ordinal": 1,
        "anchors": [
            skill_anchor
            | {
                "document_id": document_id,
                "location": {
                    "kind": "text",
                    "line_start": 1,
                    "line_end": 2,
                    "char_start": 0,
                    "char_end": 42,
                },
            }
        ],
    }
    validate_report(
        {
            "coverage": {
                "status": "complete",
                "target_fragment_ids": ["source-main-lines-1-2"],
                "reviewed_fragment_ids": compact["coverage"]["reviewed_fragment_ids"],
                "gaps": [],
            },
            "findings": [report_finding],
        },
        {
            "source-main-lines-1-2": {
                "source_id": "source-main",
                "document_id": document_id,
                "text": primary_text,
            }
        },
        primary_source_id="source-main",
    )


def test_compact_dialogue_fixture_maps_to_advisory_output_with_literal_context() -> None:
    compact = load_json_no_duplicates(FIXTURES / "dialogue-response.json")
    primary_text = (FIXTURES / "primary.md").read_text()
    context_text = (FIXTURES / "context.md").read_text()
    primary_anchor, context_anchor = compact["anchors"]

    assert set(compact) == {"action", "content", "proposed_resolution", "anchors"}
    assert set(primary_anchor) == set(context_anchor) == {"source_id", "fragment_id", "quote"}
    assert primary_text[0:23] == primary_anchor["quote"] == "Refresh runs regularly."
    assert context_text[0:30] == context_anchor["quote"] == "Use UTC for refresh schedules."
    assert primary_text.count(primary_anchor["quote"]) == context_text.count(context_anchor["quote"]) == 1

    assistant_message = compact | {
        "anchors": [
            primary_anchor | {"quote_start": 0, "quote_end": 23},
            context_anchor | {"quote_start": 0, "quote_end": 30},
        ]
    }
    skill_output = {
        "contract_version": "finding-dialogue-output.v1",
        "run_id": "11111111-1111-4111-8111-111111111111",
        "dialogue_id": "90000000-0000-4000-8000-000000000001",
        "turn_id": "91000000-0000-4000-8000-000000000001",
        "assistant_message": assistant_message,
    }
    validate_schema(load_json_no_duplicates(SCHEMAS / "finding-dialogue-output.schema.json"), skill_output)
    validate_dialogue_output(assistant_message)
    assert assistant_message["action"] == "propose_resolution"
    assert assistant_message["proposed_resolution"]["text"] == "Refresh runs every day at 04:00 UTC."
