---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-type
title: 설비 Alarm 발생
description: 설비 Alarm 또는 Response Chain 이상이 발생해 설비 이상 대응 SOP를 시작하는 이벤트
tags: [EventType, Equipment, SOP, EventBroker]
timestamp: 2026-06-17T16:00:00+09:00
boi_id: boi:public:event-types:equipment.alarm.raised.v1
visibility: public
classification: internal
owner: AIX 확산 TF
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
event_type: equipment.alarm.raised.v1
---

# Summary

`equipment.alarm.raised.v1`는 [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)의 `detect` stage를 시작한다.

# Recommended Actions

- [Trend / 이력 확인 요청](/public/actions/api/request-trend-history.md)
- [Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md)
- [원인 분석 이벤트 발행](/public/actions/event-broker/create-root-cause-event.md)
- [Alarm / Trend / 이력 맥락 확인](/public/actions/manual/confirm-alarm-context.md)

# Examples

```bash
curl -X POST "http://localhost:8000/api/workflows/demo/equipment-anomaly/start?employee_id=100001"
```

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
