from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from review_runtime.postgres.models import (
    DialoguePolicyVersion,
    ModelProfileVersion,
    ReviewProfileFamily,
    ReviewProfileHead,
    ReviewProfileVersion,
    SkillVersion,
)


class ConfigurationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def effective_profile_heads(
        self, organization_id: str, workspace_id: str
    ) -> list[ReviewProfileVersion]:
        statement = (
            select(ReviewProfileVersion)
            .join(ReviewProfileHead)
            .join(ReviewProfileFamily)
            .where(
                (ReviewProfileFamily.scope == "system")
                | (
                    (ReviewProfileFamily.organization_id == organization_id)
                    & (ReviewProfileFamily.workspace_id == workspace_id)
                )
            )
            .order_by(ReviewProfileFamily.scope, ReviewProfileFamily.public_id)
        )
        return list((await self.session.scalars(statement)).all())

    async def exact_config(self, model: str, config_id: str, version: str):  # type: ignore[no-untyped-def]
        types = {
            "model": ModelProfileVersion,
            "skill": SkillVersion,
            "dialogue_policy": DialoguePolicyVersion,
        }
        return await self.session.get(types[model], (config_id, version))
