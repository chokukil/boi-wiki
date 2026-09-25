"""Bounded execution DAG for the eight existing ontology migration Skills."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Callable, Iterable, Mapping

from .ontology_migration_batch import (
    ConceptCandidate,
    ConceptDefinition,
    MigrationBatchPlanner,
)
from .ontology_migration_harness import MigrationHarness, MigrationRecord
from .ontology_migration_pi_worker import _normalize_output
from .ontology_migration_skills import ontology_migration_skill_registry
from .sql_lineage import analyze_sql_lineage
from .corporate_metadata_intake import build_corporate_metadata_intake


SourceResolver = Callable[[str], bytes]
PiStageRunner = Callable[[str, dict[str, object]], dict[str, object]]
PiInvocationRecorder = Callable[[dict[str, object]], None]


_DAG_ORDER = (
    "legacy-source-intake",
    "sql-lineage-extract",
    "physical-mapping-verify",
    "domain-ontology-draft",
    "existing-concept-match",
    "query-contract-author",
    "migration-batch-review",
    "harness-evolution",
)

_MODEL_STAGES = frozenset({"domain-ontology-draft", "existing-concept-match"})

# Exact deterministic reason codes only; arbitrary exception text may contain
# source material and must not be forwarded from a model-enabled stage.
_SEMANTIC_REASON_CODES = frozenset({
    'SEMANTIC_FIELD_INDEX_INVALID', 'SEMANTIC_EXTRACTION_RESOLUTION_STALE',
    'ACTIVE_DEFINITION_SNAPSHOT_DRIFT', 'SOURCE_DEFINITION_NAMESPACE_MISMATCH',
    'SEMANTIC_INPUT_SCOPE_SHARD_REQUIRED', 'SEMANTIC_FIELD_EVIDENCE_OUTSIDE_SOURCE',
    'SEMANTIC_CLAIM_NAMESPACE_MISMATCH', 'SEMANTIC_MATCH_PROPOSAL_OUTSIDE_READ_DEFINITIONS',
    'DEFINITION_READ_ACCESS_OR_POLICY_DENIED', 'DEFINITION_READ_LOOKUP_SCOPE_INCOMPLETE',
    'DEFINITION_READ_REVISION_CLOSURE_MISMATCH', 'DEFINITION_READ_IDENTITY_AMBIGUOUS',
    'DEFINITION_READ_DOMAIN_ONLY', 'DEFINITION_READ_IDENTITY_MISMATCH',
    'DEFINITION_READ_PROFILE_MIGRATION_REQUIRED', 'DEFINITION_READ_BOUNDED_SCOPE_REQUIRED',
    'SEMANTIC_IMMUTABLE_RECORD_DRIFT', 'SEMANTIC_EXTRACTION_RESOLUTION_CONTRACT_REQUIRED',
    'DERIVED_CANDIDATE_SHARD_LIMIT_EXCEEDED', 'SEMANTIC_RUN_CONTEXT_MISMATCH',
    'METADATA_PIPELINE_STAGE_UNSUPPORTED', 'SEMANTIC_METADATA_SERVICES_REQUIRED',
    'SEMANTIC_CANONICAL_EVIDENCE_RESOLVER_REQUIRED', 'SOURCE_MODEL_INPUT_NOT_AUTHORIZED',
    'METADATA_RECORD_FIELD_CLOSURE_MISMATCH', 'METADATA_RECORD_SEMANTIC_INPUT_DRIFT',
    'METADATA_CANONICAL_RECORD_REQUIRED', 'METADATA_CANONICAL_EVIDENCE_REQUIRED',
    'METADATA_EVIDENCE_ACCESS_DENIED',
    'SEMANTIC_ACTIVE_AUTHORITY_CLOSURE_STALE', 'SEMANTIC_AUTHORITY_ACCESS_DENIED',
    'SEMANTIC_APPROVED_EXTRACTION_POLICY_STALE', 'SEMANTIC_APPROVED_EXTRACTION_EVIDENCE_STALE',
    'SEMANTIC_AUTHORITY_PROFILE_NOT_QUALIFIED', 'SEMANTIC_DEFINITION_SOURCE_CLOSURE_MISMATCH',
    'SEMANTIC_EVIDENCE_REVIEW_UNAVAILABLE', 'SEMANTIC_DEFINITION_EVIDENCE_DRIFT',
    'SEMANTIC_APPROVED_REUSE_AMBIGUOUS', 'SEMANTIC_APPROVED_EXTRACTION_NOT_VALIDATED',
    'SEMANTIC_ACTIVE_USER_AUTHORITY_REQUIRED',
    'SEMANTIC_DEFINITION_JUSTIFICATION_REQUIRED',
    'SEMANTIC_DRAFT_CONTRACT_UNSUPPORTED', 'LOGICAL_SUPPORT_WITHOUT_DEFINITION',
    'LOGICAL_NEW_AND_REUSE_PROPOSALS_MUST_BE_SEPARATE', 'LOGICAL_CANDIDATE_SEMANTICS_MISMATCH',
    'LOGICAL_FIELD_EVIDENCE_CLOSURE_REQUIRED', 'LOGICAL_FIELD_EVIDENCE_INDEX_INVALID',
    'LOGICAL_FIELD_EVIDENCE_OUTSIDE_SOURCE',
    'SEMANTIC_MODEL_WIRE_BINDING_MISMATCH', 'SEMANTIC_MODEL_WIRE_CONTRACT_REQUIRED',
    'SEMANTIC_MODEL_WIRE_BYTE_LIMIT',
    'SEMANTIC_MODEL_WIRE_BINDING_REQUIRED', 'LOGICAL_DOMAIN_JSON_SCHEMA_INVALID',
    'SEMANTIC_SCOPE_REFERENCE_NOT_READ', 'SEMANTIC_QUANTITY_REFERENCE_NOT_READ',
    'SEMANTIC_UNIT_REVISION_NOT_READ',
})


@dataclass(frozen=True)
class PipelineContract:
    contract_id: str
    required_stage_ids: tuple[str, ...]
    optional_stage_ids: tuple[str, ...]
    dependencies: dict[str, tuple[str, ...]]


P0_B3_PIPELINE_V2 = PipelineContract(
    contract_id="boi/p0-b3-pipeline@0.2.0",
    required_stage_ids=_DAG_ORDER,
    optional_stage_ids=(),
    dependencies={
        stage: _DAG_ORDER[:index] for index, stage in enumerate(_DAG_ORDER)
    },
)

_METADATA_STAGES = ('legacy-source-intake', 'domain-ontology-draft', 'existing-concept-match',
    'physical-mapping-verify', 'query-contract-author', 'migration-batch-review', 'harness-evolution')
SEMANTIC_METADATA_PIPELINE_V1 = PipelineContract(
    contract_id='boi/semantic-metadata-pipeline@1.0.0', required_stage_ids=_METADATA_STAGES,
    optional_stage_ids=(), dependencies={stage:_METADATA_STAGES[:index]
        for index,stage in enumerate(_METADATA_STAGES)})

# Explicit historical transport/checkpoint scope, never semantic qualification.
INTAKE_CHECKPOINT_PIPELINE_V1 = PipelineContract(
    contract_id='boi/p0-scale-intake@1.0.0', required_stage_ids=('legacy-source-intake',),
    optional_stage_ids=(), dependencies={'legacy-source-intake':()})

_NORTH_STAR_ETCH_STAGES = (
    "source-artifact",
    "evidence-span",
    "sql-lineage",
    "sparse-domain-candidate",
    "existing-concept-match",
    "physical-mapping-data-quality",
    "relationship-result-shape-contract",
    "candidate-logical-plan-freeze",
    "cold-semantic-planning",
    "gateway-execution",
    "independent-dexa-evaluation",
)

NORTH_STAR_ETCH_PIPELINE_V1 = PipelineContract(
    contract_id="boi/north-star-etch-pipeline@1.0.0",
    required_stage_ids=_NORTH_STAR_ETCH_STAGES,
    optional_stage_ids=(),
    dependencies={
        stage: _NORTH_STAR_ETCH_STAGES[:index]
        for index, stage in enumerate(_NORTH_STAR_ETCH_STAGES)
    },
)

_PREFREEZE_ORACLE_ROLES = frozenset(
    {
        "dexa_profile",
        "query_spec",
        "golden_sql",
        "golden_count",
        "golden_result",
        "golden_rows",
    }
)


@dataclass(frozen=True)
class CandidateFreezeReceipt:
    contract_version: str
    pipeline_contract_id: str
    candidate_digest: str
    logical_plan_digest: str
    allowed_input_refs: tuple[str, ...]
    denied_oracle_refs: tuple[str, ...]
    closure_digests: dict[str, str]
    generator_code_digest: str
    status: str
    prefreeze_oracle_access_count: int
    receipt_digest: str

    @classmethod
    def create(
        cls,
        *,
        candidate_digest: str,
        logical_plan_digest: str,
        allowed_input_refs: Iterable[str],
        denied_oracle_refs: Iterable[str],
        closure_digests: Mapping[str, str],
        generator_code_digest: str,
    ) -> "CandidateFreezeReceipt":
        allowed = tuple(sorted(dict.fromkeys(str(item) for item in allowed_input_refs)))
        denied = tuple(sorted(dict.fromkeys(str(item) for item in denied_oracle_refs)))
        overlap = sorted(set(allowed).intersection(denied))
        if overlap:
            raise ValueError("FREEZE_ALLOWLIST_ORACLE_OVERLAP:" + ",".join(overlap))
        normalized_closure = {
            str(key): str(value) for key, value in sorted(closure_digests.items())
        }
        payload = {
            "contract_version": "boi/candidate-freeze-receipt@1.0.0",
            "pipeline_contract_id": NORTH_STAR_ETCH_PIPELINE_V1.contract_id,
            "candidate_digest": candidate_digest,
            "logical_plan_digest": logical_plan_digest,
            "allowed_input_refs": list(allowed),
            "denied_oracle_refs": list(denied),
            "closure_digests": normalized_closure,
            "generator_code_digest": generator_code_digest,
            "status": "frozen",
            "prefreeze_oracle_access_count": 0,
        }
        for field, value in {
            "candidate_digest": candidate_digest,
            "logical_plan_digest": logical_plan_digest,
            "generator_code_digest": generator_code_digest,
            **{f"closure_digests.{key}": value for key, value in normalized_closure.items()},
        }.items():
            if not str(value).startswith("sha256:"):
                raise ValueError(f"FREEZE_DIGEST_REQUIRED:{field}")
        return cls(
            contract_version=str(payload["contract_version"]),
            pipeline_contract_id=str(payload["pipeline_contract_id"]),
            candidate_digest=candidate_digest,
            logical_plan_digest=logical_plan_digest,
            allowed_input_refs=allowed,
            denied_oracle_refs=denied,
            closure_digests=normalized_closure,
            generator_code_digest=generator_code_digest,
            status="frozen",
            prefreeze_oracle_access_count=0,
            receipt_digest=_digest(payload),
        )


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


def _byte_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _safe_value(value: object, *, path: str = "output") -> None:
    forbidden = {
        "raw_sql",
        "sql",
        "model_generated_sql",
        "repaired_sql",
        "compiled_sql",
        "executed_sql",
        "raw_rows",
        "rows",
        "golden",
        "golden_result",
        "golden_count",
        "historical_oracle",
        "credential",
        "password",
        "secret",
        "token",
        "verdict",
        "approved",
        "released",
        "active_release",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).casefold()
            if normalized in forbidden:
                raise ValueError(f"FORBIDDEN_STAGE_VALUE:{path}.{key}")
            _safe_value(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _safe_value(child, path=f"{path}[{index}]")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise ValueError(f"UNSUPPORTED_STAGE_VALUE:{path}")


def _catalog_boundary_view(catalog: Mapping[str, object]) -> dict[str, object]:
    """Check payload keys without treating catalog identifiers as instructions.

    Only the catalog's declared table/column/key maps receive this structural
    view. Nothing is removed from the source, execution input or its digest.
    Table and column metadata still pass the ordinary forbidden-payload guard;
    worker/model outputs never receive this exception.
    """
    result = dict(catalog)
    tables = result.get("tables")
    if isinstance(tables, Mapping):
        entries = []
        for table, definition in tables.items():
            if isinstance(definition, Mapping) and isinstance(definition.get("columns"), Mapping):
                definition = {**definition, "columns": [
                    {"column_name": name, "metadata": metadata}
                    for name, metadata in definition["columns"].items()
                ]}
            entries.append({"table_name": table, "metadata": definition})
        result["tables"] = entries
    keys = result.get("keys")
    if isinstance(keys, Mapping):
        result["keys"] = [{"table_name": name, "metadata": metadata}
                          for name, metadata in keys.items()]
    return result


@dataclass(frozen=True)
class BulkMigrationExecutionContext:
    migration_id: str
    manifest_digest: str
    source_artifacts: tuple[dict[str, object], ...]
    catalog_snapshot: dict[str, object]
    evidence_spans: tuple[dict[str, object], ...]
    active_concept_index: tuple[dict[str, object], ...]
    mapping_candidates: tuple[dict[str, object], ...]
    failure_clusters: tuple[dict[str, object], ...]
    before_hashes: dict[str, str]
    model_role_prompt_digests: tuple[str, ...] = ()


@dataclass(frozen=True)
class MigrationStageResult:
    skill_id: str
    status: str
    input_digest: str
    output_digest: str
    evidence_digest: str
    output: dict[str, object] | None
    reason_codes: tuple[str, ...] = ()
    model_invocation_count: int = 0
    model_input_bytes: int = 0
    model_invocation_record_digest: str = ""
    unresolved_reason: str = ""


@dataclass(frozen=True)
class SubmittedMigrationStageResult(MigrationStageResult):
    # Only submitted executions use the new receipt shape; old result bytes
    # (including dataclass/asdict consumers) remain unchanged.
    worker_verification: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BulkMigrationPipelineResult:
    stage_results: tuple[MigrationStageResult, ...]
    harness_state: str
    harness_event_digests: tuple[str, ...]
    pipeline_digest: str
    pi_invocation_count: int
    pi_input_bytes: int
    pipeline_contract_id: str
    required_stage_ids: tuple[str, ...]
    optional_stage_ids: tuple[str, ...]
    missing_required_stage_ids: tuple[str, ...]
    qualification_status: str
    codex_invocation_count: int = 0
    static_fallback_count: int = 0
    forbidden_authority_invocations: int = 0
    production_changed: bool = False
    active_transition: bool = False


class BulkMigrationSkillExecutor:
    """Execute bounded transformations; authority-bearing operations are absent."""

    def __init__(
        self,
        *,
        source_resolver: SourceResolver,
        pi_runner: PiStageRunner,
        pi_invocation_recorder: PiInvocationRecorder | None = None,
        pipeline_contract: PipelineContract = P0_B3_PIPELINE_V2,
        semantic_services: Any | None = None,
        worker_execution: Any | None = None,
    ) -> None:
        self.source_resolver = source_resolver
        self.pi_runner = pi_runner
        self.pi_invocation_recorder = pi_invocation_recorder or (lambda _record: None)
        self.pipeline_contract = pipeline_contract
        self.semantic_services = semantic_services
        self.worker_execution = worker_execution
        self.skills = ontology_migration_skill_registry()

    @staticmethod
    def _assert_prefreeze_resource_boundary(
        context: BulkMigrationExecutionContext,
    ) -> None:
        denied_roles = sorted(
            {
                str(item.get("role") or "").casefold()
                for item in context.source_artifacts
            }.intersection(_PREFREEZE_ORACLE_ROLES)
        )
        if denied_roles:
            raise ValueError(
                "PREFREEZE_ORACLE_ACCESS_DENIED:" + ",".join(denied_roles)
            )
        try:
            _safe_value(
                {
                    "catalog_snapshot": _catalog_boundary_view(context.catalog_snapshot),
                    "evidence_spans": context.evidence_spans,
                    "active_concept_index": context.active_concept_index,
                    "mapping_candidates": context.mapping_candidates,
                },
                path="prefreeze_accessible_resources",
            )
        except ValueError as exc:
            raise ValueError(f"PREFREEZE_ORACLE_ACCESS_DENIED:{exc}") from exc

    def _intake(self, context: BulkMigrationExecutionContext) -> dict[str, object]:
        artifacts: list[dict[str, object]] = []
        resolved: dict[str, bytes] = {}
        for source in context.source_artifacts:
            ref = str(source.get("artifact_ref") or "")
            expected = str(source.get("digest") or "")
            content = self.source_resolver(ref)
            actual = _byte_digest(content)
            if actual != expected:
                raise ValueError(f"SOURCE_DIGEST_MISMATCH:{ref}")
            resolved[ref] = content
            artifacts.append(
                {
                    "artifact_ref": ref,
                    "digest": actual,
                    "role": str(source.get("role") or ""),
                    "byte_count": len(content),
                }
            )
        output: dict[str, object] = {
            "SourceArtifact": artifacts,
            "SourceArtifactCandidate": artifacts,
            "source_manifest": {
                "manifest_digest": context.manifest_digest,
                "source_count": len(artifacts),
                "source_digests": [item["digest"] for item in artifacts],
            },
        }
        metadata_sources = [
            item
            for item in context.source_artifacts
            if str(item.get("role") or "") == "corporate_metadata"
        ]
        catalog_sources = [
            item
            for item in context.source_artifacts
            if str(item.get("role") or "") == "catalog_snapshot"
        ]
        # Legacy P0-B3 manifests may carry pre-derived evidence with a metadata
        # source but no registered catalog artifact.  The new deterministic
        # intake path is selected only by the exact metadata+catalog closure.
        if catalog_sources:
            if len(metadata_sources) != 1 or len(catalog_sources) != 1:
                raise ValueError("EXACT_METADATA_AND_CATALOG_SOURCE_REQUIRED")
            metadata_source = metadata_sources[0]
            catalog_source = catalog_sources[0]
            catalog_ref = str(catalog_source.get("artifact_ref") or "")
            catalog_payload = json.loads(resolved[catalog_ref].decode("utf-8"))
            if not isinstance(catalog_payload, Mapping):
                raise ValueError("CATALOG_SNAPSHOT_SCHEMA_INVALID")
            intake = build_corporate_metadata_intake(
                metadata_bytes=resolved[str(metadata_source.get("artifact_ref") or "")],
                metadata_artifact_ref=str(metadata_source.get("artifact_ref") or ""),
                metadata_digest=str(metadata_source.get("digest") or ""),
                catalog_snapshot=catalog_payload,
                catalog_snapshot_digest=str(catalog_source.get("digest") or ""),
            )
            output["EvidenceSpan"] = intake["evidence_spans"]
            output["CatalogReconciliationReceipt"] = intake[
                "catalog_reconciliation_receipt"
            ]
        return output

    def _lineage(self, context: BulkMigrationExecutionContext) -> dict[str, object]:
        sql_sources = [
            item for item in context.source_artifacts if str(item.get("role") or "") == "sql"
        ]
        if len(sql_sources) != 1:
            raise ValueError("EXACTLY_ONE_SQL_SOURCE_REQUIRED")
        sql_bytes = self.source_resolver(str(sql_sources[0]["artifact_ref"]))
        sql = sql_bytes.decode("utf-8")
        catalog_tables = context.catalog_snapshot.get("tables") or {}
        schema = {
            str(table): {
                str(column): str(kind)
                for column, kind in dict(
                    definition.get("columns", definition)
                    if isinstance(definition, Mapping)
                    else {}
                ).items()
            }
            for table, definition in dict(catalog_tables).items()
        }
        report = analyze_sql_lineage(
            sql,
            dialect=str(context.catalog_snapshot.get("dialect") or "sqlite"),
            schema=schema,
        )
        columns = [
            {
                "output_column": item.output_column,
                "classification": item.classification,
                "source_columns": [
                    {
                        "catalog": source.catalog,
                        "database": source.database,
                        "table": source.table,
                        "column": source.column,
                    }
                    for source in item.sources
                ],
            }
            for item in report.columns
        ]
        return {
            "lineage_report": {
                "input_digest": report.input_digest,
                "ast_digest": report.ast_digest,
                "dialect": report.dialect,
                "columns": columns,
                "read_only": report.read_only,
            },
            "unresolved_items": [
                item["output_column"]
                for item in columns
                if item["classification"] == "unresolved"
            ],
        }

    def _physical_mapping(self, context: BulkMigrationExecutionContext) -> dict[str, object]:
        tables = {
            str(table): set(
                str(column)
                for column in dict(
                    definition.get("columns", definition)
                    if isinstance(definition, Mapping)
                    else {}
                )
            )
            for table, definition in dict(
                context.catalog_snapshot.get("tables") or {}
            ).items()
        }
        keys = {
            str(table): set(str(column) for column in columns)
            for table, columns in (
                dict(context.catalog_snapshot.get("keys") or {}).items()
                if context.catalog_snapshot.get("keys")
                else (
                    (
                        str(table),
                        definition.get("primary_key", ())
                        if isinstance(definition, Mapping)
                        else (),
                    )
                    for table, definition in dict(
                        context.catalog_snapshot.get("tables") or {}
                    ).items()
                )
            )
        }
        checks: list[dict[str, object]] = []
        for mapping in context.mapping_candidates:
            table = str(mapping.get("table") or "")
            column = str(mapping.get("column") or "")
            exists = table in tables and column in tables[table]
            checks.append(
                {
                    "mapping_id": str(mapping.get("mapping_id") or ""),
                    "table": table,
                    "column": column,
                    "exists": exists,
                    "is_key": column in keys.get(table, set()),
                    "check_status": "pass" if exists else "fail",
                    "evidence_digest": _digest(
                        {
                            "catalog_digest": context.catalog_snapshot.get("digest"),
                            "schema_digest": context.catalog_snapshot.get("schema_digest"),
                            "table": table,
                            "column": column,
                            "exists": exists,
                        }
                    ),
                }
            )
        if not checks or any(not item["exists"] for item in checks):
            raise ValueError("PHYSICAL_MAPPING_VALIDATION_FAILED")
        return {
            "mapping_checks": checks,
            "mapping_health": {
                "checked": len(checks),
                "passed": sum(item["check_status"] == "pass" for item in checks),
                "catalog_digest": context.catalog_snapshot.get("digest"),
                "schema_digest": context.catalog_snapshot.get("schema_digest"),
            },
        }

    @staticmethod
    def _effective_evidence_spans(
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
    ) -> tuple[dict[str, object], ...]:
        if context.evidence_spans:
            return tuple(dict(item) for item in context.evidence_spans)
        generated = prior_outputs.get("legacy-source-intake", {}).get("EvidenceSpan") or ()
        return tuple(dict(item) for item in generated if isinstance(item, Mapping))

    @staticmethod
    def _pi_payload(
        skill_id: str,
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
        *,
        evidence_spans: Iterable[Mapping[str, object]] | None = None,
    ) -> dict[str, object]:
        selected_evidence = tuple(
            dict(item)
            for item in (
                evidence_spans
                if evidence_spans is not None
                else BulkMigrationSkillExecutor._effective_evidence_spans(
                    context, prior_outputs
                )
            )
        )
        payload: dict[str, object] = {
            "evidence_spans": list(selected_evidence),
        }
        if skill_id == "domain-ontology-draft":
            payload["domain_context"] = {
                "catalog_digest": context.catalog_snapshot.get("digest"),
                "schema_digest": context.catalog_snapshot.get("schema_digest"),
            }
            if (
                not context.evidence_spans
                and prior_outputs.get("legacy-source-intake", {}).get("EvidenceSpan")
            ):
                payload["domain_context"][
                    "candidate_scope"
                ] = "sparse_object_type_per_evidence_span"
        else:
            payload["domain_candidates"] = list(
                prior_outputs.get("domain-ontology-draft", {}).get("domain_candidates") or []
            )
            payload["active_concept_index"] = [
                dict(item) for item in context.active_concept_index
            ]
        _safe_value(payload, path="pi_input")
        if len(_canonical(payload)) > 11_264:
            raise ValueError("PI_INPUT_LIMIT_EXCEEDED")
        return payload

    @staticmethod
    def _deterministic_domain_draft(
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
    ) -> dict[str, object] | None:
        spans = BulkMigrationSkillExecutor._effective_evidence_spans(
            context, prior_outputs
        )
        candidates = [
            dict(candidate)
            for span in spans
            for candidate in span.get("domain_candidates") or ()
            if isinstance(candidate, Mapping)
        ]
        if not candidates:
            return None
        cache_receipts = tuple(
            sorted(
                {
                    str(span.get("candidate_cache_receipt_digest") or "")
                    for span in spans
                    if str(span.get("candidate_cache_receipt_digest") or "")
                }
            )
        )
        return {
            "domain_candidates": candidates,
            "uncertainties": [],
            # An embedded label has not resolved a cache entry, input closure or
            # output bytes. Preserve the contribution without claiming a hit.
            "candidate_cache_receipt_digests": [],
            "unverified_candidate_cache_claims": list(cache_receipts),
        }

    @staticmethod
    def _deterministic_existing_match(
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
    ) -> dict[str, object] | None:
        candidates = list(
            prior_outputs.get("domain-ontology-draft", {}).get("domain_candidates") or []
        )
        if not candidates:
            return None
        if not context.active_concept_index:
            return {
                "match_candidates": [
                    {
                        "candidate_id": str(candidate.get("candidate_id") or ""),
                        "decision": "new",
                        "existing_concept_id": None,
                        "explanation": "active concept index closure is empty",
                        "match_basis": "deterministic_empty_index",
                        "evidence_span_refs": list(
                            candidate.get("evidence_span_refs") or ()
                        ),
                    }
                    for candidate in candidates
                ],
                "duplicate_risks": [],
            }
        matches: list[dict[str, object]] = []
        for candidate in candidates:
            exact = [
                item
                for item in context.active_concept_index
                if str(item.get("kind") or "").casefold()
                == str(candidate.get("kind") or "").casefold()
                and str(item.get("name") or "").strip().casefold()
                == str(candidate.get("name") or "").strip().casefold()
            ]
            if len(exact) != 1:
                return None
            matches.append(
                {
                    "candidate_id": str(candidate.get("candidate_id") or ""),
                    "decision": "reuse",
                    "existing_concept_id": str(exact[0].get("concept_id") or ""),
                    "explanation": "deterministic exact name and kind match",
                    "match_basis": "exact_name_kind",
                    "evidence_span_refs": list(
                        candidate.get("evidence_span_refs") or ()
                    ),
                }
            )
        return {"match_candidates": matches, "duplicate_risks": []}

    def _invoke_pi(
        self,
        *,
        skill_id: str,
        unresolved_reason: str,
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
        evidence_spans: Iterable[Mapping[str, object]] | None = None,
    ) -> tuple[dict[str, object], int, int, dict[str, object]]:
        if skill_id not in _MODEL_STAGES:
            raise ValueError("PI_STAGE_NOT_ALLOWED")
        if not context.model_role_prompt_digests:
            raise ValueError("MODEL_ROLE_PROMPT_DIGEST_REQUIRED")
        payload = self._pi_payload(
            skill_id,
            context,
            prior_outputs,
            evidence_spans=evidence_spans,
        )
        input_bytes = len(_canonical(payload))
        evidence_closure_digest = _digest(
            sorted(
                str(item.get("evidence_span_ref") or "")
                for item in payload["evidence_spans"]
            )
        )
        prompt_digest = str(context.model_role_prompt_digests[0])
        cache_key = _digest(
            {
                "skill_id": skill_id,
                "unresolved_reason": unresolved_reason,
                "evidence_span_closure_digest": evidence_closure_digest,
                "model_role_prompt_digest": prompt_digest,
                "payload_digest": _digest(payload),
            }
        )
        audit_record = {
            "skill_id": skill_id,
            "unresolved_reason": unresolved_reason,
            "evidence_span_closure_digest": evidence_closure_digest,
            "model_role_prompt_digest": prompt_digest,
            "input_bytes": input_bytes,
            "cache_key": cache_key,
            "state": "prepared",
        }
        audit_record["record_digest"] = _digest(audit_record)
        self.pi_invocation_recorder(dict(audit_record))
        output = self.pi_runner(skill_id, payload)
        normalized = _normalize_output(skill=self.skills[skill_id], output=output)
        return normalized, 1, input_bytes, audit_record

    def _invoke_domain_pi_shards(
        self,
        *,
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
    ) -> tuple[dict[str, object], int, int, dict[str, object]]:
        spans = self._effective_evidence_spans(context, prior_outputs)
        if not spans:
            raise ValueError("EVIDENCE_SPAN_REQUIRED")
        sparse_object_scope = bool(
            not context.evidence_spans
            and prior_outputs.get("legacy-source-intake", {}).get("EvidenceSpan")
        )
        candidates_by_id: dict[str, dict[str, object]] = {}
        uncertainties: list[str] = []
        audit_digests: list[str] = []
        total_calls = 0
        total_bytes = 0
        for span in spans:
            output, calls, input_bytes, audit = self._invoke_pi(
                skill_id="domain-ontology-draft",
                unresolved_reason="NO_DETERMINISTIC_DOMAIN_EXTRACTION",
                context=context,
                prior_outputs=prior_outputs,
                evidence_spans=(span,),
            )
            if sparse_object_scope and (
                len(output["domain_candidates"]) != 1
                or output["domain_candidates"][0].get("kind") != "ObjectType"
            ):
                raise ValueError("PI_SPARSE_DOMAIN_CONTRACT_INVALID")
            total_calls += calls
            total_bytes += input_bytes
            audit_digests.append(str(audit["record_digest"]))
            uncertainties.extend(str(item) for item in output["uncertainties"])
            for candidate in output["domain_candidates"]:
                candidate_id = str(candidate.get("candidate_id") or "")
                previous = candidates_by_id.get(candidate_id)
                if previous is not None and _canonical(previous) != _canonical(candidate):
                    raise ValueError(f"PI_CANDIDATE_CONFLICT:{candidate_id}")
                candidates_by_id[candidate_id] = dict(candidate)
        aggregate_audit = {
            "record_digest": _digest(audit_digests),
            "unresolved_reason": "NO_DETERMINISTIC_DOMAIN_EXTRACTION",
            "shard_count": len(spans),
        }
        return (
            {
                "domain_candidates": list(candidates_by_id.values()),
                "uncertainties": list(dict.fromkeys(uncertainties)),
            },
            total_calls,
            total_bytes,
            aggregate_audit,
        )

    def _query_contract(
        self,
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
    ) -> dict[str, object]:
        domain_candidates = list(
            prior_outputs.get("domain-ontology-draft", {}).get("domain_candidates") or []
        )
        domain_refs = [str(item.get("candidate_id") or "") for item in domain_candidates]
        mapping_refs = [
            str(item.get("mapping_id") or "") for item in context.mapping_candidates
        ]
        candidate = {
            "query_spec_id": "query-candidate:" + context.manifest_digest.split(":")[-1][:16],
            "domain_refs": domain_refs,
            "mapping_refs": mapping_refs,
            "typed_parameters": [],
            "invariants": ["read_only", "candidate_only", "no_sql_compile"],
            "logical_plan": {
                "root_candidates": domain_refs,
                "mapping_candidates": mapping_refs,
            },
        }
        return {
            "LogicalQuerySpecCandidate": [candidate],
            "golden_questions": [],
            "invariants": list(candidate["invariants"]),
        }

    def _batch_review(
        self,
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
    ) -> dict[str, object]:
        existing = tuple(
            ConceptDefinition(
                concept_id=str(item.get("concept_id") or ""),
                kind=str(item.get("kind") or "Term"),
                canonical_name=str(item.get("name") or ""),
                revision_digest=str(item.get("revision_digest") or ""),
            )
            for item in context.active_concept_index
        )
        domain = list(
            prior_outputs.get("domain-ontology-draft", {}).get("domain_candidates") or []
        )
        candidates = {
            str(item["candidate_id"]): ConceptCandidate(
                candidate_id=str(item["candidate_id"]),
                kind=str(item["kind"]),
                proposed_name=str(item["name"]),
                aliases=tuple(str(value) for value in item.get("aliases") or ()),
                properties=tuple(
                    str(value) for value in item.get("properties") or ()
                ),
                evidence_digests=tuple(
                    _digest(ref) for ref in item.get("evidence_span_refs") or []
                ),
                requested_action=(
                    str(item.get("requested_action"))
                    if item.get("requested_action") is not None
                    else None
                ),
                force_new_reason=(
                    str(item.get("force_new_reason"))
                    if item.get("force_new_reason") is not None
                    else None
                ),
            )
            for item in domain
        }
        if not candidates:
            candidates = {
                "candidate:evidence-only": ConceptCandidate(
                    "candidate:evidence-only", "Term", "Evidence only"
                )
            }
        plan = MigrationBatchPlanner(existing).plan_batch(
            selected_ids=tuple(candidates),
            candidates=candidates,
            dependencies={},
            before_hashes=context.before_hashes,
        )
        return {
            "review_plan": {
                "candidate_ids": list(plan.candidate_ids),
                "dependency_closure": {
                    key: list(value) for key, value in plan.dependency_closure.items()
                },
                "before_hashes": dict(plan.before_hashes),
            },
            "preview_hash": plan.preview_hash,
            "attention_items": [
                item.candidate_id for item in plan.decisions if item.attention_required
            ],
        }

    @staticmethod
    def _harness_evolution(context: BulkMigrationExecutionContext) -> dict[str, object]:
        evaluations = [
            {
                "reason_code": str(item.get("reason_code") or ""),
                "count": int(item.get("count") or 0),
                "candidate_digest": _digest(item),
                "authority": "candidate",
            }
            for item in context.failure_clusters
        ]
        return {
            "rule_candidates": [],
            "skill_candidates": [],
            "evaluation_candidates": evaluations,
        }

    def _execute_stage(
        self,
        skill_id: str,
        *,
        context: BulkMigrationExecutionContext,
        prior_outputs: Mapping[str, dict[str, object]],
        frozen_only: bool = False,
    ) -> tuple[dict[str, object], int, int, dict[str, object] | None]:
        if self.pipeline_contract.contract_id == SEMANTIC_METADATA_PIPELINE_V1.contract_id:
            if self.semantic_services is None:
                raise ValueError('SEMANTIC_METADATA_SERVICES_REQUIRED')
            return self.semantic_services.execute_stage(skill_id, context=context, prior_outputs=prior_outputs,
                frozen_only=frozen_only)
        if skill_id == "legacy-source-intake":
            return self._intake(context), 0, 0, None
        if skill_id == "sql-lineage-extract":
            return self._lineage(context), 0, 0, None
        if skill_id == "physical-mapping-verify":
            return self._physical_mapping(context), 0, 0, None
        if skill_id == "domain-ontology-draft":
            deterministic = self._deterministic_domain_draft(context, prior_outputs)
            if deterministic is not None:
                return deterministic, 0, 0, None
            if frozen_only:raise ValueError('WORKER_FROZEN_INFERENCE_REQUIRED')
            return self._invoke_domain_pi_shards(
                context=context,
                prior_outputs=prior_outputs,
            )
        if skill_id == "existing-concept-match":
            deterministic = self._deterministic_existing_match(context, prior_outputs)
            if deterministic is not None:
                return deterministic, 0, 0, None
            if frozen_only:raise ValueError('WORKER_FROZEN_INFERENCE_REQUIRED')
            return self._invoke_pi(
                skill_id=skill_id,
                unresolved_reason="NO_EXACT_EXISTING_CONCEPT_MATCH",
                context=context,
                prior_outputs=prior_outputs,
            )
        if skill_id == "query-contract-author":
            return self._query_contract(context, prior_outputs), 0, 0, None
        if skill_id == "migration-batch-review":
            return self._batch_review(context, prior_outputs), 0, 0, None
        if skill_id == "harness-evolution":
            return self._harness_evolution(context), 0, 0, None
        raise ValueError(f"UNKNOWN_SKILL_STAGE:{skill_id}")

    def execute_pipeline(
        self,
        *,
        requested_stages: Iterable[str],
        context: BulkMigrationExecutionContext,
    ) -> BulkMigrationPipelineResult:
        self._assert_prefreeze_resource_boundary(context)
        metadata_only = self.pipeline_contract.contract_id == SEMANTIC_METADATA_PIPELINE_V1.contract_id
        requested = tuple(dict.fromkeys(str(item) for item in requested_stages))
        unknown = sorted(set(requested).difference(self.skills))
        if unknown:
            raise ValueError("UNKNOWN_SKILL_STAGE:" + ",".join(unknown))
        if metadata_only and set(requested)-set(self.pipeline_contract.required_stage_ids):
            raise ValueError('METADATA_PIPELINE_STAGE_UNSUPPORTED')
        ordered = tuple(
            item for item in self.pipeline_contract.required_stage_ids if item in requested
        ) + tuple(
            item for item in self.pipeline_contract.optional_stage_ids if item in requested
        )
        missing_required = tuple(
            item for item in self.pipeline_contract.required_stage_ids if item not in requested
        )
        record = MigrationRecord.create(
            migration_id=context.migration_id,
            source_manifest_digest=context.manifest_digest,
            candidate_digest=_digest(
                {
                    "manifest_digest": context.manifest_digest,
                    "requested_stages": list(ordered),
                }
            ),
        )
        harness = MigrationHarness(record, pipeline_contract_id=self.pipeline_contract.contract_id if metadata_only else '')
        results: list[MigrationStageResult] = []
        outputs: dict[str, dict[str, object]] = {}
        pi_count = 0
        pi_bytes = 0

        for skill_id in ordered:
            submitted=self.worker_execution.before_stage(skill_id) if self.worker_execution else False
            input_payload = {
                "manifest_digest": context.manifest_digest,
                "skill_id": skill_id,
                "prior_output_digests": {
                    key: _digest(value) for key, value in sorted(outputs.items())
                },
            }
            if metadata_only and any(stage not in outputs for stage in self.pipeline_contract.dependencies[skill_id]):
                results.append(MigrationStageResult(skill_id=skill_id,status='not_run',
                    input_digest=_digest(input_payload),output_digest='',evidence_digest='',output=None,
                    reason_codes=('REQUIRED_STAGE_DEPENDENCY_MISSING',)))
                continue
            try:
                output, model_calls, model_bytes, model_record = self._execute_stage(
                    skill_id,
                    context=context,
                    prior_outputs=outputs,
                    frozen_only=submitted,
                )
                _safe_value(output)
            except Exception as error:
                exact_reason = str(error).split(":", 1)[0]
                reason = (
                    exact_reason
                    if metadata_only and exact_reason in _SEMANTIC_REASON_CODES
                    else exact_reason
                    if skill_id in _MODEL_STAGES and exact_reason.startswith("PI_")
                    else "LOCAL_MODEL_EXECUTION_FAILED"
                    if skill_id in _MODEL_STAGES
                    else exact_reason or "STAGE_EXECUTION_FAILED"
                )
                if harness.record.current_state != "blocked":
                    harness.transition("blocked", actor_role="deterministic_executor")
                results.append(
                    MigrationStageResult(
                        skill_id=skill_id,
                        status="blocked",
                        input_digest=_digest(input_payload),
                        output_digest="",
                        evidence_digest=_digest(
                            {"skill_id": skill_id, "reason_code": reason}
                        ),
                        output=None,
                        reason_codes=(reason,),
                    )
                )
                break

            outputs[skill_id] = output
            pi_count += model_calls
            pi_bytes += model_bytes
            output_digest = _digest(output)
            declared_status = str(output.get('stage_status') or 'pass') if metadata_only else 'pass'
            if declared_status not in {'pass','partial','flag','skip','not_run','blocked','fail'}:
                raise ValueError('METADATA_STAGE_STATUS_INVALID')
            stage_reason_codes: tuple[str, ...] = ()
            if skill_id == "legacy-source-intake":
                reconciliation = output.get("CatalogReconciliationReceipt")
                if (
                    isinstance(reconciliation, Mapping)
                    and reconciliation.get("status") != "pass"
                ):
                    stage_reason_codes = tuple(
                        str(item)
                        for item in reconciliation.get("reason_codes")
                        or ("CATALOG_RECONCILIATION_FAILED",)
                    )
            results.append(
                MigrationStageResult(
                    skill_id=skill_id,
                    status="blocked" if stage_reason_codes else declared_status,
                    input_digest=_digest(input_payload),
                    output_digest=output_digest,
                    evidence_digest=_digest(
                        {"skill_id": skill_id, "output_digest": output_digest}
                    ),
                    output=output,
                    reason_codes=stage_reason_codes,
                    model_invocation_count=model_calls,
                    model_input_bytes=model_bytes,
                    model_invocation_record_digest=(
                        str(model_record.get("record_digest") or "")
                        if model_record
                        else ""
                    ),
                    unresolved_reason=(
                        str(model_record.get("unresolved_reason") or "")
                        if model_record
                        else ""
                    ),
                )
            )
            if self.worker_execution:
                results[-1]=self.worker_execution.verify_result(results[-1])
                if results[-1].status=='blocked':
                    stage_reason_codes=results[-1].reason_codes
                    outputs.pop(skill_id,None)
            if stage_reason_codes:
                if harness.record.current_state != "blocked":
                    harness.transition("blocked", actor_role="deterministic_executor")
                break
            current = harness.record.current_state
            if metadata_only:
                if skill_id == 'legacy-source-intake' and declared_status == 'pass':
                    harness.transition('inventoried',actor_role='deterministic_executor')
                    harness.transition('parsed',actor_role='deterministic_executor')
                elif skill_id == 'domain-ontology-draft' and current == 'parsed':
                    harness.transition('semantically_drafted',actor_role='deterministic_executor')
                continue
            target = {
                "legacy-source-intake": "inventoried",
                "sql-lineage-extract": "parsed",
                "physical-mapping-verify": "physically_validated",
                "domain-ontology-draft": "semantically_drafted",
            }.get(skill_id)
            if target and (
                (current == "captured" and target == "inventoried")
                or (current == "inventoried" and target == "parsed")
                or (current == "parsed" and target == "physically_validated")
                or (current == "physically_validated" and target == "semantically_drafted")
            ):
                harness.transition(target, actor_role="deterministic_executor")

        if results and (all(item.status == "pass" for item in results)
            or (metadata_only and not missing_required and not any(item.status in {'blocked','fail','not_run'} for item in results))):
            if harness.record.current_state == "semantically_drafted":
                harness.transition("deterministic_checked", actor_role="deterministic_executor")
                attention = any(
                    (item.output or {}).get("attention_items")
                    or (item.output or {}).get("duplicate_risks")
                    or (metadata_only and item.status != 'pass')
                    for item in results
                )
                harness.transition(
                    "attention_required" if attention else "approval_ready",
                    actor_role="deterministic_executor",
                )

        qualification_status = (
            "blocked"
            if (any(item.status in {'blocked','fail','not_run'} for item in results) if metadata_only
                else any(item.status != 'pass' for item in results))
            else "partial"
            if missing_required or (metadata_only and any(item.status!='pass'
                or (item.output or {}).get('attention_items') for item in results))
            else "pass"
        )
        public_harness_state = (
            "partial" if qualification_status == "partial" and not metadata_only else harness.record.current_state
        )
        pipeline_payload = {
            "pipeline_contract_id": self.pipeline_contract.contract_id,
            "required_stage_ids": list(self.pipeline_contract.required_stage_ids),
            "optional_stage_ids": list(self.pipeline_contract.optional_stage_ids),
            "missing_required_stage_ids": list(missing_required),
            "qualification_status": qualification_status,
            "manifest_digest": context.manifest_digest,
            "stages": [
                {
                    "skill_id": item.skill_id,
                    "status": item.status,
                    "input_digest": item.input_digest,
                    "output_digest": item.output_digest,
                    "evidence_digest": item.evidence_digest,
                    "reason_codes": list(item.reason_codes),
                    **({'worker_verification_digest':item.worker_verification['verification_digest']}
                       if isinstance(item,SubmittedMigrationStageResult) else {}),
                }
                for item in results
            ],
            "harness_state": public_harness_state,
            "harness_event_digests": [item.event_digest for item in harness.record.events],
            "pi_invocation_count": pi_count,
            "pi_input_bytes": pi_bytes,
            "codex_invocation_count": 0,
            "static_fallback_count": 0,
            "forbidden_authority_invocations": 0,
            "production_changed": False,
            "active_transition": False,
        }
        return BulkMigrationPipelineResult(
            stage_results=tuple(results),
            harness_state=public_harness_state,
            harness_event_digests=tuple(item.event_digest for item in harness.record.events),
            pipeline_digest=_digest(pipeline_payload),
            pi_invocation_count=pi_count,
            pi_input_bytes=pi_bytes,
            pipeline_contract_id=self.pipeline_contract.contract_id,
            required_stage_ids=self.pipeline_contract.required_stage_ids,
            optional_stage_ids=self.pipeline_contract.optional_stage_ids,
            missing_required_stage_ids=missing_required,
            qualification_status=qualification_status,
        )
