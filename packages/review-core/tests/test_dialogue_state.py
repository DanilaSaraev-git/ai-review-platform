from review_core.dialogue.state import DialogueState


def test_published_finding_dialogue_starts_open_and_allows_one_active_turn() -> None:
    dialogue = DialogueState.new("dialogue", "run", "finding", max_member_turns=None)
    assert dialogue.projection()["can_send_message"] is True
    dialogue.start_turn("turn-1")
    projection = dialogue.projection()
    assert projection["state"] == "generating"
    assert projection["blocked_reason"] == "generation_in_progress"


def test_decision_blocks_dialogue_even_when_generation_finishes() -> None:
    dialogue = DialogueState.new("dialogue", "run", "finding", max_member_turns=3)
    dialogue.start_turn("turn-1")
    dialogue.human_decision_recorded = True
    dialogue.finish_turn("turn-1")
    assert dialogue.projection()["blocked_reason"] == "human_decision_recorded"
