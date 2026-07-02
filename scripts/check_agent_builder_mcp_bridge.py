#!/usr/bin/env python3
"""Smoke Agent Builder and Evidence Sandbox through the MCP bridge."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any
from urllib import error, request


def _load_service_token(env_files: list[str], explicit: str) -> str:
    if explicit:
        return explicit
    for env_file in env_files:
        path = Path(env_file)
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key == "SERVICE_TOKEN" and value.strip():
                return value.strip().strip("\"'")
    return ""


def _bridge_call(base_url: str, service_token: str, tool: str, arguments: dict[str, Any], timeout: float) -> tuple[dict[str, Any], int]:
    payload = {
        "server": {"name": "boi-wiki-mcp"},
        "tool": tool,
        "arguments": arguments,
    }
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-service-token": service_token,
    }
    req = request.Request(f"{base_url.rstrip('/')}/api/mcp/call", data=data, headers=headers, method="POST")
    started = time.time()
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            status = resp.status
    except error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}
        status = exc.code
    elapsed_ms = round((time.time() - started) * 1000)
    if status != 200:
        raise AssertionError(f"{tool} returned HTTP {status}: {body}")
    if body.get("ok") is not True or not isinstance(body.get("result"), dict) or body["result"].get("ok") is not True:
        raise AssertionError(f"{tool} did not return ok=true: {body}")
    return body, elapsed_ms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-base-url", default="http://localhost:8200")
    parser.add_argument("--employee-id", default="100001")
    parser.add_argument("--expected-model", default="gpt-5.5")
    parser.add_argument("--service-token", default="")
    parser.add_argument("--env-file", action="append", default=[".env", ".env.local-full.example"])
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    service_token = _load_service_token(args.env_file, args.service_token)
    if not service_token:
        raise SystemExit("SERVICE_TOKEN is required. Pass --service-token or include SERVICE_TOKEN in an env file.")

    summary: dict[str, Any] = {}
    create, elapsed = _bridge_call(
        args.mcp_base_url,
        service_token,
        "agent_draft_create",
        {
            "employee_id": args.employee_id,
            "title": "MCP Bridge Evidence Agent",
            "prompt": "Trend와 Raw Data를 검증하고 승인 판단 근거를 정리해줘.",
            "files": [{"name": "raw.csv", "note": "MCP bridge smoke sample"}],
            "mcp_servers": ["boi-wiki-local"],
            "skills": ["data-analytics:validate-data"],
            "scope": "private",
        },
        args.timeout,
    )
    draft = create["result"]["draft"]
    draft_id = draft["draft_id"]
    model = draft.get("runtime", {}).get("model")
    if model != args.expected_model:
        raise AssertionError(f"agent_draft_create model mismatch: {model!r}")
    summary["draft_create"] = {"ms": elapsed, "draft_id": draft_id, "model": model}

    test, elapsed = _bridge_call(
        args.mcp_base_url,
        service_token,
        "agent_draft_test",
        {"employee_id": args.employee_id, "draft_id": draft_id},
        args.timeout,
    )
    test_payload = test["result"]["test"]
    if test_payload.get("runtime_backend") != "agents_sdk":
        raise AssertionError(f"agent_draft_test backend mismatch: {test_payload}")
    if test_payload.get("model") != args.expected_model:
        raise AssertionError(f"agent_draft_test model mismatch: {test_payload}")
    summary["draft_test"] = {
        "ms": elapsed,
        "backend": test_payload.get("runtime_backend"),
        "model": test_payload.get("model"),
    }

    code = "\n".join(
        [
            "from pathlib import Path",
            "Path('mcp_result.csv').write_text('metric,value\\ntrend_anomaly,1\\nraw_rows,3\\n', encoding='utf-8')",
            "Path('mcp_summary.md').write_text('# MCP Sandbox Smoke\\n\\nTrend anomaly confirmed from sample rows.\\n', encoding='utf-8')",
            "print('mcp-sandbox-ok')",
        ]
    )
    job_body, elapsed = _bridge_call(
        args.mcp_base_url,
        service_token,
        "agent_sandbox_job_create",
        {
            "employee_id": args.employee_id,
            "title": "MCP Sandbox Evidence Smoke",
            "task": "샘플 데이터를 분석해 검증 근거 artifact를 만들어줘.",
            "code": code,
            "language": "python",
            "evidence_intent": "mcp_bridge_smoke",
            "user_confirmed": True,
        },
        args.timeout,
    )
    job = job_body["result"]["job"]
    job_id = job["job_id"]
    if job.get("status") != "completed":
        raise AssertionError(f"sandbox job did not complete: {job}")
    if job.get("execution_mode") != "agents_sdk_unix_local":
        raise AssertionError(f"sandbox execution mode mismatch: {job}")
    if len(job.get("artifacts") or []) < 2:
        raise AssertionError(f"sandbox artifact count is too small: {job}")
    sdk_summary = job.get("agents_sdk_summary") or {}
    if sdk_summary.get("model") != args.expected_model:
        raise AssertionError(f"sandbox summary model mismatch: {sdk_summary}")
    summary["sandbox_create"] = {
        "ms": elapsed,
        "job_id": job_id,
        "status": job.get("status"),
        "execution_mode": job.get("execution_mode"),
        "artifact_count": len(job.get("artifacts") or []),
        "summary_model": sdk_summary.get("model"),
    }

    events, elapsed = _bridge_call(
        args.mcp_base_url,
        service_token,
        "agent_sandbox_job_events",
        {"employee_id": args.employee_id, "job_id": job_id},
        args.timeout,
    )
    event_count = len(events["result"].get("items") or [])
    if event_count < 1:
        raise AssertionError("sandbox job events are empty")
    summary["sandbox_events"] = {"ms": elapsed, "event_count": event_count}

    adopt, elapsed = _bridge_call(
        args.mcp_base_url,
        service_token,
        "agent_sandbox_adopt_evidence",
        {
            "employee_id": args.employee_id,
            "job_id": job_id,
            "evidence_state": "verified_evidence",
            "validation_note": "MCP bridge smoke confirmed sandbox artifact and GPT-5.5 summary.",
            "user_confirmed": True,
        },
        args.timeout,
    )
    evidence_state = adopt["result"]["job"].get("evidence_state")
    if evidence_state != "verified_evidence":
        raise AssertionError(f"evidence adoption failed: {adopt}")
    summary["adopt_evidence"] = {"ms": elapsed, "state": evidence_state}

    if args.summary:
        print(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2))
    else:
        print("Agent Builder MCP bridge smoke: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
