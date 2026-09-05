from __future__ import annotations

from collections.abc import Callable

import pytest
from review_core.application.model_retry import generate_with_retry
from review_core.ports.models import (
    FinishReason,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    ModelAdapterError,
    ModelCapabilities,
    ModelErrorCode,
    ModelProfileSnapshot,
)


class VirtualClock:
    def __init__(self, now: float = 10.0) -> None:
        self.now = now
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class ScriptedAdapter:
    def __init__(self, outcomes: list[GenerationResult | ModelAdapterError]) -> None:
        self.outcomes = outcomes
        self.requests: list[GenerationRequest] = []

    async def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            text_generation=True,
            vision=False,
            native_structured_output=False,
            max_context_tokens=4096,
            supported_parameters=frozenset(),
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, ModelAdapterError):
            raise outcome
        return outcome


def request_factory(seen_timeouts: list[float]) -> Callable[[int, float], GenerationRequest]:
    def build(ordinal: int, timeout_seconds: float) -> GenerationRequest:
        seen_timeouts.append(timeout_seconds)
        return GenerationRequest(
            request_id=f"request-{ordinal}",
            purpose=GenerationPurpose.REVIEW,
            work_item_id="whole-document",
            trusted_instructions="Return the declared synthetic schema.",
            untrusted_input='{"document":"synthetic data"}',
            response_schema={"type": "object"},
            model_profile=ModelProfileSnapshot(id="synthetic-model", version="1.0.0", config_sha256="a" * 64),
            max_output_tokens=256,
            timeout_seconds=timeout_seconds,
        )

    return build


def result(request_id: str) -> GenerationResult:
    return GenerationResult(
        request_id=request_id,
        text='{"ok":true}',
        provider="synthetic",
        model="synthetic-model",
        model_version="unknown",
        finish_reason=FinishReason.STOP,
        usage=None,
        provider_request_id=None,
        latency_ms=5,
        safe_parameters={},
    )


@pytest.mark.asyncio
async def test_explicit_transient_failure_retries_once_with_new_request_id() -> None:
    clock = VirtualClock()
    adapter = ScriptedAdapter(
        [
            ModelAdapterError(
                code=ModelErrorCode.RATE_LIMITED,
                message="The model endpoint is temporarily rate limited.",
                retryable=True,
                automatic_retry_allowed=True,
            ),
            result("request-2"),
        ]
    )
    seen_timeouts: list[float] = []

    actual = await generate_with_retry(
        adapter,
        request_factory(seen_timeouts),
        deadline=15.0,
        clock=clock,
        sleep=clock.sleep,
    )

    assert actual.request_id == "request-2"
    assert [request.request_id for request in adapter.requests] == ["request-1", "request-2"]
    assert clock.sleeps == [1.0]
    assert seen_timeouts == [5.0, 4.0]


@pytest.mark.asyncio
async def test_retry_after_uses_same_operation_deadline() -> None:
    clock = VirtualClock()
    adapter = ScriptedAdapter(
        [
            ModelAdapterError(
                code=ModelErrorCode.PROVIDER_UNAVAILABLE,
                message="The model endpoint is temporarily unavailable.",
                retryable=True,
                retry_after_seconds=2.5,
                automatic_retry_allowed=True,
            ),
            result("request-2"),
        ]
    )
    seen_timeouts: list[float] = []

    await generate_with_retry(
        adapter,
        request_factory(seen_timeouts),
        deadline=15.0,
        clock=clock,
        sleep=clock.sleep,
    )

    assert clock.sleeps == [2.5]
    assert seen_timeouts == [5.0, 2.5]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "retryable", "automatic_retry_allowed", "outcome_known"),
    [
        (ModelErrorCode.AUTHENTICATION_FAILED, False, False, True),
        (ModelErrorCode.CONTEXT_LIMIT, False, False, True),
        (ModelErrorCode.TIMEOUT, True, False, False),
        (ModelErrorCode.INVALID_PROVIDER_RESPONSE, True, False, True),
        (ModelErrorCode.PROVIDER_UNAVAILABLE, True, True, False),
    ],
)
async def test_non_automatic_and_unknown_outcomes_are_never_retried(
    code: ModelErrorCode,
    retryable: bool,
    automatic_retry_allowed: bool,
    outcome_known: bool,
) -> None:
    clock = VirtualClock()
    expected = ModelAdapterError(
        code=code,
        message="Safe model error.",
        retryable=retryable,
        automatic_retry_allowed=automatic_retry_allowed,
        outcome_known=outcome_known,
    )
    adapter = ScriptedAdapter([expected])

    with pytest.raises(ModelAdapterError) as caught:
        await generate_with_retry(
            adapter,
            request_factory([]),
            deadline=15.0,
            clock=clock,
            sleep=clock.sleep,
        )

    assert caught.value is expected
    assert len(adapter.requests) == 1
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_retry_is_not_started_when_delay_consumes_remaining_deadline() -> None:
    clock = VirtualClock()
    expected = ModelAdapterError(
        code=ModelErrorCode.RATE_LIMITED,
        message="The model endpoint is temporarily rate limited.",
        retryable=True,
        retry_after_seconds=5.0,
        automatic_retry_allowed=True,
    )
    adapter = ScriptedAdapter([expected])

    with pytest.raises(ModelAdapterError) as caught:
        await generate_with_retry(
            adapter,
            request_factory([]),
            deadline=15.0,
            clock=clock,
            sleep=clock.sleep,
        )

    assert caught.value is expected
    assert len(adapter.requests) == 1
    assert clock.sleeps == []


@pytest.mark.asyncio
async def test_at_most_two_network_attempts_are_made() -> None:
    clock = VirtualClock()
    first = ModelAdapterError(
        code=ModelErrorCode.PROVIDER_UNAVAILABLE,
        message="Temporary provider failure.",
        retryable=True,
        automatic_retry_allowed=True,
    )
    second = ModelAdapterError(
        code=ModelErrorCode.PROVIDER_UNAVAILABLE,
        message="Temporary provider failure.",
        retryable=True,
        automatic_retry_allowed=True,
    )
    adapter = ScriptedAdapter([first, second, result("request-3")])

    with pytest.raises(ModelAdapterError) as caught:
        await generate_with_retry(
            adapter,
            request_factory([]),
            deadline=20.0,
            clock=clock,
            sleep=clock.sleep,
        )

    assert caught.value is second
    assert [request.request_id for request in adapter.requests] == ["request-1", "request-2"]
    assert clock.sleeps == [1.0]
