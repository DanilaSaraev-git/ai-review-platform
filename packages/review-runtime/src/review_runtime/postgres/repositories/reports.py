from __future__ import annotations

from typing import cast

from review_runtime.postgres.models import Finding, FindingDialogue, FindingState, ReviewReport
from review_runtime.postgres.repositories.base import NamespaceRepository


class ReportRepository(NamespaceRepository):
    async def publish(
        self,
        report: ReviewReport,
        findings: list[Finding],
        states: list[FindingState],
        dialogues: list[FindingDialogue],
    ) -> None:
        await self.add(report)
        for rows in (findings, states, dialogues):
            for row in rows:
                await self.add(row)

    async def report_for_run(self, run_id: str) -> ReviewReport | None:
        return cast(
            ReviewReport | None,
            await self.session.execute(self.scoped(ReviewReport).where(ReviewReport.run_id == run_id)),
        ).scalar_one_or_none()
