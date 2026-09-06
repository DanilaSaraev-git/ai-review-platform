from __future__ import annotations

import json
import os
from functools import partial
from pathlib import Path

import anyio
import httpx
import psycopg
import typer
from review_runtime.config.model_profiles import load_model_profiles
from review_runtime.config.settings import OperatorSettings
from review_runtime.config.verify import verify
from review_runtime.models.availability import (
    AvailabilityObservation,
    AvailabilityService,
    HTTPProbeTransport,
)
from review_runtime.models.config import FileSecretProvider
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.skills.registry import SkillRegistry


def model_probe() -> None:
    """Refresh configured models' persisted availability without generating text."""
    try:
        observations = anyio.run(probe_configured_models)
    except (OSError, ValueError, RuntimeError, psycopg.Error):
        typer.echo(
            json.dumps(
                {
                    "status": "failed",
                    "code": "invalid_configuration",
                    "action": "check the declared probe and mounted model files",
                },
                sort_keys=True,
            ),
            err=True,
        )
        raise typer.Exit(2) from None
    available = all(item.public_state() == "available" for item in observations)
    result = (
        _observation_value(observations[0])
        if len(observations) == 1
        else {
            "status": "available" if available else "unavailable",
            "profiles": [_observation_value(item) for item in observations],
        }
    )
    typer.echo(json.dumps(result, sort_keys=True))
    if not available:
        raise typer.Exit(2)


def _observation_value(observation: AvailabilityObservation) -> dict[str, object]:
    return {
        "status": "available" if observation.public_state() == "available" else "unavailable",
        "profile": {"id": observation.profile_id, "version": observation.profile_version},
        "reason_code": observation.reason_code,
        "checked_at": observation.checked_at.isoformat(),
        "expires_at": observation.expires_at.isoformat(),
    }


async def probe_configured_model(
    *,
    settings: OperatorSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AvailabilityObservation:
    """Compatibility entry point returning the default profile's observation."""
    configured = settings or OperatorSettings()  # type: ignore[call-arg]
    observations = await probe_configured_models(settings=configured, transport=transport)
    return next(item for item in observations if item.profile_id == configured.model_profile_id)


async def probe_configured_models(
    *,
    settings: OperatorSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[AvailabilityObservation, ...]:
    if os.environ.get("REVIEW_COMPOSITION") != "ml":
        raise ValueError("model probe requires the ML composition")
    configured = settings or OperatorSettings()  # type: ignore[call-arg]
    if configured.model_profile_path is None or configured.skill_package_path is None:
        raise ValueError("model profile and skill package are required")
    profiles = load_model_profiles(configured.model_profile_path)
    if any(profile.adapter_kind != "openai_compatible" for profile in profiles):
        raise ValueError("model probe requires external profiles")
    if configured.model_profile_id not in {profile.id for profile in profiles}:
        raise ValueError("selected model profile does not match the configured external profiles")
    capabilities = frozenset.intersection(*(frozenset(profile.capabilities) for profile in profiles))
    root = Path(__file__).resolve().parents[5]
    skill = SkillRegistry(
        root / "contracts/review-platform/v1/schemas/skill-manifest.schema.json",
        engine_version="0.1.0",
        model_capabilities=capabilities,
    ).resolve(configured.skill_package_path)
    platform = PostgresReviewPlatform(
        None,
        configured,
        model_profiles=profiles,
        resolved_skill=skill,
        runtime_policy=verify(configured.runtime_config_path),
        composition="ml",
    )
    observations = []
    for profile in profiles:
        secrets = None
        if profile.secret_ref is not None:
            if configured.model_credential_path is None:
                raise ValueError("model credential is required")
            secrets = FileSecretProvider(profile.secret_ref, configured.model_credential_path)
        observation = await AvailabilityService().refresh(
            profile,
            HTTPProbeTransport(
                secrets=secrets,
                transport=transport,
                max_response_bytes=configured.model_max_response_bytes,
            ),
        )
        await anyio.to_thread.run_sync(
            partial(
                platform.observe_model_profile,
                {"id": profile.id, "version": profile.version},
                state=observation.state,
                reason_code=observation.reason_code,
                expires_at=observation.expires_at,
            )
        )
        observations.append(observation)
    return tuple(observations)
