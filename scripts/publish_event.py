#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from kafka import KafkaProducer

KST = timezone(timedelta(hours=9))


def now_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a BoI PoC event to Kafka")
    parser.add_argument("event_type", choices=["meeting.closed.v1", "action.created.v1", "report.requested.v1", "promotion.requested.v1", "equipment.alarm.raised.v1", "trend.anomaly.detected.v1", "root_cause.analysis.requested.v1", "maintenance.guide.requested.v1", "corrective_action.requested.v1", "external.webhook.received.v1"])
    parser.add_argument("--employee", default="100001")
    parser.add_argument("--bootstrap", default="localhost:9094")
    parser.add_argument("--topic", default="boi.events")
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    title = args.title or {
        "meeting.closed.v1": "AIX 확산 TF 업무 맥락 자산화 PoC 회의",
        "action.created.v1": "BoI Wiki Web 접근성 확인",
        "report.requested.v1": "업무 맥락 자산화 PoC 주간보고",
        "promotion.requested.v1": "Private BoI Team 승격 요청",
        "equipment.alarm.raised.v1": "설비 Alarm 발생 - SOP Workflow Demo",
        "trend.anomaly.detected.v1": "Trend 이상 감지 - SOP Workflow Demo",
        "root_cause.analysis.requested.v1": "원인 분석 요청 - SOP Workflow Demo",
        "maintenance.guide.requested.v1": "장비 보전 가이드 요청 - SOP Workflow Demo",
        "corrective_action.requested.v1": "이상 조치 요청 - SOP Workflow Demo",
        "external.webhook.received.v1": "외부 Webhook 수신 Demo",
    }[args.event_type]

    event = {
        "event_id": f"evt-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "event_type": args.event_type,
        "event_version": "1",
        "occurred_at": now_iso(),
        "producer": "scripts/publish_event.py",
        "actor": {"type": "human", "employee_id": args.employee, "employee_id_hash": args.employee},
        "visibility_hint": "private",
        "classification_hint": "internal",
        "source_refs": [{"type": "demo", "ref": "scripts/publish_event.py"}],
        "target": {"flow_key": args.event_type.replace(".", "-")},
        "payload": {"title": title, "equipment_id": "EQP-001", "lot_id": "LOT-001", "wafer_id": "WF-001", "alarm_code": "ALM-DEMO", "owner": args.employee},
        "trace_id": f"trace-{uuid.uuid4().hex}",
    }
    producer = KafkaProducer(bootstrap_servers=args.bootstrap, value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"))
    producer.send(args.topic, event)
    producer.flush()
    print(json.dumps(event, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
