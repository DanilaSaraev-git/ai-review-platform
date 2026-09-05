import pytest
from review_runtime.queue.outbox import validate_job_envelope


def test_job_envelope_resolves_exact_review_attempt() -> None:
    value = validate_job_envelope(
        {
            "schema_version": "job-envelope.v1",
            "job_id": "00000000-0000-4000-8000-000000000006",
            "kind": "execute_review",
            "organization_id": "00000000-0000-4000-8000-000000000007",
            "workspace_id": "00000000-0000-4000-8000-000000000008",
            "payload": {
                "review_run_id": "00000000-0000-4000-8000-000000000001",
                "review_execution_id": "00000000-0000-4000-8000-000000000002",
            },
            "requested_by": "00000000-0000-4000-8000-000000000009",
            "trace_id": "trace-1",
        }
    )
    assert value.payload["review_execution_id"] == "00000000-0000-4000-8000-000000000002"


def test_job_envelope_rejects_cross_kind_attempt() -> None:
    with pytest.raises(ValueError):
        validate_job_envelope(
            {
                "schema_version": "job-envelope.v1",
                "job_id": "00000000-0000-4000-8000-000000000006",
                "kind": "execute_review",
                "organization_id": "00000000-0000-4000-8000-000000000007",
                "workspace_id": "00000000-0000-4000-8000-000000000008",
                "payload": {
                    "dialogue_id": "00000000-0000-4000-8000-000000000003",
                    "dialogue_turn_id": "00000000-0000-4000-8000-000000000004",
                    "generation_attempt_id": "00000000-0000-4000-8000-000000000005",
                },
                "requested_by": "00000000-0000-4000-8000-000000000009",
                "trace_id": "trace-1",
            }
        )
