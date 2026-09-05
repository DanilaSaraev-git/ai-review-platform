from __future__ import annotations

from typing import Any


def next_decision(
    current: dict[str, Any], body: dict[str, Any], *, actor: dict[str, str], decided_at: str
) -> dict[str, Any]:
    if body["expected_revision"] != current["revision"]:
        raise ValueError("stale decision revision")
    revision = current["revision"] + 1
    if body["status"] == "unreviewed":
        if body.get("reason") is not None or body.get("resolution") is not None:
            raise ValueError("reset must clear reason and resolution")
        return {
            "status": "unreviewed",
            "revision": revision,
            "actor": None,
            "reason": None,
            "resolution": None,
            "decided_at": None,
        }
    if (
        body["status"] not in {"confirmed", "rejected", "needs_context"}
        or not str(body.get("reason") or "").strip()
    ):
        raise ValueError("a non-unreviewed decision needs status and reason")
    return {
        "status": body["status"],
        "revision": revision,
        "actor": actor,
        "reason": body["reason"],
        "resolution": body.get("resolution"),
        "decided_at": decided_at,
    }
