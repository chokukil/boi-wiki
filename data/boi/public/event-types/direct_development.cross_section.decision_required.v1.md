---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/event-type
title: 단면검사 필요 여부 판단 요청
description: Map View와 Trend 근거를 바탕으로 사람이 단면검사 필요 여부를 판단해야 하는 시점
tags:
- EventType
- DirectDevelopment
- SOP
- SIMULATED
timestamp: '2026-06-21T09:15:00+09:00'
boi_id: boi:public:event-types:direct_development.cross_section.decision_required.v1
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
event_type: direct_development.cross_section.decision_required.v1
sop_ref: boi:public:sop:direct-development-reporting
sop_stage_id: cross_section_decision
workflow_stage: 단면검사 판단
recommended_actions: []
recommended_manual_actions:
- manual.direct_development.decide_cross_section
---

# Summary

`direct_development.cross_section.decision_required.v1`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 `cross_section_decision` stage를 실행하거나 사람이 판단해야 할 지점을 기록한다.

# Recommended Actions

- [단면검사 필요 여부 판단](/public/actions/manual/direct-development-decide-cross-section.md)

# Simulation Boundary

사내 시스템이 필요한 action은 `SIMULATED`로 기록되며 실제 시스템 호출이 아니다. 사람이 해야 하는 단계는 `manual_required`, 승인 전 공유는 `approval_required`로 멈춘다.

# Example

```bash
curl -X POST "http://localhost:8000/api/workflows/direct-development-reporting/start?employee_id=100001" -H "x-service-token: $SERVICE_TOKEN"
```

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
