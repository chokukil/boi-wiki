"""Local-only lifecycle helpers for the shared Agent Playground demo login.

The demo username is an OIDC alias for employee 100002.  These helpers only
change validation Keycloak data and the existing Agent Hub validation user
mapping.  They never modify Agent Hub source or schema.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import httpx


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AGENT_HUB_SOURCE = Path("/home/chokukil/agent-hub-pr25-validation")
DEFAULT_AGENT_HUB_COMPOSE = ROOT / "validation" / "agent-hub" / "docker-compose.yml"
DEFAULT_PLAYGROUND_COMPOSE = (
    ROOT / "validation" / "agent-playground-mainline" / "docker-compose.yml"
)
DEFAULT_ALLOWLIST = (
    ROOT
    / "validation"
    / "agent-playground-mainline"
    / "langflow-browser-allowed-emails.txt"
)
EXPECTED_AGENT_HUB_SHA = "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
DEMO_USERNAME = "boi-dev"
DEMO_EMAIL = "boi-dev@boi.validation"
DEMO_EMPLOYEE_ID = "100002"
DEMO_DISPLAY_NAME = "BoI Demo"
DEMO_FIRST_NAME = "BoI"
DEMO_LAST_NAME = "Demo"
DEFAULT_REALM = "boi-validation"
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def default_state_file() -> Path:
    state_root = Path(
        os.getenv(
            "XDG_STATE_HOME",
            str(Path.home() / ".local" / "state"),
        )
    )
    return state_root / "boi-agent-playground" / "demo-account.json"


def ensure_local_url(value: str, *, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise RuntimeError(f"{label} must be an http(s) URL")
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(f"{label} must target the local validation environment")
    if parsed.username or parsed.password:
        raise RuntimeError(f"{label} must not contain credentials")
    return value.rstrip("/")


def ensure_agent_hub_baseline(source: Path) -> None:
    resolved = source.resolve()
    if resolved != DEFAULT_AGENT_HUB_SOURCE.resolve():
        raise RuntimeError(
            "Agent Hub source must be the immutable validation checkout "
            f"{DEFAULT_AGENT_HUB_SOURCE}"
        )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=resolved,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if head != EXPECTED_AGENT_HUB_SHA:
        raise RuntimeError(
            f"Agent Hub HEAD is {head}; expected {EXPECTED_AGENT_HUB_SHA}"
        )
    status_output = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=resolved,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    if status_output.strip():
        raise RuntimeError("Agent Hub validation checkout is not clean")


def admin_headers(
    client: httpx.Client,
    *,
    keycloak_url: str,
    admin_username: str,
    admin_password: str,
) -> dict[str, str]:
    response = client.post(
        f"{keycloak_url}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": admin_username,
            "password": admin_password,
        },
    )
    response.raise_for_status()
    token = str(response.json().get("access_token") or "")
    if not token:
        raise RuntimeError("Keycloak admin token response was empty")
    return {"Authorization": f"Bearer {token}"}


def lookup_keycloak_user(
    client: httpx.Client,
    *,
    keycloak_url: str,
    realm: str,
    username: str,
    headers: dict[str, str],
) -> dict[str, Any] | None:
    response = client.get(
        f"{keycloak_url}/admin/realms/{quote(realm, safe='')}/users",
        params={"username": username, "exact": "true"},
        headers=headers,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise RuntimeError("Keycloak user lookup returned an invalid response")
    exact = [row for row in rows if str(row.get("username") or "") == username]
    if len(exact) > 1:
        raise RuntimeError(f"multiple Keycloak users exist for {username}")
    return exact[0] if exact else None


def ensure_demo_keycloak_user(
    client: httpx.Client,
    *,
    keycloak_url: str,
    realm: str,
    headers: dict[str, str],
    password: str,
) -> dict[str, Any]:
    user = lookup_keycloak_user(
        client,
        keycloak_url=keycloak_url,
        realm=realm,
        username=DEMO_USERNAME,
        headers=headers,
    )
    representation = {
        "username": DEMO_USERNAME,
        "enabled": True,
        "emailVerified": True,
        "firstName": DEMO_FIRST_NAME,
        "lastName": DEMO_LAST_NAME,
        "email": DEMO_EMAIL,
        "attributes": {"empno": [DEMO_EMPLOYEE_ID]},
    }
    if user is None:
        created = client.post(
            f"{keycloak_url}/admin/realms/{quote(realm, safe='')}/users",
            headers={**headers, "Content-Type": "application/json"},
            json=representation,
        )
        if created.status_code != 201:
            raise RuntimeError(
                f"failed to create local demo user (HTTP {created.status_code})"
            )
        user = lookup_keycloak_user(
            client,
            keycloak_url=keycloak_url,
            realm=realm,
            username=DEMO_USERNAME,
            headers=headers,
        )
    else:
        current_empno = [
            str(value)
            for value in (user.get("attributes") or {}).get("empno", [])
        ]
        current_email = str(user.get("email") or "")
        if current_empno not in ([], [DEMO_EMPLOYEE_ID]):
            raise RuntimeError(
                f"{DEMO_USERNAME} belongs to another employee: {current_empno}"
            )
        if current_email not in ("", DEMO_EMAIL):
            raise RuntimeError(
                f"{DEMO_USERNAME} uses an unexpected email: {current_email}"
            )
        subject = str(user.get("id") or "")
        updated = client.put(
            f"{keycloak_url}/admin/realms/{quote(realm, safe='')}/users/"
            f"{quote(subject, safe='')}",
            headers={**headers, "Content-Type": "application/json"},
            json={**user, **representation},
        )
        if updated.status_code != 204:
            raise RuntimeError(
                f"failed to update local demo user (HTTP {updated.status_code})"
            )
        user = lookup_keycloak_user(
            client,
            keycloak_url=keycloak_url,
            realm=realm,
            username=DEMO_USERNAME,
            headers=headers,
        )
    if user is None:
        raise RuntimeError("local demo user was not found after creation")
    subject = str(user.get("id") or "")
    if not UUID_PATTERN.fullmatch(subject):
        raise RuntimeError("local demo user has an invalid Keycloak subject")
    reset = client.put(
        f"{keycloak_url}/admin/realms/{quote(realm, safe='')}/users/"
        f"{quote(subject, safe='')}/reset-password",
        headers={**headers, "Content-Type": "application/json"},
        json={"type": "password", "value": password, "temporary": False},
    )
    if reset.status_code != 204:
        raise RuntimeError(
            f"failed to set local demo password (HTTP {reset.status_code})"
        )
    return user


def compose_environment(agent_hub_source: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["AGENT_HUB_SOURCE_DIR"] = str(agent_hub_source.resolve())
    return environment


def run_agent_hub_sql(
    sql: str,
    *,
    compose_file: Path,
    agent_hub_source: Path,
    tuples_only: bool = False,
) -> str:
    args = [
        "docker",
        "compose",
        "-f",
        str(compose_file.resolve()),
        "exec",
        "-T",
        "db",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        "agenthub",
        "-d",
        "agenthub",
    ]
    if tuples_only:
        args.extend(["-A", "-t"])
    completed = subprocess.run(
        args,
        cwd=ROOT,
        env=compose_environment(agent_hub_source),
        input=sql.rstrip() + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise RuntimeError(
            "Agent Hub validation DB command failed"
            + (f": {detail[-1][:300]}" if detail else "")
        )
    return completed.stdout.strip()


def read_agent_hub_user(
    *,
    compose_file: Path,
    agent_hub_source: Path,
    employee_id: str = DEMO_EMPLOYEE_ID,
) -> dict[str, Any]:
    employee = sql_literal(employee_id)
    payload = run_agent_hub_sql(
        "SELECT row_to_json(candidate)::text FROM ("
        "SELECT employee_id, name, email, role, keycloak_sub, profile_image_url "
        f"FROM users WHERE employee_id = {employee}"
        ") AS candidate;",
        compose_file=compose_file,
        agent_hub_source=agent_hub_source,
        tuples_only=True,
    )
    if not payload:
        raise RuntimeError(f"Agent Hub validation user {employee_id} does not exist")
    parsed = json.loads(payload)
    if str(parsed.get("employee_id") or "") != employee_id:
        raise RuntimeError("Agent Hub validation user lookup returned another employee")
    return parsed


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def sql_value(value: Any) -> str:
    return "NULL" if value is None else sql_literal(str(value))


def update_agent_hub_for_demo(
    *,
    subject: str,
    compose_file: Path,
    agent_hub_source: Path,
) -> None:
    subject_value = sql_literal(subject)
    employee_value = sql_literal(DEMO_EMPLOYEE_ID)
    conflict = run_agent_hub_sql(
        "SELECT employee_id FROM users "
        f"WHERE keycloak_sub = {subject_value} "
        f"AND employee_id <> {employee_value};",
        compose_file=compose_file,
        agent_hub_source=agent_hub_source,
        tuples_only=True,
    )
    if conflict:
        raise RuntimeError(
            f"demo Keycloak subject is already mapped to Agent Hub user {conflict}"
        )
    run_agent_hub_sql(
        "BEGIN;\n"
        "UPDATE users SET "
        f"name = {sql_literal(DEMO_DISPLAY_NAME)}, "
        f"email = {sql_literal(DEMO_EMAIL)}, "
        f"keycloak_sub = {subject_value} "
        f"WHERE employee_id = {employee_value};\n"
        "COMMIT;",
        compose_file=compose_file,
        agent_hub_source=agent_hub_source,
    )


def restore_agent_hub_user(
    original: dict[str, Any],
    *,
    compose_file: Path,
    agent_hub_source: Path,
) -> None:
    if str(original.get("employee_id") or "") != DEMO_EMPLOYEE_ID:
        raise RuntimeError("demo state does not contain the original 100002 user")
    assignments = ", ".join(
        f"{column} = {sql_value(original.get(column))}"
        for column in (
            "name",
            "email",
            "role",
            "keycloak_sub",
            "profile_image_url",
        )
    )
    run_agent_hub_sql(
        "BEGIN;\n"
        f"UPDATE users SET {assignments} "
        f"WHERE employee_id = {sql_literal(DEMO_EMPLOYEE_ID)};\n"
        "COMMIT;",
        compose_file=compose_file,
        agent_hub_source=agent_hub_source,
    )


def read_state(path: Path) -> dict[str, Any] | None:
    try:
        details = path.stat()
    except FileNotFoundError:
        return None
    if stat.S_IMODE(details.st_mode) != 0o600:
        raise RuntimeError(f"demo state file must use mode 0600: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("demo state file is invalid")
    return payload


def write_state(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    handle, temporary_name = tempfile.mkstemp(
        prefix=".demo-account-",
        suffix=".json",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        os.fchmod(handle, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.replace(path)
        os.chmod(path, 0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def assert_demo_email_allowlisted(path: Path) -> None:
    emails = {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    if DEMO_EMAIL not in emails:
        raise RuntimeError(
            f"{DEMO_EMAIL} is missing from the Langflow browser SSO allowlist"
        )


def restart_langflow_browser_sso(compose_file: Path) -> None:
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(compose_file.resolve()),
            "restart",
            "langflow-browser-sso",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise RuntimeError(
            "failed to reload the Langflow browser SSO allowlist"
            + (f": {detail[-1][:300]}" if detail else "")
        )
