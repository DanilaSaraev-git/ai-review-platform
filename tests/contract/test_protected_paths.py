from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
APPROVED_FEATURE_009_WEB_PATHS = (
    "apps/web/README.md",
    "apps/web/e2e/document-cycle.spec.ts",
    "apps/web/e2e/us1-run-review.spec.ts",
    "apps/web/src/api/query-keys.ts",
    "apps/web/src/app/layout/AppLayout.tsx",
    "apps/web/src/app/router.tsx",
    "apps/web/src/features/document-cycle/DocumentFamilyPage.test.tsx",
    "apps/web/src/features/document-cycle/DocumentFamilyPage.tsx",
    "apps/web/src/features/document-cycle/DocumentsPage.tsx",
    "apps/web/src/features/document-cycle/NewVersionDialog.test.tsx",
    "apps/web/src/features/document-cycle/NewVersionDialog.tsx",
    "apps/web/src/features/document-cycle/ReviewHistory.tsx",
    "apps/web/src/features/document-cycle/ReviewNextStep.test.ts",
    "apps/web/src/features/document-cycle/ReviewNextStep.tsx",
    "apps/web/src/features/document-cycle/ReviewCyclePage.test.tsx",
    "apps/web/src/features/document-cycle/ReviewCyclePage.tsx",
    "apps/web/src/features/document-cycle/comparison-text.ts",
    "apps/web/src/features/document-cycle/effective-decision.test.ts",
    "apps/web/src/features/document-cycle/effective-decision.ts",
    "apps/web/src/features/finding-decision/components/DecisionForm.test.tsx",
    "apps/web/src/features/finding-decision/components/DecisionForm.tsx",
    "apps/web/src/features/finding-decision/components/DecisionSummary.tsx",
    "apps/web/src/features/finding-dialogue/api/use-create-turn.ts",
    "apps/web/src/features/finding-dialogue/components/AssistantResponseCard.tsx",
    "apps/web/src/features/finding-dialogue/components/DialogueAttachments.tsx",
    "apps/web/src/features/finding-dialogue/components/DialoguePanel.test.tsx",
    "apps/web/src/features/finding-dialogue/components/DialoguePanel.tsx",
    "apps/web/src/features/finding-dialogue/components/TurnComposer.test.tsx",
    "apps/web/src/features/finding-dialogue/components/TurnComposer.tsx",
    "apps/web/src/features/finding-dialogue/components/TurnList.tsx",
    "apps/web/src/features/new-review/NewReviewPage.tsx",
    "apps/web/src/features/new-review/RepeatReviewPage.test.tsx",
    "apps/web/src/features/new-review/api/use-create-review-run.ts",
    "apps/web/src/features/review-report/FindingPage.tsx",
    "apps/web/src/features/review-report/ReportPage.tsx",
    "apps/web/src/features/review-report/api/use-finding-states.ts",
    "apps/web/src/features/review-report/components/DownloadPdfButton.test.tsx",
    "apps/web/src/features/review-report/components/DownloadPdfButton.tsx",
    "apps/web/src/features/review-report/components/FindingCard.tsx",
    "apps/web/src/features/review-report/components/ReviewWorkspaceLayout.tsx",
    "apps/web/src/lib/error-messages.ts",
    "apps/web/src/mocks/fixtures/index.ts",
    "apps/web/src/mocks/scenarios/base.ts",
    "apps/web/src/mocks/scenarios/document-cycle.ts",
    "apps/web/src/mocks/scenarios/index.ts",
    "apps/web/src/styles/unified-review.css",
)


def test_protected_paths_unchanged_from_approved_web_baseline() -> None:
    approved_args = [
        argument for path in APPROVED_FEATURE_009_WEB_PATHS for argument in ("--allow-path", path)
    ]
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/contracts/check_protected_paths.py"),
            "--json",
            *approved_args,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["unexpected_changes"] == []
