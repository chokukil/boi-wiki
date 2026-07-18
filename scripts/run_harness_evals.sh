#!/usr/bin/env bash
# §10 P1-11: 하네스 골든 태스크 eval suite를 "실제로 기록되게" 실행하는 wrapper.
#
# acceptance의 harness_eval_status가 실배포에서 항상 not_recorded였던 이유는
# tests/harness_evals/conftest.py의 record_harness_eval_status가 BOI_HARNESS_EVAL_RECORD=1일
# 때만 data/harness-evals/status.json을 쓰는데, 그 값을 세팅해 실행해주는 도구가 하나도 없었기
# 때문이다(문서에는 절차만 있었다). 이 스크립트가 그 실행 주체다.
#
# 반드시 repo root에서 실행한다 (harness_meta.REPO_ROOT는 소스 트리 기준 상대경로를 쓴다).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

export BOI_HARNESS_EVAL_RECORD=1
exec python3 -m pytest tests/harness_evals -q "$@"
