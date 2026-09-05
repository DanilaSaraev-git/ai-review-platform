from __future__ import annotations

from review_runtime.postgres.models import (
    Artifact,
    DocumentExtraction,
    DocumentVersion,
    Fragment,
    SourceDiagnostic,
)
from review_runtime.postgres.repositories.base import NamespaceRepository


class DocumentRepository(NamespaceRepository):
    async def document(self, document_id: str) -> DocumentVersion | None:
        return await self.get(DocumentVersion, document_id)

    async def add_document(
        self, artifact: Artifact, document: DocumentVersion, extraction: DocumentExtraction
    ) -> None:
        await self.add(artifact)
        await self.add(document)
        await self.add(extraction)

    async def fragments(self, document_id: str) -> list[Fragment]:
        statement = (
            self.scoped(Fragment).where(Fragment.document_id == document_id).order_by(Fragment.ordinal)
        )
        return list((await self.session.scalars(statement)).all())

    async def diagnostics(self, extraction_id: str) -> list[SourceDiagnostic]:
        statement = (
            self.scoped(SourceDiagnostic)
            .where(SourceDiagnostic.extraction_id == extraction_id)
            .order_by(SourceDiagnostic.ordinal)
        )
        return list((await self.session.scalars(statement)).all())

    async def page(self, *, limit: int, before: tuple[str, str] | None = None) -> list[DocumentVersion]:
        statement = self.scoped(DocumentVersion)
        if before is not None:
            statement = statement.where(
                (DocumentVersion.created_at < before[0])
                | ((DocumentVersion.created_at == before[0]) & (DocumentVersion.id < before[1]))
            )
        return list(
            (
                await self.session.scalars(
                    statement.order_by(DocumentVersion.created_at.desc(), DocumentVersion.id.desc()).limit(
                        limit
                    )
                )
            ).all()
        )
