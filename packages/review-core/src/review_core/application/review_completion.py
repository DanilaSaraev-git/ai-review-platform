"""Explicit completion is a snapshot of human work, separate from the report."""

from typing import Any

from review_core.canonical import digest_value
from review_core.domain.errors import Conflict


def completion_state(
    cycle: dict[str, Any], report: dict[str, Any] | None, decisions: dict[str, Any]
) -> tuple[bool, str]:
    entries = cycle["entries"]
    digest = digest_value(
        {
            "entries": entries,
            "decisions": decisions,
            "coverage": report["coverage"] if report else None,
            "limitations": cycle["limitations"],
        }
    )
    if (
        not report
        or cycle["status"] != "ready"
        or cycle["limitations"]
        or report["coverage"]["status"] != "complete"
    ):
        return False, digest
    by_finding = {e["current_finding_id"]: e for e in entries if e["current_finding_id"]}
    for finding in report["findings"]:
        entry = by_finding.get(finding["id"], {})
        decision = decisions.get(finding["id"], {})
        if decision.get("revision", 0) == 0 and entry.get("decision_carried"):
            decision = entry.get("previous_decision") or {}
        if decision.get("status") == "rejected":
            continue
        if decision.get("status") != "confirmed" or entry.get("resolution", {}).get("status") != "resolved":
            return False, digest
    for entry in entries:
        if entry["status"] in {"uncertain", "not_checked"}:
            return False, digest
        if not entry["current_finding_id"] and entry["resolution"]["status"] != "resolved":
            if (entry.get("previous_decision") or {}).get("status") != "rejected":
                return False, digest
    return True, digest


def complete(
    cycle: dict[str, Any],
    report: dict[str, Any] | None,
    decisions: dict[str, Any],
    expected_revision: int,
    actor: dict[str, Any],
    now: str,
) -> None:
    if cycle["revision"] != expected_revision:
        raise Conflict("revision_conflict", "Review cycle changed. Refresh before completing.")
    ready, digest = completion_state(cycle, report, decisions)
    if not ready:
        raise Conflict("review_not_ready", "Open questions or incomplete analysis prevent completion.")
    if (cycle.get("completion") or {}).get("state_digest") == digest:
        return
    cycle["completion"] = {"completed_at": now, "actor": actor, "state_digest": digest}
    cycle["revision"] += 1


def project_completion(
    cycle: dict[str, Any], report: dict[str, Any] | None, decisions: dict[str, Any]
) -> dict[str, Any]:
    ready, digest = completion_state(cycle, report, decisions)
    saved = cycle.get("completion")
    return cycle | {"completion": saved if ready and saved and saved["state_digest"] == digest else None}
