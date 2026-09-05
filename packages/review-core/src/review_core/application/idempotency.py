from __future__ import annotations

from review_core.domain.errors import InvalidRequest


def require_idempotency_key(key: str) -> None:
    if not 8 <= len(key) <= 128:
        raise InvalidRequest(
            "invalid_idempotency_key",
            "Idempotency-Key must contain between 8 and 128 characters.",
        )
