from __future__ import annotations

import asyncio
import json
import os
import signal
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
TOPIC = os.getenv("BOI_EVENTS_TOPIC", "boi.events")
AUDIT_TOPIC = os.getenv("BOI_AUDIT_TOPIC", "boi.audit")
DLQ_TOPIC = os.getenv("BOI_DLQ_TOPIC", "boi.dead-letter")
BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000")
BOI_API_SERVICE_TOKEN = os.getenv("BOI_API_SERVICE_TOKEN", "dev-service-token-change-me")
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100")
ACTION_GATEWAY_SERVICE_TOKEN = os.getenv("ACTION_GATEWAY_SERVICE_TOKEN", BOI_API_SERVICE_TOKEN)
AUTO_ROUTE_EVENTS = os.getenv("AUTO_ROUTE_EVENTS", "true").lower() == "true"

stop_event = asyncio.Event()


def _decode(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def _encode(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


async def emit(producer: AIOKafkaProducer, topic: str, payload: dict[str, Any]) -> None:
    await producer.send_and_wait(topic, payload)


async def write_boi_event_audit(event: dict[str, Any], status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    """Mirror Kafka processing status into BoI Wiki's business-facing Event Stream."""
    url = f"{BOI_API_URL.rstrip('/')}/api/events/audit"
    payload = {"status": status, "event": event, "result": result, "error": error}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, headers={"x-service-token": BOI_API_SERVICE_TOKEN}, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        print(json.dumps({"status": "audit-write-failed", "event_id": event.get("event_id"), "error": repr(exc)}, ensure_ascii=False), flush=True)


async def dispatch_event(event: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an event to all registered connector actions.

    The Event Router does not know or prefer Langflow, BoI Writer, Webhook, API, MCP,
    or future protocols. It only routes the event to Action Gateway, which executes the
    action catalog in a connector-agnostic manner.
    """
    if not AUTO_ROUTE_EVENTS:
        return {"ok": True, "status": "routing_disabled", "results": []}
    employee_id = ((event.get("actor") or {}).get("employee_id") or (event.get("actor") or {}).get("employee_id_hash") or "100001")
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{ACTION_GATEWAY_URL.rstrip('/')}/api/actions/dispatch",
            headers={"x-service-token": ACTION_GATEWAY_SERVICE_TOKEN},
            json={
                "employee_id": employee_id,
                "event": event,
                "payload": event.get("payload") or {},
            },
        )
        resp.raise_for_status()
        return resp.json()


async def enrich_generated_boi(event: dict[str, Any], dispatch_result: dict[str, Any]) -> dict[str, Any]:
    employee_id = ((event.get("actor") or {}).get("employee_id") or (event.get("actor") or {}).get("employee_id_hash") or "100001")
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{BOI_API_URL.rstrip('/')}/api/boi/enrich-from-dispatch",
                headers={"x-service-token": BOI_API_SERVICE_TOKEN},
                json={
                    "employee_id": employee_id,
                    "event": event,
                    "dispatch_result": dispatch_result,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        return {"ok": False, "status": "enrichment_failed", "error": repr(exc)}


async def process_event(event: dict[str, Any], producer: AIOKafkaProducer) -> None:
    event_type = event.get("event_type", "")
    try:
        await write_boi_event_audit(event, "routing")
        dispatch_result = await dispatch_event(event)
        enrichment_result = await enrich_generated_boi(event, dispatch_result)
        result = {"routed_by": "event-router", "dispatch_result": dispatch_result, "enrichment_result": enrichment_result}
        await emit(producer, AUDIT_TOPIC, {"status": "processed", "event_id": event.get("event_id"), "event_type": event_type, "result": result})
        await write_boi_event_audit(event, "processed", result=result)
        print(json.dumps({"status": "processed", "event_id": event.get("event_id"), "event_type": event_type, "connector_count": len(dispatch_result.get("results") or [])}, ensure_ascii=False), flush=True)
    except Exception as exc:
        payload = {"status": "failed", "event": event, "error": repr(exc)}
        await emit(producer, DLQ_TOPIC, payload)
        await write_boi_event_audit(event, "failed", error=repr(exc))
        print(json.dumps(payload, ensure_ascii=False), flush=True)


async def main() -> None:
    consumer = AIOKafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id="boi-event-router",
        value_deserializer=_decode,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, value_serializer=_encode)
    await consumer.start()
    await producer.start()
    print(f"event-router started: topic={TOPIC}, kafka={KAFKA_BOOTSTRAP}, action_gateway={ACTION_GATEWAY_URL}", flush=True)
    try:
        while not stop_event.is_set():
            msg_batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            for _tp, messages in msg_batch.items():
                for msg in messages:
                    await process_event(msg.value, producer)
    finally:
        await consumer.stop()
        await producer.stop()


def request_stop(*_: Any) -> None:
    stop_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    asyncio.run(main())
