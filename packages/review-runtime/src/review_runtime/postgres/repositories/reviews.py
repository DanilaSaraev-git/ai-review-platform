from __future__ import annotations

from sqlalchemy import select

from review_runtime.postgres.models import IdempotencyRecord, JobOutbox, ReviewRun, ReviewRunExecution
from review_runtime.postgres.repositories.base import NamespaceRepository


class IdempotencyConflict(ValueError):
    pass


class ReviewRepository(NamespaceRepository):
    async def create_run_once(
        self,
        *,
        record: IdempotencyRecord,
        run: ReviewRun,
        execution: ReviewRunExecution,
        outbox: JobOutbox,
    ) -> tuple[ReviewRun, bool]:
        existing = (
            await self.session.execute(
                select(IdempotencyRecord)
                .where(
                    IdempotencyRecord.organization_id == self.organization_id,
                    IdempotencyRecord.workspace_id == self.workspace_id,
                    IdempotencyRecord.operation == record.operation,
                    IdempotencyRecord.key == record.key,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.request_digest != record.request_digest:
                raise IdempotencyConflict("idempotency key already has another request digest")
            replay = await self.get(ReviewRun, existing.resource_id)
            if replay is None:
                raise RuntimeError("idempotency record references a missing run")
            return replay, False
        await self.add(run)
        await self.add(execution)
        await self.add(outbox)
        self.session.add(record)
        await self.session.flush()
        return run, True

    async def run(self, run_id: str) -> ReviewRun | None:
        return await self.get(ReviewRun, run_id)
