from __future__ import annotations

import copy
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import AgentV2Settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentV2Store:
    mode = "unknown"
    durable = False
    degraded_reason = ""

    def health(self) -> dict[str, Any]:
        raise NotImplementedError

    def put(self, collection: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    def list(self, collection: str, *, employee_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        raise NotImplementedError

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

    def put(self, collection: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            stored = copy.deepcopy(value)
            stored.setdefault("updated_at", now_iso())
            self._collections.setdefault(collection, {})[key] = stored
            return copy.deepcopy(stored)

    def get(self, collection: str, key: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._collections.get(collection, {}).get(key)
            return copy.deepcopy(value) if value is not None else None

    def list(self, collection: str, *, employee_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
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

        frontier = {item for item in seed_ids if item}
        visited = set(frontier)
        selected_edges: list[dict[str, Any]] = []
        for _ in range(max(1, min(depth, 6))):
            next_frontier: set[str] = set()
            for edge in edges:
                source = str(edge.get("source_id") or "")
                target = str(edge.get("target_id") or "")
                if source not in frontier and target not in frontier:
                    continue
                other = target if source in frontier else source
                node = nodes.get(other)
                if node and visible(node):
                    selected_edges.append(edge)
                    next_frontier.add(other)
                if len(selected_edges) >= limit:
                    break
            visited.update(next_frontier)
            frontier = next_frontier
            if not frontier or len(selected_edges) >= limit:
                break
        selected_nodes = [nodes[item] for item in visited if item in nodes and visible(nodes[item])]
        return {"nodes": selected_nodes[:limit], "edges": selected_edges[:limit]}


class PostgresAgentV2Store(AgentV2Store):
    mode = "postgres"
    durable = True

    COLLECTION_TABLES = {
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
        "semantic_routes": "agent_semantic_routes",
        "source_sets": "agent_source_sets",
        "starter_suggestion_sets": "agent_starter_suggestion_sets",
        "goal_plans": "agent_goal_plans",
        "citations": "agent_citations",
        "work_runs": "agent_work_runs",
        "harness_results": "agent_harness_results",
        "harness_failure_records": "agent_harness_failure_records",
        "harness_failure_patterns": "agent_harness_failure_patterns",
        "negative_results": "agent_negative_results",
        "context_playbook_items": "agent_context_playbook_items",
        "harness_candidates": "agent_harness_candidates",
        "harness_shadow_runs": "agent_harness_shadow_runs",
        "harness_eval_runs": "agent_harness_eval_runs",
        "harness_versions": "agent_harness_versions",
        "harness_active_versions": "agent_harness_active_versions",
        "harness_release_audits": "agent_harness_release_audits",
        "knowledge_candidates": "agent_knowledge_candidates",
        "completion_records": "agent_completion_records",
        "work_role_profiles": "agent_work_role_profiles",
        "evidence_ledger": "agent_evidence_ledger",
        "usage_ledgers": "agent_usage_ledgers",
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
    }

    def __init__(self, dsn: str, dimensions: int):
        import psycopg

        self.psycopg = psycopg
        self.dsn = dsn
        self.dimensions = dimensions
        self._initialize()

    def _connect(self):
        return self.psycopg.connect(self.dsn, autocommit=True)

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
        with self._connect() as connection:
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
            with self._connect() as connection:
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

    def put(self, collection: str, key: str, value: dict[str, Any]) -> dict[str, Any]:
        if collection == "search_documents":
            return self._put_search_document(key, value)
        if collection == "search_chunks":
            return self._put_search_chunk(key, value)
        table = self._table(collection)
        payload = copy.deepcopy(value)
        payload.setdefault("updated_at", now_iso())
        employee_id = str(payload.get("employee_id") or "")
        with self._connect() as connection:
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
        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._put_search_document_cursor(cursor, key, value)
        return copy.deepcopy(value)

    def _put_search_chunk(self, key: str, value: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
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
        if collection == "search_documents":
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('record_id',record_id,'kind',kind,'title',title,'source',source,'authority',authority,'content',content) FROM search_documents WHERE record_id=%s",
                        (key,),
                    )
                    row = cursor.fetchone()
            return dict(row[0]) if row else None
        if collection == "search_chunks":
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('chunk_id',chunk_id,'record_id',record_id,'kind',kind,'title',title,'heading',heading,'content',content,'start_line',start_line,'end_line',end_line) FROM search_chunks WHERE chunk_id=%s",
                        (key,),
                    )
                    row = cursor.fetchone()
            return dict(row[0]) if row else None
        table = self._table(collection)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"SELECT payload FROM {table} WHERE item_key=%s", (key,))
                row = cursor.fetchone()
        return dict(row[0]) if row else None

    def list(self, collection: str, *, employee_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        if collection == "search_documents":
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT metadata || jsonb_build_object('record_id',record_id,'kind',kind,'title',title,'source',source,'authority',authority,'content',content) FROM search_documents ORDER BY updated_at DESC LIMIT %s",
                        (limit,),
                    )
                    rows = cursor.fetchall()
            return [dict(row[0]) for row in rows]
        if collection == "search_chunks":
            with self._connect() as connection:
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
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, values)
                rows = cursor.fetchall()
        return [dict(row[0]) for row in rows]

    def delete(self, collection: str, key: str) -> bool:
        special = {
            "search_documents": ("search_documents", "record_id"),
            "search_chunks": ("search_chunks", "chunk_id"),
        }
        if collection in special:
            table, id_column = special[collection]
        else:
            table, id_column = self._table(collection), "item_key"
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(f"DELETE FROM {table} WHERE {id_column}=%s", (key,))
                return cursor.rowcount > 0

    def replace_search_documents(self, rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
    ) -> dict[str, list[dict[str, Any]]]:
        clean_seeds = [str(item) for item in seed_ids if str(item).strip()]
        if not clean_seeds:
            return {"nodes": [], "edges": []}
        allowed_teams = [str(item) for item in (team_ids or []) if str(item).strip()]
        max_depth = max(1, min(int(depth), 6))
        row_limit = max(1, min(int(limit), 500))
        with self._connect() as connection:
            with connection.cursor() as cursor:
                raw_edges: list[tuple[Any, ...]] = []
                seen_edge_ids: set[str] = set()
                seen_node_ids = set(clean_seeds)
                frontier = list(clean_seeds)
                for hop in range(1, max_depth + 1):
                    if not frontier or len(raw_edges) >= row_limit:
                        break
                    cursor.execute(
                        """
                        SELECT edge_id, source_id, target_id, relation, payload
                        FROM ontology_edges
                        WHERE source_id = ANY(%s) OR target_id = ANY(%s)
                        ORDER BY edge_id
                        LIMIT %s
                        """,
                        (frontier, frontier, row_limit - len(raw_edges)),
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
                node_ids = list(
                    dict.fromkeys(
                        [*clean_seeds, *[str(row[1]) for row in raw_edges], *[str(row[2]) for row in raw_edges]]
                    )
                )
                cursor.execute(
                    """
                    SELECT node_id, node_type, payload
                    FROM ontology_nodes
                    WHERE node_id = ANY(%s)
                      AND (
                        %s
                        OR COALESCE(payload->>'visibility','public') = 'public'
                        OR (payload->>'visibility' = 'private' AND payload->>'owner' = %s)
                        OR (payload->>'visibility' = 'private' AND COALESCE(payload->'allowed_employee_ids','[]'::jsonb) ? %s)
                        OR (payload->>'visibility' = 'team' AND payload->>'team_id' = ANY(%s))
                        OR (
                          payload->>'visibility' = 'directory'
                          AND (
                            payload->>'owner' = %s
                            OR COALESCE(payload->'allowed_employee_ids','[]'::jsonb) ? %s
                            OR COALESCE(payload->'allowed_team_ids','[]'::jsonb) ?| %s
                          )
                        )
                      )
                    """,
                    (node_ids, include_all, employee_id, employee_id, allowed_teams, employee_id, employee_id, allowed_teams),
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
        with self._connect() as connection:
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
        with self._connect() as connection:
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
        with self._connect() as connection:
            connection.autocommit = False
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT item_key, payload FROM agent_jobs
                        WHERE payload->>'status'='queued'
                        ORDER BY created_at
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
