from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    trusted_instructions: str
    untrusted_input: tuple[str, ...]


def build_generation_request(
    *,
    skill_instructions: str,
    document_text: str,
    context_texts: list[str],
    intermediate_outputs: list[str],
) -> GenerationRequest:
    if not skill_instructions.strip():
        raise ValueError("trusted skill instructions are required")
    return GenerationRequest(
        trusted_instructions=skill_instructions,
        untrusted_input=(document_text, *context_texts, *intermediate_outputs),
    )
