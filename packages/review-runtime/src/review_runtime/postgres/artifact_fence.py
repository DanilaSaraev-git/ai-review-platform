from __future__ import annotations

import hashlib

from sqlalchemy import text


def advisory_fence_key(namespace: str, store_key: str, digest: str) -> int:
    raw = hashlib.sha256(f"{namespace}\0{store_key}\0{digest}".encode()).digest()[:8]
    return int.from_bytes(raw, "big", signed=True)


async def acquire_artifact_fence(session, namespace: str, store_key: str, digest: str) -> int:  # type: ignore[no-untyped-def]
    key = advisory_fence_key(namespace, store_key, digest)
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})
    return key
