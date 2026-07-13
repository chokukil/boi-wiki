---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/validation-report
title: Task·Ontology·동적 결과 Acceptance 2026-07-13
description: 실제 handler, 브라우저와 로컬 Gemma로 Task·Ontology·동적 결과 계약을 재검증한 결과
tags: [Validation, Task, Ontology, A2UI, Harness, Browser, Gemma]
timestamp: 2026-07-13T21:31:00+09:00
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
  reviewed_at: 2026-07-13T21:31:00+09:00
  review_status: reviewed
---

# 실행 기준

> 이 문서는 통합 acceptance의 실제 최종 실행 기록이다. core와 선택 Adapter gate를 구분해 실행했으며 둘 다 통과했다. 형식 검사나 숨겨진 fixture는 브라우저 성공으로 계산하지 않았다.

- 검증 기준: `32edc02` graph artifact·OpenKB 경계, `6d1e4d4` Pet graph lifecycle, `7f8e95b` 실제 browser journey, `41385e3` graph view·guarded confirmation, `52aedf7` 의미별 browser acceptance
- fixture version: `1.0`
- generation model: `google/gemma-4-26b-a4b-qat`
- embedding model: `text-embedding-bge-m3`
- 외부 판정 모델: 사용하지 않음
- LM Studio model load/unload: 0건

# 결과

| 영역 | 결과 |
|---|---:|
| 실제 scenario handler | 50/50 |
| clean 전체 pytest | 815 passed · 23분 26초 · 격리 TMP runtime |
| Gemma 단일·멀티턴 의미 평가 | 17/17 · 모든 지표 100% · GPT-5.5 미사용 |
| Browser journey | 17/17 · 실제 조작 · console 오류 0 |
| Browser 1440×1000 | 통과 |
| Browser 1180×850 | 통과 |
| Browser 949×1151 | 통과 |
| Browser 390×844 | 통과 |
| Sigma canvas·하단 inspector | workbench 폭 100% · nonblank · inspector가 폭을 줄이지 않음 |
| Compact graph lifecycle | canvas 미생성 · 한 줄 결과 버튼 · Expanded 복원 통과 |
| invalid surface fallback | 통과 |
| Harness shadow·held-out·사람 검토 | 통과 · 실제 release·rollback 감사 이력 확인 |
| Context Playbook model·team scope | 통과 |
| 반복 실패·NegativeResult·운영 Ontology | 통과 |
| Task Snapshot cold p95 / warm p50 | 260.32ms / 14.70ms |
| Ontology 1-hop p95 | 17.20ms |
| Ontology 4-hop path p95 | 11.37ms |
| A2UI compile p95 | 0.56ms |
| 생성 graph artifact final p95 | 464.27ms |
| Graphify 0.9.13 | 실제 CLI 90 node·177 edge, import·rollback 통과 |
| OpenKB 0.4.4 | 실제 PDF → private 후보 4개 · index/log 제외 · canonical 변경 0 |
| Mermaid 직접 링크 cold browser | cold URL·desktop reload·mobile reload 통과 · SVG nonblank·console 오류 0 |
| 검색 품질 | Recall@8 1.00 · authoritative Top-3 1.00 |
| Web·REST·MCP parity | 10/10 |
| LM Studio load/unload | 0건 |

브라우저에서는 Task의 `확인한 내용·수행한 조치·판단·결과·근거·막힌 점·다음 업무`, 복수 담당자 picker, revision 409, Ontology 1-hop 지연 확장, node 선택과 canonical 이동, split·집중 보기, Compact 중지·복원, 9개 관계 보기, 동적 표·Timeline·Mermaid·form·Confirmation과 fallback을 실제 DOM과 canvas로 확인했다. 자동 확인은 관계 그림으로 우회하지 않고 기존 preview·confirmation 계약을 통해서만 생성된다.

실제 Graphify export가 mock과 달리 `links`, `confidence: EXTRACTED`, `confidence_score`를 사용한다는 결함을 release gate에서 발견했다. importer를 실제 `0.9.13` 계약에 맞춘 뒤 90개 node와 177개 edge를 수입하고 같은 manifest로 모두 rollback했다. 정본 변경은 없었다.

OpenKB는 `0.4.4`를 격리 tool로 실행했다. compatibility gateway가 `response_format: json_object` 요청을 이미 로드된 Gemma의 일반 JSON 요청으로 바꾸고 반환 schema를 검증한다. 실제 PDF에서 private 후보 4개가 생성됐고 `index.md`, `log.md` 후보는 0건이었다. gateway 요청 5회 중 변환은 4회, 복구 재시도는 0회였고 canonical 파일은 바뀌지 않았다.

생성 graph artifact는 GraphQuery 결과를 deterministic compiler로 바로 저장하고 A2UI를 위해 별도 모델 호출을 하지 않도록 바꿨다. 최종 p95는 464.27ms다. 한편 일반 장문 Gemma 답변은 시나리오별 20~45초가 걸렸으므로 별도 운영 성능 개선 항목으로 남긴다.

# 발견한 결함과 수정

실모델 멀티턴 `업무 이벤트와 SOP 관계 설명 → 방금 설명한 관계만 Mermaid`가 처음에는 `needs_input`으로 끝났다. 직전 답변의 실제 citation보다 넓은 검색 후보를 Graph entity로 다시 해석하면서 대상이 모호해졌기 때문이다.

후속 표현 변환은 직전 assistant 답변의 citation source를 우선 경계로 사용하고, broad retrieval candidate를 대상 확정 근거로 쓰지 않도록 수정했다. 재검증 결과 `mermaid_diagram` artifact, citation 실재성, 의도 보존과 무단 전환 방지 항목이 모두 통과했다.

Harness 개선 검증에서는 실제 Postgres collection registry에 `harness_failure_patterns`, `harness_shadow_runs`, `harness_versions`가 빠져 연결 상태와 조회 API가 500을 반환하는 결함을 발견했다. 메모리 fixture만으로는 드러나지 않았던 차이이며, 명시 registry와 회귀 테스트를 추가한 뒤 실제 Postgres에서 200 응답을 확인했다.

Context Playbook은 관리자 진단 권한과 실제 Context 주입 권한을 분리했다. 다른 사용자의 private 항목과 검토 전 team provisional 항목은 질문 맥락에 들어가지 않는다. 후보는 서버 shadow fingerprint와 fixture revision이 일치해야 평가할 수 있고, held-in·held-out·adversarial·long-term 기준을 모두 통과해도 `approved_not_deployed`로 남는다.

자동 확인 starter는 처음에 `presentation_hint`를 우선한 graph 분기에 가로채져 plan과 Confirmation 대신 Ontology artifact를 만들었다. graph 실행을 지식 탐색 operation으로 제한하고 `work_routine.plan`은 전용 handler가 처리하도록 수정했다. 재검증에서는 Confirmation component가 실제로 보였고, 확인 전 production routine 변경은 0건이었다.

Timeline API는 16개 행을 반환했지만 응답에 함께 있던 빈 `tour_steps` 배열이 실제 `timeline` 배열보다 먼저 선택돼 화면이 비어 보였다. renderer가 이름이 아니라 첫 번째 non-empty 의미 payload를 선택하도록 수정하고, neighbors·path·workflow·impact·lineage·responsibility·timeline·compare·tour를 화면 버튼으로 각각 전환해 결과 차이를 확인했다.

# Raw artifact

검증 raw artifact는 정본 지식이 아니라 runtime evidence다.

- `.tmp/task-ontology-acceptance-report-final6.json`
- `.tmp/task-ontology-browser-report-final6d.json`
- `.tmp/task-ontology-browser-shots-final6d/`
- `.tmp/agent-v2-semantic-report-final5-core.json`
- `.tmp/agent-v2-semantic-report-final5-deep.json`
- `.tmp/full-pytest-final6.log`
- `.tmp/search-quality-final5.json`
- `.tmp/interface-parity-final5.json`
- `.tmp/openkb-release-report-final6.json`
- `.tmp/current-manual-capture-manifest.json`
- `.tmp/graphify-job.json`
- `.tmp/graphify-rollback.json`
- `.tmp/openkb-job-final.json`
- `.tmp/task-ontology-a2ui-harness-acceptance-final.json`
- `.tmp/task-ontology-a2ui-harness-runtime-final.json`
- `.tmp/task-ontology-a2ui-harness-browser-final.json`
- `.tmp/acceptance-browser/task-ontology-a2ui.json`
- `.tmp/acceptance-browser/agent-v2-multiturn-mermaid.json`
- `.tmp/acceptance-browser/agent-v2-work-scenarios-final.json`
- `.tmp/acceptance-browser/ontology-1440x1000.png`
- `.tmp/acceptance-browser/ontology-1180x850.png`
- `.tmp/acceptance-browser/ontology-390x844.png`

# 다음 실행 원칙

새 relation, component, Task mode, Adapter와 Harness editable surface 계약은 기존 50개에 이름만 추가해서는 안 된다. 실제 handler와 browser journey를 함께 추가한다. 계약이 바뀌면 이 문서를 다시 `draft`로 내리고 전체 gate를 재실행한다.
