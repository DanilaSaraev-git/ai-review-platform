from __future__ import annotations

import json

import pytest
from review_core.application.dialogue import (
    DialoguePreparationContext,
    PinnedDialogueSkill,
    prepare_dialogue_generation,
)
from review_core.review.prompt import PromptBudgetExceeded


def _context() -> DialoguePreparationContext:
    return DialoguePreparationContext(
        run_id="run-1",
        dialogue_id="dialogue-1",
        turn_id="turn-3",
        turn_ordinal=3,
        member_message_id="member-message-3",
        member_message="CURRENT_CANARY",
        finding={"id": "finding-1", "kind": "ambiguity"},
        sources=({"id": "source-main", "role": "document"},),
        profile={"id": "profile-1", "version": "1.0.0"},
        completed_history=(
            {
                "turn_id": "turn-1",
                "ordinal": 1,
                "member_message": {"message_id": "member-1", "content": "HISTORY_MEMBER"},
                "assistant_message": {
                    "message_id": "assistant-1",
                    "action": "clarify",
                    "content": "HISTORY_ASSISTANT",
                    "proposed_resolution": None,
                    "anchors": [],
                },
            },
        ),
        follow_up_allowed=True,
        locale="ru",
        execution_snapshot={
            "skill": {"id": "synthetic", "version": "1.2.3", "package_sha256": "a" * 64},
            "model_profile": {
                "id": "model-pinned",
                "version": "2.0.0",
                "config_sha256": "b" * 64,
            },
        },
    )


def _skill() -> PinnedDialogueSkill:
    return PinnedDialogueSkill(
        id="synthetic",
        version="1.2.3",
        package_sha256="a" * 64,
        instructions="Explain the finding; never decide for the analyst.",
    )


def test_dialogue_preparation_pins_versions_and_separates_completed_history_from_current_turn() -> None:
    context = _context()

    request = prepare_dialogue_generation(
        context=context,
        skill=_skill(),
        request_id="attempt-1",
        response_schema={"type": "object"},
        max_input_utf8_bytes=20_000,
        max_output_tokens=256,
        timeout_seconds=60.0,
    )
    dialogue_input = json.loads(request.untrusted_input)

    assert request.model_profile.id == "model-pinned"
    assert request.model_profile.version == "2.0.0"
    assert [turn["turn_id"] for turn in dialogue_input["history"]] == ["turn-1"]
    assert dialogue_input["current_turn"]["turn_id"] == "turn-3"
    assert dialogue_input["current_turn"]["member_message"]["content"] == "CURRENT_CANARY"
    assert "CURRENT_CANARY" not in json.dumps(dialogue_input["history"])


def test_dialogue_preparation_rejects_a_skill_other_than_the_snapshotted_package() -> None:
    different = PinnedDialogueSkill(
        id="synthetic",
        version="9.9.9",
        package_sha256="c" * 64,
        instructions="Different package instructions.",
    )

    with pytest.raises(ValueError, match="snapshot"):
        prepare_dialogue_generation(
            context=_context(),
            skill=different,
            request_id="attempt-1",
            response_schema={"type": "object"},
            max_input_utf8_bytes=20_000,
            max_output_tokens=256,
            timeout_seconds=60.0,
        )


def test_dialogue_preparation_rejects_current_turn_inside_completed_history() -> None:
    context = _context()
    duplicate = dict(context.completed_history[0]) | {"turn_id": context.turn_id}
    context = DialoguePreparationContext(
        run_id=context.run_id,
        dialogue_id=context.dialogue_id,
        turn_id=context.turn_id,
        turn_ordinal=context.turn_ordinal,
        member_message_id=context.member_message_id,
        member_message=context.member_message,
        finding=context.finding,
        sources=context.sources,
        profile=context.profile,
        completed_history=(duplicate,),
        follow_up_allowed=context.follow_up_allowed,
        locale=context.locale,
        execution_snapshot=context.execution_snapshot,
    )

    with pytest.raises(ValueError, match="current turn"):
        prepare_dialogue_generation(
            context=context,
            skill=_skill(),
            request_id="attempt-1",
            response_schema={"type": "object"},
            max_input_utf8_bytes=20_000,
            max_output_tokens=256,
            timeout_seconds=60.0,
        )


def test_dialogue_preparation_rejects_complete_prompt_over_budget() -> None:
    with pytest.raises(PromptBudgetExceeded, match="budget"):
        prepare_dialogue_generation(
            context=_context(),
            skill=_skill(),
            request_id="attempt-1",
            response_schema={"type": "object"},
            max_input_utf8_bytes=32,
            max_output_tokens=256,
            timeout_seconds=60.0,
        )
