from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

from .a2ui import capability_catalog
from .model_gateway import ModelGateway
from .models import EvidenceRef, Principal, SearchResponse
from .repository import KnowledgeRecord, KnowledgeRepository, normalize_tokens
from .store import AgentV2Store, now_iso


SEARCH_INDEX_SCHEMA_VERSION = "3.2"


def ontology_edge_payload(
    provenance: str,
    source_refs: list[str],
    source_revision: str,
    **metadata: Any,
) -> dict[str, Any]:
    return {
        "provenance": provenance,
        "confidence": 1.0,
        "source_refs": list(dict.fromkeys(str(item) for item in source_refs if str(item))),
        "extractor_version": "hybrid-search-index/3.2",
        "source_revision": source_revision,
        **metadata,
    }


def record_content_checksum(record: KnowledgeRecord) -> str:
    payload = {
        "record_id": record.record_id,
        "kind": record.kind,
        "title": record.title,
        "description": record.description,
        "text": record.text,
        "url": record.url,
        "source": record.source,
        "authority": record.authority,
        "status": record.status,
        "visibility": record.visibility,
        "owner": record.owner,
        "team_id": record.team_id,
        "metadata": record.metadata,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def meaningful_query_tokens(value: str) -> set[str]:
    tokens = normalize_tokens(value)
    domain_tokens = tokens - {"boi", "wiki"}
    return domain_tokens if len(domain_tokens) >= 2 else tokens


def chunks_for_record(
    record: KnowledgeRecord,
    *,
    min_chars: int = 800,
    max_chars: int = 1200,
    overlap_chars: int = 120,
) -> list[dict[str, Any]]:
    """Split one knowledge record into heading-aware, line-addressable chunks."""

    source_lines = record.text.splitlines() or [record.description or record.title]
    units: list[tuple[int, str, str]] = []
    heading = ""
    for line_number, raw in enumerate(source_lines, start=1):
        line = raw.rstrip()
        if line.lstrip().startswith("#"):
            heading = line.lstrip("# ").strip()
        if len(line) <= max_chars:
            units.append((line_number, line, heading))
            continue
        for offset in range(0, len(line), max_chars):
            units.append((line_number, line[offset : offset + max_chars], heading))

    chunks: list[dict[str, Any]] = []
    buffer: list[tuple[int, str, str]] = []

    def flush() -> None:
        nonlocal buffer
        content = "\n".join(item[1] for item in buffer).strip()
        if not content:
            buffer = []
            return
        start_line = buffer[0][0]
        end_line = buffer[-1][0]
        chunk_heading = next((item[2] for item in buffer if item[2]), "")
        digest = hashlib.sha256(
            f"{record.record_id}:{start_line}:{end_line}:{content}".encode("utf-8")
        ).hexdigest()[:24]
        chunks.append(
            {
                "chunk_id": f"chunk:{digest}",
                "record_id": record.record_id,
                "kind": record.kind,
                "title": record.title,
                "heading": chunk_heading,
                "content": content,
                "start_line": start_line,
                "end_line": end_line,
                "metadata": {"url": record.url, "status": record.status},
            }
        )
        overlap: list[tuple[int, str, str]] = []
        overlap_length = 0
        for item in reversed(buffer):
            overlap.insert(0, item)
            overlap_length += len(item[1])
            if overlap_length >= overlap_chars:
                break
        buffer = overlap if len(overlap) < len(buffer) else []

    for unit in units:
        next_heading = unit[1].lstrip().startswith("#")
        current_length = sum(len(item[1]) + 1 for item in buffer)
        if buffer and next_heading and current_length >= min_chars:
            flush()
        buffer.append(unit)
        current_length = sum(len(item[1]) + 1 for item in buffer)
        if current_length >= max_chars:
            flush()
    if buffer:
        flush()
    return chunks


def best_chunk_for_query(record: KnowledgeRecord, query: str) -> dict[str, Any]:
    chunks = chunks_for_record(record)
    if not chunks:
        return {}
    query_tokens = meaningful_query_tokens(query)
    return max(
        chunks,
        key=lambda item: (
            len(query_tokens & normalize_tokens(f"{item.get('heading', '')} {item.get('content', '')}")),
            -int(item.get("start_line") or 0),
        ),
    )


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def lexical_score(query_tokens: set[str], record: KnowledgeRecord, expanded_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    title_tokens = normalize_tokens(record.title)
    description_tokens = normalize_tokens(record.description)
    raw_aliases = record.metadata.get("aliases") or []
    aliases = raw_aliases if isinstance(raw_aliases, list) else [raw_aliases]
    alias_tokens = normalize_tokens(" ".join(str(item) for item in aliases if str(item).strip()))
    body_tokens = normalize_tokens(record.search_blob)
    exact = len(query_tokens & title_tokens) * 1.0
    exact += len(query_tokens & alias_tokens) * 0.85
    exact += len(query_tokens & description_tokens) * 0.65
    exact += len(query_tokens & body_tokens) * 0.25
    expanded = len((expanded_tokens - query_tokens) & body_tokens) * 0.15
    denominator = max(1.0, len(query_tokens) * 1.4)
    return clamp((exact + expanded) / denominator)


def authority_score(record: KnowledgeRecord) -> float:
    return {
        "published": 1.0,
        "reviewed": 0.95,
        "active": 0.9,
        "historical": 0.72,
        "runtime": 0.65,
        "provisional": 0.45,
    }.get(record.authority.lower(), 0.5)


def recency_score(timestamp: str) -> float:
    if not timestamp:
        return 0.5
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400)
        return math.exp(-age_days / 365.0)
    except ValueError:
        return 0.5


def precise_context_ref(value: str) -> str:
    clean = str(value or "").strip().split("?", 1)[0].rstrip("/")
    if clean.startswith("/docs/") and clean != "/docs":
        return clean
    if clean.startswith(("boi:", "sop:", "workflow:", "task:", "event:", "action:")):
        return clean
    if re.search(r"/(?:runs|tasks|inbox)/[^/]+", clean):
        return clean
    return ""


def graph_score(record: KnowledgeRecord, query_tokens: set[str]) -> float:
    metadata = record.metadata
    links: list[str] = []
    for key in (
        "sop_ref",
        "sop_refs",
        "action_refs",
        "event_type",
        "event_types",
        "workflow_definition_key",
        "source_refs",
        "related",
    ):
        value = metadata.get(key)
        if isinstance(value, list):
            links.extend(str(item) for item in value)
        elif value:
            links.append(str(value))
    link_tokens = normalize_tokens(" ".join(links))
    return clamp(min(1.0, len(query_tokens & link_tokens) / max(1, len(query_tokens))))


def context_anchor_score(record: KnowledgeRecord, page_ref: str, task_ref: str) -> float:
    """Boost an already-relevant result without making the current page a candidate."""

    context = 0.0
    page_context = precise_context_ref(page_ref)
    if page_context and (page_context == record.url.rstrip("/") or page_context in record.search_blob):
        context += 0.5
    if task_ref and task_ref in record.search_blob:
        context += 0.5
    return clamp(context)


def diversify_ranked(
    ranked: list[tuple[float, KnowledgeRecord, dict[str, float]]],
    limit: int,
) -> list[tuple[float, KnowledgeRecord, dict[str, float]]]:
    selected: list[tuple[float, KnowledgeRecord, dict[str, float]]] = []
    deferred: list[tuple[float, KnowledgeRecord, dict[str, float]]] = []
    title_clusters: set[str] = set()
    for item in ranked:
        title = re.sub(r"\s+\d+건$", "", re.sub(r"\s+", " ", item[1].title.lower())).strip()
        if title and title in title_clusters:
            deferred.append(item)
            continue
        if title:
            title_clusters.add(title)
        selected.append(item)
        if len(selected) >= limit:
            return selected
    if len(selected) < limit:
        selected.extend(deferred[: limit - len(selected)])
    return selected


def ontology_score(record: KnowledgeRecord, query_tokens: set[str]) -> float:
    if record.kind != "dictionary" or not query_tokens:
        return 0.0
    values = [record.title, str(record.metadata.get("term") or "")]
    for key in ("aliases", "related", "related_terms", "broader", "narrower"):
        raw = record.metadata.get(key)
        if isinstance(raw, list):
            values.extend(str(item) for item in raw)
        elif raw:
            values.append(str(raw))
    value_tokens = normalize_tokens(" ".join(values))
    return clamp(len(query_tokens & value_tokens) / max(1, len(query_tokens)))


def identity_score(record: KnowledgeRecord, query_tokens: set[str]) -> float:
    if not query_tokens:
        return 0.0
    values = [record.title, str(record.metadata.get("term") or "")]
    aliases = record.metadata.get("aliases") or []
    if isinstance(aliases, list):
        values.extend(str(item) for item in aliases if str(item).strip())
    elif aliases:
        values.append(str(aliases))
    best = 0.0
    for value in values:
        value_tokens = normalize_tokens(value)
        if not value_tokens:
            continue
        overlap = len(query_tokens & value_tokens)
        if not overlap:
            continue
        if value_tokens == query_tokens:
            return 1.0
        coverage = overlap / len(query_tokens)
        precision = overlap / len(value_tokens)
        best = max(best, 0.8 * coverage + 0.2 * precision)
    return clamp(best)


class HybridSearchService:
    def __init__(self, repository: KnowledgeRepository, store: AgentV2Store, model: ModelGateway):
        self.repository = repository
        self.store = store
        self.model = model

    @staticmethod
    def candidate_record(item: dict[str, Any]) -> KnowledgeRecord:
        return KnowledgeRecord(
            record_id=str(item.get("candidate_id") or ""),
            kind="knowledge",
            title=str(item.get("title") or "업무에서 남긴 내용"),
            description=str(item.get("summary") or ""),
            text=str(item.get("reusable_lesson") or item.get("summary") or ""),
            url=f"/api/v2/knowledge-candidates/{item.get('candidate_id')}",
            source="knowledge_candidate",
            authority="reviewed" if item.get("status") == "reviewed" else "provisional",
            status=str(item.get("status") or "provisional"),
            visibility="private",
            owner=str(item.get("employee_id") or ""),
            timestamp=str(item.get("updated_at") or item.get("created_at") or ""),
            metadata={
                "source_refs": item.get("source_refs") or [],
                "source_work_run_id": item.get("source_work_run_id") or "",
                "target_asset_ref": item.get("target_asset_ref") or "",
                "novelty": item.get("novelty") or {},
            },
        )

    def runtime_record(self, ref: str, principal: Principal) -> KnowledgeRecord | None:
        if ref != "runtime:a2ui-capability-catalog":
            return None
        surfaces = self.store.list(
            "a2ui_surfaces",
            employee_id="" if principal.is_admin else principal.employee_id,
            limit=5000,
        )
        catalog = capability_catalog(surfaces)
        component_rows = [
            (
                str(item["name"]),
                int(item.get("observed_surface_count") or 0),
            )
            for item in catalog.get("components") or []
            if isinstance(item, dict) and item.get("name")
        ]
        component_names = [name for name, _count in component_rows]
        most_observed = max(component_rows, key=lambda item: item[1], default=("", 0))
        component_lines = [
            f"현재 등록 component {name}: 실제 surface 관측 {count}건"
            for name, count in component_rows
        ]
        return KnowledgeRecord(
            record_id=ref,
            kind="runtime",
            title="A2UI 현재 등록 component와 사용 현황",
            description=(
                f"{catalog.get('compatibility_id')} catalog의 현재 실제 registry와 사용자별 관측 surface 현황. "
                "실제로 사용된 부분, 현재 등록된 component와 실제 사용 여부는 이 운영 상태 자료로 확인합니다."
            ),
            text="\n".join(
                [
                    "이 자료는 A2UI의 정의 문서가 아니라 현재 실행 중인 BoI component registry와 surface 사용 현황입니다.",
                    "실제로 사용된 부분을 묻는 경우 현재 등록된 component와 관측된 surface를 이 자료에서 확인합니다.",
                    f"현재 protocol version: {catalog.get('protocol_version')}",
                    f"현재 catalog: {catalog.get('compatibility_id')}",
                    f"현재 등록 component: {', '.join(component_names)}",
                    f"현재 생성된 surface: {int(catalog.get('surface_count') or 0)}건",
                    (
                        f"현재 실제 surface 관측이 가장 많은 component: "
                        f"{most_observed[0]} {most_observed[1]}건"
                    ),
                    *component_lines,
                    f"현재 mutation policy: {catalog.get('mutation_policy')}",
                ]
            ),
            url="/api/v2/a2ui/catalogs/boi/v1",
            source="runtime",
            authority="reviewed",
            status="reviewed",
            visibility="private",
            owner=principal.employee_id,
            metadata={
                "answer_scope": "operational",
                "catalog_id": catalog.get("compatibility_id"),
                "protocol_version": catalog.get("protocol_version"),
                "surface_count": catalog.get("surface_count"),
                "component_names": component_names,
                "component_usage": {
                    name: count for name, count in component_rows
                },
                "mutation_policy": catalog.get("mutation_policy"),
            },
        )

    def runtime_records(self, principal: Principal) -> list[KnowledgeRecord]:
        record = self.runtime_record("runtime:a2ui-capability-catalog", principal)
        return [record] if record is not None else []

    def search(
        self,
        query: str,
        principal: Principal,
        *,
        limit: int = 8,
        include_history: bool = False,
        include_drafts: bool = False,
        page_ref: str = "",
        task_ref: str = "",
        kinds: set[str] | None = None,
        answer_scopes: set[str] | None = None,
        ranking_policy: dict[str, float] | None = None,
    ) -> SearchResponse:
        clean_query = query.strip()
        if not clean_query:
            return SearchResponse(query="", mode="hybrid", items=[], degraded=[], index_manifest={})
        aliases = self.repository.ontology_aliases(clean_query, principal)
        query_tokens = meaningful_query_tokens(clean_query)
        expanded_tokens = query_tokens | normalize_tokens(" ".join(aliases))
        records = self.repository.authoritative_records(principal, include_drafts=include_drafts)
        records.extend(self.runtime_records(principal))
        candidate_rows = self.store.list(
            "knowledge_candidates",
            employee_id=principal.employee_id,
            limit=500,
        )
        records.extend(
            self.candidate_record(item)
            for item in candidate_rows
            if item.get("candidate_id")
            and item.get("status") in {"provisional", "reviewed"}
            and not (item.get("status") == "reviewed" and item.get("target_asset_ref"))
        )
        if include_history:
            records.extend(self.repository.history_records(principal, include_seed=True))
        if kinds:
            records = [record for record in records if record.kind in kinds]
        if answer_scopes:
            records = [
                record
                for record in records
                if self.repository.answer_scope(record) in answer_scopes
            ]

        semantic_by_id: dict[str, float] = {}
        semantic_chunk_by_id: dict[str, dict[str, Any]] = {}
        degraded: list[str] = []
        model_state = self.model.readiness()
        store_state = self.store.health()
        if model_state.get("embeddings") and store_state.get("mode") == "postgres" and store_state.get("ready"):
            try:
                embedding = self.model.embed([clean_query])[0]
                semantic_rows = self.store.vector_search_chunks(
                    embedding,
                    limit=max(limit * 5, 30),
                    employee_id=principal.employee_id,
                    team_ids=principal.teams,
                    include_all=principal.is_admin,
                )
                if semantic_rows:
                    for item in semantic_rows:
                        record_id = str(item.get("record_id") or "")
                        score = clamp(float(item.get("semantic_score") or 0.0))
                        if score > semantic_by_id.get(record_id, 0.0):
                            semantic_by_id[record_id] = score
                            semantic_chunk_by_id[record_id] = item
                else:
                    semantic_rows = self.store.vector_search(
                        embedding,
                        limit=max(limit * 3, 20),
                        employee_id=principal.employee_id,
                        team_ids=principal.teams,
                        include_all=principal.is_admin,
                    )
                    semantic_by_id = {
                        str(item.get("record_id") or ""): clamp(float(item.get("semantic_score") or 0.0))
                        for item in semantic_rows
                    }
            except Exception as exc:
                degraded.append(f"semantic_search_failed:{type(exc).__name__}")
        else:
            degraded.append("semantic_search_unavailable")

        record_ids = {item.record_id for item in records}
        graph_seed_ids: list[str] = []
        semantic_seeds = sorted(semantic_by_id.items(), key=lambda item: -item[1])[:3]
        graph_seed_ids.extend(item[0] for item in semantic_seeds if item[0] in record_ids)
        for record in records:
            raw_aliases = record.metadata.get("aliases") or []
            record_aliases = raw_aliases if isinstance(raw_aliases, list) else [raw_aliases]
            identity_tokens = normalize_tokens(
                " ".join(
                    [
                        record.title,
                        str(record.metadata.get("term") or ""),
                        " ".join(str(item) for item in record_aliases),
                    ]
                )
            )
            if query_tokens and len(query_tokens & identity_tokens) >= min(2, len(query_tokens)):
                graph_seed_ids.append(record.record_id)
            if len(graph_seed_ids) >= 8:
                break
        graph_seed_ids = list(dict.fromkeys(item for item in graph_seed_ids if item))[:8]
        graph_scores: dict[str, float] = {item: 1.0 for item in graph_seed_ids if item in record_ids}
        graph_paths: dict[str, list[dict[str, Any]]] = {}
        if graph_seed_ids:
            try:
                graph_result = self.store.ontology_neighbors(
                    graph_seed_ids,
                    depth=2,
                    limit=max(limit * 8, 48),
                    employee_id=principal.employee_id,
                    team_ids=principal.teams,
                    include_all=principal.is_admin,
                )
                for edge in graph_result.get("edges") or []:
                    distance_score = 0.75 if int(edge.get("depth") or 1) <= 1 else 0.5
                    for node_id in (str(edge.get("source_id") or ""), str(edge.get("target_id") or "")):
                        if node_id in record_ids:
                            graph_scores[node_id] = max(graph_scores.get(node_id, 0.0), distance_score)
                            graph_paths.setdefault(node_id, []).append(
                                {
                                    "source_id": edge.get("source_id"),
                                    "target_id": edge.get("target_id"),
                                    "relation": edge.get("relation"),
                                    "depth": edge.get("depth") or 1,
                                }
                            )
            except Exception as exc:
                degraded.append(f"ontology_traversal_failed:{type(exc).__name__}")

        base_weights = {
            "lexical": 0.30,
            "semantic": 0.26,
            "graph": 0.08,
            "ontology": 0.18,
            "authority": 0.07,
            "recency": 0.03,
            "identity": 0.08,
            "context_anchor": 0.03,
        }
        multipliers = {
            key: max(0.25, min(2.0, float((ranking_policy or {}).get(f"{key}_weight", 1.0))))
            for key in base_weights
        }
        ranked: list[tuple[float, KnowledgeRecord, dict[str, float]]] = []
        for record in records:
            lexical = lexical_score(query_tokens, record, expanded_tokens)
            semantic = semantic_by_id.get(record.record_id, 0.0)
            ontology = ontology_score(record, query_tokens)
            graph = max(graph_score(record, query_tokens), graph_scores.get(record.record_id, 0.0))
            context_anchor = context_anchor_score(record, page_ref, task_ref)
            authority = authority_score(record)
            recency = recency_score(record.timestamp)
            identity = identity_score(record, query_tokens)
            if lexical <= 0 and semantic <= 0 and graph <= 0 and ontology <= 0 and identity <= 0:
                continue
            component_values = {
                "lexical": lexical,
                "semantic": semantic,
                "graph": graph,
                "ontology": ontology,
                "authority": authority,
                "recency": recency,
                "identity": identity,
                "context_anchor": context_anchor,
            }
            score = sum(
                base_weights[key] * multipliers[key] * component_values[key]
                for key in base_weights
            )
            ranked.append(
                (
                    score,
                    record,
                    {
                        "lexical": round(lexical, 4),
                        "semantic": round(semantic, 4),
                        "graph": round(graph, 4),
                        "ontology": round(ontology, 4),
                        "authority": round(authority, 4),
                        "recency": round(recency, 4),
                        "identity": round(identity, 4),
                        "context_anchor": round(context_anchor, 4),
                    },
                )
            )
        ranked.sort(key=lambda item: (-item[0], item[1].record_id))
        ranked = diversify_ranked(ranked, max(1, min(limit, 20)))
        items: list[EvidenceRef] = []
        for score, record, components in ranked[: max(1, min(limit, 20))]:
            summary = record.description or re.sub(r"\s+", " ", record.text).strip()[:360]
            best_chunk = semantic_chunk_by_id.get(record.record_id) or best_chunk_for_query(record, clean_query)
            items.append(
                EvidenceRef(
                    evidence_id=record.record_id,
                    kind=record.kind,
                    title=record.title,
                    summary=summary,
                    url=record.url,
                    source=record.source,
                    authority=record.authority,
                    score=round(score, 4),
                    metadata={
                        "score_components": components,
                        "status": record.status,
                        "answer_scope": self.repository.answer_scope(record),
                        "best_chunk": best_chunk,
                        "graph_paths": graph_paths.get(record.record_id, [])[:4],
                    },
                )
            )
        manifest = self.store.get("manifests", "search") or {}
        return SearchResponse(
            query=clean_query,
            mode="ontology+lexical+semantic+graph",
            items=items,
            ontology_terms=aliases,
            degraded=degraded,
            index_manifest={
                key: manifest.get(key)
                for key in (
                    "indexed_at",
                    "record_count",
                    "embedding_provider",
                    "embedding_model",
                    "dimensions",
                    "index_schema_version",
                    "status",
                )
                if key in manifest
            }
            | {
                "ranking_policy": {
                    key: value
                    for key, value in multipliers.items()
                    if value != 1.0
                }
            },
        )

    def index_private_candidate(self, candidate: dict[str, Any]) -> dict[str, Any]:
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id or candidate.get("status") not in {"provisional", "reviewed"}:
            return {"status": "skipped", "record_id": candidate_id, "chunk_ids": []}
        record = self.candidate_record(candidate)
        model_state = self.model.readiness()
        store_state = self.store.health()
        if not model_state.get("embeddings") or store_state.get("mode") != "postgres" or not store_state.get("ready"):
            return {"status": "lexical_ready", "record_id": candidate_id, "chunk_ids": []}

        content = f"{record.title}\n{record.description}\n{record.text[:12000]}"
        vector = self.model.embed([content])[0]
        chunks = chunks_for_record(record)
        chunk_texts = [f"{item['title']}\n{item.get('heading') or ''}\n{item['content']}" for item in chunks]
        chunk_vectors = self.model.embed(chunk_texts) if chunk_texts else []
        employee_scope = f"private:{record.owner}"
        checksum = record_content_checksum(record)
        stale_chunk_ids = [
            str(item.get("chunk_id") or "")
            for item in self.store.list("search_chunks", limit=100_000)
            if str(item.get("record_id") or "") == candidate_id
        ]
        for chunk_id in stale_chunk_ids:
            self.store.delete("search_chunks", chunk_id)
        self.store.remove_ontology_records([candidate_id])
        self.store.put(
            "search_documents",
            candidate_id,
            {
                "record_id": candidate_id,
                "employee_scope": employee_scope,
                "kind": record.kind,
                "title": record.title,
                "source": record.source,
                "authority": record.authority,
                "content": content,
                "metadata": {
                    "url": record.url,
                    "status": record.status,
                    "content_checksum": checksum,
                    **record.metadata,
                },
                "embedding": vector,
            },
        )
        for chunk, chunk_vector in zip(chunks, chunk_vectors):
            self.store.put(
                "search_chunks",
                str(chunk["chunk_id"]),
                {**chunk, "employee_scope": employee_scope, "embedding": chunk_vector},
            )
        self.store.upsert_ontology(
            [
                {
                    "node_id": candidate_id,
                    "node_type": "knowledge",
                    "payload": {
                        "title": record.title,
                        "url": record.url,
                        "visibility": "private",
                        "owner": record.owner,
                        "authority": record.authority,
                    },
                }
            ],
            [
                {
                    "edge_id": hashlib.sha1(f"{candidate_id}:evidence:{ref}".encode()).hexdigest()[:24],
                    "source_id": candidate_id,
                    "target_id": str(ref),
                    "relation": "evidence",
                    "payload": ontology_edge_payload(
                        "declared",
                        [candidate_id, str(ref)],
                        str(candidate.get("updated_at") or candidate.get("created_at") or ""),
                    ),
                }
                for ref in candidate.get("source_refs") or []
                if str(ref).strip()
            ],
        )
        return {
            "status": "indexed",
            "record_id": candidate_id,
            "chunk_ids": [str(item["chunk_id"]) for item in chunks],
        }

    def remove_private_candidate(self, candidate: dict[str, Any]) -> None:
        candidate_id = str(candidate.get("candidate_id") or "")
        if not candidate_id:
            return
        self.store.delete("search_documents", candidate_id)
        chunk_ids = [str(item) for item in candidate.get("search_chunk_ids") or [] if str(item)]
        if not chunk_ids:
            chunk_ids = [
                str(item.get("chunk_id") or "")
                for item in self.store.list("search_chunks", limit=100_000)
                if str(item.get("record_id") or "") == candidate_id
            ]
        for chunk_id in chunk_ids:
            self.store.delete("search_chunks", chunk_id)

    def similar_cases(self, query: str, principal: Principal, *, task_ref: str = "", limit: int = 8) -> SearchResponse:
        return self.search(
            query,
            principal,
            limit=limit,
            include_history=True,
            page_ref="",
            task_ref=task_ref,
            kinds={"case"},
        )

    def index_records(
        self,
        principal: Principal,
        record_ids: list[str],
        *,
        finalize_manifest: bool = True,
    ) -> dict[str, Any]:
        requested = {str(item) for item in record_ids if str(item).strip()}
        self.repository.invalidate_source_cache()
        records = [
            item
            for item in self.repository.authoritative_records(principal, include_drafts=False)
            if item.record_id in requested
        ]
        missing = sorted(requested - {item.record_id for item in records})
        if not records:
            return {"status": "not_found", "indexed": [], "missing": missing}
        model_state = self.model.readiness()
        store_state = self.store.health()
        if not model_state.get("embeddings") or store_state.get("mode") != "postgres" or not store_state.get("ready"):
            return {
                "status": "lexical_ready",
                "indexed": [item.record_id for item in records],
                "missing": missing,
                "source_signature": self.repository.source_signature(),
            }

        def employee_scope(record: KnowledgeRecord) -> str:
            if record.visibility == "private":
                return f"private:{record.owner}"
            if record.visibility == "team":
                return f"team:{record.team_id}"
            return "public"

        document_texts = [f"{item.title}\n{item.description}\n{item.text[:12000]}" for item in records]
        vectors = self.model.embed(document_texts)
        chunk_rows = [chunk for record in records for chunk in chunks_for_record(record)]
        chunk_texts = [f"{item['title']}\n{item.get('heading') or ''}\n{item['content']}" for item in chunk_rows]
        chunk_vectors = self.model.embed(chunk_texts) if chunk_texts else []
        record_ids_to_replace = {item.record_id for item in records}
        stale_chunk_ids = [
            str(item.get("chunk_id") or "")
            for item in self.store.list("search_chunks", limit=100_000)
            if str(item.get("record_id") or "") in record_ids_to_replace
        ]
        for chunk_id in stale_chunk_ids:
            self.store.delete("search_chunks", chunk_id)
        self.store.remove_ontology_records(sorted(record_ids_to_replace))
        for record, content, vector in zip(records, document_texts, vectors):
            self.store.put(
                "search_documents",
                record.record_id,
                {
                    "record_id": record.record_id,
                    "employee_scope": employee_scope(record),
                    "kind": record.kind,
                    "title": record.title,
                    "source": record.source,
                    "authority": record.authority,
                    "content": content,
                    "metadata": {
                        "url": record.url,
                        "status": record.status,
                        "content_checksum": record_content_checksum(record),
                        **record.metadata,
                    },
                    "embedding": vector,
                },
            )
        record_lookup = {item.record_id: item for item in records}
        for chunk, vector in zip(chunk_rows, chunk_vectors):
            record = record_lookup[str(chunk["record_id"])]
            chunk["employee_scope"] = employee_scope(record)
            chunk["embedding"] = vector
            self.store.put("search_chunks", str(chunk["chunk_id"]), chunk)
        nodes = [
            {
                "node_id": item.record_id,
                "node_type": item.kind,
                "payload": {
                    "title": item.title,
                    "url": item.url,
                    "visibility": item.visibility,
                    "owner": item.owner,
                    "team_id": item.team_id,
                    "authority": item.authority,
                    "aliases": item.metadata.get("aliases") or [],
                },
            }
            for item in records
        ]
        edges: list[dict[str, Any]] = []
        for record in records:
            for raw in record.metadata.get("source_refs") or []:
                target = str(raw.get("ref") or raw.get("id") or "") if isinstance(raw, dict) else str(raw or "")
                if not target:
                    continue
                edges.append(
                    {
                        "edge_id": hashlib.sha1(f"{record.record_id}:evidence:{target}".encode()).hexdigest()[:24],
                        "source_id": record.record_id,
                        "target_id": target,
                        "relation": "evidence",
                        "payload": ontology_edge_payload(
                            "declared",
                            [record.record_id, target],
                            record_content_checksum(record),
                            field="source_refs",
                        ),
                    }
                )
        self.store.upsert_ontology(nodes, edges)
        updated_health = self.store.health()
        manifest = self.store.get("manifests", "search") or {}
        source_signature = self.repository.source_signature()
        manifest.update(
            {
                "indexed_at": now_iso(),
                "record_count": int(updated_health.get("search_documents") or manifest.get("record_count") or 0),
                "chunk_count": int(updated_health.get("search_chunks") or manifest.get("chunk_count") or 0),
                "target_source_signature": source_signature,
                "index_schema_version": SEARCH_INDEX_SCHEMA_VERSION,
                "status": "ready" if finalize_manifest else "syncing",
                "sync_state": "ready" if finalize_manifest else "syncing",
                "embedding_provider": model_state.get("embedding_provider"),
                "embedding_model": model_state.get("embedding_model"),
                "dimensions": len(vectors[0]) if vectors else int(manifest.get("dimensions") or 0),
            }
        )
        if finalize_manifest:
            manifest["source_signature"] = source_signature
        self.store.put("manifests", "search", manifest)
        return {
            "status": "indexed",
            "indexed": [item.record_id for item in records],
            "missing": missing,
            "chunk_count": len(chunk_rows),
            "manifest": manifest,
        }

    def remove_records(self, record_ids: list[str], *, finalize_manifest: bool = False) -> dict[str, Any]:
        targets = {str(item) for item in record_ids if str(item).strip()}
        if not targets:
            return {"status": "unchanged", "removed": []}
        for chunk in self.store.list("search_chunks", limit=100_000):
            if str(chunk.get("record_id") or "") in targets:
                self.store.delete("search_chunks", str(chunk.get("chunk_id") or ""))
        for record_id in targets:
            self.store.delete("search_documents", record_id)
        self.store.remove_ontology_records(sorted(targets))
        manifest = self.store.get("manifests", "search") or {}
        health = self.store.health()
        signature = self.repository.source_signature()
        manifest.update(
            {
                "record_count": int(health.get("search_documents") or 0),
                "chunk_count": int(health.get("search_chunks") or 0),
                "target_source_signature": signature,
                "status": "ready" if finalize_manifest else "syncing",
                "sync_state": "ready" if finalize_manifest else "syncing",
                "index_schema_version": SEARCH_INDEX_SCHEMA_VERSION,
            }
        )
        if finalize_manifest:
            manifest["source_signature"] = signature
            manifest["indexed_at"] = now_iso()
        self.store.put("manifests", "search", manifest)
        return {"status": "removed", "removed": sorted(targets), "manifest": manifest}

    def finalize_incremental_index(self, *, expected_source_signature: str = "") -> dict[str, Any]:
        self.repository.invalidate_source_cache()
        signature = self.repository.source_signature()
        if expected_source_signature and signature != expected_source_signature:
            manifest = self.store.get("manifests", "search") or {}
            manifest.update(
                {
                    "status": "syncing",
                    "sync_state": "syncing",
                    "target_source_signature": signature,
                    "index_schema_version": SEARCH_INDEX_SCHEMA_VERSION,
                }
            )
            self.store.put("manifests", "search", manifest)
            return {"status": "source_changed", "source_signature": signature, "manifest": manifest}
        health = self.store.health()
        model_state = self.model.readiness()
        manifest = self.store.get("manifests", "search") or {}
        manifest.update(
            {
                "indexed_at": now_iso(),
                "record_count": int(health.get("search_documents") or 0),
                "chunk_count": int(health.get("search_chunks") or 0),
                "source_signature": signature,
                "target_source_signature": signature,
                "index_schema_version": SEARCH_INDEX_SCHEMA_VERSION,
                "status": "ready",
                "sync_state": "ready",
                "embedding_provider": model_state.get("embedding_provider"),
                "embedding_model": model_state.get("embedding_model"),
            }
        )
        self.store.put("manifests", "search", manifest)
        return {"status": "ready", "source_signature": signature, "manifest": manifest}

    def reconcile(self, principal: Principal) -> dict[str, Any]:
        model_state = self.model.readiness()
        store_state = self.store.health()
        if not model_state.get("embeddings") or store_state.get("mode") != "postgres" or not store_state.get("ready"):
            return {"status": "degraded", "reason": "embedding index dependencies are unavailable"}
        manifest = self.store.get("manifests", "search") or {}
        if manifest.get("index_schema_version") != SEARCH_INDEX_SCHEMA_VERSION:
            return self.reindex(principal)
        self.repository.invalidate_source_cache()
        target_signature = self.repository.source_signature()
        records = self.repository.authoritative_records(principal, include_drafts=False)
        records_by_id = {item.record_id: item for item in records}
        stored = {
            str(item.get("record_id") or ""): item
            for item in self.store.list("search_documents", limit=100_000)
            if str(item.get("source") or "") != "knowledge_candidate"
        }
        changed = [
            record_id
            for record_id, record in records_by_id.items()
            if str((stored.get(record_id) or {}).get("content_checksum") or "") != record_content_checksum(record)
        ]
        deleted = sorted(set(stored) - set(records_by_id))
        for offset in range(0, len(changed), 64):
            self.index_records(principal, changed[offset : offset + 64], finalize_manifest=False)
        if deleted:
            self.remove_records(deleted, finalize_manifest=False)
        finalized = self.finalize_incremental_index(expected_source_signature=target_signature)
        return {
            "status": str(finalized.get("status") or "ready"),
            "indexed": changed,
            "removed": deleted,
            "manifest": finalized.get("manifest") or {},
        }

    def reindex(self, principal: Principal) -> dict[str, Any]:
        model_state = self.model.readiness()
        store_state = self.store.health()
        if not model_state.get("embeddings"):
            raise RuntimeError("a real embedding model must be configured before reindex")
        if store_state.get("mode") != "postgres" or not store_state.get("ready"):
            raise RuntimeError("Postgres/pgvector must be ready before reindex")
        self.repository.invalidate_source_cache()
        indexed_source_signature = self.repository.source_signature()
        records = self.repository.authoritative_records(principal, include_drafts=False)
        records.extend(
            self.candidate_record(item)
            for item in self.store.list("knowledge_candidates", limit=100_000)
            if item.get("candidate_id") and item.get("status") in {"provisional", "reviewed"}
        )
        texts = [f"{item.title}\n{item.description}\n{item.text[:12000]}" for item in records]
        vectors: list[list[float]] = []
        for offset in range(0, len(texts), 64):
            vectors.extend(self.model.embed(texts[offset : offset + 64]))
        rows: list[dict[str, Any]] = []
        for record, vector, content in zip(records, vectors, texts):
            scope = "public"
            if record.visibility == "private":
                scope = f"private:{record.owner}"
            elif record.visibility == "team":
                scope = f"team:{record.team_id}"
            rows.append(
                {
                    "record_id": record.record_id,
                    "employee_scope": scope,
                    "kind": record.kind,
                    "title": record.title,
                    "source": record.source,
                    "authority": record.authority,
                    "content": content,
                    "metadata": {
                        "url": record.url,
                        "status": record.status,
                        "content_checksum": record_content_checksum(record),
                        **record.metadata,
                    },
                    "embedding": vector,
                }
            )
        chunk_rows = [chunk for record in records for chunk in chunks_for_record(record)]
        chunk_texts = [
            f"{item['title']}\n{item.get('heading') or ''}\n{item['content']}"
            for item in chunk_rows
        ]
        chunk_vectors: list[list[float]] = []
        for offset in range(0, len(chunk_texts), 64):
            chunk_vectors.extend(self.model.embed(chunk_texts[offset : offset + 64]))
        record_lookup = {item.record_id: item for item in records}
        for chunk, vector in zip(chunk_rows, chunk_vectors):
            record = record_lookup[str(chunk["record_id"])]
            scope = "public"
            if record.visibility == "private":
                scope = f"private:{record.owner}"
            elif record.visibility == "team":
                scope = f"team:{record.team_id}"
            chunk["employee_scope"] = scope
            chunk["embedding"] = vector

        readiness = self.model.readiness()
        manifest = {
            "indexed_at": now_iso(),
            "record_count": len(rows),
            "chunk_count": len(chunk_rows),
            "source_signature": indexed_source_signature,
            "target_source_signature": indexed_source_signature,
            "index_schema_version": SEARCH_INDEX_SCHEMA_VERSION,
            "status": "building",
            "sync_state": "syncing",
            "embedding_provider": readiness.get("embedding_provider"),
            "embedding_model": readiness.get("embedding_model"),
            "dimensions": len(vectors[0]) if vectors else 0,
        }
        self.store.replace_search_documents(rows, manifest)
        self.store.replace_search_chunks(chunk_rows)
        record_ids = {item.record_id for item in records}
        nodes = [
            {
                "node_id": item.record_id,
                "node_type": item.kind,
                "payload": {
                    "title": item.title,
                    "url": item.url,
                    "visibility": item.visibility,
                    "owner": item.owner,
                    "team_id": item.team_id,
                    "authority": item.authority,
                    "aliases": item.metadata.get("aliases") or [],
                },
            }
            for item in records
        ]
        edges: list[dict[str, Any]] = []
        name_lookup: dict[str, str] = {}
        alias_node_ids: set[str] = set()

        def lookup_key(value: str) -> str:
            return " ".join(sorted(normalize_tokens(value)))

        for record in records:
            names = [record.record_id, record.record_id.rsplit(":", 1)[-1], record.title, str(record.metadata.get("term") or "")]
            aliases = record.metadata.get("aliases") or []
            if isinstance(aliases, list):
                names.extend(str(alias) for alias in aliases)
            for name in names:
                key = lookup_key(name)
                if key:
                    name_lookup.setdefault(key, record.record_id)
            if record.kind != "dictionary" or not isinstance(aliases, list):
                continue
            for alias in aliases:
                label = str(alias or "").strip()
                if not label:
                    continue
                alias_id = "alias:" + hashlib.sha256(f"{record.record_id}:{label.lower()}".encode()).hexdigest()[:24]
                if alias_id in alias_node_ids:
                    continue
                alias_node_ids.add(alias_id)
                nodes.append(
                    {
                        "node_id": alias_id,
                        "node_type": "dictionary_alias",
                        "payload": {
                            "label": label,
                            "visibility": record.visibility,
                            "owner": record.owner,
                            "team_id": record.team_id,
                        },
                    }
                )
                edges.append(
                    {
                        "edge_id": hashlib.sha256(f"{alias_id}:alias_of:{record.record_id}".encode()).hexdigest()[:24],
                        "source_id": alias_id,
                        "target_id": record.record_id,
                        "relation": "alias_of",
                        "payload": ontology_edge_payload(
                            "declared",
                            [alias_id, record.record_id],
                            record_content_checksum(record),
                            field="aliases",
                        ),
                    }
                )

        def resolve_target(value: str) -> str:
            candidates = [value, f"action:{value}", f"event:{value}", f"workflow:{value}"]
            target = next((candidate for candidate in candidates if candidate in record_ids), "")
            return target or name_lookup.get(lookup_key(value), "")

        for record in records:
            workflow = record.metadata.get("workflow") if isinstance(record.metadata.get("workflow"), dict) else {}
            stages = workflow.get("stages") if isinstance(workflow.get("stages"), list) else []
            tasks = record.metadata.get("tasks") if isinstance(record.metadata.get("tasks"), list) else []
            for index, raw_stage in enumerate([*stages, *tasks]):
                if not isinstance(raw_stage, dict):
                    continue
                stage_key = str(raw_stage.get("id") or raw_stage.get("task_id") or f"stage-{index + 1}")
                stage_id = "task:" + hashlib.sha256(f"{record.record_id}:{stage_key}".encode()).hexdigest()[:24]
                nodes.append(
                    {
                        "node_id": stage_id,
                        "node_type": "task",
                        "payload": {
                            "title": str(raw_stage.get("name") or raw_stage.get("title") or stage_key),
                            "parent_ref": record.record_id,
                            "task_key": stage_key,
                            "visibility": record.visibility,
                            "owner": record.owner,
                            "team_id": record.team_id,
                            "execution_mode": raw_stage.get("execution_mode") or raw_stage.get("mode") or "",
                        },
                    }
                )
                edges.append(
                    {
                        "edge_id": hashlib.sha256(f"{record.record_id}:has_task:{stage_id}".encode()).hexdigest()[:24],
                        "source_id": record.record_id,
                        "target_id": stage_id,
                        "relation": "has_task",
                        "payload": ontology_edge_payload(
                            "extracted",
                            [record.record_id, stage_id],
                            record_content_checksum(record),
                            order=index,
                        ),
                    }
                )
                stage_relations = {
                    "entry_event": "uses_event",
                    "event_types": "uses_event",
                    "emits_event": "emits_event",
                    "automated_actions": "uses_action",
                    "manual_actions": "uses_action",
                    "action_refs": "uses_action",
                    "skill_refs": "uses_skill",
                    "evidence_refs": "requires_evidence",
                    "outputs": "produces",
                }
                for field, relation in stage_relations.items():
                    raw_values = raw_stage.get(field)
                    values = raw_values if isinstance(raw_values, list) else [raw_values] if raw_values else []
                    for raw_value in values:
                        value = str(raw_value.get("ref") or raw_value.get("boi_id") or "") if isinstance(raw_value, dict) else str(raw_value or "")
                        target = resolve_target(value)
                        if not target:
                            continue
                        edges.append(
                            {
                                "edge_id": hashlib.sha256(f"{stage_id}:{relation}:{target}".encode()).hexdigest()[:24],
                                "source_id": stage_id,
                                "target_id": target,
                                "relation": relation,
                                "payload": ontology_edge_payload(
                                    "extracted",
                                    [record.record_id, stage_id, target],
                                    record_content_checksum(record),
                                    field=field,
                                    parent_ref=record.record_id,
                                ),
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
        }
        for record in records:
            for field, relation in relation_fields.items():
                raw_values = record.metadata.get(field)
                values = raw_values if isinstance(raw_values, list) else [raw_values] if raw_values else []
                for raw_value in values:
                    value = str(raw_value.get("ref") or raw_value.get("boi_id") or "") if isinstance(raw_value, dict) else str(raw_value or "")
                    target = resolve_target(value)
                    if not target:
                        continue
                    edge_id = hashlib.sha256(f"{record.record_id}:{relation}:{target}".encode()).hexdigest()[:24]
                    edges.append(
                        {
                            "edge_id": edge_id,
                            "source_id": record.record_id,
                            "target_id": target,
                            "relation": relation,
                            "payload": ontology_edge_payload(
                                "declared",
                                [record.record_id, target],
                                record_content_checksum(record),
                                field=field,
                            ),
                        }
                    )
        unique_edges = {str(edge["edge_id"]): edge for edge in edges}
        edges = list(unique_edges.values())
        self.store.replace_ontology(nodes, edges)
        manifest["ontology_nodes"] = len(nodes)
        manifest["ontology_edges"] = len(edges)
        self.repository.invalidate_source_cache()
        current_source_signature = self.repository.source_signature()
        source_changed = current_source_signature != indexed_source_signature
        manifest["target_source_signature"] = current_source_signature
        manifest["status"] = "syncing" if source_changed else "ready"
        manifest["sync_state"] = "syncing" if source_changed else "ready"
        self.store.put("manifests", "search", manifest)
        return manifest
