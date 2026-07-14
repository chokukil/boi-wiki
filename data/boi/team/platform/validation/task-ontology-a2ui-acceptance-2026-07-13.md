---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/validation-report
title: Task·Ontology·동적 결과 Acceptance 2026-07-13
description: 실제 handler, 브라우저와 로컬 Gemma로 Task·Ontology·동적 결과 계약을 재검증한 결과
tags: [Validation, Task, Ontology, A2UI, Harness, Browser, Gemma]
timestamp: 2026-07-14T12:43:25+09:00
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
  reviewed_at: 2026-07-14T12:43:25+09:00
  review_status: reviewed
---

# 실행 기준

> 이 문서는 재검증 감사 문서다. 빈 Ontology 그래프, Mermaid 초기 로드 실패, 자체 renderer 결함과 grounded 응답 지연을 고친 뒤 결정적·브라우저·Gemma·Adapter gate와 전체 회귀를 다시 실행했다. cache version을 무효화한 cold Gemma 실행까지 p95 10초 기준을 통과해 `reviewed`로 승격했다.

- 검증 기준: `cdab2a2` 공식 A2UI·Mermaid·typed Ontology·grounded follow-up·Planner 결과 재사용·실제 browser journey
- fixture version: `1.0`
- generation model: `google/gemma-4-26b-a4b-qat`
- embedding model: `text-embedding-bge-m3`
- 외부 판정 모델: 사용하지 않음
- LM Studio model load/unload: 0건

# 결과

| 영역 | 결과 |
|---|---:|
| 실제 scenario handler | 50/50 |
| clean 전체 pytest | 831 passed · 실패 0 · 23분 36초 · deprecation warning 1,904건 |
| Gemma 단일·멀티턴 의미 평가 | 17/17 · route·operation·의도·맥락·source 관련성 100% · GPT-5.5 미사용 |
| Browser journey | 21/21 · fresh runtime 실제 조작 · 예상된 revision 409 외 console 오류 0 |
| Browser 1440×1000 | 통과 |
| Browser 1180×850 | 통과 |
| Browser 949×1151 | 통과 |
| Browser 390×844 | 통과 |
| Sigma canvas·하단 inspector | workbench 폭 100% · nonblank · inspector가 폭을 줄이지 않음 · hub/Agent/mobile 최소 간격 82/170/75px · label overlap 0건 |
| Compact graph lifecycle | canvas 미생성 · 한 줄 결과 버튼 · Expanded 복원 통과 |
| invalid surface fallback | 통과 |
| Harness shadow·held-out·사람 검토 | 통과 · 실제 release·rollback 감사 이력 확인 |
| Context Playbook model·team scope | 통과 |
| 반복 실패·NegativeResult·운영 Ontology | 통과 |
| Task Snapshot p95 | 282.23ms |
| Ontology 1-hop p95 | 33.94ms |
| Ontology 4-hop path p95 | 28.92ms |
| 첫 동적 surface update p95 | 25.23ms |
| 생성 graph artifact final p95 | 1.44초 |
| cold 자연어 Mermaid | 6.78초 · deterministic Ontology graph artifact · 10초 기준 통과 |
| grounded Agent turn cold p95 | 9.08초 · 최대 9.43초 · 10초 기준 통과 |
| grounded Agent turn warm p95 | 6.96초 · 최대 9.69초 |
| Graphify | 실제 CLI 5 node·6 edge, import·rollback 통과 |
| OpenKB 0.4.4 | 실제 PDF → private 후보 4개 · index/log 제외 · canonical 변경 0 |
| Mermaid 직접 링크 cold browser | cold URL·desktop reload·mobile reload 통과 · SVG nonblank·console 오류 0 |
| 검색 품질 | Recall@8 100% · authoritative Top-3 100% · 검토 완료 canonical alias 기준 |
| Web·REST·MCP parity | 자연어 route·근거·Task mutation·후보 ID 일치 |
| LM Studio load/unload | 0건 |

브라우저에서는 Task의 `확인한 내용·수행한 조치·판단·결과·근거·막힌 점·다음 업무`, 복수 담당자 picker, revision 409, Ontology 1-hop 지연 확장, node 선택과 canonical 이동, split·집중 보기, Compact 중지·복원, 9개 관계 보기, 동적 표·Timeline·Mermaid·form·Confirmation과 fallback을 실제 DOM과 canvas로 확인했다. 자동 확인은 관계 그림으로 우회하지 않고 기존 preview·confirmation 계약을 통해서만 생성된다.

실제 Graphify CLI가 `graphify <path>`가 아니라 `graphify extract <path>`를 요구한다는 결함을 release gate에서 발견했다. Adapter를 `extract --code-only --no-cluster` 계약에 맞춘 뒤 격리 corpus의 5개 node와 6개 edge를 수입하고 같은 manifest로 모두 rollback했다. 정본 변경은 없었다.

OpenKB는 `0.4.4`를 격리 tool로 실행했다. compatibility gateway가 `response_format: json_object` 요청을 이미 로드된 Gemma의 일반 JSON 요청으로 바꾸고 반환 schema를 검증한다. 실제 PDF에서 private 후보 4개가 생성됐고 `index.md`, `log.md` 후보는 0건이었다. gateway 요청 5회 중 변환은 4회, 복구 재시도는 0회였고 canonical 파일은 바뀌지 않았다.

생성 graph artifact는 GraphQuery 결과를 deterministic compiler로 바로 저장하고 동적 화면을 위해 별도 모델 호출을 하지 않도록 바꿨다. 현재 50개 결정적 실행의 p95는 1.71초다. 자연어 Planner와 grounded 답변은 같은 로컬 Gemma 호출에서 구조화 결과를 함께 만들고 검색 결과를 재사용한다. 최종 응답은 별도 의미·성능 실행 결과로 판정하며 10초 기준을 넘으면 기능 acceptance와 분리해 미달 상태로 남긴다.

# 2026-07-14 재검증

`4ca4743`에서 Mermaid 요청의 대상을 현재 문서와 검증된 관계로 먼저 고정하고, 후속 요청은 직전 답변의 실제 citation을 관계 경계로 사용하도록 변경했다. `cdab2a2`에서는 같은 structured Planner 결과에 grounded answer와 private SOP outline을 함께 담아 지식 답변과 초안 생성의 중복 모델 호출을 제거했다. source alias는 서버가 실제 retrieved ref로 다시 해석하고, 검증되지 않은 ref와 완료 기준·필수 근거가 없는 SOP 윤곽은 폐기한다. 로컬 기본 reasoning effort는 `none`이며 사용자가 명시한 값은 보존한다.

route cache가 이전 schema를 재사용하지 않도록 `SEMANTIC_ROUTE_CACHE_VERSION=21`로 무효화한 뒤 17개 시나리오, 23개 실제 turn을 다시 실행했다. cold p50은 5.00초, p95는 9.08초, 최대는 9.43초였고 warm p50은 1.83초, p95는 6.96초, 최대는 9.69초였다. 의도·맥락·source 관련성·안전성은 모두 100%였고 GPT-5.5는 사용하지 않았다.

공식 `@a2ui/web_core`와 `@a2ui/lit`는 `0.9.1` exact version으로 lock했다. 실제 브라우저는 네 viewport에서 공식 lifecycle, 표·Timeline·Mermaid·관계 탐색·업무 기록·근거 선택·실행 전 확인을 조작했고 21/21을 통과했다. Harness 후보가 없는 운영 runtime에서 이 여정을 성공으로 세지 않고, 격리 acceptance runtime에 검토 가능한 후보를 준비해 rehearsal·release·rollback까지 실행했다. 25개 이하 그래프는 중심 항목을 기준으로 여러 원에 배치하고 그보다 큰 그래프는 ForceAtlas2와 겹침 방지를 사용한다. 최종 화면의 hub·Agent·mobile 최소 node 간격은 각각 82px, 170px, 75px였고 DOM label 겹침은 0건이었다. 관계 문구는 선 위에 겹쳐 그리지 않고 범례·필터·하단 inspector에서 읽는다.

이번 실행 증거는 다음 runtime artifact에 남겼다.

- `.tmp/acceptance-20260714/task-ontology-a2ui-final2.json`
- `.tmp/acceptance-20260714/browser-journeys-final8.json`
- `.tmp/acceptance-20260714/screenshots-final8/`
- `.tmp/acceptance-20260714/graphify-release-final.json`
- `.tmp/acceptance-20260714/openkb-release-final.json`
- `.tmp/acceptance-20260714/agent-semantic-final3.json`
- `.tmp/acceptance-20260714/agent-semantic-final2.json` (동일 turn의 latency 원본)
- `.tmp/pytest-full-20260714-final2.log`
- `.tmp/pytest-full-20260714-final2.exit`

이번 실행은 전체 pytest 단일 실행, 실제 사용자 여정, Mermaid, Graphify와 OpenKB CLI release gate를 모두 새 코드에서 다시 실행했다. Graphify는 실제 export·import·rollback을, OpenKB는 실제 PDF 변환·후보 생성·탐색 파일 제외·정본 비변경을 확인했다. grounded 최종 응답 cold p95도 10초 기준을 통과했으므로 이 revision을 `reviewed`로 기록한다.

# 발견한 결함과 수정

실모델 멀티턴 `업무 이벤트와 SOP 관계 설명 → 방금 설명한 관계만 Mermaid`가 처음에는 평가기에서 artifact 누락으로 표시됐다. 실제 응답은 `mermaid_diagram`을 반환했지만 평가기가 artifact metadata의 `presentation` 필드만 읽고 typed artifact 종류를 표현으로 해석하지 못했다. 동시에 현재 Inbox 화면을 과도하게 우선하는 Planner 응답도 회귀 fixture로 추가했다.

후속 표현 변환은 직전 assistant 답변의 citation source를 우선 경계로 사용하고, broad retrieval candidate를 대상 확정 근거로 쓰지 않도록 수정했다. 평가기는 `mermaid_diagram`을 Mermaid 표현으로 해석하도록 고쳤다. 전체 응답을 다시 채점한 결과 17/17, citation 실재성, 의도 보존과 무단 전환 방지 항목이 모두 통과했다.

Harness 개선 검증에서는 실제 Postgres collection registry에 `harness_failure_patterns`, `harness_shadow_runs`, `harness_versions`가 빠져 연결 상태와 조회 API가 500을 반환하는 결함을 발견했다. 메모리 fixture만으로는 드러나지 않았던 차이이며, 명시 registry와 회귀 테스트를 추가한 뒤 실제 Postgres에서 200 응답을 확인했다.

Context Playbook은 관리자 진단 권한과 실제 Context 주입 권한을 분리했다. 다른 사용자의 private 항목과 검토 전 team provisional 항목은 질문 맥락에 들어가지 않는다. 후보는 서버 shadow fingerprint와 fixture revision이 일치해야 평가할 수 있고, held-in·held-out·adversarial·long-term 기준을 모두 통과해도 `approved_not_deployed`로 남는다.

자동 확인 starter는 처음에 `presentation_hint`를 우선한 graph 분기에 가로채져 plan과 Confirmation 대신 Ontology artifact를 만들었다. graph 실행을 지식 탐색 operation으로 제한하고 `work_routine.plan`은 전용 handler가 처리하도록 수정했다. 재검증에서는 Confirmation component가 실제로 보였고, 확인 전 production routine 변경은 0건이었다.

Timeline API는 16개 행을 반환했지만 응답에 함께 있던 빈 `tour_steps` 배열이 실제 `timeline` 배열보다 먼저 선택돼 화면이 비어 보였다. renderer가 이름이 아니라 첫 번째 non-empty 의미 payload를 선택하도록 수정하고, neighbors·path·workflow·impact·lineage·responsibility·timeline·compare·tour를 화면 버튼으로 각각 전환해 결과 차이를 확인했다.

# Raw artifact

검증 raw artifact는 정본 지식이 아니라 runtime evidence다.

- `.tmp/acceptance-20260714/task-ontology-a2ui-final2.json`
- `.tmp/acceptance-20260714/browser-journeys-final8.json`
- `.tmp/acceptance-20260714/screenshots-final8/`
- `.tmp/acceptance-20260714/agent-semantic-final3.json`
- `.tmp/acceptance-20260714/agent-semantic-final2.json`
- `.tmp/agent-v2-search-quality-final8.log`
- `.tmp/task-ontology-a2ui-acceptance-latest.json` (50/50 · 최신 성능 계측)
- `.tmp/task-ontology-a2ui-browser-isolated-final.json` (21/21 · 네 viewport)
- `.tmp/task-ontology-a2ui-browser-isolated-final/` (실제 화면 캡처)
- `.tmp/agent-v2-semantic-cold-final.json` (cold 17/17 · p95 9.08초)
- `.tmp/agent-v2-semantic-final-pass.json` (warm 17/17 · p95 6.96초)
- `.tmp/agent-v2-interface-parity-latest.log` (10/10)
- `.tmp/agent-v2-search-quality-latest.log` (15/15)
- `.tmp/pytest-full-final-pass.log` (831 passed · 실패 0 · 23분 36초)
- `.tmp/pytest-full-final-pass.exit` (exit 0)
- `.tmp/agent-v2-search-quality-final.json`
- `.tmp/agent-v2-interface-parity-final4.json`
- `.tmp/acceptance-20260714/openkb-release-final.json`
- `.tmp/acceptance-20260714/graphify-release-final.json`
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
