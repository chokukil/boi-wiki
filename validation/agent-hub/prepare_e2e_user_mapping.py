#!/usr/bin/env python3
"""Align immutable Agent Hub's isolated E2E users with validation Keycloak.

This helper changes validation data only. It does not alter Agent Hub source,
schema, migrations, or any BoI runtime path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COMPOSE = ROOT / "validation" / "agent-hub" / "docker-compose.yml"
DEFAULT_AGENT_HUB_SOURCE = Path("/home/chokukil/agent-hub-pr25-validation")
EMPLOYEE_ROLES = {
    "100001": "user",
    "100002": "user",
    "2074795": "admin",
}
USER_PROFILES = {
    "100001": ("BoI", "Administrator"),
    "100002": ("BoI", "Developer"),
    "2074795": ("BoI", "Reviewer"),
}
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare isolated Agent Hub E2E user-to-Keycloak mappings."
    )
    parser.add_argument("--identity-file", type=Path, required=True)
    parser.add_argument("--keycloak-url", default="http://localhost:18082")
    parser.add_argument("--compose-file", type=Path, default=DEFAULT_COMPOSE)
    parser.add_argument(
        "--reset-endpoints-for",
        action="append",
        default=[],
        choices=sorted(EMPLOYEE_ROLES),
        help="Remove only this validation user's saved Langflow endpoint settings.",
    )
    args = parser.parse_args()

    identities = json.loads(args.identity_file.read_text(encoding="utf-8"))
    missing = sorted(employee_id for employee_id in EMPLOYEE_ROLES if not identities.get(employee_id))
    if missing:
        raise RuntimeError(f"validation identities are missing: {missing}")

    keycloak_url = args.keycloak_url.rstrip("/")
    with httpx.Client(timeout=20) as client:
        token_response = client.post(
            f"{keycloak_url}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": "validation-admin",
                "password": "validation-admin",
            },
        )
        token_response.raise_for_status()
        headers = {
            "Authorization": f"Bearer {token_response.json()['access_token']}",
        }
        subjects: dict[str, str] = {}
        for employee_id in EMPLOYEE_ROLES:
            def lookup_user() -> list[dict]:
                response = client.get(
                    f"{keycloak_url}/admin/realms/boi-validation/users",
                    params={"username": employee_id, "exact": "true"},
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()

            rows = lookup_user()
            if not rows:
                first_name, last_name = USER_PROFILES[employee_id]
                created = client.post(
                    f"{keycloak_url}/admin/realms/boi-validation/users",
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "username": employee_id,
                        "enabled": True,
                        "emailVerified": True,
                        "firstName": first_name,
                        "lastName": last_name,
                        "email": f"{employee_id}@boi.validation",
                        "attributes": {"empno": [employee_id]},
                    },
                )
                if created.status_code != 201:
                    raise RuntimeError(
                        f"failed to create validation Keycloak user {employee_id}"
                    )
                rows = lookup_user()
            if len(rows) != 1:
                raise RuntimeError(f"expected one Keycloak user for {employee_id}")
            subject = str(rows[0].get("id") or "")
            if not UUID_PATTERN.fullmatch(subject):
                raise RuntimeError(f"invalid Keycloak subject for {employee_id}")
            password_reset = client.put(
                f"{keycloak_url}/admin/realms/boi-validation/users/{subject}/reset-password",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "type": "password",
                    "value": str(identities[employee_id]),
                    "temporary": False,
                },
            )
            if password_reset.status_code != 204:
                raise RuntimeError(
                    f"failed to set validation Keycloak password for {employee_id}"
                )
            subjects[employee_id] = subject

    statements = ["BEGIN;"]
    for employee_id, role in EMPLOYEE_ROLES.items():
        subject = subjects[employee_id]
        statements.append(
            "UPDATE users SET keycloak_sub = NULL "
            f"WHERE keycloak_sub = {sql_literal(subject)} "
            f"AND employee_id <> {sql_literal(employee_id)};"
        )
        statements.append(
            "INSERT INTO users "
            "(employee_id, name, email, role, keycloak_sub, profile_image_url) VALUES "
            f"({sql_literal(employee_id)}, {sql_literal('BoI Validation')}, "
            f"{sql_literal(employee_id + '@boi.validation')}, {sql_literal(role)}, "
            f"{sql_literal(subject)}, '') "
            "ON CONFLICT (employee_id) DO UPDATE SET "
            "name = EXCLUDED.name, email = EXCLUDED.email, role = EXCLUDED.role, "
            "keycloak_sub = EXCLUDED.keycloak_sub;"
        )
    for employee_id in args.reset_endpoints_for:
        statements.append(
            "DELETE FROM langflow_endpoints "
            f"WHERE user_id = {sql_literal(employee_id)};"
        )
    statements.append("COMMIT;")

    environment = os.environ.copy()
    environment.setdefault("AGENT_HUB_SOURCE_DIR", str(DEFAULT_AGENT_HUB_SOURCE))
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(args.compose_file),
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
        ],
        cwd=ROOT,
        env=environment,
        input="\n".join(statements) + "\n",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Agent Hub validation user mapping failed: "
            + completed.stderr.strip()[:500]
        )
    print(json.dumps({"ok": True, "employees": sorted(EMPLOYEE_ROLES)}))


if __name__ == "__main__":
    main()
