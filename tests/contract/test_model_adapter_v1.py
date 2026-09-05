from __future__ import annotations

import httpx
import pytest
from review_core.ports.models import (
    GenerationPurpose,
    GenerationRequest,
    ModelAdapter,
    ModelAdapterError,
    ModelErrorCode,
    ModelProfileSnapshot,
)
from review_runtime.config.model_profiles import ModelProfile, profile_config_digest
from review_runtime.models.openai_compatible import OpenAICompatibleModelAdapter

from tests.integration.fake_model_provider import FakeModelProvider, ScriptedReply, chat_completion


def _profile() -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "id": "contract-http",
            "version": "1.0.0",
            "adapter_kind": "openai_compatible",
            "provider": "synthetic-provider",
            "model": "synthetic-model",
            "chat_url": "http://model.invalid/exact/chat",
            "capabilities": ["text_generation"],
            "context_window_tokens": 2048,
            "max_input_utf8_bytes": 4000,
            "max_output_tokens": 512,
            "supported_parameters": ["max_tokens"],
        }
    )


def _request(profile: ModelProfile) -> GenerationRequest:
    return GenerationRequest(
        request_id="contract-attempt-1",
        purpose=GenerationPurpose.REVIEW,
        work_item_id="whole-document",
        trusted_instructions="Trusted contract instructions.",
        untrusted_input="Synthetic data.",
        response_schema={"type": "object"},
        model_profile=ModelProfileSnapshot(
            id=profile.id,
            version=profile.version,
            config_sha256=profile_config_digest(profile),
        ),
        max_output_tokens=128,
        timeout_seconds=10,
    )


async def test_openai_compatible_adapter_satisfies_typed_v1_port_and_preserves_raw_text() -> None:
    provider = FakeModelProvider([ScriptedReply(chat_completion("not parsed JSON"))])
    profile = _profile()
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(profile=profile, client=client, max_response_bytes=4096)
        assert isinstance(adapter, ModelAdapter)
        result = await adapter.generate(_request(profile))

    assert result.request_id == "contract-attempt-1"
    assert result.text == "not parsed JSON"
    assert provider.call_count == 1


async def test_profile_snapshot_mismatch_is_rejected_without_transport() -> None:
    provider = FakeModelProvider([])
    profile = _profile()
    mismatched = _request(profile)
    object.__setattr__(
        mismatched,
        "model_profile",
        ModelProfileSnapshot(id=profile.id, version=profile.version, config_sha256="f" * 64),
    )
    async with httpx.AsyncClient(transport=provider.transport) as client:
        adapter = OpenAICompatibleModelAdapter(profile=profile, client=client, max_response_bytes=4096)
        with pytest.raises(ModelAdapterError) as caught:
            await adapter.generate(mismatched)

    assert caught.value.code is ModelErrorCode.UNSUPPORTED_OPTION
    assert provider.call_count == 0
