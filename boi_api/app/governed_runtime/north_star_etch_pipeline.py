"""Shared candidate-preview continuation for the CM-ETCH bulk import run.

This service is channel-neutral.  It consumes the immutable outputs of the
bounded migration skills, performs the deterministic/profile/runtime stages,
and records only protected references and semantic digests in the same ledger.
Historical DEXA oracles are injected into the final evaluator callback and are
therefore structurally unreachable before every logical plan is frozen.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .bulk_migration import BulkMigrationOrchestrator, BulkMigrationPolicyError
from .bulk_migration_execution import NORTH_STAR_ETCH_PIPELINE_V1
from .candidate_execution_attester import attest_candidate_execution
from .candidate_semantic_search import (
    build_candidate_search_receipt,
    freeze_candidate_search_closure,
)
from .cold_candidate_query_planner import (
    build_cold_candidate_logical_plan,
    freeze_cold_candidate_plan,
)
from .metadata_mapping_profile import build_metadata_mapping_profile
from .multi_result_query_gateway import (
    MultiResultExploratoryExecutionRequest,
    MultiResultSqliteGateway,
    capture_multi_result_sqlite_schema,
    validate_multi_result_plan_authority,
)
from .post_freeze_dexa_evaluator import evaluate_post_freeze_dexa


def _canonical(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class NorthStarEtchPreviewResult:
    run_id: str
    candidate_id: str
    candidate_digest: str
    receipt_digest: str
    preview_digest: str
    result_counts: tuple[dict[str, int], ...]
    execution_receipt_digests: tuple[str, ...]
    status: str = "INTEGRATION_QUALIFIED_REVIEW_READY"
    result_classification: str = "PROVISIONAL"
    production_release_qualified: bool = False
    active_release_transition: bool = False


class NorthStarEtchPreviewService:
    """Continue an existing ImportRun through the versioned North-Star DAG."""

    def __init__(
        self,
        *,
        store: Any,
        orchestrator: BulkMigrationOrchestrator,
        sqlite_path: Path,
        result_artifact_root: Path,
        source_resolver: Callable[[str], bytes],
        oracle_loader: Callable[[], Mapping[str, int]],
        source_id: str = "fixture:dexa-mes-sqlite@5d82a5f7",
    ) -> None:
        self.store = store
        self.orchestrator = orchestrator
        self.sqlite_path = sqlite_path
        self.result_artifact_root = result_artifact_root
        self.source_resolver = source_resolver
        self.oracle_loader = oracle_loader
        self.source_id = source_id

    def _owned_records(self, collection: str, run_id: str, principal: str):
        return tuple(
            item
            for item in self.store.list(collection, limit=1_000_000)
            if str(item.get("run_id") or "") == run_id
            and str(item.get("employee_id") or "") == principal
        )

    def qualify(
        self,
        *,
        principal: str,
        run_id: str,
        questions: tuple[str, str, str],
        catalog_snapshot: Mapping[str, object],
        policy_digest: str,
        active_concept_index_digest: str,
    ) -> NorthStarEtchPreviewResult:
        run = self.orchestrator.get_run(principal=principal, run_id=run_id)
        manifest_record = self.store.get("bulk_migration_manifests", run.manifest_digest)
        if not manifest_record or str(manifest_record.get("employee_id") or "") != principal:
            raise BulkMigrationPolicyError("MANIFEST_ACCESS_DENIED")
        manifest = dict(manifest_record.get("semantic_payload") or {})
        if manifest.get("pipeline_contract_id") != NORTH_STAR_ETCH_PIPELINE_V1.contract_id:
            raise BulkMigrationPolicyError("NORTH_STAR_PIPELINE_CONTRACT_REQUIRED")
        expected_questions = tuple(
            sorted(str(item) for item in manifest.get("candidate_preview_question_digests") or ())
        )
        actual_questions = tuple(sorted(_digest(question) for question in questions))
        if expected_questions != actual_questions:
            raise BulkMigrationPolicyError("CANDIDATE_PREVIEW_QUESTION_CLOSURE_MISMATCH")
        existing_preview = self.store.get(
            "bulk_migration_candidate_previews", f"preview:{run_id}"
        )
        if existing_preview is not None:
            if str(existing_preview.get("employee_id") or "") != principal:
                raise BulkMigrationPolicyError("CANDIDATE_PREVIEW_ACCESS_DENIED")
            candidate_id = run.candidate_refs[0]
            candidate = self.store.get("bulk_migration_candidates", candidate_id) or {}
            receipts = self._owned_records(
                "bulk_migration_receipts", run_id, principal
            )
            from .bulk_migration_qualification import select_current_receipt
            receipt = select_current_receipt(run, manifest, self.orchestrator.repository, receipts)
            if receipt.get('status') != 'pass':
                raise BulkMigrationPolicyError("NORTH_STAR_RECEIPT_CLOSURE_INVALID")
            return NorthStarEtchPreviewResult(
                run_id=run_id,
                candidate_id=candidate_id,
                candidate_digest=str(candidate.get("candidate_digest") or ""),
                receipt_digest=str(receipt["receipt_digest"]),
                preview_digest=str(existing_preview["preview_digest"]),
                result_counts=tuple(
                    {
                        str(key): int(value)
                        for key, value in dict(item).items()
                    }
                    for item in existing_preview.get("result_counts") or ()
                ),
                execution_receipt_digests=tuple(
                    str(item)
                    for item in existing_preview.get("execution_receipt_digests") or ()
                ),
            )
        prior = {
            str(item.get("skill_id") or ""): item
            for item in self._owned_records(
                "bulk_migration_stage_results", run_id, principal
            )
        }
        required_base = (
            "legacy-source-intake",
            "sql-lineage-extract",
            "domain-ontology-draft",
            "existing-concept-match",
        )
        if any(stage not in prior or prior[stage].get("status") != "pass" for stage in required_base):
            raise BulkMigrationPolicyError("BASE_PIPELINE_CLOSURE_INCOMPLETE")
        intake_output = dict(prior["legacy-source-intake"].get("output") or {})
        evidence_spans = tuple(
            dict(item) for item in intake_output.get("EvidenceSpan") or ()
        )
        domain_candidates = tuple(
            dict(item)
            for item in dict(prior["domain-ontology-draft"].get("output") or {}).get(
                "domain_candidates"
            )
            or ()
        )
        if not evidence_spans or not domain_candidates:
            raise BulkMigrationPolicyError("BASE_EVIDENCE_OR_DOMAIN_OUTPUT_MISSING")

        sources = tuple(dict(item) for item in manifest.get("source_artifacts") or ())
        sql_sources = [item for item in sources if item.get("role") == "sql"]
        metadata_sources = [
            item for item in sources if item.get("role") == "corporate_metadata"
        ]
        if len(sql_sources) != 1 or len(metadata_sources) != 1:
            raise BulkMigrationPolicyError("EXACT_SQL_METADATA_SOURCE_REQUIRED")
        legacy_sql = self.source_resolver(str(sql_sources[0]["artifact_ref"])).decode(
            "utf-8"
        )
        catalog_digest = str(manifest["catalog_snapshot_digest"])
        profile = build_metadata_mapping_profile(
            source_id=self.source_id,
            sqlite_path=self.sqlite_path,
            catalog_snapshot=dict(catalog_snapshot),
            catalog_snapshot_digest=catalog_digest,
            evidence_spans=evidence_spans,
            domain_candidates=domain_candidates,
            legacy_sql=legacy_sql,
            dialect=str(catalog_snapshot.get("dialect") or "sqlite"),
            policy_digest=policy_digest,
            fanout_budget_per_parent=1000,
        )
        retriever_digest = _digest("boi/candidate-semantic-search@1.0.0")
        search_receipts = tuple(
            build_candidate_search_receipt(
                question=question,
                metadata_snapshot_digest=str(metadata_sources[0]["digest"]),
                catalog_snapshot_digest=catalog_digest,
                schema_snapshot_digest=profile.schema_snapshot_digest,
                active_concept_index_digest=active_concept_index_digest,
                deterministic_retriever_digest=retriever_digest,
                domain_candidates=domain_candidates,
                evidence_spans=evidence_spans,
                object_mappings=profile.object_mappings,
                relationships=profile.relationship_contracts,
            )
            for question in questions
        )
        search_freeze = freeze_candidate_search_closure(
            candidate_digest=profile.profile_digest,
            search_receipts=search_receipts,
            allowed_input_refs=tuple(str(item["artifact_ref"]) for item in sources),
            denied_oracle_refs=(
                "dexa:profile",
                "registered-query-spec:*",
                "golden-sql:*",
                "golden-count:*",
                "golden-result:*",
                "historical-flat-view:*",
            ),
            closure_digests={
                "source": run.manifest_digest,
                "catalog": catalog_digest,
                "profile": profile.profile_digest,
            },
            generator_code_digest=_digest("candidate-semantic-search-v1"),
        )
        candidates = tuple(
            build_cold_candidate_logical_plan(
                question=question,
                search_receipt=search,
                profile=profile,
                candidate_freeze_digest=search_freeze.receipt_digest,
                domain_profile_digest=_digest(domain_candidates),
                query_profile_digest=_digest("boi/query-profile@0.1.0"),
            )
            for question, search in zip(questions, search_receipts)
        )
        freezes = tuple(
            freeze_cold_candidate_plan(
                candidate,
                profile_digest=profile.profile_digest,
                source_manifest_digest=run.manifest_digest,
                catalog_snapshot_digest=catalog_digest,
                generator_code_digest=_digest("cold-candidate-query-planner-v1"),
            )
            for candidate in candidates
        )
        allowed_tables = tuple(sorted(item["table"] for item in profile.object_mappings))
        schema = capture_multi_result_sqlite_schema(
            self.sqlite_path, allowed_tables=allowed_tables
        )
        gateway = MultiResultSqliteGateway(
            self.sqlite_path,
            schema=schema,
            result_artifact_root=self.result_artifact_root / run_id,
        )
        executions = []
        attestations = []
        for index, (candidate, freeze) in enumerate(zip(candidates, freezes), start=1):
            authority = validate_multi_result_plan_authority(
                candidate.plan,
                physical_mappings=profile.physical_mappings,
                selected_relationship_ids=candidate.selected_relationship_ids,
            )
            execution = gateway.create(
                MultiResultExploratoryExecutionRequest(
                    lane="exploratory",
                    logical_plan=candidate.plan,
                    validation_receipt=authority,
                    physical_mappings=profile.physical_mappings,
                    selected_relationship_ids=candidate.selected_relationship_ids,
                    quality_receipts=candidate.quality_receipts,
                    parameters=candidate.parameters,
                    principal=principal,
                    purpose=f"north-star candidate preview Q{index}",
                    idempotency_key=f"{run_id}:north-star:q{index}",
                    inline_row_limit=1000,
                    timeout_seconds=30,
                )
            )
            attestation = attest_candidate_execution(
                candidate=candidate,
                authority=authority,
                execution=execution,
                freeze_receipt=freeze,
            )
            executions.append(execution)
            attestations.append(attestation)

        # Only the independent evaluator can invoke this callback, and only
        # after the exact three-plan freeze/execution closure above has passed.
        dexa = evaluate_post_freeze_dexa(
            candidates=candidates,
            freezes=freezes,
            executions=tuple(executions),
            oracle_loader=self.oracle_loader,
        )
        if dexa.status != "PASS":
            raise BulkMigrationPolicyError("INDEPENDENT_DEXA_EVALUATION_FAILED")

        for freeze in (search_freeze, *freezes):
            freeze_payload = asdict(freeze)
            self.store.put(
                "bulk_migration_freeze_receipts",
                freeze.receipt_digest,
                {
                    **freeze_payload,
                    "run_id": run_id,
                    "employee_id": principal,
                    "production_changed": False,
                    "active_transition": False,
                },
            )
        self.store.put(
            "bulk_migration_independent_evaluations",
            dexa.receipt_digest,
            {
                **asdict(dexa),
                "run_id": run_id,
                "employee_id": principal,
                "production_changed": False,
                "active_transition": False,
            },
        )

        result_counts = tuple(
            {
                result_set.result_set_id: result_set.row_count
                for result_set in execution.result.result_sets
            }
            for execution in executions
        )
        stage_values: dict[str, object] = {
            "source-artifact": intake_output.get("source_manifest"),
            "evidence-span": [item.get("evidence_span_ref") for item in evidence_spans],
            "sql-lineage": prior["sql-lineage-extract"].get("output_digest"),
            "sparse-domain-candidate": domain_candidates,
            "existing-concept-match": prior["existing-concept-match"].get("output_digest"),
            "physical-mapping-data-quality": {
                "profile": profile.profile_digest,
                "quality": [item.receipt_digest for item in profile.data_quality_receipts],
            },
            "relationship-result-shape-contract": {
                "relationships": [item.contract_digest for item in profile.relationship_contracts],
                "result_shape": profile.result_shape_contract.contract_digest,
            },
            "candidate-logical-plan-freeze": {
                "search": search_freeze.receipt_digest,
                "plans": [item.receipt_digest for item in freezes],
            },
            "cold-semantic-planning": [item.candidate_plan_digest for item in candidates],
            "gateway-execution": [item.receipt.receipt_digest for item in executions],
            "independent-dexa-evaluation": dexa.receipt_digest,
        }
        stage_digests = {key: _digest(value) for key, value in stage_values.items()}
        checks = tuple(
            {
                "check_id": f"north-star-stage:{stage}",
                "stage_id": stage,
                "status": "pass",
                "evidence_digest": stage_digests[stage],
            }
            for stage in NORTH_STAR_ETCH_PIPELINE_V1.required_stage_ids
        )
        existing_matches = list(
            prior["existing-concept-match"].get("match_candidates") or ()
        )
        catalog_tables = dict(catalog_snapshot.get("tables") or {})
        logical_by_mapping: dict[str, str] = {}
        primary_mapping_refs: set[str] = set()
        for object_mapping in profile.object_mappings:
            object_ref = str(object_mapping["object_ref"])
            for mapping_ref in object_mapping["property_mapping_refs"]:
                logical_by_mapping[str(mapping_ref)] = object_ref
            primary_mapping_refs.update(
                str(item) for item in object_mapping["logical_key_mapping_refs"]
            )
        foreign_mapping_refs = {
            str(item)
            for relationship in profile.relationship_contracts
            for item in relationship.physical_keys.right_mapping_refs
        }
        workbench_mappings = []
        for mapping in profile.physical_mappings:
            table_definition = dict(catalog_tables.get(mapping.table) or {})
            column_definition = dict(table_definition.get("columns") or {}).get(
                mapping.column, "UNKNOWN"
            )
            data_type = (
                str(column_definition.get("data_type") or "UNKNOWN")
                if isinstance(column_definition, Mapping)
                else str(column_definition)
            )
            key_role = (
                "primary"
                if mapping.mapping_ref in primary_mapping_refs
                else "foreign"
                if mapping.mapping_ref in foreign_mapping_refs
                else "attribute"
            )
            workbench_mappings.append(
                {
                    "mapping_id": mapping.mapping_ref,
                    "logical_ref": logical_by_mapping[mapping.mapping_ref],
                    "source_ref": mapping.source_id,
                    "table_ref": f"table:{mapping.table}",
                    "column_ref": f"column:{mapping.table}.{mapping.column}",
                    "key_role": key_role,
                    "data_type": data_type,
                    "unit": None,
                    "cardinality": "one" if key_role == "primary" else "many",
                    "status": "verified",
                    "evidence_digest": mapping.revision_digest,
                }
            )
        plan_summaries = []
        for candidate, execution, attestation in zip(
            candidates, executions, attestations
        ):
            parameter_types = {
                item.name: item.type for item in candidate.plan.parameter_specs
            }
            plan_summaries.append(
                {
                    "logical_plan_digest": candidate.plan.plan_digest,
                    "typed_parameters": {
                        name: {"type": parameter_types[name], "value": value}
                        for name, value in sorted(candidate.parameters.items())
                    },
                    "protected_sql_ref": f"protected-sql:{execution.execution_id}",
                    "result_digest": execution.result.result_digest,
                    "execution_receipt_digest": execution.receipt.receipt_digest,
                    "classification": "PROVISIONAL",
                    "attestation_status": "PROVISIONAL",
                    "attestation_receipt_digest": attestation.attestation_digest,
                }
            )
        domain_profile_digest = _digest(domain_candidates)
        query_profile_digest = _digest(
            [item.candidate_plan_digest for item in candidates]
        )
        preview_payload = {
            "preview_version": "boi/north-star-etch-preview@1.0.0",
            "run_id": run_id,
            "manifest_digest": run.manifest_digest,
            "pipeline_contract_id": NORTH_STAR_ETCH_PIPELINE_V1.contract_id,
            "stage_digests": stage_digests,
            "candidate_profile_digest": profile.profile_digest,
            "domain_profile_digest": domain_profile_digest,
            "query_profile_digest": query_profile_digest,
            "domain_candidates": domain_candidates,
            "existing_matches": existing_matches,
            "object_mappings": list(profile.object_mappings),
            "workbench_mappings": workbench_mappings,
            "relationship_contracts": [
                {
                    **item.model_dump(mode="json"),
                    "contract_digest": item.contract_digest,
                }
                for item in profile.relationship_contracts
            ],
            "result_shape_contract": profile.result_shape_contract.model_dump(
                mode="json"
            ),
            "plan_summaries": plan_summaries,
            "search_receipt_digests": [
                item.candidate_search_result_digest for item in search_receipts
            ],
            "freeze_receipt_digests": [item.receipt_digest for item in freezes],
            "plan_digests": [item.plan.plan_digest for item in candidates],
            "execution_receipt_digests": [
                item.receipt.receipt_digest for item in executions
            ],
            "execution_receipts": [
                item.receipt.model_dump(mode="json", exclude={"executed_sql"})
                for item in executions
            ],
            "attestation_digests": [item.attestation_digest for item in attestations],
            "attestations": [asdict(item) for item in attestations],
            "dexa_evaluation_receipt_digest": dexa.receipt_digest,
            "result_counts": result_counts,
            "data_quality_receipts": [
                item.model_dump(mode="json") for item in profile.data_quality_receipts
            ],
            "result_artifact_refs": [
                item.receipt.result_artifact_ref for item in executions
            ],
            "result_classification": "PROVISIONAL",
            "production_release_qualified": False,
            "production_changed": False,
            "active_transition": False,
        }
        preview_digest = _digest(preview_payload)
        preview_id = f"preview:{run_id}"
        self.store.put(
            "bulk_migration_candidate_previews",
            preview_id,
            {
                **preview_payload,
                "preview_id": preview_id,
                "preview_digest": preview_digest,
                "employee_id": principal,
            },
        )
        run = self.orchestrator.record_service_stage_evidence(
            principal=principal, run_id=run_id,
            pipeline_contract_id=NORTH_STAR_ETCH_PIPELINE_V1.contract_id,
            stage_values=stage_values,
            executor_code_digest='sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
        run = self.orchestrator.mark_candidate_preview_ready(
            principal=principal,
            run_id=run_id,
        )
        candidate_id = run.candidate_refs[0]
        existing_candidate = self.store.get("bulk_migration_candidates", candidate_id)
        if not existing_candidate or str(existing_candidate.get("employee_id") or "") != principal:
            raise BulkMigrationPolicyError("CANDIDATE_ACCESS_DENIED")
        candidate_digest = _digest(
            {
                "base_candidate_digest": existing_candidate["candidate_digest"],
                "preview_digest": preview_digest,
                "pipeline_contract_id": NORTH_STAR_ETCH_PIPELINE_V1.contract_id,
            }
        )
        self.store.put(
            "bulk_migration_candidates",
            candidate_id,
            {
                **existing_candidate,
                "state": "candidate_preview_ready",
                "candidate_digest": candidate_digest,
                "preview_digest": preview_digest,
                "production_changed": False,
                "active_transition": False,
            },
        )
        receipt = self.orchestrator.finalize_receipt(
            principal=principal,
            run_id=run_id,
            pipeline_contract_id=NORTH_STAR_ETCH_PIPELINE_V1.contract_id,
            required_stage_ids=NORTH_STAR_ETCH_PIPELINE_V1.required_stage_ids,
            optional_stage_ids=NORTH_STAR_ETCH_PIPELINE_V1.optional_stage_ids,
            stage_digests=stage_digests,
            component_digests=(
                profile.profile_digest,
                search_freeze.receipt_digest,
                dexa.receipt_digest,
                *(item.attestation_digest for item in attestations),
            ),
            checks=checks,
            token_metrics={
                "pi_invocation_count": 0,
                "pi_input_bytes": 0,
                "codex_invocation_count": 0,
                # This service replays a contributed structured candidate; it
                # does not resolve an extraction-cache entry/output closure.
                "cache_hit_count": 0,
                "deterministic_replay_count": 1,
            },
        )
        return NorthStarEtchPreviewResult(
            run_id=run_id,
            candidate_id=candidate_id,
            candidate_digest=candidate_digest,
            receipt_digest=receipt.receipt_digest,
            preview_digest=preview_digest,
            result_counts=result_counts,
            execution_receipt_digests=tuple(
                item.receipt.receipt_digest for item in executions
            ),
        )
