from __future__ import annotations


def create_review_request(document_id: str, profile_id: str, *, context_count: int = 0) -> dict[str, object]:
    return {
        "document_id": document_id,
        "context_document_ids": [f"00000000-0000-4000-8000-{index:012d}" for index in range(context_count)],
        "profile": {"id": profile_id, "version": "1.0.0"},
        "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
        "locale": "en-US",
    }
