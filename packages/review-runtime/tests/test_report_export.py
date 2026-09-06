import io
import json
from copy import deepcopy
from pathlib import Path

import pdfplumber
from review_runtime.report_export import render_review_pdf

ROOT = Path(__file__).resolve().parents[3]


def snapshot() -> dict:
    report = json.loads((ROOT / "contracts/review-platform/v1/examples/http/report.json").read_text())
    states = json.loads((ROOT / "contracts/review-platform/v1/examples/http/finding-states.json").read_text())
    states["items"][0]["decision"].update(
        status="confirmed",
        revision=1,
        reason="Нужно уточнить время <запуска> & часовой пояс",
        actor={"id": "test-actor", "display_name": "Тестовый аналитик"},
        decided_at="2026-09-06T10:00:00Z",
    )
    return {
        "exported_at": "2026-09-06T11:00:00Z",
        "family": {"name": "Синтетический поток заказов"},
        "version": {"version_number": 2, "filename": "orders-v2.md"},
        "run": {"id": report["run_id"], "created_at": "2026-09-06T09:00:00Z"},
        "report": report,
        "finding_states": states,
        "cycle": {"status": "ready", "baseline_run_id": None, "entries": [], "limitations": []},
        "previous_findings": {},
    }


def test_pdf_has_cyrillic_current_decision_and_escaped_input() -> None:
    value = snapshot()
    before = deepcopy(value)
    result = render_review_pdf(value)
    assert result.startswith(b"%PDF-")
    with pdfplumber.open(io.BytesIO(result)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Синтетический поток заказов" in text
    assert "Нужно уточнить время <запуска> & часовой пояс" in text
    assert "Подтверждено" in text
    assert "2026-09-06T11:00:00Z" in text
    assert value == before


def test_long_report_is_paginated_without_dropping_last_finding() -> None:
    value = snapshot()
    template = value["report"]["findings"][0]
    value["report"]["findings"] = [
        dict(deepcopy(template), id=f"finding-{i}", ordinal=i, title=f"Замечание номер {i}")
        for i in range(1, 25)
    ]
    value["report"]["findings"][-1]["reason"] = "Последний фрагмент " + ("длинное объяснение " * 1000)
    with pdfplumber.open(io.BytesIO(render_review_pdf(value))) as pdf:
        assert len(pdf.pages) > 3
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        assert "Замечание номер 24" in text
        assert "Последний фрагмент" in text
        # Words may be separated by line/page breaks in extracted PDF text.
        assert text.count("длинное") == 1000
        assert text.count("объяснение") == 1000


def test_absent_issue_and_partial_coverage_are_explicit() -> None:
    value = snapshot()
    old = deepcopy(value["report"]["findings"][0])
    old["id"] = "old"
    value["previous_findings"] = {"old": old}
    value["report"]["coverage"]["status"] = "partial"
    value["cycle"]["entries"] = [
        {
            "issue_id": "issue-old",
            "previous_finding_id": "old",
            "current_finding_id": None,
            "status": "not_checked",
            "previous_decision": None,
            "resolution": {"status": "open"},
            "decision_carried": False,
        }
    ]
    with pdfplumber.open(io.BytesIO(render_review_pdf(value))) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert "Частичная проверка" in text
    assert "Не удалось подтвердить" in text
    assert "Ранее найденные замечания" in text
