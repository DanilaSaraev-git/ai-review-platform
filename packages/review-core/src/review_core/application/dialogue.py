from __future__ import annotations

from typing import Any

from review_core.dialogue.prompt import build_dialogue_request


def dialogue_generation_input(
    *, message: str, turns: list[dict[str, Any]], anchors: list[dict[str, Any]]
) -> object:
    history: list[str] = []
    for turn in turns:
        history.append(turn["member_message"])
        if turn.get("assistant_response"):
            history.append(turn["assistant_response"]["content"])
    return build_dialogue_request(
        instructions="Explain or propose a resolution; never create a Human Decision.",
        current_message=message,
        history=history,
        evidence=[anchor["quote"] for anchor in anchors],
    )
