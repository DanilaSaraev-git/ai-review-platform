from review_core.dialogue.prompt import build_dialogue_request


def test_current_message_full_history_and_evidence_are_only_untrusted() -> None:
    request = build_dialogue_request(
        instructions="Explain the finding without deciding for the human.",
        current_message="CANARY_CURRENT",
        history=["CANARY_MEMBER", "CANARY_ASSISTANT"],
        evidence=["CANARY_EVIDENCE"],
    )
    assert "CANARY" not in request.trusted_instructions
    assert all(
        any(token in chunk for chunk in request.untrusted_input)
        for token in (
            "CANARY_CURRENT",
            "CANARY_MEMBER",
            "CANARY_ASSISTANT",
            "CANARY_EVIDENCE",
        )
    )
