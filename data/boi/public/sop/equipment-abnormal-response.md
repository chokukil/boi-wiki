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
event_type: equipment.alarm.raised.v1
workflow:
  workflow_key: equipment-anomaly
  stages:
    - id: detect
      name: 이상 감지
      agent: 이상 감지 Agent
      event_types: [equipment.alarm.raised.v1, trend.anomaly.detected.v1]
      source_systems: [VM system monitoring, TAS Agent, Trend alarm, Lot/Wafer 이력, HyVIS]
      automated_actions:
        - sop.equipment.request_trend_history
        - sop.equipment.request_raw_data
        - sop.equipment.create_root_cause_event
      manual_actions:
        - manual.equipment.confirm_alarm_context
    - id: analyze
      name: 원인 분석
      agent: 원인 분석 Agent
      event_types: [root_cause.analysis.requested.v1]
      source_systems: [HyVIS Raw Data, TAS Source Data, 장비 이력]
      automated_actions:
        - sop.equipment.request_raw_data
        - sop.equipment.request_maintenance_guide
        - sop.equipment.create_maintenance_guide_event
      manual_actions:
        - manual.equipment.review_root_cause
    - id: guide
      name: 장비 보전 가이드
      agent: 보전 가이드 Agent
      event_types: [maintenance.guide.requested.v1]
      source_systems: [SOP, Runbook, 장비 이력, Source Data]
      automated_actions:
        - sop.equipment.request_raw_data
        - sop.equipment.request_maintenance_guide
        - sop.equipment.create_corrective_action_event
      manual_actions:
        - manual.equipment.review_root_cause
    - id: correct
      name: 이상 조치
      agent: 이상 조치 Agent
      event_types: [corrective_action.requested.v1]
      source_systems: [Action Gateway, 담당자 알림, 변경관리 절차]
      automated_actions:
        - sop.equipment.notify_action_owner
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
| 이상 감지 | Alarm 또는 Trend 이상이 발생 | `equipment.alarm.raised.v1` | 이상 감지 Agent | `boi/sop-instance` | Trend/Raw Data 확인 |
| 원인 분석 | 이력과 Trend를 확인해 원인 후보 생성 | `root_cause.analysis.requested.v1` | 원인 분석 Agent | `boi/analysis` | Raw/Source Data 조회 |
| 장비 보전 가이드 | 장비 이상 가능성에 대해 SOP/Runbook 참조 | `maintenance.guide.requested.v1` | 보전 가이드 Agent | `boi/runbook` | 장비 이력/가이드 조회 |
| 이상 조치 | 조치 담당자 요청 또는 고위험 조치 후보 생성 | `corrective_action.requested.v1` | 이상 조치 Agent | `boi/action` | 알림, 공정 Hold, Spec/Rule 변경 후보 |

# Stage Details

| Stage ID | 개발 필요 Agent | Source Systems | Automated Actions | Manual Actions |
|---|---|---|---|---|
| `detect` | 이상 감지 Agent | VM system monitoring, TAS Agent, Trend alarm, Lot/Wafer 이력, HyVIS | `sop.equipment.request_trend_history`, `sop.equipment.request_raw_data`, `sop.equipment.create_root_cause_event` | `manual.equipment.confirm_alarm_context` |
| `analyze` | 원인 분석 Agent | HyVIS Raw Data, TAS Source Data, 장비 이력 | `sop.equipment.request_raw_data`, `sop.equipment.request_maintenance_guide`, `sop.equipment.create_maintenance_guide_event` | `manual.equipment.review_root_cause` |
| `guide` | 보전 가이드 Agent | SOP, Runbook, 장비 이력, Source Data | `sop.equipment.request_raw_data`, `sop.equipment.request_maintenance_guide`, `sop.equipment.create_corrective_action_event` | `manual.equipment.review_root_cause` |
| `correct` | 이상 조치 Agent | Action Gateway, 담당자 알림, 변경관리 절차 | `sop.equipment.notify_action_owner`, `sop.equipment.block_process_progress`, `sop.equipment.change_spec_rule` | `manual.equipment.approve_process_hold`, `manual.equipment.approve_spec_rule_change`, `manual.equipment.confirm_maintenance_done` |

# Public Action Specs

- API Action 명세: `public/actions/api`
- Webhook Action 명세: `public/actions/webhook`
- MCP Action 명세: `public/actions/mcp`
- Langflow Action 명세: `public/actions/langflow`
- Manual Action 명세: `public/actions/manual`

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

# References

- 첨부 SOP 이미지: 시스템 활용 업무 / 생성형 AI / 분석형 AI / 개발 필요 영역 구분 사례
