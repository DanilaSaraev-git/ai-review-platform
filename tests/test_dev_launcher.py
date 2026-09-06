"""Safety checks for the localhost supervisor; no Docker, API or real credentials."""

from __future__ import annotations

import importlib.util
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from tools import dev


@pytest.fixture
def local_state(tmp_path, monkeypatch):
    checkout = tmp_path / "synthetic-checkout"
    checkout.mkdir()
    previous_umask = os.umask(0o077)
    # macOS Unix-domain socket paths have a much shorter limit than tmp_path.
    with tempfile.TemporaryDirectory(prefix="review-dev-", dir="/tmp") as directory:
        state = Path(directory)
        (state / "artifacts").mkdir()
        monkeypatch.setattr(dev, "ROOT", checkout)
        monkeypatch.setattr(dev, "STATE", state)
        monkeypatch.setattr(dev, "CONTROL", state / "control.sock")
        try:
            yield state
        finally:
            os.umask(previous_umask)


def sleeping_child(supervisor, log="synthetic-service"):
    return supervisor.spawn([sys.executable, "-c", "import time; time.sleep(300)"], log, dev.ROOT)


def test_environment_cannot_inherit_production_configuration(local_state, monkeypatch):
    inherited = {
        "REVIEW_DATABASE_URL": "postgresql://synthetic-production.invalid/review",
        "REVIEW_QUEUE_DATABASE_URL": "postgresql://synthetic-production.invalid/queue",
        "REVIEW_MODEL_CREDENTIAL_PATH": "/synthetic/production/credential",
        "REVIEW_UNKNOWN_FUTURE_OPTION": "unsafe",
        "VITE_API_BASE_URL": "https://synthetic-production.invalid/api",
        "VITE_MSW_SCENARIO": "fake-success",
        "VITE_UNKNOWN_FUTURE_OPTION": "unsafe",
        "COMPOSE_FILE": "synthetic-production.yaml",
        "POSTGRES_PASSWORD": "synthetic-production-password",
        "DOCKER_HOST": "tcp://synthetic-production.invalid:2375",
        "UV_PROJECT": "/synthetic/other-project",
        "PYTHONPATH": "/synthetic/other-packages",
        "HF_TOKEN": "synthetic-token-never-used",
    }
    for name, value in inherited.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("LOCAL_DEV_TEST_KEEP", "preserved")

    environment = dev.environment()

    assert not set(inherited.values()) & set(environment.values())
    assert "127.0.0.1:55451/" in environment["REVIEW_DATABASE_URL"]
    assert "127.0.0.1:55451/" in environment["REVIEW_QUEUE_DATABASE_URL"]
    assert environment["REVIEW_ARTIFACT_ROOT"] == str(local_state / "artifacts")
    assert environment["VITE_API_BASE_URL"] == "/api"
    assert environment["VITE_API_PROXY_TARGET"] == dev.API
    assert not environment["VITE_MSW_SCENARIO"]
    assert environment["LOCAL_DEV_TEST_KEEP"] == "preserved"


def test_occupied_port_reports_conflict_and_keeps_listener_alive():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        address = listener.getsockname()

        with pytest.raises(RuntimeError, match=f"Порт {address[1]} занят"):
            dev.require_free_port(address[1])

        with socket.create_connection(address, timeout=1), listener.accept()[0]:
            pass


@pytest.mark.parametrize("missing", ["docker", "credential"])
def test_missing_prerequisite_fails_before_starting_resources(local_state, monkeypatch, missing):
    supervisor = dev.Supervisor()
    supervisor.env["REVIEW_MODEL_CREDENTIAL_PATH"] = str(local_state / "absent-synthetic-credential")
    monkeypatch.setattr(dev.shutil, "which", lambda name: None if name == missing else sys.executable)
    launch = Mock(side_effect=AssertionError("No process may start before prerequisites pass"))
    docker = Mock(side_effect=AssertionError("Docker must not be contacted"))
    monkeypatch.setattr(supervisor, "spawn", launch)
    monkeypatch.setattr(supervisor, "docker", docker)

    with pytest.raises(RuntimeError, match="Нужен docker" if missing == "docker" else "huggingface.token"):
        supervisor.setup()

    launch.assert_not_called()
    docker.assert_not_called()


def test_stop_uses_owned_children_and_ignores_stale_pid_files(local_state, monkeypatch):
    supervisor = dev.Supervisor()
    own = sleeping_child(supervisor)
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(300)"], start_new_session=True
    )
    (local_state / "supervisor.pid").write_text(str(unrelated.pid))
    (local_state / "state.json").write_text(json.dumps({"pid": unrelated.pid, "root": str(dev.ROOT)}))
    # A stale socket and PID records must not become authority to signal a process.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stale:
        stale.bind(str(dev.CONTROL))
    try:
        # Simulate a reaped child whose numerical PID has since been reused.
        reused_pid = Mock(pid=unrelated.pid, returncode=0)
        dev.stop_processes([own, reused_pid])
        assert own.returncode is not None
        assert unrelated.poll() is None
        monkeypatch.setattr(sys, "argv", ["dev", "stop"])
        assert dev.main() == 0
        assert unrelated.poll() is None
    finally:
        if own.poll() is None:
            own.kill()
        own.wait(timeout=3)
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_exited_leader_still_owns_its_live_descendant(local_state):
    supervisor = dev.Supervisor()
    descendant = """
import signal, socket
signal.signal(signal.SIGTERM, signal.SIG_IGN)
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    listener.settimeout(5)
    print(listener.getsockname()[1], flush=True)
    while True:
        connection, _ = listener.accept()
        with connection:
            if connection.recv(8) == b'stop':
                break
"""
    leader = supervisor.spawn(
        [
            sys.executable,
            "-c",
            "import subprocess, sys; subprocess.Popen([sys.executable, '-c', sys.argv[1]])",
            descendant,
        ],
        "descendant",
        dev.ROOT,
    )
    unrelated = sleeping_child(supervisor, "unrelated")
    address = None
    try:
        deadline = time.monotonic() + 3
        log = local_state / "descendant.log"
        while (not log.read_text().strip() or not dev.exited(leader)) and time.monotonic() < deadline:
            time.sleep(0.02)
        address = ("127.0.0.1", int(log.read_text().strip()))
        assert dev.exited(leader)
        assert leader.returncode is None, "The process group must stay pinned until descendant cleanup"
        with socket.create_connection(address, timeout=1):
            pass

        dev.stop_processes([leader])

        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(address, timeout=0.1):
                    pass
            except OSError:
                break
            time.sleep(0.02)
        else:
            pytest.fail("Descendant still serves its socket after the leader was stopped")
        assert unrelated.poll() is None
    finally:
        if address:
            try:
                with socket.create_connection(address, timeout=0.1) as connection:
                    connection.sendall(b"stop")
            except OSError:
                pass
        if leader.returncode is None:
            dev.stop_processes([leader])
        unrelated.terminate()
        unrelated.wait(timeout=3)


def test_permission_error_on_living_child_is_not_hidden(local_state, monkeypatch):
    supervisor = dev.Supervisor()
    child = sleeping_child(supervisor)
    try:
        with monkeypatch.context() as patch:
            patch.setattr(dev.os, "killpg", Mock(side_effect=PermissionError("Synthetic denial")))
            with pytest.raises(PermissionError, match="Synthetic denial"):
                dev.stop_processes([child])
        assert child.poll() is None
    finally:
        child.terminate()
        child.wait(timeout=3)


def test_other_checkout_rejects_stop_before_side_effect(local_state):
    module_spec = importlib.util.spec_from_file_location("synthetic_other_checkout", dev.__file__)
    assert module_spec is not None and module_spec.loader is not None
    foreign = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(foreign)
    foreign.ROOT = dev.ROOT / "different-checkout"
    foreign.STATE = local_state
    supervisor = foreign.Supervisor()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(dev.CONTROL))
        server.listen()
        server.settimeout(0.05)
        control = threading.Thread(target=supervisor.control, args=(server,))
        control.start()
        try:
            with pytest.raises(RuntimeError, match="другому checkout"):
                dev.request("stop")
            assert not supervisor.stopping.wait(0.1), "Foreign checkout received a destructive stop"
        finally:
            supervisor.stopping.set()
            server.close()
            control.join(timeout=3)
        assert not control.is_alive()


def test_concurrent_and_repeated_start_spawn_one_supervisor(local_state, monkeypatch):
    current = None

    def launch(*args, **kwargs):
        nonlocal current
        current = {"root": str(dev.ROOT), "phase": "running"}
        return Mock()

    spawn = Mock(side_effect=launch)
    monkeypatch.setattr(dev.subprocess, "Popen", spawn)
    monkeypatch.setattr(dev, "request", lambda command="status": current)
    monkeypatch.setattr(sys, "argv", ["dev", "start"])
    barrier = threading.Barrier(2)

    def simultaneous_start():
        barrier.wait(timeout=3)
        return dev.main()

    with ThreadPoolExecutor(max_workers=2) as pool:
        launches = [pool.submit(simultaneous_start) for _ in range(2)]
        assert [launch.result(timeout=5) for launch in launches] == [0, 0]
    assert dev.main() == 0
    assert spawn.call_count == 1


def test_partial_start_cleans_only_owned_resources_and_preserves_artifacts(local_state, monkeypatch):
    supervisor = dev.Supervisor()
    artifact = local_state / "artifacts" / "synthetic-report.json"
    artifact.write_text('{"synthetic": true}')
    children = []

    def fail_after_start():
        children.append(sleeping_child(supervisor))
        supervisor.database = "synthetic-owned-postgres-container"
        raise RuntimeError("Synthetic migration failure")

    monkeypatch.setattr(supervisor, "setup", fail_after_start)
    monkeypatch.setattr(supervisor, "control", lambda server: None)
    monkeypatch.setattr(dev.signal, "signal", lambda *args: None)
    docker = Mock(return_value="")
    monkeypatch.setattr(supervisor, "docker", docker)

    try:
        supervisor.serve()
        assert supervisor.error == "Synthetic migration failure"
        assert children[0].returncode is not None
        assert not dev.CONTROL.exists()
        assert json.loads(artifact.read_text()) == {"synthetic": True}
        docker.assert_called_once_with("stop", "--time", "10", "synthetic-owned-postgres-container")
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)


def test_failed_probe_keeps_services_alive_and_runs_again(local_state, monkeypatch, capsys):
    supervisor = dev.Supervisor()
    services = []
    observations = []

    def unavailable_probe(argv, *, log, check):
        assert argv[-1] == "model-probe"
        assert log == "probe" and not check
        observations.append([service.poll() is None for service in services])
        if len(observations) == 3:
            supervisor.stopping.set()
        return 2

    def setup():
        services.extend([sleeping_child(supervisor, "api"), sleeping_child(supervisor, "web")])
        supervisor.probe()
        return tuple(services)

    monkeypatch.setattr(supervisor, "setup", setup)
    monkeypatch.setattr(supervisor, "run", unavailable_probe)
    monkeypatch.setattr(supervisor, "control", lambda server: None)
    monkeypatch.setattr(dev.signal, "signal", lambda *args: None)
    monkeypatch.setattr(dev, "PROBE_INTERVAL", 0.01)
    # A regression must fail promptly instead of leaving a hanging pytest process.
    watchdog = threading.Timer(5, supervisor.stopping.set)
    watchdog.start()
    try:
        supervisor.serve()
        assert observations == [[True, True]] * 3
        assert supervisor.error is None
        assert capsys.readouterr().out.count("model-probe exit=2") == 3
    finally:
        watchdog.cancel()
        for service in services:
            if service.poll() is None:
                service.kill()
            service.wait(timeout=3)
