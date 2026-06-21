from __future__ import annotations

import asyncio
import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
import httpx
from datetime import date, datetime, timezone, timedelta
from html import escape as html_escape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import quote, urlencode, urlsplit

import yaml
from aiokafka import AIOKafkaProducer
from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
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
APP_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.getenv("DATA_ROOT", "/data/boi"))
EVENTS_ROOT = Path(os.getenv("EVENTS_ROOT", "/data/events"))
EVENT_CATALOG_ROOT = Path(os.getenv("EVENT_CATALOG_ROOT", "/data/event_catalog"))
ACTION_CATALOG_ROOT = Path(os.getenv("ACTION_CATALOG_ROOT", "/data/action_catalog"))
ACTION_LOG_ROOT = Path(os.getenv("ACTION_LOG_ROOT", "/data/actions"))
DRAFT_ROOT = Path(os.getenv("DRAFT_ROOT", str(DATA_ROOT.parent / "drafts")))
ACTION_GATEWAY_URL = os.getenv("ACTION_GATEWAY_URL", "http://action-gateway:8100")
SERVICE_TOKEN = os.getenv("SERVICE_TOKEN", "dev-service-token-change-me")
DEFAULT_TEAM_ID = os.getenv("DEFAULT_TEAM_ID", "aix-tf")
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
BOI_EVENTS_TOPIC = os.getenv("BOI_EVENTS_TOPIC", "boi.events")
DEMO_EMPLOYEE_ID = os.getenv("DEMO_EMPLOYEE_ID", "100001")
BOI_LLM_BASE_URL = os.getenv("BOI_LLM_BASE_URL", "http://llm-gateway.example:1236/v1").rstrip("/")
BOI_LLM_MODEL = os.getenv("BOI_LLM_MODEL", "google/gemma-4-26b-a4b-qat")
BOI_LLM_API_KEY = os.getenv("BOI_LLM_API_KEY", "not-needed")
KAFKA_PUBLISH_TIMEOUT_SECONDS = float(os.getenv("BOI_KAFKA_PUBLISH_TIMEOUT_SECONDS", "20"))

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

_EVENT_TYPES_CACHE: dict[str, Any] = {"signature": None, "items": []}
_ACTION_CATALOG_CACHE: dict[str, Any] = {"signature": None, "items": []}
_DOCS_CACHE: dict[str, Any] = {"signature": None, "docs": []}
_WORKFLOW_DOCS_CACHE: dict[str, Any] = {"signature": None, "docs": []}
_EVENT_LOG_CACHE: dict[str, Any] = {"signature": None, "rows": []}
_ACTION_LOG_CACHE: dict[str, Any] = {"signature": None, "rows": []}
_RECOVERED_DOC_CACHE: dict[str, Any] = {"signature": None, "by_boi_id": {}, "by_uri": {}}
_FILE_SIGNATURE_CACHE: dict[str, tuple[float, tuple[tuple[str, int, int], ...]]] = {}
_DOC_BODY_HTML_CACHE: dict[tuple[Any, ...], Markup] = {}
SIGNATURE_TTL_SECONDS = 1.0


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
    (DRAFT_ROOT / "sop_packages").mkdir(parents=True, exist_ok=True)
    (DRAFT_ROOT / "action_packages").mkdir(parents=True, exist_ok=True)
    (DRAFT_ROOT / "promotions").mkdir(parents=True, exist_ok=True)


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
    _WORKFLOW_DOCS_CACHE["signature"] = None
    _WORKFLOW_DOCS_CACHE["docs"] = []
    _DOC_BODY_HTML_CACHE.clear()
    _OKF_GRAPH_CACHE.clear()


def invalidate_event_log_caches() -> None:
    _FILE_SIGNATURE_CACHE.clear()
    _EVENT_LOG_CACHE["signature"] = None
    _EVENT_LOG_CACHE["rows"] = []
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


def markdown_href_for_doc_route(
    href: str,
    employee_id: str,
    source_path: Path | None = None,
    doc_lookup: dict[str, dict[str, Any]] | None = None,
) -> str:
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#"):
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
    if doc is None:
        doc = find_recovered_doc_by_id(lookup_ref, employee_id) if doc_lookup is not None else find_doc_by_id(lookup_ref, employee_id)
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
    rendered = html_escape(value)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)

    def replace_image(match: re.Match[str]) -> str:
        alt = match.group(1)
        href = match.group(2)
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
        href = match.group(2)
        routed_href = markdown_href_for_doc_route(href, employee_id, source_path, doc_lookup) if employee_id else href
        return f'<a href="{html_escape(routed_href, quote=True)}">{label}</a>'

    rendered = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)", replace_image, rendered)
    rendered = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)(?:\s+&quot;[^&]*&quot;)?\)", replace_link, rendered)
    return rendered


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


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
    table_lines: list[str] = []
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
                    f"<li>{render_inline_markdown(item, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</li>"
                    for item in list_items
                )
                + "</ul>"
            )
            list_items.clear()

    def flush_table() -> None:
        if table_lines:
            html_parts.append(render_table(table_lines, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup))
            table_lines.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
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
            flush_table()
        elif stripped.startswith("#"):
            flush_paragraph()
            flush_list()
            flush_table()
            marker, _, title = stripped.partition(" ")
            level = min(max(len(marker), 1) + 2, 5)
            html_parts.append(
                f"<h{level}>{render_inline_markdown(title or stripped.lstrip('#').strip(), employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)}</h{level}>"
            )
        elif re.match(r"^\s*[-*]\s+\S", line):
            flush_paragraph()
            flush_table()
            list_items.append(re.sub(r"^\s*[-*]\s+", "", line).strip())
        elif stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            table_lines.append(stripped)
        elif re.fullmatch(r"!\[[^\]]*\]\([^)]+\)", stripped):
            flush_paragraph()
            flush_list()
            flush_table()
            html_parts.append(render_inline_markdown(stripped, employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup))
        else:
            flush_list()
            flush_table()
            paragraph.append(line)
        index += 1

    flush_paragraph()
    flush_list()
    flush_table()
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
    return identity_for_employee(employee_id).teams


def user_name_for(employee_id: str) -> str:
    identity = identity_for_employee(employee_id)
    return identity.display_name or name_for_employee(employee_id)


def require_employee_role(employee_id: str, role: str) -> None:
    try:
        require_role(identity_for_employee(employee_id), role)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def is_accessible(doc: dict[str, Any], employee_id: str) -> bool:
    meta = doc["metadata"]
    hotl = meta.get("hotl") or {}
    if str(hotl.get("status") or "") in HOTL_HIDDEN_STATUSES:
        return False
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
    docs = [doc for doc in _DOCS_CACHE["docs"] if is_accessible(doc, employee_id)]
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
            f'-d \'{{"payload":{{"title":"{event_label(event_type)}","workflow":"{workflow_key}"}}}}\''
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


def find_recovered_doc_by_id(boi_id: str, employee_id: str | None = None) -> dict[str, Any] | None:
    normalized_uri = boi_id.lstrip("/")
    by_boi_id, by_uri = recovered_doc_indexes()
    candidates = [by_boi_id.get(boi_id), by_uri.get(normalized_uri)]
    if normalized_uri.endswith(".md"):
        candidates.append(by_uri.get(normalized_uri[:-3]))
    for doc in candidates:
        if doc and (employee_id is None or is_accessible(doc, employee_id)):
            return doc
    return None


def find_doc_by_id(boi_id: str, employee_id: str | None = None) -> dict[str, Any] | None:
    normalized_uri = boi_id.lstrip("/")
    normalized_concept_id = normalized_uri[:-3] if normalized_uri.endswith(".md") else normalized_uri
    for p in all_markdown_files():
        try:
            doc = read_doc(p)
        except Exception:
            continue
        doc_uri = doc.get("uri", "").lstrip("/")
        doc_concept_id = doc_uri[:-3] if doc_uri.endswith(".md") else doc_uri
        if doc["metadata"].get("boi_id") == boi_id or doc_uri == normalized_uri or doc_concept_id == normalized_concept_id:
            if employee_id is None or is_accessible(doc, employee_id):
                return doc
    return find_recovered_doc_by_id(boi_id, employee_id)


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


def candidate_path_in_temp_data_root(temp_root: Path, source_path: Path) -> Path | None:
    try:
        rel_path = source_path.resolve().relative_to(DATA_ROOT.resolve())
    except ValueError:
        return None
    return temp_root / "boi" / rel_path


def candidate_okf_lint_report(source_path: Path, proposed_content: str) -> dict[str, Any] | None:
    with tempfile.TemporaryDirectory(prefix="boi-edit-") as temp_dir:
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
        post_validation = current_source_validation_report(source_path)
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
    content = path.read_text(encoding="utf-8")
    return {
        "body": doc.get("body") or "",
        "base_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "preview_url": "/api/docs/" + str(doc["metadata"].get("boi_id") or doc.get("uri", "").lstrip("/")) + "/body-preview?" + urlencode({"employee_id": employee_id}),
        "apply_url": "/api/docs/" + str(doc["metadata"].get("boi_id") or doc.get("uri", "").lstrip("/")) + "/body-apply?" + urlencode({"employee_id": employee_id}),
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
        hashlib.sha1(repr(_DOCS_CACHE.get("signature")).encode("utf-8")).hexdigest(),
    )
    cached = _DOC_BODY_HTML_CACHE.get(key)
    if cached is not None:
        return cached
    if len(_DOC_BODY_HTML_CACHE) > 128:
        _DOC_BODY_HTML_CACHE.clear()
    rendered = render_markdown(doc["body"], employee_id=employee_id, source_path=source_path, doc_lookup=doc_lookup)
    _DOC_BODY_HTML_CACHE[key] = rendered
    return rendered


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
        return DATA_ROOT / "private" / owner
    if visibility == "team":
        team_id = str(metadata.get("team_id") or DEFAULT_TEAM_ID)
        return DATA_ROOT / "team" / team_id
    if visibility == "public":
        boi_type = str(metadata.get("type") or "")
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
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    trace_id: str | None = None


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


@app.on_event("startup")
async def startup() -> None:
    ensure_dirs()


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
        "llm": {
            "provider": "openai-compatible",
            "base_url": BOI_LLM_BASE_URL,
            "model": BOI_LLM_MODEL,
            "api_key_configured": bool(BOI_LLM_API_KEY),
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
    filtered_docs = filter_docs(
        accessible,
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


@app.post("/api/docs/{boi_id:path}/body-preview")
async def preview_doc_body_edit(
    boi_id: str,
    req: BodyPreviewRequest,
    employee_id: str = Depends(current_employee),
) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.editor")
    docs = accessible_docs(employee_id)
    doc_lookup = build_doc_lookup(docs)
    doc = doc_from_lookup(boi_id, doc_lookup)
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
    docs = accessible_docs(employee_id)
    doc_lookup = build_doc_lookup(docs)
    doc = doc_from_lookup(boi_id, doc_lookup)
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
    docs = accessible_docs(employee_id)
    doc_lookup = build_doc_lookup(docs)
    doc = doc_from_lookup(boi_id, doc_lookup) or find_recovered_doc_by_id(boi_id, employee_id)
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
    if doc.get("recovered_from_log"):
        docs = docs + [doc]
        doc_lookup.update(build_doc_lookup([doc]))
    doc_folder_path = doc_folder(doc)
    return_folder = normalize_folder(folder) or doc_folder_path
    workflow = doc["metadata"].get("workflow") or {}
    workflow_key = str(workflow.get("workflow_key") or "")
    workflow_poc = workflow_context(workflow_key, employee_id, doc_lookup=doc_lookup) if workflow_key else None
    graph_ref = str(doc["metadata"].get("boi_id") or doc.get("uri", "").lstrip("/"))
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
            "event_type_url": browse_url(employee_id, event_type=doc["metadata"].get("event_type", "")),
            "body_html": cached_doc_body_html(doc, employee_id, doc_lookup),
            "body_editor": body_editor_payload_for_doc(doc, employee_id),
            "citations": citation_rows_for_doc(doc, employee_id, doc_lookup=doc_lookup),
            "workflow_poc": workflow_poc,
            "metadata_rows": metadata_rows_for_template(doc["metadata"], request),
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
    filtered_docs = filter_docs(
        accessible_docs(employee_id),
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
    return cached_okf_graph_for_docs(accessible_docs(employee_id), employee_id)


@app.get("/api/okf/graph/doc/{boi_id:path}")
async def api_okf_doc_graph(boi_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    docs = accessible_docs(employee_id)
    doc_lookup = build_doc_lookup(docs)
    doc = doc_from_lookup(boi_id, doc_lookup) or find_recovered_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    if doc.get("recovered_from_log"):
        docs = docs + [doc]
    return relationship_context_for_doc(doc, employee_id, docs=docs)


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
                "doc_uri": action_doc_uri(action, employee_id, doc_lookup=doc_lookup)
                if doc_lookup is not None
                else (doc_url_for_ref(str(action.get("doc_ref") or ""), employee_id) if action.get("doc_ref") else ""),
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


def workflow_status_payload(
    workflow_key: str,
    trace_id: str,
    employee_id: str,
    graph_scope: str = "trace",
) -> dict[str, Any]:
    docs = accessible_docs(employee_id) if graph_scope == "global" else workflow_docs_for_registry(employee_id)
    context = workflow_context(workflow_key, employee_id, trace_id=trace_id)
    events = filtered_event_log_rows(trace_id=trace_id)
    event_ids = {str(row.get("event_id")) for row in events if row.get("event_id")}
    action_logs = [
        dict(row)
        for row in trace_action_log_rows(trace_id, event_ids=event_ids, limit=500)
        if action_log_visible_to_employee(row, employee_id)
    ]
    generated_doc_by_id: dict[str, dict[str, Any]] = {}
    for row in events:
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
    relation_graph = (
        cached_okf_graph_for_docs(docs, employee_id)
        if graph_scope == "global"
        else workflow_trace_graph(context=context, events=events, actions=action_logs, generated_docs=generated_docs, employee_id=employee_id)
    )
    return {
        "ok": True,
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
) -> dict[str, Any]:
    return workflow_status_payload("equipment-anomaly", trace_id, employee_id, graph_scope=graph_scope)


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


WORKFLOW_START_CONTROL_KEYS = {"payload", "event_type", "actor_employee_id", "owner", "source_refs", "trace_id"}


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
    result = await publish_event(
        EventPublishRequest(
            event_type=event_type,
            actor_employee_id=owner,
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
    return await start_workflow_from_data(workflow_key, raw, employee_id)


@app.post("/api/workflows/demo/equipment-anomaly/start")
async def start_equipment_anomaly_demo(req: EquipmentAnomalyStartRequest, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    require_employee_role(employee_id, "boi.workflow_runner")
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
) -> Any:
    payload = workflow_status_payload(workflow_key, trace_id, employee_id, graph_scope=graph_scope)
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
) -> Any:
    payload = equipment_anomaly_status_payload(trace_id, employee_id, graph_scope=graph_scope)
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
    docs = accessible_docs(employee_id)
    doc_lookup = build_doc_lookup(docs)
    event_type = str(req.event.get("event_type") or "")
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
    trace_id = str(req.event.get("trace_id") or "")
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
    require_employee_role(employee_id, "boi.action_invoker")
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
    return {
        "auth_mode": auth_mode(),
        "users": [{"employee_id": k, "name": USER_NAMES.get(k), "teams": v} for k, v in USER_TEAMS.items()],
    }
