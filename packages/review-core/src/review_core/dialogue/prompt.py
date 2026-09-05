from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from uuid import uuid4

from review_core.ports.models import (
    GenerationPurpose,
    GenerationRequest,
    JsonValue,
    ModelProfileSnapshot,
)
from review_core.review.prompt import PromptBudgetExceeded, prompt_utf8_size

_LEGACY_PROFILE = ModelProfileSnapshot(id="unconfigured", version="0.0.0", config_sha256="0" * 64)


def build_dialogue_generation_request(
    *,
    instructions: str,
    dialogue_input: Mapping[str, JsonValue],
    request_id: str,
    work_item_id: str,
    response_schema: dict[str, JsonValue],
    model_profile: ModelProfileSnapshot,
    max_input_utf8_bytes: int,
    max_output_tokens: int,
    timeout_seconds: float,
    temperature: float | None = None,
) -> GenerationRequest:
    if not instructions.strip():
        raise ValueError("trusted dialogue instructions are required")
    if max_input_utf8_bytes <= 0:
        raise ValueError("max_input_utf8_bytes must be positive")
    request = GenerationRequest(
        request_id=request_id,
        purpose=GenerationPurpose.DIALOGUE,
        work_item_id=work_item_id,
        trusted_instructions=instructions,
        untrusted_input=json.dumps(
            dialogue_input,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
        response_schema=deepcopy(response_schema),
        model_profile=model_profile,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
    actual_size = prompt_utf8_size(request)
    if actual_size > max_input_utf8_bytes:
        raise PromptBudgetExceeded(
            f"complete prompt exceeds the model input budget ({actual_size} > {max_input_utf8_bytes} bytes)"
        )
    return request


def build_dialogue_request(
    *,
    instructions: str,
    current_message: str,
    history: list[str],
    evidence: list[str],
    request_id: str | None = None,
    work_item_id: str = "legacy-dialogue-turn",
    response_schema: dict[str, JsonValue] | None = None,
    model_profile: ModelProfileSnapshot | None = None,
    max_output_tokens: int = 1,
    timeout_seconds: float = 1.0,
    temperature: float | None = None,
) -> GenerationRequest:
    history_values: list[JsonValue] = list(history)
    evidence_values: list[JsonValue] = list(evidence)
    dialogue_input: dict[str, JsonValue] = {
        "current_message": current_message,
        "evidence": evidence_values,
        "history": history_values,
    }
    return build_dialogue_generation_request(
        request_id=request_id or str(uuid4()),
        work_item_id=work_item_id,
        instructions=instructions,
        dialogue_input=dialogue_input,
        response_schema=response_schema or {},
        model_profile=model_profile or _LEGACY_PROFILE,
        max_input_utf8_bytes=2**63 - 1,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
