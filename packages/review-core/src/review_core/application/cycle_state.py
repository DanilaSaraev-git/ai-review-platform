"""Mutable review-cycle projection kept separate from immutable reports."""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from typing import Any
from uuid import uuid4

from review_core.application.review_cycle import can_carry_decision, match_findings
from review_core.domain.errors import Conflict, NotFound


def open_resolution() -> dict[str, Any]:
    return {"status": "open", "revision": 0, "actor": None, "reason": None, "decided_at": None}


def empty_cycle(run_id: str, version: dict[str, Any], baseline_run_id: str | None) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "family_id": version["family_id"],
        "document_id": version["document"]["id"],
        "version_number": version["version_number"],
        "baseline_run_id": baseline_run_id,
        "status": "unavailable",
        "revision": 0,
        "compared_at": None,
        "entries": [],
        "limitations": ["review_report_unavailable"],
    }


def build_cycle(
    value: dict[str, Any],
    report: dict[str, Any],
    previous: dict[str, dict[str, Any]],
    *,
    same_sources: bool,
    same_conditions: bool,
    compared_at: str,
    previous_evidence_keys: dict[str, tuple[str, ...]] | None = None,
    current_evidence_keys: dict[str, tuple[str, ...]] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Snapshot earlier states exactly once; later retries leave the ready projection intact."""
    if value["status"] == "ready":
        return deepcopy(value), deepcopy(previous)
    previous_by_finding = {item["finding"]["id"]: (issue_id, item) for issue_id, item in previous.items()}
    current = {item["id"]: item for item in report["findings"]}
    comparable = same_conditions and report["coverage"]["status"] == "complete"
    entries: list[dict[str, Any]] = []
    lineage: dict[str, dict[str, Any]] = {}
    for match in match_findings(
        [item["finding"] for item in previous.values()],
        list(current.values()),
        previous_evidence_keys=previous_evidence_keys,
        current_evidence_keys=current_evidence_keys,
    ):
        old_pair = previous_by_finding.get(match.previous_id) if match.previous_id else None
        issue_id, old = old_pair if old_pair else (str(uuid4()), {})
        finding = current.get(match.current_id, {}) if match.current_id else {}
        status = match.status
        if not finding and status == "not_detected" and not comparable:
            status = "not_checked"
        resolution = deepcopy(old["resolution"]) if old else open_resolution()
        if finding and old and resolution["status"] == "resolved":
            status = "reappeared"
            resolution = open_resolution()
        previous_decision = deepcopy(old.get("decision")) if old else None
        carried = bool(
            old
            and finding
            and old["last_run_id"] == value["baseline_run_id"]
            and status == "persisting"
            and previous_decision
            and previous_decision["status"] != "unreviewed"
            and can_carry_decision(
                old["finding"],
                finding,
                same_sources=same_sources,
                same_conditions=same_conditions,
                evidence_unchanged=bool(
                    previous_evidence_keys
                    and current_evidence_keys
                    and previous_evidence_keys.get(old["finding"]["id"])
                    and previous_evidence_keys.get(old["finding"]["id"])
                    == current_evidence_keys.get(finding["id"])
                ),
            )
        )
        entry = {
            "issue_id": issue_id,
            "origin_run_id": old["origin_run_id"] if old else value["run_id"],
            "origin_finding_id": old["origin_finding_id"] if old else finding["id"],
            "previous_run_id": old["last_run_id"] if old else None,
            "previous_finding_id": old["finding"]["id"] if old else None,
            "current_finding_id": finding["id"] if finding else None,
            "status": status,
            "match_basis": match.basis,
            "decision_carried": carried,
            "previous_decision": previous_decision,
            "resolution": resolution,
        }
        entries.append(entry)
        lineage[issue_id] = {
            "origin_run_id": entry["origin_run_id"],
            "origin_finding_id": entry["origin_finding_id"],
            "last_run_id": value["run_id"] if finding else old["last_run_id"],
            "finding": deepcopy(finding if finding else old["finding"]),
            "decision": deepcopy(previous_decision) if carried or not finding else None,
            "resolution": deepcopy(resolution),
        }
    limitations = []
    if value["baseline_run_id"] and not same_conditions:
        limitations.append("review_conditions_changed")
    if report["coverage"]["status"] != "complete":
        limitations.append("review_coverage_incomplete")
    return value | {
        "status": "ready",
        "revision": value["revision"] + 1,
        "compared_at": compared_at,
        "entries": entries,
        "limitations": limitations,
    }, lineage


def revise_link(
    value: dict[str, Any],
    lineage: dict[str, dict[str, Any]],
    body: dict[str, Any],
    finding: dict[str, Any],
    previous: dict[str, dict[str, Any]],
) -> None:
    if value["revision"] != body["expected_revision"]:
        raise Conflict("revision_conflict", "Review cycle revision changed.")
    current = next(
        (entry for entry in value["entries"] if entry["current_finding_id"] == finding["id"]), None
    )
    if current is None:
        raise NotFound()
    issue_id = body["previous_issue_id"]
    target = next((entry for entry in value["entries"] if entry["issue_id"] == issue_id), None)
    if issue_id is not None:
        if issue_id not in previous or target is None:
            raise NotFound()
        if target["current_finding_id"] not in (None, finding["id"]):
            raise Conflict("link_conflict", "The previous issue is already linked to another finding.")
        if target is current:
            return
    if current["previous_finding_id"] is not None:
        old = previous[current["issue_id"]]
        current.update(
            current_finding_id=None, status="not_checked", decision_carried=False, match_basis="manual_unlink"
        )
        lineage[current["issue_id"]] = deepcopy(old)
        lineage[current["issue_id"]]["resolution"] = deepcopy(current["resolution"])
    else:
        value["entries"].remove(current)
        lineage.pop(current["issue_id"], None)
    if target is None:
        issue_id = str(uuid4())
        target = {
            "issue_id": issue_id,
            "origin_run_id": value["run_id"],
            "origin_finding_id": finding["id"],
            "previous_run_id": None,
            "previous_finding_id": None,
            "current_finding_id": finding["id"],
            "status": "new",
            "match_basis": "manual_unlink",
            "decision_carried": False,
            "previous_decision": None,
            "resolution": open_resolution(),
        }
        value["entries"].append(target)
    else:
        reappeared = target["resolution"]["status"] == "resolved"
        target.update(
            current_finding_id=finding["id"],
            status="reappeared" if reappeared else "persisting",
            match_basis="manual_link",
            decision_carried=False,
            resolution=open_resolution() if reappeared else target["resolution"],
        )
    lineage[issue_id] = {
        "origin_run_id": target["origin_run_id"],
        "origin_finding_id": target["origin_finding_id"],
        "last_run_id": value["run_id"],
        "finding": deepcopy(finding),
        "decision": None,
        "resolution": deepcopy(target["resolution"]),
    }
    value["revision"] += 1


def revise_resolution(
    value: dict[str, Any],
    lineage: dict[str, dict[str, Any]],
    issue_id: str,
    body: dict[str, Any],
    actor: dict[str, Any],
    now: str,
) -> None:
    entry = next((item for item in value["entries"] if item["issue_id"] == issue_id), None)
    if entry is None:
        raise NotFound()
    if entry["resolution"]["revision"] != body["expected_revision"]:
        raise Conflict("revision_conflict", "Issue resolution revision changed.")
    resolution = {
        "status": body["status"],
        "reason": body["reason"],
        "actor": actor,
        "decided_at": now,
        "revision": entry["resolution"]["revision"] + 1,
    }
    entry["resolution"] = resolution
    lineage[issue_id]["resolution"] = deepcopy(resolution)
    value["revision"] += 1


def verified_evidence_keys(
    findings: list[dict[str, Any]], sources: list[dict[str, Any]]
) -> dict[str, tuple[str, ...]]:
    """Resolve complete exact anchors to unique extracted text, never merely similar quotes."""
    by_source = {source["source_id"]: source for source in sources}
    result: dict[str, tuple[str, ...]] = {}
    for finding in findings:
        keys: list[str] = []
        for anchor in finding.get("anchors", []):
            source = by_source.get(anchor["source_id"])
            if source is None:
                break
            fragments = source.get("fragments", [])
            counts = Counter(fragment["text"] for fragment in fragments)
            candidates = []
            for fragment in fragments:
                location = fragment["location"]
                stable = (
                    f"{anchor['source_id']}-page-{location['page']}"
                    if "page" in location
                    else f"{anchor['source_id']}-lines-"
                    f"{location.get('line_start')}-{location.get('line_end')}"
                )
                if anchor["fragment_id"] in (fragment["id"], stable):
                    candidates.append(fragment)
            if len(candidates) != 1:
                break
            fragment = candidates[0]
            start, end = anchor.get("quote_start"), anchor.get("quote_end")
            if (
                counts[fragment["text"]] != 1
                or not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end <= start
                or fragment["text"][start:end] != anchor["quote"]
            ):
                break
            keys.append(
                json.dumps(
                    [source["role"], source["ordinal"], fragment["text"], start, end], ensure_ascii=False
                )
            )
        else:
            if keys:
                result[finding["id"]] = tuple(sorted(keys))
    return result
