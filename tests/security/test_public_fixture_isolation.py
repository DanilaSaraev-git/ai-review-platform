from pathlib import Path

from tools.security.scan_release import scan_paths

ROOT = Path(__file__).parents[2]


def test_public_packages_and_fixtures_are_client_neutral() -> None:
    violations = scan_paths(
        [
            ROOT / "packages",
            ROOT / "apps/api",
            ROOT / "apps/worker",
            ROOT / "apps/cli",
            ROOT / "skills",
            ROOT / "tests/fixtures/synthetic-review",
        ]
    )
    assert violations == []
