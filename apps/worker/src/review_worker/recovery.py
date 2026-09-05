from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def stalled(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    now = datetime.now(UTC)
    return [
        item
        for item in items
        if item.get("state") in {"running", "publishing", "extracting"}
        and item.get("lease_expires_at")
        and datetime.fromisoformat(item["lease_expires_at"]) < now
    ]
