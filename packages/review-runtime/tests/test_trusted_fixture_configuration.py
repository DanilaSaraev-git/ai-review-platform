from __future__ import annotations

import json
from pathlib import Path

from review_core.application.platform import ReviewPlatform
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor

ROOT = Path(__file__).parents[3]


def test_executor_uses_binding_from_runtime_config(tmp_path: Path) -> None:
    config = json.loads(
        (ROOT / "deploy/compose/config/runtime-config.synthetic.v1.json").read_text()
    )
    config["deterministic_gateway"]["trusted_fixture_bindings"][0]["binding_id"] = (
        "operator-selected-binding"
    )
    config_path = tmp_path / "runtime-config.json"
    config_path.write_text(json.dumps(config))
    expected_output_path = (
        ROOT / "deploy/compose/config/trusted-fixture-output.synthetic.v1.json"
    )
    executor = TrustedFixtureReviewExecutor(
        ROOT,
        runtime_config_path=config_path,
        expected_output_path=expected_output_path,
    )
    platform = ReviewPlatform(executor)
    document = platform.upload(
        platform.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (ROOT / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    run = platform.create_run(
        platform.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {
                "id": platform.system_profile.id,
                "version": platform.system_profile.version,
            },
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        "operator-config-binding",
    )
    report_bytes, _ = platform.report(platform.workspace_id, run["id"])
    report = json.loads(report_bytes)

    assert report["provenance"]["model"]["safe_parameters"]["binding_id"] == (
        "operator-selected-binding"
    )


def test_executor_rejects_expected_output_digest_drift(tmp_path: Path) -> None:
    expected_output = (
        ROOT / "deploy/compose/config/trusted-fixture-output.synthetic.v1.json"
    ).read_bytes()
    expected_output_path = tmp_path / "expected-output.json"
    expected_output_path.write_bytes(expected_output)
    executor = TrustedFixtureReviewExecutor(
        ROOT,
        runtime_config_path=ROOT / "deploy/compose/config/runtime-config.synthetic.v1.json",
        expected_output_path=expected_output_path,
    )
    expected_output_path.write_bytes(expected_output + b"\n")

    try:
        executor.check_configuration()
    except ValueError as error:
        assert str(error) == "trusted expected-output resource digest drift"
    else:
        raise AssertionError("drifted expected output was accepted")
