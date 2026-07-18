#!/usr/bin/env python3
"""§10 P1-12: 하네스 규칙별 ablation(제거) 재검증 러너.

harness/README.md의 "Load-bearing 재검증" 절차 ②를 실행 가능하게 만든다 — 지금까지는
절차만 문서에 있고 그것을 실행하는 도구가 없어 재검증이 실제로 일어나지 않았다.

harness/ablation-flags.yaml에 등록된 플래그를 하나씩 `HARNESS_ABLATE` 환경변수로 설정해
`python3 -m pytest tests/harness_evals -q`를 반복 실행한다. 어떤 플래그를 ablate해도(=그
플래그가 가리는 채점 assertion을 꺼도) eval suite가 여전히 통과한다면, 그 규칙을 제거해도
지금 golden task 중 어느 것도 실패로 잡아내지 못한다는 뜻이다 — "load-bearing 후보 아님,
검토 필요"로 보고한다. 이 스크립트는 advisory tool이라 결과와 무관하게 항상 exit 0이다
(실제로 규칙을 제거할지는 사람이 판단한다).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
ABLATION_FLAGS_PATH = REPO_ROOT / "harness" / "ablation-flags.yaml"


def load_flags() -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(ABLATION_FLAGS_PATH.read_text(encoding="utf-8"))
    entries = raw.get("flags") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        return {}
    return {
        str(item["name"]): item
        for item in entries
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }


def run_eval_suite_with_ablation(flag: str) -> tuple[int, str]:
    env = dict(os.environ)
    env["HARNESS_ABLATE"] = flag
    # ablation 실행은 acceptance의 harness_eval_status 기록을 더럽히면 안 된다.
    env.pop("BOI_HARNESS_EVAL_RECORD", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/harness_evals", "-q"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode, output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ablate harness grading checks one at a time and report which are still load-bearing (§10 P1-12)."
    )
    parser.add_argument(
        "--flags",
        default="",
        help="Comma-separated subset of flags to run (default: all flags in harness/ablation-flags.yaml).",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Print pytest output for each flag.")
    args = parser.parse_args()

    if not ABLATION_FLAGS_PATH.exists():
        print(f"ablation flags registry is missing: {ABLATION_FLAGS_PATH}", file=sys.stderr)
        return 0

    flags = load_flags()
    if not flags:
        print("no ablation flags registered in harness/ablation-flags.yaml", file=sys.stderr)
        return 0

    if args.flags.strip():
        selected = [name.strip() for name in args.flags.split(",") if name.strip()]
    else:
        selected = sorted(flags)
    unknown = [name for name in selected if name not in flags]
    if unknown:
        print(f"unknown flag(s): {', '.join(unknown)} (known: {', '.join(sorted(flags))})", file=sys.stderr)
        return 0

    print("BoI Harness ablation report (advisory — exit code is always 0)")
    print(f"flags: {', '.join(selected)}")
    print()

    review_candidates: list[str] = []
    for name in selected:
        entry = flags[name]
        description = str(entry.get("description") or "").strip()
        disables = str(entry.get("disables") or "").strip()
        returncode, output = run_eval_suite_with_ablation(name)
        status = "PASS" if returncode == 0 else "FAIL"
        print(f"- {name}: {status}  (disables: {disables})")
        if description:
            print(f"    {description}")
        if args.verbose:
            for line in output.strip().splitlines():
                print(f"    | {line}")
        if returncode == 0:
            review_candidates.append(name)
            print("    -> load-bearing 후보 아님 — 검토 필요")
        print()

    if review_candidates:
        print("검토 필요(ablation 후에도 eval 전부 통과): " + ", ".join(review_candidates))
    else:
        print("이번 실행 대상 플래그는 전부 ablation 시 eval 실패로 이어짐 — 현재 규칙이 load-bearing 근거를 유지.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
