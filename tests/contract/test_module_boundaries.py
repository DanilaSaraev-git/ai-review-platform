from pathlib import Path


def test_review_core_has_no_framework_or_provider_imports() -> None:
    root = Path(__file__).parents[2] / "packages/review-core/src/review_core"
    forbidden = ("fastapi", "pydantic", "sqlalchemy", "procrastinate", "pdfplumber", "httpx")
    for path in root.rglob("*.py"):
        text = path.read_text()
        for package in forbidden:
            assert f"import {package}" not in text
            assert f"from {package}" not in text
