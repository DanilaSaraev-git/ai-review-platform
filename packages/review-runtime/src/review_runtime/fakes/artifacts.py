from __future__ import annotations

import hashlib
from uuid import uuid4


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self.values: dict[str, bytes] = {}

    async def put(self, namespace: str, data: bytes, *, expected_sha256: str | None = None) -> str:
        digest = hashlib.sha256(data).hexdigest()
        if expected_sha256 is not None and digest != expected_sha256:
            raise ValueError("artifact digest mismatch")
        key = f"{namespace}/{uuid4()}"
        self.values[key] = bytes(data)
        return key

    async def get(self, key: str) -> bytes:
        return self.values[key]
