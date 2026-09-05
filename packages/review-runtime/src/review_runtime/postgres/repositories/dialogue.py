from __future__ import annotations

from typing import Any, cast

from sqlalchemy import update

from review_runtime.postgres.models import DialogueTurn, FindingDialogue, HumanDecision
from review_runtime.postgres.repositories.base import NamespaceRepository


class DialogueRepository(NamespaceRepository):
    async def append_turn(self, dialogue_id: str, expected_revision: int, turn: DialogueTurn) -> bool:
        result = await self.session.execute(
            update(FindingDialogue)
            .where(
                FindingDialogue.organization_id == self.organization_id,
                FindingDialogue.workspace_id == self.workspace_id,
                FindingDialogue.id == dialogue_id,
                FindingDialogue.revision == expected_revision,
            )
            .values(revision=FindingDialogue.revision + 1)
        )
        if cast(Any, result).rowcount != 1:
            return False
        await self.add(turn)
        return True

    async def record_decision(self, decision: HumanDecision) -> HumanDecision:
        await self.add(decision)
        return decision
