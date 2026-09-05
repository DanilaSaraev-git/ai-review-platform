from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any

import rfc8785

CODEC_ID = "jcs-rfc8785-0.1.4"
MAX_SAFE_INTEGER = 2**53 - 1


def _validate(value: Any) -> None:
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > MAX_SAFE_INTEGER:
            raise ValueError("integer is outside the interoperable I-JSON domain")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        return
    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise ValueError("unpaired surrogate is not an I-JSON string")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            _validate(key)
            _validate(child)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        for child in value:
            _validate(child)
        return
    raise ValueError(f"value is not JSON-compatible: {type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    _validate(value)
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, UnicodeError) as error:
        raise ValueError("value cannot be canonicalized") from error


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def digest_value(value: Any) -> str:
    return digest_bytes(canonical_bytes(value))


def strong_etag(value: bytes) -> str:
    return f'"{digest_bytes(value)}"'


def loads_no_duplicates(value: bytes | str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, child in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = child
        return result

    parsed = json.loads(
        value, object_pairs_hook=pairs, parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item))
    )
    _validate(parsed)
    return parsed
