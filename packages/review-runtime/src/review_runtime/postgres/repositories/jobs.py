from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, cast

from sqlalchemy import update

from review_runtime.postgres.models import JobOutbox
from review_runtime.postgres.repositories.base import NamespaceRepository


class JobRepository(NamespaceRepository):
    async def claim(self, *, owner: str, now: datetime, lease_seconds: int) -> JobOutbox | None:
        statement = (
            self.scoped(JobOutbox)
            .where(
                JobOutbox.next_attempt_at <= now,
                (JobOutbox.state == "pending")
                | ((JobOutbox.state == "publishing") & (JobOutbox.lease_expires_at < now)),
            )
            .order_by(JobOutbox.next_attempt_at, JobOutbox.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        row = cast(JobOutbox | None, (await self.session.execute(statement)).scalar_one_or_none())
        if row is None:
            return None
        row.state = "publishing"
        row.claimed_by = owner
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.attempts += 1
        await self.session.flush()
        return row

    async def mark_published(self, outbox_id: str, owner: str) -> bool:
        result = await self.session.execute(
            update(JobOutbox)
            .where(
                JobOutbox.organization_id == self.organization_id,
                JobOutbox.workspace_id == self.workspace_id,
                JobOutbox.id == outbox_id,
                JobOutbox.state == "publishing",
                JobOutbox.claimed_by == owner,
            )
            .values(state="published", claimed_by=None, claim_token=None, lease_expires_at=None)
        )
        return cast(Any, result).rowcount == 1
