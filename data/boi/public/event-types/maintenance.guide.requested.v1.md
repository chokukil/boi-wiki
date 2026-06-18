---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-type
title: 장비 보전 가이드 요청
description: 원인 후보를 바탕으로 장비 보전 가이드와 runbook 참조를 요청하는 이벤트
tags: [EventType, Equipment, Maintenance, SOP]
timestamp: 2026-06-17T16:00:00+09:00
boi_id: boi:public:event-types:maintenance.guide.requested.v1
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
event_type: maintenance.guide.requested.v1
---

# Summary

`maintenance.guide.requested.v1`는 [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)의 `guide` stage에서 SOP/Runbook과 장비 이력을 참조한다. 결과는 [이상 조치 요청](/public/event-types/corrective_action.requested.v1.md)으로 이어진다.

# Recommended Actions

- [Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md)
- [장비 보전 가이드 요청](/public/actions/api/request-maintenance-guide.md)
- [이상 조치 요청 이벤트 발행](/public/actions/event-broker/create-corrective-action-event.md)
- [원인 후보 검토 및 판단](/public/actions/manual/review-root-cause.md)

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
