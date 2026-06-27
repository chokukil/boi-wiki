from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import ssl
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_MODE = os.getenv("KAFKA_MODE", "local").strip().lower()
KAFKA_SECURITY_PROTOCOL = os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT")
KAFKA_SASL_MECHANISM = os.getenv("KAFKA_SASL_MECHANISM", "")
KAFKA_SASL_USERNAME = os.getenv("KAFKA_SASL_USERNAME", "")
KAFKA_SASL_PASSWORD = os.getenv("KAFKA_SASL_PASSWORD", "")
KAFKA_SSL_CAFILE = os.getenv("KAFKA_SSL_CAFILE", "")
KAFKA_CLIENT_LOG_LEVEL = os.getenv("EVENT_ROUTER_AIOKAFKA_LOG_LEVEL", "CRITICAL").upper()
TOPIC = os.getenv("BOI_EVENTS_TOPIC", "boi.events")
AUDIT_TOPIC = os.getenv("BOI_AUDIT_TOPIC", "boi.audit")
DLQ_TOPIC = os.getenv("BOI_DLQ_TOPIC", "boi.dead-letter")
GROUP_ID = os.getenv("EVENT_ROUTER_GROUP_ID", "boi-event-router")
AUTO_OFFSET_RESET = os.getenv("EVENT_ROUTER_AUTO_OFFSET_RESET", "earliest")
BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000")
BOI_API_SERVICE_TOKEN = os.getenv("BOI_API_SERVICE_TOKEN", "dev-service-token-change-me")
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100")
ACTION_GATEWAY_SERVICE_TOKEN = os.getenv("ACTION_GATEWAY_SERVICE_TOKEN", BOI_API_SERVICE_TOKEN)
AUTO_ROUTE_EVENTS = os.getenv("AUTO_ROUTE_EVENTS", "true").lower() == "true"

stop_event = asyncio.Event()

_kafka_log_level = getattr(logging, KAFKA_CLIENT_LOG_LEVEL, logging.ERROR)
logging.getLogger("aiokafka").setLevel(_kafka_log_level)
logging.getLogger("kafka").setLevel(_kafka_log_level)
if _kafka_log_level >= logging.CRITICAL:
    logging.disable(logging.ERROR)
elif _kafka_log_level >= logging.ERROR:
    logging.disable(logging.WARNING)


def kafka_client_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "bootstrap_servers": KAFKA_BOOTSTRAP,
        "security_protocol": KAFKA_SECURITY_PROTOCOL,
    }
    if KAFKA_SASL_MECHANISM:
        kwargs["sasl_mechanism"] = KAFKA_SASL_MECHANISM
    if KAFKA_SASL_USERNAME:
        kwargs["sasl_plain_username"] = KAFKA_SASL_USERNAME
    if KAFKA_SASL_PASSWORD:
        kwargs["sasl_plain_password"] = KAFKA_SASL_PASSWORD
    if KAFKA_SSL_CAFILE:
        kwargs["ssl_context"] = ssl.create_default_context(cafile=KAFKA_SSL_CAFILE)
    return kwargs


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


AUDIT_HTTP_TIMEOUT_SECONDS = _env_float("EVENT_ROUTER_AUDIT_TIMEOUT_SECONDS", 10)
DISPATCH_HTTP_TIMEOUT_SECONDS = _env_float("EVENT_ROUTER_DISPATCH_TIMEOUT_SECONDS", 300)
ENRICH_HTTP_TIMEOUT_SECONDS = _env_float("EVENT_ROUTER_ENRICH_TIMEOUT_SECONDS", 60)
AUDIT_TEXT_LIMIT = int(_env_float("EVENT_ROUTER_AUDIT_TEXT_LIMIT", 600))
CONSUMER_SESSION_TIMEOUT_MS = int(_env_float("EVENT_ROUTER_CONSUMER_SESSION_TIMEOUT_MS", 60_000))
CONSUMER_HEARTBEAT_INTERVAL_MS = int(_env_float("EVENT_ROUTER_CONSUMER_HEARTBEAT_INTERVAL_MS", 10_000))
CONSUMER_MAX_POLL_INTERVAL_MS = int(_env_float("EVENT_ROUTER_CONSUMER_MAX_POLL_INTERVAL_MS", 900_000))
STARTUP_DELAY_SECONDS = _env_float("EVENT_ROUTER_STARTUP_DELAY_SECONDS", 0)
TOPIC_READY_TIMEOUT_SECONDS = _env_float("EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS", 60)
TOPIC_READY_INTERVAL_SECONDS = _env_float("EVENT_ROUTER_TOPIC_READY_INTERVAL_SECONDS", 2)
POST_TOPIC_READY_DELAY_SECONDS = _env_float("EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS", 0)


def _decode(value: bytes) -> dict[str, Any]:
    return json.loads(value.decode("utf-8"))


def _encode(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def _short_text(value: Any, limit: int = AUDIT_TEXT_LIMIT) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip() + " ... [truncated for event audit; use action raw log for full result]"


def compact_action_result_for_audit(item: dict[str, Any]) -> dict[str, Any]:
    result = item.get("result") if isinstance(item.get("result"), dict) else {}
    simulation_agent = result.get("simulation_agent") if isinstance(result.get("simulation_agent"), dict) else {}
    compact_result: dict[str, Any] = {}
    for key in (
        "ok",
        "status",
        "request_id",
        "action_key",
        "connector_kind",
        "boi_id",
        "boi_uri",
        "flow_id",
        "flow_name",
        "simulation",
        "simulation_label",
        "real_system_status",
        "simulated_system",
        "retrieval_rounds",
        "coverage_score",
        "langflow_renderer_status",
    ):
        if key in result:
            compact_result[key] = _short_text(result[key])
    if "message" in result:
        compact_result["message"] = _short_text(result["message"])
    if simulation_agent:
        coverage = simulation_agent.get("coverage_report") if isinstance(simulation_agent.get("coverage_report"), dict) else {}
        context_pack = simulation_agent.get("context_pack") if isinstance(simulation_agent.get("context_pack"), dict) else {}
        compact_result["simulation_agent"] = {
            "coverage_score": coverage.get("coverage_score"),
            "missing_context": coverage.get("missing_context") or [],
            "retrieval_rounds": (simulation_agent.get("agent") or {}).get("retrieval_rounds")
            if isinstance(simulation_agent.get("agent"), dict)
            else None,
            "used_docs": [
                {
                    "role": doc.get("role"),
                    "boi_id": doc.get("boi_id"),
                    "uri": doc.get("uri"),
                    "title": doc.get("title"),
                }
                for doc in (context_pack.get("documents") or [])[:12]
                if isinstance(doc, dict)
            ],
            "evidence_packets": [
                {
                    "id": packet.get("id"),
                    "label": packet.get("label"),
                    "provenance": packet.get("provenance"),
                    "source_action": packet.get("source_action"),
                }
                for packet in (simulation_agent.get("evidence_packets") or [])[:12]
                if isinstance(packet, dict)
            ],
        }
    compact: dict[str, Any] = {}
    for key in (
        "action_key",
        "type",
        "connector_kind",
        "status",
        "request_id",
        "doc_ref",
        "boi_id",
        "boi_uri",
        "event_id",
        "event_type",
        "simulation",
        "simulation_label",
        "real_system_status",
        "simulated_system",
        "retrieval_rounds",
        "coverage_score",
    ):
        value = item.get(key)
        if value is not None:
            compact[key] = _short_text(value)
    if compact_result:
        compact["result"] = compact_result
    return compact


def compact_dispatch_result_for_audit(dispatch_result: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key in ("ok", "status", "handled_by", "boi_id", "boi_uri", "request_id"):
        if key in dispatch_result:
            compact[key] = _short_text(dispatch_result[key])
    results = dispatch_result.get("results")
    if isinstance(results, list):
        compact["results"] = [compact_action_result_for_audit(item) for item in results if isinstance(item, dict)]
        compact["result_count"] = len(results)
    return compact


async def emit(producer: AIOKafkaProducer, topic: str, payload: dict[str, Any]) -> None:
    await producer.send_and_wait(topic, payload)


async def wait_for_topic_readiness() -> None:
    try:
        from aiokafka.admin import AIOKafkaAdminClient
    except Exception as exc:  # pragma: no cover - dependency is present in the container image
        print(json.dumps({"status": "topic-readiness-unavailable", "error": repr(exc)}, ensure_ascii=False), flush=True)
        return
    deadline = asyncio.get_running_loop().time() + max(TOPIC_READY_TIMEOUT_SECONDS, 0)
    last_error = ""
    while True:
        admin = AIOKafkaAdminClient(**kafka_client_kwargs())
        try:
            await admin.start()
            topics = await admin.list_topics()
            if TOPIC in topics:
                print(json.dumps({"status": "topic-ready", "topic": TOPIC, "mode": KAFKA_MODE}, ensure_ascii=False), flush=True)
                return
            last_error = f"topic {TOPIC} not listed"
        except Exception as exc:
            last_error = repr(exc)
        finally:
            try:
                await admin.close()
            except Exception:
                pass
        if asyncio.get_running_loop().time() >= deadline:
            raise RuntimeError(f"Kafka topic readiness timed out for {TOPIC}: {last_error}")
        print(
            json.dumps(
                {
                    "status": "topic-wait",
                    "topic": TOPIC,
                    "mode": KAFKA_MODE,
                    "error": last_error,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        await asyncio.sleep(max(TOPIC_READY_INTERVAL_SECONDS, 0.2))


async def write_boi_event_audit(event: dict[str, Any], status: str, result: dict[str, Any] | None = None, error: str | None = None) -> None:
    """Mirror Kafka processing status into BoI Wiki's business-facing Event Stream."""
    url = f"{BOI_API_URL.rstrip('/')}/api/events/audit"
    payload = {"status": status, "event": event, "result": result, "error": error}
    try:
        async with httpx.AsyncClient(timeout=AUDIT_HTTP_TIMEOUT_SECONDS) as client:
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
    async with httpx.AsyncClient(timeout=DISPATCH_HTTP_TIMEOUT_SECONDS) as client:
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
        async with httpx.AsyncClient(timeout=ENRICH_HTTP_TIMEOUT_SECONDS) as client:
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
        result = {
            "routed_by": "event-router",
            "dispatch_result": compact_dispatch_result_for_audit(dispatch_result),
            "enrichment_result": enrichment_result,
        }
        await emit(producer, AUDIT_TOPIC, {"status": "processed", "event_id": event.get("event_id"), "event_type": event_type, "result": result})
        await write_boi_event_audit(event, "processed", result=result)
        print(json.dumps({"status": "processed", "event_id": event.get("event_id"), "event_type": event_type, "connector_count": len(dispatch_result.get("results") or [])}, ensure_ascii=False), flush=True)
    except Exception as exc:
        payload = {"status": "failed", "event": event, "error": repr(exc)}
        await emit(producer, DLQ_TOPIC, payload)
        await write_boi_event_audit(event, "failed", error=repr(exc))
        print(json.dumps(payload, ensure_ascii=False), flush=True)


async def main() -> None:
    if KAFKA_MODE == "disabled":
        print("event-router disabled: KAFKA_MODE=disabled", flush=True)
        return
    if STARTUP_DELAY_SECONDS > 0:
        print(
            json.dumps(
                {
                    "status": "startup-wait",
                    "delay_seconds": STARTUP_DELAY_SECONDS,
                    "reason": "waiting for Kafka topic readiness",
                    "mode": KAFKA_MODE,
                    "topic": TOPIC,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        await asyncio.sleep(STARTUP_DELAY_SECONDS)
    await wait_for_topic_readiness()
    if POST_TOPIC_READY_DELAY_SECONDS > 0:
        print(
            json.dumps(
                {
                    "status": "post-topic-ready-wait",
                    "delay_seconds": POST_TOPIC_READY_DELAY_SECONDS,
                    "reason": "waiting for Kafka consumer group coordinator readiness",
                    "mode": KAFKA_MODE,
                    "topic": TOPIC,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        await asyncio.sleep(POST_TOPIC_READY_DELAY_SECONDS)
    consumer = AIOKafkaConsumer(
        TOPIC,
        **kafka_client_kwargs(),
        group_id=GROUP_ID,
        value_deserializer=_decode,
        enable_auto_commit=False,
        auto_offset_reset=AUTO_OFFSET_RESET,
        session_timeout_ms=CONSUMER_SESSION_TIMEOUT_MS,
        heartbeat_interval_ms=CONSUMER_HEARTBEAT_INTERVAL_MS,
        max_poll_interval_ms=CONSUMER_MAX_POLL_INTERVAL_MS,
    )
    producer = AIOKafkaProducer(**kafka_client_kwargs(), value_serializer=_encode)
    await consumer.start()
    await producer.start()
    print(f"event-router started: mode={KAFKA_MODE}, topic={TOPIC}, kafka={KAFKA_BOOTSTRAP}, action_gateway={ACTION_GATEWAY_URL}", flush=True)
    try:
        while not stop_event.is_set():
            msg_batch = await consumer.getmany(timeout_ms=1000, max_records=10)
            for _tp, messages in msg_batch.items():
                for msg in messages:
                    await process_event(msg.value, producer)
                    await consumer.commit()
    finally:
        await consumer.stop()
        await producer.stop()


def request_stop(*_: Any) -> None:
    stop_event.set()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    asyncio.run(main())
