from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
import yaml

ROOT = Path(__file__).parents[2]


def test_compose_exposes_guest_quota_configuration_to_api() -> None:
    compose = yaml.safe_load((ROOT / "deploy/compose/compose.yaml").read_text())
    env = compose["services"]["api"]["environment"]
    for key, default in {
        "REVIEW_GUEST_STORAGE_BYTES": 209715200,
        "REVIEW_GUEST_TOTAL_STORAGE_BYTES": 1073741824,
        "REVIEW_GUEST_DOCUMENT_LIMIT": 20,
        "REVIEW_GUEST_DISK_RESERVE_BYTES": 3221225472,
    }.items():
        assert env[key] == "${" + key + ":-" + str(default) + "}"


@pytest.mark.integration
@pytest.mark.parametrize("scenario", ["backup_low_space", "disable", "enable", "recreate_failure"])
def test_ops_preserve_state_and_close_gateway_on_failure(tmp_path: Path, scenario: str) -> None:
    if os.environ.get("REVIEW_GATEWAY_TEST") != "1":
        pytest.skip("set REVIEW_GATEWAY_TEST=1 for the isolated shell/ops checks")
    fixture = tmp_path / "fixture"
    release = fixture / "releases" / "current"
    state = fixture / "state"
    backups = fixture / "backups"
    bin_dir = fixture / "bin"
    ops = release / "tools" / "ops"
    for directory in [state, backups, bin_dir, ops, release / "deploy" / "compose"]:
        directory.mkdir(parents=True, exist_ok=True)
    for filename in ["common.sh", "backup.sh", "backup_space.py", "guest-access-mode.sh"]:
        shutil.copy2(ROOT / "tools" / "ops" / filename, ops / filename)
    for filename in ["compose.yaml", "compose.production.yaml"]:
        (release / "deploy" / "compose" / filename).write_text("services: {}\n")
    (release / "RELEASE_COMMIT").write_text("a" * 40 + "\n")
    migration = release / "packages/review-runtime/migrations/versions/20260906_0003_guest_sessions.py"
    migration.parent.mkdir(parents=True)
    migration.write_text("# Synthetic marker for the supported release\n")
    (state / "review.env").write_text("OTHER_SETTING=synthetic\nREVIEW_GUEST_ACCESS=true\n")
    (state / "review.env").chmod(0o600)
    existing = backups / "20260906T000000Z"
    existing.mkdir()
    (existing / "database.dump").write_bytes(b"synthetic previous copy")
    (ops / "verify-deployment.sh").write_text("#!/bin/sh\nprintf 'verify\\n' >> /fixture/events\n")
    (ops / "verify-deployment.sh").chmod(0o755)
    docker_stub = bin_dir / "docker"
    docker_stub.write_text(
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$*" >> /fixture/events\n'
        'case "$*" in\n'
        "  *'ps --services'*) printf 'gateway\\nproxy\\napi\\n' ;;\n"
        "  *'pg_database_size'*) printf '1000000000000000000\\n' ;;\n"
        "  *'du -sb /source'*) printf '64 /source\\n' ;;\n"
        "  *' up '*) exit \"${OPS_TEST_UP_STATUS:-0}\" ;;\n"
        "esac\n"
    )
    docker_stub.chmod(0o755)
    script = "backup.sh" if scenario == "backup_low_space" else "guest-access-mode.sh"
    arguments = [] if scenario == "backup_low_space" else ["true" if scenario == "enable" else "false"]
    name = f"review-guest-ops-test-{uuid4().hex[:12]}"

    def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, check=check, capture_output=True, text=True, timeout=30)

    try:
        run(
            "docker", "create", "--pull=never", "--name", name, "--user", "0", "--network", "none",
            "--env", "PATH=/fixture/bin:/app/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "--env", "REVIEW_RELEASES_DIR=/fixture/releases",
            "--env", "REVIEW_CURRENT_LINK=/fixture/releases/current",
            "--env", "REVIEW_STATE_DIR=/fixture/state",
            "--env", "REVIEW_BACKUP_DIR=/fixture/backups",
            "--env", f"OPS_TEST_UP_STATUS={1 if scenario == 'recreate_failure' else 0}",
            "--entrypoint", "/bin/bash",
            os.environ.get("REVIEW_OPS_TEST_IMAGE", "review-platform-mvp:local"),
            f"/fixture/releases/current/tools/ops/{script}", *arguments,
        )
        run("docker", "cp", str(fixture), f"{name}:/fixture")
        result = run("docker", "start", "--attach", name, check=False)
        exit_code = run("docker", "inspect", "--format", "{{.State.ExitCode}}", name).stdout.strip()
        observed = tmp_path / "observed"
        run("docker", "cp", f"{name}:/fixture", str(observed))
        events = (observed / "events").read_text().splitlines()
        config = (observed / "state/review.env").read_text()
        previous_copy = observed / "backups/20260906T000000Z/database.dump"
        assert previous_copy.read_bytes() == b"synthetic previous copy"
        assert not any("pg_dump" in event for event in events)
        if scenario == "backup_low_space":
            assert exit_code == "1", result.stderr
            assert "backup refused" in result.stderr
            assert events[-1].endswith(" start gateway proxy api")
            assert config.endswith("REVIEW_GUEST_ACCESS=true\n")
            assert sorted(path.name for path in (observed / "backups").iterdir()) == [
                ".backup.lock", "20260906T000000Z"
            ]
        else:
            mode = "true" if scenario == "enable" else "false"
            assert config == f"OTHER_SETTING=synthetic\nREVIEW_GUEST_ACCESS={mode}\n"
            assert events[1].endswith(" stop --timeout 30 gateway")
            assert "--no-deps --force-recreate --wait api proxy gateway" in events[2]
            if scenario == "recreate_failure":
                assert exit_code == "1", result.stderr
                assert events[-1].endswith(" stop --timeout 30 gateway")
                assert "verify" not in events
            else:
                assert exit_code == "0", result.stderr
                assert events[-1] == "verify"
    finally:
        run("docker", "rm", "--force", name, check=False)
