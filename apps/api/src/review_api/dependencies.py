from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import httpx
from review_core.application.platform import ReviewPlatform
from review_runtime.composition import compose_model_runtime
from review_runtime.config.model_profiles import ModelProfile
from review_runtime.config.settings import OperatorSettings
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.ml_runtime import LLMReviewRuntime
from review_runtime.models.config import FileSecretProvider
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.skills.registry import SkillRegistry


def build_components(
    composition: str = "fixture",
    *,
    model_transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[Any, LLMReviewRuntime | None]:
    root = Path(__file__).resolve().parents[4]
    selected = os.environ.get("REVIEW_COMPOSITION", composition)
    if selected in {"durable", "ml"}:
        settings = OperatorSettings()  # type: ignore[call-arg]
        executor = TrustedFixtureReviewExecutor(
            root,
            runtime_config_path=settings.runtime_config_path,
            expected_output_path=settings.expected_output_path,
        )
        if selected == "durable":
            return PostgresReviewPlatform(executor, settings), None
        if settings.model_profile_path is None or settings.skill_package_path is None:
            raise ValueError("ML composition requires model profile and skill package paths")
        profile = ModelProfile.model_validate(
            json.loads(settings.model_profile_path.read_text(encoding="utf-8"))
        )
        skill = SkillRegistry(
            root / "contracts/review-platform/v1/schemas/skill-manifest.schema.json",
            engine_version="0.1.0",
            model_capabilities=frozenset(profile.capabilities),
        ).resolve(settings.skill_package_path)
        platform = PostgresReviewPlatform(
            executor,
            settings,
            model_profiles=(profile,),
            resolved_skill=skill,
        )
        secrets = None
        if profile.secret_ref is not None:
            if settings.model_credential_path is None:
                raise ValueError("ML composition requires a mounted credential file")
            secrets = FileSecretProvider(profile.secret_ref, settings.model_credential_path)
        model_runtime = compose_model_runtime(
            profile=profile,
            secrets=secrets,
            max_response_bytes=settings.model_max_response_bytes,
            transport=model_transport,
        )
        runtime = LLMReviewRuntime(
            platform=platform,
            model_runtime=model_runtime,
            model_profile=profile,
            skill=skill,
            root=root,
        )
        return platform, runtime
    executor = TrustedFixtureReviewExecutor(root)
    return ReviewPlatform(executor), None


def build_platform(composition: str = "fixture") -> Any:
    return build_components(composition)[0]
