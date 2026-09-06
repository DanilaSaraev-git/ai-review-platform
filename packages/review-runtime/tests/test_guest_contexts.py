from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import anyio
import httpx
import pytest
from review_core.ports.models import ModelAdapter
from review_runtime.composition import ModelRuntime
from review_runtime.config.model_profiles import ModelProfile
from review_runtime.config.settings import RuntimePolicy
from review_runtime.ml_runtime import LLMReviewRuntime
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.security.guest_contexts import GuestContextRegistry
from review_runtime.skills.registry import SkillRegistry


@dataclass
class _Platform:
    workspace_id: str = "private"
    actor_id: str = "operator"
    children: list[_Platform] = field(default_factory=list)
    reconciled: list[str] = field(default_factory=list)
    fail_next: bool = False

    def for_guest(self, workspace_id: str, actor_id: str) -> _Platform:
        if self.fail_next:
            self.fail_next = False
            raise ValueError("synthetic initialization failure")
        child = _Platform(workspace_id, actor_id, reconciled=self.reconciled)
        self.children.append(child)
        return child

    def reconcile_interrupted(self) -> None:
        self.reconciled.append(self.workspace_id)


class _Runtime:
    def __init__(self, platform: _Platform) -> None:
        self.platform = platform
        self.children: list[_Runtime] = []
        self.closed = anyio.Event()
        self.completed = anyio.Event()
        self.release = anyio.Event()
        self.has_pending_work = False
        self.saved_workspace: str | None = None
        self.owner: asyncio.Task[Any] | None = None
        self.tasks: anyio.abc.TaskGroup | None = None

    def for_platform(self, platform: _Platform) -> _Runtime:
        child = _Runtime(platform)
        self.children.append(child)
        return child

    async def __aenter__(self) -> _Runtime:
        self.owner = asyncio.current_task()
        self.tasks = await anyio.create_task_group().__aenter__()
        return self

    async def __aexit__(self, *args: Any) -> None:
        assert asyncio.current_task() is self.owner
        assert self.tasks is not None
        await self.tasks.__aexit__(*args)
        self.closed.set()

    def start_background_work(self) -> None:
        assert self.tasks is not None
        self.has_pending_work = True
        self.tasks.start_soon(self._work)

    async def _work(self) -> None:
        await self.release.wait()
        self.saved_workspace = self.platform.workspace_id
        self.has_pending_work = False
        self.completed.set()

    async def wait_idle(self) -> None:
        if self.has_pending_work:
            await self.completed.wait()


def _registry(platform: _Platform, runtime: _Runtime | None = None, **kwargs: Any) -> GuestContextRegistry:
    return GuestContextRegistry(
        cast(PostgresReviewPlatform, platform), cast(LLMReviewRuntime | None, runtime), **kwargs
    )


async def test_concurrent_borrowers_share_one_context_and_owner_task() -> None:
    platform = _Platform()
    runtime = _Runtime(platform)
    release, all_entered = anyio.Event(), anyio.Event()
    contexts = []
    with anyio.fail_after(3):
        async with _registry(platform, runtime) as registry:
            async def borrow() -> None:
                async with registry.use("guest-a", "actor-a") as context:
                    contexts.append(context)
                    if len(contexts) == 10:
                        all_entered.set()
                    await release.wait()

            async with anyio.create_task_group() as borrowers:
                for _ in range(10):
                    borrowers.start_soon(borrow)
                await all_entered.wait()
                assert len(platform.children) == len(runtime.children) == 1
                assert all(context is contexts[0] for context in contexts)
                release.set()
            await runtime.children[0].closed.wait()
    assert not runtime.closed.is_set()


async def test_two_guests_have_separate_scopes_and_leave_private_scope_unchanged() -> None:
    platform = _Platform()
    runtime = _Runtime(platform)
    async with _registry(platform, runtime) as registry:
        async with registry.use("guest-a", "actor-a") as first:
            async with registry.use("guest-b", "actor-b") as second:
                assert first.platform is not second.platform
                assert first.runtime is not second.runtime
                assert first.platform.workspace_id == "guest-a"
                assert second.platform.workspace_id == "guest-b"
                with pytest.raises(ValueError, match="actor does not match"):
                    async with registry.use("guest-a", "actor-b"):
                        pytest.fail("mismatched actor was accepted")
    assert (platform.workspace_id, platform.actor_id) == ("private", "operator")
    assert all(child.closed.is_set() for child in runtime.children)


async def test_cancelled_http_waiter_keeps_background_work_and_can_rejoin() -> None:
    platform = _Platform()
    runtime = _Runtime(platform)
    started, detached = anyio.Event(), anyio.Event()
    scope: anyio.CancelScope | None = None
    with anyio.fail_after(3):
        async with _registry(platform, runtime) as registry:
            async def request() -> None:
                nonlocal scope
                with anyio.CancelScope() as scope:
                    async with registry.use("guest-a", "actor-a"):
                        runtime.children[0].start_background_work()
                        started.set()
                        await anyio.sleep_forever()
                detached.set()

            async with anyio.create_task_group() as requests:
                requests.start_soon(request)
                await started.wait()
                assert scope is not None
                scope.cancel()
                await detached.wait()
                child = runtime.children[0]
                assert not child.closed.is_set()
                async with registry.use("guest-a", "actor-a") as context:
                    assert context.runtime is child
                    child.release.set()
                    await child.completed.wait()
                await child.closed.wait()
    assert child.saved_workspace == "guest-a"


async def test_capacity_waits_for_detached_work_then_releases_memory() -> None:
    platform = _Platform()
    runtime = _Runtime(platform)
    second_entered = anyio.Event()
    with anyio.fail_after(3):
        async with _registry(platform, runtime, max_contexts=1) as registry:
            async with registry.use("guest-a", "actor-a"):
                first = runtime.children[0]
                first.start_background_work()

            async def second_request() -> None:
                async with registry.use("guest-b", "actor-b"):
                    second_entered.set()

            async with anyio.create_task_group() as requests:
                requests.start_soon(second_request)
                with anyio.move_on_after(0.02) as blocked:
                    await second_entered.wait()
                assert blocked.cancel_called
                first.release.set()
                await second_entered.wait()
            assert first.closed.is_set()
        assert len(runtime.children) == 2
        assert all(child.closed.is_set() for child in runtime.children)


async def test_failed_initialization_does_not_poison_registry_or_leak_capacity() -> None:
    platform = _Platform(fail_next=True)
    with anyio.fail_after(3):
        async with _registry(platform, max_contexts=1) as registry:
            with pytest.raises(ValueError, match="synthetic initialization"):
                async with registry.use("guest-a", "actor-a"):
                    pytest.fail("failed context was borrowed")
            async with registry.use("guest-a", "actor-a") as context:
                assert context.platform.workspace_id == "guest-a"
                assert context.runtime is None


async def test_startup_reconciles_registered_namespaces_before_first_borrow() -> None:
    platform = _Platform()
    async with _registry(platform) as registry:
        await registry.reconcile("guest-a", "actor-a")
        await registry.reconcile("guest-b", "actor-b")
        assert platform.reconciled == ["guest-a", "guest-b"]
        async with registry.use("guest-a", "actor-a"):
            with pytest.raises(RuntimeError, match="precede request handling"):
                await registry.reconcile("guest-a", "actor-a")


async def test_registry_rejects_borrow_before_start_and_after_shutdown() -> None:
    registry = _registry(_Platform())
    with pytest.raises(RuntimeError, match="not running"):
        async with registry.use("guest-a", "actor-a"):
            pytest.fail("unstarted registry accepted request")
    async with registry:
        pass
    with pytest.raises(RuntimeError, match="not running"):
        async with registry.use("guest-a", "actor-a"):
            pytest.fail("stopped registry accepted request")


async def test_real_runtime_clones_share_call_budget_and_borrow_client_ownership() -> None:
    root = Path(__file__).parents[3]
    profile = ModelProfile.model_validate_json(
        (root / "tests/fixtures/ml-integration/model-profile.compose.json").read_text()
    )
    skill = SkillRegistry(
        root / "contracts/review-platform/v1/schemas/skill-manifest.schema.json",
        engine_version="0.1.0",
        model_capabilities={"text_generation"},
    ).resolve(root / "tests/fixtures/ml-integration/skill")
    writes: list[str] = []

    class Adapter:
        active = 0
        maximum = 0

        async def capabilities(self) -> Any:
            return SimpleNamespace(text_generation=True)

        async def generate(self, _request: Any) -> Any:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            await anyio.sleep(0.02)
            self.active -= 1
            return object()

    class Storage:
        def __init__(self, workspace_id: str) -> None:
            self.workspace_id = workspace_id

        def begin_model_attempt(self, _request: Any) -> str:
            return self.workspace_id

        def finish_model_attempt(self, _attempt_id: str, **_kwargs: Any) -> None:
            writes.append(self.workspace_id)

    def platform(workspace_id: str) -> PostgresReviewPlatform:
        return cast(
            PostgresReviewPlatform,
            SimpleNamespace(
                workspace_id=workspace_id,
                review_storage=Storage(workspace_id),
                runtime_policy=RuntimePolicy(budgets={"max_parallel_model_calls": 1}),
                settings=SimpleNamespace(review_deadline_seconds=2, finalization_timeout_seconds=1),
                observe_model_profile=lambda *_args, **_kwargs: None,
            ),
        )

    adapter = Adapter()
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200)))
    parent = LLMReviewRuntime(
        platform=platform("private"),
        model_runtime=ModelRuntime(adapter=cast(ModelAdapter, adapter), _owned_client=client),
        model_profile=profile,
        skill=skill,
        root=root,
    )
    first = parent.for_platform(platform("guest-a"))
    second = parent.for_platform(platform("guest-b"))
    async with parent:
        async with first, second:
            assert not first.has_pending_work
            await first.wait_idle()
            async with anyio.create_task_group() as calls:
                calls.start_soon(first._recording_adapter.generate, object())
                calls.start_soon(second._recording_adapter.generate, object())
        assert not client.is_closed
    assert client.is_closed
    assert adapter.maximum == 1
    assert sorted(writes) == ["guest-a", "guest-b"]
    assert parent.platform.workspace_id == "private"
