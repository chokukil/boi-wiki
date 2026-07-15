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
from .models import (
    GraphQueryPlan,
    KnowledgeEdge,
    KnowledgePatchProposal,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceDefinition,
    Principal,
)
from .openkb_compat import OpenKBCompatibilityGateway
from .repository import KnowledgeRecord, KnowledgeRepository
from .search import HybridSearchService, record_content_checksum
from .store import AgentV2Store, now_iso


EXTRACTOR_VERSION = "boi-knowledge-compiler/7"
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)\)")


RELATION_PRESENTATION: dict[str, tuple[str, str, int]] = {
    "part_of": ("structure", "구성 요소", 96),
    "guides": ("guidance", "업무 기준을 안내", 94),
    "uses": ("work", "업무에 활용", 90),
    "triggers": ("event", "업무를 시작", 94),
    "executes": ("work", "업무에서 실행", 94),
    "part_of_workflow": ("structure", "업무 흐름에 포함", 95),
    "has_task": ("structure", "Task로 구성", 95),
    "next_task": ("sequence", "다음 단계", 100),
    "precedes": ("sequence", "먼저 수행", 100),
    "uses_sop": ("work", "SOP를 활용", 90),
    "uses_event": ("work", "업무 이벤트를 사용", 88),
    "uses_action": ("work", "Action을 실행", 88),
    "uses_skill": ("work", "Skill을 활용", 82),
    "triggered_by": ("event", "이 이벤트로 시작", 92),
    "results_in": ("result", "이 결과로 이어짐", 92),
    "produces": ("result", "결과를 생성", 92),
    "assigned_to": ("responsibility", "현재 담당", 100),
    "reviewed_by": ("responsibility", "검토 담당", 94),
    "related_team": ("responsibility", "유관 팀", 88),
    "member_of": ("organization", "소속 팀", 96),
    "has_role": ("organization", "공식 역할", 96),
    "performed_by": ("responsibility", "수행 기록", 90),
    "completed_by": ("responsibility", "완료 기록", 94),
    "repeated_performer": ("responsibility", "반복 수행", 98),
    "requires_evidence": ("lineage", "확인 근거가 필요", 92),
    "derived_from": ("lineage", "이 근거에서 도출", 94),
    "evidence": ("lineage", "근거로 연결", 35),
    "broader": ("concept", "상위 개념", 80),
    "narrower": ("concept", "하위 개념", 80),
    "related": ("concept", "관련 개념", 65),
    "links_to": ("reference", "함께 참고", 50),
    "supersedes": ("change", "이전 내용을 대체", 86),
}

DECLARED_RELATIONS = frozenset(RELATION_PRESENTATION)

SYMMETRIC_RELATIONS = {"related", "links_to", "evidence"}


def _relation_display(relation: str) -> tuple[str, str, int]:
    return RELATION_PRESENTATION.get(relation, ("other", relation.replace("_", " "), 45))


def _decorate_edge(item: dict[str, Any]) -> dict[str, Any]:
    relation = str(item.get("relation") or "related")
    family, user_label, priority = _relation_display(relation)
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


def _decorate_graph_result(result: dict[str, Any], *, query_kind: str) -> dict[str, Any]:
    nodes = list(result.get("nodes") or [])
    edges = [_decorate_edge(item) for item in result.get("edges") or []]
    families = sorted({str(item.get("relation_family") or "other") for item in edges})
    presentation = str(result.get("presentation") or "")
    layout_hint = (
        "timeline" if query_kind == "timeline"
        else "hierarchical" if query_kind in {"path", "workflow", "lineage"}
        else "comparison" if query_kind == "compare"
        else "force"
    )
    empty_reason = ""
    if len(nodes) <= 1 and not edges:
        empty_reason = {
            "workflow": "이 항목과 직접 연결된 Workflow·Task·Event·Action 관계가 아직 없습니다.",
            "impact": "이 항목에서 이어지는 검증된 영향 관계가 아직 없습니다.",
            "responsibility": "공식 역할·현재 배정·검증된 수행 관계가 아직 없습니다.",
            "lineage": "이 항목의 근거와 결과 계보를 확인할 관계가 아직 없습니다.",
        }.get(query_kind, "조건에 맞는 검증된 관계가 아직 없습니다.")
    relation_required = query_kind in {
        "path",
        "workflow",
        "impact",
        "lineage",
        "responsibility",
        "tour",
    }
    meaningful = bool(edges) if relation_required else bool(nodes)
    if query_kind == "timeline":
        meaningful = bool(result.get("timeline"))
    elif query_kind == "compare":
        meaningful = bool(edges) and len(result.get("groups") or {}) >= 2
    result.update(
        {
            "nodes": nodes,
            "edges": edges,
            "layout_hint": layout_hint,
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


def _dedupe_semantic_edges(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provenance_rank = {
        "human_verified": 5,
        "declared": 4,
        "extracted": 3,
        "ambiguous": 2,
        "inferred": 1,
    }
    selected: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in rows:
        source_id = str(item.get("source_id") or "")
        target_id = str(item.get("target_id") or "")
        relation = str(item.get("relation") or "")
        if relation in SYMMETRIC_RELATIONS and source_id > target_id:
            source_id, target_id = target_id, source_id
        key = (source_id, relation, target_id)
        if not all(key):
            continue
        current = selected.get(key)
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        current_payload = current.get("payload") if current and isinstance(current.get("payload"), dict) else {}
        score = (
            provenance_rank.get(str(payload.get("provenance") or ""), 0),
            -int(item.get("depth") or 1),
        )
        current_score = (
            provenance_rank.get(str(current_payload.get("provenance") or ""), 0),
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
        self._adapter_lock = threading.Lock()
        self._adapter_worker_event = threading.Event()
        self._adapter_worker_stop = threading.Event()
        self._adapter_worker_thread: threading.Thread | None = None
        self._ensure_defaults()
        if self._resume_adapter_jobs():
            self._ensure_adapter_worker()

    def directory_principals(self, current: Principal) -> list[Principal]:
        rows: list[Principal] = []
        if self.directory_provider is not None:
            try:
                rows = list(self.directory_provider() or [])
            except Exception:
                rows = []
        rows.append(current)
        return list({item.employee_id: item for item in rows if item.employee_id}.values())

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
        ) -> None:
            edge = KnowledgeEdge(
                edge_id=_stable_id("edge", source_id, relation, target_id),
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                provenance=provenance,  # type: ignore[arg-type]
                confidence=confidence,
                source_refs=[source_id, target_id],
                extractor_version=EXTRACTOR_VERSION,
                source_revision=source_revision,
                metadata=metadata or {},
            )
            payload = edge.model_dump(mode="json")
            edges.append(
                {
                    "edge_id": edge.edge_id,
                    "source_id": source_id,
                    "target_id": target_id,
                    "relation": relation,
                    "payload": payload,
                }
            )

        relation_fields = {
            "sop_ref": "uses_sop",
            "sop_refs": "uses_sop",
            "action_refs": "uses_action",
            "event_type": "uses_event",
            "event_types": "uses_event",
            "related": "related",
            "related_terms": "related",
            "broader": "broader",
            "narrower": "narrower",
            "source_refs": "evidence",
            "supersedes": "supersedes",
        }
        for record in records:
            revision = record_content_checksum(record)
            declared_relationships = record.metadata.get("relationships") or record.metadata.get("relations") or []
            if isinstance(declared_relationships, dict):
                declared_relationships = [declared_relationships]
            for item in declared_relationships if isinstance(declared_relationships, list) else []:
                if not isinstance(item, dict):
                    continue
                relation = str(item.get("relation") or item.get("type") or "").strip()
                value = str(item.get("target") or item.get("ref") or item.get("boi_id") or "").strip()
                if relation not in DECLARED_RELATIONS or relation == "evidence":
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
            for href in MARKDOWN_LINK.findall(record.text):
                target = self._resolve_target(href, records_by_id, records_by_url, aliases)
                if target and target != record.record_id:
                    append_edge(record.record_id, target, "links_to", "extracted", revision, metadata={"href": href})
            stages = []
            workflow = record.metadata.get("workflow") if isinstance(record.metadata.get("workflow"), dict) else {}
            stages.extend(item for item in workflow.get("stages") or [] if isinstance(item, dict))
            stages.extend(item for item in record.metadata.get("tasks") or [] if isinstance(item, dict))
            for index, stage in enumerate(stages):
                task_key = str(stage.get("task_id") or stage.get("id") or f"task-{index + 1}")
                task_title = str(stage.get("name") or stage.get("title") or task_key)
                task_titles.setdefault(task_key, task_title)
                task_id = _stable_id("task", record.record_id, task_key)
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
                    append_edge(task_id, person_id, "assigned_to", "declared", revision, metadata={"source_ref": record.record_id})
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
                        append_edge(task_id, person_id, "reviewed_by", "declared", revision, metadata={"source_ref": record.record_id})
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
                        append_edge(task_id, team_node_id, "related_team", "declared", revision, metadata={"source_ref": record.record_id})
                for field, relation in {
                    "event_types": "uses_event",
                    "entry_event": "uses_event",
                    "action_refs": "uses_action",
                    "automated_actions": "uses_action",
                    "manual_actions": "uses_action",
                    "skill_refs": "uses_skill",
                    "evidence_refs": "requires_evidence",
                }.items():
                    raw_values = stage.get(field)
                    values = raw_values if isinstance(raw_values, list) else [raw_values] if raw_values else []
                    for raw in values:
                        value = str(raw.get("ref") or "") if isinstance(raw, dict) else str(raw or "")
                        target = self._resolve_target(value, records_by_id, records_by_url, aliases)
                        if target:
                            append_edge(task_id, target, relation, "extracted", revision, metadata={"field": field})

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
                "extracted",
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
                    append_edge(task_id, target, relation, "extracted", revision, metadata={"source_ref": record.record_id})

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
                append_edge(task_id, f"person:{employee_id}", "assigned_to", "declared", revision, metadata={"source_ref": task_id})
            for employee_id in reviewers:
                append_edge(task_id, f"person:{employee_id}", "reviewed_by", "declared", revision, metadata={"source_ref": task_id})
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
                append_edge(task_id, team_node_id, "related_team", "declared", revision, metadata={"source_ref": task_id})

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
                    "declared",
                    identity_revision,
                    metadata={"source_ref": person_id},
                )
            for role_id in identity.roles:
                role_node_id = f"role:{role_id}"
                nodes.append(
                    {
                        "node_id": role_node_id,
                        "node_type": "role",
                        "payload": {
                            "title": role_titles.get(role_id, role_id),
                            "visibility": "public",
                            "source_revision": identity_revision,
                        },
                    }
                )
                append_edge(
                    person_id,
                    role_node_id,
                    "has_role",
                    "declared",
                    identity_revision,
                    metadata={"source_ref": person_id},
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
                nodes.append(
                    {
                        "node_id": node_id,
                        "node_type": node_type,
                        "payload": {
                            "title": title,
                            "visibility": "private",
                            "owner": "",
                            "allowed_employee_ids": admin_employee_ids,
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
        supported = {"ranked", "neighbors", "path", "workflow", "impact", "lineage", "responsibility", "timeline", "compare", "tour"}
        mode = view if view in supported else "neighbors"
        if mode == "ranked":
            result = self.search.search(q or source_ref, principal, limit=min(limit, 20))
            return {"view": mode, **result.model_dump(mode="json")}
        if not source_ref:
            raise HTTPException(status_code=422, detail="관계를 살펴볼 지식을 선택해주세요.")
        graph_manifest = self.store.get("manifests", "knowledge_graph") or {}
        if (
            graph_manifest.get("compiler_version") != EXTRACTOR_VERSION
            or graph_manifest.get("source_signature") != self.repository.source_signature()
            or graph_manifest.get("directory_signature") != self.directory_signature(principal)
        ):
            self.compile_graph(principal)
        offset = int(cursor) if str(cursor).isdigit() else 0
        graph = self.store.ontology_neighbors(
            [source_ref],
            depth=max(1, min(depth if mode != "path" else 6, 6)),
            limit=max(1, min(offset + limit + 1, 500)),
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=principal.is_admin,
        )
        nodes = graph.get("nodes") or []
        edges = _dedupe_semantic_edges(graph.get("edges") or [])
        node_kind_set = {str(item) for item in (node_kinds or []) if str(item)}
        relation_set = {str(item) for item in (relation_kinds or []) if str(item)}
        provenance_set = {str(item) for item in (provenance or []) if str(item)}
        lower_time = _parse_time(time_from)
        upper_time = _parse_time(time_to)

        def edge_time(edge: dict[str, Any]) -> Any:
            payload = edge.get("payload") or {}
            return _parse_time(str(payload.get("observed_at") or payload.get("valid_from") or payload.get("recorded_at") or ""))

        def temporal_match(edge: dict[str, Any]) -> bool:
            observed = edge_time(edge)
            if not observed:
                return not lower_time and not upper_time
            return (not lower_time or observed >= lower_time) and (not upper_time or observed <= upper_time)

        if relation_set:
            edges = [item for item in edges if str(item.get("relation") or "") in relation_set]
        elif mode != "lineage":
            edges = [item for item in edges if str(item.get("relation") or "") != "evidence"]
        if provenance_set:
            edges = [item for item in edges if str((item.get("payload") or {}).get("provenance") or "") in provenance_set]
        if lower_time or upper_time:
            edges = [item for item in edges if temporal_match(item)]
        if direction == "outgoing":
            edges = [item for item in edges if str(item.get("source_id") or "") == source_ref]
        elif direction == "incoming":
            edges = [item for item in edges if str(item.get("target_id") or "") == source_ref]
        visible_refs = {source_ref}
        for edge in edges:
            visible_refs.update({str(edge.get("source_id") or ""), str(edge.get("target_id") or "")})
        nodes = [
            item for item in nodes
            if str(item.get("node_id") or "") in visible_refs
            and (not node_kind_set or str(item.get("node_type") or "") in node_kind_set or str(item.get("node_id") or "") == source_ref)
        ]
        allowed_node_refs = {str(item.get("node_id") or "") for item in nodes}
        edges = [item for item in edges if str(item.get("source_id") or "") in allowed_node_refs and str(item.get("target_id") or "") in allowed_node_refs]
        has_more = len(edges) > offset + limit
        page_edges = edges[offset:offset + limit]
        page_refs = {source_ref}
        for edge in page_edges:
            page_refs.update({str(edge.get("source_id") or ""), str(edge.get("target_id") or "")})
        nodes = [item for item in nodes if str(item.get("node_id") or "") in page_refs]
        edges = page_edges
        if mode == "neighbors":
            return _decorate_graph_result({
                "view": mode,
                "source_ref": source_ref,
                "presentation": "explorer",
                "nodes": nodes,
                "edges": edges,
                "cursor": str(offset),
                "next_cursor": str(offset + limit) if has_more else "",
            }, query_kind=mode)

        if mode in {"workflow", "lineage", "responsibility", "timeline", "compare"}:
            result = self.query(
                principal,
                GraphQueryPlan(
                    focal_entities=[source_ref],
                    target_entities=[target_ref] if target_ref else [],
                    query_kind=mode,
                    node_kinds=list(node_kind_set),
                    relation_kinds=list(relation_set),
                    direction=direction,
                    depth=depth,
                    time_from=time_from,
                    time_to=time_to,
                    limit=limit,
                    presentation="auto",
                ),
            )
            return {"view": mode, "source_ref": source_ref, **result}

        adjacency: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for edge in edges:
            source = str(edge.get("source_id") or "")
            target = str(edge.get("target_id") or "")
            adjacency.setdefault(source, []).append((target, edge))
            if mode in {"path", "tour"}:
                adjacency.setdefault(target, []).append((source, edge))

        if mode == "path":
            if not target_ref:
                raise HTTPException(status_code=422, detail="연결 경로의 도착 지식을 선택해주세요.")
            node_lookup = {str(item.get("node_id") or ""): item for item in nodes}
            queue = deque([(source_ref, [source_ref], [])])
            visited = {source_ref}
            while queue:
                current, path_nodes, path_edges = queue.popleft()
                if current == target_ref:
                    return _decorate_graph_result({
                        "view": mode,
                        "source_ref": source_ref,
                        "target_ref": target_ref,
                        "presentation": "mermaid",
                        "path_refs": path_nodes,
                        "nodes": [node_lookup[item] for item in path_nodes if item in node_lookup],
                        "edges": path_edges,
                    }, query_kind=mode)
                for neighbor, edge in adjacency.get(current, []):
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    queue.append((neighbor, [*path_nodes, neighbor], [*path_edges, edge]))
            return _decorate_graph_result({
                "view": mode,
                "source_ref": source_ref,
                "target_ref": target_ref,
                "presentation": "mermaid",
                "path_refs": [],
                "nodes": [],
                "edges": [],
                "status": "not_connected",
            }, query_kind=mode)

        if mode == "impact":
            affected = {source_ref}
            queue = deque([source_ref])
            selected_edges: list[dict[str, Any]] = []
            while queue and len(affected) < limit:
                current = queue.popleft()
                for neighbor, edge in adjacency.get(current, []):
                    if neighbor in affected:
                        continue
                    affected.add(neighbor)
                    selected_edges.append(edge)
                    queue.append(neighbor)
            return _decorate_graph_result({
                "view": mode,
                "source_ref": source_ref,
                "presentation": "explorer" if len(affected) > 20 else "list",
                "affected_refs": list(affected - {source_ref}),
                "nodes": [item for item in nodes if str(item.get("node_id") or "") in affected],
                "edges": selected_edges,
            }, query_kind=mode)

        order: list[str] = []
        visited = {source_ref}
        queue = deque([source_ref])
        while queue and len(order) < limit:
            current = queue.popleft()
            order.append(current)
            for neighbor, _edge in adjacency.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        node_lookup = {str(item.get("node_id") or ""): item for item in nodes}
        return _decorate_graph_result({
            "view": "tour",
            "source_ref": source_ref,
            "presentation": "list",
            "nodes": [node_lookup[item] for item in order if item in node_lookup],
            "edges": [edge for ref in order for _neighbor, edge in adjacency.get(ref, [])],
            "steps": [
                {
                    "order": index + 1,
                    "ref": ref,
                    "title": str((node_lookup.get(ref) or {}).get("payload", {}).get("title") or ref),
                    "node": node_lookup.get(ref) or {},
                }
                for index, ref in enumerate(order)
            ],
        }, query_kind="tour")

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
            item for item in _dedupe_semantic_edges(graph.get("edges") or [])
            if node_id in {str(item.get("source_id") or ""), str(item.get("target_id") or "")}
        ]
        return {"node": node, "edges": edges, "relation_count": len(edges)}

    def query(self, principal: Principal, plan: GraphQueryPlan) -> dict[str, Any]:
        manifest = self.store.get("manifests", "knowledge_graph") or {}
        if (
            manifest.get("compiler_version") != EXTRACTOR_VERSION
            or manifest.get("source_signature") != self.repository.source_signature()
            or manifest.get("directory_signature") != self.directory_signature(principal)
        ):
            self.compile_graph(principal)
        manifest = self.store.get("manifests", "knowledge_graph") or {}
        cache_payload = {
            "employee_id": principal.employee_id,
            "teams": sorted(principal.teams),
            "is_admin": principal.is_admin,
            "source_signature": manifest.get("source_signature") or "",
            "directory_signature": manifest.get("directory_signature") or "",
            "compiler_version": manifest.get("compiler_version") or "",
            "plan": plan.model_dump(mode="json"),
        }
        cache_id = _stable_id(
            "graph-query",
            json.dumps(cache_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        cached = self.store.get("knowledge_graph_queries", cache_id) or {}
        if isinstance(cached.get("result"), dict):
            return json.loads(json.dumps(cached["result"], ensure_ascii=False))

        def cache_result(result: dict[str, Any]) -> dict[str, Any]:
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

        graph = self.store.ontology_neighbors(
            plan.focal_entities,
            depth=plan.depth,
            limit=plan.limit,
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=principal.is_admin,
        )
        nodes = list({str(item.get("node_id") or ""): item for item in graph.get("nodes") or [] if str(item.get("node_id") or "")}.values())
        edges = _dedupe_semantic_edges(graph.get("edges") or [])
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
        if plan.relation_kinds:
            allowed_relations = set(plan.relation_kinds)
            edges = [item for item in edges if str(item.get("relation") or "") in allowed_relations]
        elif plan.query_kind != "lineage":
            # source_refs are citation lineage, not a useful default business relationship.
            edges = [item for item in edges if str(item.get("relation") or "") != "evidence"]
        focal = set(plan.focal_entities)
        node_lookup = {str(item.get("node_id") or ""): item for item in nodes}
        responsibility_relations = {
            "assigned_to", "reviewed_by", "related_team", "member_of", "has_role",
            "performed_by", "completed_by", "repeated_performer", "owns",
        }
        workflow_relations = {
            "has_task", "part_of_workflow", "uses_sop", "uses_event", "uses_action",
            "uses_skill", "requires_evidence", "produces", "results_in", "triggered_by",
            "next_task", "precedes", "part_of", "triggers", "executes",
        }
        impact_relations = {
            *workflow_relations, "links_to", "related", "narrower", "supersedes",
            "consumed_by", "depends_on", "guides", "uses",
        }
        lineage_relations = {
            "evidence", "requires_evidence", "derived_from", "produces", "results_in",
            "generated_from", "completed_by", "performed_by", "supersedes", "links_to",
        }

        relation_scope = {
            "responsibility": responsibility_relations,
            "workflow": workflow_relations,
            "impact": impact_relations,
            "lineage": lineage_relations,
        }.get(plan.query_kind)
        if relation_scope is not None:
            edges = [item for item in edges if str(item.get("relation") or "") in relation_scope]

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
            selected: list[dict[str, Any]] = []
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
                    selected.append(edge)
                    queue.append(neighbor)
                    if len(reached) >= plan.limit:
                        break
            return reached, selected, depth_by_ref

        traversal_direction = plan.direction
        if plan.query_kind in {"workflow", "impact"} and traversal_direction == "both":
            traversal_direction = "outgoing"

        if plan.query_kind == "path":
            if not plan.target_entities:
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
                if len(path_edges) >= plan.depth:
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
                "presentation": "mermaid" if plan.presentation == "auto" else plan.presentation,
                "status": "connected" if found_nodes else "not_connected",
                "path_refs": found_nodes,
                "nodes": [node_lookup[item] for item in found_nodes if item in node_lookup],
                "edges": found_edges,
                "provenance_required": True,
            }, query_kind=plan.query_kind))

        depth_by_ref: dict[str, int] = {item: 0 for item in focal}
        semantic_refs: list[str] = []
        if plan.query_kind in {"workflow", "impact", "lineage", "responsibility", "neighbors"}:
            query_edges = edges
            if plan.query_kind == "responsibility":
                query_edges = [item for item in edges if str(item.get("relation") or "") in responsibility_relations]
            visible_ids, edges, depth_by_ref = traverse(
                focal,
                query_edges,
                direction=traversal_direction,
                max_depth=1 if plan.query_kind == "responsibility" else plan.depth,
            )
            nodes = [item for item in nodes if str(item.get("node_id") or "") in visible_ids]
            semantic_refs = sorted(visible_ids - focal)

        groups: dict[str, Any] = {}
        comparison: dict[str, Any] = {}
        if plan.query_kind == "compare":
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
        if plan.query_kind == "timeline":
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
        if plan.query_kind == "tour":
            tour_relations = workflow_relations | {
                "broader", "narrower", "links_to", "guides", "uses", "part_of",
            }
            tour_edges = [item for item in edges if str(item.get("relation") or "") in tour_relations]
            visible_ids, selected_edges, depth_by_ref = traverse(
                focal,
                tour_edges,
                direction=plan.direction,
                max_depth=plan.depth,
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
            if plan.query_kind == "timeline":
                presentation = "timeline"
            elif plan.query_kind == "compare":
                presentation = "table"
            elif plan.query_kind in {"workflow", "path", "lineage"} and len(nodes) <= 14 and len(edges) <= 20:
                presentation = "mermaid"
            elif len(nodes) > 20:
                presentation = "explorer"
            else:
                presentation = "list"
        return cache_result(_decorate_graph_result({
            "ok": True,
            "query_plan": plan.model_dump(mode="json"),
            "presentation": presentation,
            "nodes": nodes,
            "edges": edges,
            "groups": groups,
            "comparison": comparison,
            "timeline": timeline,
            "tour_steps": tour_steps,
            "depth_by_ref": depth_by_ref,
            "downstream_refs": semantic_refs if plan.query_kind == "impact" else [],
            "lineage_refs": semantic_refs if plan.query_kind == "lineage" else [],
            "responsibility_refs": semantic_refs if plan.query_kind == "responsibility" else [],
            "provenance_required": True,
        }, query_kind=plan.query_kind))

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
            finding_id = _stable_id("finding", kind, *sorted(refs))
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
        return {"count": len(findings), "items": findings, "refreshed": True, "graph": graph}

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
