from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException

from .config import AgentV2Settings
from ..governed_runtime.canonical_projection_reader import CanonicalProjectionReader
from .models import (
    GraphQueryPlan,
    KnowledgeEdge,
    KnowledgeHealthScanRequest,
    KnowledgePatchProposal,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceDefinition,
    OntologyProposalCreateRequest,
    OntologyProposalPublishRequest,
    OntologyProposalReviewRequest,
    OntologyQueryRequest,
    OntologyQueryRecipeDefinition,
    Principal,
    UsageRecord,
    is_access_control_role,
)
from .openkb_compat import OpenKBCompatibilityGateway
from .ontology_registry import OntologySchemaRegistry
from .repository import KnowledgeRecord, KnowledgeRepository
from .search import HybridSearchService, record_content_checksum
from .store import AgentV2Store, now_iso


EXTRACTOR_VERSION = "boi-knowledge-compiler/13"
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)\)")


def _relation_display(relation: str) -> tuple[str, str, int]:
    return "other", relation.replace("_", " "), 45


def _decorate_edge(
    item: dict[str, Any],
    *,
    ontology_registry: OntologySchemaRegistry | None = None,
) -> dict[str, Any]:
    relation = str(item.get("relation") or "related")
    relation_definition = (
        ontology_registry.relation(relation) if ontology_registry is not None else None
    )
    family, user_label, priority = (
        (
            relation_definition.family,
            relation_definition.label,
            relation_definition.display_priority,
        )
        if relation_definition is not None
        else _relation_display(relation)
    )
    decorated = dict(item)
    decorated.update(
        {
            "relation_family": family,
            "user_label": user_label,
            "display_priority": priority,
        }
    )
    payload = dict(item.get("payload") or {}) if isinstance(item.get("payload"), dict) else {}
    payload.update(
        {
            "relation_family": family,
            "user_label": user_label,
            "display_priority": priority,
        }
    )
    decorated["payload"] = payload
    return decorated


def _decorate_graph_result(
    result: dict[str, Any],
    *,
    recipe: OntologyQueryRecipeDefinition,
    ontology_registry: OntologySchemaRegistry | None = None,
) -> dict[str, Any]:
    nodes = list(result.get("nodes") or [])
    edges = [
        _decorate_edge(item, ontology_registry=ontology_registry)
        for item in result.get("edges") or []
    ]
    families = sorted({str(item.get("relation_family") or "other") for item in edges})
    presentation = str(result.get("presentation") or "")
    meaningful_checks = {
        "nodes": bool(nodes),
        "edges": bool(edges),
        "timeline_items": bool(result.get("timeline")),
        "two_groups_and_edges": bool(edges) and len(result.get("groups") or {}) >= 2,
    }
    meaningful = meaningful_checks[recipe.meaningful_when]
    empty_reason = recipe.empty_reason if not meaningful else ""
    result.update(
        {
            "nodes": nodes,
            "edges": edges,
            "layout_hint": recipe.layout_hint,
            "primary_path": list(result.get("path_refs") or []),
            "clusters": [
                {
                    "cluster_id": family,
                    "label": next(
                        (str(item.get("user_label") or family) for item in edges if item.get("relation_family") == family),
                        family,
                    ),
                }
                for family in families
            ],
            "legend": [
                {
                    "relation_family": family,
                    "labels": sorted(
                        {str(item.get("user_label") or "관계") for item in edges if item.get("relation_family") == family}
                    ),
                }
                for family in families
            ],
            "empty_reason": empty_reason,
            "meaningful": meaningful,
            "ok": bool(result.get("ok", True)) and meaningful,
            "presentation": presentation,
        }
    )
    return result


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256(":".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dedupe_semantic_edges(
    rows: list[dict[str, Any]],
    *,
    ontology_registry: OntologySchemaRegistry,
) -> list[dict[str, Any]]:
    aliases = {
        "declared": "canonical_declared",
        "extracted": "deterministic_extracted",
    }
    priority = {
        item: len(ontology_registry.document.provenance_priority) - index
        for index, item in enumerate(ontology_registry.document.provenance_priority)
    }

    def provenance(payload: dict[str, Any]) -> str:
        raw = str(payload.get("evidence_provenance") or payload.get("provenance") or "")
        return aliases.get(raw, raw)

    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in rows:
        source_id = str(item.get("source_id") or "")
        target_id = str(item.get("target_id") or "")
        relation = str(item.get("relation") or "")
        relation_definition = ontology_registry.relation(relation)
        if relation_definition is not None and relation_definition.symmetric and source_id > target_id:
            source_id, target_id = target_id, source_id
        key = (source_id, relation, target_id)
        if not all(key):
            continue
        current = selected.get(key)
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        current_payload = current.get("payload") if current and isinstance(current.get("payload"), dict) else {}
        score = (
            priority.get(provenance(payload), 0),
            -int(item.get("depth") or 1),
        )
        current_score = (
            priority.get(provenance(current_payload), 0),
            -int(current.get("depth") or 1),
        ) if current else (-1, -99)
        if current is None or score > current_score:
            selected[key] = item
    return list(selected.values())


class LivingKnowledgeService:
    """Deterministic source, graph, and health layer over the BoI source of truth."""

    def __init__(
        self,
        settings: AgentV2Settings,
        repository: KnowledgeRepository,
        store: AgentV2Store,
        search: HybridSearchService,
        directory_provider: Callable[[], list[Principal]] | None = None,
    ):
        self.settings = settings
        self.repository = repository
        self.store = store
        self.search = search
        self.directory_provider = directory_provider
        self.ontology_registry = OntologySchemaRegistry(
            settings.ontology_registry_root / "schema-registry-v1.yaml"
        )
        active_schema = self.store.get("ontology_schema_active", "current") or {}
        active_version = self.store.get(
            "ontology_schema_versions",
            str(active_schema.get("version_id") or ""),
        )
        if active_version and isinstance(active_version.get("schema"), dict):
            self.ontology_registry.activate_payload(active_version["schema"])
        self._adapter_lock = threading.Lock()
        self._adapter_worker_event = threading.Event()
        self._adapter_worker_stop = threading.Event()
        self._adapter_worker_thread: threading.Thread | None = None
        self._ensure_defaults()
        if self._resume_adapter_jobs():
            self._ensure_adapter_worker()

    @staticmethod
    def _people_analytics_enabled(principal: Principal) -> bool:
        return principal.is_admin or "ontology.people.analytics" in principal.roles

    def directory_principals(self, current: Principal) -> list[Principal]:
        rows: list[Principal] = []
        if self.directory_provider is not None:
            try:
                rows = list(self.directory_provider() or [])
            except Exception:
                rows = []
        principals = {item.employee_id: item for item in rows if item.employee_id}
        # Authentication scopes and transient roles belong to the request, not to
        # the directory read model. Only use the caller as a directory fallback
        # when that person is not present in the authoritative provider.
        if current.employee_id:
            principals.setdefault(
                current.employee_id,
                current.model_copy(
                    update={
                        "roles": [
                            role
                            for role in current.roles
                            if not is_access_control_role(role)
                        ]
                    }
                ),
            )
        return list(principals.values())

    def directory_signature(self, current: Principal) -> str:
        payload = [
            {
                "employee_id": item.employee_id,
                "display_name": item.display_name,
                "teams": sorted(item.teams),
                "roles": sorted(item.roles),
            }
            for item in sorted(self.directory_principals(current), key=lambda row: row.employee_id)
        ]
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def _runtime_relation_files(self) -> list[Path]:
        root = self.settings.runtime_root / "task-execution"
        files: list[Path] = []
        for name in ("assignments", "assignment-history", "work-records"):
            folder = root / name
            if folder.exists():
                files.extend(path for path in folder.rglob("*") if path.is_file())
        action_root = self.settings.runtime_root / "actions"
        if action_root.exists():
            files.extend(path for path in action_root.rglob("*.jsonl") if path.is_file())
        return sorted(files)

    def runtime_relation_signature(self) -> str:
        digest = hashlib.sha256()
        for path in self._runtime_relation_files():
            try:
                stat = path.stat()
                relative = path.relative_to(self.settings.runtime_root)
            except OSError:
                continue
            digest.update(f"{relative}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8"))
        for record in self.store.list("completion_records", limit=10_000):
            digest.update(
                json.dumps(record, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            )
        for collection in (
            "usage_records",
            "event_detector_decisions",
            "event_occurrences",
            "action_runs",
            "external_work_results",
            "workflow_runs",
            "task_runs",
            "outcomes",
            "evidence_ledger",
            "next_events",
            "context_playbook_items",
            "harness_failure_patterns",
            "harness_candidates",
            "harness_shadow_runs",
            "harness_eval_runs",
            "harness_versions",
        ):
            for record in self.store.list(collection, limit=10_000):
                digest.update(
                    f"{collection}:".encode("utf-8")
                    + json.dumps(record, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                )
        return digest.hexdigest()

    def _ensure_defaults(self) -> None:
        repo_root = self.settings.content_root.parents[1] if len(self.settings.content_root.parents) > 1 else self.settings.content_root
        defaults = [
            KnowledgeSourceDefinition(
                source_id="source:okf",
                name="BoI Wiki 정본",
                source_kind="okf_markdown",
                location=str(self.settings.content_root),
                visibility="public",
                adapter="builtin.okf",
                sync_policy="on_change",
                status="ready" if self.settings.content_root.exists() else "unavailable",
            ),
            KnowledgeSourceDefinition(
                source_id="source:git",
                name="BoI Wiki 변경 이력",
                source_kind="git",
                location=str(repo_root),
                visibility="public",
                adapter="builtin.git",
                sync_policy="on_change",
                status="ready" if (repo_root / ".git").exists() else "unavailable",
            ),
            KnowledgeSourceDefinition(
                source_id="source:data-lake",
                name="자료 보관함",
                source_kind="data_lake",
                location=str(self.settings.runtime_root / "data-lake-artifacts" / "metadata"),
                visibility="private",
                adapter="builtin.data_lake",
                sync_policy="on_change",
                status="ready" if self.settings.minio_endpoint else "pending",
            ),
        ]
        for definition in defaults:
            if self.store.get("knowledge_sources", definition.source_id) is None:
                self.store.put("knowledge_sources", definition.source_id, definition.model_dump(mode="json"))

    @staticmethod
    def _visible(principal: Principal, source: dict[str, Any]) -> bool:
        if principal.is_admin or source.get("visibility") == "public":
            return True
        if source.get("visibility") == "private":
            owner = str(source.get("owner") or "")
            return not owner or owner == principal.employee_id
        return str(source.get("team_id") or "") in principal.teams

    def list_sources(self, principal: Principal) -> dict[str, Any]:
        self._ensure_defaults()
        items = [
            item
            for item in self.store.list("knowledge_sources", limit=500)
            if self._visible(principal, item)
        ]
        return {"count": len(items), "items": items}

    def create_source(self, principal: Principal, request: KnowledgeSourceCreateRequest) -> dict[str, Any]:
        if request.visibility == "public" and not principal.is_admin:
            raise HTTPException(status_code=403, detail="공용 지식 Source는 관리자만 등록할 수 있습니다.")
        if request.visibility == "team" and request.team_id not in principal.teams and not principal.is_admin:
            raise HTTPException(status_code=403, detail="현재 팀의 Source만 등록할 수 있습니다.")
        if request.source_kind in {"graphify", "openkb", "codegraph", "external_cli"} and not principal.is_admin:
            raise HTTPException(status_code=403, detail="외부 Source adapter는 관리자만 등록할 수 있습니다.")
        source_id = _stable_id("source", principal.employee_id, request.name, request.location)
        adapter = {
            "data_lake": "builtin.data_lake",
            "graphify": "optional.graphify",
            "openkb": "optional.openkb",
            "codegraph": "optional.codegraph",
            "external_cli": "optional.cli",
        }[request.source_kind]
        definition = KnowledgeSourceDefinition(
            source_id=source_id,
            name=request.name,
            source_kind=request.source_kind,
            location=request.location,
            visibility=request.visibility,
            owner=principal.employee_id if request.visibility == "private" else "",
            team_id=request.team_id,
            adapter=adapter,
            sync_policy=request.sync_policy,
            status="pending",
            adapter_config={
                key: value
                for key, value in request.adapter_config.items()
                if key not in {"token", "secret", "password", "api_key"}
            },
        )
        return self.store.put("knowledge_sources", source_id, definition.model_dump(mode="json"))

    def _require_source(self, principal: Principal, source_id: str) -> dict[str, Any]:
        source = self.store.get("knowledge_sources", source_id)
        if not source:
            raise HTTPException(status_code=404, detail="지식 Source를 찾을 수 없습니다.")
        if not self._visible(principal, source):
            raise HTTPException(status_code=403, detail="이 지식 Source를 볼 수 없습니다.")
        return source

    def _records_for_source(self, principal: Principal, source: dict[str, Any]) -> list[KnowledgeRecord]:
        records = self.repository.authoritative_records(principal, include_drafts=False)
        kind = str(source.get("source_kind") or "")
        if kind == "okf_markdown":
            return [item for item in records if item.source in {"knowledge", "catalog"}]
        if kind == "data_lake":
            return [item for item in records if item.source == "data_lake"]
        if kind == "git":
            return []
        return []

    @staticmethod
    def _git_revision(location: str) -> str:
        root = Path(location)
        if not (root / ".git").exists():
            return ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return result.stdout.strip()

    @staticmethod
    def _optional_adapter_state(source: dict[str, Any]) -> dict[str, Any]:
        kind = str(source.get("source_kind") or "")
        executable = {
            "graphify": "graphify",
            "codegraph": "codegraph",
            "external_cli": str((source.get("adapter_config") or {}).get("executable") or ""),
        }.get(kind, "")
        found = shutil.which(executable) if executable else None
        enabled = os.getenv("BOI_KNOWLEDGE_EXTERNAL_ADAPTERS_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
        return {
            "ready": bool(found and enabled),
            "installed": bool(found),
            "enabled": enabled,
            "message": (
                "선택형 adapter가 준비되었습니다. 비교 검증 후 source별로 활성화하세요."
                if found and enabled
                else "선택형 adapter는 기본 운영 경로에서 비활성화되어 있습니다."
            ),
        }

    def _adapter_input(self, source: dict[str, Any], filename: str) -> Path:
        location = Path(str(source.get("location") or "")).expanduser().resolve()
        input_path = location / filename if location.is_dir() else location
        allowed_roots = [
            (self.settings.runtime_root / "knowledge-adapters").resolve(),
            self.settings.runtime_root.resolve(),
        ]
        if not any(input_path == root or root in input_path.parents for root in allowed_roots):
            raise ValueError("adapter_input_outside_staging_root")
        if not input_path.is_file():
            raise ValueError("adapter_input_missing")
        return input_path

    def _adapter_workspace(self, source: dict[str, Any], job_id: str) -> Path:
        root = (self.settings.runtime_root / "knowledge-adapters" / str(source["source_id"]) / job_id).resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _adapter_source_path(self, source: dict[str, Any]) -> Path:
        config = source.get("adapter_config") if isinstance(source.get("adapter_config"), dict) else {}
        raw = str(config.get("input_path") or source.get("location") or "").strip()
        path = Path(raw).expanduser().resolve()
        repo_root = self.settings.content_root.parents[1] if len(self.settings.content_root.parents) > 1 else self.settings.content_root
        allowed = [repo_root.resolve(), self.settings.runtime_root.resolve()]
        if not any(path == root or root in path.parents for root in allowed):
            raise ValueError("adapter_source_outside_allowed_roots")
        if not path.exists():
            raise ValueError("adapter_source_missing")
        return path

    def _checkpoint_adapter_job(self, job_id: str, stage: str, progress: int, **extra: Any) -> dict[str, Any]:
        job = self.store.get("knowledge_source_jobs", job_id) or {}
        checkpoint = {"stage": stage, "progress": progress, "updated_at": now_iso(), **extra}
        job.update({"stage": stage, "progress": progress, "checkpoint": checkpoint, "updated_at": now_iso()})
        if "compatibility_gateway" in extra:
            job["compatibility_gateway"] = extra["compatibility_gateway"]
        return self.store.put("knowledge_source_jobs", job_id, job)

    def _run_adapter_command(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_seconds: float,
        input_text: str | None = None,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["BOI_ADAPTER_NO_MODEL_MANAGEMENT"] = "1"
        if self.settings.model_base_url:
            env.setdefault("OPENAI_API_BASE", self.settings.model_base_url)
            env.setdefault("OPENAI_BASE_URL", self.settings.model_base_url)
        if self.settings.model_api_key:
            env.setdefault("OPENAI_API_KEY", self.settings.model_api_key)
            env.setdefault("LLM_API_KEY", self.settings.model_api_key)
        env.update(extra_env or {})
        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            input=input_text,
            start_new_session=True,
            timeout=timeout_seconds,
        )

    def _prepare_graphify_export(self, source: dict[str, Any], job_id: str, timeout_seconds: float) -> Path:
        location = Path(str(source.get("location") or "")).expanduser()
        if location.is_dir() or location.name == "graph.json":
            try:
                return self._adapter_input(source, "graph.json")
            except ValueError:
                pass
        state = self._optional_adapter_state(source)
        if not state["ready"]:
            raise ValueError("graphify_adapter_not_ready")
        executable = shutil.which("graphify")
        if not executable:
            raise ValueError("graphify_executable_missing")
        workspace = self._adapter_workspace(source, job_id)
        input_path = self._adapter_source_path(source)
        self._checkpoint_adapter_job(job_id, "extract", 20, executable=executable)
        self._run_adapter_command(
            [
                executable,
                "extract",
                str(input_path),
                "--code-only",
                "--no-cluster",
                "--out",
                str(workspace),
            ],
            cwd=workspace,
            timeout_seconds=timeout_seconds,
        )
        output = workspace / "graphify-out" / "graph.json"
        if not output.is_file() and input_path.is_dir():
            output = input_path / "graphify-out" / "graph.json"
        if not output.is_file():
            raise ValueError("graphify_export_missing")
        return output

    def _prepare_openkb_export(self, source: dict[str, Any], job_id: str, timeout_seconds: float) -> Path:
        location = Path(str(source.get("location") or "")).expanduser()
        if location.is_dir() or location.name == "manifest.json":
            try:
                return self._adapter_input(source, "manifest.json")
            except ValueError:
                pass
        enabled = os.getenv("BOI_KNOWLEDGE_EXTERNAL_ADAPTERS_ENABLED", "0").lower() in {"1", "true", "yes", "on"}
        executable = shutil.which("openkb")
        if not enabled or not executable:
            raise ValueError("openkb_adapter_not_ready")
        workspace = self._adapter_workspace(source, job_id)
        input_path = self._adapter_source_path(source)
        config = source.get("adapter_config") if isinstance(source.get("adapter_config"), dict) else {}
        model_name = str(config.get("model") or self.settings.model_name or "").strip()
        if model_name and not model_name.startswith(("openai/", "anthropic/", "gemini/", "ollama/")):
            model_name = f"openai/{model_name}"
        language = str(config.get("language") or "ko").strip() or "ko"
        if not model_name:
            raise ValueError("openkb_model_missing")
        self._checkpoint_adapter_job(job_id, "extract", 20, executable=executable)
        self._run_adapter_command(
            [executable, "init", "--model", model_name, "--language", language],
            cwd=workspace,
            timeout_seconds=min(timeout_seconds, 60.0),
            input_text="\n",
        )
        with OpenKBCompatibilityGateway(self.settings.model_base_url, self.settings.model_api_key) as gateway:
            self._run_adapter_command(
                [executable, "add", str(input_path)],
                cwd=workspace,
                timeout_seconds=timeout_seconds,
                extra_env={
                    "OPENAI_API_BASE": gateway.base_url,
                    "OPENAI_BASE_URL": gateway.base_url,
                    "BOI_OPENKB_COMPAT_GATEWAY": "1",
                },
            )
            self._checkpoint_adapter_job(job_id, "extract", 35, compatibility_gateway=gateway.metrics)
        pages: list[dict[str, Any]] = []
        wiki_root = workspace / "wiki"
        for path in sorted(wiki_root.rglob("*.md")) if wiki_root.exists() else []:
            if path.name.lower() in {"index.md", "log.md", "agents.md"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            summary = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.DOTALL).strip()[:4000]
            if summary:
                pages.append({"id": str(path.relative_to(wiki_root)), "title": title_match.group(1).strip() if title_match else path.stem, "summary": summary, "deterministic": False})
        manifest = workspace / "manifest.json"
        manifest.write_text(json.dumps({"pages": pages}, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest

    def _assert_adapter_job_active(self, job_id: str, started: float, timeout_seconds: float) -> None:
        job = self.store.get("knowledge_source_jobs", job_id) or {}
        if job.get("cancel_requested"):
            raise InterruptedError("adapter_job_cancelled")
        if time.monotonic() - started > timeout_seconds:
            raise TimeoutError("adapter_job_timeout")

    def _import_graphify(
        self,
        principal: Principal,
        source: dict[str, Any],
        *,
        job_id: str = "",
        started: float = 0.0,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        input_path = self._prepare_graphify_export(source, job_id, timeout_seconds) if job_id else self._adapter_input(source, "graph.json")
        if job_id:
            self._checkpoint_adapter_job(job_id, "normalize", 45, raw_artifact_url=str(input_path))
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        raw_nodes = raw.get("nodes") if isinstance(raw, dict) else []
        raw_edges = (
            raw.get("edges") if "edges" in raw else raw.get("links")
        ) if isinstance(raw, dict) else []
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise ValueError("invalid_graphify_export")
        source_id = str(source["source_id"])
        visibility = str(source.get("visibility") or "private")
        owner = str(source.get("owner") or principal.employee_id)
        revision = hashlib.sha256(input_path.read_bytes()).hexdigest()
        node_ids: dict[str, str] = {}
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        for index, item in enumerate(raw_nodes[:50_000]):
            if job_id and index % 500 == 0:
                self._assert_adapter_job_active(job_id, started, timeout_seconds)
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id") or item.get("node_id") or item.get("key") or index)
            node_id = _stable_id("adapter-node", source_id, raw_id)
            node_ids[raw_id] = node_id
            nodes.append(
                {
                    "node_id": node_id,
                    "node_type": str(item.get("type") or item.get("kind") or "code_entity"),
                    "payload": {
                        "title": str(item.get("name") or item.get("title") or raw_id),
                        "summary": str(item.get("summary") or ""),
                        "source_location": str(item.get("path") or item.get("location") or ""),
                        "community": item.get("community"),
                        "centrality": item.get("centrality"),
                        "visibility": visibility,
                        "owner": owner,
                        "allowed_employee_ids": [owner] if visibility == "private" else [],
                        "source_id": source_id,
                        "source_revision": revision,
                    },
                }
            )
        for index, item in enumerate(raw_edges[:100_000]):
            if job_id and index % 500 == 0:
                self._assert_adapter_job_active(job_id, started, timeout_seconds)
            if not isinstance(item, dict):
                continue
            raw_source = str(item.get("source") or item.get("source_id") or "")
            raw_target = str(item.get("target") or item.get("target_id") or "")
            source_node = node_ids.get(raw_source)
            target_node = node_ids.get(raw_target)
            if not source_node or not target_node:
                continue
            confidence_tag = item.get("confidence") if isinstance(item.get("confidence"), str) else ""
            raw_provenance = str(item.get("provenance") or confidence_tag or "extracted").lower()
            provenance = raw_provenance if raw_provenance in {"extracted", "inferred", "ambiguous"} else "extracted"
            raw_confidence = item.get("confidence_score")
            if not isinstance(raw_confidence, (int, float)):
                raw_confidence = item.get("confidence") if isinstance(item.get("confidence"), (int, float)) else None
            relation = str(item.get("relation") or item.get("type") or "depends_on")
            edge_id = _stable_id("adapter-edge", source_id, raw_source, relation, raw_target, str(index))
            edges.append(
                {
                    "edge_id": edge_id,
                    "source_id": source_node,
                    "target_id": target_node,
                    "relation": relation,
                    "payload": {
                        "edge_id": edge_id,
                        "source_id": source_node,
                        "target_id": target_node,
                        "relation": relation,
                        "provenance": provenance,
                        "confidence": float(raw_confidence if raw_confidence is not None else (1.0 if provenance == "extracted" else 0.6)),
                        "source_refs": [source_id],
                        "extractor_version": "graphify-adapter/1",
                        "source_revision": revision,
                        "metadata": {"raw_artifact": str(input_path)},
                    },
                }
            )
        previous = self.store.get("knowledge_source_manifests", source_id) or {}
        self.store.remove_ontology_entries(
            sorted(set(previous.get("node_ids") or []) - {item["node_id"] for item in nodes}),
            sorted(set(previous.get("edge_ids") or []) - {item["edge_id"] for item in edges}),
        )
        self.store.upsert_ontology(nodes, edges)
        if job_id:
            self._checkpoint_adapter_job(job_id, "validate", 75, node_count=len(nodes), edge_count=len(edges))
        manifest = {
            "source_id": source_id,
            "adapter": "graphify",
            "source_revision": revision,
            "node_ids": [item["node_id"] for item in nodes],
            "edge_ids": [item["edge_id"] for item in edges],
            "raw_artifact_url": str(input_path),
            "validation_report": {
                "valid": bool(nodes),
                "node_count": len(nodes),
                "edge_count": len(edges),
                "canonical_changed": False,
            },
            "imported_at": now_iso(),
        }
        self.store.put("knowledge_source_manifests", source_id, manifest)
        return manifest

    def _import_openkb(
        self,
        principal: Principal,
        source: dict[str, Any],
        *,
        job_id: str = "",
        started: float = 0.0,
        timeout_seconds: float = 300.0,
    ) -> dict[str, Any]:
        input_path = self._prepare_openkb_export(source, job_id, timeout_seconds) if job_id else self._adapter_input(source, "manifest.json")
        if job_id:
            self._checkpoint_adapter_job(job_id, "normalize", 45, raw_artifact_url=str(input_path))
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        pages = raw.get("pages") if isinstance(raw, dict) else []
        if not isinstance(pages, list):
            raise ValueError("invalid_openkb_manifest")
        source_id = str(source["source_id"])
        revision = hashlib.sha256(input_path.read_bytes()).hexdigest()
        candidate_ids: list[str] = []
        for index, item in enumerate(pages[:10_000]):
            if job_id and index % 250 == 0:
                self._assert_adapter_job_active(job_id, started, timeout_seconds)
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("name") or f"자료 후보 {index + 1}").strip()
            summary = str(item.get("summary") or item.get("content_summary") or "").strip()
            if not title or not summary:
                continue
            candidate_id = _stable_id("candidate", source_id, str(item.get("id") or title))
            candidate = {
                "candidate_id": candidate_id,
                "employee_id": principal.employee_id,
                "source_id": source_id,
                "source_revision": revision,
                "title": title,
                "summary": summary,
                "reusable_claim": str(item.get("claim") or summary),
                "source_refs": [source_id],
                "target_asset_ref": str(item.get("target_ref") or ""),
                "visibility": "private",
                "status": "proposed",
                "review_state": "review_required",
                "provenance": "extracted" if item.get("deterministic") else "inferred",
                "raw_artifact_url": str(input_path),
                "created_at": now_iso(),
            }
            self.store.put("knowledge_candidates", candidate_id, candidate)
            candidate_ids.append(candidate_id)
        manifest = {
            "source_id": source_id,
            "adapter": "openkb",
            "source_revision": revision,
            "candidate_ids": candidate_ids,
            "raw_artifact_url": str(input_path),
            "validation_report": {
                "valid": bool(candidate_ids),
                "candidate_count": len(candidate_ids),
                "canonical_changed": False,
                "review_required": True,
            },
            "imported_at": now_iso(),
        }
        self.store.put("knowledge_source_manifests", source_id, manifest)
        if job_id:
            self._checkpoint_adapter_job(job_id, "validate", 75, candidate_count=len(candidate_ids))
        return manifest

    def _run_adapter_job(self, principal: Principal, source: dict[str, Any], job_id: str) -> None:
        source_id = str(source["source_id"])
        job = self.store.get("knowledge_source_jobs", job_id) or {}
        if job.get("cancel_requested"):
            job.update({"status": "cancelled", "completed_at": now_iso()})
            self.store.put("knowledge_source_jobs", job_id, job)
            return
        started = time.monotonic()
        timeout_seconds = max(1.0, min(float((source.get("adapter_config") or {}).get("timeout_seconds") or 300), 3600.0))
        job.update({"status": "running", "stage": "inventory", "progress": 5, "started_at": now_iso(), "timeout_seconds": timeout_seconds})
        self.store.put("knowledge_source_jobs", job_id, job)
        try:
            if str(source.get("source_kind") or "") == "graphify":
                manifest = self._import_graphify(
                    principal, source, job_id=job_id, started=started, timeout_seconds=timeout_seconds
                )
            elif str(source.get("source_kind") or "") == "openkb":
                manifest = self._import_openkb(
                    principal, source, job_id=job_id, started=started, timeout_seconds=timeout_seconds
                )
            else:
                raise ValueError("adapter_import_not_supported")
            validation = manifest.get("validation_report") if isinstance(manifest, dict) else {}
            if not isinstance(validation, dict) or validation.get("valid") is not True:
                raise ValueError("adapter_validation_failed")
            self._assert_adapter_job_active(job_id, started, timeout_seconds)
            job.update(
                {
                    "status": "completed",
                    "stage": "import",
                    "progress": 100,
                    "completed_at": now_iso(),
                    "manifest": manifest,
                    "error": "",
                    "retryable": False,
                }
            )
            source.update({"status": "ready", "checksum": manifest["source_revision"], "last_sync_at": now_iso(), "last_error": ""})
        except InterruptedError as exc:
            job.update({"status": "cancelled", "completed_at": now_iso(), "error": str(exc)})
            source.update({"status": "pending", "last_error": "", "last_sync_at": now_iso()})
        except (OSError, ValueError, TimeoutError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
            job.update({"status": "failed", "stage": "failed", "completed_at": now_iso(), "error": str(exc), "retryable": True})
            source.update({"status": "failed", "last_error": str(exc), "last_sync_at": now_iso()})
        except Exception as exc:
            job.update(
                {
                    "status": "failed",
                    "stage": "failed",
                    "completed_at": now_iso(),
                    "error": f"{type(exc).__name__}: {exc}",
                    "retryable": True,
                }
            )
            source.update({"status": "failed", "last_error": job["error"], "last_sync_at": now_iso()})
        latest_job = self.store.get("knowledge_source_jobs", job_id) or {}
        latest_job.update(job)
        job = latest_job
        source["revision"] = int(source.get("revision") or 1) + 1
        self.store.put("knowledge_sources", source_id, source)
        self.store.put("knowledge_source_jobs", job_id, job)

    def _ensure_adapter_worker(self) -> None:
        with self._adapter_lock:
            if self._adapter_worker_thread and self._adapter_worker_thread.is_alive():
                self._adapter_worker_event.set()
                return
            self._adapter_worker_thread = threading.Thread(
                target=self._adapter_worker_loop,
                name="boi-knowledge-source-worker",
                daemon=True,
            )
            self._adapter_worker_thread.start()

    def _adapter_worker_loop(self) -> None:
        while not self._adapter_worker_stop.is_set():
            queued = [
                item for item in self.store.list("knowledge_source_jobs", limit=500)
                if str(item.get("status") or "") == "queued" and not item.get("cancel_requested")
            ]
            queued.sort(key=lambda item: str(item.get("queued_at") or item.get("created_at") or ""))
            if not queued:
                self._adapter_worker_event.wait(0.5)
                self._adapter_worker_event.clear()
                continue
            job = queued[0]
            source = self.store.get("knowledge_sources", str(job.get("source_id") or "")) or {}
            if str(source.get("source_kind") or "") not in {"graphify", "openkb"}:
                job.update({"status": "failed", "stage": "failed", "error": "adapter_import_not_supported", "completed_at": now_iso()})
                self.store.put("knowledge_source_jobs", str(job.get("job_id") or ""), job)
                continue
            principal = Principal(
                employee_id=str(job.get("employee_id") or source.get("owner") or "system"),
                display_name="Knowledge Source Worker",
                roles=["boi.admin"],
                auth_source="service",
            )
            self._run_adapter_job(principal, source, str(job["job_id"]))

    def _queue_adapter_job(
        self,
        principal: Principal,
        source: dict[str, Any],
        *,
        existing_job_id: str = "",
    ) -> dict[str, Any]:
        source_id = str(source["source_id"])
        job_id = existing_job_id or _stable_id("source-job", source_id, now_iso())
        job = self.store.get("knowledge_source_jobs", job_id) or {
            "job_id": job_id,
            "source_id": source_id,
            "employee_id": principal.employee_id,
            "created_at": now_iso(),
        }
        job.update(
            {
                "status": "queued",
                "stage": "queued",
                "progress": 0,
                "cancel_requested": False,
                "queued_at": now_iso(),
                "attempt": int(job.get("attempt") or 0) + 1,
                "error": "",
                "retryable": False,
            }
        )
        self.store.put("knowledge_source_jobs", job_id, job)
        self._ensure_adapter_worker()
        self._adapter_worker_event.set()
        return job

    def _resume_adapter_jobs(self) -> bool:
        resumed = False
        for job in self.store.list("knowledge_source_jobs", limit=500):
            if str(job.get("status") or "") not in {"queued", "running"}:
                continue
            source = self.store.get("knowledge_sources", str(job.get("source_id") or "")) or {}
            if str(source.get("source_kind") or "") not in {"graphify", "openkb"}:
                continue
            job.update({"status": "queued", "stage": "queued", "recovered_after_restart": True, "queued_at": now_iso()})
            self.store.put("knowledge_source_jobs", str(job["job_id"]), job)
            resumed = True
        return resumed

    def cancel_source_job(self, principal: Principal, job_id: str) -> dict[str, Any]:
        job = self.source_job(principal, job_id)
        if str(job.get("status") or "") in {"completed", "failed", "cancelled"}:
            return job
        job.update({"cancel_requested": True, "cancel_requested_at": now_iso()})
        if job.get("status") == "queued":
            job.update({"status": "cancelled", "completed_at": now_iso()})
        return self.store.put("knowledge_source_jobs", job_id, job)

    def retry_source_job(self, principal: Principal, job_id: str) -> dict[str, Any]:
        job = self.source_job(principal, job_id)
        if str(job.get("status") or "") not in {"failed", "cancelled"} or not job.get("retryable", True):
            raise HTTPException(status_code=409, detail="다시 실행할 수 있는 실패 작업이 아닙니다.")
        source = self._require_source(principal, str(job.get("source_id") or ""))
        return self._queue_adapter_job(principal, source, existing_job_id=job_id)

    def rollback_source_import(self, principal: Principal, source_id: str, request: Any) -> dict[str, Any]:
        source = self._require_source(principal, source_id)
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="boi.admin is required")
        if not request.user_confirmed:
            raise HTTPException(status_code=400, detail="외부 Source 가져오기 되돌리기를 확인해주세요.")
        manifest = self.store.get("knowledge_source_manifests", source_id)
        if not manifest:
            raise HTTPException(status_code=404, detail="되돌릴 가져오기 기록이 없습니다.")
        node_ids = list(manifest.get("node_ids") or [])
        edge_ids = list(manifest.get("edge_ids") or [])
        candidate_ids = list(manifest.get("candidate_ids") or [])
        self.store.remove_ontology_entries(node_ids, edge_ids)
        for candidate_id in candidate_ids:
            candidate = self.store.get("knowledge_candidates", str(candidate_id)) or {}
            if candidate:
                candidate.update({"status": "archived", "review_state": "rolled_back", "updated_at": now_iso()})
                self.store.put("knowledge_candidates", str(candidate_id), candidate)
        rollback_id = _stable_id("source-rollback", source_id, now_iso())
        result = {"rollback_id": rollback_id, "source_id": source_id, "removed_nodes": len(node_ids), "removed_edges": len(edge_ids), "archived_candidates": len(candidate_ids), "reason": request.reason, "created_at": now_iso()}
        self.store.put("knowledge_source_rollbacks", rollback_id, result)
        self.store.delete("knowledge_source_manifests", source_id)
        source.update({"status": "pending", "checksum": "", "last_error": "", "revision": int(source.get("revision") or 1) + 1})
        self.store.put("knowledge_sources", source_id, source)
        return result

    def source_job(self, principal: Principal, job_id: str) -> dict[str, Any]:
        job = self.store.get("knowledge_source_jobs", job_id)
        if not job:
            raise HTTPException(status_code=404, detail="지식 Source 작업을 찾을 수 없습니다.")
        if not principal.is_admin and str(job.get("employee_id") or "") != principal.employee_id:
            raise HTTPException(status_code=403, detail="이 지식 Source 작업을 볼 수 없습니다.")
        return job

    def _resolve_target(
        self,
        value: str,
        records_by_id: dict[str, KnowledgeRecord],
        records_by_url: dict[str, str],
        aliases: dict[str, str],
    ) -> str:
        clean = str(value or "").strip()
        if not clean:
            return ""
        if clean in records_by_id:
            return clean
        path = clean.split("?", 1)[0].rstrip("/")
        if path in records_by_url:
            return records_by_url[path]
        for prefix in ("action:", "event:", "workflow:", "skill:"):
            if prefix + clean in records_by_id:
                return prefix + clean
        key = re.sub(r"\s+", " ", clean.casefold()).strip()
        return aliases.get(key, "")

    def compile_graph(self, principal: Principal) -> dict[str, Any]:
        compiler_principal = (
            principal
            if principal.is_admin
            else principal.model_copy(update={"roles": list(dict.fromkeys([*principal.roles, "boi.admin"]))})
        )
        candidate_records = self.repository.authoritative_records(compiler_principal, include_drafts=True)
        records = []
        for record in candidate_records:
            state = record.status.casefold()
            marker = f"{record.title} {record.description} {record.metadata.get('tags', [])}".casefold()
            if state in {"deprecated", "candidate", "test", "smoke"} or "smoke" in marker or "fixture" in marker:
                continue
            declared_relationships = record.metadata.get("relationships") or record.metadata.get("relations")
            if state == "draft" and not declared_relationships:
                continue
            records.append(record)
        records_by_id = {item.record_id: item for item in records}
        records_by_url = {item.url.split("?", 1)[0].rstrip("/"): item.record_id for item in records if item.url}
        aliases: dict[str, str] = {}
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        task_titles: dict[str, str] = {}

        for record in records:
            revision = record_content_checksum(record)
            nodes.append(
                {
                    "node_id": record.record_id,
                    "node_type": record.kind,
                    "payload": {
                        "title": record.title,
                        "url": record.url,
                        "visibility": record.visibility,
                        "owner": record.owner,
                        "team_id": record.team_id,
                        "authority": record.authority,
                        "status": record.status,
                        "reviewed": record.status.casefold() in {"published", "reviewed", "active"},
                        "observed_at": record.timestamp,
                        "source_revision": revision,
                    },
                }
            )
            names = [record.record_id, record.title, str(record.metadata.get("term") or "")]
            names.extend(str(item) for item in record.metadata.get("aliases") or [])
            for name in names:
                key = re.sub(r"\s+", " ", str(name).casefold()).strip()
                if key:
                    aliases.setdefault(key, record.record_id)

        def append_edge(
            source_id: str,
            target_id: str,
            relation: str,
            provenance: str,
            source_revision: str,
            *,
            confidence: float = 1.0,
            metadata: dict[str, Any] | None = None,
            source_refs: list[str] | None = None,
        ) -> None:
            evidence_provenance = {
                "declared": "canonical_declared",
                "extracted": "deterministic_extracted",
            }.get(provenance, provenance)
            edge = KnowledgeEdge(
                edge_id=_stable_id("edge", source_id, relation, target_id),
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                provenance=provenance,  # type: ignore[arg-type]
                confidence=confidence,
                # Entity identifiers describe the graph topology; they are not
                # necessarily evidence records that can be opened or cited.
                # Adapters with a canonical/operational source binding must
                # provide it explicitly. Record-derived edges retain the
                # historical fallback because their node ids are source ids.
                source_refs=list(
                    dict.fromkeys(
                        str(item)
                        for item in (source_refs or [source_id, target_id])
                        if str(item).strip()
                    )
                ),
                extractor_version=EXTRACTOR_VERSION,
                source_revision=source_revision,
                metadata={
                    **(metadata or {}),
                    "evidence_provenance": evidence_provenance,
                },
            )
            payload = edge.model_dump(mode="json")
            payload["evidence_provenance"] = evidence_provenance
            edges.append(
                {
                    "edge_id": edge.edge_id,
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation": relation,
                    "payload": payload,
                }
            )

        okf_binding = self.ontology_registry.document.source_bindings.get(
            "okf_markdown",
            {},
        )
        relation_fields = {
            str(field): str(relation)
            for field, relation in (
                okf_binding.get("metadata_relation_fields") or {}
            ).items()
            if str(field) and str(relation)
        }
        relationship_fields = [
            str(item)
            for item in okf_binding.get("explicit_relationship_fields") or []
            if str(item)
        ]
        excluded_explicit_relations = {
            str(item)
            for item in okf_binding.get("excluded_explicit_relations") or []
            if str(item)
        }
        markdown_link_relation = str(
            okf_binding.get("markdown_link_relation") or ""
        )
        for record in records:
            revision = record_content_checksum(record)
            declared_relationships: list[dict[str, Any]] = []
            for field in relationship_fields:
                raw_relationships = record.metadata.get(field) or []
                values = (
                    raw_relationships
                    if isinstance(raw_relationships, list)
                    else [raw_relationships]
                )
                declared_relationships.extend(
                    item for item in values if isinstance(item, dict)
                )
            for item in declared_relationships:
                if not isinstance(item, dict):
                    continue
                relation = str(item.get("relation") or item.get("type") or "").strip()
                value = str(item.get("target") or item.get("ref") or item.get("boi_id") or "").strip()
                relation_definition = self.ontology_registry.relation(relation)
                if (
                    relation_definition is None
                    or relation in excluded_explicit_relations
                    or "canonical_declared" not in relation_definition.allowed_provenance
                ):
                    continue
                target = self._resolve_target(value, records_by_id, records_by_url, aliases)
                if target and target != record.record_id:
                    append_edge(
                        record.record_id,
                        target,
                        relation,
                        "declared",
                        revision,
                        metadata={"field": "relationships", "label": str(item.get("label") or "")},
                    )
            for field, relation in relation_fields.items():
                raw_values = record.metadata.get(field)
                values = raw_values if isinstance(raw_values, list) else [raw_values] if raw_values else []
                for raw in values:
                    value = str(raw.get("ref") or raw.get("boi_id") or "") if isinstance(raw, dict) else str(raw or "")
                    target = self._resolve_target(value, records_by_id, records_by_url, aliases)
                    if target and target != record.record_id:
                        append_edge(record.record_id, target, relation, "declared", revision, metadata={"field": field})
            if markdown_link_relation:
                for href in MARKDOWN_LINK.findall(record.text):
                    target = self._resolve_target(
                        href,
                        records_by_id,
                        records_by_url,
                        aliases,
                    )
                    if target and target != record.record_id:
                        append_edge(
                            record.record_id,
                            target,
                            markdown_link_relation,
                            "extracted",
                            revision,
                            metadata={"href": href},
                        )
            stages = []
            workflow = record.metadata.get("workflow") if isinstance(record.metadata.get("workflow"), dict) else {}
            stages.extend(item for item in workflow.get("stages") or [] if isinstance(item, dict))
            stages.extend(item for item in record.metadata.get("tasks") or [] if isinstance(item, dict))
            for index, stage in enumerate(stages):
                task_key = str(stage.get("task_id") or stage.get("id") or f"task-{index + 1}")
                task_title = str(stage.get("name") or stage.get("title") or task_key)
                task_titles.setdefault(task_key, task_title)
                # The UI, Task runtime, and external Agent contract already
                # identify a definition step as ``<SOP ref>#<task id>``.
                # Keep the Ontology node stable and reversible so canonical
                # Event/Action/Evidence edges and operational UsageRecord
                # edges converge on one Task instead of unrelated hash IDs.
                task_id = f"task:{record.record_id}#{task_key}"
                nodes.append(
                    {
                        "node_id": task_id,
                        "node_type": "task",
                        "payload": {
                            "title": task_title,
                            "parent_ref": record.record_id,
                            "visibility": record.visibility,
                            "owner": record.owner,
                            "team_id": record.team_id,
                            "order": index,
                        },
                    }
                )
                append_edge(record.record_id, task_id, "has_task", "extracted", revision, metadata={"order": index})
                assignment = stage.get("assignment_design") if isinstance(stage.get("assignment_design"), dict) else {}
                for employee_id in assignment.get("assignee_employee_ids") or []:
                    person_id = f"person:{str(employee_id).strip()}"
                    if person_id == "person:":
                        continue
                    nodes.append(
                        {
                            "node_id": person_id,
                            "node_type": "person",
                            "payload": {
                                "title": str(employee_id),
                                "visibility": record.visibility,
                                "owner": record.owner,
                                "team_id": record.team_id,
                                "source_revision": revision,
                            },
                        }
                    )
                    append_edge(
                        task_id,
                        person_id,
                        "designed_assignee",
                        "canonical_declared",
                        revision,
                        metadata={"source_ref": record.record_id},
                    )
                for employee_id in assignment.get("reviewer_employee_ids") or []:
                    person_id = f"person:{str(employee_id).strip()}"
                    if person_id != "person:":
                        nodes.append(
                            {
                                "node_id": person_id,
                                "node_type": "person",
                                "payload": {
                                    "title": str(employee_id),
                                    "visibility": record.visibility,
                                    "owner": record.owner,
                                    "team_id": record.team_id,
                                    "source_revision": revision,
                                },
                            }
                        )
                        append_edge(
                            task_id,
                            person_id,
                            "designed_reviewer",
                            "canonical_declared",
                            revision,
                            metadata={"source_ref": record.record_id},
                        )
                for team_id in assignment.get("related_team_ids") or []:
                    team_node_id = f"team:{str(team_id).strip()}"
                    if team_node_id != "team:":
                        nodes.append(
                            {
                                "node_id": team_node_id,
                                "node_type": "team",
                                "payload": {
                                    "title": str(team_id),
                                    "visibility": record.visibility,
                                    "team_id": str(team_id),
                                    "source_revision": revision,
                                },
                            }
                        )
                        append_edge(
                            task_id,
                            team_node_id,
                            "designed_related_team",
                            "canonical_declared",
                            revision,
                            metadata={"source_ref": record.record_id},
                        )
                for field, relation in {
                    "event_types": "uses_event",
                    "entry_event": "uses_event",
                    "action_refs": "uses_action",
                    "automated_actions": "uses_action",
                    "manual_actions": "uses_action",
                    "skill_refs": "uses_skill",
                    "evidence_refs": "requires_evidence",
                    "required_evidence": "requires_evidence",
                }.items():
                    raw_values = stage.get(field)
                    values = raw_values if isinstance(raw_values, list) else [raw_values] if raw_values else []
                    for raw in values:
                        value = str(raw.get("ref") or "") if isinstance(raw, dict) else str(raw or "")
                        target = self._resolve_target(value, records_by_id, records_by_url, aliases)
                        if not target and relation == "requires_evidence" and value.strip():
                            target = _stable_id(
                                "input-evidence",
                                record.record_id,
                                task_key,
                                value.strip(),
                            )
                            nodes.append(
                                {
                                    "node_id": target,
                                    "node_type": "input_evidence",
                                    "payload": {
                                        "title": value.strip(),
                                        "parent_ref": task_id,
                                        "source_ref": record.record_id,
                                        "visibility": record.visibility,
                                        "owner": record.owner,
                                        "team_id": record.team_id,
                                        "source_revision": revision,
                                    },
                                }
                            )
                        if target:
                            append_edge(
                                task_id,
                                target,
                                relation,
                                "extracted",
                                revision,
                                metadata={
                                    "field": field,
                                    "source_ref": record.record_id,
                                },
                                source_refs=[record.record_id],
                            )

        runtime_records = self.repository.history_records(compiler_principal, include_seed=False)
        runtime_by_identity: dict[str, KnowledgeRecord] = {}
        for record in runtime_records:
            identity = str(record.metadata.get("request_id") or record.metadata.get("task_id") or "").removeprefix("task:")
            if identity:
                runtime_by_identity[identity] = record
            if record.source != "runtime" or "action" not in record.record_id or not record.owner:
                continue
            task_id = _stable_id("runtime-task", record.record_id)
            revision = hashlib.sha256(record.text.encode("utf-8")).hexdigest()
            nodes.extend(
                [
                    {
                        "node_id": task_id,
                        "node_type": "task",
                        "payload": {
                            "title": record.title,
                            "url": record.url,
                            "visibility": "private",
                            "owner": record.owner,
                            "allowed_employee_ids": [record.owner],
                            "status": record.status,
                            "observed_at": record.timestamp,
                            "source_ref": record.record_id,
                            "source_revision": revision,
                        },
                    },
                    {
                        "node_id": f"person:{record.owner}",
                        "node_type": "person",
                        "payload": {
                            "title": record.owner,
                            "visibility": "private",
                            "owner": record.owner,
                            "allowed_employee_ids": [record.owner],
                            "source_revision": revision,
                        },
                    },
                ]
            )
            append_edge(
                task_id,
                f"person:{record.owner}",
                "assigned_to",
                "operational_verified",
                revision,
                metadata={"source_ref": record.record_id, "observed_at": record.timestamp},
            )
            for field, relation in {
                "sop_ref": "uses_sop",
                "workflow_definition_key": "part_of_workflow",
                "action_key": "uses_action",
                "event_type": "uses_event",
            }.items():
                value = str(record.metadata.get(field) or "")
                target = self._resolve_target(value, records_by_id, records_by_url, aliases)
                if target:
                    append_edge(
                        task_id,
                        target,
                        relation,
                        "operational_verified",
                        revision,
                        metadata={"source_ref": record.record_id},
                    )

        assignment_root = self.settings.runtime_root / "task-execution" / "assignments"
        for path in sorted(assignment_root.glob("*.json")) if assignment_root.exists() else []:
            try:
                assignment = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(assignment, dict):
                continue
            task_key = str(assignment.get("task_key") or path.stem)
            task_identity = str(assignment.get("task_identity") or "")
            record = runtime_by_identity.get(task_identity)
            assignees = list(dict.fromkeys(str(item) for item in assignment.get("assignee_employee_ids") or [] if str(item)))
            reviewers = list(dict.fromkeys(str(item) for item in assignment.get("reviewer_employee_ids") or [] if str(item)))
            allowed_employees = list(dict.fromkeys([*assignees, *reviewers]))
            if not allowed_employees:
                continue
            revision = hashlib.sha256(json.dumps(assignment, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            task_id = f"runtime-task:{task_key}"
            title = str((record.title if record else "") or assignment.get("title") or task_identity or "현재 Task")
            nodes.append(
                {
                    "node_id": task_id,
                    "node_type": "task",
                    "payload": {
                        "title": title,
                        "url": record.url if record else "",
                        "visibility": "private",
                        "owner": assignees[0] if assignees else reviewers[0],
                        "allowed_employee_ids": allowed_employees,
                        "status": record.status if record else "assigned",
                        "task_identity": task_identity,
                        "source_revision": revision,
                        "observed_at": str(assignment.get("updated_at") or (record.timestamp if record else "")),
                    },
                }
            )
            for employee_id in allowed_employees:
                person_id = f"person:{employee_id}"
                nodes.append(
                    {
                        "node_id": person_id,
                        "node_type": "person",
                        "payload": {
                            "title": employee_id,
                            "visibility": "private",
                            "owner": employee_id,
                            "allowed_employee_ids": allowed_employees,
                            "source_revision": revision,
                        },
                    }
                )
            for employee_id in assignees:
                append_edge(task_id, f"person:{employee_id}", "assigned_to", "operational_verified", revision, metadata={"source_ref": task_id})
            for employee_id in reviewers:
                append_edge(task_id, f"person:{employee_id}", "reviewed_by", "operational_verified", revision, metadata={"source_ref": task_id})
            for team_id in assignment.get("related_team_ids") or []:
                team_ref = str(team_id).strip()
                if not team_ref:
                    continue
                team_node_id = f"team:{team_ref}"
                nodes.append(
                    {
                        "node_id": team_node_id,
                        "node_type": "team",
                        "payload": {
                            "title": team_ref,
                            "visibility": "private",
                            "owner": assignees[0] if assignees else reviewers[0],
                            "allowed_employee_ids": allowed_employees,
                            "team_id": team_ref,
                            "source_revision": revision,
                        },
                    }
                )
                append_edge(task_id, team_node_id, "related_team", "operational_verified", revision, metadata={"source_ref": task_id})

            records_path = self.settings.runtime_root / "task-execution" / "work-records" / f"{task_key}.jsonl"
            if records_path.exists():
                for line in records_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    try:
                        work_record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    actor = str(work_record.get("actor_employee_id") or "")
                    if not actor:
                        continue
                    append_edge(
                        task_id,
                        f"person:{actor}",
                        "performed_by",
                        "human_verified",
                        str(work_record.get("record_id") or revision),
                        metadata={
                            "source_ref": task_id,
                            "recorded_at": str(work_record.get("recorded_at") or ""),
                            "record_id": str(work_record.get("record_id") or ""),
                        },
                    )

        completion_rows = self.store.list("completion_records", limit=10_000)
        repeated_work: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        recent_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
        for completion in completion_rows:
            task_ref = str(completion.get("task_ref") or "")
            employee_id = str(completion.get("employee_id") or "")
            if not task_ref or not employee_id:
                continue
            task_id = task_ref if task_ref.startswith(("task:", "runtime-task:")) else f"task:{task_ref}"
            revision = str(completion.get("completion_id") or completion.get("created_at") or "")
            clean_task_ref = task_ref.removeprefix("task:").removeprefix("runtime-task:")
            completion_title = task_titles.get(clean_task_ref) or str(
                completion.get("task_title") or completion.get("title") or ""
            ).strip()
            if not completion_title or len(completion_title) > 120:
                completion_title = re.sub(r"[_\-.]+", " ", clean_task_ref).strip()
            nodes.append(
                {
                    "node_id": task_id,
                    "node_type": "task",
                    "payload": {
                        "title": completion_title or "완료한 Task",
                        "visibility": "private",
                        "owner": employee_id,
                        "allowed_employee_ids": [employee_id],
                        "recorded_at": str(completion.get("created_at") or ""),
                        "source_revision": revision,
                    },
                }
            )
            nodes.append(
                {
                    "node_id": f"person:{employee_id}",
                    "node_type": "person",
                    "payload": {
                        "title": employee_id,
                        "visibility": "private",
                        "owner": employee_id,
                        "allowed_employee_ids": [employee_id],
                        "source_revision": revision,
                    },
                }
            )
            append_edge(
                task_id,
                f"person:{employee_id}",
                "completed_by",
                "human_verified",
                revision,
                metadata={"source_ref": str(completion.get("completion_id") or ""), "recorded_at": str(completion.get("created_at") or "")},
            )
            completed_at = _parse_time(str(completion.get("created_at") or ""))
            execution_id = str(completion.get("work_run_id") or completion.get("completion_id") or "")
            if completed_at and completed_at >= recent_cutoff and execution_id:
                repeated_work[(employee_id, task_id)].append(
                    {
                        "completion_id": str(completion.get("completion_id") or ""),
                        "execution_id": execution_id,
                        "completed_at": completed_at,
                    }
                )

        active_profile_ids: set[str] = set()
        for (employee_id, task_id), rows in repeated_work.items():
            distinct_rows = list({item["execution_id"]: item for item in rows}.values())
            if len(distinct_rows) < 3:
                continue
            distinct_rows.sort(key=lambda item: item["completed_at"])
            profile_id = _stable_id("workrole", employee_id, task_id)
            active_profile_ids.add(profile_id)
            source_refs = [item["completion_id"] for item in distinct_rows if item["completion_id"]]
            profile = {
                "profile_id": profile_id,
                "employee_id": employee_id,
                "task_ref": task_id,
                "completion_count": len(distinct_rows),
                "window_days": 180,
                "first_completed_at": distinct_rows[0]["completed_at"].isoformat(),
                "last_completed_at": distinct_rows[-1]["completed_at"].isoformat(),
                "source_refs": source_refs,
                "verification": "human_verified",
                "updated_at": now_iso(),
            }
            self.store.put("work_role_profiles", profile_id, profile)
            append_edge(
                task_id,
                f"person:{employee_id}",
                "repeated_performer",
                "human_verified",
                profile_id,
                metadata={
                    "source_refs": source_refs,
                    "completion_count": len(distinct_rows),
                    "window_days": 180,
                    "last_completed_at": profile["last_completed_at"],
                },
            )
        for profile in self.store.list("work_role_profiles", limit=10_000):
            profile_id = str(profile.get("profile_id") or "")
            if profile_id and profile_id not in active_profile_ids:
                self.store.delete("work_role_profiles", profile_id)

        role_titles = {
            "boi.viewer": "BoI 지식 사용자",
            "boi.editor": "BoI 지식 편집자",
            "boi.workflow_runner": "업무 흐름 수행자",
            "boi.action_invoker": "Action 요청자",
            "boi.reviewer": "지식 검토자",
            "boi.promoter": "공유 지식 검토 요청자",
            "boi.admin": "BoI 운영 관리자",
        }
        for identity in self.directory_principals(principal):
            directory_source_ref = f"directory:person:{identity.employee_id}"
            identity_revision = hashlib.sha256(
                json.dumps(
                    {
                        "employee_id": identity.employee_id,
                        "display_name": identity.display_name,
                        "teams": sorted(identity.teams),
                        "roles": sorted(identity.roles),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()
            person_id = f"person:{identity.employee_id}"
            existing_person = next(
                (item for item in reversed(nodes) if str(item.get("node_id") or "") == person_id),
                {},
            )
            existing_payload = (
                existing_person.get("payload")
                if isinstance(existing_person.get("payload"), dict)
                else {}
            )
            allowed_employees = list(
                dict.fromkeys(
                    [
                        identity.employee_id,
                        *[
                            str(item)
                            for item in existing_payload.get("allowed_employee_ids") or []
                            if str(item)
                        ],
                    ]
                )
            )
            nodes.append(
                {
                    "node_id": person_id,
                    "node_type": "person",
                    "payload": {
                        "title": identity.display_name or identity.employee_id,
                        "employee_id": identity.employee_id,
                        "visibility": "directory",
                        "owner": identity.employee_id,
                        "allowed_employee_ids": allowed_employees,
                        "allowed_team_ids": sorted(identity.teams),
                        "source_revision": identity_revision,
                    },
                }
            )
            for team_id in identity.teams:
                team_node_id = f"team:{team_id}"
                nodes.append(
                    {
                        "node_id": team_node_id,
                        "node_type": "team",
                        "payload": {
                            "title": team_id,
                            "visibility": "public",
                            "team_id": team_id,
                            "source_revision": identity_revision,
                        },
                    }
                )
                append_edge(
                    person_id,
                    team_node_id,
                    "member_of",
                    "canonical_declared",
                    identity_revision,
                    metadata={"source_ref": directory_source_ref},
                    source_refs=[directory_source_ref],
                )
            for role_id in identity.roles:
                access_role = is_access_control_role(role_id)
                role_node_id = (
                    f"access-role:{role_id}" if access_role else f"role:{role_id}"
                )
                nodes.append(
                    {
                        "node_id": role_node_id,
                        "node_type": "access_role" if access_role else "role",
                        "payload": {
                            "title": role_titles.get(role_id, role_id),
                            "visibility": "private" if access_role else "directory",
                            "owner": identity.employee_id if access_role else "",
                            "allowed_employee_ids": [identity.employee_id] if access_role else [],
                            "role_class": "access" if access_role else "official_business",
                            "source_revision": identity_revision,
                        },
                    }
                )
                append_edge(
                    person_id,
                    role_node_id,
                    "has_access_role" if access_role else "has_role",
                    "canonical_declared",
                    identity_revision,
                    metadata={"source_ref": directory_source_ref},
                    source_refs=[directory_source_ref],
                )

        # A UsageRecord is an observed WorkRun fact, never an expertise score.
        # Keep only typed refs and coarse purpose; prompts and source bodies do
        # not enter this read model.
        active_usage_ids: set[str] = set()
        known_node_ids = {str(item.get("node_id") or "") for item in nodes}

        def append_usage_record(usage: UsageRecord) -> None:
            employee_id = usage.employee_id
            revision = usage.source_revision or usage.work_run_id or usage.usage_record_id
            allowed_employee_ids = list(
                dict.fromkeys([employee_id, *usage.allowed_employee_ids])
            )

            def ensure_usage_node(
                node_id: str,
                node_type: str,
                title: str,
                *,
                visibility: str = "private",
            ) -> None:
                if not node_id or node_id in known_node_ids:
                    return
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "payload": {
                            "title": title or node_id,
                            "visibility": visibility,
                            "owner": employee_id if visibility == "private" else "",
                            "allowed_employee_ids": allowed_employee_ids
                            if visibility in {"private", "directory"}
                            else [],
                            "allowed_team_ids": list(usage.allowed_team_ids),
                            "source_revision": revision,
                        },
                    }
                )
                known_node_ids.add(node_id)

            ensure_usage_node(
                usage.person_ref,
                "person",
                employee_id,
                visibility="private",
            )
            usage_payload = usage.model_dump(mode="json")
            graph_visibility = (
                "private"
                if usage.visibility in {"private", "internal"}
                else usage.visibility
            )
            nodes.append(
                {
                    "node_id": usage.usage_record_id,
                    "node_type": "usage_record",
                    "payload": {
                        **usage_payload,
                        "title": usage.purpose,
                        "owner": employee_id,
                        "declared_visibility": usage.visibility,
                        "visibility": graph_visibility,
                        "allowed_employee_ids": allowed_employee_ids,
                        "allowed_team_ids": list(usage.allowed_team_ids),
                        "source_revision": revision,
                        "observed_at": usage_payload["occurred_at"],
                    },
                }
            )
            known_node_ids.add(usage.usage_record_id)
            append_edge(
                usage.person_ref,
                usage.usage_record_id,
                "has_usage",
                usage.provenance,
                revision,
                metadata={
                    "source_ref": usage.usage_record_id,
                    "source_revision": revision,
                    "valid_from": usage.model_dump(mode="json").get("valid_from"),
                    "valid_to": usage.model_dump(mode="json").get("valid_to"),
                    "tombstoned_at": usage.model_dump(mode="json").get("tombstoned_at"),
                },
            )

            ensure_usage_node(
                usage.agent_definition_ref,
                "agent_definition",
                usage.agent_definition_ref,
                visibility="public",
            )
            ensure_usage_node(
                usage.agent_deployment_ref,
                "agent_deployment",
                usage.agent_deployment_ref,
                visibility="directory",
            )
            if usage.agent_deployment_ref:
                append_edge(
                    usage.usage_record_id,
                    usage.agent_deployment_ref,
                    "used_agent",
                    usage.provenance,
                    revision,
                    metadata={"source_ref": usage.usage_record_id, "source_revision": revision},
                )
            if usage.agent_deployment_ref and usage.agent_definition_ref:
                append_edge(
                    usage.agent_deployment_ref,
                    usage.agent_definition_ref,
                    "part_of",
                    "canonical_declared",
                    usage.version or revision,
                    metadata={"source_ref": usage.usage_record_id, "source_revision": revision},
                )
            ensure_usage_node(
                usage.system_ref,
                "system",
                usage.system_ref,
                visibility="directory",
            )
            if usage.system_ref:
                append_edge(
                    usage.usage_record_id,
                    usage.system_ref,
                    "used_system",
                    usage.provenance,
                    revision,
                    metadata={"source_ref": usage.usage_record_id, "source_revision": revision},
                )

            if usage.task_ref:
                task_node_ref = (
                    usage.task_ref
                    if usage.task_ref.startswith(("task:", "runtime-task:"))
                    else f"task:{usage.task_ref}"
                )
                task_run_key = usage.task_ref.removeprefix("runtime-task:")
                task_run = self.store.get("task_runs", task_run_key) or {}
                task_title = str(
                    task_run.get("task_ref")
                    or task_run.get("task_id")
                    or usage.task_ref
                )
                ensure_usage_node(task_node_ref, "task", task_title)
                append_edge(
                    usage.usage_record_id,
                    task_node_ref,
                    "used_in_task",
                    usage.provenance,
                    revision,
                    metadata={"source_ref": usage.usage_record_id, "source_revision": revision},
                )

            for ref, relation, node_type in [
                *[(item, "uses_action", "action") for item in usage.action_refs],
                *[(item, "uses_skill", "skill") for item in usage.skill_refs],
                *[(item, "used_connector", "connector") for item in usage.connector_refs],
                *[(item, "used_harness", "harness_version") for item in usage.harness_refs],
            ]:
                ensure_usage_node(ref, node_type, ref)
                append_edge(
                    usage.usage_record_id,
                    ref,
                    relation,
                    usage.provenance,
                    revision,
                    metadata={"source_ref": usage.usage_record_id, "source_revision": revision},
                )
            for result_ref in usage.result_refs:
                if self.store.get("external_work_results", result_ref):
                    result_type = "external_work_result"
                elif self.store.get("completion_records", result_ref):
                    result_type = "completion_record"
                elif self.store.get("action_runs", result_ref):
                    result_type = "action_run"
                elif self.store.get("outcomes", result_ref):
                    result_type = "outcome"
                else:
                    result_type = "output_artifact"
                ensure_usage_node(result_ref, result_type, result_ref)
                append_edge(
                    usage.usage_record_id,
                    result_ref,
                    "produces",
                    usage.provenance,
                    revision,
                    metadata={"source_ref": usage.usage_record_id, "source_revision": revision},
                )

        action_runs_by_work_run: dict[str, list[str]] = {}
        for action_run in self.store.list("action_runs", limit=10_000):
            action_run_id = str(action_run.get("action_run_id") or "")
            source_work_run_id = str(action_run.get("work_run_id") or "")
            if action_run_id and source_work_run_id:
                action_runs_by_work_run.setdefault(source_work_run_id, []).append(
                    action_run_id
                )

        for run in self.store.list("work_runs", limit=10_000):
            work_run_id = str(run.get("work_run_id") or "")
            employee_id = str(run.get("employee_id") or "")
            if not work_run_id or not employee_id:
                continue
            intent = run.get("intent") if isinstance(run.get("intent"), dict) else {}
            context = self.store.get("contexts", str(run.get("context_id") or "")) or {}
            business_context = (
                context.get("business_context")
                if isinstance(context.get("business_context"), dict)
                else {}
            )
            contract_revisions = (
                run.get("contract_revisions")
                if isinstance(run.get("contract_revisions"), dict)
                else {}
            )
            action_refs = list(
                dict.fromkeys(
                    str(item)
                    for item in [
                        business_context.get("action_key"),
                        intent.get("target_ref")
                        if str(intent.get("asset_kind") or "") == "action"
                        else "",
                    ]
                    if item is not None and str(item).strip()
                )
            )
            skill_refs = list(
                dict.fromkeys(
                    str(item)
                    for item in business_context.get("skill_refs") or []
                    if str(item)
                )
            )
            harness_refs = [
                f"harness:{binding.get('harness_id')}:{binding.get('version') or 'current'}:{binding.get('model_profile') or 'default'}"
                for binding in run.get("harness_bindings") or []
                if isinstance(binding, dict) and binding.get("harness_id")
            ]
            result_refs = list(
                dict.fromkeys(
                    str(item)
                    for item in [
                        *(run.get("artifact_refs") or []),
                        *action_runs_by_work_run.get(work_run_id, []),
                        run.get("outcome_id"),
                        run.get("completion_record_id"),
                        run.get("job_id"),
                    ]
                    if item is not None and str(item).strip()
                )
            )
            occurred_at = _parse_time(
                str(run.get("updated_at") or run.get("created_at") or "")
            ) or datetime.now(timezone.utc)
            usage_id = _stable_id("usage", work_run_id, employee_id)
            active_usage_ids.add(usage_id)
            usage = UsageRecord(
                usage_id=usage_id,
                employee_id=employee_id,
                person_ref=f"person:{employee_id}",
                task_ref=str(context.get("task_ref") or ""),
                work_run_id=work_run_id,
                agent_definition_ref="agent:boi-agent",
                agent_deployment_ref="agent-deployment:boi-agent:harness-runtime",
                system_ref="system:boi-wiki",
                connector_refs=[
                    str(item)
                    for item in business_context.get("connector_refs") or []
                    if str(item)
                ],
                action_refs=action_refs,
                skill_refs=skill_refs,
                harness_refs=harness_refs,
                purpose=(
                    f"{str(intent.get('asset_kind') or 'knowledge')}:"
                    f"{str(intent.get('operation') or 'understand')}"
                ),
                version=str(contract_revisions.get("capability_catalog") or ""),
                result_refs=result_refs,
                source="work_run",
                provenance="operational_verified",
                visibility="private",
                allowed_employee_ids=[employee_id],
                allowed_team_ids=list(
                    next(
                        (
                            identity.teams
                            for identity in self.directory_principals(principal)
                            if identity.employee_id == employee_id
                        ),
                        [],
                    )
                ),
                occurred_at=occurred_at,
            )
            self.store.put("usage_records", usage_id, usage.model_dump(mode="json"))
            append_usage_record(usage)
        for usage in self.store.list("usage_records", limit=20_000):
            usage_id = str(usage.get("usage_record_id") or usage.get("usage_id") or "")
            if not usage_id or usage_id in active_usage_ids:
                continue
            try:
                persisted_usage = UsageRecord.model_validate(
                    {
                        field: usage[field]
                        for field in UsageRecord.model_fields
                        if field in usage
                    }
                )
            except Exception:
                continue
            if (
                persisted_usage.source == "work_run"
                and not self.store.get("work_runs", persisted_usage.work_run_id)
                and not self.store.get("workflow_runs", persisted_usage.work_run_id)
                and not persisted_usage.source_ref
                and not persisted_usage.source_revision
            ):
                self.store.delete("usage_records", usage_id)
                continue
            active_usage_ids.add(usage_id)
            append_usage_record(persisted_usage)

        # Materialize the Event -> Workflow -> Task -> Action/Result/Outcome
        # execution lineage from the append-only runtime records. UsageRecord
        # remains the person/system observation, while these edges preserve
        # the actual business-work topology so a Task can be explored without
        # first traversing through a person's tool usage. All nodes inherit the
        # runtime principal ACL before they enter the read model.
        def ensure_runtime_node(
            node_id: str,
            node_type: str,
            title: str,
            row: dict[str, Any],
        ) -> None:
            if not node_id or node_id in known_node_ids:
                return
            employee_id = str(row.get("employee_id") or "")
            allowed_employee_ids = [employee_id] if employee_id else []
            allowed_team_ids = list(
                next(
                    (
                        identity.teams
                        for identity in self.directory_principals(principal)
                        if identity.employee_id == employee_id
                    ),
                    [],
                )
            )
            revision = str(
                row.get("revision")
                or row.get("updated_at")
                or row.get("created_at")
                or node_id
            )
            nodes.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "payload": {
                        "title": title or node_id,
                        "visibility": "private",
                        "owner": employee_id,
                        "allowed_employee_ids": allowed_employee_ids,
                        "allowed_team_ids": allowed_team_ids,
                        "status": str(row.get("status") or "active"),
                        "observed_at": str(
                            row.get("updated_at")
                            or row.get("created_at")
                            or row.get("occurred_at")
                            or ""
                        ),
                        "source_revision": revision,
                    },
                }
            )
            known_node_ids.add(node_id)

        workflow_runs = {
            str(row.get("workflow_run_id") or ""): row
            for row in self.store.list("workflow_runs", limit=10_000)
            if str(row.get("workflow_run_id") or "")
        }
        task_runs = {
            str(row.get("task_run_id") or ""): row
            for row in self.store.list("task_runs", limit=20_000)
            if str(row.get("task_run_id") or "")
        }
        event_occurrences = {
            str(row.get("event_occurrence_id") or ""): row
            for row in self.store.list("event_occurrences", limit=10_000)
            if str(row.get("event_occurrence_id") or "")
        }
        action_runs = {
            str(row.get("action_run_id") or ""): row
            for row in self.store.list("action_runs", limit=20_000)
            if str(row.get("action_run_id") or "")
        }
        external_results = {
            str(row.get("external_work_result_id") or ""): row
            for row in self.store.list("external_work_results", limit=20_000)
            if str(row.get("external_work_result_id") or "")
        }
        outcomes = {
            str(row.get("outcome_id") or ""): row
            for row in self.store.list("outcomes", limit=20_000)
            if str(row.get("outcome_id") or "")
        }
        evidence_ledgers = {
            str(row.get("ledger_id") or ""): row
            for row in self.store.list("evidence_ledger", limit=20_000)
            if str(row.get("ledger_id") or "")
        }

        for workflow_run_id, workflow in workflow_runs.items():
            ensure_runtime_node(
                workflow_run_id,
                "workflow_run",
                str(workflow.get("workflow_ref") or workflow_run_id),
                workflow,
            )
            event_occurrence_id = str(workflow.get("event_occurrence_id") or "")
            event_occurrence = event_occurrences.get(event_occurrence_id)
            if event_occurrence:
                ensure_runtime_node(
                    event_occurrence_id,
                    "event_occurrence",
                    str(event_occurrence.get("event_type") or event_occurrence_id),
                    event_occurrence,
                )
                append_edge(
                    workflow_run_id,
                    event_occurrence_id,
                    "triggered_by",
                    "operational_verified",
                    str(workflow.get("revision") or workflow_run_id),
                    source_refs=[workflow_run_id, event_occurrence_id],
                    metadata={"source_ref": workflow_run_id},
                )

            for task_run_id in workflow.get("task_run_ids") or []:
                task_run_id = str(task_run_id or "")
                task = task_runs.get(task_run_id)
                if not task:
                    continue
                task_node_ref = f"runtime-task:{task_run_id}"
                ensure_runtime_node(
                    task_node_ref,
                    "task",
                    str(task.get("task_ref") or task.get("task_id") or task_run_id),
                    task,
                )
                append_edge(
                    workflow_run_id,
                    task_node_ref,
                    "has_task",
                    str(task.get("provenance") or "operational_verified"),
                    str(task.get("revision") or task_run_id),
                    source_refs=[workflow_run_id, task_run_id],
                    metadata={"source_ref": task_run_id},
                )

                for action_run_id in workflow.get("action_run_ids") or []:
                    action_run_id = str(action_run_id or "")
                    action = action_runs.get(action_run_id)
                    if not action or str(action.get("task_run_id") or "") != task_run_id:
                        continue
                    ensure_runtime_node(
                        action_run_id,
                        "action_run",
                        str(action.get("action_ref") or action_run_id),
                        action,
                    )
                    append_edge(
                        task_node_ref,
                        action_run_id,
                        "executes",
                        str(action.get("provenance") or "operational_verified"),
                        str(action.get("updated_at") or action_run_id),
                        source_refs=[task_run_id, action_run_id],
                        metadata={"source_ref": action_run_id},
                    )
                    action_ref = str(action.get("action_ref") or "")
                    if action_ref:
                        ensure_runtime_node(action_ref, "action", action_ref, action)
                        append_edge(
                            action_run_id,
                            action_ref,
                            "uses_action",
                            str(action.get("provenance") or "operational_verified"),
                            str(action.get("updated_at") or action_run_id),
                            source_refs=[action_run_id],
                            metadata={"source_ref": action_run_id},
                        )

                for result_ref in [
                    str(task.get("result_ref") or ""),
                    *[
                        str(item or "")
                        for item in workflow.get("executor_result_refs") or []
                    ],
                ]:
                    result = external_results.get(result_ref)
                    if not result or str(result.get("task_run_id") or "") != task_run_id:
                        continue
                    ensure_runtime_node(
                        result_ref,
                        "external_work_result",
                        str((result.get("result") or {}).get("summary") or result_ref),
                        result,
                    )
                    append_edge(
                        task_node_ref,
                        result_ref,
                        "produces",
                        "operational_verified",
                        str(result.get("created_at") or result_ref),
                        source_refs=[task_run_id, result_ref],
                        metadata={"source_ref": result_ref},
                    )

                for outcome_id, outcome in outcomes.items():
                    if task_run_id not in {
                        str(item) for item in outcome.get("task_run_ids") or []
                    }:
                        continue
                    ensure_runtime_node(
                        outcome_id,
                        "outcome",
                        str(outcome.get("boi_ref") or outcome_id),
                        outcome,
                    )
                    append_edge(
                        task_node_ref,
                        outcome_id,
                        "results_in",
                        "operational_verified",
                        str(outcome.get("created_at") or outcome_id),
                        source_refs=[task_run_id, outcome_id],
                        metadata={"source_ref": outcome_id},
                    )
                    ledger_refs = [
                        str(outcome.get("evidence_ledger_ref") or ""),
                        *[
                            str(item or "")
                            for item in outcome.get("evidence_ledger_ids") or []
                        ],
                    ]
                    for ledger_ref in dict.fromkeys(ledger_refs):
                        ledger = evidence_ledgers.get(ledger_ref)
                        if not ledger:
                            continue
                        ensure_runtime_node(
                            ledger_ref,
                            "evidence_ledger",
                            str(ledger.get("title") or ledger_ref),
                            ledger,
                        )
                        append_edge(
                            task_node_ref,
                            ledger_ref,
                            "requires_evidence",
                            "operational_verified",
                            str(ledger.get("updated_at") or ledger_ref),
                            source_refs=[task_run_id, ledger_ref],
                            metadata={"source_ref": ledger_ref},
                        )

        # Operational learning relations are administrator-only. They make the
        # runtime Harness inspectable without turning diagnostics into public knowledge.
        operational_revision = self.runtime_relation_signature()
        if operational_revision:
            admin_employee_ids = [
                item.employee_id
                for item in self.directory_principals(compiler_principal)
                if item.is_admin
            ]

            def append_operational_node(node_id: str, node_type: str, title: str, row: dict[str, Any]) -> None:
                existing = next(
                    (
                        item
                        for item in reversed(nodes)
                        if str(item.get("node_id") or "") == node_id
                    ),
                    {},
                )
                existing_payload = (
                    existing.get("payload")
                    if isinstance(existing.get("payload"), dict)
                    else {}
                )
                row_owner = str(row.get("employee_id") or "")
                allowed_employee_ids = list(
                    dict.fromkeys(
                        [
                            *admin_employee_ids,
                            *([row_owner] if row_owner else []),
                            *[
                                str(item)
                                for item in existing_payload.get("allowed_employee_ids") or []
                                if str(item)
                            ],
                        ]
                    )
                )
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "payload": {
                            "title": title,
                            "visibility": "private",
                            "owner": str(existing_payload.get("owner") or row_owner),
                            "allowed_employee_ids": allowed_employee_ids,
                            "status": str(row.get("status") or ""),
                            "source_revision": str(row.get("updated_at") or row.get("created_at") or operational_revision),
                            "observed_at": str(row.get("updated_at") or row.get("created_at") or ""),
                        },
                    }
                )

            harness_nodes: set[str] = set()
            for run in self.store.list("work_runs", limit=10_000):
                run_id = str(run.get("work_run_id") or "")
                if not run_id:
                    continue
                run_node_id = f"work-run:{run_id}"
                append_operational_node(run_node_id, "work_run", str((run.get("intent") or {}).get("resolved_goal") or "업무 실행"), run)
                for binding in run.get("harness_bindings") or []:
                    if not isinstance(binding, dict) or not binding.get("harness_id"):
                        continue
                    harness_node_id = f"harness:{binding['harness_id']}:{binding.get('version') or 'current'}:{binding.get('model_profile') or 'default'}"
                    if harness_node_id not in harness_nodes:
                        append_operational_node(harness_node_id, "harness_version", str(binding.get("harness_id")), binding)
                        harness_nodes.add(harness_node_id)
                    append_edge(run_node_id, harness_node_id, "used_harness", "extracted", operational_revision, metadata={"source_ref": run_id})

            for pattern in self.store.list("harness_failure_patterns", limit=10_000):
                pattern_id = str(pattern.get("failure_pattern_id") or "")
                if not pattern_id:
                    continue
                append_operational_node(pattern_id, "failure_pattern", str(pattern.get("summary") or "반복 실패"), pattern)
                for run_id in pattern.get("work_run_ids") or []:
                    append_edge(pattern_id, f"work-run:{run_id}", "observed_in", "extracted", operational_revision, metadata={"source_ref": pattern_id})

            for candidate in self.store.list("harness_candidates", limit=10_000):
                candidate_id = str(candidate.get("candidate_id") or "")
                if not candidate_id:
                    continue
                append_operational_node(candidate_id, "harness_candidate", str(candidate.get("rationale") or "Harness 개선 후보"), candidate)
                for pattern_id in candidate.get("failure_pattern_ids") or []:
                    append_edge(candidate_id, str(pattern_id), "addresses_failure", "declared", operational_revision, metadata={"source_ref": candidate_id})
                eval_id = str(candidate.get("latest_eval_id") or "")
                if eval_id:
                    append_edge(candidate_id, eval_id, "evaluated_by", "extracted", operational_revision, metadata={"source_ref": candidate_id})

            for evaluation in self.store.list("harness_eval_runs", limit=10_000):
                eval_id = str(evaluation.get("eval_id") or "")
                if eval_id:
                    append_operational_node(eval_id, "evaluation_run", "Harness 회귀·안전 평가", evaluation)

            for version in self.store.list("harness_versions", limit=10_000):
                version_id = str(version.get("harness_version_id") or "")
                if not version_id:
                    continue
                append_operational_node(version_id, "harness_version", str(version.get("harness_id") or "Harness 버전"), version)
                candidate_id = str(version.get("candidate_id") or "")
                if candidate_id:
                    append_edge(version_id, candidate_id, "approved_from", "human_verified", operational_revision, metadata={"source_ref": version_id})

            for playbook in self.store.list("context_playbook_items", limit=10_000):
                item_id = str(playbook.get("item_id") or "")
                if not item_id:
                    continue
                append_operational_node(item_id, "context_playbook_item", str(playbook.get("description") or "업무 맥락 Playbook"), playbook)
                for run_id in playbook.get("supporting_work_run_ids") or []:
                    append_edge(item_id, f"work-run:{run_id}", "supported_by", "declared", operational_revision, metadata={"source_ref": item_id})

        unique_nodes = {str(item["node_id"]): item for item in nodes}
        unique_edges = {str(item["edge_id"]): item for item in edges}
        previous = self.store.get("manifests", "knowledge_graph") or {}
        previous_nodes = {str(item) for item in previous.get("node_ids") or []}
        previous_edges = {str(item) for item in previous.get("edge_ids") or []}
        current_nodes = set(unique_nodes)
        current_edges = set(unique_edges)
        removed_nodes = sorted(previous_nodes - current_nodes)
        removed_edges = sorted(previous_edges - current_edges)
        self.store.remove_ontology_entries(removed_nodes, removed_edges)
        self.store.upsert_ontology(list(unique_nodes.values()), list(unique_edges.values()))
        manifest = {
            "compiler_version": EXTRACTOR_VERSION,
            "ontology_schema_revision": self.ontology_registry.schema_revision,
            "ontology_schema_checksum": self.ontology_registry.checksum,
            "source_signature": self.repository.source_signature(),
            "runtime_relation_signature": self.runtime_relation_signature(),
            "directory_signature": self.directory_signature(principal),
            "nodes": len(unique_nodes),
            "edges": len(unique_edges),
            "node_ids": sorted(current_nodes),
            "edge_ids": sorted(current_edges),
            "removed_nodes": len(removed_nodes),
            "removed_edges": len(removed_edges),
            "sync_mode": "incremental_upsert",
            "compiled_at": now_iso(),
        }
        self.store.put("manifests", "knowledge_graph", manifest)
        return manifest

    def graph_snapshot_state(self, principal: Principal) -> dict[str, Any]:
        """Describe the stored Ontology read model without rebuilding it.

        A user read must stay bounded. Graph compilation can traverse every
        canonical record and operational relation, so it belongs to the
        explicit/background reconciliation path rather than ``query`` or a
        readiness probe. A compatible stale snapshot may still be inspected
        by callers that do not require freshness; incompatible snapshots fail
        closed.
        """

        manifest = self.store.get("manifests", "knowledge_graph") or {}
        current_source_signature = self.repository.source_signature()
        current_directory_signature = self.directory_signature(principal)
        compatibility_checks = {
            "manifest": bool(manifest),
            "compiler": manifest.get("compiler_version") == EXTRACTOR_VERSION,
            "ontology_schema": (
                manifest.get("ontology_schema_revision")
                == self.ontology_registry.schema_revision
                and manifest.get("ontology_schema_checksum")
                == self.ontology_registry.checksum
            ),
        }
        compatible = all(compatibility_checks.values())
        freshness_checks = {
            "source": bool(compatible)
            and manifest.get("source_signature") == current_source_signature,
            "directory": bool(compatible)
            and manifest.get("directory_signature") == current_directory_signature,
        }
        fresh = bool(compatible and all(freshness_checks.values()))
        status = "ready" if fresh else "stale" if compatible else "unavailable"
        reasons = [
            name
            for name, passed in {**compatibility_checks, **freshness_checks}.items()
            if not passed
        ]
        return {
            "status": status,
            "available": bool(manifest),
            "compatible": compatible,
            "fresh": fresh,
            "degraded_reasons": reasons,
            "compiler_version": str(manifest.get("compiler_version") or ""),
            "ontology_schema_revision": str(
                manifest.get("ontology_schema_revision") or ""
            ),
            "ontology_schema_checksum": str(
                manifest.get("ontology_schema_checksum") or ""
            ),
            "source_signature": str(manifest.get("source_signature") or ""),
            "current_source_signature": current_source_signature,
            "directory_signature": str(manifest.get("directory_signature") or ""),
            "current_directory_signature": current_directory_signature,
            "runtime_relation_signature": str(
                manifest.get("runtime_relation_signature") or ""
            ),
            # Exact runtime relation freshness is intentionally not probed
            # here: calculating it scans durable execution ledgers. Writers
            # and reconciliation jobs own that invalidation/refresh cycle.
            "runtime_relation_freshness": "not_probed",
            "compiled_at": str(manifest.get("compiled_at") or ""),
            "nodes": int(manifest.get("nodes") or 0),
            "edges": int(manifest.get("edges") or 0),
        }

    def sync_source(self, principal: Principal, source_id: str) -> dict[str, Any]:
        source = self._require_source(principal, source_id)
        source["status"] = "syncing"
        source["last_error"] = ""
        self.store.put("knowledge_sources", source_id, source)
        kind = str(source.get("source_kind") or "")
        if kind in {"graphify", "openkb"}:
            return {"source": source, "job": self._queue_adapter_job(principal, source)}
        if kind in {"codegraph", "external_cli"}:
            adapter_state = self._optional_adapter_state(source)
            source.update(
                {
                    "status": "ready" if adapter_state["ready"] else "unavailable",
                    "last_error": "" if adapter_state["ready"] else adapter_state["message"],
                    "last_sync_at": now_iso(),
                    "revision": int(source.get("revision") or 1) + 1,
                }
            )
            self.store.put("knowledge_sources", source_id, source)
            return {"source": source, "adapter": adapter_state, "changed": [], "removed": []}

        self.repository.invalidate_source_cache()
        records = self._records_for_source(principal, source)
        checksums = {item.record_id: record_content_checksum(item) for item in records}
        if kind == "git":
            revision = self._git_revision(str(source.get("location") or ""))
            checksums = {"git_revision": revision} if revision else {}
        old_manifest = self.store.get("knowledge_source_manifests", source_id) or {}
        old_checksums = old_manifest.get("records") if isinstance(old_manifest.get("records"), dict) else {}
        changed = sorted(key for key, value in checksums.items() if old_checksums.get(key) != value)
        removed = sorted(set(old_checksums) - set(checksums))
        graph = self.compile_graph(principal)
        index_result: dict[str, Any]
        try:
            index_result = self.search.reconcile(principal)
        except RuntimeError as exc:
            index_result = {"status": "lexical_ready", "reason": str(exc)}
        manifest = {
            "source_id": source_id,
            "records": checksums,
            "source_checksum": hashlib.sha256(
                json.dumps(checksums, sort_keys=True).encode("utf-8")
            ).hexdigest(),
            "changed": changed,
            "removed": removed,
            "graph": graph,
            "index_status": index_result.get("status") or "unknown",
            "synced_at": now_iso(),
        }
        self.store.put("knowledge_source_manifests", source_id, manifest)
        source.update(
            {
                "status": "ready",
                "checksum": manifest["source_checksum"],
                "last_sync_at": manifest["synced_at"],
                "last_error": "",
                "revision": int(source.get("revision") or 1) + 1,
            }
        )
        self.store.put("knowledge_sources", source_id, source)
        return {"source": source, "changed": changed, "removed": removed, "graph": graph, "index": index_result}

    def explore(
        self,
        principal: Principal,
        *,
        view: str,
        source_ref: str = "",
        target_ref: str = "",
        q: str = "",
        depth: int = 2,
        limit: int = 80,
        cursor: str = "",
        node_kinds: list[str] | None = None,
        relation_kinds: list[str] | None = None,
        provenance: list[str] | None = None,
        direction: str = "both",
        time_from: str = "",
        time_to: str = "",
    ) -> dict[str, Any]:
        supported = {
            "ranked",
            *[item.query_kind for item in self.ontology_registry.document.query_recipes],
        }
        if view not in supported:
            raise HTTPException(
                status_code=422,
                detail={"code": "unknown_ontology_view", "view": view},
            )
        mode = view
        if mode == "ranked":
            result = self.search.search(q or source_ref, principal, limit=min(limit, 20))
            return {"view": mode, **result.model_dump(mode="json")}
        if not source_ref:
            raise HTTPException(status_code=422, detail="관계를 살펴볼 지식을 선택해주세요.")
        offset = int(cursor) if str(cursor).isdigit() else 0
        plan = GraphQueryPlan(
            focal_entities=[source_ref],
            target_entities=[target_ref] if target_ref else [],
            query_kind=mode,  # type: ignore[arg-type]
            recipe_id=mode,
            node_kinds=[str(item) for item in (node_kinds or []) if str(item)],
            relation_kinds=[str(item) for item in (relation_kinds or []) if str(item)],
            provenance=[str(item) for item in (provenance or []) if str(item)],
            direction=direction,  # type: ignore[arg-type]
            depth=depth,
            time_from=time_from,
            time_to=time_to,
            limit=max(1, min(offset + limit + 1, 500)),
            presentation="auto",
        )
        result = (
            self._canonical_projection_query(principal, plan)
            if self.settings.canonical_projection_enabled
            else self.query(principal, plan)
        )
        if mode == "neighbors":
            all_edges = list(result.get("edges") or [])
            page_edges = all_edges[offset : offset + limit]
            page_refs = {source_ref}
            for edge in page_edges:
                page_refs.update(
                    {
                        str(edge.get("source_id") or ""),
                        str(edge.get("target_id") or ""),
                    }
                )
            result["edges"] = page_edges
            result["nodes"] = [
                item
                for item in result.get("nodes") or []
                if str(item.get("node_id") or "") in page_refs
            ]
            result["cursor"] = str(offset)
            result["next_cursor"] = (
                str(offset + limit) if len(all_edges) > offset + limit else ""
            )
        return {"view": mode, "source_ref": source_ref, **result}

    def _canonical_projection_query(
        self,
        principal: Principal,
        plan: GraphQueryPlan,
    ) -> dict[str, Any]:
        """Traverse only resolved, ACL-visible edges from the active Release."""

        visible_records = {
            record.record_id: record
            for record in self.repository.authoritative_records(
                principal,
                include_drafts=True,
            )
        }
        source_id = str((plan.focal_entities or [""])[0])
        target_id = str((plan.target_entities or [""])[0])
        if source_id not in visible_records:
            raise HTTPException(
                status_code=404,
                detail="이 관계 항목을 찾을 수 없거나 접근할 수 없습니다.",
            )
        bundle = CanonicalProjectionReader(self.settings.runtime_root).load_active()
        recipe = self.ontology_registry.query_recipe(
            query_kind=plan.query_kind,
            recipe_id=plan.recipe_id,
        )
        is_path_query = recipe.operator == "path"
        requested_relations = set(plan.relation_kinds)
        edges: list[dict[str, Any]] = []
        for item in bundle.graph_edges:
            source = str(item.get("source_boi_id") or "")
            target = str(item.get("target_boi_id") or "")
            relation = str(item.get("relation") or "")
            if (
                not item.get("resolved")
                or source not in visible_records
                or target not in visible_records
                or (requested_relations and relation not in requested_relations)
            ):
                continue
            edges.append(
                _decorate_edge(
                    {
                        "edge_id": _stable_id(
                            "release-edge",
                            bundle.release_id,
                            source,
                            relation,
                            target,
                        ),
                        "source_id": source,
                        "target_id": target,
                        "relation": relation,
                        "depth": 1,
                        "payload": {
                            "provenance": "released",
                            "release_id": bundle.release_id,
                            "release_manifest_digest": bundle.release_manifest_digest,
                            "source_revision_id": item.get("source_revision_id"),
                            "target_revision_id": item.get("target_revision_id"),
                        },
                    },
                    ontology_registry=self.ontology_registry,
                )
            )

        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for edge in edges:
            outgoing = str(edge["source_id"])
            incoming = str(edge["target_id"])
            if plan.direction in {"outgoing", "both"}:
                adjacency[outgoing].append((incoming, edge))
            if plan.direction in {"incoming", "both"}:
                adjacency[incoming].append((outgoing, edge))

        discovered = {source_id}
        selected_edges: dict[str, dict[str, Any]] = {}
        queue: deque[tuple[str, int]] = deque([(source_id, 0)])
        parent: dict[str, tuple[str, dict[str, Any]]] = {}
        while queue and len(selected_edges) < plan.limit:
            current, current_depth = queue.popleft()
            if current_depth >= plan.depth:
                continue
            for neighbor, edge in adjacency.get(current, []):
                edge_key = str(edge["edge_id"])
                selected_edges.setdefault(edge_key, edge)
                if neighbor not in discovered:
                    discovered.add(neighbor)
                    parent[neighbor] = (current, edge)
                    queue.append((neighbor, current_depth + 1))
                if is_path_query and target_id and neighbor == target_id:
                    queue.clear()
                    break

        if is_path_query:
            if not target_id or target_id not in discovered:
                discovered = {source_id}
                selected_edges = {}
            else:
                path_edges: dict[str, dict[str, Any]] = {}
                path_nodes = {target_id}
                cursor_id = target_id
                while cursor_id != source_id:
                    previous, edge = parent[cursor_id]
                    path_edges[str(edge["edge_id"])] = edge
                    path_nodes.add(previous)
                    cursor_id = previous
                discovered = path_nodes
                selected_edges = path_edges

        requested_node_kinds = set(plan.node_kinds)
        nodes = []
        for record_id in sorted(discovered):
            record = visible_records[record_id]
            if requested_node_kinds and record.kind not in requested_node_kinds:
                continue
            nodes.append(
                {
                    "node_id": record.record_id,
                    "node_type": record.kind,
                    "payload": {
                        "title": record.title,
                        "summary": record.description,
                        "url": record.url,
                        "visibility": record.visibility,
                        "release_id": bundle.release_id,
                        "release_manifest_digest": bundle.release_manifest_digest,
                    },
                }
            )
        visible_node_ids = {str(node["node_id"]) for node in nodes}
        projected_edges = [
            edge
            for edge in selected_edges.values()
            if str(edge["source_id"]) in visible_node_ids
            and str(edge["target_id"]) in visible_node_ids
        ]
        projected_edges.sort(
            key=lambda edge: (
                str(edge["source_id"]),
                str(edge["relation"]),
                str(edge["target_id"]),
            )
        )
        return {
            "ok": True,
            "meaningful": bool(nodes),
            "status": "ready",
            "query_plan": plan.model_dump(mode="json"),
            "presentation": "list" if plan.presentation == "auto" else plan.presentation,
            "nodes": nodes,
            "edges": projected_edges,
            "read_model_state": {
                "status": "ready",
                "source": "active_release_projection",
                "release_id": bundle.release_id,
                "release_manifest_digest": bundle.release_manifest_digest,
                "projection_digest": bundle.projection_digest,
            },
            "degraded": [],
        }
    def node(self, principal: Principal, node_id: str) -> dict[str, Any]:
        graph = self.store.ontology_neighbors(
            [node_id],
            depth=1,
            limit=80,
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=principal.is_admin,
        )
        node = next((item for item in graph.get("nodes") or [] if str(item.get("node_id") or "") == node_id), None)
        if not node:
            raise HTTPException(status_code=404, detail="이 관계 항목을 찾을 수 없거나 접근할 수 없습니다.")
        edges = [
            item
            for item in _dedupe_semantic_edges(
                graph.get("edges") or [],
                ontology_registry=self.ontology_registry,
            )
            if node_id in {str(item.get("source_id") or ""), str(item.get("target_id") or "")}
        ]
        return {"node": node, "edges": edges, "relation_count": len(edges)}

    def resolve_node_reference(
        self,
        principal: Principal,
        reference: str,
        *,
        lookup_key: str = "source_ref",
    ) -> str:
        """Resolve one visible node through Registry-declared identity aliases.

        Exact identities always win. An alias is accepted only when exactly
        one ACL-visible candidate exists; hidden and ambiguous candidates have
        the same observable result as a missing candidate.
        """

        clean = str(reference or "").strip()
        if not clean:
            return ""
        candidates = list(
            dict.fromkeys(
                [
                    clean,
                    *self.ontology_registry.entity_lookup_candidates(
                        lookup_key,
                        clean,
                    ),
                ]
            )
        )
        graph = self.store.ontology_neighbors(
            candidates,
            # Identity resolution needs ACL-visible nodes, not their edges.
            # A zero-depth lookup preserves pre-traversal ACL semantics while
            # avoiding an otherwise duplicate neighborhood query before the
            # actual Catalog recipe runs.
            depth=0,
            limit=max(1, min(len(candidates) * 10, 200)),
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=principal.is_admin,
        )
        visible_ids = {
            str(item.get("node_id") or "")
            for item in graph.get("nodes") or []
            if str(item.get("node_id") or "") in candidates
        }
        if clean in visible_ids:
            return clean
        aliases = [item for item in candidates[1:] if item in visible_ids]
        return aliases[0] if len(aliases) == 1 else clean

    def ontology_schema(self) -> dict[str, Any]:
        return self.ontology_registry.public_payload()

    @staticmethod
    def _require_ontology_admin(principal: Principal) -> None:
        if not principal.is_admin:
            raise HTTPException(status_code=403, detail="Ontology schema 관리는 Admin 전용입니다.")

    def create_ontology_proposal(
        self,
        principal: Principal,
        request: OntologyProposalCreateRequest,
    ) -> dict[str, Any]:
        self._require_ontology_admin(principal)
        if request.base_version != self.ontology_registry.version:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ontology_base_version_stale",
                    "current_version": self.ontology_registry.version,
                },
            )
        proposal_id = _stable_id(
            "ontology-proposal",
            principal.employee_id,
            request.title,
            now_iso(),
        )
        candidate_version = f"{self.ontology_registry.version}+proposal.{proposal_id[-8:]}"
        candidate_revision = f"boi-ontology-schema/proposal/{proposal_id}"
        try:
            candidate, impact = self.ontology_registry.preview_changes(
                request.changes,
                version=candidate_version,
                schema_revision=candidate_revision,
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "ontology_proposal_invalid", "message": str(exc)},
            ) from exc
        graph_manifest = self.store.get("manifests", "knowledge_graph") or {}
        proposal = {
            "proposal_id": proposal_id,
            "employee_id": principal.employee_id,
            "title": request.title,
            "reason": request.reason,
            "base_version": request.base_version,
            "base_checksum": self.ontology_registry.checksum,
            "candidate_version": candidate_version,
            "candidate_schema_revision": candidate_revision,
            "changes": request.changes,
            "candidate_schema": candidate.model_dump(mode="json"),
            "impact_preview": {
                **impact,
                "current_graph": {
                    "nodes": int(graph_manifest.get("nodes") or 0),
                    "edges": int(graph_manifest.get("edges") or 0),
                    "compiler_version": str(graph_manifest.get("compiler_version") or ""),
                },
                "requires_graph_recompile": bool(
                    impact["upserted"].get("entity_types")
                    or impact["removed"].get("entity_types")
                    or impact["upserted"].get("relation_types")
                    or impact["removed"].get("relation_types")
                ),
            },
            "status": "draft",
            "revision": 1,
            "review": {},
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        return self.store.put("ontology_schema_proposals", proposal_id, proposal)

    def ontology_proposal(
        self,
        principal: Principal,
        proposal_id: str,
    ) -> dict[str, Any]:
        self._require_ontology_admin(principal)
        proposal = self.store.get("ontology_schema_proposals", proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Ontology proposal을 찾을 수 없습니다.")
        return proposal

    def review_ontology_proposal(
        self,
        principal: Principal,
        proposal_id: str,
        request: OntologyProposalReviewRequest,
    ) -> dict[str, Any]:
        proposal = self.ontology_proposal(principal, proposal_id)
        if int(proposal.get("revision") or 0) != request.expected_revision:
            raise HTTPException(status_code=409, detail="Ontology proposal revision이 변경되었습니다.")
        if proposal.get("status") not in {"draft", "revision_required"}:
            raise HTTPException(status_code=409, detail="현재 상태에서는 review할 수 없습니다.")
        proposal.update(
            {
                "status": "approved" if request.decision == "approve" else "rejected",
                "review": {
                    "decision": request.decision,
                    "reviewer_employee_id": principal.employee_id,
                    "note": request.note,
                    "reviewed_at": now_iso(),
                },
                "revision": request.expected_revision + 1,
                "updated_at": now_iso(),
            }
        )
        return self.store.put("ontology_schema_proposals", proposal_id, proposal)

    def publish_ontology_proposal(
        self,
        principal: Principal,
        proposal_id: str,
        request: OntologyProposalPublishRequest,
    ) -> dict[str, Any]:
        proposal = self.ontology_proposal(principal, proposal_id)
        if not request.user_confirmed:
            raise HTTPException(status_code=422, detail="Ontology version publish 확인이 필요합니다.")
        if int(proposal.get("revision") or 0) != request.expected_revision:
            raise HTTPException(status_code=409, detail="Ontology proposal revision이 변경되었습니다.")
        if proposal.get("status") != "approved":
            raise HTTPException(status_code=409, detail="승인된 Ontology proposal만 publish할 수 있습니다.")
        if proposal.get("base_checksum") != self.ontology_registry.checksum:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "ontology_schema_changed_after_review",
                    "current_checksum": self.ontology_registry.checksum,
                },
            )
        schema = proposal.get("candidate_schema")
        if not isinstance(schema, dict):
            raise HTTPException(status_code=422, detail="검증된 candidate schema가 없습니다.")
        self.ontology_registry.activate_payload(schema)
        version_id = _stable_id(
            "ontology-version",
            str(proposal.get("candidate_version") or ""),
            self.ontology_registry.checksum,
        )
        version = {
            "version_id": version_id,
            "employee_id": principal.employee_id,
            "proposal_id": proposal_id,
            "version": self.ontology_registry.version,
            "schema_revision": self.ontology_registry.schema_revision,
            "checksum": self.ontology_registry.checksum,
            "schema": self.ontology_registry.document.model_dump(mode="json"),
            "review": proposal.get("review") or {},
            "publish_note": request.note,
            "published_by": principal.employee_id,
            "published_at": now_iso(),
        }
        self.store.put("ontology_schema_versions", version_id, version)
        self.store.put(
            "ontology_schema_active",
            "current",
            {
                "version_id": version_id,
                "version": version["version"],
                "checksum": version["checksum"],
                "activated_by": principal.employee_id,
                "activated_at": now_iso(),
            },
        )
        proposal.update(
            {
                "status": "published",
                "published_version_id": version_id,
                "revision": request.expected_revision + 1,
                "updated_at": now_iso(),
            }
        )
        self.store.put("ontology_schema_proposals", proposal_id, proposal)
        return {
            "status": "published",
            "version": version,
            "proposal": proposal,
            "source_file_changed": False,
            "runtime_registry_changed": True,
        }

    def project(
        self,
        principal: Principal,
        *,
        projection_id: str,
        subject_ref: str,
        as_of: str = "",
        limit: int = 200,
        section_ids: set[str] | None = None,
    ) -> dict[str, Any]:
        try:
            projection = self.ontology_registry.projection_recipe(projection_id)
            query_recipe = self.ontology_registry.query_recipe(
                recipe_id=projection.query_recipe_id
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Ontology projection을 찾을 수 없습니다.") from exc
        if projection.admin_only and not self._people_analytics_enabled(principal):
            raise HTTPException(status_code=403, detail="이 사람·조직 분석은 Admin 전용입니다.")
        selected_section_ids = set(section_ids or [])
        relation_kinds = sorted(
            {
                *projection.traversal_relation_types,
                *(
                    relation
                    for section_id, relations in projection.sections.items()
                    if not selected_section_ids or section_id in selected_section_ids
                    for relation in relations
                ),
            }
        )
        result = self.query(
            principal,
            GraphQueryPlan(
                focal_entities=[subject_ref],
                query_kind=query_recipe.query_kind,
                recipe_id=query_recipe.recipe_id,
                direction="both",
                depth=query_recipe.max_depth,
                limit=max(1, min(limit, 500)),
                relation_kinds=relation_kinds,
                as_of=as_of,
                evidence_use="read",
                presentation="auto",
            ),
            _projection_relation_scope=set(relation_kinds),
        )
        node_by_ref = {
            str(item.get("node_id") or ""): item for item in result.get("nodes") or []
        }
        subject = node_by_ref.get(subject_ref)
        if subject is None:
            # A missing and an ACL-hidden subject deliberately share one result.
            raise HTTPException(status_code=404, detail="Ontology 대상을 찾을 수 없습니다.")
        if (
            projection.subject_types
            and str(subject.get("node_type") or "") not in set(projection.subject_types)
        ):
            raise HTTPException(status_code=422, detail="이 projection에 맞는 대상 유형이 아닙니다.")
        depth_by_ref = {
            str(key): int(value)
            for key, value in (result.get("depth_by_ref") or {}).items()
            if str(key) and isinstance(value, int)
        }
        subject_node_type = str(subject.get("node_type") or "")

        def scoped_section_edges(
            section_id: str,
            section_edges: list[dict[str, Any]],
        ) -> list[dict[str, Any]]:
            # Reverse adoption projections may traverse Person -> Team and
            # then reach unrelated members of the same team.  The Registry's
            # nearest/max-depth output contracts identify the legitimate
            # endpoints. Keep only shortest evidence paths from the subject
            # to those endpoints, while retaining bridge edges on the path.
            constrained_sources = [
                source
                for sources in projection.output_fields.values()
                for source in sources
                if source.projection_id == projection.projection_id
                and source.section_id == section_id
                and (source.nearest_only or source.max_depth_by_subject_type)
            ]
            if not constrained_sources or not depth_by_ref:
                return section_edges

            endpoint_refs: set[str] = set()
            for source in constrained_sources:
                allowed_types = set(source.node_types)
                max_depth = source.max_depth_by_subject_type.get(subject_node_type)
                if source.max_depth_by_subject_type and max_depth is None:
                    continue
                candidates = [
                    node
                    for node in node_by_ref.values()
                    if str(node.get("node_id") or "") != subject_ref
                    and (
                        not allowed_types
                        or str(node.get("node_type") or "") in allowed_types
                    )
                    and str(node.get("node_id") or "") in depth_by_ref
                    and (
                        max_depth is None
                        or depth_by_ref[str(node.get("node_id") or "")] <= max_depth
                    )
                ]
                if source.nearest_only:
                    nearest_by_type: dict[str, int] = {}
                    for node in candidates:
                        node_ref = str(node.get("node_id") or "")
                        node_type = str(node.get("node_type") or "")
                        node_depth = depth_by_ref[node_ref]
                        nearest_by_type[node_type] = min(
                            node_depth,
                            nearest_by_type.get(node_type, node_depth),
                        )
                    candidates = [
                        node
                        for node in candidates
                        if depth_by_ref[str(node.get("node_id") or "")]
                        == nearest_by_type.get(str(node.get("node_type") or ""), -1)
                    ]
                endpoint_refs.update(
                    str(node.get("node_id") or "") for node in candidates
                )

            if not endpoint_refs:
                return []
            retained_edge_indexes: set[int] = set()
            pending = list(endpoint_refs)
            visited: set[str] = set()
            while pending:
                current_ref = pending.pop()
                if current_ref in visited:
                    continue
                visited.add(current_ref)
                current_depth = depth_by_ref.get(current_ref)
                if current_depth is None or current_depth <= 0:
                    continue
                for index, edge in enumerate(section_edges):
                    source_ref = str(edge.get("source_id") or "")
                    target_ref = str(edge.get("target_id") or "")
                    if current_ref == source_ref:
                        predecessor_ref = target_ref
                    elif current_ref == target_ref:
                        predecessor_ref = source_ref
                    else:
                        continue
                    if depth_by_ref.get(predecessor_ref) != current_depth - 1:
                        continue
                    retained_edge_indexes.add(index)
                    if predecessor_ref != subject_ref:
                        pending.append(predecessor_ref)
            return [
                edge
                for index, edge in enumerate(section_edges)
                if index in retained_edge_indexes
            ]

        sections: dict[str, dict[str, Any]] = {}
        for section_id, relations in projection.sections.items():
            relation_set = set(relations)
            section_edges = scoped_section_edges(
                section_id,
                [
                    item
                    for item in result.get("edges") or []
                    if str(item.get("relation") or "") in relation_set
                ],
            )
            section_refs = {subject_ref}
            for edge in section_edges:
                section_refs.update(
                    {
                        str(edge.get("source_id") or ""),
                        str(edge.get("target_id") or ""),
                    }
                )
            sections[section_id] = {
                "nodes": [
                    node_by_ref[item]
                    for item in section_refs
                    if item in node_by_ref and item != subject_ref
                ],
                "edges": section_edges,
                "count": len(section_edges),
            }
        projection_edge_count = len(
            {
                str(edge.get("edge_id") or "")
                for section in sections.values()
                for edge in section.get("edges") or []
                if str(edge.get("edge_id") or "")
            }
        )
        result.update(
            {
                # A projection is meaningful only when one of its declared
                # sections contains a relation.  The focal subject node by
                # itself proves that the subject exists, not that the
                # requested work, usage, or outcome evidence exists.
                "meaningful": projection_edge_count > 0,
                "projection_edge_count": projection_edge_count,
                "projection_id": projection.projection_id,
                "projection_label": projection.label,
                "projection_recipe": projection.model_dump(mode="json"),
                "subject": subject,
                "sections": sections,
                "as_of": as_of,
                "usage_interpretation": (
                    "공식 WorkRun 사용 기록이며 전문성·권한·성과 점수가 아닙니다."
                    if projection_id in {"person_tools", "agent_adoption", "system_adoption"}
                    else ""
                ),
            }
        )
        return result

    def query_ontology(
        self,
        principal: Principal,
        request: OntologyQueryRequest,
    ) -> dict[str, Any]:
        try:
            recipe = self.ontology_registry.projection_recipe(request.recipe)
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        analytics_enabled = self._people_analytics_enabled(principal)

        resolved_subjects: list[dict[str, str]] = []
        for subject in request.subjects:
            try:
                entity_type = self.ontology_registry.entity_type(subject.entity_type)
            except KeyError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
            entity_ref = subject.entity_ref.strip()
            lookup_key = ""
            lookup_value = ""
            if not entity_ref:
                for key, value in subject.lookup.items():
                    template = entity_type.lookup_templates.get(str(key))
                    if template and str(value).strip():
                        lookup_key = str(key)
                        lookup_value = str(value).strip()
                        entity_ref = template.replace("{value}", lookup_value)
                        break
            if not entity_ref:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "ontology_subject_unresolved",
                        "entity_type": entity_type.entity_type_id,
                        "supported_lookup_keys": sorted(entity_type.lookup_templates),
                    },
                )
            resolved_subjects.append(
                {
                    "entity_ref": entity_ref,
                    "entity_type": entity_type.entity_type_id,
                    "lookup_key": lookup_key,
                    "lookup_value": lookup_value,
                }
            )

        requested_fields = list(dict.fromkeys(str(item) for item in request.projection if str(item)))
        public_projection_fields = {"public_usage_summary"}
        if (
            recipe.admin_only
            and not analytics_enabled
            and not set(requested_fields).issubset(public_projection_fields)
        ):
            raise HTTPException(status_code=403, detail="이 사람·조직 분석은 Admin 전용입니다.")
        private_fields = set(
            (self.ontology_registry.document.acl_policy or {}).get(
                "private_projection_fields", []
            )
        )
        if private_fields.intersection(requested_fields) and not analytics_enabled:
            owns_all_subjects = all(
                item["entity_type"] != "person"
                or item["entity_ref"] == f"person:{principal.employee_id}"
                for item in resolved_subjects
            )
            if not owns_all_subjects:
                # Do not reveal whether a private node, path, or count exists.
                raise HTTPException(status_code=404, detail="Ontology 대상을 찾을 수 없습니다.")

        output_fields = recipe.output_fields
        if not output_fields:
            output_fields = {
                section_id: [
                    {
                        "projection_id": recipe.projection_id,
                        "section_id": section_id,
                        "node_types": [],
                        "id_field": "",
                    }
                ]
                for section_id in recipe.sections
            }
        available_fields = set(output_fields)
        selected_fields = requested_fields or list(output_fields)
        unknown_fields = set(selected_fields) - available_fields
        if unknown_fields:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "ontology_projection_field_unknown",
                    "fields": sorted(unknown_fields),
                    "available_fields": sorted(available_fields),
                },
            )

        as_of = request.as_of
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", as_of):
            as_of = f"{as_of}T23:59:59.999999+00:00"
        projection_rows: dict[str, list[dict[str, Any]]] = {
            field: [] for field in selected_fields
        }
        subject_payloads: list[dict[str, Any]] = []
        provenance_refs: set[str] = {
            item["entity_ref"] for item in resolved_subjects
        }
        projection_cache: dict[tuple[str, str, str], dict[str, Any]] = {}
        provenance_priority = {
            value: len(self.ontology_registry.document.provenance_priority) - index
            for index, value in enumerate(
                self.ontology_registry.document.provenance_priority
            )
        }

        for subject in resolved_subjects:
            subject_ref = subject["entity_ref"]
            for field in selected_fields:
                raw_sources = output_fields[field]
                for raw_source in raw_sources:
                    source = (
                        raw_source.model_dump(mode="json")
                        if hasattr(raw_source, "model_dump")
                        else dict(raw_source)
                    )
                    projection_id = str(source.get("projection_id") or recipe.projection_id)
                    section_id = str(source.get("section_id") or "")
                    cache_key = (projection_id, subject_ref, section_id)
                    if cache_key not in projection_cache:
                        projection_cache[cache_key] = self.project(
                            principal,
                            projection_id=projection_id,
                            subject_ref=subject_ref,
                            as_of=as_of,
                            limit=request.limit,
                            section_ids={section_id} if section_id else None,
                        )
                    projected = projection_cache[cache_key]
                    if not any(
                        item.get("entity_ref") == subject_ref
                        for item in subject_payloads
                    ):
                        subject_node = projected.get("subject") or {}
                        payload = (
                            dict(subject_node.get("payload") or {})
                            if isinstance(subject_node.get("payload"), dict)
                            else {}
                        )
                        for hidden_key in ("owner", "allowed_employee_ids", "allowed_team_ids"):
                            payload.pop(hidden_key, None)
                        subject_payloads.append(
                            {
                                **payload,
                                "entity_ref": subject_ref,
                                "entity_type": str(subject_node.get("node_type") or subject["entity_type"]),
                            }
                        )
                    section = (projected.get("sections") or {}).get(
                        section_id,
                        {},
                    )
                    allowed_node_types = set(source.get("node_types") or [])
                    depth_by_ref = {
                        str(key): int(value)
                        for key, value in (projected.get("depth_by_ref") or {}).items()
                        if str(key) and isinstance(value, int)
                    }
                    section_edges = [
                        item for item in section.get("edges") or [] if isinstance(item, dict)
                    ]
                    section_nodes = [
                        node
                        for node in section.get("nodes") or []
                        if isinstance(node, dict)
                    ]
                    subject_node = (
                        projected.get("subject")
                        if isinstance(projected.get("subject"), dict)
                        else {}
                    )
                    subject_node_type = str(
                        subject_node.get("node_type") or subject["entity_type"]
                    )
                    max_depth_by_subject_type = source.get(
                        "max_depth_by_subject_type"
                    )
                    if isinstance(max_depth_by_subject_type, dict):
                        configured_max_depth = max_depth_by_subject_type.get(
                            subject_node_type
                        )
                        if isinstance(configured_max_depth, int):
                            section_nodes = [
                                node
                                for node in section_nodes
                                if depth_by_ref.get(
                                    str(node.get("node_id") or ""), 10_000
                                )
                                <= configured_max_depth
                            ]
                    if source.get("nearest_only"):
                        nearest_depth_by_type: dict[str, int] = {}
                        for node in section_nodes:
                            node_ref = str(node.get("node_id") or "")
                            node_type = str(node.get("node_type") or "")
                            if not node_ref or (
                                allowed_node_types and node_type not in allowed_node_types
                            ):
                                continue
                            depth = depth_by_ref.get(node_ref, 10_000)
                            nearest_depth_by_type[node_type] = min(
                                depth,
                                nearest_depth_by_type.get(node_type, depth),
                            )
                        section_nodes = [
                            node
                            for node in section_nodes
                            if depth_by_ref.get(str(node.get("node_id") or ""), 10_000)
                            == nearest_depth_by_type.get(
                                str(node.get("node_type") or ""),
                                -1,
                            )
                        ]
                    section_nodes.sort(
                        key=lambda node: (
                            depth_by_ref.get(str(node.get("node_id") or ""), 10_000),
                            str(node.get("node_type") or ""),
                            str(node.get("node_id") or ""),
                        )
                    )
                    for node in section_nodes:
                        node_ref = str(node.get("node_id") or "")
                        node_type = str(node.get("node_type") or "")
                        if not node_ref or (allowed_node_types and node_type not in allowed_node_types):
                            continue
                        related_edges = [
                            edge
                            for edge in section_edges
                            if node_ref
                            in {
                                str(edge.get("source_id") or ""),
                                str(edge.get("target_id") or ""),
                            }
                        ]
                        node_depth = depth_by_ref.get(node_ref, 10_000)

                        def edge_rank(edge: dict[str, Any]) -> tuple[int, int, str]:
                            source_ref = str(edge.get("source_id") or "")
                            target_ref = str(edge.get("target_id") or "")
                            other_ref = target_ref if source_ref == node_ref else source_ref
                            predecessor = int(
                                depth_by_ref.get(other_ref, 10_000) == node_depth - 1
                            )
                            edge_payload = (
                                edge.get("payload")
                                if isinstance(edge.get("payload"), dict)
                                else {}
                            )
                            provenance = str(
                                edge_payload.get("evidence_provenance")
                                or edge_payload.get("provenance")
                                or ""
                            )
                            return (
                                predecessor,
                                provenance_priority.get(provenance, 0),
                                str(edge.get("edge_id") or ""),
                            )

                        related_edges.sort(key=edge_rank, reverse=True)
                        edge = related_edges[0] if related_edges else {}
                        edge_payload = edge.get("payload") if isinstance(edge.get("payload"), dict) else {}
                        payload = (
                            dict(node.get("payload") or {})
                            if isinstance(node.get("payload"), dict)
                            else {}
                        )
                        for hidden_key in ("owner", "allowed_employee_ids", "allowed_team_ids"):
                            payload.pop(hidden_key, None)
                        row = {
                            **payload,
                            "entity_ref": node_ref,
                            "entity_type": node_type,
                            "relation": str(edge.get("relation") or ""),
                            "provenance": str(
                                edge_payload.get("evidence_provenance")
                                or edge_payload.get("provenance")
                                or ""
                            ),
                        }
                        id_field = str(source.get("id_field") or "")
                        if id_field:
                            row[id_field] = node_ref
                        source_refs = [
                            str(item)
                            for item in [
                                edge_payload.get("source_ref"),
                                *(edge_payload.get("source_refs") or []),
                            ]
                            if item is not None and str(item).strip()
                        ]
                        row["source_refs"] = list(dict.fromkeys(source_refs))
                        provenance_refs.update(source_refs)
                        fingerprint = (
                            node_ref,
                            row["relation"],
                            row["provenance"],
                        )
                        if not any(
                            (
                                item.get("entity_ref"),
                                item.get("relation"),
                                item.get("provenance"),
                            )
                            == fingerprint
                            for item in projection_rows[field]
                        ):
                            projection_rows[field].append(row)

        return {
            "status": "completed",
            "recipe": recipe.projection_id,
            "schema_revision": self.ontology_registry.schema_revision,
            "schema_checksum": self.ontology_registry.checksum,
            "subjects": subject_payloads,
            "projections": projection_rows,
            "provenance_refs": sorted(provenance_refs),
            "as_of": request.as_of,
            "acl_applied_before_traversal": True,
            "policy": {
                "analytics_enabled": analytics_enabled,
                "acl_applied_before_traversal": True,
                "usage_is_not_expertise_or_authority": True,
            },
        }

    def query(
        self,
        principal: Principal,
        plan: GraphQueryPlan,
        *,
        _projection_relation_scope: set[str] | None = None,
    ) -> dict[str, Any]:
        try:
            recipe = self.ontology_registry.query_recipe(
                query_kind=plan.query_kind,
                recipe_id=plan.recipe_id,
            )
        except KeyError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if recipe.admin_only and not self._people_analytics_enabled(principal):
            raise HTTPException(status_code=403, detail="이 Ontology 분석은 Admin 전용입니다.")
        read_model_state = self.graph_snapshot_state(principal)
        manifest = self.store.get("manifests", "knowledge_graph") or {}
        projection_relation_scope = set(_projection_relation_scope or set())
        cache_payload = {
            "employee_id": principal.employee_id,
            "teams": sorted(principal.teams),
            "is_admin": principal.is_admin,
            "people_analytics_enabled": self._people_analytics_enabled(principal),
            "source_signature": manifest.get("source_signature") or "",
            "current_source_signature": read_model_state["current_source_signature"],
            "runtime_relation_signature": manifest.get("runtime_relation_signature") or "",
            "directory_signature": manifest.get("directory_signature") or "",
            "current_directory_signature": read_model_state[
                "current_directory_signature"
            ],
            "compiler_version": manifest.get("compiler_version") or "",
            "ontology_schema_revision": self.ontology_registry.schema_revision,
            "ontology_schema_checksum": self.ontology_registry.checksum,
            "read_model_status": read_model_state["status"],
            "read_model_reasons": read_model_state["degraded_reasons"],
            "query_recipe": recipe.model_dump(mode="json"),
            "plan": plan.model_dump(mode="json"),
            "projection_relation_scope": sorted(projection_relation_scope),
        }
        cache_id = _stable_id(
            "graph-query",
            json.dumps(cache_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        cached = self.store.get("knowledge_graph_queries", cache_id) or {}
        if isinstance(cached.get("result"), dict):
            return json.loads(json.dumps(cached["result"], ensure_ascii=False))

        def cache_result(result: dict[str, Any]) -> dict[str, Any]:
            result = {
                **result,
                "read_model_state": read_model_state,
                "degraded": (
                    []
                    if read_model_state["status"] == "ready"
                    else [f"knowledge_graph_{read_model_state['status']}"]
                ),
            }
            self.store.put(
                "knowledge_graph_queries",
                cache_id,
                {
                    "cache_id": cache_id,
                    "employee_id": principal.employee_id,
                    "context_fingerprint": hashlib.sha256(
                        json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    ).hexdigest(),
                    "result": result,
                    "created_at": now_iso(),
                },
            )
            return result

        if not read_model_state["compatible"]:
            return cache_result(
                {
                    "ok": False,
                    "meaningful": False,
                    "status": "unavailable",
                    "stop_reason": "knowledge_graph_unavailable",
                    "empty_reason": (
                        "호환되는 Knowledge Graph snapshot이 없습니다. "
                        "명시적 동기화가 끝난 뒤 다시 확인해주세요."
                    ),
                    "query_plan": plan.model_dump(mode="json"),
                    "query_recipe": recipe.model_dump(mode="json"),
                    "ontology_schema_revision": self.ontology_registry.schema_revision,
                    "ontology_schema_checksum": self.ontology_registry.checksum,
                    "presentation": (
                        recipe.auto_presentation
                        if plan.presentation == "auto"
                        else plan.presentation
                    ),
                    "nodes": [],
                    "edges": [],
                }
            )

        recipe_relations = set(recipe.relation_types)
        requested_relations = set(plan.relation_kinds)
        if projection_relation_scope:
            undeclared_projection_relations = (
                requested_relations - projection_relation_scope
            )
            if undeclared_projection_relations:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "ontology_relation_outside_projection",
                        "relations": sorted(undeclared_projection_relations),
                    },
                )
        if requested_relations and recipe_relations:
            # Projection recipes are a separate, versioned ontology contract.
            # They may declare bridge relations that are required to reach a
            # section but must not broaden the corresponding public query
            # recipe. Only project() supplies this trusted registry scope.
            disallowed = requested_relations - (
                recipe_relations | projection_relation_scope
            )
            if disallowed:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "ontology_relation_outside_recipe",
                        "recipe_id": recipe.recipe_id,
                        "relations": sorted(disallowed),
                    },
                )
        allowed_for_use = self.ontology_registry.relation_ids_for_evidence_use(
            plan.evidence_use
        )
        # An empty recipe relation list is the Catalog contract for a generic
        # graph query (neighbors/path/compare/timeline): traverse every
        # relation allowed for the requested evidence use, then apply the
        # recipe exclusions. It must not compile to an empty allowlist.
        allowed_relations = (
            set(requested_relations)
            if requested_relations
            else set(recipe_relations)
            if recipe_relations
            else set(allowed_for_use)
        )
        allowed_relations &= allowed_for_use
        allowed_relations -= set(recipe.excluded_relation_types)
        graph = self.store.ontology_neighbors(
            plan.focal_entities,
            # Query recipes own traversal depth. Fetching a broader raw
            # neighborhood first can exhaust the bounded edge window around
            # one noisy focal entity before another focal entity (for example
            # a Person in a combined current-work/responsibility query) is
            # visited at all.
            depth=min(plan.depth, recipe.max_depth),
            limit=plan.limit,
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=self._people_analytics_enabled(principal),
            relation_kinds=sorted(allowed_relations),
        )
        nodes = list({str(item.get("node_id") or ""): item for item in graph.get("nodes") or [] if str(item.get("node_id") or "")}.values())
        edges = _dedupe_semantic_edges(
            graph.get("edges") or [],
            ontology_registry=self.ontology_registry,
        )
        time_from = _parse_time(plan.time_from)
        time_to = _parse_time(plan.time_to)
        if time_from or time_to:
            def item_time(item: dict[str, Any]) -> datetime | None:
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                raw = next(
                    (payload.get(key) for key in ("observed_at", "logged_at", "timestamp", "valid_from", "recorded_at") if payload.get(key)),
                    "",
                )
                return _parse_time(str(raw or ""))

            def in_time_range(item: dict[str, Any]) -> bool:
                timestamp = item_time(item)
                if not timestamp:
                    return False
                return (not time_from or timestamp >= time_from) and (not time_to or timestamp <= time_to)

            nodes = [item for item in nodes if in_time_range(item)]
            visible_ids = {str(item.get("node_id") or "") for item in nodes}
            edges = [
                item for item in edges
                if str(item.get("source_id") or "") in visible_ids
                and str(item.get("target_id") or "") in visible_ids
                and (not item_time(item) or in_time_range(item))
            ]
        if plan.node_kinds:
            allowed_node_kinds = set(plan.node_kinds)
            nodes = [item for item in nodes if str(item.get("node_type") or "") in allowed_node_kinds]
            visible_ids = {str(item.get("node_id") or "") for item in nodes} | set(plan.focal_entities)
            edges = [item for item in edges if str(item.get("source_id") or "") in visible_ids and str(item.get("target_id") or "") in visible_ids]
        if allowed_relations:
            edges = [
                item
                for item in edges
                if str(item.get("relation") or "") in allowed_relations
            ]
        else:
            edges = []

        provenance_aliases = {
            "declared": "canonical_declared",
            "extracted": "deterministic_extracted",
        }

        def normalized_provenance(item: dict[str, Any]) -> str:
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            raw = str(
                payload.get("evidence_provenance")
                or payload.get("provenance")
                or ""
            )
            return provenance_aliases.get(raw, raw)

        requested_provenance = {
            provenance_aliases.get(str(item), str(item))
            for item in plan.provenance
            if str(item)
        }
        if requested_provenance:
            edges = [
                item for item in edges if normalized_provenance(item) in requested_provenance
            ]
        denied_provenance = set(
            (self.ontology_registry.document.acl_policy or {}).get(
                "inferred_evidence_denied_for", []
            )
        )
        if plan.evidence_use in denied_provenance:
            edges = [
                item
                for item in edges
                if normalized_provenance(item)
                not in {"inferred", "ambiguous", "private_provisional"}
            ]

        as_of = _parse_time(plan.as_of)
        if plan.as_of and as_of is None:
            raise HTTPException(status_code=422, detail="as_of는 ISO-8601 형식이어야 합니다.")
        if as_of is not None:
            def valid_as_of(item: dict[str, Any]) -> bool:
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
                valid_from = _parse_time(str(payload.get("valid_from") or metadata.get("valid_from") or ""))
                valid_to = _parse_time(str(payload.get("valid_to") or metadata.get("valid_to") or ""))
                tombstoned_at = _parse_time(
                    str(payload.get("tombstoned_at") or metadata.get("tombstoned_at") or "")
                )
                observed = _parse_time(
                    str(
                        payload.get("observed_at")
                        or payload.get("recorded_at")
                        or metadata.get("observed_at")
                        or metadata.get("recorded_at")
                        or ""
                    )
                )
                return bool(
                    (valid_from is None or valid_from <= as_of)
                    and (valid_to is None or as_of < valid_to)
                    and (observed is None or observed <= as_of)
                    and (tombstoned_at is None or as_of < tombstoned_at)
                )

            nodes = [item for item in nodes if valid_as_of(item)]
            visible_as_of = {str(item.get("node_id") or "") for item in nodes}
            edges = [
                item
                for item in edges
                if str(item.get("source_id") or "") in visible_as_of
                and str(item.get("target_id") or "") in visible_as_of
                and valid_as_of(item)
            ]
        focal = set(plan.focal_entities)
        node_lookup = {str(item.get("node_id") or ""): item for item in nodes}

        def adjacent(edge: dict[str, Any], current: str, direction: str) -> str:
            source = str(edge.get("source_id") or "")
            target = str(edge.get("target_id") or "")
            if direction in {"outgoing", "both"} and source == current:
                return target
            if direction in {"incoming", "both"} and target == current:
                return source
            return ""

        def traverse(
            seeds: set[str],
            candidate_edges: list[dict[str, Any]],
            *,
            direction: str,
            max_depth: int,
        ) -> tuple[set[str], list[dict[str, Any]], dict[str, int]]:
            reached = set(seeds)
            depth_by_ref = {item: 0 for item in seeds}
            queue = deque(seeds)
            while queue and len(reached) < plan.limit:
                current = queue.popleft()
                current_depth = depth_by_ref[current]
                if current_depth >= max_depth:
                    continue
                for edge in candidate_edges:
                    neighbor = adjacent(edge, current, direction)
                    if not neighbor or neighbor in reached:
                        continue
                    reached.add(neighbor)
                    depth_by_ref[neighbor] = current_depth + 1
                    queue.append(neighbor)
                    if len(reached) >= plan.limit:
                        break
            selected: list[dict[str, Any]] = []
            for edge in candidate_edges:
                source = str(edge.get("source_id") or "")
                target = str(edge.get("target_id") or "")
                if source not in reached or target not in reached:
                    continue
                outgoing_visible = (
                    direction in {"outgoing", "both"}
                    and depth_by_ref.get(source, max_depth) < max_depth
                )
                incoming_visible = (
                    direction in {"incoming", "both"}
                    and depth_by_ref.get(target, max_depth) < max_depth
                )
                if outgoing_visible or incoming_visible:
                    selected.append(edge)
            return reached, selected, depth_by_ref

        traversal_direction = plan.direction
        if (
            traversal_direction == "both"
            and recipe.default_direction != "both"
            and not projection_relation_scope
        ):
            traversal_direction = recipe.default_direction
        traversal_depth = min(plan.depth, recipe.max_depth)

        if recipe.operator == "path":
            if recipe.requires_target and not plan.target_entities:
                raise HTTPException(status_code=422, detail="연결 경로의 도착 지식을 선택해주세요.")
            target = plan.target_entities[0]
            queue = deque([(plan.focal_entities[0], [plan.focal_entities[0]], [])])
            visited = {plan.focal_entities[0]}
            found_nodes: list[str] = []
            found_edges: list[dict[str, Any]] = []
            while queue:
                current, path_nodes, path_edges = queue.popleft()
                if current == target:
                    found_nodes, found_edges = path_nodes, path_edges
                    break
                if len(path_edges) >= traversal_depth:
                    continue
                for edge in edges:
                    neighbor = adjacent(edge, current, plan.direction)
                    if not neighbor or neighbor in visited:
                        continue
                    visited.add(neighbor)
                    queue.append((neighbor, [*path_nodes, neighbor], [*path_edges, edge]))
            return cache_result(_decorate_graph_result({
                "ok": True,
                "query_plan": plan.model_dump(mode="json"),
                "presentation": (
                    recipe.auto_presentation
                    if plan.presentation == "auto"
                    else plan.presentation
                ),
                "status": "connected" if found_nodes else "not_connected",
                "path_refs": found_nodes,
                "nodes": [node_lookup[item] for item in found_nodes if item in node_lookup],
                "edges": found_edges,
                "provenance_required": True,
            }, recipe=recipe, ontology_registry=self.ontology_registry))

        depth_by_ref: dict[str, int] = {item: 0 for item in focal}
        semantic_refs: list[str] = []
        if recipe.operator == "traverse":
            visible_ids, edges, depth_by_ref = traverse(
                focal,
                edges,
                direction=traversal_direction,
                max_depth=traversal_depth,
            )
            nodes = [item for item in nodes if str(item.get("node_id") or "") in visible_ids]
            semantic_refs = sorted(visible_ids - focal)

        groups: dict[str, Any] = {}
        comparison: dict[str, Any] = {}
        if recipe.operator == "compare":
            groups = {}
            relation_sets: dict[str, set[str]] = {}
            neighbor_sets: dict[str, set[str]] = {}
            for entity in plan.focal_entities:
                entity_edges = [
                    item for item in edges
                    if adjacent(item, entity, plan.direction)
                ]
                neighbor_refs = {adjacent(item, entity, plan.direction) for item in entity_edges}
                neighbor_refs.discard("")
                relation_sets[entity] = {str(item.get("relation") or "") for item in entity_edges}
                neighbor_sets[entity] = neighbor_refs
                groups[entity] = {
                    "nodes": [node_lookup[item] for item in {entity, *neighbor_refs} if item in node_lookup],
                    "edges": entity_edges,
                }
            common_relations = set.intersection(*relation_sets.values()) if relation_sets else set()
            common_neighbors = set.intersection(*neighbor_sets.values()) if neighbor_sets else set()
            comparison = {
                "common_relations": sorted(common_relations),
                "common_node_refs": sorted(common_neighbors),
                "unique_relations": {
                    entity: sorted(values - common_relations) for entity, values in relation_sets.items()
                },
                "unique_node_refs": {
                    entity: sorted(values - common_neighbors) for entity, values in neighbor_sets.items()
                },
            }

        timeline: list[dict[str, Any]] = []
        if recipe.operator == "timeline":
            for item in nodes:
                payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
                occurred_at = next(
                    (str(payload.get(key) or "") for key in ("observed_at", "logged_at", "timestamp", "recorded_at", "valid_from") if payload.get(key)),
                    "",
                )
                if occurred_at:
                    timeline.append(
                        {
                            "occurred_at": occurred_at,
                            "node_ref": str(item.get("node_id") or ""),
                            "node_type": str(item.get("node_type") or ""),
                            "title": str(payload.get("title") or "연결된 업무 기록"),
                        }
                    )
            timeline.sort(key=lambda item: item["occurred_at"])

        tour_steps: list[dict[str, Any]] = []
        if recipe.operator == "tour":
            visible_ids, selected_edges, depth_by_ref = traverse(
                focal,
                edges,
                direction=traversal_direction,
                max_depth=traversal_depth,
            )
            priority = {"sop": 1, "workflow": 2, "task": 3, "event": 4, "action": 5, "evidence": 6, "boi": 7}
            ordered_refs = sorted(
                visible_ids,
                key=lambda ref: (
                    depth_by_ref.get(ref, 99),
                    priority.get(str((node_lookup.get(ref) or {}).get("node_type") or ""), 50),
                    str(((node_lookup.get(ref) or {}).get("payload") or {}).get("title") or ref),
                ),
            )
            nodes = [node_lookup[item] for item in ordered_refs if item in node_lookup]
            edges = selected_edges
            tour_steps = [
                {
                    "order": index + 1,
                    "node_ref": ref,
                    "title": str(((node_lookup.get(ref) or {}).get("payload") or {}).get("title") or "살펴볼 항목"),
                    "reason": "먼저 이해해야 할 관계" if depth_by_ref.get(ref, 0) == 0 else "앞 단계와 직접 연결된 항목",
                }
                for index, ref in enumerate(ordered_refs)
            ]
        presentation = plan.presentation
        if presentation == "auto":
            presentation = recipe.auto_presentation
            if len(nodes) > 20 and presentation not in {"timeline", "table"}:
                presentation = "explorer"
            elif presentation == "explorer" and len(nodes) <= 20:
                presentation = recipe.compact_presentation
        result_payload = {
            "ok": True,
            "query_plan": plan.model_dump(mode="json"),
            "query_recipe": recipe.model_dump(mode="json"),
            "ontology_schema_revision": self.ontology_registry.schema_revision,
            "ontology_schema_checksum": self.ontology_registry.checksum,
            "presentation": presentation,
            "nodes": nodes,
            "edges": edges,
            "groups": groups,
            "comparison": comparison,
            "timeline": timeline,
            "tour_steps": tour_steps,
            "depth_by_ref": depth_by_ref,
            "provenance_required": True,
            "relation_groups": {
                group: [
                    item
                    for item in edges
                    if str(item.get("relation") or "") in set(relations)
                ]
                for group, relations in recipe.relation_groups.items()
            },
        }
        if recipe.output_ref_field:
            result_payload[recipe.output_ref_field] = semantic_refs
        return cache_result(
            _decorate_graph_result(
                result_payload,
                recipe=recipe,
                ontology_registry=self.ontology_registry,
            )
        )

    def health(self, principal: Principal, *, refresh: bool = False) -> dict[str, Any]:
        existing = self.store.list("knowledge_health_findings", employee_id=principal.employee_id, limit=1000)
        if existing and not refresh:
            return {"count": len(existing), "items": existing, "refreshed": False}
        for item in existing:
            self.store.delete("knowledge_health_findings", str(item.get("finding_id") or ""))
        records = self.repository.authoritative_records(principal, include_drafts=False)
        health_records = [
            record
            for record in records
            if record.kind != "case" and record.source not in {"runtime", "history_seed"}
        ]
        graph = self.compile_graph(principal)
        graph_edges: list[dict[str, Any]] = []
        for offset in range(0, len(records), 100):
            graph_data = self.store.ontology_neighbors(
                [item.record_id for item in records[offset : offset + 100]],
                depth=1,
                limit=5000,
                employee_id=principal.employee_id,
                team_ids=principal.teams,
                include_all=principal.is_admin,
            )
            graph_edges.extend(graph_data.get("edges") or [])
        connected = {
            str(edge.get("source_id") or "")
            for edge in graph_edges
        } | {
            str(edge.get("target_id") or "")
            for edge in graph_edges
        }
        findings: list[dict[str, Any]] = []

        def add(kind: str, severity: str, title: str, refs: list[str], summary: str, proposal_kind: str) -> None:
            # Health findings are principal-scoped records.  The same canonical
            # source can legitimately be scanned by a user and by a scheduled
            # service principal; sharing a deterministic key would let the
            # later scan overwrite ownership and ACL metadata of the former.
            finding_id = _stable_id("finding", principal.employee_id, kind, *sorted(refs))
            finding = {
                "finding_id": finding_id,
                "employee_id": principal.employee_id,
                "kind": kind,
                "severity": severity,
                "title": title,
                "summary": summary,
                "source_refs": refs,
                "status": "open",
                "graph_revision": graph["source_signature"],
                "created_at": now_iso(),
            }
            findings.append(self.store.put("knowledge_health_findings", finding_id, finding))
            proposal_id = _stable_id("proposal", finding_id, proposal_kind)
            visibility = next((item.visibility for item in health_records if item.record_id in refs), "private")
            proposal = KnowledgePatchProposal(
                proposal_id=proposal_id,
                finding_id=finding_id,
                kind=proposal_kind,  # type: ignore[arg-type]
                title=title,
                summary=summary,
                target_refs=refs,
                source_refs=refs,
                diff={"before": "현재 상태", "after": "검토 후 반영할 후보"},
                deterministic=proposal_kind in {"reindex", "remove_stale_edge"},
                visibility=visibility if visibility in {"private", "team", "public"} else "private",  # type: ignore[arg-type]
            )
            self.store.put(
                "knowledge_patch_proposals",
                proposal_id,
                {**proposal.model_dump(mode="json"), "employee_id": principal.employee_id, "created_at": now_iso()},
            )

        known_document_urls = {
            unquote(urlsplit(record.url).path).rstrip("/")
            for record in health_records
            if record.url
        }
        known_markdown_paths = {
            "/" + str(record.metadata.get("relative_path") or "").lstrip("/")
            for record in health_records
            if record.metadata.get("relative_path")
        }
        by_title: dict[str, list[KnowledgeRecord]] = {}
        for record in health_records:
            by_title.setdefault(re.sub(r"\s+", " ", record.title.casefold()).strip(), []).append(record)
            timestamp = _parse_time(record.timestamp)
            if timestamp and (datetime.now(timezone.utc) - timestamp).days > 365 and not record.metadata.get("valid_to"):
                add("stale", "info", f"오래 확인되지 않은 지식: {record.title}", [record.record_id], "최신 상태를 확인할 후보입니다.", "add_coverage")
            if record.record_id not in connected and record.kind not in {"data_artifact"}:
                add("orphan", "info", f"연결이 없는 지식: {record.title}", [record.record_id], "관련 업무 또는 근거 연결을 검토할 후보입니다.", "add_coverage")
            for href in MARKDOWN_LINK.findall(record.text):
                if href.startswith(("http://", "https://", "#")):
                    continue
                href_path = unquote(urlsplit(href).path).rstrip("/")
                if href_path.startswith("/api/"):
                    continue
                target_known = href_path in known_document_urls or href_path in known_markdown_paths
                if href_path.startswith(("/public/", "/team/", "/private/")) and not href_path.endswith(".md"):
                    target_known = target_known or f"{href_path}.md" in known_markdown_paths
                if not target_known and href_path.startswith(("/docs/", "/public/", "/team/", "/private/")):
                    add("broken_link", "warning", f"열리지 않는 연결: {record.title}", [record.record_id], f"연결 대상 '{href}'를 확인해야 합니다.", "repair_link")
        for duplicates in by_title.values():
            if len(duplicates) > 1:
                add("duplicate", "warning", f"비슷한 제목의 지식 {len(duplicates)}개", [item.record_id for item in duplicates[:10]], "새 문서를 만들기보다 기존 지식 보강 여부를 검토해야 합니다.", "merge_duplicate")
            claims = {
                str(item.metadata.get("claim_value") or "")
                for item in duplicates
                if item.metadata.get("claim_key") and item.metadata.get("claim_value")
            }
            if len(claims) > 1:
                add("contradiction", "error", "서로 다른 판단이 있는 지식", [item.record_id for item in duplicates[:10]], "유효 기간과 근거를 비교해 어떤 판단을 유지할지 검토해야 합니다.", "resolve_contradiction")
        for source in self.store.list(
            "knowledge_sources",
            employee_id=principal.employee_id,
            limit=10_000,
        ):
            source_id = str(source.get("source_id") or "").strip()
            if not source_id or str(source.get("status") or "") in {
                "removed",
                "deleted",
                "tombstoned",
            }:
                continue
            verified_at = _parse_time(
                str(
                    source.get("last_verified_at")
                    or source.get("last_sync_at")
                    or ""
                )
            )
            if verified_at and (datetime.now(timezone.utc) - verified_at).days > 365:
                add(
                    "stale",
                    "info",
                    f"오래 검증되지 않은 Source: {source.get('title') or source_id}",
                    [source_id],
                    "Source의 최신성, 유효 기간과 원천 상태를 사람이 확인해야 합니다.",
                    "add_coverage",
                )
        for candidate in self.store.list(
            "knowledge_candidates",
            employee_id=principal.employee_id,
            limit=10_000,
        ):
            if str(candidate.get("status") or "") in {
                "archived",
                "rejected",
                "expired",
            }:
                continue
            candidate_id = str(candidate.get("candidate_id") or "").strip()
            source_work_run_id = str(candidate.get("source_work_run_id") or "").strip()
            if candidate_id and (
                not source_work_run_id
                or self.store.get("work_runs", source_work_run_id) is None
            ):
                add(
                    "orphan",
                    "warning",
                    f"출처 WorkRun이 없는 지식 후보: {candidate.get('title') or candidate_id}",
                    [candidate_id],
                    "검증된 WorkRun, Evidence Ledger 또는 원천 지식과의 lineage를 보완해야 합니다.",
                    "add_coverage",
                )
        return {"count": len(findings), "items": findings, "refreshed": True, "graph": graph}

    def scan_health(
        self,
        principal: Principal,
        request: KnowledgeHealthScanRequest,
    ) -> dict[str, Any]:
        """Compare one owned candidate with explicit ACL-visible sources.

        The scan is deterministic and typed: it compares predicate/value pairs
        already verified by their source ledgers.  It never asks a model to
        reinterpret prose and it does not change canonical knowledge.
        """

        candidate = self.store.get("knowledge_candidates", request.candidate_id)
        if (
            not candidate
            or str(candidate.get("employee_id") or "") != principal.employee_id
            or str(candidate.get("visibility") or "private") != "private"
        ):
            raise HTTPException(status_code=404, detail="knowledge candidate not found")
        candidate_claims = [
            dict(item)
            for item in candidate.get("claims") or []
            if isinstance(item, dict)
            and item.get("support_status") == "supported"
            and item.get("verification") == "verified"
        ]
        findings: list[dict[str, Any]] = []
        scanned_refs: list[str] = []
        for source_ref in dict.fromkeys(str(item).strip() for item in request.source_refs):
            if not source_ref:
                continue
            source = self.store.get("knowledge_sources", source_ref)
            if not source:
                continue
            owner = str(source.get("employee_id") or "")
            visibility = str(source.get("visibility") or "private")
            if visibility == "private" and owner != principal.employee_id:
                continue
            scanned_refs.append(source_ref)
            source_claims = [
                dict(item)
                for item in source.get("claims") or []
                if isinstance(item, dict)
                and item.get("support_status") == "supported"
                and item.get("verification") == "verified"
            ]
            for candidate_claim in candidate_claims:
                predicate = str(candidate_claim.get("predicate") or "").strip()
                candidate_value = str(candidate_claim.get("value") or "").strip().casefold()
                if not predicate or not candidate_value:
                    continue
                for source_claim in source_claims:
                    if str(source_claim.get("predicate") or "").strip() != predicate:
                        continue
                    source_value = str(source_claim.get("value") or "").strip().casefold()
                    if not source_value or source_value == candidate_value:
                        continue
                    finding_id = _stable_id(
                        "finding",
                        "contradiction",
                        request.candidate_id,
                        source_ref,
                        predicate,
                    )
                    finding = {
                        "finding_id": finding_id,
                        "employee_id": principal.employee_id,
                        "kind": "contradiction",
                        "severity": "error",
                        "title": "검증된 판단이 서로 상충합니다.",
                        "summary": (
                            f"{predicate}에 대해 candidate와 비교 source의 값이 다릅니다. "
                            "어느 판단을 유지할지 사람 검토가 필요합니다."
                        ),
                        "source_refs": [request.candidate_id, source_ref],
                        "status": "open",
                        "comparison": {
                            "predicate": predicate,
                            "candidate_value": candidate_claim.get("value"),
                            "source_value": source_claim.get("value"),
                            "candidate_claim_id": candidate_claim.get("claim_id"),
                            "source_claim_id": source_claim.get("claim_id"),
                        },
                        "canonical_changed": False,
                        "created_at": now_iso(),
                    }
                    findings.append(
                        self.store.put(
                            "knowledge_health_findings",
                            finding_id,
                            finding,
                        )
                    )
        return {
            "count": len(findings),
            "findings": findings,
            "candidate_id": request.candidate_id,
            "scanned_source_refs": scanned_refs,
            "canonical_changed": False,
        }

    def proposals(self, principal: Principal, *, status: str = "") -> dict[str, Any]:
        items = self.store.list("knowledge_patch_proposals", employee_id=principal.employee_id, limit=1000)
        if status:
            items = [item for item in items if str(item.get("status") or "") == status]
        return {"count": len(items), "items": items}

    def apply_proposal(
        self,
        principal: Principal,
        proposal_id: str,
        request: KnowledgeProposalApplyRequest,
    ) -> dict[str, Any]:
        proposal = self.store.get("knowledge_patch_proposals", proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="지식 개선 후보를 찾을 수 없습니다.")
        if str(proposal.get("employee_id") or "") != principal.employee_id and not principal.is_admin:
            raise HTTPException(status_code=403, detail="이 지식 개선 후보를 적용할 수 없습니다.")
        if int(proposal.get("revision") or 1) != request.expected_revision:
            raise HTTPException(status_code=409, detail={"status": "revision_conflict", "proposal": proposal})
        deterministic = bool(proposal.get("deterministic"))
        visibility = str(proposal.get("visibility") or "private")
        if not deterministic or visibility in {"team", "public"}:
            proposal.update(
                {
                    "status": "review_required",
                    "review_reason": request.reason,
                    "revision": int(proposal.get("revision") or 1) + 1,
                    "updated_at": now_iso(),
                }
            )
            self.store.put("knowledge_patch_proposals", proposal_id, proposal)
            return {"status": "review_required", "proposal": proposal, "source_of_truth_changed": False}
        graph = self.compile_graph(principal)
        proposal.update(
            {
                "status": "applied",
                "applied_at": now_iso(),
                "revision": int(proposal.get("revision") or 1) + 1,
            }
        )
        self.store.put("knowledge_patch_proposals", proposal_id, proposal)
        return {"status": "applied", "proposal": proposal, "graph": graph, "source_of_truth_changed": False}
