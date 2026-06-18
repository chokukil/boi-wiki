---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/event-type
title: 이상 조치 요청
description: 담당자 알림, 공정 Hold, Spec/Rule 변경 후보를 추적하는 설비 이상 대응 이벤트
tags: [EventType, Equipment, CorrectiveAction, SOP]
timestamp: 2026-06-17T16:00:00+09:00
boi_id: boi:public:event-types:corrective_action.requested.v1
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
event_type: corrective_action.requested.v1
---

# Summary

`corrective_action.requested.v1`는 [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)의 `correct` stage를 실행한다. 자동 action과 manual approval을 함께 남겨 고위험 조치가 임의 실행되지 않도록 한다.

# Recommended Actions

- [이상 조치 담당자 알림](/public/actions/api/notify-action-owner.md)
- [공정 진행 금지 요청](/public/actions/api/block-process-progress.md)
- [Spec / Rule 변경 요청](/public/actions/api/change-spec-rule.md)
- [공정 진행 금지 승인](/public/actions/manual/approve-process-hold.md)
- [Spec / Rule 변경 승인](/public/actions/manual/approve-spec-rule-change.md)
- [정비 조치 완료 확인](/public/actions/manual/confirm-maintenance-done.md)

# Citations

[1] Event Catalog: `data/event_catalog/event_types.yaml`
