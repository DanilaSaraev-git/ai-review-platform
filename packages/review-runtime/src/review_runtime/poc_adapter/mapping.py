from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from jsonschema import Draft202012Validator, FormatChecker
from review_core.canonical import digest_value

from review_runtime.poc_adapter.validation import validate_mapped_view

NAMESPACE = UUID("7edc6db1-81aa-5c6f-90d7-f46d9967ca53")


def identity(run_digest: str, kind: str, legacy_id: str) -> str:
    return str(uuid5(NAMESPACE, f"{run_digest}:{kind}:{legacy_id}"))


def _location(fragment: dict[str, Any], raw: dict[str, Any] | None) -> dict[str, Any]:
    location = fragment.get("location", {})
    if "line_start" in location:
        return {
            "kind": "text",
            "line_start": location["line_start"],
            "line_end": location["line_end"],
            "char_start": 0,
            "char_end": len(fragment["text"]),
        }
    page_number = location.get("page")
    pages = [] if raw is None else raw.get("pages", [])
    page = next((item for item in pages if item.get("page_number") == page_number), None)
    bbox = location.get("bbox")
    if page is None or not bbox or page.get("width", 0) <= 0 or page.get("height", 0) <= 0:
        raise ValueError("legacy_location_imprecise")
    left, top, right, bottom = bbox
    width, height = page["width"], page["height"]
    rect = [left / width, top / height, right / width, bottom / height]
    if any(value < 0 or value > 1 for value in rect):
        raise ValueError("legacy_location_imprecise")
    return {
        "kind": "pdf",
        "page": page_number,
        "rects": [rect],
        "table": location.get("table"),
        "row": location.get("row"),
    }


def map_legacy_run(
    *,
    manifest: dict[str, Any],
    bundle: dict[str, Any],
    profile: dict[str, Any],
    report: dict[str, Any],
    raw_by_source: dict[str, dict[str, Any]],
    run_digest: str,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    source_rows = manifest.get("sources", [])
    if sum(source.get("role") == "document" for source in source_rows) != 1:
        raise ValueError("legacy run must have exactly one primary source")
    source_map: dict[str, dict[str, Any]] = {}
    projected_sources: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    fragments: list[dict[str, Any]] = []
    fragment_map: dict[str, dict[str, Any]] = {}
    legacy_fragments = bundle.get("fragments", [])
    for source in source_rows:
        source_id = source["id"]
        document_id = identity(run_digest, "document", source_id)
        owned = [fragment for fragment in legacy_fragments if fragment.get("source_id") == source_id]
        mapped_ids: list[str] = []
        for ordinal, fragment in enumerate(owned, start=1):
            fragment_id = identity(run_digest, "fragment", fragment["id"])
            mapped = {
                "id": fragment_id,
                "source_id": source_id,
                "document_id": document_id,
                "ordinal": ordinal,
                "kind": fragment["kind"],
                "text": fragment["text"],
                "content_sha256": hashlib.sha256(fragment["text"].encode()).hexdigest(),
                "location": _location(fragment, raw_by_source.get(source_id)),
            }
            fragments.append(mapped)
            fragment_map[fragment["id"]] = mapped
            mapped_ids.append(fragment_id)
        status = source["status"]
        parser = source.get("parser")
        projected = {
            "source_id": source_id,
            "document_id": document_id,
            "role": source["role"],
            "status": status,
            "sha256": source.get("sha256"),
            "parser": None
            if parser is None
            else {
                "name": parser["name"],
                "version": str(parser["version"]),
                "settings_digest": digest_value(parser.get("settings", {})),
            },
            "fragment_ids": mapped_ids,
        }
        source_map[source_id] = projected
        projected_sources.append(projected)
        if status == "unavailable":
            diagnostics.append(
                {
                    "code": "legacy_source_unavailable",
                    "entity_kind": "source",
                    "entity_id": source_id,
                    "message": "A legacy context source was unavailable.",
                }
            )
    primary = next(source for source in projected_sources if source["role"] == "document")
    target = list(primary["fragment_ids"])
    if not target:
        raise ValueError("legacy primary source has no usable fragments")
    reviewed = [
        fragment_map[legacy]["id"]
        for legacy in report.get("coverage", {}).get("reviewed_fragment_ids", [])
        if legacy in fragment_map and fragment_map[legacy]["source_id"] == primary["source_id"]
    ]
    gaps = []
    for item in report.get("coverage", {}).get("unreviewed", []):
        legacy_id = item.get("fragment_id")
        fragment = fragment_map.get(legacy_id)
        if fragment and fragment["source_id"] == primary["source_id"]:
            gaps.append(
                {
                    "source_id": primary["source_id"],
                    "fragment_id": fragment["id"],
                    "code": "other",
                    "reason": item.get("reason") or "legacy_unreviewed",
                }
            )
    if primary["status"] == "partial":
        gaps.append(
            {
                "source_id": primary["source_id"],
                "fragment_id": None,
                "code": "source_partial",
                "reason": "primary_source_partial",
            }
        )
    for source in projected_sources:
        if source["role"] == "context" and source["status"] == "unavailable":
            gaps.append(
                {
                    "source_id": source["source_id"],
                    "fragment_id": None,
                    "code": "source_unavailable",
                    "reason": "legacy_context_unavailable",
                }
            )
    mapped_findings = []
    finding_states = []
    for ordinal, finding in enumerate(report.get("findings", []), start=1):
        finding_id = identity(run_digest, "finding", finding["id"])
        anchors = []
        for anchor in finding.get("anchors", []):
            fragment = fragment_map.get(anchor.get("fragment_id"))
            source = source_map.get(anchor.get("source_id"))
            if fragment is None or source is None or fragment["source_id"] != source["source_id"]:
                raise ValueError("legacy anchor references an unknown fragment")
            quote = anchor.get("quote", "")
            positions: list[int] = []
            cursor = 0
            while True:
                offset = fragment["text"].find(quote, cursor)
                if offset < 0:
                    break
                positions.append(offset)
                cursor = offset + max(1, len(quote))
            if len(positions) != 1:
                raise ValueError("legacy_quote_not_found" if not positions else "legacy_quote_ambiguous")
            anchors.append(
                {
                    "source_id": source["source_id"],
                    "document_id": source["document_id"],
                    "fragment_id": fragment["id"],
                    "quote": quote,
                    "quote_start": positions[0],
                    "quote_end": positions[0] + len(quote),
                    "location": fragment["location"],
                }
            )
        scope = []
        for legacy_id in finding.get("scope", []):
            fragment = fragment_map.get(legacy_id)
            if fragment is None or fragment["source_id"] != primary["source_id"]:
                raise ValueError("legacy finding scope is invalid")
            scope.append(fragment["id"])
        mapped_findings.append(
            {
                "id": finding_id,
                "legacy_id": finding["id"],
                "ordinal": ordinal,
                "kind": finding["kind"],
                "title": finding["title"],
                "problem": finding["problem"],
                "reason": finding["reason"],
                "question": finding["question"],
                "priority": {
                    "level": finding["priority"],
                    "rationale": finding["priority_reason"],
                },
                "anchors": anchors,
                "scope": scope,
            }
        )
        finding_states.append(
            {
                "finding_id": finding_id,
                "decision_status": "unreviewed",
                "decision_revision": 0,
                "actor": None,
                "reason": None,
                "resolution": None,
                "decided_at": None,
            }
        )
        if finding.get("status") != "unreviewed" or finding.get("human_review") is not None:
            diagnostics.append(
                {
                    "code": "legacy_human_state_unrepresentable",
                    "entity_kind": "human_state",
                    "entity_id": finding["id"],
                    "message": "Legacy human state cannot be attributed safely.",
                }
            )
    generation = report.get("generation", {})
    mode = generation.get("mode")
    mapped_mode = "deterministic_legacy" if mode == "demo_fixture" else "agent"
    if generation.get("agent") == "unknown" and generation.get("model") == "unknown":
        mapped_mode = "unknown"
    coverage_status = "complete" if set(reviewed) == set(target) and not gaps else "partial"
    view = {
        "schema_version": "poc-import-view.v1",
        "mapping_status": "complete" if not diagnostics and coverage_status == "complete" else "partial",
        "adapter": {
            "id": "feature-001-poc-v1",
            "version": "1.0.0",
            "legacy_schema_version": 1,
            "legacy_run_digest": run_digest,
        },
        "run_id": identity(run_digest, "run", manifest["run_id"]),
        "report_id": identity(run_digest, "report", manifest["run_id"]),
        "sources": projected_sources,
        "fragments": fragments,
        "coverage": {
            "status": coverage_status,
            "target_fragment_ids": target,
            "reviewed_fragment_ids": reviewed,
            "gaps": gaps,
        },
        "findings": mapped_findings,
        "finding_states": finding_states,
        "provenance": {
            "profile": {
                "name": profile["name"],
                "version": profile["version"],
                "role": profile["role"],
                "goal": profile["goal"],
                "checks": profile["checks"],
                "semantic_digest": digest_value(
                    {key: profile[key] for key in ("name", "version", "role", "goal", "checks")}
                ),
            },
            "generation": {
                "mode": mapped_mode,
                "agent": str(generation.get("agent") or "unknown"),
                "model": str(generation.get("model") or "unknown"),
                "model_version": str(generation.get("model_version") or "unknown"),
            },
            "limitations": report.get("limitations", []),
        },
        "diagnostics": diagnostics,
    }
    if schema_path is None:
        schema_path = (
            Path(__file__).resolve().parents[5]
            / "specs/003-backend-implementation/contracts/poc-import-view.v1.schema.json"
        )
    import json

    schema = json.loads(schema_path.read_text())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(view))
    if errors:
        raise ValueError("mapped legacy view does not satisfy the closed schema")
    validate_mapped_view(view)
    return view
