from __future__ import annotations

from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any

import anyio
from review_core.domain.errors import Conflict

from review_runtime.ml_runtime import LLMReviewRuntime
from review_runtime.postgres.platform import PostgresReviewPlatform


class LLMReviewRouter:
    """Route configured models without changing the report's pinned model identity."""

    def __init__(self, platform: PostgresReviewPlatform, runtimes: tuple[LLMReviewRuntime, ...]) -> None:
        if not runtimes or any(runtime.platform is not platform for runtime in runtimes):
            raise ValueError("model runtimes must share one platform")
        self.platform = platform
        self._runtimes = {
            (runtime.model_profile.id, runtime.model_profile.version): runtime for runtime in runtimes
        }
        if len(self._runtimes) != len(runtimes):
            raise ValueError("model runtime identity must be unique")
        self._stack: AsyncExitStack | None = None

    def for_platform(self, platform: PostgresReviewPlatform) -> LLMReviewRouter:
        """Bind every configured model to one isolated workspace execution owner."""
        return LLMReviewRouter(
            platform,
            tuple(runtime.for_platform(platform) for runtime in self._runtimes.values()),
        )

    @property
    def has_pending_work(self) -> bool:
        return any(runtime.has_pending_work for runtime in self._runtimes.values())

    async def wait_idle(self) -> None:
        for runtime in self._runtimes.values():
            await runtime.wait_idle()

    async def __aenter__(self) -> LLMReviewRouter:
        async with AsyncExitStack() as stack:
            for runtime in self._runtimes.values():
                await stack.enter_async_context(runtime)
            self._stack = stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._stack is not None:
            await self._stack.__aexit__(exc_type, exc_value, traceback)
            self._stack = None

    def _select(self, reference: dict[str, str]) -> LLMReviewRuntime:
        runtime = self._runtimes.get((reference["id"], reference["version"]))
        if runtime is None:
            raise Conflict("model_unavailable", "The report's model profile is unavailable.")
        return runtime

    async def create_run(
        self, workspace_id: str, body: dict[str, Any], idempotency_key: str
    ) -> dict[str, Any]:
        self.platform.exact_model_profile(body["model_profile"])
        return await self._select(body["model_profile"]).create_run(workspace_id, body, idempotency_key)

    async def _for_dialogue(self, workspace_id: str, run_id: str, finding_id: str) -> LLMReviewRuntime:
        reference = await anyio.to_thread.run_sync(
            self.platform.dialogue_model_reference, workspace_id, run_id, finding_id
        )
        return self._select(reference)

    async def create_dialogue_turn(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        runtime = await self._for_dialogue(workspace_id, run_id, finding_id)
        return await runtime.create_dialogue_turn(workspace_id, run_id, finding_id, body, idempotency_key)

    async def retry_dialogue_turn(
        self,
        workspace_id: str,
        run_id: str,
        finding_id: str,
        turn_id: str,
        body: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        runtime = await self._for_dialogue(workspace_id, run_id, finding_id)
        return await runtime.retry_dialogue_turn(
            workspace_id, run_id, finding_id, turn_id, body, idempotency_key
        )
