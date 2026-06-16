# BoI Wiki PoC Evidence Summary

- Collected at: `2026-06-16T16:14:25+00:00`
- Git commit: `0bda590`
- LLM endpoint: `http://mangugil.iptime.org:1236/v1`
- LLM model: `google/gemma-4-26b-a4b-qat`
- Kafka topic: `boi.events`
- Event catalog count: `10`
- Action catalog count: `15`
- Event log count: `60`
- Action log count: `48`
- Accessible BoI docs: `10`
- Private BoI docs in list: `4`
- Materialized BoI actions in log: `12`
- Approval-required action records in log: `6`

## Demo Run

- First event type: `equipment.alarm.raised.v1`
- Equipment: `ETCH-VM-01`
- Trace ID: `trace-aa400a08a2b442efa3df7ccd87c9ce86`

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
- Response: 제시해주신 PoC 실행 결과(PoC evidence run)를 바탕으로, 설계된 AI Native Workflow의 핵심 가치를 관통하는 검증 요약 문장입니다.

**[BoI Wiki PoC 검증 결과 요약]**

"본 PoC는 파편화된 업무 맥락의 자산화를 기반으로 Event Broker를 통한 자동화 트리거와 Action Gateway를 활용한 고위험 액션 통제 메커니즘을 구현하였으며, 데이터 신뢰도 및 재사용성 기준에 따른 Private BoI의 Team BoI 승격 프로세스가 AI Native 워크플로우로서 유효함을 입증하였습니다."

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
