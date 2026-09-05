from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def project_availability(observation: dict[str, Any] | None, *, now: datetime | None = None) -> str:
    if observation is None:
        return "unavailable"
    current = now or datetime.now(UTC)
    expires = observation.get("expires_at")
    if not isinstance(expires, datetime) or expires <= current:
        return "unavailable"
    return "available" if observation.get("state") == "available" else "unavailable"
