from __future__ import annotations

import re


def provider_headers(*, provider: str, model: str, secret: str | None) -> dict[str, str]:
    """Build provider authentication and project headers without exposing credentials."""
    headers: dict[str, str] = {}
    if provider == "yandex":
        match = re.fullmatch(r"gpt://([A-Za-z0-9_-]+)/[^\s?#]+", model)
        if match is None:
            raise ValueError("Yandex model must use gpt://<folder_id>/<model>")
        headers["OpenAI-Project"] = match.group(1)
    if secret is not None:
        scheme = "Api-Key" if provider == "yandex" else "Bearer"
        headers["Authorization"] = f"{scheme} {secret}"
    return headers
