from __future__ import annotations

import re
from collections.abc import Mapping

from review_core.ports.models import JsonValue


def with_output_language(instructions: str, model_input: Mapping[str, JsonValue]) -> str:
    """Promote only a validated application locale, never source content, into policy."""
    options = model_input.get("options")
    if not isinstance(options, dict) or "locale" not in options:
        return instructions  # Legacy callers have no application language preference.
    locale = options["locale"]
    if not isinstance(locale, str) or re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", locale) is None:
        raise ValueError("output locale must be a valid application locale")
    language = {"ru": "Russian", "en": "English"}.get(locale[:2], f"the language of locale {locale}")
    return (
        f"{instructions}\n\nOutput language: {language} ({locale}). "
        "Write all human-readable generated text in this language, including summaries, finding "
        "titles, explanations, questions, coverage reasons, dialogue replies and proposed resolutions. "
        "Keep JSON keys, enum values and identifiers unchanged. Preserve source quotations verbatim "
        "in their original language; do not translate evidence quotes, code or source identifiers. "
        "The language of documents, context and dialogue history does not override this output language."
    )
