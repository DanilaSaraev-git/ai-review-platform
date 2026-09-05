from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest
from review_core.ports.models import (
    FinishReason,
    GenerationPurpose,
    GenerationRequest,
    ModelAdapterError,
    ModelErrorCode,
    ModelProfileSnapshot,
)
from review_runtime.config.model_profiles import ModelProfile, profile_config_digest
from review_runtime.models.config import SecretProvider
from review_runtime.models.openai_compatible import OpenAICompatibleModelAdapter

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion


class StaticSecrets(SecretProvider):
    def __init__(self, value: str = "synthetic-secret") -> None:
        self.value = value

    def resolve(self, reference: str) -> str:
        assert reference == "REVIEW_SYNTHETIC_TOKEN"
        return self.value


def profile(**overrides: object) -> ModelProfile:
    value: dict[str, object] = {
        "schema_version": "model-profile.v1",
        "id": "synthetic-http",
        "version": "1.0.0",
        "adapter_kind": "openai_compatible",
        "provider": "synthetic-provider",
        "model": "synthetic-model",
        "checkpoint": None,
        "chat_url": "http://model.invalid/exact/chat",
        "secret_ref": "REVIEW_SYNTHETIC_TOKEN",
        "capabilities": ["text_generation"],
        "context_window_tokens": 8192,
        "max_input_utf8_bytes": 12000,
        "max_output_tokens": 1024,
        "structured_output": "plain_json",
        "supported_parameters": ["max_tokens"],
        "request_options": {},
        "probe": None,
    }
    value.update(overrides)
    return ModelProfile.model_validate(value)


def request(model_profile: ModelProfile, **overrides: object) -> GenerationRequest:
    value: dict[str, object] = {
        "request_id": "attempt-1",
        "purpose": GenerationPurpose.REVIEW,
        "work_item_id": "whole-document",
        "trusted_instructions": "Trusted synthetic instructions.",
        "untrusted_input": "Untrusted synthetic document text.",
        "response_schema": {"type": "object", "required": ["findings"]},
        "model_profile": ModelProfileSnapshot(
            id=model_profile.id,
            version=model_profile.version,
            config_sha256=profile_config_digest(model_profile),
        ),
        "max_output_tokens": 512,
        "timeout_seconds": 12.5,
        "temperature": None,
    }
    value.update(overrides)
    return GenerationRequest(**value)  # type: ignore[arg-type]


async def test_one_exact_post_returns_raw_text_and_honest_metadata() -> None:
    provider = FakeModelProvider(
        [
            ScriptedReply(
                chat_completion(
                    "not-json-and-not-parsed-by-adapter",
                    model="actual-provider-model",
                    finish_reason="stop",
                    usage={"prompt_tokens": 23, "completion_tokens": 7},
                    headers={"x-request-id": "provider-request-1", "x-model-version": "checkpoint-7"},
                )
            )
        ]
    )
    model_profile = profile()
    async with httpx.AsyncClient(transport=provider.transport, follow_redirects=False) as client:
        adapter = OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=4096,
            monotonic_ms=lambda: 100,
        )
        result = await adapter.generate(request(model_profile))

    assert provider.call_count == 1
    sent = provider.requests[0]
    assert str(sent.url) == "http://model.invalid/exact/chat"
    assert sent.headers["authorization"] == "Bearer synthetic-secret"
    assert json.loads(sent.content) == {
        "model": "synthetic-model",
        "messages": [
            {"role": "system", "content": "Trusted synthetic instructions."},
            {"role": "user", "content": "Untrusted synthetic document text."},
        ],
        "max_tokens": 512,
    }
    assert result.text == "not-json-and-not-parsed-by-adapter"
    assert result.model == "actual-provider-model"
    assert result.model_version == "checkpoint-7"
    assert result.provider_request_id == "provider-request-1"
    assert result.finish_reason is FinishReason.STOP
    assert result.usage is not None
    assert (result.usage.input_tokens, result.usage.output_tokens) == (23, 7)
    assert result.safe_parameters == {"max_tokens": 512, "structured_output": "plain_json"}


async def test_native_schema_and_nullable_parameters_are_profile_gated() -> None:
    provider = FakeModelProvider([ScriptedReply(chat_completion("{}"))])
    model_profile = profile(
        capabilities=["text_generation", "native_structured_output"],
        structured_output="native_json_schema",
        supported_parameters=["max_tokens", "temperature", "seed"],
        request_options={"seed": 11},
    )
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=4096,
        )
        await adapter.generate(request(model_profile, temperature=0.25))

    payload = json.loads(provider.requests[0].content)
    assert payload["temperature"] == 0.25
    assert payload["seed"] == 11
    assert payload["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "review_response",
            "strict": True,
            "schema": {"type": "object", "required": ["findings"]},
        },
    }
    assert all(value is not None for value in payload.values())


async def test_adapter_rejects_unsupported_option_before_network() -> None:
    provider = FakeModelProvider([])
    model_profile = profile()
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=4096,
        )
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.generate(request(model_profile, temperature=0.2))

    assert caught.value.code is ModelErrorCode.UNSUPPORTED_OPTION
    assert provider.call_count == 0


@pytest.mark.parametrize(
    ("status", "code", "retryable", "automatic"),
    [
        (401, ModelErrorCode.AUTHENTICATION_FAILED, False, False),
        (404, ModelErrorCode.MODEL_NOT_FOUND, False, False),
        (413, ModelErrorCode.CONTEXT_LIMIT, False, False),
        (429, ModelErrorCode.RATE_LIMITED, True, True),
        (502, ModelErrorCode.PROVIDER_UNAVAILABLE, True, True),
        (503, ModelErrorCode.PROVIDER_UNAVAILABLE, True, True),
        (504, ModelErrorCode.PROVIDER_UNAVAILABLE, True, True),
        (500, ModelErrorCode.PROVIDER_UNAVAILABLE, True, False),
    ],
)
async def test_http_errors_are_safe_typed_and_never_retried_inside_adapter(
    status: int,
    code: ModelErrorCode,
    retryable: bool,
    automatic: bool,
) -> None:
    first = httpx.Response(
        status,
        text="raw provider body with synthetic-secret",
        headers={"retry-after": "3", "x-request-id": "provider-error-1"},
    )
    provider = FakeModelProvider([ScriptedReply(first), ScriptedReply(chat_completion("{}"))])
    model_profile = profile()
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=4096,
        )
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.generate(request(model_profile))

    error = caught.value
    assert provider.call_count == 1
    assert (error.code, error.retryable, error.automatic_retry_allowed) == (code, retryable, automatic)
    assert error.retry_after_seconds == (3 if status == 429 else None)
    assert error.provider_request_id == "provider-error-1"
    assert error.outcome_known is True
    assert "synthetic-secret" not in str(error)


@pytest.mark.parametrize(
    ("transport_error", "code", "automatic", "outcome_known"),
    [
        (httpx.ConnectError, ModelErrorCode.PROVIDER_UNAVAILABLE, True, True),
        (httpx.ReadTimeout, ModelErrorCode.TIMEOUT, False, False),
    ],
)
async def test_transport_errors_distinguish_pre_send_from_ambiguous_timeout(
    transport_error: type[httpx.TransportError],
    code: ModelErrorCode,
    automatic: bool,
    outcome_known: bool,
) -> None:
    provider = FakeModelProvider([ScriptedReply(transport_error)])
    model_profile = profile()
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=4096,
        )
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.generate(request(model_profile))

    assert caught.value.code is code
    assert caught.value.automatic_retry_allowed is automatic
    assert caught.value.outcome_known is outcome_known


async def test_response_bytes_are_bounded_before_provider_envelope_is_accepted() -> None:
    provider = FakeModelProvider([ScriptedReply(chat_completion("x" * 300))])
    model_profile = profile()
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=64,
        )
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.generate(request(model_profile))

    assert caught.value.code is ModelErrorCode.INVALID_PROVIDER_RESPONSE


async def test_capabilities_are_declared_by_profile_without_network_probe() -> None:
    provider = FakeModelProvider([])
    model_profile = profile(capabilities=["text_generation", "vision"])
    async with httpx.AsyncClient(transport=provider.transport) as client:
        capabilities = await OpenAICompatibleModelAdapter(
            profile=model_profile,
            client=client,
            secrets=StaticSecrets(),
            max_response_bytes=4096,
        ).capabilities()

    assert capabilities.text_generation
    assert capabilities.vision
    assert not capabilities.native_structured_output
    assert capabilities.max_context_tokens == 8192
    assert capabilities.supported_parameters == frozenset({"max_tokens"})
    assert provider.call_count == 0


def test_retry_after_http_date_is_normalized_against_injected_clock() -> None:
    model_profile = profile()
    adapter = OpenAICompatibleModelAdapter(
        profile=model_profile,
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(500))),
        secrets=StaticSecrets(),
        max_response_bytes=4096,
        now=lambda: datetime(2026, 9, 5, 12, tzinfo=UTC),
    )
    assert adapter.parse_retry_after("Sat, 05 Sep 2026 12:00:07 GMT") == 7
