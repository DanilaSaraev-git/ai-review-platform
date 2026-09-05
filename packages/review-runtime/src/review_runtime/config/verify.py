from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from review_runtime.config.settings import RuntimePolicy


def verify(path: Path) -> RuntimePolicy:
    value = json.loads(path.read_text(), object_pairs_hook=_unique_pairs)
    policy = RuntimePolicy.from_value(value)
    expected_path = os.environ.get("REVIEW_EXPECTED_OUTPUT_PATH")
    document_path = os.environ.get("REVIEW_TRUSTED_DOCUMENT_PATH")
    for binding in policy.deterministic_gateway.trusted_fixture_bindings:
        if expected_path is None or document_path is None:
            continue
        expected = Path(expected_path).read_bytes()
        document = Path(document_path).read_bytes()
        if hashlib.sha256(expected).hexdigest() != binding.expected_output_sha256:
            raise ValueError("trusted expected-output resource digest mismatch")
        if hashlib.sha256(document).hexdigest() != binding.primary_document_sha256:
            raise ValueError("trusted primary document digest mismatch")
        resource = json.loads(expected, object_pairs_hook=_unique_pairs)
        if resource.get("resource_id") != binding.expected_output_resource_id:
            raise ValueError("trusted expected-output resource id mismatch")
    return policy


def _unique_pairs(items: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main() -> None:
    path = Path(
        os.environ.get("REVIEW_RUNTIME_CONFIG_PATH", "deploy/compose/config/runtime-config.synthetic.v1.json")
    )
    policy = verify(path)
    print(f"runtime config ok: {policy.schema_version}")
