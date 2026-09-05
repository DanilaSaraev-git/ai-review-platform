from pathlib import Path

from review_core.application.platform import ReviewPlatform
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor


def test_direct_and_http_core_use_same_deterministic_semantics() -> None:
    root = Path(__file__).parents[2]
    platform = ReviewPlatform(TrustedFixtureReviewExecutor(root))
    document = platform.upload(
        platform.workspace_id,
        "synthetic-spec.md",
        "text/markdown",
        (root / "tests/fixtures/synthetic-review/synthetic-spec.md").read_bytes(),
    )
    profile = platform.system_profile
    run = platform.create_run(
        platform.workspace_id,
        {
            "document_id": document["id"],
            "context_document_ids": [],
            "profile": {"id": profile.id, "version": profile.version},
            "model_profile": {"id": "deterministic-v1", "version": "1.0.0"},
            "locale": "en-US",
        },
        "channel-contract",
    )
    report, _ = platform.report(platform.workspace_id, run["id"])
    assert b'"provider":"deterministic"' in report
    assert b'"findings":[' in report
