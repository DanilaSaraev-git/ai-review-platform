from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from review_core.dialogue.validation import validate_dialogue_output
from review_core.ports.models import (
    FinishReason,
    GenerationRequest,
    JsonValue,
    ModelAdapter,
    ModelAdapterError,
    ModelErrorCode,
    ModelProfileSnapshot,
)
from review_core.review.engine import ReviewFragment
from review_core.review.validation import resolve_unique_quote_offset


@dataclass(frozen=True, slots=True)
class DialogueMappingContext:
    fragments: Mapping[str, ReviewFragment]
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if any(key != fragment.id for key, fragment in self.fragments.items()):
            raise ValueError("dialogue mapping fragment key does not match its identity")
        if set(self.provenance) != {"skill", "model"}:
            raise ValueError("dialogue provenance fields do not match the canonical contract")
        skill = self.provenance.get("skill")
        model = self.provenance.get("model")
        if not isinstance(skill, Mapping) or set(skill) != {"id", "version", "package_sha256"}:
            raise ValueError("dialogue skill provenance is invalid")
        if not isinstance(model, Mapping) or set(model) != {
            "provider",
            "model",
            "model_version",
            "safe_parameters",
            "usage",
        }:
            raise ValueError("dialogue model provenance is invalid")
        if not isinstance(model["safe_parameters"], Mapping) or not isinstance(model["usage"], Mapping):
            raise ValueError("dialogue model provenance is invalid")
        if set(model["usage"]) != {"input_tokens", "output_tokens"}:
            raise ValueError("dialogue model usage provenance is invalid")


def _validate_compact_dialogue_shape(value: Mapping[str, Any]) -> None:
    if set(value) != {"action", "content", "proposed_resolution", "anchors"}:
        raise ValueError("compact dialogue fields do not match the model-output contract")
    if not isinstance(value.get("anchors"), list):
        raise ValueError("compact dialogue anchors must be an array")
    for anchor in value["anchors"]:
        if not isinstance(anchor, Mapping) or set(anchor) != {"source_id", "fragment_id", "quote"}:
            raise ValueError("compact dialogue anchor fields do not match the model-output contract")


class DialogueEngine:
    async def execute(
        self,
        *,
        adapter: ModelAdapter,
        request: GenerationRequest,
        parse_and_validate: Callable[[str], dict[str, Any]],
        fragments: Mapping[str, ReviewFragment],
        skill_snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        result = await adapter.generate(request)
        if result.request_id != request.request_id:
            raise ModelAdapterError(
                code=ModelErrorCode.INVALID_PROVIDER_RESPONSE,
                message="Model response request identity did not match the attempt.",
                retryable=False,
            )
        if result.finish_reason is not FinishReason.STOP:
            code = (
                ModelErrorCode.CONTENT_BLOCKED
                if result.finish_reason is FinishReason.CONTENT_FILTER
                else ModelErrorCode.INVALID_PROVIDER_RESPONSE
            )
            raise ModelAdapterError(
                code=code,
                message="Model response did not finish with a complete result.",
                retryable=False,
            )
        if any(
            not isinstance(value, (str, int, float, bool)) and value is not None
            for value in result.safe_parameters.values()
        ):
            raise ValueError("dialogue model provenance contains a non-public parameter value")
        usage = result.usage
        provenance = {
            "skill": deepcopy(dict(skill_snapshot)),
            "model": {
                "provider": result.provider,
                "model": result.model,
                "model_version": result.model_version,
                "safe_parameters": deepcopy(result.safe_parameters),
                "usage": {
                    "input_tokens": None if usage is None else usage.input_tokens,
                    "output_tokens": None if usage is None else usage.output_tokens,
                },
            },
        }
        return self.map_model_output(
            parse_and_validate(result.text),
            context=DialogueMappingContext(fragments=fragments, provenance=provenance),
        )

    def prepare_generation_request(
        self,
        *,
        dialogue_input: Mapping[str, JsonValue],
        skill_instructions: str,
        request_id: str,
        turn_id: str,
        response_schema: dict[str, JsonValue],
        model_profile: ModelProfileSnapshot,
        max_input_utf8_bytes: int,
        max_output_tokens: int,
        timeout_seconds: float,
        temperature: float | None = None,
    ) -> GenerationRequest:
        from review_core.dialogue.prompt import build_dialogue_generation_request

        return build_dialogue_generation_request(
            dialogue_input=dialogue_input,
            instructions=skill_instructions,
            request_id=request_id,
            work_item_id=turn_id,
            response_schema=response_schema,
            model_profile=model_profile,
            max_input_utf8_bytes=max_input_utf8_bytes,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )

    def map_model_output(
        self, model_output: dict[str, Any], *, context: DialogueMappingContext
    ) -> dict[str, Any]:
        _validate_compact_dialogue_shape(model_output)
        anchors: list[dict[str, Any]] = []
        for compact_anchor in model_output["anchors"]:
            fragment = context.fragments.get(compact_anchor["fragment_id"])
            if fragment is None:
                raise ValueError("dialogue anchor references an unknown fragment")
            if compact_anchor["source_id"] != fragment.source_id:
                raise ValueError("dialogue anchor source identity mismatch")
            quote = compact_anchor["quote"]
            if not isinstance(quote, str) or not quote:
                raise ValueError("dialogue anchor quote is required")
            start = resolve_unique_quote_offset(fragment.text, quote)
            anchors.append(
                {
                    "source_id": fragment.source_id,
                    "document_id": fragment.document_id,
                    "source_name": fragment.source_name,
                    "fragment_id": fragment.id,
                    "quote": quote,
                    "quote_start": start,
                    "quote_end": start + len(quote),
                    "location": deepcopy(dict(fragment.location)),
                }
            )
        response = {
            "action": model_output["action"],
            "content": model_output["content"],
            "proposed_resolution": deepcopy(model_output["proposed_resolution"]),
            "anchors": anchors,
            "provenance": deepcopy(dict(context.provenance)),
        }
        return validate_dialogue_output(
            response,
            fragments={
                fragment_id: {
                    "source_id": fragment.source_id,
                    "document_id": fragment.document_id,
                    "source_name": fragment.source_name,
                    "text": fragment.text,
                    "location": dict(fragment.location),
                }
                for fragment_id, fragment in context.fragments.items()
            },
        )


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
