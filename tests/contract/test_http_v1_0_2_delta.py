from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
OPENAPI = ROOT / "contracts/review-platform/v1/openapi.yaml"


def _operation_block(text: str, operation_id: str) -> str:
    marker = f"operationId: {operation_id}"
    start = text.index(marker)
    following = re.search(r"\n\s+operationId: ", text[start + len(marker) :])
    end = len(text) if following is None else start + len(marker) + following.start()
    return text[start:end]


def test_exact_additive_http_v1_0_2_delta() -> None:
    text = OPENAPI.read_text()
    assert re.search(r"^\s*version: 1\.0\.2$", text, re.MULTILINE)
    for operation, status in (
        ("listDocuments", '"400"'),
        ("listReviewRuns", '"400"'),
        ("uploadDocument", '"404"'),
        ("createReviewProfile", '"409"'),
    ):
        assert status in _operation_block(text, operation)


def test_semantics_are_documented_without_new_public_enum() -> None:
    text = OPENAPI.read_text()
    assert "primary_source_partial" in text
    assert "source_partial" in text
    assert "semantic_analysis_not_performed" in text
    assert "quoted lowercase SHA-256" in text
    assert "immutable family" in text
    assert "deployment-scoped release data" in text
    assert "awaiting or undergoing extraction" in text
    assert "Requested source" in text
    assert "degraded, unknown, missing, or expired" in text
    assert "YYYY-MM-DDTHH:mm:ss.ffffffZ" in text
    assert "primary_source_partial" not in re.findall(r"code:\s*\{enum:\s*\[([^]]+)\]", text)[0]


def test_swagger_runtime_is_fully_offline() -> None:
    swagger = ROOT / "contracts/review-platform/v1/swagger"
    html = (swagger / "index.html").read_text()
    assert "https://" not in html
    assert "http://" not in html
    assert (swagger / "swagger-ui.css").is_file()
    assert (swagger / "swagger-ui-bundle.js").is_file()


def test_only_allowlisted_contract_files_changed_from_v1_0_1() -> None:
    changed = subprocess_output(
        "git",
        "diff",
        "--name-only",
        "review-platform-contract-v1.0.1",
        "--",
        "contracts/review-platform/v1",
    )
    allowed = {
        "contracts/review-platform/v1/openapi.yaml",
        "contracts/review-platform/v1/README.md",
        "contracts/review-platform/v1/CHANGELOG.md",
        "contracts/review-platform/v1/swagger/README.md",
        "contracts/review-platform/v1/swagger/index.html",
        "contracts/review-platform/v1/swagger/swagger-ui.css",
        "contracts/review-platform/v1/swagger/swagger-ui-bundle.js",
        "contracts/review-platform/v1/swagger/LICENSE",
        "contracts/review-platform/v1/swagger/NOTICE",
        "contracts/review-platform/v1/swagger/swagger-ui-bundle.js.LICENSE.txt",
        "contracts/review-platform/v1/examples/http/README.md",
    }
    assert set(changed.splitlines()) <= allowed


def subprocess_output(*args: str) -> str:
    import subprocess

    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()
