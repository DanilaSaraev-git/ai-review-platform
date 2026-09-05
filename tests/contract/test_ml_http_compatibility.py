from __future__ import annotations

from pathlib import Path

import yaml
from review_core.application.model_retry import public_model_error_code
from review_core.ports.models import ModelAdapterError, ModelErrorCode

ROOT = Path(__file__).parents[2]

REVIEW_ERROR_ENUM = {
    "invalid_document",
    "unsupported_document",
    "extraction_failed",
    "context_limit",
    "model_unavailable",
    "model_output_invalid",
    "validation_failed",
    "cancelled",
    "internal_error",
}
DIALOGUE_ERROR_ENUM = {
    "model_unavailable",
    "context_limit",
    "content_blocked",
    "model_output_invalid",
    "validation_failed",
    "internal_error",
}


def _schema_enum(schema_name: str) -> set[str]:
    contract = yaml.safe_load((ROOT / "contracts/review-platform/v1/openapi.yaml").read_text())
    return set(contract["components"]["schemas"][schema_name]["properties"]["code"]["enum"])


def _error(code: ModelErrorCode) -> ModelAdapterError:
    return ModelAdapterError(code=code, message="Safe model failure.", retryable=False)


def test_public_error_enums_remain_exactly_v1_0_2() -> None:
    assert _schema_enum("AsyncError") == REVIEW_ERROR_ENUM
    assert _schema_enum("DialogueError") == DIALOGUE_ERROR_ENUM


def test_every_internal_model_error_has_a_canonical_review_projection() -> None:
    expected = {
        ModelErrorCode.AUTHENTICATION_FAILED: "model_unavailable",
        ModelErrorCode.MODEL_NOT_FOUND: "model_unavailable",
        ModelErrorCode.RATE_LIMITED: "model_unavailable",
        ModelErrorCode.PROVIDER_UNAVAILABLE: "model_unavailable",
        ModelErrorCode.TIMEOUT: "model_unavailable",
        ModelErrorCode.CONTEXT_LIMIT: "context_limit",
        ModelErrorCode.CONTENT_BLOCKED: "model_output_invalid",
        ModelErrorCode.UNSUPPORTED_OPTION: "model_unavailable",
        ModelErrorCode.INVALID_PROVIDER_RESPONSE: "model_output_invalid",
    }

    assert {
        code: public_model_error_code(_error(code), purpose="review") for code in ModelErrorCode
    } == expected
    assert set(expected.values()) <= REVIEW_ERROR_ENUM


def test_dialogue_preserves_content_blocked_without_expanding_public_enum() -> None:
    projected = {
        code: public_model_error_code(_error(code), purpose="dialogue") for code in ModelErrorCode
    }

    assert projected[ModelErrorCode.CONTENT_BLOCKED] == "content_blocked"
    assert set(projected.values()) <= DIALOGUE_ERROR_ENUM
