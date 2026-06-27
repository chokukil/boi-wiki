#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import ssl
import time
import uuid
from typing import Any

import httpx


def kafka_kwargs() -> dict[str, Any]:
    bootstrap = (
        os.getenv("KAFKA_SMOKE_BOOTSTRAP")
        or os.getenv("KAFKA_EXTERNAL_BOOTSTRAP")
        or os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
    )
    kwargs: dict[str, Any] = {
        "bootstrap_servers": bootstrap,
        "security_protocol": os.getenv("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
    }
    if os.getenv("KAFKA_SASL_MECHANISM"):
        kwargs["sasl_mechanism"] = os.environ["KAFKA_SASL_MECHANISM"]
    if os.getenv("KAFKA_SASL_USERNAME"):
        kwargs["sasl_plain_username"] = os.environ["KAFKA_SASL_USERNAME"]
    if os.getenv("KAFKA_SASL_PASSWORD"):
        kwargs["sasl_plain_password"] = os.environ["KAFKA_SASL_PASSWORD"]
    if os.getenv("KAFKA_SSL_CAFILE"):
        kwargs["ssl_context"] = ssl.create_default_context(cafile=os.environ["KAFKA_SSL_CAFILE"])
    return kwargs


async def check_kafka(*, consume: bool, timeout: float) -> dict[str, Any]:
    from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

    topic = os.getenv("BOI_EVENTS_TOPIC", "boi.events")
    event_id = f"evt-pilot-smoke-{uuid.uuid4().hex[:8]}"
    payload = {
        "event_id": event_id,
        "event_type": "pilot.kafka.smoke.v1",
        "event_version": "1",
        "occurred_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "producer": "check_pilot_external_services",
        "payload": {"smoke": True},
        "trace_id": f"trace-pilot-smoke-{uuid.uuid4().hex[:8]}",
    }
    consumer: AIOKafkaConsumer | None = None
    if consume:
        consumer = AIOKafkaConsumer(
            topic,
            **kafka_kwargs(),
            group_id=f"boi-pilot-smoke-{uuid.uuid4().hex[:8]}",
            auto_offset_reset="latest",
            enable_auto_commit=False,
            value_deserializer=lambda value: json.loads(value.decode("utf-8")),
        )
        await asyncio.wait_for(consumer.start(), timeout=timeout)

    try:
        producer: AIOKafkaProducer | None = None
        try:
            producer = AIOKafkaProducer(
                **kafka_kwargs(),
                value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
                request_timeout_ms=int(timeout * 1000),
            )
            await asyncio.wait_for(producer.start(), timeout=timeout)
            await asyncio.wait_for(producer.send_and_wait(topic, payload), timeout=timeout)
        finally:
            if producer is not None:
                try:
                    await producer.stop()
                except Exception:
                    pass
        result: dict[str, Any] = {"ok": True, "topic": topic, "produced_event_id": event_id, "consumed": False}
        if not consume:
            return result
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            assert consumer is not None
            batch = await consumer.getmany(timeout_ms=500, max_records=20)
            for _tp, messages in batch.items():
                for message in messages:
                    if isinstance(message.value, dict) and message.value.get("event_id") == event_id:
                        result["consumed"] = True
                        return result
        result["ok"] = False
        result["error"] = "produced smoke event was not consumed before timeout"
        return result
    finally:
        if consumer is not None:
            await consumer.stop()


async def check_langflow(*, run_endpoint: str, timeout: float) -> dict[str, Any]:
    base_url = (
        os.getenv("LANGFLOW_SMOKE_URL")
        or os.getenv("LANGFLOW_EXTERNAL_URL")
        or os.getenv("LANGFLOW_URL", "")
    ).rstrip("/")
    if not base_url:
        return {"ok": False, "error": "LANGFLOW_URL is not configured"}
    headers = {}
    api_key = os.getenv("LANGFLOW_API_KEY", "")
    if api_key:
        headers["x-api-key"] = api_key
    async with httpx.AsyncClient(timeout=timeout) as client:
        flows_resp = await client.get(f"{base_url}/api/v1/flows/", headers=headers)
        flows_resp.raise_for_status()
        flows = flows_resp.json()
        result: dict[str, Any] = {
            "ok": True,
            "base_url": base_url,
            "flow_count": len(flows) if isinstance(flows, list) else None,
            "run_checked": False,
        }
        if run_endpoint:
            run_resp = await client.post(
                f"{base_url}/api/v1/run/{run_endpoint}",
                headers=headers,
                json={"input_value": "BoI Pilot smoke", "output_type": "chat", "input_type": "chat"},
            )
            run_resp.raise_for_status()
            result["run_checked"] = True
            result["run_endpoint"] = run_endpoint
        return result


async def main() -> int:
    parser = argparse.ArgumentParser(description="Check BoI Wiki pilot external Kafka/Langflow dependencies.")
    parser.add_argument("--kafka", action="store_true", help="Produce a smoke event to BOI_EVENTS_TOPIC.")
    parser.add_argument("--consume", action="store_true", help="Also try to consume the produced smoke event.")
    parser.add_argument("--langflow", action="store_true", help="List Langflow flows.")
    parser.add_argument("--run-langflow-endpoint", default="", help="Optionally run a Langflow endpoint.")
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    output: dict[str, Any] = {"ok": True, "checks": {}}
    if args.kafka:
        try:
            output["checks"]["kafka"] = await check_kafka(consume=args.consume, timeout=args.timeout)
        except Exception as exc:
            output["checks"]["kafka"] = {"ok": False, "error": repr(exc)}
    if args.langflow:
        try:
            output["checks"]["langflow"] = await check_langflow(run_endpoint=args.run_langflow_endpoint, timeout=args.timeout)
        except Exception as exc:
            output["checks"]["langflow"] = {"ok": False, "error": repr(exc)}
    output["ok"] = all(check.get("ok") for check in output["checks"].values())
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
