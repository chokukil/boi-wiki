---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/event-type
title: 연구소-양산 FAB 비교 요청
description: 단면검사 결과 확인 후 연구소-양산 FAB Trend를 비교해야 하는 시점
tags:
- EventType
- DirectDevelopment
- SOP
- SIMULATED
timestamp: '2026-06-21T09:15:00+09:00'
boi_id: boi:public:event-types:direct_development.fab_trend.compare_requested.v1
visibility: public
classification: internal
owner: AIX 확산 TF / Direct Development PoC
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
- type: event_catalog
  ref: data/event_catalog/event_types.yaml
review:
  reviewer: tf-lead
  review_status: reviewed
event_type: direct_development.fab_trend.compare_requested.v1
sop_ref: boi:public:sop:direct-development-reporting
sop_stage_id: fab_trend_compare
workflow_stage: 연구소-양산 FAB 비교
recommended_actions:
- direct_development.fab_trend_compare.simulate
- direct_development.create_reporting_event
recommended_manual_actions: []
---

# Summary

`direct_development.fab_trend.compare_requested.v1`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 `fab_trend_compare` stage를 실행하거나 사람이 판단해야 할 지점을 기록한다.

# Recommended Actions

- [연구소-양산 FAB 비교 Trend 확인 시뮬레이션](/public/actions/langflow/direct-development-fab-trend-compare-simulate.md)
- [Reporting 요청 이벤트 발행](/public/actions/event-broker/direct-development-create-reporting-event.md)

# Simulation Boundary

사내 시스템이 필요한 action은 `SIMULATED`로 기록되며 실제 시스템 호출이 아니다. 사람이 해야 하는 단계는 `manual_required`, 승인 전 공유는 `approval_required`로 멈춘다.

# Example

```bash
curl -X POST "http://localhost:8000/api/workflows/direct-development-reporting/start?employee_id=100001" -H "x-service-token: $SERVICE_TOKEN"
```

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
