from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from review_core.application.platform import ReviewPlatform
from review_runtime.config.settings import OperatorSettings
from review_runtime.fakes.review_executor import TrustedFixtureReviewExecutor
from review_runtime.postgres.platform import PostgresReviewPlatform


def build_platform(composition: str = "fixture") -> Any:
    root = Path(__file__).resolve().parents[4]
    if composition == "durable" or os.environ.get("REVIEW_COMPOSITION") == "durable":
        settings = OperatorSettings()  # type: ignore[call-arg]
        executor = TrustedFixtureReviewExecutor(
            root,
            runtime_config_path=settings.runtime_config_path,
            expected_output_path=settings.expected_output_path,
        )
        return PostgresReviewPlatform(executor, settings)
    executor = TrustedFixtureReviewExecutor(root)
    return ReviewPlatform(executor)
