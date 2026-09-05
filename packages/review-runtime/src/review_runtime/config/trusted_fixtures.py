from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from review_runtime.config.settings import TrustedFixtureBinding


@dataclass(frozen=True, slots=True)
class TrustedFixtureResource:
    binding: TrustedFixtureBinding
    value: dict[str, Any]


class TrustedFixtureRegistry:
    def __init__(self, schema_path: Path, resources: dict[str, Path]) -> None:
        self.schema = json.loads(schema_path.read_text())
        self.resources = resources

    def resolve(self, binding: TrustedFixtureBinding) -> TrustedFixtureResource:
        path = self.resources.get(binding.expected_output_resource_id)
        if path is None:
            raise ValueError("trusted expected-output resource is missing")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != binding.expected_output_sha256:
            raise ValueError("trusted expected-output resource digest drift")
        value = json.loads(raw, object_pairs_hook=_unique_pairs)
        Draft202012Validator(self.schema).validate(value)
        if value["resource_id"] != binding.expected_output_resource_id:
            raise ValueError("trusted expected-output resource identity mismatch")
        return TrustedFixtureResource(binding, value)


def _unique_pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result
