from __future__ import annotations

import math

import pytest
from review_core.canonical import CODEC_ID, canonical_bytes, digest_value, strong_etag


def test_rfc8785_known_vector_and_utf16_property_order() -> None:
    value = {"numbers": [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27], "string": '€$\u000f\nA\'B"\\"/'}
    assert canonical_bytes(value) == (
        b'{"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27],'
        b'"string":"\xe2\x82\xac$\\u000f\\nA\'B\\"\\\\\\"/"}'
    )
    assert canonical_bytes({"\r": 1, "1": 2, "\u0080": 3, "ö": 4, "€": 5, "😀": 6, "דּ": 7})
    assert CODEC_ID == "jcs-rfc8785-0.1.4"


def test_digest_and_strong_etag_use_exact_bytes() -> None:
    digest = digest_value({"b": 2, "a": 1})
    assert digest == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    assert strong_etag(b"abc") == '"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"'


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 9007199254740992, "\ud800"])
def test_invalid_ijson_values_are_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        canonical_bytes({"value": value})
