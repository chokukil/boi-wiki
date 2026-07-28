from __future__ import annotations

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "validation" / "agent-playground-mainline" / "demo_account.py"
)
SPEC = importlib.util.spec_from_file_location("demo_account", MODULE_PATH)
assert SPEC and SPEC.loader
demo_account = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo_account)


def test_demo_identity_is_a_local_alias_for_existing_developer() -> None:
    assert demo_account.DEMO_USERNAME == "boi-dev"
    assert demo_account.DEMO_EMPLOYEE_ID == "100002"
    assert demo_account.DEMO_DISPLAY_NAME == "BoI Demo"
    assert demo_account.DEFAULT_REALM == "boi-validation"


def test_demo_tools_reject_non_local_keycloak_urls() -> None:
    assert (
        demo_account.ensure_local_url(
            "http://localhost:18082",
            label="Keycloak URL",
        )
        == "http://localhost:18082"
    )
    with pytest.raises(RuntimeError, match="local validation"):
        demo_account.ensure_local_url(
            "https://sso.example.com",
            label="Keycloak URL",
        )
    with pytest.raises(RuntimeError, match="credentials"):
        demo_account.ensure_local_url(
            "http://admin:password@localhost:18082",
            label="Keycloak URL",
        )


def test_demo_state_is_written_with_mode_0600() -> None:
    # The repository pytest tmp root may live on a Windows mount that cannot
    # represent POSIX file modes.  The real state file lives on the Linux home
    # filesystem, so exercise the same semantics in /tmp.
    with tempfile.TemporaryDirectory(prefix="boi-demo-state-", dir="/tmp") as root:
        state_path = Path(root) / "nested" / "demo-account.json"
        payload = {
            "environment": "local-boi-validation",
            "original_agent_hub_user": {"employee_id": "100002"},
        }
        demo_account.write_state(state_path, payload)

        assert stat.S_IMODE(state_path.stat().st_mode) == 0o600
        assert demo_account.read_state(state_path) == payload

        state_path.chmod(0o644)
        with pytest.raises(RuntimeError, match="0600"):
            demo_account.read_state(state_path)


def test_langflow_browser_allowlist_contains_demo_email() -> None:
    demo_account.assert_demo_email_allowlisted(
        ROOT
        / "validation"
        / "agent-playground-mainline"
        / "langflow-browser-allowed-emails.txt"
    )


def test_connected_key_launcher_separates_login_alias_from_employee_owner() -> None:
    script_root = ROOT / "validation" / "agent-playground-mainline"
    environment = dict(os.environ)
    environment.update(
        {
            "AGENT_HUB_USERNAME": "boi-dev",
            "AGENT_HUB_EMPLOYEE_ID": "100002",
        }
    )
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import run_agent_hub_with_connected_key as launcher; "
            "print(launcher.EMPLOYEE_ID)",
        ],
        cwd=script_root,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "100002"
