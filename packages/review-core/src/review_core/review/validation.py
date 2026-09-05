from __future__ import annotations

import math
from typing import Any


def resolve_unique_quote_offset(text: str, quote: str) -> int:
    first = text.find(quote)
    if first < 0:
        raise ValueError("anchor quote does not resolve exactly")
    if text.find(quote, first + 1) >= 0:
        raise ValueError("anchor quote is ambiguous within its fragment")
    return first


def _validate_location(location: dict[str, Any]) -> None:
    if location.get("kind") == "text":
        if location["line_start"] < 1 or location["line_end"] < location["line_start"]:
            raise ValueError("invalid text location")
        if location["char_start"] < 0 or location["char_end"] <= location["char_start"]:
            raise ValueError("invalid text location")
    elif location.get("kind") == "pdf":
        if location["page"] < 1 or not location.get("rects"):
            raise ValueError("invalid PDF location")
        for rectangle in location["rects"]:
            if len(rectangle) != 4 or not all(
                math.isfinite(value) and 0 <= value <= 1 for value in rectangle
            ):
                raise ValueError("invalid PDF rectangle")
            if rectangle[0] >= rectangle[2] or rectangle[1] >= rectangle[3]:
                raise ValueError("invalid PDF rectangle")
    else:
        raise ValueError("unknown source location")


def validate_report(
    report: dict[str, Any], fragments: dict[str, dict[str, Any]], *, primary_source_id: str
) -> None:
    coverage = report["coverage"]
    target = coverage["target_fragment_ids"]
    reviewed = coverage["reviewed_fragment_ids"]
    fragment_gaps = [
        gap["fragment_id"]
        for gap in coverage["gaps"]
        if gap["fragment_id"] is not None and gap["source_id"] == primary_source_id
    ]
    if (
        len(target) != len(set(target))
        or len(reviewed) != len(set(reviewed))
        or len(fragment_gaps) != len(set(fragment_gaps))
    ):
        raise ValueError("coverage partition contains duplicates")
    if set(reviewed) & set(fragment_gaps) or set(reviewed) | set(fragment_gaps) != set(target):
        raise ValueError("coverage partition is not exact")
    if any(
        fragment_id not in fragments or fragments[fragment_id]["source_id"] != primary_source_id
        for fragment_id in target
    ):
        raise ValueError("coverage contains an unknown or non-primary target")
    for gap in coverage["gaps"]:
        fragment_id = gap["fragment_id"]
        if fragment_id is None:
            continue
        fragment = fragments.get(fragment_id)
        if fragment is None or fragment["source_id"] != gap["source_id"]:
            raise ValueError("coverage gap source identity mismatch")
    if coverage["status"] == "complete" and coverage["gaps"]:
        raise ValueError("complete coverage cannot contain gaps")
    if coverage["status"] == "partial" and not coverage["gaps"]:
        raise ValueError("partial coverage requires a gap")
    finding_ids: set[str] = set()
    ordinals: set[int] = set()
    for finding in report["findings"]:
        if finding["id"] in finding_ids or finding["ordinal"] in ordinals:
            raise ValueError("finding identity or ordinal is duplicated")
        finding_ids.add(finding["id"])
        ordinals.add(finding["ordinal"])
        anchors = finding["anchors"]
        scope = finding["scope"]
        if finding["kind"] == "missing":
            if anchors or not scope:
                raise ValueError("missing finding needs scope and no anchor")
        elif not anchors:
            raise ValueError("present-text finding needs an anchor")
        primary_basis = False
        for anchor in anchors:
            fragment = fragments.get(anchor["fragment_id"])
            if fragment is None:
                raise ValueError("anchor must reference a known fragment")
            if fragment["source_id"] == primary_source_id and anchor["fragment_id"] not in reviewed:
                raise ValueError("primary anchor must reference a reviewed fragment")
            if fragment["source_id"] == primary_source_id:
                primary_basis = True
            start, end = anchor["quote_start"], anchor["quote_end"]
            if start < 0 or end <= start or fragment["text"][start:end] != anchor["quote"]:
                raise ValueError("anchor quote and offsets do not resolve exactly")
            if (
                anchor["document_id"] != fragment["document_id"]
                or anchor["source_id"] != fragment["source_id"]
            ):
                raise ValueError("anchor source identity mismatch")
            _validate_location(anchor["location"])
        for fragment_id in scope:
            fragment = fragments.get(fragment_id)
            if (
                fragment is None
                or fragment["source_id"] != primary_source_id
                or fragment_id not in reviewed
            ):
                raise ValueError("scope must reference a reviewed primary fragment")
            primary_basis = True
        if not primary_basis:
            raise ValueError("finding has no primary-document basis")
