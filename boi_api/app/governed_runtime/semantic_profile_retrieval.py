"""Domain-neutral hybrid retrieval over an ACL-filtered semantic bundle."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from .semantic_profile_loader import LoadedProfileEntry, SemanticContextBundle
from .semantic_authority import SemanticAuthorityFields, semantic_authority_values


_TOKEN_RE = re.compile(r"[\w가-힣]+", re.UNICODE)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(token.casefold() for token in _TOKEN_RE.findall(value)))


def _digest(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()


class SemanticRetrievalError(RuntimeError):
    pass


class RetrievalDocument(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str
    kind: str
    search_text: str
    revision_digest: str = ""


class RetrievalCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str
    kind: str
    revision_id: str
    revision_digest: str
    rank: int
    ordering_score: float
    methods: tuple[Literal["lexical", "alias", "embedding", "graph_expansion", "dependency_closure", "authorized_scope"], ...]
    evidence_resources: tuple[str, ...]


class GraphExpansionEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    from_entry_id: str
    to_entry_id: str
    relation: Literal["logical_dependency"] = "logical_dependency"


class RetrievalReceipt(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    question_digest: str
    active_release_digest: str | None
    principal_id: str
    purpose: str
    acl_projection_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    catalog_snapshot_digest: str
    schema_digest: str
    capability_digest: str
    candidates: tuple[RetrievalCandidate, ...]
    graph_expansion_edges: tuple[GraphExpansionEdge, ...]
    mapping_revision_ids: tuple[str, ...]
    excluded_revision_ids: tuple[str, ...]
    withheld_logical_ids: tuple[str, ...]
    retrieval_index_digest: str
    semantic_bundle_digest: str
    methods_executed: tuple[str, ...]
    # Empty only for historical lexical-only receipts. Production profile
    # assembly requires and supplies a content-addressed local provider.
    embedding_identity_digest: str = ""
    embedding_index_diagnostics: dict[str, object] = Field(default_factory=dict)
    decision_status: Literal["NOT_A_VALIDATION_DECISION"] = "NOT_A_VALIDATION_DECISION"
    receipt_digest: str


EmbeddingProvider = Callable[[str, tuple[RetrievalDocument, ...]], dict[str, float]]


class HybridSemanticRetriever:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider | None = None,
        embedding_identity_digest: str = "",
        policy_version: str = "dependency-v1",
    ):
        if policy_version not in {"dependency-v1", "query-local-v2", "object-attributes-v3", "multi-object-v4", "object-inventory-v5", "path-inventory-v6", "scope-inventory-v7"}:
            raise ValueError("RETRIEVAL_POLICY_VERSION_UNSUPPORTED")
        self.policy_version = policy_version
        self.embedding_provider = embedding_provider
        self.embedding_identity_digest = embedding_identity_digest
        if embedding_provider is not None and not embedding_identity_digest:
            identity = getattr(embedding_provider, "identity_digest", "")
            self.embedding_identity_digest = str(identity)

    @staticmethod
    def _logical_text(entry: LoadedProfileEntry) -> tuple[str, tuple[str, ...]]:
        payload = entry.payload
        name = str(payload.get("name") or payload.get("term") or entry.entry_id)
        description = str(payload.get("description") or "")
        aliases = tuple(str(value) for value in payload.get("aliases") or ())
        # This text is discovery only; it cannot establish semantic equivalence.
        # Preserve conditions and negation exactly, including case-sensitive units.
        meaning = {key: payload[key] for key in (
            "term", "definition", "applicability", "exceptions", "quantity_kind",
            "logical_role", "unit_ref", "time_semantics", "semantic_contract",
        ) if key in payload}
        text = " ".join((entry.entry_id, name, description)).strip()
        if meaning:
            text += " " + json.dumps(meaning, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return text, aliases

    def _retrieval_entries(self, bundle: SemanticContextBundle) -> tuple[LoadedProfileEntry, ...]:
        unavailable = set(bundle.unavailable_logical_ids)
        return tuple(entry for entry in (*bundle.domain_entries, *bundle.query_entries)
                     if entry.entry_id not in unavailable
                     and (self.policy_version == "dependency-v1" or entry.category == "domain"))

    def documents_for_bundle(self, bundle: SemanticContextBundle) -> tuple[RetrievalDocument, ...]:
        """The exact logical projection shared by explicit indexing and retrieval."""
        return tuple(RetrievalDocument(
            entry_id=entry.entry_id, kind=str(entry.payload.get("kind") or entry.category),
            search_text=self._logical_text(entry)[0] + " " + " ".join(self._logical_text(entry)[1]),
            revision_digest=entry.revision_digest,
        ) for entry in self._retrieval_entries(bundle))

    def index_bundle(self, bundle: SemanticContextBundle) -> dict:
        """Explicit ingestion/backfill hook. Question retrieval never calls it."""
        indexer = getattr(self.embedding_provider, "index_documents", None)
        if not callable(indexer):
            raise SemanticRetrievalError("EMBEDDING_DOCUMENT_INDEX_UNSUPPORTED")
        return indexer(self.documents_for_bundle(bundle))

    @staticmethod
    def _dependencies(entry: LoadedProfileEntry) -> set[str]:
        payload = entry.payload
        collected: list[object] = []
        for key in (
            "depends_on", "identity_property_ref", "properties", "property_refs",
            "logical_grain", "left_property_ref",
            "right_property_ref", "numerator_ref", "denominator_ref",
            "left_property_refs", "right_property_refs", "relationship_identity_ref",
            "unit_property_ref", "value_type_ref", "unit_ref",
        ):
            if key in payload:
                collected.append(payload[key])
        plan = payload.get("logical_plan")
        if isinstance(plan, dict) and "depends_on" in plan:
            collected.append(plan["depends_on"])
        conversions = payload.get("unit_conversions")
        if isinstance(conversions, list):
            collected.extend(
                item.get("from_unit_ref")
                for item in conversions
                if isinstance(item, dict) and item.get("from_unit_ref")
            )
        result: set[str] = set()
        from .latest_selection_contract import latest_contract_dependencies
        result.update(latest_contract_dependencies(payload))
        for value in collected:
            if isinstance(value, str):
                result.add(value)
            elif isinstance(value, list):
                result.update(str(item) for item in value)
        return result

    @staticmethod
    def _query_dependencies(entry: LoadedProfileEntry) -> set[str]:
        # An object's full property inventory is discoverable metadata, not a
        # requirement to answer every question about that object. Ownership,
        # identity, units and semantic operands remain hard dependencies.
        payload = dict(entry.payload)
        if payload.get("kind") == "ObjectType":
            payload.pop("properties", None)
            payload.pop("property_refs", None)
        result = HybridSemanticRetriever._dependencies(entry.model_copy(update={"payload": payload}))
        result.update(str(payload[key]) for key in (
            "owner_ref", "left_endpoint_ref", "right_endpoint_ref"
        ) if payload.get(key))
        return result

    @staticmethod
    def _query_path_refs(selected: set[str], by_id: dict[str, LoadedProfileEntry]) -> set[str]:
        endpoints = set()
        for ref in selected:
            item = by_id[ref].payload
            if item.get("kind") == "ObjectType":
                endpoints.add(ref)
            elif item.get("owner_ref") in by_id:
                endpoints.add(str(item["owner_ref"]))
        adjacency: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for ref, entry in by_id.items():
            item = entry.payload
            if item.get("kind") != "RelationType":
                continue
            left, right = item.get("left_endpoint_ref"), item.get("right_endpoint_ref")
            if left in by_id and right in by_id:
                adjacency[str(left)].append((str(right), ref))
                adjacency[str(right)].append((str(left), ref))
        found: set[str] = set()
        # Discover all equal shortest logical paths, never choose the first path
        # as authoritative. Binder/resolver still owns ambiguity and permission.
        for start in sorted(endpoints):
            for finish in sorted(endpoints):
                if start >= finish:
                    continue
                frontier = [(start, (start,), ())]
                for _depth in range(3):
                    following = []
                    winners = []
                    for node, visited, refs in frontier:
                        for neighbor, ref in sorted(adjacency[node]):
                            if neighbor in visited:
                                continue
                            path = (*refs, ref)
                            if neighbor == finish:
                                winners.append(path)
                            else:
                                following.append((neighbor, (*visited, neighbor), path))
                    if winners:
                        found.update(ref for path in winners for ref in path)
                        break
                    frontier = following
        return found

    @staticmethod
    def _query_tokens(value: str) -> tuple[str, ...]:
        separated = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
        separated = re.sub(r"([A-Za-z0-9])([가-힣])|([가-힣])([A-Za-z0-9])", r"\1\3 \2\4", separated)
        return _tokens(separated)

    @classmethod
    def _mentioned_objects(cls, question: str, objects: list, by_id: dict) -> list:
        # Exact logical names/aliases only, not descriptions or physical names.
        # Longest phrase wins over a nested short alias; semantic ambiguity
        # still belongs to the resolver. Korean suffixes do not hide a mention.
        text = " ".join(cls._query_tokens(question))
        matches = []
        for item in objects:
            payload = by_id[item[1]].payload
            for label in (payload.get("name") or item[1], *payload.get("aliases", [])):
                phrase = " ".join(cls._query_tokens(str(label)))
                if not phrase:
                    continue
                for match in re.finditer(r"(?<!\w)" + re.escape(phrase) + r"(?![a-z0-9_])", text):
                    matches.append((match.start(), match.end(), item[1]))
        full_mentions = [(start, end, ref) for start, end, ref in matches if not any(
            other_ref != ref and other_start <= start and other_end >= end
            and (other_start < start or other_end > end)
            for other_start, other_end, other_ref in matches)]
        selected = {ref for _start, _end, ref in full_mentions}
        remaining_text = list(text)
        for start, end, _ref in full_mentions:
            remaining_text[start:end] = ' ' * (end - start)
        # Corporate labels may contain descriptive words absent from a question.
        # Use rare name/alias tokens as discovery anchors (never descriptions).
        # This selects context only; it does not choose an entity in the intent.
        token_owners: dict[str, set[str]] = defaultdict(set)
        for item in objects:
            payload = by_id[item[1]].payload
            for label in (payload.get("name") or item[1], *payload.get("aliases", [])):
                for token in cls._query_tokens(str(label)):
                    if len(token) >= 3 or (len(token) >= 2 and re.search(r"[가-힣]", token)):
                        token_owners[token].add(item[1])
        # Do not rediscover unrelated labels from words already consumed by an
        # exact phrase. Identical full-label alternatives remain available.
        for token in cls._query_tokens(''.join(remaining_text)):
            owners = token_owners.get(token, set())
            if owners and len(owners) <= max(1, len(objects) // 2):
                selected.update(owners)
        return [item for item in objects if item[1] in selected]

    def retrieve(
        self, question: str, *, bundle: SemanticContextBundle, top_k: int = 8,
        max_expanded_entries: int = 64,
    ) -> RetrievalReceipt:
        if not question.strip():
            raise SemanticRetrievalError("QUESTION_REQUIRED")
        if top_k < 1:
            raise SemanticRetrievalError("TOP_K_MUST_BE_POSITIVE")
        if max_expanded_entries < top_k:
            raise SemanticRetrievalError("RETRIEVAL_CONTEXT_BUDGET_INVALID")

        entries = self._retrieval_entries(bundle)
        by_id = {entry.entry_id: entry for entry in entries}
        if self.policy_version=='scope-inventory-v7' and len(entries)>max_expanded_entries:
            raise SemanticRetrievalError('RETRIEVAL_AUTHORIZED_SCOPE_BUDGET_EXCEEDED')
        documents = self.documents_for_bundle(bundle)
        embedding_scores = (self.embedding_provider(question, documents)
            if self.embedding_provider and self.policy_version!='scope-inventory-v7' else {})
        embedding_diagnostics = (getattr(self.embedding_provider, 'last_retrieval_diagnostics', {})
            if self.embedding_provider and self.policy_version != 'scope-inventory-v7' else {})
        if not isinstance(embedding_diagnostics, dict):
            embedding_diagnostics = {}
        unknown_embedding_ids = set(embedding_scores) - set(by_id)
        if unknown_embedding_ids:
            raise SemanticRetrievalError("EMBEDDING_RESULT_OUTSIDE_ACTIVE_INDEX")
        if any(not isinstance(score, (int, float)) or not math.isfinite(score) or score < 0 or score > 1
               for score in embedding_scores.values()):
            raise SemanticRetrievalError("EMBEDDING_SCORE_INVALID")

        tokenize = self._query_tokens if self.policy_version != "dependency-v1" else _tokens
        question_tokens = set(tokenize(question))
        scored: list[tuple[float, str, set[str]]] = []
        for entry in entries:
            logical_text, aliases = self._logical_text(entry)
            lexical_tokens = set(tokenize(logical_text))
            alias_tokens = set(tokenize(" ".join(aliases)))
            lexical = len(question_tokens & lexical_tokens) / max(1, len(question_tokens))
            alias = len(question_tokens & alias_tokens) / max(1, len(question_tokens))
            embedding = float(embedding_scores.get(entry.entry_id, 0.0))
            score = round(0.4 * lexical + 0.3 * alias + 0.3 * embedding, 12)
            methods: set[str] = set()
            if lexical:
                methods.add("lexical")
            if alias:
                methods.add("alias")
            if entry.entry_id in embedding_scores:
                methods.add("embedding")
            if score > 0:
                scored.append((score, entry.entry_id, methods))
        scored.sort(key=lambda item: (-item[0], item[1]))
        seeds = scored[:top_k]
        if self.policy_version=='scope-inventory-v7':
            # An explicitly selected, authorized bounded scope can be supplied
            # in full. Zero similarity is not evidence that a definition is
            # irrelevant, particularly across languages. This selects context
            # only and makes no match, binding or execution decision.
            seeds=[(0.0,ref,{'authorized_scope'}) for ref in sorted(by_id)]
        if self.policy_version in {"object-attributes-v3", "multi-object-v4", "object-inventory-v5", "path-inventory-v6"}:
            # Entity/relationship descriptions must not consume every seed slot
            # while hiding the attributes needed to express the question. This
            # explicit preview policy allocates a bounded inventory to the two
            # highest-ranked objects; large inventories are round-robin ranked.
            # No domain names, physical identifiers or question families occur.
            objects = [s for s in scored if by_id[s[1]].payload.get("kind") == "ObjectType"][:min(2, top_k)]
            if self.policy_version in {"multi-object-v4", "object-inventory-v5", "path-inventory-v6"}:
                ranked_objects = [s for s in scored if by_id[s[1]].payload.get("kind") == "ObjectType"]
                mentioned = self._mentioned_objects(question, ranked_objects, by_id)
                if len(mentioned) > min(3, top_k):
                    raise SemanticRetrievalError("RETRIEVAL_OBJECT_BUDGET_EXCEEDED")
                objects = mentioned or ranked_objects[:min(2, top_k)]
            seeds = list(objects)
            inventories = [[s for s in scored if by_id[s[1]].payload.get("kind") == "PropertyDefinition"
                            and by_id[s[1]].payload.get("owner_ref") == obj[1]] for obj in objects]
            seed_budget = 18 if self.policy_version == "multi-object-v4" else 24
            remaining = min(seed_budget, max(0, max_expanded_entries - len(objects) - 4))
            while remaining and any(inventories):
                for inventory in inventories:
                    if inventory and remaining:
                        seeds.append(inventory.pop(0))
                        remaining -= 1
            if self.policy_version in {'object-inventory-v5', 'path-inventory-v6'}:
                # Expose the complete bounded inventory for discovered objects,
                # including zero-score attributes. Ranking is not proof that a
                # property is unnecessary to express the user's question.
                owners = {obj[1] for obj in objects}
                scored_map = {item[1]: item for item in scored}
                owned = sorted(ref for ref, item in by_id.items()
                               if item.payload.get('kind') == 'PropertyDefinition'
                               and item.payload.get('owner_ref') in owners)
                seeds = list(objects) + [scored_map.get(ref, (0.0, ref, {'dependency_closure'})) for ref in owned]
            # Metrics/terms can be requested independently of an object. They
            # retain ranked discovery rather than being guessed from labels.
            seeds.extend(s for s in scored[:top_k] if by_id[s[1]].payload.get("kind") in {"Metric", "Term", "Rule"})
            if not seeds:
                seeds = [s for s in scored if by_id[s[1]].payload.get("kind") != "RelationType"][:top_k]

        reverse: dict[str, set[str]] = defaultdict(set)
        dependencies_by_id: dict[str, set[str]] = {}
        for entry in entries:
            dependencies = (
                self._query_dependencies(entry) if self.policy_version != "dependency-v1"
                else self._dependencies(entry)
            ) & set(by_id)
            dependencies_by_id[entry.entry_id] = dependencies
            for dependency in dependencies:
                reverse[dependency].add(entry.entry_id)

        selected = {entry_id for _score, entry_id, _methods in seeds}
        method_map = {entry_id: set(methods) for _score, entry_id, methods in seeds}
        score_map = {entry_id: score for score, entry_id, _methods in seeds}
        if self.policy_version != "dependency-v1":
            for ref in self._query_path_refs(selected, by_id):
                selected.add(ref)
                method_map.setdefault(ref, set()).add("graph_expansion")
                score_map.setdefault(ref, 0.0)
            if len(selected) > max_expanded_entries:
                raise SemanticRetrievalError("RETRIEVAL_CONTEXT_BUDGET_EXCEEDED")
        queue = list(sorted(selected))
        used_edges: set[tuple[str, str]] = set()
        while queue:
            current = queue.pop(0)
            if self.policy_version == 'path-inventory-v6' and by_id[current].payload.get('kind') == 'ObjectType':
                # Logical transit objects can own sequence, role, value or time
                # semantics just as named roots do. Ranking alone cannot drop
                # those fields. The same ACL/availability and hard budget apply.
                inventory = sorted(ref for ref, entry in by_id.items()
                    if entry.payload.get('kind') == 'PropertyDefinition'
                    and entry.payload.get('owner_ref') == current)
                for ref in inventory:
                    used_edges.add((ref, current))
                    method_map.setdefault(ref, set()).add('dependency_closure')
                    score_map.setdefault(ref, 0.0)
                    if ref not in selected:
                        selected.add(ref)
                        if len(selected) > max_expanded_entries:
                            raise SemanticRetrievalError('RETRIEVAL_CONTEXT_BUDGET_EXCEEDED')
                        queue.append(ref)
            for dependency in sorted(dependencies_by_id.get(current, ())):
                used_edges.add((current, dependency))
                method_map.setdefault(dependency, set()).update(("dependency_closure", "graph_expansion"))
                score_map.setdefault(dependency, 0.0)
                if dependency not in selected:
                    selected.add(dependency)
                    if len(selected) > max_expanded_entries:
                        raise SemanticRetrievalError("RETRIEVAL_CONTEXT_BUDGET_EXCEEDED")
                    queue.append(dependency)
            for neighbor in sorted(reverse.get(current, ()) if self.policy_version == "dependency-v1" else ()):
                used_edges.add((neighbor, current))
                method_map.setdefault(neighbor, set()).add("graph_expansion")
                score_map.setdefault(neighbor, 0.0)
                if neighbor not in selected:
                    selected.add(neighbor)
                    if len(selected) > max_expanded_entries:
                        raise SemanticRetrievalError("RETRIEVAL_CONTEXT_BUDGET_EXCEEDED")

        ordered_ids = [entry_id for _score, entry_id, _methods in seeds]
        ordered_ids.extend(sorted(selected - set(ordered_ids)))
        candidates = tuple(
            RetrievalCandidate(
                entry_id=entry_id,
                kind=str(by_id[entry_id].payload.get("kind") or by_id[entry_id].category),
                revision_id=by_id[entry_id].revision_id,
                revision_digest=by_id[entry_id].revision_digest,
                rank=index,
                ordering_score=score_map[entry_id],
                methods=tuple(sorted(method_map[entry_id])),
                evidence_resources=by_id[entry_id].evidence_resources,
            )
            for index, entry_id in enumerate(ordered_ids, start=1)
        )
        mapping_ids = tuple(sorted(
            entry.revision_id for entry in bundle.mapping_entries
            if str(entry.payload.get("domain_ref")) in selected
        ))
        edges = tuple(
            GraphExpansionEdge(from_entry_id=source, to_entry_id=target)
            for source, target in sorted(used_edges)
        )
        methods_executed = ("lexical", "alias", "ontology_graph", "dependency_closure")
        if (self.embedding_provider and self.policy_version != 'scope-inventory-v7'
                and (not embedding_diagnostics or embedding_diagnostics.get('query_embedding_calls', 0) > 0)):
            methods_executed = (*methods_executed, "embedding")
        if self.policy_version != "dependency-v1":
            methods_executed = (*methods_executed, self.policy_version)
        receipt_values = {
            "question_digest": _digest(question),
            **semantic_authority_values(bundle),
            "principal_id": bundle.principal_id,
            "purpose": bundle.purpose,
            "acl_projection_digest": bundle.acl_projection_digest,
            "domain_profile_digest": bundle.domain_profile_digest,
            "mapping_profile_digest": bundle.mapping_profile_digest,
            "query_profile_digest": bundle.query_profile_digest,
            "catalog_snapshot_digest": bundle.catalog_snapshot_digest,
            "schema_digest": bundle.schema_digest,
            "capability_digest": bundle.capability_digest,
            "candidates": candidates,
            "graph_expansion_edges": edges,
            "mapping_revision_ids": mapping_ids,
            "excluded_revision_ids": bundle.excluded_revision_ids,
            "withheld_logical_ids": tuple(sorted(bundle.unavailable_logical_ids)),
            "retrieval_index_digest": bundle.retrieval_index_digest,
            "semantic_bundle_digest": bundle.bundle_digest,
            "methods_executed": methods_executed,
            "embedding_identity_digest": self.embedding_identity_digest,
            "embedding_index_diagnostics": embedding_diagnostics,
            "decision_status": "NOT_A_VALIDATION_DECISION",
        }
        digest_values = {
            **receipt_values,
            **({'reviewed_definition_authority':bundle.reviewed_definition_authority.model_dump(mode='json')}
                if bundle.reviewed_definition_authority is not None else {}),
            "candidates": tuple(item.model_dump(mode="json") for item in candidates),
            "graph_expansion_edges": tuple(item.model_dump(mode="json") for item in edges),
        }
        return RetrievalReceipt(**receipt_values, receipt_digest=_digest(digest_values))
