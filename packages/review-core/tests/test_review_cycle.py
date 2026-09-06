from copy import deepcopy

from review_core.application.review_cycle import (
    can_carry_decision,
    match_findings,
    same_review_conditions,
    same_source_texts,
)


def finding(identity: str, *, problem: str = "Не указано время", quote: str = "Ежедневно") -> dict:
    return {
        "id": identity,
        "kind": "ambiguity",
        "title": problem,
        "problem": problem,
        "reason": "Нельзя проверить",
        "question": "Когда?",
        "priority": {"level": "high", "rationale": "SLA"},
        "anchors": [
            {
                "source_id": "source-main",
                "fragment_id": identity + "-fragment",
                "quote": quote,
                "location": {"page": 1},
            }
        ],
        "scope": [],
    }


def test_match_survives_new_ids_and_page_moves() -> None:
    current = finding("new")
    current["anchors"][0]["location"] = {"page": 7}
    result = match_findings(
        [finding("old")],
        [current],
        previous_evidence_keys={"old": ("source-main|unique-fragment|0:10",)},
        current_evidence_keys={"new": ("source-main|unique-fragment|0:10",)},
    )
    assert [(m.previous_id, m.current_id, m.status) for m in result] == [("old", "new", "persisting")]


def test_duplicate_evidence_never_gets_arbitrary_identity() -> None:
    result = match_findings([finding("old-a"), finding("old-b")], [finding("new")])
    current = next(m for m in result if m.current_id)
    assert current.status == "uncertain"
    assert set(current.candidate_previous_ids) == {"old-a", "old-b"}
    assert not any(m.status == "persisting" for m in result)


def test_reworded_finding_is_candidate_without_automatic_transfer() -> None:
    result = match_findings([finding("old")], [finding("new", problem="Не задано точное время")])
    current = next(m for m in result if m.current_id)
    assert current.status == "uncertain"
    assert current.candidate_previous_ids == ("old",)


def test_new_and_absent_are_separate_records() -> None:
    result = match_findings([finding("old")], [finding("new", problem="Нет ключа", quote="Таблица заказов")])
    assert {(m.previous_id, m.current_id, m.status) for m in result} == {
        (None, "new", "new"),
        ("old", None, "not_detected"),
    }


def test_decision_transfer_requires_all_invariants() -> None:
    old, new = finding("old"), finding("new")
    assert can_carry_decision(old, new, same_sources=True, same_conditions=True, evidence_unchanged=True)
    assert not can_carry_decision(old, new, same_sources=False, same_conditions=True)
    assert not can_carry_decision(old, new, same_sources=True, same_conditions=False)
    new["reason"] = "Другое основание"
    assert not can_carry_decision(old, new, same_sources=True, same_conditions=True)


def test_identical_quotes_in_different_fragments_require_review() -> None:
    old, new = finding("old"), finding("new")
    result = match_findings([old], [new])
    assert all(m.status == "uncertain" for m in result)
    assert not can_carry_decision(old, new, same_sources=True, same_conditions=True)


def test_reused_fragment_ids_across_documents_do_not_establish_lineage() -> None:
    old, new = finding("same"), finding("same-new")
    new["anchors"][0]["fragment_id"] = old["anchors"][0]["fragment_id"]
    old["anchors"][0].update({"quote_start": 0, "quote_end": 9})
    new["anchors"][0].update({"quote_start": 0, "quote_end": 9})
    old["document_id"], new["document_id"] = "document-v1", "document-v2"

    result = match_findings(
        [old],
        [new],
        previous_evidence_keys={"same": ("source|fragment-v1|0:9",)},
        current_evidence_keys={"same-new": ("source|fragment-v2|0:9",)},
    )

    assert not any(item.status == "persisting" for item in result)


def test_same_occurrence_fallback_requires_same_document() -> None:
    old, new = finding("same"), finding("same-new")
    new["anchors"][0]["fragment_id"] = old["anchors"][0]["fragment_id"]
    old["anchors"][0].update({"quote_start": 0, "quote_end": 9})
    new["anchors"][0].update({"quote_start": 0, "quote_end": 9})
    old["document_id"] = new["document_id"] = "stored-document"

    result = match_findings([old], [new])

    assert any(item.status == "persisting" for item in result)


def test_repeated_missing_finding_remains_candidate_for_human_linking() -> None:
    old, new = finding("old"), finding("new")
    for item in (old, new):
        item.update(kind="missing", anchors=[], scope=["source-main-lines-1-3"])

    result = match_findings([old], [new])

    assert {(item.previous_id, item.current_id, item.status) for item in result} == {
        (None, "new", "uncertain"),
        ("old", None, "uncertain"),
    }


def test_context_text_role_and_order_are_material() -> None:
    sources = [
        {"role": "document", "ordinal": 0, "text": "A"},
        {"role": "context", "ordinal": 1, "text": "B"},
    ]
    assert same_source_texts(sources, deepcopy(sources))
    assert not same_source_texts(sources, [sources[1], sources[0]])
    changed = deepcopy(sources)
    changed[1]["text"] = "C"
    assert not same_source_texts(sources, changed)
    assert not same_source_texts([], [])


def test_condition_comparison_ignores_usage_but_not_model_or_profile() -> None:
    report = {
        "provenance": {
            "execution_snapshot": {"profile": {"digest": "abc"}},
            "model": {"model": "m", "safe_parameters": {"temperature": 0}, "usage": {"tokens": 10}},
        }
    }
    other = deepcopy(report)
    other["provenance"]["model"]["usage"] = {"tokens": 11}
    assert same_review_conditions(report, other)
    other["provenance"]["execution_snapshot"]["profile"]["digest"] = "def"
    assert not same_review_conditions(report, other)
    assert not same_review_conditions({}, {})
