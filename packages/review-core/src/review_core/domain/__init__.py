from __future__ import annotations

from enum import StrEnum
from uuid import UUID, uuid4


class InvalidTransition(ValueError):
    """A persisted lifecycle transition violates the domain state machine."""


class ServerId(str):
    @classmethod
    def new(cls) -> ServerId:
        return cls(str(uuid4()))

    @classmethod
    def parse(cls, value: str) -> ServerId:
        return cls(str(UUID(value)))


class TransitionState(StrEnum):
    def transition(self, target: TransitionState) -> TransitionState:
        allowed = self.allowed_transitions()
        if target not in allowed:
            raise InvalidTransition(f"cannot transition {self.value} to {target.value}")
        return target

    def allowed_transitions(self) -> frozenset[TransitionState]:
        raise NotImplementedError


class ReviewRunState(TransitionState):
    QUEUED = "queued"
    PREPARING = "preparing"
    REVIEWING = "reviewing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    def allowed_transitions(self) -> frozenset[ReviewRunState]:
        active = {self.QUEUED, self.PREPARING, self.REVIEWING, self.VALIDATING}
        if self not in active:
            return frozenset()
        expected = {
            self.QUEUED: self.PREPARING,
            self.PREPARING: self.REVIEWING,
            self.REVIEWING: self.VALIDATING,
            self.VALIDATING: self.COMPLETED,
        }[self]
        return frozenset({expected, self.FAILED, self.CANCELLED})


class DialogueTurnState(TransitionState):
    QUEUED = "queued"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"

    def allowed_transitions(self) -> frozenset[DialogueTurnState]:
        return {
            self.QUEUED: frozenset({self.GENERATING, self.FAILED}),
            self.GENERATING: frozenset({self.COMPLETED, self.FAILED}),
            self.COMPLETED: frozenset(),
            self.FAILED: frozenset(),
        }[self]


class ExtractionState(TransitionState):
    PENDING = "pending"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"

    def allowed_transitions(self) -> frozenset[ExtractionState]:
        return {
            self.PENDING: frozenset({self.EXTRACTING, self.FAILED}),
            self.EXTRACTING: frozenset({self.COMPLETED, self.PARTIAL, self.FAILED}),
            self.COMPLETED: frozenset(),
            self.PARTIAL: frozenset(),
            self.FAILED: frozenset(),
        }[self]


def project_extraction_state(state: ExtractionState) -> str:
    return "pending" if state in {ExtractionState.PENDING, ExtractionState.EXTRACTING} else state.value


def project_model_availability(state: str | None, *, fresh: bool = True) -> str:
    return "available" if state == "available" and fresh else "unavailable"
