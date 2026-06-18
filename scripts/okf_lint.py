#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from boi_api.app.okf import lint_data_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint OKF/BoI markdown and materialized log payloads.")
    parser.add_argument("--root", default="data", help="Data root containing boi/, events/, and actions/ directories.")
    parser.add_argument("--include-logs", action="store_true", help="Also validate materialized BoI payloads in JSONL logs.")
    parser.add_argument("--strict-links", action="store_true", help="Fail when an internal OKF markdown link cannot be resolved.")
    args = parser.parse_args()

    result = lint_data_root(Path(args.root), include_logs=args.include_logs, strict_links=args.strict_links)
    print(
        "OKF lint checked "
        f"{result.checked_markdown_count} markdown docs"
        + (f" and {result.checked_log_item_count} log materialized items" if args.include_logs else "")
        + f"; found {result.markdown_link_count} markdown graph links."
    )
    if result.ok:
        print("OKF lint passed")
        return 0
    print("OKF lint failed")
    for error in result.errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
