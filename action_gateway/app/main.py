from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

KST = timezone(timedelta(hours=9))
ACTION_CATALOG_ROOT = Path(os.getenv("ACTION_CATALOG_ROOT", "/data/action_catalog"))
ACTION_LOG_ROOT = Path(os.getenv("ACTION_LOG_ROOT", "/data/actions"))
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
BOI_API_URL = os.getenv("BOI_API_URL", "http://boi-api:8000")
LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://langflow:7860")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "dev-langflow-key-change-me")
LANGFLOW_AUTH_MODE = os.getenv("LANGFLOW_AUTH_MODE", "auto-login")
MCP_BRIDGE_URL = os.getenv("MCP_BRIDGE_URL", "")
DRY_RUN_DEFAULT = os.getenv("ACTION_DRY_RUN_DEFAULT", "true").lower() == "true"
ALLOWED_HOSTS = {
    h.strip()
    for h in os.getenv(
        "ACTION_ALLOWED_HOSTS",
        "boi-api,langflow,action-gateway,localhost,127.0.0.1,boi-wiki-mcp",
    ).split(",")
    if h.strip()
}

FIRST_CLASS_ACTION_TYPES = {"boi_materialize", "boi_materializer", "event_publish", "boi_event"}
HTTP_ACTION_TYPES = {"http", "api", "api_call", "webhook", "http_webhook", "internal_webhook", "langflow_webhook"}
LANGFLOW_RUN_ACTION_TYPES = {"langflow_run", "langflow_flow"}

app = FastAPI(title="BoI Action Gateway", version="0.4.0")


def now_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    ACTION_CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    ACTION_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def load_catalog() -> list[dict[str, Any]]:
    ensure_dirs()
    items: list[dict[str, Any]] = []
    for p in sorted(ACTION_CATALOG_ROOT.glob("*.yaml")) + sorted(ACTION_CATALOG_ROOT.glob("*.yml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
            if isinstance(data, dict):
                data = data.get("actions", [data])
            if isinstance(data, list):
                items.extend([x for x in data if isinstance(x, dict) and x.get("action_key")])
        except Exception as exc:
            items.append({"action_key": f"catalog.load_error.{p.name}", "name_ko": "Catalog load error", "error": repr(exc), "enabled": False})
    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        dedup[str(item["action_key"])] = item
    return sorted(dedup.values(), key=lambda x: (int(x.get("order", 100)), str(x.get("action_key"))))


def get_action(action_key: str) -> dict[str, Any] | None:
    for item in load_catalog():
        if item.get("action_key") == action_key:
            return item
    return None


def actions_for_event(event_type: str) -> list[dict[str, Any]]:
    return [a for a in load_catalog() if a.get("enabled", True) and (event_type in (a.get("event_types") or []) or "*" in (a.get("event_types") or [])) and a.get("auto_dispatch", True)]


def simulation_metadata(action: dict[str, Any]) -> dict[str, Any]:
    mode = str(action.get("simulation_mode") or "")
    if not mode:
        return {}
    action_key = str(action.get("action_key") or "")
    simulated_system = str(action.get("simulated_system") or action.get("system") or action.get("name_ko") or action_key)
    return {
        "simulation": True,
        "simulation_mode": mode,
        "simulation_label": str(action.get("simulation_label") or "SIMULATED"),
        "simulation_notice": str(action.get("simulation_notice") or "SIMULATED: 실제 시스템 호출이 아니라 BoI Universal Action Simulator Flow가 생성한 PoC 결과입니다."),
        "real_system_status": str(action.get("real_system_status") or "unavailable"),
        "real_system_connected": False,
        "simulated_system": simulated_system,
        "simulated_action_key": action_key,
        "simulation_contract": {
            "status": "simulated",
            "simulated_action_key": action_key,
            "simulated_system": simulated_system,
            "real_system_connected": False,
        },
    }


def append_action_log(row: dict[str, Any]) -> None:
    ensure_dirs()
    payload = {"logged_at": now_iso(), **row}
    path = ACTION_LOG_ROOT / f"actions-{datetime.now(KST).strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_action_logs(limit: int = 200, action_key: str | None = None, trace_id: str | None = None) -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for p in sorted(ACTION_LOG_ROOT.glob("actions-*.jsonl"), reverse=True):
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if action_key and row.get("action_key") != action_key:
                continue
            if trace_id and row.get("trace_id") != trace_id:
                continue
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def merge_prior_results(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for row in group:
            if not isinstance(row, dict):
                continue
            key = (
                str(row.get("action_key") or ""),
                str(row.get("request_id") or ""),
                str(row.get("_log_ref") or row.get("summary") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return merged


def trace_prior_results(trace_id: str, employee_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
    if not trace_id:
        return []
    rows: list[dict[str, Any]] = []
    for row in reversed(read_action_logs(limit=1000, trace_id=trace_id)):
        if str(row.get("employee_id") or employee_id) != employee_id:
            continue
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        rows.append(
            {
                "action_key": row.get("action_key"),
                "status": row.get("status") or result.get("status"),
                "request_id": row.get("request_id") or result.get("request_id"),
                "summary": row.get("summary") or result.get("message") or result.get("summary"),
                "doc_ref": row.get("doc_ref"),
                "connector_kind": row.get("connector_kind"),
                "event_id": row.get("event_id"),
                "event_type": row.get("event_type"),
                "trace_id": row.get("trace_id"),
                "simulation": bool(row.get("simulation") or result.get("simulation")),
                "coverage_score": row.get("coverage_score") if row.get("coverage_score") is not None else result.get("coverage_score"),
                "evidence_packets": row.get("evidence_packets") or result.get("evidence_packets"),
                "result": result,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def prior_action_refs(prior_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in prior_results[-12:]:
        action_key = str(row.get("action_key") or "")
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        request_id = str(row.get("request_id") or result.get("request_id") or "")
        if not action_key and not request_id:
            continue
        key = (action_key, request_id)
        if key in seen:
            continue
        seen.add(key)
        refs.append({"type": "action", "action_key": action_key, "request_id": request_id})
    return refs


def host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname in ALLOWED_HOSTS


def render_template(value: Any, context: dict[str, Any]) -> Any:
    """Tiny template replacement for catalog URLs/payloads: ${key.path}."""
    if isinstance(value, str):
        full_match = re.fullmatch(r"\$\{([A-Za-z0-9_.\-_]+)\}", value)
        if full_match:
            cur: Any = context
            for part in full_match.group(1).split("."):
                if isinstance(cur, dict):
                    cur = cur.get(part, "")
                else:
                    return ""
            return cur

        def repl(match: re.Match[str]) -> str:
            path = match.group(1).split(".")
            cur: Any = context
            for part in path:
                if isinstance(cur, dict):
                    cur = cur.get(part, "")
                else:
                    return ""
            return str(cur)
        return re.sub(r"\$\{([A-Za-z0-9_.\-_]+)\}", repl, value)
    if isinstance(value, list):
        return [render_template(v, context) for v in value]
    if isinstance(value, dict):
        return {k: render_template(v, context) for k, v in value.items()}
    return value


def is_unresolved_flow_ref(value: str) -> bool:
    normalized = value.strip()
    return not normalized or normalized.startswith("${") or normalized.startswith("replace-with")


async def langflow_auth_headers(client: httpx.AsyncClient) -> dict[str, str]:
    if LANGFLOW_AUTH_MODE == "api-key":
        return {"x-api-key": LANGFLOW_API_KEY}
    resp = await client.get(f"{LANGFLOW_URL.rstrip('/')}/api/v1/auto_login")
    resp.raise_for_status()
    token = (resp.json() or {}).get("access_token")
    if not token:
        raise RuntimeError("Langflow auto_login did not return access_token")
    return {"Authorization": f"Bearer {token}"}


def flow_name_matches(flow_name: str, wanted_name: str) -> bool:
    return flow_name == wanted_name or re.fullmatch(rf"{re.escape(wanted_name)} \(\d+\)", flow_name) is not None


def langflow_flow_matches(flow: dict[str, Any], action: dict[str, Any], wanted_name: str) -> bool:
    if not flow_name_matches(str(flow.get("name") or ""), wanted_name):
        return False
    data_text = json.dumps(flow.get("data") or {}, ensure_ascii=False)
    required_model = str(action.get("require_model") or "")
    if required_model and required_model not in data_text:
        return False
    required_marker = str(action.get("require_marker") or "")
    if required_marker and required_marker not in data_text:
        return False
    return True


async def resolve_langflow_run_target(client: httpx.AsyncClient, action: dict[str, Any], context: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, str]]:
    explicit_flow_id = render_template(str(action.get("flow_id") or ""), context)
    explicit_endpoint = render_template(str(action.get("endpoint_name") or action.get("flow_endpoint_name") or ""), context)
    auth_headers = await langflow_auth_headers(client)
    if not is_unresolved_flow_ref(explicit_flow_id):
        return explicit_flow_id, {"id": explicit_flow_id}, auth_headers
    if explicit_endpoint and not is_unresolved_flow_ref(explicit_endpoint) and not action.get("resolve_latest", False):
        return explicit_endpoint, {"endpoint_name": explicit_endpoint}, auth_headers

    wanted_name = render_template(str(action.get("flow_name") or "BoI Reference Flow"), context)
    resp = await client.get(f"{LANGFLOW_URL.rstrip('/')}/api/v1/flows/", headers=auth_headers)
    resp.raise_for_status()
    flows = resp.json()
    if not isinstance(flows, list):
        raise RuntimeError("Langflow flows API did not return a list")
    matches = [flow for flow in flows if isinstance(flow, dict) and langflow_flow_matches(flow, action, wanted_name)]
    if not matches:
        raise RuntimeError(f"Langflow flow not found: {wanted_name}")
    matches.sort(key=lambda flow: str(flow.get("updated_at") or ""), reverse=True)
    selected = matches[0]
    target = str(selected.get("id") or selected.get("endpoint_name") or "")
    if not target:
        raise RuntimeError(f"Langflow flow has no id or endpoint_name: {wanted_name}")
    return target, selected, auth_headers


def first_langflow_message(value: Any) -> str:
    if isinstance(value, dict):
        text = value.get("text")
        if isinstance(text, str) and text.strip():
            return text
        message = value.get("message")
        if isinstance(message, str) and message.strip():
            return message
        if isinstance(message, dict):
            found = first_langflow_message(message)
            if found:
                return found
        for child in value.values():
            found = first_langflow_message(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = first_langflow_message(child)
            if found:
                return found
    return ""


def extract_boi_id(result: dict[str, Any]) -> str | None:
    try:
        return (((result.get("response") or {}).get("item") or {}).get("metadata") or {}).get("boi_id")
    except Exception:
        return None


def first_summary_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("message", "text", "status"):
            found = first_summary_text(value.get(key))
            if found:
                return found
        for child in value.values():
            found = first_summary_text(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = first_summary_text(child)
            if found:
                return found
    return ""


def truncate_summary(value: str, limit: int = 500) -> str:
    summary = " ".join(str(value or "").split())
    if len(summary) <= limit:
        return summary
    cutoff = max(0, limit - 3)
    head = summary[:cutoff].rstrip()
    boundary = head.rfind(" ")
    if boundary >= int(cutoff * 0.75):
        head = head[:boundary].rstrip()
    return head.rstrip("`*_-[({/:;,") + "..."


def summarize_action_result(result: dict[str, Any] | None, error: Any = None) -> str:
    if result:
        response = result.get("response")
        if isinstance(response, dict) and isinstance(response.get("result"), dict):
            for key in (
                "raw_data_ref",
                "source_data_ref",
                "trend_status",
                "guide_boi_ref",
                "notification_status",
                "requested_state",
                "requested_change",
            ):
                if response["result"].get(key):
                    return f"{key}={response['result'][key]}"
        return truncate_summary(first_summary_text(result))
    if error:
        return truncate_summary(first_summary_text(error) or str(error))
    return ""


async def universal_simulation_agent_context(
    client: httpx.AsyncClient,
    action: dict[str, Any],
    req: "InvokeRequest",
) -> dict[str, Any]:
    if str(action.get("simulation_mode") or "") != "langflow_universal":
        return {}
    url = f"{BOI_API_URL.rstrip('/')}/api/simulations/universal-agent"
    body = {
        "action_key": action.get("action_key"),
        "employee_id": req.employee_id,
        "event": req.event,
        "payload": req.payload or req.event.get("payload") or {},
        "prior_results": req.prior_results,
        "workflow_key": action.get("workflow_key") or "",
        "sop_ref": action.get("sop_ref") or "",
        "sop_stage_id": action.get("sop_stage_id") or "",
        "max_rounds": int(action.get("simulation_agent_max_rounds") or 4),
        "simulation_depth": action.get("simulation_depth") or "stage_prerequisites",
    }
    try:
        resp = await client.post(url, headers={"x-service-token": SERVICE_TOKEN}, json=body)
        try:
            payload: Any = resp.json()
        except Exception:
            payload = {"ok": False, "error": resp.text[:2000]}
        if resp.status_code >= 400:
            return {"ok": False, "status": "simulation_agent_failed", "http_status": resp.status_code, "error": payload}
        return payload if isinstance(payload, dict) else {"ok": False, "status": "simulation_agent_failed", "error": payload}
    except Exception as exc:
        return {"ok": False, "status": "simulation_agent_failed", "error": repr(exc)}


def simulation_agent_prompt_prefix(value: dict[str, Any]) -> str:
    if not value:
        return ""
    compact = {
        "action_key": value.get("action_key"),
        "event_type": value.get("event_type"),
        "trace_id": value.get("trace_id"),
        "agent": value.get("agent"),
        "coverage_report": value.get("coverage_report"),
        "evidence_packets": value.get("evidence_packets"),
        "citations": value.get("citations"),
        "limitations": value.get("limitations"),
        "retrieval_trace": value.get("retrieval_trace"),
        "workflow": ((value.get("context_pack") or {}).get("workflow") if isinstance(value.get("context_pack"), dict) else {}),
        "prior_results": ((value.get("context_pack") or {}).get("prior_results") if isinstance(value.get("context_pack"), dict) else []),
        "context_documents": ((value.get("context_pack") or {}).get("documents") or [])[:8],
        "simulation_result": value.get("simulation_result"),
    }
    return (
        "BoI Simulation Agent retrieved context. Use this as authoritative context before final rendering.\n"
        + json.dumps(compact, ensure_ascii=False, indent=2, default=str)
        + "\n\nOriginal Langflow request follows.\n"
    )


def simulation_agent_fields(value: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "simulation_agent": value or {},
            "retrieval_rounds": None,
            "used_docs": [],
            "missing_context": [],
            "coverage_score": None,
            "evidence_packets": [],
            "simulation_boundaries": [],
        }
    context_pack = value.get("context_pack") if isinstance(value.get("context_pack"), dict) else {}
    return {
        "simulation_agent": value,
        "retrieval_rounds": ((value.get("agent") or {}).get("retrieval_rounds") if isinstance(value.get("agent"), dict) else None),
        "used_docs": context_pack.get("documents") or [],
        "missing_context": ((value.get("coverage_report") or {}).get("missing_context") if isinstance(value.get("coverage_report"), dict) else []),
        "coverage_score": ((value.get("coverage_report") or {}).get("coverage_score") if isinstance(value.get("coverage_report"), dict) else None),
        "evidence_packets": value.get("evidence_packets") or context_pack.get("evidence_packets") or [],
        "simulation_boundaries": value.get("limitations") or [],
    }


def simulation_agent_markdown(value: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ""
    result = value.get("simulation_result")
    if isinstance(result, dict):
        markdown = result.get("markdown")
        if markdown:
            return str(markdown)
    return "# SIMULATED BoI Wiki Simulation Result\n\nSimulation Agent context was generated, but no rendered markdown was returned."


async def require_service_token(x_service_token: str | None = Header(None)) -> None:
    if x_service_token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


class InvokeRequest(BaseModel):
    action_key: str = Field(examples=["boi.materialize.event"])
    employee_id: str = "100001"
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool | None = None
    approved_by: str | None = None
    idempotency_key: str | None = None
    prior_results: list[dict[str, Any]] = Field(default_factory=list)


class DispatchRequest(BaseModel):
    employee_id: str = "100001"
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool | None = None
    approved_by: str | None = None
    idempotency_key: str | None = None
    prior_results: list[dict[str, Any]] = Field(default_factory=list)


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/actions")
async def list_actions(event_type: str = "", risk_level: str = "") -> dict[str, Any]:
    items = [x for x in load_catalog() if x.get("enabled", True)]
    if event_type:
        items = [x for x in items if event_type in (x.get("event_types") or []) or "*" in (x.get("event_types") or [])]
    if risk_level:
        items = [x for x in items if x.get("risk_level") == risk_level]
    return {"count": len(items), "items": items}


@app.get("/api/actions/logs")
async def logs(limit: int = 200, action_key: str = "", trace_id: str = "") -> dict[str, Any]:
    rows = read_action_logs(limit=limit, action_key=action_key or None, trace_id=trace_id or None)
    return {"count": len(rows), "items": rows}


async def invoke_action(action: dict[str, Any], req: InvokeRequest) -> dict[str, Any]:
    request_id = req.idempotency_key or f"act-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    action_type = str(action.get("type", "mock_api"))

    if req.dry_run is not None:
        dry_run = req.dry_run
    elif "dry_run" in action:
        dry_run = bool(action.get("dry_run"))
    elif action_type in FIRST_CLASS_ACTION_TYPES:
        dry_run = False
    else:
        dry_run = DRY_RUN_DEFAULT

    approval_required = bool(action.get("approval_required"))
    action_refs = prior_action_refs(req.prior_results)
    context = {
        "request_id": request_id,
        "employee_id": req.employee_id,
        "event": req.event,
        "payload": req.payload or req.event.get("payload") or {},
        "boi_id": req.boi_id or "",
        "service_token": SERVICE_TOKEN,
        "dry_run": dry_run,
        "approved_by": req.approved_by or "",
        "prior_results": req.prior_results,
        "prior_results_json": json.dumps(req.prior_results, ensure_ascii=False, indent=2),
        "prior_action_refs": action_refs,
        "prior_action_refs_json": json.dumps(action_refs, ensure_ascii=False, indent=2),
    }
    base_log = {
        "action_key": action.get("action_key"),
        "request_id": request_id,
        "employee_id": req.employee_id,
        "event_id": req.event.get("event_id"),
        "event_type": req.event.get("event_type"),
        "trace_id": req.event.get("trace_id"),
        "boi_id": req.boi_id,
        "dry_run": dry_run,
        "approved_by": req.approved_by,
        "risk_level": action.get("risk_level"),
        "action_type": action_type,
        "connector_kind": action.get("connector_kind"),
        "doc_ref": action.get("doc_ref"),
        **simulation_metadata(action),
    }

    if approval_required and not req.approved_by:
        result = {
            "ok": False,
            "status": "approval_required",
            "request_id": request_id,
            "action_key": action.get("action_key"),
            "message": "This action is registered as approval_required. Re-invoke with approved_by after human approval.",
            "action": {k: action.get(k) for k in ["action_key", "name_ko", "risk_level", "owner", "description", "type", "doc_ref", "connector_kind"]},
            **simulation_metadata(action),
        }
        append_action_log({**base_log, "status": "approval_required", "payload": req.payload})
        return result

    try:
        if action_type == "manual_task":
            result = {
                "ok": True,
                "status": "manual_required",
                "request_id": request_id,
                "action_key": action.get("action_key"),
                "action_name": action.get("name_ko") or action.get("name"),
                "manual_handoff": {
                    "owner": action.get("owner"),
                    "approved_by": req.approved_by,
                    "risk_level": action.get("risk_level"),
                    "doc_ref": action.get("doc_ref"),
                    "checklist": render_template(action.get("checklist") or [], context),
                    "payload": req.payload,
                },
                **simulation_metadata(action),
            }

        elif dry_run or action_type == "mock_api":
            result = {
                "ok": True,
                "status": "dry_run" if dry_run else "mocked",
                "request_id": request_id,
                "action_key": action.get("action_key"),
                "action_name": action.get("name_ko") or action.get("name"),
                "mock_response": render_template(action.get("mock_response") or {}, context),
                **simulation_metadata(action),
            }

        elif action_type in {"boi_materialize", "boi_materializer"}:
            url = f"{BOI_API_URL.rstrip('/')}/api/boi/materialize-event"
            async with httpx.AsyncClient(timeout=float(action.get("timeout_seconds", 30))) as client:
                resp = await client.post(url, headers={"x-service-token": SERVICE_TOKEN}, json=req.event)
                resp.raise_for_status()
                result = {"ok": True, "status": "materialized", "request_id": request_id, "action_key": action.get("action_key"), "response": resp.json()}

        elif action_type in {"event_publish", "boi_event"}:
            url = f"{BOI_API_URL.rstrip('/')}/api/events/publish?employee_id={req.employee_id}"
            body = render_template(action.get("body") or {}, context)
            if isinstance(body, dict):
                refs = body.get("source_refs") if isinstance(body.get("source_refs"), list) else []
                seen_refs = {
                    (
                        str(item.get("type") if isinstance(item, dict) else ""),
                        str(item.get("request_id") or item.get("ref") if isinstance(item, dict) else item),
                    )
                    for item in refs
                }
                for ref in action_refs:
                    marker = (str(ref.get("type") or ""), str(ref.get("request_id") or ref.get("ref") or ""))
                    if marker not in seen_refs:
                        refs.append(ref)
                        seen_refs.add(marker)
                body["source_refs"] = refs
                payload = body.get("payload")
                if isinstance(payload, dict) and "prior_action_refs" not in payload:
                    payload["prior_action_refs"] = action_refs
            async with httpx.AsyncClient(timeout=float(action.get("timeout_seconds", 20))) as client:
                resp = await client.post(url, headers={"x-service-token": SERVICE_TOKEN}, json=body)
                resp.raise_for_status()
                result = {"ok": True, "status": "event_published", "request_id": request_id, "action_key": action.get("action_key"), "response": resp.json()}

        elif action_type in LANGFLOW_RUN_ACTION_TYPES:
            async with httpx.AsyncClient(timeout=float(action.get("timeout_seconds", 90))) as client:
                simulation_agent = await universal_simulation_agent_context(client, action, req)
                context["simulation_agent"] = simulation_agent
                context["simulation_agent_json"] = json.dumps(simulation_agent, ensure_ascii=False, indent=2, default=str)
                agent_fields = simulation_agent_fields(simulation_agent)
                flow_target = str(action.get("flow_id") or action.get("flow_name") or "unresolved")
                flow_info: dict[str, Any] = {}
                langflow_timeout_seconds = float(action.get("timeout_seconds", 90))

                async def perform_langflow_request() -> tuple[Any, Any]:
                    nonlocal flow_target, flow_info
                    flow_target, flow_info, auth_headers = await resolve_langflow_run_target(client, action, context)
                    url = render_template(str(action.get("url", "")), context) or f"{LANGFLOW_URL.rstrip('/')}/api/v1/run/{flow_target}"
                    if not host_allowed(url):
                        raise HTTPException(status_code=400, detail=f"Langflow URL is not allowlisted: {url}")
                    headers = {"Content-Type": "application/json", **auth_headers}
                    headers.update(render_template(action.get("headers") or {}, context))
                    body = render_template(
                        action.get("body")
                        or {
                            "input_value": str(req.payload or req.event),
                            "input_type": "chat",
                            "output_type": "chat",
                        },
                        context,
                    )
                    if simulation_agent and isinstance(body, dict):
                        prefix = simulation_agent_prompt_prefix(simulation_agent)
                        if prefix:
                            body["input_value"] = prefix + str(body.get("input_value") or "")
                    resp = await client.request("POST", url, headers=headers, json=body)
                    try:
                        resp_body: Any = resp.json()
                    except Exception:
                        resp_body = resp.text[:2000]
                    return resp, resp_body

                try:
                    resp, resp_body = await asyncio.wait_for(perform_langflow_request(), timeout=langflow_timeout_seconds)
                    if resp.status_code >= 400:
                        raise HTTPException(status_code=resp.status_code, detail=resp_body)
                    result = {
                        "ok": True,
                        "status": "langflow_invoked",
                        "request_id": request_id,
                        "action_key": action.get("action_key"),
                        "http_status": resp.status_code,
                        "flow_id": flow_info.get("id") or flow_target,
                        "flow_endpoint_name": flow_info.get("endpoint_name") or flow_target,
                        "flow_name": flow_info.get("name") or action.get("flow_name"),
                        "message": first_langflow_message(resp_body),
                        "response": resp_body,
                        **agent_fields,
                        **simulation_metadata(action),
                    }
                except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
                    if not (isinstance(simulation_agent, dict) and simulation_agent.get("ok") is not False):
                        raise
                    result = {
                        "ok": True,
                        "status": "langflow_invoked",
                        "request_id": request_id,
                        "action_key": action.get("action_key"),
                        "http_status": None,
                        "flow_id": flow_info.get("id") or flow_target,
                        "flow_endpoint_name": flow_info.get("endpoint_name") or flow_target,
                        "flow_name": flow_info.get("name") or action.get("flow_name"),
                        "message": simulation_agent_markdown(simulation_agent),
                        "response": {
                            "ok": True,
                            "status": "langflow_renderer_timeout_fallback",
                            "timeout_error": repr(exc),
                            "fallback": "boi_simulation_agent",
                        },
                        "langflow_renderer_status": "timeout_fallback",
                        **agent_fields,
                        **simulation_metadata(action),
                    }

        elif action_type in HTTP_ACTION_TYPES:
            method = str(action.get("method", "POST")).upper()
            if action_type == "langflow_webhook":
                flow_id = render_template(str(action.get("flow_id", "")), context)
                url = render_template(str(action.get("url", "")), context) or f"{LANGFLOW_URL.rstrip('/')}/api/v1/webhook/{flow_id}"
                headers = {"x-api-key": LANGFLOW_API_KEY, "Content-Type": "application/json"}
                headers.update(render_template(action.get("headers") or {}, context))
            else:
                url = render_template(str(action.get("url", "")), context)
                headers = render_template(action.get("headers") or {}, context)
            if not url or not host_allowed(url):
                raise HTTPException(status_code=400, detail=f"URL is not allowlisted: {url}")
            body = render_template(action.get("body") or req.payload or req.event, context)
            async with httpx.AsyncClient(timeout=float(action.get("timeout_seconds", 20))) as client:
                resp = await client.request(method, url, headers=headers, json=body)
                try:
                    resp_body: Any = resp.json()
                except Exception:
                    resp_body = resp.text[:2000]
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp_body)
                result = {
                    "ok": True,
                    "status": "invoked",
                    "request_id": request_id,
                    "action_key": action.get("action_key"),
                    "http_status": resp.status_code,
                    "response": resp_body,
                    **simulation_metadata(action),
                }

        elif action_type in {"mcp_bridge", "mcp_tool"}:
            bridge_url = render_template(str(action.get("url") or MCP_BRIDGE_URL), context)
            if not bridge_url:
                raise HTTPException(status_code=400, detail="MCP bridge URL is not configured")
            if not host_allowed(bridge_url):
                raise HTTPException(status_code=400, detail=f"MCP bridge URL is not allowlisted: {bridge_url}")
            body = {
                "server": render_template(action.get("server") or {}, context),
                "tool": render_template(action.get("tool") or action.get("tool_name") or "", context),
                "arguments": render_template(action.get("arguments") or req.payload, context),
                "event": req.event,
                "boi_id": req.boi_id,
                "request_id": request_id,
            }
            async with httpx.AsyncClient(timeout=float(action.get("timeout_seconds", 30))) as client:
                resp = await client.post(bridge_url, headers=render_template(action.get("headers") or {}, context), json=body)
                try:
                    resp_body = resp.json()
                except Exception:
                    resp_body = resp.text[:2000]
                if resp.status_code >= 400:
                    raise HTTPException(status_code=resp.status_code, detail=resp_body)
                result = {"ok": True, "status": "mcp_invoked", "request_id": request_id, "action_key": action.get("action_key"), "response": resp_body}

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported action type: {action_type}")

        simulation_log = {
            key: result.get(key)
            for key in (
                "retrieval_rounds",
                "used_docs",
                "missing_context",
                "coverage_score",
                "evidence_packets",
                "simulation_boundaries",
                "langflow_renderer_status",
            )
            if key in result
        }
        append_action_log({**base_log, **simulation_log, "status": result.get("status"), "result": result})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        append_action_log({**base_log, "status": "failed", "error": repr(exc)})
        raise HTTPException(status_code=500, detail=repr(exc))


@app.post("/api/actions/invoke", dependencies=[Depends(require_service_token)])
async def invoke(req: InvokeRequest) -> dict[str, Any]:
    action = get_action(req.action_key)
    if not action or not action.get("enabled", True):
        raise HTTPException(status_code=404, detail=f"Action not found or disabled: {req.action_key}")
    return await invoke_action(action, req)


@app.post("/api/actions/dispatch", dependencies=[Depends(require_service_token)])
async def dispatch(req: DispatchRequest) -> dict[str, Any]:
    event_type = str(req.event.get("event_type") or "")
    if not event_type:
        raise HTTPException(status_code=400, detail="event.event_type is required")
    actions = actions_for_event(event_type)
    results: list[dict[str, Any]] = []
    current_boi_id = req.boi_id
    prior_results = merge_prior_results(trace_prior_results(str(req.event.get("trace_id") or ""), req.employee_id), list(req.prior_results or []))
    for action in actions:
        child_req = InvokeRequest(
            action_key=str(action.get("action_key")),
            employee_id=req.employee_id,
            event=req.event,
            boi_id=current_boi_id,
            payload=req.payload or req.event.get("payload") or {},
            dry_run=req.dry_run,
            approved_by=req.approved_by,
            idempotency_key=None,
            prior_results=prior_results,
        )
        try:
            result = await invoke_action(action, child_req)
            new_boi_id = extract_boi_id(result)
            if new_boi_id and not current_boi_id:
                current_boi_id = new_boi_id
            row = {
                "action_key": action.get("action_key"),
                "type": action.get("type"),
                "order": action.get("order"),
                "connector_kind": action.get("connector_kind"),
                "doc_ref": action.get("doc_ref"),
                "request_id": result.get("request_id"),
                "summary": summarize_action_result(result),
                "result": result,
            }
            results.append(row)
            prior_results.append(row)
        except HTTPException as exc:
            row = {
                "action_key": action.get("action_key"),
                "type": action.get("type"),
                "order": action.get("order"),
                "connector_kind": action.get("connector_kind"),
                "doc_ref": action.get("doc_ref"),
                "request_id": "",
                "summary": summarize_action_result(None, exc.detail),
                "error": exc.detail,
                "status_code": exc.status_code,
            }
            results.append(row)
            prior_results.append(row)
            if action.get("continue_on_error", True) is False:
                break
    return {"ok": True, "status": "dispatched", "event_type": event_type, "boi_id": current_boi_id, "count": len(results), "results": results}
