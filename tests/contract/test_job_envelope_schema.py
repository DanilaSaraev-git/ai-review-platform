from __future__ import annotations

from pathlib import Path

import pytest

from tests.contract.contract_helpers import load_json_no_duplicates, validate_schema

ROOT = Path(__file__).parents[2]
SCHEMA = load_json_no_duplicates(
    ROOT / "specs/003-backend-implementation/contracts/job-envelope.v1.schema.json"
)


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        (
            "execute_review",
            {
                "review_run_id": "00000000-0000-4000-8000-000000000001",
                "review_execution_id": "00000000-0000-4000-8000-000000000002",
            },
        ),
        (
            "generate_dialogue_turn",
            {
                "dialogue_id": "00000000-0000-4000-8000-000000000003",
                "dialogue_turn_id": "00000000-0000-4000-8000-000000000004",
                "generation_attempt_id": "00000000-0000-4000-8000-000000000005",
            },
        ),
    ],
)
def test_attempt_specific_envelope(kind: str, payload: dict[str, str]) -> None:
    validate_schema(
        SCHEMA,
        {
            "schema_version": "job-envelope.v1",
            "job_id": "00000000-0000-4000-8000-000000000006",
            "organization_id": "00000000-0000-4000-8000-000000000007",
            "workspace_id": "00000000-0000-4000-8000-000000000008",
            "kind": kind,
            "payload": payload,
            "requested_by": "00000000-0000-4000-8000-000000000009",
            "trace_id": "trace-1",
        },
    )


def test_duplicate_json_keys_are_rejected(tmp_path: Path) -> None:
    broken = tmp_path / "duplicate.json"
    broken.write_text('{"kind":"execute_review","kind":"generate_dialogue_turn"}')
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_json_no_duplicates(broken)
