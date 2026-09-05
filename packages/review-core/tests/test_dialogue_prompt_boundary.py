from review_core.dialogue.prompt import build_dialogue_request
from review_core.ports.models import GenerationPurpose, ModelProfileSnapshot


def test_current_message_full_history_and_evidence_are_only_untrusted() -> None:
    request = build_dialogue_request(
        request_id="dialogue-request-1",
        work_item_id="dialogue-turn-1",
        instructions="Explain the finding without deciding for the human.",
        current_message="CANARY_CURRENT",
        history=["CANARY_MEMBER", "CANARY_ASSISTANT"],
        evidence=["CANARY_EVIDENCE"],
        response_schema={"type": "object"},
        model_profile=ModelProfileSnapshot(id="synthetic", version="1.0.0", config_sha256="a" * 64),
        max_output_tokens=128,
        timeout_seconds=60.0,
    )
    assert request.purpose is GenerationPurpose.DIALOGUE
    assert "CANARY" not in request.trusted_instructions
    assert all(
        token in request.untrusted_input
        for token in ("CANARY_CURRENT", "CANARY_MEMBER", "CANARY_ASSISTANT", "CANARY_EVIDENCE")
    )
