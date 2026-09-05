from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from review_core.canonical import digest_value
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from review_runtime.config.settings import OperatorSettings
from review_runtime.postgres.models import (
    Actor,
    Deployment,
    DialoguePolicyVersion,
    ModelProfileAvailability,
    ModelProfileVersion,
    Organization,
    ReviewProfileFamily,
    ReviewProfileHead,
    ReviewProfileVersion,
    SkillVersion,
    Workspace,
)

CODEC = "jcs-rfc8785-0.1.4"


async def seed_runtime(session: AsyncSession, settings: OperatorSettings) -> dict[str, str]:
    """Insert the complete immutable release seed, or validate the existing exact seed."""
    now = datetime.now(UTC)
    values: list[Any] = [
        Deployment(id=str(settings.deployment_id), release_version="0.1.0", created_at=now),
        Organization(id=str(settings.organization_id), name=settings.organization_name),
        Workspace(
            organization_id=str(settings.organization_id),
            id=str(settings.workspace_id),
            name=settings.workspace_name,
        ),
        Actor(
            organization_id=str(settings.organization_id),
            workspace_id=str(settings.workspace_id),
            id=str(settings.actor_id),
            display_name=settings.actor_display_name,
        ),
    ]
    for row in values:
        if await session.get(type(row), tuple(row.__mapper__.primary_key_from_instance(row))) is None:
            session.add(row)
    family = (
        await session.execute(
            select(ReviewProfileFamily).where(ReviewProfileFamily.public_id == settings.system_profile_id)
        )
    ).scalar_one_or_none()
    if family is None:
        family = ReviewProfileFamily(
            row_id=str(settings.deployment_id),
            organization_id=None,
            workspace_id=None,
            deployment_id=str(settings.deployment_id),
            public_id=settings.system_profile_id,
            scope="system",
            created_at=now,
        )
        session.add(family)
        await session.flush()
        semantic = {
            "name": "Base data specification review",
            "role": "Analyst with developer and tester viewpoints",
            "goal": "Find ambiguity before implementation",
            "checks": ["Sources and fields", "Transformations and schedules"],
        }
        version = ReviewProfileVersion(
            family_row_id=family.row_id,
            version="1.0.0",
            semantic_digest=digest_value(semantic),
            semantic_codec_id=CODEC,
            name=semantic["name"],
            role=semantic["role"],
            goal=semantic["goal"],
            checks=semantic["checks"],
            supersedes_version=None,
            created_at=now,
        )
        session.add(version)
        await session.flush()
        session.add(ReviewProfileHead(family_row_id=family.row_id, head_version="1.0.0", revision=0))
        await session.flush()
    configs = (
        (
            ModelProfileVersion,
            settings.model_profile_id,
            {"adapter_kind": "deterministic", "capabilities": ["text_generation"]},
        ),
        (SkillVersion, settings.skill_id, {"package_sha256": settings.skill_package_sha256}),
        (
            DialoguePolicyVersion,
            settings.dialogue_policy_id,
            {"max_member_turns": None},
        ),
    )
    for model, config_id, payload in configs:
        if await session.get(model, (config_id, "1.0.0")) is None:
            session.add(
                model(
                    id=config_id,
                    version="1.0.0",
                    digest=digest_value(payload),
                    codec_id=CODEC,
                    payload=payload,
                    created_at=now,
                )
            )
    availability_key = (str(settings.deployment_id), settings.model_profile_id, "1.0.0")
    if await session.get(ModelProfileAvailability, availability_key) is None:
        session.add(
            ModelProfileAvailability(
                deployment_id=str(settings.deployment_id),
                model_profile_id=settings.model_profile_id,
                model_profile_version="1.0.0",
                state="available",
                reason_code=None,
                checked_at=now,
                expires_at=now + timedelta(days=3650),
                revision=0,
            )
        )
    await session.flush()
    return {
        "deployment_id": str(settings.deployment_id),
        "organization_id": str(settings.organization_id),
        "workspace_id": str(settings.workspace_id),
        "actor_id": str(settings.actor_id),
    }


async def check_runtime_seed(session: AsyncSession, settings: OperatorSettings) -> bool:
    expected = (
        (Deployment, str(settings.deployment_id)),
        (Organization, str(settings.organization_id)),
        (Workspace, (str(settings.organization_id), str(settings.workspace_id))),
        (
            Actor,
            (str(settings.organization_id), str(settings.workspace_id), str(settings.actor_id)),
        ),
        (ModelProfileVersion, (settings.model_profile_id, "1.0.0")),
        (SkillVersion, (settings.skill_id, "1.0.0")),
        (DialoguePolicyVersion, (settings.dialogue_policy_id, "1.0.0")),
    )
    for model, key in expected:
        if await session.get(model, key) is None:
            return False
    return True
