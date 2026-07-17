---
okf_version: "0.1"
boi_profile_version: "0.1"
harness_version: "0.2.0"
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

모델 세대 교체 시 하네스는 다음 절차로 얇게 유지한다. ① `tests/harness_evals/` 골든 태스크 회귀를 실행한다. ② 하네스 규칙별로 제거해도 eval이 통과하는지 ablation으로 확인한다. ③ 더 이상 load-bearing이 아닌 규칙은 제거하고 제거 근거를 CHANGELOG에 기록한다. 하네스는 얇을수록 좋다.

# Citations

- Repo source: `harness/README.md`
- Version SSOT: `harness/manifest.yaml`, `harness/CHANGELOG.md`
