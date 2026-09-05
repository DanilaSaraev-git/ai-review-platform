from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID

JobKind = Literal["execute_review", "generate_dialogue_turn"]


@dataclass(frozen=True, slots=True)
class JobEnvelope:
    schema_version: str
    job_id: str
    organization_id: str
    workspace_id: str
    kind: JobKind
    payload: dict[str, str]
    requested_by: str
    trace_id: str


def _uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a UUID string")
    try:
        UUID(value)
    except ValueError as error:
        raise ValueError(f"{field} must be a UUID string") from error
    return value


def validate_job_envelope(value: dict[str, Any]) -> JobEnvelope:
    top_fields = {
        "schema_version",
        "job_id",
        "organization_id",
        "workspace_id",
        "kind",
        "payload",
        "requested_by",
        "trace_id",
    }
    if set(value) != top_fields:
        raise ValueError("job envelope fields do not match job-envelope.v1")
    if value["schema_version"] != "job-envelope.v1":
        raise ValueError("unsupported job envelope schema version")
    kind = value["kind"]
    payload_fields = {
        "execute_review": {"review_run_id", "review_execution_id"},
        "generate_dialogue_turn": {
            "dialogue_id",
            "dialogue_turn_id",
            "generation_attempt_id",
        },
    }
    if kind not in payload_fields:
        raise ValueError("unsupported job kind")
    payload = value["payload"]
    if not isinstance(payload, dict) or set(payload) != payload_fields[kind]:
        raise ValueError("job payload does not match its kind")
    normalized_payload = {name: _uuid(payload[name], f"payload.{name}") for name in payload}
    trace_id = value["trace_id"]
    if not isinstance(trace_id, str) or not 1 <= len(trace_id) <= 128:
        raise ValueError("trace_id must contain 1 to 128 characters")
    return JobEnvelope(
        schema_version="job-envelope.v1",
        job_id=_uuid(value["job_id"], "job_id"),
        organization_id=_uuid(value["organization_id"], "organization_id"),
        workspace_id=_uuid(value["workspace_id"], "workspace_id"),
        kind=kind,
        payload=normalized_payload,
        requested_by=_uuid(value["requested_by"], "requested_by"),
        trace_id=trace_id,
    )
