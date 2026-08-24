#!/usr/bin/env python3
"""Run deterministic public qualification for an inactive Science Release."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.science.qualification import (  # noqa: E402
    qualify_release_candidate,
    render_preflight_markdown,
)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--boi-root", type=Path, required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--holdout-path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        result = qualify_release_candidate(
            arguments.boi_root.resolve(),
            arguments.release_id,
            holdout_path=(
                arguments.holdout_path.resolve() if arguments.holdout_path else None
            ),
        )
    except Exception as exc:
        print(
            f"Science release qualification failed closed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    _atomic_text(arguments.output.resolve(), render_preflight_markdown(result))
    return (
        0
        if all(result.gates[f"G{number}"].status == "PASS" for number in range(5))
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
