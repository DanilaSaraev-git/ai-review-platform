from __future__ import annotations

from review_core.ports.models import (
    FinishReason,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    ModelCapabilities,
    ModelProfileSnapshot,
)
from review_runtime.composition import AsyncFixtureModelAdapter, compose_model_runtime
from review_runtime.config.model_profiles import ModelProfile, profile_config_digest

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion


def _result(request: GenerationRequest) -> GenerationResult:
    return GenerationResult(
        request_id=request.request_id,
        text="fixture response",
        provider="fixture",
        model="fixture",
        model_version="1",
        finish_reason=FinishReason.STOP,
        usage=None,
        provider_request_id=None,
        latency_ms=0,
        safe_parameters={},
    )


def _request(profile: ModelProfile) -> GenerationRequest:
    return GenerationRequest(
        request_id="composition-1",
        purpose=GenerationPurpose.REVIEW,
        work_item_id="whole-document",
        trusted_instructions="Trusted.",
        untrusted_input="Data.",
        response_schema={"type": "object"},
        model_profile=ModelProfileSnapshot(
            id=profile.id,
            version=profile.version,
            config_sha256=profile_config_digest(profile),
        ),
        max_output_tokens=32,
        timeout_seconds=5,
    )


async def test_offline_composition_creates_no_network_client_and_wraps_fixture_async() -> None:
    fixture = AsyncFixtureModelAdapter(
        handler=_result,
        declared_capabilities=ModelCapabilities(
            text_generation=True,
            vision=False,
            native_structured_output=False,
            max_context_tokens=None,
            supported_parameters=frozenset(),
        ),
    )
    runtime = compose_model_runtime(fixture=fixture)

    assert not runtime.network_enabled
    async with runtime as adapter:
        assert (await adapter.generate(_request(_deterministic_profile()))).text == "fixture response"


async def test_http_composition_reuses_one_explicitly_owned_client() -> None:
    provider = FakeModelProvider(
        [ScriptedReply(chat_completion("first")), ScriptedReply(chat_completion("second"))]
    )
    profile = _http_profile()
    runtime = compose_model_runtime(profile=profile, transport=provider.transport, max_response_bytes=4096)

    assert runtime.network_enabled
    async with runtime as adapter:
        first = await adapter.generate(_request(profile))
        second = await adapter.generate(_request(profile))

    assert (first.text, second.text) == ("first", "second")
    assert provider.call_count == 2


def _deterministic_profile() -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "id": "fixture",
            "version": "1.0.0",
            "adapter_kind": "deterministic",
            "provider": "fixture",
            "model": "fixture",
            "capabilities": ["text_generation"],
            "context_window_tokens": 1000,
            "max_input_utf8_bytes": 2000,
            "max_output_tokens": 128,
        }
    )


def _http_profile() -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "id": "synthetic-http",
            "version": "1.0.0",
            "adapter_kind": "openai_compatible",
            "provider": "synthetic",
            "model": "synthetic-model",
            "chat_url": "http://model.invalid/exact/chat",
            "capabilities": ["text_generation"],
            "context_window_tokens": 1000,
            "max_input_utf8_bytes": 2000,
            "max_output_tokens": 128,
            "supported_parameters": ["max_tokens"],
        }
    )
