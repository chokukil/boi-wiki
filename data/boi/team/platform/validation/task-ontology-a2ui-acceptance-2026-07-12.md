---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/report
title: Task·Ontology·동적 화면 Acceptance 결과 2026-07-12
description: 32개 결정적 시나리오와 로컬 Gemma 의미 평가, 성능 및 모델 residency 검증 결과
tags: [Task, Ontology, A2UI, Acceptance, Validation]
timestamp: 2026-07-12T21:45:00+09:00
boi_id: boi:team:platform:validation:task-ontology-a2ui-2026-07-12
visibility: team
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:team:platform
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance
  - type: code
    ref: tests/test_task_ontology_a2ui.py
  - type: code
    ref: tests/test_agent_v2.py
  - type: code
    ref: scripts/evaluate_agent_v2_work_scenarios.py
review:
  reviewer: platform-lead
  review_status: reviewed
---

# 결과 요약

| 항목 | 결과 |
|---|---:|
| Acceptance fixture | 32개, 구성 검증 통과 |
| Agent·Ontology·A2UI 집중 회귀 | 151 passed |
| Agent 실모델 시나리오 | 17/17, 100% |
| Routing | 100% |
| Safety·무단 전환 방지 | 100% |
| Context·source 관련성 | 100% |
| 의도 보존 | 100% |
| Task Snapshot p95 | 328.38ms |
| 1-hop graph p95 | 36.39ms |
| LM Studio load/unload 변화 | 0/0 |
| 브라우저 Ontology 결과 | 10 node·9 edge, 필터·복원 통과 |
| 브라우저 viewport | 1440×1000, 390×844 통과 |

실모델 평가는 이미 로드된 `google/gemma-4-26b-a4b-qat`와 `text-embedding-bge-m3`를 사용했다. GPT-5.5는 호출하지 않았다.

# 검증에서 발견하고 수정한 결함

1. Postgres collection registry에 A2UI surface table이 없어 모든 Agent turn이 500이 되던 문제를 수정했다.
2. 8KB 응답 압축이 Markdown과 중복된 HTML보다 WorkIntent·citation을 먼저 제거하던 순서를 수정했다.
3. 접근할 수 없는 자료나 임의 문자열이 Task 완료 근거로 통과하지 못하도록 했다.
4. reviewer가 배정에는 포함되지만 배정 변경 route에서 Task를 찾지 못하던 경계를 수정했다.
5. GraphQueryPlan의 `time_from/time_to`가 실제 node 필터에 반영되도록 했다.
6. 멀티턴 평가는 마지막 짧은 문장뿐 아니라 전체 대화 주제를 기준으로 의도 보존을 평가하도록 했다.
7. 설명·비교 요청이 Action 같은 draft capability로 잘못 전환되던 경우를 구조화된 `result_purpose`와 operation 계약으로 차단했다. 명시적인 실행·생성 요청과 `deep.research`는 영향을 받지 않는다.

# 브라우저 검증

저장된 WorkSession과 artifact를 다시 열어 A2UI `OntologyExplorer`가 실제 DOM에 렌더링되는지 확인했다. 10개 node와 9개 관계가 표시됐고, node 선택 시 관계 필터가 동작했다. 데스크톱과 모바일 viewport에서 가로 overflow, 콘솔 오류와 실패한 네트워크 요청은 없었다. 잘못된 surface는 기존 typed artifact renderer로 복구하는 결정적 테스트를 별도로 유지한다.

# 근거 보존

raw JSON 결과와 브라우저 실행 로그는 runtime artifact에 두며 정본으로 승격하지 않는다. 반복 검증은 [Task·Ontology·동적 화면 검증 기준](/docs/boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance)의 명령과 기준을 따른다.
