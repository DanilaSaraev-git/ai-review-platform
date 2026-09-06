from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import anyio
import httpx
from review_core.application.platform import ReviewPlatform
from review_runtime.composition import compose_model_runtime
from review_runtime.config.model_profiles import load_model_profiles
from review_runtime.config.settings import OperatorSettings
from review_runtime.config.verify import verify
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.ml_runtime import LLMReviewRuntime
from review_runtime.models.config import FileSecretProvider
from review_runtime.multi_model_runtime import LLMReviewRouter
from review_runtime.postgres.platform import PostgresReviewPlatform
from review_runtime.skills.registry import SkillRegistry


def build_components(
    composition: str = "fixture",
    *,
    model_transport: httpx.AsyncBaseTransport | None = None,
) -> tuple[Any, LLMReviewRuntime | LLMReviewRouter | None]:
    root = Path(__file__).resolve().parents[4]
    selected = os.environ.get("REVIEW_COMPOSITION", composition)
    if selected in {"durable", "ml", "unconfigured"}:
        settings = OperatorSettings()  # type: ignore[call-arg]
        policy = verify(settings.runtime_config_path)
        if selected == "unconfigured":
            platform = PostgresReviewPlatform(
                None,
                settings,
                runtime_policy=policy,
                semantic_execution_available=False,
                composition="unconfigured",
            )
            return platform, None
        if selected == "durable":
            if settings.expected_output_path is None:
                raise ValueError("durable fixture composition requires expected output path")
            executor = TrustedFixtureReviewExecutor(
                root,
                runtime_config_path=settings.runtime_config_path,
                expected_output_path=settings.expected_output_path,
            )
            platform = PostgresReviewPlatform(
                executor, settings, runtime_policy=policy, composition="durable"
            )
            return platform, None
        if settings.model_profile_path is None or settings.skill_package_path is None:
            raise ValueError("ML composition requires model profile and skill package paths")
        profiles = load_model_profiles(settings.model_profile_path)
        if any(profile.adapter_kind != "openai_compatible" for profile in profiles):
            raise ValueError("ML composition requires external model profiles")
        if (
            any(profile.secret_ref is not None for profile in profiles)
            and settings.model_credential_path is None
        ):
            raise ValueError("ML composition requires a mounted credential file")
        skill = SkillRegistry(
            root / "contracts/review-platform/v1/schemas/skill-manifest.schema.json",
            engine_version="0.1.0",
            model_capabilities=frozenset.intersection(
                *(frozenset(profile.capabilities) for profile in profiles)
            ),
        ).resolve(settings.skill_package_path)
        platform = PostgresReviewPlatform(
            None,
            settings,
            model_profiles=profiles,
            resolved_skill=skill,
            runtime_policy=policy,
            composition="ml",
        )
        semaphore = anyio.Semaphore(policy.budgets.max_parallel_model_calls)
        runtimes = []
        for profile in profiles:
            secrets = None
            if profile.secret_ref is not None and settings.model_credential_path is not None:
                secrets = FileSecretProvider(profile.secret_ref, settings.model_credential_path)
            model_runtime = compose_model_runtime(
                profile=profile,
                secrets=secrets,
                max_response_bytes=settings.model_max_response_bytes,
                transport=model_transport,
            )
            runtimes.append(
                LLMReviewRuntime(
                    platform=platform,
                    model_runtime=model_runtime,
                    model_profile=profile,
                    skill=skill,
                    root=root,
                    model_call_semaphore=semaphore,
                )
            )
        return platform, runtimes[0] if len(runtimes) == 1 else LLMReviewRouter(platform, tuple(runtimes))
    if selected in {"fixture", "real"}:
        executor = TrustedFixtureReviewExecutor(root)
        return ReviewPlatform(executor), None
    raise ValueError(f"unsupported review composition: {selected}")


def build_platform(composition: str = "fixture") -> Any:
    return build_components(composition)[0]
