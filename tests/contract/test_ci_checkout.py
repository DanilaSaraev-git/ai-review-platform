from pathlib import Path

import yaml


def test_backend_ci_fetches_contract_baseline_tag() -> None:
    root = Path(__file__).parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/ci.yml").read_text())
    steps = workflow["jobs"]["release-check"]["steps"]
    checkout = next(step for step in steps if step.get("uses") == "actions/checkout@v5")

    assert checkout.get("with", {}).get("fetch-depth") == 0
