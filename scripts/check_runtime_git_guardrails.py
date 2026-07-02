#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import subprocess
from pathlib import Path


BLOCKED_PATTERNS = (
    "data/actions/*",
    "data/private-trash/*",
    "data/events/*.jsonl",
    "data/boi/private/*/inbox-reports/*",
    "data/boi/private/*/boi-private-*.md",
    "data/boi/private/*/**/boi-private-*.md",
    "data/boi/team/*/boi-team-*.md",
    "data/boi/public/boi-public-*.md",
)


def staged_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--cached", "--name-only", "--diff-filter=ACMRT"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_blocked_runtime_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in BLOCKED_PATTERNS)


def file_size(root: Path, path: str) -> int:
    candidate = root / path
    if not candidate.exists() or not candidate.is_file():
        return 0
    return candidate.stat().st_size


def main() -> int:
    parser = argparse.ArgumentParser(description="Prevent runtime BoI evidence/log files from being committed.")
    parser.add_argument("--root", default=".", help="Git repository root")
    parser.add_argument("--warn-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--fail-bytes", type=int, default=25 * 1024 * 1024)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paths = staged_paths(root)
    blocked = [path for path in paths if is_blocked_runtime_path(path)]
    oversized = [
        {"path": path, "bytes": file_size(root, path)}
        for path in paths
        if file_size(root, path) >= args.fail_bytes
    ]
    warnings = [
        {"path": path, "bytes": file_size(root, path)}
        for path in paths
        if args.warn_bytes <= file_size(root, path) < args.fail_bytes
    ]

    if blocked or oversized:
        print("Runtime git guardrails: FAILED")
        if blocked:
            print("Runtime/generated files must not be staged:")
            for path in blocked:
                print(f"  - {path}")
        if oversized:
            print("Staged files exceed the hard size limit:")
            for item in oversized:
                print(f"  - {item['path']} ({item['bytes']} bytes)")
        return 1

    print("Runtime git guardrails: OK")
    if warnings:
        print("Large staged files warning:")
        for item in warnings:
            print(f"  - {item['path']} ({item['bytes']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
