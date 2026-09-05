from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, cast

import httpx
from review_core.ports.models import (
    FinishReason,
    GenerationRequest,
    GenerationResult,
    JsonValue,
    ModelAdapterError,
    ModelCapabilities,
    ModelErrorCode,
    TokenUsage,
)

from review_runtime.config.model_profiles import ModelProfile, profile_config_digest
from review_runtime.models.config import SecretProvider


class OpenAICompatibleModelAdapter:
    """One-request adapter; orchestration, retry and response-content validation stay in core."""

    def __init__(
        self,
        *,
        profile: ModelProfile,
        client: httpx.AsyncClient,
        max_response_bytes: int,
        secrets: SecretProvider | None = None,
        monotonic_ms: Callable[[], int] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if profile.adapter_kind != "openai_compatible" or profile.chat_url is None:
            raise ValueError("OpenAI-compatible adapter requires an openai_compatible profile")
        if max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        self.profile = profile
        self.chat_url: str = profile.chat_url
        self.client = client
        self.secrets = secrets
        self.max_response_bytes = max_response_bytes
        self._monotonic_ms = monotonic_ms or (lambda: int(time.monotonic() * 1000))
        self._now = now or (lambda: datetime.now(UTC))

    async def capabilities(self) -> ModelCapabilities:
        declared = set(self.profile.capabilities)
        return ModelCapabilities(
            text_generation="text_generation" in declared,
            vision="vision" in declared,
            native_structured_output="native_structured_output" in declared,
            max_context_tokens=self.profile.context_window_tokens,
            supported_parameters=frozenset(self.profile.supported_parameters),
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self._validate_request(request)
        payload, safe_parameters = self._payload(request)
        encoded_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(encoded_payload) > self.profile.max_input_utf8_bytes:
            raise self._safe_error(ModelErrorCode.CONTEXT_LIMIT, "model input exceeds profile budget")
        headers = self._headers()
        started = self._monotonic_ms()
        try:
            async with self.client.stream(
                "POST",
                self.chat_url,
                headers=headers,
                content=encoded_payload,
                timeout=request.timeout_seconds,
            ) as response:
                provider_request_id = response.headers.get("x-request-id")
                if response.status_code != 200:
                    raise self._http_error(response, provider_request_id)
                raw = await self._bounded_body(response)
                response_headers = response.headers
        except ModelAdapterError:
            raise
        except httpx.ConnectError as error:
            raise self._safe_error(
                ModelErrorCode.PROVIDER_UNAVAILABLE,
                "model connection failed before a response was received",
                retryable=True,
                automatic_retry_allowed=True,
                outcome_known=True,
            ) from error
        except httpx.TimeoutException as error:
            raise self._safe_error(
                ModelErrorCode.TIMEOUT,
                "model request timed out with unknown provider outcome",
                retryable=True,
                outcome_known=False,
            ) from error
        except httpx.NetworkError as error:
            raise self._safe_error(
                ModelErrorCode.PROVIDER_UNAVAILABLE,
                "model transport failed with unknown provider outcome",
                retryable=True,
                outcome_known=False,
            ) from error

        envelope = self._envelope(raw)
        choice = cast(dict[str, Any], cast(list[Any], envelope["choices"])[0])
        message = cast(dict[str, Any], choice["message"])
        text = cast(str, message["content"])
        actual_model = envelope.get("model")
        if not isinstance(actual_model, str) or not actual_model.strip():
            actual_model = self.profile.model
        body_request_id = envelope.get("id")
        if provider_request_id is None and isinstance(body_request_id, str):
            provider_request_id = body_request_id
        return GenerationResult(
            request_id=request.request_id,
            text=text,
            provider=self.profile.provider,
            model=actual_model,
            model_version=response_headers.get("x-model-version") or self.profile.checkpoint or "unknown",
            finish_reason=self._finish_reason(choice.get("finish_reason")),
            usage=self._usage(envelope.get("usage")),
            provider_request_id=provider_request_id,
            latency_ms=max(0, self._monotonic_ms() - started),
            safe_parameters=safe_parameters,
        )

    def _validate_request(self, request: GenerationRequest) -> None:
        snapshot = request.model_profile
        if (
            snapshot.id != self.profile.id
            or snapshot.version != self.profile.version
            or snapshot.config_sha256 != profile_config_digest(self.profile)
        ):
            raise self._safe_error(
                ModelErrorCode.UNSUPPORTED_OPTION,
                "model profile snapshot does not match configured adapter",
            )
        if request.max_output_tokens > self.profile.max_output_tokens:
            raise self._safe_error(ModelErrorCode.CONTEXT_LIMIT, "requested output exceeds profile budget")
        if request.temperature is not None and "temperature" not in self.profile.supported_parameters:
            raise self._safe_error(
                ModelErrorCode.UNSUPPORTED_OPTION,
                "temperature is not supported by the selected model profile",
            )

    def _payload(self, request: GenerationRequest) -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
        output_parameter = (
            "max_completion_tokens"
            if "max_completion_tokens" in self.profile.supported_parameters
            else "max_tokens"
        )
        payload: dict[str, JsonValue] = {
            "model": self.profile.model,
            "messages": [
                {"role": "system", "content": request.trusted_instructions},
                {"role": "user", "content": request.untrusted_input},
            ],
            output_parameter: request.max_output_tokens,
        }
        safe: dict[str, JsonValue] = {
            output_parameter: request.max_output_tokens,
            "structured_output": self.profile.structured_output,
        }
        for key, value in self.profile.request_options.items():
            if value is not None:
                payload[key] = value
                safe[key] = value
        if request.temperature is not None:
            payload["temperature"] = request.temperature
            safe["temperature"] = request.temperature
        if self.profile.structured_output == "native_json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{request.purpose.value}_response",
                    "strict": True,
                    "schema": request.response_schema,
                },
            }
        return payload, safe

    def _headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json"}
        if self.profile.secret_ref is None:
            return headers
        if self.secrets is None:
            raise self._safe_error(
                ModelErrorCode.AUTHENTICATION_FAILED,
                "configured model credential reference is unavailable",
            )
        try:
            secret = self.secrets.resolve(self.profile.secret_ref)
        except (KeyError, ValueError) as error:
            raise self._safe_error(
                ModelErrorCode.AUTHENTICATION_FAILED,
                "configured model credential reference is unavailable",
            ) from error
        headers["authorization"] = f"Bearer {secret}"
        return headers

    async def _bounded_body(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > self.max_response_bytes:
                raise self._safe_error(
                    ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                    "model provider response exceeded configured byte limit",
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def _envelope(self, raw: bytes) -> dict[str, Any]:
        try:
            value = json.loads(raw)
            choices = value["choices"]
            choice = choices[0]
            content = choice["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as error:
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned an invalid response envelope",
            ) from error
        if not isinstance(value, dict) or not isinstance(choices, list) or not isinstance(choice, dict):
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned an invalid response envelope",
            )
        if not isinstance(content, str):
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned non-text content",
            )
        return cast(dict[str, Any], value)

    def _usage(self, value: object) -> TokenUsage | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned invalid usage metadata",
            )
        input_tokens = value.get("prompt_tokens")
        output_tokens = value.get("completion_tokens")
        if input_tokens is not None and (not isinstance(input_tokens, int) or isinstance(input_tokens, bool)):
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned invalid usage metadata",
            )
        if output_tokens is not None and (
            not isinstance(output_tokens, int) or isinstance(output_tokens, bool)
        ):
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned invalid usage metadata",
            )
        try:
            return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)
        except ValueError as error:
            raise self._safe_error(
                ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                "model provider returned invalid usage metadata",
            ) from error

    @staticmethod
    def _finish_reason(value: object) -> FinishReason:
        if value == "stop":
            return FinishReason.STOP
        if value == "length":
            return FinishReason.LENGTH
        if value == "content_filter":
            return FinishReason.CONTENT_FILTER
        return FinishReason.OTHER

    def _http_error(
        self, response: httpx.Response, provider_request_id: str | None
    ) -> ModelAdapterError:
        status = response.status_code
        if status in {401, 403}:
            code, message, retryable, automatic = (
                ModelErrorCode.AUTHENTICATION_FAILED,
                "model provider rejected configured credentials",
                False,
                False,
            )
        elif status == 404:
            code, message, retryable, automatic = (
                ModelErrorCode.MODEL_NOT_FOUND,
                "configured model was not found",
                False,
                False,
            )
        elif status == 413:
            code, message, retryable, automatic = (
                ModelErrorCode.CONTEXT_LIMIT,
                "model provider rejected the request size",
                False,
                False,
            )
        elif status == 429:
            code, message, retryable, automatic = (
                ModelErrorCode.RATE_LIMITED,
                "model provider rate limited the request",
                True,
                True,
            )
        elif status in {502, 503, 504}:
            code, message, retryable, automatic = (
                ModelErrorCode.PROVIDER_UNAVAILABLE,
                "model provider is temporarily unavailable",
                True,
                True,
            )
        elif status >= 500:
            code, message, retryable, automatic = (
                ModelErrorCode.PROVIDER_UNAVAILABLE,
                "model provider failed the request",
                True,
                False,
            )
        else:
            code, message, retryable, automatic = (
                ModelErrorCode.UNSUPPORTED_OPTION,
                "model provider rejected the request",
                False,
                False,
            )
        retry_after = self.parse_retry_after(response.headers.get("retry-after")) if status == 429 else None
        return self._safe_error(
            code,
            message,
            retryable=retryable,
            retry_after_seconds=retry_after,
            provider_request_id=provider_request_id,
            automatic_retry_allowed=automatic,
            outcome_known=True,
        )

    def parse_retry_after(self, value: str | None) -> float | None:
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return None
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            seconds = (parsed - self._now()).total_seconds()
        return max(0.0, seconds)

    @staticmethod
    def _safe_error(
        code: ModelErrorCode,
        message: str,
        *,
        retryable: bool = False,
        retry_after_seconds: float | None = None,
        provider_request_id: str | None = None,
        automatic_retry_allowed: bool = False,
        outcome_known: bool = True,
    ) -> ModelAdapterError:
        return ModelAdapterError(
            code=code,
            message=message,
            retryable=retryable,
            retry_after_seconds=retry_after_seconds,
            provider_request_id=provider_request_id,
            automatic_retry_allowed=automatic_retry_allowed,
            outcome_known=outcome_known,
        )


# Transitional import compatibility; this is the same typed v1 adapter, not a second gateway.
OpenAICompatibleModelGateway = OpenAICompatibleModelAdapter
