---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/report
title: Task·Ontology·동적 화면 Acceptance 결과 2026-07-12
description: 과거 Task·Ontology·동적 화면 검증 기록의 한계와 재검증이 필요한 범위를 남긴 draft 감사 문서
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
status: draft
answer_scope: validation
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance
implementation_refs:
  - type: repo
    ref: tests/test_task_ontology_a2ui.py
  - type: repo
    ref: tests/test_agent_v2.py
  - type: repo
    ref: scripts/evaluate_agent_v2_work_scenarios.py
review:
  reviewer: platform-lead
  review_status: needs_revision
---

# 결과 정정

이 보고서는 acceptance 결과로 사용할 수 없어 `draft`로 철회했다. 당시 fixture 32개는 계약 이름과 개수만 검사했으며 32개 handler 실행 결과가 아니다. 브라우저 viewport 역시 journey manifest의 항목 존재를 검사했을 뿐, 해당 journey를 자동 실행한 결과가 아니다.

아래 표는 과거 기록을 삭제하지 않고 무엇이 측정값이고 무엇이 과대 표기였는지 구분하기 위한 감사 기록이다.

| 항목 | 결과 |
|---|---:|
| Acceptance fixture | 32개 이름·구성만 확인, scenario 실행 아님 |
| Agent·Ontology·A2UI 집중 회귀 | 일부 pytest 통과 기록, 32개 계약과 1:1 대응 없음 |
| Agent 실모델 시나리오 | 별도 평가 기록, 결정적 acceptance 대체 불가 |
| Routing | 별도 평가기 기록, acceptance 미확정 |
| Safety·무단 전환 방지 | 일부 회귀 기록, 32개 계약 전체 미확정 |
| Context·source 관련성 | 별도 평가기 기록, acceptance 미확정 |
| 의도 보존 | 별도 평가기 기록, acceptance 미확정 |
| Task Snapshot p95 | 328.38ms |
| 1-hop graph p95 | 36.39ms |
| LM Studio load/unload 변화 | 0/0 |
| 브라우저 Ontology 결과 | 수동 단일 화면 확인, 통합 Explorer acceptance 아님 |
| 브라우저 viewport | manifest 형식 확인, journey 자동 실행 아님 |

실모델 평가는 이미 로드된 `google/gemma-4-26b-a4b-qat`와 `text-embedding-bge-m3`를 사용했다. GPT-5.5는 호출하지 않았다.

# 당시 발견하고 수정한 결함

1. Postgres collection registry에 A2UI surface table이 없어 모든 Agent turn이 500이 되던 문제를 수정했다.
2. 8KB 응답 압축이 Markdown과 중복된 HTML보다 WorkIntent·citation을 먼저 제거하던 순서를 수정했다.
3. 접근할 수 없는 자료나 임의 문자열이 Task 완료 근거로 통과하지 못하도록 했다.
4. reviewer가 배정에는 포함되지만 배정 변경 route에서 Task를 찾지 못하던 경계를 수정했다.
5. GraphQueryPlan의 `time_from/time_to`가 실제 node 필터에 반영되도록 했다.
6. 멀티턴 평가는 마지막 짧은 문장뿐 아니라 전체 대화 주제를 기준으로 의도 보존을 평가하도록 했다.
7. 설명·비교 요청이 Action 같은 draft capability로 잘못 전환되던 경우를 구조화된 `result_purpose`와 operation 계약으로 차단했다. 명시적인 실행·생성 요청과 `deep.research`는 영향을 받지 않는다.

# 남은 검증

통합 `/knowledge-graph` Sigma Explorer, Agent와 Task Console의 공통 A2UI renderer, GraphQuery 9종 의미 차이, Inbox·보고서·Task Console Snapshot parity와 세 viewport 실제 browser journey를 다시 실행해야 한다. 실패를 포함한 새 실행 보고서가 생성되기 전에는 이 문서를 reviewed로 되돌리지 않는다.

# 근거 보존

raw JSON 결과와 브라우저 실행 로그는 runtime artifact에 두며 정본으로 승격하지 않는다. 반복 검증은 [Task·Ontology·동적 화면 검증 기준](/docs/boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance)의 명령과 기준을 따른다.
