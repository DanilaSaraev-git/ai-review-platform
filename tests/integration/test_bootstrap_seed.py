from review_runtime.postgres.bootstrap import check_runtime_seed, seed_runtime
from review_runtime.postgres.uow import AsyncUnitOfWork, create_uow_factory


async def test_full_seed_is_clean_and_idempotent(operator_settings) -> None:  # type: ignore[no-untyped-def]
    engine, factory = create_uow_factory(operator_settings.database_url)
    async with AsyncUnitOfWork(factory) as uow:
        await seed_runtime(uow.session, operator_settings)
    async with AsyncUnitOfWork(factory) as uow:
        assert await check_runtime_seed(uow.session, operator_settings)
        await seed_runtime(uow.session, operator_settings)
    await engine.dispose()
