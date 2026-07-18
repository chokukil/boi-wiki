---
okf_version: "0.1"
boi_profile_version: "0.1"
harness_version: "0.4.0"
type: boi/reference
title: BoI Agent Harness Overview
description: SOP, Action, Web validated edit 작업을 모든 agent가 같은 방식으로 수행하기 위한 public harness 진입점
tags: [Harness, Agent, SOP, Action, Edit]
timestamp: 2026-07-17T00:00:00+09:00
boi_id: boi:public:harness:overview
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: harness/README.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Agent Harness는 Codex, Claude, Langflow, Custom Agent가 BoI Wiki, Event Broker, Action Gateway를 같은 방식으로 다루도록 하는 운영 기준이다.

# Harness Documents

- [Web Validated Editing Guide](/public/harness/web-draft-editing-guide.md)
- [SOP Authoring Harness](/public/harness/sop-authoring-harness.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
- [Dictionary Authoring Harness](/public/harness/dictionary-authoring-harness.md)
- [Local Private Agent Harness](/public/harness/local-private-agent-harness.md)
- [HTML Share Harness](/public/harness/html-share-harness.md)
- [Agent Harness SOP](/public/public-sop-agent-harness.md)
- [BoI Wiki Manual Overview](/public/boi-wiki-manual/overview.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)

# Operating Rule

Source/body 직접 수정은 preview, validation, apply, auto-commit 경로를 사용한다. Team/Public promotion은 사용자의 preview 승인과 원격 자동 검증을 통과하면 즉시 게시되며, 품질/정책 판단은 HOTL로 사후 개입한다.

Codex skill은 얇은 bootstrap으로 유지하고, 상세 절차는 BoI Wiki MCP resource와 public harness 문서를 우선 읽는다.

# 하네스 버전과 CHANGELOG

하네스 버전의 SSOT는 repo의 `harness/manifest.yaml`이다. 이 문서를 포함한 모든 서빙 사본 frontmatter의 `harness_version`은 manifest와 일치해야 한다. 하네스 문서를 개정할 때는 version bump와 함께 `harness/CHANGELOG.md`에 근거(evidence)를 기록한다 — 모든 규칙 추가/강화는 실제 실패 사례로 소급 가능해야 하며(ratchet 원칙), 근거 없는 규칙 추가는 리뷰에서 거부된다.

# Load-bearing 재검증

모델 세대 교체 시 하네스는 다음 절차로 얇게 유지한다. 하네스는 얇을수록 좋다.

1. `tests/harness_evals/` 골든 태스크 회귀를 실행한다. `scripts/run_harness_evals.sh`가 `BOI_HARNESS_EVAL_RECORD=1`을 설정해 repo root에서 실행해주는 wrapper이며(§10 P1-11), exit code를 그대로 전달한다. `scripts/check_local_full_readiness.py --harness-evals`로 실행 중인 배포의 readiness 점검에 같은 결과를 포함시킬 수 있다.
2. 하네스 규칙별로 제거해도 eval이 통과하는지 ablation으로 확인한다. `scripts/run_harness_ablation.py`가 `harness/ablation-flags.yaml`에 등록된 플래그를 하나씩 `HARNESS_ABLATE` 환경변수로 켜서 eval suite를 반복 실행하고, ablation 후에도 계속 통과하는 규칙을 "load-bearing 후보 아님 — 검토 필요"로 보고한다(§10 P1-12, advisory tool — exit code는 항상 0).
3. 더 이상 load-bearing이 아닌 규칙은 제거하고 제거 근거(eval 결과)를 CHANGELOG에 기록한다.

# LLM 골든 태스크 eval (옵트인, §10 P2-20)

`tests/harness_evals/`는 LLM을 호출하지 않는 결정적 suite이고 `harness_eval_status` 회귀 게이트다. `tests/harness_evals_llm/`은 별도 디렉터리로, 실제 composer LLM에게 저작 태스크(공유 HTML 본문에서 제목/설명/태그 초안 작성)를 수행시키고 결과를 채점하는 옵트인 suite다. 기본 실행은 항상 SKIP되며, `BOI_HARNESS_LLM_EVALS=1`과 composer LLM 엔드포인트(`BOI_AGENT_COMPOSER_BASE_URL`/`BOI_AGENT_COMPOSER_MODEL`)가 함께 설정됐을 때만 실행된다. 채점은 `tests/harness_evals_llm/grading_llm.py`(단일 평가자)가 한국어 출력·길이 범위·태그 8개 이하·비밀 값 패턴 없음을 확인하며, 결정적 suite의 상태에는 절대 포함되지 않는다.

# Citations

- Repo source: `harness/README.md`
- Version SSOT: `harness/manifest.yaml`, `harness/CHANGELOG.md`
