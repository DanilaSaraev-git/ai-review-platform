from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4


def claim_execution(execution: dict[str, Any], *, owner: str, lease_seconds: int) -> str | None:
    now = datetime.now(UTC)
    expires = execution.get("lease_expires_at")
    if execution.get("state") == "completed":
        return None
    if execution.get("lease_token") and expires and datetime.fromisoformat(expires) >= now:
        return None
    token = str(uuid4())
    execution.update(
        state="running",
        lease_token=token,
        lease_owner=owner,
        lease_expires_at=(now + timedelta(seconds=lease_seconds)).isoformat(),
        attempt_count=execution.get("attempt_count", 0) + 1,
    )
    return token


def finish_execution(execution: dict[str, Any], token: str) -> bool:
    if execution.get("lease_token") != token:
        return False
    execution.update(state="completed", checkpoint="published", lease_token=None, lease_owner=None)
    return True
