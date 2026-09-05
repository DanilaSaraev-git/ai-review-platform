from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

from review_runtime.skills.registry import ResolvedSkill, SkillFile


@dataclass(frozen=True, slots=True)
class TrustedInstructions:
    primary: str
    references: tuple[SkillFile, ...]


class SkillExecutor:
    def __init__(
        self,
        output_schemas: dict[str, dict[str, Any]],
        *,
        package: ResolvedSkill | None = None,
    ) -> None:
        self.output_schemas = output_schemas
        self.package = package

    def trusted_instructions(self, operation: str) -> TrustedInstructions:
        if self.package is None:
            raise ValueError("verified skill package is required")
        try:
            instruction_path = self.package.manifest["operations"][operation]["instructions"]
        except KeyError as error:
            raise ValueError("unsupported skill operation") from error
        primary = self.package.files[instruction_path].content.decode("utf-8")
        references = tuple(self.package.files[path] for path in self.package.manifest["references"])
        return TrustedInstructions(primary=primary, references=references)

    def validate_output(self, operation: str, value: dict[str, Any]) -> dict[str, Any]:
        try:
            schema = self.output_schemas[operation]
        except KeyError as error:
            raise ValueError("unsupported skill operation") from error
        errors = list(Draft202012Validator(schema).iter_errors(value))
        if errors:
            raise ValueError("skill output violates its declared schema")
        return value
