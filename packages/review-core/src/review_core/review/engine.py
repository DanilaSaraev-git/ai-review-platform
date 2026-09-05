from __future__ import annotations

from typing import Any

from review_core.review.validation import validate_report


def build_unbound_coverage(
    source_id: str, target_fragment_ids: list[str], *, primary_partial: bool = False
) -> dict[str, Any]:
    if not target_fragment_ids:
        raise ValueError("Primary document has no usable target fragments.")
    gaps: list[dict[str, Any]] = [
        {
            "source_id": source_id,
            "fragment_id": fragment_id,
            "code": "other",
            "reason": "semantic_analysis_not_performed",
        }
        for fragment_id in target_fragment_ids
    ]
    if primary_partial:
        gaps.append(
            {
                "source_id": source_id,
                "fragment_id": None,
                "code": "source_partial",
                "reason": "primary_source_partial",
            }
        )
    return {
        "status": "partial",
        "target_fragment_ids": target_fragment_ids,
        "reviewed_fragment_ids": [],
        "gaps": gaps,
    }


class ReviewEngine:
    def validate(
        self, report: dict[str, Any], fragments: dict[str, dict[str, Any]], primary_source_id: str
    ) -> dict[str, Any]:
        validate_report(report, fragments, primary_source_id=primary_source_id)
        return report
