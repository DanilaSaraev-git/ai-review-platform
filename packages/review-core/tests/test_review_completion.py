from review_core.application.review_completion import completion_state


def test_context_and_missing_decisions_block_completion():
    cycle = {"status": "ready", "limitations": [], "entries": []}
    report = {"coverage": {"status": "complete"}, "findings": [{"id": "f"}]}
    assert not completion_state(cycle, report, {})[0]
    assert not completion_state(cycle, report, {"f": {"status": "needs_context", "revision": 1}})[0]
    assert completion_state(cycle, report, {"f": {"status": "rejected", "revision": 1}})[0]


def test_absence_partial_and_uncertainty_are_not_success():
    report = {"coverage": {"status": "complete"}, "findings": []}
    entry = {"current_finding_id": None, "status": "not_detected", "resolution": {"status": "open"}}
    cycle = {"status": "ready", "limitations": [], "entries": [entry]}
    assert not completion_state(cycle, report, {})[0]
    entry["resolution"]["status"] = "resolved"
    assert completion_state(cycle, report, {})[0]
    report["coverage"]["status"] = "partial"
    assert not completion_state(cycle, report, {})[0]
    report["coverage"]["status"] = "complete"
    entry["status"] = "uncertain"
    assert not completion_state(cycle, report, {})[0]


def test_digest_changes_when_a_decision_is_edited():
    report = {"coverage": {"status": "complete"}, "findings": [{"id": "f"}]}
    cycle = {"status": "ready", "limitations": [], "entries": []}
    first = completion_state(cycle, report, {"f": {"status": "rejected", "revision": 1}})
    second = completion_state(cycle, report, {"f": {"status": "rejected", "revision": 2}})
    assert first[1] != second[1]
