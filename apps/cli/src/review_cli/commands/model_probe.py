from __future__ import annotations

import json
import os
from pathlib import Path

import anyio
import httpx
import psycopg
import typer
from review_runtime.config.model_profiles import ModelProfile
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
    """Refresh the selected model's persisted availability without generating text."""
    try:
        observation = anyio.run(probe_configured_model)
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
    result = {
        "status": "available" if observation.public_state() == "available" else "unavailable",
        "profile": {"id": observation.profile_id, "version": observation.profile_version},
        "reason_code": observation.reason_code,
        "checked_at": observation.checked_at.isoformat(),
        "expires_at": observation.expires_at.isoformat(),
    }
    typer.echo(json.dumps(result, sort_keys=True))
    if observation.public_state() != "available":
        raise typer.Exit(2)


async def probe_configured_model(
    *,
    settings: OperatorSettings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AvailabilityObservation:
    if os.environ.get("REVIEW_COMPOSITION") != "ml":
        raise ValueError("model probe requires the ML composition")
    configured = settings or OperatorSettings()  # type: ignore[call-arg]
    if configured.model_profile_path is None or configured.skill_package_path is None:
        raise ValueError("model profile and skill package are required")
    profile = ModelProfile.model_validate(
        json.loads(configured.model_profile_path.read_text(encoding="utf-8"))
    )
    if profile.adapter_kind != "openai_compatible" or profile.id != configured.model_profile_id:
        raise ValueError("selected model profile does not match the configured external profile")
    root = Path(__file__).resolve().parents[5]
    skill = SkillRegistry(
        root / "contracts/review-platform/v1/schemas/skill-manifest.schema.json",
        engine_version="0.1.0",
        model_capabilities=frozenset(profile.capabilities),
    ).resolve(configured.skill_package_path)
    platform = PostgresReviewPlatform(
        None,
        configured,
        model_profiles=(profile,),
        resolved_skill=skill,
        runtime_policy=verify(configured.runtime_config_path),
        composition="ml",
    )
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
        lambda: platform.observe_model_profile(
            {"id": profile.id, "version": profile.version},
            state=observation.state,
            reason_code=observation.reason_code,
            expires_at=observation.expires_at,
        )
    )
    return observation
