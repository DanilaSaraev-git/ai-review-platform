from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from review_runtime.postgres.repositories.jobs import JobRepository


async def dispatch_one(
    repository: JobRepository,
    publish: Callable[[str, dict[str, object]], Awaitable[object]],
    *,
    owner: str,
    lease_seconds: int = 60,
) -> bool:
    row = await repository.claim(owner=owner, now=datetime.now(UTC), lease_seconds=lease_seconds)
    if row is None:
        return False
    await publish(row.kind, row.payload)
    if not await repository.mark_published(row.id, owner):
        raise RuntimeError("outbox claim was lost before publication confirmation")
    return True
