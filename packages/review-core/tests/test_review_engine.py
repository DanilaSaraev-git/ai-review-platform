from review_core.review.engine import build_unbound_coverage


def test_unbound_deterministic_coverage_has_one_gap_per_target() -> None:
    coverage = build_unbound_coverage("source-main", ["f1", "f2", "f3"])
    assert coverage["reviewed_fragment_ids"] == []
    assert [gap["fragment_id"] for gap in coverage["gaps"]] == ["f1", "f2", "f3"]
    assert {gap["reason"] for gap in coverage["gaps"]} == {"semantic_analysis_not_performed"}


def test_partial_primary_adds_source_gap_without_replacing_partition() -> None:
    coverage = build_unbound_coverage("source-main", ["f1"], primary_partial=True)
    assert coverage["gaps"][0]["fragment_id"] == "f1"
    assert coverage["gaps"][-1] == {
        "source_id": "source-main",
        "fragment_id": None,
        "code": "source_partial",
        "reason": "primary_source_partial",
    }
