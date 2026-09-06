from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from review_core.domain.errors import Conflict
from review_runtime.ml_runtime import LLMReviewRuntime
from review_runtime.multi_model_runtime import LLMReviewRouter
from review_runtime.postgres.platform import PostgresReviewPlatform


class _Runtime:
    def __init__(self, platform: object, name: str, events: list[str], *, fail_start: bool = False) -> None:
        self.platform = platform
        self.model_profile = SimpleNamespace(id=name, version="1.0.0")
        self.events = events
        self.fail_start = fail_start

    async def __aenter__(self) -> _Runtime:
        self.events.append(f"enter:{self.model_profile.id}")
        if self.fail_start:
            raise RuntimeError("synthetic startup failure")
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.events.append(f"exit:{self.model_profile.id}")


async def test_router_closes_all_started_runtimes_in_reverse_order() -> None:
    platform = cast(PostgresReviewPlatform, object())
    events: list[str] = []
    runtimes = tuple(cast(LLMReviewRuntime, _Runtime(platform, name, events)) for name in ("first", "second"))
    router = LLMReviewRouter(platform, runtimes)

    async with router as entered:
        assert entered is router
        assert events == ["enter:first", "enter:second"]

    assert events == ["enter:first", "enter:second", "exit:second", "exit:first"]


async def test_router_unwinds_started_runtime_when_later_startup_fails() -> None:
    platform = cast(PostgresReviewPlatform, object())
    events: list[str] = []
    router = LLMReviewRouter(
        platform,
        (
            cast(LLMReviewRuntime, _Runtime(platform, "first", events)),
            cast(LLMReviewRuntime, _Runtime(platform, "second", events, fail_start=True)),
        ),
    )

    with pytest.raises(RuntimeError, match="synthetic startup failure"):
        async with router:
            pytest.fail("failed startup must never admit calls")

    assert events == ["enter:first", "enter:second", "exit:first"]


@pytest.mark.parametrize("retry", [False, True])
async def test_missing_pinned_model_never_reaches_a_runtime_or_deterministic_fallback(retry: bool) -> None:
    platform = cast(
        PostgresReviewPlatform,
        SimpleNamespace(dialogue_model_reference=lambda *_: {"id": "removed", "version": "1.0.0"}),
    )
    events: list[str] = []
    router = LLMReviewRouter(platform, (cast(LLMReviewRuntime, _Runtime(platform, "available", events)),))

    with pytest.raises(Conflict, match="model profile is unavailable"):
        if retry:
            await router.retry_dialogue_turn("workspace", "run", "finding", "turn", {}, "key")
        else:
            await router.create_dialogue_turn("workspace", "run", "finding", {}, "key")

    assert events == []
