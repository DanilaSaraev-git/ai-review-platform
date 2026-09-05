from __future__ import annotations

from collections.abc import Mapping
from typing import Any

HUMAN_FIELDS = {"human_decision", "decision", "decision_status", "confirmed", "accepted"}


def _contains_human_field(value: object) -> bool:
    if isinstance(value, Mapping):
        return bool(HUMAN_FIELDS & value.keys()) or any(
            _contains_human_field(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_human_field(item) for item in value)
    return False


def validate_dialogue_output(
    value: dict[str, Any], *, fragments: Mapping[str, Mapping[str, Any]] | None = None
) -> dict[str, Any]:
    if _contains_human_field(value):
        raise ValueError("Model output cannot contain a Human Decision")
    if value.get("action") not in {"clarify", "propose_resolution", "escalate"}:
        raise ValueError("invalid dialogue action")
    if not isinstance(value.get("content"), str) or not value["content"].strip():
        raise ValueError("dialogue content is required")
    resolution = value.get("proposed_resolution")
    if value["action"] == "propose_resolution":
        if not isinstance(resolution, Mapping):
            raise ValueError("propose_resolution requires an advisory resolution")
    elif resolution is not None:
        raise ValueError("only propose_resolution may include an advisory resolution")
    if fragments is not None:
        for anchor in value.get("anchors", []):
            fragment = fragments.get(anchor.get("fragment_id"))
            if fragment is None:
                raise ValueError("dialogue anchor references an unknown fragment")
            if (
                anchor.get("source_id") != fragment["source_id"]
                or anchor.get("document_id") != fragment["document_id"]
                or anchor.get("source_name") != fragment["source_name"]
            ):
                raise ValueError("dialogue anchor source identity mismatch")
            start, end = anchor.get("quote_start"), anchor.get("quote_end")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or start < 0
                or end <= start
                or fragment["text"][start:end] != anchor.get("quote")
            ):
                raise ValueError("dialogue anchor quote and offsets do not resolve exactly")
            if anchor.get("location") != fragment["location"]:
                raise ValueError("dialogue anchor location does not match the saved fragment")
    return value
