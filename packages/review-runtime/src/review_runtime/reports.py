from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


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
