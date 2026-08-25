#!/usr/bin/env python3
"""Build the reviewed testcase-identity contract used by the final report."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from _pytest.junitxml import mangle_test_address


SUITES = {
    "science_tests": {
        "suite_id": "science-tests",
        "pytest_args": ["tests", "-k", "science and not mcp"],
    },
    "mcp_tests": {
        "suite_id": "science-mcp",
        "pytest_args": ["tests/test_science_mcp.py"],
    },
    "full_regression": {
        "suite_id": "full-regression",
        "pytest_args": ["tests"],
    },
}


def canonical_digest(value: object) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def junit_identity(node_id: str) -> str:
    address = mangle_test_address(node_id)
    if len(address) < 2:
        raise ValueError(f"invalid pytest node ID: {node_id}")
    return f"{'.'.join(address[:-1])}::{address[-1]}"


def collect(repo_root: Path, pytest_args: list[str]) -> list[str]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--capture=no",
            *pytest_args,
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    node_ids = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    ]
    identities = sorted(junit_identity(node_id) for node_id in node_ids)
    if not identities or len(identities) != len(set(identities)):
        raise ValueError("collected testcase identities must be non-empty and unique")
    return identities


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    suites: dict[str, object] = {}
    for name, definition in SUITES.items():
        identities = collect(repo_root, list(definition["pytest_args"]))
        suites[name] = {
            **definition,
            "collected": len(identities),
            "testcase_identity_digest": canonical_digest(identities),
        }
    payload = {
        "schema_version": "science-test-suite-contract/0.1",
        "identity_format": "pytest-junit-classname::name",
        "suites": suites,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
