from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

KST = timezone(timedelta(hours=9))
APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("DATA_ROOT", "/data/boi"))
EVENTS_ROOT = Path(os.getenv("EVENTS_ROOT", "/data/events"))
EVENT_CATALOG_ROOT = Path(os.getenv("EVENT_CATALOG_ROOT", "/data/event_catalog"))
ACTION_CATALOG_ROOT = Path(os.getenv("ACTION_CATALOG_ROOT", "/data/action_catalog"))
ACTION_LOG_ROOT = Path(os.getenv("ACTION_LOG_ROOT", "/data/actions"))
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
DEFAULT_TEAM_ID = os.getenv("DEFAULT_TEAM_ID", "aix-tf")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
BOI_EVENTS_TOPIC = os.getenv("BOI_EVENTS_TOPIC", "boi.events")
DEMO_EMPLOYEE_ID = os.getenv("DEMO_EMPLOYEE_ID", "100001")
BOI_LLM_BASE_URL = os.getenv("BOI_LLM_BASE_URL", "http://mangugil.iptime.org:1236/v1").rstrip("/")
BOI_LLM_MODEL = os.getenv("BOI_LLM_MODEL", "google/gemma-4-26b-a4b-qat")
BOI_LLM_API_KEY = os.getenv("BOI_LLM_API_KEY", "not-needed")

# PoC user/team map. Replace with SSO/IAM/HR master during internalization.
USER_TEAMS: dict[str, list[str]] = {
    "100001": ["aix-tf", "platform"],
    "100002": ["aix-tf"],
    "100003": ["platform"],
}
USER_NAMES: dict[str, str] = {
    "100001": "AIX TF User 100001",
    "100002": "AIX TF User 100002",
    "100003": "Platform User 100003",
}

# Business-facing Event Type Catalog. The UI exposes this catalog so Event Broker is not
# hidden as a Kafka-only implementation detail. Replace/extend with YAML files under
# /data/event_catalog during internalization.
BUILTIN_EVENT_TYPES: list[dict[str, Any]] = [
    {
        "event_type": "meeting.closed.v1",
        "name_ko": "회의 종료",
        "description": "회의가 종료되어 회의 요약, 결정사항, Action Item을 BoI로 정리해야 하는 시점",
        "default_boi_type": "boi/meeting",
        "default_flow_key": "boi-meeting-writer-v0.1",
        "default_visibility": "private",
        "owner": "AIX 확산 TF",
        "status": "poc",
        "topic": "boi.events",
        "wiki_usage": "회의 종료 후 Private BoI를 만들고, 공유 가치가 있으면 Team BoI draft로 승격",
    },
    {
        "event_type": "action.created.v1",
        "name_ko": "Action Item 생성",
        "description": "회의/보고/요청에서 담당자별 Action Item이 생성된 시점",
        "default_boi_type": "boi/action",
        "default_flow_key": "boi-action-writer-v0.1",
        "default_visibility": "private",
        "owner": "AIX 확산 TF",
        "status": "poc",
        "topic": "boi.events",
        "wiki_usage": "담당자 Private BoI로 Action 맥락을 정리하고 진행 상태를 추적",
    },
    {
        "event_type": "report.requested.v1",
        "name_ko": "보고 요청",
        "description": "주간보고/경영진 보고/TF 현황 보고 초안이 필요한 시점",
        "default_boi_type": "boi/report",
        "default_flow_key": "boi-report-draft-v0.1",
        "default_visibility": "private",
        "owner": "AIX 확산 TF",
        "status": "poc",
        "topic": "boi.events",
        "wiki_usage": "권한 있는 Public/Team BoI와 본인 Private BoI를 Lazy Loading하여 보고 초안 작성",
    },
    {
        "event_type": "promotion.requested.v1",
        "name_ko": "BoI 승격 요청",
        "description": "사용자가 Private BoI를 Team/Public 공유용 draft로 승격하라고 명시적으로 요청한 시점",
        "default_boi_type": "boi/reference",
        "default_flow_key": "boi-promotion-v0.1",
        "default_visibility": "team",
        "owner": "AIX 확산 TF",
        "status": "poc",
        "topic": "boi.events",
        "wiki_usage": "Private 원본은 유지하고 공유용 사본을 만들며 reviewer 검토 상태로 저장",
    },
]

REQUIRED_FIELDS = [
    "okf_version",
    "boi_profile_version",
    "type",
    "title",
    "description",
    "timestamp",
    "boi_id",
    "visibility",
    "classification",
    "owner",
    "acl_policy",
    "status",
]

app = FastAPI(title="BoI Wiki PoC", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def now_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def employee_hash(employee_id: str) -> str:
    return hashlib.sha256(employee_id.encode()).hexdigest()[:12]


def safe_filename(value: str) -> str:
    value = value.replace(":", "-").replace("/", "-")
    value = re.sub(r"[^A-Za-z0-9_.-]", "-", value)
    return value[:160] or f"boi-{uuid.uuid4().hex}"


def ensure_dirs() -> None:
    for sub in ["public", f"team/{DEFAULT_TEAM_ID}", "team/platform"]:
        (DATA_ROOT / sub).mkdir(parents=True, exist_ok=True)
    for employee_id in USER_TEAMS:
        (DATA_ROOT / "private" / employee_id).mkdir(parents=True, exist_ok=True)
    EVENTS_ROOT.mkdir(parents=True, exist_ok=True)
    EVENT_CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    ACTION_CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    ACTION_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    if markdown.startswith("---"):
        parts = markdown.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].lstrip("\n")
    return {}, markdown


def compose_markdown(metadata: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body.lstrip("\n")


def all_markdown_files() -> list[Path]:
    ensure_dirs()
    return sorted(DATA_ROOT.rglob("*.md"))


def read_doc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(text)
    visibility = metadata.get("visibility", "unknown")
    source_event = metadata.get("source_event") or {}
    event_type = metadata.get("event_type") or source_event.get("event_type")
    if event_type:
        metadata.setdefault("event_type", event_type)
    return {
        "path": str(path),
        "uri": "/" + str(path.relative_to(DATA_ROOT)).replace("\\", "/"),
        "metadata": metadata,
        "body": body,
        "visibility": visibility,
        "event_type": event_type,
    }


def load_event_types() -> list[dict[str, Any]]:
    ensure_dirs()
    items: list[dict[str, Any]] = []
    for p in sorted(EVENT_CATALOG_ROOT.glob("*.yaml")) + sorted(EVENT_CATALOG_ROOT.glob("*.yml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
            if isinstance(data, dict):
                data = data.get("event_types", [data])
            if isinstance(data, list):
                items.extend([x for x in data if isinstance(x, dict) and x.get("event_type")])
        except Exception:
            continue
    if not items:
        items = BUILTIN_EVENT_TYPES
    # latest definition wins
    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        dedup[str(item["event_type"])] = item
    return list(dedup.values())


def event_type_map() -> dict[str, dict[str, Any]]:
    return {str(e["event_type"]): e for e in load_event_types()}


def get_event_type(event_type: str) -> dict[str, Any] | None:
    return event_type_map().get(event_type)


def event_label(event_type: str | None) -> str:
    if not event_type:
        return ""
    rec = get_event_type(event_type)
    return str(rec.get("name_ko") or event_type) if rec else event_type


def load_action_catalog() -> list[dict[str, Any]]:
    ensure_dirs()
    items: list[dict[str, Any]] = []
    for p in sorted(ACTION_CATALOG_ROOT.glob("*.yaml")) + sorted(ACTION_CATALOG_ROOT.glob("*.yml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
            if isinstance(data, dict):
                data = data.get("actions", [data])
            if isinstance(data, list):
                items.extend([x for x in data if isinstance(x, dict) and x.get("action_key")])
        except Exception:
            continue
    dedup: dict[str, dict[str, Any]] = {}
    for item in items:
        dedup[str(item["action_key"])] = item
    return list(dedup.values())


def read_action_logs(limit: int = 200, action_key: str | None = None) -> list[dict[str, Any]]:
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
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def append_event_log(*, status: str, event: dict[str, Any], result: dict[str, Any] | None = None, error: str | None = None) -> None:
    ensure_dirs()
    payload = {
        "logged_at": now_iso(),
        "status": status,
        "event_id": event.get("event_id"),
        "event_type": event.get("event_type"),
        "actor": event.get("actor"),
        "producer": event.get("producer"),
        "trace_id": event.get("trace_id"),
        "payload_title": (event.get("payload") or {}).get("title"),
        "source_refs": event.get("source_refs") or [],
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    path = EVENTS_ROOT / f"events-{datetime.now(KST).strftime('%Y%m%d')}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_event_logs(limit: int = 200, event_type: str | None = None) -> list[dict[str, Any]]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for p in sorted(EVENTS_ROOT.glob("events-*.jsonl"), reverse=True):
        for line in reversed(p.read_text(encoding="utf-8").splitlines()):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if event_type and row.get("event_type") != event_type:
                continue
            row["event_label"] = event_label(row.get("event_type"))
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def teams_for(employee_id: str) -> list[str]:
    return USER_TEAMS.get(employee_id, [])


def is_accessible(doc: dict[str, Any], employee_id: str) -> bool:
    meta = doc["metadata"]
    visibility = meta.get("visibility")
    path = Path(doc["path"])
    if visibility == "public":
        return True
    if visibility == "team":
        # Team ID can come from metadata.team_id or path /team/{team_id}
        team_id = meta.get("team_id")
        if not team_id:
            parts = path.relative_to(DATA_ROOT).parts
            if len(parts) >= 2 and parts[0] == "team":
                team_id = parts[1]
        return team_id in teams_for(employee_id)
    if visibility == "private":
        parts = path.relative_to(DATA_ROOT).parts
        # Only web-stored Private BoI under /private/{employee_id} is visible here.
        return len(parts) >= 2 and parts[0] == "private" and parts[1] == employee_id
    return False


def accessible_docs(employee_id: str) -> list[dict[str, Any]]:
    docs = []
    for p in all_markdown_files():
        try:
            doc = read_doc(p)
        except Exception:
            continue
        if is_accessible(doc, employee_id):
            docs.append(doc)
    docs.sort(key=lambda d: d["metadata"].get("timestamp", ""), reverse=True)
    return docs


def find_doc_by_id(boi_id: str, employee_id: str | None = None) -> dict[str, Any] | None:
    for p in all_markdown_files():
        try:
            doc = read_doc(p)
        except Exception:
            continue
        if doc["metadata"].get("boi_id") == boi_id:
            if employee_id is None or is_accessible(doc, employee_id):
                return doc
    return None


def target_dir_for(metadata: dict[str, Any]) -> Path:
    visibility = metadata.get("visibility", "private")
    if visibility == "private":
        owner = str(metadata.get("owner") or DEMO_EMPLOYEE_ID)
        return DATA_ROOT / "private" / owner
    if visibility == "team":
        team_id = str(metadata.get("team_id") or DEFAULT_TEAM_ID)
        return DATA_ROOT / "team" / team_id
    if visibility == "public":
        return DATA_ROOT / "public"
    raise HTTPException(status_code=400, detail=f"Unsupported visibility: {visibility}")


def validate_metadata(metadata: dict[str, Any], promotion: bool = False) -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in metadata or metadata[field] in (None, ""):
            errors.append(f"missing required metadata: {field}")
    if metadata.get("visibility") not in {"private", "team", "public"}:
        errors.append("visibility must be private/team/public")
    if metadata.get("status") not in {"draft", "reviewed", "approved", "deprecated"}:
        errors.append("status must be draft/reviewed/approved/deprecated")
    if metadata.get("visibility") in {"team", "public"} or promotion:
        if not metadata.get("source_refs"):
            errors.append("team/public BoI requires source_refs")
        review = metadata.get("review") or {}
        if not review.get("reviewer") and not metadata.get("reviewer"):
            errors.append("team/public BoI requires reviewer")
        if metadata.get("status") == "approved" and not review.get("reviewed_at"):
            errors.append("approved BoI requires review.reviewed_at")
    return errors


def write_boi(metadata: dict[str, Any], body: str) -> dict[str, Any]:
    ensure_dirs()
    errors = validate_metadata(metadata)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    path_dir = target_dir_for(metadata)
    path_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(metadata["boi_id"]) + ".md"
    path = path_dir / filename
    path.write_text(compose_markdown(metadata, body), encoding="utf-8")
    return read_doc(path)


def make_metadata(
    *,
    boi_type: str,
    title: str,
    description: str,
    owner: str,
    visibility: Literal["private", "team", "public"] = "private",
    classification: str = "internal",
    team_id: str | None = None,
    source_event: dict[str, Any] | None = None,
    source_refs: list[dict[str, Any]] | None = None,
    status: str = "draft",
    tags: list[str] | None = None,
    promotion: dict[str, Any] | None = None,
    reviewer: str | None = None,
) -> dict[str, Any]:
    scope = visibility if visibility != "team" else f"team:{team_id or DEFAULT_TEAM_ID}"
    boi_id = f"boi:{scope}:{owner}:{datetime.now(KST).strftime('%Y%m%d%H%M%S')}:{uuid.uuid4().hex[:6]}"
    meta: dict[str, Any] = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": boi_type,
        "title": title,
        "description": description,
        "tags": tags or ["BoI", "PoC"],
        "timestamp": now_iso(),
        "boi_id": boi_id,
        "visibility": visibility,
        "classification": classification,
        "owner": owner,
        "author": {"type": "agent", "agent_id": "boi-writer-v0.4"},
        "acl_policy": f"acl:{visibility}:{owner if visibility == 'private' else (team_id or 'public')}",
        "status": status,
    }
    if team_id:
        meta["team_id"] = team_id
    if source_event:
        meta["source_event"] = source_event
        if source_event.get("event_type"):
            meta["event_type"] = source_event.get("event_type")
            meta["event_label"] = event_label(source_event.get("event_type"))
    if source_refs:
        meta["source_refs"] = source_refs
    if reviewer:
        meta["review"] = {"reviewer": reviewer, "review_status": "pending"}
    if promotion:
        meta["promotion"] = promotion
    return meta


async def require_service_token(x_service_token: str | None = Header(None)) -> None:
    if x_service_token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


def current_employee(
    employee_id: str | None = Query(default=None),
    x_employee_id: str | None = Header(default=None),
) -> str:
    return employee_id or x_employee_id or DEMO_EMPLOYEE_ID


class BoiCreate(BaseModel):
    metadata: dict[str, Any]
    body: str


class PromotionRequest(BaseModel):
    target_visibility: Literal["team", "public"] = "team"
    team_id: str | None = None
    reviewer: str = "tf-lead"
    promotion_reason: str = "User explicitly requested promotion."


class EventPublishRequest(BaseModel):
    event_type: str = Field(examples=["meeting.closed.v1"])
    payload: dict[str, Any] = Field(default_factory=dict)
    actor_employee_id: str | None = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)


class EquipmentAnomalyStartRequest(BaseModel):
    equipment_id: str = "ETCH-VM-01"
    alarm_code: str = "RESPONSE_CHAIN_ABNORMAL"
    title: str = "Response Chain 이상 Alarm 발생"
    lot_id: str = "LOT-POC-001"
    wafer_id: str = "WF-POC-001"
    owner: str | None = None


class EventHandleRequest(BaseModel):
    event_id: str
    event_type: str
    event_version: str | None = "1"
    occurred_at: str | None = None
    producer: str | None = None
    actor: dict[str, Any] | None = None
    visibility_hint: str | None = "private"
    classification_hint: str | None = "internal"
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    target: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: str | None = None


class EventAuditRequest(BaseModel):
    status: str
    event: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


class ActionInvokeRequest(BaseModel):
    action_key: str
    employee_id: str | None = None
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool | None = None
    approved_by: str | None = None
    idempotency_key: str | None = None


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/runtime/config")
async def runtime_config() -> dict[str, Any]:
    return {
        "llm": {
            "provider": "openai-compatible",
            "base_url": BOI_LLM_BASE_URL,
            "model": BOI_LLM_MODEL,
            "api_key_configured": bool(BOI_LLM_API_KEY),
        },
        "event_broker": {"type": "kafka", "bootstrap": KAFKA_BOOTSTRAP, "topic": BOI_EVENTS_TOPIC},
        "connectors": {"action_gateway_url": ACTION_GATEWAY_URL, "langflow": "peer_connector"},
    }


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    employee_id: str = Depends(current_employee),
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
) -> HTMLResponse:
    docs = accessible_docs(employee_id)
    if q:
        q_lower = q.lower()
        docs = [d for d in docs if q_lower in json.dumps(d["metadata"], ensure_ascii=False).lower() or q_lower in d["body"].lower()]
    if event_type:
        docs = [d for d in docs if d["metadata"].get("event_type") == event_type]
    if visibility:
        docs = [d for d in docs if d["metadata"].get("visibility") == visibility]
    if boi_type:
        docs = [d for d in docs if d["metadata"].get("type") == boi_type]
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "employee_id": employee_id,
            "user_name": USER_NAMES.get(employee_id, employee_id),
            "teams": teams_for(employee_id),
            "docs": docs,
            "q": q,
            "event_type": event_type,
            "visibility": visibility,
            "boi_type": boi_type,
            "event_types": load_event_types(),
            "event_logs": read_event_logs(limit=8),
        },
    )


@app.get("/sops", response_class=HTMLResponse)
async def sops_page(request: Request, employee_id: str = Depends(current_employee)) -> HTMLResponse:
    docs = [
        d
        for d in accessible_docs(employee_id)
        if "sop" in str(d["metadata"].get("boi_id", "")).lower()
        or "sop" in str(d["metadata"].get("title", "")).lower()
        or "SOP" in (d["metadata"].get("tags") or [])
    ]
    return templates.TemplateResponse(
        "sops.html",
        {
            "request": request,
            "employee_id": employee_id,
            "docs": docs,
        },
    )


@app.get("/docs/{boi_id:path}", response_class=HTMLResponse)
async def doc_page(request: Request, boi_id: str, employee_id: str = Depends(current_employee)) -> HTMLResponse:
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    return templates.TemplateResponse(
        "doc.html",
        {"request": request, "employee_id": employee_id, "doc": doc, "metadata_yaml": yaml.safe_dump(doc["metadata"], allow_unicode=True, sort_keys=False)},
    )


@app.get("/api/boi")
async def list_boi(
    employee_id: str = Depends(current_employee),
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
) -> dict[str, Any]:
    docs = accessible_docs(employee_id)
    if q:
        q_lower = q.lower()
        docs = [d for d in docs if q_lower in json.dumps(d["metadata"], ensure_ascii=False).lower() or q_lower in d["body"].lower()]
    if event_type:
        docs = [d for d in docs if d["metadata"].get("event_type") == event_type]
    if visibility:
        docs = [d for d in docs if d["metadata"].get("visibility") == visibility]
    if boi_type:
        docs = [d for d in docs if d["metadata"].get("type") == boi_type]
    return {"employee_id": employee_id, "teams": teams_for(employee_id), "count": len(docs), "items": docs}


@app.post("/api/boi")
async def create_boi(req: BoiCreate, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    meta = dict(req.metadata)
    meta.setdefault("owner", employee_id)
    meta.setdefault("visibility", "private")
    doc = write_boi(meta, req.body)
    return {"ok": True, "item": doc}


@app.post("/api/boi/{boi_id:path}/promote")
async def promote_boi(boi_id: str, req: PromotionRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    source = find_doc_by_id(boi_id, employee_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source BoI not found or not accessible")
    source_meta = source["metadata"]
    if source_meta.get("visibility") != "private":
        raise HTTPException(status_code=400, detail="Only private BoI can be promoted in this PoC")

    target_visibility = req.target_visibility
    team_id = req.team_id or (teams_for(employee_id)[0] if target_visibility == "team" else None)
    title = source_meta.get("title", "Untitled BoI")
    description = source_meta.get("description", "Promoted BoI draft")
    source_refs = source_meta.get("source_refs") or [
        {"type": "boi", "ref": source_meta.get("boi_id"), "note": "source private BoI; sanitized copy required"}
    ]
    body = (
        "# Summary\n\n"
        + f"이 문서는 Private BoI `{source_meta.get('boi_id')}`에서 사용자의 명시적 요청으로 생성된 공유용 draft입니다.\n\n"
        + "# Shared Content Draft\n\n"
        + source["body"]
        + "\n\n# Promotion Checklist\n\n- [ ] 민감정보 제거 확인\n- [ ] 출처 확인\n- [ ] Owner/Reviewer 확인\n- [ ] Team/Public 공유 적합성 확인\n"
    )
    meta = make_metadata(
        boi_type=source_meta.get("type", "boi/reference"),
        title=f"[공유 Draft] {title}",
        description=description,
        owner=employee_id,
        visibility=target_visibility,
        classification=source_meta.get("classification", "internal"),
        team_id=team_id,
        source_event=source_meta.get("source_event"),
        source_refs=source_refs,
        status="draft",
        tags=list(set((source_meta.get("tags") or []) + ["promoted-draft"])),
        promotion={
            "source_boi_id": source_meta.get("boi_id"),
            "promoted_by": employee_id,
            "promoted_at": now_iso(),
            "promotion_reason": req.promotion_reason,
        },
        reviewer=req.reviewer,
    )
    doc = write_boi(meta, body)
    return {"ok": True, "source": source_meta.get("boi_id"), "target": doc}


@app.post("/api/events/publish")
async def publish_event(req: EventPublishRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    actor = req.actor_employee_id or employee_id
    event = {
        "event_id": f"evt-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "event_type": req.event_type,
        "event_version": "1",
        "occurred_at": now_iso(),
        "producer": "boi-api-web",
        "actor": {"type": "human", "employee_id_hash": actor, "employee_id": actor},
        "visibility_hint": "private",
        "classification_hint": "internal",
        "source_refs": req.source_refs,
        "target": {"flow_key": event_to_flow_key(req.event_type), "boi_type": event_to_boi_type(req.event_type)},
        "event_type_label": event_label(req.event_type),
        "payload": req.payload,
        "trace_id": f"trace-{uuid.uuid4().hex}",
    }
    append_event_log(status="published", event=event)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode())
    await producer.start()
    try:
        await producer.send_and_wait(BOI_EVENTS_TOPIC, event)
    finally:
        await producer.stop()
    return {"ok": True, "topic": BOI_EVENTS_TOPIC, "event": event}


@app.post("/api/workflows/demo/equipment-anomaly/start")
async def start_equipment_anomaly_demo(req: EquipmentAnomalyStartRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    owner = req.owner or employee_id
    result = await publish_event(
        EventPublishRequest(
            event_type="equipment.alarm.raised.v1",
            actor_employee_id=owner,
            payload={
                "title": req.title,
                "equipment_id": req.equipment_id,
                "lot_id": req.lot_id,
                "wafer_id": req.wafer_id,
                "alarm_code": req.alarm_code,
                "owner": owner,
                "workflow": "equipment-anomaly",
            },
            source_refs=[{"type": "demo-workflow", "ref": "equipment-anomaly"}],
        ),
        employee_id=employee_id,
    )
    return {
        "ok": True,
        "workflow": {
            "name": "equipment-anomaly",
            "first_event_type": "equipment.alarm.raised.v1",
            "expected_next": ["root_cause.analysis.requested.v1", "maintenance.guide.requested.v1", "corrective_action.requested.v1"],
        },
        "topic": result["topic"],
        "event": result["event"],
    }


@app.post("/api/webhooks/{source}")
async def inbound_webhook(
    source: str,
    request: Request,
    employee_id: str = Depends(current_employee),
    x_service_token: str | None = Header(None),
) -> dict[str, Any]:
    """Inbound webhook for non-Langflow systems.

    External systems can POST JSON here; the endpoint converts it to a business event and publishes it to Kafka.
    This makes API/Webhook sources first-class Event Producers in the PoC.
    """
    if x_service_token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")
    try:
        incoming = await request.json()
    except Exception:
        incoming = {"payload": (await request.body()).decode("utf-8", errors="replace")}
    event_type = incoming.get("event_type") or "external.webhook.received.v1"
    actor = incoming.get("actor_employee_id") or employee_id
    event = {
        "event_id": f"evt-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "event_type": event_type,
        "event_version": "1",
        "occurred_at": now_iso(),
        "producer": f"webhook:{source}",
        "actor": {"type": "system", "employee_id_hash": actor, "employee_id": actor},
        "visibility_hint": incoming.get("visibility_hint", "private"),
        "classification_hint": incoming.get("classification_hint", "internal"),
        "source_refs": incoming.get("source_refs") or [{"type": "webhook", "ref": source}],
        "target": {"flow_key": event_to_flow_key(event_type), "boi_type": event_to_boi_type(event_type)},
        "event_type_label": event_label(event_type),
        "payload": incoming.get("payload") or incoming,
        "trace_id": incoming.get("trace_id") or f"trace-{uuid.uuid4().hex}",
    }
    append_event_log(status="published", event=event)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode())
    await producer.start()
    try:
        await producer.send_and_wait(BOI_EVENTS_TOPIC, event)
    finally:
        await producer.stop()
    return {"ok": True, "source": source, "topic": BOI_EVENTS_TOPIC, "event": event}


def event_to_flow_key(event_type: str) -> str:
    rec = get_event_type(event_type)
    if rec and rec.get("default_flow_key"):
        return str(rec["default_flow_key"])
    return {
        "meeting.closed.v1": "boi-meeting-writer-v0.1",
        "action.created.v1": "boi-action-writer-v0.1",
        "report.requested.v1": "boi-report-draft-v0.1",
        "promotion.requested.v1": "boi-promotion-v0.1",
        "external.webhook.received.v1": "boi-external-webhook-v0.1",
        "equipment.alarm.raised.v1": "boi-equipment-abnormal-detector-v0.1",
        "trend.anomaly.detected.v1": "boi-root-cause-analysis-v0.1",
        "root_cause.analysis.requested.v1": "boi-root-cause-analysis-v0.1",
        "maintenance.guide.requested.v1": "boi-maintenance-guide-v0.1",
        "corrective_action.requested.v1": "boi-corrective-action-v0.1",
    }.get(event_type, "boi-generic-v0.1")


def event_to_boi_type(event_type: str) -> str:
    rec = get_event_type(event_type)
    if rec and rec.get("default_boi_type"):
        return str(rec["default_boi_type"])
    return "boi/reference"


@app.post("/api/boi/materialize-event", dependencies=[Depends(require_service_token)])
@app.post("/api/boi/from-event", dependencies=[Depends(require_service_token)])
@app.post("/api/boi/materialize-from-event", dependencies=[Depends(require_service_token)])
@app.post("/api/events/handle", dependencies=[Depends(require_service_token)])
async def handle_event(req: EventHandleRequest) -> dict[str, Any]:
    """Materialize a business event into a BoI document.

    This is a first-class BoI Writer connector endpoint used by the Event Router and Action Gateway.
    It is one supported invocation target alongside Langflow, HTTP API, Webhook, MCP bridge, and future connectors.
    """
    event_for_log = req.model_dump()
    append_event_log(status="handling", event=event_for_log)
    actor = (req.actor or {}).get("employee_id") or (req.actor or {}).get("employee_id_hash") or DEMO_EMPLOYEE_ID
    payload = req.payload or {}
    event = {
        "event_id": req.event_id,
        "event_type": req.event_type,
        "occurred_at": req.occurred_at or now_iso(),
    }
    if req.event_type.startswith("meeting.closed"):
        title = payload.get("title") or "회의 정리"
        body = f"""# Summary

`{title}` 회의가 종료되어 Private BoI 초안을 생성했습니다.

# Key Decisions

- PoC 범위는 Agent Harness, BoI Wiki, Langflow BoI 공통 컴포넌트, Kafka Event Broker로 확정합니다.

# Action Items

| Action | Owner | Due | Status |
|---|---|---:|---|
| Langflow BoI 공통 컴포넌트 확인 | {actor} | TBD | Open |
| BoI Wiki Web 접근 검증 | {actor} | TBD | Open |

# Risks / Open Questions

- 사내 SSO/IAM 연계는 PoC 이후 이관 단계에서 확정합니다.

# References

- Event: `{req.event_id}`
"""
        meta = make_metadata(
            boi_type="boi/meeting",
            title=title,
            description="BoI Writer connector가 생성한 회의 Private BoI",
            owner=str(actor),
            source_event=event,
            source_refs=req.source_refs,
            tags=["AIX", "BoIWiki", "Langflow", "Meeting"],
        )
    elif req.event_type.startswith("action.created"):
        title = payload.get("title") or "Action Item"
        body = f"""# Summary

Action Item `{title}`이 생성되었습니다.

# Context

Event Broker를 통해 Action 생성 이벤트가 수신되었고, 담당자 Private BoI로 정리했습니다.

# Action Items

| Action | Owner | Due | Status |
|---|---|---:|---|
| {title} | {actor} | {payload.get('due', 'TBD')} | Open |

# References

- Event: `{req.event_id}`
"""
        meta = make_metadata(
            boi_type="boi/action",
            title=title,
            description="Action Item Private BoI",
            owner=str(actor),
            source_event=event,
            source_refs=req.source_refs,
            tags=["AIX", "Action", "BoIWiki"],
        )
    elif req.event_type.startswith("report.requested"):
        title = payload.get("title") or "주간보고 초안"
        visible = accessible_docs(str(actor))[:5]
        refs_md = "\n".join([f"- {d['metadata'].get('title')} (`{d['metadata'].get('boi_id')}`)" for d in visible]) or "- 참조 가능한 BoI 없음"
        body = f"""# Summary

권한 있는 BoI를 Lazy Loading하여 `{title}` 초안을 생성했습니다.

# Key Messages

- 개인 업무 맥락은 Private BoI에 축적됩니다.
- 명시적 요청과 검토를 거쳐 Team/Public BoI로 승격됩니다.
- Agent나 사람이 Web BoI Wiki에 접속하는 것만으로 SOP와 조직 지식을 활용할 수 있습니다.

# References

{refs_md}
"""
        meta = make_metadata(
            boi_type="boi/report",
            title=title,
            description="권한 기반 BoI 참조로 생성한 보고서 Private Draft",
            owner=str(actor),
            source_event=event,
            source_refs=req.source_refs or [{"type": "boi-search", "ref": d["metadata"].get("boi_id")} for d in visible],
            tags=["AIX", "Report", "BoIWiki"],
        )
    elif req.event_type.startswith(("equipment.alarm.raised", "trend.anomaly.detected", "root_cause.analysis.requested", "maintenance.guide.requested", "corrective_action.requested")):
        title = payload.get("title") or f"SOP Workflow Instance - {event_label(req.event_type)}"
        event_def = get_event_type(req.event_type) or {}
        action_keys = event_def.get("recommended_actions") or []
        actions = [a for a in load_action_catalog() if a.get("action_key") in action_keys]
        action_md = "\n".join([f"- `{a.get('action_key')}`: {a.get('name_ko')} / risk={a.get('risk_level')} / approval_required={a.get('approval_required')}" for a in actions]) or "- 등록된 추천 Action 없음"
        sop_ref = "boi:public:sop:equipment-abnormal-response"
        body = f"""# Summary

첨부 SOP 사례를 AI Native Workflow로 실행하기 위한 Private BoI 인스턴스입니다. Event Broker가 `{req.event_type}` 이벤트를 수신했고, Harness는 SOP 단계에 맞춰 필요한 API/Webhook Action 후보와 참조 BoI를 정리했습니다.

# SOP Stage

- Event Label: {event_label(req.event_type)}
- Workflow Stage: {event_def.get('workflow_stage', 'SOP Workflow')}
- Default Flow: {event_def.get('default_flow_key', event_to_flow_key(req.event_type))}
- SOP Reference: `{sop_ref}`

# Payload

```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```

# Recommended Actions

{action_md}

# AI Native Workflow Interpretation

1. Event Broker는 업무 시점, 예: 설비 Alarm 발생 또는 Trend 이상 감지를 발행합니다.
2. Langflow/Webhook/API Agent는 BoI Wiki에서 SOP와 관련 Runbook을 Lazy Loading합니다.
3. Agent는 필요한 데이터 조회 Action을 Action Gateway를 통해 호출합니다.
4. 분석 결과는 Private BoI로 남기고, 팀 재사용 가치가 있으면 명시적 요청으로 Team BoI draft 승격합니다.
5. 공정 진행 금지, Spec/Rule 변경 같은 고위험 Action은 자동 실행하지 않고 승인 필요 상태로만 기록합니다.

# References

- Source Event: `{req.event_id}`
- SOP: `{sop_ref}`
"""
        meta = make_metadata(
            boi_type=event_to_boi_type(req.event_type),
            title=title,
            description="SOP 기반 AI Native Workflow 실행 인스턴스",
            owner=str(actor),
            source_event=event,
            source_refs=req.source_refs or [{"type": "boi", "ref": sop_ref}],
            tags=["SOP", "AI-Native-Workflow", "EventBroker", "ActionGateway", "BoIWiki"],
        )
        meta["workflow_stage"] = event_def.get("workflow_stage")
        meta["recommended_actions"] = action_keys
    else:
        title = payload.get("title") or req.event_type
        body = f"# Summary\n\n이벤트 `{req.event_type}`에서 생성된 Generic Private BoI입니다.\n\n# Payload\n\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```\n"
        meta = make_metadata(
            boi_type="boi/reference",
            title=title,
            description="Generic event BoI",
            owner=str(actor),
            source_event=event,
            source_refs=req.source_refs,
        )
    doc = write_boi(meta, body)
    append_event_log(status="handled", event=event_for_log, result={"boi_id": doc["metadata"].get("boi_id"), "boi_uri": doc.get("uri")})
    return {"ok": True, "handled_by": "boi-writer-connector", "item": doc}


@app.get("/event-types", response_class=HTMLResponse)
async def event_types_page(request: Request, employee_id: str = Depends(current_employee)) -> HTMLResponse:
    types = load_event_types()
    counts = {t["event_type"]: 0 for t in types}
    for d in accessible_docs(employee_id):
        et = d["metadata"].get("event_type")
        if et in counts:
            counts[et] += 1
    return templates.TemplateResponse(
        "event_types.html",
        {"request": request, "employee_id": employee_id, "event_types": types, "counts": counts},
    )


@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, employee_id: str = Depends(current_employee), event_type: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "employee_id": employee_id,
            "event_type": event_type,
            "event_types": load_event_types(),
            "events": read_event_logs(limit=200, event_type=event_type or None),
        },
    )


@app.get("/api/event-types")
async def api_event_types() -> dict[str, Any]:
    return {"items": load_event_types()}


@app.get("/api/events/log")
async def api_event_logs(event_type: str = "", limit: int = 200) -> dict[str, Any]:
    return {"count": len(read_event_logs(limit=limit, event_type=event_type or None)), "items": read_event_logs(limit=limit, event_type=event_type or None)}


@app.post("/api/events/audit", dependencies=[Depends(require_service_token)])
async def api_event_audit(req: EventAuditRequest) -> dict[str, Any]:
    append_event_log(status=req.status, event=req.event, result=req.result, error=req.error)
    return {"ok": True}


@app.get("/actions", response_class=HTMLResponse)
async def actions_page(request: Request, employee_id: str = Depends(current_employee), event_type: str = "") -> HTMLResponse:
    actions = load_action_catalog()
    if event_type:
        actions = [a for a in actions if event_type in (a.get("event_types") or [])]
    return templates.TemplateResponse(
        "actions.html",
        {
            "request": request,
            "employee_id": employee_id,
            "event_type": event_type,
            "event_types": load_event_types(),
            "actions": actions,
            "action_logs": read_action_logs(limit=100),
        },
    )


@app.get("/api/actions/catalog")
async def api_action_catalog(event_type: str = "") -> dict[str, Any]:
    actions = load_action_catalog()
    if event_type:
        actions = [a for a in actions if event_type in (a.get("event_types") or [])]
    return {"count": len(actions), "items": actions}


@app.get("/api/actions/logs")
async def api_action_logs(action_key: str = "", limit: int = 200) -> dict[str, Any]:
    rows = read_action_logs(limit=limit, action_key=action_key or None)
    return {"count": len(rows), "items": rows}


@app.post("/api/actions/invoke")
async def api_action_invoke(req: ActionInvokeRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    payload = req.model_dump()
    payload["employee_id"] = req.employee_id or employee_id
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{ACTION_GATEWAY_URL.rstrip('/')}/api/actions/invoke",
            headers={"x-service-token": SERVICE_TOKEN},
            json=payload,
        )
        try:
            body = resp.json()
        except Exception:
            body = {"text": resp.text}
        if resp.status_code >= 400:
            raise HTTPException(status_code=resp.status_code, detail=body)
        return body


@app.get("/api/users")
async def users() -> dict[str, Any]:
    return {"users": [{"employee_id": k, "name": USER_NAMES.get(k), "teams": v} for k, v in USER_TEAMS.items()]}
