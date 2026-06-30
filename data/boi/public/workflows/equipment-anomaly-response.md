---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/workflow-definition
title: Equipment Anomaly Response WorkflowDefinition
description: 설비 알람 Event를 기준으로 SOP, Action, Manual Handoff, Generated BoI를 연결하는 event-native WorkflowDefinition
tags: [WorkflowDefinition, EventNative, Equipment, SOP]
timestamp: 2026-06-27T11:25:00+09:00
boi_id: boi:public:workflows:equipment-anomaly-response
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
workflow_definition_key: equipment-anomaly-response
workflow_engine: event_native
entry_events:
  - equipment.alarm.raised.v1
emitted_events:
  - trend.anomaly.detected.v1
  - root_cause.analysis.requested.v1
  - maintenance.guide.requested.v1
  - corrective_action.requested.v1
sop_refs:
  - boi:public:sop:equipment-abnormal-response
action_refs:
  - sop.equipment.request_trend_history
  - sop.equipment.request_raw_map
  - sop.equipment.share_cause_analysis
  - sop.equipment.request_maintenance_guide
  - manual.equipment.corrective_action
event_skill_refs:
  - event.workflow_trigger
  - event.workflow_transition
action_skill_refs:
  - evidence.quality_trend
  - evidence.raw_data_lookup
  - event.publish
  - manual.handoff_complete
source_refs:
  - type: catalog
    ref: data/workflow_catalog/workflows.yaml#equipment-anomaly-response
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Summary

이 WorkflowDefinition는 `equipment.alarm.raised.v1` Event가 들어왔을 때 설비 이상 대응 SOP를 시작하고, Trend/Map evidence, 원인 분석, 정비 가이드, 수동 조치를 BoI evidence로 연결한다.

# Event-Native Flow

```mermaid
flowchart TD
  E["equipment.alarm.raised.v1"] --> S["equipment-anomaly SOP"]
  S --> A1["sop.equipment.request_trend_history"]
  S --> A2["sop.equipment.request_raw_map"]
  S --> A3["sop.equipment.share_cause_analysis"]
  S --> A4["sop.equipment.request_maintenance_guide"]
  S --> M["manual.equipment.corrective_action"]
  A1 --> N1["trend.anomaly.detected.v1"]
  M --> N2["corrective_action.requested.v1"]
```

# Agent Use

BoI Agent는 이 WorkflowDefinition을 근거로 “이 이벤트가 발생하면 뭘 해야 해?” 질문에 Event, SOP Stage, Action, Manual Handoff, Next Event 흐름을 답한다. 연결되지 않은 후속 행동은 추천하지 않는다.

# Related

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
- [Event Contract Guide](/public/boi-wiki-manual/workflows/event-contract-guide.md)
- [Event-Native Workflow Guide](/public/boi-wiki-manual/workflows/event-native-workflow-guide.md)
