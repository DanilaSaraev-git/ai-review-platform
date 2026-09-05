from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, cast

from review_core.dialogue.engine import DialogueEngine
from review_core.dialogue.prompt import build_dialogue_request
from review_core.ports.models import GenerationRequest, JsonValue, ModelProfileSnapshot


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


@dataclass(frozen=True, slots=True)
class PinnedDialogueSkill:
    id: str
    version: str
    package_sha256: str
    instructions: str

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.version.strip() or not self.instructions.strip():
            raise ValueError("pinned dialogue skill identity and instructions are required")
        if not _is_sha256(self.package_sha256):
            raise ValueError("pinned dialogue skill package_sha256 is invalid")


@dataclass(frozen=True, slots=True)
class DialoguePreparationContext:
    run_id: str
    dialogue_id: str
    turn_id: str
    turn_ordinal: int
    member_message_id: str
    member_message: str
    finding: Mapping[str, Any]
    sources: tuple[Mapping[str, Any], ...]
    profile: Mapping[str, Any]
    completed_history: tuple[Mapping[str, Any], ...]
    follow_up_allowed: bool
    locale: str
    execution_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.run_id,
                self.dialogue_id,
                self.turn_id,
                self.member_message_id,
                self.member_message,
            )
        ):
            raise ValueError("dialogue preparation identity and current message are required")
        if self.turn_ordinal < 1:
            raise ValueError("dialogue turn ordinal must be positive")
        if not self.sources:
            raise ValueError("dialogue preparation requires at least one source")
        if len(self.locale) not in {2, 5}:
            raise ValueError("dialogue locale is invalid")


def _completed_history(context: DialoguePreparationContext) -> list[dict[str, Any]]:
    completed: list[dict[str, Any]] = []
    seen_turn_ids: set[str] = set()
    prior_ordinal = 0
    required = {"turn_id", "ordinal", "member_message", "assistant_message"}
    for turn in context.completed_history:
        if set(turn) != required or not isinstance(turn.get("assistant_message"), Mapping):
            raise ValueError("dialogue history must contain only completed turns")
        turn_id = turn["turn_id"]
        ordinal = turn["ordinal"]
        if not isinstance(turn_id, str) or not isinstance(ordinal, int):
            raise ValueError("completed dialogue turn identity is invalid")
        if turn_id == context.turn_id:
            raise ValueError("current turn cannot appear in completed dialogue history")
        if turn_id in seen_turn_ids or ordinal <= prior_ordinal or ordinal >= context.turn_ordinal:
            raise ValueError("completed dialogue history order is invalid")
        seen_turn_ids.add(turn_id)
        prior_ordinal = ordinal
        completed.append(deepcopy(dict(turn)))
    return completed


def prepare_dialogue_generation(
    *,
    context: DialoguePreparationContext,
    skill: PinnedDialogueSkill,
    request_id: str,
    response_schema: dict[str, JsonValue],
    max_input_utf8_bytes: int,
    max_output_tokens: int,
    timeout_seconds: float,
    temperature: float | None = None,
) -> GenerationRequest:
    snapshotted_skill = context.execution_snapshot.get("skill")
    snapshotted_model = context.execution_snapshot.get("model_profile")
    if not isinstance(snapshotted_skill, Mapping) or not isinstance(snapshotted_model, Mapping):
        raise ValueError("dialogue execution snapshot is incomplete")
    if (
        snapshotted_skill.get("id"),
        snapshotted_skill.get("version"),
        snapshotted_skill.get("package_sha256"),
    ) != (skill.id, skill.version, skill.package_sha256):
        raise ValueError("resolved dialogue skill does not match the execution snapshot")
    try:
        model_profile = ModelProfileSnapshot(
            id=str(snapshotted_model["id"]),
            version=str(snapshotted_model["version"]),
            config_sha256=str(snapshotted_model["config_sha256"]),
        )
    except KeyError as error:
        raise ValueError("dialogue model profile snapshot is incomplete") from error
    dialogue_input: dict[str, Any] = {
        "contract_version": "finding-dialogue-input.v1",
        "run_id": context.run_id,
        "dialogue_id": context.dialogue_id,
        "finding": deepcopy(dict(context.finding)),
        "sources": deepcopy([dict(source) for source in context.sources]),
        "profile": deepcopy(dict(context.profile)),
        "history": _completed_history(context),
        "current_turn": {
            "turn_id": context.turn_id,
            "ordinal": context.turn_ordinal,
            "member_message": {
                "message_id": context.member_message_id,
                "content": context.member_message,
            },
            "follow_up_allowed": context.follow_up_allowed,
        },
        "options": {"locale": context.locale},
    }
    return DialogueEngine().prepare_generation_request(
        dialogue_input=cast(Mapping[str, JsonValue], dialogue_input),
        skill_instructions=skill.instructions,
        request_id=request_id,
        turn_id=context.turn_id,
        response_schema=response_schema,
        model_profile=model_profile,
        max_input_utf8_bytes=max_input_utf8_bytes,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


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
