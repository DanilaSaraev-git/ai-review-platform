import pytest
from review_core.dialogue.validation import validate_dialogue_output


def test_model_output_cannot_contain_human_decision() -> None:
    with pytest.raises(ValueError, match="Human Decision"):
        validate_dialogue_output(
            {"action": "clarify", "content": "Question", "human_decision": {"status": "confirmed"}}
        )
