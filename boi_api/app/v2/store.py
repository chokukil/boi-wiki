from __future__ import annotations

import copy
import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import AgentV2Settings
from .atomic_store_contract import (
    AtomicWrite, MIGRATION_COLLECTIONS, prepare_atomic_writes, atomic_json_equal, atomic_json_wire,
    is_atomic_read_fence,
)
from .store_observation import record_store_read
from .store_connections import store_connection


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_fingerprint(value):
    return ('json-wire-sha256:' + hashlib.sha256(atomic_json_wire(value).encode('utf-8')).hexdigest()
            if value is not None else None)


class AgentV2Store:
    mode = "unknown"
    durable = False
    degraded_reason = ""

    def atomic_compare_and_write(self, writes: Iterable[AtomicWrite]) -> bool:
        """Fail closed if an adapter cannot provide a real atomic CAS boundary."""
        raise NotImplementedError('ATOMIC_STORE_UNSUPPORTED')

    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    def put(self, collection: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def read_snapshot(self, collection: str, key: str):
        """Request-local change detection only; never an authorization receipt."""
        value = self.get(collection, key)
        return value, _snapshot_fingerprint(value)

    def read_fingerprint(self, collection: str, key: str):
        return self.read_snapshot(collection, key)[1]

    def get_many(self, collection: str, keys: list[str]) -> dict[str, dict[str, Any]]:
        """Bounded read of existing records, preserving missing-key semantics."""
        if not 1 <= len(keys) <= 1000:
            raise ValueError('MULTI_GET_LIMIT_INVALID')
        return {key:value for key in set(keys) if (value:=self.get(collection,key)) is not None}

    def list(self, collection: str, *, employee_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

    def list_key_page(self, collection: str, *, employee_id: str, after_key: str = "", limit: int = 100) -> list[dict[str, Any]]:
        """Keyset page for owner-scoped generic records; caller binds a snapshot."""
        raise NotImplementedError('KEYSET_PAGE_UNSUPPORTED')

    def a2ui_catalog_observation(
        self,
        *,
        employee_id: str = "",
        allowed_components: set[str] | None = None,
    ) -> dict[str, Any]:
        """Return an ACL-bounded aggregate without exposing surface payloads."""

        rows = self.list("a2ui_surfaces", employee_id=employee_id, limit=5_000)
        allowed = set(allowed_components or [])
        usage = {name: 0 for name in allowed}
        for row in rows:
            observed = {
                str(item.get("component") or "")
                for item in row.get("components") or []
                if isinstance(item, dict)
                and str(item.get("component") or "") in allowed
            }
            for name in observed:
                usage[name] += 1
        return {
            "surface_count": len(rows),
            "component_usage": usage,
            "updated_at": max(
                (str(item.get("updated_at") or "") for item in rows),
                default="",
            ),
        }

    def delete(self, collection: str, key: str) -> bool:
        raise NotImplementedError

    def heartbeat(self, worker_id: str, metadata: dict[str, Any] | None = None) -> None:
        self.put(
            "worker_heartbeats",
            worker_id,
            {"worker_id": worker_id, "last_seen_at": now_iso(), "metadata": metadata or {}},
        )

    def claim_job(self, worker_id: str) -> dict[str, Any] | None:
        for job in self.list("jobs", limit=1000):
            if job.get("status") != "queued":
                continue
            waiting_for = str(job.get("restart_waiting_for") or "")
            if waiting_for:
                previous = self.get("jobs", waiting_for) or {}
                if not previous.get("worker_stop_ack", False):
                    continue
            claimed = {**job, "status": "running", "worker_id": worker_id, "started_at": now_iso()}
            self.put("jobs", str(job["job_id"]), claimed)
            return claimed
        return None

    def replace_search_documents(self, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
        for existing in self.list("search_documents", limit=1_000_000):
            self.delete("search_documents", str(existing.get("record_id") or ""))
        for row in rows:
            self.put("search_documents", str(row["record_id"]), row)
        self.put("manifests", "search", manifest)

    def replace_search_chunks(self, rows: list[dict[str, Any]]) -> None:
        for existing in self.list("search_chunks", limit=1_000_000):
            self.delete("search_chunks", str(existing.get("chunk_id") or ""))
        for row in rows:
            self.put("search_chunks", str(row["chunk_id"]), row)

    def replace_ontology(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        return None

    def upsert_ontology(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        return None

    def remove_ontology_records(self, record_ids: list[str]) -> None:
        return None

    def remove_ontology_entries(self, node_ids: list[str], edge_ids: list[str]) -> None:
        self.remove_ontology_records(node_ids)

    def ontology_neighbors(
        self,
        seed_ids: list[str],
        *,
        depth: int,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
        relation_kinds: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        return {"nodes": [], "edges": []}

    def vector_search(
        self,
        embedding: list[float],
        *,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        return []

    def vector_search_chunks(
        self,
        embedding: list[float],
        *,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        return []


class MemoryAgentV2Store(AgentV2Store):
    mode = "memory"
    durable = False

    def __init__(self, degraded_reason: str = "Postgres is not configured"):
        self.degraded_reason = degraded_reason
        self._lock = threading.RLock()
        self._collections: dict[str, dict[str, dict[str, Any]]] = {}

    def health(self) -> dict[str, Any]:
        return {
            "ready": True,
            "mode": self.mode,
            "durable": self.durable,
            "degraded": True,
            "reason": self.degraded_reason,
        }

    def atomic_compare_and_write(self, writes: Iterable[AtomicWrite]) -> bool:
        prepared = prepare_atomic_writes(writes)
        with self._lock:
            # Historical put() retained tuples; PostgreSQL stores JSON arrays.
            # Compare existing records at the same declared wire boundary as CAS inputs.
            if any(not atomic_json_equal(json.loads(json.dumps(self.get(item.collection, item.key),
                                         ensure_ascii=False, allow_nan=False)), item.expected)
                   for item in prepared):
                return False
            for item in prepared:
                if not is_atomic_read_fence(item):
                    self.put(item.collection, item.key, item.value)
        return True

    def put(self, collection: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            stored = copy.deepcopy(value)
            stored.setdefault("updated_at", now_iso())
            self._collections.setdefault(collection, {})[key] = stored
            return copy.deepcopy(stored)

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        record_store_read(collection, 'get')
        with self._lock:
            value = self._collections.get(collection, {}).get(key)
            return copy.deepcopy(value) if value is not None else None

    def read_snapshot(self, collection: str, key: str):
        record_store_read(collection, 'read_snapshot')
        with self._lock:
            value = self._collections.get(collection, {}).get(key)
            return copy.deepcopy(value), _snapshot_fingerprint(value)

    def read_fingerprint(self, collection: str, key: str):
        record_store_read(collection, 'read_fingerprint')
        with self._lock:
            return _snapshot_fingerprint(self._collections.get(collection, {}).get(key))

    def list(self, collection: str, *, employee_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        record_store_read(collection, 'list')
        with self._lock:
            values = list(self._collections.get(collection, {}).values())
        if employee_id:
            values = [item for item in values if str(item.get("employee_id") or "") == employee_id]
        values.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
        return copy.deepcopy(values[:limit])

    def delete(self, collection: str, key: str) -> bool:
        with self._lock:
            values = self._collections.get(collection, {})
            return values.pop(key, None) is not None

    def list_key_page(self, collection: str, *, employee_id: str, after_key: str = "", limit: int = 100) -> list[dict[str, Any]]:
        record_store_read(collection, 'list_key_page')
        if not employee_id or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError('KEYSET_PAGE_SCOPE_OR_LIMIT_INVALID')
        with self._lock:
            items = self._collections.get(collection, {})
            keys = sorted(key for key, value in items.items() if key > after_key
                and value.get('employee_id') == employee_id)
            return [{'key':key, 'value':copy.deepcopy(items[key])} for key in keys[:limit]]

    def replace_ontology(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        with self._lock:
            self._collections["_ontology_nodes"] = {
                str(item["node_id"]): copy.deepcopy(item) for item in nodes
            }
            self._collections["_ontology_edges"] = {
                str(item["edge_id"]): copy.deepcopy(item) for item in edges
            }

    def upsert_ontology(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        with self._lock:
            node_store = self._collections.setdefault("_ontology_nodes", {})
            edge_store = self._collections.setdefault("_ontology_edges", {})
            node_store.update({str(item["node_id"]): copy.deepcopy(item) for item in nodes})
            edge_store.update({str(item["edge_id"]): copy.deepcopy(item) for item in edges})

    def remove_ontology_entries(self, node_ids: list[str], edge_ids: list[str]) -> None:
        with self._lock:
            node_store = self._collections.setdefault("_ontology_nodes", {})
            edge_store = self._collections.setdefault("_ontology_edges", {})
            node_targets = {str(item) for item in node_ids if str(item)}
            edge_targets = {str(item) for item in edge_ids if str(item)}
            for node_id in node_targets:
                node_store.pop(node_id, None)
            for edge_id in edge_targets:
                edge_store.pop(edge_id, None)
            self._collections["_ontology_edges"] = {
                key: edge
                for key, edge in edge_store.items()
                if str(edge.get("source_id") or "") not in node_targets
                and str(edge.get("target_id") or "") not in node_targets
            }

    def remove_ontology_records(self, record_ids: list[str]) -> None:
        targets = {str(item) for item in record_ids if str(item)}
        if not targets:
            return
        with self._lock:
            nodes = self._collections.setdefault("_ontology_nodes", {})
            edges = self._collections.setdefault("_ontology_edges", {})
            for record_id in targets:
                nodes.pop(record_id, None)
            self._collections["_ontology_edges"] = {
                key: edge
                for key, edge in edges.items()
                if str(edge.get("source_id") or "") not in targets
                and str(edge.get("target_id") or "") not in targets
            }

    def ontology_neighbors(
        self,
        seed_ids: list[str],
        *,
        depth: int,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
        relation_kinds: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            nodes = copy.deepcopy(self._collections.get("_ontology_nodes", {}))
            edges = list(copy.deepcopy(self._collections.get("_ontology_edges", {})).values())
        allowed_teams = set(team_ids or [])

        def visible(node: dict[str, Any]) -> bool:
            payload = node.get("payload") or {}
            visibility = str(payload.get("visibility") or "public")
            allowed_employees = {str(item) for item in payload.get("allowed_employee_ids") or []}
            allowed_node_teams = {str(item) for item in payload.get("allowed_team_ids") or []}
            return bool(
                include_all
                or visibility == "public"
                or (visibility == "private" and payload.get("owner") == employee_id)
                or (visibility == "private" and employee_id in allowed_employees)
                or (visibility == "team" and payload.get("team_id") in allowed_teams)
                or (
                    visibility == "directory"
                    and (
                        payload.get("owner") == employee_id
                        or employee_id in allowed_employees
                        or bool(allowed_node_teams & allowed_teams)
                    )
                )
            )

        visible_node_ids = {
            node_id for node_id, node in nodes.items() if visible(node)
        }
        visible_edges = [
            edge
            for edge in edges
            if str(edge.get("source_id") or "") in visible_node_ids
            and str(edge.get("target_id") or "") in visible_node_ids
        ]
        if relation_kinds is not None:
            allowed_relations = {str(item) for item in relation_kinds if str(item)}
            visible_edges = [
                edge
                for edge in visible_edges
                if str(edge.get("relation") or "") in allowed_relations
            ]
        # ACL is a traversal predicate, not a result filter. A hidden bridge
        # must not make a visible downstream node discoverable.
        frontier = list(
            dict.fromkeys(
                item for item in seed_ids if item and item in visible_node_ids
            )
        )
        visited = set(frontier)
        selected_edges: list[dict[str, Any]] = []
        selected_edge_ids: set[str] = set()
        for _ in range(max(0, min(depth, 6))):
            next_frontier: list[str] = []
            next_frontier_seen: set[str] = set()
            edges_by_bucket: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for edge in visible_edges:
                source = str(edge.get("source_id") or "")
                target = str(edge.get("target_id") or "")
                relation = str(edge.get("relation") or "")
                for seed in frontier:
                    if source == seed or target == seed:
                        edges_by_bucket.setdefault((seed, relation), []).append(edge)
            ranked_edges = sorted(
                (
                    rank,
                    seed_index,
                    relation,
                    str(edge.get("edge_id") or ""),
                    seed,
                    edge,
                )
                for seed_index, seed in enumerate(frontier)
                for (bucket_seed, relation), bucket_edges in edges_by_bucket.items()
                if bucket_seed == seed
                for rank, edge in enumerate(
                    sorted(
                        bucket_edges,
                        key=lambda item: str(item.get("edge_id") or ""),
                    )
                )
            )
            for _rank, _seed_index, _relation, _edge_id, seed, edge in ranked_edges:
                edge_id = str(edge.get("edge_id") or "")
                if edge_id and edge_id in selected_edge_ids:
                    continue
                source = str(edge.get("source_id") or "")
                target = str(edge.get("target_id") or "")
                other = target if source == seed else source
                selected_edges.append(edge)
                if edge_id:
                    selected_edge_ids.add(edge_id)
                if other not in next_frontier_seen:
                    next_frontier_seen.add(other)
                    next_frontier.append(other)
                if len(selected_edges) >= limit:
                    break
            visited.update(next_frontier)
            frontier = next_frontier
            if not frontier or len(selected_edges) >= limit:
                break
        selected_nodes = [nodes[item] for item in visited if item in visible_node_ids]
        return {"nodes": selected_nodes[:limit], "edges": selected_edges[:limit]}


class PostgresAgentV2Store(AgentV2Store):
    mode = "postgres"
    durable = True

    COLLECTION_TABLES = {
        **{key: 'agent_' + key for key in MIGRATION_COLLECTIONS},
        "runs": "agent_runs",
        "turns": "agent_turns",
        "jobs": "agent_jobs",
        "checkpoints": "agent_checkpoints",
        "offers": "agent_offers",
        "plans": "agent_plans",
        "evaluations": "agent_evaluations",
        "contexts": "agent_contexts",
        "artifacts": "agent_artifacts",
        "tokens": "agent_tokens",
        "worker_heartbeats": "agent_worker_heartbeats",
        "manifests": "search_index_manifests",
        "task_modes": "agent_task_modes",
        "work_sessions": "agent_work_sessions",
        "session_messages": "agent_session_messages",
        "artifact_revisions": "agent_artifact_revisions",
        "helper_drafts": "agent_helper_drafts",
        "helpers": "agent_helpers",
        "skills": "agent_skills",
        "skill_test_runs": "agent_skill_test_runs",
        "semantic_routes": "agent_semantic_routes",
        "semantic_plans": "agent_semantic_plans",
        "source_sets": "agent_source_sets",
        "starter_suggestion_sets": "agent_starter_suggestion_sets",
        "goal_plans": "agent_goal_plans",
        "citations": "agent_citations",
        "work_runs": "agent_work_runs",
        "work_run_checkpoints": "agent_work_run_checkpoints",
        "harness_results": "agent_harness_results",
        "harness_failure_records": "agent_harness_failure_records",
        "harness_failure_patterns": "agent_harness_failure_patterns",
        "negative_results": "agent_negative_results",
        "context_playbook_items": "agent_context_playbook_items",
        "harness_candidates": "agent_harness_candidates",
        "harness_code_patch_artifacts": "agent_harness_code_patch_artifacts",
        "harness_shadow_runs": "agent_harness_shadow_runs",
        "harness_eval_runs": "agent_harness_eval_runs",
        "harness_versions": "agent_harness_versions",
        "harness_active_versions": "agent_harness_active_versions",
        "harness_release_audits": "agent_harness_release_audits",
        "knowledge_candidates": "agent_knowledge_candidates",
        "knowledge_candidate_suppressions": "agent_knowledge_candidate_suppressions",
        "completion_records": "agent_completion_records",
        "work_role_profiles": "agent_work_role_profiles",
        "evidence_ledger": "agent_evidence_ledger",
        "usage_ledgers": "agent_usage_ledgers",
        "usage_records": "ontology_usage_records",
        "work_routines": "agent_work_routines",
        "routine_triggers": "agent_routine_triggers",
        "user_work_profiles": "agent_user_work_profiles",
        "a2ui_surfaces": "agent_a2ui_surfaces",
        "knowledge_sources": "knowledge_sources",
        "knowledge_source_manifests": "knowledge_source_manifests",
        "knowledge_source_jobs": "knowledge_source_jobs",
        "knowledge_source_rollbacks": "knowledge_source_rollbacks",
        "knowledge_health_findings": "knowledge_health_findings",
        "knowledge_patch_proposals": "knowledge_patch_proposals",
        "knowledge_graph_queries": "knowledge_graph_queries",
        "graph_relation_evidence": "agent_graph_relation_evidence",
        "ontology_schema_proposals": "ontology_schema_proposals",
        "ontology_schema_versions": "ontology_schema_versions",
        "ontology_schema_active": "ontology_schema_active",
        "event_runtime_plans": "event_runtime_plans",
        "event_runtime_definitions": "event_runtime_definitions",
        "event_runtime_idempotency": "event_runtime_idempotency",
        "event_detector_decisions": "event_detector_decisions",
        "event_occurrences": "event_occurrences",
        "workflow_runs": "workflow_runs",
        "task_runs": "task_runs",
        "action_runs": "action_runs",
        "outcomes": "ontology_outcomes",
        "next_events": "ontology_next_events",
        "agent_task_packages": "agent_task_packages",
        "agent_task_idempotency": "agent_task_idempotency",
        "external_work_results": "external_work_results",
        "verified_answers": "verified_answers",
        "verified_answer_idempotency": "verified_answer_idempotency",
        "verified_answer_invocations": "verified_answer_invocations",
        "prepared_answer_executions": "prepared_answer_executions",
        "verified_answer_result_cache": "verified_answer_result_cache",
        "governed_answer_records_v2": "governed_answer_records_v2",
        "governed_answer_semantic_v2": "governed_answer_semantic_v2",
        "governed_answer_idempotency_v2": "governed_answer_idempotency_v2",
        "governed_answer_invocations_v2": "governed_answer_invocations_v2",
        "governed_answer_frozen_results_v2": "governed_answer_frozen_results_v2",
        "governed_answer_access_v2": "governed_answer_access_v2",
        "governed_answer_exports_v2": "governed_answer_exports_v2",
        "governed_answer_artifacts_v3": "governed_answer_artifacts_v3",
        "governed_answer_artifact_idempotency_v3": "governed_answer_artifact_idempotency_v3",
        "governed_answer_artifact_invocations_v3": "governed_answer_artifact_invocations_v3",
    }

    def __init__(self, dsn: str, dimensions: int):
        import psycopg

        self.psycopg = psycopg
        self.dsn = dsn
        self.dimensions = dimensions
        self._initialize()

    def _connect(self):
        return self.psycopg.connect(self.dsn, autocommit=True)

    def _connection(self):
        return store_connection(self)

    @staticmethod
    def _ensure_vector_dimension(cursor: Any, table: str, dimensions: int) -> bool:
        cursor.execute(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = to_regclass(%s) AND attname = 'embedding' AND NOT attisdropped",
            (table,),
        )
        row = cursor.fetchone()
        expected = f"vector({dimensions})"
        if row and str(row[0]) == expected:
            return False
        cursor.execute(f"DROP INDEX IF EXISTS {table}_embedding_hnsw")
        cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.execute(
            f"ALTER TABLE {table} ALTER COLUMN embedding TYPE vector({dimensions}) "
            f"USING NULL::vector({dimensions})"
        )
        return True

    def _initialize(self) -> None:
        dimensions = int(self.dimensions)
        if dimensions < 1 or dimensions > 16000:
            raise ValueError("invalid embedding dimensions")
        generic_tables = ",".join(self.COLLECTION_TABLES.values())
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
                for table in generic_tables.split(","):
                    cursor.execute(
                        f"""
                        CREATE TABLE IF NOT EXISTS {table} (
                            item_key TEXT PRIMARY KEY,
                            employee_id TEXT NOT NULL DEFAULT '',
                            payload JSONB NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {table}_employee_idx ON {table}(employee_id, updated_at DESC)")
                from ..governed_runtime.native_reference_projection import install_reference_index
                install_reference_index(cursor,self._table('domain_knowledge_assets'))
                from ..governed_runtime.native_reference_guard import install_reference_guard
                install_reference_guard(cursor,self)
                from ..governed_runtime.native_profile_catalog import install_profile_catalog
                install_profile_catalog(cursor,self._table('domain_knowledge_assets'))
                from ..governed_runtime.native_contract_catalog import install_contract_catalog
                install_contract_catalog(cursor,self._table('domain_knowledge_assets'))
                from ..governed_runtime.native_text_projection import install_text_index
                install_text_index(cursor,self._table('knowledge_text_projections'))
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS search_documents (
                        record_id TEXT PRIMARY KEY,
                        employee_scope TEXT NOT NULL DEFAULT 'public',
                        kind TEXT NOT NULL,
                        title TEXT NOT NULL,
                        source TEXT NOT NULL,
                        authority TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({dimensions}),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                dimension_changed = self._ensure_vector_dimension(cursor, "search_documents", dimensions)
                cursor.execute("CREATE INDEX IF NOT EXISTS search_documents_kind_idx ON search_documents(kind, authority)")
                try:
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS search_documents_embedding_hnsw "
                        "ON search_documents USING hnsw (embedding vector_cosine_ops)"
                    )
                except Exception:
                    # pgvector versions without HNSW still support exact vector search.
                    pass
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS search_chunks (
                        chunk_id TEXT PRIMARY KEY,
                        record_id TEXT NOT NULL,
                        employee_scope TEXT NOT NULL DEFAULT 'public',
                        kind TEXT NOT NULL,
                        title TEXT NOT NULL,
                        heading TEXT NOT NULL DEFAULT '',
                        content TEXT NOT NULL,
                        start_line INTEGER NOT NULL DEFAULT 0,
                        end_line INTEGER NOT NULL DEFAULT 0,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({dimensions}),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                dimension_changed = (
                    self._ensure_vector_dimension(cursor, "search_chunks", dimensions) or dimension_changed
                )
                if dimension_changed:
                    cursor.execute("DELETE FROM search_index_manifests WHERE item_key = 'search'")
                cursor.execute("CREATE INDEX IF NOT EXISTS search_chunks_record_idx ON search_chunks(record_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS search_chunks_kind_idx ON search_chunks(kind)")
                try:
                    cursor.execute(
                        "CREATE INDEX IF NOT EXISTS search_chunks_embedding_hnsw "
                        "ON search_chunks USING hnsw (embedding vector_cosine_ops)"
                    )
                except Exception:
                    pass
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ontology_nodes (
                        node_id TEXT PRIMARY KEY,
                        node_type TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ontology_edges (
                        edge_id TEXT PRIMARY KEY,
                        source_id TEXT NOT NULL,
                        target_id TEXT NOT NULL,
                        relation TEXT NOT NULL,
                        payload JSONB NOT NULL DEFAULT '{}'::jsonb,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute("CREATE INDEX IF NOT EXISTS ontology_edges_source_idx ON ontology_edges(source_id, relation)")
                cursor.execute("CREATE INDEX IF NOT EXISTS ontology_edges_target_idx ON ontology_edges(target_id, relation)")
                cursor.execute("CREATE INDEX IF NOT EXISTS ontology_edges_relation_idx ON ontology_edges(relation)")

    def health(self) -> dict[str, Any]:
        try:
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
                    row = cursor.fetchone()
                    cursor.execute("SELECT COUNT(*) FROM search_documents")
                    search_documents = int(cursor.fetchone()[0])
                    cursor.execute("SELECT COUNT(*) FROM search_chunks")
                    search_chunks = int(cursor.fetchone()[0])
            return {
                "ready": bool(row),
                "mode": self.mode,
                "durable": self.durable,
                "degraded": not bool(row),
                "pgvector_version": str(row[0]) if row else "",
                "search_documents": search_documents,
                "search_chunks": search_chunks,
            }
        except Exception as exc:
            return {
                "ready": False,
                "mode": self.mode,
                "durable": self.durable,
                "degraded": True,
                "reason": f"{type(exc).__name__}: {exc}",
            }

    def _table(self, collection: str) -> str:
        try:
            return self.COLLECTION_TABLES[collection]
        except KeyError as exc:
            raise KeyError(f"unsupported collection: {collection}") from exc

    def read_snapshot(self, collection: str, key: str):
        record_store_read(collection, 'read_snapshot')
        table = self._table(collection)
        with self._connection() as connection:
            row = connection.execute(f"SELECT payload,encode(sha256(convert_to(payload::text,'UTF8')),'hex') "
                                     f'FROM {table} WHERE item_key=%s', (key,)).fetchone()
        return (row[0], 'pg-jsonb-sha256:' + row[1]) if row else (None, None)

    def read_fingerprint(self, collection: str, key: str):
        record_store_read(collection, 'read_fingerprint')
        table = self._table(collection)
        with self._connection() as connection:
            row = connection.execute(f"SELECT encode(sha256(convert_to(payload::text,'UTF8')),'hex') "
                                     f'FROM {table} WHERE item_key=%s', (key,)).fetchone()
        return 'pg-jsonb-sha256:' + row[0] if row else None

    def atomic_compare_and_write(self, writes: Iterable[AtomicWrite]) -> bool:
        prepared = prepare_atomic_writes(writes)

        class Conflict(Exception):
            pass

        try:
            with self._connection() as connection:
                with connection.transaction():
                    with connection.cursor() as cursor:
                        for item in prepared:
                            table = self._table(item.collection)
                            expected = atomic_json_wire(item.expected)
                            if item.expected is not None and expected == atomic_json_wire(item.value):
                                # Keep the dependency locked until every mutation commits,
                                # without rewriting its JSONB/TOAST value or recency.
                                cursor.execute(
                                    f'SELECT 1 FROM {table} WHERE item_key=%s AND payload=%s::jsonb FOR UPDATE',
                                    (item.key, expected))
                                if cursor.rowcount != 1:
                                    raise Conflict()
                                continue
                            payload = item.value
                            payload.setdefault('updated_at', now_iso())
                            encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
                            owner = str(payload.get('employee_id') or '')
                            if item.expected is None:
                                cursor.execute(
                                    f'INSERT INTO {table}(item_key,employee_id,payload) '
                                    'VALUES (%s,%s,%s::jsonb) ON CONFLICT(item_key) DO NOTHING',
                                    (item.key, owner, encoded))
                            else:
                                cursor.execute(
                                    f'UPDATE {table} SET employee_id=%s,payload=%s::jsonb,updated_at=NOW() '
                                    'WHERE item_key=%s AND payload=%s::jsonb',
                                    (owner, encoded, item.key, expected))
                            if cursor.rowcount != 1:
                                raise Conflict()
            return True
        except Conflict:
            # The transaction rolls back every preceding write on any stale key.
            return False

    def put(self, collection: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        if collection == "search_documents":
            return self._put_search_document(key, value)
        if collection == "search_chunks":
            return self._put_search_chunk(key, value)
        table = self._table(collection)
        payload = copy.deepcopy(value)
        payload.setdefault("updated_at", now_iso())
        employee_id = str(payload.get("employee_id") or "")
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {table}(item_key, employee_id, payload)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT(item_key) DO UPDATE
                    SET employee_id=EXCLUDED.employee_id, payload=EXCLUDED.payload, updated_at=NOW()
                    """,
                    (key, employee_id, json.dumps(payload, ensure_ascii=False, default=str)),
                )
        return payload

    def _put_search_document(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                self._put_search_document_cursor(cursor, key, value)
        return copy.deepcopy(value)

    def _put_search_chunk(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                self._put_search_chunk_cursor(cursor, key, value)
        return copy.deepcopy(value)

    @staticmethod
    def _put_search_chunk_cursor(cursor: Any, key: str, value: dict[str, Any]) -> None:
        embedding = value.get("embedding")
        embedding_value = (
            "[" + ",".join(str(float(item)) for item in embedding) + "]"
            if isinstance(embedding, list)
            else None
        )
        cursor.execute(
            """
            INSERT INTO search_chunks(
                chunk_id, record_id, employee_scope, kind, title, heading, content,
                start_line, end_line, metadata, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT(chunk_id) DO UPDATE SET
                record_id=EXCLUDED.record_id,
                employee_scope=EXCLUDED.employee_scope,
                kind=EXCLUDED.kind,
                title=EXCLUDED.title,
                heading=EXCLUDED.heading,
                content=EXCLUDED.content,
                start_line=EXCLUDED.start_line,
                end_line=EXCLUDED.end_line,
                metadata=EXCLUDED.metadata,
                embedding=EXCLUDED.embedding,
                updated_at=NOW()
            """,
            (
                key,
                str(value.get("record_id") or ""),
                str(value.get("employee_scope") or "public"),
                str(value.get("kind") or "document"),
                str(value.get("title") or key),
                str(value.get("heading") or ""),
                str(value.get("content") or ""),
                int(value.get("start_line") or 0),
                int(value.get("end_line") or 0),
                json.dumps(value.get("metadata") or {}, ensure_ascii=False, default=str),
                embedding_value,
            ),
        )

    @staticmethod
    def _put_search_document_cursor(cursor: Any, key: str, value: dict[str, Any]) -> None:
        embedding = value.get("embedding")
        embedding_value = (
            "[" + ",".join(str(float(item)) for item in embedding) + "]"
            if isinstance(embedding, list)
            else None
        )
        cursor.execute(
            """
            INSERT INTO search_documents(
                record_id, employee_scope, kind, title, source, authority, content, metadata, embedding
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT(record_id) DO UPDATE SET
                employee_scope=EXCLUDED.employee_scope,
                kind=EXCLUDED.kind,
                title=EXCLUDED.title,
                source=EXCLUDED.source,
                authority=EXCLUDED.authority,
                content=EXCLUDED.content,
                metadata=EXCLUDED.metadata,
                embedding=EXCLUDED.embedding,
                updated_at=NOW()
            """,
            (
                key,
                str(value.get("employee_scope") or "public"),
                str(value.get("kind") or "document"),
                str(value.get("title") or key),
                str(value.get("source") or "knowledge"),
                str(value.get("authority") or "reviewed"),
                str(value.get("content") or ""),
                json.dumps(value.get("metadata") or {}, ensure_ascii=False, default=str),
                embedding_value,
            ),
        )

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        record_store_read(collection, 'get')
        if collection == "search_documents":
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('record_id',record_id,'kind',kind,'title',title,'source',source,'authority',authority,'content',content) FROM search_documents WHERE record_id=%s",
                        (key,),
                    )
                    row = cursor.fetchone()
            return dict(row[0]) if row else None
        if collection == "search_chunks":
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('chunk_id',chunk_id,'record_id',record_id,'kind',kind,'title',title,'heading',heading,'content',content,'start_line',start_line,'end_line',end_line) FROM search_chunks WHERE chunk_id=%s",
                        (key,),
                    )
                    row = cursor.fetchone()
            return dict(row[0]) if row else None
        table = self._table(collection)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT payload FROM {table} WHERE item_key=%s", (key,))
                row = cursor.fetchone()
        return dict(row[0]) if row else None

    def get_many(self, collection: str, keys: list[str]) -> dict[str, dict[str, Any]]:
        if not 1 <= len(keys) <= 1000:
            raise ValueError('MULTI_GET_LIMIT_INVALID')
        if collection in {'search_documents','search_chunks'}:
            return super().get_many(collection,keys)
        table = self._table(collection)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT item_key, payload FROM {table} WHERE item_key = ANY(%s)',(list(set(keys)),))
                rows = cursor.fetchall()
        return {row[0]:dict(row[1]) for row in rows}

    def list(self, collection: str, *, employee_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        record_store_read(collection, 'list')
        if collection == "search_documents":
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('record_id',record_id,'kind',kind,'title',title,'source',source,'authority',authority,'content',content) FROM search_documents ORDER BY updated_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cursor.fetchall()
            return [dict(row[0]) for row in rows]
        if collection == "search_chunks":
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('chunk_id',chunk_id,'record_id',record_id,'kind',kind,'title',title,'heading',heading,'content',content,'start_line',start_line,'end_line',end_line) FROM search_chunks ORDER BY updated_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cursor.fetchall()
            return [dict(row[0]) for row in rows]
        table = self._table(collection)
        sql = f"SELECT payload FROM {table}"
        values: tuple[Any, ...]
        if employee_id:
            sql += " WHERE employee_id=%s ORDER BY updated_at DESC LIMIT %s"
            values = (employee_id, limit)
        else:
            sql += " ORDER BY updated_at DESC LIMIT %s"
            values = (limit,)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                rows = cursor.fetchall()
        return [dict(row[0]) for row in rows]

    def list_key_page(self, collection: str, *, employee_id: str, after_key: str = "", limit: int = 100) -> list[dict[str, Any]]:
        record_store_read(collection, 'list_key_page')
        if not employee_id or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
            raise ValueError('KEYSET_PAGE_SCOPE_OR_LIMIT_INVALID')
        if collection in {'search_documents', 'search_chunks'}:
            raise ValueError('KEYSET_PAGE_GENERIC_COLLECTION_REQUIRED')
        table = self._table(collection)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT item_key, payload FROM {table} WHERE employee_id=%s AND item_key>%s ORDER BY item_key LIMIT %s',
                    (employee_id, after_key, limit))
                rows = cursor.fetchall()
        return [{'key':row[0], 'value':dict(row[1])} for row in rows]

    def a2ui_catalog_observation(
        self,
        *,
        employee_id: str = "",
        allowed_components: set[str] | None = None,
    ) -> dict[str, Any]:
        """Aggregate component observations in Postgres instead of decoding every surface."""

        table = self._table("a2ui_surfaces")
        allowed = sorted(str(item) for item in allowed_components or set() if str(item))
        employee_filter = "WHERE employee_id=%s" if employee_id else ""
        values: tuple[Any, ...] = (
            (employee_id, allowed)
            if employee_id
            else (allowed,)
        )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    WITH visible AS (
                        SELECT item_key, payload, updated_at
                        FROM {table}
                        {employee_filter}
                    ), observed AS (
                        SELECT DISTINCT
                            visible.item_key,
                            component.value->>'component' AS component
                        FROM visible
                        CROSS JOIN LATERAL jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof(visible.payload->'components') = 'array'
                                THEN visible.payload->'components'
                                ELSE '[]'::jsonb
                            END
                        ) AS component(value)
                        WHERE component.value->>'component' = ANY(%s)
                    ), usage AS (
                        SELECT component, COUNT(*)::integer AS observed_count
                        FROM observed
                        GROUP BY component
                    )
                    SELECT
                        (SELECT COUNT(*)::integer FROM visible),
                        (SELECT MAX(updated_at) FROM visible),
                        COALESCE(
                            (SELECT jsonb_object_agg(component, observed_count) FROM usage),
                            '{{}}'::jsonb
                        )
                    """,
                    values,
                )
                row = cursor.fetchone()
        usage = dict(row[2] or {}) if row else {}
        return {
            "surface_count": int(row[0] or 0) if row else 0,
            "component_usage": {
                name: int(usage.get(name) or 0)
                for name in allowed
            },
            "updated_at": str(row[1] or "") if row else "",
        }

    def delete(self, collection: str, key: str) -> bool:
        special = {
            "search_documents": ("search_documents", "record_id"),
            "search_chunks": ("search_chunks", "chunk_id"),
        }
        if collection in special:
            table, id_column = special[collection]
        else:
            table, id_column = self._table(collection), "item_key"
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE {id_column}=%s", (key,))
                return cursor.rowcount > 0

    def replace_search_documents(self, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
        with self._connection() as connection:
            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute("TRUNCATE search_documents")
                    for row in rows:
                        self._put_search_document_cursor(cursor, str(row["record_id"]), row)
                    manifest_payload = {**manifest, "updated_at": now_iso()}
                    cursor.execute(
                        """
                        INSERT INTO search_index_manifests(item_key, employee_id, payload)
                        VALUES ('search', '', %s::jsonb)
                        ON CONFLICT(item_key) DO UPDATE
                        SET payload=EXCLUDED.payload, updated_at=NOW()
                        """,
                        (json.dumps(manifest_payload, ensure_ascii=False, default=str),),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def upsert_ontology(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        with self._connection() as connection:
            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    for node in nodes:
                        cursor.execute(
                            """
                            INSERT INTO ontology_nodes(node_id,node_type,payload)
                            VALUES (%s,%s,%s::jsonb)
                            ON CONFLICT(node_id) DO UPDATE SET
                                node_type=EXCLUDED.node_type,
                                payload=EXCLUDED.payload,
                                updated_at=NOW()
                            """,
                            (
                                str(node["node_id"]),
                                str(node.get("node_type") or "knowledge"),
                                json.dumps(node.get("payload") or {}, ensure_ascii=False, default=str),
                            ),
                        )
                    for edge in edges:
                        cursor.execute(
                            """
                            INSERT INTO ontology_edges(edge_id,source_id,target_id,relation,payload)
                            VALUES (%s,%s,%s,%s,%s::jsonb)
                            ON CONFLICT(edge_id) DO UPDATE SET
                                source_id=EXCLUDED.source_id,
                                target_id=EXCLUDED.target_id,
                                relation=EXCLUDED.relation,
                                payload=EXCLUDED.payload
                            """,
                            (
                                str(edge["edge_id"]),
                                str(edge["source_id"]),
                                str(edge["target_id"]),
                                str(edge.get("relation") or "related"),
                                json.dumps(edge.get("payload") or {}, ensure_ascii=False, default=str),
                            ),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def remove_ontology_records(self, record_ids: list[str]) -> None:
        targets = [str(item) for item in record_ids if str(item)]
        if not targets:
            return
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM ontology_edges WHERE source_id = ANY(%s) OR target_id = ANY(%s)",
                    (targets, targets),
                )
                cursor.execute("DELETE FROM ontology_nodes WHERE node_id = ANY(%s)", (targets,))

    def remove_ontology_entries(self, node_ids: list[str], edge_ids: list[str]) -> None:
        node_targets = [str(item) for item in node_ids if str(item)]
        edge_targets = [str(item) for item in edge_ids if str(item)]
        if not node_targets and not edge_targets:
            return
        with self._connection() as connection:
            with connection.cursor() as cursor:
                if edge_targets:
                    cursor.execute("DELETE FROM ontology_edges WHERE edge_id = ANY(%s)", (edge_targets,))
                if node_targets:
                    cursor.execute(
                        "DELETE FROM ontology_edges WHERE source_id = ANY(%s) OR target_id = ANY(%s)",
                        (node_targets, node_targets),
                    )
                    cursor.execute("DELETE FROM ontology_nodes WHERE node_id = ANY(%s)", (node_targets,))

    def replace_search_chunks(self, rows: list[dict[str, Any]]) -> None:
        with self._connection() as connection:
            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute("TRUNCATE search_chunks")
                    for row in rows:
                        self._put_search_chunk_cursor(cursor, str(row["chunk_id"]), row)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def replace_ontology(self, nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
        with self._connection() as connection:
            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute("TRUNCATE ontology_edges, ontology_nodes")
                    for node in nodes:
                        cursor.execute(
                            "INSERT INTO ontology_nodes(node_id,node_type,payload) VALUES (%s,%s,%s::jsonb)",
                            (
                                str(node["node_id"]),
                                str(node.get("node_type") or "knowledge"),
                                json.dumps(node.get("payload") or {}, ensure_ascii=False, default=str),
                            ),
                        )
                    for edge in edges:
                        cursor.execute(
                            "INSERT INTO ontology_edges(edge_id,source_id,target_id,relation,payload) VALUES (%s,%s,%s,%s,%s::jsonb)",
                            (
                                str(edge["edge_id"]),
                                str(edge["source_id"]),
                                str(edge["target_id"]),
                                str(edge.get("relation") or "related"),
                                json.dumps(edge.get("payload") or {}, ensure_ascii=False, default=str),
                            ),
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def ontology_neighbors(
        self,
        seed_ids: list[str],
        *,
        depth: int,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
        relation_kinds: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        clean_seeds = [str(item) for item in seed_ids if str(item).strip()]
        if not clean_seeds:
            return {"nodes": [], "edges": []}
        allowed_teams = [str(item) for item in (team_ids or []) if str(item).strip()]
        max_depth = max(0, min(int(depth), 6))
        row_limit = max(1, min(int(limit), 500))

        def acl_clause(alias: str) -> str:
            return f"""(
              %s
              OR COALESCE({alias}.payload->>'visibility','public') = 'public'
              OR ({alias}.payload->>'visibility' = 'private' AND {alias}.payload->>'owner' = %s)
              OR ({alias}.payload->>'visibility' = 'private' AND COALESCE({alias}.payload->'allowed_employee_ids','[]'::jsonb) ? %s)
              OR ({alias}.payload->>'visibility' = 'team' AND {alias}.payload->>'team_id' = ANY(%s))
              OR (
                {alias}.payload->>'visibility' = 'directory'
                AND (
                  {alias}.payload->>'owner' = %s
                  OR COALESCE({alias}.payload->'allowed_employee_ids','[]'::jsonb) ? %s
                  OR COALESCE({alias}.payload->'allowed_team_ids','[]'::jsonb) ?| %s
                )
              )
            )"""

        acl_parameters = (
            include_all,
            employee_id,
            employee_id,
            allowed_teams,
            employee_id,
            employee_id,
            allowed_teams,
        )
        with self._connection() as connection:
            with connection.cursor() as cursor:
                # Resolve ACL-visible nodes first. Traversing raw edges and
                # filtering nodes afterwards leaks reachability through a
                # hidden bridge even when the bridge itself is omitted. Keep
                # the ACL check in SQL at each endpoint instead of loading all
                # visible node IDs into Python and sending the full set back
                # for every hop. The latter made a bounded relationship read
                # scale with the complete graph rather than its neighborhood.
                cursor.execute(
                    f"""
                    SELECT seed.node_id
                    FROM ontology_nodes AS seed
                    WHERE seed.node_id = ANY(%s)
                      AND {acl_clause("seed")}
                    """,
                    (clean_seeds, *acl_parameters),
                )
                visible_seed_set = {str(row[0]) for row in cursor.fetchall()}
                visible_seed_ids = [item for item in clean_seeds if item in visible_seed_set]
                if not visible_seed_ids:
                    return {"nodes": [], "edges": []}
                raw_edges: list[tuple[Any, ...]] = []
                seen_edge_ids: set[str] = set()
                seen_node_ids = set(visible_seed_ids)
                frontier = list(visible_seed_ids)
                for hop in range(1, max_depth + 1):
                    if not frontier or len(raw_edges) >= row_limit:
                        break
                    cursor.execute(
                        f"""
                        WITH frontier(seed_id) AS (
                          SELECT unnest(%s::text[])
                        ), ranked AS (
                          SELECT e.edge_id, e.source_id, e.target_id, e.relation, e.payload,
                                 f.seed_id,
                                 ROW_NUMBER() OVER (
                                   PARTITION BY f.seed_id, e.relation ORDER BY e.edge_id
                                 ) AS seed_rank
                          FROM frontier AS f
                          JOIN ontology_edges AS e
                            ON e.source_id = f.seed_id OR e.target_id = f.seed_id
                          JOIN ontology_nodes AS source_node
                            ON source_node.node_id = e.source_id
                           AND {acl_clause("source_node")}
                          JOIN ontology_nodes AS target_node
                            ON target_node.node_id = e.target_id
                           AND {acl_clause("target_node")}
                          WHERE (%s OR e.relation = ANY(%s))
                        ), deduplicated AS (
                          SELECT DISTINCT ON (edge_id)
                                 edge_id, source_id, target_id, relation, payload,
                                 seed_id, seed_rank
                          FROM ranked
                          ORDER BY edge_id, seed_rank, seed_id
                        )
                        SELECT edge_id, source_id, target_id, relation, payload
                        FROM deduplicated
                        ORDER BY seed_rank, seed_id, edge_id
                        LIMIT %s
                        """,
                        (
                            frontier,
                            *acl_parameters,
                            *acl_parameters,
                            relation_kinds is None,
                            [str(item) for item in relation_kinds or [] if str(item)],
                            row_limit - len(raw_edges),
                        ),
                    )
                    next_frontier: list[str] = []
                    for row in cursor.fetchall():
                        edge_id = str(row[0])
                        if edge_id in seen_edge_ids:
                            continue
                        seen_edge_ids.add(edge_id)
                        raw_edges.append((*row, hop))
                        for node_id in (str(row[1]), str(row[2])):
                            if node_id not in seen_node_ids:
                                seen_node_ids.add(node_id)
                                next_frontier.append(node_id)
                    frontier = list(dict.fromkeys(next_frontier))
                cursor.execute(
                    f"""
                    SELECT selected.node_id, selected.node_type, selected.payload
                    FROM ontology_nodes AS selected
                    WHERE selected.node_id = ANY(%s)
                      AND {acl_clause("selected")}
                    """,
                    (list(seen_node_ids), *acl_parameters),
                )
                raw_nodes = cursor.fetchall()
        nodes = [
            {"node_id": row[0], "node_type": row[1], "payload": dict(row[2] or {})}
            for row in raw_nodes
        ]
        visible_ids = {str(item["node_id"]) for item in nodes}
        edges = [
            {
                "edge_id": row[0],
                "source_id": row[1],
                "target_id": row[2],
                "relation": row[3],
                "payload": dict(row[4] or {}),
                "depth": int(row[5] or 1),
            }
            for row in raw_edges
            if str(row[1]) in visible_ids and str(row[2]) in visible_ids
        ]
        return {"nodes": nodes[:row_limit], "edges": edges[:row_limit]}

    def vector_search(
        self,
        embedding: list[float],
        *,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        vector_value = "[" + ",".join(str(float(item)) for item in embedding) + "]"
        allowed_scopes = ["public", f"private:{employee_id}"]
        allowed_scopes.extend(f"team:{team_id}" for team_id in (team_ids or []) if team_id)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT record_id, kind, title, source, authority, content, metadata,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM search_documents
                    WHERE embedding IS NOT NULL
                      AND (%s OR employee_scope = ANY(%s))
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vector_value, include_all, allowed_scopes, vector_value, limit),
                )
                rows = cursor.fetchall()
        return [
            {
                "record_id": row[0],
                "kind": row[1],
                "title": row[2],
                "source": row[3],
                "authority": row[4],
                "content": row[5],
                "metadata": dict(row[6] or {}),
                "semantic_score": float(row[7] or 0.0),
            }
            for row in rows
        ]

    def vector_search_chunks(
        self,
        embedding: list[float],
        *,
        limit: int,
        employee_id: str,
        team_ids: list[str] | None = None,
        include_all: bool = False,
    ) -> list[dict[str, Any]]:
        vector_value = "[" + ",".join(str(float(item)) for item in embedding) + "]"
        allowed_scopes = ["public", f"private:{employee_id}"]
        allowed_scopes.extend(f"team:{team_id}" for team_id in (team_ids or []) if team_id)
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT chunk_id, record_id, kind, title, heading, content, start_line, end_line, metadata,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM search_chunks
                    WHERE embedding IS NOT NULL
                      AND (%s OR employee_scope = ANY(%s))
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vector_value, include_all, allowed_scopes, vector_value, limit),
                )
                rows = cursor.fetchall()
        return [
            {
                "chunk_id": row[0],
                "record_id": row[1],
                "kind": row[2],
                "title": row[3],
                "heading": row[4],
                "content": row[5],
                "start_line": int(row[6] or 0),
                "end_line": int(row[7] or 0),
                "metadata": dict(row[8] or {}),
                "semantic_score": float(row[9] or 0.0),
            }
            for row in rows
        ]

    def claim_job(self, worker_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT candidate.item_key, candidate.payload FROM agent_jobs AS candidate
                        WHERE candidate.payload->>'status'='queued'
                          AND NOT EXISTS (
                            SELECT 1 FROM agent_jobs AS previous
                            WHERE previous.item_key = candidate.payload->>'restart_waiting_for'
                              AND COALESCE(previous.payload->>'worker_stop_ack','false') <> 'true'
                          )
                        ORDER BY candidate.created_at
                        FOR UPDATE SKIP LOCKED LIMIT 1
                        """
                    )
                    row = cursor.fetchone()
                    if not row:
                        connection.commit()
                        return None
                    job = dict(row[1])
                    job.update({"status": "running", "worker_id": worker_id, "started_at": now_iso()})
                    cursor.execute(
                        "UPDATE agent_jobs SET payload=%s::jsonb, updated_at=NOW() WHERE item_key=%s",
                        (json.dumps(job, ensure_ascii=False, default=str), row[0]),
                    )
                connection.commit()
                return job
            except Exception:
                connection.rollback()
                raise


def build_store(settings: AgentV2Settings) -> AgentV2Store:
    if not settings.database_dsn:
        return MemoryAgentV2Store("BOI_AGENT_V2_DATABASE_URL is not configured")
    try:
        return PostgresAgentV2Store(settings.database_dsn, settings.embedding_dimensions)
    except Exception as exc:
        return MemoryAgentV2Store(f"Postgres unavailable: {type(exc).__name__}: {exc}")
