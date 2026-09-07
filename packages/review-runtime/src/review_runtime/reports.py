from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


class ModelReviewOutputError(ValueError):
    """Schema-owned diagnostics only; never include model values or unknown keys."""

    def __init__(self, message: str, feedback: str) -> None:
        super().__init__(message)
        self.feedback = feedback


def _unique_json_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        if key in value:
            raise ValueError("compact review model output is not valid JSON")
        value[key] = item
    return value


class ModelReviewOutputValidator:
    def __init__(self, schema_path: Path) -> None:
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema)

    def validate(self, value: dict[str, Any]) -> dict[str, Any]:
        errors = list(self.validator.iter_errors(value))
        if errors:
            details = []
            for error in errors[:8]:
                detail: dict[str, Any] = {
                    "schema_path": list(error.absolute_schema_path),
                    "rule": error.validator,
                }
                if error.validator == "required":
                    detail["missing_fields"] = [k for k in error.validator_value if k not in error.instance]
                if error.validator in {"type", "enum"}:
                    detail["expected"] = error.validator_value
                details.append(detail)
            raise ModelReviewOutputError(
                "compact review model output violates its declared schema",
                json.dumps(details, ensure_ascii=False),
            )
        return value

    def parse_and_validate(self, text: str) -> dict[str, Any]:
        try:
            value = json.loads(text, object_pairs_hook=_unique_json_object)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("compact review model output is not valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("compact review model output must be a JSON object")
        return self.validate(value)


class CanonicalReportValidator:
    def __init__(self, openapi_path: Path) -> None:
        contract = yaml.safe_load(openapi_path.read_text())
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": "#/components/schemas/ReviewReport",
            "components": contract["components"],
        }
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, report: dict[str, Any]) -> None:
        if next(self.validator.iter_errors(report), None) is not None:
            raise ValueError("review report violates canonical schema")
