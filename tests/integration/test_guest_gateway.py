from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).parents[2]
NGINX_IMAGE = "nginx:1.29.4-alpine"


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=check, timeout=30)


@pytest.fixture
def gateway(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[httpx.Client]:
    if os.environ.get("REVIEW_GATEWAY_TEST") != "1":
        pytest.skip("set REVIEW_GATEWAY_TEST=1 to run the isolated nginx gateway smoke")
    guest_access, api_guest_access = request.param
    prefix = f"review-guest-gateway-test-{uuid4().hex[:12]}"
    proxy_name = f"{prefix}-proxy"
    gateway_name = f"{prefix}-gateway"
    gateway_root = tmp_path / "gateway"
    certificate_dir = gateway_root / "etc" / "letsencrypt" / "live" / "127.0.0.1"
    certificate_dir.mkdir(parents=True)
    certificate = certificate_dir / "fullchain.pem"
    run(
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-keyout", str(certificate_dir / "privkey.pem"), "-out", str(certificate),
        "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
    )
    password_hash = run("openssl", "passwd", "-apr1", "synthetic-password").stdout.strip()
    secret = gateway_root / "run" / "review-secrets" / "gateway.htpasswd"
    secret.parent.mkdir(parents=True)
    secret.write_text(f"review:{password_hash}\n")
    for source, destination in [
        ("nginx.gateway.conf.template", "etc/nginx/templates/review.conf.template"),
        ("gateway-copy-secrets.sh", "docker-entrypoint.d/20-review-copy-secrets.sh"),
    ]:
        target = gateway_root / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "deploy" / "compose" / source, target)
    proxy_config = tmp_path / "proxy.conf"
    proxy_config.write_text(
        "server { listen 8080; access_log off; "
        f"location = /health/guest-access {{ return {204 if api_guest_access else 403}; }} "
        'location / { default_type text/plain; return 200 "synthetic upstream\\n"; } }'
    )
    run("docker", "network", "create", prefix)
    try:
        run(
            "docker", "create", "--pull=never", "--name", proxy_name,
            "--network", prefix, "--network-alias", "proxy", NGINX_IMAGE,
        )
        run("docker", "cp", str(proxy_config), f"{proxy_name}:/etc/nginx/conf.d/default.conf")
        run("docker", "start", proxy_name)
        run(
            "docker", "create", "--pull=never", "--name", gateway_name,
            "--network", prefix, "--publish", "127.0.0.1::443",
            "--env", "REVIEW_PUBLIC_IP=127.0.0.1", "--env", f"REVIEW_GUEST_ACCESS={guest_access}",
            "--env", "NGINX_ENVSUBST_FILTER=^REVIEW_(PUBLIC_IP|GUEST_ACCESS)$",
            NGINX_IMAGE,
        )
        run("docker", "cp", f"{gateway_root}/.", f"{gateway_name}:/")
        run("docker", "start", gateway_name)
        state = json.loads(run("docker", "inspect", gateway_name).stdout)[0]
        ports = state["NetworkSettings"]["Ports"].get("443/tcp")
        if not ports:
            logs = run("docker", "logs", gateway_name, check=False)
            pytest.fail(logs.stdout + logs.stderr)
        port = ports[0]["HostPort"]
        tls = ssl.create_default_context(cafile=str(certificate))
        with httpx.Client(base_url=f"https://127.0.0.1:{port}", verify=tls, timeout=3) as client:
            for attempt in range(40):
                try:
                    client.get("/")
                    break
                except httpx.TransportError:
                    if attempt == 39:
                        logs = run("docker", "logs", gateway_name, check=False)
                        pytest.fail(logs.stdout + logs.stderr)
                    time.sleep(0.1)
            yield client
    finally:
        run("docker", "rm", "--force", gateway_name, proxy_name, check=False)
        run("docker", "network", "rm", prefix, check=False)


@pytest.mark.integration
@pytest.mark.parametrize("gateway", [("true", True)], indirect=True)
def test_guest_gateway_opens_main_and_keeps_every_demo_route_private(gateway: httpx.Client) -> None:
    for path in ["/", "/api/v1/bootstrap", "/v1/bootstrap", "/docs/", "/openapi.json"]:
        assert gateway.get(path).status_code == 200, path
    for path in [
        "/demo", "/demo/", "/demo/new", "/demo/data/demo.json", "/demo/data/document.pdf",
        "/demo/mockServiceWorker.js", "/demo/api/v1/bootstrap", "/%64emo/data/demo.json",
        "/demo%2Fdata%2Fdocument.pdf", "/demo//data/demo.json",
    ]:
        response = gateway.get(path, headers={"Cookie": "review_guest=synthetic-cookie"})
        assert response.status_code == 401, path
        assert 'Basic realm="AI Review MVP"' in response.headers["www-authenticate"]
        assert gateway.get(path, auth=("review", "synthetic-password")).status_code == 200, path
    assert gateway.get("/_review_guest_access_check").status_code == 404
    response = gateway.post("/api/v1/review-runs", headers={"Origin": "https://cross-origin.invalid"})
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize("gateway", [("false", False)], indirect=True)
def test_trusted_gateway_requires_basic_for_main_and_api(gateway: httpx.Client) -> None:
    for path in ["/", "/api/v1/bootstrap", "/v1/bootstrap", "/demo", "/demo/data/demo.json", "/health/ready"]:
        assert gateway.get(path).status_code == 401, path
        assert gateway.get(path, auth=("review", "synthetic-password")).status_code == 200, path


@pytest.mark.integration
@pytest.mark.parametrize("gateway", [("true", False)], indirect=True)
def test_public_gateway_fails_closed_when_api_still_uses_trusted_mode(gateway: httpx.Client) -> None:
    for path in ["/", "/api/v1/bootstrap", "/v1/bootstrap"]:
        assert gateway.get(path).status_code == 403, path
        assert gateway.get(path, auth=("review", "synthetic-password")).status_code == 403, path


@pytest.mark.parametrize("flag", ["TRUE", "1", "yes", "invalid", ""])
def test_gateway_rejects_invalid_flag_before_handling_secrets(flag: str) -> None:
    result = subprocess.run(
        ["sh", str(ROOT / "deploy/compose/gateway-copy-secrets.sh")],
        env={**os.environ, "REVIEW_GUEST_ACCESS": flag},
        capture_output=True, text=True, check=False, timeout=5,
    )
    assert result.returncode == 1
    assert result.stderr.strip() == "REVIEW_GUEST_ACCESS must be true or false"


def test_compose_passes_the_same_flag_to_api_and_gateway() -> None:
    base = (ROOT / "deploy/compose/compose.yaml").read_text()
    production = (ROOT / "deploy/compose/compose.production.yaml").read_text()
    setting = "REVIEW_GUEST_ACCESS: ${REVIEW_GUEST_ACCESS:-false}"
    assert setting in base.partition("  api:")[2].partition("  proxy:")[0]
    assert setting in production.partition("  gateway:")[2]
    assert "NGINX_ENVSUBST_FILTER: ^REVIEW_(PUBLIC_IP|GUEST_ACCESS)$" in production
