from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from fastapi import HTTPException

from .config import AgentV2Settings
from .models import (
    KnowledgeEdge,
    KnowledgePatchProposal,
    KnowledgeProposalApplyRequest,
    KnowledgeSourceCreateRequest,
    KnowledgeSourceDefinition,
    Principal,
)
from .repository import KnowledgeRecord, KnowledgeRepository
from .search import HybridSearchService, record_content_checksum
from .store import AgentV2Store, now_iso


EXTRACTOR_VERSION = "boi-knowledge-compiler/1"
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)\)")


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


class LivingKnowledgeService:
    """Deterministic source, graph, and health layer over the BoI source of truth."""

    def __init__(
        self,
        settings: AgentV2Settings,
        repository: KnowledgeRepository,
        store: AgentV2Store,
        search: HybridSearchService,
    ):
        self.settings = settings
        self.repository = repository
        self.store = store
        self.search = search
        self._ensure_defaults()

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
        if request.source_kind in {"graphify", "codegraph", "external_cli"} and not principal.is_admin:
            raise HTTPException(status_code=403, detail="외부 Source adapter는 관리자만 등록할 수 있습니다.")
        source_id = _stable_id("source", principal.employee_id, request.name, request.location)
        adapter = {
            "data_lake": "builtin.data_lake",
            "graphify": "optional.graphify",
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
        records = self.repository.authoritative_records(compiler_principal, include_drafts=False)
        records_by_id = {item.record_id: item for item in records}
        records_by_url = {item.url.split("?", 1)[0].rstrip("/"): item.record_id for item in records if item.url}
        aliases: dict[str, str] = {}
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []

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
                task_id = _stable_id("task", record.record_id, task_key)
                nodes.append(
                    {
                        "node_id": task_id,
                        "node_type": "task",
                        "payload": {
                            "title": str(stage.get("name") or stage.get("title") or task_key),
                            "parent_ref": record.record_id,
                            "visibility": record.visibility,
                            "owner": record.owner,
                            "team_id": record.team_id,
                            "order": index,
                        },
                    }
                )
                append_edge(record.record_id, task_id, "has_task", "extracted", revision, metadata={"order": index})
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

        unique_nodes = {str(item["node_id"]): item for item in nodes}
        unique_edges = {str(item["edge_id"]): item for item in edges}
        self.store.replace_ontology(list(unique_nodes.values()), list(unique_edges.values()))
        manifest = {
            "compiler_version": EXTRACTOR_VERSION,
            "source_signature": self.repository.source_signature(),
            "nodes": len(unique_nodes),
            "edges": len(unique_edges),
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
        if kind in {"graphify", "codegraph", "external_cli"}:
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
    ) -> dict[str, Any]:
        mode = view if view in {"ranked", "neighbors", "path", "impact", "tour"} else "neighbors"
        if mode == "ranked":
            result = self.search.search(q or source_ref, principal, limit=min(limit, 20))
            return {"view": mode, **result.model_dump(mode="json")}
        if not source_ref:
            raise HTTPException(status_code=422, detail="관계를 살펴볼 지식을 선택해주세요.")
        graph_manifest = self.store.get("manifests", "knowledge_graph") or {}
        if graph_manifest.get("source_signature") != self.repository.source_signature():
            self.compile_graph(principal)
        graph = self.store.ontology_neighbors(
            [source_ref],
            depth=max(1, min(depth if mode != "path" else 6, 6)),
            limit=max(1, min(limit, 300)),
            employee_id=principal.employee_id,
            team_ids=principal.teams,
            include_all=principal.is_admin,
        )
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        if mode == "neighbors":
            return {"view": mode, "source_ref": source_ref, "nodes": nodes, "edges": edges}

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
                    return {
                        "view": mode,
                        "source_ref": source_ref,
                        "target_ref": target_ref,
                        "path_refs": path_nodes,
                        "nodes": [node_lookup[item] for item in path_nodes if item in node_lookup],
                        "edges": path_edges,
                    }
                for neighbor, edge in adjacency.get(current, []):
                    if neighbor in visited:
                        continue
                    visited.add(neighbor)
                    queue.append((neighbor, [*path_nodes, neighbor], [*path_edges, edge]))
            return {
                "view": mode,
                "source_ref": source_ref,
                "target_ref": target_ref,
                "path_refs": [],
                "nodes": [],
                "edges": [],
                "status": "not_connected",
            }

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
            return {
                "view": mode,
                "source_ref": source_ref,
                "affected_refs": list(affected - {source_ref}),
                "nodes": [item for item in nodes if str(item.get("node_id") or "") in affected],
                "edges": selected_edges,
            }

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
        return {
            "view": "tour",
            "source_ref": source_ref,
            "steps": [
                {
                    "order": index + 1,
                    "ref": ref,
                    "title": str((node_lookup.get(ref) or {}).get("payload", {}).get("title") or ref),
                    "node": node_lookup.get(ref) or {},
                }
                for index, ref in enumerate(order)
            ],
        }

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
