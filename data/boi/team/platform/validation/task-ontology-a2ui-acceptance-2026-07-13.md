---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/validation-report
title: Task·Ontology·동적 결과 Acceptance 2026-07-13
description: 실제 handler, 브라우저와 로컬 Gemma로 Task·Ontology·동적 결과 계약을 재검증한 결과
tags: [Validation, Task, Ontology, A2UI, Harness, Browser, Gemma]
timestamp: 2026-07-13T12:00:00+09:00
boi_id: boi:team:platform:validation:task-ontology-a2ui-2026-07-13
visibility: team
team_id: platform
classification: internal
owner: platform-team
author:
  type: agent
  agent_id: codex
acl_policy: acl:team:platform
status: draft
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance
  - type: boi
    ref: boi:public:boi-wiki-manual:workflows:task-execution-ontology-guide
  - type: boi
    ref: boi:public:boi-wiki-manual:knowledge:ontology-explorer-and-source-adapters
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:harness-observability-and-improvement
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
  reviewed_at: 2026-07-13T12:00:00+09:00
  review_status: needs_revision
---

# 실행 기준

> 이 문서는 통합 acceptance 진행 중인 중간 기록이다. 아래 수치는 당시 범위의 부분 검증 결과이며, 전체 clean regression, 12개 browser journey, 실제 Adapter 실행과 최신 화면 근거를 모두 통과하기 전에는 최종 acceptance로 사용하지 않는다.

- 검증 기준: `665918a` acceptance, `8bc2c00` backend, `c3526af` Web renderer와 Explorer, `8ffe42a` Harness 개선 경계
- fixture version: `1.0`
- generation model: `google/gemma-4-26b-a4b-qat`
- embedding model: `text-embedding-bge-m3`
- 외부 판정 모델: 사용하지 않음
- LM Studio model load/unload: 0건

# 결과

| 영역 | 결과 |
|---|---:|
| 실제 scenario handler | 38/38 |
| Task·Ontology·A2UI·Harness 집중 회귀 | 170 passed |
| API route 장기 회귀 | 448 passed 후 Mermaid source 기대값 1건 발견·수정, 관련 5건 재검증 통과 |
| Gemma 단일·멀티턴 의미 평가 | 100% · 실패 0건 |
| Browser 1440×1000 | 통과 |
| Browser 1180×850 | 통과 |
| Browser 390×844 | 통과 |
| Sigma canvas nonblank | 통과 |
| invalid surface fallback | 통과 |
| Harness shadow·held-out·사람 검토 | 통과 · production 변경 0건 |
| Context Playbook model·team scope | 통과 |
| 반복 실패·NegativeResult·운영 Ontology | 통과 |
| Task Snapshot 5회 p95 | 439.92ms |
| Ontology 1-hop 5회 p95 | 27.36ms |

브라우저에서는 Task의 `확인한 내용·수행한 조치·판단·결과·근거·막힌 점·다음 업무`, 복수 담당자 picker, Ontology 1-hop 지연 확장, raw ref 비노출, 동적 component와 fallback을 실제 DOM과 canvas로 확인했다.

# 발견한 결함과 수정

실모델 멀티턴 `업무 이벤트와 SOP 관계 설명 → 방금 설명한 관계만 Mermaid`가 처음에는 `needs_input`으로 끝났다. 직전 답변의 실제 citation보다 넓은 검색 후보를 Graph entity로 다시 해석하면서 대상이 모호해졌기 때문이다.

후속 표현 변환은 직전 assistant 답변의 citation source를 우선 경계로 사용하고, broad retrieval candidate를 대상 확정 근거로 쓰지 않도록 수정했다. 재검증 결과 `mermaid_diagram` artifact, citation 실재성, 의도 보존과 무단 전환 방지 항목이 모두 통과했다.

Harness 개선 검증에서는 실제 Postgres collection registry에 `harness_failure_patterns`, `harness_shadow_runs`, `harness_versions`가 빠져 연결 상태와 조회 API가 500을 반환하는 결함을 발견했다. 메모리 fixture만으로는 드러나지 않았던 차이이며, 명시 registry와 회귀 테스트를 추가한 뒤 실제 Postgres에서 200 응답을 확인했다.

Context Playbook은 관리자 진단 권한과 실제 Context 주입 권한을 분리했다. 다른 사용자의 private 항목과 검토 전 team provisional 항목은 질문 맥락에 들어가지 않는다. 후보는 서버 shadow fingerprint와 fixture revision이 일치해야 평가할 수 있고, held-in·held-out·adversarial·long-term 기준을 모두 통과해도 `approved_not_deployed`로 남는다.

# Raw artifact

검증 raw artifact는 정본 지식이 아니라 runtime evidence다.

- `.tmp/task-ontology-a2ui-acceptance-final.json`
- `.tmp/task-ontology-a2ui-harness-acceptance-final.json`
- `.tmp/task-ontology-a2ui-harness-runtime-final.json`
- `.tmp/task-ontology-a2ui-harness-browser-final.json`
- `.tmp/acceptance-browser/task-ontology-a2ui.json`
- `.tmp/acceptance-browser/agent-v2-multiturn-mermaid.json`
- `.tmp/acceptance-browser/agent-v2-work-scenarios-final.json`
- `.tmp/acceptance-browser/ontology-1440x1000.png`
- `.tmp/acceptance-browser/ontology-1180x850.png`
- `.tmp/acceptance-browser/ontology-390x844.png`

# 남은 운영 원칙

새 relation, component, Task mode, Adapter와 Harness editable surface 계약은 기존 38개에 이름만 추가해서는 안 된다. 실제 handler와 browser journey를 함께 추가한다. 실패 결과를 합격 수치에 포함하지 않으며, immutable Harness 경계를 낮추는 후보는 shadow 전에 차단한다.
