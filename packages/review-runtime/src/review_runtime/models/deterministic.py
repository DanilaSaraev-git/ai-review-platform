from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SELECTOR_KEYS = (
    "primary_document_sha256",
    "review_profile_semantic_digest",
    "skill_package_sha256",
    "parser_settings_digest",
    "engine_version",
)


class DeterministicModelGateway:
    def __init__(self, bindings: list[dict[str, Any]]) -> None:
        self.bindings = bindings
        self.external_connection_attempts: list[str] = []

    @classmethod
    def from_manifest(cls, path: Path) -> DeterministicModelGateway:
        value = json.loads(path.read_text())
        if value.get("schema_version") != "trusted-fixture-manifest.v1":
            raise ValueError("unsupported trusted fixture manifest")
        return cls.from_bindings(value["bindings"])

    @classmethod
    def from_bindings(cls, bindings: list[dict[str, Any]]) -> DeterministicModelGateway:
        selectors = [tuple(binding[key] for key in SELECTOR_KEYS) for binding in bindings]
        if len(selectors) != len(set(selectors)):
            raise ValueError("trusted fixture selectors are not unique")
        return cls(bindings)

    @staticmethod
    def selector(binding: dict[str, Any]) -> dict[str, str]:
        return {key: binding[key] for key in SELECTOR_KEYS}

    def match(self, **selector: str) -> dict[str, Any] | None:
        expected = tuple(selector.get(key) for key in SELECTOR_KEYS)
        for binding in self.bindings:
            if tuple(binding[key] for key in SELECTOR_KEYS) == expected:
                return binding
        return None
