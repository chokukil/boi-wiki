#!/usr/bin/env python3
"""Run a validation command with the current Playground Langflow key.

The encrypted credential is read from the isolated validation container,
decrypted only in this process, and passed to the replacement process through
its environment.  The raw key is never written or printed.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from run_agent_hub_with_connected_key import (
    EMPLOYEE_ID,
    _connected_api_key,
    _container_environment,
    _container_json,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    if len(sys.argv) < 2:
        raise RuntimeError("usage: run_with_connected_langflow_key.py COMMAND [ARG ...]")

    record = _container_json(
        f"/runtime/agent-playground/users/{EMPLOYEE_ID}.json"
    )
    if str(record.get("employee_id") or "") != EMPLOYEE_ID:
        raise RuntimeError("Playground credential owner mismatch")
    encryption_secret = str(
        _container_environment().get("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY") or ""
    )
    if not encryption_secret:
        raise RuntimeError("Playground encryption key is unavailable")

    child_environment = dict(os.environ)
    child_environment["LANGFLOW_API_KEY"] = _connected_api_key(
        record,
        encryption_secret,
    )
    command = list(sys.argv[1:])
    candidate = Path(command[0])
    if not candidate.is_absolute() and "/" in command[0]:
        command[0] = str((REPO_ROOT / candidate).resolve())
    os.execvpe(command[0], command, child_environment)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Connected Langflow validation launcher failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
