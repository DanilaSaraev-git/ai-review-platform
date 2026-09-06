from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from review_cli.commands import model_smoke as smoke_module
from review_cli.main import app
from review_runtime.composition import compose_model_runtime
from typer.testing import CliRunner

ROOT = Path(__file__).parents[3]
FRAGMENT_ID = "source-main-lines-1-1"
QUOTE = "Refresh runs regularly."
RAW_SENTINEL = "PRIVATE_MODEL_OUTPUT_DO_NOT_PRINT"


def review_output() -> dict[str, Any]:
    return {
        "summary": "The refresh interval is unspecified.",
        "coverage": {"reviewed_fragment_ids": [FRAGMENT_ID], "unreviewed": [], "source_gaps": []},
        "findings": [{
            "kind": "ambiguity",
            "title": "Unspecified refresh interval",
            "problem": "Regularly does not define a testable interval.",
            "reason": "A schedule is needed for acceptance tests.",
            "question": "Which refresh interval is required?",
            "priority": {"level": "medium", "rationale": "The schedule cannot be tested."},
            "anchors": [{"source_id": "source-main", "fragment_id": FRAGMENT_ID, "quote": QUOTE}],
            "scope": [],
        }],
        "limitations": [],
    }


def dialogue_output() -> dict[str, Any]:
    return {
        "action": "clarify",
        "content": "Which refresh interval is required?",
        "proposed_resolution": None,
        "anchors": [{"source_id": "source-main", "fragment_id": FRAGMENT_ID, "quote": QUOTE}],
    }


def invoke_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    responses: list[str],
    *,
    finish_reason: str | list[str] = "stop",
) -> tuple[Any, list[dict[str, Any]], Path]:
    profile = json.loads((ROOT / "tests/fixtures/ml-integration/model-profile.compose.json").read_text())
    profile["secret_ref"] = None
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(profile))
    evidence = tmp_path / "evidence.json"
    requests: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        assert len(requests) <= len(responses), "Unexpected additional model call"
        return httpx.Response(200, json={
            "model": "synthetic-model",
            "choices": [{
                "message": {"content": responses[len(requests) - 1]},
                "finish_reason": (
                    finish_reason[len(requests) - 1]
                    if isinstance(finish_reason, list)
                    else finish_reason
                ),
            }],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        })

    monkeypatch.setattr(
        smoke_module,
        "compose_model_runtime",
        lambda **kwargs: compose_model_runtime(**kwargs, transport=httpx.MockTransport(handle)),
    )
    result = CliRunner().invoke(app, [
        "model-smoke",
        "--profile", str(profile_path),
        "--fixture", str(ROOT / "tests/fixtures/ml-integration/primary.md"),
        "--skill", str(ROOT / "skills/review-data-spec"),
        "--output", str(evidence),
    ])
    return result, requests, evidence


def test_smoke_verifies_both_mapped_results_and_uses_canonical_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, requests, evidence = invoke_smoke(
        tmp_path, monkeypatch, [json.dumps(review_output()), json.dumps(dialogue_output())]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(evidence.read_text())["status"] == "verified"
    assert len(requests) == 2
    finding = json.loads(requests[1]["messages"][-1]["content"])["finding"]
    assert finding["id"]
    assert finding["ordinal"] == 1
    anchor = finding["anchors"][0]
    assert anchor["document_id"]
    assert anchor["quote_start"] == 0
    assert anchor["quote_end"] == len(QUOTE)
    assert anchor["location"]["kind"] == "text"
    assert QUOTE not in result.output


@pytest.mark.parametrize("case,phase,expected_calls", [
    ("invalid_review_json", "review_schema", 1),
    ("review_unknown_fragment", "review_semantics", 1),
    ("review_inexact_quote", "review_semantics", 1),
    ("review_incomplete_coverage", "review_semantics", 1),
    ("invalid_dialogue_json", "dialogue_schema", 2),
    ("dialogue_duplicate_field", "dialogue_schema", 2),
    ("dialogue_unknown_fragment", "dialogue_semantics", 2),
    ("dialogue_inexact_quote", "dialogue_semantics", 2),
])
def test_smoke_rejects_model_schema_and_evidence_errors_safely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    phase: str,
    expected_calls: int,
) -> None:
    review = deepcopy(review_output())
    dialogue = deepcopy(dialogue_output())
    if case == "review_unknown_fragment":
        review["findings"][0]["anchors"][0]["fragment_id"] = RAW_SENTINEL
    elif case == "review_inexact_quote":
        review["findings"][0]["anchors"][0]["quote"] = RAW_SENTINEL
    elif case == "review_incomplete_coverage":
        review["coverage"]["reviewed_fragment_ids"] = []
    elif case == "dialogue_unknown_fragment":
        dialogue["anchors"][0]["fragment_id"] = RAW_SENTINEL
    elif case == "dialogue_inexact_quote":
        dialogue["anchors"][0]["quote"] = RAW_SENTINEL
    review_text = RAW_SENTINEL if case == "invalid_review_json" else json.dumps(review)
    dialogue_text = RAW_SENTINEL if case == "invalid_dialogue_json" else json.dumps(dialogue)
    if case == "dialogue_duplicate_field":
        dialogue_text = dialogue_text[:-1] + ', "content": "' + RAW_SENTINEL + '"}'
    result, requests, evidence = invoke_smoke(tmp_path, monkeypatch, [review_text, dialogue_text])
    assert result.exit_code == 2, result.output
    assert json.loads(result.output) == {"status": "failed", "code": "model_output_invalid", "phase": phase}
    assert len(requests) == expected_calls
    assert RAW_SENTINEL not in result.output
    assert not evidence.exists()


def test_smoke_does_not_verify_a_truncated_but_schema_valid_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result, requests, evidence = invoke_smoke(
        tmp_path, monkeypatch, [json.dumps(review_output())], finish_reason="length"
    )
    assert result.exit_code == 2
    assert json.loads(result.output)["code"] == "model_output_invalid"
    assert len(requests) == 1
    assert not evidence.exists()


@pytest.mark.parametrize("purpose", ["review", "dialogue"])
@pytest.mark.parametrize("response_shape", ["valid_json", "truncated_json"])
def test_smoke_identifies_output_limit_before_schema_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    purpose: str,
    response_shape: str,
) -> None:
    responses = [json.dumps(review_output())]
    reasons = ["length"]
    if purpose == "dialogue":
        responses.append(json.dumps(dialogue_output()))
        reasons = ["stop", "length"]
    if response_shape == "truncated_json":
        responses[-1] = '{"summary":"' + RAW_SENTINEL
    result, requests, evidence = invoke_smoke(
        tmp_path, monkeypatch, responses, finish_reason=reasons
    )
    assert result.exit_code == 2
    assert json.loads(result.output) == {
        "status": "failed",
        "code": "model_output_invalid",
        "phase": f"{purpose}_completion",
        "message": "The model response reached the output token limit before completion.",
    }
    assert len(requests) == len(responses)
    assert RAW_SENTINEL not in result.output
    assert not evidence.exists()


def test_smoke_reports_missing_dialogue_fixture_without_inventing_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    review = review_output()
    review["findings"] = []
    result, requests, evidence = invoke_smoke(tmp_path, monkeypatch, [json.dumps(review)])
    assert result.exit_code == 2
    assert json.loads(result.output) == {
        "status": "failed", "code": "fixture_no_finding", "phase": "dialogue_preparation"
    }
    assert len(requests) == 1
    assert not evidence.exists()


def test_smoke_keeps_invalid_configuration_distinct(tmp_path: Path) -> None:
    profile = tmp_path / "bad-profile.json"
    profile.write_text(RAW_SENTINEL)
    result = CliRunner().invoke(app, [
        "model-smoke",
        "--profile", str(profile),
        "--fixture", str(ROOT / "tests/fixtures/ml-integration/primary.md"),
        "--skill", str(ROOT / "skills/review-data-spec"),
    ])
    assert result.exit_code == 2
    assert json.loads(result.output) == {
        "status": "failed", "code": "invalid_configuration", "phase": "configuration"
    }
    assert RAW_SENTINEL not in result.output
