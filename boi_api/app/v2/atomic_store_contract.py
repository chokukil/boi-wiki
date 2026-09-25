"""Bounded additive CAS contract for the existing migration store, not a SOT.

Only application-service callers resolve owner/ACL authority. This primitive
provides all-or-nothing writes and exact expected-state comparison, not approval.
Canonical projection and active/Release collections are deliberately excluded.
"""
from dataclasses import dataclass
import json
from typing import Any, Iterable

MAX_ATOMIC_WRITES = 1000


MIGRATION_COLLECTIONS = (
    'atomic_knowledge_reference_guards',
    'bulk_migration_projects', 'bulk_migration_runs', 'bulk_migration_shards',
    'bulk_migration_task_packages', 'bulk_migration_candidates', 'bulk_migration_receipts',
    'bulk_migration_checkpoints', 'bulk_migration_approvals', 'bulk_migration_idempotency',
    'bulk_migration_invocations', 'bulk_migration_manifests', 'bulk_migration_stage_results',
    'bulk_migration_source_artifacts', 'bulk_migration_catalog_snapshots',
    'bulk_migration_concept_indexes', 'bulk_migration_evidence_spans',
    'bulk_migration_model_invocations', 'bulk_migration_release_proposals',
    'bulk_migration_candidate_previews', 'bulk_migration_freeze_receipts',
    'bulk_migration_independent_evaluations', 'bulk_migration_service_stage_results',
    'bulk_migration_source_profiles', 'bulk_migration_source_outbox',
    'source_display_names',
    'bulk_migration_semantic_templates', 'bulk_migration_semantic_cache',
    'bulk_migration_semantic_cache_receipts', 'bulk_migration_semantic_cache_access',
    'ontology_migration_jobs', 'agent_task_packages', 'agent_task_idempotency', 'task_runs',
    'domain_knowledge_assets', 'domain_asset_heads', 'domain_asset_idempotency',
    'domain_context_deliveries', 'domain_asset_catalogs',
    'domain_tool_invocations', 'domain_tool_receipts', 'domain_work_completions',
    'native_formula_executions', 'database_native_bindings',
    'native_composition_results',
    'knowledge_publication_scopes', 'knowledge_publication_manifests',
    'knowledge_projection_outbox', 'knowledge_publication_receipts',
    'domain_asset_staging_requests', 'domain_asset_staging_revisions',
    'knowledge_local_bundles', 'knowledge_local_bundle_challenges', 'knowledge_local_bundle_uploads',
    'knowledge_local_bundle_imports',
    'knowledge_document_feedback',
    'knowledge_local_publication_units',
    'knowledge_local_publication_preparations',
    'knowledge_native_check_executions',
    'knowledge_use_qualifications',
    'knowledge_use_qualification_requests',
    'knowledge_space_heads', 'knowledge_space_entries', 'knowledge_space_epochs',
    'knowledge_query_sets',
    'knowledge_reference_repairs',
    'knowledge_local_bundle_impacts',
    'knowledge_text_projections',
)


@dataclass(frozen=True)
class AtomicWrite:
    collection: str
    key: str
    expected: dict[str, Any] | None
    value: dict[str, Any]


def atomic_json_wire(value: Any) -> str:
    """Deterministic JSON representation; booleans never alias numeric values."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(',', ':'))


def is_atomic_read_fence(write: AtomicWrite) -> bool:
    return write.expected is not None and atomic_json_wire(write.expected) == atomic_json_wire(write.value)


def atomic_json_equal(left: Any, right: Any) -> bool:
    """Compare normalized JSON like JSONB (numeric equality, distinct booleans)."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) or isinstance(right, dict):
        return (isinstance(left, dict) and isinstance(right, dict)
                and left.keys() == right.keys()
                and all(atomic_json_equal(left[key], right[key]) for key in left))
    if isinstance(left, list) or isinstance(right, list):
        return (isinstance(left, list) and isinstance(right, list) and len(left) == len(right)
                and all(atomic_json_equal(a, b) for a, b in zip(left, right)))
    return left == right


def prepare_atomic_writes(writes: Iterable[AtomicWrite]) -> tuple[AtomicWrite, ...]:
    # Bound consumption even when given a generator; no unbounded materialization.
    prepared = []
    seen = set()
    for item in writes:
        if len(prepared) >= MAX_ATOMIC_WRITES:
            raise ValueError('ATOMIC_WRITE_COUNT_INVALID')
        if not isinstance(item, AtomicWrite):
            raise ValueError('ATOMIC_WRITE_INVALID')
        interpretation_projection = bool(
            item.collection == 'plans' and isinstance(item.key, str)
            and isinstance(item.value, dict) and isinstance(item.expected, dict)
            and all(value.get('domain_operation') == 'ontology.migration.interpretation-review'
                and isinstance(value.get('plan_id'), str)
                and value['plan_id'].startswith('interpretation_')
                and (item.key == value['plan_id'] or item.key.endswith(':' + value['plan_id']))
                and value.get('capability_id') == 'ontology.migration.migration-batch-review'
                for value in (item.expected, item.value)))
        # Existing PAT authority may fence a governed write against concurrent
        # revocation. This never grants token creation, mutation or deletion.
        token_read_fence = (item.collection == 'tokens' and isinstance(item.expected, dict)
            and isinstance(item.value, dict) and is_atomic_read_fence(item))
        if item.collection not in MIGRATION_COLLECTIONS and not interpretation_projection and not token_read_fence:
            raise ValueError('ATOMIC_COLLECTION_NOT_ALLOWED')
        if not isinstance(item.key, str) or not item.key.strip() or not isinstance(item.value, dict):
            raise ValueError('ATOMIC_WRITE_INVALID')
        if (item.collection, item.key) in seen:
            raise ValueError('ATOMIC_WRITE_DUPLICATE_KEY')
        if item.expected is not None and not isinstance(item.expected, dict):
            raise ValueError('ATOMIC_EXPECTED_INVALID')
        seen.add((item.collection, item.key))
        # Snapshot nested values and normalize the JSON wire before any mutation.
        value = json.loads(json.dumps(item.value, ensure_ascii=False, allow_nan=False))
        expected = json.loads(json.dumps(item.expected, ensure_ascii=False, allow_nan=False))
        prepared.append(AtomicWrite(item.collection, item.key, expected, value))
    if not prepared:
        raise ValueError('ATOMIC_WRITE_COUNT_INVALID')
    # Consistent lock order avoids reversed multi-key transaction deadlocks.
    return tuple(sorted(prepared, key=lambda item:(item.collection, item.key)))
