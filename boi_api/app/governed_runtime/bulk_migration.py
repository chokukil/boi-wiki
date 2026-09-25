"""Canonical, channel-neutral contracts for governed bulk ontology migration.

The module deliberately owns no SQL compilation, database execution, attestation,
Verdict, approval, Release creation, or active-pointer authority. UI, REST, and MCP
are transport adapters over this same application service.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Literal, Mapping, Protocol
from pydantic import BaseModel, ConfigDict, Field
from .semantic_binding_contract import Digest


Channel = Literal["ui", "rest", "mcp", "cli"]
MigrationMode = Literal["query_first", "metadata_first", "hybrid"]


class BulkMigrationPolicyError(ValueError):
    """Fail-closed contract or authorization error."""


def _stage_receipt(run_id, principal, shard_id, attempt_digest, raw):
    """Revision 0.2 hashes every persisted stage field; caller owns no authority."""
    allowed = {'skill_id', 'status', 'input_digest', 'output_digest', 'evidence_digest',
               'output', 'reason_codes', 'model_invocation_count', 'model_input_bytes',
               'model_invocation_record_digest', 'unresolved_reason', 'worker_verification'}
    if set(raw) - allowed:
        raise BulkMigrationPolicyError('STAGE_RESULT_FIELD_NOT_ALLOWED')
    item = json.loads(json.dumps(dict(raw), ensure_ascii=False, allow_nan=False))
    if not item.get('skill_id'):
        raise BulkMigrationPolicyError('STAGE_SKILL_ID_REQUIRED')
    if item.get('status') not in {'pass', 'fail', 'blocked', 'partial', 'flag', 'skip', 'not_run'}:
        raise BulkMigrationPolicyError('STAGE_STATUS_INVALID')
    for name in ('input_digest', 'output_digest', 'evidence_digest'):
        value = str(item.get(name) or '')
        if value or item['status'] == 'pass':
            _require_digest(value, field='stage.' + name)
    for name in ('model_invocation_count', 'model_input_bytes'):
        if name in item and (type(item[name]) is not int or item[name] < 0):
            raise BulkMigrationPolicyError('STAGE_METRICS_INVALID')
    verification=item.get('worker_verification')
    if verification:
        material={k:v for k,v in verification.items() if k!='verification_digest'}
        if (verification.get('verification_digest')!=_digest(material)
            or verification.get('contract_version')!='boi/task-submission-verification@1'
            or verification.get('run_id')!=run_id or verification.get('shard_id')!=shard_id
            or verification.get('principal')!=principal or verification.get('stage_input_digest')!=item['input_digest']
            or (item['status']=='pass' and (verification.get('verification_status')!='pass'
                or verification.get('evaluated_status')!='pass' or verification.get('evaluated_output_digest')!=item['output_digest']))):
            raise BulkMigrationPolicyError('WORKER_STAGE_VERIFICATION_INVALID')
    elif 'worker_verification' in item:raise BulkMigrationPolicyError('WORKER_STAGE_VERIFICATION_REQUIRED')
    payload = {**item, 'contract_version':'boi/migration-stage-receipt@0.3.0' if verification else 'boi/migration-stage-receipt@0.2.0',
               'run_id':run_id, 'shard_id':shard_id, 'employee_id':principal,
               'attempt_digest':attempt_digest, 'production_changed':False, 'active_transition':False}
    return {**payload, 'stage_receipt_digest':_digest(payload)}


def stage_receipt_contract_valid(receipt):
    version=receipt.get('contract_version')
    if version=='boi/migration-stage-receipt@0.2.0':return 'worker_verification' not in receipt
    if version!='boi/migration-stage-receipt@0.3.0' or not receipt.get('worker_verification'):return False
    raw={k:v for k,v in receipt.items() if k not in {'updated_at','stage_receipt_digest','contract_version',
        'run_id','shard_id','employee_id','attempt_digest','production_changed','active_transition'}}
    try:
        exact=_stage_receipt(receipt['run_id'],receipt['employee_id'],receipt['shard_id'],receipt['attempt_digest'],raw)
        return exact=={k:v for k,v in receipt.items() if k!='updated_at'}
    except (ValueError,KeyError,TypeError):return False


_FORBIDDEN_KEYS = frozenset(
    {
        "raw_sql",
        "sql",
        "repaired_sql",
        "model_generated_sql",
        "raw_rows",
        "rows",
        "result_rows",
        "golden",
        "golden_result",
        "golden_count",
        "historical_oracle",
        "dexa_query_spec",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
        "production_release_manifest",
        "promotion",
        "activate_release",
    }
)

_SKILL_IDS = frozenset(
    {
        "legacy-source-intake",
        "sql-lineage-extract",
        "domain-ontology-draft",
        "existing-concept-match",
        "physical-mapping-verify",
        "query-contract-author",
        "migration-batch-review",
        "harness-evolution",
    }
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _require_digest(value: str, *, field: str) -> str:
    normalized = str(value or "").strip()
    if not normalized.startswith("sha256:") or len(normalized) <= len("sha256:"):
        raise BulkMigrationPolicyError(f"DIGEST_REQUIRED:{field}")
    return normalized


@dataclass(frozen=True)
class SourceArtifactRef:
    artifact_ref: str
    digest: str
    role: str

    def __post_init__(self) -> None:
        if not self.artifact_ref.strip():
            raise BulkMigrationPolicyError("SOURCE_ARTIFACT_REF_REQUIRED")
        _require_digest(self.digest, field="source_artifact.digest")
        if not self.role.strip():
            raise BulkMigrationPolicyError("SOURCE_ARTIFACT_ROLE_REQUIRED")

    def semantic_payload(self) -> dict[str, str]:
        return {
            "artifact_ref": self.artifact_ref,
            "digest": self.digest,
            "role": self.role,
        }


@dataclass(frozen=True)
class SelectorManifest:
    systems: tuple[str, ...]
    schemas: tuple[str, ...]
    tables: tuple[str, ...]
    dependency_closure_refs: tuple[str, ...]
    selector_digest: str

    @classmethod
    def create(
        cls,
        *,
        systems: Iterable[str] = (),
        schemas: Iterable[str] = (),
        tables: Iterable[str] = (),
        dependency_closure_refs: Iterable[str] = (),
    ) -> "SelectorManifest":
        payload = {
            "systems": sorted({str(item).strip() for item in systems if str(item).strip()}),
            "schemas": sorted({str(item).strip() for item in schemas if str(item).strip()}),
            "tables": sorted({str(item).strip() for item in tables if str(item).strip()}),
            "dependency_closure_refs": sorted(
                {str(item).strip() for item in dependency_closure_refs if str(item).strip()}
            ),
        }
        if not any(payload.values()):
            raise BulkMigrationPolicyError("SELECTOR_SCOPE_REQUIRED")
        return cls(
            systems=tuple(payload["systems"]),
            schemas=tuple(payload["schemas"]),
            tables=tuple(payload["tables"]),
            dependency_closure_refs=tuple(payload["dependency_closure_refs"]),
            selector_digest=_digest(payload),
        )

    def semantic_payload(self) -> dict[str, object]:
        return {
            "systems": list(self.systems),
            "schemas": list(self.schemas),
            "tables": list(self.tables),
            "dependency_closure_refs": list(self.dependency_closure_refs),
            "selector_digest": self.selector_digest,
        }


class MetadataExecutionClosure(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True, strict=True)
    contract_version: Literal['boi/metadata-execution-closure@1']
    configuration_digest: Digest
    source_profile_digest: Digest
    source_selection_id: str = Field(min_length=1)
    definition_closure_digest: Digest
    source_record_count: int = Field(ge=1)
    source_record_set_digest: Digest
    records_per_shard: int = Field(ge=1, le=100)
    candidate_capacity_per_record: int = Field(ge=1, le=4)
    atomic_count_basis: Literal['derived_candidate_capacity']


class MetadataExecutionClosureV2(MetadataExecutionClosure):
    """Reserve Domain + physical Mapping + Query children; v1 stays readable."""
    contract_version: Literal['boi/metadata-execution-closure@2']
    candidate_capacity_per_record: int = Field(ge=1, le=12)
    atomic_count_basis: Literal['domain_mapping_query_candidate_capacity']


class MetadataExecutionClosureV3(MetadataExecutionClosure):
    """Explicit complete logical candidate revision, not a new execution DAG."""
    contract_version:Literal['boi/metadata-execution-closure@3']
    candidate_capacity_per_record:int=Field(ge=1,le=12)
    atomic_count_basis:Literal['derived_candidate_capacity','domain_mapping_query_candidate_capacity']
    draft_contract_version:Literal['boi/metadata-logical-draft@1']
    logical_profile_revision:Literal['boi/domain@0.4.0']


class MetadataExecutionClosureV4(MetadataExecutionClosureV3):
    contract_version:Literal['boi/metadata-execution-closure@4']
    reviewed_definition_policy:Literal['boi/reviewed-definitions@1']


def parse_metadata_execution_closure(value):
    if value.get('contract_version')=='boi/metadata-execution-closure@4':
        return MetadataExecutionClosureV4.model_validate(value)
    model=MetadataExecutionClosureV3 if value.get('contract_version')=='boi/metadata-execution-closure@3' else MetadataExecutionClosureV2 if value.get('contract_version')=='boi/metadata-execution-closure@2' else MetadataExecutionClosure
    return model.model_validate(value)


@dataclass(frozen=True)
class BulkMigrationManifest:
    manifest_version: str
    project_id: str
    mode: MigrationMode
    source_artifacts: tuple[SourceArtifactRef, ...]
    catalog_snapshot_ref: str
    catalog_snapshot_digest: str
    schema_snapshot_digest: str
    selector: SelectorManifest
    requested_skill_stages: tuple[str, ...]
    profile_revisions: tuple[str, ...]
    evaluator_code_digests: tuple[str, ...]
    model_role_prompt_digests: tuple[str, ...]
    acl_policy_digest: str
    purpose: str
    idempotency_key: str
    before_hashes: dict[str, str]
    atomic_object_count: int
    max_objects_per_shard: int
    dry_run: bool
    local_model_policy: str
    resume_retry_policy: str
    active_concept_index_digest: str
    pipeline_contract_id: str
    candidate_preview_question_digests: tuple[str, ...]
    production_changed: bool
    active_transition: bool
    manifest_digest: str
    metadata_execution: dict[str, Any] | None = None

    @staticmethod
    def validate_safe_value(value: Any, *, path: str = "manifest") -> Any:
        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}
            for raw_key, item in value.items():
                key = str(raw_key).strip()
                if key.casefold() in _FORBIDDEN_KEYS:
                    raise BulkMigrationPolicyError(f"FORBIDDEN_MANIFEST_FIELD:{path}.{key}")
                sanitized[key] = BulkMigrationManifest.validate_safe_value(
                    item, path=f"{path}.{key}"
                )
            return sanitized
        if isinstance(value, (list, tuple)):
            return [
                BulkMigrationManifest.validate_safe_value(item, path=f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        raise BulkMigrationPolicyError(f"UNSUPPORTED_MANIFEST_VALUE:{path}")

    @classmethod
    def create(
        cls,
        *,
        project_id: str,
        mode: MigrationMode,
        source_artifacts: Iterable[SourceArtifactRef],
        catalog_snapshot_ref: str,
        catalog_snapshot_digest: str,
        schema_snapshot_digest: str,
        selector: SelectorManifest,
        requested_skill_stages: Iterable[str],
        profile_revisions: Iterable[str],
        evaluator_code_digests: Iterable[str],
        model_role_prompt_digests: Iterable[str],
        acl_policy_digest: str,
        purpose: str,
        idempotency_key: str,
        before_hashes: Mapping[str, str],
        atomic_object_count: int,
        max_objects_per_shard: int,
        dry_run: bool,
        local_model_policy: str,
        resume_retry_policy: str,
        active_concept_index_digest: str = "",
        pipeline_contract_id: str = "boi/p0-b3-pipeline@0.2.0",
        candidate_preview_question_digests: Iterable[str] = (),
        metadata_execution: Mapping[str, Any] | None = None,
    ) -> "BulkMigrationManifest":
        if mode not in {"query_first", "metadata_first", "hybrid"}:
            raise BulkMigrationPolicyError(f"UNSUPPORTED_MIGRATION_MODE:{mode}")
        if not project_id.strip():
            raise BulkMigrationPolicyError("PROJECT_ID_REQUIRED")
        sources = tuple(sorted(source_artifacts, key=lambda item: item.artifact_ref))
        if not sources:
            raise BulkMigrationPolicyError("SOURCE_ARTIFACT_REQUIRED")
        if not catalog_snapshot_ref.strip():
            raise BulkMigrationPolicyError("CATALOG_SNAPSHOT_REF_REQUIRED")
        _require_digest(catalog_snapshot_digest, field="catalog_snapshot_digest")
        _require_digest(schema_snapshot_digest, field="schema_snapshot_digest")
        _require_digest(acl_policy_digest, field="acl_policy_digest")
        if not purpose.strip():
            raise BulkMigrationPolicyError("PURPOSE_REQUIRED")
        if not idempotency_key.strip():
            raise BulkMigrationPolicyError("IDEMPOTENCY_KEY_REQUIRED")
        if not 1 <= int(max_objects_per_shard) <= 100:
            raise BulkMigrationPolicyError(
                f"SHARD_SIZE_LIMIT_INVALID:{max_objects_per_shard}"
            )
        if not 1 <= int(atomic_object_count) <= 100:
            raise BulkMigrationPolicyError(
                f"ATOMIC_OBJECT_LIMIT_EXCEEDED:{atomic_object_count}"
            )
        stages = tuple(dict.fromkeys(str(item).strip() for item in requested_skill_stages))
        unknown_stages = sorted(set(stages).difference(_SKILL_IDS))
        if unknown_stages:
            raise BulkMigrationPolicyError(
                "UNKNOWN_SKILL_STAGE:" + ",".join(unknown_stages)
            )
        if not stages:
            raise BulkMigrationPolicyError("SKILL_STAGE_REQUIRED")
        normalized_before = {
            str(key): _require_digest(str(value), field=f"before_hashes.{key}")
            for key, value in sorted(before_hashes.items())
        }
        normalized_concept_index_digest = (
            _require_digest(
                active_concept_index_digest,
                field="active_concept_index_digest",
            )
            if active_concept_index_digest
            else ""
        )
        normalized_question_digests = tuple(
            sorted(
                _require_digest(str(value), field="candidate_preview_question_digest")
                for value in candidate_preview_question_digests
            )
        )
        if not str(pipeline_contract_id).strip():
            raise BulkMigrationPolicyError("PIPELINE_CONTRACT_ID_REQUIRED")
        payload = {
            "manifest_version": "boi/bulk-migration-manifest@0.2.0",
            "project_id": project_id,
            "mode": mode,
            "source_artifacts": [item.semantic_payload() for item in sources],
            "catalog_snapshot_ref": catalog_snapshot_ref,
            "catalog_snapshot_digest": catalog_snapshot_digest,
            "schema_snapshot_digest": schema_snapshot_digest,
            "selector": selector.semantic_payload(),
            "requested_skill_stages": list(stages),
            "profile_revisions": sorted(set(profile_revisions)),
            "evaluator_code_digests": sorted(set(evaluator_code_digests)),
            "model_role_prompt_digests": sorted(set(model_role_prompt_digests)),
            "acl_policy_digest": acl_policy_digest,
            "purpose": purpose,
            "idempotency_key": idempotency_key,
            "before_hashes": normalized_before,
            "atomic_object_count": int(atomic_object_count),
            "max_objects_per_shard": int(max_objects_per_shard),
            "dry_run": bool(dry_run),
            "local_model_policy": local_model_policy,
            "resume_retry_policy": resume_retry_policy,
            "pipeline_contract_id": str(pipeline_contract_id),
            "candidate_preview_question_digests": list(normalized_question_digests),
            "production_changed": False,
            "active_transition": False,
        }
        if normalized_concept_index_digest:
            payload["active_concept_index_digest"] = normalized_concept_index_digest
        metadata = None
        if metadata_execution is not None:
            metadata = parse_metadata_execution_closure(dict(metadata_execution)).model_dump(mode='json')
            if pipeline_contract_id != 'boi/semantic-metadata-pipeline@1.0.0':
                raise BulkMigrationPolicyError('METADATA_EXECUTION_PIPELINE_MISMATCH')
            if (metadata['records_per_shard'] * metadata['candidate_capacity_per_record'] > int(max_objects_per_shard)
                or int(atomic_object_count) != min(metadata['source_record_count'],metadata['records_per_shard'])*metadata['candidate_capacity_per_record']):
                raise BulkMigrationPolicyError('METADATA_SHARD_CAPACITY_MISMATCH')
            payload['manifest_version']='boi/bulk-migration-manifest@0.3.0'
            payload['metadata_execution']=metadata
        cls.validate_safe_value(payload)
        return cls(
            manifest_version=str(payload["manifest_version"]),
            project_id=project_id,
            mode=mode,
            source_artifacts=sources,
            catalog_snapshot_ref=catalog_snapshot_ref,
            catalog_snapshot_digest=catalog_snapshot_digest,
            schema_snapshot_digest=schema_snapshot_digest,
            selector=selector,
            requested_skill_stages=stages,
            profile_revisions=tuple(payload["profile_revisions"]),
            evaluator_code_digests=tuple(payload["evaluator_code_digests"]),
            model_role_prompt_digests=tuple(payload["model_role_prompt_digests"]),
            acl_policy_digest=acl_policy_digest,
            purpose=purpose,
            idempotency_key=idempotency_key,
            before_hashes=normalized_before,
            atomic_object_count=int(atomic_object_count),
            max_objects_per_shard=int(max_objects_per_shard),
            dry_run=bool(dry_run),
            local_model_policy=local_model_policy,
            resume_retry_policy=resume_retry_policy,
            active_concept_index_digest=normalized_concept_index_digest,
            pipeline_contract_id=str(pipeline_contract_id),
            candidate_preview_question_digests=normalized_question_digests,
            production_changed=False,
            active_transition=False,
            manifest_digest=_digest(payload),
            metadata_execution=metadata,
        )

    def semantic_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "manifest_version": self.manifest_version,
            "project_id": self.project_id,
            "mode": self.mode,
            "source_artifacts": [item.semantic_payload() for item in self.source_artifacts],
            "catalog_snapshot_ref": self.catalog_snapshot_ref,
            "catalog_snapshot_digest": self.catalog_snapshot_digest,
            "schema_snapshot_digest": self.schema_snapshot_digest,
            "selector": self.selector.semantic_payload(),
            "requested_skill_stages": list(self.requested_skill_stages),
            "profile_revisions": list(self.profile_revisions),
            "evaluator_code_digests": list(self.evaluator_code_digests),
            "model_role_prompt_digests": list(self.model_role_prompt_digests),
            "acl_policy_digest": self.acl_policy_digest,
            "purpose": self.purpose,
            "idempotency_key": self.idempotency_key,
            "before_hashes": dict(self.before_hashes),
            "atomic_object_count": self.atomic_object_count,
            "max_objects_per_shard": self.max_objects_per_shard,
            "dry_run": self.dry_run,
            "local_model_policy": self.local_model_policy,
            "resume_retry_policy": self.resume_retry_policy,
            "pipeline_contract_id": self.pipeline_contract_id,
            "candidate_preview_question_digests": list(
                self.candidate_preview_question_digests
            ),
            "production_changed": False,
            "active_transition": False,
        }
        if self.active_concept_index_digest:
            payload["active_concept_index_digest"] = self.active_concept_index_digest
        if self.metadata_execution is not None:
            payload['metadata_execution']=dict(self.metadata_execution)
        return payload


@dataclass(frozen=True)
class BulkMigrationShard:
    shard_id: str
    input_fingerprint: str
    atomic_object_count: int
    state: str = "queued"
    candidate_state: str = "captured"
    execution_count: int = 0
    retry_count: int = 0
    result_digest: str | None = None
    reason_code: str | None = None
    last_checkpoint_digest: str | None = None
    stage_states: dict[str, str] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    attention_refs: tuple[str, ...] = ()
    model_invocation_count: int = 0
    model_input_bytes: int = 0
    last_attempt_digest: str = ''
    stage_receipt_refs: dict[str, str] = field(default_factory=dict)

    def semantic_payload(self) -> dict[str, object]:
        payload = {
            "input_fingerprint": self.input_fingerprint,
            "atomic_object_count": self.atomic_object_count,
            "state": self.state,
            "candidate_state": self.candidate_state,
            "execution_count": self.execution_count,
            "retry_count": self.retry_count,
            "result_digest": self.result_digest,
            "reason_code": self.reason_code,
            "last_checkpoint_digest": self.last_checkpoint_digest,
        }
        # Preserve old queued/history shapes; new shard-result revisions carry
        # their own metrics and evidence rather than borrowing run-global state.
        if self.stage_states:
            payload.update(stage_states=dict(sorted(self.stage_states.items())),
                evidence_refs=list(self.evidence_refs), attention_refs=list(self.attention_refs),
                model_invocation_count=self.model_invocation_count, model_input_bytes=self.model_input_bytes,
                last_attempt_digest=self.last_attempt_digest)
            if self.stage_receipt_refs:
                payload['stage_receipt_refs'] = dict(sorted(self.stage_receipt_refs.items()))
        return payload


@dataclass(frozen=True)
class BulkMigrationRun:
    run_id: str
    principal: str
    project_id: str
    manifest_digest: str
    idempotency_key: str
    control_state: str
    candidate_state: str
    shards: tuple[BulkMigrationShard, ...]
    stage_states: dict[str, str]
    input_digest: str
    output_digest: str | None
    candidate_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    attention_refs: tuple[str, ...]
    retry_count: int
    cache_hits: int
    model_invocation_count: int
    model_input_bytes: int
    started_at: str
    completed_at: str | None
    last_immutable_checkpoint_digest: str
    semantic_digest: str
    ui_url: str
    mcp_invocation_ref: dict[str, str]
    production_changed: bool = False
    active_transition: bool = False
    service_stage_receipt_refs: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class BulkMigrationReceipt:
    pipeline_contract_id: str
    required_stage_ids: tuple[str, ...]
    optional_stage_ids: tuple[str, ...]
    missing_required_stage_ids: tuple[str, ...]
    manifest_digest: str
    run_digest: str
    stage_digests: dict[str, str]
    component_digests: tuple[str, ...]
    candidate_package_digest: str
    attention_digest: str
    checks: tuple[dict[str, object], ...]
    passed_check_count: int
    failed_check_count: int
    partial_check_count: int
    token_metrics: dict[str, int]
    status: str
    production_changed: bool
    active_transition: bool
    receipt_digest: str
    receipt_version: str = 'boi/bulk-migration-receipt@0.2.0'

    def semantic_payload(self) -> dict[str, object]:
        return {
            "receipt_version": self.receipt_version,
            "pipeline_contract_id": self.pipeline_contract_id,
            "required_stage_ids": list(self.required_stage_ids),
            "optional_stage_ids": list(self.optional_stage_ids),
            "missing_required_stage_ids": list(self.missing_required_stage_ids),
            "manifest_digest": self.manifest_digest,
            "run_digest": self.run_digest,
            "stage_digests": dict(sorted(self.stage_digests.items())),
            "component_digests": list(self.component_digests),
            "candidate_package_digest": self.candidate_package_digest,
            "attention_digest": self.attention_digest,
            "checks": [dict(item) for item in self.checks],
            "passed_check_count": self.passed_check_count,
            "failed_check_count": self.failed_check_count,
            "partial_check_count": self.partial_check_count,
            "token_metrics": dict(sorted(self.token_metrics.items())),
            "status": self.status,
            "production_changed": False,
            "active_transition": False,
        }


class BulkMigrationRepository(Protocol):
    def manifest_payload(self, run: BulkMigrationRun) -> dict[str, object]: ...
    def get_stage_receipt(self, ref: str) -> dict[str, object] | None: ...
    def initialize(self, manifest: BulkMigrationManifest, run: BulkMigrationRun) -> BulkMigrationRun: ...
    def compare_and_put(self, expected: BulkMigrationRun, run: BulkMigrationRun,
                        *, stage_results=(), shard_id=None, service_receipts=()) -> bool: ...
    def get_service_stage_receipt(self, ref: str) -> dict[str, object] | None: ...
    def put_manifest(self, manifest: BulkMigrationManifest, *, principal: str) -> None: ...
    def get(self, run_id: str) -> BulkMigrationRun | None: ...
    def put(self, run: BulkMigrationRun) -> None: ...
    def find_idempotent(self, principal: str, key: str) -> BulkMigrationRun | None: ...
    def save_receipt(self, run: BulkMigrationRun, receipt: BulkMigrationReceipt) -> None: ...
    def save_approval(self, run: BulkMigrationRun, approval: dict[str, object]) -> None: ...
    def get_approval(self, run_id: str) -> dict[str, object] | None: ...
    def record_invocation(self, run: BulkMigrationRun, channel: Channel) -> None: ...
    def record_stage_results(
        self,
        *,
        run: BulkMigrationRun,
        shard_id: str,
        results: Iterable[Mapping[str, object]],
    ) -> None: ...


class InMemoryBulkMigrationRepository:
    """Test/reference repository; persistent adapters implement this boundary."""

    def __init__(self) -> None:
        import threading
        self._lock = threading.RLock()
        self._runs: dict[str, BulkMigrationRun] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._manifests: dict[str, BulkMigrationManifest] = {}
        self._receipts: dict[str, list[BulkMigrationReceipt]] = {}
        self._approvals: dict[str, dict[str, object]] = {}
        self._stage_results: dict[tuple[str, str], tuple[dict[str, object], ...]] = {}
        self._stage_receipts: dict[str, dict[str, object]] = {}
        self._service_stage_receipts: dict[str, dict[str, object]] = {}
        self._invocations: dict[tuple[str, str], dict[str, object]] = {}

    def initialize(self, manifest: BulkMigrationManifest, run: BulkMigrationRun) -> BulkMigrationRun:
        with self._lock:
            old = self.find_idempotent(run.principal, run.idempotency_key)
            if old:
                if old.manifest_digest != run.manifest_digest:
                    raise BulkMigrationPolicyError('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_MANIFEST')
                return old
            if any(item.project_id == run.project_id and item.principal != run.principal
                   for item in self._runs.values()):
                raise BulkMigrationPolicyError('PROJECT_ACCESS_DENIED')
            self.put_manifest(manifest, principal=run.principal)
            self.put(run)
            return run

    def compare_and_put(self, expected, run, *, stage_results=(), shard_id=None, service_receipts=(), task_execution=None) -> bool:
        with self._lock:
            if task_execution is not None:raise BulkMigrationPolicyError('WORKER_PERSISTENT_REPOSITORY_REQUIRED')
            if self.get(run.run_id) != expected:
                return False
            results = tuple(dict(item) for item in stage_results)
            if results:
                self.record_stage_results(run=run, shard_id=shard_id, results=results)
            for receipt in service_receipts:
                self._service_stage_receipts[receipt['stage_receipt_digest']] = dict(receipt)
            self.put(run)
            return True

    def put_manifest(self, manifest: BulkMigrationManifest, *, principal: str) -> None:
        del principal
        self._manifests[manifest.manifest_digest] = manifest

    def manifest_payload(self, run):
        value = self._manifests[run.manifest_digest].semantic_payload()
        if _digest(value) != run.manifest_digest:
            raise BulkMigrationPolicyError('MIGRATION_MANIFEST_DRIFT')
        return value

    def get_stage_receipt(self, ref):
        import copy
        return copy.deepcopy(self._stage_receipts.get(ref))

    def get_service_stage_receipt(self, ref):
        import copy
        return copy.deepcopy(self._service_stage_receipts.get(ref))

    def get(self, run_id: str) -> BulkMigrationRun | None:
        return self._runs.get(run_id)

    def put(self, run: BulkMigrationRun) -> None:
        self._runs[run.run_id] = run
        self._idempotency[(run.principal, run.idempotency_key)] = run.run_id

    def find_idempotent(self, principal: str, key: str) -> BulkMigrationRun | None:
        run_id = self._idempotency.get((principal, key))
        return self._runs.get(run_id) if run_id else None

    def list_runs(self) -> tuple[BulkMigrationRun, ...]:
        return tuple(self._runs[key] for key in sorted(self._runs))

    def save_receipt(self, run: BulkMigrationRun, receipt: BulkMigrationReceipt) -> None:
        self._receipts.setdefault(run.run_id, []).append(receipt)

    def save_approval(self, run: BulkMigrationRun, approval: dict[str, object]) -> None:
        self._approvals[run.run_id] = dict(approval)

    def get_approval(self, run_id: str) -> dict[str, object] | None:
        value = self._approvals.get(run_id)
        return dict(value) if value else None

    def record_invocation(self, run: BulkMigrationRun, channel: Channel) -> None:
        self._invocations[(run.run_id, channel)] = {
            "run_id": run.run_id,
            "channel": channel,
            "manifest_digest": run.manifest_digest,
        }

    def record_stage_results(
        self,
        *,
        run: BulkMigrationRun,
        shard_id: str,
        results: Iterable[Mapping[str, object]],
    ) -> None:
        values = tuple(dict(item) for item in results)
        attempt = next(s.last_attempt_digest for s in run.shards if s.shard_id == shard_id)
        receipts = tuple(_stage_receipt(run.run_id, run.principal, shard_id, attempt, item) for item in values)
        for receipt in receipts:
            self._stage_receipts[receipt['stage_receipt_digest']] = receipt
        self._stage_results[(run.run_id, shard_id)] = values


def _shard_to_record(run: BulkMigrationRun, shard: BulkMigrationShard) -> dict[str, object]:
    return {
        "shard_id": shard.shard_id,
        "run_id": run.run_id,
        "employee_id": run.principal,
        "input_fingerprint": shard.input_fingerprint,
        "atomic_object_count": shard.atomic_object_count,
        "state": shard.state,
        "candidate_state": shard.candidate_state,
        "execution_count": shard.execution_count,
        "retry_count": shard.retry_count,
        "result_digest": shard.result_digest,
        "reason_code": shard.reason_code,
        "last_checkpoint_digest": shard.last_checkpoint_digest,
        **({"stage_states":dict(shard.stage_states), "evidence_refs":list(shard.evidence_refs),
            "attention_refs":list(shard.attention_refs), "model_invocation_count":shard.model_invocation_count,
            "model_input_bytes":shard.model_input_bytes, "last_attempt_digest":shard.last_attempt_digest} if shard.stage_states else {}),
        **({'stage_receipt_refs':dict(shard.stage_receipt_refs)} if shard.stage_receipt_refs else {}),
    }


class AgentV2StoreBulkMigrationRepository:
    """Persistent adapter over the existing AgentV2 store boundary."""

    def __init__(self, store: Any) -> None:
        self.store = store

    @staticmethod
    def _check_owner(buffer, collection, key, principal):
        record = buffer.get(collection, key)
        if record and record.get('employee_id') != principal:
            reason = 'PROJECT_ACCESS_DENIED' if collection == 'bulk_migration_projects' else 'MANIFEST_ACCESS_DENIED'
            raise BulkMigrationPolicyError(reason)
        return record

    def compare_and_put(self, expected, run, *, stage_results=(), shard_id=None, service_receipts=(), task_execution=None) -> bool:
        from .bulk_migration_transaction import MigrationWriteSet
        buffer = MigrationWriteSet(self.store)
        root_key = ('bulk_migration_runs', run.run_id)
        current = buffer.get(*root_key)
        if not current or self._run_from_record(current) != expected:
            return False
        owner_keys = (('bulk_migration_projects', run.project_id),
                      ('bulk_migration_manifests', run.manifest_digest))
        for collection, key in owner_keys:
            if not self._check_owner(buffer, collection, key, run.principal):
                raise BulkMigrationPolicyError('RUN_AUTHORITY_RECORD_MISSING')
        if task_execution is not None:
            if task_execution.run_id!=run.run_id or task_execution.shard_id!=shard_id or task_execution.principal!=run.principal:
                raise BulkMigrationPolicyError('WORKER_EXECUTION_CLOSURE_MISMATCH')
            task_execution.validate_into(buffer)
            if task_execution.final_write_validator is not None:
                task_execution.final_write_validator(buffer)
        elif run!=expected and any(item.get('worker_verification') for item in stage_results):
            raise BulkMigrationPolicyError('WORKER_EXECUTION_RESERVATION_REQUIRED')
        writer = AgentV2StoreBulkMigrationRepository(buffer)
        # The root CAS fences the complete run revision. Materialize only changed
        # children, plus the selected replay shard whose history must be checked.
        # Reading every unrelated task here turns a bounded shard commit into an
        # unbounded corpus-sized atomic write set (even for unchanged records).
        previous = {item.shard_id: item for item in expected.shards}
        selected = {item.shard_id for item in run.shards
                    if previous.get(item.shard_id) != item}
        if shard_id is not None:
            selected.add(shard_id)
        writer.put(run, shard_ids=selected)
        if stage_results:
            writer.record_stage_results(run=run, shard_id=shard_id, results=stage_results)
        if task_execution is not None:task_execution.finish_into(buffer,stage_results)
        for receipt in service_receipts:
            ref = receipt['stage_receipt_digest']
            existing = buffer.get('bulk_migration_service_stage_results', ref)
            if existing and {k:v for k,v in existing.items() if k!='updated_at'} != receipt:
                raise BulkMigrationPolicyError('SERVICE_STAGE_RECEIPT_INTEGRITY_FAILURE')
            buffer.put('bulk_migration_service_stage_results', ref, receipt)
        # Same-result replay is verification, never a silent repair of history.
        if run == expected and buffer.writes():
            raise BulkMigrationPolicyError('STAGE_RECEIPT_INTEGRITY_FAILURE')
        fences=tuple(key for key,value in buffer.before.items() if value is not None)
        return self.store.atomic_compare_and_write(buffer.writes(fences=fences))

    def initialize(self, manifest: BulkMigrationManifest, run: BulkMigrationRun) -> BulkMigrationRun:
        """Reserve one run, materialize bounded child batches, then expose queued.

        A connection interruption leaves a non-executable initializing header.
        Exact resubmission populates missing children without reprocessing sources
        or rerunning a model. Every child batch checks the reserved run and owner.
        """
        from ..v2.atomic_store_contract import AtomicWrite
        from .bulk_migration_transaction import MigrationWriteSet
        buffer = MigrationWriteSet(self.store)
        project_key = ('bulk_migration_projects', run.project_id)
        manifest_key = ('bulk_migration_manifests', run.manifest_digest)
        root_key = ('bulk_migration_runs', run.run_id)
        idempotency_key = ('bulk_migration_idempotency', self._idempotency_record_id(run.principal, run.idempotency_key))
        for collection, key in (project_key, manifest_key):
            self._check_owner(buffer, collection, key, run.principal)
        existing = buffer.get(*idempotency_key)
        if existing and existing.get('manifest_digest') != run.manifest_digest:
            raise BulkMigrationPolicyError('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_MANIFEST')
        if not existing:
            initializing = BulkMigrationOrchestrator.revised_run(run, control_state='initializing')
            writer = AgentV2StoreBulkMigrationRepository(buffer)
            writer.put_manifest(manifest, principal=run.principal)
            writer.put(initializing)
            header_keys = (project_key, manifest_key, root_key, idempotency_key)
            writes = { (item.collection, item.key): item for item in buffer.writes() }
            for key in header_keys:
                if key not in writes:
                    value = buffer.get(*key)
                    writes[key] = AtomicWrite(*key, buffer.before[key], value)
            if not self.store.atomic_compare_and_write(tuple(writes[key] for key in header_keys)):
                winner = self.store.get(*idempotency_key)
                if not winner or winner.get('manifest_digest') != run.manifest_digest:
                    raise BulkMigrationPolicyError('IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_MANIFEST')
        current = self.get(run.run_id)
        if current is None:
            raise BulkMigrationPolicyError('RUN_INITIALIZATION_HEADER_MISSING')
        if tuple(s.input_fingerprint for s in current.shards) != tuple(s.input_fingerprint for s in run.shards):
            raise BulkMigrationPolicyError('IDEMPOTENCY_SELECTOR_EXPANSION_DRIFT')
        if current.control_state != 'initializing':
            return current
        header_keys = (project_key, manifest_key, root_key, idempotency_key)
        while True:
            buffer = MigrationWriteSet(self.store)
            header = buffer.get(*root_key)
            if not header:
                raise BulkMigrationPolicyError('RUN_INITIALIZATION_HEADER_MISSING')
            if header['control_state'] != 'initializing':
                return self._run_from_record(header)
            current = self._run_from_record(header)
            for collection, key in (project_key, manifest_key):
                if not self._check_owner(buffer, collection, key, current.principal):
                    raise BulkMigrationPolicyError('RUN_AUTHORITY_RECORD_MISSING')
            AgentV2StoreBulkMigrationRepository(buffer).put(current)
            children = buffer.writes(exclude=header_keys)
            fences = tuple(AtomicWrite(*key, buffer.before[key], buffer.get(*key))
                           for key in (root_key, project_key, manifest_key))
            if not children:
                queued = BulkMigrationOrchestrator.revised_run(current, control_state='queued')
                value = {**header, 'control_state':'queued', 'semantic_digest':queued.semantic_digest}
                writes = (AtomicWrite(*root_key, header, value), *fences[1:])
            else:
                # Three authority/header fences + at most 997 child writes.
                writes = (*fences, *children[:997])
            if not self.store.atomic_compare_and_write(writes):
                return self.get(run.run_id)
            if not children:
                return self.get(run.run_id)

    @staticmethod
    def _idempotency_record_id(principal: str, key: str) -> str:
        return _digest({"principal": principal, "idempotency_key": key})

    @staticmethod
    def _run_from_record(record: Mapping[str, object]) -> BulkMigrationRun:
        raw_shards = record.get("shards") or []
        shards = tuple(
            BulkMigrationShard(
                shard_id=str(item["shard_id"]),
                input_fingerprint=str(item["input_fingerprint"]),
                atomic_object_count=int(item["atomic_object_count"]),
                state=str(item.get("state") or "queued"),
                candidate_state=str(item.get("candidate_state") or "captured"),
                execution_count=int(item.get("execution_count") or 0),
                retry_count=int(item.get("retry_count") or 0),
                result_digest=(str(item["result_digest"]) if item.get("result_digest") else None),
                reason_code=(str(item["reason_code"]) if item.get("reason_code") else None),
                last_checkpoint_digest=(
                    str(item["last_checkpoint_digest"])
                    if item.get("last_checkpoint_digest")
                    else None
                ),
                stage_states=dict(item.get('stage_states') or {}),
                evidence_refs=tuple(item.get('evidence_refs') or ()),
                attention_refs=tuple(item.get('attention_refs') or ()),
                model_invocation_count=int(item.get('model_invocation_count') or 0),
                model_input_bytes=int(item.get('model_input_bytes') or 0),
                last_attempt_digest=str(item.get('last_attempt_digest') or ''),
                stage_receipt_refs=dict(item.get('stage_receipt_refs') or {}),
            )
            for item in raw_shards
            if isinstance(item, Mapping)
        )
        return BulkMigrationRun(
            run_id=str(record["run_id"]),
            principal=str(record["employee_id"]),
            project_id=str(record["project_id"]),
            manifest_digest=str(record["manifest_digest"]),
            idempotency_key=str(record["idempotency_key"]),
            control_state=str(record["control_state"]),
            candidate_state=str(record["candidate_state"]),
            shards=shards,
            stage_states={
                str(key): str(value)
                for key, value in dict(record.get("stage_states") or {}).items()
            },
            input_digest=str(record.get("input_digest") or record["manifest_digest"]),
            output_digest=(str(record["output_digest"]) if record.get("output_digest") else None),
            candidate_refs=tuple(str(item) for item in record.get("candidate_refs") or ()),
            evidence_refs=tuple(str(item) for item in record.get("evidence_refs") or ()),
            attention_refs=tuple(str(item) for item in record.get("attention_refs") or ()),
            retry_count=int(record.get("retry_count") or 0),
            cache_hits=int(record.get("cache_hits") or 0),
            model_invocation_count=int(record.get("model_invocation_count") or 0),
            model_input_bytes=int(record.get("model_input_bytes") or 0),
            started_at=str(record.get("started_at") or ""),
            completed_at=(str(record["completed_at"]) if record.get("completed_at") else None),
            last_immutable_checkpoint_digest=str(
                record.get("last_immutable_checkpoint_digest") or ""
            ),
            semantic_digest=str(record["semantic_digest"]),
            ui_url=str(record["ui_url"]),
            mcp_invocation_ref=dict(record.get("mcp_invocation_ref") or {}),
            production_changed=bool(record.get("production_changed", False)),
            active_transition=bool(record.get("active_transition", False)),
            service_stage_receipt_refs=dict(record.get('service_stage_receipt_refs') or {}),
        )

    def put_manifest(self, manifest: BulkMigrationManifest, *, principal: str) -> None:
        self.store.put(
            "bulk_migration_manifests",
            manifest.manifest_digest,
            {
                "manifest_digest": manifest.manifest_digest,
                "employee_id": principal,
                "project_id": manifest.project_id,
                "semantic_payload": manifest.semantic_payload(),
                "production_changed": False,
                "active_transition": False,
            },
        )

    def get(self, run_id: str) -> BulkMigrationRun | None:
        record = self.store.get("bulk_migration_runs", run_id)
        return self._run_from_record(record) if record else None

    def manifest_payload(self, run):
        record = self.store.get('bulk_migration_manifests', run.manifest_digest)
        if not record or record.get('employee_id') != run.principal:
            raise BulkMigrationPolicyError('MANIFEST_ACCESS_DENIED')
        value = dict(record.get('semantic_payload') or {})
        if record.get('manifest_digest') != run.manifest_digest or _digest(value) != run.manifest_digest:
            raise BulkMigrationPolicyError('MIGRATION_MANIFEST_DRIFT')
        return value

    def get_stage_receipt(self, ref):
        return self.store.get('bulk_migration_stage_results', ref)

    def get_service_stage_receipt(self, ref):
        return self.store.get('bulk_migration_service_stage_results', ref)

    def put(self, run: BulkMigrationRun, *, shard_ids=None) -> None:
        run_record = {
            "run_id": run.run_id,
            "employee_id": run.principal,
            "project_id": run.project_id,
            "manifest_digest": run.manifest_digest,
            "idempotency_key": run.idempotency_key,
            "control_state": run.control_state,
            "candidate_state": run.candidate_state,
            "shards": [_shard_to_record(run, item) for item in run.shards],
            "stage_states": dict(run.stage_states),
            "input_digest": run.input_digest,
            "output_digest": run.output_digest,
            "candidate_refs": list(run.candidate_refs),
            "evidence_refs": list(run.evidence_refs),
            "attention_refs": list(run.attention_refs),
            "retry_count": run.retry_count,
            "cache_hits": run.cache_hits,
            "model_invocation_count": run.model_invocation_count,
            "model_input_bytes": run.model_input_bytes,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "last_immutable_checkpoint_digest": run.last_immutable_checkpoint_digest,
            "semantic_digest": run.semantic_digest,
            "ui_url": run.ui_url,
            "mcp_invocation_ref": dict(run.mcp_invocation_ref),
            "production_changed": False,
            "active_transition": False,
        }
        if run.service_stage_receipt_refs:
            run_record['service_stage_receipt_refs'] = dict(run.service_stage_receipt_refs)
        self.store.put("bulk_migration_runs", run.run_id, run_record)
        self.store.put(
            "bulk_migration_idempotency",
            self._idempotency_record_id(run.principal, run.idempotency_key),
            {
                "employee_id": run.principal,
                "idempotency_key": run.idempotency_key,
                "run_id": run.run_id,
                "manifest_digest": run.manifest_digest,
            },
        )
        if not self.store.get("bulk_migration_projects", run.project_id):
            self.store.put(
                "bulk_migration_projects",
                run.project_id,
                {
                    "project_id": run.project_id,
                    "employee_id": run.principal,
                    "production_changed": False,
                },
            )
        for shard in run.shards:
            if shard_ids is not None and shard.shard_id not in shard_ids:
                continue
            shard_record = _shard_to_record(run, shard)
            self.store.put("bulk_migration_shards", shard.shard_id, shard_record)
            suffix = shard.shard_id.split(":", 1)[-1]
            candidate_id = f"candidate:{suffix}"
            manifest_record = self.store.get(
                "bulk_migration_manifests", run.manifest_digest
            ) or {}
            manifest_payload = dict(manifest_record.get("semantic_payload") or {})
            stages = tuple(
                str(item) for item in manifest_payload.get("requested_skill_stages") or ()
            )
            prompt_digests = tuple(
                str(item)
                for item in manifest_payload.get("model_role_prompt_digests") or ()
            )
            for skill_id in stages:
                task_package_id = f"taskpkg:{suffix}:{skill_id}"
                existing_task = self.store.get(
                    "bulk_migration_task_packages", task_package_id
                ) or {}
                self.store.put(
                    "bulk_migration_task_packages",
                    task_package_id,
                    {
                        **existing_task,
                        "task_package_id": task_package_id,
                        "run_id": run.run_id,
                        "shard_id": shard.shard_id,
                        "employee_id": run.principal,
                        "skill_id": skill_id,
                        "skill_digest": _digest({"skill_id": skill_id}),
                        "model_role_prompt_digest": (
                            prompt_digests[0]
                            if skill_id in {"domain-ontology-draft", "existing-concept-match"}
                            and prompt_digests
                            else None
                        ),
                        "state": shard.stage_states.get(skill_id, str(existing_task.get('state') or 'queued')),
                        "expected_revision": int(existing_task.get("expected_revision") or 1),
                        "lease": existing_task.get("lease"),
                        "input_fingerprint": _digest(
                            {
                                "shard_input_fingerprint": shard.input_fingerprint,
                                "skill_id": skill_id,
                                "manifest_digest": run.manifest_digest,
                            }
                        ),
                        "result_digest": existing_task.get("result_digest"),
                    },
                )
            existing_candidate = self.store.get(
                "bulk_migration_candidates", candidate_id
            ) or {}
            self.store.put(
                "bulk_migration_candidates",
                candidate_id,
                {
                    **existing_candidate,
                    "candidate_id": candidate_id,
                    "run_id": run.run_id,
                    "shard_id": shard.shard_id,
                    "employee_id": run.principal,
                    "state": shard.candidate_state,
                    "candidate_digest": (
                        str(existing_candidate.get("candidate_digest") or "")
                        or _digest(
                            {
                                "manifest_digest": run.manifest_digest,
                                "input_fingerprint": shard.input_fingerprint,
                            }
                        )
                    ),
                    "production_changed": False,
                    "active_transition": False,
                },
            )
            if shard.last_checkpoint_digest:
                checkpoint_id = shard.last_checkpoint_digest
                if not self.store.get("bulk_migration_checkpoints", checkpoint_id):
                    self.store.put(
                        "bulk_migration_checkpoints",
                        checkpoint_id,
                        {
                            "checkpoint_digest": checkpoint_id,
                            "run_id": run.run_id,
                            "shard_id": shard.shard_id,
                            "employee_id": run.principal,
                            "state": shard.state,
                            "execution_count": shard.execution_count,
                            "retry_count": shard.retry_count,
                            "result_digest": shard.result_digest,
                            "reason_code": shard.reason_code,
                        },
                    )

    def find_idempotent(self, principal: str, key: str) -> BulkMigrationRun | None:
        record = self.store.get(
            "bulk_migration_idempotency", self._idempotency_record_id(principal, key)
        )
        return self.get(str(record["run_id"])) if record else None

    def list_runs(self) -> tuple[BulkMigrationRun, ...]:
        return tuple(
            self._run_from_record(item)
            for item in self.store.list("bulk_migration_runs", limit=1_000_000)
        )

    def checkpoint_history(self, run_id: str, shard_id: str) -> list[dict[str, object]]:
        rows = [
            item
            for item in self.store.list("bulk_migration_checkpoints", limit=1_000_000)
            if str(item.get("run_id") or "") == run_id
            and str(item.get("shard_id") or "") == shard_id
        ]
        rows.sort(key=lambda item: (int(item.get("execution_count") or 0), int(item.get("retry_count") or 0)))
        return rows

    def save_receipt(self, run: BulkMigrationRun, receipt: BulkMigrationReceipt) -> None:
        self.store.put(
            "bulk_migration_receipts",
            receipt.receipt_digest,
            {
                **receipt.semantic_payload(),
                "receipt_digest": receipt.receipt_digest,
                "run_id": run.run_id,
                "employee_id": run.principal,
            },
        )

    def save_approval(self, run: BulkMigrationRun, approval: dict[str, object]) -> None:
        self.store.put(
            "bulk_migration_approvals",
            run.run_id,
            {**approval, "run_id": run.run_id, "employee_id": run.principal},
        )

    def get_approval(self, run_id: str) -> dict[str, object] | None:
        return self.store.get("bulk_migration_approvals", run_id)

    def record_invocation(self, run: BulkMigrationRun, channel: Channel) -> None:
        invocation_digest = _digest(
            {
                "run_id": run.run_id,
                "principal": run.principal,
                "manifest_digest": run.manifest_digest,
                "channel": channel,
            }
        )
        self.store.put(
            "bulk_migration_invocations",
            invocation_digest,
            {
                "invocation_digest": invocation_digest,
                "run_id": run.run_id,
                "employee_id": run.principal,
                "channel": channel,
                "manifest_digest": run.manifest_digest,
                "semantic_identity_digest": _digest(
                    {
                        "principal": run.principal,
                        "manifest_digest": run.manifest_digest,
                        "idempotency_key": run.idempotency_key,
                    }
                ),
                "production_changed": False,
                "active_transition": False,
            },
        )

    def record_stage_results(
        self,
        *,
        run: BulkMigrationRun,
        shard_id: str,
        results: Iterable[Mapping[str, object]],
    ) -> None:
        suffix = shard_id.split(":", 1)[-1]
        attempt = next(item.last_attempt_digest for item in run.shards if item.shard_id == shard_id)
        for raw in results:
            receipt = _stage_receipt(run.run_id, run.principal, shard_id, attempt, raw)
            item = dict(raw)
            skill_id = str(item.get("skill_id") or "")
            if not skill_id:
                raise BulkMigrationPolicyError("STAGE_SKILL_ID_REQUIRED")
            task_package_id = f"taskpkg:{suffix}:{skill_id}"
            task = self.store.get("bulk_migration_task_packages", task_package_id)
            if not task or str(task.get("run_id") or "") != run.run_id:
                raise BulkMigrationPolicyError("TASK_PACKAGE_NOT_FOUND")
            output_digest = str(item.get("output_digest") or "")
            evidence_digest = str(item.get("evidence_digest") or "")
            state = str(item.get("status") or "not_run")
            self.store.put(
                "bulk_migration_task_packages",
                task_package_id,
                {
                    **task,
                    "state": state,
                    "result_digest": output_digest or None,
                    "evidence_digest": evidence_digest,
                    "reason_codes": list(item.get("reason_codes") or ()),
                    "model_invocation_count": int(
                        item.get("model_invocation_count") or 0
                    ),
                    "model_input_bytes": int(item.get("model_input_bytes") or 0),
                },
            )
            stage_receipt_digest = receipt['stage_receipt_digest']
            existing = self.store.get('bulk_migration_stage_results', stage_receipt_digest)
            if existing and {key:value for key,value in existing.items() if key != 'updated_at'} != receipt:
                raise BulkMigrationPolicyError('STAGE_RECEIPT_INTEGRITY_FAILURE')
            self.store.put('bulk_migration_stage_results', stage_receipt_digest, receipt)

    def hierarchy(self, run_id: str) -> dict[str, object]:
        run = self.store.get("bulk_migration_runs", run_id)
        if not run:
            raise BulkMigrationPolicyError("RUN_NOT_FOUND")
        project_id = str(run["project_id"])
        by_run = lambda collection: [
            item
            for item in self.store.list(collection, limit=1_000_000)
            if str(item.get("run_id") or "") == run_id
        ]
        return {
            "project": self.store.get("bulk_migration_projects", project_id),
            "import_run": run,
            "shards": by_run("bulk_migration_shards"),
            "task_packages": by_run("bulk_migration_task_packages"),
            "candidates": by_run("bulk_migration_candidates"),
            "receipts": by_run("bulk_migration_receipts"),
        }


class BulkMigrationOrchestrator:
    """One channel-neutral application service for migration run control."""

    def __init__(
        self,
        repository: BulkMigrationRepository,
        *,
        clock: Any | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc).isoformat())

    @staticmethod
    def _shards(
        manifest: BulkMigrationManifest,
        object_fingerprints: tuple[str, ...],
    ) -> tuple[BulkMigrationShard, ...]:
        if not object_fingerprints:
            raise BulkMigrationPolicyError("EMPTY_SELECTOR_EXPANSION")
        size = manifest.max_objects_per_shard
        capacity = 1
        if manifest.metadata_execution is not None:
            metadata=parse_metadata_execution_closure(manifest.metadata_execution)
            if (len(object_fingerprints)!=metadata.source_record_count
                or _digest(object_fingerprints)!=metadata.source_record_set_digest):
                raise BulkMigrationPolicyError('METADATA_SELECTOR_EXPANSION_DRIFT')
            size=metadata.records_per_shard
            capacity=metadata.candidate_capacity_per_record
        result: list[BulkMigrationShard] = []
        for offset in range(0, len(object_fingerprints), size):
            fingerprints = object_fingerprints[offset : offset + size]
            fingerprint = _digest(
                {
                    "manifest_digest": manifest.manifest_digest,
                    "selector_digest": manifest.selector.selector_digest,
                    "object_fingerprints": list(fingerprints),
                    "offset": offset,
                }
            )
            result.append(
                BulkMigrationShard(
                    shard_id="shard:" + fingerprint.removeprefix("sha256:")[:24],
                    input_fingerprint=fingerprint,
                    atomic_object_count=len(fingerprints)*capacity,
                    last_checkpoint_digest=_digest(
                        {"state": "queued", "input_fingerprint": fingerprint}
                    ),
                )
            )
        return tuple(result)

    @staticmethod
    def _run_semantic_digest(
        manifest_digest: str,
        *,
        control_state: str,
        candidate_state: str,
        shards: tuple[BulkMigrationShard, ...],
        stage_states: Mapping[str, str] | None = None,
        output_digest: str | None = None,
        candidate_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        attention_refs: tuple[str, ...] = (),
        retry_count: int = 0,
        cache_hits: int = 0,
        model_invocation_count: int = 0,
        model_input_bytes: int = 0,
        service_stage_receipt_refs: Mapping[str, str] | None = None,
    ) -> str:
        return _digest(
            {
                "manifest_digest": manifest_digest,
                "control_state": control_state,
                "candidate_state": candidate_state,
                "shards": [item.semantic_payload() for item in shards],
                "stage_states": dict(sorted((stage_states or {}).items())),
                "output_digest": output_digest,
                "candidate_refs": list(candidate_refs),
                "evidence_refs": list(evidence_refs),
                "attention_refs": list(attention_refs),
                "retry_count": retry_count,
                "cache_hits": cache_hits,
                "model_invocation_count": model_invocation_count,
                "model_input_bytes": model_input_bytes,
                "production_changed": False,
                "active_transition": False,
                **({'service_stage_receipt_refs':dict(sorted(service_stage_receipt_refs.items()))}
                   if service_stage_receipt_refs else {}),
            }
        )

    def _submit(
        self,
        *,
        principal: str,
        manifest: BulkMigrationManifest,
        channel: Channel,
        object_fingerprints: tuple[str, ...],
    ) -> BulkMigrationRun:
        if channel not in {"ui", "rest", "mcp", "cli"}:
            raise BulkMigrationPolicyError(f"UNSUPPORTED_CHANNEL:{channel}")
        shards = self._shards(manifest, object_fingerprints)
        existing = self.repository.find_idempotent(principal, manifest.idempotency_key)
        if existing:
            if existing.manifest_digest != manifest.manifest_digest:
                raise BulkMigrationPolicyError(
                    "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_MANIFEST"
                )
            if tuple(item.input_fingerprint for item in existing.shards) != tuple(item.input_fingerprint for item in shards):
                raise BulkMigrationPolicyError('IDEMPOTENCY_SELECTOR_EXPANSION_DRIFT')
            if existing.control_state == 'initializing':
                existing = self.repository.initialize(manifest, existing)
            self.repository.record_invocation(existing, channel)
            return existing
        candidate_refs = tuple(
            f"candidate:{item.shard_id.split(':', 1)[-1]}" for item in shards
        )
        stage_states = {stage: "queued" for stage in manifest.requested_skill_stages}
        run_seed = {
            "principal": principal,
            "manifest_digest": manifest.manifest_digest,
            "idempotency_key": manifest.idempotency_key,
        }
        run_id = "migration_" + _digest(run_seed).removeprefix("sha256:")[:24]
        semantic_digest = self._run_semantic_digest(
            manifest.manifest_digest,
            control_state="queued",
            candidate_state="captured",
            shards=shards,
            stage_states=stage_states,
            candidate_refs=candidate_refs,
        )
        run = BulkMigrationRun(
            run_id=run_id,
            principal=principal,
            project_id=manifest.project_id,
            manifest_digest=manifest.manifest_digest,
            idempotency_key=manifest.idempotency_key,
            control_state="queued",
            candidate_state="captured",
            shards=shards,
            stage_states=stage_states,
            input_digest=manifest.manifest_digest,
            output_digest=None,
            candidate_refs=candidate_refs,
            evidence_refs=(),
            attention_refs=(),
            retry_count=0,
            cache_hits=0,
            model_invocation_count=0,
            model_input_bytes=0,
            started_at=self.clock(),
            completed_at=None,
            last_immutable_checkpoint_digest=_digest(
                [item.last_checkpoint_digest for item in shards]
            ),
            semantic_digest=semantic_digest,
            ui_url=f"/ontology/migrations/{run_id}",
            mcp_invocation_ref={"tool": "boi_job_status", "job_id": run_id},
        )
        run = self.repository.initialize(manifest, run)
        self.repository.record_invocation(run, channel)
        return run

    def submit(
        self,
        *,
        principal: str,
        manifest: BulkMigrationManifest,
        channel: Channel,
    ) -> BulkMigrationRun:
        fingerprints = tuple(
            _digest(
                {
                    "selector_digest": manifest.selector.selector_digest,
                    "ordinal": index,
                }
            )
            for index in range(manifest.atomic_object_count)
        )
        return self._submit(
            principal=principal,
            manifest=manifest,
            channel=channel,
            object_fingerprints=fingerprints,
        )

    def submit_expanded_selector(
        self,
        *,
        principal: str,
        manifest: BulkMigrationManifest,
        channel: Channel,
        expanded_object_fingerprints: Iterable[str],
    ) -> BulkMigrationRun:
        fingerprints = tuple(str(item) for item in expanded_object_fingerprints)
        return self._submit(
            principal=principal,
            manifest=manifest,
            channel=channel,
            object_fingerprints=fingerprints,
        )

    def get_run(self, *, principal: str, run_id: str) -> BulkMigrationRun:
        run = self.repository.get(run_id)
        if run is None:
            raise BulkMigrationPolicyError("RUN_NOT_FOUND")
        if run.principal != principal:
            raise BulkMigrationPolicyError("RUN_ACCESS_DENIED")
        return run

    @classmethod
    def revised_run(cls, run: BulkMigrationRun, **changes: object) -> BulkMigrationRun:
        """Pure revision construction; no repository or authority transition."""
        if ('shards' not in changes and changes.get('candidate_state') in {
            'approval_ready','candidate_preview_ready','approved','release_proposed'}
            and all(shard.state == 'completed' for shard in run.shards)):
            changes['shards'] = tuple(replace(shard,candidate_state=str(changes['candidate_state'])) for shard in run.shards)
        updated = replace(run, **changes)
        updated = replace(
            updated,
            last_immutable_checkpoint_digest=_digest([item.last_checkpoint_digest for item in updated.shards]),
            semantic_digest=cls._run_semantic_digest(
                updated.manifest_digest,
                control_state=updated.control_state,
                candidate_state=updated.candidate_state,
                shards=updated.shards,
                stage_states=updated.stage_states,
                output_digest=updated.output_digest,
                candidate_refs=updated.candidate_refs,
                evidence_refs=updated.evidence_refs,
                attention_refs=updated.attention_refs,
                retry_count=updated.retry_count,
                cache_hits=updated.cache_hits,
                model_invocation_count=updated.model_invocation_count,
                model_input_bytes=updated.model_input_bytes,
                service_stage_receipt_refs=updated.service_stage_receipt_refs,
            ),
        )
        return updated

    def _replace_run(self, run: BulkMigrationRun, *, stage_results=(), stage_shard_id=None,
                     service_receipts=(), task_execution=None,
                     **changes: object) -> BulkMigrationRun:
        if run.control_state == 'initializing':
            raise BulkMigrationPolicyError('RUN_INITIALIZATION_INCOMPLETE')
        updated = self.revised_run(run, **changes)
        extra={'task_execution':task_execution} if task_execution is not None else {}
        if not self.repository.compare_and_put(run, updated, stage_results=stage_results, shard_id=stage_shard_id,
                                               service_receipts=service_receipts,**extra):
            raise BulkMigrationPolicyError('RUN_REVISION_CONFLICT')
        return updated

    def record_service_stage_evidence(self, *, principal, run_id, pipeline_contract_id,
                                      stage_values, executor_code_digest):
        """Deterministic-service evidence only; never exposed to a Skill or model.

        Values are frozen structured outputs/receipt references, never raw SQL or
        operational rows. The service does not obtain execution authority here.
        """
        from .bulk_migration_execution import NORTH_STAR_ETCH_PIPELINE_V1
        run = self.get_run(principal=principal, run_id=run_id)
        manifest = self.repository.manifest_payload(run)
        contract = NORTH_STAR_ETCH_PIPELINE_V1
        if (pipeline_contract_id != manifest.get('pipeline_contract_id') or
            pipeline_contract_id != contract.contract_id or set(stage_values) != set(contract.required_stage_ids)):
            raise BulkMigrationPolicyError('SERVICE_STAGE_CONTRACT_MISMATCH')
        _require_digest(executor_code_digest, field='executor_code_digest')
        BulkMigrationManifest.validate_safe_value(stage_values)
        base_refs = {shard.shard_id:dict(shard.stage_receipt_refs) for shard in run.shards}
        receipts = []
        for stage, value in sorted(stage_values.items()):
            body = {'contract_version':'boi/service-stage-receipt@0.2.0',
                'run_id':run_id, 'employee_id':principal, 'manifest_digest':run.manifest_digest,
                'pipeline_contract_id':pipeline_contract_id, 'stage_id':stage, 'status':'pass',
                'output':value, 'output_digest':_digest(value), 'evidence_digest':_digest(value),
                'executor_code_digest':executor_code_digest, 'base_stage_receipt_refs':base_refs,
                'production_changed':False, 'active_transition':False}
            receipts.append({**body,'stage_receipt_digest':_digest(body)})
        refs = {r['stage_id']:r['stage_receipt_digest'] for r in receipts}
        return self._replace_run(run, service_stage_receipt_refs=refs, service_receipts=receipts)

    def pause(self, *, principal: str, run_id: str) -> BulkMigrationRun:
        run = self.get_run(principal=principal, run_id=run_id)
        if run.control_state not in {"queued", "running"}:
            raise BulkMigrationPolicyError(f"RUN_NOT_PAUSABLE:{run.control_state}")
        return self._replace_run(run, control_state="paused")

    def cancel(self, *, principal: str, run_id: str) -> BulkMigrationRun:
        run = self.get_run(principal=principal, run_id=run_id)
        if run.control_state == "cancelled":
            return run
        return self._replace_run(run, control_state="cancelled")

    def resume(self, *, principal: str, run_id: str) -> BulkMigrationRun:
        run = self.get_run(principal=principal, run_id=run_id)
        shards = tuple(
            item
            if item.state in {"completed", "failed"}
            else replace(item, state="queued")
            for item in run.shards
        )
        return self._replace_run(run, control_state="queued", shards=shards)

    def _replace_shard(
        self,
        *,
        principal: str,
        run_id: str,
        shard_id: str,
        transform: Any,
    ) -> BulkMigrationRun:
        run = self.get_run(principal=principal, run_id=run_id)
        if not any(item.shard_id == shard_id for item in run.shards):
            raise BulkMigrationPolicyError("SHARD_NOT_FOUND")
        shards = tuple(
            transform(item) if item.shard_id == shard_id else item
            for item in run.shards
        )
        return self._replace_run(run, shards=shards)

    def mark_shard_completed(
        self,
        *,
        principal: str,
        run_id: str,
        shard_id: str,
        result_digest: str,
    ) -> BulkMigrationRun:
        _require_digest(result_digest, field="result_digest")

        def complete(item: BulkMigrationShard) -> BulkMigrationShard:
            if item.state == "completed":
                if item.result_digest != result_digest:
                    raise BulkMigrationPolicyError('COMPLETED_SHARD_RESULT_DRIFT')
                return item
            if item.state == 'failed':
                raise BulkMigrationPolicyError('FAILED_SHARD_RETRY_REQUIRED')
            checkpoint = _digest(
                {
                    "input_fingerprint": item.input_fingerprint,
                    "state": "completed",
                    "result_digest": result_digest,
                }
            )
            return replace(
                item,
                state="completed",
                execution_count=item.execution_count + 1,
                result_digest=result_digest,
                reason_code=None,
                last_checkpoint_digest=checkpoint,
            )

        return self._replace_shard(
            principal=principal,
            run_id=run_id,
            shard_id=shard_id,
            transform=complete,
        )

    def mark_shard_failed(
        self,
        *,
        principal: str,
        run_id: str,
        shard_id: str,
        reason_code: str,
    ) -> BulkMigrationRun:
        if not reason_code.strip():
            raise BulkMigrationPolicyError("FAILURE_REASON_REQUIRED")

        def fail(item: BulkMigrationShard) -> BulkMigrationShard:
            if item.state == 'completed':
                raise BulkMigrationPolicyError('COMPLETED_SHARD_FAILURE_FORBIDDEN')
            if item.state == 'failed':
                if item.reason_code != reason_code:
                    raise BulkMigrationPolicyError('FAILED_SHARD_RETRY_REQUIRED')
                return item
            checkpoint = _digest(
                {
                    "input_fingerprint": item.input_fingerprint,
                    "state": "failed",
                    "reason_code": reason_code,
                }
            )
            return replace(
                item,
                state="failed",
                execution_count=item.execution_count + 1,
                reason_code=reason_code,
                last_checkpoint_digest=checkpoint,
            )

        return self._replace_shard(
            principal=principal,
            run_id=run_id,
            shard_id=shard_id,
            transform=fail,
        )

    def retry_shard(
        self, *, principal: str, run_id: str, shard_id: str
    ) -> BulkMigrationRun:
        def retry(item: BulkMigrationShard) -> BulkMigrationShard:
            if item.state == "completed":
                raise BulkMigrationPolicyError("COMPLETED_SHARD_RETRY_FORBIDDEN")
            if item.state != "failed":
                raise BulkMigrationPolicyError(f"SHARD_NOT_RETRYABLE:{item.state}")
            if item.retry_count >= 1:
                raise BulkMigrationPolicyError("SHARD_RETRY_LIMIT_EXCEEDED")
            return replace(
                item,
                state="queued",
                retry_count=item.retry_count + 1,
                reason_code=None,
                last_checkpoint_digest=_digest(
                    {
                        "input_fingerprint": item.input_fingerprint,
                        "state": "queued",
                        "retry_count": item.retry_count + 1,
                    }
                ),
            )

        return self._replace_shard(
            principal=principal,
            run_id=run_id,
            shard_id=shard_id,
            transform=retry,
        )

    def record_pipeline_result(
        self, *, principal: str, run_id: str, shard_id: str,
        pipeline_digest: str, harness_state: str,
        stage_results: Iterable[Mapping[str, object]],
        evidence_refs: Iterable[str] = (), attention_refs: Iterable[str] = (),
        model_invocation_count: int = 0, model_input_bytes: int = 0,
        task_execution=None,
    ) -> BulkMigrationRun:
        _require_digest(pipeline_digest, field="pipeline_digest")
        run = self.get_run(principal=principal, run_id=run_id)
        if run.control_state=='initializing':raise BulkMigrationPolicyError('RUN_INITIALIZATION_INCOMPLETE')
        if run.control_state in {'cancelled','paused'}:
            raise BulkMigrationPolicyError('RUN_NOT_EXECUTABLE')
        shard = next((item for item in run.shards if item.shard_id == shard_id), None)
        if shard is None:
            raise BulkMigrationPolicyError("SHARD_NOT_FOUND")
        results = tuple(dict(item) for item in stage_results)
        if not results:
            raise BulkMigrationPolicyError("PIPELINE_STAGE_RESULTS_REQUIRED")
        if len({str(item.get("skill_id")) for item in results}) != len(results):
            raise BulkMigrationPolicyError("PIPELINE_DUPLICATE_STAGE_RESULT")
        for item in results:
            if str(item.get("skill_id") or "") not in run.stage_states:
                raise BulkMigrationPolicyError("PIPELINE_STAGE_OUTSIDE_MANIFEST")
            if item.get("status") == "pass" and not item.get("evidence_digest"):
                raise BulkMigrationPolicyError("PIPELINE_PASS_EVIDENCE_REQUIRED")
        states = {str(item["skill_id"]):str(item.get("status") or "not_run") for item in results}
        evidence_refs = tuple(sorted(set(str(item) for item in evidence_refs)))
        attention_refs = tuple(sorted(set(str(item) for item in attention_refs)))
        attempt_digest = _digest({'pipeline_digest':pipeline_digest,'harness_state':harness_state,
            'stage_results':sorted(results,key=lambda item:str(item['skill_id'])),
            'evidence_refs':evidence_refs,'attention_refs':attention_refs,
            'model_invocation_count':model_invocation_count,'model_input_bytes':model_input_bytes})
        receipt_refs = {str(item['skill_id']):_stage_receipt(run.run_id, run.principal,
            shard_id, attempt_digest, item)['stage_receipt_digest'] for item in results}
        if shard.state in {"completed", "failed"}:
            if shard.result_digest == pipeline_digest and shard.stage_states == states and shard.last_attempt_digest == attempt_digest:
                if not self.repository.compare_and_put(run, run, stage_results=results, shard_id=shard_id):
                    raise BulkMigrationPolicyError('RUN_REVISION_CONFLICT')
                return run
            reason = ("COMPLETED_SHARD_RESULT_DRIFT" if shard.state == "completed"
                      else "FAILED_SHARD_RETRY_REQUIRED")
            raise BulkMigrationPolicyError(reason)
        if model_invocation_count < 0 or model_input_bytes < 0:
            raise BulkMigrationPolicyError("PIPELINE_METRICS_INVALID")
        failed = next((item for item in results if item.get("status") != "pass"), None)
        reasons = tuple(str(value) for value in (failed or {}).get("reason_codes") or ())
        new_evidence = tuple(sorted(set(shard.evidence_refs).union(str(item) for item in evidence_refs)))
        new_attention = tuple(sorted(set(str(item) for item in attention_refs)))
        checkpoint = _digest({"input_fingerprint":shard.input_fingerprint,
            "state":"failed" if failed else "completed", "pipeline_digest":pipeline_digest,
            "stage_states":states, "retry_count":shard.retry_count,
            "evidence_refs":new_evidence, "attention_refs":new_attention})
        updated_shard = replace(shard, state="failed" if failed else "completed",
            candidate_state=harness_state, execution_count=shard.execution_count+1,
            result_digest=pipeline_digest, reason_code=(reasons[0] if reasons else "PIPELINE_STAGE_FAILED") if failed else None,
            last_checkpoint_digest=checkpoint, stage_states=states,
            last_attempt_digest=attempt_digest,
            stage_receipt_refs=receipt_refs,
            evidence_refs=new_evidence, attention_refs=new_attention,
            model_invocation_count=shard.model_invocation_count+int(model_invocation_count),
            model_input_bytes=shard.model_input_bytes+int(model_input_bytes))
        shards = tuple(updated_shard if item.shard_id == shard_id else item for item in run.shards)
        all_complete = all(item.state == "completed" for item in shards)
        any_failed = any(item.state == "failed" for item in shards)
        any_pending = any(item.state not in {"completed", "failed"} for item in shards)
        aggregate_states = {}
        for stage in run.stage_states:
            observed = [item.stage_states.get(stage, "queued") for item in shards]
            aggregate_states[stage] = next((status for status in
                ("fail", "blocked", "partial", "flag", "not_run", "skip", "queued") if status in observed), "pass")
        candidate_state = next((state for state in ("blocked", "attention_required", "partial")
            if any(item.candidate_state == state for item in shards)),
            harness_state if all_complete else "captured")
        # Retain unattributed historical counters while adding per-shard metrics.
        prior_calls = max(0, run.model_invocation_count-sum(item.model_invocation_count for item in run.shards))
        prior_bytes = max(0, run.model_input_bytes-sum(item.model_input_bytes for item in run.shards))
        output_digest = (pipeline_digest if len(shards)==1 else _digest({
            "shard_results":[(item.shard_id,item.result_digest,item.state) for item in sorted(shards,key=lambda s:s.shard_id)]}))
        updated = self._replace_run(run, shards=shards, stage_results=results, stage_shard_id=shard_id,
            task_execution=task_execution,
            control_state="failed" if any_failed else "completed" if all_complete else "running",
            candidate_state=candidate_state, stage_states=aggregate_states,
            output_digest=output_digest,
            evidence_refs=tuple(sorted(set(run.evidence_refs).union(*(item.evidence_refs for item in shards)))),
            attention_refs=tuple(sorted(set().union(*(item.attention_refs for item in shards)))),
            model_invocation_count=prior_calls+sum(item.model_invocation_count for item in shards),
            model_input_bytes=prior_bytes+sum(item.model_input_bytes for item in shards),
            completed_at=self.clock() if not any_pending else None)
        return updated

    def mark_approval_ready(
        self,
        *,
        principal: str,
        run_id: str,
        required_checks: Iterable[Mapping[str, object]],
    ) -> BulkMigrationRun:
        run = self.get_run(principal=principal, run_id=run_id)
        checks = tuple(required_checks)
        if not checks:
            raise BulkMigrationPolicyError("REQUIRED_CHECKS_MISSING")
        for check in checks:
            if str(check.get("status") or "") != "pass":
                raise BulkMigrationPolicyError("REQUIRED_CHECK_NOT_PASS")
            evidence_digest = str(check.get("evidence_digest") or "")
            _require_digest(evidence_digest, field="check.evidence_digest")
        if any(item.state != "completed" for item in run.shards):
            raise BulkMigrationPolicyError("INCOMPLETE_SHARD_BLOCKS_APPROVAL_READY")
        from .bulk_migration_review import review_context
        review_context(self.repository, run)
        return self._replace_run(run, candidate_state="approval_ready")

    def mark_candidate_preview_ready(
        self,
        *,
        principal: str,
        run_id: str,
    ) -> BulkMigrationRun:
        """Record non-production preview readiness without granting approval authority."""

        run = self.get_run(principal=principal, run_id=run_id)
        if run.control_state != "completed":
            raise BulkMigrationPolicyError("INCOMPLETE_RUN_BLOCKS_CANDIDATE_PREVIEW")
        return self._replace_run(run, candidate_state="candidate_preview_ready")

    def finalize_receipt(
        self,
        *,
        principal: str,
        run_id: str,
        pipeline_contract_id: str | None = None,
        required_stage_ids: Iterable[str] = (),
        optional_stage_ids: Iterable[str] = (),
        stage_digests: Mapping[str, str],
        component_digests: Iterable[str],
        checks: Iterable[Mapping[str, object]],
        token_metrics: Mapping[str, int],
    ) -> BulkMigrationReceipt:
        run = self.get_run(principal=principal, run_id=run_id)
        from .bulk_migration_qualification import required_stage_evidence
        manifest = self.repository.manifest_payload(run)
        (actual_contract, normalized_required, normalized_optional, missing_required,
         normalized_stages, authoritative_checks) = required_stage_evidence(run, manifest, self.repository)
        requested_contract = pipeline_contract_id
        pipeline_contract_id = actual_contract
        normalized_components = tuple(sorted(
            _require_digest(str(value), field="component_digest") for value in component_digests if value))
        normalized_checks_list = list(authoritative_checks)
        if requested_contract is not None and requested_contract != actual_contract:
            normalized_checks_list.append({"check_id":"requested-contract", "status":"partial",
                "reason_code":"PIPELINE_CONTRACT_REQUEST_MISMATCH",
                "evidence_digest":_digest({"actual":actual_contract,"requested":requested_contract})})
        for key, value in stage_digests.items():
            if key in normalized_stages and value != normalized_stages[key]:
                normalized_checks_list.append({"check_id":"stage-digest:"+key, "status":"fail",
                    "reason_code":"STAGE_OUTPUT_DIGEST_MISMATCH"})
        for raw in checks:
            check = dict(raw)
            if check.get("stage_id") in normalized_required:
                continue  # Persisted exact stage closure, never a caller's pass string.
            status = check.get("status")
            if status not in {"pass","fail","blocked","partial","flag","skip","not_run"}:
                check.update(status="fail", reason_code="CHECK_STATUS_INVALID")
            elif status == "pass" and not check.get("evidence_digest"):
                check.update(status="fail", reason_code="CHECK_PASS_EVIDENCE_MISSING")
            normalized_checks_list.append(check)
        normalized_checks = tuple(normalized_checks_list)
        statuses = [str(item.get("status") or "not_run") for item in normalized_checks]
        passed = statuses.count("pass")
        failed = sum(status in {"fail", "blocked"} for status in statuses)
        partial = sum(status in {"partial", "flag", "skip", "not_run"} for status in statuses)
        status = "failed" if failed else "partial" if partial or not statuses else "pass"
        candidate_package_digest = _digest(
            {
                "manifest_digest": run.manifest_digest,
                "shard_inputs": [item.input_fingerprint for item in run.shards],
                "shard_results": [item.result_digest for item in run.shards],
            }
        )
        payload = {
            "receipt_version": "boi/bulk-migration-receipt@0.2.0",
            "pipeline_contract_id": pipeline_contract_id,
            "required_stage_ids": list(normalized_required),
            "optional_stage_ids": list(normalized_optional),
            "missing_required_stage_ids": missing_required,
            "manifest_digest": run.manifest_digest,
            "run_digest": run.semantic_digest,
            "stage_digests": normalized_stages,
            "component_digests": list(normalized_components),
            "candidate_package_digest": candidate_package_digest,
            "attention_digest": _digest(run.attention_refs),
            "checks": normalized_checks,
            "passed_check_count": passed,
            "failed_check_count": failed,
            "partial_check_count": partial,
            "token_metrics": {str(key): int(value) for key, value in sorted(token_metrics.items())},
            "status": status,
            "production_changed": False,
            "active_transition": False,
        }
        receipt = BulkMigrationReceipt(
            pipeline_contract_id=pipeline_contract_id,
            required_stage_ids=normalized_required,
            optional_stage_ids=normalized_optional,
            missing_required_stage_ids=tuple(missing_required),
            manifest_digest=run.manifest_digest,
            run_digest=run.semantic_digest,
            stage_digests=normalized_stages,
            component_digests=normalized_components,
            candidate_package_digest=candidate_package_digest,
            attention_digest=_digest(run.attention_refs),
            checks=normalized_checks,
            passed_check_count=passed,
            failed_check_count=failed,
            partial_check_count=partial,
            token_metrics=dict(payload["token_metrics"]),
            status=status,
            production_changed=False,
            active_transition=False,
            receipt_digest=_digest(payload),
        )
        self.repository.save_receipt(run, receipt)
        return receipt

    def record_review_approval(
        self,
        *,
        principal: str,
        run_id: str,
        expected_manifest_digest: str,
        expected_before_hashes: Mapping[str, str],
        preview_digest: str,
        expected_qualification_receipt_digest: str | None = None,
        expected_run_digest: str | None = None,
        expected_candidate_digest: str | None = None,
    ) -> dict[str, object]:
        run = self.get_run(principal=principal, run_id=run_id)
        if run.candidate_state not in {"approval_ready", "candidate_preview_ready", "approved"}:
            raise BulkMigrationPolicyError("CANDIDATE_NOT_APPROVAL_READY")
        if expected_run_digest is not None and run.semantic_digest != expected_run_digest:
            raise BulkMigrationPolicyError('REVIEW_RUN_REVISION_CONFLICT')
        _require_digest(preview_digest, field="preview_digest")
        from .bulk_migration_review import persist_review
        return persist_review(self.repository, run, self.revised_run(run, candidate_state='approved'),
            {'manifest_digest':expected_manifest_digest, 'before_hashes':dict(expected_before_hashes),
             'preview_digest':preview_digest,
             'candidate_digest':expected_candidate_digest,
             'qualification_receipt_digest':expected_qualification_receipt_digest})

    def assert_approval_current(
        self,
        *,
        principal: str,
        run_id: str,
        manifest_digest: str,
        before_hashes: Mapping[str, str],
        preview_digest: str,
    ) -> dict[str, object]:
        run = self.get_run(principal=principal, run_id=run_id)
        from .bulk_migration_review import current_approval
        approval = current_approval(self.repository, run)
        if (
            str(approval.get("manifest_digest") or "") != manifest_digest
            or dict(approval.get("before_hashes") or {}) != dict(before_hashes)
            or str(approval.get("preview_digest") or "") != preview_digest
        ):
            raise BulkMigrationPolicyError("STALE_APPROVAL")
        return approval

    def mark_release_proposed(
        self,
        *,
        principal: str,
        run_id: str,
        approval_receipt_digest: str,
        preview_digest: str,
    ) -> BulkMigrationRun:
        """Record proposal state only; this cannot create or activate a Release."""

        run = self.get_run(principal=principal, run_id=run_id)
        if run.candidate_state not in {"approved", "release_proposed"}:
            raise BulkMigrationPolicyError("CANDIDATE_NOT_APPROVED")
        from .bulk_migration_review import persist_proposal
        updated = self.revised_run(run, candidate_state='release_proposed')
        persist_proposal(self.repository, run, updated, approval_receipt_digest, preview_digest)
        return updated

    def record_release_proposal(self, *, principal, run_id, approval_receipt_digest, preview_digest):
        run = self.get_run(principal=principal, run_id=run_id)
        if run.candidate_state not in {'approved', 'release_proposed'}:
            raise BulkMigrationPolicyError('CANDIDATE_NOT_APPROVED')
        from .bulk_migration_review import persist_proposal
        return persist_proposal(self.repository, run, self.revised_run(run,candidate_state='release_proposed'),
                                approval_receipt_digest, preview_digest)
