---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: SOP Workflow 작성과 Runtime 연결
description: 사용자 SOP 이미지/문서에서 Workflow, Task, Event, Action, Skill, Data Lake 근거 요구사항을 만드는 절차
tags: [Manual, SOP, Workflow, Task, EventBroker, ActionGateway, Skill]
timestamp: 2026-06-18T15:20:00+09:00
boi_id: boi:public:boi-wiki-manual:sop-workflows:create-and-connect-sop
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
    ref: harness/sop-authoring-harness.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

사용자가 SOP 문서나 이미지를 주면 agent는 관련 BoI Wiki 문서를 먼저 검색하고, 전체 Workflow와 Task 맵을 추출해 OKF SOP package를 만든다. Task마다 판단 질문, 필요한 근거, 실행 방식, Action 또는 Skill, 결과 BoI, TAT 기준을 정리한다.

원본 SOP 이미지나 업무 화면 캡처는 해석 결과와 분리한다. 원본 asset은 `_media/source/{source-slug}/...`에 보존하고, agent가 임의로 다시 그리거나 파일명을 덮어쓰지 않는다.

일반 사용자가 Web UI에서 직접 따라할 때는 [Workflow/Task Builder Step-by-step](/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md)을 기준으로 한다. 이 문서는 `직개발 결과 확인 및 Reporting` 예시를 사용해 Workflow 개요, Task 맵, Task 상세, 시작/연결, 검증·저장, 실행 smoke, TAT 확인을 순서대로 보여준다.

# Package Output

- SOP BoI 문서 with `workflow.workflow_key`, `workflow.tasks`, legacy `workflow.stages` alias
- Event Type docs
- API/Webhook/MCP/Langflow/Manual/Event Broker/Skill action spec docs
- `data/event_catalog/event_types.yaml` and `data/action_catalog/actions.yaml` draft patches
- OKF links, citations, media references
- source media manifest entries for user-supplied SOP images or screenshots

# Workflow / Task Rule

각 Task는 최소 `task_id`, `task_name`, `stage_goal`, `execution_mode`, `decision_question`, `required_evidence`, `expected_outputs`를 가진다. 구체화된 Task는 `actions`, `skills`, `tat_target`, `baseline_tat`, `measurement_policy`, `approval_policy`, `verification_policy`, `fallback_owner`를 추가한다.

`workflow.stages`는 기존 문서와 runtime 호환을 위한 legacy alias다. 새 문서와 사용자-facing 설명은 `Workflow / Task`를 기준으로 한다. 단계 전환 Event는 Task detail에서 정의하고, Action 또는 Skill이 다음 Event를 발행해야 하면 해당 Task 실행 연결에 `emits_event_type`을 남긴다.

SOP Builder에서는 Raw Data나 작업 결과 파일을 업로드하지 않는다. 실행 중 필요한 원본 파일은 SOP Run, Inbox 판단, Manual Action 완료, Report BoI 검토, Agent 대화에서 Data Lake artifact로 첨부하고, SOP 정의에는 필요한 근거 종류와 첨부 위치만 남긴다.

# Validation

1. `python scripts/okf_lint.py --root data --include-logs --strict-media`
2. `pytest tests -q -s`
3. `python scripts/check_boi_wiki_mcp.py`
4. `python scripts/run_equipment_sop_poc.py`
5. `python scripts/run_equipment_sop_poc.py --scenario-profile semiconductor-varied --count 8`
6. `python scripts/check_langflow_universal_simulator.py --langflow-url http://localhost:7860 --boi-api-url http://localhost:28000`

SSO dev overlay에서 검증할 때는 BoI API가 Keycloak session 또는 service token을 요구한다. 자동 smoke는 browser login을 쓰지 않으므로 다음처럼 service token을 명시한다.

```bash
SERVICE_TOKEN="$SERVICE_TOKEN" python scripts/run_equipment_sop_poc.py
```

사용자 bearer token으로 검증해야 하면 `BOI_AUTH_BEARER`를 넘긴다. `SERVICE_TOKEN`과 `BOI_AUTH_BEARER`가 모두 있으면 둘 다 헤더에 붙지만, 일반 검증에서는 하나만 사용한다.

반도체 업무 차이를 검증할 때는 단일 고정 payload를 seed하지 않는다. `semiconductor-varied` profile은 ETCH pressure spike, CVD temperature drift, Metrology ring pattern, Furnace recipe mismatch를 Event Broker publish와 Action Gateway 실행 경로로 생성한다. Inbox와 Agent는 이 경로에서 생성된 장비, LOT, Wafer, Alarm, Trend/Raw 상태, 승인 위험도를 기준으로 업무 차이를 비교해야 한다.

# Citations

- [SOP Authoring Harness](/public/harness/sop-authoring-harness.md)
- [Workflow/Task Builder Step-by-step](/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md)
- [Data Lake Artifact Lifecycle](/public/boi-wiki-manual/data-lake/data-lake-artifact-lifecycle.md)
- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
