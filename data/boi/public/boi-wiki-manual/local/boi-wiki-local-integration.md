---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki Local 연계 가이드
description: Local Private 업무 BoI를 shared BoI Wiki의 WorkflowDefinition, MCP, Local Second Brain, promotion 흐름과 연결하는 기준
tags: [BoIWiki, LocalPrivate, WorkBoI, WorkflowDefinition, MCP, LocalSecondBrain]
timestamp: 2026-07-05T22:00:00+09:00
boi_id: boi:public:boi-wiki-manual:local:boi-wiki-local-integration
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: local-template
    ref: boi-wiki-local/README.md
  - type: local-template
    ref: boi-wiki-local/AGENTS.md
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

BoI Wiki Local은 개인 PC에서 시작하는 Local Private 업무 BoI 작업공간이다. SOP 초안뿐 아니라 회의록, 임시 분석, 보고 초안, 반복 업무 패턴을 먼저 안전하게 정리하고, 사용자가 명시 승인한 경우에만 shared BoI Wiki로 promotion draft를 보낸다.

운영 목표는 사람이 문서를 매번 읽지 않아도 agent가 capture inbox, classify, OKF 문서화, memory 후보, cleanup preview, promotion preflight를 자연스럽게 반복하는 것이다. 서버, DB, Docker 없이 동작해야 하며 원격 BoI Wiki와 붙는 부분은 MCP/API endpoint 설정만 바뀐다.

# Local to Shared Boundary

```mermaid
flowchart LR
  L["Local Private 업무 BoI"] --> C["Context Pack / Evidence 정리"]
  C --> M{"MCP 연결됨?"}
  M -->|"예"| R["shared SOP / WorkflowDefinition / Event / Action 조회"]
  M -->|"아니오"| F["local 파일과 사용자 제공 자료만 사용"]
  R --> D["WorkflowDefinition draft 또는 promotion draft"]
  F --> D
  D --> P{"사용자 명시 승인"}
  P -->|"승인"| S["shared sync validation / publish"]
  P -->|"미승인"| K["local-only 유지"]
```

# Local에서 다루는 업무

| 업무 | 저장 위치 | shared 연계 |
|---|---|---|
| 회의록/개인 메모 | `notes/` | 필요 시 요약 또는 promotion draft |
| SOP 초안 | `sop-drafts/` | SOP 후보 또는 WorkflowDefinition 연결 |
| API/Action 초안 | `action-drafts/` | Action 등록과 WorkflowDefinition draft |
| Event 후보 | `event-drafts/` | Event Contract draft |
| 업무 context pack | `context-packs/` | Agent/MCP가 읽는 업무 맥락 |
| 반복 업무 패턴 | `reports/`, `notes/`, future `work-patterns/` | WorkflowDefinition 또는 Skill 후보 |

# Local Lifecycle

`boi-wiki-local`은 shared Web runtime에 private 원문을 자동 전송하지 않는다. 하지만 lifecycle metadata는 Web과 맞춘다.

| Metadata | Use |
|---|---|
| `artifact_visibility` | `memory`, `working`, `background`, `archived`, `delete_candidate`, `protected` |
| `lifecycle_state` | 현재 보관 상태 |
| `memory_candidate` | Agent가 장기 기억 후보로 제안했는지 |
| `cleanup_policy` | keep, generated artifact cleanup, promotion protected 같은 정책 |

Local generated artifact는 `.boi-trash/{cleanup_id}/`로 quarantine하고 7일 후 hard delete한다. 삭제 전에는 preview를 보여줘야 하며, promotion draft, 사용자가 직접 작성한 memory/working 문서, protected 문서는 cleanup 대상이 아니다. Web으로 promotion하기 전에는 local cleanup이 promotion 대상 원문을 보호해야 한다.

# Local Second Brain Helpers

`boi-wiki-local`은 경량 스크립트로 agent 반복 작업을 돕는다. 일반 사용자는 직접 실행하지 않아도 되고, agent가 사전 점검이나 preview를 만들 때 사용한다.

| Script | 목적 |
|---|---|
| `scripts/local_capture.py` | 자유 메모를 `notes/capture-inbox/` 아래 Local Private capture 후보로 저장 |
| `scripts/local_review.py` | stale 문서, duplicate 제목, memory 후보, promotion 후보, cleanup 후보를 비파괴로 산출 |
| `scripts/promotion_preflight.py` | Team/Public 공유 전 target visibility, source_refs, sensitive pattern, preview draft를 확인 |

```bash
python3 scripts/local_capture.py --check
python3 scripts/local_review.py --check
python3 scripts/promotion_preflight.py --check
```

local helper는 표준 Python만 사용한다. raw local private 원문은 사용자 승인 없이 원격 API/MCP로 보내지 않는다.

# Source Wiki And OpenWiki

repo 문서화는 두 단계로 나눈다.

| 단계 | 용도 |
|---|---|
| BoI Source Wiki API/MCP | 사내 OKF source wiki 생성, source inventory, selected/skipped file, commit SHA, citations, validation report, last-good manifest 관리 |
| hosted OpenWiki | 외부 public repo 검증 또는 사내 mirror repo 문서 사이트 검증 |

`chokukil/boi-wiki-local`은 고도화 커밋이 merge된 뒤 OpenWiki hosted wiki로 먼저 검증한다. 사내 저장소로 옮길 때는 GitHub Enterprise, GitLab, Gitea host를 source wiki allowlist와 MCP/API env에 추가하고 같은 workflow를 유지한다.

# MCP 사용 기준

MCP가 있으면 agent는 shared BoI Wiki에서 다음을 조회한다.

| Tool | 목적 |
|---|---|
| `ontology_search` | SOP, Event, Action, Dictionary, runtime evidence를 함께 검색 |
| `workflow_definitions_search` | 내부 WorkflowDefinition 기준 기존 연결 중복 확인 |
| `workflow_definition_get` | 내부 WorkflowDefinition 상세 확인 |
| `workflow_definition_deduplicate` | 신규 등록 전 재사용/확장/신규 판단 |
| `boi_agent_chat` | shared BoI Agent에게 현재 업무 질문 |
| `boi_search` | 문서 목록만 필요한 경우 |
| `agent_memory_review` | Web Private Second Brain 후보와 cleanup 후보를 확인 |
| `promotion_preview` | Team/Public 공유 전 remote validation preview |
| `source_wiki_plan` | repo/source wiki 생성 전 inventory와 citation 계획 확인 |

# 사용 예시

| 사용자 요청 | Agent 처리 |
|---|---|
| 이번 회의 내용을 BoI로 정리해줘 | Local Private 업무 BoI로 저장 |
| 매주 FAB Trend 보고를 자동화하고 싶어 | 반복 업무 패턴을 정리하고 SOP 추가/Action 연결 초안 제안 |
| 이 API를 연결하고 싶어 | 기존 SOP/Event/Action 후보와 내부 WorkflowDefinition 중복 확인 후 Action draft 생성 |
| Public으로 공유해줘 | local promotion draft와 preview를 만든 뒤 승인 요청 |

# Guardrail

Local Private 원문은 사용자 명시 승인 없이 원격으로 보내지 않는다. shared로 보내는 것은 검증된 promotion candidate, context pack 요약, 또는 draft proposal이다. 7자리 사번 기반 private path와 `local_owner_ref`는 항상 일치해야 한다.

Generated report나 sandbox artifact를 shared로 보낼 때도 raw 원문 전체를 기본 전송하지 않는다. 필요한 경우 summary/profile/artifact reference를 만들고, 사용자가 선택한 promotion candidate만 Web API/MCP로 보낸다.

# Related Documents

- [업무 BoI-first 개념 모델](/public/boi-wiki-manual/concepts/work-boi-first-model.md)
- [Local Private 시작하기](/public/boi-wiki-manual/local-private/overview.md)
- [Register and Use BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [BoI Wiki 종합 가이드](/public/boi-wiki-manual/guide/final-operator-guide.md)
