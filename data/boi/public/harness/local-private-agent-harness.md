---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Local Private Agent Harness
description: Codex, Claude, Cursor가 Local Private BoI workspace를 같은 방식으로 만들고 검증하는 기준
tags: [Harness, LocalPrivate, Codex, Claude, Cursor]
timestamp: 2026-06-19T18:00:00+09:00
boi_id: boi:public:harness:local-private-agent-harness
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:local-private:overview
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Local Private Agent Harness는 일반 사용자가 lint, MCP, Git을 몰라도 agent가 Local Private BoI를 OKF 구조로 저장하도록 하는 기준이다.

# Agent Rules

1. 전체 파일을 먼저 뒤지지 말고 `index.md`에서 시작해 필요한 폴더의 `index.md`와 concept 문서로 좁힌다.
2. 개인 기록은 local workspace의 `data/boi/private/{7자리사번}/...` 아래에 저장한다. `0000000`은 scaffold 전용이며, 실제 작업 전 agent가 7자리 사번을 확인해야 한다.
3. Local Private 문서에는 `visibility: local-private`, `local_only: true`, `promotion_status`, lifecycle metadata를 넣는다.
4. 저장 전 Level 0 self-check를 반드시 수행하고, promotion 전에는 local preflight와 preview를 같이 만든다.
5. `index.md`와 `log.md`를 업데이트한다.
6. 사용자 명시 승인 없이 Local Private 원문이나 Team/Public promotion candidate를 원격 MCP/API/GitHub/외부 서비스에 전송하지 않는다.
7. 사용자가 승인한 promotion candidate는 MCP `promotion_submit` 또는 Web promotion API로 원격 동기 검증/게시를 요청한다.

# Skills-first Use Cases

`boi-wiki-local`은 local MCP를 공식 경로로 요구하지 않는다. Agent는 skills와 이 하네스를 기준으로 다음 작업을 local-only로 완료할 수 있어야 한다.

- SOP를 Mermaid/SVG 도식으로 변환. Mermaid 기본 산출물은 `Overview + Swimlane`이고, 복잡한 구간은 stage detail diagram으로 분리한다.
- Event 발생 시 SOP stage, action, manual handoff 계획
- API/Webhook/MCP/Langflow/Manual action spec 초안 작성
- 업무 단위 agent context pack 작성
- Event payload 기반 workflow 사전 확인 시뮬레이션
- BoI 연계 Langflow workflow 설계 초안

원격 `boi-wiki-mcp`가 연결되어 있으면 shared SOP, Event Type, Action Spec, Workflow Status 조회에 사용한다. `source_apply`, `doc_body_apply`, `promotion_submit`, `action_invoke` 같은 원격 쓰기/실행 tool은 사용자 명시 승인 후에만 사용한다.

# Validation Levels

| Level | Actor | Description |
|---|---|---|
| 0 | Agent | frontmatter, path, lifecycle, index/log, citation, publish confirmation self-check |
| 1 | OS shell | `check.ps1` 또는 `check.sh` no-dependency 구조 점검 |
| 2 | Developer agent | Python이 있을 때 local strict OKF lint |
| 3 | Shared repo API | 원격 동기 promotion validation, publish status, HOTL watching |

# Citations

- [Local Private Overview](/public/boi-wiki-manual/local-private/overview.md)
- [Promotion Flow](/public/boi-wiki-manual/local-private/promotion-flow.md)
- [BoI Wiki Use Cases](/public/boi-wiki-manual/use-cases/sop-flow-visualization.md)
