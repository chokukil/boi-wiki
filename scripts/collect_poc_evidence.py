#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = ROOT / "artifacts" / "boi-poc"
DEFAULT_DOCKER_EXE = "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_json(client: httpx.Client, url: str) -> dict[str, Any]:
    response = client.get(url)
    response.raise_for_status()
    return response.json()


def post_json(client: httpx.Client, url: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    response = client.post(url, json=payload or {})
    response.raise_for_status()
    return response.json()


def run_command(args: list[str], cwd: Path | None = None) -> dict[str, Any]:
    result = subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True, check=False)
    return {
        "command": args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def latest_boi_reference_flow(flows: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [flow for flow in flows if str(flow.get("name", "")).startswith("BoI Reference Flow")]
    if not candidates:
        return None
    return sorted(candidates, key=lambda flow: flow.get("updated_at") or "")[-1]


def langflow_smoke(client: httpx.Client, langflow_url: str) -> dict[str, Any]:
    token_response = get_json(client, f"{langflow_url}/api/v1/auto_login")
    token = token_response["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    flows_response = client.get(f"{langflow_url}/api/v1/flows/", headers=headers)
    flows_response.raise_for_status()
    flow = latest_boi_reference_flow(flows_response.json())
    if not flow:
        return {"ok": False, "reason": "BoI Reference Flow is not imported"}

    payload = {
        "input_value": "PoC evidence run. 한국어 한 문장으로 BoI Wiki PoC 검증 결과를 요약해줘.",
        "input_type": "chat",
        "output_type": "chat",
    }
    run_response = client.post(f"{langflow_url}/api/v1/run/{flow['id']}", headers=headers, json=payload)
    run_response.raise_for_status()
    return {
        "ok": True,
        "flow": {
            "id": flow.get("id"),
            "name": flow.get("name"),
            "endpoint_name": flow.get("endpoint_name"),
            "updated_at": flow.get("updated_at"),
        },
        "run": run_response.json(),
    }


def extract_langflow_message(smoke: dict[str, Any]) -> str:
    try:
        outputs = smoke["run"]["outputs"][0]["outputs"][0]
        return outputs["outputs"]["message"]["message"]
    except Exception:
        return ""


def summarize(evidence: dict[str, Any]) -> str:
    runtime = evidence["runtime_config"]
    event_types = evidence["event_types"].get("items", [])
    actions = evidence["action_catalog"].get("items", [])
    events = evidence["events_log"].get("items", [])
    action_logs = evidence["action_logs"].get("items", [])
    boi_docs = evidence["boi_docs"].get("items", [])
    private_docs = [doc for doc in boi_docs if doc.get("visibility") == "private"]
    approval_required = [log for log in action_logs if log.get("status") == "approval_required"]
    materialized = [log for log in action_logs if log.get("status") == "materialized"]
    langflow_message = extract_langflow_message(evidence.get("langflow_smoke", {}))

    lines = [
        "# BoI Wiki PoC Evidence Summary",
        "",
        f"- Collected at: `{evidence['collected_at']}`",
        f"- Git commit: `{evidence.get('git_commit', '').strip()}`",
        f"- LLM endpoint: `{runtime['llm']['base_url']}`",
        f"- LLM model: `{runtime['llm']['model']}`",
        f"- Kafka topic: `{runtime['event_broker']['topic']}`",
        f"- Event catalog count: `{len(event_types)}`",
        f"- Action catalog count: `{len(actions)}`",
        f"- Event log count: `{evidence['events_log'].get('count')}`",
        f"- Action log count: `{evidence['action_logs'].get('count')}`",
        f"- Accessible BoI docs: `{evidence['boi_docs'].get('count')}`",
        f"- Private BoI docs in list: `{len(private_docs)}`",
        f"- Materialized BoI actions in log: `{len(materialized)}`",
        f"- Approval-required action records in log: `{len(approval_required)}`",
        "",
        "## Demo Run",
        "",
        f"- First event type: `{evidence['demo_event']['event']['event_type']}`",
        f"- Equipment: `{evidence['demo_event']['event']['payload']['equipment_id']}`",
        f"- Trace ID: `{evidence['demo_event']['event']['trace_id']}`",
        "",
        "## Kafka Topics",
        "",
        "```text",
        evidence.get("kafka_topics", {}).get("stdout", "").strip(),
        "```",
        "",
        "## Langflow Smoke",
        "",
        f"- Flow: `{evidence.get('langflow_smoke', {}).get('flow', {}).get('name', '')}`",
        f"- Flow ID: `{evidence.get('langflow_smoke', {}).get('flow', {}).get('id', '')}`",
        f"- Response: {langflow_message or '(no message extracted)'}",
        "",
        "## Latest Actions",
        "",
    ]
    for log in action_logs[:12]:
        lines.append(f"- `{log.get('status')}` / `{log.get('action_key')}` / risk=`{log.get('risk_level')}`")
    lines.extend(["", "## Latest Events", ""])
    for item in events[:12]:
        lines.append(f"- `{item.get('status')}` / `{item.get('event_type')}` / `{item.get('payload_title')}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect executable BoI Wiki PoC evidence for documents and slides.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--boi-api-url", default="http://localhost:8000")
    parser.add_argument("--action-gateway-url", default="http://localhost:8100")
    parser.add_argument("--langflow-url", default="http://localhost:7860")
    parser.add_argument("--docker-exe", default=DEFAULT_DOCKER_EXE)
    parser.add_argument("--trigger-demo", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--wait-seconds", type=float, default=8.0)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    boi_api_url = args.boi_api_url.rstrip("/")
    action_gateway_url = args.action_gateway_url.rstrip("/")
    langflow_url = args.langflow_url.rstrip("/")

    with httpx.Client(timeout=90) as client:
        before_actions = get_json(client, f"{action_gateway_url}/api/actions/logs")
        demo_event: dict[str, Any] | None = None
        if args.trigger_demo:
            demo_event = post_json(
                client,
                f"{boi_api_url}/api/workflows/demo/equipment-anomaly/start?employee_id=100001",
                {
                    "equipment_id": "ETCH-VM-01",
                    "alarm_code": "RESPONSE_CHAIN_ABNORMAL",
                    "title": "Response Chain 이상 Alarm 발생",
                },
            )
            target_action_count = int(before_actions.get("count", 0)) + 16
            deadline = time.time() + max(args.wait_seconds, 1.0)
            while time.time() < deadline:
                current = get_json(client, f"{action_gateway_url}/api/actions/logs")
                if int(current.get("count", 0)) >= target_action_count:
                    break
                time.sleep(0.5)

        evidence = {
            "collected_at": utc_now(),
            "git_commit": run_command(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT)["stdout"],
            "health": {
                "boi_api": get_json(client, f"{boi_api_url}/health"),
                "action_gateway": get_json(client, f"{action_gateway_url}/health"),
            },
            "runtime_config": get_json(client, f"{boi_api_url}/api/runtime/config"),
            "demo_event": demo_event,
            "event_types": get_json(client, f"{boi_api_url}/api/event-types"),
            "action_catalog": get_json(client, f"{boi_api_url}/api/actions/catalog"),
            "events_log": get_json(client, f"{boi_api_url}/api/events/log"),
            "action_logs": get_json(client, f"{action_gateway_url}/api/actions/logs"),
            "boi_docs": get_json(client, f"{boi_api_url}/api/boi?employee_id=100001"),
            "langflow_smoke": langflow_smoke(client, langflow_url),
            "kafka_topics": run_command(
                [
                    args.docker_exe,
                    "exec",
                    "boi-kafka",
                    "/opt/kafka/bin/kafka-topics.sh",
                    "--bootstrap-server",
                    "kafka:9092",
                    "--list",
                ]
            ),
        }

    json_path = out_dir / "evidence.json"
    summary_path = out_dir / "evidence-summary.md"
    json_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_path.write_text(summarize(evidence), encoding="utf-8")

    print(json.dumps({"ok": True, "json": str(json_path), "summary": str(summary_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
