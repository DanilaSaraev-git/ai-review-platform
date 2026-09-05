from __future__ import annotations

from typing import Any

HUMAN_FIELDS = {"human_decision", "decision", "decision_status", "confirmed", "accepted"}


def validate_dialogue_output(value: dict[str, Any]) -> dict[str, Any]:
    if HUMAN_FIELDS & value.keys():
        raise ValueError("Model output cannot contain a Human Decision")
    if value.get("action") not in {"clarify", "propose_resolution", "escalate"}:
        raise ValueError("invalid dialogue action")
    if not isinstance(value.get("content"), str) or not value["content"].strip():
        raise ValueError("dialogue content is required")
    return value
