from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


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
        if next(self.validator.iter_errors(value), None) is not None:
            raise ValueError("compact review model output violates its declared schema")
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
