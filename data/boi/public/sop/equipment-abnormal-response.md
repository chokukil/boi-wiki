---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/sop
title: 설비 이상 감지·원인 분석·이상 조치 SOP
description: 첨부 SOP 이미지를 AI Native Workflow PoC에서 실행 가능한 public SOP로 정리한 기준 문서
tags: [SOP, EventBroker, BoIWiki, ActionGateway, ManualHandoff, Langflow]
timestamp: 2026-06-16T14:00:00+09:00
boi_id: boi:public:sop:equipment-abnormal-response
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: hybrid
  agent_id: boi-seed-writer-v0.3
acl_policy: acl:public
status: reviewed
source_refs:
  - type: user-provided-sop
    ref: equipment-abnormal-response-sop-image
review:
  reviewer: tf-lead
  reviewed_at: 2026-06-16T14:00:00+09:00
  review_status: reviewed
event_type: equipment.alarm.raised.v1
workflow:
  workflow_key: equipment-anomaly
  stages:
    - id: detect
      name: 이상 감지
      agent: 이상 감지 Agent
      entry_event: equipment.alarm.raised.v1
      next_stage: analyze
      emits_event: root_cause.analysis.requested.v1
      event_types: [equipment.alarm.raised.v1, trend.anomaly.detected.v1]
      source_systems: [VM system monitoring, TAS Agent, Trend alarm, Lot/Wafer 이력, HyVIS]
      evidence_refs: [Trend alarm, Lot/Wafer 이력]
      outputs: [boi/sop-instance, root_cause.analysis.requested.v1]
      failure_modes: [alarm_context_missing, trend_data_unavailable]
      automated_actions:
        - sop.equipment.request_trend_history
        - sop.equipment.request_raw_data
        - langflow.boi.reference_flow
        - sop.equipment.create_root_cause_event
      manual_actions:
        - manual.equipment.confirm_alarm_context
    - id: analyze
      name: 원인 분석
      agent: 원인 분석 Agent
      entry_event: root_cause.analysis.requested.v1
      next_stage: guide
      emits_event: maintenance.guide.requested.v1
      event_types: [root_cause.analysis.requested.v1]
      source_systems: [HyVIS Raw Data, TAS Source Data, 장비 이력]
      evidence_refs: [HyVIS Raw Data, TAS Source Data]
      outputs: [boi/analysis, maintenance.guide.requested.v1]
      failure_modes: [raw_data_unavailable, root_cause_uncertain]
      automated_actions:
        - sop.equipment.request_raw_data
        - sop.equipment.request_maintenance_guide
        - langflow.equipment.stage_analysis
        - sop.equipment.create_maintenance_guide_event
      manual_actions:
        - manual.equipment.review_root_cause
    - id: guide
      name: 장비 보전 가이드
      agent: 보전 가이드 Agent
      entry_event: maintenance.guide.requested.v1
      next_stage: correct
      emits_event: corrective_action.requested.v1
      event_types: [maintenance.guide.requested.v1]
      source_systems: [SOP, Runbook, 장비 이력, Source Data]
      evidence_refs: [SOP, Runbook, 장비 이력]
      outputs: [boi/runbook, corrective_action.requested.v1]
      failure_modes: [runbook_missing, maintenance_action_ambiguous]
      automated_actions:
        - sop.equipment.request_raw_data
        - sop.equipment.request_maintenance_guide
        - langflow.equipment.stage_analysis
        - sop.equipment.create_corrective_action_event
      manual_actions:
        - manual.equipment.review_root_cause
    - id: correct
      name: 이상 조치
      agent: 이상 조치 Agent
      entry_event: corrective_action.requested.v1
      next_stage: complete
      emits_event: null
      event_types: [corrective_action.requested.v1]
      source_systems: [Action Gateway, 담당자 알림, 변경관리 절차]
      evidence_refs: [Action Gateway, 변경관리 절차]
      outputs: [boi/action, manual_handoff, approval_required]
      failure_modes: [approval_missing, owner_unavailable, high_risk_action_blocked]
      automated_actions:
        - sop.equipment.notify_action_owner
        - langflow.equipment.stage_analysis
        - sop.equipment.block_process_progress
        - sop.equipment.change_spec_rule
      manual_actions:
        - manual.equipment.approve_process_hold
        - manual.equipment.approve_spec_rule_change
        - manual.equipment.confirm_maintenance_done
  event_types:
    - equipment.alarm.raised.v1
    - trend.anomaly.detected.v1
    - root_cause.analysis.requested.v1
    - maintenance.guide.requested.v1
    - corrective_action.requested.v1
---

# Summary

이 BoI는 첨부된 설비 이상 대응 SOP를 PoC에서 실제 workflow로 실행하기 위한 Public SOP 문서다. 원본 이미지는 `시스템 활용 업무`, `생성형 AI`, `분석형 AI`, `개발 필요 영역`을 구분하고 있으며, 설비 이상 감지에서 원인 분석, 장비 보전 가이드, 이상 조치로 이어지는 흐름을 보여준다.

# AI Native Workflow 해석

| 단계 | 업무 의미 | Event Type | Agent / Flow | BoI 결과물 | 주요 Action |
|---|---|---|---|---|---|
| 이상 감지 | Alarm 또는 Trend 이상이 발생 | [equipment.alarm.raised.v1](/public/event-types/equipment.alarm.raised.v1.md) | 이상 감지 Agent / [Langflow Reference Flow](/public/actions/langflow/reference-flow.md) | `boi/sop-instance` | [Trend 확인](/public/actions/api/request-trend-history.md), [Raw Data 확인](/public/actions/api/request-raw-data.md), [Langflow 요약](/public/actions/langflow/reference-flow.md) |
| 원인 분석 | 이력과 Trend를 확인해 원인 후보 생성 | [root_cause.analysis.requested.v1](/public/event-types/root_cause.analysis.requested.v1.md) | 원인 분석 Agent | `boi/analysis` | [Raw Data 조회](/public/actions/api/request-raw-data.md), [보전 가이드 요청](/public/actions/api/request-maintenance-guide.md) |
| 장비 보전 가이드 | 장비 이상 가능성에 대해 SOP/Runbook 참조 | [maintenance.guide.requested.v1](/public/event-types/maintenance.guide.requested.v1.md) | 보전 가이드 Agent | `boi/runbook` | [보전 가이드 요청](/public/actions/api/request-maintenance-guide.md), [이상 조치 이벤트 발행](/public/actions/event-broker/create-corrective-action-event.md) |
| 이상 조치 | 조치 담당자 요청 또는 고위험 조치 후보 생성 | [corrective_action.requested.v1](/public/event-types/corrective_action.requested.v1.md) | 이상 조치 Agent | `boi/action` | [담당자 알림](/public/actions/api/notify-action-owner.md), [공정 Hold](/public/actions/api/block-process-progress.md), [Spec 변경](/public/actions/api/change-spec-rule.md) |

# Stage Details

| Stage ID | 개발 필요 Agent | Source Systems | Automated Actions | Manual Actions |
|---|---|---|---|---|
| `detect` | 이상 감지 Agent | VM system monitoring, TAS Agent, Trend alarm, Lot/Wafer 이력, HyVIS | [Trend](/public/actions/api/request-trend-history.md), [Raw](/public/actions/api/request-raw-data.md), [Langflow 요약](/public/actions/langflow/reference-flow.md), [원인 분석 이벤트](/public/actions/event-broker/create-root-cause-event.md) | [Alarm 맥락 확인](/public/actions/manual/confirm-alarm-context.md) |
| `analyze` | 원인 분석 Agent | HyVIS Raw Data, TAS Source Data, 장비 이력 | [Raw](/public/actions/api/request-raw-data.md), [보전 가이드](/public/actions/api/request-maintenance-guide.md), [보전 이벤트](/public/actions/event-broker/create-maintenance-guide-event.md) | [원인 후보 검토](/public/actions/manual/review-root-cause.md) |
| `guide` | 보전 가이드 Agent | SOP, Runbook, 장비 이력, Source Data | [Raw](/public/actions/api/request-raw-data.md), [보전 가이드](/public/actions/api/request-maintenance-guide.md), [조치 이벤트](/public/actions/event-broker/create-corrective-action-event.md) | [원인 후보 검토](/public/actions/manual/review-root-cause.md) |
| `correct` | 이상 조치 Agent | Action Gateway, 담당자 알림, 변경관리 절차 | [담당자 알림](/public/actions/api/notify-action-owner.md), [공정 Hold](/public/actions/api/block-process-progress.md), [Spec 변경](/public/actions/api/change-spec-rule.md) | [공정 Hold 승인](/public/actions/manual/approve-process-hold.md), [Spec 변경 승인](/public/actions/manual/approve-spec-rule-change.md), [정비 완료 확인](/public/actions/manual/confirm-maintenance-done.md) |

# Public Action Specs

- API Action 명세: [API Actions](/public/actions/api/request-trend-history.md)
- Webhook Action 명세: [Webhook Actions](/public/actions/webhook/inbound-external-event.md)
- MCP Action 명세: [MCP Actions](/public/actions/mcp/boi-search-sample.md)
- Langflow Action 명세: [Langflow Reference Flow](/public/actions/langflow/reference-flow.md)
- Manual Action 명세: [Manual Actions](/public/actions/manual/confirm-alarm-context.md)

# Event Broker 원칙

- Event Broker는 모든 내용을 담는 저장소가 아니라 “업무가 발생한 시점”을 발행한다.
- Event payload는 `event_type`, `source_refs`, `payload`, `target.flow_key` 중심으로 가볍게 유지한다.
- 실제 업무 맥락, 판단 근거, Action 후보는 BoI 문서에 축적한다.

# Action Gateway 원칙

- Agent는 임의 URL을 직접 호출하지 않는다.
- Agent는 Action Catalog에 등록된 API/Webhook만 호출한다.
- 사람이 해야 하는 판단, 승인, 현장 조치는 manual action으로 문서화하고 자동 실행하지 않는다.
- 고위험 Action, 예: 공정 진행 금지, Spec/Rule 변경은 대응 manual approval action 없이는 완료 처리하지 않는다.
- PoC에서 고위험 system action은 승인 전 `approval_required` 또는 dry-run 상태로만 기록한다.

# Citations

- 첨부 SOP 이미지: 시스템 활용 업무 / 생성형 AI / 분석형 AI / 개발 필요 영역 구분 사례
- [Public Action Library](/public/actions/overview.md)
