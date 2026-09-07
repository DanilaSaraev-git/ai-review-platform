from __future__ import annotations

import math
import re
from types import MappingProxyType
from typing import Any

_SEMANTIC_ERROR_MESSAGES = MappingProxyType(
    {
        "anchor_quote_not_found": "anchor quote does not resolve exactly",
        "anchor_quote_ambiguous": "anchor quote is ambiguous within its fragment",
        "anchor_quote_invalid": "anchor quote is required",
        "anchor_quote_offsets_invalid": "anchor quote and offsets do not resolve exactly",
        "anchor_fragment_unknown": "anchor references an unknown fragment",
        "anchor_source_mismatch": "anchor source identity mismatch",
        "anchor_primary_unreviewed": "primary anchor must reference a reviewed fragment",
        "text_location_invalid": "invalid text location",
        "pdf_location_invalid": "invalid PDF location",
        "pdf_rectangle_invalid": "invalid PDF rectangle",
        "source_location_unknown": "unknown source location",
        "coverage_partition_duplicates": "coverage partition contains duplicates",
        "coverage_partition_inexact": "coverage partition is not exact",
        "coverage_target_invalid": "coverage contains an unknown or non-primary target",
        "coverage_gap_source_mismatch": "coverage gap source identity mismatch",
        "coverage_complete_has_gaps": "complete coverage cannot contain gaps",
        "coverage_partial_without_gaps": "partial coverage requires a gap",
        "finding_identity_duplicate": "finding identity or ordinal is duplicated",
        "missing_finding_scope_invalid": "missing finding needs scope and no anchor",
        "finding_anchor_required": "present-text finding needs an anchor",
        "finding_scope_invalid": "scope must reference a reviewed primary fragment",
        "finding_primary_basis_missing": "finding has no primary-document basis",
        "compact_fields_invalid": "compact fields do not match the model-output contract",
        "compact_output_shape_invalid": "compact output has an invalid coverage or findings shape",
        "compact_coverage_shape_invalid": "compact coverage fields must be arrays",
        "compact_unreviewed_shape_invalid": "compact unreviewed entry must be an object",
        "compact_source_gap_shape_invalid": "compact source gap must be an object",
        "compact_finding_shape_invalid": "compact finding must be an object",
        "compact_priority_shape_invalid": "compact priority must be an object",
        "compact_finding_basis_shape_invalid": "compact finding anchors and scope must be arrays",
        "compact_anchor_shape_invalid": "compact anchor must be an object",
    }
)


class ReviewSemanticValidationError(ValueError):
    """A content-free reason for rejecting review evidence or coverage."""

    def __init__(self, code: str, *, finding_index: int | None = None) -> None:
        if code not in _SEMANTIC_ERROR_MESSAGES:
            raise ValueError("unknown review semantic validation code")
        self._code = code
        self.finding_index = finding_index
        super().__init__(_SEMANTIC_ERROR_MESSAGES[code])

    @property
    def code(self) -> str:
        return self._code


def resolve_unique_quote_offset(text: str, quote: str) -> int:
    first = text.find(quote)
    if first < 0:
        raise ReviewSemanticValidationError("anchor_quote_not_found")
    if text.find(quote, first + 1) >= 0:
        raise ReviewSemanticValidationError("anchor_quote_ambiguous")
    return first


def resolve_unique_quote_span(text: str, quote: str) -> tuple[int, int]:
    """Recover PDF whitespace only, returning offsets into the unchanged source.

    Do not correct words, case, punctuation, numbers, or fragment identity.
    A normalized match must still be unique; report validation stays exact.
    """
    if not quote.strip():
        raise ReviewSemanticValidationError("anchor_quote_invalid")
    try:
        start = resolve_unique_quote_offset(text, quote)
        return start, start + len(quote)
    except ReviewSemanticValidationError as error:
        if error.code != "anchor_quote_not_found":
            raise

    characters: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\s+|\S", text):
        characters.append(" " if match.group().isspace() else match.group())
        spans.append(match.span())
    normalized_quote = re.sub(r"\s+", " ", quote.strip())
    start = resolve_unique_quote_offset("".join(characters), normalized_quote)
    return spans[start][0], spans[start + len(normalized_quote) - 1][1]


def _validate_location(location: dict[str, Any]) -> None:
    if location.get("kind") == "text":
        if location["line_start"] < 1 or location["line_end"] < location["line_start"]:
            raise ReviewSemanticValidationError("text_location_invalid")
        if location["char_start"] < 0 or location["char_end"] <= location["char_start"]:
            raise ReviewSemanticValidationError("text_location_invalid")
    elif location.get("kind") == "pdf":
        if location["page"] < 1 or not location.get("rects"):
            raise ReviewSemanticValidationError("pdf_location_invalid")
        for rectangle in location["rects"]:
            if len(rectangle) != 4 or not all(
                math.isfinite(value) and 0 <= value <= 1 for value in rectangle
            ):
                raise ReviewSemanticValidationError("pdf_rectangle_invalid")
            if rectangle[0] >= rectangle[2] or rectangle[1] >= rectangle[3]:
                raise ReviewSemanticValidationError("pdf_rectangle_invalid")
    else:
        raise ReviewSemanticValidationError("source_location_unknown")


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
        raise ReviewSemanticValidationError("coverage_partition_duplicates")
    if set(reviewed) & set(fragment_gaps) or set(reviewed) | set(fragment_gaps) != set(target):
        raise ReviewSemanticValidationError("coverage_partition_inexact")
    if any(
        fragment_id not in fragments or fragments[fragment_id]["source_id"] != primary_source_id
        for fragment_id in target
    ):
        raise ReviewSemanticValidationError("coverage_target_invalid")
    for gap in coverage["gaps"]:
        fragment_id = gap["fragment_id"]
        if fragment_id is None:
            continue
        fragment = fragments.get(fragment_id)
        if fragment is None or fragment["source_id"] != gap["source_id"]:
            raise ReviewSemanticValidationError("coverage_gap_source_mismatch")
    if coverage["status"] == "complete" and coverage["gaps"]:
        raise ReviewSemanticValidationError("coverage_complete_has_gaps")
    if coverage["status"] == "partial" and not coverage["gaps"]:
        raise ReviewSemanticValidationError("coverage_partial_without_gaps")
    finding_ids: set[str] = set()
    ordinals: set[int] = set()
    for finding in report["findings"]:
        if finding["id"] in finding_ids or finding["ordinal"] in ordinals:
            raise ReviewSemanticValidationError("finding_identity_duplicate")
        finding_ids.add(finding["id"])
        ordinals.add(finding["ordinal"])
        anchors = finding["anchors"]
        scope = finding["scope"]
        if finding["kind"] == "missing":
            if anchors:
                raise ReviewSemanticValidationError("missing_finding_scope_invalid")
        primary_basis = False
        for anchor in anchors:
            fragment = fragments.get(anchor["fragment_id"])
            if fragment is None:
                raise ReviewSemanticValidationError("anchor_fragment_unknown")
            if fragment["source_id"] == primary_source_id and anchor["fragment_id"] not in reviewed:
                raise ReviewSemanticValidationError("anchor_primary_unreviewed")
            if fragment["source_id"] == primary_source_id:
                primary_basis = True
            start, end = anchor["quote_start"], anchor["quote_end"]
            if start < 0 or end <= start or fragment["text"][start:end] != anchor["quote"]:
                raise ReviewSemanticValidationError("anchor_quote_offsets_invalid")
            if (
                anchor["document_id"] != fragment["document_id"]
                or anchor["source_id"] != fragment["source_id"]
            ):
                raise ReviewSemanticValidationError("anchor_source_mismatch")
            _validate_location(anchor["location"])
        for fragment_id in scope:
            fragment = fragments.get(fragment_id)
            if fragment is None or fragment["source_id"] != primary_source_id or fragment_id not in reviewed:
                raise ReviewSemanticValidationError("finding_scope_invalid")
            primary_basis = True
        if not primary_basis and (anchors or scope):
            raise ReviewSemanticValidationError("finding_primary_basis_missing")
