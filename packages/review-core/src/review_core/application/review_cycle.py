"""Conservative correspondence; no model calls and no human-state mutations.

IDs, page numbers and offsets identify an occurrence, not a recurring problem.
Exact unique semantic matches are linked. Similarity only suggests candidates;
it never authorizes carrying a decision or declaring an issue resolved.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class FindingMatch:
    previous_id: str | None
    current_id: str | None
    status: str
    basis: str
    candidate_previous_ids: tuple[str, ...] = ()


def _text(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def _anchors(finding: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted((_text(a.get("source_id")), _text(a.get("quote"))) for a in finding.get("anchors", []))
    )


def _identity(finding: dict[str, Any]) -> tuple[Any, ...]:
    return (
        _text(finding.get("kind")),
        _text(finding.get("title")),
        _text(finding.get("problem")),
        _anchors(finding),
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _same_occurrence(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    def locations(finding: dict[str, Any]) -> tuple[Any, ...]:
        return tuple(
            sorted(
                (
                    a.get("source_id", ""),
                    a.get("fragment_id", ""),
                    a.get("quote_start", -1),
                    a.get("quote_end", -1),
                )
                for a in finding.get("anchors", [])
            )
        )

    old = locations(previous)
    return bool(old) and all(a[1] and a[2] >= 0 and a[3] > a[2] for a in old) and old == locations(current)


def _overlap(left: str, right: str) -> float:
    # Token overlap is used only for suggestions. Avoid quadratic character
    # alignment on repeated, long document fragments.
    a, b = set(re.findall(r"\w+", left.casefold())), set(re.findall(r"\w+", right.casefold()))
    return len(a & b) / len(a | b) if a and b else 0.0


def _decision_basis(finding: dict[str, Any]) -> tuple[Any, ...]:
    # Scope contains fragment identities whose remapping cannot be inferred here.
    # A non-identical scope conservatively prevents transfer.
    return (
        _identity(finding),
        _text(finding.get("reason")),
        _text(finding.get("question")),
        _canonical(finding.get("priority")),
        _canonical(finding.get("scope", [])),
    )


def _candidate(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    if previous.get("kind") != current.get("kind"):
        return False
    p_quotes = {quote for _, quote in _anchors(previous) if quote}
    c_quotes = {quote for _, quote in _anchors(current) if quote}
    if p_quotes & c_quotes:
        return True
    # These thresholds are a candidate-display heuristic, never confidence in a
    # match. Empty evidence must not match merely because both sets are empty.
    quote_similarity = max((_overlap(p, c) for p in p_quotes for c in c_quotes), default=0.0)
    problem_similarity = _overlap(_text(previous.get("problem")), _text(current.get("problem")))
    return quote_similarity >= 0.72 and problem_similarity >= 0.55


def match_findings(
    previous: list[dict[str, Any]],
    current: list[dict[str, Any]],
    *,
    previous_evidence_keys: dict[str, tuple[str, ...]] | None = None,
    current_evidence_keys: dict[str, tuple[str, ...]] | None = None,
) -> list[FindingMatch]:
    """Match the previous lineage pool against one current report, one-to-one.

    The caller supplies a unique previous ID per issue (its latest occurrence,
    including issues absent from the preceding report). For unmatched candidates,
    both sides remain represented so no previous problem silently disappears.
    Cross-version auto-links additionally require caller-verified evidence keys:
    ordered source identity + unique full fragment text + quote offsets. Missing
    keys only permit links to the exact same validated fragment occurrence.
    """
    p_by_id = {str(f["id"]): f for f in previous}
    c_by_id = {str(f["id"]): f for f in current}
    if len(p_by_id) != len(previous) or len(c_by_id) != len(current):
        raise ValueError("Finding occurrence IDs must be unique within each comparison side")
    p_groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    c_groups: dict[tuple[Any, ...], list[str]] = defaultdict(list)
    for finding in previous:
        p_groups[_identity(finding)].append(str(finding["id"]))
    for finding in current:
        c_groups[_identity(finding)].append(str(finding["id"]))
    matches: dict[str, str] = {}
    for identity, c_ids in c_groups.items():
        p_ids = p_groups.get(identity, [])
        # Empty/missing evidence cannot establish an automatic correspondence.
        if len(p_ids) == len(c_ids) == 1 and any(q for _, q in identity[-1]):
            previous_key = (previous_evidence_keys or {}).get(p_ids[0])
            current_key = (current_evidence_keys or {}).get(c_ids[0])
            if (previous_key and previous_key == current_key) or _same_occurrence(
                p_by_id[p_ids[0]], c_by_id[c_ids[0]]
            ):
                matches[c_ids[0]] = p_ids[0]
    used = set(matches.values())
    suggested: set[str] = set()
    result: list[FindingMatch] = []
    for current_id, finding in c_by_id.items():
        if current_id in matches:
            result.append(FindingMatch(matches[current_id], current_id, "persisting", "exact_unique"))
            continue
        candidates = tuple(
            p_id for p_id, old in p_by_id.items() if p_id not in used and _candidate(old, finding)
        )
        suggested.update(candidates)
        result.append(
            FindingMatch(
                None,
                current_id,
                "uncertain" if candidates else "new",
                "candidate_only" if candidates else "no_correspondence",
                candidates,
            )
        )
    for previous_id in p_by_id:
        if previous_id not in used:
            result.append(
                FindingMatch(
                    previous_id,
                    None,
                    "uncertain" if previous_id in suggested else "not_detected",
                    "candidate_only" if previous_id in suggested else "not_in_current_report",
                )
            )
    return result


def can_carry_decision(
    previous_finding: dict[str, Any],
    current_finding: dict[str, Any],
    *,
    same_sources: bool,
    same_conditions: bool,
    evidence_unchanged: bool = False,
) -> bool:
    """Necessary semantic gate; caller must also establish an exact unique link."""
    return (
        same_sources
        and same_conditions
        and bool(_anchors(previous_finding))
        and (evidence_unchanged or _same_occurrence(previous_finding, current_finding))
        and _decision_basis(previous_finding) == _decision_basis(current_finding)
    )


def same_source_texts(previous_sources: list[dict[str, Any]], current_sources: list[dict[str, Any]]) -> bool:
    """Compare ordered, fully extracted sources, not new document/fragment IDs.

    Each input has role, ordinal, text. Caller additionally verifies parser/settings
    provenance and successful extraction. Whitespace and case remain significant.
    """

    def values(sources: list[dict[str, Any]]) -> list[tuple[Any, Any, Any]]:
        return [(s.get("role"), s.get("ordinal"), s.get("text")) for s in sources]

    return (
        bool(previous_sources)
        and bool(current_sources)
        and all(isinstance(s.get("text"), str) and s["text"] for s in previous_sources + current_sources)
        and values(previous_sources) == values(current_sources)
    )


def same_review_conditions(previous_report: dict[str, Any], current_report: dict[str, Any]) -> bool:
    """Compare published semantic execution conditions, ignoring token usage.

    Locale and parser provenance live outside the canonical report; caller must
    compare them separately. Unknown provenance never establishes equivalence.
    """

    def conditions(report: dict[str, Any]) -> dict[str, Any] | None:
        provenance = report.get("provenance", {})
        snapshot = provenance.get("execution_snapshot")
        model = provenance.get("model")
        if not snapshot or not model:
            return None
        return {
            "snapshot": snapshot,
            "model": {k: model.get(k) for k in ("provider", "model", "model_version", "safe_parameters")},
        }

    previous = conditions(previous_report)
    return previous is not None and previous == conditions(current_report)
