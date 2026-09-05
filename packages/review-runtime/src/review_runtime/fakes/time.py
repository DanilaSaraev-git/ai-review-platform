from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5


@dataclass(slots=True)
class FrozenClock:
    value: datetime = datetime(2026, 9, 5, tzinfo=UTC)

    def now(self) -> datetime:
        return self.value

    def advance(self, **kwargs: float) -> None:
        self.value += timedelta(**kwargs)


class DeterministicIdGenerator:
    def __init__(self, namespace: UUID) -> None:
        self.namespace = namespace
        self.ordinal = 0

    def new(self) -> str:
        self.ordinal += 1
        return str(uuid5(self.namespace, str(self.ordinal)))
