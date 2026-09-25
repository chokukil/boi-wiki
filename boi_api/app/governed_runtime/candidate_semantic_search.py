"""Cold deterministic search over candidate-only Domain/Mapping evidence."""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import hashlib
import json
import re
from typing import Iterable, Mapping

from .bulk_migration_execution import CandidateFreezeReceipt
from .cardinality_query_shape import RelationshipContract


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _tokens(value: str) -> tuple[str, ...]:
    output: list[str] = []
    for token in re.findall(r"[a-z0-9_]+|[가-힣]+", value.casefold()):
        if re.fullmatch(r"[가-힣]+", token):
            for suffix in ("으로", "에서", "에게", "까지", "부터", "대로", "은", "는", "이", "가", "을", "를", "에", "의", "과", "와", "도", "로"):
                if token.endswith(suffix) and len(token) - len(suffix) >= 2:
                    token = token[: -len(suffix)]
                    break
        if len(token) > 1:
            output.append(token)
    return tuple(output)


def _camel_tokens(value: str) -> tuple[str, ...]:
    separated = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    return _tokens(separated)


def _head_aliases(candidate: Mapping[str, object], evidence: Mapping[str, object]) -> set[str]:
    aliases: set[str] = set()
    name_tokens = list(_camel_tokens(str(candidate.get("name") or "")))
    while name_tokens and name_tokens[-1] in {"setting", "record", "master", "information"}:
        name_tokens.pop()
    if name_tokens:
        aliases.add(name_tokens[-1])
    structured = evidence.get("structured_evidence")
    if isinstance(structured, Mapping):
        display_tokens = list(_tokens(str(structured.get("display_name") or "")))
        while display_tokens and display_tokens[-1] in {"기준정보", "설정", "정보"}:
            display_tokens.pop()
        if display_tokens:
            aliases.add(display_tokens[-1])
    return aliases


def _stable_ids(evidence: Mapping[str, object]) -> frozenset[str]:
    structured = evidence.get("structured_evidence")
    if not isinstance(structured, Mapping):
        return frozenset()
    return frozenset(
        str(column.get("stable_id") or "")
        for column in structured.get("columns") or ()
        if isinstance(column, Mapping) and str(column.get("stable_id") or "")
    )


def _semantic_evidence_supported(evidence: Mapping[str, object]) -> bool:
    structured = evidence.get("structured_evidence")
    if not isinstance(structured, Mapping):
        return False
    descriptions = [
        str(structured.get("display_name") or ""),
        str(structured.get("description") or ""),
    ]
    for column in structured.get("columns") or ():
        if isinstance(column, Mapping):
            descriptions.extend(
                (
                    str(column.get("display_name") or ""),
                    str(column.get("description") or ""),
                )
            )
    return any(value.strip() for value in descriptions)


def rebind_domain_candidate_evidence_by_stable_ids(
    *,
    candidates: Iterable[Mapping[str, object]],
    prior_evidence_spans: Iterable[Mapping[str, object]],
    current_evidence_spans: Iterable[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    """Rebind evidence revisions after a physical rename without semantic inference."""

    prior = {str(item.get("evidence_span_ref") or ""): dict(item) for item in prior_evidence_spans}
    current_by_ids: dict[frozenset[str], list[str]] = {}
    for item in current_evidence_spans:
        normalized = dict(item)
        ids = _stable_ids(normalized)
        if ids:
            current_by_ids.setdefault(ids, []).append(
                str(normalized.get("evidence_span_ref") or "")
            )
    rebound: list[dict[str, object]] = []
    for raw_candidate in candidates:
        candidate = dict(raw_candidate)
        refs = tuple(str(item) for item in candidate.get("evidence_span_refs") or ())
        next_refs: list[str] = []
        for ref in refs:
            ids = _stable_ids(prior.get(ref, {}))
            matches = current_by_ids.get(ids, []) if ids else []
            if len(matches) != 1:
                raise ValueError(f"STABLE_ID_EVIDENCE_REBIND_UNRESOLVED:{ref}")
            next_refs.append(matches[0])
        candidate["evidence_span_refs"] = next_refs
        rebound.append(candidate)
    return tuple(rebound)


@dataclass(frozen=True)
class CandidateSearchReceipt:
    receipt_version: str
    question_digest: str
    metadata_snapshot_digest: str
    catalog_snapshot_digest: str
    schema_snapshot_digest: str
    active_concept_index_digest: str
    deterministic_retriever_digest: str
    retrieved_concept_refs: tuple[str, ...]
    retrieved_evidence_span_refs: tuple[str, ...]
    selected_dependency_closure: tuple[str, ...]
    excluded_unrelated_concept_refs: tuple[str, ...]
    literal_terms: tuple[str, ...]
    semantic_operators: tuple[str, ...]
    unresolved_terms: tuple[str, ...]
    ambiguity_codes: tuple[str, ...]
    clarification_required: bool
    prefreeze_oracle_access_count: int
    registered_query_spec_access_count: int
    candidate_search_result_digest: str


def build_candidate_search_receipt(
    *,
    question: str,
    metadata_snapshot_digest: str,
    catalog_snapshot_digest: str,
    schema_snapshot_digest: str,
    active_concept_index_digest: str,
    deterministic_retriever_digest: str,
    domain_candidates: Iterable[Mapping[str, object]],
    evidence_spans: Iterable[Mapping[str, object]],
    object_mappings: Iterable[Mapping[str, object]],
    relationships: Iterable[RelationshipContract],
) -> CandidateSearchReceipt:
    from boi_api.app.governed_runtime.semantic_selection_guard import reject_unstructured_selection
    reject_unstructured_selection()


def freeze_candidate_search_closure(
    *,
    candidate_digest: str,
    search_receipts: Iterable[CandidateSearchReceipt],
    allowed_input_refs: Iterable[str],
    denied_oracle_refs: Iterable[str],
    closure_digests: Mapping[str, str],
    generator_code_digest: str,
) -> CandidateFreezeReceipt:
    receipts = tuple(search_receipts)
    if not receipts:
        raise ValueError("CANDIDATE_SEARCH_RECEIPT_REQUIRED")
    search_plan_digest = _digest(
        {
            "contract": "boi/candidate-search-plan-closure@1.0.0",
            "receipt_digests": [
                item.candidate_search_result_digest for item in receipts
            ],
            "selected_dependency_closures": [
                list(item.selected_dependency_closure) for item in receipts
            ],
        }
    )
    return CandidateFreezeReceipt.create(
        candidate_digest=candidate_digest,
        logical_plan_digest=search_plan_digest,
        allowed_input_refs=allowed_input_refs,
        denied_oracle_refs=denied_oracle_refs,
        closure_digests=closure_digests,
        generator_code_digest=generator_code_digest,
    )
