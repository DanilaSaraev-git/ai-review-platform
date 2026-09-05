from __future__ import annotations

from typing import Any, Protocol

from review_core.ports.models import (
    FinishReason,
    GenerationPurpose,
    GenerationRequest,
    GenerationResult,
    ModelAdapter,
    ModelAdapterError,
    ModelCapabilities,
    ModelErrorCode,
    ModelProfileSnapshot,
    TokenUsage,
)

__all__ = [
    "ArtifactStore",
    "DocumentParser",
    "FinishReason",
    "GenerationPurpose",
    "GenerationRequest",
    "GenerationResult",
    "JobQueue",
    "ModelAdapter",
    "ModelAdapterError",
    "ModelCapabilities",
    "ModelErrorCode",
    "ModelGateway",
    "ModelProfileSnapshot",
    "TokenUsage",
    "UnitOfWork",
]


class ArtifactStore(Protocol):
    async def put(self, namespace: str, data: bytes, *, expected_sha256: str | None = None) -> str: ...
    async def get(self, key: str) -> bytes: ...


class DocumentParser(Protocol):
    def parse(self, data: bytes, media_type: str) -> Any: ...


# Compatibility name for callers of the former untyped port. It is the same
# normative protocol, not a second model boundary.
ModelGateway = ModelAdapter


class JobQueue(Protocol):
    async def publish(self, envelope: dict[str, Any]) -> None: ...


class UnitOfWork(Protocol):
    async def __aenter__(self) -> UnitOfWork: ...
    async def __aexit__(self, *exc: object) -> None: ...
    async def commit(self) -> None: ...
