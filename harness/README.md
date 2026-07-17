# BoI Harness

This directory is the repo-side source for agent harness guidance.

Use these documents before creating or changing curated BoI Wiki knowledge:

- `harness-responsibility-matrix.md`: map Observation, Context, Control, Action, State, and Verification to BoI API/MCP/UI/runtime checks.
- `web-draft-editing-guide.md`: source/body edits use preview, validation, apply, and auto-commit; Team/Public promotion uses user-confirmed validated publish.
- `sop-authoring-harness.md`: create SOP packages with events, actions, citations, and OKF links.
- `action-authoring-harness.md`: create executable API/Webhook/MCP/Langflow/manual/event-broker/BoI-writer action packages.
- `data-lake-query-harness.md`: use optional Data Lake artifacts and structured demo sources through BoI API/MCP without making MinIO or PostgreSQL core dependencies.
- `data-lake-artifact-harness.md`: store file evidence as Data Lake artifacts and pass only URL/profile/sample metadata into BoI/LLM context.
- `html-share-harness.md`: publish self-contained HTML documents to shortlinks with an embedded BoI HTML Profile, an auto-generated knowledge card, and preview-confirm-publish write boundaries.

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
   `data/harness-evals/status.json`을 더럽히지 않는다.
2. 하네스 규칙별로 해당 규칙을 제거한 상태에서도 eval이 통과하는지 ablation으로 확인한다.
3. 더 이상 load-bearing이 아닌 규칙은 제거하고, 제거 근거(eval 결과)를 CHANGELOG에 기록한다.
