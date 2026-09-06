"""Render an already-consistent review snapshot without DB, network or LLM I/O."""

from __future__ import annotations

import io
import re
from collections import Counter
from pathlib import Path
from threading import Lock
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.lib.styles import ParagraphStyle  # type: ignore[import-untyped]
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.pdfbase import pdfmetrics  # type: ignore[import-untyped]
from reportlab.pdfbase.ttfonts import TTFont  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
)

_FONT_LOCK = Lock()
_ASSETS = Path(__file__).with_name("fonts")
_RED = colors.HexColor("#C52C35")
_INK = colors.HexColor("#24272C")
_MUTED = colors.HexColor("#657080")
DECISIONS = {
    "unreviewed": "Не рассмотрено",
    "confirmed": "Подтверждено",
    "rejected": "Отклонено",
    "needs_context": "Нужен контекст",
}
CHANGES = {
    "new": "Новое",
    "persisting": "Сохранилось",
    "not_detected": "Больше не обнаружено",
    "uncertain": "Нужна проверка связи",
    "not_checked": "Не удалось подтвердить",
    "reappeared": "Обнаружено снова",
}
PRIORITIES = {"high": "Высокий", "medium": "Средний", "low": "Низкий"}
LIMITATIONS = {
    "review_conditions_changed": (
        "Условия проверки изменились: прежние решения требуют повторной оценки человеком."
    ),
    "review_coverage_incomplete": (
        "Проверка охватила документ не полностью: отсутствие замечания не подтверждает исправление."
    ),
    "comparison_failed": "Сравнение проверок не выполнено; статусы изменений недоступны.",
    "review_report_unavailable": "Результат проверки ещё недоступен для сравнения.",
}


def _safe(value: Any) -> str:
    # ReportLab Paragraph accepts markup; checked documents never supply it.
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(value if value is not None else ""))
    return escape(value).replace("\n", "<br/>")


def _fonts() -> None:
    with _FONT_LOCK:
        if "NumbatBody" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("NumbatBody", str(_ASSETS / "DejaVuSans.ttf")))
            pdfmetrics.registerFont(TTFont("NumbatBold", str(_ASSETS / "DejaVuSans-Bold.ttf")))
            pdfmetrics.registerFontFamily("NumbatBody", normal="NumbatBody", bold="NumbatBold")


def effective_decision(state: dict[str, Any] | None, entry: dict[str, Any] | None) -> dict[str, Any]:
    decision = (state or {}).get("decision", {})
    if decision.get("revision", 0) > 0 or decision.get("status", "unreviewed") != "unreviewed":
        return dict(decision)
    if entry and entry.get("decision_carried") and entry.get("previous_decision"):
        return dict(entry["previous_decision"])
    return dict(decision) if decision else {"status": "unreviewed"}


def render_review_pdf(snapshot: dict[str, Any]) -> bytes:
    """Input is the server's coherent snapshot; this function never mutates it.

    Keys: exported_at, family, version, run, report, finding_states {items},
    cycle, previous_findings {finding_id: Finding}. Canonical report stays intact.
    """
    _fonts()
    buffer = io.BytesIO()
    family = snapshot.get("family", {})
    version = snapshot.get("version", {})
    run = snapshot["run"]
    report = snapshot["report"]
    cycle = snapshot.get("cycle") or {"status": "unavailable", "entries": [], "limitations": []}
    title = family.get("name") or version.get("filename") or "Документ"
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=21 * mm,
        leftMargin=21 * mm,
        topMargin=26 * mm,
        bottomMargin=22 * mm,
        title=str(title),
        author="Numbat",
        pageCompression=1,
    )
    body = ParagraphStyle(
        "body",
        fontName="NumbatBody",
        fontSize=9,
        leading=14,
        textColor=_INK,
        spaceAfter=7,
        splitLongWords=True,
    )
    muted = ParagraphStyle("muted", parent=body, fontSize=8, leading=12, textColor=_MUTED)
    heading = ParagraphStyle(
        "heading",
        parent=body,
        fontName="NumbatBold",
        fontSize=14,
        leading=19,
        spaceBefore=16,
        spaceAfter=9,
        keepWithNext=True,
    )
    finding_heading = ParagraphStyle("finding", parent=heading, fontSize=11, leading=16, spaceBefore=13)
    hero = ParagraphStyle("hero", parent=heading, fontSize=22, leading=28, spaceBefore=3, spaceAfter=13)
    quote = ParagraphStyle(
        "quote",
        parent=body,
        backColor=colors.HexColor("#F3F4F6"),
        borderPadding=8,
        leftIndent=9,
        rightIndent=9,
        spaceBefore=5,
        spaceAfter=12,
    )
    story: list[Any] = []

    def paragraph(value: Any, style: Any = body) -> None:
        if value is not None and str(value).strip():
            story.append(Paragraph(_safe(value), style))

    def field(label: str, value: Any, style: Any = body) -> None:
        if value is not None and str(value).strip():
            story.append(Paragraph(f"<b>{_safe(label)}</b> {_safe(value)}", style))

    def show_decision(decision: dict[str, Any], *, label: str = "Решение:") -> None:
        field(label, DECISIONS.get(decision.get("status", "unreviewed"), "Не рассмотрено"))
        field("Основание решения:", decision.get("reason"))
        field("Согласованное уточнение:", decision.get("resolution"))
        actor = decision.get("actor") or {}
        signature = " · ".join(str(v) for v in (actor.get("display_name"), decision.get("decided_at")) if v)
        paragraph(signature, muted)

    def show_cycle(entry: dict[str, Any] | None) -> None:
        if not entry:
            return
        field("Изменение:", CHANGES.get(str(entry.get("status", "")), entry.get("status")))
        resolution = entry.get("resolution") or {}
        if resolution.get("status") == "resolved":
            field("Исправление:", "Подтверждено аналитиком")
        else:
            field("Исправление:", "Не подтверждено", muted)
        if resolution.get("revision", 0) > 0 or resolution.get("status") == "resolved":
            field("Пояснение:", resolution.get("reason"))
            actor = resolution.get("actor") or {}
            paragraph(
                " · ".join(str(v) for v in (actor.get("display_name"), resolution.get("decided_at")) if v),
                muted,
            )
        if entry.get("previous_finding_id"):
            field("Предыдущее замечание:", entry["previous_finding_id"], muted)
        if entry.get("previous_run_id"):
            field("Предыдущая проверка:", entry["previous_run_id"], muted)

    def show_finding(
        finding: dict[str, Any],
        entry: dict[str, Any] | None,
        state: dict[str, Any] | None,
        *,
        previous: bool = False,
    ) -> None:
        paragraph(f"{finding.get('ordinal', '')}. {finding.get('title', 'Замечание')}", finding_heading)
        field("Приоритет:", PRIORITIES.get(finding.get("priority", {}).get("level"), "Не задан"))
        field("Основание приоритета:", finding.get("priority", {}).get("rationale"), muted)
        if finding.get("scope"):
            field("Область проверки:", ", ".join(str(item) for item in finding["scope"]), muted)
        if not finding.get("anchors"):
            paragraph("Точная цитата отсутствует: замечание относится к области проверки.", muted)
        for anchor in finding.get("anchors", []):
            location = anchor.get("location", {})
            if location.get("kind") == "pdf":
                place = f"стр. {location.get('page', location.get('page_number', ''))}"
            else:
                place = f"строка {location.get('line_start', '')}"
            paragraph(" · ".join(v for v in (anchor.get("source_name", ""), place) if v), muted)
            paragraph(anchor.get("quote"), quote)
        field("Проблема:", finding.get("problem"))
        field("Причина:", finding.get("reason"))
        field("Вопрос:", finding.get("question"))
        if previous:
            show_decision(
                (entry or {}).get("previous_decision") or {"status": "unreviewed"}, label="Прежнее решение:"
            )
        else:
            show_decision(effective_decision(state, entry))
            if entry and entry.get("previous_decision"):
                if (
                    entry.get("decision_carried")
                    and (state or {}).get("decision", {}).get("revision", 0) == 0
                ):
                    paragraph("Сохранено из предыдущей проверки: основания и условия не изменились.", muted)
                elif not entry.get("decision_carried"):
                    show_decision(entry["previous_decision"], label="Прежнее решение (для пересмотра):")
        show_cycle(entry)
        story.append(
            HRFlowable(width="100%", thickness=0.45, color=colors.HexColor("#DDE1E7"), spaceBefore=8)
        )

    entries = cycle.get("entries", [])
    by_finding = {e["current_finding_id"]: e for e in entries if e.get("current_finding_id")}
    states = {s["finding_id"]: s for s in snapshot.get("finding_states", {}).get("items", [])}
    findings = report.get("findings", [])
    counts = Counter(
        effective_decision(states.get(f["id"]), by_finding.get(f["id"])).get("status", "unreviewed")
        for f in findings
    )
    paragraph("Отчёт проверки", muted)
    paragraph(title, hero)
    field("Версия:", version.get("version_number", cycle.get("version_number", 1)))
    field("Файл:", version.get("filename") or version.get("document", {}).get("filename"))
    field("Проверка:", run.get("id"), muted)
    field("Результат опубликован:", report.get("created_at"), muted)
    field("Состояние на:", snapshot.get("exported_at"), muted)
    if cycle.get("baseline_run_id"):
        field("Сравнение с проверкой:", cycle["baseline_run_id"], muted)
    paragraph("Сводка", heading)
    paragraph(report.get("summary"))
    field("Всего замечаний в этой проверке:", len(findings))
    for status, label in DECISIONS.items():
        field(f"{label}:", counts[status])
    absent = [entry for entry in entries if not entry.get("current_finding_id")]
    if absent:
        field("Ранее найденных замечаний вне текущего результата:", len(absent))
    if report.get("coverage", {}).get("status") != "complete":
        paragraph("Частичная проверка. Непросмотренные фрагменты не считаются свободными от замечаний.")
    for gap in report.get("coverage", {}).get("gaps", []):
        field("Ограничение охвата:", gap.get("message") or gap.get("reason") or str(gap))
    if cycle.get("status") != "ready":
        paragraph("Сопоставление недоступно. Исправления по отсутствию замечаний не подтверждены.")
    for limitation in [*report.get("limitations", []), *cycle.get("limitations", [])]:
        paragraph(LIMITATIONS.get(str(limitation), limitation), muted)
    paragraph("Замечания текущей проверки", heading)
    if not findings:
        paragraph(
            "В опубликованном результате замечаний нет. Это не является утверждением готовности документа."
        )
    for finding in findings:
        show_finding(finding, by_finding.get(finding["id"]), states.get(finding["id"]))
    if absent:
        paragraph("Ранее найденные замечания", heading)
        paragraph("Отсутствие в новом результате само по себе не подтверждает исправление.", muted)
        for entry in absent:
            old_id = entry.get("previous_finding_id") or entry.get("origin_finding_id")
            old = snapshot.get("previous_findings", {}).get(old_id)
            if old:
                show_finding(old, entry, None, previous=True)
            else:
                field("Замечание:", old_id or entry.get("issue_id"))
                show_cycle(entry)
    def page(canvas: Any, _document: Any) -> None:
        canvas.saveState()
        canvas.setFillColor(_RED)
        canvas.rect(0, A4[1] - 4 * mm, A4[0], 4 * mm, fill=1, stroke=0)
        canvas.setFont("NumbatBold", 10)
        canvas.drawImage(
            str(Path(__file__).with_name("assets") / "numbat-icon.png"),
            21 * mm,
            A4[1] - 20 * mm,
            width=8 * mm,
            height=8 * mm,
            preserveAspectRatio=True,
            mask="auto",
        )
        canvas.drawString(31 * mm, A4[1] - 17 * mm, "Numbat")
        canvas.setFillColor(_MUTED)
        canvas.setFont("NumbatBody", 8)
        canvas.drawString(
            21 * mm,
            17 * mm,
            "Состояние на дату выгрузки. Окончательное решение принимает человек.",
        )
        canvas.drawRightString(A4[0] - 21 * mm, 12 * mm, f"Страница {canvas.getPageNumber()}")
        canvas.drawString(21 * mm, 12 * mm, "Отчёт проверки")
        canvas.restoreState()

    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
