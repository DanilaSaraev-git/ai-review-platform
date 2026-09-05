from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator


class SkillExecutor:
    def __init__(self, output_schemas: dict[str, dict[str, Any]]) -> None:
        self.output_schemas = output_schemas

    def validate_output(self, operation: str, value: dict[str, Any]) -> dict[str, Any]:
        try:
            schema = self.output_schemas[operation]
        except KeyError as error:
            raise ValueError("unsupported skill operation") from error
        errors = list(Draft202012Validator(schema).iter_errors(value))
        if errors:
            raise ValueError("skill output violates its declared schema")
        return value
