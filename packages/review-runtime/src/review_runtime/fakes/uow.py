from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4


@dataclass(slots=True)
class InMemoryState:
    values: dict[str, dict[str, Any]] = field(default_factory=dict)
    outbox: dict[str, dict[str, Any]] = field(default_factory=dict)
    leases: dict[str, dict[str, Any]] = field(default_factory=dict)


class InMemoryUnitOfWork:
    def __init__(self, state: InMemoryState) -> None:
        self.state = state
        self.committed = False

    async def __aenter__(self) -> InMemoryUnitOfWork:
        return self

    async def __aexit__(self, *exc: object) -> None:
        if exc[0] is not None:
            self.committed = False

    async def commit(self) -> None:
        self.committed = True


class InMemoryOutbox:
    def __init__(self, state: InMemoryState) -> None:
        self.state = state

    def add(self, kind: str, business_key: str, payload: dict[str, Any]) -> str:
        for job in self.state.outbox.values():
            if job["business_key"] == business_key:
                return cast(str, job["id"])
        job_id = str(uuid4())
        self.state.outbox[job_id] = {
            "id": job_id,
            "kind": kind,
            "business_key": business_key,
            "payload": payload,
            "state": "pending",
        }
        return job_id


class InMemoryLeaseStore:
    def __init__(self, state: InMemoryState) -> None:
        self.state = state

    def claim(self, key: str, owner: str, seconds: int, now: datetime | None = None) -> str | None:
        now = now or datetime.now(UTC)
        current = self.state.leases.get(key)
        if current and current["expires_at"] > now:
            return None
        token = str(uuid4())
        self.state.leases[key] = {
            "token": token,
            "owner": owner,
            "expires_at": now + timedelta(seconds=seconds),
        }
        return token

    def heartbeat(self, key: str, token: str, seconds: int, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        current = self.state.leases.get(key)
        if not current or current["token"] != token:
            return False
        current["expires_at"] = now + timedelta(seconds=seconds)
        return True
