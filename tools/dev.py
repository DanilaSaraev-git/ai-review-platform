"""Local development supervisor. Control uses a private socket, never saved PIDs."""

# Commands below are fixed local tools, with argv lists and no shell interpolation.
# ruff: noqa: S603, S606, S607
from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
STATE = Path.home() / ".local/state/ai-review-platform/dev"
CONTROL = STATE / "control.sock"
PROJECT = "review-platform-dev"
WEB = "http://localhost:5173"
API = "http://127.0.0.1:18000"
PROBE_INTERVAL = 60


def environment() -> dict[str, str]:
    # An exported production DSN, Compose overlay or MSW scenario must not leak in.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("REVIEW_", "VITE_", "POSTGRES_", "COMPOSE_", "UV_", "PYTHON"))
        and k not in {"DOCKER_HOST", "VIRTUAL_ENV", "HF_TOKEN", "HF_API_TOKEN", "OPENAI_API_KEY"}
    }
    env.update(
        {
            "POSTGRES_DB": "review",
            "POSTGRES_USER": "review",
            "POSTGRES_PASSWORD": "review-local-only",
            "REVIEW_TEST_POSTGRES_PORT": "55451",
            "REVIEW_COMPOSITION": "ml",
            "REVIEW_DATABASE_URL": "postgresql+psycopg://review:review-local-only@127.0.0.1:55451/review",
            "REVIEW_QUEUE_DATABASE_URL": "postgresql://review:review-local-only@127.0.0.1:55451/review",
            "REVIEW_ARTIFACT_ROOT": str(STATE / "artifacts"),
            "REVIEW_RUNTIME_CONFIG_PATH": str(
                ROOT / "deploy/compose/config/runtime-config.synthetic.v1.json"
            ),
            "REVIEW_MODEL_PROFILE_PATH": str(
                ROOT / "deploy/compose/config/model-profile.huggingface-kimi-k2.json"
            ),
            "REVIEW_MODEL_PROFILE_ID": "kimi-k2-hf-novita",
            "REVIEW_MODEL_CREDENTIAL_PATH": str(
                Path.home() / ".config/ai-analytics-review/huggingface.token"
            ),
            "REVIEW_SKILL_PACKAGE_PATH": str(ROOT / "skills/review-data-spec"),
            "REVIEW_SKILL_ID": "review-data-spec",
            "REVIEW_SKILL_PACKAGE_SHA256": "93f89a407f19fb3035bee58b8aa355aaf2587bfab7f1bcf4663baad9fbdc71f7",
            "REVIEW_ORGANIZATION_NAME": "Local Development",
            "REVIEW_WORKSPACE_NAME": "Local Development",
            "REVIEW_ACTOR_DISPLAY_NAME": "Local Developer",
            "REVIEW_DIALOGUE_POLICY_ID": "local-dev-dialogue-v1",
            "VITE_API_BASE_URL": "/api",
            "VITE_API_PROXY_TARGET": API,
            "VITE_MSW_SCENARIO": "",
            "PYTHONUNBUFFERED": "1",
        }
    )
    for kind in ("DEPLOYMENT", "ORGANIZATION", "WORKSPACE", "ACTOR", "SYSTEM_PROFILE"):
        env[f"REVIEW_{kind}_ID"] = str(uuid5(NAMESPACE_URL, f"ai-review-platform/local-dev/{kind}"))
    return env


def require_free_port(port: int) -> None:
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        with socket.socket(family, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                listener.bind((host, port))
            except OSError as exc:
                raise RuntimeError(f"Порт {port} занят; чужие процессы не остановлены.") from exc


def request(command: str = "status") -> dict | None:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(2)
        try:
            client.connect(str(CONTROL))
        except (FileNotFoundError, ConnectionRefusedError):
            return None
        client.sendall(json.dumps({"command": command, "root": str(ROOT)}).encode())
        data = json.loads(client.recv(16384))
    if data["root"] != str(ROOT):
        raise RuntimeError(f"Local dev уже принадлежит другому checkout: {data['root']}")
    return data


def exited(process: subprocess.Popen) -> bool:
    # Keep the group leader unreaped: its PID cannot be reused before cleanup.
    return (
        process.returncode is not None
        or os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    )


def signal_group(process: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS returns EPERM for a group containing only the unreaped zombie.
        if not exited(process):
            raise


def stop_processes(processes: list[subprocess.Popen]) -> None:
    # Never use a reaped child's PID. Unreaped leaders pin our process group IDs,
    # including when a failed reloader left a descendant serving requests.
    live = [process for process in processes if process.returncode is None]
    for process in live:
        signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + 75  # API may drain review and dialogue separately.
    for process in live:
        while not exited(process) and time.monotonic() < deadline:
            time.sleep(0.1)
        signal_group(process, signal.SIGKILL)
        process.wait()


class Supervisor:
    def __init__(self) -> None:
        self.env = environment()
        self.stopping = threading.Event()
        self.phase = "starting"
        self.processes: list[subprocess.Popen] = []
        self.database: str | None = None
        self.error: str | None = None

    def spawn(self, argv: list[str], log: str, cwd: Path = ROOT) -> subprocess.Popen:
        if self.stopping.is_set():
            raise InterruptedError("Остановка локального стенда")
        with (STATE / f"{log}.log").open("ab") as output:
            process = subprocess.Popen(
                argv,
                cwd=cwd,
                env=self.env,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        self.processes.append(process)
        return process

    def run(self, argv: list[str], *, log: str = "launcher", timeout: int = 120, check: bool = True) -> int:
        process = self.spawn(argv, log)
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if self.stopping.wait(0.2):
                raise InterruptedError("Остановка локального стенда")
            if time.monotonic() > deadline:
                stop_processes([process])
                raise RuntimeError(f"Истекло время {argv[0]}; см. {log}.log")
        self.processes.remove(process)
        if check and process.returncode:
            raise RuntimeError(f"Команда {argv[0]} завершилась с кодом {process.returncode}; см. {log}.log")
        return process.returncode

    def docker(self, *args: str) -> str:
        return subprocess.check_output(
            ["docker", *args], env=self.env, cwd=ROOT, text=True, timeout=15
        ).strip()

    def control(self, server: socket.socket) -> None:
        while True:
            try:
                connection, _ = server.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(2)
                try:
                    message = json.loads(connection.recv(16384))
                    connection.sendall(
                        json.dumps(
                            {"root": str(ROOT), "phase": self.phase, "url": WEB, "logs": str(STATE)}
                        ).encode()
                    )
                    if message.get("command") == "stop" and message.get("root") == str(ROOT):
                        self.stopping.set()
                except (OSError, ValueError):
                    continue

    def ready(self, url: str, process: subprocess.Popen) -> None:
        deadline = time.monotonic() + 60
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while not self.stopping.wait(0.3):
            if exited(process):
                raise RuntimeError("Dev-сервис завершился до readiness; см. журналы")
            try:
                with opener.open(url, timeout=2) as response:
                    if response.status == 200:
                        return
            except (OSError, urllib.error.URLError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError(f"Нет readiness: {url}; см. журналы")
        raise InterruptedError("Остановка локального стенда")

    def setup(self) -> tuple[subprocess.Popen, subprocess.Popen]:
        for name in ("uv", "npm", "node", "docker"):
            if shutil.which(name) is None:
                raise RuntimeError(f"Нужен {name}; см. docs/operations/local-development.md")
        credential = Path(self.env["REVIEW_MODEL_CREDENTIAL_PATH"])
        if not credential.is_file() or not os.access(credential, os.R_OK):
            raise RuntimeError("Нет читаемого huggingface.token; см. инструкцию локального запуска")
        for port in (5173, 18000):
            require_free_port(port)
        self.env["DOCKER_CONTEXT"] = self.docker("context", "show")
        endpoint = json.loads(self.docker("context", "inspect"))[0]["Endpoints"]["docker"]["Host"]
        if not endpoint.startswith("unix://"):
            raise RuntimeError("Для localhost требуется локальный Docker context (unix socket)")
        existing = self.docker("ps", "-aq", "--filter", f"label=com.docker.compose.project={PROJECT}")
        if existing:
            containers = json.loads(self.docker("inspect", *existing.splitlines()))
            if len(containers) != 1:
                raise RuntimeError("Compose project review-platform-dev занят другими сервисами")
            container = containers[0]
            labels = container["Config"]["Labels"]
            if labels.get("com.docker.compose.service") != "postgres" or labels.get(
                "com.docker.compose.project.working_dir"
            ) != str(ROOT / "deploy/compose"):
                raise RuntimeError("Compose project review-platform-dev принадлежит другому checkout")
            if not container["State"]["Running"]:
                require_free_port(55451)
        else:
            require_free_port(55451)
        self.run(["uv", "sync", "--frozen"])
        if not (ROOT / "apps/web/node_modules/.bin/vite").exists():
            raise RuntimeError("Нужны web dependencies: cd apps/web && npm ci")
        compose = [
            "docker",
            "compose",
            "--project-name",
            PROJECT,
            "--env-file",
            "/dev/null",
            "-f",
            "deploy/compose/compose.yaml",
            "-f",
            "deploy/compose/compose.release.yaml",
        ]
        self.run([*compose, "create", "--no-build", "postgres"])
        self.database = self.docker("compose", *compose[2:], "ps", "--all", "--quiet", "postgres")
        self.run([*compose, "up", "--detach", "--no-build", "--wait", "--wait-timeout", "60", "postgres"])
        self.run(
            [str(ROOT / ".venv/bin/alembic"), "-c", "packages/review-runtime/alembic.ini", "upgrade", "head"]
        )
        self.probe()
        api = self.spawn(
            [
                str(ROOT / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "review_api.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "18000",
                "--reload",
                "--reload-dir",
                "apps/api/src",
                "--reload-dir",
                "packages/review-core/src",
                "--reload-dir",
                "packages/review-runtime/src",
            ],
            "api",
        )
        self.ready(API + "/health/ready", api)
        web = self.spawn(
            [
                "node",
                "node_modules/vite/bin/vite.js",
                "--host",
                "127.0.0.1",
                "--port",
                "5173",
                "--strictPort",
            ],
            "web",
            ROOT / "apps/web",
        )
        self.ready("http://127.0.0.1:5173/api/v1/bootstrap", web)
        return api, web

    def probe(self) -> None:
        try:
            code = self.run([str(ROOT / ".venv/bin/review-cli"), "model-probe"], log="probe", check=False)
        except RuntimeError as exc:
            print(f"model-probe: {exc}; следующий цикл продолжится", flush=True)
            return
        print(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} model-probe exit={code}", flush=True)

    def serve(self) -> None:
        with (STATE / "supervisor.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            CONTROL.unlink(missing_ok=True)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(str(CONTROL))
                server.listen(4)
                server.settimeout(0.5)
                threading.Thread(target=self.control, args=(server,), daemon=True).start()
                for sig in (signal.SIGTERM, signal.SIGINT):
                    signal.signal(sig, lambda *_: self.stopping.set())
                try:
                    services = self.setup()
                    self.phase = "running"
                    print(f"Готово: {WEB}", flush=True)
                    next_probe = time.monotonic() + PROBE_INTERVAL
                    while not self.stopping.wait(0.5):
                        if any(exited(service) for service in services):
                            raise RuntimeError("Dev-сервис завершился; останавливаю локальный стенд")
                        if time.monotonic() >= next_probe:
                            self.probe()
                            next_probe += PROBE_INTERVAL
                except InterruptedError:
                    pass
                except Exception as exc:
                    self.error = str(exc)
                    print(f"Ошибка: {self.error}", flush=True)
                finally:
                    self.phase = "stopping"
                    self.stopping.set()
                    try:
                        stop_processes(self.processes)
                    finally:
                        try:
                            if self.database:
                                self.docker("stop", "--time", "10", self.database)
                        except (subprocess.SubprocessError, OSError):
                            print("Не удалось остановить локальную PostgreSQL; данные сохранены", flush=True)
                        finally:
                            CONTROL.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI Review localhost: start / stop / status / logs")
    parser.add_argument("command", choices=("start", "stop", "status", "logs", "_serve"))
    command = parser.parse_args().command
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    (STATE / "artifacts").mkdir(exist_ok=True)
    if command == "_serve":
        Supervisor().serve()
        return 0
    if command == "logs":
        print(f"Журналы: {STATE}", flush=True)
        files = [str(path) for path in sorted(STATE.glob("*.log"))]
        if files:
            os.execvp("tail", ["tail", "-n", "40", "-F", *files])
        return 0
    current = request()
    if command == "status":
        if current and current["phase"] == "running":
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            for key, url in (
                ("health", API + "/health/ready"),
                (
                    "models",
                    API + "/v1/workspaces/" + environment()["REVIEW_WORKSPACE_ID"] + "/model-profiles",
                ),
            ):
                try:
                    with opener.open(url, timeout=2) as response:
                        current[key] = json.load(response)
                except (OSError, ValueError):
                    current[key] = "unavailable"
        print(json.dumps(current or {"phase": "stopped", "logs": str(STATE)}, ensure_ascii=False, indent=2))
        return 0
    if command == "stop":
        if current:
            request("stop")
            deadline = time.monotonic() + 100
            while request() is not None and time.monotonic() < deadline:
                time.sleep(0.3)
            if request() is not None:
                raise RuntimeError("Остановка ещё не завершена; см. ./dev logs")
        print("Локальный стенд остановлен. БД и документы сохранены.")
        return 0
    process = None
    with (STATE / "command.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = request()
        if current is None:
            with (STATE / "launcher.log").open("ab") as output:
                process = subprocess.Popen(
                    [sys.executable, str(Path(__file__).resolve()), "_serve"],
                    cwd=ROOT,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
            # Serialize only the socket handshake, never the slow service startup.
            handshake = time.monotonic() + 5
            while request() is None and time.monotonic() < handshake:
                if process.poll() is not None:
                    raise RuntimeError(f"Local dev не запустился; см. {STATE / 'launcher.log'}")
                time.sleep(0.1)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        current = request()
        if current and current["phase"] == "running":
            print(f"Работает: {WEB}\nОстановка: ./dev stop\nЖурналы: ./dev logs")
            return 0
        if current and current["phase"] == "stopping":
            raise RuntimeError(f"Локальный стенд останавливается; см. {STATE / 'launcher.log'}")
        if process and process.poll() is not None:
            raise RuntimeError(f"Локальный запуск не удался. См. {STATE / 'launcher.log'}")
        time.sleep(0.3)
    raise RuntimeError("Запуск ещё не завершён; ./dev status или ./dev logs; отмена: ./dev stop")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
