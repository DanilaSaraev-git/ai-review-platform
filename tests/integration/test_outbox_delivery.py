from datetime import UTC, datetime
from uuid import uuid4

from review_runtime.postgres.bootstrap import seed_runtime
from review_runtime.postgres.models import JobOutbox
from review_runtime.postgres.repositories.jobs import JobRepository
from review_runtime.postgres.uow import AsyncUnitOfWork, create_uow_factory


async def test_outbox_claim_is_single_owner_and_duplicate_safe(operator_settings) -> None:  # type: ignore[no-untyped-def]
    engine, factory = create_uow_factory(operator_settings.database_url)
    organization = str(operator_settings.organization_id)
    workspace = str(operator_settings.workspace_id)
    outbox_id = str(uuid4())
    async with AsyncUnitOfWork(factory) as uow:
        await seed_runtime(uow.session, operator_settings)
        uow.session.add(
            JobOutbox(
                organization_id=organization,
                workspace_id=workspace,
                id=outbox_id,
                kind="execute_review",
                business_key=str(uuid4()),
                payload={"review_execution_id": str(uuid4())},
                state="pending",
                attempts=0,
                max_attempts=3,
                claim_token=None,
                claimed_by=None,
                lease_expires_at=None,
                next_attempt_at=datetime.now(UTC),
            )
        )
    async with AsyncUnitOfWork(factory) as uow:
        repository = JobRepository(uow.session, organization, workspace)
        row = await repository.claim(owner="worker-a", now=datetime.now(UTC), lease_seconds=60)
        assert row is not None and row.id == outbox_id
        assert await repository.mark_published(row.id, "worker-a")
        assert not await repository.mark_published(row.id, "worker-a")
    await engine.dispose()
