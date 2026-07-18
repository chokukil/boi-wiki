# BoI Harness

This directory is the repo-side source for agent harness guidance.

Use these documents before creating or changing curated BoI Wiki knowledge:

- `harness-responsibility-matrix.md`: map Observation, Context, Control, Action, State, and Verification to BoI API/MCP/UI/runtime checks.
- `web-draft-editing-guide.md`: source/body edits use preview, validation, apply, and auto-commit; Team/Public promotion uses user-confirmed validated publish.
- `sop-authoring-harness.md`: create SOP packages with events, actions, citations, and OKF links.
- `action-authoring-harness.md`: create executable API/Webhook/MCP/Langflow/manual/event-broker/BoI-writer action packages.
- `data-lake-query-harness.md`: use optional Data Lake artifacts and structured demo sources through BoI API/MCP without making MinIO or PostgreSQL core dependencies.
- `data-lake-artifact-harness.md`: store file evidence as Data Lake artifacts and pass only URL/profile/sample metadata into BoI/LLM context.
- `html-share-harness.md`: publish self-contained HTML documents to shortlinks with an embedded BoI HTML Profile, an auto-generated knowledge card, and preview-confirm-publish write boundaries; also covers metadata-only PATCH and ownership transfer (§10 P1-6/P1-7).

The BoI Wiki copies live under `data/boi/public/harness/` so Langflow, Codex, Claude, and other agents can lazy-load the same rules through the wiki or BoI Wiki MCP. Codex skills should stay thin and bootstrap agents into MCP/harness resources instead of duplicating the full rules.

## 하네스 버전과 CHANGELOG

- 버전의 SSOT는 `harness/manifest.yaml`이다. 하네스 문서 쌍(repo 원본 ↔ 서빙 사본)마다
  `{key, version, repo_path, served_path, served_boi_id, title}` 항목이 하나씩 있고,
  서빙 사본 frontmatter의 `harness_version`은 manifest의 version과 일치해야 한다.
  plain markdown인 repo 원본에는 frontmatter를 추가하지 않으며, 버전은 manifest가 대표한다.
- 하네스 문서를 개정하면 반드시 manifest의 version을 bump하고 `harness/CHANGELOG.md`에
  근거(evidence)를 기록한다 (ratchet 원칙: 모든 규칙 추가/강화는 실제 실패 사례로 소급 가능해야
  하며, 근거 없는 규칙 추가는 리뷰에서 거부한다).
- 일관성은 `boi_api/app/harness_meta.py`가 검증하고, `/api/harness/acceptance`의 `Meta` 버킷과
  `tests/harness_evals/`가 회귀를 막는다.

## Load-bearing 재검증

모델 세대 교체 시(예: 새 Claude/Codex 도입) 각 하네스 규칙이 여전히 load-bearing인지 재검증한다.
하네스는 얇을수록 좋다 — 과적재된 컨텍스트는 성공률을 낮추고 비용을 높인다.

1. `tests/harness_evals/`를 실행해 골든 태스크 회귀가 전부 통과하는지 확인한다
   (`python3 -m pytest tests/harness_evals -q`). eval 상태를 acceptance `Meta` 버킷에 기록하려면
   `BOI_HARNESS_EVAL_RECORD=1`로 실행한다 — 기본값은 기록하지 않아 CI/임시 환경 실행이
   `data/harness-evals/status.json`을 더럽히지 않는다. `scripts/run_harness_evals.sh`가 이 환경변수를
   설정해 repo root에서 실행해주는 wrapper다(§10 P1-11) — exit code를 그대로 전달하므로 CI 게이트로
   그대로 쓸 수 있다:

   ```bash
   bash scripts/run_harness_evals.sh
   ```

   `scripts/check_local_full_readiness.py --harness-evals`로 실행 중인 배포의 readiness 점검에
   같은 eval 실행 결과를 포함시킬 수 있다 — 실배포에서 acceptance의 harness_eval_status가
   `not_recorded`로만 남던 문제의 실제 기록 주체다.
2. 하네스 규칙별로 해당 규칙을 제거한 상태에서도 eval이 통과하는지 ablation으로 확인한다.
   `scripts/run_harness_ablation.py`가 `harness/ablation-flags.yaml`에 등록된 플래그를 하나씩
   `HARNESS_ABLATE` 환경변수로 설정해 eval suite를 반복 실행하고, ablation 후에도 계속 통과하는
   규칙(= 제거해도 어떤 golden task도 실패시키지 못하는 규칙)을 "load-bearing 후보 아님 — 검토
   필요"로 보고한다(§10 P1-12, advisory tool — exit code는 항상 0):

   ```bash
   python3 scripts/run_harness_ablation.py                                   # 등록된 모든 플래그
   python3 scripts/run_harness_ablation.py --flags frame-ancestors-check
   ```
3. 더 이상 load-bearing이 아닌 규칙은 제거하고, 제거 근거(eval 결과)를 CHANGELOG에 기록한다.

## LLM 골든 태스크 eval (옵트인, §10 P2-20)

`tests/harness_evals/`는 LLM을 호출하지 않는 결정적 suite다(`harness_eval_status` 회귀 게이트).
`tests/harness_evals_llm/`은 별도 디렉터리로, 실제 composer LLM에게 저작 태스크(예: 공유 HTML
본문에서 제목/설명/태그 초안 작성)를 수행시키고 결과를 채점하는 옵트인 suite다 — 네트워크/LLM
가용성에 의존하므로 결정적 suite의 상태에는 절대 포함하지 않는다.

- 기본 실행(`pytest` 전체 또는 `pytest tests/harness_evals_llm`)은 항상 SKIP된다.
- `BOI_HARNESS_LLM_EVALS=1`이고 composer LLM 엔드포인트(`BOI_AGENT_COMPOSER_BASE_URL`,
  `BOI_AGENT_COMPOSER_MODEL`, 선택적으로 `BOI_AGENT_COMPOSER_API_KEY`)가 설정되어 있을 때만 실행된다:

  ```bash
  BOI_HARNESS_LLM_EVALS=1 \
  BOI_AGENT_COMPOSER_BASE_URL=http://llm-gateway.example:1236/v1 \
  BOI_AGENT_COMPOSER_MODEL=google/gemma-4-26b-a4b-qat \
  python3 -m pytest tests/harness_evals_llm -q
  ```
- 채점은 `tests/harness_evals_llm/grading_llm.py`(단일 평가자)에 위임한다: 한국어 출력, title/description
  길이 범위, tags 8개 이하, 비밀 값 패턴 없음을 확인한다(생성자/평가자 분리 원칙은 결정적 suite와 동일).
