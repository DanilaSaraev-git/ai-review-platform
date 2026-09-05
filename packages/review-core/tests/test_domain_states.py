from __future__ import annotations

import pytest
from review_core.domain import DialogueTurnState, InvalidTransition, ReviewRunState, ServerId


def test_server_ids_are_uuid_and_never_caller_selected() -> None:
    first = ServerId.new()
    second = ServerId.new()
    assert first != second
    assert str(ServerId.parse(str(first))) == str(first)
    with pytest.raises(ValueError):
        ServerId.parse("../../foreign")


def test_review_run_state_machine_has_strict_terminal_invariants() -> None:
    state = ReviewRunState.QUEUED
    for next_state in (
        ReviewRunState.PREPARING,
        ReviewRunState.REVIEWING,
        ReviewRunState.VALIDATING,
        ReviewRunState.COMPLETED,
    ):
        state = state.transition(next_state)
    with pytest.raises(InvalidTransition):
        state.transition(ReviewRunState.CANCELLED)


def test_dialogue_retry_is_explicit_not_a_terminal_transition() -> None:
    assert DialogueTurnState.QUEUED.transition(DialogueTurnState.GENERATING) is DialogueTurnState.GENERATING
    assert DialogueTurnState.GENERATING.transition(DialogueTurnState.FAILED) is DialogueTurnState.FAILED
    with pytest.raises(InvalidTransition):
        DialogueTurnState.FAILED.transition(DialogueTurnState.QUEUED)
