from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from typing import Literal

import anyio

from review_core.ports.models import (
    GenerationRequest,
    GenerationResult,
    ModelAdapter,
    ModelAdapterError,
    ModelErrorCode,
)

type Clock = Callable[[], float]
type Sleep = Callable[[float], Awaitable[None]]
type RequestFactory = Callable[[int, float], GenerationRequest]

_MAX_ATTEMPTS = 2
_DEFAULT_RETRY_DELAY_SECONDS = 1.0
_AUTOMATIC_RETRY_CODES = frozenset({ModelErrorCode.RATE_LIMITED, ModelErrorCode.PROVIDER_UNAVAILABLE})

type PublicReviewErrorCode = Literal[
    "context_limit", "model_unavailable", "model_output_invalid"
]
type PublicDialogueErrorCode = Literal[
    "context_limit", "content_blocked", "model_unavailable", "model_output_invalid"
]


def public_model_error_code(
    error: ModelAdapterError, *, purpose: Literal["review", "dialogue"]
) -> PublicReviewErrorCode | PublicDialogueErrorCode:
    """Project internal adapter errors onto the frozen HTTP v1 error enums."""

    if error.code is ModelErrorCode.CONTEXT_LIMIT:
        return "context_limit"
    if error.code is ModelErrorCode.CONTENT_BLOCKED:
        return "content_blocked" if purpose == "dialogue" else "model_output_invalid"
    if error.code is ModelErrorCode.INVALID_PROVIDER_RESPONSE:
        return "model_output_invalid"
    return "model_unavailable"


class ModelOperationDeadlineExceeded(ModelAdapterError):
    def __init__(self) -> None:
        super().__init__(
            code=ModelErrorCode.TIMEOUT,
            message="The model operation deadline was exceeded.",
            retryable=True,
            automatic_retry_allowed=False,
            outcome_known=False,
        )


def _can_retry(error: ModelAdapterError) -> bool:
    return error.automatic_retry_allowed and error.outcome_known and error.code in _AUTOMATIC_RETRY_CODES


async def generate_with_retry(
    adapter: ModelAdapter,
    request_factory: RequestFactory,
    *,
    deadline: float,
    clock: Clock = time.monotonic,
    sleep: Sleep = anyio.sleep,
) -> GenerationResult:
    """Execute at most two adapter calls inside one monotonic operation deadline."""

    for ordinal in range(1, _MAX_ATTEMPTS + 1):
        remaining = deadline - clock()
        if remaining <= 0:
            raise ModelOperationDeadlineExceeded

        request = request_factory(ordinal, remaining)
        try:
            result = await adapter.generate(request)
        except ModelAdapterError as error:
            if clock() >= deadline:
                raise ModelOperationDeadlineExceeded from error
            if ordinal == _MAX_ATTEMPTS or not _can_retry(error):
                raise

            delay = (
                error.retry_after_seconds
                if error.retry_after_seconds is not None
                else _DEFAULT_RETRY_DELAY_SECONDS
            )
            if delay >= deadline - clock():
                raise
            await sleep(delay)
            continue

        if result.request_id != request.request_id:
            raise ModelAdapterError(
                code=ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                message="The model response request ID does not match the request.",
                retryable=False,
            )
        if clock() >= deadline:
            raise ModelOperationDeadlineExceeded
        return result

    raise AssertionError("model retry loop exhausted without a result or error")
