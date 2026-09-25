from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import yaml

from .config import AgentV2Settings
from .models import Principal
from ..domain_status import (
    ACTION_OPEN_STATES,
    ACTION_TERMINAL_STATES,
    normalized_action_outcome_status,
)
from ..governed_runtime.artifact_access import artifact_acl_shape_valid
from ..governed_runtime.canonical_projection_reader import CanonicalProjectionReader
from ..governed_runtime.projection import evaluate_release_projection, load_active_release_pointer

logger = logging.getLogger(__name__)


FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
TOKEN_RE = re.compile(r"[\w.+:-]+", re.UNICODE)
NUMBER_TOKEN_RE = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?")


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


def _suffixes_by_last_character(suffixes: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for suffix in suffixes:
        if suffix:
            grouped.setdefault(suffix[-1], []).append(suffix)
    return {key: tuple(values) for key, values in grouped.items()}


# A suffix can only match when its final character matches the token's final
# character. Preserving declaration order inside each group keeps token
# semantics identical while avoiding a full particle/ending scan for every
# English identifier and every word in large operational records.
KOREAN_PARTICLES_BY_LAST_CHARACTER = _suffixes_by_last_character(KOREAN_PARTICLES)
KOREAN_ENDINGS_BY_LAST_CHARACTER = _suffixes_by_last_character(KOREAN_ENDINGS)
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


@lru_cache(maxsize=65_536)
def _normalize_token(raw: str) -> str:
    if NUMBER_TOKEN_RE.fullmatch(raw):return raw.lower()
    token = raw.lower().strip("._:-")
    if not token or token in SEARCH_STOPWORDS or (len(token)==1 and token in KOREAN_PARTICLES):
        return ""
    for suffix in KOREAN_PARTICLES_BY_LAST_CHARACTER.get(token[-1], ()):
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            token = token[: -len(suffix)]
            break
    for suffix in KOREAN_ENDINGS_BY_LAST_CHARACTER.get(token[-1], ()):
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            token = token[: -len(suffix)]
            break
    return token if token and token not in SEARCH_STOPWORDS else ""


@lru_cache(maxsize=65_536)
def _identifier_lexemes(raw: str) -> tuple[str, ...]:
    """Retain exact spelling plus lexical parts, never infer aliases or roles.

    Numeric punctuation remains intact (1.25 is not a mention of 25). Lowercase
    alphanumeric runs and content digests stay whole; underscore/qualified names
    and case boundaries expose their actual words without expanding acronyms.
    """
    if NUMBER_TOKEN_RE.fullmatch(raw) or not any(c.isalpha() for c in raw):return (raw,)
    parts=[raw]
    for segment in re.findall(r"[^\W_]+",raw,re.UNICODE):
        parts.append(segment)
        start=0
        for i in range(1,len(segment)):
            if (segment[i-1].islower() and segment[i].isupper()
                    or segment[i-1].isupper() and segment[i].isupper()
                    and i+1<len(segment) and segment[i+1].islower()):
                parts.append(segment[start:i]);start=i
        parts.append(segment[start:])
    return tuple(dict.fromkeys(parts))


@lru_cache(maxsize=16_384)
def normalize_tokens(value: str) -> frozenset[str]:
    """Normalize Korean particles/endings without requiring a morphology service."""

    # The result is a set, so repeated raw tokens cannot affect semantics.
    # Deduplicating before normalization and sharing token-level normalization
    # across records avoids repeatedly processing common JSON keys and workflow
    # vocabulary in large append-only history partitions.
    result = {
        token
        for raw in set(TOKEN_RE.findall(value or ""))
        for part in _identifier_lexemes(raw)
        if (token := _normalize_token(part))
    }
    # Search treats tokens as immutable values.  Returning a frozenset makes
    # the shared cache safe across principals and concurrent requests while
    # avoiding repeated normalization of the same versioned record fields.
    return frozenset(result)


def query_lexeme_weights(value: str) -> dict[str, float]:
    """One query spelling has one vote, even if it yields several index words."""
    weights={}
    for raw in set(TOKEN_RE.findall(value or '')):
        family=normalize_tokens(raw)
        for token in family:weights[token]=max(weights.get(token,0.0),1/len(family))
    return weights


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
    # An ActionRun is a child of an EventOccurrence. Several Actions can share
    # one event_id, so event-first identity silently collapsed an entire
    # workflow stage into whichever log row happened to be read first. Events
    # keep event identity; Actions keep invocation identity and retain the
    # event_id in provenance metadata for reverse traversal.
    keys = (
        ("request_id", "action_id", "task_id", "event_id", "trace_id", "id")
        if "action" in source
        else ("event_id", "request_id", "action_id", "task_id", "trace_id", "id")
    )
    for key in keys:
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
    DISK_CACHE_VERSION = 6
    AUTHORITY_SCOPE_LEVELS = {"person": 1, "team": 2, "org": 3, "company": 4}

    def __init__(self, settings: AgentV2Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._cache_signature = ""
        self._cache: list[KnowledgeRecord] = []
        self._signature_value = ""
        self._file_digest_cache: dict[str, tuple[int, int, str]] = {}
        self._history_cache: dict[str, tuple[str, list[KnowledgeRecord]]] = {}
        self._disk_cache_path = settings.runtime_root / "agent-v2" / "knowledge-index.json"

    def content_ready(self) -> bool:
        if self.settings.canonical_projection_enabled:
            return bool(
                CanonicalProjectionReader(
                    self.settings.runtime_root
                ).wiki_documents()
            )
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
            self._cache_signature = ""
            self._cache = []

    def _signature(self) -> str:
        # Canonical knowledge is a versioned read model. Repository mutation,
        # promotion, compiler, and reconcile paths explicitly invalidate this
        # snapshot. Rewalking every source tree on a five-second timer inside
        # user requests both mixed revisions within one turn and added seconds
        # of latency after a normal planner call.
        if self._signature_value:
            return self._signature_value
        roots: list[tuple[str, Path]] = []
        values: list[str] = []
        if self.settings.canonical_projection_enabled:
            bundle = CanonicalProjectionReader(self.settings.runtime_root).load_active()
            values.append(
                "canonical:"
                f"{bundle.release_id}:"
                f"{bundle.release_manifest_digest}:"
                f"{bundle.projection_digest}"
            )
            # The canonical branch does not walk the content root, so the
            # native-knowledge snapshot must be folded into the signature
            # explicitly; otherwise a refreshed snapshot would never
            # invalidate the cached index here.
            if self.settings.native_knowledge_search_enabled:
                values.append(self._native_knowledge_snapshot_signature())
        else:
            roots = [
                ("content", self.settings.content_root),
                ("event_catalog", self.settings.event_catalog_root),
                ("action_catalog", self.settings.action_catalog_root),
                ("workflow_catalog", self.settings.workflow_catalog_root),
                ("action_skill_catalog", self.settings.action_skill_catalog_root),
                ("data_lake", self.settings.runtime_root / "data-lake-artifacts" / "metadata"),
            ]
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
        # The native-knowledge snapshot file is walked above, but the adapter
        # flag alone must also invalidate the cached index (flag flip with an
        # unchanged file must not keep serving the previous record set).
        values.append(f"native_knowledge_search_enabled:{self.settings.native_knowledge_search_enabled}")
        self._signature_value = hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()
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

    @staticmethod
    def answer_scope(record: KnowledgeRecord) -> str:
        explicit = str(record.metadata.get("answer_scope") or "").strip().lower()
        if explicit in {"canonical", "operational", "validation", "generated", "navigation", "deprecated"}:
            return explicit
        if record.status.lower() == "deprecated":
            return "deprecated"
        relative = str(record.metadata.get("relative_path") or "").lower()
        boi_type = str(record.metadata.get("type") or "").lower()
        tags = " ".join(str(item) for item in record.metadata.get("tags") or []).lower()
        if relative.rsplit("/", 1)[-1] in NAVIGATION_MARKDOWN_NAMES:
            return "navigation"
        if "validation" in boi_type or "/validation/" in f"/{relative}" or "acceptance" in tags:
            return "validation"
        if "source-wiki" in relative or "generated" in boi_type or record.source == "generated":
            return "generated"
        if record.source != "knowledge" or "/operations/" in f"/{relative}" or "runbook" in relative:
            return "operational"
        return "canonical"

    @classmethod
    def authority_scope(cls, record: KnowledgeRecord) -> str:
        explicit = str(record.metadata.get("authority_scope") or "").strip().lower()
        if explicit in cls.AUTHORITY_SCOPE_LEVELS:
            return explicit
        visibility = str(record.visibility or "").strip().lower()
        # Authorship is provenance, not organizational authority.  Public
        # canonical knowledge frequently retains an owner/steward for review;
        # treating that metadata as personal scope wrongly prevents the same
        # published source from supporting company-level claims.
        if visibility == "private":
            return "person"
        if visibility == "team":
            return "team"
        if visibility in {"org", "organization"}:
            return "org"
        return "company"

    @classmethod
    def authority_scope_value_satisfies(cls, source_scope: str, required_scope: str) -> bool:
        required = str(required_scope or "any").strip().lower()
        if required == "any":
            return True
        source = str(source_scope or "").strip().lower()
        return cls.AUTHORITY_SCOPE_LEVELS.get(source, 0) >= cls.AUTHORITY_SCOPE_LEVELS.get(required, 99)

    @classmethod
    def authority_scope_satisfies(cls, record: KnowledgeRecord, required_scope: str) -> bool:
        return cls.authority_scope_value_satisfies(cls.authority_scope(record), required_scope)

    def _markdown_records(self) -> list[KnowledgeRecord]:
        if self.settings.canonical_projection_enabled:
            return self._canonical_projection_records()
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
                metadata={**metadata, "relative_path": relative, "answer_scope": str(metadata.get("answer_scope") or "")},
            )

        paths = list(root.rglob("*.md"))
        with ThreadPoolExecutor(max_workers=min(12, max(2, len(paths) // 50))) as executor:
            loaded = list(executor.map(load, paths))
        return [record for record in loaded if record is not None]

    def _canonical_projection_records(self) -> list[KnowledgeRecord]:
        documents = CanonicalProjectionReader(
            self.settings.runtime_root
        ).wiki_documents()
        records: list[KnowledgeRecord] = []
        for document in documents:
            metadata = dict(document["metadata"])
            body = str(document["body"])
            boi_id = str(metadata["boi_id"])
            status = str(metadata.get("status") or "stable")
            authority = (
                "published"
                if status in {"published", "reviewed", "active", "stable"}
                else status
            )
            records.append(
                KnowledgeRecord(
                    record_id=boi_id,
                    kind=self._kind_for_boi_type(
                        str(metadata.get("type") or "boi/document")
                    ),
                    title=markdown_display_title(metadata, body, Path(boi_id)),
                    description=str(metadata.get("description") or ""),
                    text=body,
                    url=f"/docs/{quote(boi_id, safe='')}",
                    source="knowledge",
                    authority=authority,
                    status=status,
                    visibility=str(metadata.get("visibility") or ""),
                    owner=str(metadata.get("owner") or ""),
                    team_id=str(metadata.get("team_id") or ""),
                    timestamp=str(metadata.get("timestamp") or ""),
                    metadata={
                        **metadata,
                        "relative_path": "",
                        "answer_scope": str(metadata.get("answer_scope") or ""),
                        "canonical_projection": True,
                        "governance": dict(document["governance"]),
                    },
                )
            )
        return records

    def _data_lake_records(self) -> list[KnowledgeRecord]:
        root = self.settings.runtime_root / "data-lake-artifacts" / "metadata"
        if not root.exists():
            return []
        records: list[KnowledgeRecord] = []
        active_pointer = load_active_release_pointer(self.settings.runtime_root)
        for path in sorted(root.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            if not artifact_acl_shape_valid(payload):
                continue
            if not evaluate_release_projection(payload, active_pointer).visible:
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
                        "governance": payload.get("governance") if isinstance(payload.get("governance"), dict) else {},
                    },
                )
            )
        return records

    NATIVE_KNOWLEDGE_SNAPSHOT_NAME = "native-knowledge.json"
    NATIVE_KNOWLEDGE_SCHEMA = "boi/native-knowledge-snapshot@1"

    @staticmethod
    def _native_knowledge_snapshot_digest(payload: dict[str, Any]) -> str:
        """sha256 over the canonical sorted-keys JSON minus digest/time fields.

        Must stay byte-compatible with the exporter's canonical_digest
        (scripts/governed_runtime/export_native_knowledge.py).
        """
        digest_payload = {
            key: value
            for key, value in payload.items()
            if key not in ("sha256", "generated_at")
        }
        canonical = json.dumps(
            digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _native_knowledge_snapshot_signature(self) -> str:
        """Raw-content digest of the snapshot file, for cache invalidation.

        ``absent`` when the file does not exist so a missing file is a stable,
        distinct signature (and thus a distinct index state).
        """
        path = self.settings.content_root / self.NATIVE_KNOWLEDGE_SNAPSHOT_NAME
        try:
            return f"native-knowledge:{hashlib.sha256(path.read_bytes()).hexdigest()}"
        except OSError:
            return "native-knowledge:absent"

    def _native_knowledge_records(self) -> list[KnowledgeRecord]:
        """Passive reader for the exported native-knowledge snapshot (D1(a)).

        The exporter precomputes the ruled identifier join and the inclusion
        decision offline (snapshot schema ``boi/native-knowledge-snapshot@1``).
        This method re-derives only the file digest and materializes
        ``included`` assets as search records; it never re-joins identifiers,
        re-scores, or re-filters at read time. Missing file, flag off,
        unknown schema, or digest mismatch all yield ``[]`` (never a partial
        ingest).
        """
        if not self.settings.native_knowledge_search_enabled:
            return []
        path = self.settings.content_root / self.NATIVE_KNOWLEDGE_SNAPSHOT_NAME
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict):
            return []
        if payload.get("schema") != self.NATIVE_KNOWLEDGE_SCHEMA:
            logger.warning(
                "native-knowledge snapshot rejected: unsupported schema %r",
                payload.get("schema"),
            )
            return []
        stored_digest = str(payload.get("sha256") or "")
        recomputed_digest = self._native_knowledge_snapshot_digest(payload)
        if not stored_digest or recomputed_digest != stored_digest:
            logger.warning(
                "native-knowledge snapshot rejected: sha256 mismatch "
                "(stored %s, recomputed %s); no records ingested",
                stored_digest or "<missing>",
                recomputed_digest,
            )
            return []
        assets = payload.get("assets")
        if not isinstance(assets, list):
            return []
        records: list[KnowledgeRecord] = []
        for asset in assets:
            if not isinstance(asset, dict) or asset.get("included") is not True:
                continue
            corpus = asset.get("corpus") if isinstance(asset.get("corpus"), dict) else {}
            boi_id = str(corpus.get("boi_id") or "").strip()
            record_id = str(asset.get("record_id") or "").strip() or boi_id
            if not record_id:
                continue
            stable_id = str(asset.get("stable_id") or "")
            body = str(asset.get("body") or "")
            selection = (
                asset.get("selection") if isinstance(asset.get("selection"), dict) else {}
            )
            boi_type = str(corpus.get("type") or "boi/document")
            title = (
                str(asset.get("title") or "").strip()
                or str(corpus.get("title") or "").strip()
                or record_id
            )
            records.append(
                KnowledgeRecord(
                    record_id=record_id,
                    kind=self._kind_for_boi_type(boi_type),
                    title=title,
                    description=str(corpus.get("description") or ""),
                    text=body,
                    url=f"/docs/{quote(record_id, safe='')}",
                    source="native_knowledge",
                    authority="published",
                    status="stable",
                    visibility=str(asset.get("visibility") or "public"),
                    owner=str(asset.get("owner") or corpus.get("owner") or ""),
                    team_id=str(asset.get("team_id") or corpus.get("team_id") or ""),
                    timestamp=str(corpus.get("generated_at") or ""),
                    metadata={
                        "answer_scope": "canonical",
                        "kobject_stable_id": stable_id,
                        "revision": str(asset.get("revision") or ""),
                        "selection": selection,
                        "svid": str(asset.get("svid") or ""),
                        "boi_id_resolution": "corpus_crossref" if boi_id else "fallback",
                        "mapping_status": str(asset.get("mapping_status") or ""),
                        "visibility_basis": str(asset.get("visibility_basis") or ""),
                        "store_scope": str(asset.get("store_scope") or ""),
                        "use_qualification": asset.get("use_qualification"),
                        "semantic_truth_proven": asset.get("semantic_truth_proven"),
                        "declared_unresolved": asset.get("declared_unresolved"),
                        "source_fidelity_qualified": asset.get("source_fidelity_qualified"),
                        "relative_path": str(corpus.get("relative_path") or ""),
                        "type": boi_type,
                        "snapshot_sha256": stored_digest,
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
                if cached is None:
                    base = (
                        self._markdown_records()
                        if self.settings.canonical_projection_enabled
                        else [
                            *self._markdown_records(),
                            *self._catalog_records(),
                            *self._data_lake_records(),
                        ]
                    )
                    # Identifier restoration assigns the corpus boi_id as the
                    # native-knowledge record identity. Corpus-sourced records
                    # win any record_id collision, so a colliding adapter
                    # record is dropped (never a duplicate).
                    occupied = {record.record_id for record in base}
                    native = [
                        record
                        for record in self._native_knowledge_records()
                        if record.record_id not in occupied
                    ]
                    self._cache = [*base, *native]
                    self._write_disk_cache(signature, self._cache)
                else:
                    self._cache = cached
                self._cache_signature = signature
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

    def _history_sources(self, *, include_seed: bool) -> list[tuple[Path, str]]:
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
        return sources

    @staticmethod
    def _history_source_revision(sources: list[tuple[Path, str]]) -> str:
        """Return a cheap revision for the append-only history partitions.

        History used to be cached for five seconds. A normal planner call can
        exceed that TTL, so the execution phase reparsed the same JSONL files
        in the same turn. File identity, size, and nanosecond mtime preserve
        freshness while allowing one immutable history snapshot to be reused
        for the full request.
        """

        digest = hashlib.sha256()
        for root, source in sources:
            digest.update(f"{source}:{root}:".encode("utf-8"))
            if not root.exists():
                digest.update(b"missing\n")
                continue
            prefix = "events" if "event" in source else "actions"
            paths = sorted(
                [
                    *root.glob(f"{prefix}-*.jsonl"),
                    *root.glob(f"{prefix}-*.jsonl.idx"),
                ],
                key=lambda item: item.name,
            )
            for path in paths:
                try:
                    stat = path.stat()
                except OSError:
                    continue
                digest.update(
                    f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}\n".encode("utf-8")
                )
        return digest.hexdigest()

    def history_source_revision(self, *, include_seed: bool = True) -> str:
        return self._history_source_revision(
            self._history_sources(include_seed=include_seed)
        )

    def history_records(self, principal: Principal, *, include_seed: bool = True) -> list[KnowledgeRecord]:
        sources = self._history_sources(include_seed=include_seed)
        source_revision = self._history_source_revision(sources)
        cache_key = f"{'admin' if principal.is_admin else principal.employee_id}:{'seed' if include_seed else 'active'}"
        cached = self._history_cache.get(cache_key)
        if cached and cached[0] == source_revision:
            records = list(cached[1])
            if not include_seed:
                records = [item for item in records if item.source != "history_seed"]
            return [
                item
                for item in records
                if principal.is_admin or not item.owner or item.owner == principal.employee_id
            ]
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
                source_status = str(
                    row.get("status") or row.get("decision") or "recorded"
                )
                status = normalized_action_outcome_status(
                    source_status,
                    row.get("result"),
                )
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
                        metadata={
                            **row,
                            "source_status": source_status,
                        },
                    )
                )
        self._history_cache[cache_key] = (source_revision, list(records))
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
            if state in ACTION_OPEN_STATES or (requires_confirmation and state not in ACTION_TERMINAL_STATES):
                current.append(record)
        current.sort(key=lambda item: item.timestamp, reverse=True)
        return current[:limit]

    def ontology_aliases(self, query: str, principal: Principal) -> list[str]:
        """Expand registered names for discovery, never topic tags as identity.

        Related/broader terms may follow a matched name, but cannot themselves
        activate another dictionary entry. This remains candidate expansion.
        """
        query_tokens = normalize_tokens(query)
        aliases: list[str] = []
        for record in self.authoritative_records(principal):
            if record.kind != "dictionary":
                continue
            names = [record.title, str(record.metadata.get('term') or '')]
            raw = record.metadata.get('aliases') or []
            names.extend(str(v) for v in (raw if isinstance(raw,list) else [raw]))
            if not any(tokens and tokens <= query_tokens for value in names
                       if (tokens := normalize_tokens(value))):
                continue
            values = list(names)
            for key in ("related", "related_terms", "broader", "narrower"):
                raw = record.metadata.get(key)
                if isinstance(raw, list):
                    values.extend(str(item) for item in raw)
                elif raw:
                    values.append(str(raw))
            aliases.extend(values)
        deduped: list[str] = []
        for value in aliases:
            clean = value.strip()
            if clean and clean.lower() not in {item.lower() for item in deduped}:
                deduped.append(clean)
        return deduped[:20]

    def stats(self, principal: Principal, *, include_history: bool = True) -> dict[str, Any]:
        records = self.authoritative_records(principal)
        counts: dict[str, int] = {}
        for record in records:
            counts[record.kind] = counts.get(record.kind, 0) + 1
        result: dict[str, Any] = {
            "content_root": str(self.settings.content_root),
            "content_ready": self.content_ready(),
            "authoritative_records": len(records),
            "by_kind": counts,
            "history_counts_included": include_history,
        }
        if include_history:
            all_history = self.history_records(principal, include_seed=True)
            result["active_history_records"] = sum(
                1 for item in all_history if item.source != "history_seed"
            )
            result["seed_history_records"] = sum(
                1 for item in all_history if item.source == "history_seed"
            )
        return result
