from review_runtime.postgres.artifact_fence import acquire_artifact_fence, advisory_fence_key
from review_runtime.postgres.uow import create_uow_factory
from sqlalchemy import text


async def test_publication_and_collector_share_transaction_fence(database_url: str) -> None:
    engine, factory = create_uow_factory(database_url)
    key = advisory_fence_key("org-workspace", "key", "0" * 64)
    async with factory() as publisher, publisher.begin():
        assert await acquire_artifact_fence(publisher, "org-workspace", "key", "0" * 64) == key
        async with factory() as collector, collector.begin():
            result = await collector.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key})
            assert result is False
    async with factory() as collector, collector.begin():
        result = await collector.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key})
        assert result is True
    await engine.dispose()
