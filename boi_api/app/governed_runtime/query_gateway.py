"""Internal QueryExecution contract and SQLite reference implementation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Callable, Literal
import uuid
import sqlite3

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from .query_plan_contracts import (
    CatalogSnapshot,
    LogicalQueryPlanCandidate,
    PlanValidationReceipt,
)
from .ledger import GovernedRuntimeLedger
from .multi_result_query_gateway import (
    MultiResultExploratoryExecutionRequest,
    MultiResultQueryExecution,
    MultiResultSqliteGateway,
    MultiResultSqliteSchema,
)
from .semantic_query_execution import (
    SemanticColdPathTrace,
    SemanticExplorationReceipt,
    SemanticExploratoryExecutionRequest,
    SemanticSqliteCompiler,
    capture_sqlite_planner_catalog,
)
from .semantic_query_planner import (
    CheckEvidenceStore,
    SemanticPlanValidationVerifier,
)
from .semantic_plan_reuse import QualifiedSemanticPlanStore
from .result_canonicalization import normalize_result_rows as _normalize_result_rows
from .semantic_binding_contract import Digest, Ref


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


class QueryExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: Literal["attested", "exploratory"]
    query_spec_id: str | None = None
    query_revision_digest: str | None = None
    parameters: dict[str, Any]
    domain_release_digest: str
    mapping_release_digest: str
    schema_release_digest: str
    signed_logical_plan_digest: str | None = None
    logical_plan: LogicalQueryPlanCandidate | None = None
    logical_plan_digest: str | None = None
    logical_plan_ref: str | None = None
    catalog_snapshot: CatalogSnapshot | None = None
    catalog_snapshot_digest: str | None = None
    plan_validation_receipt: PlanValidationReceipt | None = None
    plan_validation_receipt_digest: str | None = None
    principal: str
    purpose: str
    idempotency_key: str
    timeout_seconds: int = Field(default=30, ge=1, le=30)
    row_limit: int = Field(default=1000, ge=1, le=1000)

    @field_validator(
        "logical_plan",
        "catalog_snapshot",
        "plan_validation_receipt",
        mode="before",
    )
    @classmethod
    def normalize_legacy_contract_models(cls, value: object) -> object:
        """Accept historical contract instances without importing their module.

        The legacy planner exports structurally equivalent Pydantic models.
        Converting at the boundary preserves its regression surface while the
        canonical dependency closure remains bound to neutral contracts only.
        """

        if isinstance(value, BaseModel):
            return value.model_dump(mode="python")
        return value

    @model_validator(mode="after")
    def validate_execution_mode(self) -> "QueryExecutionRequest":
        registered = bool(self.query_spec_id and self.query_revision_digest)
        dynamic_fields = (
            self.logical_plan,
            self.logical_plan_digest,
            self.logical_plan_ref,
            self.catalog_snapshot,
            self.catalog_snapshot_digest,
            self.plan_validation_receipt,
            self.plan_validation_receipt_digest,
        )
        dynamic = self.logical_plan is not None
        if self.lane == "attested":
            if not registered or any(value is not None for value in dynamic_fields):
                raise ValueError("ATTESTED_REQUIRES_REGISTERED_QUERYSPEC")
            return self
        if registered == dynamic:
            raise ValueError("EXPLORATORY_REQUIRES_EXACTLY_ONE_QUERY_MODE")
        if dynamic:
            if self.query_spec_id is not None or self.query_revision_digest is not None:
                raise ValueError("DYNAMIC_PLAN_FORBIDS_QUERYSPEC")
            if not all(
                isinstance(value, str) and bool(value)
                for value in (
                    self.logical_plan_digest,
                    self.logical_plan_ref,
                    self.catalog_snapshot_digest,
                    self.plan_validation_receipt_digest,
                )
            ):
                raise ValueError("DYNAMIC_PLAN_BINDINGS_REQUIRED")
            if self.plan_validation_receipt is None:
                raise ValueError("PLAN_VALIDATION_RECEIPT_REQUIRED")
            if self.catalog_snapshot is None:
                raise ValueError("CATALOG_SNAPSHOT_REQUIRED")
            if self.logical_plan_digest != self.logical_plan.plan_digest:
                raise ValueError("LOGICAL_PLAN_DIGEST_MISMATCH")
            if self.catalog_snapshot_digest != self.logical_plan.catalog_snapshot_digest:
                raise ValueError("CATALOG_SNAPSHOT_DIGEST_MISMATCH")
            if self.catalog_snapshot.snapshot_digest != self.catalog_snapshot_digest:
                raise ValueError("CATALOG_SNAPSHOT_CONTENT_MISMATCH")
            if (
                self.catalog_snapshot.principal != self.principal
                or self.catalog_snapshot.purpose != self.purpose
            ):
                raise ValueError("CATALOG_SNAPSHOT_AUTHORIZATION_MISMATCH")
            validation = self.plan_validation_receipt
            if validation.status != "PASS" or validation.error_codes:
                raise ValueError("PLAN_VALIDATION_NOT_PASSING")
            if validation.receipt_digest != self.plan_validation_receipt_digest:
                raise ValueError("PLAN_VALIDATION_RECEIPT_DIGEST_MISMATCH")
            if validation.plan_digest != self.logical_plan_digest:
                raise ValueError("PLAN_VALIDATION_PLAN_MISMATCH")
            if validation.intent_digest != self.logical_plan.intent_digest:
                raise ValueError("PLAN_VALIDATION_INTENT_MISMATCH")
            if validation.catalog_snapshot_digest != self.catalog_snapshot_digest:
                raise ValueError("PLAN_VALIDATION_CATALOG_MISMATCH")
            if validation.policy_digest != self.logical_plan.policy_digest:
                raise ValueError("PLAN_VALIDATION_POLICY_MISMATCH")
            if validation.active_release_digest != self.catalog_snapshot.active_release_digest:
                raise ValueError("PLAN_VALIDATION_RELEASE_MISMATCH")
            required_checks = (
                validation.acl_checked,
                validation.schema_checked,
                validation.key_type_checked,
                validation.join_connectivity_checked,
                validation.cardinality_checked,
                validation.grain_checked,
                validation.unit_checked,
                validation.time_checked,
                validation.cost_checked,
                validation.compiler_capability_checked,
            )
            if not all(required_checks):
                raise ValueError("PLAN_VALIDATION_CHECK_INCOMPLETE")
            if self.signed_logical_plan_digest is not None:
                raise ValueError("DYNAMIC_SIGNED_PLAN_OVERRIDE_FORBIDDEN")
        return self


class QueryCapability(BaseModel):
    model_config = ConfigDict(frozen=True)

    backend: str
    verification_status: Literal["VERIFIED", "UNVERIFIED"]
    execution_enabled: bool
    lanes: tuple[str, ...]
    schema_status: Literal["CURRENT", "STALE", "UNVERIFIED"]
    schema_release_digest: str
    schema_expires_at: str


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: tuple[dict[str, Any], ...]
    row_count: int
    result_schema: tuple[tuple[str, str], ...]
    result_schema_digest: str
    result_digest: str


class ExecutionReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    computation_id: str
    query_revision_digest: str
    logical_plan_digest: str
    domain_release_digest: str
    mapping_release_digest: str
    schema_release_digest: str
    compiler_digest: str
    parameter_digest: str
    execution_artifact_ref: str
    execution_artifact_digest: str
    executed_sql: None = None
    backend_execution_id: str
    source_snapshot: str
    result_schema_digest: str
    row_count: int
    result_digest: str
    authorization_policy_digest: str
    started_at: str
    completed_at: str
    error_code: str | None = None


class QueryAttestation(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["PASS", "FAIL"]
    error_codes: tuple[str, ...]
    attester_digest: str


class ExplorationReceipt(BaseModel):
    model_config = ConfigDict(frozen=True)

    intent_digest: str
    logical_plan_digest: str
    domain_release_digest: str
    mapping_release_digest: str
    schema_release_digest: str
    compiler_digest: str
    parameter_digest: str
    catalog_snapshot_digest: str
    plan_validation_receipt_digest: str
    execution_artifact_ref: str
    execution_artifact_digest: str
    executed_sql: None = None
    backend_execution_id: str
    source_snapshot: str
    result_schema_digest: str
    row_count: int
    result_digest: str
    authorization_policy_digest: str
    result_status: Literal["PROVISIONAL"] = "PROVISIONAL"
    dry_run_status: Literal["PASS"] = "PASS"
    dry_run_digest: str
    started_at: str
    completed_at: str

    @property
    def receipt_digest(self) -> str:
        return _digest(self.model_dump(mode="json"))


class QueryExecution(BaseModel):
    model_config = ConfigDict(frozen=True)

    execution_id: str
    lane: Literal["attested", "exploratory"]
    status: Literal["SUCCEEDED", "BLOCKED", "FAILED"]
    result_status: Literal["ATTESTED", "PROVISIONAL", "BLOCKED"]
    result: QueryResult
    receipt: ExecutionReceipt
    attestation: QueryAttestation | None
    exploration_receipt: ExplorationReceipt | SemanticExplorationReceipt | None = None


def _parameter_digest(
    request: QueryExecutionRequest | SemanticExploratoryExecutionRequest,
) -> str:
    return _digest(request.parameters)


def _authorization_digest(
    request: QueryExecutionRequest | SemanticExploratoryExecutionRequest,
) -> str:
    return _digest(
        {
            "principal": request.principal,
            "purpose": request.purpose,
            "lane": request.lane,
            "policy": "boi.query-execution-policy@0.1.0",
        }
    )


def _result_schema(rows: tuple[dict[str, Any], ...]) -> tuple[tuple[str, str], ...]:
    if not rows:
        return ()
    first = rows[0]
    return tuple((name, type(value).__name__) for name, value in first.items())


class MetadataQualityGrant(BaseModel):
    """Server-resolved scalar data-audit grant, not an intake or query grant."""
    model_config=ConfigDict(extra='forbid',frozen=True,hide_input_in_errors=True)
    contract_version: Literal['boi/metadata-quality-grant@1']
    scope: Literal['isolated_candidate_preview']
    principal_ids: tuple[Ref,...] = Field(min_length=1)
    purposes: tuple[Ref,...] = Field(min_length=1)
    source_id: Ref
    source_snapshot_digest: Digest
    schema_snapshot_digest: Digest
    catalog_snapshot_digest: Digest
    source_policy_digest: Digest
    allowed_columns: dict[Ref,tuple[Ref,...]]
    effective_from: datetime
    stale_after: datetime

    @model_validator(mode='after')
    def explicit_scope(self):
        from .multi_result_query_gateway import _identifier
        if not self.allowed_columns or any(not columns for columns in self.allowed_columns.values()):
            raise ValueError('METADATA_QUALITY_SCOPE_EMPTY')
        for table,columns in self.allowed_columns.items():
            _identifier(table)
            for column in columns:_identifier(column)
        if any(v=='*' for v in (*self.principal_ids,*self.purposes)):
            raise ValueError('METADATA_QUALITY_EXPLICIT_GRANT_REQUIRED')
        if (self.effective_from.tzinfo is None or self.stale_after.tzinfo is None
            or not timedelta(0)<self.stale_after-self.effective_from<=timedelta(hours=24)):
            raise ValueError('METADATA_QUALITY_GRANT_WINDOW_INVALID')
        return self


def metadata_quality_grant_resolver_from_environment(environ):
    """Default-off existing Gateway capability; re-read pinned policy per use."""
    if str(environ.get('BOI_METADATA_QUALITY_ENABLED','')).lower() not in {'true','1','yes','on'}:
        return None
    path=environ.get('BOI_METADATA_QUALITY_POLICY_PATH','')
    expected=environ.get('BOI_METADATA_QUALITY_POLICY_DIGEST','')
    if not path or not expected:
        raise ValueError('METADATA_QUALITY_GRANT_CONFIGURATION_REQUIRED')
    def resolve():
        try:
            with Path(path).open('rb') as handle:raw=handle.read(131073)
            if len(raw)>131072 or 'sha256:'+hashlib.sha256(raw).hexdigest()!=expected:
                raise ValueError('drift')
            return MetadataQualityGrant.model_validate_json(raw)
        except (OSError,ValueError):
            raise ValueError('METADATA_QUALITY_GRANT_INVALID_OR_CHANGED') from None
    resolve()
    return resolve


class QueryGatewayService:
    def __init__(
        self,
        mes_path: Path | None,
        *,
        schema_release_digest: str = "sha256:schema-release-v1",
        schema_captured_at: datetime | None = None,
        schema_ttl_seconds: int = 86_400,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
        semantic_path: Path | None = None,
        semantic_ledger: GovernedRuntimeLedger | None = None,
        semantic_evidence_store: CheckEvidenceStore | None = None,
        semantic_plan_store: QualifiedSemanticPlanStore | None = None,
        cancellation_probe: Callable[[str], bool] | None = None,
        multi_result_gateway: MultiResultSqliteGateway | None = None,
        metadata_quality_grant_resolver: Callable[[], MetadataQualityGrant] | None = None,
    ) -> None:
        # Reference computations are not distributed as product knowledge.
        if mes_path is not None:
            raise ValueError('REFERENCE_FIXTURE_ADAPTER_NOT_DISTRIBUTED')
        self._historical_adapter = None
        self._idempotency: dict[str, tuple[str, QueryExecution]] = {}
        self._schema_release_digest = schema_release_digest
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        captured = schema_captured_at or self._clock()
        self._schema_captured_at = captured if captured.tzinfo else captured.replace(tzinfo=timezone.utc)
        self._schema_ttl_seconds = schema_ttl_seconds
        self._monotonic = monotonic or time.monotonic
        self._semantic_path = semantic_path
        self._semantic_ledger = semantic_ledger
        self._semantic_evidence_store = semantic_evidence_store
        self._semantic_plan_store = semantic_plan_store
        self._cancellation_probe = cancellation_probe
        self._multi_result_gateway = multi_result_gateway
        self._metadata_quality_grant_resolver = metadata_quality_grant_resolver
        self._semantic_source_digest = (
            "sha256:" + hashlib.sha256(semantic_path.read_bytes()).hexdigest()
            if semantic_path else ""
        )

    @classmethod
    def sqlite_reference(
        cls,
        mes_path: Path,
        **kwargs: Any,
    ) -> "QueryGatewayService":
        return cls(mes_path, **kwargs)

    @classmethod
    def unavailable(cls) -> "QueryGatewayService":
        return cls(None)

    @classmethod
    def sqlite_multi_result_reference(
        cls,
        path: Path,
        *,
        schema: MultiResultSqliteSchema,
        result_artifact_root: Path,
        contract_schema_digest: str | None = None,
        **kwargs: Any,
    ) -> "QueryGatewayService":
        clock = kwargs.get("clock")
        monotonic = kwargs.get("monotonic")
        cancellation_probe = kwargs.get("cancellation_probe")
        gateway = MultiResultSqliteGateway(
            path,
            schema=schema,
            result_artifact_root=result_artifact_root,
            clock=clock,
            monotonic=monotonic,
            cancellation_probe=cancellation_probe,
            contract_schema_digest=contract_schema_digest,
        )
        return cls(
            None,
            schema_release_digest=schema.schema_digest,
            multi_result_gateway=gateway,
            **kwargs,
        )

    @classmethod
    def sqlite_semantic_reference(
        cls, path: Path, *, ledger: GovernedRuntimeLedger,
        evidence_store: CheckEvidenceStore, **kwargs: Any,
    ) -> "QueryGatewayService":
        return cls(
            None,
            semantic_path=path,
            semantic_ledger=ledger,
            semantic_evidence_store=evidence_store,
            **kwargs,
        )

    def _schema_expires_at(self) -> datetime:
        return self._schema_captured_at + timedelta(seconds=self._schema_ttl_seconds)

    def profile_declared_mapping(self, *, inputs, principal, purpose, manifest_digest, expected_grant_digest):
        """Same Gateway owns bounded key scans; source metadata grants no DB read.

        Accepts a closed candidate mapping, never SQL. The scalar audit proves
        exact declared composite grain on the immutable SQLite snapshot. It is
        not a general query execution, semantic approval or Release operation.
        """
        from pydantic import TypeAdapter
        from .metadata_mapping_profile import parse_declared_metadata_mapping_inputs, DeclaredPropertyMappingV2, sqlite_logical_type_check
        from .multi_result_query_gateway import capture_multi_result_sqlite_schema, _identifier
        resolver=self._metadata_quality_grant_resolver
        backend=self._multi_result_gateway
        if resolver is None or backend is None:
            raise ValueError('METADATA_QUALITY_CAPABILITY_UNAVAILABLE')
        def authorize():
            grant=MetadataQualityGrant.model_validate(resolver().model_dump(mode='json'))
            current=self._clock()
            if current.tzinfo is None:current=current.replace(tzinfo=timezone.utc)
            if principal not in grant.principal_ids or purpose not in grant.purposes:
                raise ValueError('METADATA_QUALITY_ACCESS_DENIED')
            if not grant.effective_from<=current<grant.stale_after or self._schema_stale():
                raise ValueError('METADATA_QUALITY_GRANT_STALE')
            return grant
        grant=authorize()
        inputs=parse_declared_metadata_mapping_inputs(inputs)
        input_digest=_digest(inputs.model_dump(mode='json'))
        grant_digest=_digest(grant.model_dump(mode='json'))
        if grant_digest!=expected_grant_digest:
            raise ValueError('METADATA_QUALITY_GRANT_CHANGED')
        TypeAdapter(Digest).validate_python(manifest_digest)
        if len(inputs.properties)>100 or len(inputs.objects)>100 or len(inputs.relationships)>100:
            raise ValueError('METADATA_QUALITY_SHARD_LIMIT_EXCEEDED')
        if (inputs.source_id!=grant.source_id or inputs.policy_digest!=grant.source_policy_digest
            or inputs.catalog_snapshot_digest!=grant.catalog_snapshot_digest
            or inputs.schema_snapshot_digest!=grant.schema_snapshot_digest
            or inputs.schema_snapshot_digest!=self._schema_release_digest
            or inputs.source_snapshot_digest!=grant.source_snapshot_digest):
            raise ValueError('METADATA_QUALITY_SCOPE_OR_SNAPSHOT_MISMATCH')
        if any(p.physical.column not in grant.allowed_columns.get(p.physical.table,()) for p in inputs.properties):
            raise ValueError('METADATA_QUALITY_MAPPING_NOT_AUTHORIZED')
        def snapshot():
            current=capture_multi_result_sqlite_schema(backend.path,allowed_tables=backend.schema.allowed_tables)
            if (current.source_snapshot_digest!=grant.source_snapshot_digest
                or current.schema_digest!=backend.schema.schema_digest):
                raise ValueError('METADATA_QUALITY_SOURCE_DRIFT')
            return current
        schema=snapshot()
        for prop in inputs.properties:
            table=schema.table(prop.physical.table)
            column=next((c for c in table.columns if c.name==prop.physical.column),None) if table else None
            if column is None or column.data_type.casefold()!=prop.declared_data_type.casefold():
                raise ValueError('METADATA_QUALITY_PHYSICAL_TYPE_MISMATCH')
            if (isinstance(prop,DeclaredPropertyMappingV2)
                and not sqlite_logical_type_check(
                    column.data_type,prop.logical_primitive_type,
                    prop.physical.temporal_encoding,
                )['compatible']):
                raise ValueError('METADATA_QUALITY_LOGICAL_TYPE_MISMATCH')
        by_ref={p.physical.mapping_ref:p for p in inputs.properties}
        receipts=[];storage_receipts=[];relation_receipts=[];relation_reasons=[]
        deadline=self._monotonic()+30
        connection=sqlite3.connect('file:'+str(backend.path)+'?mode=ro',uri=True,timeout=30)
        try:
            from .latest_time_order import register_latest_time_functions
            register_latest_time_functions(connection)
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            connection.set_progress_handler(lambda:int(self._monotonic()>=deadline),100)
            for obj in inputs.objects:
                keys=[by_ref[ref].physical for ref in obj.logical_key_mapping_refs]
                table=_identifier(keys[0].table)
                key_names=[_identifier(key.column) for key in keys]
                nulls=' OR '.join(name+' IS NULL' for name in key_names)
                counts='SELECT COUNT(*),COALESCE(SUM('+nulls+'),0) FROM '+table
                duplicates=('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM '+table+
                    ' WHERE '+' AND '.join(name+' IS NOT NULL' for name in key_names)+
                    ' GROUP BY '+','.join(key_names)+' HAVING COUNT(*)>1)')
                scanned,null_rows=connection.execute(counts).fetchone()
                duplicate_rows=connection.execute(duplicates).fetchone()[0]
                body={'contract_version':'boi/object-key-quality@1','object_ref':obj.object_ref,
                    'mapping_input_digest':input_digest,'source_snapshot_digest':grant.source_snapshot_digest,
                    'schema_snapshot_digest':inputs.schema_snapshot_digest,'physical_schema_digest':schema.schema_digest,
                    'catalog_snapshot_digest':inputs.catalog_snapshot_digest,'policy_digest':inputs.policy_digest,
                    'grant_digest':grant_digest,'principal':principal,'purpose':purpose,'manifest_digest':manifest_digest,
                    'exact_grain':list(obj.logical_key_mapping_refs),'scanned_rows':scanned,
                    'null_key_rows':null_rows,'duplicate_key_rows':duplicate_rows,
                    'status':'pass' if null_rows==duplicate_rows==0 else 'fail',
                    'reason_codes':([] if null_rows==duplicate_rows==0 else ['DECLARED_OBJECT_GRAIN_NOT_UNIQUE_OR_NULL']),
                    'protected_query_digest':_digest([counts,duplicates])}
                receipts.append({**body,'evidence_digest':_digest(body)})
            for prop in inputs.properties:
                if not isinstance(prop,DeclaredPropertyMappingV2):continue
                physical=prop.physical;name=_identifier(physical.column)
                temporal=prop.physical.temporal_encoding
                expected=({'date':('text',),'datetime':('text',)}[prop.logical_primitive_type]
                    if temporal is not None else
                    {'string':('text',),'integer':('integer',),'number':('integer','real'),
                     'boolean':('integer',)}[prop.logical_primitive_type])
                storage='typeof('+name+') IN ('+','.join("'"+value+"'" for value in expected)+')'
                if prop.logical_primitive_type=='boolean':storage+=' AND '+name+' IN (0,1)'
                if prop.logical_primitive_type=='number':storage+=' AND '+name+' BETWEEN -1.7976931348623157e308 AND 1.7976931348623157e308'
                if temporal is not None:
                    temporal_valid=("boi_latest_time_key("+name+", '"+
                        temporal.representation+"') IS NOT NULL")
                    query=('SELECT COUNT(*), COALESCE(SUM('+name+' IS NULL),0), '+
                        'COALESCE(SUM('+name+' IS NOT NULL AND NOT ('+storage+')),0), '+
                        'COALESCE(SUM('+name+' IS NOT NULL AND ('+storage+') AND NOT ('+
                        temporal_valid+')),0) FROM '+_identifier(physical.table))
                    scanned,null_rows,invalid,invalid_temporal=connection.execute(query).fetchone()
                else:
                    query=('SELECT COUNT(*), COALESCE(SUM('+name+' IS NULL),0), '+
                        'COALESCE(SUM('+name+' IS NOT NULL AND NOT ('+storage+')),0) FROM '+_identifier(physical.table))
                    scanned,null_rows,invalid=connection.execute(query).fetchone()
                    invalid_temporal=0
                blocked_null=bool(temporal is not None and null_rows
                    and temporal.null_policy=='BLOCK')
                reasons=[]
                if invalid:reasons.append('LOGICAL_STORAGE_TYPE_VIOLATION')
                if invalid_temporal:reasons.append('TEMPORAL_ENCODING_VIOLATION')
                if blocked_null:reasons.append('TEMPORAL_NULL_POLICY_VIOLATION')
                material={'contract_version':('boi/property-storage-quality@2'
                        if temporal is not None else 'boi/property-storage-quality@1'),
                    'mapping_ref':physical.mapping_ref,'logical_property_ref':prop.logical_property_ref,
                    'value_type_ref':prop.value_type_ref,'value_type_revision_digest':prop.value_type_revision_digest,
                    'logical_primitive_type':prop.logical_primitive_type,'mapping_input_digest':input_digest,
                    'source_snapshot_digest':grant.source_snapshot_digest,'physical_schema_digest':schema.schema_digest,
                    'grant_digest':grant_digest,'principal':principal,'purpose':purpose,'manifest_digest':manifest_digest,
                    'scanned_rows':scanned,'null_rows':null_rows,'invalid_storage_type_rows':invalid,
                    'status':'fail' if reasons else 'pass','reason_codes':reasons,
                    'protected_query_digest':_digest(query)}
                if temporal is not None:
                    material.update(temporal_encoding=temporal.model_dump(mode='json'),
                        invalid_temporal_encoding_rows=invalid_temporal)
                storage_receipts.append({**material,'evidence_digest':_digest(material)})
            if inputs.relationships:
                from .metadata_relation_quality import measure_declared_relation
                for relationship in inputs.relationships:
                    observed,reasons=measure_declared_relation(connection,
                        relationship=relationship,inputs=inputs,grant_digest=grant_digest,
                        principal=principal,purpose=purpose,manifest_digest=manifest_digest,
                        storage_by_mapping={item['mapping_ref']:item for item in storage_receipts})
                    relation_receipts.extend(observed)
                    relation_reasons.extend(reasons)
        except sqlite3.Error:
            raise ValueError('METADATA_QUALITY_SCAN_REJECTED_OR_TIMEOUT') from None
        finally:
            connection.close()
        if self._monotonic()>=deadline:
            raise ValueError('METADATA_QUALITY_SCAN_REJECTED_OR_TIMEOUT')
        snapshot()
        if authorize()!=grant:
            raise ValueError('METADATA_QUALITY_GRANT_CHANGED')
        key_pass=all(item['status']=='pass' for item in (*receipts,*storage_receipts))
        relation_failed=any(item['status']=='fail' for item in relation_receipts)
        relation_measured=(len(relation_receipts)==sum(
            2 if item.direction=='bidirectional' else 1 for item in inputs.relationships))
        relation_status=('not_requested' if not inputs.relationships else
            'fail' if relation_failed else
            'measured_candidate_only' if relation_measured else 'partial')
        body={'contract_version':'boi/metadata-quality-audit@1','mapping_input_digest':input_digest,
            'grant_digest':grant_digest,'principal':principal,'purpose':purpose,'manifest_digest':manifest_digest,
            'object_key_receipts':receipts,'relationship_quality_status':'not_run' if inputs.relationships else 'not_requested',
            'status':('partial' if inputs.relationships else 'pass') if key_pass else 'fail',
            'reason_codes':['RELATIONSHIP_QUALITY_MEASUREMENT_REQUIRED'] if inputs.relationships else [],
            'query_execution_status':'not_run','production_changed':False,'active_transition':False,
            'evaluator_code_digest':_digest({name:'sha256:'+hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                for name in ('query_gateway.py','metadata_mapping_profile.py','multi_result_query_gateway.py',
                    'sqlite_source_snapshot.py','physical_temporal_encoding.py','latest_time_order.py')})}
        if storage_receipts:
            body.update(contract_version=('boi/metadata-quality-audit@3'
                    if any('temporal_encoding' in item for item in storage_receipts)
                    else 'boi/metadata-quality-audit@2'),
                value_type_quality_receipts=storage_receipts)
            body['reason_codes']=list(dict.fromkeys([*body['reason_codes'],*(reason for item in storage_receipts for reason in item['reason_codes'])]))
        if inputs.relationships:
            body.update(contract_version='boi/metadata-quality-audit@4',
                relationship_quality_receipts=relation_receipts,
                relationship_quality_status=relation_status,
                status='fail' if not key_pass or relation_failed else 'partial',
                reason_codes=list(dict.fromkeys([
                    'RELATIONSHIP_SEMANTIC_AUTHORITY_REQUIRED',*relation_reasons,
                    *(reason for item in storage_receipts for reason in item['reason_codes'])])),
                evaluator_code_digest=_digest({name:'sha256:'+hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                    for name in ('query_gateway.py','metadata_mapping_profile.py','metadata_relation_quality.py',
                        'multi_result_query_gateway.py','sqlite_source_snapshot.py','physical_temporal_encoding.py',
                        'latest_time_order.py')}))
        return {**body,'receipt_digest':_digest(body)}

    def profile_identity_key(self, *, context, property_ref: str) -> dict[str, Any]:
        """Snapshot-bound key-only quality scan, never model/user SQL execution.

        SQLite TEXT PRIMARY KEY may contain NULL and a composite PK does not
        imply per-column uniqueness. Prove the actual snapshot, not that metadata
        shortcut. Only a bound property in the authorized context can be scanned.
        """
        if not self._semantic_path or not context.principal_id or not context.purpose or len(context.catalog.sources)!=1:
            raise ValueError('KEY_PROFILE_CAPABILITY_UNAVAILABLE')
        if self._schema_stale(): raise ValueError('SCHEMA_SNAPSHOT_STALE')
        mappings = [e for e in context.bundle.mapping_entries if e.payload.get('domain_ref')==property_ref
                    and e.availability=='bound' and e.physical is not None]
        if len(mappings)!=1: raise ValueError('KEY_PROFILE_MAPPING_NOT_AUTHORIZED')
        mapping=mappings[0]; physical=mapping.physical
        source=context.catalog.source(physical.source)
        table=context.catalog.table(physical.source,physical.table)
        if source is None or not source.read_only or source.backend!='sqlite' or table is None or not any(c.name==physical.column for c in table.columns):
            raise ValueError('KEY_PROFILE_MAPPING_NOT_AUTHORIZED')
        def snapshot():
            return 'sha256:'+hashlib.sha256(self._semantic_path.read_bytes()).hexdigest()
        if snapshot()!=self._semantic_source_digest: raise ValueError('SOURCE_SNAPSHOT_CHANGED')
        quoted_table='"'+physical.table.replace('"','""')+'"'
        quoted_column='"'+physical.column.replace('"','""')+'"'
        sql=f'SELECT COUNT(*), COUNT({quoted_column}), COUNT(DISTINCT {quoted_column}) FROM {quoted_table}'
        progress,interruption=self._execution_progress_handler(idempotency_key='key-profile:'+context.context_digest,
            timeout_seconds=min(30,context.policy.timeout_seconds),started_tick=self._monotonic())
        connection=sqlite3.connect(f'file:{self._semantic_path}?mode=ro',uri=True)
        try:
            connection.execute('PRAGMA query_only = ON')
            connection.set_progress_handler(progress,100)
            scanned,non_null,distinct=connection.execute(sql).fetchone()
        except sqlite3.OperationalError:
            self._raise_for_interruption(interruption)
            raise
        finally:
            connection.close()
        if progress(): self._raise_for_interruption(interruption)
        if snapshot()!=self._semantic_source_digest: raise ValueError('SOURCE_SNAPSHOT_CHANGED')
        values={'schema':'boi-identity-key-quality/v1','property_ref':property_ref,
                'mapping_revision_digest':mapping.revision_digest,'catalog_snapshot_digest':context.catalog.snapshot_digest,
                'source_snapshot_digest':self._semantic_source_digest,'schema_digest':context.catalog.schema_digest,
                'acl_projection_digest':context.bundle.acl_projection_digest,
                'scanned_rows':scanned,'null_key_rows':scanned-non_null,'duplicate_key_rows':non_null-distinct,
                'query_digest':_digest(sql),'status':'PASS' if scanned==non_null==distinct else 'FAIL'}
        return {**values,'receipt_digest':_digest(values)}

    def _schema_stale(self) -> bool:
        now = self._clock()
        current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
        return current >= self._schema_expires_at()

    def _execution_progress_handler(
        self, *, idempotency_key: str, timeout_seconds: int,
        started_tick: float,
    ) -> tuple[Callable[[], int], dict[str, bool]]:
        state = {"cancelled": False, "timed_out": False}

        def progress() -> int:
            if (
                self._cancellation_probe is not None
                and self._cancellation_probe(idempotency_key)
            ):
                state["cancelled"] = True
                return 1
            if self._monotonic() - started_tick > timeout_seconds:
                state["timed_out"] = True
                return 1
            return 0

        return progress, state

    @staticmethod
    def _raise_for_interruption(state: dict[str, bool]) -> None:
        if state["cancelled"]:
            raise ValueError("QUERY_CANCELLED")
        if state["timed_out"]:
            raise ValueError("QUERY_TIMEOUT")

    def _source_snapshot_current(self) -> bool:
        if self._historical_adapter is None:
            return False
        return self._historical_adapter.source_snapshot_current()

    def capabilities(self) -> tuple[QueryCapability, ...]:
        sqlite_verified = (
            self._historical_adapter is not None
            or self._semantic_path is not None
            or self._multi_result_gateway is not None
        )
        schema_stale = sqlite_verified and self._schema_stale()
        sqlite_lanes = (
            ("attested", "exploratory")
            if self._historical_adapter is not None
            else ("exploratory",)
            if self._semantic_path is not None or self._multi_result_gateway is not None
            else ()
        )
        return (
            QueryCapability(
                backend="sqlite-reference",
                verification_status="VERIFIED" if sqlite_verified else "UNVERIFIED",
                execution_enabled=bool(sqlite_verified and not schema_stale),
                lanes=sqlite_lanes if sqlite_verified and not schema_stale else (),
                schema_status="STALE" if schema_stale else "CURRENT" if sqlite_verified else "UNVERIFIED",
                schema_release_digest=self._schema_release_digest if sqlite_verified else "",
                schema_expires_at=self._schema_expires_at().isoformat() if sqlite_verified else "",
            ),
            QueryCapability(
                backend="oracle-internal-gateway",
                verification_status="UNVERIFIED",
                execution_enabled=False,
                lanes=(),
                schema_status="UNVERIFIED",
                schema_release_digest="",
                schema_expires_at="",
            ),
        )

    @staticmethod
    def _request_digest(
        request: QueryExecutionRequest | SemanticExploratoryExecutionRequest,
    ) -> str:
        payload = request.model_dump(mode="json", exclude={"idempotency_key"})
        return _digest(payload)

    def _create_semantic(
        self, request: SemanticExploratoryExecutionRequest, request_digest: str,
    ) -> QueryExecution:
        if (
            self._semantic_path is None
            or self._semantic_ledger is None
            or self._semantic_evidence_store is None
        ):
            raise RuntimeError("SEMANTIC_SQLITE_REFERENCE_UNAVAILABLE")
        if request.semantic_context.schema_digest != self._schema_release_digest:
            raise ValueError("SCHEMA_DRIFT")
        source_digest = "sha256:" + hashlib.sha256(
            self._semantic_path.read_bytes()
        ).hexdigest()
        if source_digest != self._semantic_source_digest:
            raise ValueError("SOURCE_SNAPSHOT_DRIFT")
        verification = SemanticPlanValidationVerifier().verify(
            request.validation_receipt,
            ledger=self._semantic_ledger,
            evidence_store=self._semantic_evidence_store,
        )
        if not verification.ok:
            raise ValueError(verification.error_codes[0])
        if request.plan_reuse_receipt is not None and self._semantic_plan_store is None:
            raise ValueError("SEMANTIC_PLAN_CACHE_STORE_REQUIRED")
        cache_hit_id = (
            self._semantic_plan_store.validate_request(
                request,
                ledger=self._semantic_ledger,
                evidence_store=self._semantic_evidence_store,
            )
            if self._semantic_plan_store is not None
            else None
        )
        catalog = request.semantic_context.catalog
        if len(catalog.sources) != 1 or catalog.sources[0].backend != "sqlite":
            raise ValueError("SEMANTIC_SQLITE_SOURCE_CONTRACT_INVALID")
        source = catalog.sources[0]
        fresh = capture_sqlite_planner_catalog(
            self._semantic_path,
            source_id=source.source_id,
            allowed_tables=tuple(table.name for table in source.tables),
            captured_at=catalog.captured_at,
        )
        if (
            fresh.schema_digest != catalog.schema_digest
            or fresh.capability_digest != catalog.capability_digest
        ):
            raise ValueError("SEMANTIC_CATALOG_SCHEMA_DRIFT")
        compiled = SemanticSqliteCompiler().compile(
            request.logical_plan,
            context=request.semantic_context,
            binding=request.binding_receipt,
        )
        if request.parameters != compiled.parameter_bindings:
            raise ValueError("SEMANTIC_PARAMETER_CONTRACT_MISMATCH")
        started_at = self._clock().isoformat()
        started_tick = self._monotonic()
        progress, interruption = self._execution_progress_handler(
            idempotency_key=request.idempotency_key,
            timeout_seconds=request.timeout_seconds,
            started_tick=started_tick,
        )
        if progress():
            self._raise_for_interruption(interruption)
        connection = sqlite3.connect(
            f"file:{self._semantic_path}?mode=ro", uri=True
        )
        connection.row_factory = sqlite3.Row
        try:
            from .relational_time import register_relational_time
            register_relational_time(connection)
            connection.set_progress_handler(progress, 100)
            try:
                connection.execute("PRAGMA query_only = ON")
                dry_run_rows = tuple(
                    tuple(row)
                    for row in connection.execute(
                        f"EXPLAIN QUERY PLAN {compiled.sql}",
                        compiled.parameter_bindings,
                    ).fetchall()
                )
                rows = _normalize_result_rows(tuple(
                    dict(row)
                    for row in connection.execute(
                        compiled.sql, compiled.parameter_bindings
                    ).fetchall()
                ))
            except sqlite3.OperationalError:
                self._raise_for_interruption(interruption)
                raise
        finally:
            connection.close()
        if progress():
            self._raise_for_interruption(interruption)
        if len(rows) > request.row_limit:
            raise ValueError("ROW_LIMIT_EXCEEDED")
        completed_at = self._clock().isoformat()
        schema = _result_schema(rows)
        result = QueryResult(
            rows=rows,
            row_count=len(rows),
            result_schema=schema,
            result_schema_digest=_digest(schema),
            result_digest=_digest(rows),
        )
        execution_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL,
            f"boi-semantic-query:{request.idempotency_key}:{request_digest}",
        ))
        receipt = ExecutionReceipt(
            computation_id=request.logical_plan_ref,
            query_revision_digest=request.logical_plan.plan_digest,
            logical_plan_digest=request.logical_plan.plan_digest,
            domain_release_digest=request.semantic_context.domain_profile_digest,
            mapping_release_digest=request.semantic_context.mapping_profile_digest,
            schema_release_digest=request.semantic_context.schema_digest,
            compiler_digest=compiled.compiler_digest,
            parameter_digest=_parameter_digest(request),
            execution_artifact_ref=(
                f"protected:sqlite-sql:{compiled.compiled_sql_digest}"
            ),
            execution_artifact_digest=compiled.compiled_sql_digest,
            backend_execution_id=execution_id,
            source_snapshot=source_digest,
            result_schema_digest=result.result_schema_digest,
            row_count=result.row_count,
            result_digest=result.result_digest,
            authorization_policy_digest=_authorization_digest(request),
            started_at=started_at,
            completed_at=completed_at,
        )
        promotion_candidate = (
            self._semantic_plan_store.observe_success(
                request,
                execution_id=execution_id,
                execution_receipt_digest=_digest(receipt.model_dump(mode="json")),
                result_digest=result.result_digest,
                ledger=self._semantic_ledger,
                evidence_store=self._semantic_evidence_store,
                occurred_at=completed_at,
            )
            if self._semantic_plan_store is not None
            else None
        )
        context = request.semantic_context
        exploration = SemanticExplorationReceipt(
            semantic_context_digest=context.context_digest,
            question_digest=context.question_digest,
            principal_id=context.principal_id,
            purpose=context.purpose,
            acl_projection_digest=context.acl_projection_digest,
            semantic_bundle_digest=context.semantic_bundle_digest,
            semantic_bundle_content_digest=context.semantic_bundle_content_digest,
            retrieval_receipt_digest=context.retrieval_receipt_digest,
            semantic_resolution_receipt_digest=(
                context.semantic_resolution_receipt_digest
            ),
            intent_synthesis_receipt_digest=(
                context.intent_synthesis_receipt_digest
            ),
            intent_model_id=context.intent_model_id,
            intent_model_digest=context.intent_model_digest,
            intent_role_digest=context.intent_role_digest,
            intent_prompt_digest=context.intent_prompt_digest,
            binding_digest=request.binding_receipt.binding_digest,
            validation_receipt_digest=request.validation_receipt.receipt_digest,
            validation_run_id=request.validation_receipt.run_id,
            validation_check_ids=request.validation_receipt.check_ids,
            intent_digest=request.logical_plan.intent_digest,
            logical_plan_digest=request.logical_plan.plan_digest,
            active_release_digest=context.active_release_digest,
            domain_profile_digest=context.domain_profile_digest,
            mapping_profile_digest=context.mapping_profile_digest,
            query_profile_digest=context.query_profile_digest,
            catalog_snapshot_digest=context.catalog_snapshot_digest,
            catalog_snapshot_content_digest=context.catalog_snapshot_content_digest,
            schema_digest=context.schema_digest,
            capability_digest=context.capability_digest,
            compiler_digest=compiled.compiler_digest,
            policy_digest=context.planning_policy_digest,
            parameter_digest=receipt.parameter_digest,
            execution_artifact_ref=receipt.execution_artifact_ref,
            execution_artifact_digest=receipt.execution_artifact_digest,
            backend_execution_id=execution_id,
            source_snapshot=source_digest,
            result_schema_digest=result.result_schema_digest,
            row_count=result.row_count,
            result_digest=result.result_digest,
            authorization_policy_digest=receipt.authorization_policy_digest,
            cold_path_trace=SemanticColdPathTrace(
                cache_hit_ids=(cache_hit_id,) if cache_hit_id else (),
                promotion_candidate_ids=(
                    (promotion_candidate.candidate_id,)
                    if promotion_candidate is not None else ()
                ),
            ),
            dry_run_digest=_digest(dry_run_rows),
            started_at=started_at,
            completed_at=completed_at,
        )
        execution = QueryExecution(
            execution_id=execution_id,
            lane="exploratory",
            status="SUCCEEDED",
            result_status="PROVISIONAL",
            result=result,
            receipt=receipt,
            attestation=None,
            exploration_receipt=exploration,
        )
        self._idempotency[request.idempotency_key] = (request_digest, execution)
        return execution

    def _create_dynamic(
        self,
        request: QueryExecutionRequest,
        request_digest: str,
    ) -> QueryExecution:
        if self._historical_adapter is None:
            raise RuntimeError("SQLITE_REFERENCE_UNAVAILABLE")
        return self._historical_adapter.create_dynamic(self, request, request_digest)

    def create(
        self, request: QueryExecutionRequest | SemanticExploratoryExecutionRequest
        | MultiResultExploratoryExecutionRequest,
    ) -> QueryExecution | MultiResultQueryExecution:
        if isinstance(request, MultiResultExploratoryExecutionRequest):
            if self._multi_result_gateway is None:
                raise RuntimeError("MULTI_RESULT_SQLITE_REFERENCE_UNAVAILABLE")
            if self._schema_stale():
                raise ValueError("SCHEMA_SNAPSHOT_STALE")
            return self._multi_result_gateway.create(request)
        if isinstance(request, SemanticExploratoryExecutionRequest):
            try:
                request = SemanticExploratoryExecutionRequest.model_validate(
                    request.model_dump(mode="python")
                )
            except ValidationError as error:
                first = error.errors()[0]
                detail = str(first.get("ctx", {}).get("error") or first["msg"])
                raise ValueError(detail) from error
            if self._schema_stale():
                raise ValueError("SCHEMA_SNAPSHOT_STALE")
            request_digest = self._request_digest(request)
            prior = self._idempotency.get(request.idempotency_key)
            if prior:
                if prior[0] != request_digest:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                return prior[1]
            return self._create_semantic(request, request_digest)
        if self._historical_adapter is None:
            raise RuntimeError("SQLITE_REFERENCE_UNAVAILABLE")
        if self._schema_stale():
            raise ValueError("SCHEMA_SNAPSHOT_STALE")
        if request.schema_release_digest != self._schema_release_digest:
            raise ValueError("SCHEMA_DRIFT")
        if not self._source_snapshot_current():
            raise ValueError("SOURCE_SNAPSHOT_DRIFT")
        request_digest = self._request_digest(request)
        prior = self._idempotency.get(request.idempotency_key)
        if prior:
            if prior[0] != request_digest:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            return prior[1]

        if request.logical_plan is not None:
            return self._create_dynamic(request, request_digest)

        return self._historical_adapter.create_registered(
            self, request, request_digest
        )

    def get(self, execution_id: str) -> QueryExecution | MultiResultQueryExecution | None:
        for _, execution in self._idempotency.values():
            if execution.execution_id == execution_id:
                return execution
        return (
            self._multi_result_gateway.get(execution_id)
            if self._multi_result_gateway is not None else None
        )

    def read_multi_result_artifact(
        self, artifact_ref: str, *, principal: str, purpose: str
    ) -> dict[str, Any]:
        if self._multi_result_gateway is None:
            raise RuntimeError("MULTI_RESULT_SQLITE_REFERENCE_UNAVAILABLE")
        return self._multi_result_gateway.read_result_artifact(
            artifact_ref, principal=principal, purpose=purpose
        )

    def get_authorized_multi_result(self, execution_id: str, *, principal: str, purpose: str):
        execution = self._multi_result_gateway.get(execution_id) if self._multi_result_gateway else None
        if execution is None:
            raise ValueError('QUERY_EXECUTION_NOT_FOUND')
        expected = MultiResultSqliteGateway._authorization_digest(principal=principal, purpose=purpose)
        if execution.receipt.authorization_policy_digest != expected:
            raise ValueError('EXECUTION_ACCESS_DENIED')
        artifact = self.read_multi_result_artifact(execution.receipt.result_artifact_ref,
                                                  principal=principal, purpose=purpose)
        if (artifact['result_digest'] != execution.receipt.result_digest
            or artifact['run_id'] != execution.execution_id):
            raise ValueError('EXECUTION_RESULT_CHAIN_MISMATCH')
        return execution

    def read_snapshot_result_page(self, paging_ref: str, *, principal: str,
                                  purpose: str, cursor: str | None = None) -> dict[str, Any]:
        if self._multi_result_gateway is None or self._multi_result_gateway.snapshot_pager is None:
            raise ValueError("SNAPSHOT_PAGING_CAPABILITY_UNAVAILABLE")
        if self._schema_stale():
            raise ValueError("SCHEMA_SNAPSHOT_STALE")
        return self._multi_result_gateway.snapshot_pager.read_page(
            paging_ref, principal=principal, purpose=purpose, cursor=cursor)

    def supports_snapshot_result_paging(self, policy_digest: str) -> bool:
        """Report only an explicitly assembled and approved pager policy."""
        pager = (
            self._multi_result_gateway.snapshot_pager
            if self._multi_result_gateway is not None else None
        )
        return bool(
            pager is not None and policy_digest in pager.approved_policy_digests
        )
