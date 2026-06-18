---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-type
title: 원인 분석 요청
description: 설비 이상 맥락을 바탕으로 원인 후보 분석을 요청하는 이벤트
tags: [EventType, Equipment, RootCause, SOP]
timestamp: 2026-06-17T16:00:00+09:00
boi_id: boi:public:event-types:root_cause.analysis.requested.v1
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
event_type: root_cause.analysis.requested.v1
---

# Summary

`root_cause.analysis.requested.v1`는 [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)의 `analyze` stage를 실행한다. 분석 결과는 [장비 보전 가이드 요청](/public/event-types/maintenance.guide.requested.v1.md)으로 이어진다.

# Recommended Actions

- [Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md)
- [장비 보전 가이드 요청](/public/actions/api/request-maintenance-guide.md)
- [장비 보전 가이드 이벤트 발행](/public/actions/event-broker/create-maintenance-guide-event.md)
- [원인 후보 검토 및 판단](/public/actions/manual/review-root-cause.md)

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
