from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import yaml

from .config import AgentV2Settings
from .models import Principal


FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣_.:-]+")
TERMINAL_ACTION_STATES = {"completed", "success", "succeeded", "failed", "cancelled", "rejected", "approved"}
OPEN_ACTION_STATES = {
    "open",
    "pending",
    "pending_confirmation",
    "awaiting_confirmation",
    "needs_confirmation",
    "running",
    "queued",
    "blocked",
}


KOREAN_PARTICLES = (
    "으로부터",
    "에게서",
    "에서는",
    "까지는",
    "부터는",
    "으로",
    "에서",
    "에게",
    "한테",
    "처럼",
    "보다",
    "까지",
    "부터",
    "와",
    "과",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "의",
    "에",
    "도",
    "만",
    "로",
)
KOREAN_ENDINGS = (
    "해주세요",
    "해줘요",
    "해줘",
    "되나요",
    "됩니다",
    "하는지",
    "하도록",
    "하는",
    "하고",
)
SEARCH_STOPWORDS = {
    "그리고",
    "그러면",
    "어떻게",
    "무엇을",
    "무엇이",
    "알려줘",
    "보여줘",
    "해줘",
}
NAVIGATION_MARKDOWN_NAMES = {"index.md", "log.md"}


def is_navigation_markdown(path: Path) -> bool:
    return path.name.lower() in NAVIGATION_MARKDOWN_NAMES


def normalize_tokens(value: str) -> set[str]:
    """Normalize Korean particles/endings without requiring a morphology service."""

    result: set[str] = set()
    for raw in TOKEN_RE.findall(value or ""):
        token = raw.lower()
        if len(token) <= 1 or token in SEARCH_STOPWORDS:
            continue
        for suffix in KOREAN_PARTICLES:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                token = token[: -len(suffix)]
                break
        for suffix in KOREAN_ENDINGS:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                token = token[: -len(suffix)]
                break
        if len(token) > 1 and token not in SEARCH_STOPWORDS:
            result.add(token)
    return result


def parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata if isinstance(metadata, dict) else {}, text[match.end() :]


def markdown_display_title(metadata: dict[str, Any], body: str, path: Path) -> str:
    for key in ("title", "title_ko", "term", "name", "name_ko"):
        value = re.sub(r"\s+", " ", str(metadata.get(key) or "")).strip()
        if value:
            return value[:200]
    heading = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    if heading:
        value = re.sub(r"\s+", " ", heading.group(1)).strip()
        if value:
            return value[:200]
    stem = path.stem.replace("-", " ").replace("_", " ").strip()
    return stem if stem.lower() not in {"index", "readme"} else "업무 지식 모음"


def row_identity(row: dict[str, Any], source: str) -> str:
    for key in ("event_id", "request_id", "action_id", "task_id", "trace_id", "id"):
        value = str(row.get(key) or "").strip()
        if value:
            return f"{source}:{value}"
    digest = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:20]
    return f"{source}:{digest}"


@dataclass
class KnowledgeRecord:
    record_id: str
    kind: str
    title: str
    description: str
    text: str
    url: str
    source: str
    authority: str
    status: str
    visibility: str = "public"
    owner: str = ""
    team_id: str = ""
    timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def search_blob(self) -> str:
        return "\n".join(
            [
                self.record_id,
                self.kind,
                self.title,
                self.description,
                self.text[:20000],
                json.dumps(self.metadata, ensure_ascii=False, default=str),
            ]
        ).lower()


class KnowledgeRepository:
    DISK_CACHE_VERSION = 4

    def __init__(self, settings: AgentV2Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._cache_signature = ""
        self._cache: list[KnowledgeRecord] = []
        self._signature_value = ""
        self._signature_checked_at = 0.0
        self._file_digest_cache: dict[str, tuple[int, int, str]] = {}
        self._history_cache: dict[str, tuple[float, list[KnowledgeRecord]]] = {}
        self._disk_cache_path = settings.runtime_root / "agent-v2" / "knowledge-index.json"

    def content_ready(self) -> bool:
        return self.settings.content_root.exists() and any(
            not is_navigation_markdown(path)
            for path in self.settings.content_root.rglob("*.md")
        )

    def source_signature(self) -> str:
        return self._signature()

    def invalidate_source_cache(self) -> None:
        """Force the next authoritative read to observe newly promoted assets."""

        with self._lock:
            self._signature_value = ""
            self._signature_checked_at = 0.0
            self._cache_signature = ""
            self._cache = []

    def _signature(self) -> str:
        now = time.monotonic()
        if self._signature_value and now - self._signature_checked_at < 5.0:
            return self._signature_value
        roots = [
            ("content", self.settings.content_root),
            ("event_catalog", self.settings.event_catalog_root),
            ("action_catalog", self.settings.action_catalog_root),
            ("workflow_catalog", self.settings.workflow_catalog_root),
            ("action_skill_catalog", self.settings.action_skill_catalog_root),
            ("data_lake", self.settings.runtime_root / "data-lake-artifacts" / "metadata"),
        ]
        values: list[str] = []
        for root_kind, root in roots:
            if not root.exists():
                continue
            for path in (
                sorted(root.rglob("*.md"))
                + sorted(root.rglob("*.yaml"))
                + sorted(root.rglob("*.json"))
            ):
                if is_navigation_markdown(path):
                    continue
                try:
                    stat = path.stat()
                    relative = path.relative_to(root).as_posix()
                    cache_key = f"{root_kind}:{relative}"
                    cached = self._file_digest_cache.get(cache_key)
                    if cached and cached[:2] == (stat.st_mtime_ns, stat.st_size):
                        digest = cached[2]
                    else:
                        content_hash = hashlib.sha256()
                        with path.open("rb") as handle:
                            for chunk in iter(lambda: handle.read(128 * 1024), b""):
                                content_hash.update(chunk)
                        digest = content_hash.hexdigest()
                        self._file_digest_cache[cache_key] = (stat.st_mtime_ns, stat.st_size, digest)
                    values.append(f"{root_kind}:{relative}:{digest}")
                except OSError:
                    continue
        self._signature_value = hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()
        self._signature_checked_at = now
        return self._signature_value

    def _visible(self, record: KnowledgeRecord, principal: Principal) -> bool:
        if principal.is_admin or record.visibility == "public":
            return True
        if record.visibility == "private":
            return record.owner == principal.employee_id or f"/private/{principal.employee_id}/" in record.url
        if record.visibility == "team":
            return bool(record.team_id and record.team_id in principal.teams)
        return False

    @staticmethod
    def _is_searchable(record: KnowledgeRecord, include_drafts: bool) -> bool:
        if include_drafts:
            return True
        if record.status.lower() in {"draft", "candidate", "deprecated", "test", "smoke"}:
            return False
        marker = f"{record.title} {record.description} {record.metadata.get('tags', [])}".lower()
        return "smoke" not in marker and "fixture" not in marker

    def _markdown_records(self) -> list[KnowledgeRecord]:
        root = self.settings.content_root
        if not root.exists():
            return []

        def load(path: Path) -> KnowledgeRecord | None:
            if is_navigation_markdown(path):
                return None
            try:
                metadata, body = parse_markdown(path)
            except OSError:
                return None
            relative = path.relative_to(root).as_posix()
            explicit_boi_id = str(metadata.get("boi_id") or "")
            boi_id = explicit_boi_id or f"doc:{relative}"
            route_ref = explicit_boi_id or relative
            boi_type = str(metadata.get("type") or "boi/document")
            visibility = str(metadata.get("visibility") or relative.split("/", 1)[0] or "public")
            owner = str(metadata.get("owner") or "")
            if visibility == "private" and not owner:
                parts = relative.split("/")
                owner = parts[1] if len(parts) > 1 else ""
            status = str(metadata.get("status") or "reviewed")
            authority = "published" if status in {"published", "reviewed", "active"} else status
            return KnowledgeRecord(
                record_id=boi_id,
                kind=self._kind_for_boi_type(boi_type),
                title=markdown_display_title(metadata, body, path),
                description=str(metadata.get("description") or ""),
                text=body,
                url=f"/docs/{quote(route_ref, safe='')}",
                source="knowledge",
                authority=authority,
                status=status,
                visibility=visibility,
                owner=owner,
                team_id=str(metadata.get("team_id") or ""),
                timestamp=str(metadata.get("timestamp") or ""),
                metadata={**metadata, "relative_path": relative},
            )

        paths = list(root.rglob("*.md"))
        with ThreadPoolExecutor(max_workers=min(12, max(2, len(paths) // 50))) as executor:
            loaded = list(executor.map(load, paths))
        return [record for record in loaded if record is not None]

    def _data_lake_records(self) -> list[KnowledgeRecord]:
        root = self.settings.runtime_root / "data-lake-artifacts" / "metadata"
        if not root.exists():
            return []
        records: list[KnowledgeRecord] = []
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            artifact_id = str(payload.get("artifact_id") or path.stem).strip()
            if not artifact_id:
                continue
            profile = payload.get("profile") if isinstance(payload.get("profile"), dict) else {}
            source_context = (
                payload.get("source_context") if isinstance(payload.get("source_context"), dict) else {}
            )
            sample = profile.get("sample") or profile.get("sample_rows") or payload.get("sample") or []
            if isinstance(sample, list):
                sample = sample[:5]
            elif isinstance(sample, dict):
                sample = {key: sample[key] for key in list(sample)[:20]}
            else:
                sample = []
            summary = str(
                profile.get("summary")
                or payload.get("description")
                or source_context.get("description")
                or ""
            )
            title = str(payload.get("label") or payload.get("filename") or artifact_id)
            visibility = str(payload.get("visibility") or "private")
            owner = str(payload.get("owner_employee_id") or payload.get("owner") or "")
            try:
                size_bytes = int(payload.get("size_bytes") or 0)
            except (TypeError, ValueError):
                size_bytes = 0
            records.append(
                KnowledgeRecord(
                    record_id=f"data_artifact:{artifact_id}",
                    kind="data_artifact",
                    title=title,
                    description=summary,
                    text=json.dumps(
                        {
                            "summary": summary,
                            "profile": {
                                key: value
                                for key, value in profile.items()
                                if key not in {"raw", "content", "rows", "full_text"}
                            },
                            "sample": sample,
                            "source_context": source_context,
                        },
                        ensure_ascii=False,
                        default=str,
                    )[:20000],
                    url=f"/api/data-lake/artifacts/{quote(artifact_id, safe='')}",
                    source="data_lake",
                    authority="runtime",
                    status=str(payload.get("validation_state") or "uploaded"),
                    visibility=visibility,
                    owner=owner,
                    team_id=str(payload.get("team_id") or ""),
                    timestamp=str(payload.get("updated_at") or payload.get("created_at") or ""),
                    metadata={
                        "artifact_id": artifact_id,
                        "sha256": str(payload.get("sha256") or ""),
                        "content_type": str(payload.get("content_type") or ""),
                        "size_bytes": size_bytes,
                        "source_context": source_context,
                    },
                )
            )
        return records

    def _load_disk_cache(self, signature: str) -> list[KnowledgeRecord] | None:
        try:
            payload = json.loads(self._disk_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if payload.get("cache_version") != self.DISK_CACHE_VERSION or payload.get("signature") != signature:
            return None
        try:
            return [KnowledgeRecord(**item) for item in payload.get("records") or []]
        except (TypeError, ValueError):
            return None

    def _write_disk_cache(self, signature: str, records: list[KnowledgeRecord]) -> None:
        try:
            self._disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._disk_cache_path.write_text(
                json.dumps(
                    {
                        "cache_version": self.DISK_CACHE_VERSION,
                        "signature": signature,
                        "records": [record.__dict__ for record in records],
                    },
                    ensure_ascii=False,
                    default=str,
                ),
                encoding="utf-8",
            )
        except OSError:
            return

    @staticmethod
    def _kind_for_boi_type(boi_type: str) -> str:
        lowered = boi_type.lower()
        if "dictionary" in lowered:
            return "dictionary"
        if "sop" in lowered or "workflow" in lowered:
            return "sop"
        if "action" in lowered:
            return "action"
        if "event" in lowered:
            return "event"
        if "skill" in lowered:
            return "skill"
        if "inbox" in lowered:
            return "case"
        return "document"

    @staticmethod
    def _yaml_items(path: Path, key: str) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        values = payload.get(key) if isinstance(payload, dict) else []
        return [item for item in (values or []) if isinstance(item, dict)]

    def _catalog_records(self) -> list[KnowledgeRecord]:
        records: list[KnowledgeRecord] = []
        specs = [
            (self.settings.event_catalog_root / "event_types.yaml", "event_types", "event", "event_type", "name_ko"),
            (self.settings.action_catalog_root / "actions.yaml", "actions", "action", "action_key", "name_ko"),
            (
                self.settings.workflow_catalog_root / "workflows.yaml",
                "workflows",
                "workflow",
                "workflow_definition_key",
                "title",
            ),
            (
                self.settings.action_skill_catalog_root / "skills.yaml",
                "action_skills",
                "skill",
                "skill_key",
                "title",
            ),
        ]
        for path, key, kind, id_field, title_field in specs:
            for item in self._yaml_items(path, key):
                item_id = str(item.get(id_field) or "").strip()
                if not item_id:
                    continue
                status = str(item.get("status") or ("active" if item.get("enabled", True) else "disabled"))
                url = {
                    "event": f"/event-types/{quote(item_id, safe='')}",
                    "action": f"/actions?action_key={quote(item_id, safe='')}",
                    "workflow": f"/workflows/definitions?q={quote(item_id, safe='')}",
                    "skill": f"/agent?capability=skill.plan&seed={quote(item_id, safe='')}",
                }[kind]
                records.append(
                    KnowledgeRecord(
                        record_id=f"{kind}:{item_id}",
                        kind=kind,
                        title=str(item.get(title_field) or item_id),
                        description=str(item.get("description") or item.get("business_goal") or ""),
                        text=json.dumps(item, ensure_ascii=False, default=str),
                        url=url,
                        source="catalog",
                        authority="reviewed" if status in {"reviewed", "active", "poc"} else status,
                        status=status,
                        metadata=item,
                    )
                )
        return records

    def authoritative_records(self, principal: Principal, *, include_drafts: bool = False) -> list[KnowledgeRecord]:
        signature = self._signature()
        with self._lock:
            if signature != self._cache_signature:
                cached = self._load_disk_cache(signature)
                self._cache = (
                    cached
                    if cached is not None
                    else [*self._markdown_records(), *self._catalog_records(), *self._data_lake_records()]
                )
                self._cache_signature = signature
                if cached is None:
                    self._write_disk_cache(signature, self._cache)
            records = list(self._cache)
        return [record for record in records if self._visible(record, principal) and self._is_searchable(record, include_drafts)]

    @staticmethod
    def _jsonl_rows(root: Path, prefix: str, source: str) -> Iterable[dict[str, Any]]:
        if not root.exists():
            return []
        result: list[dict[str, Any]] = []
        indexed_files: set[str] = set()
        for index_path in sorted(root.glob(f"{prefix}-*.jsonl.idx")):
            indexed_files.add(index_path.name.removesuffix(".idx"))
            try:
                with index_path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line_number, line in enumerate(handle, 1):
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(row, dict):
                            result.append(
                                {
                                    **row,
                                    "_source": source,
                                    "_file": str(row.get("file") or index_path.name.removesuffix(".idx")),
                                    "_line": int(row.get("line_number") or line_number),
                                    "_indexed_summary": True,
                                }
                            )
            except OSError:
                continue
        for path in sorted(root.glob(f"{prefix}-*.jsonl")):
            if path.name in indexed_files:
                continue
            try:
                if path.stat().st_size > 64 * 1024 * 1024:
                    continue
            except OSError:
                continue
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line_number, line in enumerate(handle, 1):
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(row, dict):
                            result.append({**row, "_source": source, "_file": path.name, "_line": line_number})
            except OSError:
                continue
        return result

    def history_records(self, principal: Principal, *, include_seed: bool = True) -> list[KnowledgeRecord]:
        now = time.monotonic()
        cache_key = f"{'admin' if principal.is_admin else principal.employee_id}:{'seed' if include_seed else 'active'}"
        cached = self._history_cache.get(cache_key)
        if cached and now - cached[0] < 5.0:
            records = list(cached[1])
            if not include_seed:
                records = [item for item in records if item.source != "history_seed"]
            return [
                item
                for item in records
                if principal.is_admin or not item.owner or item.owner == principal.employee_id
            ]
        sources: list[tuple[Path, str]] = [
            (self.settings.runtime_root / "events", "active_event"),
            (self.settings.runtime_root / "actions", "active_action"),
        ]
        if include_seed and self.settings.history_seed_root:
            sources.extend(
                [
                    (self.settings.history_seed_root / "events", "history_seed_event"),
                    (self.settings.history_seed_root / "actions", "history_seed_action"),
                ]
            )
        records: list[KnowledgeRecord] = []
        seen: set[str] = set()
        for root, source in sources:
            prefix = "events" if "event" in source else "actions"
            for row in self._jsonl_rows(root, prefix, source):
                employee_id = str(row.get("employee_id") or (row.get("payload") or {}).get("employee_id") or "")
                if employee_id and employee_id != principal.employee_id and not principal.is_admin:
                    continue
                identity = row_identity(row, source.replace("history_seed_", ""))
                base_identity = identity.replace("active_", "").replace("history_seed_", "")
                if base_identity in seen:
                    continue
                seen.add(base_identity)
                title = str(
                    row.get("title")
                    or row.get("name")
                    or row.get("event_type")
                    or row.get("action_key")
                    or row.get("request_id")
                    or "실행 이력"
                )
                status = str(row.get("status") or row.get("decision") or "recorded")
                records.append(
                    KnowledgeRecord(
                        record_id=identity,
                        kind="case",
                        title=title,
                        description=str(row.get("summary") or row.get("message") or row.get("result_summary") or ""),
                        text=json.dumps(row, ensure_ascii=False, default=str),
                        url="/events" if "event" in source else "/actions?view=history",
                        source="history_seed" if source.startswith("history_seed") else "runtime",
                        authority="historical" if source.startswith("history_seed") else "runtime",
                        status=status,
                        visibility="private",
                        owner=employee_id or principal.employee_id,
                        timestamp=str(row.get("logged_at") or row.get("timestamp") or row.get("created_at") or ""),
                        metadata=row,
                    )
                )
        self._history_cache[cache_key] = (now, list(records))
        if not include_seed:
            records = [item for item in records if item.source != "history_seed"]
        return records

    def current_work(self, principal: Principal, *, limit: int = 50) -> list[KnowledgeRecord]:
        records = self.history_records(principal, include_seed=False)
        current: list[KnowledgeRecord] = []
        for record in records:
            if record.source != "runtime" or "action" not in record.record_id:
                continue
            state = record.status.lower()
            metadata = record.metadata
            requires_confirmation = bool(metadata.get("approval_required") or metadata.get("requires_confirmation"))
            if state in OPEN_ACTION_STATES or (requires_confirmation and state not in TERMINAL_ACTION_STATES):
                current.append(record)
        current.sort(key=lambda item: item.timestamp, reverse=True)
        return current[:limit]

    def ontology_aliases(self, query: str, principal: Principal) -> list[str]:
        query_tokens = normalize_tokens(query)
        aliases: list[str] = []
        for record in self.authoritative_records(principal):
            if record.kind != "dictionary":
                continue
            values = [record.title]
            for key in ("aliases", "related", "related_terms", "broader", "narrower", "tags"):
                raw = record.metadata.get(key)
                if isinstance(raw, list):
                    values.extend(str(item) for item in raw)
                elif raw:
                    values.append(str(raw))
            value_tokens = normalize_tokens(" ".join(values))
            if query_tokens & value_tokens:
                aliases.extend(values)
        deduped: list[str] = []
        for value in aliases:
            clean = value.strip()
            if clean and clean.lower() not in {item.lower() for item in deduped}:
                deduped.append(clean)
        return deduped[:20]

    def stats(self, principal: Principal) -> dict[str, Any]:
        records = self.authoritative_records(principal)
        all_history = self.history_records(principal, include_seed=True)
        active = [item for item in all_history if item.source != "history_seed"]
        seed = [item for item in all_history if item.source == "history_seed"]
        counts: dict[str, int] = {}
        for record in records:
            counts[record.kind] = counts.get(record.kind, 0) + 1
        return {
            "content_root": str(self.settings.content_root),
            "content_ready": self.content_ready(),
            "authoritative_records": len(records),
            "by_kind": counts,
            "active_history_records": len(active),
            "seed_history_records": len(seed),
        }
