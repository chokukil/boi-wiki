from __future__ import annotations

import asyncio
import ast
import hashlib
import json
import os
import re
import uuid
import httpx
from datetime import date, datetime, timezone, timedelta
from html import escape as html_escape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlencode

import yaml
from aiokafka import AIOKafkaProducer
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
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


def render_inline_markdown(value: str) -> str:
    rendered = html_escape(value)
    rendered = re.sub(r"`([^`]+)`", r"<code>\1</code>", rendered)
    rendered = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", rendered)
    return rendered


def table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    cells = table_cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def render_table(lines: list[str]) -> str:
    if len(lines) < 2 or not is_table_separator(lines[1]):
        return render_paragraph(lines)
    headers = table_cells(lines[0])
    rows = [table_cells(line) for line in lines[2:]]
    head = "".join(f"<th>{render_inline_markdown(cell)}</th>" for cell in headers)
    body_rows = []
    for row in rows:
        padded = row + [""] * max(len(headers) - len(row), 0)
        body_rows.append("<tr>" + "".join(f"<td>{render_inline_markdown(cell)}</td>" for cell in padded[: len(headers)]) + "</tr>")
    return f'<div class="table-wrap"><table class="markdown-table"><thead><tr>{head}</tr></thead><tbody>{"".join(body_rows)}</tbody></table></div>'


def render_paragraph(lines: list[str]) -> str:
    text = " ".join(line.strip() for line in lines if line.strip())
    return f"<p>{render_inline_markdown(text)}</p>" if text else ""


def render_markdown(value: str) -> Markup:
    lines = value.splitlines()
    html_parts: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    table_lines: list[str] = []
    index = 0

    def flush_paragraph() -> None:
        if paragraph:
            html_parts.append(render_paragraph(paragraph))
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            html_parts.append("<ul>" + "".join(f"<li>{render_inline_markdown(item)}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    def flush_table() -> None:
        if table_lines:
            html_parts.append(render_table(table_lines))
            table_lines.clear()

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph()
            flush_list()
            flush_table()
            language = stripped.strip("`").strip().lower()
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                code_lines.append(lines[index])
                index += 1
            code = "\n".join(code_lines)
            if language == "json":
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
            html_parts.append(f"<h{level}>{render_inline_markdown(title or stripped.lstrip('#').strip())}</h{level}>")
        elif re.match(r"^\s*[-*]\s+\S", line):
            flush_paragraph()
            flush_table()
            list_items.append(re.sub(r"^\s*[-*]\s+", "", line).strip())
        elif stripped.startswith("|") and stripped.endswith("|"):
            flush_paragraph()
            flush_list()
            table_lines.append(stripped)
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


def event_dispatch_summary(result: dict[str, Any], employee_id: str) -> dict[str, Any] | None:
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
                "boi_url": doc_url_for_ref(row_boi_id, employee_id) if row_boi_id else "",
            }
        )
    return {
        "routed_by": result.get("routed_by"),
        "status": dispatch.get("status"),
        "ok": dispatch.get("ok"),
        "boi_id": boi_id,
        "boi_url": doc_url_for_ref(boi_id, employee_id) if boi_id else "",
        "actions": rows,
    }


def event_rows_for_template(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rendered_rows = []
    for row in rows:
        item = dict(row)
        if row.get("result") is not None:
            summary = event_dispatch_summary(row["result"], str(row.get("employee_id") or DEMO_EMPLOYEE_ID))
            if summary:
                item["dispatch_summary"] = summary
                item["raw_result_html"] = render_value_html(row["result"])
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


def read_event_logs(limit: int = 200, event_type: str | None = None, trace_id: str | None = None) -> list[dict[str, Any]]:
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
            if trace_id and row.get("trace_id") != trace_id:
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


def event_run_example(event_type: str, employee_id: str) -> str:
    if event_type == "equipment.alarm.raised.v1":
        return (
            f'curl -X POST "http://localhost:8000/api/workflows/demo/equipment-anomaly/start?employee_id={employee_id}" '
            '-H "Content-Type: application/json" '
            '-d \'{"equipment_id":"ETCH-VM-01","alarm_code":"RESPONSE_CHAIN_ABNORMAL","title":"Response Chain 이상 Alarm 발생"}\''
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
) -> list[dict[str, Any]]:
    filtered = docs
    if q:
        q_lower = q.lower()
        filtered = [
            d
            for d in filtered
            if q_lower in json.dumps(d["metadata"], ensure_ascii=False).lower() or q_lower in d["body"].lower()
        ]
    if event_type:
        filtered = [d for d in filtered if d["metadata"].get("event_type") == event_type]
    if visibility:
        filtered = [d for d in filtered if d["metadata"].get("visibility") == visibility]
    if boi_type:
        filtered = [d for d in filtered if d["metadata"].get("type") == boi_type]
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


def metadata_rows_for_template(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    return [{"key": str(key), "value_html": render_value_html(value)} for key, value in metadata.items()]


def action_spec_for_template(metadata: dict[str, Any]) -> dict[str, Any] | None:
    if metadata.get("type") != "boi/action-spec":
        return None
    connector_kind = str(metadata.get("connector_kind") or "")
    request_fields = ["request_schema", "input_schema", "example_request", "example_tool_call"]
    response_fields = ["response_schema", "output_schema", "example_response"]
    return {
        "action_key": metadata.get("action_key"),
        "connector_kind": connector_kind,
        "execution_mode": metadata.get("execution_mode"),
        "endpoint_label": "MCP Tool" if connector_kind == "mcp" else "Endpoint",
        "method": metadata.get("method") or "POST",
        "url": metadata.get("url") or metadata.get("mcp_server"),
        "protocol": metadata.get("protocol"),
        "auth_html": render_value_html(metadata.get("auth") or {}),
        "headers_html": render_value_html(metadata.get("headers") or {}),
        "request_rows": [
            {"key": field, "value_html": render_value_html(metadata.get(field))}
            for field in request_fields
            if metadata.get(field) is not None
        ],
        "response_rows": [
            {"key": field, "value_html": render_value_html(metadata.get(field))}
            for field in response_fields
            if metadata.get(field) is not None
        ],
        "gateway_html": render_value_html(metadata.get("action_gateway_mapping") or {}),
        "curl": metadata.get("curl"),
        "security_html": render_value_html(metadata.get("security_notes")),
        "mcp_tool_name": metadata.get("tool_name"),
        "mcp_transport": metadata.get("transport"),
    }


def find_doc_by_id(boi_id: str, employee_id: str | None = None) -> dict[str, Any] | None:
    normalized_uri = boi_id.lstrip("/")
    for p in all_markdown_files():
        try:
            doc = read_doc(p)
        except Exception:
            continue
        if doc["metadata"].get("boi_id") == boi_id or doc.get("uri", "").lstrip("/") == normalized_uri:
            if employee_id is None or is_accessible(doc, employee_id):
                return doc
    return None


def doc_url_for_ref(ref: str, employee_id: str) -> str:
    return f"/docs/{ref}?" + urlencode({"employee_id": employee_id})


def action_doc_uri(action: dict[str, Any], employee_id: str) -> str:
    doc_ref = str(action.get("doc_ref") or "")
    if not doc_ref:
        return ""
    doc = find_doc_by_id(doc_ref, employee_id)
    return str(doc.get("uri", "")) if doc else ""


def actions_for_template(actions: list[dict[str, Any]], employee_id: str) -> list[dict[str, Any]]:
    items = []
    for action in actions:
        item = dict(action)
        doc_ref = str(item.get("doc_ref") or "")
        if doc_ref:
            item["doc_url"] = doc_url_for_ref(doc_ref, employee_id)
            item["doc_uri"] = action_doc_uri(item, employee_id)
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


@app.post("/api/poc/equipment/trend-history", dependencies=[Depends(require_service_token)])
async def poc_equipment_trend_history(req: PocConnectorRequest) -> dict[str, Any]:
    payload = poc_payload(req)
    return poc_result(
        action="sop.equipment.request_trend_history",
        req=req,
        result={
            "equipment_id": payload.get("equipment_id"),
            "trend_status": "anomaly_detected",
            "lot_history_ref": f"/mock/hyvis/lot-history/{payload.get('lot_id', 'LOT-UNKNOWN')}",
            "wafer_history_ref": f"/mock/hyvis/wafer-history/{payload.get('wafer_id', 'WF-UNKNOWN')}",
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
            "raw_data_ref": f"/mock/hyvis/raw-data/{equipment_id}/{lot_id}",
            "source_data_ref": f"/mock/tas/source-data/{equipment_id}",
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
    results = []
    for doc in accessible_docs(employee_id):
        metadata = doc["metadata"]
        visibility = str(metadata.get("visibility") or "")
        haystack = json.dumps(metadata, ensure_ascii=False, default=str).lower() + "\n" + str(doc.get("body", "")).lower()
        if visibility not in allowed_visibility:
            continue
        if query and query not in haystack:
            continue
        results.append(
            {
                "boi_id": metadata.get("boi_id"),
                "title": metadata.get("title"),
                "description": metadata.get("description"),
                "type": metadata.get("type"),
                "visibility": visibility,
                "uri": doc.get("uri"),
            }
        )
        if len(results) >= int(req.arguments.get("limit") or 10):
            break
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
    partial: str = "",
) -> HTMLResponse:
    selected_folder = normalize_folder(folder)
    filtered_docs = filter_docs(
        accessible_docs(employee_id),
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
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
    context = {
        "request": request,
        "employee_id": employee_id,
        "user_name": USER_NAMES.get(employee_id, employee_id),
        "teams": teams_for(employee_id),
        "docs": docs_for_template(docs, employee_id, selected_folder),
        "q": q,
        "event_type": event_type,
        "visibility": visibility,
        "boi_type": boi_type,
        "folder": selected_folder,
        "folder_tree": folder_tree,
        "breadcrumbs": breadcrumbs,
        "event_context": event_context_for_template(event_type, employee_id),
        "selected_folder_label": folder_label(selected_folder),
        "total_filtered_docs": len(filtered_docs),
        "event_types": load_event_types(),
        "event_logs": read_event_logs(limit=8),
    }
    template_name = "library_fragment.html" if partial == "library" else "index.html"
    return templates.TemplateResponse(template_name, context)


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
async def doc_page(
    request: Request,
    boi_id: str,
    employee_id: str = Depends(current_employee),
    folder: str = "",
) -> HTMLResponse:
    doc = find_doc_by_id(boi_id, employee_id)
    if not doc:
        raise HTTPException(status_code=404, detail="BoI not found or not accessible")
    doc_folder_path = doc_folder(doc)
    return_folder = normalize_folder(folder) or doc_folder_path
    workflow = doc["metadata"].get("workflow") or {}
    workflow_poc = equipment_workflow_context(employee_id) if workflow.get("workflow_key") == "equipment-anomaly" else None
    return templates.TemplateResponse(
        "doc.html",
        {
            "request": request,
            "employee_id": employee_id,
            "doc": doc,
            "doc_folder": doc_folder_path,
            "doc_folder_breadcrumbs": with_breadcrumb_urls(
                folder_breadcrumbs(doc_folder_path),
                employee_id=employee_id,
            ),
            "doc_list_url": browse_url(employee_id, folder=return_folder),
            "event_type_url": browse_url(employee_id, event_type=doc["metadata"].get("event_type", "")),
            "metadata_rows": metadata_rows_for_template(doc["metadata"]),
            "body_html": render_markdown(doc["body"]),
            "workflow_poc": workflow_poc,
            "action_spec": action_spec_for_template(doc["metadata"]),
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
) -> dict[str, Any]:
    selected_folder = normalize_folder(folder)
    filtered_docs = filter_docs(
        accessible_docs(employee_id),
        q=q,
        event_type=event_type,
        visibility=visibility,
        boi_type=boi_type,
    )
    docs = [d for d in filtered_docs if folder_matches(d, selected_folder)]
    return {
        "employee_id": employee_id,
        "teams": teams_for(employee_id),
        "folder": selected_folder,
        "breadcrumbs": folder_breadcrumbs(selected_folder),
        "folder_tree": build_folder_tree(filtered_docs, selected_folder),
        "count": len(docs),
        "items": docs,
    }


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
        "trace_id": req.trace_id or f"trace-{uuid.uuid4().hex}",
    }
    append_event_log(status="published", event=event)
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP, value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode())
    await producer.start()
    try:
        await producer.send_and_wait(BOI_EVENTS_TOPIC, event)
    finally:
        await producer.stop()
    return {"ok": True, "topic": BOI_EVENTS_TOPIC, "event": event}


EQUIPMENT_WORKFLOW_EVENT_SEQUENCE = [
    "equipment.alarm.raised.v1",
    "trend.anomaly.detected.v1",
    "root_cause.analysis.requested.v1",
    "maintenance.guide.requested.v1",
    "corrective_action.requested.v1",
]


def unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def equipment_workflow_event_defs() -> list[dict[str, Any]]:
    return [event for event_type in EQUIPMENT_WORKFLOW_EVENT_SEQUENCE if (event := get_event_type(event_type))]


def workflow_sop_context(employee_id: str) -> dict[str, Any]:
    event_defs = equipment_workflow_event_defs()
    sop_ref = next((str(event.get("sop_ref")) for event in event_defs if event.get("sop_ref")), "boi:public:sop:equipment-abnormal-response")
    sop_doc = find_doc_by_id(sop_ref, employee_id)
    return {
        "sop_ref": sop_ref,
        "sop_uri": str(sop_doc.get("uri", "")) if sop_doc else "",
        "sop_title": str((sop_doc or {}).get("metadata", {}).get("title", "")),
        "sop_url": doc_url_for_ref(sop_ref, employee_id),
    }


def action_details_for_keys(action_keys: list[str], employee_id: str) -> list[dict[str, Any]]:
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
                "doc_uri": action_doc_uri(action, employee_id),
                "requires_manual_action": action.get("requires_manual_action"),
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
        rows.append(
            "- "
            + f"`{detail.get('action_key')}`: {detail.get('name_ko')} "
            + f"/ connector={detail.get('connector_kind')} "
            + f"/ risk={detail.get('risk_level')} "
            + f"/ approval_required={detail.get('approval_required')} "
            + f"/ doc_ref=`{detail.get('doc_ref')}` "
            + f"/ doc_uri=`{detail.get('doc_uri')}`"
            + manual_note
        )
    return "\n".join(rows) if rows else "- 등록된 Action 없음"


def equipment_workflow_context(employee_id: str, trace_id: str | None = None) -> dict[str, Any]:
    event_defs = equipment_workflow_event_defs()
    automated_keys = unique_values([key for event in event_defs for key in (event.get("recommended_actions") or [])])
    manual_keys = unique_values([key for event in event_defs for key in (event.get("recommended_manual_actions") or [])])
    sop = workflow_sop_context(employee_id)
    context = {
        **sop,
        "expected_event_types": [event["event_type"] for event in event_defs],
        "expected_stages": [
            {
                "event_type": event.get("event_type"),
                "stage": event.get("workflow_stage"),
                "sop_stage_id": event.get("sop_stage_id"),
            }
            for event in event_defs
        ],
        "expected_actions": automated_keys,
        "expected_manual_actions": manual_keys,
        "action_details": action_details_for_keys(automated_keys, employee_id),
        "manual_action_details": action_details_for_keys(manual_keys, employee_id),
    }
    if trace_id:
        context["status_url"] = "/api/workflows/demo/equipment-anomaly/status?" + urlencode({"trace_id": trace_id, "employee_id": employee_id})
    return context


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
    trace_id = str(result["event"].get("trace_id") or "")
    workflow = equipment_workflow_context(employee_id, trace_id=trace_id)
    workflow.update(
        {
            "name": "equipment-anomaly",
            "first_event_type": "equipment.alarm.raised.v1",
            "expected_next": ["root_cause.analysis.requested.v1", "maintenance.guide.requested.v1", "corrective_action.requested.v1"],
        }
    )
    return {
        "ok": True,
        "workflow": workflow,
        "topic": result["topic"],
        "event": result["event"],
    }


@app.get("/api/workflows/demo/equipment-anomaly/status")
async def equipment_anomaly_status(trace_id: str, employee_id: str = Depends(current_employee)) -> dict[str, Any]:
    context = equipment_workflow_context(employee_id, trace_id=trace_id)
    events = [row for row in read_event_logs(limit=500) if row.get("trace_id") == trace_id]
    event_ids = {row.get("event_id") for row in events if row.get("event_id")}
    action_logs = [row for row in read_action_logs(limit=500) if row.get("trace_id") == trace_id or row.get("event_id") in event_ids]
    generated_docs = []
    for row in events:
        result = row.get("result") or {}
        boi_id = result.get("boi_id")
        if boi_id:
            generated_docs.append(
                {
                    "boi_id": boi_id,
                    "boi_uri": result.get("boi_uri"),
                    "doc_url": doc_url_for_ref(str(boi_id), employee_id),
                    "event_id": row.get("event_id"),
                    "event_type": row.get("event_type"),
                }
            )
    return {
        "ok": True,
        "trace_id": trace_id,
        "sop_ref": context["sop_ref"],
        "sop_uri": context["sop_uri"],
        "sop_url": context["sop_url"],
        "expected_event_types": context["expected_event_types"],
        "expected_actions": context["expected_actions"],
        "manual_handoffs": context["expected_manual_actions"],
        "action_details": context["action_details"],
        "manual_action_details": context["manual_action_details"],
        "events": events,
        "actions": action_logs,
        "generated_docs": generated_docs,
        "approval_required_actions": [row for row in action_logs if row.get("status") == "approval_required"],
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
        manual_action_keys = event_def.get("recommended_manual_actions") or []
        action_details = action_details_for_keys(action_keys, str(actor))
        manual_action_details = action_details_for_keys(manual_action_keys, str(actor))
        action_md = action_details_markdown(action_details)
        manual_action_md = action_details_markdown(manual_action_details)
        sop_ref = str(event_def.get("sop_ref") or "boi:public:sop:equipment-abnormal-response")
        sop_doc = find_doc_by_id(sop_ref, str(actor))
        sop_uri = str(sop_doc.get("uri", "")) if sop_doc else ""
        sop_title = str((sop_doc or {}).get("metadata", {}).get("title", ""))
        body = f"""# Summary

첨부 SOP 사례를 AI Native Workflow로 실행하기 위한 Private BoI 인스턴스입니다. Event Broker가 `{req.event_type}` 이벤트를 수신했고, Harness는 SOP 단계에 맞춰 필요한 API/Webhook Action 후보와 참조 BoI를 정리했습니다.

# SOP Stage

- Event Label: {event_label(req.event_type)}
- Workflow Stage: {event_def.get('workflow_stage', 'SOP Workflow')}
- SOP Stage ID: {event_def.get('sop_stage_id', '')}
- Default Flow: {event_def.get('default_flow_key', event_to_flow_key(req.event_type))}
- SOP Reference: `{sop_ref}`
- SOP Title: {sop_title}
- SOP URI: `{sop_uri}`

# Payload

```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```

# Recommended Automated Actions

{action_md}

# Manual Handoff Actions

{manual_action_md}

# AI Native Workflow Interpretation

1. Event Broker는 업무 시점, 예: 설비 Alarm 발생 또는 Trend 이상 감지를 발행합니다.
2. Langflow/Webhook/API Agent는 BoI Wiki에서 SOP와 관련 Runbook을 Lazy Loading합니다.
3. Agent는 필요한 데이터 조회 Action을 Action Gateway를 통해 호출합니다.
4. 사람 판단, 승인, 현장 조치는 manual action으로 남겨 human handoff를 추적합니다.
5. 분석 결과는 Private BoI로 남기고, 팀 재사용 가치가 있으면 명시적 요청으로 Team BoI draft 승격합니다.
6. 공정 진행 금지, Spec/Rule 변경 같은 고위험 Action은 자동 실행하지 않고 승인 필요 상태로만 기록합니다.

# References

- Source Event: `{req.event_id}`
- SOP: `{sop_ref}`
- SOP URI: `{sop_uri}`
"""
        source_refs = req.source_refs or [{"type": "boi", "ref": sop_ref}]
        source_refs = source_refs + [{"type": "sop", "ref": sop_ref, "uri": sop_uri}]
        for detail in action_details + manual_action_details:
            if detail.get("doc_ref"):
                source_refs.append({"type": "action-spec", "ref": detail.get("doc_ref"), "uri": detail.get("doc_uri")})
        meta = make_metadata(
            boi_type=event_to_boi_type(req.event_type),
            title=title,
            description="SOP 기반 AI Native Workflow 실행 인스턴스",
            owner=str(actor),
            source_event=event,
            source_refs=source_refs,
            tags=["SOP", "AI-Native-Workflow", "EventBroker", "ActionGateway", "BoIWiki"],
        )
        meta["workflow_stage"] = event_def.get("workflow_stage")
        meta["sop_ref"] = sop_ref
        meta["sop_uri"] = sop_uri
        meta["sop_stage_id"] = event_def.get("sop_stage_id")
        meta["recommended_actions"] = action_keys
        meta["recommended_manual_actions"] = manual_action_keys
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


@app.get("/event-types/{event_type:path}", response_class=HTMLResponse)
async def event_type_detail_page(request: Request, event_type: str, employee_id: str = Depends(current_employee)) -> HTMLResponse:
    event_def = get_event_type(event_type)
    if not event_def:
        raise HTTPException(status_code=404, detail=f"Event Type not found: {event_type}")
    docs = filter_docs(accessible_docs(employee_id), event_type=event_type)
    actions = [
        action
        for action in load_action_catalog()
        if event_type in (action.get("event_types") or []) or "*" in (action.get("event_types") or [])
    ]
    recent_events = read_event_logs(limit=20, event_type=event_type)
    return templates.TemplateResponse(
        "event_type_detail.html",
        {
            "request": request,
            "employee_id": employee_id,
            "event_type": event_type,
            "event": event_def,
            "docs": docs_for_template(docs, employee_id),
            "actions": actions_for_template(actions, employee_id),
            "api_mcp_actions": [
                action for action in actions_for_template(actions, employee_id) if action.get("connector_kind") in {"api", "mcp", "webhook", "langflow", "boi_writer", "event_broker"}
            ],
            "events": event_rows_for_template(recent_events),
            "stream_url": "/events?" + urlencode({"employee_id": employee_id, "event_type": event_type}),
            "actions_url": "/actions?" + urlencode({"employee_id": employee_id, "event_type": event_type}),
            "boi_filter_url": browse_url(employee_id, event_type=event_type),
            "run_example": event_run_example(event_type, employee_id),
        },
    )


@app.get("/events", response_class=HTMLResponse)
async def events_page(request: Request, employee_id: str = Depends(current_employee), event_type: str = "", trace_id: str = "") -> HTMLResponse:
    events = read_event_logs(limit=200, event_type=event_type or None, trace_id=trace_id or None)
    return templates.TemplateResponse(
        "events.html",
        {
            "request": request,
            "employee_id": employee_id,
            "event_type": event_type,
            "trace_id": trace_id,
            "event_types": load_event_types(),
            "events": event_rows_for_template(events),
        },
    )


@app.get("/api/event-types")
async def api_event_types() -> dict[str, Any]:
    return {"items": load_event_types()}


@app.get("/api/events/log")
async def api_event_logs(event_type: str = "", trace_id: str = "", limit: int = 200) -> dict[str, Any]:
    rows = read_event_logs(limit=limit, event_type=event_type or None, trace_id=trace_id or None)
    return {"count": len(rows), "items": rows}


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
            "actions": actions_for_template(actions, employee_id),
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
