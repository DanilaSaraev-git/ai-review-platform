from __future__ import annotations

from typing import Any

from review_core.dialogue.validation import validate_dialogue_output


def deterministic_dialogue_response(
    snapshot: dict[str, Any], anchors: list[dict[str, Any]]
) -> dict[str, Any]:
    response = {
        "action": "propose_resolution",
        "content": "State an exact attempt limit and terminal outcome for the retry policy.",
        "proposed_resolution": {
            "text": (
                "Retry at most three times; after exhaustion mark the load failed and alert the operator."
            ),
            "rationale": "This makes failure handling deterministic and testable.",
        },
        "anchors": anchors,
        "provenance": {
            "skill": snapshot["skill"],
            "model": {
                "provider": "deterministic",
                "model": "dialogue-fixture",
                "model_version": "1.0.0",
                "safe_parameters": {"temperature": 0},
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    }
    return validate_dialogue_output(response)
