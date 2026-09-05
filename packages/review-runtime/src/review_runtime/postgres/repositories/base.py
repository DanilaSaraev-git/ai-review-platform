from __future__ import annotations

from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession


class NamespaceRepository:
    def __init__(self, session: AsyncSession, organization_id: str, workspace_id: str) -> None:
        self.session = session
        self.organization_id = organization_id
        self.workspace_id = workspace_id

    def scoped(self, model: type[Any]) -> Select[tuple[Any]]:
        return select(model).where(
            model.organization_id == self.organization_id,
            model.workspace_id == self.workspace_id,
        )

    async def get(self, model: type[Any], resource_id: str) -> Any | None:
        return (
            await self.session.execute(self.scoped(model).where(model.id == resource_id))
        ).scalar_one_or_none()

    async def add(self, row: Any) -> Any:
        if row.organization_id != self.organization_id or row.workspace_id != self.workspace_id:
            raise ValueError("repository namespace mismatch")
        self.session.add(row)
        await self.session.flush()
        return row
