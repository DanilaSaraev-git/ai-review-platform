from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from review_core.application.platform import ReviewPlatform
from review_core.domain.errors import Conflict
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor


def test_one_dialogue_revision_wins() -> None:
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
        "dialogue-run",
    )
    finding_id = next(iter(platform.dialogues))[1]
    body = {"message": "Explain", "expected_revision": 0}

    def invoke(key: str):
        try:
            return platform.create_dialogue_turn(platform.workspace_id, run["id"], finding_id, body, key)
        except Conflict:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(invoke, ["turn-key-a", "turn-key-b"]))
    assert sum(value is not None for value in results) == 1
