#!/usr/bin/env python3
"""Restore the original local validation identity after a boi-dev demo."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

from demo_account import (
    DEFAULT_AGENT_HUB_COMPOSE,
    DEFAULT_AGENT_HUB_SOURCE,
    DEFAULT_REALM,
    DEMO_EMPLOYEE_ID,
    DEMO_USERNAME,
    admin_headers,
    default_state_file,
    ensure_agent_hub_baseline,
    ensure_local_url,
    lookup_keycloak_user,
    read_agent_hub_user,
    read_state,
    restore_agent_hub_user,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Restore the local validation state after a boi-dev demo."
    )
    parser.add_argument("--keycloak-url", default="http://localhost:18082")
    parser.add_argument("--realm", default=DEFAULT_REALM)
    parser.add_argument("--state-file", type=Path, default=default_state_file())
    parser.add_argument(
        "--agent-hub-source", type=Path, default=DEFAULT_AGENT_HUB_SOURCE
    )
    parser.add_argument(
        "--agent-hub-compose", type=Path, default=DEFAULT_AGENT_HUB_COMPOSE
    )
    args = parser.parse_args()

    if args.realm != DEFAULT_REALM:
        raise RuntimeError("the shared demo login is only allowed in boi-validation")
    keycloak_url = ensure_local_url(args.keycloak_url, label="Keycloak URL")
    ensure_agent_hub_baseline(args.agent_hub_source)

    with httpx.Client(timeout=20) as client:
        headers = admin_headers(
            client,
            keycloak_url=keycloak_url,
            admin_username=os.getenv(
                "BOI_VALIDATION_KEYCLOAK_ADMIN_USERNAME", "validation-admin"
            ),
            admin_password=os.getenv(
                "BOI_VALIDATION_KEYCLOAK_ADMIN_PASSWORD", "validation-admin"
            ),
        )
        demo_user = lookup_keycloak_user(
            client,
            keycloak_url=keycloak_url,
            realm=args.realm,
            username=DEMO_USERNAME,
            headers=headers,
        )
        state = read_state(args.state_file)
        if state is None:
            if demo_user is None:
                print(
                    json.dumps(
                        {
                            "ok": True,
                            "already_restored": True,
                            "employee_id": DEMO_EMPLOYEE_ID,
                        }
                    )
                )
                return
            raise RuntimeError(
                "boi-dev exists but the original Agent Hub mapping backup is missing"
            )
        original = state.get("original_agent_hub_user") or {}
        if str(original.get("employee_id") or "") != DEMO_EMPLOYEE_ID:
            raise RuntimeError("demo state does not contain the original 100002 mapping")
        expected_subject = str((state.get("demo") or {}).get("keycloak_sub") or "")
        if demo_user is not None and str(demo_user.get("id") or "") != expected_subject:
            raise RuntimeError("boi-dev Keycloak subject changed after setup")

        restore_agent_hub_user(
            original,
            compose_file=args.agent_hub_compose,
            agent_hub_source=args.agent_hub_source,
        )
        restored = read_agent_hub_user(
            compose_file=args.agent_hub_compose,
            agent_hub_source=args.agent_hub_source,
        )
        for field in (
            "employee_id",
            "name",
            "email",
            "role",
            "keycloak_sub",
            "profile_image_url",
        ):
            if restored.get(field) != original.get(field):
                raise RuntimeError(
                    f"Agent Hub restore verification failed for {field}"
                )

        if demo_user is not None:
            subject = str(demo_user["id"])
            deleted = client.delete(
                f"{keycloak_url}/admin/realms/{args.realm}/users/{subject}",
                headers=headers,
            )
            if deleted.status_code != 204:
                raise RuntimeError(
                    f"failed to remove local demo user (HTTP {deleted.status_code})"
                )

    args.state_file.unlink()
    print(
        json.dumps(
            {
                "ok": True,
                "employee_id": DEMO_EMPLOYEE_ID,
                "agent_hub_mapping": "restored",
                "demo_user": "removed",
            }
        )
    )


if __name__ == "__main__":
    main()
