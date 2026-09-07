from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


class ModelReviewOutputError(ValueError):
    """Schema-owned diagnostics only; never include model values or unknown keys."""

    def __init__(self, message: str, feedback: str) -> None:
        super().__init__(message)
        self.feedback = feedback


def _unique_json_object(items: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        if key in value:
            raise ValueError("compact review model output is not valid JSON")
        value[key] = item
    return value


class ModelReviewOutputValidator:
    def __init__(self, schema_path: Path) -> None:
        schema = json.loads(schema_path.read_text())
        Draft202012Validator.check_schema(schema)
        self.schema = schema
        self.validator = Draft202012Validator(schema)
        # The model is asked for strict metadata, but publication can retain a
        # finding after its unverifiable links have been removed.
        recovered_schema = deepcopy(schema)
        recovered_schema["$defs"]["finding"].pop("allOf", None)
        self.recovered_validator = Draft202012Validator(recovered_schema)

    def validate(self, value: dict[str, Any], *, recover_metadata: bool = False) -> dict[str, Any]:
        validator = self.recovered_validator if recover_metadata else self.validator
        errors = list(validator.iter_errors(value))
        if errors:
            details = []
            for error in errors[:8]:
                detail: dict[str, Any] = {
                    "schema_path": list(error.absolute_schema_path),
                    "rule": error.validator,
                }
                if error.validator == "required":
                    detail["missing_fields"] = [k for k in error.validator_value if k not in error.instance]
                if error.validator in {"type", "enum"}:
                    detail["expected"] = error.validator_value
                details.append(detail)
            raise ModelReviewOutputError(
                "compact review model output violates its declared schema",
                json.dumps(details, ensure_ascii=False),
            )
        return value

    def parse_and_validate(self, text: str, *, recover_metadata: bool = False) -> dict[str, Any]:
        if recover_metadata:
            text = text.strip()
            if text.startswith("```json\n") or text.startswith("```\n"):
                if text.endswith("```"):
                    text = text.split("\n", 1)[1][:-3].strip()
        try:
            value = json.loads(text, object_pairs_hook=_unique_json_object)
        except (TypeError, json.JSONDecodeError) as error:
            raise ValueError("compact review model output is not valid JSON") from error
        if not isinstance(value, dict):
            raise ValueError("compact review model output must be a JSON object")
        if recover_metadata:
            value = _normalize_metadata(value, self.schema)
        return self.validate(value, recover_metadata=recover_metadata)



def _normalize_metadata(value: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Project known fields and repair ancillary metadata, never invent finding text."""
    value = deepcopy(value)
    coverage = value.get("coverage")
    if not isinstance(coverage, dict):
        coverage = {}
    value["coverage"] = coverage
    for name in ("reviewed_fragment_ids", "unreviewed", "source_gaps"):
        if not isinstance(coverage.get(name), list):
            coverage[name] = []
    if value.get("limitations") is None:
        value["limitations"] = []
    findings = value.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue  # Content errors still require a correcting generation.
            for name in ("anchors", "scope"):
                if not isinstance(finding.get(name), list):
                    finding[name] = []
            finding["anchors"] = [
                {k: anchor[k] for k in ("source_id", "fragment_id", "quote")}
                for anchor in finding["anchors"] if isinstance(anchor, dict)
                and all(isinstance(anchor.get(k), str) and anchor[k]
                        for k in ("source_id", "fragment_id", "quote"))
                and len(anchor["source_id"]) <= 128 and len(anchor["fragment_id"]) <= 160
                and len(anchor["quote"]) <= 4000
            ]
            finding["scope"] = [s for s in finding["scope"] if isinstance(s, str) and 0 < len(s) <= 160]
            if finding.get("kind") == "missing":
                finding["scope"].extend(a["fragment_id"] for a in finding["anchors"])
                finding["anchors"] = []
    # Keep content constraints from the same schema. Unknown properties and
    # duplicate metadata are representational noise, not reasons to lose findings.
    def project(item: Any, shape: dict[str, Any]) -> Any:
        if "$ref" in shape:
            shape = schema["$defs"][shape["$ref"].rsplit("/", 1)[1]]
        if isinstance(item, dict) and "properties" in shape:
            return {k: project(v, shape["properties"][k])
                    for k, v in item.items() if k in shape["properties"]}
        if isinstance(item, list) and "items" in shape:
            result = []
            for child in item:
                projected = project(child, shape["items"])
                if not shape.get("uniqueItems") or projected not in result:
                    result.append(projected)
            return result
        return item
    projected: dict[str, Any] = project(value, schema)
    for name, shape in schema["properties"]["coverage"]["properties"].items():
        item_validator = Draft202012Validator({"$defs": schema["$defs"], **shape["items"]})
        projected["coverage"][name] = [
            item for item in projected["coverage"][name] if item_validator.is_valid(item)
        ]
    return projected


class CanonicalReportValidator:
    def __init__(self, openapi_path: Path) -> None:
        contract = yaml.safe_load(openapi_path.read_text())
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$ref": "#/components/schemas/ReviewReport",
            "components": contract["components"],
        }
        Draft202012Validator.check_schema(schema)
        self.validator = Draft202012Validator(schema, format_checker=FormatChecker())

    def validate(self, report: dict[str, Any]) -> None:
        if next(self.validator.iter_errors(report), None) is not None:
            raise ValueError("review report violates canonical schema")
