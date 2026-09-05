from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Protocol, runtime_checkable

type JsonValue = None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]


class GenerationPurpose(StrEnum):
    REVIEW = "review"
    SYNTHESIS = "synthesis"
    DIALOGUE = "dialogue"
    REPAIR = "repair"


class FinishReason(StrEnum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    OTHER = "other"


class ModelErrorCode(StrEnum):
    AUTHENTICATION_FAILED = "authentication_failed"
    MODEL_NOT_FOUND = "model_not_found"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    CONTEXT_LIMIT = "context_limit"
    CONTENT_BLOCKED = "content_blocked"
    UNSUPPORTED_OPTION = "unsupported_option"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"


@dataclass(frozen=True, slots=True)
class ModelProfileSnapshot:
    id: str
    version: str
    config_sha256: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.version.strip():
            raise ValueError("model profile id and version are required")
        if len(self.config_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.config_sha256
        ):
            raise ValueError("model profile config_sha256 must be a lowercase SHA-256 digest")


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    request_id: str
    purpose: GenerationPurpose
    work_item_id: str
    trusted_instructions: str
    untrusted_input: str
    response_schema: dict[str, JsonValue]
    model_profile: ModelProfileSnapshot
    max_output_tokens: int
    timeout_seconds: float
    temperature: float | None = None

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.work_item_id.strip():
            raise ValueError("request_id and work_item_id are required")
        if not self.trusted_instructions.strip():
            raise ValueError("trusted instructions are required")
        if self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if self.temperature is not None and not isfinite(self.temperature):
            raise ValueError("temperature must be finite when provided")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None
    output_tokens: int | None

    def __post_init__(self) -> None:
        if self.input_tokens is not None and self.input_tokens < 0:
            raise ValueError("input_tokens cannot be negative")
        if self.output_tokens is not None and self.output_tokens < 0:
            raise ValueError("output_tokens cannot be negative")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    request_id: str
    text: str
    provider: str
    model: str
    model_version: str
    finish_reason: FinishReason
    usage: TokenUsage | None
    provider_request_id: str | None
    latency_ms: int
    safe_parameters: dict[str, JsonValue]

    def __post_init__(self) -> None:
        if not self.request_id.strip():
            raise ValueError("request_id is required")
        if not self.provider.strip() or not self.model.strip() or not self.model_version.strip():
            raise ValueError("provider, model, and model_version are required")
        if self.latency_ms < 0:
            raise ValueError("latency_ms cannot be negative")


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    text_generation: bool
    vision: bool
    native_structured_output: bool
    max_context_tokens: int | None
    supported_parameters: frozenset[str]

    def __post_init__(self) -> None:
        if self.max_context_tokens is not None and self.max_context_tokens <= 0:
            raise ValueError("max_context_tokens must be positive when provided")


class ModelAdapterError(RuntimeError):
    """Safe, normalized model-boundary error without a raw provider response."""

    def __init__(
        self,
        *,
        code: ModelErrorCode,
        message: str,
        retryable: bool,
        retry_after_seconds: float | None = None,
        provider_request_id: str | None = None,
        automatic_retry_allowed: bool = False,
        outcome_known: bool = True,
    ) -> None:
        if not message.strip():
            raise ValueError("a safe error message is required")
        if retry_after_seconds is not None and (not isfinite(retry_after_seconds) or retry_after_seconds < 0):
            raise ValueError("retry_after_seconds must be finite and non-negative")
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds
        self.provider_request_id = provider_request_id
        self.automatic_retry_allowed = automatic_retry_allowed
        self.outcome_known = outcome_known


@runtime_checkable
class ModelAdapter(Protocol):
    async def capabilities(self) -> ModelCapabilities: ...

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...
