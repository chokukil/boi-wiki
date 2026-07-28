#!/usr/bin/env python3
"""Verify official Langflow external-JWT validation without patching Langflow.

The verifier starts an ephemeral official 1.11.0 container with a temporary
SQLite database and an in-process JWKS endpoint. It proves that a valid
employee-bound token is accepted and that signature, issuer, audience, and
expiry failures are rejected. Raw JWTs are never printed or written.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


OFFICIAL_IMAGE = (
    "langflowai/langflow:1.11.0@"
    "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf"
)
CONTAINER = "boi-langflow-external-auth-contract-audit"
JWKS_CONTAINER = f"{CONTAINER}-jwks"
HOST_PORT = 17872
JWKS_PORT = 18388
ISSUER = "boi-external-auth-contract-audit"
AUDIENCE = "boi-wiki"


def b64url_uint(value: int) -> str:
    width = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(width, "big")).rstrip(b"=").decode()


def public_jwk(key: rsa.RSAPrivateKey, kid: str) -> dict[str, str]:
    numbers = key.public_key().public_numbers()
    return {
        "kty": "RSA",
        "use": "sig",
        "alg": "RS256",
        "kid": kid,
        "n": b64url_uint(numbers.n),
        "e": b64url_uint(numbers.e),
    }


def request_status(url: str, *, token: str | None = None) -> tuple[int, str]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def wait_for_health() -> None:
    # The first official-image boot performs its own schema migration.  Lazy
    # component loading keeps this verifier focused on the authentication
    # contract, while the longer deadline still accommodates a cold image/DB.
    deadline = time.time() + 420
    while time.time() < deadline:
        try:
            status, _ = request_status(f"http://localhost:{HOST_PORT}/health")
            # Some 1.11 builds protect the health route when external auth is
            # enabled.  A deterministic auth rejection still proves the HTTP
            # server is ready for the whoami contract checks below.
            if status in {200, 401, 403}:
                return
        except (OSError, TimeoutError):
            pass
        time.sleep(0.5)
    logs = subprocess.run(
        ["docker", "logs", "--tail", "80", CONTAINER],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (logs.stdout + "\n" + logs.stderr)[-4000:]
    raise RuntimeError(f"Langflow external-auth audit did not become healthy: {output}")


def container_exists() -> bool:
    return (
        subprocess.run(
            ["docker", "inspect", CONTAINER],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def named_container_exists(name: str) -> bool:
    return (
        subprocess.run(
            ["docker", "inspect", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def stop_owned_named_container(name: str, expected_label: str) -> None:
    if not named_container_exists(name):
        return
    label = subprocess.check_output(
        [
            "docker",
            "inspect",
            "--format",
            "{{index .Config.Labels \"boi.validation\"}}",
            name,
        ],
        text=True,
    ).strip()
    if label != expected_label:
        raise RuntimeError(f"refusing to stop an unrelated container named {name}")
    subprocess.run(
        ["docker", "stop", "--time", "10", name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        ["docker", "rm", "--force", name],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def stop_owned_container() -> None:
    stop_owned_named_container(JWKS_CONTAINER, "external-auth-jwks")
    stop_owned_named_container(CONTAINER, "external-auth-contract")


def issue_token(
    key: rsa.RSAPrivateKey,
    kid: str,
    *,
    issuer: str = ISSUER,
    audience: str = AUDIENCE,
    expires_at: int,
) -> str:
    now = int(time.time())
    claims = {
        "sub": "100002",
        "empno": "100002",
        "preferred_username": "100002",
        "name": "BoI Developer",
        "email": "100002@boi.validation",
        "iss": issuer,
        "aud": audience,
        "iat": now - 1,
        "nbf": now - 2,
        "exp": expires_at,
    }
    return jwt.encode(
        claims,
        key,
        algorithm="RS256",
        headers={"kid": kid, "typ": "JWT"},
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--keep-container-on-failure", action="store_true")
    parser.add_argument(
        "--reuse-owned-container",
        action="store_true",
        help="reuse a running verifier-owned container after a timed-out cold boot",
    )
    args = parser.parse_args()

    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_der = signing_key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    kid = hashlib.sha256(public_der).hexdigest()[:16]
    jwks_payload = {"keys": [public_jwk(signing_key, kid)]}
    reuse_container = args.reuse_owned_container and container_exists()
    if reuse_container:
        label = subprocess.check_output(
            [
                "docker",
                "inspect",
                "--format",
                "{{index .Config.Labels \"boi.validation\"}}",
                CONTAINER,
            ],
            text=True,
        ).strip()
        running = subprocess.check_output(
            ["docker", "inspect", "--format", "{{.State.Running}}", CONTAINER],
            text=True,
        ).strip()
        if label != "external-auth-contract" or running != "true":
            raise RuntimeError("the requested reusable container is not a running verifier-owned container")
    elif container_exists():
        stop_owned_container()

    run_command = [
        "docker",
        "run",
        "--detach",
        "--name",
        CONTAINER,
        "--label",
        "boi.validation=external-auth-contract",
        "--publish",
        f"127.0.0.1:{HOST_PORT}:{HOST_PORT}",
        "--env",
        "LANGFLOW_DATABASE_URL=sqlite:////tmp/langflow/langflow.db",
        "--env",
        "LANGFLOW_CONFIG_DIR=/tmp/langflow",
        "--env",
        "LANGFLOW_LOG_LEVEL=info",
        "--env",
        "LANGFLOW_LOG_ENV=container",
        "--env",
        "LANGFLOW_AUTO_LOGIN=false",
        "--env",
        "LANGFLOW_SKIP_AUTH_AUTO_LOGIN=false",
        "--env",
        "LANGFLOW_ENABLE_SIGNUP=false",
        "--env",
        "LANGFLOW_NEW_USER_IS_ACTIVE=true",
        "--env",
        "LANGFLOW_LAZY_LOAD_COMPONENTS=true",
        "--env",
        "LANGFLOW_CREATE_STARTER_PROJECTS=false",
        "--env",
        "LANGFLOW_UPDATE_STARTER_PROJECTS=false",
        "--env",
        "LANGFLOW_TELEMETRY_WRITER_ENABLED=false",
        "--env",
        "LANGFLOW_SUPERUSER=boi-external-auth-audit",
        "--env",
        "LANGFLOW_SUPERUSER_PASSWORD=validation-only-change-me",
        "--env",
        "LANGFLOW_SECRET_KEY=U1NPLWNvbnRyYWN0LWF1ZGl0LXNlY3JldC1rZXktMjAyNg==",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_ENABLED=true",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_PROVIDER=boi-contract-audit",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_TOKEN_HEADER=Authorization",
        "--env",
        f"LANGFLOW_EXTERNAL_AUTH_JWKS_URL=http://127.0.0.1:{JWKS_PORT}/jwks.json",
        "--env",
        f"LANGFLOW_EXTERNAL_AUTH_ISSUER={ISSUER}",
        "--env",
        f"LANGFLOW_EXTERNAL_AUTH_AUDIENCE={AUDIENCE}",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_ALGORITHMS=RS256",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_SUBJECT_CLAIM=empno",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_USERNAME_CLAIM=empno",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_EMAIL_CLAIM=email",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_NAME_CLAIM=name",
        "--env",
        "LANGFLOW_EXTERNAL_AUTH_TRUSTED_JWT_DECODE=false",
        OFFICIAL_IMAGE,
        "langflow",
        "run",
        "--port",
        str(HOST_PORT),
        "--host",
        "0.0.0.0",
        "--workers",
        "1",
        "--log-level",
        "info",
    ]

    result: dict[str, Any] = {
        "ok": False,
        "image": OFFICIAL_IMAGE,
        "container": CONTAINER,
        "token_header": "Authorization: Bearer",
        "token_exposed": False,
        "checks": {},
    }
    tokens: list[str] = []
    with tempfile.TemporaryDirectory(prefix="boi-lf-jwks-") as jwks_dir:
        jwks_path = Path(jwks_dir) / "jwks.json"
        jwks_path.write_text(json.dumps(jwks_payload), encoding="utf-8")
        try:
            if not reuse_container:
                subprocess.run(run_command, check=True, stdout=subprocess.DEVNULL)
            stop_owned_named_container(JWKS_CONTAINER, "external-auth-jwks")
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    JWKS_CONTAINER,
                    "--label",
                    "boi.validation=external-auth-jwks",
                    "--network",
                    f"container:{CONTAINER}",
                    "--volume",
                    f"{jwks_dir}:/jwks:ro",
                    OFFICIAL_IMAGE,
                    "python",
                    "-m",
                    "http.server",
                    str(JWKS_PORT),
                    "--bind",
                    "127.0.0.1",
                    "--directory",
                    "/jwks",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            wait_for_health()
            now = int(time.time())
            valid = issue_token(signing_key, kid, expires_at=now + 120)
            invalid_signature = issue_token(wrong_key, kid, expires_at=now + 120)
            invalid_issuer = issue_token(
                signing_key,
                kid,
                issuer="wrong-issuer",
                expires_at=now + 120,
            )
            invalid_audience = issue_token(
                signing_key,
                kid,
                audience="wrong-audience",
                expires_at=now + 120,
            )
            expired = issue_token(signing_key, kid, expires_at=now - 120)
            tokens.extend([valid, invalid_signature, invalid_issuer, invalid_audience, expired])

            endpoint = f"http://localhost:{HOST_PORT}/api/v1/users/whoami"
            statuses: dict[str, int] = {}
            bodies: dict[str, str] = {}
            for name, token in {
                "valid": valid,
                "invalid_signature": invalid_signature,
                "invalid_issuer": invalid_issuer,
                "invalid_audience": invalid_audience,
                "expired": expired,
            }.items():
                status, body = request_status(endpoint, token=token)
                statuses[name] = status
                bodies[name] = body
            no_token_status, no_token_body = request_status(endpoint)
            statuses["missing_token"] = no_token_status
            bodies["missing_token"] = no_token_body

            valid_body = json.loads(bodies["valid"]) if statuses["valid"] == 200 else {}

            def safe_detail(body: str) -> str:
                try:
                    parsed = json.loads(body)
                    detail = parsed.get("detail") if isinstance(parsed, dict) else parsed
                    return str(detail)[:500]
                except json.JSONDecodeError:
                    return body[:500]

            result["checks"] = {
                "valid": {
                    "status": statuses["valid"],
                    "username": str(valid_body.get("username") or ""),
                    "detail": safe_detail(bodies["valid"]),
                },
                **{
                    name: {
                        "status": statuses[name],
                        "rejected": statuses[name] in {401, 403},
                        "detail": safe_detail(bodies[name]),
                    }
                    for name in (
                        "invalid_signature",
                        "invalid_issuer",
                        "invalid_audience",
                        "expired",
                        "missing_token",
                    )
                },
            }
            logs = subprocess.check_output(
                ["docker", "logs", "--since", "10m", CONTAINER],
                text=True,
            )
            jwks_logs = subprocess.check_output(
                ["docker", "logs", JWKS_CONTAINER],
                text=True,
                stderr=subprocess.STDOUT,
            )
            serialized_bodies = "\n".join(bodies.values())
            result["token_exposed"] = any(
                token in logs or token in serialized_bodies for token in tokens
            )
            result["jwks_requests"] = jwks_logs.count("GET /jwks.json")
            result["ok"] = (
                statuses["valid"] == 200
                and str(valid_body.get("username") or "") == "100002"
                and all(
                    statuses[name] in {401, 403}
                    for name in (
                        "invalid_signature",
                        "invalid_issuer",
                        "invalid_audience",
                        "expired",
                        "missing_token",
                    )
                )
                and result["jwks_requests"] > 0
                and result["token_exposed"] is False
            )
            if not result["ok"]:
                raise RuntimeError(f"external-auth contract failed: {result['checks']}")
        finally:
            if container_exists() and (result["ok"] or not args.keep_container_on_failure):
                stop_owned_container()
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
