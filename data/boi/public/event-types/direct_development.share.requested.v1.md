---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/event-type
title: 협의체 공유 요청
description: Reporting 초안을 협의체에 공유하기 전에 preview와 승인 상태를 기록해야 하는 시점
tags:
- EventType
- DirectDevelopment
- SOP
- SIMULATED
timestamp: '2026-06-21T09:15:00+09:00'
boi_id: boi:public:event-types:direct_development.share.requested.v1
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
event_type: direct_development.share.requested.v1
sop_ref: boi:public:sop:direct-development-reporting
sop_stage_id: share
workflow_stage: 협의체 공유
recommended_actions:
- direct_development.messenger_share_preview.simulate
- direct_development.messenger_share.publish
recommended_manual_actions:
- manual.direct_development.approve_committee_share
---

# Summary

`direct_development.share.requested.v1`는 [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 `share` stage를 실행하거나 사람이 판단해야 할 지점을 기록한다.

# Recommended Actions

- [협의체 공유 Preview 시뮬레이션](/public/actions/langflow/direct-development-messenger-share-preview-simulate.md)
- [협의체 메신저 공유 실행](/public/actions/webhook/direct-development-messenger-share-publish.md)
- [협의체 공유 승인](/public/actions/manual/direct-development-approve-committee-share.md)

# Simulation Boundary

사내 시스템이 필요한 action은 `SIMULATED`로 기록되며 실제 시스템 호출이 아니다. 사람이 해야 하는 단계는 `manual_required`, 승인 전 공유는 `approval_required`로 멈춘다.

# Example

```bash
curl -X POST "http://localhost:8000/api/workflows/direct-development-reporting/start?employee_id=100001" \
  -H "x-service-token: $SERVICE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_confirmed":true}'
```

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
