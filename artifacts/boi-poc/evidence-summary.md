# BoI Wiki PoC Evidence Summary

- Collected at: `2026-06-16T16:29:24+00:00`
- Git commit: `3932232`
- LLM endpoint: `http://mangugil.iptime.org:1236/v1`
- LLM model: `google/gemma-4-26b-a4b-qat`
- Kafka topic: `boi.events`
- Event catalog count: `10`
- Action catalog count: `15`
- Event log count: `80`
- Action log count: `64`
- Accessible BoI docs: `14`
- Private BoI docs in list: `8`
- Materialized BoI actions in log: `16`
- Approval-required action records in log: `8`

## Demo Run

- First event type: `equipment.alarm.raised.v1`
- Equipment: `ETCH-VM-01`
- Trace ID: `trace-248ae94e90bc4f0a9221e2cc28eb2106`

## Kafka Topics

```text
__consumer_offsets
boi.audit
boi.dead-letter
boi.events
```

## Langflow Smoke

- Flow: `BoI Reference Flow (2)`
- Flow ID: `15b0199d-583a-4b2e-b692-3ec1744a7c75`
- Response: 본 PoC는 **Event Broker**와 **Action Gateway**를 기반으로 업무 맥락을 자산화하고, 고위험 액션에 대한 승인 통제 및 Private BoI의 Team BoI 승격 기준을 검증함으로써 AI Native Workflow의 실효성과 운영 안정성을 입증하였습니다.

## Latest Actions

- `approval_required` / `sop.equipment.change_spec_rule` / risk=`high`
- `approval_required` / `sop.equipment.block_process_progress` / risk=`high`
- `dry_run` / `sop.equipment.notify_action_owner` / risk=`medium`
- `materialized` / `boi.materialize_event` / risk=`low`
- `event_published` / `sop.equipment.create_corrective_action_event` / risk=`medium`
- `dry_run` / `sop.equipment.request_raw_data` / risk=`low`
- `dry_run` / `sop.equipment.request_maintenance_guide` / risk=`medium`
- `materialized` / `boi.materialize_event` / risk=`low`
- `event_published` / `sop.equipment.create_maintenance_guide_event` / risk=`medium`
- `dry_run` / `sop.equipment.request_raw_data` / risk=`low`
- `dry_run` / `sop.equipment.request_trend_history` / risk=`low`
- `materialized` / `boi.materialize_event` / risk=`low`

## Latest Events

- `processed` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `handled` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `handling` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `routing` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `processed` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `published` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `handled` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `handling` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `routing` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `processed` / `root_cause.analysis.requested.v1` / `원인 분석 요청 - ETCH-VM-01`
- `published` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `handled` / `root_cause.analysis.requested.v1` / `원인 분석 요청 - ETCH-VM-01`
