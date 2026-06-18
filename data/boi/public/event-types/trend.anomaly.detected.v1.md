---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-type
title: Trend 이상 감지
description: Trend 이상 감지 결과를 설비 이상 대응 SOP의 감지 stage에 연결하는 이벤트
tags: [EventType, Equipment, Trend, SOP]
timestamp: 2026-06-17T16:00:00+09:00
boi_id: boi:public:event-types:trend.anomaly.detected.v1
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
event_type: trend.anomaly.detected.v1
---

# Summary

`trend.anomaly.detected.v1`는 [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)의 감지 stage에서 trend 이상을 확인하고, 필요 시 [원인 분석 이벤트](/public/event-types/root_cause.analysis.requested.v1.md)로 이어진다.

# Recommended Actions

- [Trend / 이력 확인 요청](/public/actions/api/request-trend-history.md)
- [원인 분석 이벤트 발행](/public/actions/event-broker/create-root-cause-event.md)
- [Alarm / Trend / 이력 맥락 확인](/public/actions/manual/confirm-alarm-context.md)

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
