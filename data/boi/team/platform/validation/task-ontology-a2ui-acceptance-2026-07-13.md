---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/validation-report
title: Task·Ontology·동적 결과 Acceptance 2026-07-13
description: 실제 handler, 브라우저와 로컬 Gemma로 Task·Ontology·동적 결과 계약을 재검증한 결과
tags: [Validation, Task, Ontology, A2UI, Browser, Gemma]
timestamp: 2026-07-13T03:10:00+09:00
boi_id: boi:team:platform:validation:task-ontology-a2ui-2026-07-13
visibility: team
team_id: platform
classification: internal
owner: platform-team
author:
  type: agent
  agent_id: codex
acl_policy: acl:team:platform
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance
  - type: boi
    ref: boi:public:boi-wiki-manual:workflows:task-execution-ontology-guide
  - type: boi
    ref: boi:public:boi-wiki-manual:knowledge:ontology-explorer-and-source-adapters
implementation_refs:
  - type: repo
    ref: tests/fixtures/task_ontology_a2ui_acceptance.yaml
  - type: repo
    ref: scripts/check_task_ontology_a2ui_acceptance.py
  - type: repo
    ref: scripts/check_task_ontology_a2ui_browser.mjs
  - type: repo
    ref: scripts/evaluate_agent_v2_work_scenarios.py
review:
  reviewer: platform-lead
  reviewed_at: 2026-07-13T03:10:00+09:00
  review_status: reviewed
---

# 실행 기준

- 검증 기준: `665918a` acceptance, `8bc2c00` backend, `c3526af` Web renderer와 Explorer
- fixture version: `1.0`
- generation model: `google/gemma-4-26b-a4b-qat`
- embedding model: `text-embedding-bge-m3`
- 외부 판정 모델: 사용하지 않음
- LM Studio model load/unload: 0건

# 결과

| 영역 | 결과 |
|---|---:|
| 실제 scenario handler | 32/32 |
| 관련 pytest 회귀 | 57 passed |
| Gemma 단일·멀티턴 의미 평가 | 100% · 실패 0건 |
| Browser 1440×1000 | 통과 |
| Browser 1180×850 | 통과 |
| Browser 390×844 | 통과 |
| Sigma canvas nonblank | 통과 |
| invalid surface fallback | 통과 |
| Task Snapshot 5회 p95 | 326.62ms |
| Ontology 1-hop 5회 p95 | 27.92ms |

브라우저에서는 Task의 `확인한 내용·수행한 조치·판단·결과·근거·막힌 점·다음 업무`, 복수 담당자 picker, Ontology 1-hop 지연 확장, raw ref 비노출, 동적 component와 fallback을 실제 DOM과 canvas로 확인했다.

# 발견한 결함과 수정

실모델 멀티턴 `업무 이벤트와 SOP 관계 설명 → 방금 설명한 관계만 Mermaid`가 처음에는 `needs_input`으로 끝났다. 직전 답변의 실제 citation보다 넓은 검색 후보를 Graph entity로 다시 해석하면서 대상이 모호해졌기 때문이다.

후속 표현 변환은 직전 assistant 답변의 citation source를 우선 경계로 사용하고, broad retrieval candidate를 대상 확정 근거로 쓰지 않도록 수정했다. 재검증 결과 `mermaid_diagram` artifact, citation 실재성, 의도 보존과 무단 전환 방지 항목이 모두 통과했다.

# Raw artifact

검증 raw artifact는 정본 지식이 아니라 runtime evidence다.

- `.tmp/task-ontology-a2ui-acceptance-final.json`
- `.tmp/acceptance-browser/task-ontology-a2ui.json`
- `.tmp/acceptance-browser/agent-v2-multiturn-mermaid.json`
- `.tmp/acceptance-browser/agent-v2-work-scenarios-final.json`
- `.tmp/acceptance-browser/ontology-1440x1000.png`
- `.tmp/acceptance-browser/ontology-1180x850.png`
- `.tmp/acceptance-browser/ontology-390x844.png`

# 남은 운영 원칙

새 relation, component, Task mode와 Adapter 계약은 기존 32개에 이름만 추가해서는 안 된다. 실제 handler와 browser journey를 함께 추가한다. 실패 결과를 합격 수치에 포함하지 않으며, immutable Harness 경계를 낮추는 후보는 사람 검토 전에 차단한다.
