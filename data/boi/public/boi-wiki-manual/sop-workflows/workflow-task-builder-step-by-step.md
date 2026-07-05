---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Workflow/Task Builder Step-by-step
description: 직개발 결과 확인 및 Reporting 시나리오로 /sops/new Workflow/Task Builder를 작성하고 실행 smoke와 TAT로 검증하는 절차
tags: [Manual, SOP, Workflow, Task, TAT, DirectDevelopment]
timestamp: 2026-07-04T14:05:00+09:00
boi_id: boi:public:boi-wiki-manual:sop-workflows:workflow-task-builder-step-by-step
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: sop
    ref: boi:public:sop:direct-development-reporting
  - type: source-image
    ref: /public/boi-wiki-manual/_media/source/natural-language-poc/sop_sample_image.png
  - type: script
    ref: scripts/check_workflow_task_builder_tutorial.mjs
  - type: script
    ref: scripts/run_direct_development_sop_poc.py
  - type: capture-manifest
    ref: data/boi/public/boi-wiki-manual/sop-workflows/workflow-task-builder-capture-manifest.json
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

이 문서는 `직개발 결과 확인 및 Reporting` 업무를 예시로, `/sops/new`에서 Workflow 전체와 Task 단위를 먼저 잡고 필요한 Task만 상세화하는 절차를 보여준다.

핵심은 내부 ID를 먼저 맞추는 것이 아니라 `어떤 맥락에서 어떤 판단을 하고, 어떤 근거와 결과를 BoI로 남길지`를 정하는 것이다. 실행 중 Raw Data, PDF, PPT, Excel, 로그, 캡처 같은 원본 파일은 SOP Builder가 아니라 SOP Run, Inbox 판단, Report BoI 검토에서 Data Lake artifact로 첨부한다.

# 준비사항

- BoI API: `http://localhost:28000`
- 작성 화면: `/sops/new?employee_id=100001`
- 기준 SOP: [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)
- 원본 이미지: `/public/boi-wiki-manual/_media/source/natural-language-poc/sop_sample_image.png`

![원본 SOP 이미지](/public/boi-wiki-manual/_media/source/natural-language-poc/sop_sample_image.png)

# 1. Workflow 개요 입력

`Workflow 개요`에서는 전체 업무 맥락을 먼저 적는다. 여기서 입력한 업무 대상, 업무 상황, 판단 질문, 필요한 근거, 남길 결과가 이후 Task, Event, Action, Skill 추천의 기준이 된다.

예시 입력:

| 항목 | 값 |
|---|---|
| 제목 | 직개발 결과 확인 및 Reporting |
| 업무 목적 | 직개발 결과 확인, 단면검사 판단, 보고서 작성, 협의체 공유 전 승인 기록을 하나의 Workflow로 남긴다. |
| 업무 대상 | Product-A / Tech-A / Work ID 1.10 |
| 판단 질문 | 단면검사가 필요한가? 협의체 공유 전에 근거와 승인 상태가 충분한가? |
| 필요한 근거 | Response Trend, Map View Image, 단면검사 결과, 연구소-양산 FAB 비교 Trend, Reporting 초안 |
| 남길 결과 | 검증 보고서 BoI, 결정 기록, 협의체 공유 승인 기록 |

![Workflow 개요 입력](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-01-workflow-overview.png)

# 2. Task 맵 작성

`Task 맵`에서는 Workflow 전체를 작은 업무 단위로 나눈다. Task 상세가 전부 정리되지 않아도 Workflow 제목 또는 설명과 Task 1개 이상이면 틀을 저장할 수 있다.

예시 Task:

| Task | 실행 방식 | 목표 TAT | 기준 TAT |
|---|---|---:|---:|
| Response Trend 확인 | Autopilot | 30분 | 평균 2h |
| Map View 확인 | Autopilot | 30분 | 평균 1h |
| 단면검사 판단 | Manual | 15분 | 최근 3건 40분 |
| 단면검사 의뢰/결과 확인 | Copilot | 1일 | 평균 2일 |
| 연구소-양산 FAB 비교 | Autopilot | 1h | 평균 4h |
| Reporting | Copilot | 1h | 평균 4h |
| 협의체 공유 | Copilot | 30분 | 평균 2h |

실행 방식은 사용자에게 `Manual`, `Copilot`, `Autopilot` 세 가지만 보여준다.

- `Manual`: 사람이 직접 판단하거나 작업하고 결과를 남긴다.
- `Copilot`: BoI Wiki Agent/Skill/API 또는 외부 AI/도구의 도움을 받아 사람이 최종 판단과 결과를 남긴다.
- `Autopilot`: Agent/System이 정책 범위 안에서 자동 실행하고 검증 기록을 남긴다.

![Task 맵 작성](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-02-task-map.png)

# 3. Task 상세 설정

필요한 Task를 선택해 판단 질문, 필요한 근거, 결과 BoI, 지식 업데이트 정책, TAT 기준을 보강한다.

예를 들어 `단면검사 판단` Task는 `Manual`이다. 이 Task는 사람이 Response Trend와 Map View 근거를 보고 단면검사 필요 여부를 결정한다.

![Task 상세 설정](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-03-task-detail.png)

Copilot Task는 두 경우를 모두 허용한다.

- BoI Wiki 내부 Agent, Skill, API, MCP를 사용한 경우
- ChatGPT, Claude, Excel, 사내 도구, 별도 스크립트처럼 BoI Wiki가 세부 과정을 추적하지 못하는 외부 도움을 받은 경우

외부 Copilot은 세부 실행 로그를 요구하지 않는다. 대신 결과 파일, 요약, 판단 근거, 사람이 남긴 메모를 Data Lake artifact나 BoI 링크로 남긴다.

# 4. 시작/연결 설정

`시작/연결`에서는 이 Workflow가 어떤 신호로 시작되는지 정한다. 기존 Event를 재사용할 수 있고, Webhook, Legacy/API Poll, MCP/Data Lake adapter, 외부 Kafka 직접 발행, 수동 시작을 선택할 수 있다.

외부 Kafka 직접 발행은 먼저 BoI Event 발행 가이드 BoI 초안을 만들고, topic, schema, required fields, sample payload, idempotency key, trace policy, 테스트 URL을 외부 시스템 담당자에게 제공하는 흐름으로 다룬다.

![시작/연결 설정](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-04-start-signal.png)

# 5. 검증·저장

최종 단계에서는 SOP 실행 흐름 draft를 저장한다. 이 시점에는 운영 catalog, Event Broker runtime, Action Gateway에 바로 반영하지 않는다.

중요한 경계:

- SOP Builder는 실제 Raw Data 파일을 올리는 화면이 아니다.
- 이 화면에서는 필요한 근거 종류와 어느 Task에서 판단에 쓰일지만 설계한다.
- 실제 원본 파일은 Workflow 실행 중 SOP Run, Inbox 판단, Report BoI 검토에서 Data Lake artifact로 첨부한다.
- OKF 문서에는 원본 파일이 아니라 artifact URL, profile, sample, checksum, validation metadata를 남긴다.

![검증 저장](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-05-review-save.png)

# 6. 저장된 SOP 확인

기준 문서는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)이다. 문서에는 원본 이미지, Workflow stage, Event Type, 주요 Action, simulation boundary가 남아 있다.

![저장된 SOP 문서](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-06-saved-sop.png)

# 7. 실행 테스트

다음 smoke는 `direct-development-reporting` workflow를 시작하고, 수동 판단 단계와 simulated Langflow Action, approval-required 단계를 검증한다.

```bash
python scripts/run_direct_development_sop_poc.py
```

캡처까지 함께 검증하려면 다음 명령을 사용한다.

```bash
node scripts/check_workflow_task_builder_tutorial.mjs \
  --base-url http://localhost:28000 \
  --employee-id 100001 \
  --run-smoke \
  --strict
```

이 스크립트는 `/sops/new`에 예시 값을 실제로 입력하고, `workflow_tasks` hidden payload에 7개 Task와 `Manual/Copilot/Autopilot`이 모두 포함되는지 확인한다.

![실행 status](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-07-runtime-status.png)

# 8. TAT 성과 화면 확인

Workflow와 Task TAT는 runtime event/action timestamp에서 계산하되, 사람은 JSON 로그가 아니라 TAT 성과 화면에서 확인한다.

화면: `/workflows/direct-development-reporting/tat?employee_id=100001`

표시 기준:

- Workflow TAT: 시작 신호부터 완료까지
- Task TAT: Task 시작부터 완료 또는 다음 Task 전환까지
- 기준 TAT 대비 최근/평균 실측 TAT
- 병목 Task와 최대 개선 Task
- Manual, Copilot, Autopilot 실행 방식 mix
- 실패율, 반려율, 근거 부족률 같은 품질 guardrail
- 표본이 부족하면 `실측 전` 또는 관찰 대상으로 표시

![TAT summary](/public/boi-wiki-manual/_media/browser/workflow-task-builder/workflow-task-08-tat-summary.png)

# 결과 해석

이 튜토리얼에서 남아야 하는 근거는 다음과 같다.

- Workflow/Task 구조가 사람 기준으로 이해된다.
- Task마다 Manual, Copilot, Autopilot이 명확히 구분된다.
- Copilot은 내부 BoI Wiki 도구와 외부 AI/도구 사용을 모두 포괄한다.
- TAT 성과 화면에서 기준 대비 개선 시간, 병목 Task, 표본 수, guardrail을 확인할 수 있다.
- 실행 중 원본 파일은 Data Lake artifact로 연결되고, OKF에는 bounded reference만 남는다.

# Citations

- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)
- [SOP Workflow 작성과 Runtime 연결](/public/boi-wiki-manual/sop-workflows/create-and-connect-sop.md)
- [SOP Authoring Harness](/public/harness/sop-authoring-harness.md)
- [Data Lake Artifact Harness](/public/harness/data-lake-artifact-harness.md)
- `scripts/check_workflow_task_builder_tutorial.mjs`
- `scripts/run_direct_development_sop_poc.py`
