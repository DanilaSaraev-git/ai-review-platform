from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from review_runtime.config.model_profiles import ModelProfile
from review_runtime.models.availability import (
    AvailabilityService,
    CompatibilityResult,
    ProbeRequest,
    ProbeResponse,
    generation_observation,
    manual_observation,
)


def _profile(*, probe: dict[str, object] | None) -> ModelProfile:
    return ModelProfile.model_validate(
        {
            "schema_version": "model-profile.v1",
            "id": "synthetic-http",
            "version": "1.0.0",
            "adapter_kind": "openai_compatible",
            "provider": "synthetic",
            "model": "synthetic-model",
            "checkpoint": None,
            "chat_url": "http://127.0.0.1:9999/chat/completions",
            "secret_ref": None,
            "capabilities": ["text_generation"],
            "context_window_tokens": 8192,
            "max_input_utf8_bytes": 12000,
            "max_output_tokens": 1024,
            "structured_output": "plain_json",
            "supported_parameters": ["max_tokens"],
            "request_options": {},
            "probe": probe,
        }
    )


class RecordingProbe:
    def __init__(self, response: ProbeResponse) -> None:
        self.response = response
        self.requests: list[ProbeRequest] = []

    async def observe(self, request: ProbeRequest) -> ProbeResponse:
        self.requests.append(request)
        return self.response


async def test_explicit_models_probe_is_non_generative_and_profile_driven() -> None:
    now = datetime(2026, 9, 5, 12, tzinfo=UTC)
    profile = _profile(
        probe={
            "mode": "models",
            "url": "http://127.0.0.1:9999/models",
            "timeout_seconds": 5,
            "success_ttl_seconds": 300,
        }
    )
    transport = RecordingProbe(
        ProbeResponse(status_code=200, json_value={"data": [{"id": "synthetic-model"}]})
    )

    observation = await AvailabilityService().refresh(profile, transport, now=now)

    assert transport.requests == [
        ProbeRequest(
            mode="models",
            url="http://127.0.0.1:9999/models",
            model="synthetic-model",
            secret_ref=None,
            timeout_seconds=5,
        )
    ]
    assert observation.state == "available"
    assert observation.source == "probe"
    assert observation.expires_at == now + timedelta(seconds=300)
    assert observation.is_fresh(now=now)


async def test_missing_probe_never_falls_back_to_generation_or_guessed_endpoint() -> None:
    transport = RecordingProbe(ProbeResponse(status_code=200))
    with pytest.raises(ValueError, match="does not declare"):
        await AvailabilityService().refresh(_profile(probe=None), transport)
    assert transport.requests == []


async def test_models_probe_does_not_guess_availability_from_a_healthy_response() -> None:
    profile = _profile(
        probe={
            "mode": "models",
            "url": "http://127.0.0.1:9999/models",
            "timeout_seconds": 5,
            "success_ttl_seconds": 300,
        }
    )
    transport = RecordingProbe(
        ProbeResponse(status_code=200, json_value={"data": [{"id": "another-model"}]})
    )

    observation = await AvailabilityService().refresh(profile, transport)

    assert observation.state == "unavailable"
    assert observation.reason_code == "model_not_found"


def test_manual_observation_has_explicit_expiry_and_expired_is_unavailable() -> None:
    checked = datetime(2026, 9, 5, 12, tzinfo=UTC)
    observation = manual_observation(
        _profile(probe=None),
        state="available",
        reason_code="operator_confirmed",
        checked_at=checked,
        expires_at=checked + timedelta(seconds=30),
    )

    assert observation.public_state(now=checked + timedelta(seconds=29)) == "available"
    assert observation.public_state(now=checked + timedelta(seconds=30)) == "unavailable"
    with pytest.raises(ValueError, match="after checked_at"):
        manual_observation(
            _profile(probe=None),
            state="available",
            reason_code=None,
            checked_at=checked,
            expires_at=checked,
        )


def test_generation_outcomes_update_availability_without_claiming_compatibility() -> None:
    now = datetime(2026, 9, 5, 12, tzinfo=UTC)
    profile = _profile(probe=None)

    success = generation_observation(profile, outcome="success", now=now)
    auth = generation_observation(profile, outcome="authentication_failed", now=now)
    rate = generation_observation(profile, outcome="rate_limited", now=now, retry_after_seconds=7)

    assert (success.state, success.expires_at) == ("available", now + timedelta(seconds=300))
    assert (auth.state, auth.reason_code) == ("unavailable", "authentication_failed")
    assert (rate.state, rate.expires_at) == ("degraded", now + timedelta(seconds=7))


def test_compatibility_is_an_exact_separate_tuple_and_defaults_unverified() -> None:
    result = CompatibilityResult.unverified(
        profile_digest="a" * 64,
        skill_digest="b" * 64,
        engine_version="0.1.0",
        backend_version="d07dc4d",
        suite_version="ml-contract-v1",
    )

    assert result.status == "unverified"
    assert result.key == (
        "a" * 64,
        "b" * 64,
        "0.1.0",
        "d07dc4d",
        "ml-contract-v1",
    )
    assert not hasattr(generation_observation(_profile(probe=None), outcome="success"), "compatibility")
