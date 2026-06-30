---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/harness
title: Inbox Review Report Harness
description: BoI Inbox 검증 보고서 품질, 성능, 근거 정책을 검증하는 하네스
tags: [BoIWiki, Inbox, Harness, Report]
timestamp: 2026-06-30T00:00:00+09:00
boi_id: boi:public:harness:inbox-review-report-harness
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
    ref: harness/inbox-review-report-harness.md
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Inbox Review Report Harness

`/inbox`와 `GET /api/inbox`는 빠른 slim manifest로 먼저 렌더링해야 하며 LLM, Langflow, Data Lake, report materialize를 기다리지 않는다. 화면에 보이는 report 후보는 bounded background queue에 넣어 순차 warm-up할 수 있지만, 이 작업이 첫 응답을 막아서는 안 된다. 검증 보고서는 task 생성/변경, 명시적 refresh, 또는 background queue에서 생성되고, QA를 통과한 BoI만 의사결정 보고서로 표시한다.

보고서의 실제 근거는 Event Broker 실제 Event, Action Gateway 결과, 생성 BoI, manual note, Data Lake artifact, 유사 과거 사례다. Langflow Universal Simulator 결과는 dry-run/PoC용이며 기본 보고서 근거로 섞지 않는다.

기본 화면과 report visible text에는 `source_id`, raw trace/action id, schema dump, `WorkflowDefinition`, 반복 fallback 문장이 없어야 한다. 고위험 group bulk approve는 차단한다.

검증 보고서는 판단 준비도를 포함해야 한다. 각 항목은 `개별 승인/반려 검토 가능`, `추가 근거 필요`, `개별 검토 필요` 중 사용자가 다음 행동을 알 수 있는 상태와 먼저 확인할 근거를 보여준다. 그룹 카드는 우선순위와 처리 순서만 보여주는 roll-up이며, group report BoI 링크나 group report 생성 버튼을 노출하지 않는다.

Data Lake가 켜져 있고 관련 source가 있으면 sample/profile/artifact link를 자동 근거 후보로 붙일 수 있다. 없으면 근거를 꾸미지 않고 Event, Action, 생성 BoI, manual note, 과거 사례만 사용한다.

```bash
python scripts/check_inbox_narrative_quality.py --base-url http://localhost:28000 --summary --require-ready-report
node scripts/check_boi_inbox_ui.mjs --strict
pytest tests/test_boi_api_routes.py -q -s -k "boi_inbox or agent_inbox"
```
