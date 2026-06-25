from __future__ import annotations

import asyncio
import ast
import copy
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
import httpx
from datetime import date, datetime, timezone, timedelta
from html import escape as html_escape, unescape as html_unescape
from pathlib import Path
from typing import Any, Callable, Literal
from urllib.parse import parse_qs, quote, urlencode, urlsplit, unquote

import yaml
from aiokafka import AIOKafkaProducer
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from pydantic import BaseModel, Field

from .okf import (
    ALLOWED_MEDIA_EXTENSIONS,
    REQUIRED_FIELDS,
    iter_jsonl_rows,
    iter_materialized_items,
    markdown_link_edges,
    lint_data_root,
    resolve_okf_media_path,
    resolve_okf_link,
    validate_okf_metadata,
)
from .workflow_materializer import (
    build_enriched_body,
    sanitize_stage_analysis_message,
    render_stage_execution_body,
)
from .simulation_agent import build_simulation_agent_result
from .native_agent import LANGGRAPH_AVAILABLE, NativeAgentConfig, NativeAgentRuntimeUnavailable, NativeAgentTools, NativeBoiAgent
from .access_policy import CLASSIFICATION_POLICY_VERSION, AccessPolicyDecision, doc_access_policy
from .auth import (
    AuthError,
    AuthIdentity,
    DEFAULT_USER_NAMES as USER_NAMES,
    DEFAULT_USER_TEAMS as USER_TEAMS,
    OIDC_STATE_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    auth_mode,
    create_oidc_state,
    create_session_token,
    decode_keycloak_bearer,
    decode_oidc_state,
    dev_identity,
    exchange_keycloak_code,
    has_role,
    identity_from_claims,
    keycloak_authorization_url,
    keycloak_logout_url,
    name_for_employee,
    require_role,
    resolve_identity,
    service_identity,
    teams_for_employee,
)

KST = timezone(timedelta(hours=9))


def resolve_router_llm_enabled(raw_value: str | None, mode: str, base_url: str) -> bool:
    raw = str(raw_value if raw_value is not None else "auto").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return (
        raw in {"", "auto"}
        and str(mode or "") == "llm_first"
        and bool(str(base_url or "").strip())
        and "llm-gateway.example" not in str(base_url or "")
    )


LLM_PLACEHOLDER_MARKERS = ("llm-gateway.example",)
LLM_API_KEY_PLACEHOLDERS = {"", "not-needed", "boi-router-dummy-key"}


def inherit_llm_env_value(raw_value: str | None, fallback: str, *, secret: bool = False) -> str:
    """Use a specific LLM env value unless it is an example placeholder.

    Docker Compose often injects example defaults even when the application code
    would otherwise inherit from the router LLM settings.  Treat those example
    values as absent so secondary Agent components do not silently disable
    themselves while the Router is correctly configured.
    """
    value = str(raw_value or "").strip()
    fallback_value = str(fallback or "").strip()
    if not value:
        return fallback_value
    if secret:
        if value in LLM_API_KEY_PLACEHOLDERS and fallback_value and fallback_value not in LLM_API_KEY_PLACEHOLDERS:
            return fallback_value
        return value
    if any(marker in value for marker in LLM_PLACEHOLDER_MARKERS) and fallback_value and not any(
        marker in fallback_value for marker in LLM_PLACEHOLDER_MARKERS
    ):
        return fallback_value
    return value


APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("DATA_ROOT", "/data/boi"))
EVENTS_ROOT = Path(os.getenv("EVENTS_ROOT", "/data/events"))
EVENT_CATALOG_ROOT = Path(os.getenv("EVENT_CATALOG_ROOT", "/data/event_catalog"))
ACTION_CATALOG_ROOT = Path(os.getenv("ACTION_CATALOG_ROOT", "/data/action_catalog"))
ACTION_LOG_ROOT = Path(os.getenv("ACTION_LOG_ROOT", "/data/actions"))
DRAFT_ROOT = Path(os.getenv("DRAFT_ROOT", str(DATA_ROOT.parent / "drafts")))
ACTIVITY_ROOT = Path(os.getenv("ACTIVITY_ROOT", str(DATA_ROOT.parent / "activity")))
RBAC_ROOT = Path(os.getenv("RBAC_ROOT", str(DATA_ROOT.parent / "rbac")))
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100")
ACTION_INVOKE_TIMEOUT_SECONDS = float(os.getenv("ACTION_INVOKE_TIMEOUT_SECONDS", "90"))
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
DEFAULT_TEAM_ID = os.getenv("DEFAULT_TEAM_ID", "aix-tf")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
BOI_EVENTS_TOPIC = os.getenv("BOI_EVENTS_TOPIC", "boi.events")
DEMO_EMPLOYEE_ID = os.getenv("DEMO_EMPLOYEE_ID", "100001")
BOI_LLM_BASE_URL = os.getenv("BOI_LLM_BASE_URL", "http://llm-gateway.example:1236/v1").rstrip("/")
BOI_LLM_MODEL = os.getenv("BOI_LLM_MODEL", "google/gemma-4-26b-a4b-qat")
BOI_LLM_API_KEY = os.getenv("BOI_LLM_API_KEY", "not-needed")
BOI_AGENT_ROUTER_MODE = os.getenv("BOI_AGENT_ROUTER_MODE", "llm_first")
BOI_AGENT_ROUTER_BASE_URL = os.getenv("BOI_AGENT_ROUTER_BASE_URL", BOI_LLM_BASE_URL).rstrip("/")
BOI_AGENT_ROUTER_API_KEY = os.getenv("BOI_AGENT_ROUTER_API_KEY", BOI_LLM_API_KEY)
BOI_AGENT_ROUTER_MODEL = os.getenv("BOI_AGENT_ROUTER_MODEL", BOI_LLM_MODEL)
BOI_AGENT_ROUTER_LLM_ENABLED_RAW = os.getenv("BOI_AGENT_ROUTER_LLM_ENABLED", "auto").strip().lower()
BOI_AGENT_ROUTER_LLM_ENABLED = resolve_router_llm_enabled(
    BOI_AGENT_ROUTER_LLM_ENABLED_RAW,
    BOI_AGENT_ROUTER_MODE,
    BOI_AGENT_ROUTER_BASE_URL,
)
# Router/status/composer/suggestions are user-facing Agent quality contracts.
# The env names remain for older compose files/docs, but production policy is
# intentionally not downgradeable: if the configured LLM cannot produce these
# fields, the Agent is unhealthy rather than silently falling back to canned
# copy or deterministic routing.
BOI_AGENT_ROUTER_REQUIRED = True
BOI_AGENT_ROUTER_TIMEOUT_SECONDS = float(os.getenv("BOI_AGENT_ROUTER_TIMEOUT_SECONDS", "12"))
BOI_AGENT_ROUTER_FAILURE_BACKOFF_SECONDS = float(os.getenv("BOI_AGENT_ROUTER_FAILURE_BACKOFF_SECONDS", "30"))
BOI_AGENT_ROUTER_MAX_TOKENS = int(os.getenv("BOI_AGENT_ROUTER_MAX_TOKENS", "1536"))
BOI_AGENT_ROUTER_CONFIDENCE_THRESHOLD = float(os.getenv("BOI_AGENT_ROUTER_CONFIDENCE_THRESHOLD", "0.7"))
BOI_AGENT_STATUS_BASE_URL = os.getenv("BOI_AGENT_STATUS_BASE_URL", BOI_AGENT_ROUTER_BASE_URL).rstrip("/")
BOI_AGENT_STATUS_API_KEY = os.getenv("BOI_AGENT_STATUS_API_KEY", BOI_AGENT_ROUTER_API_KEY)
BOI_AGENT_STATUS_MODEL = os.getenv("BOI_AGENT_STATUS_MODEL", BOI_AGENT_ROUTER_MODEL)
BOI_AGENT_STATUS_LLM_ENABLED_RAW = os.getenv("BOI_AGENT_STATUS_LLM_ENABLED", BOI_AGENT_ROUTER_LLM_ENABLED_RAW).strip().lower()
BOI_AGENT_STATUS_LLM_ENABLED = resolve_router_llm_enabled(
    BOI_AGENT_STATUS_LLM_ENABLED_RAW,
    "llm_first",
    BOI_AGENT_STATUS_BASE_URL,
)
BOI_AGENT_STATUS_TIMEOUT_SECONDS = float(os.getenv("BOI_AGENT_STATUS_TIMEOUT_SECONDS", "30"))
BOI_AGENT_STATUS_MAX_TOKENS = int(os.getenv("BOI_AGENT_STATUS_MAX_TOKENS", "1536"))
# Status text is part of the user-facing Agent contract.  The env name is kept
# for older compose files/docs, but runtime policy is intentionally not
# downgradeable: if the stream planner cannot generate status text, the Agent is
# unhealthy instead of falling back to canned copy.
BOI_AGENT_STATUS_REQUIRED = True
BOI_AGENT_SUGGESTIONS_BASE_URL = inherit_llm_env_value(os.getenv("BOI_AGENT_SUGGESTIONS_BASE_URL"), BOI_AGENT_ROUTER_BASE_URL).rstrip("/")
BOI_AGENT_SUGGESTIONS_API_KEY = inherit_llm_env_value(os.getenv("BOI_AGENT_SUGGESTIONS_API_KEY"), BOI_AGENT_ROUTER_API_KEY, secret=True)
BOI_AGENT_SUGGESTIONS_MODEL = inherit_llm_env_value(os.getenv("BOI_AGENT_SUGGESTIONS_MODEL"), BOI_AGENT_ROUTER_MODEL)
BOI_AGENT_SUGGESTIONS_LLM_ENABLED_RAW = os.getenv("BOI_AGENT_SUGGESTIONS_LLM_ENABLED", BOI_AGENT_ROUTER_LLM_ENABLED_RAW).strip().lower()
BOI_AGENT_SUGGESTIONS_LLM_ENABLED = resolve_router_llm_enabled(
    BOI_AGENT_SUGGESTIONS_LLM_ENABLED_RAW,
    "llm_first",
    BOI_AGENT_SUGGESTIONS_BASE_URL,
)
BOI_AGENT_SUGGESTIONS_REQUIRED = True
BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS = float(os.getenv("BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS", "8"))
BOI_AGENT_SUGGESTIONS_MAX_TOKENS = int(os.getenv("BOI_AGENT_SUGGESTIONS_MAX_TOKENS", "1024"))
BOI_AGENT_COMPOSER_BASE_URL = os.getenv("BOI_AGENT_COMPOSER_BASE_URL", BOI_AGENT_ROUTER_BASE_URL).rstrip("/")
BOI_AGENT_COMPOSER_API_KEY = os.getenv("BOI_AGENT_COMPOSER_API_KEY", BOI_AGENT_ROUTER_API_KEY)
BOI_AGENT_COMPOSER_MODEL = os.getenv("BOI_AGENT_COMPOSER_MODEL", BOI_AGENT_ROUTER_MODEL)
BOI_AGENT_COMPOSER_LLM_ENABLED_RAW = os.getenv("BOI_AGENT_COMPOSER_LLM_ENABLED", BOI_AGENT_ROUTER_LLM_ENABLED_RAW).strip().lower()
BOI_AGENT_COMPOSER_LLM_ENABLED = resolve_router_llm_enabled(
    BOI_AGENT_COMPOSER_LLM_ENABLED_RAW,
    "llm_first",
    BOI_AGENT_COMPOSER_BASE_URL,
)
BOI_AGENT_COMPOSER_REQUIRED = True
BOI_AGENT_COMPOSER_TIMEOUT_SECONDS = float(os.getenv("BOI_AGENT_COMPOSER_TIMEOUT_SECONDS", "20"))
BOI_AGENT_COMPOSER_MAX_TOKENS = min(int(os.getenv("BOI_AGENT_COMPOSER_MAX_TOKENS", "1536")), 1536)
BOI_AGENT_BACKEND = os.getenv("BOI_AGENT_BACKEND", "native").strip().lower()
BOI_AGENT_NATIVE_MAX_TOOL_LOOPS = int(os.getenv("BOI_AGENT_NATIVE_MAX_TOOL_LOOPS", "5"))
BOI_AGENT_NATIVE_TOOL_TIMEOUT_SECONDS = float(os.getenv("BOI_AGENT_NATIVE_TOOL_TIMEOUT_SECONDS", "8"))
BOI_AGENT_LANGGRAPH_REQUIRED = os.getenv("BOI_AGENT_LANGGRAPH_REQUIRED", "1").strip().lower() not in {"0", "false", "no", "off"}
BOI_AGENT_CHAT_TIMEOUT_SECONDS = float(os.getenv("BOI_AGENT_CHAT_TIMEOUT_SECONDS", "45"))
BOI_AGENT_STREAM_HEARTBEAT_SECONDS = float(os.getenv("BOI_AGENT_STREAM_HEARTBEAT_SECONDS", "2"))
BOI_AGENT_CACHE_WARMUP_ON_STARTUP = os.getenv("BOI_AGENT_CACHE_WARMUP_ON_STARTUP", "1").strip().lower() not in {"0", "false", "no", "off"}
BOI_BUILD_REVISION = os.getenv("BOI_BUILD_REVISION") or os.getenv("GIT_COMMIT") or "unknown"
LANGFLOW_URL = os.getenv("LANGFLOW_URL", "http://langflow:7860").rstrip("/")
LANGFLOW_API_KEY = os.getenv("LANGFLOW_API_KEY", "dev-langflow-key-change-me")
LANGFLOW_AUTH_MODE = os.getenv("LANGFLOW_AUTH_MODE", "api-key")
LANGFLOW_BOI_AGENT_ENDPOINT = os.getenv("LANGFLOW_BOI_AGENT_ENDPOINT", "boi-agent")
LANGFLOW_AGENT_TIMEOUT_SECONDS = float(os.getenv("LANGFLOW_AGENT_TIMEOUT_SECONDS", "120"))
KAFKA_PUBLISH_TIMEOUT_SECONDS = float(os.getenv("BOI_KAFKA_PUBLISH_TIMEOUT_SECONDS", "20"))
_BOI_AGENT_ROUTER_BACKOFF_UNTIL = 0.0
_BOI_AGENT_ROUTER_BACKOFF_REASON = ""

LOCALHOST_NAMES = {"localhost", "127.0.0.1", "::1", "testserver"}
DEFAULT_EXTERNAL_TOOL_PORTS = {
    "ACTION_GATEWAY_EXTERNAL_URL": 28100,
    "LANGFLOW_EXTERNAL_URL": 27860,
    "KAFKA_UI_EXTERNAL_URL": 28081,
    "BOI_WIKI_MCP_EXTERNAL_URL": 28200,
}

# Development fallback user/team maps. In SSO modes, Keycloak/HCP identity
# resolves teams and roles and these maps are only used for local compatibility.

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
        "wiki_usage": "회의 종료 후 Private BoI를 만들고, 공유 가치가 있으면 사용자 승인과 자동 검증 후 Team BoI로 게시",
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
        "description": "사용자가 Private BoI 또는 Local promotion candidate를 Team/Public로 게시하라고 명시적으로 승인한 시점",
        "default_boi_type": "boi/reference",
        "default_flow_key": "boi-promotion-v0.1",
        "default_visibility": "team",
        "owner": "AIX 확산 TF",
        "status": "poc",
        "topic": "boi.events",
        "wiki_usage": "Private 원본은 유지하고 공유용 사본을 사용자 승인/자동 검증 후 게시하며 HOTL 상태로 추적",
    },
]

app = FastAPI(title="BoI Wiki", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))


def asset_url(path: str) -> str:
    clean_path = str(path or "").lstrip("/")
    return f"/static/{clean_path}?v={quote(BOI_BUILD_REVISION)}"


templates.env.globals["asset_url"] = asset_url

_EVENT_TYPES_CACHE: dict[str, Any] = {"signature": None, "items": []}
_ACTION_CATALOG_CACHE: dict[str, Any] = {"signature": None, "items": []}
_DOCS_CACHE: dict[str, Any] = {"signature": None, "docs": []}
_DOC_INDEX_CACHE: dict[str, Any] = {"signature": None, "by_ref": {}}
_WORKFLOW_DOCS_CACHE: dict[str, Any] = {"signature": None, "docs": []}
_EVENT_LOG_CACHE: dict[str, Any] = {"signature": None, "rows": []}
_ACTION_LOG_CACHE: dict[str, Any] = {"signature": None, "rows": []}
_RECOVERED_DOC_CACHE: dict[str, Any] = {"signature": None, "by_boi_id": {}, "by_uri": {}}
_FILE_SIGNATURE_CACHE: dict[str, tuple[float, tuple[tuple[str, int, int], ...]]] = {}
_DOC_BODY_HTML_CACHE: dict[tuple[Any, ...], Markup] = {}
_OKF_GRAPH_INDEX_CACHE: dict[str, Any] = {"signature": None, "by_employee": {}}
_SEARCH_INDEX_CACHE: dict[str, Any] = {"signature": None, "by_employee": {}}
_AGENT_CACHE_WARMUP_LOCK = threading.Lock()
_AGENT_CACHE_WARMUP_STATE: dict[str, Any] = {
    "enabled": BOI_AGENT_CACHE_WARMUP_ON_STARTUP,
    "status": "not_started",
    "employee_id": "",
    "started_at": "",
    "completed_at": "",
    "elapsed_ms": 0,
    "checks": {},
    "error": "",
}
MARKDOWN_RENDERER_VERSION = "2026-06-22-doc-detail-lazy-v1"
SIGNATURE_TTL_SECONDS = 1.0
_ENSURE_DIRS_READY = False
_RBAC_STATE_CACHE: dict[str, Any] = {"signature": None, "state": None}


def now_iso() -> str:
    return datetime.now(KST).replace(microsecond=0).isoformat()


def employee_hash(employee_id: str) -> str:
    return hashlib.sha256(employee_id.encode()).hexdigest()[:12]


def safe_filename(value: str) -> str:
    value = value.replace(":", "-").replace("/", "-")
    value = re.sub(r"[^A-Za-z0-9_.-]", "-", value)
    return value[:160] or f"boi-{uuid.uuid4().hex}"


def ensure_dirs() -> None:
    global _ENSURE_DIRS_READY
    if _ENSURE_DIRS_READY:
        return
    for sub in ["public", f"team/{DEFAULT_TEAM_ID}", "team/platform"]:
        (DATA_ROOT / sub).mkdir(parents=True, exist_ok=True)
    for employee_id in USER_TEAMS:
        (DATA_ROOT / "private" / employee_id).mkdir(parents=True, exist_ok=True)
    EVENTS_ROOT.mkdir(parents=True, exist_ok=True)
    EVENT_CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    ACTION_CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    ACTION_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    ACTIVITY_ROOT.mkdir(parents=True, exist_ok=True)
    RBAC_ROOT.mkdir(parents=True, exist_ok=True)
    (DRAFT_ROOT / "sop_packages").mkdir(parents=True, exist_ok=True)
    (DRAFT_ROOT / "action_packages").mkdir(parents=True, exist_ok=True)
    (DRAFT_ROOT / "promotions").mkdir(parents=True, exist_ok=True)
    (DRAFT_ROOT / "event_type_drafts").mkdir(parents=True, exist_ok=True)
    _ENSURE_DIRS_READY = True


def file_signature(paths: list[Path]) -> tuple[tuple[str, int, int], ...]:
    signature: list[tuple[str, int, int]] = []
    for path in paths:
        try:
            stat = path.stat()
        except OSError:
            continue
        signature.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(sorted(signature))


def cached_signature(key: str, compute: Any) -> tuple[tuple[str, int, int], ...]:
    now = time.monotonic()
    cached = _FILE_SIGNATURE_CACHE.get(key)
    if cached and cached[0] > now:
        return cached[1]
    signature = compute()
    _FILE_SIGNATURE_CACHE[key] = (now + SIGNATURE_TTL_SECONDS, signature)
    return signature


def glob_signature(root: Path, pattern: str) -> tuple[tuple[str, int, int], ...]:
    if not root.exists():
        return ()
    return cached_signature(f"glob:{root}:{pattern}", lambda: file_signature(sorted(root.glob(pattern))))


def markdown_signature() -> tuple[tuple[str, int, int], ...]:
    if not DATA_ROOT.exists():
        return ()
    return cached_signature(f"markdown:{DATA_ROOT}", lambda: file_signature(sorted(DATA_ROOT.rglob("*.md"))))


def materialized_log_signature() -> tuple[tuple[str, int, int], ...]:
    return file_signature(materialized_log_paths())


def invalidate_doc_caches() -> None:
    _FILE_SIGNATURE_CACHE.clear()
    _DOCS_CACHE["signature"] = None
    _DOCS_CACHE["docs"] = []
    _DOC_INDEX_CACHE["signature"] = None
    _DOC_INDEX_CACHE["by_ref"] = {}
    _WORKFLOW_DOCS_CACHE["signature"] = None
    _WORKFLOW_DOCS_CACHE["docs"] = []
    _DOC_BODY_HTML_CACHE.clear()
    _OKF_GRAPH_CACHE.clear()
    _OKF_GRAPH_INDEX_CACHE["signature"] = None
    _OKF_GRAPH_INDEX_CACHE["by_employee"] = {}
    _SEARCH_INDEX_CACHE["signature"] = None
    _SEARCH_INDEX_CACHE["by_employee"] = {}


def invalidate_catalog_caches() -> None:
    _FILE_SIGNATURE_CACHE.clear()
    _EVENT_TYPES_CACHE["signature"] = None
    _EVENT_TYPES_CACHE["items"] = []
    _ACTION_CATALOG_CACHE["signature"] = None
    _ACTION_CATALOG_CACHE["items"] = []
    _SEARCH_INDEX_CACHE["signature"] = None
    _SEARCH_INDEX_CACHE["by_employee"] = {}


def invalidate_event_log_caches() -> None:
    _FILE_SIGNATURE_CACHE.clear()
    _EVENT_LOG_CACHE["signature"] = None
    _EVENT_LOG_CACHE["rows"] = []
    _RECOVERED_DOC_CACHE["signature"] = None


def invalidate_action_log_caches() -> None:
    _FILE_SIGNATURE_CACHE.clear()
    _ACTION_LOG_CACHE["signature"] = None
    _ACTION_LOG_CACHE["rows"] = []
    _RECOVERED_DOC_CACHE["signature"] = None


def split_frontmatter(markdown: str) -> tuple[dict[str, Any], str]:
    if markdown.startswith("---"):
        parts = markdown.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            return meta, parts[2].lstrip("\n")
    return {}, markdown


def compose_markdown(metadata: dict[str, Any], body: str) -> str:
    return "---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---\n\n" + body.lstrip("\n")


def parse_structured_string(value: str) -> Any:
    stripped = value.strip()
    if len(stripped) < 2 or stripped[0] not in "[{" or stripped[-1] not in "]}":
        return value
    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(stripped)
        except Exception:
            continue
        if isinstance(parsed, (dict, list)):
            return parsed
    return value


def is_markdown_like(value: str) -> bool:
    stripped = value.strip()
    return (
        stripped.startswith("#")
        or "```" in stripped
        or bool(re.search(r"(^|\n)\s*[-*]\s+\S", stripped))
        or bool(re.search(r"(^|\n)\s*\d+\.\s+\S", stripped))
        or bool(re.search(r"(^|\n)\s*\|.+\|\s*(\n|$)", stripped))
    )


def normalized_doc_lookup_keys(ref: str) -> list[str]:
    raw = str(ref or "").strip()
    if not raw:
        return []
    keys = [raw, raw.lstrip("/")]
    if raw.endswith(".md"):
        keys.append(raw[:-3])
        keys.append(raw.lstrip("/")[:-3])
    return list(dict.fromkeys(key for key in keys if key))


def build_doc_lookup(docs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for doc in docs:
        metadata = doc.get("metadata") or {}
        candidates = [
            str(metadata.get("boi_id") or ""),
            str(doc.get("uri") or ""),
        ]
        path_value = str(doc.get("path") or "")
        if path_value:
            try:
                candidates.append(str(Path(path_value).relative_to(DATA_ROOT)).replace("\\", "/"))
            except Exception:
                pass
        for candidate in candidates:
            for key in normalized_doc_lookup_keys(candidate):
                lookup.setdefault(key, doc)
    return lookup


def doc_from_lookup(ref: str, doc_lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, Any] | None:
    if not doc_lookup:
        return None
    for key in normalized_doc_lookup_keys(ref):
        doc = doc_lookup.get(key)
        if doc:
            return doc
    return None


def direct_doc_candidate_paths(ref: str) -> list[Path]:
    raw = str(ref or "").strip().lstrip("/")
    if not raw:
        return []
    candidates: list[Path] = []
    concept = raw[:-3] if raw.endswith(".md") else raw
    if raw.startswith(("public/", "team/", "private/")):
        candidates.append(DATA_ROOT / (raw if raw.endswith(".md") else f"{raw}.md"))
    if raw.startswith("boi:"):
        parts = raw.split(":")
        if len(parts) >= 2:
            visibility = parts[1]
            tail = parts[2:]
            if visibility == "public" and tail:
                candidates.append(DATA_ROOT / "public" / ("/".join(tail) + ".md"))
                if len(tail) >= 2:
                    candidates.append(DATA_ROOT / "public" / "/".join(tail[:-1]) / (tail[-1].replace("_", "-") + ".md"))
            elif visibility == "team" and len(tail) >= 2:
                candidates.append(DATA_ROOT / "team" / tail[0] / ("/".join(tail[1:]) + ".md"))
                if len(tail) >= 3:
                    candidates.append(DATA_ROOT / "team" / tail[0] / "/".join(tail[1:-1]) / (tail[-1].replace("_", "-") + ".md"))
            elif visibility == "private" and len(tail) >= 3:
                employee_id, timestamp, suffix = tail[0], tail[1], tail[2]
                candidates.append(DATA_ROOT / "private" / employee_id / f"boi-private-{employee_id}-{timestamp}-{suffix}.md")
                candidates.append(DATA_ROOT / "private" / employee_id / ("/".join(tail[1:]) + ".md"))
    if concept.startswith(("public/", "team/", "private/")):
        candidates.append(DATA_ROOT / f"{concept}.md")
    seen: set[Path] = set()
    result: list[Path] = []
    for path in candidates:
        normalized = path.resolve() if path.exists() else path
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(path)
    return result


def doc_index_ref_candidates(path: Path, metadata: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    try:
        rel = str(path.relative_to(DATA_ROOT)).replace("\\", "/")
    except ValueError:
        rel = ""
    if rel:
        candidates.extend([rel, "/" + rel])
        if rel.endswith(".md"):
            candidates.extend([rel[:-3], "/" + rel[:-3]])
    boi_id = str(metadata.get("boi_id") or "")
    if boi_id:
        candidates.append(boi_id)
    return candidates


def doc_index_by_ref() -> dict[str, Path]:
    ensure_dirs()
    signature = markdown_signature()
    if _DOC_INDEX_CACHE["signature"] == signature:
        return _DOC_INDEX_CACHE["by_ref"]
    by_ref: dict[str, Path] = {}
    for path in all_markdown_files():
        try:
            metadata, _body = split_frontmatter(path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}
        for candidate in doc_index_ref_candidates(path, metadata):
            for key in normalized_doc_lookup_keys(candidate):
                by_ref.setdefault(key, path)
    _DOC_INDEX_CACHE["signature"] = signature
    _DOC_INDEX_CACHE["by_ref"] = by_ref
    return by_ref


def find_doc_path_by_ref(ref: str) -> Path | None:
    raw = str(ref or "").strip()
    normalized_uri = raw.lstrip("/")
    normalized_concept_id = normalized_uri[:-3] if normalized_uri.endswith(".md") else normalized_uri
    for path in direct_doc_candidate_paths(raw):
        if path.exists():
            return path
    index = doc_index_by_ref()
    for key in normalized_doc_lookup_keys(raw) + normalized_doc_lookup_keys(normalized_concept_id):
        path = index.get(key)
        if path:
            return path
    return None


def is_generated_private_doc(doc: dict[str, Any]) -> bool:
    metadata = doc.get("metadata") or {}
    author = metadata.get("author") if isinstance(metadata.get("author"), dict) else {}
    path = Path(str(doc.get("path") or ""))
    try:
        path_parts = path.relative_to(DATA_ROOT).parts
    except Exception:
        path_parts = path.parts
    path_generated = (
        len(path_parts) >= 3
        and path_parts[0] == "private"
        and path.name.startswith(f"boi-private-{path_parts[1]}-")
        and path.suffix.lower() == ".md"
    )
    source_event = metadata.get("source_event") if isinstance(metadata.get("source_event"), dict) else {}
    return (
        metadata.get("visibility") == "private"
        and len(path_parts) >= 2
        and path_parts[0] == "private"
        and (
            str(author.get("agent_id") or "").startswith("boi-writer")
            or path_generated
            or bool(source_event.get("trace") or source_event.get("trace_id"))
            or str(metadata.get("boi_id") or "").startswith(f"boi:private:{path_parts[1]}:")
        )
    )


MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)")
APP_ROUTE_LINK_PREFIXES = ("/docs", "/events", "/actions", "/api", "/workflows", "/source", "/okf-media")


def is_app_route_href(href: str) -> bool:
    return str(href or "").startswith(APP_ROUTE_LINK_PREFIXES)


def referenced_doc_lookup_for_doc(doc: dict[str, Any], employee_id: str) -> dict[str, dict[str, Any]]:
    lookup = build_doc_lookup([doc])
    source_path = Path(str(doc.get("path") or ""))
    refs: set[str] = set()
    if source_path.exists():
        for match in MARKDOWN_LINK_RE.finditer(str(doc.get("body") or "")):
            href = match.group(1)
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#"):
                continue
            if is_app_route_href(href):
                continue
            target, _resolved = resolve_okf_link(href, source_path=source_path, boi_root=DATA_ROOT)
            refs.add(target)
    for item in doc.get("metadata", {}).get("source_refs") or []:
        if isinstance(item, dict):
            ref = str(item.get("uri") or item.get("ref") or "")
            if ref and not ref.startswith(("http://", "https://")):
                refs.add(ref)
    for ref in sorted(refs):
        path = find_doc_path_by_ref(ref)
        if not path:
            continue
        try:
            linked_doc = read_doc(path)
        except Exception:
            continue
        if is_accessible(linked_doc, employee_id):
            lookup.update(build_doc_lookup([linked_doc]))
    return lookup


def markdown_href_for_doc_route(
    href: str,
    employee_id: str,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#"):
        return href
    if is_app_route_href(href):
        return href
    lookup_ref = href
    if source_path is not None:
        target, _resolved = resolve_okf_link(href, source_path=source_path, boi_root=DATA_ROOT)
        lookup_ref = target
    elif href.startswith("/"):
        lookup_ref = href.lstrip("/")
        if lookup_ref.endswith(".md"):
            lookup_ref = lookup_ref[:-3]
    doc = doc_from_lookup(lookup_ref, doc_lookup)
    if doc is None and doc_lookup is None:
        doc = find_doc_by_id(lookup_ref, employee_id)
    if doc:
        return doc_url_for_ref(str(doc["metadata"].get("boi_id") or doc["uri"].lstrip("/")), employee_id)
    return href


def markdown_media_url_for_doc_route(href: str, source_path: Path | None = None) -> str:
    if source_path is None:
        return ""
    target_path, error = resolve_okf_media_path(href, source_path=source_path, boi_root=DATA_ROOT)
    if error or target_path is None or not target_path.exists():
        return ""
    try:
        rel_path = str(target_path.relative_to(DATA_ROOT)).replace("\\", "/")
    except ValueError:
        return ""
    return "/okf-media/" + quote(rel_path)


def render_inline_markdown(
    value: str,
    employee_id: str | None = None,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    tokens: list[tuple[str, str]] = []

    def stash(html: str) -> str:
        token = f"@@BOI_MARKDOWN_TOKEN_{len(tokens)}@@"
        tokens.append((token, html))
        return token

    rendered = html_escape(value)
    rendered = re.sub(r"`([^`]+)`", lambda match: stash(f"<code>{match.group(1)}</code>"), rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", rendered)
    rendered = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", rendered)
    rendered = re.sub(r"(?<!\*)\*([^*\s][^*]*?)\*(?!\*)", r"<em>\1</em>", rendered)

    def replace_image(match: re.Match[str]) -> str:
        alt = html_unescape(match.group(1))
        href = html_unescape(match.group(2))
        media_url = markdown_media_url_for_doc_route(href, source_path)
        if not media_url:
            return f'<span class="missing-media">Image unavailable: {html_escape(alt or href)}</span>'
        safe_alt = html_escape(alt, quote=True)
        caption = f"<figcaption>{html_escape(alt)}</figcaption>" if alt else ""
        escaped_url = html_escape(media_url, quote=True)
        return (
            '<figure class="okf-image">'
            f'<a href="{escaped_url}" target="_blank" rel="noopener">'
            f'<img src="{escaped_url}" alt="{safe_alt}" loading="lazy" />'
            "</a>"
            f"{caption}"
            "</figure>"
        )

    def replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        href = html_unescape(match.group(2))
        routed_href = markdown_href_for_doc_route(href, employee_id, source_path, doc_lookup) if employee_id else href
        return f'<a href="{html_escape(routed_href, quote=True)}">{label}</a>'

    rendered = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)", replace_image, rendered)
    rendered = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)", replace_link, rendered)
    for token, html in tokens:
        rendered = rendered.replace(token, html)
    return rendered


def strip_table_boundary_pipes(line: str) -> str:
    source = line.strip()
    if source.startswith("|"):
        source = source[1:]
    if source.endswith("|") and not source.endswith(r"\|"):
        source = source[:-1]
    return source


def table_cells(line: str) -> list[str]:
    source = strip_table_boundary_pipes(line)
    cells: list[str] = []
    cell: list[str] = []
    escaped = False
    in_code = False
    paren_depth = 0
    for char in source:
        if escaped:
            cell.append(char if char == "|" else f"\\{char}")
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "`":
            in_code = not in_code
            cell.append(char)
        elif not in_code and char == "(":
            paren_depth += 1
            cell.append(char)
        elif not in_code and char == ")" and paren_depth > 0:
            paren_depth -= 1
            cell.append(char)
        elif char == "|" and not in_code and paren_depth == 0:
            cells.append("".join(cell).strip())
            cell = []
        else:
            cell.append(char)
    cells.append("".join(cell).strip())
    return cells


def is_table_separator(line: str) -> bool:
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    current = lines[index].strip()
    separator = lines[index + 1].strip()
    if "|" not in current or "|" not in separator:
        return False
    return len(table_cells(current)) >= 2 and is_table_separator(separator)


def render_table(
    lines: list[str],
    employee_id: str | None = None,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    if len(lines) < 2 or not is_table_separator(lines[1]):
        return render_paragraph(lines, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)
    headers = table_cells(lines[0])
    rows = [table_cells(line) for line in lines[2:]]
    head = "".join(
        f"<th>{render_inline_markdown(cell, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</th>"
        for cell in headers
    )
    body_rows = []
    for row in rows:
        padded = row + [""] * max(len(headers) - len(row), 0)
        body_rows.append(
            "<tr>"
            + "".join(
                f"<td>{render_inline_markdown(cell, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</td>"
                for cell in padded[: len(headers)]
            )
            + "</tr>"
        )
    return f'<div class="table-wrap"><table class="markdown-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'


def render_paragraph(
    lines: list[str],
    employee_id: str | None = None,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    return f"<p>{render_inline_markdown(text, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</p>" if text else ""


def render_list_item(
    item: str,
    employee_id: str | None = None,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    task = re.match(r"^\[( |x|X)\]\s+(?P<body>.*)$", item.strip())
    if task:
        checked = " checked" if task.group(1).lower() == "x" else ""
        body = render_inline_markdown(task.group("body"), employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)
        return f'<li><input type="checkbox" disabled{checked}> {body}</li>'
    return f"<li>{render_inline_markdown(item, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</li>"


def render_markdown(
    value: str,
    employee_id: str | None = None,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> Markup:
    lines = value.splitlines()
    html_parts: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    ordered_items: list[str] = []
    table_lines: list[str] = []
    blockquote_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            html_parts.append(render_paragraph(paragraph, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup))
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            html_parts.append(
                "<ul>"
                + "".join(
                    render_list_item(item, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)
                    for item in list_items
                )
                + "</ul>"
            )
            list_items.clear()

    def flush_ordered_list() -> None:
        if ordered_items:
            html_parts.append(
                "<ol>"
                + "".join(
                    render_list_item(item, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)
                    for item in ordered_items
                )
                + "</ol>"
            )
            ordered_items.clear()

    def flush_table() -> None:
        if table_lines:
            html_parts.append(render_table(table_lines, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup))
            table_lines.clear()

    def flush_blockquote() -> None:
        if not blockquote_lines:
            return
        inner = str(render_markdown("\n".join(blockquote_lines), employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup))
        prefix = '<div class="rendered-markdown">'
        if inner.startswith(prefix) and inner.endswith("</div>"):
            inner = inner[len(prefix) : -len("</div>")]
        html_parts.append(f"<blockquote>{inner}</blockquote>")
        blockquote_lines.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
            language = stripped.removeprefix("```").strip().split(None, 1)[0].lower() if stripped.removeprefix("```").strip() else ""
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            code = "\n".join(code_lines)
            if language == "mermaid":
                html_parts.append(
                    '<div class="mermaid-diagram" data-mermaid-state="pending">'
                    '<div class="mermaid">'
                    f"{html_escape(code)}"
                    "</div>"
                    '<p class="mermaid-status" aria-live="polite">Mermaid diagram pending render.</p>'
                    '<details class="mermaid-source-fallback">'
                    "<summary>Mermaid source</summary>"
                    f'<pre class="code-block"><code>{html_escape(code)}</code></pre>'
                    "</details>"
                    "</div>"
                )
            elif language == "json":
                parsed = parse_structured_string(code)
                if parsed is not code:
                    html_parts.append(str(render_value_html(parsed)))
                else:
                    html_parts.append(f'<pre class="code-block"><code>{html_escape(code)}</code></pre>')
            else:
                html_parts.append(f'<pre class="code-block"><code>{html_escape(code)}</code></pre>')
        elif not stripped:
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
        elif re.fullmatch(r"(?:-{3,}|_{3,}|\*{3,})", stripped):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
            html_parts.append("<hr>")
        elif stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
            marker, _, title = stripped.partition(" ")
            level = min(max(len(marker), 1) + 2, 5)
            html_parts.append(
                f"<h{level}>{render_inline_markdown(title or stripped.lstrip('#').strip(), employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</h{level}>"
            )
        elif re.match(r"^\s*>\s?", line):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_table()
            blockquote_lines.append(re.sub(r"^\s*>\s?", "", line))
        elif re.match(r"^\s*[-*+]\s+\S", line):
            flush_paragraph()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
            list_items.append(re.sub(r"^\s*[-*+]\s+", "", line).strip())
        elif re.match(r"^\s*\d+\.\s+\S", line):
            flush_paragraph()
            flush_list()
            flush_table()
            flush_blockquote()
            ordered_items.append(re.sub(r"^\s*\d+\.\s+", "", line).strip())
        elif is_table_start(lines, index):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_blockquote()
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                table_lines.append(lines[index].strip())
                index += 1
            index -= 1
        elif re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", stripped):
            flush_paragraph()
            flush_list()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
            html_parts.append(render_inline_markdown(stripped, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup))
        else:
            flush_list()
            flush_ordered_list()
            flush_table()
            flush_blockquote()
            paragraph.append(line)
        index += 1

    flush_paragraph()
    flush_list()
    flush_ordered_list()
    flush_table()
    flush_blockquote()
    return Markup(f'<div class="rendered-markdown">{"".join(html_parts)}</div>')


def render_value_html(value: Any, key: str = "", depth: int = 0) -> Markup:
    if isinstance(value, str):
        parsed = parse_structured_string(value)
        if parsed is not value:
            return render_value_html(parsed, key=key, depth=depth)
        if is_markdown_like(value):
            return render_markdown(value)
        if "\n" in value:
            return Markup(f'<pre class="text-block">{html_escape(value)}</pre>')
        return Markup(f'<span class="scalar string">{render_inline_markdown(value)}</span>')
    if value is None:
        return Markup('<span class="scalar null">null</span>')
    if isinstance(value, bool):
        return Markup(f'<span class="scalar bool">{str(value).lower()}</span>')
    if isinstance(value, (int, float)):
        return Markup(f'<span class="scalar number">{value}</span>')
    if isinstance(value, dict):
        rows = []
        for item_key, item_value in value.items():
            rows.append(
                '<div class="kv-row">'
                f'<div class="kv-key">{html_escape(str(item_key))}</div>'
                f'<div class="kv-value">{render_value_html(item_value, key=str(item_key), depth=depth + 1)}</div>'
                "</div>"
            )
        return Markup(f'<div class="structured-data depth-{min(depth, 3)}">{"".join(rows)}</div>')
    if isinstance(value, list):
        items = "".join(f"<li>{render_value_html(item, key=key, depth=depth + 1)}</li>" for item in value)
        return Markup(f'<ol class="structured-list depth-{min(depth, 3)}">{items}</ol>')
    return Markup(f'<span class="scalar">{html_escape(str(value))}</span>')


def render_content(value: Any) -> Markup:
    if isinstance(value, str):
        parsed = parse_structured_string(value)
        if parsed is not value:
            return render_value_html(parsed)
        return render_markdown(value) if is_markdown_like(value) else render_value_html(value)
    return render_value_html(value)


def action_catalog_by_key() -> dict[str, dict[str, Any]]:
    return {str(action.get("action_key")): action for action in load_action_catalog()}


def result_boi_id(value: dict[str, Any]) -> str:
    if value.get("boi_id"):
        return str(value["boi_id"])
    try:
        return str((((value.get("response") or {}).get("item") or {}).get("metadata") or {}).get("boi_id") or "")
    except Exception:
        return ""


def result_boi_uri(value: dict[str, Any]) -> str:
    try:
        return str(((value.get("response") or {}).get("item") or {}).get("uri") or "")
    except Exception:
        return ""


def doc_url_if_resolvable(ref: str, employee_id: str, doc_lookup: dict[str, dict[str, Any]] | None = None) -> str:
    if not ref:
        return ""
    doc = doc_from_lookup(ref, doc_lookup)
    if doc:
        return doc_url_for_ref(str(doc["metadata"].get("boi_id") or ref), employee_id)
    if doc_lookup is not None:
        return doc_url_for_ref(ref, employee_id) if find_recovered_doc_by_id(ref, employee_id) else ""
    return doc_url_for_ref(ref, employee_id) if find_doc_by_id(ref, employee_id) else ""


def event_dispatch_summary(
    result: dict[str, Any],
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    dispatch = result.get("dispatch_result") if isinstance(result, dict) else None
    if not isinstance(dispatch, dict) or not dispatch.get("results"):
        return None
    catalog = action_catalog_by_key()
    boi_id = str(dispatch.get("boi_id") or "")
    rows = []
    for row in dispatch.get("results") or []:
        action_key = str(row.get("action_key") or "")
        action = catalog.get(action_key, {})
        action_result = row.get("result") or {}
        status = str(action_result.get("status") or row.get("status_code") or row.get("error") or "unknown")
        doc_ref = str(action_result.get("doc_ref") or action.get("doc_ref") or "")
        row_boi_id = result_boi_id(action_result)
        if row_boi_id and not boi_id:
            boi_id = row_boi_id
        row_boi_url = doc_url_if_resolvable(row_boi_id, employee_id, doc_lookup=doc_lookup)
        rows.append(
            {
                "action_key": action_key,
                "connector_kind": action.get("connector_kind") or row.get("type"),
                "status": status,
                "request_id": action_result.get("request_id"),
                "doc_ref": doc_ref,
                "doc_url": doc_url_for_ref(doc_ref, employee_id) if doc_ref else "",
                "boi_id": row_boi_id,
                "boi_uri": result_boi_uri(action_result),
                "boi_url": row_boi_url,
                "boi_missing": row_boi_id if row_boi_id and not row_boi_url else "",
                "simulation": bool(action_result.get("simulation") or action.get("simulation_mode")),
                "simulation_label": action_result.get("simulation_label") or action.get("simulation_label") or ("SIMULATED" if action.get("simulation_mode") else ""),
                "simulation_notice": action_result.get("simulation_notice") or action.get("simulation_notice") or "",
                "real_system_status": action_result.get("real_system_status") or action.get("real_system_status") or "",
                "simulated_system": action_result.get("simulated_system") or action.get("simulated_system") or "",
            }
        )
    boi_url = doc_url_if_resolvable(boi_id, employee_id, doc_lookup=doc_lookup)
    return {
        "routed_by": result.get("routed_by"),
        "status": dispatch.get("status"),
        "ok": dispatch.get("ok"),
        "boi_id": boi_id,
        "boi_url": boi_url,
        "boi_missing": boi_id if boi_id and not boi_url else "",
        "actions": rows,
    }


def event_raw_url(log_ref: str, employee_id: str) -> str:
    return "/api/events/raw/" + quote(log_ref, safe="") + "?" + urlencode({"employee_id": employee_id})


def action_raw_api_url(log_ref: str, employee_id: str) -> str:
    return "/api/actions/raw/" + quote(log_ref, safe="") + "?" + urlencode({"employee_id": employee_id})


def action_raw_page_url(log_ref: str, employee_id: str) -> str:
    return "/actions/raw/" + quote(log_ref, safe="") + "?" + urlencode({"employee_id": employee_id})


def event_filter_url(event_id: str, employee_id: str) -> str:
    return "/events?" + urlencode({"employee_id": employee_id, "event_id": event_id})


def trace_events_url(trace_id: str, employee_id: str) -> str:
    return "/events?" + urlencode({"employee_id": employee_id, "trace_id": trace_id})


def parse_event_time_value(value: str, *, field_name: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO datetime value") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=KST)
    return parsed.astimezone(KST).replace(microsecond=0)


def datetime_local_value(value: datetime | None) -> str:
    return value.astimezone(KST).strftime("%Y-%m-%dT%H:%M") if value else ""


def event_time_range(
    *,
    from_time: str = "",
    to_time: str = "",
    time_preset: str = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    explicit_range = bool(str(from_time or "").strip() or str(to_time or "").strip())
    preset = str(time_preset or "").strip()
    current = (now or datetime.now(KST)).astimezone(KST).replace(microsecond=0)
    start: datetime | None = None
    end: datetime | None = None
    label = ""
    preset_labels = {"1h": "최근 1시간", "6h": "최근 6시간", "24h": "최근 24시간", "today": "오늘"}

    if explicit_range:
        start = parse_event_time_value(from_time, field_name="from_time")
        end = parse_event_time_value(to_time, field_name="to_time")
        label_parts = []
        if start:
            label_parts.append(start.strftime("%Y-%m-%d %H:%M"))
        else:
            label_parts.append("처음")
        label_parts.append("~")
        if end:
            label_parts.append(end.strftime("%Y-%m-%d %H:%M"))
        else:
            label_parts.append("현재")
        label = " ".join(label_parts)
        preset = ""
    elif preset:
        if preset == "1h":
            start = current - timedelta(hours=1)
            end = current
        elif preset == "6h":
            start = current - timedelta(hours=6)
            end = current
        elif preset == "24h":
            start = current - timedelta(hours=24)
            end = current
        elif preset == "today":
            start = datetime.combine(current.date(), datetime.min.time(), tzinfo=KST)
            end = current
        elif preset == "all":
            preset = ""
        else:
            raise ValueError("time_preset must be one of 1h, 6h, 24h, today")
        label = preset_labels.get(preset, "")

    if start and end and start > end:
        raise ValueError("from_time must be earlier than or equal to to_time")

    return {
        "from_dt": start,
        "to_dt": end,
        "from_value": datetime_local_value(start) if explicit_range else "",
        "to_value": datetime_local_value(end) if explicit_range else "",
        "time_preset": preset,
        "active": bool(start or end),
        "label": label,
    }


def workflow_status_page_url(trace_id: str, employee_id: str) -> str:
    return workflow_status_page_url_for_key("equipment-anomaly", trace_id, employee_id)


def workflow_status_api_url(trace_id: str, employee_id: str, **params: str) -> str:
    query = {"trace_id": trace_id, "employee_id": employee_id, **params}
    return "/api/workflows/demo/equipment-anomaly/status?" + urlencode(query)


def workflow_status_raw_url(trace_id: str, employee_id: str) -> str:
    return "/api/workflows/demo/equipment-anomaly/status/raw?" + urlencode({"employee_id": employee_id, "trace_id": trace_id})


def workflow_status_page_url_for_key(workflow_key: str, trace_id: str, employee_id: str) -> str:
    return f"/workflows/{workflow_key}/status?" + urlencode({"employee_id": employee_id, "trace_id": trace_id})


def workflow_status_api_url_for_key(workflow_key: str, trace_id: str, employee_id: str, **params: str) -> str:
    query = {"trace_id": trace_id, "employee_id": employee_id, **params}
    return f"/api/workflows/{workflow_key}/status?" + urlencode(query)


def workflow_status_raw_url_for_key(workflow_key: str, trace_id: str, employee_id: str) -> str:
    return f"/api/workflows/{workflow_key}/status/raw?" + urlencode({"employee_id": employee_id, "trace_id": trace_id})


def workflow_status_page_url_for_event_type(event_type: str, trace_id: str, employee_id: str) -> str:
    if not event_type or not trace_id:
        return ""
    workflow, _stage, _event_def = workflow_for_event_type(event_type, employee_id)
    if not workflow:
        return ""
    return workflow_status_page_url_for_key(str(workflow.get("workflow_key") or ""), trace_id, employee_id)


SENSITIVE_KEY_RE = re.compile(r"(authorization|api[_-]?key|password|secret|token)", re.IGNORECASE)
SECRET_VALUE_RE = re.compile(
    r"\b(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})"
    r"|(?i:(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_-]{8,})"
)
HOTL_HIDDEN_STATUSES = {"hidden", "rolled_back"}
REFERENCE_TEXT_RE = re.compile(r"(boi:[A-Za-z0-9:._/-]+|trace-[A-Za-z0-9_-]+|evt-[A-Za-z0-9_-]+|act-[A-Za-z0-9_-]+|[A-Za-z0-9_.-]+\.v\d+)")


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if SENSITIVE_KEY_RE.search(str(key)):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value


def url_for_reference_token(token: str, employee_id: str) -> str:
    if token.startswith("boi:"):
        return doc_url_if_resolvable(token, employee_id) or doc_url_for_ref(token, employee_id)
    if token.startswith("trace-"):
        return workflow_status_page_url(token, employee_id)
    if token.startswith("evt-"):
        return event_filter_url(token, employee_id)
    if token.startswith("act-"):
        action = find_action_log_row_by_request_id(token, employee_id)
        if action and action.get("_log_ref"):
            return action_raw_page_url(str(action["_log_ref"]), employee_id)
        return "/actions?" + urlencode({"employee_id": employee_id})
    if get_event_type(token):
        return f"/event-types/{token}?" + urlencode({"employee_id": employee_id})
    return ""


def linkify_reference_text(value: str, employee_id: str) -> Markup:
    escaped = html_escape(str(value))

    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        url = url_for_reference_token(token, employee_id)
        if not url:
            return token
        return f'<a href="{html_escape(url, quote=True)}">{token}</a>'

    return Markup(REFERENCE_TEXT_RE.sub(replace, escaped))


def render_linkified_value_html(value: Any, employee_id: str, depth: int = 0) -> Markup:
    if isinstance(value, str):
        if "\n" in value:
            return Markup(f'<pre class="text-block">{linkify_reference_text(value, employee_id)}</pre>')
        return Markup(f'<span class="scalar string">{linkify_reference_text(value, employee_id)}</span>')
    if value is None:
        return Markup('<span class="scalar null">null</span>')
    if isinstance(value, bool):
        return Markup(f'<span class="scalar bool">{str(value).lower()}</span>')
    if isinstance(value, (int, float)):
        return Markup(f'<span class="scalar number">{value}</span>')
    if isinstance(value, dict):
        rows = []
        for item_key, item_value in value.items():
            rows.append(
                '<div class="kv-row">'
                f'<div class="kv-key">{html_escape(str(item_key))}</div>'
                f'<div class="kv-value">{render_linkified_value_html(item_value, employee_id, depth=depth + 1)}</div>'
                "</div>"
            )
        return Markup(f'<div class="structured-data depth-{min(depth, 3)}">{"".join(rows)}</div>')
    if isinstance(value, list):
        items = "".join(f"<li>{render_linkified_value_html(item, employee_id, depth=depth + 1)}</li>" for item in value)
        return Markup(f'<ol class="structured-list depth-{min(depth, 3)}">{items}</ol>')
    return Markup(f'<span class="scalar">{html_escape(str(value))}</span>')


def first_result_text(value: Any, *, allow_string: bool = False) -> str:
    if isinstance(value, str):
        return value.strip() if allow_string else ""
    if isinstance(value, dict):
        for key in ("message", "text", "body"):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
            found = first_result_text(item, allow_string=True)
            if found:
                return found
        for key, item in value.items():
            if key in {"input", "inputs", "input_value", "prompt"}:
                continue
            found = first_result_text(item)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = first_result_text(item)
            if found:
                return found
    return ""


def action_raw_readable_markdown(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    simulation_agent = result.get("simulation_agent") if isinstance(result.get("simulation_agent"), dict) else {}
    simulation_result = simulation_agent.get("simulation_result") if isinstance(simulation_agent.get("simulation_result"), dict) else {}
    candidates: list[tuple[str, Any]] = [
        ("result.simulation_agent.simulation_result.markdown", simulation_result.get("markdown")),
        ("result.message", result.get("message")),
        ("result.response", result.get("response")),
        ("result.body", result.get("body")),
    ]
    for source, value in candidates:
        text = first_result_text(value, allow_string=True)
        if not text:
            continue
        cleaned = sanitize_stage_analysis_message(text) or text.strip()
        if cleaned:
            return {"available": True, "source": source, "markdown": cleaned}
    return {"available": False, "source": "", "markdown": ""}


def compact_action_raw_row_for_html(row: dict[str, Any]) -> dict[str, Any]:
    """Keep the HTML raw detail page responsive for large Langflow/action rows.

    The JSON API remains the authoritative full raw row. The HTML page shows
    metadata and compact evidence only, because rendering a deeply nested
    Langflow response can monopolize the single NAS PoC worker.
    """

    def short_text(value: Any, limit: int = 1800) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0].rstrip() + " ... [truncated in HTML; open JSON API for full value]"

    compact: dict[str, Any] = {}
    for key in (
        "_log_ref",
        "logged_at",
        "action_key",
        "request_id",
        "employee_id",
        "event_id",
        "event_type",
        "trace_id",
        "boi_id",
        "status",
        "connector_kind",
        "doc_ref",
        "simulation",
        "simulation_label",
        "simulation_notice",
        "simulated_system",
        "real_system_status",
        "retrieval_rounds",
        "coverage_score",
        "missing_context",
        "used_docs",
        "evidence_packets",
    ):
        if key in row:
            compact[key] = row[key]

    event = row.get("event")
    if isinstance(event, dict):
        compact["event"] = {
            key: event.get(key)
            for key in ("event_id", "event_type", "trace_id", "producer", "occurred_at")
            if event.get(key) is not None
        }
        payload = event.get("payload")
        if isinstance(payload, dict):
            compact["event"]["payload_keys"] = sorted(str(key) for key in payload.keys())[:30]

    payload = row.get("payload")
    if isinstance(payload, dict):
        compact["payload_keys"] = sorted(str(key) for key in payload.keys())[:30]

    result = row.get("result")
    if isinstance(result, dict):
        compact_result: dict[str, Any] = {}
        for key in (
            "ok",
            "status",
            "status_code",
            "request_id",
            "action_key",
            "connector_kind",
            "flow_id",
            "flow_name",
            "simulation",
            "simulation_label",
            "simulation_notice",
            "simulated_system",
            "real_system_status",
            "retrieval_rounds",
            "coverage_score",
            "missing_context",
        ):
            if key in result:
                compact_result[key] = result[key]
        for key in ("summary", "message", "text", "body"):
            if key in result:
                compact_result[key] = short_text(result[key])
        simulation_agent = result.get("simulation_agent")
        if isinstance(simulation_agent, dict):
            context_pack = simulation_agent.get("context_pack") if isinstance(simulation_agent.get("context_pack"), dict) else {}
            compact_result["simulation_agent"] = {
                "agent": simulation_agent.get("agent"),
                "coverage_report": simulation_agent.get("coverage_report"),
                "limitations": simulation_agent.get("limitations"),
                "citations": simulation_agent.get("citations"),
                "retrieval_trace": (simulation_agent.get("retrieval_trace") or [])[:8]
                if isinstance(simulation_agent.get("retrieval_trace"), list)
                else simulation_agent.get("retrieval_trace"),
                "used_docs": (context_pack.get("documents") or [])[:10]
                if isinstance(context_pack.get("documents"), list)
                else [],
                "evidence_packets": simulation_agent.get("evidence_packets")
                or context_pack.get("evidence_packets")
                or result.get("evidence_packets")
                or [],
            }
        omitted = [
            key
            for key in ("response", "outputs", "input", "inputs", "prompt", "headers", "request")
            if key in result
        ]
        if omitted:
            compact_result["_html_omitted_fields"] = omitted
            compact_result["_full_raw"] = "Open the JSON API link for omitted nested fields."
        compact["result"] = compact_result
    elif result is not None:
        compact["result"] = short_text(result)

    error = row.get("error")
    if error is not None:
        compact["error"] = short_text(error) if isinstance(error, str) else error

    return compact


def event_rows_for_template(
    rows: list[dict[str, Any]],
    doc_lookup: dict[str, dict[str, Any]] | None = None,
    employee_id: str = DEMO_EMPLOYEE_ID,
) -> list[dict[str, Any]]:
    rendered_rows = []
    workflow_url_cache: dict[tuple[str, str], str] = {}
    for row in rows:
        item = dict(row)
        item["event_url"] = event_filter_url(str(row.get("event_id") or ""), employee_id) if row.get("event_id") else ""
        item["trace_url"] = trace_events_url(str(row.get("trace_id") or ""), employee_id) if row.get("trace_id") else ""
        item["stream_url"] = events_url(employee_id, event_type=str(row.get("event_type") or ""))
        event_type_for_workflow = str(row.get("event_type") or "")
        trace_id_for_workflow = str(row.get("trace_id") or "")
        cache_key = (event_type_for_workflow, trace_id_for_workflow)
        if trace_id_for_workflow and cache_key not in workflow_url_cache:
            workflow_url_cache[cache_key] = workflow_status_page_url_for_event_type(
                event_type_for_workflow,
                trace_id_for_workflow,
                employee_id,
            )
        item["workflow_status_url"] = workflow_url_cache.get(cache_key, "")
        if row.get("_log_ref") and (row.get("result") is not None or row.get("error") is not None):
            item["raw_url"] = event_raw_url(str(row["_log_ref"]), employee_id)
        if row.get("result") is not None:
            summary = event_dispatch_summary(row["result"], str(row.get("employee_id") or DEMO_EMPLOYEE_ID), doc_lookup=doc_lookup)
            if summary:
                item["dispatch_summary"] = summary
            else:
                item["result_html"] = render_content(row["result"])
        if row.get("error") is not None:
            item["error_html"] = render_content(row["error"])
        rendered_rows.append(item)
    return rendered_rows


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
    signature = glob_signature(EVENT_CATALOG_ROOT, "*.yaml") + glob_signature(EVENT_CATALOG_ROOT, "*.yml")
    if _EVENT_TYPES_CACHE["signature"] == signature:
        return [dict(item) for item in _EVENT_TYPES_CACHE["items"]]
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
    result = list(dedup.values())
    _EVENT_TYPES_CACHE["signature"] = signature
    _EVENT_TYPES_CACHE["items"] = result
    return [dict(item) for item in result]


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
    signature = glob_signature(ACTION_CATALOG_ROOT, "*.yaml") + glob_signature(ACTION_CATALOG_ROOT, "*.yml")
    if _ACTION_CATALOG_CACHE["signature"] == signature:
        return [dict(item) for item in _ACTION_CATALOG_CACHE["items"]]
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
    result = list(dedup.values())
    _ACTION_CATALOG_CACHE["signature"] = signature
    _ACTION_CATALOG_CACHE["items"] = result
    return [dict(item) for item in result]


def cached_jsonl_rows(*, root: Path, pattern: str, cache: dict[str, Any], ref_prefix: str) -> list[dict[str, Any]]:
    ensure_dirs()
    signature = glob_signature(root, pattern)
    if cache["signature"] == signature:
        return cache["rows"]
    rows: list[dict[str, Any]] = []
    for p in sorted(root.glob(pattern), reverse=True):
        lines = p.read_text(encoding="utf-8").splitlines()
        for line_number, line in reversed(list(enumerate(lines, start=1))):
            try:
                row = json.loads(line)
            except Exception:
                continue
            row["_log_ref"] = f"{ref_prefix}:{p.name}:{line_number}"
            rows.append(row)
    cache["signature"] = signature
    cache["rows"] = rows
    return rows


def cached_action_log_rows() -> list[dict[str, Any]]:
    return cached_jsonl_rows(root=ACTION_LOG_ROOT, pattern="actions-*.jsonl", cache=_ACTION_LOG_CACHE, ref_prefix="action")


def cached_event_log_rows() -> list[dict[str, Any]]:
    return cached_jsonl_rows(root=EVENTS_ROOT, pattern="events-*.jsonl", cache=_EVENT_LOG_CACHE, ref_prefix="event")


def read_jsonl_row_by_ref(*, log_ref: str, root: Path, ref_prefix: str) -> dict[str, Any] | None:
    parts = log_ref.split(":")
    if len(parts) != 3 or parts[0] != ref_prefix:
        return None
    file_name = parts[1]
    if "/" in file_name or "\\" in file_name or not file_name.endswith(".jsonl"):
        return None
    try:
        line_number = int(parts[2])
    except ValueError:
        return None
    if line_number < 1:
        return None
    path = (root / file_name).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return None
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        for current_line_number, line in enumerate(handle, start=1):
            if current_line_number != line_number:
                continue
            try:
                row = json.loads(line)
            except Exception:
                return None
            if isinstance(row, dict):
                row["_log_ref"] = log_ref
                return row
            return None
    return None


def read_action_logs(limit: int = 200, action_key: str | None = None, offset: int = 0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in cached_action_log_rows():
        if action_key and row.get("action_key") != action_key:
            continue
        if offset > 0:
            offset -= 1
            continue
        rows.append(dict(row))
        if len(rows) >= limit:
            return rows
    return rows


def tail_jsonl_lines(
    path: Path,
    max_lines: int,
    *,
    chunk_size: int = 16384,
    max_bytes: int = 2 * 1024 * 1024,
) -> tuple[list[str], bool]:
    if max_lines <= 0 or not path.exists():
        return [], True
    data = b""
    newline_count = 0
    started_at_beginning = True
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0 and newline_count <= max_lines and len(data) < max_bytes:
            read_size = min(chunk_size, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            data = chunk + data
            newline_count = data.count(b"\n")
        started_at_beginning = position == 0
    lines = data.decode("utf-8", errors="replace").splitlines()
    return lines[-max_lines:], started_at_beginning


def read_recent_action_logs_fast(limit: int = 200, action_key: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    wanted = max(1, min(int(limit or 200), 2000))
    for path in sorted(ACTION_LOG_ROOT.glob("actions-*.jsonl"), reverse=True):
        tail_lines, complete_file = tail_jsonl_lines(path, max(wanted * 3, 200))
        start_line = 1 if complete_file else None
        for offset, line in reversed(list(enumerate(tail_lines))):
            try:
                row = json.loads(line)
            except Exception:
                continue
            if action_key and row.get("action_key") != action_key:
                continue
            if start_line is not None:
                row["_log_ref"] = f"action:{path.name}:{start_line + offset}"
            rows.append(row)
            if len(rows) >= wanted:
                return rows
    return rows


def append_action_log_row(row: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    path = ACTION_LOG_ROOT / f"actions-{datetime.now(KST).strftime('%Y%m%d')}.jsonl"
    line_number = 1
    if path.exists():
        try:
            line_number = len(path.read_text(encoding="utf-8").splitlines()) + 1
        except Exception:
            line_number = 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    invalidate_action_log_caches()
    item = dict(row)
    item["_log_ref"] = f"action:{path.name}:{line_number}"
    return item


def action_log_visible_to_employee(row: dict[str, Any], employee_id: str) -> bool:
    row_employee_id = str(row.get("employee_id") or "")
    if row_employee_id and row_employee_id != employee_id:
        return False
    return True


def find_action_log_row_by_ref(log_ref: str, employee_id: str | None = None) -> dict[str, Any] | None:
    direct_row = read_jsonl_row_by_ref(log_ref=log_ref, root=ACTION_LOG_ROOT, ref_prefix="action")
    if direct_row is not None:
        if employee_id and not action_log_visible_to_employee(direct_row, employee_id):
            return None
        return dict(direct_row)
    for row in cached_action_log_rows():
        if row.get("_log_ref") != log_ref:
            continue
        if employee_id and not action_log_visible_to_employee(row, employee_id):
            return None
        return dict(row)
    return None


def find_action_log_row_by_request_id(request_id: str, employee_id: str | None = None) -> dict[str, Any] | None:
    if not request_id:
        return None
    for row in cached_action_log_rows():
        if row.get("request_id") != request_id:
            continue
        if employee_id and not action_log_visible_to_employee(row, employee_id):
            return None
        return dict(row)
    return None


def trace_action_log_rows(trace_id: str, *, event_ids: set[str] | None = None, limit: int = 80) -> list[dict[str, Any]]:
    event_id_set = {str(event_id) for event_id in (event_ids or set()) if event_id}
    tokens = [token for token in [trace_id, *sorted(event_id_set)] if token]
    if not tokens:
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(ACTION_LOG_ROOT.glob("actions-*.jsonl")):
        with p.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not any(token in line for token in tokens):
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                row_trace_id = str(row.get("trace_id") or "")
                row_event_id = str(row.get("event_id") or "")
                if row_trace_id != trace_id and row_event_id not in event_id_set:
                    continue
                row["_log_ref"] = f"action:{p.name}:{line_number}"
                rows.append(row)
    return rows[-limit:]


def trace_prior_action_results(trace_id: str, employee_id: str, *, limit: int = 80) -> list[dict[str, Any]]:
    if not trace_id:
        return []
    rows: list[dict[str, Any]] = []
    for row in trace_action_log_rows(trace_id, limit=limit):
        if str(row.get("trace_id") or "") != trace_id:
            continue
        if not action_log_visible_to_employee(row, employee_id):
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
                "_log_ref": row.get("_log_ref"),
                "simulation": bool(row.get("simulation") or result.get("simulation")),
                "coverage_score": row.get("coverage_score") if row.get("coverage_score") is not None else result.get("coverage_score"),
                "evidence_packets": row.get("evidence_packets") or result.get("evidence_packets"),
                "result": result,
            }
        )
        if len(rows) >= limit:
            break
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


def trace_event_log_rows(trace_id: str = "", event_id: str = "", *, limit: int = 1000) -> list[dict[str, Any]]:
    tokens = [token for token in (trace_id, event_id) if token]
    if not tokens:
        return []
    rows: list[dict[str, Any]] = []
    for p in sorted(EVENTS_ROOT.glob("events-*.jsonl")):
        with p.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not any(token in line for token in tokens):
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if trace_id and str(row.get("trace_id") or "") != trace_id:
                    continue
                if event_id and str(row.get("event_id") or "") != event_id:
                    continue
                row["_log_ref"] = f"event:{p.name}:{line_number}"
                rows.append(row)
    return rows[-limit:]


def filtered_event_log_rows(
    event_type: str | None = None,
    trace_id: str | None = None,
    event_id: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> list[dict[str, Any]]:
    event_labels = {str(e["event_type"]): str(e.get("name_ko") or e["event_type"]) for e in load_event_types()}
    rows: list[dict[str, Any]] = []
    has_time_filter = bool(from_dt or to_dt)
    source_rows = trace_event_log_rows(trace_id or "", event_id or "") if trace_id or event_id else cached_event_log_rows()
    for row in source_rows:
        if event_type and row.get("event_type") != event_type:
            continue
        if trace_id and row.get("trace_id") != trace_id:
            continue
        if event_id and row.get("event_id") != event_id:
            continue
        if has_time_filter:
            try:
                logged_at = parse_event_time_value(str(row.get("logged_at") or ""), field_name="logged_at")
            except ValueError:
                continue
            if logged_at is None:
                continue
            if from_dt and logged_at < from_dt:
                continue
            if to_dt and logged_at > to_dt:
                continue
        item = dict(row)
        item["event_label"] = event_labels.get(str(row.get("event_type")), str(row.get("event_type") or ""))
        rows.append(item)
    return rows


def read_event_logs(
    limit: int = 200,
    event_type: str | None = None,
    trace_id: str | None = None,
    event_id: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = filtered_event_log_rows(event_type=event_type, trace_id=trace_id, event_id=event_id, from_dt=from_dt, to_dt=to_dt)
    return rows[offset : offset + limit]


def count_event_logs(
    event_type: str | None = None,
    trace_id: str | None = None,
    event_id: str | None = None,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
) -> int:
    return len(filtered_event_log_rows(event_type=event_type, trace_id=trace_id, event_id=event_id, from_dt=from_dt, to_dt=to_dt))


def find_event_log_row_by_ref(log_ref: str) -> dict[str, Any] | None:
    direct_row = read_jsonl_row_by_ref(log_ref=log_ref, root=EVENTS_ROOT, ref_prefix="event")
    if direct_row is not None:
        direct_row["event_label"] = event_label(direct_row.get("event_type"))
        return direct_row
    for row in cached_event_log_rows():
        if row.get("_log_ref") == log_ref:
            item = dict(row)
            item["event_label"] = event_label(item.get("event_type"))
            return item
    return None


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
    invalidate_event_log_caches()


def teams_for(employee_id: str) -> list[str]:
    identity = identity_for_employee(employee_id)
    teams = list(identity.teams)
    state = rbac_state()
    for team_id, team in (state.get("teams") or {}).items():
        if employee_id in [str(item) for item in team.get("members") or []]:
            teams.append(str(team_id))
    return sorted(dict.fromkeys(team for team in teams if team))


def roles_for(employee_id: str) -> list[str]:
    identity = identity_for_employee(employee_id)
    roles = list(identity.roles)
    teams = set(teams_for(employee_id))
    state = rbac_state()
    for binding in state.get("bindings") or []:
        subject_type = str(binding.get("subject_type") or "")
        subject_id = str(binding.get("subject_id") or "")
        if subject_type == "employee" and subject_id != employee_id:
            continue
        if subject_type == "team" and subject_id not in teams:
            continue
        scope = str(binding.get("scope") or "global")
        if scope and scope != "global":
            # Fine-grained scope checks are handled by /api/rbac/check; global
            # compatibility keeps existing role checks stable.
            continue
        roles.extend(str(role) for role in binding.get("roles") or [] if role)
    return sorted(dict.fromkeys(role for role in roles if role))


def user_name_for(employee_id: str) -> str:
    identity = identity_for_employee(employee_id)
    return identity.display_name or name_for_employee(employee_id)


def require_employee_role(employee_id: str, role: str) -> None:
    if role in roles_for(employee_id) or "boi.admin" in roles_for(employee_id):
        return
    raise HTTPException(status_code=403, detail=f"missing required role: {role}")


def require_employee_binding_or_admin_override(
    employee_id: str,
    requested_employee_id: str | None,
    *,
    operation: str,
    mismatch_detail: str,
    reason: str | None = None,
) -> bool:
    requested = str(requested_employee_id or "").strip()
    if not requested or requested == employee_id:
        return False
    if "boi.admin" not in roles_for(employee_id):
        raise HTTPException(status_code=403, detail=mismatch_detail)
    clean_reason = str(reason or "").strip()
    if not clean_reason:
        raise HTTPException(status_code=400, detail=f"{operation} admin override requires admin_override_reason")
    append_rbac_audit(
        employee_id,
        f"admin_{operation}_employee_override",
        {
            "authenticated_employee_id": employee_id,
            "requested_employee_id": requested,
            "reason": clean_reason,
        },
    )
    return True


RBAC_ROLES = [
    {"role": "boi.viewer", "label": "조회", "description": "권한 범위의 BoI와 runtime evidence를 조회합니다."},
    {"role": "boi.editor", "label": "편집", "description": "권한 범위의 draft/source/body를 수정합니다."},
    {"role": "boi.workflow_runner", "label": "업무 흐름 실행", "description": "이벤트 발행, SOP 업무 흐름 시작, 수동 조치 완료를 수행합니다."},
    {"role": "boi.action_invoker", "label": "업무 요청 실행", "description": "허용된 업무 요청을 실행합니다."},
    {"role": "boi.promoter", "label": "승격", "description": "Team/Public promotion draft와 apply를 처리합니다."},
    {"role": "boi.admin", "label": "관리", "description": "권한 관리와 break-glass audit을 운영합니다."},
]


def rbac_state_path() -> Path:
    return RBAC_ROOT / "state.yaml"


def rbac_audit_path() -> Path:
    return RBAC_ROOT / "audit.jsonl"


def default_rbac_state() -> dict[str, Any]:
    teams: dict[str, dict[str, Any]] = {}
    for employee_id, team_ids in USER_TEAMS.items():
        for team_id in team_ids:
            team = teams.setdefault(
                str(team_id),
                {
                    "team_id": str(team_id),
                    "display_name": str(team_id),
                    "description": "Dev seed team",
                    "owners": [],
                    "members": [],
                    "status": "active",
                },
            )
            team["members"].append(str(employee_id))
    return {"teams": teams, "roles": RBAC_ROLES, "bindings": []}


def invalidate_rbac_state_cache() -> None:
    _RBAC_STATE_CACHE["signature"] = None
    _RBAC_STATE_CACHE["state"] = None


def rbac_state_signature() -> tuple[str, int, int] | tuple[str, int, int, str]:
    path = rbac_state_path()
    try:
        stat = path.stat()
        return (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return (str(path), 0, 0, "missing")


def rbac_state() -> dict[str, Any]:
    ensure_dirs()
    path = rbac_state_path()
    signature = rbac_state_signature()
    if _RBAC_STATE_CACHE["signature"] != signature:
        if not path.exists():
            state = default_rbac_state()
        else:
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
            default = default_rbac_state()
            teams = {**default["teams"], **(data.get("teams") or {})}
            state = {"teams": teams, "roles": data.get("roles") or RBAC_ROLES, "bindings": data.get("bindings") or []}
        _RBAC_STATE_CACHE["signature"] = signature
        _RBAC_STATE_CACHE["state"] = state
    return copy.deepcopy(_RBAC_STATE_CACHE["state"] or default_rbac_state())


def write_rbac_state(data: dict[str, Any]) -> None:
    ensure_dirs()
    rbac_state_path().write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    invalidate_rbac_state_cache()


def append_rbac_audit(actor: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    row = {
        "audit_id": f"rbac-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "logged_at": now_iso(),
        "actor": actor,
        "action": action,
        "payload": redact_sensitive(payload),
    }
    with rbac_audit_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def access_policy_for_doc(doc: dict[str, Any], employee_id: str, *, break_glass: bool = False) -> AccessPolicyDecision:
    return doc_access_policy(
        doc,
        employee_id=employee_id,
        teams=teams_for(employee_id),
        roles=roles_for(employee_id),
        data_root=DATA_ROOT,
        break_glass=break_glass,
    )


def rbac_audit_rows(limit: int = 100) -> list[dict[str, Any]]:
    path = rbac_audit_path()
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-max(1, min(limit, 500)) :][::-1]


def rbac_team_member_ids(team: dict[str, Any]) -> list[str]:
    values = list(team.get("members") or [])
    values.extend(team.get("owners") or [])
    return sorted(dict.fromkeys(str(item) for item in values if item))


def rbac_can_manage(employee_id: str, *, team_id: str | None = None) -> bool:
    roles = roles_for(employee_id)
    if "boi.admin" in roles:
        return True
    if "boi.editor" not in roles:
        return False
    if not team_id:
        return True
    state = rbac_state()
    team = (state.get("teams") or {}).get(str(team_id)) or {}
    return str(employee_id) in [str(item) for item in (team.get("owners") or [])]


def binding_applies_to_employee(binding: dict[str, Any], employee_id: str) -> bool:
    subject_type = str(binding.get("subject_type") or "")
    subject_id = str(binding.get("subject_id") or "")
    if subject_type == "employee":
        return subject_id == employee_id
    if subject_type == "team":
        return subject_id in teams_for(employee_id)
    return False


def role_binding_decision(employee_id: str, required_role: str, *, scope: str = "global", resource: str = "") -> dict[str, Any]:
    if required_role in roles_for(employee_id) or "boi.admin" in roles_for(employee_id):
        return {"allowed": True, "reason": "role_present", "role": required_role, "scope": scope, "resource": resource}
    state = rbac_state()
    for binding in state.get("bindings") or []:
        if not binding_applies_to_employee(binding, employee_id):
            continue
        if required_role not in [str(role) for role in (binding.get("roles") or [])]:
            continue
        binding_scope = str(binding.get("scope") or "global")
        binding_resource = str(binding.get("resource") or "")
        if binding_scope in {"global", scope} and (not binding_resource or not resource or binding_resource == resource):
            return {"allowed": True, "reason": "binding_match", "binding": binding}
    return {"allowed": False, "reason": "missing_role", "role": required_role, "scope": scope, "resource": resource}


def is_accessible(doc: dict[str, Any], employee_id: str) -> bool:
    return access_policy_for_doc(doc, employee_id).can_read


def accessible_docs(employee_id: str) -> list[dict[str, Any]]:
    ensure_dirs()
    signature = markdown_signature()
    if _DOCS_CACHE["signature"] != signature:
        parsed_docs = []
        for p in all_markdown_files():
            try:
                parsed_docs.append(read_doc(p))
            except Exception:
                continue
        _DOCS_CACHE["signature"] = signature
        _DOCS_CACHE["docs"] = parsed_docs
    teams = teams_for(employee_id)
    roles = roles_for(employee_id)
    docs = [
        doc
        for doc in _DOCS_CACHE["docs"]
        if doc_access_policy(doc, employee_id=employee_id, teams=teams, roles=roles, data_root=DATA_ROOT).can_read
    ]
    docs.sort(key=lambda d: metadata_sort_value(d["metadata"].get("timestamp")), reverse=True)
    return docs


def metadata_sort_value(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")


def normalize_folder(folder: str | None) -> str:
    raw = (folder or "").replace("\\", "/").strip("/")
    parts = []
    for part in raw.split("/"):
        part = part.strip()
        if not part or part in {".", ".."}:
            continue
        parts.append(part)
    return "/".join(parts)


def doc_folder(doc: dict[str, Any]) -> str:
    uri = normalize_folder(str(doc.get("uri", "")).lstrip("/"))
    parts = uri.split("/")
    return "/".join(parts[:-1]) if len(parts) > 1 else ""


def folder_matches(doc: dict[str, Any], folder: str | None) -> bool:
    normalized = normalize_folder(folder)
    if not normalized:
        return True
    path = doc_folder(doc)
    return path == normalized or path.startswith(normalized + "/")


def folder_label(path: str) -> str:
    normalized = normalize_folder(path)
    if not normalized:
        return "All Accessible"
    return normalized.split("/")[-1]


def folder_sort_key(node: dict[str, Any]) -> tuple[int, str]:
    first = normalize_folder(node.get("path", "")).split("/")[0]
    order = {"public": 0, "team": 1, "private": 2}
    return order.get(first, 99), str(node.get("path") or node.get("label") or "")


def build_folder_tree(docs: list[dict[str, Any]], selected_folder: str | None = "") -> dict[str, Any]:
    selected = normalize_folder(selected_folder)
    root: dict[str, Any] = {
        "path": "",
        "label": "All Accessible",
        "count": len(docs),
        "_children": {},
    }
    for doc in docs:
        folder = doc_folder(doc)
        if not folder:
            continue
        node = root
        parts = folder.split("/")
        for index, segment in enumerate(parts):
            path = "/".join(parts[: index + 1])
            children = node["_children"]
            if segment not in children:
                children[segment] = {
                    "path": path,
                    "label": folder_label(path),
                    "count": 0,
                    "_children": {},
                }
            child = children[segment]
            child["count"] += 1
            node = child

    def finalize(node: dict[str, Any]) -> dict[str, Any]:
        children = [finalize(child) for child in sorted(node.pop("_children").values(), key=folder_sort_key)]
        node["selected"] = node["path"] == selected
        node["children"] = children
        return node

    return finalize(root)


def folder_breadcrumbs(folder: str | None) -> list[dict[str, str]]:
    normalized = normalize_folder(folder)
    breadcrumbs = [{"path": "", "label": "All Accessible"}]
    if not normalized:
        return breadcrumbs
    parts = normalized.split("/")
    for index, segment in enumerate(parts):
        breadcrumbs.append({"path": "/".join(parts[: index + 1]), "label": segment})
    return breadcrumbs


def browse_url(
    employee_id: str,
    *,
    folder: str | None = "",
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
) -> str:
    params = {"employee_id": employee_id}
    normalized_folder = normalize_folder(folder)
    if normalized_folder:
        params["folder"] = normalized_folder
    for key, value in {
        "q": q,
        "event_type": event_type,
        "visibility": visibility,
        "boi_type": boi_type,
    }.items():
        if value:
            params[key] = value
    return "/?" + urlencode(params)


def events_url(
    employee_id: str,
    *,
    event_type: str = "",
    trace_id: str = "",
    event_id: str = "",
    from_time: str = "",
    to_time: str = "",
    time_preset: str = "",
    page: int = 1,
    limit: int = 50,
) -> str:
    params: dict[str, Any] = {"employee_id": employee_id, "page": page, "limit": limit}
    if event_type:
        params["event_type"] = event_type
    if trace_id:
        params["trace_id"] = trace_id
    if event_id:
        params["event_id"] = event_id
    if from_time or to_time:
        if from_time:
            params["from_time"] = from_time
        if to_time:
            params["to_time"] = to_time
    elif time_preset:
        params["time_preset"] = time_preset
    return "/events?" + urlencode(params)


def with_folder_urls(
    node: dict[str, Any],
    *,
    employee_id: str,
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
) -> dict[str, Any]:
    item = dict(node)
    item["url"] = browse_url(
        employee_id,
        folder=item.get("path", ""),
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
    )
    item["children"] = [
        with_folder_urls(
            child,
            employee_id=employee_id,
            q=q,
            event_type=event_type,
            visibility=visibility,
            boi_type=boi_type,
        )
        for child in node.get("children", [])
    ]
    return item


def with_breadcrumb_urls(
    breadcrumbs: list[dict[str, str]],
    *,
    employee_id: str,
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
) -> list[dict[str, str]]:
    return [
        {
            **crumb,
            "url": browse_url(
                employee_id,
                folder=crumb["path"],
                q=q,
                event_type=event_type,
                visibility=visibility,
                boi_type=boi_type,
            ),
        }
        for crumb in breadcrumbs
    ]


def event_type_url(event_type: str, employee_id: str) -> str:
    return f"/event-types/{event_type}?" + urlencode({"employee_id": employee_id})


def event_type_okf_uri(event_type: str) -> str:
    return f"/public/event-types/{event_type}.md"


def event_run_example(event_type: str, employee_id: str) -> str:
    workflow, stage, _event_def = workflow_for_event_type(event_type, employee_id)
    if workflow and event_type == str(workflow.get("entry_event") or workflow.get("first_event_type") or ""):
        workflow_key = str(workflow.get("workflow_key") or "")
        return (
            f'curl -X POST "http://localhost:8000/api/workflows/{workflow_key}/start?employee_id={employee_id}" '
            '-H "Content-Type: application/json" '
            f'-d \'{{"user_confirmed":true,"payload":{{"title":"{event_label(event_type)}","workflow":"{workflow_key}"}}}}\''
        )
    return f"python scripts/publish_event.py {event_type} --employee {employee_id}"


def event_context_for_template(event_type: str, employee_id: str) -> dict[str, Any] | None:
    if not event_type:
        return None
    event_def = get_event_type(event_type)
    if not event_def:
        return {"event_type": event_type, "name_ko": event_type, "detail_url": event_type_url(event_type, employee_id)}
    return {
        **event_def,
        "detail_url": event_type_url(event_type, employee_id),
        "stream_url": "/events?" + urlencode({"employee_id": employee_id, "event_type": event_type}),
        "actions_url": "/actions?" + urlencode({"employee_id": employee_id, "event_type": event_type}),
        "clear_url": browse_url(employee_id),
        "run_example": event_run_example(event_type, employee_id),
    }


def filter_docs(
    docs: list[dict[str, Any]],
    *,
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
    archive_status: str = "active",
) -> list[dict[str, Any]]:
    filtered = docs
    if q:
        q_lower = q.lower()
        filtered = [
            d
            for d in filtered
            if q_lower in json.dumps(d["metadata"], ensure_ascii=False, default=str).lower()
            or q_lower in d["body"].lower()
        ]
        filtered = [
            item
            for _score, _index, item in sorted(
                (-doc_query_score(item, q_lower), index, item) for index, item in enumerate(filtered)
            )
        ]
    if event_type:
        filtered = [d for d in filtered if d["metadata"].get("event_type") == event_type]
    if visibility:
        filtered = [d for d in filtered if d["metadata"].get("visibility") == visibility]
    if boi_type:
        filtered = [d for d in filtered if d["metadata"].get("type") == boi_type]
    if archive_status and archive_status != "all":
        filtered = [d for d in filtered if d["metadata"].get("archive_status", "active") == archive_status]
    return filtered


def doc_query_score(doc: dict[str, Any], query: str) -> int:
    if not query:
        return 0
    query = str(query or "").lower()
    metadata = doc.get("metadata") or {}
    title = str(metadata.get("title") or "").lower()
    boi_id = str(metadata.get("boi_id") or "").lower()
    uri = str(doc.get("uri") or "").lower()
    description = str(metadata.get("description") or "").lower()
    tags = " ".join(str(tag) for tag in metadata.get("tags") or []).lower()
    body = str(doc.get("body") or "").lower()
    score = 0
    if query in title:
        score += 100
    if query in boi_id or query in uri:
        score += 80
    if query in description:
        score += 40
    if query in tags:
        score += 30
    if query in body:
        score += 10
    return score


def doc_search_blob(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata") or {}
    return "\n".join(
        [
            json.dumps(metadata, ensure_ascii=False, default=str),
            str(metadata.get("title") or ""),
            str(metadata.get("description") or ""),
            str(metadata.get("boi_id") or ""),
            str(doc.get("body") or ""),
        ]
    ).lower()


def doc_metadata_search_blob(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata") or {}
    return "\n".join(
        [
            str(metadata.get("title") or ""),
            str(metadata.get("description") or ""),
            str(metadata.get("boi_id") or ""),
            str(metadata.get("type") or ""),
            " ".join(str(tag) for tag in metadata.get("tags") or []),
        ]
    ).lower()


def stable_doc_ref(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata") or {}
    return str(metadata.get("boi_id") or doc.get("uri") or "")


def doc_result_item(doc: dict[str, Any], employee_id: str, *, score: int = 0, match_reason: str = "") -> dict[str, Any]:
    metadata = doc.get("metadata") or {}
    ref = stable_doc_ref(doc)
    access = access_policy_for_doc(doc, employee_id)
    visible_metadata = metadata
    title = metadata.get("title")
    description = metadata.get("description")
    url = doc_url_for_ref(ref, employee_id) if ref else ""
    if not access.can_use_in_agent_context:
        visible_metadata = {
            "boi_id": metadata.get("boi_id"),
            "type": metadata.get("type"),
            "title": metadata.get("title"),
            "visibility": metadata.get("visibility"),
            "classification": access.classification,
            "status": metadata.get("status"),
        }
        description = "보안 등급 정책에 따라 Agent context에는 원문과 상세 metadata를 사용하지 않습니다."
    if not access.can_cite:
        url = ""
    return {
        "kind": "boi",
        "score": score,
        "match_reason": match_reason,
        "boi_id": metadata.get("boi_id"),
        "title": title,
        "description": description,
        "type": metadata.get("type"),
        "visibility": metadata.get("visibility"),
        "status": metadata.get("status"),
        "uri": doc.get("uri"),
        "folder": doc_folder(doc),
        "url": url,
        "metadata": visible_metadata,
        "access": access.to_dict(),
    }


def dictionary_scope_for_doc(doc: dict[str, Any], employee_id: str) -> str:
    metadata = doc.get("metadata") or {}
    visibility = str(metadata.get("visibility") or "")
    uri = str(doc.get("uri") or "")
    if visibility == "private" or uri.startswith(f"/private/{employee_id}/"):
        return "private"
    if visibility == "team" or uri.startswith("/team/"):
        return "team"
    return "public"


def dictionary_priority(scope: str) -> int:
    return {"private": 0, "team": 1, "public": 2}.get(scope, 9)


def is_dictionary_doc(doc: dict[str, Any]) -> bool:
    metadata = doc.get("metadata") or {}
    uri = str(doc.get("uri") or "")
    return str(metadata.get("type") or "") == "boi/dictionary-term" or "/dictionary/" in uri


def dictionary_term_for_doc(doc: dict[str, Any], employee_id: str) -> dict[str, Any]:
    metadata = doc.get("metadata") or {}
    term = str(metadata.get("term") or metadata.get("title") or "").strip()
    aliases = [str(item).strip() for item in metadata.get("aliases") or [] if str(item).strip()]
    links = metadata.get("links") or metadata.get("related_docs") or []
    scope = dictionary_scope_for_doc(doc, employee_id)
    ref = stable_doc_ref(doc)
    return {
        "term": term,
        "definition": metadata.get("definition") or metadata.get("description") or "",
        "aliases": aliases,
        "domain": metadata.get("domain") or "",
        "examples": metadata.get("examples") or [],
        "links": links,
        "related_terms": metadata.get("related_terms") or [],
        "broader": metadata.get("broader") or [],
        "narrower": metadata.get("narrower") or [],
        "same_as": metadata.get("same_as") or [],
        "maps_to_event_type": metadata.get("maps_to_event_type") or "",
        "maps_to_action_key": metadata.get("maps_to_action_key") or "",
        "maps_to_sop": metadata.get("maps_to_sop") or "",
        "scope": scope,
        "priority": dictionary_priority(scope),
        "boi_id": metadata.get("boi_id") or "",
        "uri": doc.get("uri") or "",
        "url": doc_url_for_ref(ref, employee_id) if ref else "",
    }


def dictionary_terms_for_employee(employee_id: str, scope: str = "all") -> list[dict[str, Any]]:
    return dictionary_terms_from_docs(accessible_docs(employee_id), employee_id, scope=scope)


def dictionary_terms_from_docs(docs: list[dict[str, Any]], employee_id: str, scope: str = "all") -> list[dict[str, Any]]:
    docs = [doc for doc in docs if is_dictionary_doc(doc) and access_policy_for_doc(doc, employee_id).can_use_in_agent_context]
    terms = [dictionary_term_for_doc(doc, employee_id) for doc in docs]
    if scope and scope != "all":
        terms = [term for term in terms if term.get("scope") == scope]
    terms.sort(key=lambda item: (item.get("priority", 9), str(item.get("term") or "").lower()))
    return terms


def normalize_search_token(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def resolve_dictionary_query_from_terms(query: str, terms: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_search_token(query)
    matches: list[dict[str, Any]] = []
    for term in terms:
        candidates = [term.get("term", ""), *(term.get("aliases") or [])]
        haystack = "\n".join(str(candidate) for candidate in candidates).lower()
        if not normalized or normalized in haystack or any(normalize_search_token(candidate) in normalized for candidate in candidates if candidate):
            matches.append(term)
    matches.sort(key=lambda item: (item.get("priority", 9), -len(str(item.get("term") or ""))))
    expansion: list[str] = [query] if query else []
    for term in matches[:8]:
        expansion.extend([str(term.get("term") or ""), *[str(alias) for alias in term.get("aliases") or []]])
        for key in ("maps_to_event_type", "maps_to_action_key", "maps_to_sop"):
            value = str(term.get(key) or "")
            if value:
                expansion.append(value)
        expansion.extend(str(item) for item in term.get("related_terms") or [])
    unique_expansion = [item for item in dict.fromkeys(item.strip() for item in expansion if str(item).strip())]
    return {
        "query": query,
        "matches": matches,
        "canonical_terms": [term for term in matches[:3]],
        "expanded_terms": unique_expansion,
    }


def resolve_dictionary_query(query: str, employee_id: str, *, scope: str = "all") -> dict[str, Any]:
    return resolve_dictionary_query_from_terms(query, dictionary_terms_for_employee(employee_id, scope=scope))


def search_tokens_for_query(query: str, employee_id: str, *, dictionary: dict[str, Any] | None = None) -> list[str]:
    resolved = dictionary or resolve_dictionary_query(query, employee_id)
    tokens = list(resolved.get("expanded_terms") or [])
    tokens.extend(re.findall(r"[\w가-힣.:/-]+", query or ""))
    return [normalize_search_token(token) for token in dict.fromkeys(tokens) if normalize_search_token(token)]


def weighted_text_score(blob: str, tokens: list[str], *, title: str = "", id_text: str = "", description: str = "") -> int:
    if not tokens:
        return 0
    blob_lower = blob.lower()
    title_lower = title.lower()
    id_lower = id_text.lower()
    description_lower = description.lower()
    score = 0
    for token in tokens:
        if not token:
            continue
        if token in title_lower:
            score += 100
        if token in id_lower:
            score += 80
        if token in description_lower:
            score += 40
        if token in blob_lower:
            score += 12
    return score


def search_index_for_employee(employee_id: str) -> dict[str, Any]:
    signature = (
        markdown_signature(),
        glob_signature(EVENT_CATALOG_ROOT, "*.yaml"),
        glob_signature(ACTION_CATALOG_ROOT, "*.yaml"),
    )
    cached = _SEARCH_INDEX_CACHE.get("by_employee", {}).get(employee_id)
    if _SEARCH_INDEX_CACHE.get("signature") == signature and cached:
        return cached
    docs = accessible_docs(employee_id)
    doc_records = []
    for doc in docs:
        metadata = doc.get("metadata") or {}
        access = access_policy_for_doc(doc, employee_id)
        ref = stable_doc_ref(doc)
        doc_records.append(
            {
                "ref": ref,
                "doc": doc,
                "blob": doc_search_blob(doc) if access.can_use_in_agent_context else doc_metadata_search_blob(doc),
                "title": str(metadata.get("title") or ""),
                "id_text": "\n".join([str(metadata.get("boi_id") or ""), str(doc.get("uri") or "")]),
                "description": str(metadata.get("description") or ""),
                "type": str(metadata.get("type") or ""),
                "access": access.to_dict(),
            }
        )
    index = {
        "docs": docs,
        "doc_records": doc_records,
        "dictionary": dictionary_terms_from_docs(docs, employee_id),
        "event_types": load_event_types(),
        "actions": load_action_catalog(),
    }
    if _SEARCH_INDEX_CACHE.get("signature") != signature:
        _SEARCH_INDEX_CACHE["signature"] = signature
        _SEARCH_INDEX_CACHE["by_employee"] = {}
    _SEARCH_INDEX_CACHE["by_employee"][employee_id] = index
    return index


def action_doc_url(action: dict[str, Any], employee_id: str) -> str:
    doc_ref = str(action.get("doc_ref") or "")
    return doc_url_for_ref(doc_ref, employee_id) if doc_ref else ""


def ontology_item_identity(item: dict[str, Any]) -> str:
    """Return a stable semantic identity for cross-group ontology results.

    The ontology response intentionally exposes grouped views for documents,
    event catalog entries, and action catalog entries. The flat best_matches
    list should not repeat the same business concept just because it was found
    through more than one source, such as an event catalog row and its BoI doc.
    """
    if not isinstance(item, dict):
        return ""
    kind = str(item.get("kind") or "")
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    boi_type = str(item.get("type") or metadata.get("type") or "")
    boi_id = str(item.get("boi_id") or metadata.get("boi_id") or "")
    event_type = str(item.get("event_type") or metadata.get("event_type") or "")
    action_key = str(item.get("action_key") or metadata.get("action_key") or "")
    doc_ref = str(item.get("doc_ref") or "")
    if not action_key and isinstance(metadata.get("action_gateway_mapping"), dict):
        action_key = str(metadata.get("action_gateway_mapping", {}).get("action_key") or "")
    if kind == "event_type" or boi_type == "boi/event-type":
        if event_type:
            return f"event:{event_type}"
        if boi_id.startswith("boi:public:event-types:"):
            return f"event:{boi_id.removeprefix('boi:public:event-types:')}"
    if kind == "action" or boi_type == "boi/action-spec":
        if action_key:
            return f"action:{action_key}"
        if doc_ref:
            return f"doc:{doc_ref}"
    if doc_ref:
        return f"doc:{doc_ref}"
    if boi_id:
        return f"doc:{boi_id}"
    for key in ("log_ref", "request_id", "url", "term", "title"):
        value = str(item.get(key) or "")
        if value:
            return f"{key}:{value}"
    return ""


def dedupe_ontology_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = ontology_item_identity(item)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        deduped.append(item)
    return deduped


def ontology_search_payload(
    query: str,
    employee_id: str,
    *,
    scope: str = "all",
    limit: int = 8,
    current_url: str = "",
    view: str = "full",
) -> dict[str, Any]:
    query = str(query or "").strip()
    effective_limit = max(1, min(int(limit or 8), 50))
    index = search_index_for_employee(employee_id)
    dictionary_terms = index.get("dictionary") or []
    if scope in {"private", "team", "public"}:
        dictionary_terms = [term for term in dictionary_terms if term.get("scope") == scope]
    dictionary = resolve_dictionary_query_from_terms(query, dictionary_terms)
    tokens = search_tokens_for_query(query, employee_id, dictionary=dictionary)

    doc_hits: list[tuple[int, dict[str, Any]]] = []
    for record in index["doc_records"]:
        score = weighted_text_score(
            record["blob"],
            tokens,
            title=record["title"],
            id_text=record["id_text"],
            description=record["description"],
        )
        if not query:
            score = 1
        if score > 0:
            doc_hits.append((score, record["doc"]))
    doc_hits.sort(key=lambda item: (-item[0], metadata_sort_value((item[1].get("metadata") or {}).get("timestamp"))), reverse=False)
    doc_items = [doc_result_item(doc, employee_id, score=score, match_reason="document") for score, doc in doc_hits[: effective_limit * 3]]

    sop_items = [item for item in doc_items if is_official_sop_doc({"metadata": item.get("metadata") or {}, "uri": item.get("uri") or "", "path": ""})][:effective_limit]
    dictionary_items = dictionary["matches"][:effective_limit]

    event_items: list[dict[str, Any]] = []
    for event_def in index["event_types"]:
        blob = event_type_search_blob(event_def)
        score = weighted_text_score(
            blob,
            tokens,
            title=str(event_def.get("name_ko") or event_def.get("event_type") or ""),
            id_text=str(event_def.get("event_type") or ""),
            description=str(event_def.get("description") or ""),
        )
        if score > 0 or any(str(term.get("maps_to_event_type") or "") == str(event_def.get("event_type") or "") for term in dictionary["matches"]):
            event_items.append(
                {
                    "kind": "event_type",
                    "score": score or 90,
                    "event_type": event_def.get("event_type"),
                    "title": event_def.get("name_ko") or event_def.get("event_type"),
                    "description": event_def.get("description") or "",
                    "workflow_stage": event_def.get("workflow_stage") or "",
                    "sop_ref": event_def.get("sop_ref") or "",
                    "url": event_type_url(str(event_def.get("event_type") or ""), employee_id),
                }
            )
    event_items.sort(key=lambda item: -int(item.get("score") or 0))

    action_items: list[dict[str, Any]] = []
    for action in index["actions"]:
        blob = json.dumps(action, ensure_ascii=False, default=str).lower()
        score = weighted_text_score(
            blob,
            tokens,
            title=str(action.get("name") or action.get("name_ko") or action.get("action_key") or ""),
            id_text=str(action.get("action_key") or ""),
            description=str(action.get("description") or ""),
        )
        if score > 0 or any(str(term.get("maps_to_action_key") or "") == str(action.get("action_key") or "") for term in dictionary["matches"]):
            action_items.append(
                {
                    "kind": "action",
                    "score": score or 90,
                    "action_key": action.get("action_key"),
                    "title": action.get("name") or action.get("name_ko") or action.get("action_key"),
                    "description": action.get("description") or "",
                    "connector_kind": action.get("connector_kind") or action.get("type") or "",
                    "doc_ref": action.get("doc_ref") or "",
                    "url": action_doc_url(action, employee_id),
                }
            )
    action_items.sort(key=lambda item: -int(item.get("score") or 0))

    runtime_items: list[dict[str, Any]] = []
    runtime_token_pattern = re.compile(r"\b(trace-|evt-|act-|request_id|log_ref|action:|event:)", re.IGNORECASE)
    include_runtime_evidence = scope == "runtime_evidence" or bool(runtime_token_pattern.search(query))
    if query and include_runtime_evidence:
        for row in read_action_logs(limit=200):
            if not action_log_visible_to_employee(row, employee_id):
                continue
            blob = json.dumps(row, ensure_ascii=False, default=str).lower()
            score = weighted_text_score(blob, tokens, id_text=str(row.get("request_id") or row.get("action_key") or ""))
            if score > 0:
                result_status = row.get("result", {}).get("status") if isinstance(row.get("result"), dict) else ""
                runtime_items.append(
                    {
                        "kind": "action_log",
                        "score": score,
                        "title": row.get("action_key") or row.get("request_id") or "Action log",
                        "description": row.get("status") or result_status or "",
                        "trace_id": row.get("trace_id") or "",
                        "log_ref": row.get("_log_ref") or "",
                        "url": action_raw_page_url(str(row.get("_log_ref") or ""), employee_id) if row.get("_log_ref") else "",
                    }
                )
        runtime_items.sort(key=lambda item: -int(item.get("score") or 0))

    groups = {
        "sop": sop_items[:effective_limit],
        "event_types": event_items[:effective_limit],
        "actions": action_items[:effective_limit],
        "boi_documents": doc_items[:effective_limit],
        "dictionary": dictionary_items[:effective_limit],
        "runtime_evidence": runtime_items[:effective_limit],
    }
    if scope != "all":
        groups = {scope: groups.get(scope, [])}

    best_matches: list[dict[str, Any]] = []
    for items in groups.values():
        best_matches.extend(items if isinstance(items, list) else [])
    best_matches.sort(key=lambda item: -int(item.get("score") or 0))
    best_matches = dedupe_ontology_items(best_matches)

    graph_paths = []
    for item in best_matches[:3]:
        ref = str(item.get("boi_id") or item.get("doc_ref") or "")
        if not ref:
            continue
        doc = find_doc_by_id(ref, employee_id)
        if not doc:
            continue
        relationship = relationship_context_for_doc(doc, employee_id, graph=okf_graph_for_docs([doc], employee_id))
        graph_paths.append(
            {
                "source": okf_concept_id_for_doc(doc),
                "outgoing_count": len(relationship.get("outgoing") or []),
                "backlink_count": 0,
                "url": doc_url_for_ref(stable_doc_ref(doc), employee_id),
            }
        )

    citations: list[dict[str, Any]] = []
    seen_citation_keys: set[str] = set()
    for item in best_matches[:effective_limit]:
        access = item.get("access") if isinstance(item, dict) and isinstance(item.get("access"), dict) else {}
        if access.get("can_cite") is False:
            continue
        label = str(item.get("title") or item.get("term") or item.get("event_type") or item.get("action_key") or item.get("boi_id") or item.get("uri") or "")
        ref = str(item.get("boi_id") or item.get("doc_ref") or item.get("event_type") or item.get("action_key") or item.get("term") or "")
        url = str(item.get("url") or "")
        key = url or ref or label
        if not key or key in seen_citation_keys:
            continue
        seen_citation_keys.add(key)
        citations.append({"label": label or ref, "ref": ref, "url": url, "kind": item.get("kind") or ""})
        if len(citations) >= 5:
            break

    payload = {
        "ok": True,
        "query": query,
        "scope": scope,
        "employee_id": employee_id,
        "current_url": current_url,
        "query_expansion": dictionary.get("expanded_terms", []),
        "used_dictionary_terms": dictionary_items,
        "knowledge_panel": {
            "interpreted_as": [term.get("term") for term in dictionary.get("canonical_terms") or []],
            "top_sop": groups.get("sop", [])[:1],
            "top_event_type": groups.get("event_types", [])[:1],
            "top_action": groups.get("actions", [])[:1],
        },
        "groups": groups,
        "best_matches": best_matches[:effective_limit],
        "graph_paths": graph_paths,
        "citations": citations,
        "document_rank_refs": list(dict.fromkeys(str(item.get("boi_id") or item.get("uri") or "") for item in doc_items)),
    }
    if str(view or "").lower() == "compact":
        return compact_ontology_payload(payload)
    return payload


def compact_ontology_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return item
    keys = (
        "kind",
        "score",
        "match_reason",
        "boi_id",
        "uri",
        "title",
        "description",
        "type",
        "visibility",
        "status",
        "folder",
        "url",
        "term",
        "definition",
        "aliases",
        "event_type",
        "workflow_stage",
        "sop_ref",
        "action_key",
        "connector_kind",
        "doc_ref",
        "trace_id",
        "log_ref",
    )
    compact = {key: item.get(key) for key in keys if item.get(key) not in (None, "", [], {})}
    if compact.get("description"):
        compact["description"] = text_excerpt(str(compact["description"]), 260)
    return compact


def ontology_item_allowed_for_agent_context(item: Any) -> bool:
    if not isinstance(item, dict):
        return True
    access = item.get("access")
    if isinstance(access, dict) and access.get("can_use_in_agent_context") is False:
        return False
    return True


def compact_ontology_payload(payload: dict[str, Any]) -> dict[str, Any]:
    groups = payload.get("groups") if isinstance(payload.get("groups"), dict) else {}
    compact_groups = {
        key: [compact_ontology_item(item) for item in value if ontology_item_allowed_for_agent_context(item)]
        for key, value in groups.items()
        if isinstance(value, list)
    }
    knowledge_panel = payload.get("knowledge_panel") if isinstance(payload.get("knowledge_panel"), dict) else {}
    compact_knowledge = {}
    for key, value in knowledge_panel.items():
        if isinstance(value, list):
            compact_knowledge[key] = [compact_ontology_item(item) for item in value if ontology_item_allowed_for_agent_context(item)]
        else:
            compact_knowledge[key] = value
    best_matches = [
        item for item in payload.get("best_matches") or []
        if ontology_item_allowed_for_agent_context(item)
    ]
    citations = [
        item for item in payload.get("citations") or []
        if not (
            isinstance(item, dict)
            and isinstance(item.get("access"), dict)
            and item["access"].get("can_cite") is False
        )
    ]
    return {
        "ok": payload.get("ok", True),
        "query": payload.get("query", ""),
        "scope": payload.get("scope", "all"),
        "employee_id": payload.get("employee_id", ""),
        "current_url": payload.get("current_url", ""),
        "view": "compact",
        "query_expansion": payload.get("query_expansion") or [],
        "used_dictionary_terms": [compact_ontology_item(item) for item in payload.get("used_dictionary_terms") or []],
        "knowledge_panel": compact_knowledge,
        "groups": compact_groups,
        "best_matches": [compact_ontology_item(item) for item in best_matches],
        "graph_paths": payload.get("graph_paths") or [],
        "citations": citations,
        "document_rank_refs": [
            str(item.get("boi_id") or item.get("uri") or "")
            for item in best_matches
            if isinstance(item, dict) and (item.get("boi_id") or item.get("uri"))
        ],
    }


def filter_docs_ontology_aware(
    docs: list[dict[str, Any]],
    employee_id: str,
    *,
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
    archive_status: str = "active",
) -> list[dict[str, Any]]:
    if not q:
        return filter_docs(docs, q=q, event_type=event_type, visibility=visibility, boi_type=boi_type, archive_status=archive_status)
    base = filter_docs(docs, q="", event_type=event_type, visibility=visibility, boi_type=boi_type, archive_status=archive_status)
    payload = ontology_search_payload(q, employee_id, scope="all", limit=500)
    rank = {ref: index for index, ref in enumerate(payload.get("document_rank_refs") or []) if ref}
    ranked_docs = []
    for doc in base:
        direct_score = doc_query_score(doc, q)
        if direct_score <= 0:
            continue
        refs = [stable_doc_ref(doc), str(doc.get("uri") or "").lstrip("/")]
        best = min((rank[ref] for ref in refs if ref in rank), default=None)
        ranked_docs.append((best if best is not None else 999_999, -direct_score, doc))
    ranked_docs.sort(key=lambda item: (item[0], item[1]))
    return [doc for _rank, _score, doc in ranked_docs]


def is_sop_related_doc(doc: dict[str, Any]) -> bool:
    metadata = doc.get("metadata") or {}
    return (
        str(metadata.get("type") or "") == "boi/sop"
        or "sop" in str(metadata.get("boi_id") or "").lower()
        or "sop" in str(metadata.get("title") or "").lower()
        or "SOP" in (metadata.get("tags") or [])
    )


def is_official_sop_doc(doc: dict[str, Any]) -> bool:
    metadata = doc.get("metadata") or {}
    boi_id = str(metadata.get("boi_id") or "")
    uri = str(doc.get("uri") or "")
    return (
        str(metadata.get("type") or "") == "boi/sop"
        or ":sop:" in boi_id
        or "/sop/" in uri
        or uri.startswith("/public/sop/")
    )


def filter_sop_docs(
    docs: list[dict[str, Any]],
    *,
    q: str = "",
    visibility: str = "",
    status: str = "",
    category: str = "sop",
) -> list[dict[str, Any]]:
    normalized_category = "all-related" if category == "all-related" else "sop"
    filtered = [
        doc
        for doc in docs
        if is_sop_related_doc(doc)
        and (normalized_category == "all-related" or is_official_sop_doc(doc))
    ]
    if q:
        q_lower = q.lower()
        filtered = [doc for doc in filtered if q_lower in doc_search_blob(doc)]
    if visibility:
        filtered = [doc for doc in filtered if (doc.get("metadata") or {}).get("visibility") == visibility]
    if status:
        filtered = [doc for doc in filtered if (doc.get("metadata") or {}).get("status") == status]
    return filtered


def event_type_search_blob(event_type: dict[str, Any]) -> str:
    keys = (
        "event_type",
        "name_ko",
        "description",
        "owner",
        "topic",
        "wiki_usage",
        "workflow_stage",
        "sop_ref",
        "sop_stage_id",
        "recommended_actions",
        "recommended_manual_actions",
    )
    return "\n".join(json.dumps(event_type.get(key) or "", ensure_ascii=False, default=str) for key in keys).lower()


def filter_event_types_for_catalog(
    event_types: list[dict[str, Any]],
    *,
    q: str = "",
    status: str = "",
    owner: str = "",
    workflow_stage: str = "",
    has_sop: str = "",
) -> list[dict[str, Any]]:
    filtered = list(event_types)
    if q:
        q_lower = q.lower()
        filtered = [item for item in filtered if q_lower in event_type_search_blob(item)]
    if status:
        filtered = [item for item in filtered if str(item.get("status") or "") == status]
    if owner:
        filtered = [item for item in filtered if str(item.get("owner") or "") == owner]
    if workflow_stage:
        filtered = [item for item in filtered if str(item.get("workflow_stage") or "") == workflow_stage]
    if str(has_sop or "").lower() in {"true", "1", "yes"}:
        filtered = [item for item in filtered if item.get("sop_ref") or item.get("sop_stage_id")]
    return filtered


def docs_for_template(docs: list[dict[str, Any]], employee_id: str, folder: str | None = "") -> list[dict[str, Any]]:
    normalized_folder = normalize_folder(folder)
    items = []
    for doc in docs:
        item = dict(doc)
        item["folder"] = doc_folder(doc)
        params = {"employee_id": employee_id}
        if normalized_folder:
            params["folder"] = normalized_folder
        item["url"] = f"/docs/{doc['metadata'].get('boi_id', item['uri'].lstrip('/'))}?" + urlencode(params)
        items.append(item)
    return items


def clean_external_url(value: str | None) -> str:
    return str(value or "").strip().rstrip("/")


def first_forwarded_header_value(value: str | None) -> str:
    return str(value or "").split(",", 1)[0].strip()


def hostname_from_url_or_host(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw if "://" in raw else f"//{raw}")
    return (parsed.hostname or "").lower()


def is_local_url(value: str) -> bool:
    return hostname_from_url_or_host(value) in LOCALHOST_NAMES


def request_host(request: Request) -> str:
    return first_forwarded_header_value(request.headers.get("x-forwarded-host")) or request.headers.get("host") or request.url.netloc


def request_scheme(request: Request) -> str:
    return first_forwarded_header_value(request.headers.get("x-forwarded-proto")) or request.url.scheme or "http"


def is_local_request(request: Request) -> bool:
    return hostname_from_url_or_host(request_host(request) or (request.url.hostname or "")) in LOCALHOST_NAMES


def request_origin(request: Request) -> str:
    host = request_host(request)
    return f"{request_scheme(request)}://{host}".rstrip("/")


def boi_public_base_url(request: Request) -> str:
    configured = clean_external_url(os.getenv("BOI_EXTERNAL_URL"))
    if configured and (is_local_request(request) or not is_local_url(configured)):
        return configured
    return request_origin(request)


def port_from_url(value: str) -> int | None:
    try:
        return urlsplit(value).port
    except ValueError:
        return None


def derived_same_host_tool_url(request: Request, env_name: str, local_default: str) -> str:
    boi_base = boi_public_base_url(request)
    parsed = urlsplit(boi_base)
    hostname = parsed.hostname or hostname_from_url_or_host(request_host(request))
    if not hostname:
        return ""
    scheme = parsed.scheme or request_scheme(request)
    current_port = parsed.port
    local_tool_port = port_from_url(local_default)
    local_boi_port = int(os.getenv("BOI_API_PORT", "8000") or "8000")
    target_port = DEFAULT_EXTERNAL_TOOL_PORTS.get(env_name)
    if current_port and local_tool_port:
        offset_port = current_port + (local_tool_port - local_boi_port)
        if 0 < offset_port <= 65535:
            target_port = offset_port
    if not target_port:
        return ""
    host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    return f"{scheme}://{host}:{target_port}"


def optional_external_url(request: Request, env_name: str, local_default: str) -> str:
    configured = clean_external_url(os.getenv(env_name))
    if configured and (is_local_request(request) or not is_local_url(configured)):
        return configured
    if is_local_request(request) and is_local_url(boi_public_base_url(request)):
        return local_default.rstrip("/")
    return derived_same_host_tool_url(request, env_name, local_default)


def action_gateway_public_base_url(request: Request) -> str:
    return optional_external_url(request, "ACTION_GATEWAY_EXTERNAL_URL", "http://localhost:8100")


def langflow_public_base_url(request: Request) -> str:
    return optional_external_url(request, "LANGFLOW_EXTERNAL_URL", "http://localhost:7860")


def mcp_public_base_url(request: Request) -> str:
    return optional_external_url(request, "BOI_WIKI_MCP_EXTERNAL_URL", "http://localhost:8200")


def kafka_ui_public_base_url(request: Request) -> str:
    return optional_external_url(request, "KAFKA_UI_EXTERNAL_URL", "http://localhost:8081")


def external_url_marker(env_name: str) -> str:
    return f"<{env_name}_NOT_CONFIGURED>"


def display_url_replacements(request: Request) -> list[tuple[str, str]]:
    boi_base = boi_public_base_url(request)
    action_gateway_base = action_gateway_public_base_url(request) or external_url_marker("ACTION_GATEWAY_EXTERNAL_URL")
    langflow_base = langflow_public_base_url(request) or external_url_marker("LANGFLOW_EXTERNAL_URL")
    mcp_base = mcp_public_base_url(request) or external_url_marker("BOI_WIKI_MCP_EXTERNAL_URL")
    return [
        ("http://localhost:8000", boi_base),
        ("http://boi-api:8000", boi_base),
        ("http://localhost:8100", action_gateway_base),
        ("http://action-gateway:8100", action_gateway_base),
        ("http://localhost:7860", langflow_base),
        ("http://langflow:7860", langflow_base),
        ("http://localhost:8081", kafka_ui_public_base_url(request) or external_url_marker("KAFKA_UI_EXTERNAL_URL")),
        ("http://kafka-ui:8080", kafka_ui_public_base_url(request) or external_url_marker("KAFKA_UI_EXTERNAL_URL")),
        ("http://localhost:8200", mcp_base),
        ("http://boi-wiki-mcp:8200", mcp_base),
    ]


def rewrite_display_string(value: str, request: Request) -> str:
    rewritten = str(value)
    for source, target in display_url_replacements(request):
        rewritten = rewritten.replace(source, target)
    return rewritten


def rewrite_display_value(value: Any, request: Request) -> Any:
    if isinstance(value, str):
        return rewrite_display_string(value, request)
    if isinstance(value, dict):
        return {key: rewrite_display_value(item, request) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_display_value(item, request) for item in value]
    return value


def display_curl_for_action_spec(curl: str | None, request: Request) -> tuple[str, str]:
    if not curl:
        return "", ""
    rewritten = rewrite_display_string(curl, request)
    if "_EXTERNAL_URL_NOT_CONFIGURED" in rewritten:
        return "", "External invoke URL is not configured for this deployment."
    return rewritten, ""


def metadata_rows_for_template(metadata: dict[str, Any], request: Request | None = None) -> list[dict[str, Any]]:
    display_metadata = metadata
    if request is not None and metadata.get("type") == "boi/action-spec":
        display_metadata = rewrite_display_value(metadata, request)
    return [{"key": str(key), "value_html": render_value_html(value)} for key, value in display_metadata.items()]


METADATA_SUMMARY_KEYS = (
    ("type", ("type",)),
    ("boi_id", ("boi_id",)),
    ("visibility", ("visibility",)),
    ("status", ("status",)),
    ("event_type", ("event_type",)),
    ("source_event.trace", ("source_event", "trace")),
    ("source_event.trace_id", ("source_event", "trace_id")),
    ("workflow_key", ("workflow", "workflow_key")),
)


def nested_metadata_value(metadata: dict[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = metadata
    for key in path:
        if not isinstance(value, dict) or key not in value:
            return None
        value = value.get(key)
    return value


def metadata_summary_rows_for_template(metadata: dict[str, Any], request: Request | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, path in METADATA_SUMMARY_KEYS:
        value = nested_metadata_value(metadata, path)
        if value in (None, "", [], {}):
            continue
        display_value = rewrite_display_value(value, request) if request is not None and metadata.get("type") == "boi/action-spec" else value
        rows.append({"key": label, "value_html": render_value_html(display_value)})
    return rows


def metadata_fragment_html_for_doc(doc: dict[str, Any], request: Request | None = None) -> Markup:
    rows = metadata_rows_for_template(doc["metadata"], request)
    items = [
        f'<dt class="metadata-key">{html_escape(row["key"])}</dt><dd class="metadata-value">{row["value_html"]}</dd>'
        for row in rows
    ]
    return Markup(f'<dl class="metadata-grid">{"".join(items)}</dl>')


def action_spec_for_template(metadata: dict[str, Any], request: Request) -> dict[str, Any] | None:
    if metadata.get("type") != "boi/action-spec":
        return None
    connector_kind = str(metadata.get("connector_kind") or "")
    request_fields = ["request_schema", "input_schema", "example_request", "example_tool_call"]
    response_fields = ["response_schema", "output_schema", "example_response"]
    display_url = rewrite_display_value(metadata.get("url") or metadata.get("mcp_server"), request)
    gateway_mapping = rewrite_display_value(metadata.get("action_gateway_mapping") or {}, request)
    curl, curl_note = display_curl_for_action_spec(metadata.get("curl"), request)
    return {
        "action_key": metadata.get("action_key"),
        "connector_kind": connector_kind,
        "execution_mode": metadata.get("execution_mode"),
        "endpoint_label": "MCP Tool" if connector_kind == "mcp" else "Endpoint",
        "method": metadata.get("method") or "POST",
        "url": display_url,
        "protocol": metadata.get("protocol"),
        "auth_html": render_value_html(metadata.get("auth") or {}),
        "headers_html": render_value_html(metadata.get("headers") or {}),
        "request_rows": [
            {"key": field, "value_html": render_value_html(rewrite_display_value(metadata.get(field), request))}
            for field in request_fields
            if metadata.get(field) is not None
        ],
        "response_rows": [
            {"key": field, "value_html": render_value_html(rewrite_display_value(metadata.get(field), request))}
            for field in response_fields
            if metadata.get(field) is not None
        ],
        "gateway_html": render_value_html(gateway_mapping),
        "curl": curl,
        "curl_note": curl_note,
        "security_html": render_value_html(metadata.get("security_notes")),
        "mcp_tool_name": metadata.get("tool_name"),
        "mcp_transport": metadata.get("transport"),
    }


def materialized_log_paths() -> list[Path]:
    paths: list[Path] = []
    for root in (EVENTS_ROOT, ACTION_LOG_ROOT):
        if root.exists():
            paths.extend(sorted(root.glob("*.jsonl"), reverse=True))
    return paths


def item_to_recovered_doc(item: dict[str, Any]) -> dict[str, Any] | None:
    metadata = item.get("metadata")
    body = item.get("body")
    if not isinstance(metadata, dict) or not isinstance(body, str):
        return None
    if validate_okf_metadata(metadata):
        return None
    uri = str(item.get("uri") or "")
    if not uri:
        owner = str(metadata.get("owner") or DEMO_EMPLOYEE_ID)
        uri = f"/private/{owner}/{safe_filename(str(metadata.get('boi_id') or 'recovered-boi'))}.md"
    source_event = metadata.get("source_event") or {}
    event_type = metadata.get("event_type") or source_event.get("event_type")
    if event_type:
        metadata.setdefault("event_type", event_type)
    return {
        "path": str(DATA_ROOT / uri.lstrip("/")),
        "uri": uri,
        "metadata": metadata,
        "body": body,
        "visibility": metadata.get("visibility", "unknown"),
        "event_type": event_type,
        "recovered_from_log": True,
    }


def recovered_doc_indexes() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    signature = materialized_log_signature()
    if _RECOVERED_DOC_CACHE["signature"] == signature:
        return _RECOVERED_DOC_CACHE["by_boi_id"], _RECOVERED_DOC_CACHE["by_uri"]
    by_boi_id: dict[str, dict[str, Any]] = {}
    by_uri: dict[str, dict[str, Any]] = {}
    for row in cached_event_log_rows() + cached_action_log_rows():
        for item in iter_materialized_items(row):
            doc = item_to_recovered_doc(item)
            if not doc:
                continue
            boi_id = str(doc["metadata"].get("boi_id") or "")
            uri = str(doc.get("uri") or "").lstrip("/")
            if boi_id:
                by_boi_id.setdefault(boi_id, doc)
            if uri:
                by_uri.setdefault(uri, doc)
                if uri.endswith(".md"):
                    by_uri.setdefault(uri[:-3], doc)
    _RECOVERED_DOC_CACHE["signature"] = signature
    _RECOVERED_DOC_CACHE["by_boi_id"] = by_boi_id
    _RECOVERED_DOC_CACHE["by_uri"] = by_uri
    return by_boi_id, by_uri


def find_recovered_doc_by_id(
    boi_id: str,
    employee_id: str | None = None,
    *,
    include_inaccessible: bool = False,
) -> dict[str, Any] | None:
    normalized_uri = boi_id.lstrip("/")
    by_boi_id, by_uri = recovered_doc_indexes()
    candidates = [by_boi_id.get(boi_id), by_uri.get(normalized_uri)]
    if normalized_uri.endswith(".md"):
        candidates.append(by_uri.get(normalized_uri[:-3]))
    for doc in candidates:
        if doc and (include_inaccessible or employee_id is None or is_accessible(doc, employee_id)):
            return doc
    return None


def find_doc_by_id(
    boi_id: str,
    employee_id: str | None = None,
    *,
    include_inaccessible: bool = False,
) -> dict[str, Any] | None:
    normalized_uri = boi_id.lstrip("/")
    normalized_concept_id = normalized_uri[:-3] if normalized_uri.endswith(".md") else normalized_uri
    path = find_doc_path_by_ref(boi_id)
    if path:
        try:
            doc = read_doc(path)
        except Exception:
            doc = None
        if doc:
            doc_uri = doc.get("uri", "").lstrip("/")
            doc_concept_id = doc_uri[:-3] if doc_uri.endswith(".md") else doc_uri
            if doc["metadata"].get("boi_id") == boi_id or doc_uri == normalized_uri or doc_concept_id == normalized_concept_id:
                if include_inaccessible or employee_id is None or is_accessible(doc, employee_id):
                    return doc
    return find_recovered_doc_by_id(boi_id, employee_id, include_inaccessible=include_inaccessible)


def doc_url_for_ref(ref: str, employee_id: str) -> str:
    return f"/docs/{ref}?" + urlencode({"employee_id": employee_id})


def okf_concept_id_for_doc(doc: dict[str, Any]) -> str:
    uri = str(doc.get("uri") or "").lstrip("/")
    return uri[:-3] if uri.endswith(".md") else uri


def okf_graph_for_docs(docs: list[dict[str, Any]], employee_id: str) -> dict[str, Any]:
    node_map: dict[str, dict[str, Any]] = {}
    outgoing_by_source: dict[str, list[dict[str, Any]]] = {}
    incoming_by_target: dict[str, list[dict[str, Any]]] = {}
    for doc in docs:
        concept_id = okf_concept_id_for_doc(doc)
        metadata = doc["metadata"]
        node_map[concept_id] = {
            "concept_id": concept_id,
            "uri": doc.get("uri"),
            "boi_id": metadata.get("boi_id"),
            "title": metadata.get("title") or concept_id,
            "type": metadata.get("type"),
            "tags": metadata.get("tags") or [],
            "url": doc_url_for_ref(str(metadata.get("boi_id") or doc.get("uri", "").lstrip("/")), employee_id),
            "backlinks": [],
        }
    edge_by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for doc in docs:
        path = Path(doc["path"])
        if not path.exists() or not str(path).startswith(str(DATA_ROOT)):
            continue
        for edge in markdown_link_edges(path, doc["body"], DATA_ROOT):
            key = (
                str(edge.get("source") or ""),
                str(edge.get("target") or ""),
                str(edge.get("href") or ""),
                str(edge.get("label") or ""),
            )
            rendered_edge = edge_by_key.get(key)
            if rendered_edge is None:
                rendered_edge = dict(edge)
                rendered_edge["source_url"] = node_map.get(edge["source"], {}).get("url", "")
                rendered_edge["target_url"] = node_map.get(edge["target"], {}).get("url", "")
                rendered_edge["occurrence_count"] = 1
                edge_by_key[key] = rendered_edge
            else:
                rendered_edge["occurrence_count"] = int(rendered_edge.get("occurrence_count") or 1) + 1
    edges = list(edge_by_key.values())
    for edge in edges:
        outgoing_by_source.setdefault(edge["source"], []).append(edge)
        incoming_by_target.setdefault(edge["target"], []).append(edge)
        if edge["target"] in node_map and edge["source"] not in node_map[edge["target"]]["backlinks"]:
            node_map[edge["target"]]["backlinks"].append(edge["source"])
    nodes = sorted(node_map.values(), key=lambda item: item["concept_id"])
    edges = sorted(edges, key=lambda item: (item["source"], item["target"], item["label"]))
    for edge_list in outgoing_by_source.values():
        edge_list.sort(key=lambda item: (item["target"], item["label"]))
    for edge_list in incoming_by_target.values():
        edge_list.sort(key=lambda item: (item["source"], item["label"]))
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "outgoing_by_source": outgoing_by_source,
        "incoming_by_target": incoming_by_target,
    }


_OKF_GRAPH_CACHE: dict[tuple[str, tuple[tuple[str, str], ...]], dict[str, Any]] = {}
_IDENTITY_CACHE: dict[str, AuthIdentity] = {}


def remember_identity(identity: AuthIdentity) -> AuthIdentity:
    _IDENTITY_CACHE[identity.employee_id] = identity
    return identity


def identity_for_employee(employee_id: str) -> AuthIdentity:
    return _IDENTITY_CACHE.get(employee_id) or dev_identity(employee_id)


def app_url(path: str, employee_id: str, **params: str) -> str:
    query = {"employee_id": employee_id}
    query.update({key: value for key, value in params.items() if value})
    return f"{path}?" + urlencode(query)


def shell_hidden_query(request: Request) -> list[dict[str, str]]:
    return [
        {"name": key, "value": value}
        for key, value in request.query_params.multi_items()
        if key != "employee_id"
    ]


def app_shell_context(
    request: Request,
    employee_id: str,
    *,
    active_nav: str,
    title: str,
    description: str = "",
    page_actions: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    identity = identity_for_employee(employee_id)
    mode = auth_mode()
    primary_nav = [
        {"id": "library", "label": "BoI Wiki", "href": app_url("/", employee_id)},
        {"id": "sops", "label": "SOP", "href": app_url("/sops", employee_id)},
        {"id": "event_types", "label": "Event Types", "href": app_url("/event-types", employee_id)},
        {"id": "events", "label": "Event Stream", "href": app_url("/events", employee_id)},
        {"id": "actions", "label": "Actions", "href": app_url("/actions", employee_id)},
    ]
    utility_links = [
        {"label": "권한 관리", "href": app_url("/permissions", employee_id), "external": False},
        {"label": "API Docs", "href": "/docs", "external": True},
    ]
    optional_tools = [
        ("Langflow", langflow_public_base_url(request)),
        ("Kafka UI", kafka_ui_public_base_url(request)),
        ("MCP Status", mcp_public_base_url(request)),
    ]
    for label, href in optional_tools:
        if href:
            utility_links.append({"label": label, "href": href, "external": True})
    return {
        "title": title,
        "description": description,
        "active_nav": active_nav,
        "primary_nav": primary_nav,
        "utility_links": utility_links,
        "page_actions": page_actions or [],
        "auth_mode": mode,
        "dev_mode": mode == "dev",
        "sso_active": mode != "dev",
        "auth_label": "DEV 인증" if mode == "dev" else "SSO active",
        "auth_detail": "SSO 비활성 · employee_id query 허용" if mode == "dev" else "Keycloak/HCP",
        "identity": identity,
        "employee_id": identity.employee_id,
        "display_name": identity.display_name or identity.employee_id,
        "teams": identity.teams,
        "roles": identity.roles,
        "hidden_query": shell_hidden_query(request),
        "switch_action": request.url.path,
        "dev_users": [
            {"employee_id": key, "label": key}
            for key in sorted(USER_NAMES)
        ],
        "logout_url": "/auth/logout?" + urlencode({"next": request.url.path}),
        "sso_guide_url": app_url("/docs/boi:public:boi-wiki-manual:security:sso-and-permissions", employee_id),
    }


def active_nav_for_doc(doc: dict[str, Any]) -> str:
    metadata = doc.get("metadata") or {}
    boi_type = str(metadata.get("type") or "")
    uri = str(doc.get("uri") or "")
    boi_id = str(metadata.get("boi_id") or "")
    if boi_type == "boi/sop" or "/sop/" in uri or ":sop:" in boi_id:
        return "sops"
    if boi_type == "boi/action-spec" or "/actions/" in uri or ":actions:" in boi_id:
        return "actions"
    if "/event-types/" in uri or ":event-types:" in boi_id:
        return "event_types"
    return "library"


def docs_cache_signature(docs: list[dict[str, Any]]) -> tuple[tuple[str, str], ...]:
    cached_markdown_sig = _DOCS_CACHE.get("signature")
    if cached_markdown_sig:
        docset_hash = hashlib.sha1(
            "\n".join(sorted(str(doc.get("uri") or okf_concept_id_for_doc(doc)) for doc in docs)).encode("utf-8")
        ).hexdigest()
        extra: list[tuple[str, str]] = []
        for doc in docs:
            if doc.get("recovered_from_log"):
                payload = json.dumps(doc.get("metadata") or {}, ensure_ascii=False, sort_keys=True, default=str) + "\n" + str(doc.get("body") or "")
                extra.append((str(doc.get("uri") or okf_concept_id_for_doc(doc)), hashlib.sha1(payload.encode("utf-8")).hexdigest()))
        return (("docset", docset_hash), ("markdown", hashlib.sha1(repr(cached_markdown_sig).encode("utf-8")).hexdigest()), *tuple(sorted(extra)))
    signature: list[tuple[str, str]] = []
    for doc in docs:
        uri = str(doc.get("uri") or okf_concept_id_for_doc(doc))
        path_value = str(doc.get("path") or "")
        version = ""
        if path_value:
            path = Path(path_value)
            try:
                if path.exists():
                    version = str(path.stat().st_mtime_ns)
            except OSError:
                version = ""
        if not version:
            payload = json.dumps(doc.get("metadata") or {}, ensure_ascii=False, sort_keys=True, default=str) + "\n" + str(doc.get("body") or "")
            version = hashlib.sha1(payload.encode("utf-8")).hexdigest()
        signature.append((uri, version))
    return tuple(sorted(signature))


def cached_okf_graph_for_docs(docs: list[dict[str, Any]], employee_id: str) -> dict[str, Any]:
    key = (employee_id, docs_cache_signature(docs))
    cached = _OKF_GRAPH_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_OKF_GRAPH_CACHE) > 16:
        _OKF_GRAPH_CACHE.clear()
    graph = okf_graph_for_docs(docs, employee_id)
    _OKF_GRAPH_CACHE[key] = graph
    return graph


def cached_okf_graph_for_employee(employee_id: str) -> dict[str, Any]:
    signature = markdown_signature()
    if _OKF_GRAPH_INDEX_CACHE["signature"] != signature:
        _OKF_GRAPH_INDEX_CACHE["signature"] = signature
        _OKF_GRAPH_INDEX_CACHE["by_employee"] = {}
    by_employee: dict[str, dict[str, Any]] = _OKF_GRAPH_INDEX_CACHE["by_employee"]
    cached = by_employee.get(employee_id)
    if cached is not None:
        return cached
    docs = accessible_docs(employee_id)
    graph = okf_graph_for_docs(docs, employee_id)
    by_employee[employee_id] = graph
    return graph


def citation_rows_for_doc(
    doc: dict[str, Any],
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in doc["metadata"].get("source_refs") or []:
        if not isinstance(item, dict):
            continue
        ref = str(item.get("uri") or item.get("ref") or "")
        url = ""
        if ref:
            if ref.startswith("http://") or ref.startswith("https://"):
                url = ref
            else:
                target_doc = doc_from_lookup(ref, doc_lookup)
                if target_doc is None and doc_lookup is None:
                    target_doc = find_doc_by_id(ref, employee_id)
                if target_doc:
                    url = doc_url_for_ref(str(target_doc["metadata"].get("boi_id")), employee_id)
                else:
                    url = source_url_for_ref(ref, employee_id)
        rows.append({"type": str(item.get("type") or "source"), "ref": ref, "url": url})
    return rows


def source_ref_for_path(path: Path) -> str:
    try:
        return "data/boi/" + str(path.resolve().relative_to(DATA_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        pass
    try:
        return "data/action_catalog/" + str(path.resolve().relative_to(ACTION_CATALOG_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        pass
    try:
        return "data/event_catalog/" + str(path.resolve().relative_to(EVENT_CATALOG_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        pass
    return str(path)


def source_url_for_ref(ref: str, employee_id: str) -> str:
    if not ref or ref.startswith(("http://", "https://")):
        return ""
    try:
        resolve_source_path(ref)
    except HTTPException:
        return ""
    return "/source?" + urlencode({"employee_id": employee_id, "path": ref})


def source_url_for_doc(doc: dict[str, Any], employee_id: str) -> str:
    path_value = str(doc.get("path") or "")
    if not path_value:
        return ""
    ref = source_ref_for_path(Path(path_value))
    return source_url_for_ref(ref, employee_id)


def resolve_source_path(ref: str) -> Path:
    raw = str(ref or "").strip().replace("\\", "/")
    if not raw:
        raise HTTPException(status_code=400, detail="path is required")
    if raw.startswith("/"):
        raw = "data/boi/" + raw.lstrip("/")

    candidates: list[Path] = []
    if raw.startswith("data/boi/"):
        candidates.append(DATA_ROOT / raw.removeprefix("data/boi/"))
    elif raw.startswith("data/action_catalog/"):
        candidates.append(ACTION_CATALOG_ROOT / raw.removeprefix("data/action_catalog/"))
    elif raw.startswith("data/event_catalog/"):
        candidates.append(EVENT_CATALOG_ROOT / raw.removeprefix("data/event_catalog/"))
    elif raw.startswith("public/") or raw.startswith("team/") or raw.startswith("private/"):
        candidates.append(DATA_ROOT / raw)
    else:
        raise HTTPException(status_code=400, detail="source path is not allowlisted")

    for candidate in candidates:
        resolved = candidate.resolve()
        allowed_roots = [DATA_ROOT.resolve(), ACTION_CATALOG_ROOT.resolve(), EVENT_CATALOG_ROOT.resolve()]
        if not any(resolved == root or root in resolved.parents for root in allowed_roots):
            raise HTTPException(status_code=400, detail="source path escapes allowlisted roots")
        if resolved.suffix.lower() not in {".md", ".yaml", ".yml"}:
            raise HTTPException(status_code=400, detail="source file type is not editable")
        return resolved
    raise HTTPException(status_code=404, detail="source path not found")


def validate_source_content(path: Path, content: str) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    parsed: Any = None
    suffix = path.suffix.lower()
    if re.search(r"\b(sk-[A-Za-z0-9_-]{12,}|ghp_[A-Za-z0-9_]{12,}|xox[baprs]-[A-Za-z0-9-]{12,})", content):
        errors.append("potential secret token detected")
    if suffix == ".md":
        if path.name in {"index.md", "log.md"}:
            if content.startswith("---"):
                errors.append(f"reserved {path.name} must not contain BoI concept frontmatter")
        else:
            metadata, _body = split_frontmatter(content)
            if not metadata:
                errors.append("missing YAML frontmatter")
            else:
                errors.extend(validate_okf_metadata(metadata))
            parsed = {"metadata": metadata}
    elif suffix in {".yaml", ".yml"}:
        try:
            parsed = yaml.safe_load(content) or {}
        except yaml.YAMLError as exc:
            errors.append(f"invalid YAML: {exc}")
            parsed = None
        if isinstance(parsed, dict) and path.name in {"actions.yaml", "actions.yml"}:
            actions = parsed.get("actions")
            if not isinstance(actions, list):
                errors.append("actions catalog requires top-level actions list")
            else:
                seen: set[str] = set()
                actions_by_key: dict[str, dict[str, Any]] = {}
                manual_action_keys: set[str] = set()
                for index, action in enumerate(actions, start=1):
                    if not isinstance(action, dict):
                        errors.append(f"actions[{index}] must be an object")
                        continue
                    key = str(action.get("action_key") or "")
                    if not key:
                        errors.append(f"actions[{index}] missing action_key")
                    if key in seen:
                        errors.append(f"duplicate action_key: {key}")
                    seen.add(key)
                    if key:
                        actions_by_key[key] = action
                        if action.get("connector_kind") == "manual":
                            manual_action_keys.add(key)
                    for field_name in ("connector_kind", "doc_ref", "type"):
                        if not action.get(field_name):
                            errors.append(f"{key or f'actions[{index}]'} missing {field_name}")
                for action in actions_by_key.values():
                    key = str(action.get("action_key") or "")
                    manual_ref = str(action.get("requires_manual_action") or "")
                    if action.get("risk_level") == "high" and action.get("connector_kind") != "manual":
                        if not manual_ref:
                            errors.append(f"{key} high-risk action requires requires_manual_action")
                        elif manual_ref not in actions_by_key:
                            errors.append(f"{key} requires_manual_action references missing action: {manual_ref}")
                        elif manual_ref not in manual_action_keys:
                            errors.append(f"{key} requires_manual_action must reference a manual action: {manual_ref}")
        if isinstance(parsed, dict) and path.name in {"event_types.yaml", "event_types.yml"}:
            event_types = parsed.get("event_types")
            if not isinstance(event_types, list):
                errors.append("event catalog requires top-level event_types list")
            else:
                seen_events: set[str] = set()
                for index, event in enumerate(event_types, start=1):
                    if not isinstance(event, dict):
                        errors.append(f"event_types[{index}] must be an object")
                        continue
                    event_type = str(event.get("event_type") or "")
                    if not event_type:
                        errors.append(f"event_types[{index}] missing event_type")
                    if event_type in seen_events:
                        errors.append(f"duplicate event_type: {event_type}")
                    seen_events.add(event_type)
    return {"ok": not errors, "errors": errors, "warnings": warnings, "parsed": parsed}


def unique_messages(messages: list[str]) -> list[str]:
    return list(dict.fromkeys(str(message) for message in messages if str(message).strip()))


def line_number_for_hint(content: str, hint: str) -> int | None:
    if not hint:
        return None
    for index, line in enumerate(content.splitlines(), start=1):
        if hint in line:
            return index
    return None


def normalize_lint_messages(messages: list[str], temp_root: Path | None = None) -> list[str]:
    normalized: list[str] = []
    for message in messages:
        item = str(message)
        if temp_root is not None:
            item = item.replace(str((temp_root / "boi").resolve()), "data/boi")
            item = item.replace(str((temp_root / "events").resolve()), "data/events")
            item = item.replace(str((temp_root / "actions").resolve()), "data/actions")
        else:
            item = item.replace(str(DATA_ROOT.resolve()), "data/boi")
            item = item.replace(str(EVENTS_ROOT.resolve()), "data/events")
            item = item.replace(str(ACTION_LOG_ROOT.resolve()), "data/actions")
        normalized.append(item)
    return normalized


def okf_lint_report(root: Path, temp_root: Path | None = None, include_logs: bool = False) -> dict[str, Any]:
    result = lint_data_root(root, include_logs=include_logs, strict_links=True, strict_media=True)
    return {
        "ok": result.ok,
        "errors": normalize_lint_messages(result.errors, temp_root),
        "warnings": normalize_lint_messages(result.warnings, temp_root),
        "checked_markdown_count": result.checked_markdown_count,
        "checked_log_item_count": result.checked_log_item_count,
        "markdown_link_count": result.markdown_link_count,
        "media_link_count": result.media_link_count,
    }


def copy_optional_tree(source: Path, target: Path) -> None:
    if source.exists():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.mkdir(parents=True, exist_ok=True)


def fast_work_temp_parent() -> Path | None:
    configured = os.getenv("BOI_WORK_TMPDIR")
    candidates = [configured, "/tmp", tempfile.gettempdir()]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception:
            continue
        if path.exists() and os.access(path, os.W_OK):
            return path
    return None


def source_post_apply_validation_report(source_path: Path, proposed_content: str, preapply_validation: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("BOI_EDIT_POST_APPLY_FULL_LINT", "false").lower() in {"1", "true", "yes", "on"}:
        return current_source_validation_report(source_path)
    source_validation = validate_source_content(source_path, proposed_content)
    errors = list(source_validation.get("errors") or [])
    warnings = list(source_validation.get("warnings") or [])
    okf_report = preapply_validation.get("okf_lint")
    if okf_report is not None:
        errors.extend(okf_report.get("errors") or [])
        warnings.extend(okf_report.get("warnings") or [])
    errors = unique_messages(errors)
    warnings = unique_messages(warnings)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "source_validation": source_validation,
        "okf_lint": okf_report,
        "post_apply_full_lint": False,
    }


def candidate_path_in_temp_data_root(temp_root: Path, source_path: Path) -> Path | None:
    try:
        rel_path = source_path.resolve().relative_to(DATA_ROOT.resolve())
    except ValueError:
        return None
    return temp_root / "boi" / rel_path


def candidate_okf_lint_report(source_path: Path, proposed_content: str) -> dict[str, Any] | None:
    temp_parent = fast_work_temp_parent()
    with tempfile.TemporaryDirectory(prefix="boi-edit-", dir=str(temp_parent) if temp_parent else None) as temp_dir:
        temp_root = Path(temp_dir)
        copy_optional_tree(DATA_ROOT, temp_root / "boi")
        copy_optional_tree(EVENTS_ROOT, temp_root / "events")
        copy_optional_tree(ACTION_LOG_ROOT, temp_root / "actions")
        candidate_path = candidate_path_in_temp_data_root(temp_root, source_path)
        if candidate_path is None:
            return None
        candidate_path.parent.mkdir(parents=True, exist_ok=True)
        candidate_path.write_text(proposed_content, encoding="utf-8")
        return okf_lint_report(temp_root, temp_root=temp_root)


def source_edit_validation_report(source_path: Path, proposed_content: str) -> dict[str, Any]:
    source_validation = validate_source_content(source_path, proposed_content)
    errors = list(source_validation.get("errors") or [])
    warnings = list(source_validation.get("warnings") or [])
    okf_report: dict[str, Any] | None = None
    try:
        okf_report = candidate_okf_lint_report(source_path, proposed_content)
    except Exception as exc:
        errors.append(f"okf_lint failed: {exc}")
    if okf_report is not None:
        errors.extend(okf_report.get("errors") or [])
        warnings.extend(okf_report.get("warnings") or [])
    errors = unique_messages(errors)
    warnings = unique_messages(warnings)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "source_validation": source_validation,
        "okf_lint": okf_report,
    }


def current_source_validation_report(source_path: Path) -> dict[str, Any]:
    content = source_path.read_text(encoding="utf-8")
    source_validation = validate_source_content(source_path, content)
    errors = list(source_validation.get("errors") or [])
    warnings = list(source_validation.get("warnings") or [])
    okf_report: dict[str, Any] | None = None
    try:
        candidate_path_in_temp_data_root(DATA_ROOT.parent, source_path)
        okf_report = okf_lint_report(DATA_ROOT.parent)
    except Exception as exc:
        errors.append(f"okf_lint failed: {exc}")
    if okf_report is not None:
        errors.extend(okf_report.get("errors") or [])
        warnings.extend(okf_report.get("warnings") or [])
    errors = unique_messages(errors)
    warnings = unique_messages(warnings)
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "source_validation": source_validation,
        "okf_lint": okf_report,
    }


def edit_fix_suggestions(source_path: Path, proposed_content: str, validation: dict[str, Any]) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    source_ref = source_ref_for_path(source_path)
    for index, error in enumerate(validation.get("errors") or [], start=1):
        lowered = error.lower()
        title = "검증 오류 확인"
        description = "표시된 오류가 해결되도록 원문을 수정한 뒤 다시 Preview / Validate를 실행하세요."
        auto_applicable = False
        line = None
        if "missing yaml frontmatter" in lowered:
            title = "YAML frontmatter 추가"
            description = "문서 맨 위에 --- 로 감싼 OKF metadata 블록을 추가해야 합니다."
            line = 1
        elif "missing required metadata:" in lowered:
            field_name = error.rsplit(":", 1)[-1].strip()
            title = f"`{field_name}` metadata 추가"
            description = f"frontmatter에 `{field_name}` 값을 추가하세요. Public/Team 문서는 source_refs와 review 정보도 필요합니다."
            line = line_number_for_hint(proposed_content, "---") or 1
        elif "team/public boi requires source_refs" in lowered:
            title = "`source_refs` 추가"
            description = "Team/Public 문서는 출처를 추적할 수 있도록 `source_refs` 배열이 필요합니다."
            line = line_number_for_hint(proposed_content, "visibility:")
        elif "requires reviewer" in lowered:
            title = "reviewer 추가"
            description = "`review.reviewer` 또는 `reviewer` metadata를 추가하세요."
            line = line_number_for_hint(proposed_content, "review:")
        elif "potential secret token detected" in lowered:
            title = "민감정보 제거"
            description = "API token, GitHub token, Slack token처럼 보이는 문자열을 제거하거나 안전한 참조로 바꾸세요."
        elif "invalid yaml" in lowered:
            title = "YAML 문법 수정"
            description = "들여쓰기, 콜론 뒤 공백, 리스트 표기, 따옴표 닫힘을 확인하세요."
            line = line_number_for_hint(proposed_content, ":")
        elif "unresolved okf markdown link" in lowered:
            title = "OKF 링크 수정"
            description = "존재하는 BoI 문서 경로나 `/public/...md`, 상대 경로 링크로 수정하세요."
        elif "image link" in lowered or "media manifest" in lowered:
            title = "이미지/미디어 참조 수정"
            description = "이미지는 `_media` 디렉터리에 두고 `media-manifest.yaml`의 path와 sha256을 맞추세요."
        elif "reserved" in lowered:
            title = "예약 파일 frontmatter 제거"
            description = "`index.md`와 `log.md`는 BoI concept frontmatter를 가지면 안 됩니다."
            line = 1
        suggestions.append(
            {
                "id": f"fix-{index}",
                "title": title,
                "description": description,
                "target": {"path": source_ref, "line": line},
                "auto_applicable": auto_applicable,
                "source_error": error,
            }
        )
    return suggestions


def source_preview_html(source_path: Path, proposed_content: str, employee_id: str, validation: dict[str, Any]) -> dict[str, Any]:
    suffix = source_path.suffix.lower()
    if suffix == ".md":
        metadata, body = split_frontmatter(proposed_content)
        doc_lookup = build_doc_lookup(accessible_docs(employee_id))
        return {
            "kind": "markdown",
            "html": str(render_markdown(body, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)),
            "metadata": metadata,
        }
    parsed = (validation.get("source_validation") or {}).get("parsed")
    if parsed is not None:
        return {"kind": "yaml", "html": str(render_content(parsed)), "metadata": {}}
    return {"kind": "plain", "html": f"<pre>{html_escape(proposed_content)}</pre>", "metadata": {}}


def check_source_base_sha(source_path: Path, base_sha256: str | None, *, action: str) -> str:
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="source file not found")
    current_content = source_path.read_text(encoding="utf-8")
    current_sha = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
    if base_sha256 and base_sha256 != current_sha:
        raise HTTPException(
            status_code=409,
            detail={
                "ok": False,
                "status": "stale_base",
                "message": f"source changed after this edit was opened; reload before {action}",
                "current_sha256": current_sha,
            },
        )
    return current_sha


def source_preview_response(
    *,
    source_path: Path,
    proposed_content: str,
    employee_id: str,
    base_sha256: str | None = None,
) -> dict[str, Any]:
    current_sha = check_source_base_sha(source_path, base_sha256, action="previewing")
    validation = source_edit_validation_report(source_path, proposed_content)
    proposed_sha = hashlib.sha256(proposed_content.encode("utf-8")).hexdigest()
    preview = source_preview_html(source_path, proposed_content, employee_id, validation)
    return {
        "ok": validation["ok"],
        "status": "valid" if validation["ok"] else "validation_failed",
        "path": source_ref_for_path(source_path),
        "base_sha256": current_sha,
        "proposed_sha256": proposed_sha,
        "changed": proposed_sha != current_sha,
        "validation_report": validation,
        "validation": validation,
        "fix_suggestions": edit_fix_suggestions(source_path, proposed_content, validation),
        "preview": preview,
        "applied": False,
        "commit_status": "not_started",
        "commit_hash": "",
    }


def require_edit_commit_success(commit: dict[str, Any], *, changed: bool) -> None:
    required = os.getenv("BOI_EDIT_REQUIRE_COMMIT", "true").lower() in {"1", "true", "yes", "on"}
    status = str(commit.get("status") or "")
    if not required:
        return
    if changed and status != "committed":
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "status": "commit_failed",
                "message": "validated edit could not be committed; source file was rolled back",
                "commit": commit,
            },
        )


def refresh_git_index_for_path(path: Path) -> None:
    try:
        root = subprocess.run(
            ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        rel_path = str(path.resolve().relative_to(Path(root).resolve()))
        subprocess.run(["git", "-C", root, "add", rel_path], text=True, capture_output=True, check=False)
    except Exception:
        return


def rollback_source_file(source_path: Path, content: str) -> None:
    source_path.write_text(content, encoding="utf-8")
    refresh_git_index_for_path(source_path)
    invalidate_doc_caches()
    try:
        resolved = source_path.resolve()
        if any(root.resolve() == resolved or root.resolve() in resolved.parents for root in (EVENT_CATALOG_ROOT, ACTION_CATALOG_ROOT)):
            invalidate_catalog_caches()
    except Exception:
        pass


def apply_source_edit(
    *,
    source_path: Path,
    base_sha256: str,
    proposed_content: str,
    employee_id: str,
    author: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    current_content = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
    current_sha = check_source_base_sha(source_path, base_sha256, action="applying")
    preview = source_preview_response(
        source_path=source_path,
        proposed_content=proposed_content,
        employee_id=employee_id,
        base_sha256=current_sha,
    )
    if not preview["ok"]:
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "status": "validation_failed",
                "message": "validated edit failed before applying; source file was not changed",
                "validation_report": preview["validation_report"],
                "fix_suggestions": preview["fix_suggestions"],
            },
        )
    if not preview["changed"]:
        return {
            **preview,
            "ok": True,
            "status": "unchanged",
            "message": "No source changes to apply.",
            "commit_status": "unchanged",
            "commit_hash": "",
        }
    source_path.write_text(proposed_content, encoding="utf-8")
    invalidate_doc_caches()
    try:
        post_validation = source_post_apply_validation_report(source_path, proposed_content, preview["validation_report"])
        if not post_validation["ok"]:
            rollback_source_file(source_path, current_content)
            raise HTTPException(
                status_code=422,
                detail={
                    "ok": False,
                    "status": "validation_failed",
                    "message": "post-apply validation failed; source file was rolled back",
                    "validation_report": post_validation,
                    "fix_suggestions": edit_fix_suggestions(source_path, proposed_content, post_validation),
                },
            )
        commit = git_commit_for_path(
            source_path,
            f"Apply BoI source edit {source_ref_for_path(source_path)}",
        )
        try:
            require_edit_commit_success(commit, changed=True)
        except HTTPException:
            rollback_source_file(source_path, current_content)
            raise
    except Exception:
        if source_path.exists() and source_path.read_text(encoding="utf-8") != current_content:
            rollback_source_file(source_path, current_content)
        raise
    refreshed_sha = hashlib.sha256(source_path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
    try:
        resolved = source_path.resolve()
        if any(root.resolve() == resolved or root.resolve() in resolved.parents for root in (EVENT_CATALOG_ROOT, ACTION_CATALOG_ROOT)):
            invalidate_catalog_caches()
    except Exception:
        pass
    return {
        **preview,
        "ok": True,
        "status": "applied",
        "message": "Validated edit applied and committed.",
        "applied": True,
        "applied_at": now_iso(),
        "applied_by": author or employee_id,
        "note": note,
        "sha256": refreshed_sha,
        "commit_status": commit.get("status", ""),
        "commit_hash": commit.get("commit_hash", ""),
        "commit": commit,
        "validation_report": post_validation,
        "validation": post_validation,
    }


def source_payload(path: Path, employee_id: str, content: str | None = None) -> dict[str, Any]:
    actual_content = path.read_text(encoding="utf-8") if content is None else content
    validation = validate_source_content(path, actual_content)
    return {
        "path": source_ref_for_path(path),
        "exists": path.exists(),
        "sha256": hashlib.sha256(actual_content.encode("utf-8")).hexdigest(),
        "content": actual_content,
        "validation": validation,
        "guide_url": "/docs/boi:public:harness:web-draft-editing-guide?" + urlencode({"employee_id": employee_id}),
    }


def body_editor_payload_for_doc(doc: dict[str, Any], employee_id: str) -> dict[str, Any] | None:
    path_value = str(doc.get("path") or "")
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists() or path.suffix.lower() != ".md":
        return None
    try:
        source_ref_for_path(path)
    except Exception:
        return None
    doc_ref = str(doc["metadata"].get("boi_id") or doc.get("uri", "").lstrip("/"))
    return {
        "editor_url": "/api/docs/" + doc_ref + "/body-editor?" + urlencode({"employee_id": employee_id}),
        "guide_url": "/docs/boi:public:harness:web-draft-editing-guide?" + urlencode({"employee_id": employee_id}),
    }


def full_body_editor_payload_for_doc(doc: dict[str, Any], employee_id: str) -> dict[str, Any] | None:
    path_value = str(doc.get("path") or "")
    if not path_value:
        return None
    path = Path(path_value)
    if not path.exists() or path.suffix.lower() != ".md":
        return None
    try:
        source_ref_for_path(path)
    except Exception:
        return None
    content = path.read_text(encoding="utf-8")
    doc_ref = str(doc["metadata"].get("boi_id") or doc.get("uri", "").lstrip("/"))
    return {
        "body": doc.get("body") or "",
        "base_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "preview_url": "/api/docs/" + doc_ref + "/body-preview?" + urlencode({"employee_id": employee_id}),
        "apply_url": "/api/docs/" + doc_ref + "/body-apply?" + urlencode({"employee_id": employee_id}),
        "guide_url": "/docs/boi:public:harness:web-draft-editing-guide?" + urlencode({"employee_id": employee_id}),
    }


def relationship_context_for_doc(
    doc: dict[str, Any],
    employee_id: str,
    docs: list[dict[str, Any]] | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    graph = graph or cached_okf_graph_for_docs(docs if docs is not None else accessible_docs(employee_id), employee_id)
    concept_id = okf_concept_id_for_doc(doc)
    outgoing = graph.get("outgoing_by_source", {}).get(concept_id)
    incoming = graph.get("incoming_by_target", {}).get(concept_id)
    if outgoing is None:
        outgoing = [edge for edge in graph["edges"] if edge["source"] == concept_id]
    if incoming is None:
        incoming = [edge for edge in graph["edges"] if edge["target"] == concept_id]
    return {"concept_id": concept_id, "outgoing": outgoing, "incoming": incoming}


def cached_doc_body_html(doc: dict[str, Any], employee_id: str, doc_lookup: dict[str, dict[str, Any]]) -> Markup:
    source_path = Path(doc["path"])
    if source_path.exists():
        try:
            doc_version = str(source_path.stat().st_mtime_ns)
        except OSError:
            doc_version = hashlib.sha1(str(doc.get("body") or "").encode("utf-8")).hexdigest()
    else:
        doc_version = hashlib.sha1(
            (json.dumps(doc.get("metadata") or {}, ensure_ascii=False, sort_keys=True, default=str) + "\n" + str(doc.get("body") or "")).encode("utf-8")
        ).hexdigest()
    key = (
        employee_id,
        str(doc.get("uri") or ""),
        doc_version,
        MARKDOWN_RENDERER_VERSION,
    )
    cached = _DOC_BODY_HTML_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_DOC_BODY_HTML_CACHE) > 128:
        _DOC_BODY_HTML_CACHE.clear()
    rendered = render_markdown(doc["body"], employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)
    _DOC_BODY_HTML_CACHE[key] = rendered
    return rendered


def doc_body_html_for_request(doc: dict[str, Any], employee_id: str, doc_lookup: dict[str, dict[str, Any]], request: Request) -> Markup:
    rendered = cached_doc_body_html(doc, employee_id, doc_lookup)
    return Markup(rewrite_display_string(str(rendered), request))


def action_doc_uri(
    action: dict[str, Any],
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    doc_ref = str(action.get("doc_ref") or "")
    if not doc_ref:
        return ""
    doc = doc_from_lookup(doc_ref, doc_lookup)
    if doc is None and doc_lookup is None:
        doc = find_doc_by_id(doc_ref, employee_id)
    return str(doc.get("uri", "")) if doc else ""


def actions_for_template(
    actions: list[dict[str, Any]],
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items = []
    for action in actions:
        item = dict(action)
        doc_ref = str(item.get("doc_ref") or "")
        if doc_ref:
            item["doc_url"] = doc_url_for_ref(doc_ref, employee_id)
            item["doc_uri"] = action_doc_uri(item, employee_id, doc_lookup=doc_lookup)
        items.append(item)
    return items


def target_dir_for(metadata: dict[str, Any]) -> Path:
    visibility = metadata.get("visibility", "private")
    if visibility == "private":
        owner = str(metadata.get("owner") or DEMO_EMPLOYEE_ID)
        if str(metadata.get("type") or "") == "boi/dictionary-term":
            return DATA_ROOT / "private" / owner / "dictionary"
        return DATA_ROOT / "private" / owner
    if visibility == "team":
        team_id = str(metadata.get("team_id") or DEFAULT_TEAM_ID)
        if str(metadata.get("type") or "") == "boi/dictionary-term":
            return DATA_ROOT / "team" / team_id / "dictionary"
        return DATA_ROOT / "team" / team_id
    if visibility == "public":
        boi_type = str(metadata.get("type") or "")
        if boi_type == "boi/dictionary-term":
            return DATA_ROOT / "public" / "dictionary"
        if boi_type == "boi/sop":
            return DATA_ROOT / "public" / "sop"
        if boi_type == "boi/action-spec":
            connector_kind = normalize_folder(str(metadata.get("connector_kind") or "general"))
            return DATA_ROOT / "public" / "actions" / (connector_kind or "general")
        return DATA_ROOT / "public"
    raise HTTPException(status_code=400, detail=f"Unsupported visibility: {visibility}")


def validate_metadata(metadata: dict[str, Any], promotion: bool = False) -> list[str]:
    return validate_okf_metadata(metadata, promotion=promotion)


def private_lifecycle_defaults(
    *,
    boi_type: str,
    source_event: dict[str, Any] | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    tag_set = {str(tag).lower() for tag in (tags or [])}
    if source_event:
        retention_class = "ephemeral"
        review_days = 30
        retention_days = 90
    elif boi_type == "boi/report" or "report" in tag_set or "weekly-report" in tag_set:
        retention_class = "record"
        review_days = 180
        retention_days = None
    else:
        retention_class = "working"
        review_days = 90
        retention_days = None
    now = datetime.now(KST)
    return {
        "retention_class": retention_class,
        "retention_until": (now + timedelta(days=retention_days)).date().isoformat() if retention_days else "",
        "archive_status": "active",
        "review_after": (now + timedelta(days=review_days)).date().isoformat(),
        "contains_sensitive": "unknown",
    }


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
    invalidate_doc_caches()
    return read_doc(path)


def write_boi_to_subfolder(metadata: dict[str, Any], body: str, subfolder: str) -> dict[str, Any]:
    ensure_dirs()
    normalized = normalize_folder(subfolder)
    if not normalized or any(part in {"..", "."} for part in normalized.split("/")):
        raise HTTPException(status_code=400, detail="invalid BoI subfolder")
    if not normalized.startswith(("agent-memory", "dictionary")):
        raise HTTPException(status_code=400, detail="subfolder is not allowlisted for this API")
    errors = validate_metadata(metadata)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    visibility = str(metadata.get("visibility") or "private")
    if visibility != "private":
        raise HTTPException(status_code=400, detail="subfolder writer supports private BoI only")
    owner = str(metadata.get("owner") or "")
    if not owner:
        raise HTTPException(status_code=400, detail="private owner is required")
    path_dir = DATA_ROOT / "private" / owner / normalized
    path_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(metadata["boi_id"]) + ".md"
    path = path_dir / filename
    path.write_text(compose_markdown(metadata, body), encoding="utf-8")
    invalidate_doc_caches()
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
        "acl_policy": "acl:public"
        if visibility == "public"
        else f"acl:{visibility}:{owner if visibility == 'private' else (team_id or DEFAULT_TEAM_ID)}",
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
    if visibility == "private":
        meta.update(private_lifecycle_defaults(boi_type=boi_type, source_event=source_event, tags=tags))
    return meta


async def require_service_token(x_service_token: str | None = Header(None)) -> None:
    if x_service_token != SERVICE_TOKEN:
        raise HTTPException(status_code=401, detail="invalid service token")


def current_identity(
    employee_id: str | None = Query(default=None),
    x_employee_id: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
    boi_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    x_hynix_employee_id: str | None = Header(default=None),
    x_hynix_email: str | None = Header(default=None),
    x_hynix_name: str | None = Header(default=None),
    x_hynix_teams: str | None = Header(default=None),
    x_hynix_roles: str | None = Header(default=None),
) -> AuthIdentity:
    try:
        if x_service_token == SERVICE_TOKEN:
            return remember_identity(service_identity(employee_id or x_employee_id or x_hynix_employee_id or DEMO_EMPLOYEE_ID))
        return remember_identity(
            resolve_identity(
                query_employee_id=employee_id,
                x_employee_id=x_employee_id,
                authorization=authorization,
                session_token=boi_session,
                x_hynix_employee_id=x_hynix_employee_id,
                x_hynix_email=x_hynix_email,
                x_hynix_name=x_hynix_name,
                x_hynix_teams=x_hynix_teams,
                x_hynix_roles=x_hynix_roles,
            )
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def current_employee(identity: AuthIdentity = Depends(current_identity)) -> str:
    return identity.employee_id


class BoiCreate(BaseModel):
    metadata: dict[str, Any]
    body: str


class PromotionRequest(BaseModel):
    target_visibility: Literal["team", "public"] = "team"
    team_id: str | None = None
    reviewer: str = "tf-lead"
    promotion_reason: str = "User explicitly requested promotion."
    user_confirmed: bool = True
    user_confirmed_at: str | None = None


class PromotionSubmitRequest(BaseModel):
    target_visibility: Literal["team", "public"] = "team"
    team_id: str | None = None
    title: str
    description: str = "Promoted BoI"
    body: str
    boi_type: str = "boi/reference"
    classification: str = "internal"
    tags: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    source_local_id: str | None = None
    source_sha256: str | None = None
    reviewer: str = "hotl-curator"
    promotion_reason: str = "User explicitly requested promotion."
    user_confirmed: bool = False
    user_confirmed_at: str | None = None


class HotlUpdateRequest(BaseModel):
    status: Literal["watching", "hidden", "needs_revision", "rolled_back"]
    note: str = ""
    actor: str | None = None


def promotion_report_path(promotion_id: str) -> Path:
    safe_id = safe_filename(promotion_id)
    return DRAFT_ROOT / "promotions" / f"{safe_id}.json"


def write_promotion_report(report: dict[str, Any]) -> None:
    ensure_dirs()
    promotion_id = str(report.get("promotion_id") or "")
    if not promotion_id:
        raise HTTPException(status_code=500, detail="promotion report is missing promotion_id")
    promotion_report_path(promotion_id).write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def read_promotion_report(promotion_id: str) -> dict[str, Any]:
    path = promotion_report_path(promotion_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="promotion report not found")
    return json.loads(path.read_text(encoding="utf-8"))


def git_commit_for_path(path: Path, message: str) -> dict[str, str]:
    if os.getenv("BOI_PROMOTION_AUTO_COMMIT", "true").lower() not in {"1", "true", "yes", "on"}:
        return {"status": "disabled", "commit_hash": ""}
    try:
        root = subprocess.run(
            ["git", "-C", str(path.parent), "rev-parse", "--show-toplevel"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except Exception:
        return {"status": "unavailable", "commit_hash": ""}
    try:
        rel_path = str(path.resolve().relative_to(Path(root).resolve()))
    except ValueError:
        rel_path = str(path)
    try:
        subprocess.run(["git", "-C", root, "add", rel_path], text=True, capture_output=True, check=True)
        commit = subprocess.run(
            ["git", "-C", root, "commit", "-m", message, "--", rel_path],
            text=True,
            capture_output=True,
            check=False,
        )
        if commit.returncode != 0:
            combined = (commit.stdout + "\n" + commit.stderr).lower()
            if "nothing to commit" not in combined:
                return {"status": "failed", "commit_hash": "", "error": (commit.stdout + commit.stderr).strip()}
        current = subprocess.run(
            ["git", "-C", root, "rev-parse", "--short", "HEAD"],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        return {"status": "committed" if commit.returncode == 0 else "unchanged", "commit_hash": current}
    except Exception as exc:
        return {"status": "failed", "commit_hash": "", "error": repr(exc)}


def promotion_validation_failure(errors: list[str], warnings: list[str], metadata: dict[str, Any] | None = None) -> None:
    raise HTTPException(
        status_code=422,
        detail={
            "ok": False,
            "status": "validation_failed",
            "validation": {"ok": False, "errors": errors, "warnings": warnings, "metadata": metadata or {}},
        },
    )


def validate_promotion_candidate(metadata: dict[str, Any], body: str, *, user_confirmed: bool) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not user_confirmed:
        errors.append("user confirmation is required before Team/Public promotion")
    if not str(metadata.get("title") or "").strip():
        errors.append("promotion title is required")
    if not body.strip():
        errors.append("promotion body is required")
    if metadata.get("visibility") not in {"team", "public"}:
        errors.append("promotion target_visibility must be team or public")
    if not metadata.get("source_refs"):
        errors.append("Team/Public promotion requires source_refs")
    if not (metadata.get("review") or {}).get("reviewer"):
        errors.append("Team/Public promotion requires HOTL reviewer")
    if SECRET_VALUE_RE.search(body) or SECRET_VALUE_RE.search(json.dumps(metadata, ensure_ascii=False, default=str)):
        errors.append("potential secret token detected")
    errors.extend(validate_metadata(metadata, promotion=True))
    if "# Summary" not in body:
        warnings.append("promotion body has no # Summary heading")
    return {"ok": not errors, "errors": errors, "warnings": warnings, "metadata": metadata}


def publish_promotion(
    *,
    employee_id: str,
    target_visibility: Literal["team", "public"],
    team_id: str | None,
    title: str,
    description: str,
    body: str,
    boi_type: str,
    classification: str,
    tags: list[str],
    source_refs: list[dict[str, Any]],
    source_local_id: str | None,
    source_sha256: str | None,
    reviewer: str,
    promotion_reason: str,
    user_confirmed: bool,
    user_confirmed_at: str | None,
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.promoter")
    effective_team_id = team_id or (teams_for(employee_id)[0] if target_visibility == "team" else None)
    promotion_id = f"promotion-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    confirmed_at = user_confirmed_at or now_iso()
    metadata = make_metadata(
        boi_type=boi_type,
        title=title,
        description=description,
        owner=employee_id,
        visibility=target_visibility,
        classification=classification,
        team_id=effective_team_id,
        source_refs=source_refs,
        status="reviewed",
        tags=list(dict.fromkeys((tags or []) + ["promoted", "user-confirmed"])),
        promotion={
            "promotion_id": promotion_id,
            "source_local_id": source_local_id or "",
            "source_sha256": source_sha256 or "",
            "promoted_by": employee_id,
            "promoted_at": now_iso(),
            "user_confirmed_at": confirmed_at,
            "promotion_reason": promotion_reason,
            "validation_report_id": promotion_id,
        },
        reviewer=reviewer,
    )
    metadata["review"] = {
        "reviewer": reviewer,
        "review_status": "user_confirmed",
        "user_confirmed_by": employee_id,
        "user_confirmed_at": confirmed_at,
    }
    metadata["hotl"] = {"status": "watching", "owner": reviewer, "updated_at": now_iso()}
    validation = validate_promotion_candidate(metadata, body, user_confirmed=user_confirmed)
    if not validation["ok"]:
        promotion_validation_failure(validation["errors"], validation["warnings"], metadata)

    doc = write_boi(metadata, body)
    commit = git_commit_for_path(Path(str(doc["path"])), f"Publish BoI promotion {metadata['boi_id']}")
    report = {
        "ok": True,
        "status": "published",
        "promotion_id": promotion_id,
        "target_boi_id": metadata["boi_id"],
        "target_visibility": target_visibility,
        "target_path": doc["path"],
        "target_uri": doc["uri"],
        "published_at": now_iso(),
        "promoted_by": employee_id,
        "validation": validation,
        "hotl": metadata["hotl"],
        "commit": commit,
    }
    write_promotion_report(report)
    return {
        "ok": True,
        "status": "published",
        "promotion_id": promotion_id,
        "target": doc,
        "validation": validation,
        "hotl": metadata["hotl"],
        "commit_hash": commit.get("commit_hash", ""),
        "commit_status": commit.get("status", ""),
    }


def update_hotl_status(promotion_id: str, req: HotlUpdateRequest, employee_id: str) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.promoter")
    report = read_promotion_report(promotion_id)
    target_path = Path(str(report.get("target_path") or ""))
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="promoted document not found")
    metadata, body = split_frontmatter(target_path.read_text(encoding="utf-8"))
    hotl = dict(metadata.get("hotl") or {})
    hotl.update(
        {
            "status": req.status,
            "updated_at": now_iso(),
            "updated_by": req.actor or employee_id,
            "note": req.note,
        }
    )
    metadata["hotl"] = hotl
    target_path.write_text(compose_markdown(metadata, body), encoding="utf-8")
    invalidate_doc_caches()
    commit = git_commit_for_path(target_path, f"Update HOTL status for {metadata.get('boi_id')}")
    report["hotl"] = hotl
    report["status"] = req.status if req.status in HOTL_HIDDEN_STATUSES else report.get("status", "published")
    report["hotl_commit"] = commit
    write_promotion_report(report)
    return {"ok": True, "promotion_id": promotion_id, "status": report["status"], "hotl": hotl, "commit": commit}


class EventPublishRequest(BaseModel):
    event_type: str = Field(examples=["meeting.closed.v1"])
    payload: dict[str, Any] = Field(default_factory=dict)
    actor_employee_id: str | None = None
    admin_override_reason: str | None = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None


class EquipmentAnomalyStartRequest(BaseModel):
    equipment_id: str = "ETCH-VM-01"
    alarm_code: str = "RESPONSE_CHAIN_ABNORMAL"
    title: str = "Response Chain 이상 Alarm 발생"
    lot_id: str = "LOT-POC-001"
    wafer_id: str = "WF-POC-001"
    owner: str | None = None
    user_confirmed: bool = False


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


class BoIEnrichFromDispatchRequest(BaseModel):
    employee_id: str = DEMO_EMPLOYEE_ID
    event: dict[str, Any] = Field(default_factory=dict)
    dispatch_result: dict[str, Any] = Field(default_factory=dict)


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
    admin_override_reason: str | None = None


class SimulationAgentRequest(BaseModel):
    action_key: str
    employee_id: str = DEMO_EMPLOYEE_ID
    event: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    prior_results: list[dict[str, Any]] = Field(default_factory=list)
    workflow_key: str | None = None
    sop_ref: str | None = None
    sop_stage_id: str | None = None
    max_rounds: int = 4
    simulation_depth: str = "stage_prerequisites"


class BoiAgentChatRequest(BaseModel):
    question: str
    mode: Literal["auto", "fast", "deep"] = "auto"
    intent: str = ""
    current_url: str = ""
    selected_text: str = ""
    page_context: dict[str, Any] = Field(default_factory=dict)
    conversation: list[dict[str, Any]] = Field(default_factory=list)
    save_memory: bool = True


class BoiAgentSuggestionsRequest(BaseModel):
    current_url: str = ""
    page_context: dict[str, Any] = Field(default_factory=dict)


class BoiAgentApprovalRequest(BaseModel):
    operation: str
    payload: dict[str, Any] = Field(default_factory=dict)
    user_confirmed: bool = False
    note: str = ""


class RbacTeamRequest(BaseModel):
    team_id: str
    display_name: str = ""
    description: str = ""
    owners: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)
    status: str = "active"


class RbacTeamMemberRequest(BaseModel):
    employee_id: str
    action: Literal["add", "remove"] = "add"
    role: Literal["member", "owner"] = "member"


class RbacBindingRequest(BaseModel):
    subject_type: Literal["employee", "team"]
    subject_id: str
    roles: list[str]
    scope: str = "global"
    resource: str = ""


class RbacCheckRequest(BaseModel):
    operation: str = "read"
    employee_id: str = ""
    required_role: str = "boi.viewer"
    scope: str = "global"
    resource: str = ""
    boi_id: str = ""
    action_key: str = ""
    workflow_key: str = ""
    event_type: str = ""


class BreakGlassRequest(BaseModel):
    reason: str
    ticket_ref: str = ""
    user_confirmed: bool = True


class EventTypeDraftRequest(BaseModel):
    event_type: str
    name_ko: str = ""
    description: str = ""
    default_boi_type: str = ""
    default_flow_key: str = ""
    default_visibility: str = ""
    owner: str = ""
    status: str = "draft"
    topic: str = ""
    workflow_stage: str = ""
    sop_ref: str = ""
    sop_stage_id: str = ""
    wiki_usage: str = ""
    payload_schema: dict[str, Any] = Field(default_factory=dict)
    recommended_actions: list[str] = Field(default_factory=list)
    recommended_manual_actions: list[str] = Field(default_factory=list)
    source_refs: list[Any] = Field(default_factory=list)
    user_confirmed: bool = False


class EventTypeDraftApplyRequest(BaseModel):
    user_confirmed: bool = False
    author: str | None = None
    note: str = ""


class ManualHandoffCompleteRequest(BaseModel):
    task_id: str
    outcome: Literal["completed", "not_needed", "blocked"] = "completed"
    note: str
    completed_by: str | None = None
    user_confirmed: bool = True


class InboxTaskMutationRequest(BaseModel):
    note: str = ""
    user_confirmed: bool = False


class AgentMemoryRequest(BaseModel):
    memory_kind: str = "domain_context"
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    importance: int = 3


class AgentMemoryUpdateRequest(BaseModel):
    note: str = ""
    superseded_by: str | None = None


class ActivityRequest(BaseModel):
    activity_type: str
    target: str = ""
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DictionaryTermRequest(BaseModel):
    term: str
    definition: str
    aliases: list[str] = Field(default_factory=list)
    example: str = ""
    links: list[str] = Field(default_factory=list)
    scope: Literal["private", "team", "public"] = "private"
    team_id: str | None = None
    domain: str = ""
    maps_to_event_type: str = ""
    maps_to_action_key: str = ""
    maps_to_sop: str = ""


class SourcePreviewRequest(BaseModel):
    path: str = Field(examples=["data/boi/public/sop/equipment-abnormal-response.md"])
    base_sha256: str | None = None
    proposed_content: str
    author: str | None = None
    note: str = ""


class SourceApplyRequest(SourcePreviewRequest):
    base_sha256: str


class BodyPreviewRequest(BaseModel):
    base_sha256: str | None = None
    proposed_body: str
    author: str | None = None
    note: str = ""


class BodyApplyRequest(BodyPreviewRequest):
    base_sha256: str


class PocConnectorRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    request_id: str | None = None
    dry_run: bool | None = True
    approved_by: str | None = None


class PocMcpCallRequest(BaseModel):
    server: dict[str, Any] = Field(default_factory=dict)
    tool: str = ""
    arguments: dict[str, Any] = Field(default_factory=dict)
    event: dict[str, Any] = Field(default_factory=dict)
    boi_id: str | None = None
    request_id: str | None = None


def agent_cache_warmup_state() -> dict[str, Any]:
    with _AGENT_CACHE_WARMUP_LOCK:
        return copy.deepcopy(_AGENT_CACHE_WARMUP_STATE)


def warm_agent_runtime_caches(employee_id: str | None = None, *, force: bool = False) -> dict[str, Any]:
    """Warm common read-only indexes used by the first BoI Agent request."""
    warmup_employee_id = str(employee_id or DEMO_EMPLOYEE_ID)
    with _AGENT_CACHE_WARMUP_LOCK:
        if _AGENT_CACHE_WARMUP_STATE.get("status") == "running" and not force:
            return copy.deepcopy(_AGENT_CACHE_WARMUP_STATE)
        if _AGENT_CACHE_WARMUP_STATE.get("status") == "completed" and not force:
            return copy.deepcopy(_AGENT_CACHE_WARMUP_STATE)
        _AGENT_CACHE_WARMUP_STATE.update(
            {
                "enabled": BOI_AGENT_CACHE_WARMUP_ON_STARTUP,
                "status": "running",
                "employee_id": warmup_employee_id,
                "started_at": now_iso(),
                "completed_at": "",
                "elapsed_ms": 0,
                "checks": {},
                "error": "",
            }
        )
    started = time.perf_counter()
    checks: dict[str, Any] = {}
    try:
        event_types = load_event_types()
        checks["event_types"] = len(event_types)
        actions = load_action_catalog()
        checks["actions"] = len(actions)
        docs = accessible_docs(warmup_employee_id)
        checks["accessible_docs"] = len(docs)
        index = search_index_for_employee(warmup_employee_id)
        checks["search_docs"] = len(index.get("doc_records") or [])
        ontology = ontology_search_payload("SOP", warmup_employee_id, scope="all", limit=3, view="compact")
        checks["ontology_best_matches"] = len(ontology.get("best_matches") or [])
        page_context = resolve_agent_page_context(
            f"/docs/boi:public:sop:equipment-abnormal-response?employee_id={quote(warmup_employee_id)}",
            warmup_employee_id,
        )
        checks["sample_page_context_resolved"] = bool(page_context.get("resolved"))
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        with _AGENT_CACHE_WARMUP_LOCK:
            _AGENT_CACHE_WARMUP_STATE.update(
                {
                    "status": "completed",
                    "completed_at": now_iso(),
                    "elapsed_ms": elapsed_ms,
                    "checks": checks,
                    "error": "",
                }
            )
            return copy.deepcopy(_AGENT_CACHE_WARMUP_STATE)
    except Exception as exc:  # pragma: no cover - defensive startup path
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        with _AGENT_CACHE_WARMUP_LOCK:
            _AGENT_CACHE_WARMUP_STATE.update(
                {
                    "status": "failed",
                    "completed_at": now_iso(),
                    "elapsed_ms": elapsed_ms,
                    "checks": checks,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            return copy.deepcopy(_AGENT_CACHE_WARMUP_STATE)


def start_agent_cache_warmup() -> None:
    with _AGENT_CACHE_WARMUP_LOCK:
        _AGENT_CACHE_WARMUP_STATE["enabled"] = BOI_AGENT_CACHE_WARMUP_ON_STARTUP
        if not BOI_AGENT_CACHE_WARMUP_ON_STARTUP:
            if _AGENT_CACHE_WARMUP_STATE.get("status") == "not_started":
                _AGENT_CACHE_WARMUP_STATE["status"] = "disabled"
            return
        if _AGENT_CACHE_WARMUP_STATE.get("status") in {"running", "completed"}:
            return
    threading.Thread(
        target=lambda: warm_agent_runtime_caches(DEMO_EMPLOYEE_ID),
        name="boi-agent-cache-warmup",
        daemon=True,
    ).start()


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()
    start_agent_cache_warmup()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/okf-media/{media_path:path}")
async def okf_media(media_path: str) -> FileResponse:
    target_path = (DATA_ROOT / media_path).resolve()
    try:
        target_path.relative_to(DATA_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=404, detail="media not found")
    if "_media" not in target_path.parts or target_path.suffix.lower() not in ALLOWED_MEDIA_EXTENSIONS:
        raise HTTPException(status_code=404, detail="media not found")
    if not target_path.exists() or not target_path.is_file():
        raise HTTPException(status_code=404, detail="media not found")
    return FileResponse(target_path)


@app.get("/api/runtime/config")
async def runtime_config() -> dict[str, Any]:
    return {
        "build": {
            "revision": BOI_BUILD_REVISION,
        },
        "llm": {
            "provider": "openai-compatible",
            "base_url": BOI_LLM_BASE_URL,
            "model": BOI_LLM_MODEL,
            "api_key_configured": bool(BOI_LLM_API_KEY),
        },
        "boi_agent": {
            "backend": BOI_AGENT_BACKEND,
            "router": {
                "mode": BOI_AGENT_ROUTER_MODE,
                "llm_enabled": BOI_AGENT_ROUTER_LLM_ENABLED,
                "required": BOI_AGENT_ROUTER_REQUIRED,
                "base_url": BOI_AGENT_ROUTER_BASE_URL,
                "model": BOI_AGENT_ROUTER_MODEL,
                "timeout_seconds": BOI_AGENT_ROUTER_TIMEOUT_SECONDS,
                "failure_backoff_seconds": BOI_AGENT_ROUTER_FAILURE_BACKOFF_SECONDS,
                "backoff_remaining_seconds": round(router_llm_backoff_remaining(), 1),
                "max_tokens": BOI_AGENT_ROUTER_MAX_TOKENS,
                "confidence_threshold": BOI_AGENT_ROUTER_CONFIDENCE_THRESHOLD,
            },
            "status_writer": {
                "llm_enabled": BOI_AGENT_STATUS_LLM_ENABLED,
                "required": BOI_AGENT_STATUS_REQUIRED,
                "base_url": BOI_AGENT_STATUS_BASE_URL,
                "model": BOI_AGENT_STATUS_MODEL,
                "timeout_seconds": BOI_AGENT_STATUS_TIMEOUT_SECONDS,
                "max_tokens": BOI_AGENT_STATUS_MAX_TOKENS,
            },
            "composer": {
                "llm_enabled": BOI_AGENT_COMPOSER_LLM_ENABLED,
                "required": BOI_AGENT_COMPOSER_REQUIRED,
                "base_url": BOI_AGENT_COMPOSER_BASE_URL,
                "model": BOI_AGENT_COMPOSER_MODEL,
                "timeout_seconds": BOI_AGENT_COMPOSER_TIMEOUT_SECONDS,
                "max_tokens": BOI_AGENT_COMPOSER_MAX_TOKENS,
            },
            "chat_timeout_seconds": BOI_AGENT_CHAT_TIMEOUT_SECONDS,
            "native_max_tool_loops": BOI_AGENT_NATIVE_MAX_TOOL_LOOPS,
            "native_tool_timeout_seconds": BOI_AGENT_NATIVE_TOOL_TIMEOUT_SECONDS,
            "langgraph": {
                "available": LANGGRAPH_AVAILABLE,
                "required": BOI_AGENT_LANGGRAPH_REQUIRED,
                "runtime": "LangGraph" if LANGGRAPH_AVAILABLE else "unavailable",
            },
            "langflow_endpoint": LANGFLOW_BOI_AGENT_ENDPOINT,
            "cache_warmup": agent_cache_warmup_state(),
        },
        "event_broker": {"type": "kafka", "bootstrap": KAFKA_BOOTSTRAP, "topic": BOI_EVENTS_TOPIC},
        "connectors": {"action_gateway_url": ACTION_GATEWAY_URL, "langflow": "peer_connector"},
    }


@app.get("/api/auth/me")
async def api_auth_me(identity: AuthIdentity = Depends(current_identity)) -> dict[str, Any]:
    return {
        "employee_id": identity.employee_id,
        "display_name": identity.display_name,
        "email": identity.email,
        "teams": identity.teams,
        "roles": identity.roles,
        "auth_source": identity.auth_source,
        "auth_mode": auth_mode(),
        "is_admin": identity.is_admin,
    }


def cookie_secure() -> bool:
    return os.getenv("BOI_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"}


def safe_next_url(next_url: str | None) -> str:
    value = next_url or "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


@app.get("/auth/login")
async def auth_login(next: str = "/") -> RedirectResponse:
    if auth_mode() != "keycloak":
        return RedirectResponse(safe_next_url(next), status_code=302)
    try:
        state_token, state, challenge = create_oidc_state(safe_next_url(next))
        redirect = RedirectResponse(keycloak_authorization_url(state=state, code_challenge=challenge), status_code=302)
        redirect.set_cookie(
            OIDC_STATE_COOKIE_NAME,
            state_token,
            max_age=600,
            httponly=True,
            secure=cookie_secure(),
            samesite="lax",
        )
        return redirect
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/auth/callback")
async def auth_callback(
    code: str = "",
    state: str = "",
    oidc_state: str | None = Cookie(default=None, alias=OIDC_STATE_COOKIE_NAME),
) -> RedirectResponse:
    if auth_mode() != "keycloak":
        return RedirectResponse("/", status_code=302)
    if not code or not state or not oidc_state:
        raise HTTPException(status_code=400, detail="missing Keycloak callback parameters")
    try:
        state_payload = decode_oidc_state(oidc_state)
        if state_payload.get("state") != state:
            raise AuthError(401, "OIDC state mismatch")
        token_body = exchange_keycloak_code(code, state_payload)
        bearer = str(token_body.get("id_token") or token_body.get("access_token") or "")
        if not bearer:
            raise AuthError(401, "Keycloak token response has no usable token")
        claims = decode_keycloak_bearer(bearer)
        if token_body.get("id_token") and claims.get("nonce") != state_payload.get("nonce"):
            raise AuthError(401, "OIDC nonce mismatch")
        identity = remember_identity(identity_from_claims(claims, auth_source="keycloak", bearer_token=str(token_body.get("access_token") or "")))
        redirect = RedirectResponse(safe_next_url(str(state_payload.get("next") or "/")), status_code=302)
        redirect.set_cookie(
            SESSION_COOKIE_NAME,
            create_session_token(identity),
            max_age=int(os.getenv("BOI_SESSION_TTL_SECONDS", "28800")),
            httponly=True,
            secure=cookie_secure(),
            samesite="lax",
        )
        redirect.delete_cookie(OIDC_STATE_COOKIE_NAME)
        return redirect
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/auth/logout")
async def auth_logout(next: str = "/") -> RedirectResponse:
    target = keycloak_logout_url(safe_next_url(next)) if auth_mode() == "keycloak" else safe_next_url(next)
    redirect = RedirectResponse(target, status_code=302)
    redirect.delete_cookie(SESSION_COOKIE_NAME)
    redirect.delete_cookie(OIDC_STATE_COOKIE_NAME)
    return redirect


def poc_payload(req: PocConnectorRequest) -> dict[str, Any]:
    return req.payload or (req.event.get("payload") if isinstance(req.event, dict) else {}) or {}


def poc_result(*, action: str, req: PocConnectorRequest, result: dict[str, Any], status: str = "invoked") -> dict[str, Any]:
    return {
        "ok": True,
        "status": status,
        "action": action,
        "request_id": req.request_id,
        "dry_run": bool(req.dry_run),
        "approved_by": req.approved_by,
        "result": result,
    }


def require_poc_approval(req: PocConnectorRequest) -> None:
    if not req.approved_by:
        raise HTTPException(
            status_code=403,
            detail={
                "ok": False,
                "status": "approval_required",
                "message": "approved_by is required for high-risk equipment actions.",
        },
    )


@app.post("/api/poc/direct-development/messenger-share", dependencies=[Depends(require_service_token)])
async def poc_direct_development_messenger_share(req: PocConnectorRequest) -> dict[str, Any]:
    require_poc_approval(req)
    payload = poc_payload(req)
    return poc_result(
        action="direct_development.messenger_share.publish",
        req=req,
        result={
            "status": "simulated",
            "simulation": True,
            "simulation_label": "SIMULATED",
            "real_system_connected": False,
            "real_system_status": "unavailable",
            "simulated_system": "메신저",
            "share_target": payload.get("share_target") or "direct-development-council",
            "approved_by": req.approved_by,
            "message": "SIMULATED: 승인된 공유 요청을 기록했지만 실제 메신저 발송은 수행하지 않았습니다.",
        },
    )


@app.post("/api/poc/equipment/trend-history", dependencies=[Depends(require_service_token)])
async def poc_equipment_trend_history(req: PocConnectorRequest) -> dict[str, Any]:
    payload = poc_payload(req)
    return poc_result(
        action="sop.equipment.request_trend_history",
        req=req,
        result={
            "equipment_id": payload.get("equipment_id"),
            "trend_status": "anomaly_detected",
            "lot_history_ref": f"/mock/vision-inspection/lot-history/{payload.get('lot_id', 'LOT-UNKNOWN')}",
            "wafer_history_ref": f"/mock/vision-inspection/wafer-history/{payload.get('wafer_id', 'WF-UNKNOWN')}",
            "message": "Trend와 이력 데이터를 확인했습니다.",
        },
    )


@app.post("/api/poc/equipment/raw-data", dependencies=[Depends(require_service_token)])
async def poc_equipment_raw_data(req: PocConnectorRequest) -> dict[str, Any]:
    payload = poc_payload(req)
    equipment_id = payload.get("equipment_id", "EQP-UNKNOWN")
    lot_id = payload.get("lot_id", "LOT-UNKNOWN")
    return poc_result(
        action="sop.equipment.request_raw_data",
        req=req,
        result={
            "equipment_id": equipment_id,
            "raw_data_ref": f"/mock/vision-inspection/raw-data/{equipment_id}/{lot_id}",
            "source_data_ref": f"/mock/quality-system/source-data/{equipment_id}",
            "message": "Raw/Source Data 참조 링크를 생성했습니다.",
        },
    )


@app.post("/api/poc/equipment/maintenance-guide", dependencies=[Depends(require_service_token)])
async def poc_equipment_maintenance_guide(req: PocConnectorRequest) -> dict[str, Any]:
    payload = poc_payload(req)
    return poc_result(
        action="sop.equipment.request_maintenance_guide",
        req=req,
        result={
            "equipment_id": payload.get("equipment_id"),
            "guide_boi_ref": "boi:public:sop:equipment-abnormal-response",
            "recommended_steps": ["Source Data 확인", "장비 이력 확인", "장비 이상 여부 판단"],
            "message": "장비 보전 가이드를 반환했습니다.",
        },
    )


@app.post("/api/poc/equipment/notify-owner", dependencies=[Depends(require_service_token)])
async def poc_equipment_notify_owner(req: PocConnectorRequest) -> dict[str, Any]:
    payload = poc_payload(req)
    return poc_result(
        action="sop.equipment.notify_action_owner",
        req=req,
        result={
            "notification_status": "sent",
            "recipient": payload.get("owner") or payload.get("assignee") or DEMO_EMPLOYEE_ID,
            "equipment_id": payload.get("equipment_id"),
            "message": "이상 조치 요청 알림을 발송했습니다.",
        },
    )


@app.post("/api/poc/equipment/process-hold", dependencies=[Depends(require_service_token)])
async def poc_equipment_process_hold(req: PocConnectorRequest) -> dict[str, Any]:
    require_poc_approval(req)
    payload = poc_payload(req)
    return poc_result(
        action="sop.equipment.block_process_progress",
        req=req,
        result={
            "requested_state": "process_hold",
            "equipment_id": payload.get("equipment_id"),
            "approved_by": req.approved_by,
            "message": "승인된 공정 진행 금지 요청을 PoC endpoint가 접수했습니다.",
        },
    )


@app.post("/api/poc/equipment/spec-rule-change", dependencies=[Depends(require_service_token)])
async def poc_equipment_spec_rule_change(req: PocConnectorRequest) -> dict[str, Any]:
    require_poc_approval(req)
    payload = poc_payload(req)
    return poc_result(
        action="sop.equipment.change_spec_rule",
        req=req,
        result={
            "requested_change": "spec_rule_change",
            "equipment_id": payload.get("equipment_id"),
            "approved_by": req.approved_by,
            "message": "승인된 Spec/Rule 변경 요청을 PoC endpoint가 접수했습니다.",
        },
    )


@app.post("/api/poc/mcp/call", dependencies=[Depends(require_service_token)])
async def poc_mcp_call(req: PocMcpCallRequest) -> dict[str, Any]:
    tool = req.tool or str(req.arguments.get("tool") or "")
    if tool != "boi.search":
        raise HTTPException(status_code=400, detail=f"Unsupported PoC MCP tool: {tool}")
    employee_id = str(req.arguments.get("employee_id") or DEMO_EMPLOYEE_ID)
    query = str(req.arguments.get("query") or "").lower()
    allowed_visibility = set(req.arguments.get("allowed_visibility") or ["public", "team", "private"])
    limit = int(req.arguments.get("limit") or 10)
    scored_results = []
    for index, doc in enumerate(accessible_docs(employee_id)):
        metadata = doc["metadata"]
        visibility = str(metadata.get("visibility") or "")
        title = str(metadata.get("title") or "")
        boi_id = str(metadata.get("boi_id") or "")
        uri = str(doc.get("uri") or "")
        description = str(metadata.get("description") or "")
        tags = " ".join(str(tag) for tag in metadata.get("tags") or [])
        metadata_blob = "\n".join([title, boi_id, uri, description, tags]).lower()
        body_blob = str(doc.get("body", "")).lower()
        haystack = metadata_blob + "\n" + body_blob
        if visibility not in allowed_visibility:
            continue
        if query and query not in haystack:
            continue
        score = 0
        if query:
            if query in title.lower():
                score += 100
            if query in boi_id.lower() or query in uri.lower():
                score += 80
            if query in description.lower():
                score += 40
            if query in tags.lower():
                score += 30
            if query in body_blob:
                score += 10
        scored_results.append(
            (
                -score,
                index,
                {
                    "boi_id": metadata.get("boi_id"),
                    "title": metadata.get("title"),
                    "description": metadata.get("description"),
                    "type": metadata.get("type"),
                    "visibility": visibility,
                    "uri": doc.get("uri"),
                },
            )
        )
    results = [item for _score, _index, item in sorted(scored_results)[:limit]]
    return {
        "ok": True,
        "status": "mcp_invoked",
        "server": req.server or {"name": "boi-wiki-mcp"},
        "tool": tool,
        "request_id": req.request_id,
        "count": len(results),
        "results": results,
    }


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    employee_id: str = Depends(current_employee),
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
    folder: str = "",
    archive_status: str = "active",
    partial: str = "",
) -> HTMLResponse:
    selected_folder = normalize_folder(folder)
    accessible = accessible_docs(employee_id)
    filtered_docs = filter_docs_ontology_aware(
        accessible,
        employee_id,
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
        archive_status=archive_status,
    )
    folder_tree = with_folder_urls(
        build_folder_tree(filtered_docs, selected_folder),
        employee_id=employee_id,
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
    )
    docs = [d for d in filtered_docs if folder_matches(d, selected_folder)]
    breadcrumbs = with_breadcrumb_urls(
        folder_breadcrumbs(selected_folder),
        employee_id=employee_id,
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
    )
    recent_event_logs = read_event_logs(limit=8, event_type=event_type or None)
    doc_lookup = build_doc_lookup(accessible)
    context = {
        "request": request,
        "employee_id": employee_id,
        "shell": app_shell_context(
            request,
            employee_id,
            active_nav="library",
            title="BoI Wiki",
            description="AI Agent의 협업 표준 문서를 업무 단위의 Event와 SOP 기반의 AI Native Workflow 그리고 Action을 기준으로 탐색합니다.",
        ),
        "user_name": user_name_for(employee_id),
        "auth_mode": auth_mode(),
        "teams": teams_for(employee_id),
        "docs": docs_for_template(docs, employee_id, selected_folder),
        "q": q,
        "event_type": event_type,
        "visibility": visibility,
        "boi_type": boi_type,
        "folder": selected_folder,
        "archive_status": archive_status,
        "folder_tree": folder_tree,
        "breadcrumbs": breadcrumbs,
        "event_context": event_context_for_template(event_type, employee_id),
        "selected_folder_label": folder_label(selected_folder),
        "total_filtered_docs": len(filtered_docs),
        "event_types": load_event_types(),
        "event_logs": event_rows_for_template(recent_event_logs, doc_lookup=doc_lookup, employee_id=employee_id),
    }
    template_name = "library_fragment.html" if partial == "library" else "index.html"
    return templates.TemplateResponse(template_name, context)


@app.get("/sops", response_class=HTMLResponse)
async def sops_page(
    request: Request,
    employee_id: str = Depends(current_employee),
    q: str = "",
    visibility: str = "",
    status: str = "",
    category: str = "sop",
) -> HTMLResponse:
    accessible = accessible_docs(employee_id)
    base_docs = [doc for doc in accessible if is_sop_related_doc(doc)]
    normalized_category = "all-related" if category == "all-related" else "sop"
    docs = filter_sop_docs(base_docs, q=q, visibility=visibility, status=status, category=normalized_category)
    visibility_options = sorted({str((doc.get("metadata") or {}).get("visibility") or "") for doc in base_docs if (doc.get("metadata") or {}).get("visibility")})
    status_options = sorted({str((doc.get("metadata") or {}).get("status") or "") for doc in base_docs if (doc.get("metadata") or {}).get("status")})
    return templates.TemplateResponse(
        "sops.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="sops",
                title="SOP",
                description="Agent Harness, BoI Wiki, 설비 이상 대응 같은 공통 SOP와 실행 가이드를 확인합니다.",
            ),
            "docs": docs,
            "q": q,
            "visibility": visibility,
            "status": status,
            "category": normalized_category,
            "total_sop_docs": len(docs),
            "visibility_options": visibility_options,
            "status_options": status_options,
            "has_active_filter": bool(q or visibility or status or normalized_category != "sop"),
            "clear_url": app_url("/sops", employee_id),
        },
    )


@app.get("/permissions", response_class=HTMLResponse)
async def permissions_page(
    request: Request,
    employee_id: str = Depends(current_employee),
) -> HTMLResponse:
    state = rbac_state()
    return templates.TemplateResponse(
        "permissions.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="library",
                title="권한 관리",
                description="사번 기준 팀, 역할, BoI Profile ACL, audit을 관리합니다.",
            ),
            "me": {
                "employee_id": employee_id,
                "teams": teams_for(employee_id),
                "roles": roles_for(employee_id),
            },
            "teams": sorted((state.get("teams") or {}).values(), key=lambda item: str(item.get("team_id") or "")),
            "roles": state.get("roles") or RBAC_ROLES,
            "bindings": state.get("bindings") or [],
            "audit_rows": rbac_audit_rows(limit=40),
            "can_manage": rbac_can_manage(employee_id),
        },
    )


@app.get("/api/rbac/me")
async def api_rbac_me(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {
        "ok": True,
        "employee_id": employee_id,
        "teams": teams_for(employee_id),
        "roles": roles_for(employee_id),
        "can_manage": rbac_can_manage(employee_id),
        "classification_policy_version": CLASSIFICATION_POLICY_VERSION,
    }


@app.get("/api/rbac/teams")
async def api_rbac_teams(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    state = rbac_state()
    teams = sorted((state.get("teams") or {}).values(), key=lambda item: str(item.get("team_id") or ""))
    return {"ok": True, "count": len(teams), "items": teams}


@app.post("/api/rbac/teams")
async def api_rbac_create_team(req: RbacTeamRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    if not rbac_can_manage(employee_id):
        raise HTTPException(status_code=403, detail="team management role required")
    state = rbac_state()
    teams = state.setdefault("teams", {})
    team_id = req.team_id.strip()
    if not team_id:
        raise HTTPException(status_code=400, detail="team_id is required")
    team = teams.setdefault(
        team_id,
        {
            "team_id": team_id,
            "display_name": req.display_name or team_id,
            "description": req.description,
            "owners": [],
            "members": [],
            "status": "active",
        },
    )
    team["display_name"] = req.display_name or team.get("display_name") or team_id
    team["description"] = req.description
    team["status"] = req.status or team.get("status") or "active"
    if employee_id not in [str(item) for item in (team.get("owners") or [])]:
        team.setdefault("owners", []).append(employee_id)
    write_rbac_state(state)
    append_rbac_audit(employee_id, "team_upsert", {"team_id": team_id, "display_name": team["display_name"]})
    return {"ok": True, "team": team}


@app.post("/api/rbac/teams/{team_id}/members")
async def api_rbac_add_team_member(
    team_id: str,
    req: RbacTeamMemberRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    if not rbac_can_manage(employee_id, team_id=team_id):
        raise HTTPException(status_code=403, detail="team owner or admin role required")
    member_id = req.employee_id.strip()
    if not re.fullmatch(r"\d{6,7}", member_id):
        raise HTTPException(status_code=400, detail="employee_id must be 6 or 7 digits")
    state = rbac_state()
    teams = state.setdefault("teams", {})
    if team_id not in teams:
        raise HTTPException(status_code=404, detail="team not found")
    team = teams[team_id]
    bucket = "owners" if req.role == "owner" else "members"
    team.setdefault(bucket, [])
    if req.action == "remove":
        team[bucket] = [item for item in team.get(bucket) or [] if str(item) != member_id]
        if bucket == "members":
            team["owners"] = [item for item in team.get("owners") or [] if str(item) != member_id]
        audit_action = "team_member_remove"
    else:
        if member_id not in [str(item) for item in team[bucket]]:
            team[bucket].append(member_id)
        if bucket == "owners" and member_id not in [str(item) for item in team.get("members") or []]:
            team.setdefault("members", []).append(member_id)
        audit_action = "team_member_add"
    write_rbac_state(state)
    append_rbac_audit(employee_id, audit_action, {"team_id": team_id, "member_id": member_id, "role": req.role})
    return {"ok": True, "team": team}


@app.get("/api/rbac/roles")
async def api_rbac_roles(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {"ok": True, "items": rbac_state().get("roles") or RBAC_ROLES}


@app.post("/api/rbac/bindings")
async def api_rbac_binding(req: RbacBindingRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    if not rbac_can_manage(employee_id):
        raise HTTPException(status_code=403, detail="role binding management requires admin/editor")
    roles = [role for role in req.roles if role in {item["role"] for item in RBAC_ROLES}]
    if not roles:
        raise HTTPException(status_code=400, detail="at least one valid role is required")
    subject_type = req.subject_type.strip()
    if subject_type not in {"employee", "team"}:
        raise HTTPException(status_code=400, detail="subject_type must be employee or team")
    binding = {
        "binding_id": f"bind-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "subject_type": subject_type,
        "subject_id": req.subject_id.strip(),
        "roles": roles,
        "scope": req.scope or "global",
        "resource": req.resource,
        "created_by": employee_id,
        "created_at": now_iso(),
    }
    state = rbac_state()
    state.setdefault("bindings", []).append(binding)
    write_rbac_state(state)
    append_rbac_audit(employee_id, "role_binding_add", binding)
    return {"ok": True, "binding": binding}


@app.post("/api/rbac/check")
async def api_rbac_check(req: RbacCheckRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    target_employee = req.employee_id or employee_id
    if target_employee != employee_id and "boi.admin" not in roles_for(employee_id):
        raise HTTPException(status_code=403, detail="only admin can check another employee")
    decision = role_binding_decision(
        target_employee,
        req.required_role,
        scope=req.scope or "global",
        resource=req.resource or "",
    )
    return {"ok": True, "employee_id": target_employee, "decision": decision}


@app.get("/api/docs/{boi_id:path}/access")
async def api_doc_access(boi_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        hidden_doc = find_doc_by_id(boi_id, employee_id, include_inaccessible=True)
        if not hidden_doc:
            raise HTTPException(status_code=404, detail="BoI not found")
        decision = access_policy_for_doc(hidden_doc, employee_id)
        return {"ok": True, "boi_id": boi_id, "access": decision.to_dict(), "visible": False}
    decision = access_policy_for_doc(doc, employee_id)
    return {"ok": True, "boi_id": boi_id, "access": decision.to_dict(), "visible": decision.can_read}


@app.post("/api/docs/{boi_id:path}/break-glass")
async def api_doc_break_glass(
    boi_id: str,
    req: BreakGlassRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    if "boi.admin" not in roles_for(employee_id):
        raise HTTPException(status_code=403, detail="break-glass requires admin role")
    if not req.reason.strip():
        raise HTTPException(status_code=400, detail="reason is required")
    doc = find_doc_by_id(boi_id, employee_id, include_inaccessible=True)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found")
    decision = access_policy_for_doc(doc, employee_id, break_glass=True)
    if not decision.can_read:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "break-glass access denied by BoI profile policy",
                "access": decision.to_dict(),
            },
        )
    audit = append_rbac_audit(
        employee_id,
        "break_glass_access",
        {"boi_id": boi_id, "reason": req.reason, "ticket_ref": req.ticket_ref, "decision": decision.to_dict()},
    )
    return {"ok": True, "boi_id": boi_id, "access": decision.to_dict(), "audit": audit}


def event_type_draft_dir() -> Path:
    ensure_dirs()
    path = DRAFT_ROOT / "event_type_drafts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def event_type_draft_path(draft_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_.:-]", "-", draft_id)
    return event_type_draft_dir() / f"{safe}.json"


def validate_event_type_draft_payload(payload: dict[str, Any]) -> dict[str, Any]:
    event_type = str(payload.get("event_type") or "")
    errors: list[str] = []
    warnings: list[str] = []
    if not re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+\.v\d+", event_type):
        errors.append("event_type must follow dotted lower-case versioned naming, e.g. domain.event.requested.v1")
    if get_event_type(event_type):
        errors.append("event_type already exists in catalog")
    if not payload.get("name_ko"):
        warnings.append("name_ko is recommended for operator-facing UI")
    if not payload.get("description"):
        warnings.append("description is recommended")
    if not payload.get("sop_ref") and not payload.get("workflow_stage"):
        warnings.append("sop_ref or workflow_stage should be provided when this event participates in SOP workflow")
    recommended_actions = payload.get("recommended_actions") or []
    action_catalog = load_action_catalog()
    actions_by_key = {str(item.get("action_key") or item.get("key") or ""): item for item in action_catalog}
    action_keys = set(actions_by_key)
    unknown_actions = [item for item in recommended_actions if item not in action_keys]
    if unknown_actions:
        warnings.append(f"unknown recommended action(s): {', '.join(unknown_actions)}")
    recommended_manual_actions = payload.get("recommended_manual_actions") or []
    unknown_manual_actions = [item for item in recommended_manual_actions if item not in action_keys]
    if unknown_manual_actions:
        warnings.append(f"unknown recommended manual action(s): {', '.join(unknown_manual_actions)}")
    non_manual_actions = [
        item
        for item in recommended_manual_actions
        if item in actions_by_key and actions_by_key[item].get("connector_kind") != "manual"
    ]
    if non_manual_actions:
        warnings.append(f"recommended_manual_actions must reference manual action(s): {', '.join(non_manual_actions)}")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def create_event_type_draft(req: EventTypeDraftRequest, employee_id: str) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="user_confirmed=true is required to create an Event Type draft")
    payload = req.model_dump()
    validation = validate_event_type_draft_payload(payload)
    draft_id = f"event-type-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    row = {
        "draft_id": draft_id,
        "status": "draft",
        "created_at": now_iso(),
        "created_by": employee_id,
        "event_type": req.event_type,
        "proposal": payload,
        "validation": validation,
        "catalog_patch_proposal": {
            "event_type": req.event_type,
            "name_ko": req.name_ko or req.event_type,
            "description": req.description,
            "default_boi_type": req.default_boi_type,
            "default_flow_key": req.default_flow_key,
            "default_visibility": req.default_visibility,
            "owner": req.owner or employee_id,
            "topic": req.topic,
            "workflow_stage": req.workflow_stage,
            "sop_ref": req.sop_ref,
            "sop_stage_id": req.sop_stage_id,
            "wiki_usage": req.wiki_usage,
            "payload_schema": req.payload_schema,
            "recommended_actions": req.recommended_actions,
            "recommended_manual_actions": req.recommended_manual_actions,
        },
    }
    event_type_draft_path(draft_id).write_text(json.dumps(row, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    append_rbac_audit(employee_id, "event_type_draft_create", {"draft_id": draft_id, "event_type": req.event_type, "validation": validation})
    return row


def read_event_type_drafts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(event_type_draft_dir().glob("*.json")):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True)


def visible_event_type_drafts(employee_id: str) -> list[dict[str, Any]]:
    rows = read_event_type_drafts()
    admin = "boi.admin" in roles_for(employee_id)
    return [row for row in rows if row.get("created_by") == employee_id or admin]


def event_type_catalog_path() -> Path:
    ensure_dirs()
    EVENT_CATALOG_ROOT.mkdir(parents=True, exist_ok=True)
    return EVENT_CATALOG_ROOT / "event_types.yaml"


def event_type_catalog_entry_from_draft(draft: dict[str, Any]) -> dict[str, Any]:
    proposal = draft.get("proposal") if isinstance(draft.get("proposal"), dict) else {}
    patch = draft.get("catalog_patch_proposal") if isinstance(draft.get("catalog_patch_proposal"), dict) else {}
    source = {**proposal, **patch}
    keep_fields = [
        "event_type",
        "name_ko",
        "description",
        "default_boi_type",
        "default_flow_key",
        "default_visibility",
        "owner",
        "status",
        "topic",
        "workflow_stage",
        "sop_ref",
        "sop_stage_id",
        "wiki_usage",
        "payload_schema",
        "recommended_actions",
        "recommended_manual_actions",
    ]
    entry: dict[str, Any] = {}
    for field_name in keep_fields:
        value = source.get(field_name)
        if value in (None, "", [], {}):
            continue
        entry[field_name] = value
    entry.setdefault("event_type", draft.get("event_type") or proposal.get("event_type"))
    entry.setdefault("name_ko", proposal.get("name_ko") or draft.get("event_type") or entry.get("event_type"))
    entry.setdefault("description", proposal.get("description") or "")
    entry.setdefault("status", proposal.get("status") or "draft")
    entry.setdefault("topic", proposal.get("topic") or "boi.events")
    return entry


def proposed_event_catalog_content_with_entry(catalog_path: Path, entry: dict[str, Any]) -> str:
    if catalog_path.exists():
        parsed = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    else:
        parsed = {}
    if isinstance(parsed, list):
        event_types = parsed
        parsed = {"event_types": event_types}
    elif isinstance(parsed, dict):
        event_types = parsed.get("event_types")
        if not isinstance(event_types, list):
            event_types = []
            parsed["event_types"] = event_types
    else:
        parsed = {"event_types": []}
        event_types = parsed["event_types"]
    event_type = str(entry.get("event_type") or "")
    if any(str(item.get("event_type") or "") == event_type for item in event_types if isinstance(item, dict)):
        raise HTTPException(status_code=409, detail=f"event_type already exists in catalog: {event_type}")
    event_types.append(entry)
    return yaml.safe_dump(parsed, allow_unicode=True, sort_keys=False)


def apply_event_type_draft(draft_id: str, req: EventTypeDraftApplyRequest, employee_id: str) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.promoter")
    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="user_confirmed=true is required to apply an Event Type draft")
    path = event_type_draft_path(draft_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="draft not found")
    draft = json.loads(path.read_text(encoding="utf-8"))
    if draft.get("created_by") != employee_id and "boi.admin" not in roles_for(employee_id):
        raise HTTPException(status_code=403, detail="Event Type draft is not visible to this employee")
    if draft.get("status") == "applied" and draft.get("apply_result"):
        return {"ok": True, "status": "already_applied", "draft": draft, "apply_result": draft.get("apply_result")}
    validation = validate_event_type_draft_payload(draft.get("proposal") or {})
    if not validation.get("valid"):
        draft["validation"] = validation
        path.write_text(json.dumps(draft, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        raise HTTPException(
            status_code=422,
            detail={
                "ok": False,
                "status": "validation_failed",
                "validation": validation,
                "draft": draft,
            },
        )
    entry = event_type_catalog_entry_from_draft(draft)
    catalog_path = event_type_catalog_path()
    current_content = catalog_path.read_text(encoding="utf-8") if catalog_path.exists() else "event_types: []\n"
    if not catalog_path.exists():
        catalog_path.write_text(current_content, encoding="utf-8")
    base_sha = hashlib.sha256(current_content.encode("utf-8")).hexdigest()
    proposed_content = proposed_event_catalog_content_with_entry(catalog_path, entry)
    apply_result = apply_source_edit(
        source_path=catalog_path,
        base_sha256=base_sha,
        proposed_content=proposed_content,
        employee_id=employee_id,
        author=req.author,
        note=req.note or f"Apply Event Type draft {draft_id}",
    )
    draft.update(
        {
            "status": "applied",
            "validation": validation,
            "applied_at": now_iso(),
            "applied_by": employee_id,
            "catalog_entry": entry,
            "apply_result": {
                "status": apply_result.get("status"),
                "path": apply_result.get("path"),
                "commit_status": apply_result.get("commit_status"),
                "commit_hash": apply_result.get("commit_hash"),
                "sha256": apply_result.get("sha256"),
            },
        }
    )
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    invalidate_catalog_caches()
    append_rbac_audit(
        employee_id,
        "event_type_draft_apply",
        {
            "draft_id": draft_id,
            "event_type": entry.get("event_type"),
            "commit_status": apply_result.get("commit_status"),
            "commit_hash": apply_result.get("commit_hash"),
            "note": req.note,
        },
    )
    return {"ok": True, "status": "applied", "draft": draft, "apply_result": apply_result}


@app.post("/api/event-types/drafts")
async def api_event_type_draft_create(req: EventTypeDraftRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    draft = create_event_type_draft(req, employee_id)
    return {"ok": True, "draft": draft}


@app.get("/api/event-types/drafts")
async def api_event_type_drafts(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.viewer")
    visible = visible_event_type_drafts(employee_id)
    return {"ok": True, "count": len(visible), "items": visible}


@app.post("/api/event-types/drafts/{draft_id}/validate")
async def api_event_type_draft_validate(draft_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    path = event_type_draft_path(draft_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="draft not found")
    draft = json.loads(path.read_text(encoding="utf-8"))
    validation = validate_event_type_draft_payload(draft.get("proposal") or {})
    draft["validation"] = validation
    draft["validated_at"] = now_iso()
    draft["validated_by"] = employee_id
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    append_rbac_audit(employee_id, "event_type_draft_validate", {"draft_id": draft_id, "validation": validation})
    return {"ok": True, "draft": draft}


@app.post("/api/event-types/drafts/{draft_id}/apply")
async def api_event_type_draft_apply(
    draft_id: str,
    req: EventTypeDraftApplyRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    return apply_event_type_draft(draft_id, req, employee_id)


@app.get("/source", response_class=HTMLResponse)
async def source_page(
    request: Request,
    path: str,
    employee_id: str = Depends(current_employee),
) -> HTMLResponse:
    source_path = resolve_source_path(path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="source file not found")
    source = source_payload(source_path, employee_id)
    return templates.TemplateResponse(
        "source.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="library",
                title="Source Viewer",
                description=str(source.get("path") or path),
                page_actions=[{"label": "Validated edit guide", "href": source["guide_url"], "kind": "secondary"}],
            ),
            "source": source,
        },
    )


@app.get("/api/source")
async def get_source(
    path: str,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    source_path = resolve_source_path(path)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="source file not found")
    return source_payload(source_path, employee_id)


@app.post("/api/source/preview")
async def preview_source_edit(
    req: SourcePreviewRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    source_path = resolve_source_path(req.path)
    return source_preview_response(
        source_path=source_path,
        proposed_content=req.proposed_content,
        employee_id=employee_id,
        base_sha256=req.base_sha256,
    )


@app.post("/api/source/apply")
async def apply_source_edit_api(
    req: SourceApplyRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    source_path = resolve_source_path(req.path)
    return apply_source_edit(
        source_path=source_path,
        base_sha256=req.base_sha256,
        proposed_content=req.proposed_content,
        employee_id=employee_id,
        author=req.author,
        note=req.note,
    )


@app.get("/api/docs/{boi_id:path}/metadata-fragment", response_class=HTMLResponse)
async def doc_metadata_fragment(
    request: Request,
    boi_id: str,
    employee_id: str = Depends(current_employee),
) -> HTMLResponse:
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    return HTMLResponse(str(metadata_fragment_html_for_doc(doc, request)))


@app.get("/api/docs/{boi_id:path}/body-editor")
async def doc_body_editor(
    boi_id: str,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    payload = full_body_editor_payload_for_doc(doc, employee_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Body editor is not available for this document")
    return payload


@app.post("/api/docs/{boi_id:path}/body-preview")
async def preview_doc_body_edit(
    boi_id: str,
    req: BodyPreviewRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    source_path = Path(str(doc.get("path") or ""))
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="source file not found")
    proposed_content = compose_markdown(doc["metadata"], req.proposed_body)
    response = source_preview_response(
        source_path=source_path,
        proposed_content=proposed_content,
        employee_id=employee_id,
        base_sha256=req.base_sha256,
    )
    response["body_preview_html"] = response.get("preview", {}).get("html", "")
    return response


@app.post("/api/docs/{boi_id:path}/body-apply")
async def apply_doc_body_edit(
    boi_id: str,
    req: BodyApplyRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    source_path = Path(str(doc.get("path") or ""))
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="source file not found")
    proposed_content = compose_markdown(doc["metadata"], req.proposed_body)
    response = apply_source_edit(
        source_path=source_path,
        base_sha256=req.base_sha256,
        proposed_content=proposed_content,
        employee_id=employee_id,
        author=req.author,
        note=req.note or "inline body editor",
    )
    response["body_preview_html"] = response.get("preview", {}).get("html", "")
    return response


@app.get("/docs/{boi_id:path}", response_class=HTMLResponse)
async def doc_page(
    request: Request,
    boi_id: str,
    employee_id: str = Depends(current_employee),
    folder: str = "",
) -> HTMLResponse:
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        return templates.TemplateResponse(
            "missing_doc.html",
            {
                "request": request,
                "employee_id": employee_id,
                "shell": app_shell_context(
                    request,
                    employee_id,
                    active_nav="library",
                    title="BoI not found or not accessible",
                    description="요청한 BoI 문서를 찾을 수 없거나 현재 사번으로 접근할 수 없습니다.",
                    page_actions=[{"label": "BoI 목록", "href": browse_url(employee_id), "kind": "secondary"}],
                ),
                "boi_id": boi_id,
            },
            status_code=404,
        )
    doc_lookup = referenced_doc_lookup_for_doc(doc, employee_id)
    doc_folder_path = doc_folder(doc)
    return_folder = normalize_folder(folder) or doc_folder_path
    workflow = doc["metadata"].get("workflow") or {}
    workflow_key = str(workflow.get("workflow_key") or "")
    workflow_poc = workflow_context(workflow_key, employee_id, doc_lookup=doc_lookup) if workflow_key else None
    graph_ref = str(doc["metadata"].get("boi_id") or doc.get("uri", "").lstrip("/"))
    doc_query = urlencode({"employee_id": employee_id})
    return templates.TemplateResponse(
        "doc.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav=active_nav_for_doc(doc),
                title=str(doc["metadata"].get("title") or "BoI Document"),
                description=str(doc["metadata"].get("description") or ""),
                page_actions=[
                    {"label": "폴더로 돌아가기", "href": browse_url(employee_id, folder=return_folder), "kind": "secondary"},
                    *([{"label": "Source 보기 / 검증 편집", "href": source_url_for_doc(doc, employee_id), "kind": "secondary"}] if source_url_for_doc(doc, employee_id) else []),
                    *([{"label": "같은 Event Type BoI", "href": browse_url(employee_id, event_type=doc["metadata"].get("event_type", "")), "kind": "secondary"}] if doc["metadata"].get("event_type") else []),
                ],
            ),
            "doc": doc,
            "doc_folder": doc_folder_path,
            "doc_folder_breadcrumbs": with_breadcrumb_urls(
                folder_breadcrumbs(doc_folder_path),
                employee_id=employee_id,
            ),
            "doc_list_url": browse_url(employee_id, folder=return_folder),
            "source_url": source_url_for_doc(doc, employee_id),
            "doc_graph_url": "/api/okf/graph/doc/" + graph_ref + "?" + urlencode({"employee_id": employee_id}),
            "access_policy_url": "/api/docs/" + graph_ref + "/access?" + doc_query,
            "metadata_fragment_url": "/api/docs/" + graph_ref + "/metadata-fragment?" + doc_query,
            "event_type_url": browse_url(employee_id, event_type=doc["metadata"].get("event_type", "")),
            "body_html": doc_body_html_for_request(doc, employee_id, doc_lookup, request),
            "body_editor": body_editor_payload_for_doc(doc, employee_id),
            "citations": citation_rows_for_doc(doc, employee_id, doc_lookup=doc_lookup),
            "workflow_poc": workflow_poc,
            "metadata_summary_rows": metadata_summary_rows_for_template(doc["metadata"], request),
            "public_boi_base_url": boi_public_base_url(request),
            "action_spec": action_spec_for_template(doc["metadata"], request),
        },
    )


@app.get("/api/boi")
async def list_boi(
    employee_id: str = Depends(current_employee),
    q: str = "",
    event_type: str = "",
    visibility: str = "",
    boi_type: str = "",
    folder: str = "",
    archive_status: str = "active",
) -> dict[str, Any]:
    selected_folder = normalize_folder(folder)
    filtered_docs = filter_docs_ontology_aware(
        accessible_docs(employee_id),
        employee_id,
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
        archive_status=archive_status,
    )
    docs = [d for d in filtered_docs if folder_matches(d, selected_folder)]
    return {
        "employee_id": employee_id,
        "teams": teams_for(employee_id),
        "folder": selected_folder,
        "archive_status": archive_status,
        "breadcrumbs": folder_breadcrumbs(selected_folder),
        "folder_tree": build_folder_tree(filtered_docs, selected_folder),
        "count": len(docs),
        "items": docs,
    }


@app.get("/api/okf/graph")
async def api_okf_graph(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return cached_okf_graph_for_employee(employee_id)


@app.get("/api/okf/graph/doc/{boi_id:path}")
async def api_okf_doc_graph(boi_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    graph = cached_okf_graph_for_employee(employee_id)
    if doc.get("recovered_from_log"):
        graph = okf_graph_for_docs([doc], employee_id)
    return relationship_context_for_doc(doc, employee_id, graph=graph)


@app.get("/api/search/ontology")
async def api_ontology_search(
    employee_id: str = Depends(current_employee),
    q: str = "",
    scope: str = "all",
    limit: int = 8,
    current_url: str = "",
    view: str = "full",
) -> dict[str, Any]:
    return ontology_search_payload(q, employee_id, scope=scope, limit=limit, current_url=current_url, view=view)


def dedupe_suggestions(values: list[str], limit: int = 4) -> list[str]:
    seen: set[str] = set()
    suggestions: list[str] = []
    for value in values:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        suggestions.append(text)
        if len(suggestions) >= limit:
            break
    return suggestions


def page_context_suggestions(current_url: str, page_context: dict[str, Any] | None = None) -> list[str]:
    context = page_context or {}
    url = str(current_url or "")
    page_kind = str(context.get("page_kind") or "")
    title = str(context.get("title") or context.get("page_title") or "").strip()
    access = context.get("access") if isinstance(context.get("access"), dict) else {}
    if access and access.get("can_use_in_agent_context") is False:
        return [
            "현재 문서의 접근 정책과 보안 등급을 설명해줘.",
            "내 권한으로 사용할 수 있는 관련 공개 문서를 찾아줘.",
            "이 문서를 Agent context로 쓸 수 없는 이유를 알려줘.",
        ]

    suggestions: list[str] = []
    if page_kind == "workflow_status" or "/workflows/" in url or "trace_id=" in url:
        event_count = int(context.get("event_count") or 0)
        action_count = int(context.get("action_count") or 0)
        handoff_count = int(context.get("manual_handoff_count") or 0)
        workflow_key = str(context.get("workflow_key") or "workflow")
        if event_count or action_count:
            suggestions.append(f"이 {workflow_key} trace의 이벤트 {event_count}개와 업무 요청 {action_count}개를 SOP 단계 기준으로 요약해줘.")
        if handoff_count:
            suggestions.append(f"남은 수동 조치 {handoff_count}건을 일반 업무 관점으로 정리해줘.")
        suggestions.extend([
            "승인 대기 또는 조치 필요 업무 요청을 먼저 알려줘.",
            "생성된 BoI와 원본 실행 기록 링크를 묶어서 보여줘.",
        ])
    elif page_kind == "action_raw" or "/actions/raw/" in url:
        action_key = str(context.get("action_key") or "이 업무 요청")
        status = str(context.get("status") or "")
        suggestions.extend([
            f"{action_key} 실행 결과를 업무 관점으로 요약해줘.",
            f"{action_key}이 어떤 SOP/이벤트와 연결되는지 찾아줘.",
            "이 업무 요청 결과가 다음 업무 흐름 단계에 어떤 영향을 주는지 알려줘.",
        ])
        if status:
            suggestions.append(f"현재 상태 `{status}`에서 내가 할 일을 알려줘.")
    elif page_kind == "event_type" or "/event-types/" in url:
        event_type = str(context.get("event_type") or "이 이벤트 유형")
        stage = str(context.get("workflow_stage") or "")
        recommended_actions = context.get("recommended_actions") if isinstance(context.get("recommended_actions"), list) else []
        suggestions.extend([
            f"{event_type}가 발생하면 어떤 SOP 단계와 업무 요청이 이어지는지 알려줘.",
            f"{event_type} 최근 실행 trace를 찾아줘.",
        ])
        if stage:
            suggestions.append(f"`{stage}` 단계에서 사람이 확인해야 할 항목을 정리해줘.")
        if recommended_actions:
            suggestions.append(f"{event_type}의 권장 업무 요청 {len(recommended_actions)}개가 충분한지 점검해줘.")
    elif page_kind == "events" or url.startswith("/events"):
        event_type = str(context.get("event_type") or "")
        trace_id = str(context.get("trace_id") or "")
        event_count = int(context.get("event_count") or 0)
        if trace_id:
            suggestions.append("이 trace의 실행 흐름과 다음 조치를 요약해줘.")
        if event_type:
            suggestions.append(f"{event_type} 이벤트 {event_count}건에서 반복 패턴을 찾아줘.")
            suggestions.append(f"{event_type}가 연결된 SOP와 업무 요청을 보여줘.")
        suggestions.extend([
            "최근 이벤트 중 내가 처리해야 할 업무 요청을 Inbox 기준으로 보여줘.",
            "Event Stream을 시간/trace 기준으로 좁혀볼 추천 필터를 알려줘.",
        ])
    elif page_kind == "doc" or title:
        doc_type = str(context.get("type") or "")
        boi_id = str(context.get("boi_id") or "")
        stage_count = int(context.get("stage_count") or 0)
        action_count = int(context.get("workflow_action_count") or 0)
        manual_count = int(context.get("workflow_manual_action_count") or 0)
        is_sop = doc_type == "boi/sop" or ":sop:" in boi_id or "/sop/" in url or bool(stage_count)
        subject = title or "현재 문서"
        if is_sop:
            suggestions.extend([
                f"{subject}를 Mermaid 프로세스 플로우로 보여줘.",
                f"{subject}의 이벤트, 업무 요청, 수동 조치 관계를 요약해줘.",
            ])
            if action_count or manual_count:
                suggestions.append(f"{subject}의 업무 요청 {action_count}개와 수동 조치 {manual_count}개 중 부족한 명세를 찾아줘.")
            else:
                suggestions.append(f"{subject}를 실행하려면 부족한 업무 요청 명세가 있는지 찾아줘.")
        else:
            suggestions.extend([
                f"{subject}와 연결된 SOP/이벤트/업무 요청을 찾아줘.",
                f"{subject}의 핵심과 관련 BoI를 요약해줘.",
                "이 내용을 팀 공유용 draft로 만들려면 무엇을 확인해야 해?",
            ])
    else:
        suggestions = [
            "SOP/Event/Action을 함께 검색해줘.",
            "내가 처리해야 할 Action이 있는지 확인해줘.",
            "BoI Wiki에서 업무 용어를 ontology search로 찾아줘.",
        ]
    return dedupe_suggestions(suggestions)


def suggestion_context_for_llm(page_context: dict[str, Any]) -> dict[str, Any]:
    access = page_context.get("access") if isinstance(page_context.get("access"), dict) else {}
    can_use_context = access.get("can_use_in_agent_context") is not False
    keys = (
        "page_kind",
        "title",
        "boi_id",
        "type",
        "visibility",
        "classification",
        "event_type",
        "workflow_key",
        "workflow_stage",
        "stage_count",
        "workflow_action_count",
        "workflow_manual_action_count",
        "event_count",
        "action_count",
        "manual_handoff_count",
        "status",
        "trace_id",
        "action_key",
    )
    context = {key: page_context.get(key) for key in keys if page_context.get(key) not in (None, "", [])}
    context["access"] = {
        "can_use_in_agent_context": access.get("can_use_in_agent_context", True),
        "can_cite": access.get("can_cite", True),
        "classification": access.get("classification") or page_context.get("classification") or "",
        "redactions": access.get("redactions") or [],
        "reasons": access.get("reasons") or [],
    }
    if can_use_context:
        for key in ("citations", "okf_refs", "links"):
            value = page_context.get(key)
            if value:
                context[key] = value[:8] if isinstance(value, list) else value
        excerpt = text_excerpt(str(page_context.get("body_excerpt") or page_context.get("summary") or ""), 800)
        if excerpt:
            context["safe_excerpt"] = excerpt
    return redact_sensitive(context)


def suggestions_prompt_for_request(req: BoiAgentSuggestionsRequest, employee_id: str, page_context: dict[str, Any]) -> str:
    return json.dumps(
        {
            "task": "boi_agent_page_suggestions_only",
            "language": "ko",
            "employee_id": employee_id,
            "current_url": req.current_url,
            "client_page_title": req.page_context.get("title") if isinstance(req.page_context, dict) else "",
            "resolved_page_context": suggestion_context_for_llm(page_context),
            "capabilities": [
                "현재 페이지 질의응답",
                "BoI/SOP/Event/Action ontology search",
                "SOP Mermaid diagram",
                "Event to Action workflow explanation",
                "Action Spec gap check",
                "Trace reasoning",
                "Inbox 업무 확인",
                "신규 이벤트 유형 초안 제안",
            ],
            "rules": [
                "Return JSON only.",
                "Produce 3 to 5 short Korean suggestions.",
                "Every suggestion must be useful for the current page context.",
                "Avoid internal technical words unless they are visible business terms on the page.",
                "If access.can_use_in_agent_context is false, ask about access policy or allowed related documents instead of document content.",
                "For mutating work, phrase it as draft/preview/approval, not immediate execution.",
            ],
            "output_shape": {"suggestions": ["질문 또는 요청 한 문장"]},
        },
        ensure_ascii=False,
    )


def parse_suggestions_payload(text: str) -> dict[str, Any] | None:
    parsed = parse_langflow_json_text(text)
    if isinstance(parsed, dict) and isinstance(parsed.get("suggestions"), list):
        return parsed
    decoder = json.JSONDecoder()
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        fenced = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", stripped, count=1).strip()
        fenced = re.sub(r"\s*```$", "", fenced, count=1).strip()
        if fenced and fenced != stripped:
            payload = parse_suggestions_payload(fenced)
            if payload:
                return payload
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("suggestions"), list):
            return payload
    return None


def normalize_llm_suggestions(payload: dict[str, Any]) -> list[str]:
    suggestions: list[str] = []
    for item in payload.get("suggestions") or []:
        text = re.sub(r"\s+", " ", str(item or "")).strip()
        text = text.strip("\"'` ")
        if not text:
            continue
        if len(text) > 120:
            text = text[:119].rstrip() + "…"
        suggestions.append(text)
    normalized = dedupe_suggestions(suggestions, limit=5)
    if len(normalized) < 3:
        raise BoiAgentSuggestionsUnavailable("LLM suggestion writer returned fewer than 3 suggestions")
    return normalized


def call_boi_agent_suggestions_llm(req: BoiAgentSuggestionsRequest, employee_id: str, page_context: dict[str, Any]) -> list[str]:
    if not BOI_AGENT_SUGGESTIONS_LLM_ENABLED:
        raise BoiAgentSuggestionsUnavailable("LLM suggestion writer is not configured")
    if not BOI_AGENT_SUGGESTIONS_BASE_URL or not BOI_AGENT_SUGGESTIONS_MODEL:
        raise BoiAgentSuggestionsUnavailable("LLM suggestion writer base URL/model is missing")
    url = BOI_AGENT_SUGGESTIONS_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if BOI_AGENT_SUGGESTIONS_API_KEY:
        headers["Authorization"] = f"Bearer {BOI_AGENT_SUGGESTIONS_API_KEY}"
    body = {
        "model": BOI_AGENT_SUGGESTIONS_MODEL,
        "temperature": 0.35,
        "max_tokens": BOI_AGENT_SUGGESTIONS_MAX_TOKENS,
        "response_format": {"type": "text"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise, page-aware suggestion buttons for BoI Agent. "
                    "Return only JSON and never answer the user's task."
                ),
            },
            {"role": "user", "content": suggestions_prompt_for_request(req, employee_id, page_context)},
        ],
    }
    try:
        with httpx.Client(timeout=BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise BoiAgentSuggestionsUnavailable(f"LLM suggestion writer call failed: {exc}") from exc
    parsed = None
    for text in iter_langflow_text_candidates(payload):
        candidate = parse_suggestions_payload(text)
        if candidate:
            parsed = candidate
            break
    if not parsed:
        raise BoiAgentSuggestionsUnavailable("LLM suggestion writer returned invalid JSON")
    return normalize_llm_suggestions(parsed)


def agent_link_for_item(item: dict[str, Any]) -> dict[str, str]:
    label = str(item.get("title") or item.get("term") or item.get("event_type") or item.get("action_key") or item.get("boi_id") or "")
    return {
        "label": label,
        "url": str(item.get("url") or ""),
        "kind": str(item.get("kind") or ""),
    }


class LangflowBoiAgentUnavailable(RuntimeError):
    """Raised when the trusted Langflow BoI Agent backend cannot answer."""


class BoiAgentRouterUnavailable(RuntimeError):
    """Raised when the required LLM router cannot produce a usable route."""


class BoiAgentStatusUnavailable(RuntimeError):
    """Raised when the required LLM status writer cannot produce progress text."""


class BoiAgentSuggestionsUnavailable(RuntimeError):
    """Raised when the required LLM suggestion writer cannot produce page-aware suggestions."""


ALLOWED_AGENT_ROUTES = {"fast", "deep", "inbox", "manual_handoff", "approval_required"}
ALLOWED_AGENT_INTENTS = {
    "search",
    "page_qa",
    "summarize",
    "diagram",
    "workflow_explain",
    "gap_check",
    "trace_reasoning",
    "inbox",
    "manual_complete",
    "approval",
    "event_publish",
    "action_invoke",
    "workflow_start",
    "event_type_draft",
}
DEEP_AGENT_INTENTS = {"diagram", "workflow_explain", "gap_check", "trace_reasoning"}


def normalize_agent_route(value: str) -> str:
    route = str(value or "").strip().lower().replace("-", "_")
    return route if route in ALLOWED_AGENT_ROUTES else "fast"


def require_llm_agent_route(value: Any) -> str:
    route = str(value or "").strip().lower().replace("-", "_")
    if route not in ALLOWED_AGENT_ROUTES:
        raise BoiAgentRouterUnavailable("LLM router returned invalid route")
    return route


def normalize_agent_intent(value: str, *, fallback: str = "search") -> str:
    intent = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "lookup": "search",
        "page_summary": "summarize",
        "summary": "summarize",
        "workflow_reasoning": "trace_reasoning",
        "reasoning": "trace_reasoning",
        "manual_handoff": "manual_complete",
        "approval_required": "approval",
        "publish_event": "event_publish",
        "event": "event_publish",
        "invoke_action": "action_invoke",
        "action": "action_invoke",
        "start_workflow": "workflow_start",
        "forced_fast": fallback,
        "forced_deep": fallback if fallback in DEEP_AGENT_INTENTS else "trace_reasoning",
    }
    intent = aliases.get(intent, intent)
    return intent if intent in ALLOWED_AGENT_INTENTS else fallback


def require_llm_agent_intent(value: Any) -> str:
    intent = normalize_agent_intent(str(value or ""), fallback="")
    if intent not in ALLOWED_AGENT_INTENTS:
        raise BoiAgentRouterUnavailable("LLM router returned invalid intent")
    return intent


def safety_route_override(question: str) -> str | None:
    q = str(question or "").lower()
    manual_action_terms = ("handoff 완료", "핸드오프 완료", "조치 완료", "완료 처리", "조치내용", "조치 내용", "완료 기록", "완료로 기록")
    approval_terms = ("승인", "approve", "실행해", "실행해줘", "invoke", "publish", "게시", "배포", "반영", "적용", "source_apply", "doc_body_apply")
    if any(term in q for term in manual_action_terms):
        return "manual_handoff"
    if any(term in q for term in approval_terms):
        return "approval_required"
    return None


def deterministic_agent_intent(question: str, current_url: str = "") -> str:
    q = str(question or "").lower()
    if any(term in q for term in ("내 action", "내 액션", "내 할 일", "할 일", "처리해야", "inbox", "대기", "남았", "담당")):
        return "inbox"
    if (
        any(term in q for term in ("event type", "event-type", "이벤트 타입", "이벤트 유형", "이벤트 정의", "신규 이벤트"))
        and any(term in q for term in ("초안", "만들", "생성", "정의", "추가", "draft", "create"))
    ):
        return "event_type_draft"
    if re.search(r"\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+\.v\d+\b", question) and any(term in q for term in ("이벤트 발행", "event 발행", "publish event", "이벤트를 발행", "이벤트 발생", "발행해", "발행해줘")):
        return "event_publish"
    if any(term in q for term in ("workflow 시작", "workflow 실행", "워크플로우 시작", "워크플로우 실행", "workflow start", "start workflow")):
        return "workflow_start"
    if re.search(r"\b[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){2,}\b", question) and any(term in q for term in ("action 실행", "액션 실행", "action 요청", "액션 요청", "invoke", "호출", "실행해", "실행해줘")):
        return "action_invoke"
    if safety := safety_route_override(q):
        return "manual_complete" if safety == "manual_handoff" else "approval"
    if any(term in q for term in ("mermaid", "머메이드", "flowchart", "다이어그램", "도식", "프로세스 플로우", "프로세스플로우", "그려", "그려줘")):
        return "diagram"
    if any(term in q for term in ("부족", "누락", "없는지", "없나", "gap", "갭", "action spec", "액션 spec", "명세", "완성도")):
        return "gap_check"
    if any(term in q for term in ("trace", "트레이스", "workflow status", "로그", "왜", "원인", "리스크", "시뮬레이션", "추론", "판단")):
        return "trace_reasoning"
    if any(term in q for term in ("찾", "검색", "링크", "목록", "어디", "보여줘")):
        return "search"
    if any(term in q for term in ("event", "이벤트", "action", "액션", "manual handoff", "handoff", "핸드오프", "관계", "흐름", "발생하면", "뭘 해야", "어떻게 해야", "이어지는")):
        return "workflow_explain"
    if any(term in q for term in ("요약", "정리", "summary", "summarize")):
        return "summarize"
    return "page_qa" if current_url else "search"


def route_for_agent_intent(intent: str) -> str:
    if intent in DEEP_AGENT_INTENTS:
        return "deep"
    if intent == "inbox":
        return "inbox"
    if intent == "manual_complete":
        return "manual_handoff"
    if intent == "approval":
        return "approval_required"
    if intent in {"event_publish", "action_invoke", "workflow_start"}:
        return "approval_required"
    if intent == "event_type_draft":
        return "approval_required"
    return "fast"


def rule_agent_route(req: BoiAgentChatRequest, reason: str = "rules") -> dict[str, Any]:
    q = str(req.question or "").lower()
    intent = normalize_agent_intent(req.intent, fallback=deterministic_agent_intent(q, req.current_url)) if req.intent else deterministic_agent_intent(q, req.current_url)
    route = route_for_agent_intent(intent)
    return {
        "route": route,
        "confidence": 0.78 if route == "fast" else 0.82,
        "intent": intent,
        "reason": reason,
        "requires_mutation": route in {"manual_handoff", "approval_required"},
        "requires_deep_reasoning": route == "deep",
        # Compatibility field for older clients. Deep answers are handled by the native agent by default.
        "requires_langflow": False,
        "router_backend": "rules",
    }


def router_prompt_for_request(req: BoiAgentChatRequest, employee_id: str) -> str:
    return json.dumps(
        {
            "task": "Route this BoI Agent request. Return JSON only.",
            "allowed_routes": sorted(ALLOWED_AGENT_ROUTES),
            "allowed_intents": sorted(ALLOWED_AGENT_INTENTS),
            "route_policy": {
                "fast": "search, page_qa, summarize only. Use current page context and ontology search.",
                "deep": "diagram, workflow_explain, gap_check, trace_reasoning, multi-hop reasoning, artifact generation",
                "inbox": "ask what actions/manual handoffs are pending for the employee",
                "manual_handoff": "request to complete or record a manual handoff",
                "approval_required": "request to approve, execute, publish, edit, or mutate shared/runtime state",
            },
            "intent_policy": {
                "search": "find documents, SOPs, actions, events, dictionary terms",
                "page_qa": "answer a question about the current page",
                "summarize": "summarize current page or search results",
                "diagram": "produce Mermaid or visual workflow artifacts",
                "workflow_explain": "explain Event -> SOP -> Action -> Manual Handoff -> BoI flow",
                "gap_check": "find missing Action Specs, Event Types, evidence, or workflow gaps",
                "trace_reasoning": "reason over trace/workflow/action evidence",
                "inbox": "show assigned work",
                "manual_complete": "complete a manual handoff",
                "approval": "approve, publish, invoke, edit, deploy, or mutate state",
                "event_publish": "publish a specific Event Type through Event Broker after confirmation",
                "action_invoke": "invoke a specific allow-listed Action Gateway action after confirmation",
                "workflow_start": "start a specific SOP workflow after confirmation",
                "event_type_draft": "create a draft proposal for a new Event Type, never directly apply it",
            },
            "employee_id": employee_id,
            "question": req.question,
            "current_url": req.current_url,
            "page_title": req.page_context.get("title") if isinstance(req.page_context, dict) else "",
            "selected_text": req.selected_text[:1000],
            "conversation_tail": req.conversation[-4:],
            "required_json_schema": {
                "route": "fast|deep|inbox|manual_handoff|approval_required",
                "confidence": "0.0-1.0",
                "intent": "search|page_qa|summarize|diagram|workflow_explain|gap_check|trace_reasoning|inbox|manual_complete|approval|event_publish|action_invoke|workflow_start|event_type_draft",
                "reason": "short Korean or English reason",
                "requires_mutation": "boolean",
                "requires_deep_reasoning": "boolean",
            },
        },
        ensure_ascii=False,
    )


def parse_router_payload(text: str) -> dict[str, Any] | None:
    parsed = parse_langflow_json_text(text)
    if parsed is not None and parsed.get("route"):
        return parsed
    decoder = json.JSONDecoder()
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        fenced = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", stripped, count=1).strip()
        fenced = re.sub(r"\s*```$", "", fenced, count=1).strip()
        if fenced and fenced != stripped:
            payload = parse_router_payload(fenced)
            if payload and payload.get("route"):
                return payload
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("route"):
            return payload
    return None


def parse_agent_compose_payload(text: str) -> dict[str, Any] | None:
    parsed = parse_langflow_json_text(text)
    if isinstance(parsed, dict):
        answer = str(parsed.get("answer_markdown") or parsed.get("answer") or parsed.get("message") or parsed.get("final_answer") or "").strip()
        if answer:
            parsed["answer_markdown"] = answer
            return parsed
    decoder = json.JSONDecoder()
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        fenced = re.sub(r"^```[A-Za-z0-9_-]*\s*", "", stripped, count=1).strip()
        fenced = re.sub(r"\s*```$", "", fenced, count=1).strip()
        if fenced and fenced != stripped:
            payload = parse_agent_compose_payload(fenced)
            if payload:
                return payload
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            answer = str(payload.get("answer_markdown") or payload.get("answer") or payload.get("message") or payload.get("final_answer") or "").strip()
            if answer:
                payload["answer_markdown"] = answer
                return payload
    return None


def looks_like_repetitive_generation(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip().lower()
    if not normalized:
        return False
    if re.search(r"\b(de la vie|de facto)\b", normalized):
        return True
    if re.search(r"(.{3,40})(?:\\s*[-·,/]?\\s*\\1){4,}", normalized):
        return True
    tokens = re.findall(r"[a-z0-9가-힣一-龥]+", normalized)
    if len(tokens) < 30:
        return False
    for size in (1, 2, 3):
        grams = [" ".join(tokens[index : index + size]) for index in range(0, len(tokens) - size + 1)]
        if not grams:
            continue
        most_common = max(grams.count(item) for item in set(grams))
        if most_common >= max(6, int(len(grams) * 0.14)):
            return True
    return False


DISALLOWED_AGENT_SCRIPT_RE = re.compile(
    r"[\u0370-\u03ff\u0400-\u052f\u0590-\u05ff\u0600-\u06ff\u0750-\u077f\u4e00-\u9fff]"
)
ALLOWED_AGENT_LATIN_WORDS = {
    "acl",
    "action",
    "agent",
    "ai",
    "api",
    "boi",
    "codex",
    "event",
    "github",
    "hbm",
    "inbox",
    "json",
    "kafka",
    "langflow",
    "manual",
    "mcp",
    "mermaid",
    "nas",
    "native",
    "okf",
    "rbac",
    "sop",
    "sso",
    "trace",
    "url",
    "wiki",
    "workflow",
}


def agent_quality_text_without_code_and_urls(text: str) -> str:
    stripped = re.sub(r"```.*?```", " ", str(text or ""), flags=re.DOTALL)
    stripped = re.sub(r"`[^`]*`", " ", stripped)
    stripped = re.sub(r"\]\([^)]+\)", "]", stripped)
    stripped = re.sub(r"https?://\S+", " ", stripped)
    return stripped


def contains_disallowed_agent_script(text: str) -> bool:
    return bool(DISALLOWED_AGENT_SCRIPT_RE.search(agent_quality_text_without_code_and_urls(text)))


def looks_like_english_dominant_agent_line(text: str) -> bool:
    for raw_line in str(text or "").splitlines():
        line = re.sub(r"^[#>*\-\s0-9.]+", "", raw_line).strip()
        if not line:
            continue
        line = agent_quality_text_without_code_and_urls(line)
        if re.search(r"[가-힣]", line):
            continue
        latin_words = re.findall(r"\b[A-Za-z][A-Za-z-]{2,}\b", line)
        if len(latin_words) < 3:
            continue
        unexpected = [
            word
            for word in latin_words
            if word.lower().strip("-") not in ALLOWED_AGENT_LATIN_WORDS
        ]
        if unexpected:
            return True
    return False


def invalid_agent_composer_answer_reason(answer: str) -> str:
    text = str(answer or "").strip()
    if not text:
        return "empty_answer"
    if looks_like_repetitive_generation(text):
        return "degenerate_repetition"
    lowered = text.lower()
    prompt_echo_markers = (
        "user wants",
        "target audience",
        "constraint:",
        "format: github-flavored markdown",
        "structured_draft",
        "body_excerpt",
        "required_json_schema",
        "supplied evidence",
        "do not invent private data",
        "return only one json object",
    )
    if any(marker in lowered for marker in prompt_echo_markers):
        return "prompt_echo"
    if re.match(r"^\s*[-*]\s+user\s+wants\b", text, flags=re.IGNORECASE):
        return "prompt_echo"
    if contains_disallowed_agent_script(text):
        return "non_korean_script"
    if looks_like_english_dominant_agent_line(text):
        return "english_dominant_line"
    if text.startswith("{") or text.startswith("[") or text.startswith("```json"):
        return "unparsed_json"
    if text.startswith("chatcmpl-"):
        return "openai_response_metadata"
    return ""


def boi_agent_composer_request_body(payload: dict[str, Any], employee_id: str, *, repair: dict[str, Any] | None = None) -> dict[str, Any]:
    user_payload = {
        "employee_id": employee_id,
        **(payload if isinstance(payload, dict) else {}),
    }
    if repair:
        user_payload["quality_repair"] = repair
    system_content = (
        "You are the final answer composer for BoI Wiki Agent. "
        "Return only one JSON object with answer_markdown and suggested_questions. "
        "answer_markdown must be the final user-facing Korean Markdown answer, under 1200 Korean characters. "
        "Use 3-7 concise Korean bullets or short sections. Do not write Markdown tables; table artifacts are rendered separately. "
        "Write in Korean sentences. English is allowed only for official product names, action keys, event types, APIs, URLs, or code identifiers. "
        "Do not use Chinese characters, Arabic, Cyrillic, Greek, French, German, Latin filler, decorative translations, or English-only section titles. "
        "Do not repeat any word or phrase more than twice. "
        "Never echo, summarize, or restate the prompt, request fields, JSON schema, "
        "structured_draft label, body_excerpt label, or system instructions. "
        "Use only supplied evidence. Do not invent private data, links, actions, or approvals. "
        "The service rejects malformed mixed-language answers instead of falling back."
    )
    if repair:
        system_content += (
            " This is a quality repair attempt. Rewrite from the supplied structured_draft and evidence only. "
            "Do not preserve the rejected wording. Start with a Korean heading such as '## 답변'."
        )
    return {
        "model": BOI_AGENT_COMPOSER_MODEL,
        "temperature": 0,
        "frequency_penalty": 0.6,
        "max_tokens": BOI_AGENT_COMPOSER_MAX_TOKENS,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "boi_agent_final_answer",
                "schema": {
                    "type": "object",
                    "properties": {
                        "answer_markdown": {"type": "string"},
                        "suggested_questions": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["answer_markdown"],
                },
            },
        },
        "messages": [
            {"role": "system", "content": system_content},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
    }


def parse_boi_agent_composer_response(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    invalid_reasons: list[str] = []
    for text in iter_langflow_text_candidates(raw):
        candidate = parse_agent_compose_payload(text)
        if candidate:
            answer = str(candidate.get("answer_markdown") or "").strip()
            invalid_reason = invalid_agent_composer_answer_reason(answer)
            if invalid_reason:
                invalid_reasons.append(invalid_reason)
                continue
            suggestions = candidate.get("suggested_questions")
            return {
                "answer_markdown": answer,
                "suggested_questions": suggestions if isinstance(suggestions, list) else [],
            }, invalid_reasons
    return None, invalid_reasons or ["no_valid_json_answer"]


def call_boi_agent_composer_llm(payload: dict[str, Any], employee_id: str) -> dict[str, Any]:
    if not BOI_AGENT_COMPOSER_LLM_ENABLED:
        raise NativeAgentRuntimeUnavailable("LLM answer composer is not configured")
    if not BOI_AGENT_COMPOSER_BASE_URL or not BOI_AGENT_COMPOSER_MODEL:
        raise NativeAgentRuntimeUnavailable("LLM answer composer base URL/model is missing")
    url = BOI_AGENT_COMPOSER_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if BOI_AGENT_COMPOSER_API_KEY:
        headers["Authorization"] = f"Bearer {BOI_AGENT_COMPOSER_API_KEY}"
    invalid_reasons: list[str] = []
    repair_payload: dict[str, Any] | None = None
    for attempt in range(2):
        body = boi_agent_composer_request_body(payload, employee_id, repair=repair_payload)
        try:
            with httpx.Client(timeout=BOI_AGENT_COMPOSER_TIMEOUT_SECONDS) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                raw = response.json()
        except Exception as exc:
            raise NativeAgentRuntimeUnavailable(f"LLM answer composer call failed: {exc}") from exc
        parsed, reasons = parse_boi_agent_composer_response(raw)
        invalid_reasons.extend(reasons)
        if parsed:
            if attempt > 0:
                parsed["quality_repair_used"] = True
            return parsed
        repair_payload = {
            "previous_rejection_reasons": sorted(set(invalid_reasons)),
            "required_fix": "Return a Korean-only user-facing Markdown answer. Keep official BoI/SOP/Event/Action/API/MCP identifiers only when needed.",
        }
    reason_summary = ", ".join(sorted(set(invalid_reasons))) or "unknown"
    raise NativeAgentRuntimeUnavailable(f"LLM answer composer returned invalid final answer: {reason_summary}")


REQUIRED_AGENT_STATUS_STAGES = ("page_context", "intent", "retrieval", "tool_loop", "compose", "answer_stream", "waiting")


def status_prompt_for_request(req: BoiAgentChatRequest, employee_id: str) -> str:
    return json.dumps(
        {
            "task": "Write BoI Agent progress status lines. Return JSON only.",
            "language": "ko",
            "style": {
                "tone": "일반 구성원이 이해하기 쉬운 업무 문장",
                "length": "각 message는 18~70자 한 문장",
                "avoid": ["dry-run", "invoke", "router", "fallback", "stub", "LLM", "LangGraph", "stack trace"],
                "must_be_specific_to_request": True,
            },
            "required_stages": list(REQUIRED_AGENT_STATUS_STAGES),
            "stage_meaning": {
                "page_context": "현재 페이지, 사번, 접근 권한을 확인하는 단계",
                "intent": "질문 의도와 필요한 산출물을 판단하는 단계",
                "retrieval": "BoI Wiki, SOP, Event, Action, Dictionary, runtime evidence를 찾는 단계",
                "tool_loop": "필요한 근거를 여러 번 조회하고 빈틈을 점검하는 단계",
                "compose": "답변, 표, Mermaid, 링크, citation을 정리하는 단계",
                "answer_stream": "완성된 답변을 사용자에게 보여주는 단계",
                "waiting": "작업이 길어질 때 계속 처리 중임을 알리는 단계",
            },
            "employee_id": employee_id,
            "question": req.question,
            "current_url": req.current_url,
            "page_title": req.page_context.get("title") if isinstance(req.page_context, dict) else "",
            "selected_text_excerpt": text_excerpt(req.selected_text, 500),
            "conversation_tail": req.conversation[-3:],
            "required_json_schema": {
                "statuses": [
                    {
                        "stage": "one of required_stages",
                        "message": "Korean one-line progress text",
                    }
                ]
            },
        },
        ensure_ascii=False,
    )


def parse_status_payload(text: str) -> dict[str, Any] | None:
    parsed = parse_langflow_json_text(text)
    if isinstance(parsed, dict) and isinstance(parsed.get("statuses"), list):
        return parsed
    decoder = json.JSONDecoder()
    stripped = text.strip()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("statuses"), list):
            return payload
    return None


def parse_stream_plan_payload(text: str) -> dict[str, Any] | None:
    parsed = parse_langflow_json_text(text)
    if isinstance(parsed, dict) and parsed.get("route") and isinstance(parsed.get("statuses"), list):
        return parsed
    decoder = json.JSONDecoder()
    stripped = text.strip()
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            payload, _end = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("route") and isinstance(payload.get("statuses"), list):
            return payload
    return None


def is_usable_llm_status_message(message: str) -> bool:
    text = str(message or "").strip()
    if not text:
        return False
    if len(text) > 90:
        return False
    if contains_disallowed_agent_script(text):
        return False
    # Drop common local-LLM degeneration patterns instead of showing broken
    # progress text as if it were healthy. This is validation, not a canned
    # replacement: if every generated line is rejected, the Agent returns a
    # status_generation_failed error.
    if re.search(r"[A-Za-z]{8,}", text):
        return False
    if re.search(r"[가-힣]-[가-힣]", text):
        return False
    if re.search(r"([A-Za-z]{3,})(?:[-_\s]+\1){1,}", text, flags=re.IGNORECASE):
        return False
    if re.search(r"([가-힣]{2,})(?:을|를|은|는|이|가|의)?[-_\s·/]+\1", text):
        return False
    if re.search(r"([가-힣]{2,})(?:[-_\s·/]*\1){1,}", text):
        return False
    if re.search(r"([가-힣])\1{2,}", text):
        return False
    return True


def normalize_llm_status_steps(payload: dict[str, Any]) -> list[dict[str, str]]:
    seen: dict[str, str] = {}
    seen_messages: set[str] = set()
    for item in payload.get("statuses") or []:
        if not isinstance(item, dict):
            continue
        stage = str(item.get("stage") or "").strip()
        message = re.sub(r"\s+", " ", str(item.get("message") or "")).strip()
        if stage not in REQUIRED_AGENT_STATUS_STAGES or not message:
            continue
        if not is_usable_llm_status_message(message):
            continue
        if len(message) > 90:
            message = message[:89].rstrip() + "…"
        if message in seen_messages:
            continue
        seen_messages.add(message)
        seen.setdefault(stage, message)
    if not seen:
        raise BoiAgentStatusUnavailable("LLM status writer returned no usable status message")
    ordered_stages = [stage for stage in REQUIRED_AGENT_STATUS_STAGES if stage in seen]
    return [{"stage": stage, "message": seen[stage], "source": "llm_status"} for stage in ordered_stages]


def normalize_llm_route_payload(payload: dict[str, Any], req: BoiAgentChatRequest) -> dict[str, Any]:
    route = require_llm_agent_route(payload.get("route"))
    try:
        confidence = float(payload.get("confidence") or 0)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence < BOI_AGENT_ROUTER_CONFIDENCE_THRESHOLD:
        raise BoiAgentRouterUnavailable("LLM router confidence is below threshold")
    intent = require_llm_agent_intent(payload.get("intent"))
    if intent in DEEP_AGENT_INTENTS and route != "deep":
        route = "deep"
    elif intent == "inbox":
        route = "inbox"
    elif intent == "manual_complete":
        route = "manual_handoff"
    elif intent == "approval":
        route = "approval_required"
    elif intent == "event_type_draft":
        route = "approval_required"
    return {
        "route": route,
        "confidence": confidence,
        "intent": intent,
        "reason": str(payload.get("reason") or "llm_router"),
        "requires_mutation": bool(payload.get("requires_mutation") or route in {"manual_handoff", "approval_required"}),
        "requires_deep_reasoning": bool(payload.get("requires_deep_reasoning") or payload.get("requires_langflow") or route == "deep"),
        # Compatibility field for older clients. Deep answers are handled by native agent unless backend=langflow.
        "requires_langflow": False,
        "router_backend": "llm",
    }


def call_boi_agent_status_llm(req: BoiAgentChatRequest, employee_id: str) -> list[dict[str, str]]:
    if not BOI_AGENT_STATUS_REQUIRED:
        raise BoiAgentStatusUnavailable("LLM status writer is disabled by configuration")
    if not BOI_AGENT_STATUS_LLM_ENABLED:
        raise BoiAgentStatusUnavailable("LLM status writer is not configured")
    if not BOI_AGENT_STATUS_BASE_URL or not BOI_AGENT_STATUS_MODEL:
        raise BoiAgentStatusUnavailable("LLM status writer base URL/model is missing")
    url = BOI_AGENT_STATUS_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if BOI_AGENT_STATUS_API_KEY:
        headers["Authorization"] = f"Bearer {BOI_AGENT_STATUS_API_KEY}"
    body = {
        "model": BOI_AGENT_STATUS_MODEL,
        "temperature": 0.2,
        "max_tokens": BOI_AGENT_STATUS_MAX_TOKENS,
        "response_format": {"type": "text"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write concise progress status lines for BoI Agent. "
                    "Return only JSON. Do not answer the user's question."
                ),
            },
            {"role": "user", "content": status_prompt_for_request(req, employee_id)},
        ],
    }
    try:
        with httpx.Client(timeout=BOI_AGENT_STATUS_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise BoiAgentStatusUnavailable(f"LLM status writer call failed: {exc}") from exc
    parsed = None
    for text in iter_langflow_text_candidates(payload):
        candidate = parse_status_payload(text)
        if candidate:
            parsed = candidate
            break
    if not parsed:
        raise BoiAgentStatusUnavailable("LLM status writer returned invalid JSON")
    return normalize_llm_status_steps(parsed)


def stream_plan_prompt_for_request(req: BoiAgentChatRequest, employee_id: str) -> str:
    payload: dict[str, Any] = {
        "task": "route_and_status_plan_only",
        "lang": "ko",
        "employee_id": employee_id,
        "question": req.question,
        "url": req.current_url,
        "title": req.page_context.get("title") if isinstance(req.page_context, dict) else "",
        "routes": "fast|deep|inbox|manual_handoff|approval_required",
        "intents": "|".join(sorted(ALLOWED_AGENT_INTENTS)),
        "stages": "|".join(REQUIRED_AGENT_STATUS_STAGES),
        "must": [
            "JSON only",
            "No markdown",
            "Do not answer the user",
            "statuses has exactly 3 distinct Korean nontechnical messages",
            "Use three different stages: early context check, evidence/tool work, answer composition",
            "Do not include a reason field",
            "Do not repeat the same sentence or phrase",
            "Avoid broken hyphenated Korean such as 의-목",
        ],
        "output_shape": {
            "route": "route",
            "confidence": 0.0,
            "intent": "intent",
            "requires_mutation": False,
            "requires_deep_reasoning": False,
            "statuses": [{"stage": "stage", "message": "18-70 chars"}],
        },
    }
    selected = text_excerpt(req.selected_text, 220)
    if selected:
        payload["selected"] = selected
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def call_boi_agent_stream_plan_llm(req: BoiAgentChatRequest, employee_id: str) -> dict[str, Any]:
    if not BOI_AGENT_STATUS_REQUIRED:
        raise BoiAgentStatusUnavailable("LLM status writer is disabled by configuration")
    if not BOI_AGENT_STATUS_LLM_ENABLED:
        raise BoiAgentStatusUnavailable("LLM status writer is not configured")
    if not BOI_AGENT_STATUS_BASE_URL or not BOI_AGENT_STATUS_MODEL:
        raise BoiAgentStatusUnavailable("LLM status writer base URL/model is missing")
    if BOI_AGENT_ROUTER_REQUIRED and (not BOI_AGENT_ROUTER_LLM_ENABLED or BOI_AGENT_ROUTER_MODE != "llm_first"):
        raise BoiAgentRouterUnavailable("LLM router is not configured")
    url = BOI_AGENT_STATUS_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if BOI_AGENT_STATUS_API_KEY:
        headers["Authorization"] = f"Bearer {BOI_AGENT_STATUS_API_KEY}"

    stream_plan_response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "boi_agent_stream_plan",
            "schema": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "enum": sorted(ALLOWED_AGENT_ROUTES)},
                    "confidence": {"type": "number"},
                    "intent": {"type": "string", "enum": sorted(ALLOWED_AGENT_INTENTS)},
                    "requires_mutation": {"type": "boolean"},
                    "requires_deep_reasoning": {"type": "boolean"},
                    "statuses": {
                        "type": "array",
                        "minItems": 3,
                        "maxItems": 3,
                        "items": {
                            "type": "object",
                            "properties": {
                                "stage": {"type": "string", "enum": list(REQUIRED_AGENT_STATUS_STAGES)},
                                "message": {"type": "string", "maxLength": 90},
                            },
                            "required": ["stage", "message"],
                        },
                    },
                },
                "required": [
                    "route",
                    "confidence",
                    "intent",
                    "requires_mutation",
                    "requires_deep_reasoning",
                    "statuses",
                ],
            },
        },
    }

    def post_stream_plan(messages: list[dict[str, str]]) -> dict[str, Any]:
        body = {
            "model": BOI_AGENT_STATUS_MODEL,
            "temperature": 0,
            "frequency_penalty": 0.6,
            "max_tokens": max(BOI_AGENT_STATUS_MAX_TOKENS, BOI_AGENT_ROUTER_MAX_TOKENS),
            "response_format": stream_plan_response_format,
            "messages": messages,
        }
        try:
            with httpx.Client(timeout=max(BOI_AGENT_STATUS_TIMEOUT_SECONDS, BOI_AGENT_ROUTER_TIMEOUT_SECONDS)) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            raise BoiAgentStatusUnavailable(f"LLM stream plan call failed: {exc}") from exc

    def parse_stream_plan_response(payload: dict[str, Any]) -> dict[str, Any]:
        for text in iter_langflow_text_candidates(payload):
            candidate = parse_stream_plan_payload(text)
            if candidate:
                return candidate
        raise BoiAgentStatusUnavailable("LLM stream plan returned invalid JSON")

    initial_messages = [
            {
                "role": "system",
                "content": (
                    "You plan BoI Agent streaming work. Return one compact JSON object with "
                    "both routing fields and a complete progress status sequence. "
                    "Do not answer the user."
                ),
            },
            {"role": "user", "content": stream_plan_prompt_for_request(req, employee_id)},
    ]
    parsed = parse_stream_plan_response(post_stream_plan(initial_messages))
    status_steps = normalize_llm_status_steps(parsed)
    route = normalize_llm_route_payload(parsed, req)
    return {"status_steps": status_steps, "route": apply_agent_route_overrides(req, route)}


def router_llm_backoff_remaining() -> float:
    return max(0.0, _BOI_AGENT_ROUTER_BACKOFF_UNTIL - time.monotonic())


def call_boi_agent_router_llm(req: BoiAgentChatRequest, employee_id: str) -> dict[str, Any]:
    global _BOI_AGENT_ROUTER_BACKOFF_UNTIL, _BOI_AGENT_ROUTER_BACKOFF_REASON
    if not BOI_AGENT_ROUTER_LLM_ENABLED or BOI_AGENT_ROUTER_MODE != "llm_first":
        raise BoiAgentRouterUnavailable("LLM router is not configured")
    if not BOI_AGENT_ROUTER_BASE_URL or not BOI_AGENT_ROUTER_MODEL:
        raise BoiAgentRouterUnavailable("LLM router base URL/model is missing")
    backoff_remaining = router_llm_backoff_remaining()
    if backoff_remaining > 0:
        raise BoiAgentRouterUnavailable(
            f"LLM router backoff active for {backoff_remaining:.1f}s after {_BOI_AGENT_ROUTER_BACKOFF_REASON or 'previous failure'}"
        )
    url = BOI_AGENT_ROUTER_BASE_URL.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if BOI_AGENT_ROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {BOI_AGENT_ROUTER_API_KEY}"
    body = {
        "model": BOI_AGENT_ROUTER_MODEL,
        "temperature": 0,
        "max_tokens": BOI_AGENT_ROUTER_MAX_TOKENS,
        # Some OpenAI-compatible runtimes used for local Gemma serving reject
        # OpenAI's older json_object mode and only accept text/json_schema.
        # We request text and keep strict JSON extraction in parse_router_payload.
        "response_format": {"type": "text"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a routing classifier for BoI Wiki Agent. "
                    "Return only one compact JSON object. Do not answer the user."
                ),
            },
            {"role": "user", "content": router_prompt_for_request(req, employee_id)},
        ],
    }
    try:
        with httpx.Client(timeout=BOI_AGENT_ROUTER_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=body)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        if BOI_AGENT_ROUTER_FAILURE_BACKOFF_SECONDS > 0:
            _BOI_AGENT_ROUTER_BACKOFF_UNTIL = time.monotonic() + BOI_AGENT_ROUTER_FAILURE_BACKOFF_SECONDS
            _BOI_AGENT_ROUTER_BACKOFF_REASON = type(exc).__name__
        raise BoiAgentRouterUnavailable(f"LLM router call failed: {exc}") from exc
    _BOI_AGENT_ROUTER_BACKOFF_UNTIL = 0.0
    _BOI_AGENT_ROUTER_BACKOFF_REASON = ""
    parsed = None
    for text in iter_langflow_text_candidates(payload):
        candidate = parse_router_payload(text)
        if candidate and candidate.get("route"):
            parsed = candidate
            break
    if not parsed:
        raise BoiAgentRouterUnavailable("LLM router returned invalid JSON")
    return normalize_llm_route_payload(parsed, req)


def apply_agent_route_overrides(req: BoiAgentChatRequest, route: dict[str, Any]) -> dict[str, Any]:
    deterministic_intent = deterministic_agent_intent(req.question, req.current_url)
    route["intent"] = normalize_agent_intent(str(route.get("intent") or ""), fallback=deterministic_intent)
    # Rules are the safety net for obvious artifact/reasoning requests even when the LLM router says fast.
    if deterministic_intent in DEEP_AGENT_INTENTS and (route.get("route") != "deep" or route.get("intent") != deterministic_intent):
        route.update(
            {
                "route": "deep",
                "intent": deterministic_intent,
                "reason": f"intent override after {route.get('router_backend')}: {deterministic_intent}",
                "requires_deep_reasoning": True,
                "requires_langflow": False,
            }
        )
    if deterministic_intent in {"event_publish", "action_invoke", "workflow_start", "event_type_draft"}:
        route.update(
            {
                "route": "approval_required",
                "intent": deterministic_intent,
                "reason": f"mutation intent override after {route.get('router_backend')}: {deterministic_intent}",
                "requires_mutation": True,
                "requires_langflow": False,
            }
        )
    override = safety_route_override(req.question)
    if override and route.get("route") not in {"manual_handoff", "approval_required"}:
        route.update(
            {
                "route": override,
                "intent": "manual_complete" if override == "manual_handoff" else "approval",
                "reason": f"safety override after {route.get('router_backend')}",
                "requires_mutation": True,
                "requires_langflow": False,
            }
        )
    elif route.get("requires_mutation") and route.get("route") not in {"manual_handoff", "approval_required"}:
        route.update(
            {
                "route": "approval_required",
                "intent": "approval",
                "reason": f"mutation safety override after {route.get('router_backend')}",
                "requires_mutation": True,
                "requires_langflow": False,
            }
        )
    route["route"] = normalize_agent_route(str(route.get("route") or "fast"))
    route["intent"] = normalize_agent_intent(str(route.get("intent") or ""), fallback=deterministic_intent)
    return route


def route_boi_agent_request(req: BoiAgentChatRequest, employee_id: str) -> dict[str, Any]:
    deterministic_intent = deterministic_agent_intent(req.question, req.current_url)
    if req.mode == "fast":
        route = rule_agent_route(req, reason="mode=fast")
        intent = normalize_agent_intent(req.intent, fallback=deterministic_intent) if req.intent else deterministic_intent
        # Explicit fast mode can keep simple Q&A fast, but safety and mutation intents still override below.
        route.update({"route": "fast", "confidence": 1.0, "intent": intent})
    elif req.mode == "deep":
        route = rule_agent_route(req, reason="mode=deep")
        intent = normalize_agent_intent(req.intent, fallback=deterministic_intent)
        route.update({"route": "deep", "confidence": 1.0, "intent": intent, "requires_deep_reasoning": True, "requires_langflow": False})
    else:
        try:
            route = call_boi_agent_router_llm(req, employee_id)
        except BoiAgentRouterUnavailable:
            raise
    return apply_agent_route_overrides(req, route)


def text_excerpt(value: str, limit: int = 900) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[: limit - 1] + "…" if len(text) > limit else text


def resolve_agent_page_context(current_url: str, employee_id: str) -> dict[str, Any]:
    parsed = urlsplit(str(current_url or ""))
    path = parsed.path or "/"
    query = parse_qs(parsed.query)
    context: dict[str, Any] = {"page_kind": "unknown", "resolved": False, "current_url": current_url}
    if path.startswith("/docs/"):
        boi_id = unquote(path.removeprefix("/docs/"))
        doc = find_doc_by_id(boi_id, employee_id)
        if not doc:
            return {**context, "page_kind": "doc", "boi_id": boi_id, "context_resolution": "ontology_search_only"}
        metadata = doc.get("metadata") or {}
        access = access_policy_for_doc(doc, employee_id)
        source_event = metadata.get("source_event") if isinstance(metadata.get("source_event"), dict) else {}
        can_use_context = access.can_use_in_agent_context
        workflow = metadata.get("workflow") if isinstance(metadata.get("workflow"), dict) else {}
        workflow_stages = workflow.get("stages") if isinstance(workflow.get("stages"), list) and can_use_context else []
        workflow_event_types: list[str] = []
        workflow_actions: list[str] = []
        workflow_manual_actions: list[str] = []
        for stage in workflow_stages:
            if not isinstance(stage, dict):
                continue
            for event_type in stage.get("event_types") or ([stage.get("entry_event")] if stage.get("entry_event") else []):
                if event_type and str(event_type) not in workflow_event_types:
                    workflow_event_types.append(str(event_type))
            for action_key in stage.get("automated_actions") or []:
                if action_key and str(action_key) not in workflow_actions:
                    workflow_actions.append(str(action_key))
            for manual_key in stage.get("manual_actions") or []:
                if manual_key and str(manual_key) not in workflow_manual_actions:
                    workflow_manual_actions.append(str(manual_key))
        return {
            **context,
            "page_kind": "doc",
            "resolved": True,
            "title": metadata.get("title") or "",
            "description": metadata.get("description") or "" if can_use_context else "",
            "boi_id": metadata.get("boi_id") or boi_id,
            "type": metadata.get("type") or "",
            "visibility": metadata.get("visibility") or "",
            "status": metadata.get("status") or "",
            "event_type": metadata.get("event_type") or source_event.get("event_type") or "",
            "trace_id": source_event.get("trace") or "",
            "workflow_key": workflow.get("workflow_key") or "",
            "stage_count": len(workflow_stages),
            "workflow_event_types": workflow_event_types[:12],
            "workflow_action_count": len(workflow_actions),
            "workflow_manual_action_count": len(workflow_manual_actions),
            "body_excerpt": text_excerpt(str(doc.get("body") or "")) if can_use_context else "",
            "linked_items": lightweight_doc_link_items(doc, employee_id, limit=8) if can_use_context else [],
            "url": doc_url_for_ref(str(metadata.get("boi_id") or boi_id), employee_id) if access.can_cite else "",
            "access": access.to_dict(),
        }
    if path.startswith("/workflows/") and path.endswith("/status"):
        workflow_key = unquote(path.removeprefix("/workflows/").removesuffix("/status")).strip("/")
        trace_id = (query.get("trace_id") or [""])[0]
        if not workflow_key or not trace_id:
            return {**context, "page_kind": "workflow_status", "context_resolution": "ontology_search_only"}
        payload = workflow_status_payload(workflow_key, trace_id, employee_id, compact=True)
        return {
            **context,
            "page_kind": "workflow_status",
            "resolved": True,
            "workflow_key": workflow_key,
            "trace_id": trace_id,
            "sop_ref": payload.get("sop_ref") or "",
            "event_count": len(payload.get("events") or []),
            "action_count": len(payload.get("actions") or []),
            "manual_handoff_count": len(payload.get("manual_handoffs") or []),
            "generated_boi_count": len(payload.get("generated_docs") or []),
            "url": workflow_status_page_url_for_key(workflow_key, trace_id, employee_id),
        }
    if path == "/events" or path.startswith("/events"):
        event_type = (query.get("event_type") or [""])[0]
        trace_id = (query.get("trace_id") or [""])[0]
        event_id = (query.get("event_id") or [""])[0]
        rows = read_event_logs(limit=5, event_type=event_type or None, trace_id=trace_id or None, event_id=event_id or None)
        return {
            **context,
            "page_kind": "events",
            "resolved": True,
            "event_type": event_type,
            "trace_id": trace_id,
            "event_id": event_id,
            "event_count": len(rows),
            "events": [
                {
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                    "trace_id": row.get("trace_id"),
                    "status": row.get("status"),
                }
                for row in rows
            ],
        }
    if path.startswith("/actions/raw/"):
        log_ref = unquote(path.removeprefix("/actions/raw/"))
        row = find_action_log_row_by_ref(log_ref, employee_id)
        if not row:
            return {**context, "page_kind": "action_raw", "log_ref": log_ref, "context_resolution": "ontology_search_only"}
        readable = action_raw_readable_markdown(row)
        result_value = row.get("result") if isinstance(row.get("result"), dict) else {}
        return {
            **context,
            "page_kind": "action_raw",
            "resolved": True,
            "log_ref": log_ref,
            "action_key": row.get("action_key") or "",
            "status": row.get("status") or result_value.get("status") or "",
            "request_id": row.get("request_id") or "",
            "trace_id": row.get("trace_id") or "",
            "event_id": row.get("event_id") or "",
            "doc_ref": row.get("doc_ref") or "",
            "readable_excerpt": text_excerpt(str(readable.get("markdown") or ""), 700) if readable.get("available") else "",
            "url": action_raw_page_url(log_ref, employee_id),
        }
    if path.startswith("/event-types/"):
        event_type = unquote(path.removeprefix("/event-types/"))
        event_def = event_type_map().get(event_type)
        if not event_def:
            return {**context, "page_kind": "event_type", "event_type": event_type, "context_resolution": "ontology_search_only"}
        return {
            **context,
            "page_kind": "event_type",
            "resolved": True,
            "event_type": event_type,
            "title": event_def.get("name_ko") or event_type,
            "description": event_def.get("description") or "",
            "workflow_stage": event_def.get("workflow_stage") or "",
            "sop_ref": event_def.get("sop_ref") or "",
            "recommended_actions": event_def.get("recommended_actions") or [],
            "url": event_type_url(event_type, employee_id),
        }
    return {**context, "context_resolution": "ontology_search_only"}


def link_items_from_agent_context(page_context: dict[str, Any], employee_id: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    if page_context.get("url"):
        links.append({"label": str(page_context.get("title") or page_context.get("page_kind") or "현재 화면"), "url": str(page_context["url"]), "kind": "current_page"})
    if page_context.get("boi_id"):
        links.append({"label": str(page_context["boi_id"]), "url": doc_url_for_ref(str(page_context["boi_id"]), employee_id), "kind": "boi"})
    if page_context.get("sop_ref"):
        links.append({"label": str(page_context["sop_ref"]), "url": doc_url_for_ref(str(page_context["sop_ref"]), employee_id), "kind": "sop"})
    return [item for item in links if item.get("url")]


def agent_context_pack(req: BoiAgentChatRequest, employee_id: str, *, search_limit: int = 5) -> dict[str, Any]:
    page_context = resolve_agent_page_context(req.current_url, employee_id)
    ontology_seed: dict[str, Any] = {}
    intent = normalize_agent_intent(str(req.intent or ""), fallback=deterministic_agent_intent(req.question, req.current_url))
    page_first_intents = {"diagram", "workflow_explain", "gap_check", "page_qa", "summarize"}
    should_seed_search = bool(req.question.strip()) and not (page_context.get("resolved") and intent in page_first_intents)
    if should_seed_search:
        ontology_seed = ontology_search_payload(req.question, employee_id, scope="all", limit=search_limit, current_url=req.current_url, view="compact")
    return {
        "question": req.question,
        "selected_text_excerpt": text_excerpt(req.selected_text, 700) if req.selected_text else "",
        "current_url": req.current_url,
        "page_context": page_context,
        "ontology_search_seed": ontology_seed,
        "access_summary": page_context.get("access") or {"can_read": True, "can_use_in_agent_context": True},
    }


def native_agent_doc_tool(ref: str, employee_id: str) -> dict[str, Any] | None:
    doc = find_doc_by_id(ref, employee_id)
    if not doc:
        return None
    metadata = doc.get("metadata") or {}
    access = access_policy_for_doc(doc, employee_id)
    stable_ref = stable_doc_ref(doc)
    visible_metadata = metadata
    if not access.can_use_in_agent_context:
        visible_metadata = {
            "boi_id": metadata.get("boi_id"),
            "type": metadata.get("type"),
            "title": metadata.get("title"),
            "visibility": metadata.get("visibility"),
            "classification": access.classification,
            "status": metadata.get("status"),
        }
    return {
        "ok": True,
        "boi_id": metadata.get("boi_id") or stable_ref,
        "uri": doc.get("uri") or "",
        "title": metadata.get("title") or stable_ref,
        "description": metadata.get("description") or "",
        "metadata": visible_metadata,
        "body_excerpt": text_excerpt(str(doc.get("body") or ""), 1800) if access.can_use_in_agent_context else "",
        "url": doc_url_for_ref(stable_ref, employee_id) if access.can_cite else "",
        "access": access.to_dict(),
        "redacted_count": len(access.redactions),
    }


def native_agent_action_spec_tool(action_key: str, employee_id: str) -> dict[str, Any] | None:
    for action in load_action_catalog():
        if str(action.get("action_key") or "") != action_key:
            continue
        doc_ref = str(action.get("doc_ref") or "")
        return {
            "ok": True,
            "action_key": action_key,
            "item": action,
            "doc_ref": doc_ref,
            "doc": native_agent_doc_tool(doc_ref, employee_id) if doc_ref else None,
            "url": action_doc_url(action, employee_id),
        }
    return None


def native_agent_trace_context_tool(trace_id: str, employee_id: str) -> dict[str, Any]:
    event_rows = read_event_logs(limit=100, trace_id=trace_id) if trace_id else []
    action_rows = [
        row
        for row in cached_action_log_rows()
        if str(row.get("trace_id") or "") == trace_id
        if action_log_visible_to_employee(row, employee_id)
    ] if trace_id else []
    return {
        "ok": True,
        "trace_id": trace_id,
        "events": [
            {
                "event_id": row.get("event_id"),
                "event_type": row.get("event_type"),
                "status": row.get("status"),
                "url": events_url(employee_id, trace_id=trace_id, event_id=str(row.get("event_id") or "")),
            }
            for row in event_rows[:20]
        ],
        "actions": [
            {
                "request_id": row.get("request_id"),
                "action_key": row.get("action_key"),
                "status": row.get("status") or ((row.get("result") or {}).get("status") if isinstance(row.get("result"), dict) else ""),
                "raw_url": action_raw_page_url(str(row.get("_log_ref") or ""), employee_id) if row.get("_log_ref") else "",
            }
            for row in action_rows[:30]
        ],
    }


def native_agent_workflow_status_tool(workflow_key: str, trace_id: str, employee_id: str) -> dict[str, Any] | None:
    if not workflow_key or not trace_id:
        return None
    return workflow_status_payload(workflow_key, trace_id, employee_id, compact=True)


def native_agent_llm_json(employee_id: str, task: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """LLM helper used inside the native graph.

    The native agent owns routing. This adapter reuses the configured
    OpenAI-compatible router endpoint without making the API entrypoint call a
    separate pre-router first.
    """
    if task == "compose":
        return call_boi_agent_composer_llm(payload, employee_id)
    if task != "route":
        return None
    request_payload = payload.get("request") if isinstance(payload, dict) else {}
    if not isinstance(request_payload, dict):
        return None
    try:
        req = BoiAgentChatRequest(
            question=str(request_payload.get("question") or ""),
            mode=str(request_payload.get("mode") or "auto"),
            intent=str(request_payload.get("intent") or ""),
            current_url=str(request_payload.get("current_url") or ""),
            selected_text=str(request_payload.get("selected_text") or ""),
            page_context=request_payload.get("page_context") if isinstance(request_payload.get("page_context"), dict) else {},
            conversation=request_payload.get("conversation") if isinstance(request_payload.get("conversation"), list) else [],
            save_memory=bool(request_payload.get("save_memory", True)),
        )
        return call_boi_agent_router_llm(req, employee_id)
    except (BoiAgentRouterUnavailable, ValueError, TypeError):
        return None


def native_agent_memory_tool(query: str, employee_id: str, limit: int = 5) -> dict[str, Any]:
    items = agent_memory_items(employee_id, q=query, limit=limit)
    return {"ok": True, "count": len(items), "items": items}


def native_agent_tools(employee_id: str, current_url: str = "") -> NativeAgentTools:
    return NativeAgentTools(
        ontology_search=lambda query, scope="all", limit=8: ontology_search_payload(query, employee_id, scope=scope, limit=limit, current_url=current_url, view="compact"),
        boi_get=lambda ref: native_agent_doc_tool(ref, employee_id),
        event_type_lookup=lambda event_type: event_type_map().get(event_type),
        action_spec_lookup=lambda action_key: native_agent_action_spec_tool(action_key, employee_id),
        workflow_status=lambda workflow_key, trace_id: native_agent_workflow_status_tool(workflow_key, trace_id, employee_id),
        trace_context_lookup=lambda trace_id: native_agent_trace_context_tool(trace_id, employee_id),
        dictionary_resolve=lambda query: {"ok": True, **resolve_dictionary_query(query, employee_id, scope="all")},
        memory_recall=lambda query, limit=5: native_agent_memory_tool(query, employee_id, limit=limit),
        agent_inbox=lambda limit=10: agent_inbox_payload(employee_id, status="open", limit=limit),
        llm_json=lambda task, payload: native_agent_llm_json(employee_id, task, payload),
    )


def call_native_boi_agent(
    req: BoiAgentChatRequest,
    employee_id: str,
    route: dict[str, Any],
    started_at: float,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    context_pack = agent_context_pack(req, employee_id, search_limit=8)
    runtime = NativeBoiAgent(
        native_agent_tools(employee_id, req.current_url),
        NativeAgentConfig(
            max_tool_loops=BOI_AGENT_NATIVE_MAX_TOOL_LOOPS,
            tool_timeout_seconds=BOI_AGENT_NATIVE_TOOL_TIMEOUT_SECONDS,
            build_revision=BOI_BUILD_REVISION,
            llm_enabled=BOI_AGENT_ROUTER_LLM_ENABLED and BOI_AGENT_ROUTER_MODE == "llm_first",
            require_langgraph=BOI_AGENT_LANGGRAPH_REQUIRED,
            composer_enabled=BOI_AGENT_COMPOSER_LLM_ENABLED,
            composer_required=BOI_AGENT_COMPOSER_REQUIRED,
            progress_callback=progress_callback,
        ),
    )
    response = runtime.run(
        {
            "question": req.question,
            "mode": req.mode,
            "intent": req.intent,
            "current_url": req.current_url,
            "selected_text": req.selected_text,
            "page_context": req.page_context,
            "conversation": req.conversation[-12:],
            "save_memory": req.save_memory,
        },
        route,
        context_pack,
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    router_confidence = response.get("router_confidence")
    final_reference_redactions = sanitize_agent_final_references(response, employee_id)
    response.update(
        {
            "employee_id": employee_id,
            "latency_ms": latency_ms,
            "router_backend": response.get("router_backend") or route.get("router_backend"),
            "router_confidence": router_confidence if router_confidence is not None else route.get("confidence"),
            "access_summary": context_pack.get("access_summary") or {},
            "guardrails_applied": sorted(set([*(response.get("guardrails_applied") or []), "acl_policy", "classification", "mutation_confirmation", "agent_final_reference_acl"])),
            "redacted_count": max(int(response.get("redacted_count") or 0), count_agent_redactions(response), len((context_pack.get("access_summary") or {}).get("redactions") or [])) + final_reference_redactions,
        }
    )
    response.setdefault("context_summary", {})["latency_ms"] = latency_ms
    return response


AGENT_ALLOWED_APP_LINK_PREFIXES = (
    "docs",
    "events",
    "workflows",
    "actions",
    "event-types",
    "api",
    "permissions",
    "sops",
    "source",
)
AGENT_MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[(?P<label>[^\]]+)\]\((?P<href>[^)\s]+)(?:\s+\"[^\"]*\")?\)")
AGENT_HOSTLESS_APP_URL_RE = re.compile(
    r"\bhttps?:/{3,}(?P<rest>(?:docs|events|workflows|actions|event-types|api|permissions|sops|source)(?:[^\s<)]*)?)",
    flags=re.IGNORECASE,
)
AGENT_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_agent_control_chars(value: str) -> str:
    return AGENT_CONTROL_CHARS_RE.sub("", str(value or ""))


def normalize_agent_href(value: Any) -> str:
    text = strip_agent_control_chars(str(value or "")).strip()
    if not text:
        return ""
    match = re.match(r"^https?:/{3,}(?P<rest>.*)$", text, flags=re.IGNORECASE)
    if not match:
        return text
    rest = str(match.group("rest") or "").lstrip("/")
    if rest.startswith(AGENT_ALLOWED_APP_LINK_PREFIXES):
        return "/" + rest
    return text


def normalize_agent_text_references(value: str) -> str:
    text = strip_agent_control_chars(str(value or ""))

    def replace_markdown_link(match: re.Match[str]) -> str:
        return f"[{match.group('label')}]({normalize_agent_href(match.group('href'))})"

    text = AGENT_MARKDOWN_LINK_RE.sub(replace_markdown_link, text)
    return AGENT_HOSTLESS_APP_URL_RE.sub(lambda match: "/" + str(match.group("rest") or "").lstrip("/"), text)


def agent_doc_ref_from_reference(value: Any) -> str:
    text = normalize_agent_href(value)
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except Exception:
        parsed = None
    path = unquote(parsed.path if parsed else text)
    if path.startswith("/docs/"):
        return path.removeprefix("/docs/").strip()
    if text.startswith("boi:"):
        return text.split("#", 1)[0].split("?", 1)[0].strip()
    normalized_path = path.split("#", 1)[0].split("?", 1)[0].lstrip("/")
    if normalized_path.startswith(("public/", "team/", "private/")) and (
        normalized_path.endswith(".md") or find_doc_path_by_ref(normalized_path)
    ):
        return normalized_path
    return ""


def agent_reference_allowed(value: Any, employee_id: str) -> bool:
    ref = agent_doc_ref_from_reference(value)
    if not ref:
        return True
    doc = find_doc_by_id(ref, employee_id, include_inaccessible=True)
    if doc:
        access = access_policy_for_doc(doc, employee_id)
        return bool(access.can_read and access.can_cite)
    if ref.startswith("boi:private:"):
        parts = ref.split(":")
        return len(parts) >= 3 and parts[2] == employee_id
    return True


def redact_inaccessible_agent_text(value: str, employee_id: str) -> tuple[str, int]:
    redacted_count = 0

    def replace_markdown_link(match: re.Match[str]) -> str:
        nonlocal redacted_count
        label = match.group("label")
        href = match.group("href")
        if agent_reference_allowed(href, employee_id):
            return match.group(0)
        redacted_count += 1
        return f"{label} (권한 제한으로 숨김)"

    text = re.sub(
        r"\[(?P<label>[^\]]+)\]\((?P<href>[^)]+)\)",
        replace_markdown_link,
        str(value or ""),
    )

    def replace_private_ref(match: re.Match[str]) -> str:
        nonlocal redacted_count
        ref = match.group(0)
        if agent_reference_allowed(ref, employee_id):
            return ref
        redacted_count += 1
        return "[권한 제한]"

    text = re.sub(r"boi:private:[0-9]{6,8}:[A-Za-z0-9:_-]+", replace_private_ref, text)
    return text, redacted_count


def sanitize_agent_reference_value(value: Any, employee_id: str) -> tuple[Any, int]:
    if isinstance(value, dict):
        redacted_count = 0
        normalized_value = dict(value)
        for key in ("url", "href"):
            if key in normalized_value:
                normalized_value[key] = normalize_agent_href(normalized_value.get(key))
        for key in ("url", "href", "ref", "boi_id", "doc_ref"):
            if key in normalized_value and not agent_reference_allowed(normalized_value.get(key), employee_id):
                return None, 1
        sanitized: dict[str, Any] = {}
        for key, item in normalized_value.items():
            sanitized_item, item_redactions = sanitize_agent_reference_value(item, employee_id)
            redacted_count += item_redactions
            if sanitized_item is not None:
                sanitized[key] = sanitized_item
        return sanitized, redacted_count
    if isinstance(value, list):
        sanitized_items = []
        redacted_count = 0
        for item in value:
            sanitized_item, item_redactions = sanitize_agent_reference_value(item, employee_id)
            redacted_count += item_redactions
            if sanitized_item is not None:
                sanitized_items.append(sanitized_item)
        return sanitized_items, redacted_count
    if isinstance(value, str):
        return redact_inaccessible_agent_text(normalize_agent_text_references(value), employee_id)
    return value, 0


def sanitize_agent_final_references(response: dict[str, Any], employee_id: str) -> int:
    redacted_count = 0
    for key in ("answer_markdown", "display_markdown", "links", "citations", "suggested_questions", "artifacts", "tool_trace", "context_summary"):
        sanitized, count = sanitize_agent_reference_value(response.get(key), employee_id)
        redacted_count += count
        if sanitized is not None:
            response[key] = sanitized
        elif key in {"links", "citations", "artifacts", "suggested_questions", "tool_trace"}:
            response[key] = []
        else:
            response[key] = ""
    return redacted_count


def count_agent_redactions(response: dict[str, Any]) -> int:
    count = 0
    for item in response.get("tool_trace") or []:
        result = item.get("result") if isinstance(item, dict) else {}
        if isinstance(result, dict):
            count += int(result.get("redacted_count") or 0)
    access = response.get("access_summary") if isinstance(response.get("access_summary"), dict) else {}
    count += len(access.get("redactions") or []) if isinstance(access, dict) else 0
    return count


def mermaid_artifact_from_markdown(answer_markdown: str) -> dict[str, Any] | None:
    match = re.search(r"```mermaid\s*\n(?P<body>.*?)```", str(answer_markdown or ""), flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    source = match.group("body").strip()
    return {"type": "mermaid", "title": "Mermaid diagram", "source": source} if source else None


def normalize_agent_artifacts(value: Any, answer_markdown: str = "") -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for artifact_type, artifact_value in value.items():
            if artifact_type == "mermaid" and isinstance(artifact_value, str):
                artifacts.append({"type": "mermaid", "title": "Mermaid diagram", "source": artifact_value.strip()})
            elif artifact_type in {"gap_table", "workflow_summary", "task_cards"}:
                artifacts.append({"type": artifact_type, "data": artifact_value})
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("type"):
                artifacts.append(item)
    mermaid = mermaid_artifact_from_markdown(answer_markdown)
    if mermaid and not any(item.get("type") == "mermaid" and item.get("source") == mermaid["source"] for item in artifacts):
        artifacts.append(mermaid)
    return [artifact for artifact in artifacts if artifact.get("type")]


def execution_cards_from_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("type") != "confirmation_required":
            continue
        data = artifact.get("data") if isinstance(artifact.get("data"), dict) else {}
        operation = str(data.get("operation") or data.get("type") or "confirmation_required")
        cards.append(
            {
                "type": operation,
                "operation": operation,
                "title": str(data.get("title") or artifact.get("title") or "확인 필요"),
                "message": str(data.get("message") or ""),
                "primary_label": str(data.get("primary_label") or "확인 후 실행"),
                "payload": data.get("payload") or {},
                "requires_confirmation": True,
                "route": data.get("route"),
                "intent": data.get("intent"),
            }
        )
    return cards


def normalize_agent_mermaid_source(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def markdown_without_duplicate_mermaid_artifacts(answer_markdown: str, artifacts: list[dict[str, Any]]) -> str:
    """Return display Markdown with Mermaid fences removed when artifacts render them.

    Agent answers can include Mermaid both in answer_markdown and in structured
    artifacts. The Pet UI renders artifacts separately, so server-rendered
    answer_html should omit Mermaid fences whenever Mermaid artifacts exist.
    The original answer_markdown API field still preserves source transparency.
    """
    mermaid_sources = {
        normalize_agent_mermaid_source(str(artifact.get("source") or ""))
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("type") == "mermaid" and artifact.get("source")
    }
    if not mermaid_sources:
        return str(answer_markdown or "")

    def replace(match: re.Match[str]) -> str:
        return ""

    return re.sub(
        r"```[^\S\r\n]*mermaid[^\S\r\n]*(?:\r?\n)(?P<body>.*?)(?:\r?\n)?```",
        replace,
        str(answer_markdown or ""),
        flags=re.IGNORECASE | re.DOTALL,
    ).strip()


def enrich_agent_answer_html(response: dict[str, Any], employee_id: str) -> dict[str, Any]:
    answer_markdown = str(response.get("answer_markdown") or "")
    artifacts = normalize_agent_artifacts(response.get("artifacts"), answer_markdown)
    response["artifacts"] = artifacts
    if not isinstance(response.get("execution_cards"), list) or not response.get("execution_cards"):
        cards = execution_cards_from_artifacts(artifacts)
        if cards:
            response["execution_cards"] = cards
    display_markdown = markdown_without_duplicate_mermaid_artifacts(answer_markdown, artifacts)
    response["display_markdown"] = display_markdown
    response["answer_html"] = (
        str(render_markdown(display_markdown, employee_id=employee_id))
        if display_markdown.strip()
        else ""
    )
    return response


def agent_sse_event(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def iter_agent_answer_chunks(value: str, *, chunk_size: int = 180) -> list[str]:
    text = str(value or "")
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start + 120:
                end = boundary + 1
        chunks.append(text[start:end])
        start = end
    return chunks


def agent_stream_chunk_delay_seconds() -> float:
    try:
        return max(0.0, min(0.25, float(os.getenv("BOI_AGENT_STREAM_CHUNK_DELAY_SECONDS", "0.025"))))
    except (TypeError, ValueError):
        return 0.025


def agent_stream_status_steps(req: BoiAgentChatRequest, employee_id: str) -> list[dict[str, str]]:
    return call_boi_agent_status_llm(req, employee_id)


def agent_stream_plan(req: BoiAgentChatRequest, employee_id: str) -> dict[str, Any]:
    return call_boi_agent_stream_plan_llm(req, employee_id)


def agent_tool_progress_status(payload: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise BoiAgentStatusUnavailable("Agent progress payload is missing generated status message")
    return {
        "stage": str(payload.get("stage") or "tool_progress"),
        "message": message,
        "tool": str(payload.get("tool") or ""),
        "status": str(payload.get("status") or ""),
        "summary": str(payload.get("summary") or ""),
        "elapsed_ms": int(payload.get("elapsed_ms") or elapsed_ms),
    }


def lightweight_doc_link_items(doc: dict[str, Any], employee_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Extract current-document OKF links without building the full ontology index."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_path = Path(str(doc.get("path") or ""))
    if not source_path.exists():
        return items
    for match in MARKDOWN_LINK_RE.finditer(str(doc.get("body") or "")):
        href = match.group(1)
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#") or is_app_route_href(href):
            continue
        target, _resolved = resolve_okf_link(href, source_path=source_path, boi_root=DATA_ROOT)
        if target in seen:
            continue
        seen.add(target)
        path = find_doc_path_by_ref(target)
        if not path:
            continue
        try:
            linked_doc = read_doc(path)
        except Exception:
            continue
        if not is_accessible(linked_doc, employee_id):
            continue
        metadata = linked_doc.get("metadata") or {}
        ref = str(metadata.get("boi_id") or linked_doc.get("uri") or target)
        items.append(
            {
                "kind": "boi_document",
                "score": 100,
                "boi_id": metadata.get("boi_id") or "",
                "uri": linked_doc.get("uri") or "",
                "title": metadata.get("title") or ref,
                "description": metadata.get("description") or "",
                "url": doc_url_for_ref(ref, employee_id),
            }
        )
        if len(items) >= limit:
            break
    return items


def agent_fast_answer(req: BoiAgentChatRequest, employee_id: str, route: dict[str, Any], started_at: float) -> dict[str, Any]:
    context_pack = agent_context_pack(req, employee_id)
    page_context = context_pack["page_context"]
    intent = normalize_agent_intent(str(route.get("intent") or ""), fallback=deterministic_agent_intent(req.question, req.current_url))
    if page_context.get("resolved") and intent in {"page_qa", "summarize"}:
        search = {
            "best_matches": page_context.get("linked_items") or [],
            "query_expansion": [],
            "used_dictionary_terms": [],
            "knowledge_panel": {},
            "citations": [],
            "fast_path": "page_context",
        }
    else:
        search = context_pack.get("ontology_search_seed") or ontology_search_payload(req.question, employee_id, scope="all", limit=5, current_url=req.current_url)
    links: list[dict[str, Any]] = []
    links.extend(link_items_from_agent_context(page_context, employee_id))
    for item in search.get("best_matches") or []:
        link = agent_link_for_item(item)
        if link.get("url") and all(existing.get("url") != link["url"] for existing in links):
            links.append(link)
    page_label = str(page_context.get("title") or page_context.get("page_kind") or "현재 화면")
    if page_context.get("resolved"):
        answer_lines = [f"현재 화면은 `{page_context.get('page_kind')}`로 해석했습니다: **{page_label}**."]
    else:
        answer_lines = ["현재 화면을 정확히 해석하지 못해 BoI Wiki ontology search 기준으로 답변합니다."]
    if intent == "search":
        expanded = search.get("query_expansion") or []
        if expanded:
            answer_lines.append("검색어를 다음 업무 용어로 확장했습니다: " + ", ".join(f"`{term}`" for term in expanded[:6]))
        knowledge = search.get("knowledge_panel") or {}
        panel_bits = []
        for key, label in (("top_sop", "SOP"), ("top_event_type", "Event"), ("top_action", "Action")):
            value = knowledge.get(key) if isinstance(knowledge, dict) else []
            if isinstance(value, list) and value:
                item = value[0]
                panel_bits.append(f"{label}: {item.get('title') or item.get('event_type') or item.get('action_key')}")
        if panel_bits:
            answer_lines.append("가장 관련 높은 축은 " + " / ".join(panel_bits) + "입니다.")
    best = (search.get("best_matches") or [])[:3]
    if best:
        answer_lines.append("관련 항목:")
        for item in best:
            label = str(item.get("title") or item.get("term") or item.get("event_type") or item.get("action_key") or item.get("boi_id") or "결과")
            url = str(item.get("url") or "")
            description = text_excerpt(str(item.get("description") or ""), 120)
            rendered_label = f"[{label}]({url})" if url else f"**{label}**"
            reason = str(item.get("match_reason") or item.get("kind") or "").replace("_", " ")
            suffix = f": {description}" if description else ""
            if reason and reason not in description:
                suffix = f" ({reason})" + suffix
            answer_lines.append(f"- {rendered_label}{suffix}")
    elif page_context.get("body_excerpt"):
        answer_lines.append(f"본문 발췌: {page_context['body_excerpt']}")
    else:
        answer_lines.append("질문과 직접 연결되는 항목을 찾지 못했습니다.")
    if route.get("route") == "fast":
        answer_lines.append(
            "\n더 복합적인 판단이 필요하면 `도식으로 보여줘`, `누락된 Action을 찾아줘`, "
            "`실행 근거를 분석해줘`처럼 원하는 산출물을 구체적으로 요청하세요."
        )
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    context_summary = {
        "page_context": page_context,
        "current_url": req.current_url,
        "route": route.get("route"),
        "intent": intent,
        "router_backend": route.get("router_backend"),
        "router_confidence": route.get("confidence"),
        "used_backend": "fast_api",
        "latency_ms": latency_ms,
    }
    return {
        "ok": True,
        "employee_id": employee_id,
        "answer_markdown": "\n".join(answer_lines),
        "links": links[:8],
        "citations": links[:5],
        "suggested_questions": [],
        "suggested_questions_source": "suggestions_endpoint_required",
        "artifacts": [],
        "context_summary": context_summary,
        "route": route.get("route"),
        "intent": intent,
        "router_backend": route.get("router_backend"),
        "router_confidence": route.get("confidence"),
        "used_backend": "fast_api",
        "latency_ms": latency_ms,
    }


def agent_inbox_answer(req: BoiAgentChatRequest, employee_id: str, route: dict[str, Any], started_at: float) -> dict[str, Any]:
    inbox = agent_inbox_payload(employee_id, status="open", limit=5)
    items = inbox.get("items") or []
    intent = normalize_agent_intent(str(route.get("intent") or ""), fallback="inbox")
    lines = [f"현재 처리할 업무는 {len(items)}건입니다."]
    for item in items[:5]:
        display = item.get("display") if isinstance(item.get("display"), dict) else {}
        label = display.get("status_label") or item.get("status") or "확인 필요"
        title = display.get("title") or item.get("action_key") or "업무 확인"
        next_action = display.get("next_action") or "업무 흐름이나 원본 기록을 확인하세요."
        primary_url = display.get("primary_url") or item.get("workflow_url") or item.get("raw_url") or ""
        rendered_title = f"[{title}]({primary_url})" if primary_url else f"**{title}**"
        lines.append(f"- {label}: {rendered_title} - {next_action}")
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    return {
        "ok": True,
        "employee_id": employee_id,
        "answer_markdown": "\n".join(lines),
        "links": [
            {"label": str(item.get("action_key") or item.get("request_id")), "url": str(item.get("raw_url") or item.get("workflow_url") or ""), "kind": "inbox"}
            for item in items
            if item.get("raw_url") or item.get("workflow_url")
        ],
        "citations": [],
        "suggested_questions": [],
        "suggested_questions_source": "suggestions_endpoint_required",
        "artifacts": [{"type": "task_cards", "data": [item.get("display") for item in items if item.get("display")]}],
        "context_summary": {"route": route.get("route"), "intent": intent, "router_backend": route.get("router_backend"), "used_backend": "inbox_api", "latency_ms": latency_ms},
        "route": route.get("route"),
        "intent": intent,
        "router_backend": route.get("router_backend"),
        "router_confidence": route.get("confidence"),
        "used_backend": "inbox_api",
        "latency_ms": latency_ms,
    }


def agent_safety_answer(req: BoiAgentChatRequest, employee_id: str, route: dict[str, Any], started_at: float) -> dict[str, Any]:
    latency_ms = int((time.perf_counter() - started_at) * 1000)
    route_name = str(route.get("route") or "approval_required")
    intent = normalize_agent_intent(str(route.get("intent") or ""), fallback="approval" if route_name == "approval_required" else "manual_complete")
    if route_name == "manual_handoff":
        answer = "조치 완료는 Inbox 카드에서 조치 내용과 결과를 입력한 뒤 명시적으로 완료 기록을 남겨야 합니다."
    else:
        answer = "승인, 실행, 게시, 편집 같은 상태 변경 요청은 Agent 답변만으로 수행하지 않습니다. 관련 업무 흐름과 원본 기록을 확인하고 명시 승인 절차로 진행해야 합니다."
    return {
        "ok": True,
        "employee_id": employee_id,
        "answer_markdown": answer,
        "links": [],
        "citations": [],
        "suggested_questions": [],
        "suggested_questions_source": "suggestions_endpoint_required",
        "artifacts": [],
        "context_summary": {"route": route_name, "intent": intent, "router_backend": route.get("router_backend"), "used_backend": "safety_guard", "latency_ms": latency_ms},
        "route": route_name,
        "intent": intent,
        "router_backend": route.get("router_backend"),
        "router_confidence": route.get("confidence"),
        "used_backend": "safety_guard",
        "latency_ms": latency_ms,
    }


def langflow_auth_headers() -> dict[str, str]:
    if LANGFLOW_AUTH_MODE == "api-key":
        return {"x-api-key": LANGFLOW_API_KEY}
    try:
        with httpx.Client(timeout=LANGFLOW_AGENT_TIMEOUT_SECONDS) as client:
            response = client.get(f"{LANGFLOW_URL}/api/v1/auto_login")
            response.raise_for_status()
            token = response.json().get("access_token")
    except Exception as exc:  # pragma: no cover - exercised through route-level unavailable handling
        raise LangflowBoiAgentUnavailable(f"Langflow auto_login failed: {exc}") from exc
    if not token:
        raise LangflowBoiAgentUnavailable("Langflow auto_login did not return access_token")
    return {"Authorization": f"Bearer {token}"}


def iter_langflow_text_candidates(value: Any, depth: int = 0) -> list[str]:
    if depth > 12:
        return []
    candidates: list[str] = []
    if isinstance(value, str):
        if value.strip():
            candidates.append(value)
        return candidates
    if isinstance(value, list):
        for item in value:
            candidates.extend(iter_langflow_text_candidates(item, depth + 1))
        return candidates
    if isinstance(value, dict):
        preferred_keys = (
            "choices",
            "answer_markdown",
            "text",
            "message",
            "content",
            "reasoning_content",
            "output",
            "result",
            "data",
            "results",
            "artifacts",
            "outputs",
            "messages",
        )
        seen_keys: set[str] = set()
        for key in preferred_keys:
            if key in value:
                seen_keys.add(key)
                candidates.extend(iter_langflow_text_candidates(value.get(key), depth + 1))
        for key, item in value.items():
            if key not in seen_keys:
                candidates.extend(iter_langflow_text_candidates(item, depth + 1))
    return candidates


def first_langflow_text(value: Any) -> str:
    for text in iter_langflow_text_candidates(value):
        if text.strip():
            return text
    return ""


def parse_langflow_json_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped.removeprefix("```json").strip()
        if stripped.endswith("```"):
            stripped = stripped[:-3].strip()
    elif stripped.startswith("```") and stripped.endswith("```"):
        stripped = stripped[3:-3].strip()
    if not stripped.startswith("{"):
        return None
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def langflow_payload_has_answer(payload: dict[str, Any]) -> bool:
    answer = str(payload.get("answer_markdown") or payload.get("answer") or payload.get("message") or "").strip()
    return bool(answer and answer != "BoI Agent returned an empty answer.")


def parse_langflow_agent_payload(run_result: dict[str, Any]) -> dict[str, Any]:
    candidates = iter_langflow_text_candidates(run_result)
    if not candidates:
        raise LangflowBoiAgentUnavailable("BoI Agent Flow returned no message")
    parsed_candidates: list[dict[str, Any]] = []
    for text in candidates:
        parsed = parse_langflow_json_text(text)
        if parsed is None:
            continue
        if langflow_payload_has_answer(parsed):
            return parsed
        parsed_candidates.append(parsed)
    if parsed_candidates:
        return parsed_candidates[0]
    return {"answer_markdown": candidates[0]}


def normalize_langflow_agent_response(
    run_result: dict[str, Any],
    req: BoiAgentChatRequest,
    employee_id: str,
    route: dict[str, Any] | None = None,
    started_at: float | None = None,
) -> dict[str, Any]:
    parsed = parse_langflow_agent_payload(run_result)
    answer_markdown = str(parsed.get("answer_markdown") or parsed.get("answer") or parsed.get("message") or "").strip()
    if not answer_markdown:
        raise LangflowBoiAgentUnavailable("BoI Agent Flow response did not include answer_markdown")
    links = parsed.get("links")
    if not isinstance(links, list):
        links = []
    citations = parsed.get("citations")
    if not isinstance(citations, list):
        citations = links[:5]
    suggestions = parsed.get("suggested_questions")
    suggestions_source = "llm_composer" if isinstance(suggestions, list) and suggestions else "suggestions_endpoint_required"
    if not isinstance(suggestions, list) or not suggestions:
        suggestions = []
    artifacts = normalize_agent_artifacts(parsed.get("artifacts"), answer_markdown)
    intent = normalize_agent_intent(str(route.get("intent") if route else parsed.get("intent") or ""), fallback=deterministic_agent_intent(req.question, req.current_url))
    if intent == "diagram" and not any(item.get("type") == "mermaid" for item in artifacts):
        raise LangflowBoiAgentUnavailable("BoI Agent Flow did not return required Mermaid artifact for diagram intent")
    context_summary = parsed.get("context_summary")
    if not isinstance(context_summary, dict):
        context_summary = {}
    context_summary.update(
        {
            "current_url": req.current_url,
            "intent": intent,
            "langflow_flow": LANGFLOW_BOI_AGENT_ENDPOINT,
            "langflow_backend": "trusted",
        }
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000) if started_at else None
    if route:
        context_summary.update(
            {
                "route": route.get("route"),
                "router_backend": route.get("router_backend"),
                "router_confidence": route.get("confidence"),
                "used_backend": "langflow",
            }
        )
        if latency_ms is not None:
            context_summary["latency_ms"] = latency_ms
    return {
        "ok": True,
        "employee_id": employee_id,
        "answer_markdown": answer_markdown,
        "links": links,
        "citations": citations,
        "suggested_questions": suggestions,
        "suggested_questions_source": suggestions_source,
        "artifacts": artifacts,
        "context_summary": context_summary,
        "route": route.get("route") if route else "deep",
        "intent": intent,
        "router_backend": route.get("router_backend") if route else "",
        "router_confidence": route.get("confidence") if route else None,
        "used_backend": "langflow",
        "latency_ms": latency_ms,
    }


def call_langflow_boi_agent(req: BoiAgentChatRequest, employee_id: str, route: dict[str, Any] | None = None, started_at: float | None = None) -> dict[str, Any]:
    if not LANGFLOW_URL or not LANGFLOW_BOI_AGENT_ENDPOINT:
        raise LangflowBoiAgentUnavailable("Langflow BoI Agent endpoint is not configured")
    context_pack = agent_context_pack(req, employee_id, search_limit=6)
    intent = normalize_agent_intent(str(route.get("intent") if route else req.intent), fallback=deterministic_agent_intent(req.question, req.current_url))
    payload = {
        "input_value": json.dumps(
            {
                "question": req.question,
                "employee_id": employee_id,
                "mode": req.mode,
                "intent": intent,
                "route": route or {},
                "current_url": req.current_url,
                "selected_text": req.selected_text,
                "page_context": req.page_context,
                "page_context_pack": context_pack.get("page_context") or {},
                "ontology_search_seed": context_pack.get("ontology_search_seed") or {},
                "conversation": req.conversation[-12:],
                "save_memory": req.save_memory,
            },
            ensure_ascii=False,
            default=str,
        ),
        "input_type": "chat",
        "output_type": "chat",
    }
    headers = {**langflow_auth_headers(), "Content-Type": "application/json"}
    url = f"{LANGFLOW_URL}/api/v1/run/{LANGFLOW_BOI_AGENT_ENDPOINT}"
    try:
        with httpx.Client(timeout=LANGFLOW_AGENT_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=payload)
            if response.status_code == 404:
                raise LangflowBoiAgentUnavailable(f"BoI Agent Flow endpoint not found: {LANGFLOW_BOI_AGENT_ENDPOINT}")
            response.raise_for_status()
            run_result = response.json()
    except LangflowBoiAgentUnavailable:
        raise
    except Exception as exc:
        raise LangflowBoiAgentUnavailable(f"Langflow BoI Agent call failed: {exc}") from exc
    return normalize_langflow_agent_response(run_result, req, employee_id, route=route, started_at=started_at)


def agent_chat_response(
    req: BoiAgentChatRequest,
    employee_id: str,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    route: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    route = dict(route) if route else route_boi_agent_request(req, employee_id)
    if BOI_AGENT_BACKEND in {"native", "hybrid"}:
        try:
            return call_native_boi_agent(req, employee_id, route, started_at, progress_callback=progress_callback)
        except NativeAgentRuntimeUnavailable:
            raise
        except Exception as exc:
            raise NativeAgentRuntimeUnavailable(f"Native Agent runtime failed: {exc}") from exc

    route_name = str(route.get("route") or "fast")
    if route_name in {"manual_handoff", "approval_required"}:
        return agent_safety_answer(req, employee_id, route, started_at)
    if BOI_AGENT_BACKEND == "langflow" and route_name == "deep":
        return call_langflow_boi_agent(req, employee_id, route=route, started_at=started_at)
    if BOI_AGENT_BACKEND not in {"native", "hybrid", "langflow"}:
        raise NativeAgentRuntimeUnavailable(f"Unknown BOI_AGENT_BACKEND: {BOI_AGENT_BACKEND}")
    if BOI_AGENT_BACKEND in {"native", "hybrid"} or route_name in {"fast", "deep", "inbox"}:
        return call_native_boi_agent(req, employee_id, route, started_at, progress_callback=progress_callback)
    if route_name == "inbox":
        return agent_inbox_answer(req, employee_id, route, started_at)
    return agent_fast_answer(req, employee_id, route, started_at)


@app.post("/api/agents/boi-wiki/chat")
async def api_boi_agent_chat(req: BoiAgentChatRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    append_activity(employee_id, {"activity_type": "agent_question", "target": req.current_url, "title": req.question[:120]})
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(lambda: enrich_agent_answer_html(agent_chat_response(req, employee_id), employee_id)),
            timeout=BOI_AGENT_CHAT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "boi_agent_timeout",
                "message": f"BoI Agent did not finish within {BOI_AGENT_CHAT_TIMEOUT_SECONDS:.1f}s",
                "timeout_seconds": BOI_AGENT_CHAT_TIMEOUT_SECONDS,
                "used_backend": BOI_AGENT_BACKEND,
                "model": BOI_AGENT_COMPOSER_MODEL,
            },
        ) from exc
    except BoiAgentRouterUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "boi_agent_router_unavailable",
                "message": str(exc),
                "model": BOI_AGENT_ROUTER_MODEL,
                "required": BOI_AGENT_ROUTER_REQUIRED,
            },
        ) from exc
    except NativeAgentRuntimeUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "native_agent_runtime_unavailable",
                "message": str(exc),
                "langgraph_available": LANGGRAPH_AVAILABLE,
                "langgraph_required": BOI_AGENT_LANGGRAPH_REQUIRED,
            },
        ) from exc
    except LangflowBoiAgentUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "langflow_boi_agent_unavailable",
                "message": str(exc),
                "langflow_url": LANGFLOW_URL,
                "endpoint": LANGFLOW_BOI_AGENT_ENDPOINT,
            },
        ) from exc


@app.post("/api/agents/boi-wiki/chat/stream")
async def api_boi_agent_chat_stream(req: BoiAgentChatRequest, employee_id: str = Depends(current_employee)) -> StreamingResponse:
    append_activity(employee_id, {"activity_type": "agent_question", "target": req.current_url, "title": req.question[:120]})
    try:
        stream_plan = await asyncio.to_thread(agent_stream_plan, req, employee_id)
        status_steps = stream_plan["status_steps"]
        planned_route = stream_plan["route"]
    except BoiAgentStatusUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "status_generation_failed",
                "message": str(exc),
                "model": BOI_AGENT_STATUS_MODEL,
                "required": BOI_AGENT_STATUS_REQUIRED,
            },
        ) from exc
    except BoiAgentRouterUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "boi_agent_router_unavailable",
                "message": str(exc),
                "model": BOI_AGENT_ROUTER_MODEL,
                "required": BOI_AGENT_ROUTER_REQUIRED,
            },
        ) from exc
    except NativeAgentRuntimeUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "native_agent_runtime_unavailable",
                "message": str(exc),
                "langgraph_available": LANGGRAPH_AVAILABLE,
                "langgraph_required": BOI_AGENT_LANGGRAPH_REQUIRED,
            },
        ) from exc

    async def stream_events():
        emitted_status_messages: set[str] = set()

        def status_event_if_new(step: dict[str, str], elapsed_ms: int) -> str | None:
            message = str(step.get("message") or "")
            if message in emitted_status_messages:
                return None
            emitted_status_messages.add(message)
            return agent_sse_event("status", {**step, "elapsed_ms": elapsed_ms})

        initial_status = status_event_if_new(status_steps[0], 0)
        if initial_status:
            yield initial_status
        started_at = time.perf_counter()
        progress_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

        def emit_progress(payload: dict[str, Any]) -> None:
            progress_queue.put(payload)

        def drain_progress_events() -> list[dict[str, Any]]:
            drained: list[dict[str, Any]] = []
            while True:
                try:
                    drained.append(progress_queue.get_nowait())
                except queue.Empty:
                    return drained

        def run_agent() -> dict[str, Any]:
            return enrich_agent_answer_html(agent_chat_response(req, employee_id, progress_callback=emit_progress, route=planned_route), employee_id)

        def run_agent_worker() -> None:
            try:
                result_queue.put(("response", run_agent()))
            except Exception as exc:  # pragma: no cover - exercised through stream error path
                result_queue.put(("error", exc))

        worker = threading.Thread(target=run_agent_worker, name="boi-agent-stream-worker", daemon=True)
        worker.start()
        status_index = 1
        last_generic_status_at = started_at
        response: dict[str, Any] | None = None
        try:
            while True:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                drain_progress_events()

                try:
                    kind, payload = result_queue.get_nowait()
                except queue.Empty:
                    if (
                        status_index < len(status_steps)
                        and time.perf_counter() - last_generic_status_at >= max(0.5, BOI_AGENT_STREAM_HEARTBEAT_SECONDS)
                    ):
                        step = status_steps[min(status_index, len(status_steps) - 1)]
                        status_index += 1
                        last_generic_status_at = time.perf_counter()
                        status_event = status_event_if_new(step, elapsed_ms)
                        if status_event:
                            yield status_event
                    await asyncio.sleep(0.25)
                    continue
                if kind == "error":
                    raise payload
                response = payload
                break

            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            drain_progress_events()

            if response is None:
                raise RuntimeError("BoI Agent stream finished without a response")
            display_markdown = str(response.get("display_markdown") or response.get("answer_markdown") or "")
            chunks = iter_agent_answer_chunks(display_markdown)
            if chunks:
                answer_status = next((item for item in status_steps if item.get("stage") == "answer_stream"), status_steps[-1])
                status_event = status_event_if_new(answer_status, elapsed_ms)
                if status_event:
                    yield status_event
            chunk_delay = agent_stream_chunk_delay_seconds()
            for chunk in chunks:
                yield agent_sse_event("answer_delta", {"delta": chunk})
                if chunk_delay:
                    await asyncio.sleep(chunk_delay)
            yield agent_sse_event("final", response)
        except LangflowBoiAgentUnavailable as exc:
            yield agent_sse_event(
                "error",
                {
                    "status": "langflow_boi_agent_unavailable",
                    "message": str(exc),
                    "endpoint": LANGFLOW_BOI_AGENT_ENDPOINT,
                },
            )
        except BoiAgentRouterUnavailable as exc:
            yield agent_sse_event(
                "error",
                {
                    "status": "boi_agent_router_unavailable",
                    "message": str(exc),
                    "model": BOI_AGENT_ROUTER_MODEL,
                    "required": BOI_AGENT_ROUTER_REQUIRED,
                },
            )
        except NativeAgentRuntimeUnavailable as exc:
            yield agent_sse_event(
                "error",
                {
                    "status": "native_agent_runtime_unavailable",
                    "message": str(exc),
                    "langgraph_available": LANGGRAPH_AVAILABLE,
                    "langgraph_required": BOI_AGENT_LANGGRAPH_REQUIRED,
                },
            )
        except Exception as exc:
            yield agent_sse_event("error", {"status": "agent_stream_error", "message": str(exc)})
        finally:
            # The worker is daemonized because a client-side stop cannot safely
            # interrupt an in-flight LLM/tool request. Late results are dropped.
            worker.join(timeout=0)

    return StreamingResponse(stream_events(), media_type="text/event-stream")


@app.post("/api/agents/boi-wiki/suggestions")
async def api_boi_agent_suggestions(req: BoiAgentSuggestionsRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    resolved_context = resolve_agent_page_context(req.current_url, employee_id)
    if not resolved_context.get("title") and req.page_context.get("title"):
        resolved_context["title"] = req.page_context.get("title")
    source = "llm"
    try:
        suggestions = await asyncio.to_thread(call_boi_agent_suggestions_llm, req, employee_id, resolved_context)
    except BoiAgentSuggestionsUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "ok": False,
                "status": "boi_agent_suggestions_unavailable",
                "message": str(exc),
                "model": BOI_AGENT_SUGGESTIONS_MODEL,
                "required": BOI_AGENT_SUGGESTIONS_REQUIRED,
            },
        ) from exc
    return {
        "ok": True,
        "employee_id": employee_id,
        "current_url": req.current_url,
        "page_context": resolved_context,
        "suggestions": suggestions,
        "suggestions_source": source,
    }


@app.get("/api/agents/boi-wiki/capabilities")
async def api_boi_agent_capabilities(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {
        "ok": True,
        "employee_id": employee_id,
        "build_revision": BOI_BUILD_REVISION,
        "official_external_interfaces": ["BoI API", "boi-wiki-mcp"],
        "trusted_dev_backend": "Langflow optional visual/debug backend",
        "boi_agent_backend": BOI_AGENT_BACKEND,
        "router": {
            "mode": BOI_AGENT_ROUTER_MODE,
            "llm_enabled": BOI_AGENT_ROUTER_LLM_ENABLED,
            "required": BOI_AGENT_ROUTER_REQUIRED,
            "base_url": BOI_AGENT_ROUTER_BASE_URL,
            "model": BOI_AGENT_ROUTER_MODEL,
            "timeout_seconds": BOI_AGENT_ROUTER_TIMEOUT_SECONDS,
            "max_tokens": BOI_AGENT_ROUTER_MAX_TOKENS,
            "confidence_threshold": BOI_AGENT_ROUTER_CONFIDENCE_THRESHOLD,
        },
        "status_writer": {
            "llm_enabled": BOI_AGENT_STATUS_LLM_ENABLED,
            "required": BOI_AGENT_STATUS_REQUIRED,
            "base_url": BOI_AGENT_STATUS_BASE_URL,
            "model": BOI_AGENT_STATUS_MODEL,
            "timeout_seconds": BOI_AGENT_STATUS_TIMEOUT_SECONDS,
            "max_tokens": BOI_AGENT_STATUS_MAX_TOKENS,
        },
        "composer": {
            "llm_enabled": BOI_AGENT_COMPOSER_LLM_ENABLED,
            "required": BOI_AGENT_COMPOSER_REQUIRED,
            "base_url": BOI_AGENT_COMPOSER_BASE_URL,
            "model": BOI_AGENT_COMPOSER_MODEL,
            "timeout_seconds": BOI_AGENT_COMPOSER_TIMEOUT_SECONDS,
            "max_tokens": BOI_AGENT_COMPOSER_MAX_TOKENS,
        },
        "chat_timeout_seconds": BOI_AGENT_CHAT_TIMEOUT_SECONDS,
        "suggestions": {
            "llm_enabled": BOI_AGENT_SUGGESTIONS_LLM_ENABLED,
            "required": BOI_AGENT_SUGGESTIONS_REQUIRED,
            "base_url": BOI_AGENT_SUGGESTIONS_BASE_URL,
            "model": BOI_AGENT_SUGGESTIONS_MODEL,
            "timeout_seconds": BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS,
            "max_tokens": BOI_AGENT_SUGGESTIONS_MAX_TOKENS,
        },
        "rbac_enabled": True,
        "acl_guardrail_enabled": True,
        "classification_policy_version": CLASSIFICATION_POLICY_VERSION,
        "supported_execution_cards": [
            "event_publish",
            "workflow_start",
            "action_invoke",
            "manual_handoff_complete",
            "event_type_draft",
            "event_type_draft_apply",
            "promotion_submit",
        ],
        "native_agent": {
            "enabled": BOI_AGENT_BACKEND in {"native", "hybrid"},
            "runtime": "LangGraph" if LANGGRAPH_AVAILABLE else "unavailable",
            "langgraph_available": LANGGRAPH_AVAILABLE,
            "langgraph_required": BOI_AGENT_LANGGRAPH_REQUIRED,
            "max_tool_loops": BOI_AGENT_NATIVE_MAX_TOOL_LOOPS,
            "tool_timeout_seconds": BOI_AGENT_NATIVE_TOOL_TIMEOUT_SECONDS,
            "cache_warmup": agent_cache_warmup_state(),
        },
        "langflow_boi_agent_endpoint": LANGFLOW_BOI_AGENT_ENDPOINT,
        "langflow_boi_agent_configured": bool(LANGFLOW_URL and LANGFLOW_BOI_AGENT_ENDPOINT),
        "streaming": {
            "enabled": True,
            "endpoint": "/api/agents/boi-wiki/chat/stream",
            "protocol": "text/event-stream",
            "events": ["status", "answer_delta", "final", "error"],
        },
        "features": [
            "page-aware Q&A",
            "progressive response streaming",
            "ontology-assisted search",
            "dictionary resolve",
            "action inbox",
            "manual handoff completion",
            "private memory",
            "recent activity",
        ],
        "write_confirmation_required": [
            "approve",
            "event_publish",
            "workflow_start",
            "action_invoke",
            "manual_handoff_complete",
            "event_type_draft",
            "event_type_draft_apply",
            "promotion_submit",
            "source_apply",
            "doc_body_apply",
        ],
    }


@app.post("/api/agents/boi-wiki/approve")
async def api_boi_agent_approve(req: BoiAgentApprovalRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="user_confirmed=true is required")
    operation = req.operation.strip()
    payload = req.payload or {}
    if operation in {"event_publish", "publish_event"}:
        if payload.get("actor_employee_id") and payload.get("actor_employee_id") != employee_id and not payload.get("admin_override_reason") and req.note:
            payload = {**payload, "admin_override_reason": req.note}
        result = await publish_event(EventPublishRequest(**payload), employee_id)
        append_rbac_audit(employee_id, "agent_event_publish", {"operation": operation, "event_type": payload.get("event_type"), "note": req.note})
        return {"ok": True, "operation": operation, "status": "executed", "result": result}
    if operation in {"workflow_start", "start_workflow"}:
        workflow_key = str(payload.get("workflow_key") or payload.get("key") or "")
        if not workflow_key:
            raise HTTPException(status_code=400, detail="workflow_key is required")
        result = await start_workflow_from_data(workflow_key, payload.get("payload") or payload, employee_id)
        append_rbac_audit(employee_id, "agent_workflow_start", {"workflow_key": workflow_key, "note": req.note})
        return {"ok": True, "operation": operation, "status": "executed", "result": result}
    if operation in {"action_invoke", "invoke_action"}:
        if payload.get("employee_id") and payload.get("employee_id") != employee_id and not payload.get("admin_override_reason") and req.note:
            payload = {**payload, "admin_override_reason": req.note}
        result = await invoke_action_gateway(ActionInvokeRequest(**payload), employee_id)
        append_rbac_audit(employee_id, "agent_action_invoke", {"action_key": payload.get("action_key"), "note": req.note})
        return {"ok": True, "operation": operation, "status": "executed", "result": result}
    if operation in {"manual_handoff_complete", "manual_complete"}:
        result = await complete_manual_handoff(ManualHandoffCompleteRequest(**payload), employee_id)
        append_rbac_audit(employee_id, "agent_manual_handoff_complete", {"task_id": payload.get("task_id"), "note": req.note})
        return {"ok": True, "operation": operation, "status": "executed", "result": result}
    if operation in {"event_type_draft", "create_event_type_draft"}:
        draft_payload = {**payload, "user_confirmed": True}
        draft = create_event_type_draft(EventTypeDraftRequest(**draft_payload), employee_id)
        return {"ok": True, "operation": operation, "status": "draft_created", "draft": draft}
    if operation in {"event_type_draft_apply", "apply_event_type_draft"}:
        draft_id = str(payload.get("draft_id") or "")
        if not draft_id:
            raise HTTPException(status_code=400, detail="draft_id is required")
        apply_req = EventTypeDraftApplyRequest(user_confirmed=True, author=payload.get("author"), note=req.note or str(payload.get("note") or ""))
        result = apply_event_type_draft(draft_id, apply_req, employee_id)
        return {"ok": True, "operation": operation, "status": "applied", "result": result}
    if operation in {"promotion_submit", "submit_promotion"}:
        promotion_payload = {**payload, "user_confirmed": True}
        result = await submit_promotion(PromotionSubmitRequest(**promotion_payload), employee_id)
        append_rbac_audit(
            employee_id,
            "agent_promotion_submit",
            {
                "target_visibility": promotion_payload.get("target_visibility"),
                "team_id": promotion_payload.get("team_id"),
                "title": promotion_payload.get("title"),
                "note": req.note,
            },
        )
        return {"ok": True, "operation": operation, "status": "executed", "result": result}
    raise HTTPException(status_code=400, detail=f"unsupported Agent approval operation: {req.operation}")


def activity_file_for_employee(employee_id: str) -> Path:
    now = datetime.now(KST)
    return ACTIVITY_ROOT / "private" / employee_id / f"activity-{now.strftime('%Y%m')}.jsonl"


def append_activity(employee_id: str, activity: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    path = activity_file_for_employee(employee_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "activity_id": f"activity-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "employee_id": employee_id,
        "logged_at": now_iso(),
        **activity,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
    return row


def recent_activity(employee_id: str, limit: int = 50) -> list[dict[str, Any]]:
    root = ACTIVITY_ROOT / "private" / employee_id
    if not root.exists():
        return []
    rows: list[dict[str, Any]] = []
    cutoff = datetime.now(KST) - timedelta(days=30)
    for path in sorted(root.glob("activity-*.jsonl"), reverse=True):
        for line in reversed(path.read_text(encoding="utf-8").splitlines()):
            try:
                row = json.loads(line)
            except Exception:
                continue
            try:
                logged_at = datetime.fromisoformat(str(row.get("logged_at") or ""))
            except Exception:
                logged_at = datetime.now(KST)
            if logged_at < cutoff:
                continue
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


@app.post("/api/agents/boi-wiki/activity")
async def api_agent_activity_write(req: ActivityRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {"ok": True, "item": append_activity(employee_id, req.model_dump())}


@app.get("/api/agents/boi-wiki/activity")
async def api_agent_activity(employee_id: str = Depends(current_employee), limit: int = 50) -> dict[str, Any]:
    items = recent_activity(employee_id, limit=max(1, min(limit, 200)))
    return {"ok": True, "count": len(items), "items": items}


def agent_memory_items(employee_id: str, q: str = "", limit: int = 20, include_archived: bool = False) -> list[dict[str, Any]]:
    docs = [
        doc
        for doc in accessible_docs(employee_id)
        if str((doc.get("metadata") or {}).get("type") or "") == "boi/agent-memory"
        and "/agent-memory/" in str(doc.get("uri") or "")
    ]
    if not include_archived:
        docs = [doc for doc in docs if (doc.get("metadata") or {}).get("archive_status", "active") == "active"]
    if q:
        tokens = search_tokens_for_query(q, employee_id)
        docs = [
            doc
            for doc in docs
            if weighted_text_score(doc_search_blob(doc), tokens, title=str((doc.get("metadata") or {}).get("title") or "")) > 0
        ]
    items = []
    for doc in docs[: max(1, min(limit, 100))]:
        metadata = doc.get("metadata") or {}
        items.append(
            {
                "memory_id": metadata.get("boi_id"),
                "title": metadata.get("title"),
                "memory_kind": metadata.get("memory_kind") or "",
                "description": metadata.get("description") or "",
                "usage_count": metadata.get("usage_count", 1),
                "archive_status": metadata.get("archive_status", "active"),
                "url": doc_url_for_ref(stable_doc_ref(doc), employee_id),
            }
        )
    return items


@app.get("/api/agents/boi-wiki/memory")
async def api_agent_memory(employee_id: str = Depends(current_employee), q: str = "", include_archived: bool = False, limit: int = 20) -> dict[str, Any]:
    items = agent_memory_items(employee_id, q=q, limit=limit, include_archived=include_archived)
    return {"ok": True, "count": len(items), "items": items}


@app.post("/api/agents/boi-wiki/memory")
async def api_agent_memory_write(req: AgentMemoryRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    forbidden = re.compile(r"(password|token|secret|api[_ -]?key|승인 우회|자동 승인)", re.IGNORECASE)
    if forbidden.search(req.body) or forbidden.search(req.title):
        raise HTTPException(status_code=400, detail="sensitive or high-risk preference cannot be auto-saved as memory")
    metadata = make_metadata(
        boi_type="boi/agent-memory",
        title=req.title,
        description=req.body[:160],
        owner=employee_id,
        visibility="private",
        classification="internal",
        source_refs=req.source_refs or [{"type": "agent-memory", "ref": "BoI Agent conversation"}],
        status="draft",
        tags=list(dict.fromkeys(["AgentMemory", req.memory_kind, *req.tags])),
    )
    metadata.update(
        {
            "memory_kind": req.memory_kind,
            "importance": max(1, min(int(req.importance or 3), 5)),
            "usage_count": 1,
            "archive_status": "active",
            "review_after": (datetime.now(KST) + timedelta(days=90)).date().isoformat(),
        }
    )
    doc = write_boi_to_subfolder(metadata, req.body, "agent-memory")
    return {"ok": True, "item": doc_result_item(doc, employee_id)}


def update_memory_metadata(memory_id: str, employee_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    doc = find_doc_by_id(memory_id, employee_id)
    if not doc or str((doc.get("metadata") or {}).get("type") or "") != "boi/agent-memory":
        raise HTTPException(status_code=404, detail="memory not found")
    path = Path(str(doc.get("path") or ""))
    if not path.exists():
        raise HTTPException(status_code=404, detail="memory source missing")
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
    metadata.update(updates)
    metadata["updated_at"] = now_iso()
    path.write_text(compose_markdown(metadata, body), encoding="utf-8")
    invalidate_doc_caches()
    updated = read_doc(path)
    return doc_result_item(updated, employee_id)


@app.post("/api/agents/boi-wiki/memory/{memory_id:path}/archive")
async def api_agent_memory_archive(memory_id: str, req: AgentMemoryUpdateRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {"ok": True, "item": update_memory_metadata(memory_id, employee_id, {"archive_status": "archived", "archive_note": req.note})}


@app.post("/api/agents/boi-wiki/memory/{memory_id:path}/supersede")
async def api_agent_memory_supersede(memory_id: str, req: AgentMemoryUpdateRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {"ok": True, "item": update_memory_metadata(memory_id, employee_id, {"archive_status": "superseded", "superseded_by": req.superseded_by or "", "archive_note": req.note})}


@app.post("/api/agents/boi-wiki/memory/compact")
async def api_agent_memory_compact(employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    items = agent_memory_items(employee_id, limit=200)
    by_title: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_title.setdefault(normalize_search_token(str(item.get("title") or "")), []).append(item)
    candidates = [group for group in by_title.values() if len(group) > 1]
    return {"ok": True, "candidate_groups": candidates, "message": "Review candidates before superseding or archiving memory."}


@app.post("/api/agents/boi-wiki/memory/undo")
async def api_agent_memory_undo(memory_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return {"ok": True, "item": update_memory_metadata(memory_id, employee_id, {"archive_status": "active", "undo_at": now_iso()})}


@app.get("/api/dictionary/resolve")
async def api_dictionary_resolve(employee_id: str = Depends(current_employee), q: str = "", scope: str = "all") -> dict[str, Any]:
    return {"ok": True, **resolve_dictionary_query(q, employee_id, scope=scope)}


@app.get("/api/dictionary/terms")
async def api_dictionary_terms(employee_id: str = Depends(current_employee), scope: str = "all", q: str = "", limit: int = 100) -> dict[str, Any]:
    items = dictionary_terms_for_employee(employee_id, scope=scope)
    if q:
        q_lower = normalize_search_token(q)
        items = [item for item in items if q_lower in normalize_search_token(json.dumps(item, ensure_ascii=False, default=str))]
    items = items[: max(1, min(limit, 500))]
    return {"ok": True, "count": len(items), "items": items}


@app.post("/api/dictionary/terms")
async def api_dictionary_term_create(req: DictionaryTermRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    visibility = "private" if req.scope == "private" else req.scope
    team_id = req.team_id or (teams_for(employee_id)[0] if req.scope == "team" else None)
    owner = employee_id if req.scope == "private" else (team_id or "public")
    metadata = make_metadata(
        boi_type="boi/dictionary-term",
        title=req.term,
        description=req.definition,
        owner=owner,
        visibility=visibility,  # type: ignore[arg-type]
        classification="internal",
        team_id=team_id,
        source_refs=[{"type": "dictionary", "ref": "BoI Agent dictionary form"}],
        status="draft" if req.scope == "private" else "reviewed",
        tags=["Dictionary", req.domain] if req.domain else ["Dictionary"],
        reviewer="dictionary-curator" if req.scope != "private" else None,
    )
    metadata.update(
        {
            "term": req.term,
            "definition": req.definition,
            "aliases": req.aliases,
            "examples": [req.example] if req.example else [],
            "links": req.links,
            "domain": req.domain,
            "maps_to_event_type": req.maps_to_event_type,
            "maps_to_action_key": req.maps_to_action_key,
            "maps_to_sop": req.maps_to_sop,
        }
    )
    if req.scope == "private":
        doc = write_boi_to_subfolder(metadata, dictionary_body(req), "dictionary")
    else:
        doc = write_boi(metadata, dictionary_body(req))
    return {"ok": True, "item": doc_result_item(doc, employee_id)}


def dictionary_body(req: DictionaryTermRequest) -> str:
    lines = [
        "# Summary",
        "",
        req.definition,
        "",
        "## Usage",
        "",
        f"- Term: {req.term}",
    ]
    if req.aliases:
        lines.append(f"- Aliases: {', '.join(req.aliases)}")
    if req.example:
        lines.extend(["", "## Example", "", req.example])
    if req.links:
        lines.extend(["", "## Links", "", *[f"- {link}" for link in req.links]])
    return "\n".join(lines).strip() + "\n"


def completion_request_ids(rows: list[dict[str, Any]] | None = None) -> set[str]:
    completed: set[str] = set()
    for row in (rows if rows is not None else cached_action_log_rows()):
        if row.get("completion_for_request_id"):
            completed.add(str(row.get("completion_for_request_id")))
    return completed


def agent_inbox_display(row: dict[str, Any], employee_id: str, row_status: str) -> dict[str, str]:
    action_key = str(row.get("action_key") or "")
    action = action_catalog_by_key().get(action_key, {})
    action_title = str(action.get("name") or action.get("name_ko") or row.get("title") or action_key or "업무 확인")
    risk = str(action.get("risk_level") or row.get("risk_level") or "")
    workflow_url = workflow_status_page_url(str(row.get("trace_id") or ""), employee_id) if row.get("trace_id") else ""
    raw_url = action_raw_page_url(str(row.get("_log_ref") or ""), employee_id) if row.get("_log_ref") else ""
    if row_status == "approval_required":
        return {
            "title": f"{action_title} 승인 필요",
            "status_label": "승인 필요",
            "why_it_matters": "영향이 큰 작업이어서 자동 실행하지 않고 담당자 확인이 필요합니다.",
            "next_action": "업무 흐름과 근거 문서를 확인한 뒤 승인 또는 반려 여부를 결정하세요.",
            "risk_label": "고위험" if risk == "high" else "승인 필요",
            "primary_url": workflow_url or raw_url,
            "primary_label": "업무 상태 보기",
        }
    if row_status == "manual_required":
        return {
            "title": f"{action_title} 조치 필요",
            "status_label": "조치 필요",
            "why_it_matters": "사람 판단, 현장 확인, 또는 담당자 조치가 필요한 단계입니다.",
            "next_action": "확인/조치 내용을 입력하고 완료로 기록하세요.",
            "risk_label": "수동 조치",
            "primary_url": workflow_url or raw_url,
            "primary_label": "조치 내용 입력",
        }
    if row_status == "manual_blocked":
        return {
            "title": f"{action_title} 보류 상태",
            "status_label": "보류 확인",
            "why_it_matters": "필요한 근거, 승인, 담당자 확인 중 일부가 부족합니다.",
            "next_action": "막힌 이유를 확인하고 후속 조치를 남기세요.",
            "risk_label": "확인 필요",
            "primary_url": workflow_url or raw_url,
            "primary_label": "막힌 이유 보기",
        }
    return {
        "title": f"{action_title} 후속 확인",
        "status_label": "후속 확인",
        "why_it_matters": "Trace에서 추가 확인이 필요한 업무로 기록되었습니다.",
        "next_action": "관련 업무 흐름이나 원본 기록을 확인하고 필요한 조치를 결정하세요.",
        "risk_label": "후속 확인",
        "primary_url": workflow_url or raw_url,
        "primary_label": "세부 확인",
    }


def agent_inbox_payload(employee_id: str, status: str = "open", limit: int = 50) -> dict[str, Any]:
    recent_rows = read_recent_action_logs_fast(limit=max(50, min(limit * 20, 300)))
    completed = completion_request_ids(recent_rows)
    items: list[dict[str, Any]] = []
    for row in recent_rows:
        if not action_log_visible_to_employee(row, employee_id):
            continue
        request_id = str(row.get("request_id") or "")
        result_status = (row.get("result") or {}).get("status") if isinstance(row.get("result"), dict) else ""
        row_status = str(row.get("status") or result_status or "")
        if request_id in completed and status == "open":
            continue
        if row_status not in {"manual_required", "approval_required", "manual_blocked", "needs_followup"}:
            continue
        task_id = f"task:{request_id or row.get('_log_ref')}"
        display = agent_inbox_display(row, employee_id, row_status)
        items.append(
            {
                "task_id": task_id,
                "status": row_status,
                "action_key": row.get("action_key") or "",
                "request_id": request_id,
                "trace_id": row.get("trace_id") or "",
                "event_id": row.get("event_id") or "",
                "doc_ref": row.get("doc_ref") or "",
                "log_ref": row.get("_log_ref") or "",
                "raw_url": action_raw_page_url(str(row.get("_log_ref") or ""), employee_id) if row.get("_log_ref") else "",
                "workflow_url": workflow_status_page_url(str(row.get("trace_id") or ""), employee_id) if row.get("trace_id") else "",
                "summary": row.get("summary") or row.get("message") or row_status,
                "display": display,
            }
        )
        if len(items) >= max(1, min(limit, 200)):
            break
    return {"ok": True, "employee_id": employee_id, "status": status, "open_count": len(items), "count": len(items), "items": items}


@app.get("/api/agents/boi-wiki/inbox")
async def api_agent_inbox(employee_id: str = Depends(current_employee), status: str = "open", limit: int = 50) -> dict[str, Any]:
    return agent_inbox_payload(employee_id, status=status, limit=limit)


async def complete_manual_handoff(req: ManualHandoffCompleteRequest, employee_id: str) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="user_confirmed=true is required")
    if not req.note.strip():
        raise HTTPException(status_code=400, detail="completion note is required")
    parent_request_id = req.task_id.removeprefix("task:")
    row = {
        "request_id": f"manual-completion-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
        "completion_for_request_id": parent_request_id,
        "employee_id": employee_id,
        "completed_by": req.completed_by or employee_id,
        "status": "manual_completed" if req.outcome == "completed" else req.outcome,
        "outcome": req.outcome,
        "note": req.note,
        "logged_at": now_iso(),
        "action_key": "manual.handoff.complete",
        "connector_kind": "manual",
    }
    appended = append_action_log_row(row)
    return {"ok": True, "item": appended}


@app.post("/api/agents/boi-wiki/manual-handoffs/complete")
async def api_manual_handoff_complete(req: ManualHandoffCompleteRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return await complete_manual_handoff(req, employee_id)


@app.post("/api/agents/boi-wiki/inbox/{task_id:path}/snooze")
async def api_agent_inbox_snooze(
    task_id: str,
    req: InboxTaskMutationRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="user_confirmed=true is required")
    row = append_action_log_row(
        {
            "request_id": f"inbox-snooze-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            "completion_for_request_id": task_id.removeprefix("task:"),
            "employee_id": employee_id,
            "status": "snoozed",
            "note": req.note,
            "logged_at": now_iso(),
            "action_key": "agent.inbox.snooze",
        }
    )
    append_rbac_audit(employee_id, "agent_inbox_snooze", {"task_id": task_id, "note": req.note})
    return {"ok": True, "item": row}


@app.post("/api/agents/boi-wiki/inbox/{task_id:path}/dismiss")
async def api_agent_inbox_dismiss(
    task_id: str,
    req: InboxTaskMutationRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="user_confirmed=true is required")
    row = append_action_log_row(
        {
            "request_id": f"inbox-dismiss-{datetime.now(KST).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}",
            "completion_for_request_id": task_id.removeprefix("task:"),
            "employee_id": employee_id,
            "status": "dismissed",
            "note": req.note,
            "logged_at": now_iso(),
            "action_key": "agent.inbox.dismiss",
        }
    )
    append_rbac_audit(employee_id, "agent_inbox_dismiss", {"task_id": task_id, "note": req.note})
    return {"ok": True, "item": row}


@app.post("/api/boi")
async def create_boi(req: BoiCreate, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
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
    title = str(source_meta.get("title") or "Untitled BoI")
    description = str(source_meta.get("description") or "Promoted BoI")
    source_refs = source_meta.get("source_refs") or [
        {"type": "boi", "ref": source_meta.get("boi_id"), "note": "source private BoI; user-confirmed sanitized copy"}
    ]
    body = (
        "# Summary\n\n"
        + f"이 문서는 Private BoI `{source_meta.get('boi_id')}`에서 사용자의 명시적 승인 후 {target_visibility} 공유본으로 게시되었습니다.\n\n"
        + "# Shared Content\n\n"
        + source["body"]
    )
    result = publish_promotion(
        employee_id=employee_id,
        target_visibility=target_visibility,
        team_id=req.team_id,
        title=title,
        description=description,
        classification=source_meta.get("classification", "internal"),
        boi_type=source_meta.get("type", "boi/reference"),
        body=body,
        tags=list(source_meta.get("tags") or []),
        source_refs=source_refs,
        source_local_id=str(source_meta.get("boi_id") or ""),
        source_sha256=hashlib.sha256(compose_markdown(source_meta, source["body"]).encode("utf-8")).hexdigest(),
        reviewer=req.reviewer,
        promotion_reason=req.promotion_reason,
        user_confirmed=req.user_confirmed,
        user_confirmed_at=req.user_confirmed_at,
    )
    result["source"] = source_meta.get("boi_id")
    return result


@app.post("/api/promotions/submit")
async def submit_promotion(req: PromotionSubmitRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return publish_promotion(
        employee_id=employee_id,
        target_visibility=req.target_visibility,
        team_id=req.team_id,
        title=req.title,
        description=req.description,
        body=req.body,
        boi_type=req.boi_type,
        classification=req.classification,
        tags=req.tags,
        source_refs=req.source_refs,
        source_local_id=req.source_local_id,
        source_sha256=req.source_sha256,
        reviewer=req.reviewer,
        promotion_reason=req.promotion_reason,
        user_confirmed=req.user_confirmed,
        user_confirmed_at=req.user_confirmed_at,
    )


@app.get("/api/promotions/{promotion_id}")
async def get_promotion_status(promotion_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.viewer")
    return read_promotion_report(promotion_id)


@app.post("/api/promotions/{promotion_id}/hotl")
async def update_promotion_hotl(
    promotion_id: str,
    req: HotlUpdateRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    return update_hotl_status(promotion_id, req, employee_id)


@app.post("/api/events/publish")
async def publish_event(req: EventPublishRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
    require_employee_binding_or_admin_override(
        employee_id,
        req.actor_employee_id,
        operation="event_publish",
        mismatch_detail="actor_employee_id must match the authenticated employee",
        reason=req.admin_override_reason,
    )
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
        "trace_id": req.trace_id or f"trace-{uuid.uuid4().hex}",
    }
    append_event_log(status="published", event=event)
    await publish_event_to_kafka(event)
    return {"ok": True, "topic": BOI_EVENTS_TOPIC, "event": event}


async def publish_event_to_kafka(event: dict[str, Any]) -> None:
    timeout = max(1.0, KAFKA_PUBLISH_TIMEOUT_SECONDS)
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode(),
        request_timeout_ms=int(timeout * 1000),
        retry_backoff_ms=500,
    )
    started = False
    try:
        await asyncio.wait_for(producer.start(), timeout=timeout)
        started = True
        await asyncio.wait_for(producer.send_and_wait(BOI_EVENTS_TOPIC, event), timeout=timeout)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Kafka publish failed: {type(exc).__name__}") from exc
    finally:
        if started:
            try:
                await asyncio.wait_for(producer.stop(), timeout=5)
            except Exception:
                pass


def unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def workflow_docs_for_registry(employee_id: str, doc_lookup: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if doc_lookup is not None:
        seen: set[str] = set()
        docs: list[dict[str, Any]] = []
        for doc in doc_lookup.values():
            metadata = doc.get("metadata") or {}
            workflow = metadata.get("workflow") or {}
            if not isinstance(workflow, dict) or not workflow.get("workflow_key"):
                continue
            uri = str(doc.get("uri") or doc.get("path") or id(doc))
            if uri in seen:
                continue
            seen.add(uri)
            docs.append(doc)
        return docs
    candidate_paths: list[Path] = []
    for root_name in ("public", "team"):
        root = DATA_ROOT / root_name
        if root.exists():
            candidate_paths.extend(sorted(root.rglob("*.md")))
    signature = file_signature(candidate_paths)
    if _WORKFLOW_DOCS_CACHE["signature"] != signature:
        docs = []
        for path in candidate_paths:
            try:
                doc = read_doc(path)
            except Exception:
                continue
            metadata = doc.get("metadata") or {}
            workflow = metadata.get("workflow") or {}
            if isinstance(workflow, dict) and workflow.get("workflow_key"):
                docs.append(doc)
        _WORKFLOW_DOCS_CACHE["signature"] = signature
        _WORKFLOW_DOCS_CACHE["docs"] = docs
    return [doc for doc in _WORKFLOW_DOCS_CACHE["docs"] if is_accessible(doc, employee_id)]


def normalize_workflow_stage(stage: dict[str, Any]) -> dict[str, Any]:
    stage_id = str(stage.get("id") or stage.get("sop_stage_id") or stage.get("stage_id") or "")
    entry_event = str(stage.get("entry_event") or "")
    raw_event_types = stage.get("event_types") or []
    if isinstance(raw_event_types, str):
        raw_event_types = [raw_event_types]
    event_types = unique_values([entry_event, *[str(item) for item in raw_event_types if item]])
    if not event_types and stage.get("event_type"):
        event_types = [str(stage.get("event_type"))]
    automated_actions = stage.get("automated_actions") or stage.get("actions") or []
    manual_actions = stage.get("manual_actions") or []
    if isinstance(automated_actions, str):
        automated_actions = [automated_actions]
    if isinstance(manual_actions, str):
        manual_actions = [manual_actions]
    stage_name = str(stage.get("name") or stage.get("stage") or stage_id or "SOP Stage")
    return {
        **stage,
        "id": stage_id,
        "sop_stage_id": stage_id,
        "stage": stage_name,
        "name": stage_name,
        "entry_event": entry_event or (event_types[0] if event_types else ""),
        "event_type": event_types[0] if event_types else "",
        "event_types": event_types,
        "emits_event": str(stage.get("emits_event") or ""),
        "next_stage": str(stage.get("next_stage") or ""),
        "automated_actions": [str(item) for item in automated_actions if item],
        "manual_actions": [str(item) for item in manual_actions if item],
    }


def build_workflow_definition(doc: dict[str, Any], employee_id: str) -> dict[str, Any] | None:
    metadata = doc.get("metadata") or {}
    workflow = metadata.get("workflow") or {}
    workflow_key = str(workflow.get("workflow_key") or "")
    if not workflow_key:
        return None
    stages = [normalize_workflow_stage(stage) for stage in workflow.get("stages") or [] if isinstance(stage, dict)]
    if not stages:
        return None
    sop_ref = str(metadata.get("boi_id") or "")
    sop_uri = str(doc.get("uri") or "")
    expected_event_types = unique_values([event_type for stage in stages for event_type in stage.get("event_types", [])])
    expected_actions = unique_values([action for stage in stages for action in stage.get("automated_actions", [])])
    expected_manual_actions = unique_values([action for stage in stages for action in stage.get("manual_actions", [])])
    entry_event = str(workflow.get("entry_event") or stages[0].get("entry_event") or stages[0].get("event_type") or "")
    return {
        "workflow_key": workflow_key,
        "name": workflow_key,
        "sop_ref": sop_ref,
        "sop_uri": sop_uri,
        "sop_title": str(metadata.get("title") or sop_ref),
        "sop_url": doc_url_for_ref(sop_ref, employee_id) if sop_ref else "",
        "entry_event": entry_event,
        "first_event_type": entry_event,
        "stages": stages,
        "expected_stages": stages,
        "expected_event_types": expected_event_types,
        "expected_actions": expected_actions,
        "expected_manual_actions": expected_manual_actions,
        "expected_next": [stage.get("event_type") for stage in stages[1:] if stage.get("event_type")],
        "doc": doc,
        "workflow": workflow,
    }


def workflow_registry(employee_id: str, doc_lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for doc in workflow_docs_for_registry(employee_id, doc_lookup=doc_lookup):
        definition = build_workflow_definition(doc, employee_id)
        if definition:
            registry.setdefault(str(definition["workflow_key"]), definition)
    return registry


def workflow_for_key(
    workflow_key: str,
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    return workflow_registry(employee_id, doc_lookup=doc_lookup).get(workflow_key)


def workflow_for_sop_ref(
    sop_ref: str,
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not sop_ref:
        return None
    for workflow in workflow_registry(employee_id, doc_lookup=doc_lookup).values():
        if workflow.get("sop_ref") == sop_ref or workflow.get("sop_uri") == sop_ref:
            return workflow
    sop_doc = doc_from_lookup(sop_ref, doc_lookup)
    if sop_doc is None and doc_lookup is None:
        sop_doc = find_doc_by_id(sop_ref, employee_id)
    return build_workflow_definition(sop_doc, employee_id) if sop_doc else None


def stage_for_event_type(workflow: dict[str, Any], event_type: str, event_def: dict[str, Any] | None = None) -> dict[str, Any] | None:
    event_def = event_def or {}
    stage_id = str(event_def.get("sop_stage_id") or "")
    stages = workflow.get("stages") or workflow.get("expected_stages") or []
    if stage_id:
        for stage in stages:
            if str(stage.get("sop_stage_id") or stage.get("id") or "") == stage_id:
                return stage
    for stage in stages:
        event_types = [str(item) for item in stage.get("event_types") or []]
        if event_type in event_types or event_type == str(stage.get("entry_event") or "") or event_type == str(stage.get("emits_event") or ""):
            return stage
    return None


def workflow_for_event_type(
    event_type: str,
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    event_def = get_event_type(event_type) or {}
    workflow = workflow_for_sop_ref(str(event_def.get("sop_ref") or ""), employee_id, doc_lookup=doc_lookup)
    if workflow is None:
        for candidate in workflow_registry(employee_id, doc_lookup=doc_lookup).values():
            if stage_for_event_type(candidate, event_type, event_def):
                workflow = candidate
                break
    stage = stage_for_event_type(workflow, event_type, event_def) if workflow else None
    return workflow, stage, event_def


def workflow_context(
    workflow_key: str,
    employee_id: str,
    trace_id: str | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
    include_action_details: bool = True,
) -> dict[str, Any]:
    workflow = workflow_for_key(workflow_key, employee_id, doc_lookup=doc_lookup)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow not found: {workflow_key}")
    context = dict(workflow)
    context.pop("doc", None)
    context["action_details"] = (
        action_details_for_keys(context.get("expected_actions") or [], employee_id, doc_lookup=doc_lookup)
        if include_action_details
        else []
    )
    context["manual_action_details"] = (
        action_details_for_keys(context.get("expected_manual_actions") or [], employee_id, doc_lookup=doc_lookup)
        if include_action_details
        else []
    )
    if trace_id:
        context["status_url"] = workflow_status_api_url_for_key(workflow_key, trace_id, employee_id)
        context["status_page_url"] = workflow_status_page_url_for_key(workflow_key, trace_id, employee_id)
        context["status_raw_url"] = workflow_status_raw_url_for_key(workflow_key, trace_id, employee_id)
    return context


def simulation_trace_docs(employee_id: str, trace_id: str, *, limit: int = 24) -> list[dict[str, Any]]:
    if not trace_id:
        return []
    root = DATA_ROOT / "private" / employee_id
    if not root.exists():
        return []
    docs: list[dict[str, Any]] = []
    paths = sorted(root.glob("boi-private-*.md"), key=lambda item: item.stat().st_mtime_ns if item.exists() else 0, reverse=True)
    for path in paths:
        if len(docs) >= limit:
            break
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        if trace_id not in text:
            continue
        try:
            docs.append(read_doc(path))
        except Exception:
            continue
    return list(reversed(docs))


def simulation_context_docs(
    employee_id: str,
    *,
    action: dict[str, Any],
    event_type: str,
    trace_id: str,
    sop_ref: str = "",
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(doc: dict[str, Any] | None) -> None:
        if not doc:
            return
        key = str(doc.get("path") or doc.get("uri") or doc["metadata"].get("boi_id") or id(doc))
        if key in seen:
            return
        seen.add(key)
        docs.append(doc)

    for doc in workflow_docs_for_registry(employee_id):
        add(doc)
    for ref in [
        str(action.get("doc_ref") or ""),
        f"/public/event-types/{event_type}.md" if event_type else "",
        sop_ref,
        str(action.get("sop_ref") or ""),
    ]:
        if ref:
            add(find_doc_by_id(ref, employee_id))
    for doc in simulation_trace_docs(employee_id, trace_id):
        add(doc)
    return docs


def workflow_sop_context(employee_id: str, doc_lookup: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    context = workflow_context("equipment-anomaly", employee_id, doc_lookup=doc_lookup)
    return {
        "sop_ref": context["sop_ref"],
        "sop_uri": context["sop_uri"],
        "sop_title": context["sop_title"],
        "sop_url": context["sop_url"],
    }


def action_details_for_keys(
    action_keys: list[str],
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    catalog = {str(action.get("action_key")): action for action in load_action_catalog()}
    details = []
    for action_key in unique_values(action_keys):
        action = catalog.get(action_key)
        if not action:
            details.append({"action_key": action_key, "missing": True})
            continue
        details.append(
            {
                "action_key": action_key,
                "name_ko": action.get("name_ko"),
                "connector_kind": action.get("connector_kind"),
                "execution_mode": action.get("execution_mode"),
                "risk_level": action.get("risk_level"),
                "approval_required": bool(action.get("approval_required")),
                "doc_ref": action.get("doc_ref"),
                "doc_uri": action_doc_uri(action, employee_id, doc_lookup=doc_lookup),
                "requires_manual_action": action.get("requires_manual_action"),
                "simulation": bool(action.get("simulation_mode")),
                "simulation_mode": action.get("simulation_mode"),
                "simulation_label": action.get("simulation_label") or ("SIMULATED" if action.get("simulation_mode") else ""),
                "simulation_notice": action.get("simulation_notice"),
                "real_system_status": action.get("real_system_status"),
                "simulated_system": action.get("simulated_system"),
            }
        )
    return details


def action_details_markdown(details: list[dict[str, Any]]) -> str:
    rows = []
    for detail in details:
        if detail.get("missing"):
            rows.append(f"- `{detail.get('action_key')}`: catalog entry missing")
            continue
        manual_note = f" / requires_manual_action=`{detail.get('requires_manual_action')}`" if detail.get("requires_manual_action") else ""
        action_label = str(detail.get("name_ko") or detail.get("action_key"))
        action_ref = f"[{action_label}]({detail.get('doc_uri')})" if detail.get("doc_uri") else action_label
        rows.append(
            "- "
            + f"`{detail.get('action_key')}`: {action_ref} "
            + f"/ connector={detail.get('connector_kind')} "
            + f"/ risk={detail.get('risk_level')} "
            + f"/ approval_required={detail.get('approval_required')} "
            + manual_note
        )
    return "\n".join(rows) if rows else "- 등록된 Action 없음"


def equipment_workflow_context(
    employee_id: str,
    trace_id: str | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    context = workflow_context("equipment-anomaly", employee_id, trace_id=trace_id, doc_lookup=doc_lookup)
    if trace_id:
        context["status_url"] = workflow_status_api_url(trace_id, employee_id)
        context["status_page_url"] = workflow_status_page_url(trace_id, employee_id)
        context["status_raw_url"] = workflow_status_raw_url(trace_id, employee_id)
    return context


def workflow_trace_graph(
    *,
    context: dict[str, Any],
    events: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    generated_docs: list[dict[str, Any]],
    employee_id: str,
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def add_node(node_id: str, node_type: str, label: str, url: str = "") -> None:
        if not node_id:
            return
        nodes.setdefault(node_id, {"id": node_id, "type": node_type, "label": label or node_id, "url": url})

    def add_edge(source: str, target: str, label: str) -> None:
        if source and target:
            edges.append({"source": source, "target": target, "label": label})

    sop_id = f"sop:{context.get('sop_ref')}"
    add_node(sop_id, "sop", str(context.get("sop_ref") or "SOP"), str(context.get("sop_url") or ""))
    for stage in context.get("expected_stages") or []:
        stage_id = str(stage.get("sop_stage_id") or stage.get("id") or stage.get("stage") or "stage")
        event_types = [str(item) for item in (stage.get("event_types") or [stage.get("event_type")]) if item]
        for event_type in event_types:
            event_node = f"event_type:{event_type}"
            add_node(event_node, "event_type", event_label(event_type), f"/event-types/{event_type}?" + urlencode({"employee_id": employee_id}))
            add_edge(sop_id, event_node, stage_id)
            for action_key in stage.get("automated_actions") or []:
                action_node = f"action:{action_key}"
                action = action_catalog_by_key().get(str(action_key), {})
                add_node(action_node, "action", str(action_key), doc_url_for_ref(str(action.get("doc_ref") or ""), employee_id) if action.get("doc_ref") else "")
                add_edge(event_node, action_node, "recommended_action")
            for action_key in stage.get("manual_actions") or []:
                action_node = f"manual:{action_key}"
                action = action_catalog_by_key().get(str(action_key), {})
                add_node(action_node, "manual_action", str(action_key), doc_url_for_ref(str(action.get("doc_ref") or ""), employee_id) if action.get("doc_ref") else "")
                add_edge(event_node, action_node, "recommended_manual_action")

    event_node_by_id: dict[str, str] = {}
    for event in events:
        event_id = str(event.get("event_id") or "")
        event_type = str(event.get("event_type") or "")
        if event_type:
            event_type_node = f"event_type:{event_type}"
            add_node(event_type_node, "event_type", event_label(event_type), f"/event-types/{event_type}?" + urlencode({"employee_id": employee_id}))
        if event_id:
            event_node = f"event:{event_id}"
            event_node_by_id[event_id] = event_node
            add_node(event_node, "event", event.get("payload_title") or event_id, event_filter_url(event_id, employee_id))
            if event_type:
                add_edge(f"event_type:{event_type}", event_node, "observed")

    catalog = action_catalog_by_key()
    for action in actions:
        action_key = str(action.get("action_key") or "")
        action_node = f"action:{action_key}"
        catalog_item = catalog.get(action_key, {})
        doc_ref = str(action.get("doc_ref") or catalog_item.get("doc_ref") or "")
        add_node(action_node, "action", action_key, doc_url_for_ref(doc_ref, employee_id) if doc_ref else "")
        source_event = event_node_by_id.get(str(action.get("event_id") or ""))
        if source_event:
            add_edge(source_event, action_node, str(action.get("status") or "invoked"))

    for doc in generated_docs:
        boi_id = str(doc.get("boi_id") or "")
        if not boi_id:
            continue
        doc_node = f"boi:{boi_id}"
        add_node(doc_node, "boi", boi_id, str(doc.get("doc_url") or ""))
        source_event = event_node_by_id.get(str(doc.get("event_id") or ""))
        if source_event:
            add_edge(source_event, doc_node, "generated_boi")

    deduped_edges = sorted({(edge["source"], edge["target"], edge["label"]) for edge in edges})
    rendered_edges = [{"source": source, "target": target, "label": label} for source, target, label in deduped_edges]
    rendered_nodes = sorted(nodes.values(), key=lambda node: (str(node["type"]), str(node["id"])))
    return {
        "node_count": len(rendered_nodes),
        "edge_count": len(rendered_edges),
        "nodes": rendered_nodes,
        "edges": rendered_edges,
        "outgoing_by_source": {},
        "incoming_by_target": {},
    }


def compact_status_text(value: Any, limit: int = 320) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip() + " ..."


def compact_workflow_event_row(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else row.get("payload")
    compact: dict[str, Any] = {}
    for key in [
        "_log_ref",
        "logged_at",
        "event_type",
        "event_id",
        "trace_id",
        "event_label",
        "payload_title",
        "actor_employee_id",
        "employee_id",
    ]:
        if key in row:
            compact[key] = row[key]
    if isinstance(payload, dict):
        compact["result"] = {"payload": payload}
    elif result:
        compact["result"] = {
            key: result[key]
            for key in ["status", "boi_id", "boi_uri", "request_id"]
            if key in result
        }
    return compact


def compact_workflow_action_log_row(row: dict[str, Any]) -> dict[str, Any]:
    result = row.get("result") if isinstance(row.get("result"), dict) else {}
    simulation_agent = result.get("simulation_agent") if isinstance(result.get("simulation_agent"), dict) else {}
    coverage_report = simulation_agent.get("coverage_report") if isinstance(simulation_agent.get("coverage_report"), dict) else {}
    context_pack = simulation_agent.get("context_pack") if isinstance(simulation_agent.get("context_pack"), dict) else {}
    agent_meta = simulation_agent.get("agent") if isinstance(simulation_agent.get("agent"), dict) else {}

    coverage_score = row.get("coverage_score")
    if coverage_score is None:
        coverage_score = result.get("coverage_score")
    if coverage_score is None:
        coverage_score = coverage_report.get("coverage_score")

    missing_context = row.get("missing_context") or result.get("missing_context") or coverage_report.get("missing_context") or []
    used_docs = row.get("used_docs") or result.get("used_docs") or context_pack.get("documents") or []
    evidence_packets = (
        row.get("evidence_packets")
        or result.get("evidence_packets")
        or simulation_agent.get("evidence_packets")
        or context_pack.get("evidence_packets")
        or []
    )

    simulation = bool(row.get("simulation") or result.get("simulation"))
    if not simulation and (simulation_agent or row.get("simulation_label") or result.get("simulation_label")):
        simulation = True

    compact: dict[str, Any] = {}
    for key in [
        "_log_ref",
        "logged_at",
        "action_key",
        "status",
        "request_id",
        "employee_id",
        "event_id",
        "event_type",
        "trace_id",
        "connector_kind",
        "doc_ref",
        "boi_id",
        "summary",
        "simulation_label",
        "simulation_notice",
        "real_system_status",
        "simulated_system",
    ]:
        if key in row:
            compact[key] = row[key]

    compact["simulation"] = simulation
    if coverage_score is not None:
        compact["coverage_score"] = coverage_score
    if missing_context:
        compact["missing_context"] = missing_context
    if used_docs:
        compact["used_docs"] = used_docs
    if evidence_packets:
        compact["evidence_packets"] = evidence_packets
    if agent_meta.get("retrieval_rounds") is not None:
        compact["retrieval_rounds"] = agent_meta.get("retrieval_rounds")

    compact["result"] = {
        key: value
        for key, value in {
            "ok": result.get("ok"),
            "status": result.get("status"),
            "request_id": result.get("request_id"),
            "action_key": result.get("action_key"),
            "simulation": simulation,
            "simulation_label": result.get("simulation_label") or row.get("simulation_label"),
            "coverage_score": coverage_score,
            "langflow_renderer_status": result.get("langflow_renderer_status"),
            "flow_id": result.get("flow_id"),
            "flow_name": result.get("flow_name"),
            "message": compact_status_text(str(result.get("message") or result.get("summary") or ""), 320)
            if result.get("message") or result.get("summary")
            else "",
        }.items()
        if value not in (None, "")
    }
    return compact


def workflow_status_payload(
    workflow_key: str,
    trace_id: str,
    employee_id: str,
    graph_scope: str = "trace",
    compact: bool = False,
) -> dict[str, Any]:
    docs = [] if compact else (accessible_docs(employee_id) if graph_scope == "global" else workflow_docs_for_registry(employee_id))
    context = workflow_context(workflow_key, employee_id, trace_id=trace_id)
    raw_events = filtered_event_log_rows(trace_id=trace_id)
    events = [compact_workflow_event_row(row) for row in raw_events] if compact else raw_events
    event_ids = {str(row.get("event_id")) for row in events if row.get("event_id")}
    action_logs = []
    for row in trace_action_log_rows(trace_id, event_ids=event_ids, limit=500):
        if not action_log_visible_to_employee(row, employee_id):
            continue
        action_logs.append(compact_workflow_action_log_row(row) if compact else dict(row))
    generated_doc_by_id: dict[str, dict[str, Any]] = {}
    for row in raw_events:
        result = row.get("result") or {}
        boi_id = str(result.get("boi_id") or "")
        if boi_id:
            item = {
                "boi_id": boi_id,
                "boi_uri": result.get("boi_uri"),
                "doc_url": doc_url_for_ref(boi_id, employee_id),
                "event_id": row.get("event_id"),
                "event_type": row.get("event_type"),
            }
            existing = generated_doc_by_id.get(boi_id)
            if not existing or (item.get("doc_url") and not existing.get("doc_url")):
                generated_doc_by_id[boi_id] = item
    generated_docs = list(generated_doc_by_id.values())
    if compact:
        relation_graph = {
            "node_count": 0,
            "edge_count": 0,
            "nodes": [],
            "edges": [],
            "outgoing_by_source": {},
            "incoming_by_target": {},
            "omitted": "compact workflow status omits relation_graph; use /status/raw?section=graph for raw graph data",
        }
    else:
        relation_graph = (
            cached_okf_graph_for_docs(docs, employee_id)
            if graph_scope == "global"
            else workflow_trace_graph(context=context, events=events, actions=action_logs, generated_docs=generated_docs, employee_id=employee_id)
        )
    return {
        "ok": True,
        "compact": compact,
        "workflow_key": workflow_key,
        "trace_id": trace_id,
        "sop_ref": context["sop_ref"],
        "sop_uri": context["sop_uri"],
        "sop_url": context["sop_url"],
        "status_url": workflow_status_api_url_for_key(workflow_key, trace_id, employee_id),
        "status_page_url": workflow_status_page_url_for_key(workflow_key, trace_id, employee_id),
        "status_raw_url": workflow_status_raw_url_for_key(workflow_key, trace_id, employee_id),
        "expected_event_types": context["expected_event_types"],
        "expected_stages": context["expected_stages"],
        "expected_actions": context["expected_actions"],
        "manual_handoffs": context["expected_manual_actions"],
        "expected_manual_actions": context["expected_manual_actions"],
        "action_details": context["action_details"],
        "manual_action_details": context["manual_action_details"],
        "events": events,
        "actions": action_logs,
        "generated_docs": generated_docs,
        "generated_boi_refs": generated_docs,
        "relation_graph": relation_graph,
        "approval_required_actions": [row for row in action_logs if row.get("status") == "approval_required"],
    }


def equipment_anomaly_status_payload(
    trace_id: str,
    employee_id: str,
    graph_scope: str = "trace",
    compact: bool = False,
) -> dict[str, Any]:
    return workflow_status_payload("equipment-anomaly", trace_id, employee_id, graph_scope=graph_scope, compact=compact)


def workflow_status_action_rows(
    payload: dict[str, Any],
    employee_id: str,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    catalog = action_catalog_by_key()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_row(
        *,
        action_key: str,
        status: str,
        connector_kind: str = "",
        doc_ref: str = "",
        request_id: str = "",
        event_id: str = "",
        raw_log_ref: str = "",
        source: str = "",
        boi_url: str = "",
        simulation: bool | None = None,
        simulation_label: str = "",
        simulation_notice: str = "",
        real_system_status: str = "",
        simulated_system: str = "",
        retrieval_rounds: Any = "",
        coverage_score: Any = "",
        missing_context: Any = None,
        used_docs: Any = None,
        evidence_packets: Any = None,
    ) -> None:
        if not action_key:
            return
        catalog_item = catalog.get(action_key, {})
        effective_doc_ref = doc_ref or str(catalog_item.get("doc_ref") or "")
        if not raw_log_ref and request_id:
            raw_row = find_action_log_row_by_request_id(request_id, employee_id)
            raw_log_ref = str((raw_row or {}).get("_log_ref") or "")
        key = (action_key, request_id, event_id)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "action_key": action_key,
                "connector_kind": connector_kind or str(catalog_item.get("connector_kind") or ""),
                "execution_mode": catalog_item.get("execution_mode"),
                "risk_level": catalog_item.get("risk_level"),
                "approval_required": bool(catalog_item.get("approval_required")),
                "status": status or "unknown",
                "doc_ref": effective_doc_ref,
                "doc_url": doc_url_for_ref(effective_doc_ref, employee_id) if effective_doc_ref else "",
                "request_id": request_id,
                "event_id": event_id,
                "event_url": event_filter_url(event_id, employee_id) if event_id else "",
                "raw_log_ref": raw_log_ref,
                "raw_url": action_raw_page_url(raw_log_ref, employee_id) if raw_log_ref else "",
                "raw_api_url": action_raw_api_url(raw_log_ref, employee_id) if raw_log_ref else "",
                "source": source,
                "boi_url": boi_url,
                "simulation": bool(simulation) if simulation is not None else bool(catalog_item.get("simulation_mode")),
                "simulation_label": simulation_label or str(catalog_item.get("simulation_label") or ("SIMULATED" if catalog_item.get("simulation_mode") else "")),
                "simulation_notice": simulation_notice or str(catalog_item.get("simulation_notice") or ""),
                "real_system_status": real_system_status or str(catalog_item.get("real_system_status") or ""),
                "simulated_system": simulated_system or str(catalog_item.get("simulated_system") or ""),
                "retrieval_rounds": retrieval_rounds or "",
                "coverage_score": coverage_score if coverage_score is not None else "",
                "missing_context": missing_context or [],
                "used_docs": used_docs or [],
                "evidence_packets": evidence_packets or [],
            }
        )

    for action in payload.get("actions") or []:
        result = action.get("result") if isinstance(action.get("result"), dict) else {}
        add_row(
            action_key=str(action.get("action_key") or ""),
            status=str(action.get("status") or result.get("status") or "logged"),
            connector_kind=str(action.get("connector_kind") or action.get("action_type") or ""),
            doc_ref=str(action.get("doc_ref") or ""),
            request_id=str(action.get("request_id") or ""),
            event_id=str(action.get("event_id") or ""),
            raw_log_ref=str(action.get("_log_ref") or ""),
            source="action_log",
            boi_url=doc_url_if_resolvable(str(action.get("boi_id") or ""), employee_id, doc_lookup=doc_lookup) if action.get("boi_id") else "",
            simulation=bool(action.get("simulation") or result.get("simulation")),
            simulation_label=str(action.get("simulation_label") or result.get("simulation_label") or ""),
            simulation_notice=str(action.get("simulation_notice") or result.get("simulation_notice") or ""),
            real_system_status=str(action.get("real_system_status") or result.get("real_system_status") or ""),
            simulated_system=str(action.get("simulated_system") or result.get("simulated_system") or ""),
            retrieval_rounds=action.get("retrieval_rounds") or result.get("retrieval_rounds") or ((result.get("simulation_agent") or {}).get("agent") or {}).get("retrieval_rounds"),
            coverage_score=action.get("coverage_score") if action.get("coverage_score") is not None else result.get("coverage_score"),
            missing_context=action.get("missing_context") or result.get("missing_context") or ((result.get("simulation_agent") or {}).get("coverage_report") or {}).get("missing_context"),
            used_docs=action.get("used_docs") or result.get("used_docs") or ((result.get("simulation_agent") or {}).get("context_pack") or {}).get("documents"),
            evidence_packets=action.get("evidence_packets")
            or result.get("evidence_packets")
            or ((result.get("simulation_agent") or {}).get("evidence_packets"))
            or (((result.get("simulation_agent") or {}).get("context_pack") or {}).get("evidence_packets")),
        )
    for event in payload.get("events") or []:
        result = event.get("result") if isinstance(event.get("result"), dict) else {}
        summary = event_dispatch_summary(result, employee_id, doc_lookup=doc_lookup)
        if not summary:
            continue
        for action in summary.get("actions") or []:
            add_row(
                action_key=str(action.get("action_key") or ""),
                status=str(action.get("status") or ""),
                connector_kind=str(action.get("connector_kind") or ""),
                doc_ref=str(action.get("doc_ref") or ""),
                request_id=str(action.get("request_id") or ""),
                event_id=str(event.get("event_id") or ""),
                source="event_dispatch",
                boi_url=str(action.get("boi_url") or ""),
                simulation=bool(action.get("simulation")),
                simulation_label=str(action.get("simulation_label") or ""),
                simulation_notice=str(action.get("simulation_notice") or ""),
                real_system_status=str(action.get("real_system_status") or ""),
                simulated_system=str(action.get("simulated_system") or ""),
                retrieval_rounds=action.get("retrieval_rounds") or "",
                coverage_score=action.get("coverage_score") if action.get("coverage_score") is not None else "",
                missing_context=action.get("missing_context") or [],
                used_docs=action.get("used_docs") or [],
                evidence_packets=action.get("evidence_packets") or [],
            )
    for detail in payload.get("action_details") or []:
        add_row(
            action_key=str(detail.get("action_key") or ""),
            status="expected",
            connector_kind=str(detail.get("connector_kind") or ""),
            doc_ref=str(detail.get("doc_ref") or ""),
            source="expected",
            simulation=bool(detail.get("simulation")),
            simulation_label=str(detail.get("simulation_label") or ""),
            simulation_notice=str(detail.get("simulation_notice") or ""),
            real_system_status=str(detail.get("real_system_status") or ""),
            simulated_system=str(detail.get("simulated_system") or ""),
        )
    return rows


def workflow_status_template_context(request: Request, payload: dict[str, Any], employee_id: str) -> dict[str, Any]:
    doc_lookup = build_doc_lookup(accessible_docs(employee_id))
    events_by_type: dict[str, list[dict[str, Any]]] = {}
    for event in payload.get("events") or []:
        events_by_type.setdefault(str(event.get("event_type") or ""), []).append(event)
    timeline = []
    for stage in payload.get("expected_stages") or []:
        event_types = [str(item) for item in (stage.get("event_types") or [stage.get("event_type")]) if item]
        stage_events = sorted(
            [event for event_type in event_types for event in events_by_type.get(event_type, [])],
            key=lambda row: str(row.get("logged_at") or ""),
        )
        timeline.append(
            {
                "stage": stage.get("stage"),
                "sop_stage_id": stage.get("sop_stage_id"),
                "event_type": event_types[0] if event_types else "",
                "event_types": event_types,
                "event_label": event_label(event_types[0]) if event_types else "",
                "event_type_url": f"/event-types/{event_types[0]}?" + urlencode({"employee_id": employee_id}) if event_types else "",
                "event_type_links": [
                    {
                        "event_type": event_type,
                        "label": event_label(event_type),
                        "url": f"/event-types/{event_type}?" + urlencode({"employee_id": employee_id}),
                    }
                    for event_type in event_types
                ],
                "events": [
                    {
                        "event_id": event.get("event_id"),
                        "status": event.get("status"),
                        "title": event.get("payload_title") or event.get("event_id"),
                        "logged_at": event.get("logged_at"),
                        "url": event_filter_url(str(event.get("event_id") or ""), employee_id) if event.get("event_id") else "",
                        "trace_url": trace_events_url(str(event.get("trace_id") or ""), employee_id) if event.get("trace_id") else "",
                        "workflow_url": str(payload.get("status_page_url") or "") if event.get("trace_id") else "",
                    }
                    for event in stage_events
                ],
            }
        )
    action_rows = workflow_status_action_rows(payload, employee_id, doc_lookup=doc_lookup)
    manual_rows = []
    for detail in payload.get("manual_action_details") or []:
        doc_ref = str(detail.get("doc_ref") or "")
        manual_rows.append(
            {
                **detail,
                "status": "manual_required" if detail.get("approval_required") else "handoff_needed",
                "doc_url": doc_url_for_ref(doc_ref, employee_id) if doc_ref else "",
            }
        )
    graph = payload.get("relation_graph") or {}
    nodes_by_id = {str(node.get("id") or ""): node for node in graph.get("nodes", []) if isinstance(node, dict)}
    graph_edges = []
    for edge in graph.get("edges", [])[:80]:
        if not isinstance(edge, dict):
            continue
        source_node = nodes_by_id.get(str(edge.get("source") or ""), {})
        target_node = nodes_by_id.get(str(edge.get("target") or ""), {})
        graph_edges.append(
            {
                **edge,
                "source_url": source_node.get("url") or "",
                "target_url": target_node.get("url") or "",
            }
        )
    return {
        "request": request,
        "employee_id": employee_id,
        "shell": app_shell_context(
            request,
            employee_id,
            active_nav="sops",
            title="Workflow Status",
            description="Trace가 SOP, Event, Action, Manual Handoff, Generated BoI로 어떻게 이어졌는지 확인합니다.",
            page_actions=[
                {"label": "Trace Event Stream", "href": trace_events_url(str(payload.get("trace_id") or ""), employee_id), "kind": "secondary"},
                {"label": "SOP 보기", "href": str(payload.get("sop_url") or "#"), "kind": "secondary"},
                {
                    "label": "JSON 원문 API",
                    "href": payload.get("status_url") + ("&format=json" if "?" in str(payload.get("status_url") or "") else "?format=json"),
                    "kind": "secondary",
                },
            ],
        ),
        "trace_id": payload.get("trace_id"),
        "payload": payload,
        "summary": {
            "event_count": len(payload.get("events") or []),
            "action_count": len(action_rows),
            "generated_doc_count": len(payload.get("generated_docs") or []),
            "manual_count": len(manual_rows),
            "approval_count": len(payload.get("approval_required_actions") or []),
            "status": "approval_required" if payload.get("approval_required_actions") else "in_progress",
        },
        "timeline": timeline,
        "action_rows": action_rows,
        "manual_rows": manual_rows,
        "approval_rows": payload.get("approval_required_actions") or [],
        "generated_docs": payload.get("generated_docs") or [],
        "graph": graph,
        "graph_edges": graph_edges,
        "api_json_url": payload.get("status_url") + ("&format=json" if "?" in str(payload.get("status_url") or "") else "?format=json"),
        "raw_base_url": payload.get("status_raw_url"),
        "events_url": trace_events_url(str(payload.get("trace_id") or ""), employee_id),
    }


def workflow_status_should_render_html(request: Request, response_format: str) -> bool:
    if response_format == "html":
        return True
    if response_format == "json":
        return False
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept


WORKFLOW_START_CONTROL_KEYS = {
    "payload",
    "event_type",
    "actor_employee_id",
    "owner",
    "source_refs",
    "trace_id",
    "user_confirmed",
    "user_confirmed_at",
}


def require_workflow_start_confirmation(raw: dict[str, Any]) -> None:
    if not bool(raw.get("user_confirmed")):
        raise HTTPException(status_code=400, detail="user_confirmed=true is required to start workflow")


async def start_workflow_from_data(
    workflow_key: str,
    raw: dict[str, Any],
    employee_id: str,
) -> dict[str, Any]:
    workflow = workflow_context(workflow_key, employee_id, include_action_details=False)
    raw_payload = raw.get("payload")
    payload = dict(raw_payload) if isinstance(raw_payload, dict) else {key: value for key, value in raw.items() if key not in WORKFLOW_START_CONTROL_KEYS}
    owner = str(raw.get("actor_employee_id") or raw.get("owner") or payload.get("owner") or employee_id)
    event_type = str(raw.get("event_type") or workflow.get("entry_event") or workflow.get("first_event_type") or "")
    if not event_type:
        raise HTTPException(status_code=400, detail=f"Workflow has no entry event: {workflow_key}")
    payload.setdefault("workflow", workflow_key)
    payload.setdefault("owner", owner)
    result = await publish_event(
        EventPublishRequest(
            event_type=event_type,
            actor_employee_id=employee_id,
            payload=payload,
            source_refs=raw.get("source_refs") or [{"type": "workflow", "ref": workflow_key, "sop_ref": workflow.get("sop_ref")}],
            trace_id=raw.get("trace_id"),
        ),
        employee_id=employee_id,
    )
    trace_id = str(result["event"].get("trace_id") or "")
    workflow = workflow_context(workflow_key, employee_id, trace_id=trace_id, include_action_details=False)
    workflow.update(
        {
            "workflow_key": workflow_key,
            "name": workflow_key,
            "first_event_type": event_type,
        }
    )
    return {
        "ok": True,
        "workflow": workflow,
        "topic": result["topic"],
        "event": result["event"],
    }


@app.post("/api/workflows/{workflow_key}/start")
async def start_workflow(workflow_key: str, request: Request, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
    try:
        raw = await request.json()
    except Exception:
        raw = {}
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="Workflow start body must be a JSON object")
    require_workflow_start_confirmation(raw)
    return await start_workflow_from_data(workflow_key, raw, employee_id)


@app.post("/api/workflows/demo/equipment-anomaly/start")
async def start_equipment_anomaly_demo(req: EquipmentAnomalyStartRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
    require_workflow_start_confirmation(req.model_dump())
    owner = req.owner or employee_id
    result = await start_workflow_from_data(
        "equipment-anomaly",
        {
            "actor_employee_id": owner,
            "payload": {
                "title": req.title,
                "equipment_id": req.equipment_id,
                "lot_id": req.lot_id,
                "wafer_id": req.wafer_id,
                "alarm_code": req.alarm_code,
                "owner": owner,
            },
            "source_refs": [{"type": "demo-workflow", "ref": "equipment-anomaly"}],
        },
        employee_id,
    )
    trace_id = str(result["event"].get("trace_id") or "")
    result["workflow"]["status_url"] = workflow_status_api_url(trace_id, employee_id)
    result["workflow"]["status_page_url"] = workflow_status_page_url(trace_id, employee_id)
    result["workflow"]["status_raw_url"] = workflow_status_raw_url(trace_id, employee_id)
    return result


@app.get("/api/workflows/{workflow_key}/status")
async def generic_workflow_status(
    workflow_key: str,
    request: Request,
    trace_id: str,
    employee_id: str = Depends(current_employee),
    format: str = "auto",
    graph_scope: str = "trace",
    compact: bool = False,
) -> Any:
    payload = workflow_status_payload(workflow_key, trace_id, employee_id, graph_scope=graph_scope, compact=compact)
    if workflow_status_should_render_html(request, format):
        return templates.TemplateResponse("workflow_status.html", workflow_status_template_context(request, payload, employee_id))
    return payload


@app.get("/workflows/{workflow_key}/status", response_class=HTMLResponse)
async def generic_workflow_status_page(
    workflow_key: str,
    request: Request,
    trace_id: str,
    employee_id: str = Depends(current_employee),
) -> HTMLResponse:
    payload = workflow_status_payload(workflow_key, trace_id, employee_id)
    return templates.TemplateResponse("workflow_status.html", workflow_status_template_context(request, payload, employee_id))


@app.get("/api/workflows/{workflow_key}/status/raw")
async def generic_workflow_status_raw(
    workflow_key: str,
    trace_id: str,
    employee_id: str = Depends(current_employee),
    section: Literal["events", "actions", "graph", "all"] = "all",
) -> dict[str, Any]:
    payload = workflow_status_payload(workflow_key, trace_id, employee_id)
    section_map = {
        "events": payload["events"],
        "actions": payload["actions"],
        "graph": payload["relation_graph"],
        "all": payload,
    }
    return {"ok": True, "workflow_key": workflow_key, "trace_id": trace_id, "section": section, "data": section_map[section]}


@app.get("/api/workflows/demo/equipment-anomaly/status")
async def equipment_anomaly_status(
    request: Request,
    trace_id: str,
    employee_id: str = Depends(current_employee),
    format: str = "auto",
    graph_scope: str = "trace",
    compact: bool = False,
) -> Any:
    payload = equipment_anomaly_status_payload(trace_id, employee_id, graph_scope=graph_scope, compact=compact)
    if workflow_status_should_render_html(request, format):
        return templates.TemplateResponse("workflow_status.html", workflow_status_template_context(request, payload, employee_id))
    return payload


@app.get("/workflows/demo/equipment-anomaly/status", response_class=HTMLResponse)
async def equipment_anomaly_status_page(
    request: Request,
    trace_id: str,
    employee_id: str = Depends(current_employee),
) -> HTMLResponse:
    payload = equipment_anomaly_status_payload(trace_id, employee_id)
    return templates.TemplateResponse("workflow_status.html", workflow_status_template_context(request, payload, employee_id))


@app.get("/api/workflows/demo/equipment-anomaly/status/raw")
async def equipment_anomaly_status_raw(
    trace_id: str,
    employee_id: str = Depends(current_employee),
    section: Literal["events", "actions", "graph", "all"] = "all",
) -> dict[str, Any]:
    payload = equipment_anomaly_status_payload(trace_id, employee_id)
    section_map = {
        "events": payload["events"],
        "actions": payload["actions"],
        "graph": payload["relation_graph"],
        "all": payload,
    }
    return {"ok": True, "trace_id": trace_id, "section": section, "data": section_map[section]}


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
    await publish_event_to_kafka(event)
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


def dispatch_result_payload(dispatch_result: dict[str, Any]) -> dict[str, Any]:
    if isinstance(dispatch_result.get("dispatch_result"), dict):
        return dispatch_result["dispatch_result"]
    return dispatch_result


def dispatch_generated_boi_id(dispatch_result: dict[str, Any]) -> str:
    dispatch = dispatch_result_payload(dispatch_result)
    if dispatch.get("boi_id"):
        return str(dispatch["boi_id"])
    for row in dispatch.get("results") or []:
        result = row.get("result") if isinstance(row, dict) else None
        if not isinstance(result, dict):
            continue
        boi_id = result_boi_id(result)
        if boi_id:
            return boi_id
    return ""


def generated_private_doc_matches_event(doc: dict[str, Any], event: dict[str, Any]) -> bool:
    metadata = doc.get("metadata") or {}
    author = metadata.get("author") or {}
    if metadata.get("visibility") != "private":
        return False
    if not str((author or {}).get("agent_id") or "").startswith("boi-writer-"):
        return False
    source_event = metadata.get("source_event") or {}
    event_id = str(event.get("event_id") or "")
    trace_id = str(event.get("trace_id") or "")
    if event_id and str(source_event.get("event_id") or "") == event_id:
        return True
    if trace_id and str(source_event.get("trace_id") or "") == trace_id:
        return True
    return not event_id and not trace_id


@app.post("/api/boi/enrich-from-dispatch", dependencies=[Depends(require_service_token)])
async def enrich_boi_from_dispatch(req: BoIEnrichFromDispatchRequest) -> dict[str, Any]:
    dispatch_result = dispatch_result_payload(req.dispatch_result or {})
    boi_id = dispatch_generated_boi_id(dispatch_result)
    if not boi_id:
        return {"ok": True, "boi_id": "", "enriched": False, "sections_updated": [], "skipped_reason": "missing_boi_id"}

    doc = find_doc_by_id(boi_id, req.employee_id)
    if not doc:
        return {"ok": True, "boi_id": boi_id, "enriched": False, "sections_updated": [], "skipped_reason": "boi_not_found"}
    path = Path(str(doc.get("path") or ""))
    if not path.exists() or not generated_private_doc_matches_event(doc, req.event or {}):
        return {
            "ok": True,
            "boi_id": boi_id,
            "enriched": False,
            "sections_updated": [],
            "skipped_reason": "not_generated_private_boi",
        }

    def raw_url_for_action_result(request_id: str, raw_log_ref: str) -> str:
        ref = raw_log_ref
        if not ref and request_id:
            raw_row = find_action_log_row_by_request_id(request_id, req.employee_id)
            ref = str((raw_row or {}).get("_log_ref") or "")
        return action_raw_page_url(ref, req.employee_id) if ref else ""

    body, sections_updated = build_enriched_body(
        str(doc.get("body") or ""),
        dispatch_result,
        raw_url_resolver=raw_url_for_action_result,
    )
    metadata = dict(doc.get("metadata") or {})
    metadata["enrichment"] = {
        "status": "enriched",
        "enriched_at": now_iso(),
        "source": "dispatch_result",
        "sections_updated": sections_updated,
    }
    path.write_text(compose_markdown(metadata, body), encoding="utf-8")
    invalidate_doc_caches()
    append_event_log(
        status="enriched",
        event=req.event or {},
        result={"boi_id": boi_id, "sections_updated": sections_updated, "source": "dispatch_result"},
    )
    return {"ok": True, "boi_id": boi_id, "enriched": True, "sections_updated": sections_updated}


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
    if req.trace_id:
        event["trace_id"] = req.trace_id
    workflow_def, workflow_stage, workflow_event_def = workflow_for_event_type(req.event_type, str(actor))
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
- 명시적 요청, 사용자 승인, 자동 검증을 거쳐 Team/Public BoI로 게시됩니다.
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
    elif workflow_def and workflow_stage:
        title = payload.get("title") or f"SOP Workflow Instance - {event_label(req.event_type)}"
        event_def = dict(workflow_event_def or {})
        event_def["sop_ref"] = workflow_def.get("sop_ref")
        event_def["sop_stage_id"] = workflow_stage.get("sop_stage_id") or workflow_stage.get("id")
        event_def["workflow_stage"] = workflow_stage.get("stage") or workflow_stage.get("name") or event_def.get("workflow_stage")
        action_keys = workflow_stage.get("automated_actions") or event_def.get("recommended_actions") or []
        manual_action_keys = workflow_stage.get("manual_actions") or event_def.get("recommended_manual_actions") or []
        action_details = action_details_for_keys(action_keys, str(actor))
        manual_action_details = action_details_for_keys(manual_action_keys, str(actor))
        sop_ref = str(workflow_def.get("sop_ref") or event_def.get("sop_ref") or "")
        sop_doc = workflow_def.get("doc") or find_doc_by_id(sop_ref, str(actor))
        sop_uri = str(workflow_def.get("sop_uri") or (sop_doc or {}).get("uri", ""))
        sop_title = str(workflow_def.get("sop_title") or (sop_doc or {}).get("metadata", {}).get("title", ""))
        event_labels = {str(item.get("event_type")): event_label(str(item.get("event_type"))) for item in load_event_types()}
        body = render_stage_execution_body(
            event=event,
            payload=payload,
            event_def=event_def,
            sop_doc=sop_doc,
            sop_ref=sop_ref,
            sop_uri=sop_uri,
            sop_title=sop_title,
            event_label=event_label(req.event_type),
            action_details=action_details,
            manual_action_details=manual_action_details,
            event_labels=event_labels,
        )
        source_refs = req.source_refs or [{"type": "boi", "ref": sop_ref}]
        source_refs = source_refs + [{"type": "sop", "ref": sop_ref, "uri": sop_uri}]
        for detail in action_details + manual_action_details:
            if detail.get("doc_ref"):
                source_refs.append({"type": "action-spec", "ref": detail.get("doc_ref"), "uri": detail.get("doc_uri")})
        meta = make_metadata(
            boi_type=event_to_boi_type(req.event_type),
            title=title,
            description="SOP stage 기반 업무 실행 기록",
            owner=str(actor),
            source_event=event,
            source_refs=source_refs,
            tags=["SOP", "AI-Native-Workflow", "EventBroker", "ActionGateway", "BoIWiki"],
        )
        meta["workflow_stage"] = event_def.get("workflow_stage")
        meta["workflow_key"] = workflow_def.get("workflow_key")
        meta["sop_ref"] = sop_ref
        meta["sop_uri"] = sop_uri
        meta["sop_stage_id"] = event_def.get("sop_stage_id")
        meta["recommended_actions"] = action_keys
        meta["recommended_manual_actions"] = manual_action_keys
        meta["relations"] = [
            {
                "type": "triggered_by_event",
                "target": f"event_type:{req.event_type}",
                "okf_target": event_type_okf_uri(req.event_type),
            },
            {
                "type": "implements_sop",
                "target": sop_ref,
                "okf_target": sop_uri,
            },
            {
                "type": "sop_stage",
                "target": f"sop_stage:{sop_ref}#{event_def.get('sop_stage_id', '')}",
            },
        ]
        for detail in action_details:
            if detail.get("doc_ref"):
                meta["relations"].append(
                    {
                        "type": "uses_action_spec",
                        "target": detail.get("doc_ref"),
                        "okf_target": detail.get("doc_uri"),
                    }
                )
        for detail in manual_action_details:
            if detail.get("doc_ref"):
                meta["relations"].append(
                    {
                        "type": "requires_manual_action",
                        "target": detail.get("doc_ref"),
                        "okf_target": detail.get("doc_uri"),
                    }
                )
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
async def event_types_page(
    request: Request,
    employee_id: str = Depends(current_employee),
    q: str = "",
    status: str = "",
    owner: str = "",
    workflow_stage: str = "",
    has_sop: str = "",
) -> HTMLResponse:
    types = load_event_types()
    counts = {t["event_type"]: 0 for t in types}
    for d in accessible_docs(employee_id):
        et = d["metadata"].get("event_type")
        if et in counts:
            counts[et] += 1
    filtered_types = filter_event_types_for_catalog(
        types,
        q=q,
        status=status,
        owner=owner,
        workflow_stage=workflow_stage,
        has_sop=has_sop,
    )
    status_options = sorted({str(item.get("status") or "") for item in types if item.get("status")})
    owner_options = sorted({str(item.get("owner") or "") for item in types if item.get("owner")})
    workflow_stage_options = sorted({str(item.get("workflow_stage") or "") for item in types if item.get("workflow_stage")})
    event_type_drafts = visible_event_type_drafts(employee_id)
    return templates.TemplateResponse(
        "event_types.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="event_types",
                title="Event Type Catalog",
                description="Event Broker의 업무 이벤트를 기술 Topic이 아니라 업무 언어로 보여주는 카탈로그입니다.",
            ),
            "event_types": filtered_types,
            "counts": counts,
            "q": q,
            "status": status,
            "owner": owner,
            "workflow_stage": workflow_stage,
            "has_sop": has_sop,
            "status_options": status_options,
            "owner_options": owner_options,
            "workflow_stage_options": workflow_stage_options,
            "total_event_types": len(filtered_types),
            "event_type_drafts": event_type_drafts,
            "event_type_draft_count": len(event_type_drafts),
            "has_active_filter": bool(q or status or owner or workflow_stage or has_sop),
            "clear_url": app_url("/event-types", employee_id),
        },
    )


@app.get("/event-types/{event_type:path}", response_class=HTMLResponse)
async def event_type_detail_page(request: Request, event_type: str, employee_id: str = Depends(current_employee)) -> HTMLResponse:
    event_def = get_event_type(event_type)
    if not event_def:
        raise HTTPException(status_code=404, detail=f"Event Type not found: {event_type}")
    accessible = accessible_docs(employee_id)
    doc_lookup = build_doc_lookup(accessible)
    docs = filter_docs(accessible, event_type=event_type)
    actions = [
        action
        for action in load_action_catalog()
        if event_type in (action.get("event_types") or []) or "*" in (action.get("event_types") or [])
    ]
    recent_events = read_event_logs(limit=20, event_type=event_type)
    action_items = actions_for_template(actions, employee_id, doc_lookup=doc_lookup)
    return templates.TemplateResponse(
        "event_type_detail.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="event_types",
                title=str(event_def.get("name_ko") or event_type),
                description=f"{event_type} · {event_def.get('description') or ''}",
                page_actions=[
                    {"label": "이 Event Type의 BoI 보기", "href": browse_url(employee_id, event_type=event_type), "kind": "secondary"},
                    {"label": "Stream 보기", "href": "/events?" + urlencode({"employee_id": employee_id, "event_type": event_type}), "kind": "secondary"},
                    {"label": "연결 Action 보기", "href": "/actions?" + urlencode({"employee_id": employee_id, "event_type": event_type}), "kind": "secondary"},
                ],
            ),
            "event_type": event_type,
            "event": event_def,
            "docs": docs_for_template(docs, employee_id),
            "actions": action_items,
            "api_mcp_actions": [
                action for action in action_items if action.get("connector_kind") in {"api", "mcp", "webhook", "langflow", "boi_writer", "event_broker"}
            ],
            "events": event_rows_for_template(recent_events, doc_lookup=doc_lookup, employee_id=employee_id),
            "stream_url": "/events?" + urlencode({"employee_id": employee_id, "event_type": event_type}),
            "actions_url": "/actions?" + urlencode({"employee_id": employee_id, "event_type": event_type}),
            "boi_filter_url": browse_url(employee_id, event_type=event_type),
            "run_example": event_run_example(event_type, employee_id),
        },
    )


@app.get("/events", response_class=HTMLResponse)
async def events_page(
    request: Request,
    employee_id: str = Depends(current_employee),
    event_type: str = "",
    trace_id: str = "",
    event_id: str = "",
    from_time: str = "",
    to_time: str = "",
    time_preset: str = "",
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
) -> HTMLResponse:
    offset = (page - 1) * limit
    time_filter_error = ""
    try:
        time_filter = event_time_range(from_time=from_time, to_time=to_time, time_preset=time_preset)
    except ValueError as exc:
        time_filter_error = str(exc)
        time_filter = {
            "from_dt": None,
            "to_dt": None,
            "from_value": from_time,
            "to_value": to_time,
            "time_preset": time_preset,
            "active": False,
            "label": "",
        }
    if time_filter_error:
        total_events = 0
        events = []
    else:
        total_events = count_event_logs(
            event_type=event_type or None,
            trace_id=trace_id or None,
            event_id=event_id or None,
            from_dt=time_filter["from_dt"],
            to_dt=time_filter["to_dt"],
        )
        events = read_event_logs(
            limit=limit,
            event_type=event_type or None,
            trace_id=trace_id or None,
            event_id=event_id or None,
            from_dt=time_filter["from_dt"],
            to_dt=time_filter["to_dt"],
            offset=offset,
        )
    doc_lookup = build_doc_lookup(accessible_docs(employee_id))
    explicit_from = str(time_filter.get("from_value") or "")
    explicit_to = str(time_filter.get("to_value") or "")
    effective_preset = str(time_filter.get("time_preset") or "")
    preset_options = [
        {"label": "최근 1시간", "value": "1h"},
        {"label": "최근 6시간", "value": "6h"},
        {"label": "최근 24시간", "value": "24h"},
        {"label": "오늘", "value": "today"},
    ]
    time_preset_links = [
        {
            **preset,
            "url": events_url(
                employee_id,
                event_type=event_type,
                trace_id=trace_id,
                event_id=event_id,
                time_preset=preset["value"],
                page=1,
                limit=limit,
            ),
            "active": effective_preset == preset["value"],
        }
        for preset in preset_options
    ]
    clear_time_url = events_url(employee_id, event_type=event_type, trace_id=trace_id, event_id=event_id, page=1, limit=limit)
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="events",
                title="Event Stream",
                description="Kafka로 발행/처리된 업무 이벤트를 Wiki에서 업무 맥락으로 확인합니다.",
            ),
            "event_type": event_type,
            "trace_id": trace_id,
            "event_id": event_id,
            "from_time": explicit_from,
            "to_time": explicit_to,
            "time_preset": effective_preset,
            "time_filter": time_filter,
            "time_filter_error": time_filter_error,
            "time_preset_links": time_preset_links,
            "clear_time_url": clear_time_url,
            "page": page,
            "limit": limit,
            "total_events": total_events,
            "has_prev": page > 1,
            "has_next": offset + len(events) < total_events,
            "prev_url": events_url(
                employee_id,
                event_type=event_type,
                trace_id=trace_id,
                event_id=event_id,
                from_time=explicit_from,
                to_time=explicit_to,
                time_preset=effective_preset,
                page=max(1, page - 1),
                limit=limit,
            ),
            "next_url": events_url(
                employee_id,
                event_type=event_type,
                trace_id=trace_id,
                event_id=event_id,
                from_time=explicit_from,
                to_time=explicit_to,
                time_preset=effective_preset,
                page=page + 1,
                limit=limit,
            ),
            "event_types": load_event_types(),
            "events": event_rows_for_template(events, doc_lookup=doc_lookup, employee_id=employee_id),
        },
    )


@app.get("/api/event-types")
async def api_event_types() -> dict[str, Any]:
    return {"items": load_event_types()}


@app.get("/api/events/log")
async def api_event_logs(
    event_type: str = "",
    trace_id: str = "",
    event_id: str = "",
    from_time: str = "",
    to_time: str = "",
    time_preset: str = "",
    limit: int = 200,
    page: int = 1,
) -> dict[str, Any]:
    effective_limit = max(1, min(int(limit or 200), 200))
    effective_page = max(1, int(page or 1))
    offset = (effective_page - 1) * effective_limit
    try:
        time_filter = event_time_range(from_time=from_time, to_time=to_time, time_preset=time_preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    total = count_event_logs(
        event_type=event_type or None,
        trace_id=trace_id or None,
        event_id=event_id or None,
        from_dt=time_filter["from_dt"],
        to_dt=time_filter["to_dt"],
    )
    rows = read_event_logs(
        limit=effective_limit,
        event_type=event_type or None,
        trace_id=trace_id or None,
        event_id=event_id or None,
        from_dt=time_filter["from_dt"],
        to_dt=time_filter["to_dt"],
        offset=offset,
    )
    return {
        "count": len(rows),
        "total": total,
        "page": effective_page,
        "limit": effective_limit,
        "time_filter": {
            "from_time": time_filter["from_dt"].isoformat() if time_filter["from_dt"] else "",
            "to_time": time_filter["to_dt"].isoformat() if time_filter["to_dt"] else "",
            "time_preset": time_filter["time_preset"],
            "active": time_filter["active"],
            "label": time_filter["label"],
        },
        "items": rows,
    }


@app.get("/api/events/raw/{log_ref:path}")
async def api_event_raw(log_ref: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    row = find_event_log_row_by_ref(log_ref)
    if not row:
        raise HTTPException(status_code=404, detail="Event log row not found")
    return {
        "ok": True,
        "employee_id": employee_id,
        "log_ref": log_ref,
        "row": row,
    }


@app.get("/api/actions/raw/{log_ref:path}")
async def api_action_raw(log_ref: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    row = find_action_log_row_by_ref(log_ref, employee_id)
    if not row:
        raise HTTPException(status_code=404, detail="Action log row not found")
    return {
        "ok": True,
        "employee_id": employee_id,
        "log_ref": log_ref,
        "row": redact_sensitive(row),
    }


@app.get("/actions/raw/{log_ref:path}", response_class=HTMLResponse)
async def action_raw_page(request: Request, log_ref: str, employee_id: str = Depends(current_employee)) -> HTMLResponse:
    row = find_action_log_row_by_ref(log_ref, employee_id)
    if not row:
        return templates.TemplateResponse(
            "missing_doc.html",
            {
                "request": request,
                "employee_id": employee_id,
                "shell": app_shell_context(
                    request,
                    employee_id,
                    active_nav="actions",
                    title="Action log row not found",
                    description="요청한 action log 원본을 찾을 수 없거나 접근 권한이 없습니다.",
                    page_actions=[{"label": "Actions", "href": app_url("/actions", employee_id), "kind": "secondary"}],
                ),
                "boi_id": log_ref,
                "title": "Action log row not found",
                "message": "요청한 action log 원본을 찾을 수 없거나 접근 권한이 없습니다.",
            },
            status_code=404,
        )
    redacted_row = redact_sensitive(row)
    doc_ref = str(row.get("doc_ref") or "")
    trace_id = str(row.get("trace_id") or "")
    event_id = str(row.get("event_id") or "")
    result_value = row.get("result") if isinstance(row.get("result"), dict) else {}
    boi_id = str(row.get("boi_id") or result_boi_id(result_value) or "")
    readable_result = action_raw_readable_markdown(redacted_row)
    compact_row = compact_action_raw_row_for_html(redacted_row)
    simulation_agent = result_value.get("simulation_agent") if isinstance(result_value.get("simulation_agent"), dict) else {}
    coverage_report = simulation_agent.get("coverage_report") if isinstance(simulation_agent.get("coverage_report"), dict) else {}
    context_pack = simulation_agent.get("context_pack") if isinstance(simulation_agent.get("context_pack"), dict) else {}
    evidence_packets = (
        simulation_agent.get("evidence_packets")
        or (context_pack.get("evidence_packets") if isinstance(context_pack, dict) else [])
        or result_value.get("evidence_packets")
        or row.get("evidence_packets")
        or []
    )
    return templates.TemplateResponse(
        "action_raw.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="actions",
                title="Action Raw Detail",
                description="Action Gateway / Langflow / API invocation 원본 로그를 행 단위로 확인합니다.",
                page_actions=[
                    {"label": "Actions", "href": app_url("/actions", employee_id), "kind": "secondary"},
                    *([{"label": "Workflow Status", "href": workflow_status_page_url(trace_id, employee_id), "kind": "secondary"}] if trace_id else []),
                    {"label": "JSON API", "href": action_raw_api_url(log_ref, employee_id), "kind": "secondary"},
                ],
            ),
            "log_ref": log_ref,
            "row": redacted_row,
            "row_html": render_value_html(compact_row),
            "readable_result": readable_result,
            "readable_result_html": render_markdown(readable_result["markdown"], employee_id=employee_id) if readable_result["available"] else "",
            "action_key": row.get("action_key") or "",
            "request_id": row.get("request_id") or "",
            "trace_id": trace_id,
            "event_id": event_id,
            "doc_ref": doc_ref,
            "boi_id": boi_id,
            "api_url": action_raw_api_url(log_ref, employee_id),
            "trace_url": workflow_status_page_url(trace_id, employee_id) if trace_id else "",
            "trace_events_url": trace_events_url(trace_id, employee_id) if trace_id else "",
            "event_url": event_filter_url(event_id, employee_id) if event_id else "",
            "doc_url": doc_url_for_ref(doc_ref, employee_id) if doc_ref else "",
            "boi_url": doc_url_for_ref(boi_id, employee_id) if boi_id else "",
            "simulation": bool(row.get("simulation") or result_value.get("simulation")),
            "simulation_label": row.get("simulation_label") or result_value.get("simulation_label") or "SIMULATED",
            "simulation_notice": row.get("simulation_notice") or result_value.get("simulation_notice") or "",
            "real_system_status": row.get("real_system_status") or result_value.get("real_system_status") or "",
            "simulated_system": row.get("simulated_system") or result_value.get("simulated_system") or "",
            "simulation_agent": simulation_agent,
            "coverage_report": coverage_report,
            "retrieval_trace": simulation_agent.get("retrieval_trace") if simulation_agent else [],
            "used_docs": context_pack.get("documents") if context_pack else [],
            "evidence_packets": evidence_packets,
        },
    )


@app.post("/api/events/audit", dependencies=[Depends(require_service_token)])
async def api_event_audit(req: EventAuditRequest) -> dict[str, Any]:
    append_event_log(status=req.status, event=req.event, result=req.result, error=req.error)
    return {"ok": True}


@app.post("/api/simulations/universal-agent", dependencies=[Depends(require_service_token)])
async def api_universal_simulation_agent(req: SimulationAgentRequest) -> dict[str, Any]:
    action = action_catalog_by_key().get(req.action_key)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action not found: {req.action_key}")
    employee_id = req.employee_id or DEMO_EMPLOYEE_ID
    event_type = str(req.event.get("event_type") or "")
    trace_id = str(req.event.get("trace_id") or "")
    docs = simulation_context_docs(
        employee_id,
        action=action,
        event_type=event_type,
        trace_id=trace_id,
        sop_ref=req.sop_ref or "",
    )
    doc_lookup = build_doc_lookup(docs)
    event_def = get_event_type(event_type) or {}
    workflow: dict[str, Any] | None = None
    if req.workflow_key:
        try:
            workflow = workflow_context(req.workflow_key, employee_id, trace_id=str(req.event.get("trace_id") or ""), doc_lookup=doc_lookup)
        except HTTPException:
            workflow = None
    if workflow is None and event_type:
        workflow, stage, event_def = workflow_for_event_type(event_type, employee_id, doc_lookup=doc_lookup)
        if workflow and stage and not req.sop_stage_id:
            event_def = {**event_def, "sop_stage_id": stage.get("sop_stage_id") or stage.get("stage_id") or stage.get("stage")}
    prior_results = merge_prior_results(req.prior_results, trace_prior_action_results(trace_id, employee_id))
    return build_simulation_agent_result(
        action=action,
        event=req.event,
        payload=req.payload or req.event.get("payload") or {},
        prior_results=prior_results,
        employee_id=employee_id,
        docs=docs,
        event_def=event_def,
        workflow=workflow,
        sop_ref=req.sop_ref or "",
        sop_stage_id=req.sop_stage_id or "",
        max_rounds=max(1, min(int(req.max_rounds or 4), 5)),
        simulation_depth=req.simulation_depth or "stage_prerequisites",
    )


@app.get("/actions", response_class=HTMLResponse)
async def actions_page(
    request: Request,
    employee_id: str = Depends(current_employee),
    event_type: str = "",
    action_key: str = "",
) -> HTMLResponse:
    actions = load_action_catalog()
    if event_type:
        actions = [a for a in actions if event_type in (a.get("event_types") or [])]
    if action_key:
        actions = [a for a in actions if a.get("action_key") == action_key]
    doc_lookup = build_doc_lookup(accessible_docs(employee_id))
    return templates.TemplateResponse(
        "actions.html",
        {
            "request": request,
            "employee_id": employee_id,
            "shell": app_shell_context(
                request,
                employee_id,
                active_nav="actions",
                title="Action Catalog",
                description="API/Webhook 호출을 임의 URL이 아니라 allow-list Action으로 관리합니다.",
            ),
            "event_type": event_type,
            "action_key": action_key,
            "event_types": load_event_types(),
            "actions": actions_for_template(actions, employee_id, doc_lookup=doc_lookup),
            "action_logs": read_action_logs(limit=100),
            "action_invoke_url": f"{boi_public_base_url(request)}/api/actions/invoke?employee_id={quote(employee_id)}",
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


async def invoke_action_gateway(req: ActionInvokeRequest, employee_id: str) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.action_invoker")
    require_employee_binding_or_admin_override(
        employee_id,
        req.employee_id,
        operation="action_invoke",
        mismatch_detail="action employee_id must match the authenticated employee",
        reason=req.admin_override_reason,
    )
    payload = req.model_dump(exclude={"admin_override_reason"})
    payload["employee_id"] = req.employee_id if req.employee_id and "boi.admin" in roles_for(employee_id) else employee_id
    async with httpx.AsyncClient(timeout=ACTION_INVOKE_TIMEOUT_SECONDS) as client:
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


@app.post("/api/actions/invoke")
async def api_action_invoke(req: ActionInvokeRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    return await invoke_action_gateway(req, employee_id)


@app.get("/api/users")
async def users() -> dict[str, Any]:
    return {
        "auth_mode": auth_mode(),
        "users": [{"employee_id": k, "name": USER_NAMES.get(k), "teams": v} for k, v in USER_TEAMS.items()],
    }
