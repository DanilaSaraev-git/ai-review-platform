from datetime import UTC, datetime, timedelta

from review_worker.handlers import claim_execution, finish_execution
from review_worker.recovery import stalled


def test_stale_execution_takeover_invalidates_old_token() -> None:
    execution = {
        "state": "running",
        "attempt_count": 1,
        "lease_token": "old",
        "lease_expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
    }
    assert stalled([execution]) == [execution]
    token = claim_execution(execution, owner="worker-b", lease_seconds=60)
    assert token and token != "old"
    assert not finish_execution(execution, "old")
    assert finish_execution(execution, token)
