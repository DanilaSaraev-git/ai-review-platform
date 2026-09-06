from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from review_core.review import validation
from review_core.review.engine import MappingContext, ReviewEngine, ReviewFragment


def context() -> MappingContext:
    fragments = {}
    for fragment_id, source_id, text in [
        ("f1", "source-main", "Retry regularly. Retry."),
        ("f2", "source-main", "Finish."),
        ("c1", "source-context", "UTC."),
    ]:
        fragments[fragment_id] = ReviewFragment(
            id=fragment_id,
            source_id=source_id,
            document_id=f"document-{source_id}",
            source_name="synthetic.md",
            text=text,
            location={
                "kind": "text",
                "line_start": 1,
                "line_end": 1,
                "char_start": 0,
                "char_end": len(text),
            },
        )
    return MappingContext(
        run_id="run",
        report_id="report",
        created_at="2026-09-06T12:00:00Z",
        primary_source_id="source-main",
        target_fragment_ids=("f1", "f2"),
        fragments=fragments,
        provenance={},
    )


def compact() -> dict[str, Any]:
    return {
        "summary": "Synthetic review",
        "coverage": {"reviewed_fragment_ids": ["f1", "f2"], "unreviewed": [], "source_gaps": []},
        "findings": [
            {
                "kind": "ambiguity",
                "title": "Retry interval",
                "problem": "Unspecified interval",
                "reason": "Different behavior",
                "question": "How often?",
                "priority": {"level": "medium", "rationale": "Testability"},
                "anchors": [{"source_id": "source-main", "fragment_id": "f1", "quote": "regularly"}],
                "scope": [],
            }
        ],
        "limitations": [],
    }


def anchor(value: dict[str, Any]) -> dict[str, Any]:
    return value["findings"][0]["anchors"][0]


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: anchor(value).update(quote="CANARY_PRIVATE_TEXT"), "anchor_quote_not_found"),
        (lambda value: anchor(value).update(quote="Retry"), "anchor_quote_ambiguous"),
        (lambda value: anchor(value).update(quote=""), "anchor_quote_invalid"),
        (lambda value: anchor(value).update(fragment_id="CANARY_PRIVATE_TEXT"), "anchor_fragment_unknown"),
        (lambda value: anchor(value).update(source_id="CANARY_PRIVATE_TEXT"), "anchor_source_mismatch"),
        (
            lambda value: value["coverage"]["reviewed_fragment_ids"].append("f1"),
            "coverage_partition_duplicates",
        ),
        (lambda value: value["coverage"]["reviewed_fragment_ids"].remove("f2"), "coverage_partition_inexact"),
        (
            lambda value: value["coverage"]["source_gaps"].append(
                {
                    "source_id": "wrong",
                    "fragment_id": "c1",
                    "code": "other",
                    "reason": "unavailable",
                }
            ),
            "coverage_gap_source_mismatch",
        ),
        (lambda value: value["findings"][0].update(kind="missing"), "missing_finding_scope_invalid"),
        (lambda value: value["findings"][0].update(anchors=[]), "finding_anchor_required"),
        (lambda value: value["findings"][0].update(scope=["c1"]), "finding_scope_invalid"),
        (
            lambda value: anchor(value).update(source_id="source-context", fragment_id="c1", quote="UTC"),
            "finding_primary_basis_missing",
        ),
        (lambda value: value.update(unexpected="CANARY_PRIVATE_TEXT"), "compact_fields_invalid"),
        (lambda value: value.update(coverage=[]), "compact_output_shape_invalid"),
        (lambda value: value["coverage"].update(unreviewed={}), "compact_coverage_shape_invalid"),
        (lambda value: value["coverage"]["unreviewed"].append([]), "compact_unreviewed_shape_invalid"),
        (lambda value: value["coverage"]["source_gaps"].append([]), "compact_source_gap_shape_invalid"),
        (lambda value: value["findings"].append([]), "compact_finding_shape_invalid"),
        (lambda value: value["findings"][0].update(priority=[]), "compact_priority_shape_invalid"),
        (lambda value: value["findings"][0].update(scope={}), "compact_finding_basis_shape_invalid"),
        (lambda value: value["findings"][0]["anchors"].append([]), "compact_anchor_shape_invalid"),
    ],
)
def test_mapper_preserves_a_safe_semantic_reason(mutate: Callable[[dict[str, Any]], None], code: str) -> None:
    output = compact()
    mutate(output)

    with pytest.raises(ValueError) as caught:
        ReviewEngine().map_model_output(output, context=context())

    assert isinstance(caught.value, validation.ReviewSemanticValidationError)
    assert caught.value.code == code
    assert "CANARY_PRIVATE_TEXT" not in str(caught.value)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda value: anchor(value).update(quote_end=99), "anchor_quote_offsets_invalid"),
        (
            lambda value: value["coverage"].update(
                reviewed_fragment_ids=["f2"],
                gaps=[
                    {
                        "source_id": "source-main",
                        "fragment_id": "f1",
                        "code": "other",
                        "reason": "skipped",
                    }
                ],
                status="partial",
            ),
            "anchor_primary_unreviewed",
        ),
        (lambda value: anchor(value)["location"].update(line_start=0), "text_location_invalid"),
        (
            lambda value: anchor(value).update(location={"kind": "pdf", "page": 0, "rects": []}),
            "pdf_location_invalid",
        ),
        (
            lambda value: anchor(value).update(location={"kind": "pdf", "page": 1, "rects": [[0, 0, 2, 2]]}),
            "pdf_rectangle_invalid",
        ),
        (lambda value: anchor(value).update(location={"kind": "other"}), "source_location_unknown"),
        (
            lambda value: value["coverage"].update(
                target_fragment_ids=["f1", "c1"],
                reviewed_fragment_ids=["f1", "c1"],
            ),
            "coverage_target_invalid",
        ),
        (
            lambda value: value["coverage"]["gaps"].append(
                {
                    "source_id": "source-context",
                    "fragment_id": None,
                    "code": "other",
                    "reason": "skipped",
                }
            ),
            "coverage_complete_has_gaps",
        ),
        (lambda value: value["coverage"].update(status="partial"), "coverage_partial_without_gaps"),
        (
            lambda value: value["findings"].append(deepcopy(value["findings"][0])),
            "finding_identity_duplicate",
        ),
    ],
)
def test_report_validation_preserves_a_safe_semantic_reason(
    mutate: Callable[[dict[str, Any]], None], code: str
) -> None:
    report = ReviewEngine().map_model_output(compact(), context=context())
    mutate(report)
    fragments = {
        item.id: {"source_id": item.source_id, "document_id": item.document_id, "text": item.text}
        for item in context().fragments.values()
    }

    with pytest.raises(ValueError) as caught:
        validation.validate_report(report, fragments, primary_source_id="source-main")

    assert isinstance(caught.value, validation.ReviewSemanticValidationError)
    assert caught.value.code == code


def test_semantic_diagnostic_cannot_contain_an_unregistered_reason_or_message() -> None:
    with pytest.raises(ValueError, match="unknown review semantic validation code") as caught:
        validation.ReviewSemanticValidationError("CANARY_PRIVATE_TEXT")
    assert "CANARY_PRIVATE_TEXT" not in str(caught.value)
    with pytest.raises(TypeError):
        validation.ReviewSemanticValidationError("anchor_quote_not_found", "CANARY_PRIVATE_TEXT")
