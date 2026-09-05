from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from review_core.ports.models import GenerationRequest, JsonValue, ModelProfileSnapshot
from review_core.review.prompt import build_review_generation_request
from review_core.review.validation import resolve_unique_quote_offset, validate_report


@dataclass(frozen=True, slots=True)
class ReviewFragment:
    id: str
    source_id: str
    document_id: str
    source_name: str
    text: str
    location: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.id, self.source_id, self.document_id, self.source_name, self.text)
        ):
            raise ValueError("review fragment identity and text are required")


@dataclass(frozen=True, slots=True)
class MappingContext:
    run_id: str
    report_id: str
    created_at: str
    primary_source_id: str
    target_fragment_ids: tuple[str, ...]
    fragments: Mapping[str, ReviewFragment]
    provenance: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (self.run_id, self.report_id, self.created_at, self.primary_source_id)
        ):
            raise ValueError("mapping context identity is required")
        if not self.target_fragment_ids:
            raise ValueError("mapping context needs primary target fragments")
        if len(self.target_fragment_ids) != len(set(self.target_fragment_ids)):
            raise ValueError("mapping context target fragments must be unique")
        if any(key != fragment.id for key, fragment in self.fragments.items()):
            raise ValueError("mapping context fragment key does not match its identity")


def _require_exact_fields(value: Mapping[str, Any], fields: set[str], *, label: str) -> None:
    if set(value) != fields:
        raise ValueError(f"compact {label} fields do not match the model-output contract")


def _validate_compact_shape(value: Mapping[str, Any]) -> None:
    _require_exact_fields(value, {"summary", "coverage", "findings", "limitations"}, label="output")
    coverage = value.get("coverage")
    findings = value.get("findings")
    if not isinstance(coverage, Mapping) or not isinstance(findings, list):
        raise ValueError("compact output has an invalid coverage or findings shape")
    _require_exact_fields(
        coverage,
        {"reviewed_fragment_ids", "unreviewed", "source_gaps"},
        label="coverage",
    )
    if not all(isinstance(coverage.get(key), list) for key in coverage):
        raise ValueError("compact coverage fields must be arrays")
    for item in coverage["unreviewed"]:
        if not isinstance(item, Mapping):
            raise ValueError("compact unreviewed entry must be an object")
        _require_exact_fields(item, {"fragment_id", "reason"}, label="unreviewed entry")
    for item in coverage["source_gaps"]:
        if not isinstance(item, Mapping):
            raise ValueError("compact source gap must be an object")
        _require_exact_fields(
            item,
            {"source_id", "fragment_id", "code", "reason"},
            label="source gap",
        )
    finding_fields = {
        "kind",
        "title",
        "problem",
        "reason",
        "question",
        "priority",
        "anchors",
        "scope",
    }
    for finding in findings:
        if not isinstance(finding, Mapping):
            raise ValueError("compact finding must be an object")
        _require_exact_fields(finding, finding_fields, label="finding")
        priority = finding["priority"]
        if not isinstance(priority, Mapping):
            raise ValueError("compact priority must be an object")
        _require_exact_fields(priority, {"level", "rationale"}, label="priority")
        if not isinstance(finding["anchors"], list) or not isinstance(finding["scope"], list):
            raise ValueError("compact finding anchors and scope must be arrays")
        for anchor in finding["anchors"]:
            if not isinstance(anchor, Mapping):
                raise ValueError("compact anchor must be an object")
            _require_exact_fields(anchor, {"source_id", "fragment_id", "quote"}, label="anchor")


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
    def prepare_generation_request(
        self,
        *,
        review_input: Mapping[str, JsonValue],
        skill_instructions: str,
        request_id: str,
        work_item_id: str,
        response_schema: dict[str, JsonValue],
        model_profile: ModelProfileSnapshot,
        max_input_utf8_bytes: int,
        max_output_tokens: int,
        timeout_seconds: float,
        temperature: float | None = None,
    ) -> GenerationRequest:
        return build_review_generation_request(
            review_input=review_input,
            skill_instructions=skill_instructions,
            request_id=request_id,
            work_item_id=work_item_id,
            response_schema=response_schema,
            model_profile=model_profile,
            max_input_utf8_bytes=max_input_utf8_bytes,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )

    def validate(
        self, report: dict[str, Any], fragments: dict[str, dict[str, Any]], primary_source_id: str
    ) -> dict[str, Any]:
        validate_report(report, fragments, primary_source_id=primary_source_id)
        return report

    def map_model_output(
        self,
        model_output: dict[str, Any],
        *,
        context: MappingContext,
        new_finding_id: Callable[[], str] | None = None,
    ) -> dict[str, Any]:
        """Map one schema-validated compact model result to a canonical immutable report."""

        _validate_compact_shape(model_output)
        id_factory = new_finding_id or (lambda: str(uuid4()))
        compact_coverage = model_output["coverage"]
        gaps = [
            {
                "source_id": context.primary_source_id,
                "fragment_id": item["fragment_id"],
                "code": "other",
                "reason": item["reason"],
            }
            for item in compact_coverage["unreviewed"]
        ]
        gaps.extend(deepcopy(compact_coverage["source_gaps"]))
        findings: list[dict[str, Any]] = []
        for ordinal, compact_finding in enumerate(model_output["findings"], start=1):
            anchors: list[dict[str, Any]] = []
            for compact_anchor in compact_finding["anchors"]:
                fragment_id = compact_anchor["fragment_id"]
                fragment = context.fragments.get(fragment_id)
                if fragment is None:
                    raise ValueError("anchor references an unknown fragment")
                if compact_anchor["source_id"] != fragment.source_id:
                    raise ValueError("anchor source identity mismatch")
                quote = compact_anchor["quote"]
                if not isinstance(quote, str) or not quote:
                    raise ValueError("anchor quote is required")
                start = resolve_unique_quote_offset(fragment.text, quote)
                anchors.append(
                    {
                        "source_id": fragment.source_id,
                        "document_id": fragment.document_id,
                        "source_name": fragment.source_name,
                        "fragment_id": fragment.id,
                        "quote": quote,
                        "quote_start": start,
                        "quote_end": start + len(quote),
                        "location": deepcopy(dict(fragment.location)),
                    }
                )
            findings.append(
                {
                    "id": id_factory(),
                    "ordinal": ordinal,
                    "kind": compact_finding["kind"],
                    "title": compact_finding["title"],
                    "problem": compact_finding["problem"],
                    "reason": compact_finding["reason"],
                    "question": compact_finding["question"],
                    "priority": deepcopy(compact_finding["priority"]),
                    "anchors": anchors,
                    "scope": deepcopy(compact_finding["scope"]),
                }
            )
        coverage = {
            "status": "complete" if not gaps else "partial",
            "target_fragment_ids": list(context.target_fragment_ids),
            "reviewed_fragment_ids": deepcopy(compact_coverage["reviewed_fragment_ids"]),
            "gaps": gaps,
        }
        report = {
            "id": context.report_id,
            "run_id": context.run_id,
            "created_at": context.created_at,
            "summary": model_output["summary"],
            "coverage": coverage,
            "findings": findings,
            "limitations": deepcopy(model_output["limitations"]),
            "provenance": deepcopy(dict(context.provenance)),
        }
        validate_report(
            report,
            {
                fragment_id: {
                    "source_id": fragment.source_id,
                    "document_id": fragment.document_id,
                    "text": fragment.text,
                    "location": dict(fragment.location),
                }
                for fragment_id, fragment in context.fragments.items()
            },
            primary_source_id=context.primary_source_id,
        )
        return report
