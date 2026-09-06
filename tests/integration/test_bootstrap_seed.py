import json
from pathlib import Path
from uuid import uuid4

from review_runtime.config.settings import OperatorSettings
from review_runtime.config.verify import verify
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.bootstrap import check_runtime_seed, seed_runtime
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.postgres.uow import AsyncUnitOfWork, create_uow_factory


async def test_full_seed_is_clean_and_idempotent(operator_settings) -> None:  # type: ignore[no-untyped-def]
    engine, factory = create_uow_factory(operator_settings.database_url)
    async with AsyncUnitOfWork(factory) as uow:
        await seed_runtime(uow.session, operator_settings)
    async with AsyncUnitOfWork(factory) as uow:
        assert await check_runtime_seed(uow.session, operator_settings)
        await seed_runtime(uow.session, operator_settings)
    await engine.dispose()


async def test_bootstrap_seed_opens_with_the_configured_runtime_policy(
    operator_settings: OperatorSettings, tmp_path: Path
) -> None:
    config = json.loads(operator_settings.runtime_config_path.read_text())
    config["budgets"]["max_dialogue_turns"] = 7
    config_path = tmp_path / "runtime-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    settings = operator_settings.model_copy(
        update={
            "deployment_id": uuid4(),
            "organization_id": uuid4(),
            "workspace_id": uuid4(),
            "actor_id": uuid4(),
            "system_profile_id": str(uuid4()),
            "dialogue_policy_id": f"bootstrap-policy-{uuid4().hex}",
            "runtime_config_path": config_path,
        }
    )
    engine, factory = create_uow_factory(settings.database_url)
    try:
        async with AsyncUnitOfWork(factory) as uow:
            await seed_runtime(uow.session, settings)
        async with AsyncUnitOfWork(factory) as uow:
            await seed_runtime(uow.session, settings)
            assert await check_runtime_seed(uow.session, settings)
    finally:
        await engine.dispose()

    platform = PostgresReviewPlatform(
        TrustedFixtureReviewExecutor(Path(__file__).parents[2]),
        settings,
        runtime_policy=verify(config_path),
    )
    assert platform.dialogue_policy["max_member_turns"] == 7
