# BoI Wiki PoC Evidence Summary

- Collected at: `2026-06-17T16:24:13+00:00`
- Git commit: `3dd82b8`
- LLM endpoint: `http://mangugil.iptime.org:1236/v1`
- LLM model: `google/gemma-4-26b-a4b-qat`
- Kafka topic: `boi.events`
- Event catalog count: `10`
- Action catalog count: `21`
- Event log count: `144`
- Action log count: `122`
- Accessible BoI docs: `95`
- Private BoI docs in list: `58`
- Materialized BoI actions in log: `29`
- Approval-required action records in log: `14`

## Demo Run

- First event type: `equipment.alarm.raised.v1`
- Equipment: `ETCH-VM-01`
- Trace ID: `trace-266e116fb0fd4c78928016893f4a2eb1`

## Kafka Topics

```text
__consumer_offsets
boi.audit
boi.dead-letter
boi.events
```

## Langflow Smoke

- Flow: `BoI Reference Flow (15)`
- Flow ID: `3aba3309-89a8-4171-a153-00db6b16dcba`
- Response: **[Private BoI 실행 요약: PoC 검증 결과]**

"본 PoC는 업무 맥락의 자산화를 기반으로 Event Broker와 Action Gateway를 통한 고위험 액션 통제 체계를 구축함으로써, Private BoI가 Team BoI로 승격되기 위한 핵심 운영 요건 및 워크플로우 안정성을 성공적으로 검증하였습니다."

## Event-to-Langflow Action

- Trace ID: `trace-492cf5507241492abd6a7160ad14d1d5`
- Event Type: `equipment.alarm.raised.v1`
- Status: `langflow_invoked`
- Flow: `BoI Reference Flow (15)`
- Flow ID: `3aba3309-89a8-4171-a153-00db6b16dcba`
- Message excerpt: SK하이닉스 BoI Wiki PoC의 AI Native Workflow 설계자로서, 제공된 Event 데이터를 분석하여 작성한 **Private BoI(Business Operations Intelligence) 초안 실행 요약**입니다.

---

# [Private BoI 초안] Response Chain 이상 발생에 따른 대응 및 지식 자산화
**대상 장비:** ETCH-VM-01 | **관련 Trace ID:** `trace-492cf5507241492a

## Latest Actions

- `invoked` / `sop.equipment.request_raw_data` / risk=`low`
- `invoked` / `sop.equipment.request_trend_history` / risk=`low`
- `materialized` / `boi.materialize_event` / risk=`low`
- `approval_required` / `sop.equipment.change_spec_rule` / risk=`high`
- `approval_required` / `sop.equipment.block_process_progress` / risk=`high`
- `invoked` / `sop.equipment.notify_action_owner` / risk=`medium`
- `materialized` / `boi.materialize_event` / risk=`low`
- `event_published` / `sop.equipment.create_corrective_action_event` / risk=`medium`
- `invoked` / `sop.equipment.request_raw_data` / risk=`low`
- `invoked` / `sop.equipment.request_maintenance_guide` / risk=`medium`
- `materialized` / `boi.materialize_event` / risk=`low`
- `event_published` / `sop.equipment.create_maintenance_guide_event` / risk=`medium`

## Latest Events

- `handled` / `equipment.alarm.raised.v1` / `Response Chain 이상 Alarm 발생`
- `handling` / `equipment.alarm.raised.v1` / `Response Chain 이상 Alarm 발생`
- `routing` / `equipment.alarm.raised.v1` / `Response Chain 이상 Alarm 발생`
- `published` / `equipment.alarm.raised.v1` / `Response Chain 이상 Alarm 발생`
- `processed` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `handled` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `handling` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `routing` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `processed` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `published` / `corrective_action.requested.v1` / `이상 조치 요청 - ETCH-VM-01`
- `handled` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
- `handling` / `maintenance.guide.requested.v1` / `장비 보전 가이드 요청 - ETCH-VM-01`
