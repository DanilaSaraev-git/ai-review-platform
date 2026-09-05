from __future__ import annotations

import pytest
from review_core.review.validation import validate_report

FRAGMENTS = {
    "f1": {
        "id": "f1",
        "source_id": "source-main",
        "document_id": "doc",
        "text": "Retry regularly.",
        "location": {"kind": "text", "line_start": 1, "line_end": 1, "char_start": 0, "char_end": 16},
    },
    "f2": {
        "id": "f2",
        "source_id": "source-main",
        "document_id": "doc",
        "text": "Terminal state is failed.",
        "location": {"kind": "text", "line_start": 2, "line_end": 2, "char_start": 0, "char_end": 25},
    },
}


def base_report() -> dict:
    return {
        "coverage": {
            "status": "partial",
            "target_fragment_ids": ["f1", "f2"],
            "reviewed_fragment_ids": [],
            "gaps": [
                {
                    "source_id": "source-main",
                    "fragment_id": "f1",
                    "code": "other",
                    "reason": "semantic_analysis_not_performed",
                },
                {
                    "source_id": "source-main",
                    "fragment_id": "f2",
                    "code": "other",
                    "reason": "semantic_analysis_not_performed",
                },
            ],
        },
        "findings": [],
    }


def test_exact_primary_partition_accepts_all_gaps() -> None:
    validate_report(base_report(), FRAGMENTS, primary_source_id="source-main")


def test_overlap_missing_or_unknown_fragment_is_rejected() -> None:
    report = base_report()
    report["coverage"]["reviewed_fragment_ids"] = ["f1"]
    with pytest.raises(ValueError, match="partition"):
        validate_report(report, FRAGMENTS, primary_source_id="source-main")


def test_quote_offsets_and_primary_basis_are_exact() -> None:
    report = base_report()
    report["coverage"] = {
        "status": "complete",
        "target_fragment_ids": ["f1", "f2"],
        "reviewed_fragment_ids": ["f1", "f2"],
        "gaps": [],
    }
    report["findings"] = [
        {
            "id": "finding",
            "ordinal": 1,
            "kind": "ambiguity",
            "title": "Retry",
            "problem": "Unbounded",
            "reason": "Different behavior",
            "question": "How many?",
            "priority": {"level": "medium", "rationale": "Testability"},
            "anchors": [
                {
                    "source_id": "source-main",
                    "document_id": "doc",
                    "fragment_id": "f1",
                    "quote": "Retry",
                    "quote_start": 0,
                    "quote_end": 5,
                    "location": FRAGMENTS["f1"]["location"],
                }
            ],
            "scope": ["f1"],
        }
    ]
    validate_report(report, FRAGMENTS, primary_source_id="source-main")
    report["findings"][0]["anchors"][0]["quote_end"] = 6
    with pytest.raises(ValueError, match="quote"):
        validate_report(report, FRAGMENTS, primary_source_id="source-main")
