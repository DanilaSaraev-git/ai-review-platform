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

_LEGACY_PROFILE = ModelProfileSnapshot(id="unconfigured", version="0.0.0", config_sha256="0" * 64)


class PromptBudgetExceeded(ValueError):
    """The complete normalized prompt does not fit the configured model input budget."""


def _json_bytes(value: Mapping[str, JsonValue]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def prompt_utf8_size(request: GenerationRequest) -> int:
    """Return the normalized full-prompt size, including schema and framing overhead."""

    envelope: dict[str, JsonValue] = {
        "response_schema": request.response_schema,
        "trusted_instructions": request.trusted_instructions,
        "untrusted_input": request.untrusted_input,
    }
    return len(_json_bytes(envelope))


def build_review_generation_request(
    *,
    skill_instructions: str,
    review_input: Mapping[str, JsonValue],
    request_id: str,
    work_item_id: str,
    response_schema: dict[str, JsonValue],
    model_profile: ModelProfileSnapshot,
    max_input_utf8_bytes: int,
    max_output_tokens: int,
    timeout_seconds: float,
    temperature: float | None = None,
) -> GenerationRequest:
    if not skill_instructions.strip():
        raise ValueError("trusted skill instructions are required")
    if max_input_utf8_bytes <= 0:
        raise ValueError("max_input_utf8_bytes must be positive")
    request = GenerationRequest(
        request_id=request_id,
        purpose=GenerationPurpose.REVIEW,
        work_item_id=work_item_id,
        trusted_instructions=skill_instructions,
        untrusted_input=_json_bytes(review_input).decode("utf-8"),
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


def build_generation_request(
    *,
    skill_instructions: str,
    document_text: str,
    context_texts: list[str],
    intermediate_outputs: list[str],
    request_id: str | None = None,
    work_item_id: str = "legacy-whole-document",
    response_schema: dict[str, JsonValue] | None = None,
    model_profile: ModelProfileSnapshot | None = None,
    max_output_tokens: int = 1,
    timeout_seconds: float = 1.0,
    temperature: float | None = None,
) -> GenerationRequest:
    if not skill_instructions.strip():
        raise ValueError("trusted skill instructions are required")
    contexts: list[JsonValue] = list(context_texts)
    intermediates: list[JsonValue] = list(intermediate_outputs)
    review_input: dict[str, JsonValue] = {
        "context": contexts,
        "intermediate_outputs": intermediates,
        "primary_document": document_text,
    }
    return build_review_generation_request(
        request_id=request_id or str(uuid4()),
        work_item_id=work_item_id,
        skill_instructions=skill_instructions,
        review_input=review_input,
        response_schema=response_schema or {},
        model_profile=model_profile or _LEGACY_PROFILE,
        max_input_utf8_bytes=2**63 - 1,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )
