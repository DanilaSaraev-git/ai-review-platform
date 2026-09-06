from copy import deepcopy

import pytest
from review_core.application.cycle_state import build_cycle, empty_cycle, revise_link, revise_resolution
from review_core.domain.errors import Conflict

ACTOR = {"id": "analyst", "display_name": "Synthetic Analyst"}
DECISION = {
    "status": "confirmed",
    "revision": 1,
    "actor": ACTOR,
    "reason": "Confirmed",
    "resolution": None,
    "decided_at": "2026-09-06T00:00:00Z",
}


def finding(identity: str, *, fragment: str = "stable", reason: str = "Reason") -> dict:
    return {
        "id": identity,
        "kind": "ambiguity",
        "title": "Schedule",
        "problem": "Time is missing",
        "reason": reason,
        "question": "When?",
        "priority": {"level": "high", "rationale": "Data"},
        "scope": [],
        "anchors": [
            {
                "source_id": "source-main",
                "fragment_id": fragment,
                "quote": "Daily",
                "quote_start": 0,
                "quote_end": 5,
            }
        ],
    }


def cycle(run: str, baseline: str | None) -> dict:
    return empty_cycle(
        run, {"family_id": "family", "version_number": 1, "document": {"id": "version"}}, baseline
    )


def project(
    run: str, baseline: str | None, findings: list, previous: dict, *, comparable: bool = True
) -> tuple:
    return build_cycle(
        cycle(run, baseline),
        {"findings": findings, "coverage": {"status": "complete"}},
        previous,
        same_sources=True,
        same_conditions=comparable,
        compared_at="2026-09-06T00:00:00Z",
        previous_evidence_keys={
            item["finding"]["id"]: (item["finding"]["anchors"][0]["fragment_id"],)
            for item in previous.values()
        },
        current_evidence_keys={item["id"]: (item["anchors"][0]["fragment_id"],) for item in findings},
    )


def test_lineage_survives_absence_resolution_and_reappearance() -> None:
    first, lineage = project("v1", None, [finding("one")], {})
    issue = first["entries"][0]["issue_id"]
    lineage[issue]["decision"] = deepcopy(DECISION)
    second, absent = project("v2", "v1", [], lineage)
    assert second["entries"][0]["status"] == "not_detected"
    revise_resolution(
        second,
        absent,
        issue,
        {"status": "resolved", "reason": "Fixed in source", "expected_revision": 0},
        ACTOR,
        "now",
    )
    third, returned = project("v3", "v2", [finding("three")], absent)
    assert third["entries"][0]["issue_id"] == issue
    assert third["entries"][0]["status"] == "reappeared"
    assert third["entries"][0]["resolution"]["status"] == "open"
    assert third["entries"][0]["previous_decision"] == DECISION
    assert not third["entries"][0]["decision_carried"]
    assert returned[issue]["origin_run_id"] == "v1"


def test_changed_conditions_never_claim_absence_and_ancient_decision_is_not_carried() -> None:
    first, previous = project("v1", None, [finding("one")], {})
    previous[first["entries"][0]["issue_id"]]["decision"] = deepcopy(DECISION)
    second, lineage = project("v2", "v1", [], previous, comparable=False)
    assert second["entries"][0]["status"] == "not_checked"
    third, _ = project("v3", "v2", [finding("three")], lineage)
    assert third["entries"][0]["previous_decision"] == DECISION
    assert not third["entries"][0]["decision_carried"]


def test_decision_carry_is_snapshotted_and_same_evidence_required() -> None:
    first, previous = project("v1", None, [finding("one")], {})
    issue = first["entries"][0]["issue_id"]
    previous[issue]["decision"] = deepcopy(DECISION)
    second, _ = project("v2", "v1", [finding("two")], previous)
    assert second["entries"][0]["decision_carried"]
    previous[issue]["decision"]["reason"] = "Later correction"
    assert second["entries"][0]["previous_decision"]["reason"] == "Confirmed"
    uncertain, _ = project("v3", "v1", [finding("three", fragment="other-fragment")], previous)
    assert all(not entry["decision_carried"] for entry in uncertain["entries"])


def test_manual_unlink_preserves_resolved_history_and_revision_conflicts() -> None:
    first, previous = project("v1", None, [finding("one")], {})
    second, lineage = project("v2", "v1", [finding("two")], previous)
    issue = first["entries"][0]["issue_id"]
    revise_resolution(
        second,
        lineage,
        issue,
        {"status": "resolved", "reason": "Confirmed fix", "expected_revision": 0},
        ACTOR,
        "now",
    )
    revise_link(
        second,
        lineage,
        {"previous_issue_id": None, "expected_revision": second["revision"]},
        finding("two"),
        previous,
    )
    old = next(entry for entry in second["entries"] if entry["issue_id"] == issue)
    assert old["current_finding_id"] is None
    assert old["resolution"] == lineage[issue]["resolution"]
    assert old["resolution"]["status"] == "resolved"
    with pytest.raises(Conflict):
        revise_link(
            second, lineage, {"previous_issue_id": issue, "expected_revision": 0}, finding("two"), previous
        )
