#!/usr/bin/env python3
"""Prepare boi-dev as a local alias for the validated employee 100002 space."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

from demo_account import (
    DEFAULT_AGENT_HUB_COMPOSE,
    DEFAULT_AGENT_HUB_SOURCE,
    DEFAULT_ALLOWLIST,
    DEFAULT_PLAYGROUND_COMPOSE,
    DEFAULT_REALM,
    DEMO_DISPLAY_NAME,
    DEMO_EMAIL,
    DEMO_EMPLOYEE_ID,
    DEMO_USERNAME,
    admin_headers,
    assert_demo_email_allowlisted,
    default_state_file,
    ensure_agent_hub_baseline,
    ensure_demo_keycloak_user,
    ensure_empno_user_profile,
    ensure_local_url,
    read_agent_hub_user,
    read_state,
    restart_langflow_browser_sso,
    update_agent_hub_for_demo,
    write_state,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare the local boi-dev shared demo login."
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
    parser.add_argument(
        "--playground-compose", type=Path, default=DEFAULT_PLAYGROUND_COMPOSE
    )
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument(
        "--no-browser-sso-restart",
        action="store_true",
        help="Do not restart the local oauth2-proxy after checking its allowlist.",
    )
    args = parser.parse_args()

    password = os.getenv("BOI_DEMO_PASSWORD", "")
    if not password:
        raise RuntimeError("BOI_DEMO_PASSWORD is required")
    if args.realm != DEFAULT_REALM:
        raise RuntimeError("the shared demo login is only allowed in boi-validation")
    keycloak_url = ensure_local_url(args.keycloak_url, label="Keycloak URL")
    ensure_agent_hub_baseline(args.agent_hub_source)
    assert_demo_email_allowlisted(args.allowlist)

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
        ensure_empno_user_profile(
            client,
            keycloak_url=keycloak_url,
            realm=args.realm,
            headers=headers,
        )
        demo_user = ensure_demo_keycloak_user(
            client,
            keycloak_url=keycloak_url,
            realm=args.realm,
            headers=headers,
            password=password,
        )

    subject = str(demo_user["id"])
    existing_state = read_state(args.state_file)
    current_user = read_agent_hub_user(
        compose_file=args.agent_hub_compose,
        agent_hub_source=args.agent_hub_source,
    )
    if existing_state is None:
        if (
            str(current_user.get("keycloak_sub") or "") == subject
            or str(current_user.get("email") or "") == DEMO_EMAIL
        ):
            raise RuntimeError(
                "Agent Hub already uses boi-dev but the original mapping backup is missing"
            )
        state = {
            "version": 1,
            "environment": "local-boi-validation",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_hub_source": str(args.agent_hub_source.resolve()),
            "agent_hub_compose": str(args.agent_hub_compose.resolve()),
            "keycloak_url": keycloak_url,
            "realm": args.realm,
            "demo": {
                "username": DEMO_USERNAME,
                "email": DEMO_EMAIL,
                "employee_id": DEMO_EMPLOYEE_ID,
                "keycloak_sub": subject,
            },
            "original_agent_hub_user": current_user,
        }
    else:
        state = existing_state
        original = state.get("original_agent_hub_user") or {}
        if str(original.get("employee_id") or "") != DEMO_EMPLOYEE_ID:
            raise RuntimeError("demo state does not contain the original 100002 mapping")
        if state.get("environment") != "local-boi-validation":
            raise RuntimeError("demo state belongs to another environment")
        state["demo"] = {
            "username": DEMO_USERNAME,
            "email": DEMO_EMAIL,
            "employee_id": DEMO_EMPLOYEE_ID,
            "keycloak_sub": subject,
        }
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_state(args.state_file, state)

    update_agent_hub_for_demo(
        subject=subject,
        compose_file=args.agent_hub_compose,
        agent_hub_source=args.agent_hub_source,
    )
    mapped = read_agent_hub_user(
        compose_file=args.agent_hub_compose,
        agent_hub_source=args.agent_hub_source,
    )
    if (
        mapped.get("keycloak_sub") != subject
        or mapped.get("name") != DEMO_DISPLAY_NAME
        or mapped.get("email") != DEMO_EMAIL
    ):
        raise RuntimeError("Agent Hub demo mapping verification failed")

    if not args.no_browser_sso_restart:
        restart_langflow_browser_sso(args.playground_compose)

    print(
        json.dumps(
            {
                "ok": True,
                "environment": "local-boi-validation",
                "username": DEMO_USERNAME,
                "employee_id": DEMO_EMPLOYEE_ID,
                "display_name": DEMO_DISPLAY_NAME,
                "agent_hub_mapping": "prepared",
                "langflow_browser_allowlisted": True,
                "state_file": str(args.state_file),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
