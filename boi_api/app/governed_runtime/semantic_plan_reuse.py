"""Qualified cache and candidate-only reuse for the generic semantic path.

The store is deliberately absent from cold qualification runs.  It can be
constructed only from an intact PASS composite qualification receipt, caches
only a fully validated closed receipt chain, and has no Release authority.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from .ledger import GovernedRuntimeLedger, RecordKind, record_digest
from .semantic_query_execution import SemanticPlanReuseReceipt
from .semantic_query_planner import (
    BindingResolutionOutcome,
    CheckEvidenceStore,
    GenericBindingSolver,
    GenericRelationalPlanner,
    RelationalAst,
    SemanticPlanValidationReceipt,
    SemanticPlanValidationVerifier,
    SemanticPlanValidator,
    SemanticPlanningContext,
)


def _canonical(value: object) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


class QualifiedSemanticPlanPreparation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["READY", "BLOCKED", "CLARIFICATION_REQUIRED"]
    reason_codes: tuple[str, ...]
    cache_status: Literal["HIT", "MISS", "NOT_APPLICABLE"]
    binding_receipt: BindingResolutionOutcome | None
    plan: RelationalAst | None
    validation_receipt: SemanticPlanValidationReceipt | None
    plan_reuse_receipt: SemanticPlanReuseReceipt | None


class GenericPlanPromotionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_id: str
    candidate_digest: str
    qualification_receipt_digest: str
    plan_cache_key: str
    cache_entry_digest: str
    semantic_context_digest: str
    principal_id: str
    purpose: str
    acl_projection_digest: str
    semantic_bundle_digest: str
    intent_synthesis_receipt_digest: str
    intent_model_id: str
    intent_model_digest: str
    intent_role_digest: str
    intent_prompt_digest: str
    intent_digest: str
    logical_plan_digest: str
    validation_receipt_digest: str
    active_release_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    catalog_snapshot_digest: str
    catalog_snapshot_content_digest: str
    schema_digest: str
    capability_digest: str
    planning_policy_digest: str
    distinct_execution_count: int
    execution_ids: tuple[str, ...]
    execution_receipt_digests: tuple[str, ...]
    result_digests: tuple[str, ...]
    status: Literal["candidate"] = "candidate"
    qualified: Literal[False] = False
    released: Literal[False] = False
    active: Literal[False] = False
    release_authority: Literal["forbidden"] = "forbidden"


class QualifiedSemanticPlanStore:
    """Persistent content-addressed cache with a candidate-only usage ledger."""

    QUALIFICATION_SCHEMA = "boi-generality-composite-qualification/v1"
    ENTRY_SCHEMA = "boi-qualified-semantic-plan-cache-entry/v1"
    OBSERVATION_SCHEMA = "boi-qualified-semantic-plan-observation/v1"

    def __init__(
        self, root: Path | str, *, qualification_receipt: dict[str, Any],
        expected_qualification_digest: str,
        promotion_threshold: int = 3,
    ) -> None:
        if promotion_threshold < 2:
            raise ValueError("PROMOTION_THRESHOLD_TOO_LOW")
        unsigned = {
            key: value for key, value in qualification_receipt.items()
            if key != "receipt_digest"
        }
        if qualification_receipt.get("receipt_digest") != _digest(unsigned):
            raise ValueError("GENERALITY_QUALIFICATION_DIGEST_INVALID")
        if qualification_receipt.get("receipt_digest") != expected_qualification_digest:
            raise ValueError("GENERALITY_QUALIFICATION_PIN_MISMATCH")
        if not (
            qualification_receipt.get("schema") == self.QUALIFICATION_SCHEMA
            and qualification_receipt.get("status") == "PASS"
            and qualification_receipt.get("generality_qualification_eligible") is True
            and qualification_receipt.get("reason_codes") == []
            and all(
                qualification_receipt.get(field) is False
                for field in (
                    "actual_release_activation", "actual_active_pointer_transition",
                    "merge", "push",
                )
            )
        ):
            raise ValueError("GENERALITY_PATH_NOT_QUALIFIED")
        self.root = Path(root)
        self.entries_root = self.root / "entries" / "sha256"
        self.observations_root = self.root / "observations"
        self.candidates_root = self.root / "candidates"
        self.entries_root.mkdir(parents=True, exist_ok=True)
        self.observations_root.mkdir(parents=True, exist_ok=True)
        self.candidates_root.mkdir(parents=True, exist_ok=True)
        self.qualification_receipt_digest = str(
            qualification_receipt["receipt_digest"]
        )
        self.promotion_threshold = promotion_threshold

    @staticmethod
    def _key_payload(
        context: SemanticPlanningContext, *, intent_digest: str,
    ) -> dict[str, str]:
        return {
            "intent_digest": intent_digest,
            "semantic_context_digest": context.context_digest,
            "question_digest": context.question_digest,
            "principal_id": context.principal_id,
            "purpose": context.purpose,
            "acl_projection_digest": context.acl_projection_digest,
            "semantic_bundle_digest": context.semantic_bundle_digest,
            "semantic_bundle_content_digest": context.semantic_bundle_content_digest,
            "retrieval_receipt_digest": context.retrieval_receipt_digest,
            "semantic_resolution_receipt_digest": (
                context.semantic_resolution_receipt_digest
            ),
            "intent_synthesis_receipt_digest": (
                context.intent_synthesis_receipt_digest
            ),
            "intent_model_id": context.intent_model_id,
            "intent_model_digest": context.intent_model_digest,
            "intent_role_digest": context.intent_role_digest,
            "intent_prompt_digest": context.intent_prompt_digest,
            "active_release_digest": context.active_release_digest,
            "domain_profile_digest": context.domain_profile_digest,
            "mapping_profile_digest": context.mapping_profile_digest,
            "query_profile_digest": context.query_profile_digest,
            "catalog_snapshot_digest": context.catalog_snapshot_digest,
            "catalog_snapshot_content_digest": (
                context.catalog_snapshot_content_digest
            ),
            "schema_digest": context.schema_digest,
            "capability_digest": context.capability_digest,
            "planning_policy_digest": context.planning_policy_digest,
        }

    def cache_key(
        self, context: SemanticPlanningContext, *, intent_digest: str,
    ) -> str:
        return _digest(self._key_payload(context, intent_digest=intent_digest))

    def entry_path(self, cache_key: str) -> Path:
        if not cache_key.startswith("sha256:") or len(cache_key) != 71:
            raise ValueError("SEMANTIC_PLAN_CACHE_KEY_INVALID")
        suffix = cache_key.removeprefix("sha256:")
        if any(char not in "0123456789abcdef" for char in suffix):
            raise ValueError("SEMANTIC_PLAN_CACHE_KEY_INVALID")
        return self.entries_root / f"{suffix}.json"

    @staticmethod
    def _write_immutable(path: Path, value: dict[str, Any]) -> None:
        encoded = _canonical(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != encoded:
                raise ValueError("SEMANTIC_PLAN_CACHE_IMMUTABLE_CONFLICT")
            return
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    def _entry_values(
        self, *, cache_key: str, context: SemanticPlanningContext,
        binding: BindingResolutionOutcome, plan: RelationalAst,
        validation: SemanticPlanValidationReceipt,
    ) -> dict[str, Any]:
        return {
            "schema": self.ENTRY_SCHEMA,
            "cache_key": cache_key,
            "qualification_receipt_digest": self.qualification_receipt_digest,
            "key_context": self._key_payload(
                context, intent_digest=plan.intent_digest
            ),
            "binding_receipt": binding.model_dump(mode="json"),
            "logical_plan": plan.model_dump(mode="json"),
            "validation_receipt": validation.model_dump(mode="json"),
        }

    def _remember(
        self, *, context: SemanticPlanningContext,
        binding: BindingResolutionOutcome, plan: RelationalAst,
        validation: SemanticPlanValidationReceipt,
        ledger: GovernedRuntimeLedger, evidence_store: CheckEvidenceStore,
    ) -> str:
        if binding.status != "READY" or validation.status != "PASS":
            raise ValueError("ONLY_PASSING_GENERIC_PLAN_IS_CACHEABLE")
        verification = SemanticPlanValidationVerifier().verify(
            validation, ledger=ledger, evidence_store=evidence_store
        )
        if not verification.ok:
            raise ValueError(verification.error_codes[0])
        if not (
            binding.semantic_context_digest == context.context_digest
            and plan.semantic_context_digest == context.context_digest
            and plan.binding_digest == binding.binding_digest
            and validation.semantic_context_digest == context.context_digest
            and validation.plan_digest == plan.plan_digest
        ):
            raise ValueError("SEMANTIC_PLAN_CACHE_CHAIN_MISMATCH")
        cache_key = self.cache_key(context, intent_digest=plan.intent_digest)
        values = self._entry_values(
            cache_key=cache_key, context=context, binding=binding,
            plan=plan, validation=validation,
        )
        self._write_immutable(
            self.entry_path(cache_key),
            {**values, "entry_digest": _digest(values)},
        )
        return cache_key

    def _load(
        self, *, context: SemanticPlanningContext, intent_digest: str,
        ledger: GovernedRuntimeLedger, evidence_store: CheckEvidenceStore,
    ) -> tuple[
        BindingResolutionOutcome, RelationalAst,
        SemanticPlanValidationReceipt, SemanticPlanReuseReceipt,
    ] | None:
        cache_key = self.cache_key(context, intent_digest=intent_digest)
        path = self.entry_path(cache_key)
        if not path.exists():
            return None
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("SEMANTIC_PLAN_CACHE_ENTRY_DIGEST_INVALID") from exc
        if not isinstance(stored, dict):
            raise ValueError("SEMANTIC_PLAN_CACHE_ENTRY_DIGEST_INVALID")
        values = {key: value for key, value in stored.items() if key != "entry_digest"}
        entry_digest = stored.get("entry_digest")
        if (
            entry_digest != _digest(values)
            or values.get("schema") != self.ENTRY_SCHEMA
            or values.get("cache_key") != cache_key
            or values.get("qualification_receipt_digest")
            != self.qualification_receipt_digest
            or values.get("key_context")
            != self._key_payload(context, intent_digest=intent_digest)
        ):
            raise ValueError("SEMANTIC_PLAN_CACHE_ENTRY_DIGEST_INVALID")
        try:
            binding = BindingResolutionOutcome.model_validate(
                values["binding_receipt"]
            )
            plan = RelationalAst.model_validate(values["logical_plan"])
            validation = SemanticPlanValidationReceipt.model_validate(
                values["validation_receipt"]
            )
        except Exception as exc:
            raise ValueError("SEMANTIC_PLAN_CACHE_ENTRY_INVALID") from exc
        verification = SemanticPlanValidationVerifier().verify(
            validation, ledger=ledger, evidence_store=evidence_store
        )
        if not verification.ok:
            raise ValueError(verification.error_codes[0])
        if not (
            binding.status == "READY"
            and validation.status == "PASS"
            and binding.semantic_context_digest == context.context_digest
            and plan.semantic_context_digest == context.context_digest
            and plan.intent_digest == intent_digest
            and plan.binding_digest == binding.binding_digest
            and validation.plan_digest == plan.plan_digest
            and validation.receipt_digest
            == str(values["validation_receipt"]["receipt_digest"])
        ):
            raise ValueError("SEMANTIC_PLAN_CACHE_CHAIN_MISMATCH")
        cache_id = f"semantic-plan-cache:{cache_key.removeprefix('sha256:')}"
        receipt_values = {
            "schema_name": "boi-qualified-semantic-plan-reuse/v1",
            "status": "HIT",
            "cache_id": cache_id,
            "cache_key": cache_key,
            "cache_entry_ref": f"semantic-plan-cache://{cache_key}",
            "cache_entry_digest": entry_digest,
            "qualification_receipt_digest": self.qualification_receipt_digest,
            "semantic_context_digest": context.context_digest,
            "intent_digest": intent_digest,
            "binding_digest": binding.binding_digest,
            "plan_digest": plan.plan_digest,
            "validation_receipt_digest": validation.receipt_digest,
        }
        receipt = SemanticPlanReuseReceipt(
            **receipt_values, receipt_digest=_digest(receipt_values)
        )
        return binding, plan, validation, receipt

    def prepare(
        self, context: SemanticPlanningContext, *, ledger: GovernedRuntimeLedger,
        evidence_store: CheckEvidenceStore, occurred_at: str,
    ) -> QualifiedSemanticPlanPreparation:
        resolved = context.resolution.resolved_intent
        if resolved is None:
            return QualifiedSemanticPlanPreparation(
                status="BLOCKED", reason_codes=("RESOLUTION_NOT_RESOLVED",),
                cache_status="NOT_APPLICABLE", binding_receipt=None, plan=None,
                validation_receipt=None, plan_reuse_receipt=None,
            )
        cached = self._load(
            context=context, intent_digest=resolved.intent_digest,
            ledger=ledger, evidence_store=evidence_store,
        )
        if cached is not None:
            binding, plan, validation, reuse = cached
            return QualifiedSemanticPlanPreparation(
                status="READY", reason_codes=(), cache_status="HIT",
                binding_receipt=binding, plan=plan,
                validation_receipt=validation, plan_reuse_receipt=reuse,
            )
        binding = GenericBindingSolver().resolve(context)
        if binding.status != "READY":
            return QualifiedSemanticPlanPreparation(
                status=binding.status, reason_codes=binding.reason_codes,
                cache_status="NOT_APPLICABLE", binding_receipt=binding, plan=None,
                validation_receipt=None, plan_reuse_receipt=None,
            )
        planned = GenericRelationalPlanner().plan(context, binding=binding)
        if planned.status != "READY" or planned.plan is None:
            return QualifiedSemanticPlanPreparation(
                status=planned.status, reason_codes=planned.reason_codes,
                cache_status="NOT_APPLICABLE", binding_receipt=binding, plan=None,
                validation_receipt=None, plan_reuse_receipt=None,
            )
        validation = SemanticPlanValidator().validate(
            planned.plan, context=context, binding=binding, ledger=ledger,
            evidence_store=evidence_store, occurred_at=occurred_at,
        )
        if validation.status != "PASS":
            return QualifiedSemanticPlanPreparation(
                status="BLOCKED", reason_codes=validation.reason_codes,
                cache_status="NOT_APPLICABLE", binding_receipt=binding,
                plan=planned.plan, validation_receipt=validation,
                plan_reuse_receipt=None,
            )
        self._remember(
            context=context, binding=binding, plan=planned.plan,
            validation=validation, ledger=ledger, evidence_store=evidence_store,
        )
        return QualifiedSemanticPlanPreparation(
            status="READY", reason_codes=(), cache_status="MISS",
            binding_receipt=binding, plan=planned.plan,
            validation_receipt=validation, plan_reuse_receipt=None,
        )

    def validate_request(
        self, request: Any, *, ledger: GovernedRuntimeLedger,
        evidence_store: CheckEvidenceStore,
    ) -> str | None:
        loaded = self._load(
            context=request.semantic_context,
            intent_digest=request.logical_plan.intent_digest,
            ledger=ledger, evidence_store=evidence_store,
        )
        if loaded is None:
            raise ValueError("QUALIFIED_SEMANTIC_PLAN_NOT_CACHED")
        binding, plan, validation, expected_receipt = loaded
        if (
            request.binding_receipt != binding
            or request.logical_plan != plan
            or request.validation_receipt != validation
        ):
            raise ValueError("SEMANTIC_PLAN_CACHE_REQUEST_MISMATCH")
        if request.plan_reuse_receipt is None:
            return None
        if request.plan_reuse_receipt != expected_receipt:
            raise ValueError("SEMANTIC_PLAN_REUSE_RECEIPT_MISMATCH")
        return expected_receipt.cache_id

    def observe_success(
        self, request: Any, *, execution_id: str,
        execution_receipt_digest: str, result_digest: str,
        ledger: GovernedRuntimeLedger, evidence_store: CheckEvidenceStore,
        occurred_at: str,
    ) -> GenericPlanPromotionCandidate | None:
        self.validate_request(
            request, ledger=ledger, evidence_store=evidence_store
        )
        cache_key = self.cache_key(
            request.semantic_context, intent_digest=request.logical_plan.intent_digest
        )
        observation_values = {
            "schema": self.OBSERVATION_SCHEMA,
            "qualification_receipt_digest": self.qualification_receipt_digest,
            "cache_key": cache_key,
            "cache_entry_digest": json.loads(
                self.entry_path(cache_key).read_text(encoding="utf-8")
            )["entry_digest"],
            "semantic_context_digest": request.semantic_context.context_digest,
            "principal_id": request.semantic_context.principal_id,
            "purpose": request.semantic_context.purpose,
            "acl_projection_digest": request.semantic_context.acl_projection_digest,
            "semantic_bundle_digest": request.semantic_context.semantic_bundle_digest,
            "intent_synthesis_receipt_digest": (
                request.semantic_context.intent_synthesis_receipt_digest
            ),
            "intent_model_id": request.semantic_context.intent_model_id,
            "intent_model_digest": request.semantic_context.intent_model_digest,
            "intent_role_digest": request.semantic_context.intent_role_digest,
            "intent_prompt_digest": request.semantic_context.intent_prompt_digest,
            "intent_digest": request.logical_plan.intent_digest,
            "logical_plan_digest": request.logical_plan.plan_digest,
            "validation_receipt_digest": request.validation_receipt.receipt_digest,
            "active_release_digest": request.semantic_context.active_release_digest,
            "domain_profile_digest": request.semantic_context.domain_profile_digest,
            "mapping_profile_digest": request.semantic_context.mapping_profile_digest,
            "query_profile_digest": request.semantic_context.query_profile_digest,
            "catalog_snapshot_digest": request.semantic_context.catalog_snapshot_digest,
            "catalog_snapshot_content_digest": (
                request.semantic_context.catalog_snapshot_content_digest
            ),
            "schema_digest": request.semantic_context.schema_digest,
            "capability_digest": request.semantic_context.capability_digest,
            "planning_policy_digest": request.semantic_context.planning_policy_digest,
            "execution_id": execution_id,
            "execution_receipt_digest": execution_receipt_digest,
            "result_digest": result_digest,
        }
        observation = {
            **observation_values, "observation_digest": _digest(observation_values)
        }
        observation_dir = self.observations_root / cache_key.removeprefix("sha256:")
        self._write_immutable(
            observation_dir / f"{hashlib.sha256(execution_id.encode()).hexdigest()}.json",
            observation,
        )
        existing_candidates = tuple(
            self.candidates_root.glob(f"{cache_key.removeprefix('sha256:')}-*.json")
        )
        if existing_candidates:
            return self._load_candidate(existing_candidates[0], ledger=ledger)
        observations: list[dict[str, Any]] = []
        for path in observation_dir.glob("*.json"):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError("SEMANTIC_PLAN_OBSERVATION_DIGEST_INVALID") from exc
            unsigned_observation = {
                key: value for key, value in item.items()
                if key != "observation_digest"
            }
            if (
                item.get("observation_digest") != _digest(unsigned_observation)
                or item.get("schema") != self.OBSERVATION_SCHEMA
                or item.get("qualification_receipt_digest")
                != self.qualification_receipt_digest
                or item.get("cache_key") != cache_key
            ):
                raise ValueError("SEMANTIC_PLAN_OBSERVATION_DIGEST_INVALID")
            observations.append(item)
        observations.sort(key=lambda item: item["execution_id"])
        if len(observations) < self.promotion_threshold:
            return None
        selected = observations[: self.promotion_threshold]
        payload = {
            "scope": "generic_semantic_plan_reuse",
            "qualification_receipt_digest": self.qualification_receipt_digest,
            "plan_cache_key": cache_key,
            "cache_entry_digest": selected[0]["cache_entry_digest"],
            "semantic_context_digest": request.semantic_context.context_digest,
            "principal_id": request.semantic_context.principal_id,
            "purpose": request.semantic_context.purpose,
            "acl_projection_digest": request.semantic_context.acl_projection_digest,
            "semantic_bundle_digest": request.semantic_context.semantic_bundle_digest,
            "intent_synthesis_receipt_digest": (
                request.semantic_context.intent_synthesis_receipt_digest
            ),
            "intent_model_id": request.semantic_context.intent_model_id,
            "intent_model_digest": request.semantic_context.intent_model_digest,
            "intent_role_digest": request.semantic_context.intent_role_digest,
            "intent_prompt_digest": request.semantic_context.intent_prompt_digest,
            "intent_digest": request.logical_plan.intent_digest,
            "logical_plan_digest": request.logical_plan.plan_digest,
            "validation_receipt_digest": request.validation_receipt.receipt_digest,
            "active_release_digest": request.semantic_context.active_release_digest,
            "domain_profile_digest": request.semantic_context.domain_profile_digest,
            "mapping_profile_digest": request.semantic_context.mapping_profile_digest,
            "query_profile_digest": request.semantic_context.query_profile_digest,
            "catalog_snapshot_digest": request.semantic_context.catalog_snapshot_digest,
            "catalog_snapshot_content_digest": (
                request.semantic_context.catalog_snapshot_content_digest
            ),
            "schema_digest": request.semantic_context.schema_digest,
            "capability_digest": request.semantic_context.capability_digest,
            "planning_policy_digest": request.semantic_context.planning_policy_digest,
            "distinct_execution_count": len(selected),
            "execution_ids": [item["execution_id"] for item in selected],
            "execution_receipt_digests": [
                item["execution_receipt_digest"] for item in selected
            ],
            "result_digests": [item["result_digest"] for item in selected],
            "status": "candidate",
            "qualified": False,
            "released": False,
            "active": False,
            "release_authority": "forbidden",
        }
        record = ledger.append(
            RecordKind.PROMOTION_CANDIDATE, payload,
            authority="promotion_service", occurred_at=occurred_at,
        )
        candidate = GenericPlanPromotionCandidate(
            candidate_id=record.record_id,
            candidate_digest=record_digest(record.record_id),
            **{key: value for key, value in payload.items() if key != "scope"},
        )
        candidate_path = self.candidates_root / (
            f"{cache_key.removeprefix('sha256:')}-"
            f"{candidate.candidate_digest.removeprefix('sha256:')}.json"
        )
        self._write_immutable(candidate_path, candidate.model_dump(mode="json"))
        return candidate

    @staticmethod
    def _load_candidate(
        path: Path, *, ledger: GovernedRuntimeLedger | None,
    ) -> GenericPlanPromotionCandidate:
        candidate = GenericPlanPromotionCandidate.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if candidate.candidate_digest != record_digest(candidate.candidate_id):
            raise ValueError("PROMOTION_CANDIDATE_DIGEST_INVALID")
        if ledger is not None:
            record = ledger.read(candidate.candidate_id)
            expected = candidate.model_dump(
                mode="json", exclude={"candidate_id", "candidate_digest"}
            )
            if (
                record.kind is not RecordKind.PROMOTION_CANDIDATE
                or record.authority != "promotion_service"
                or record.payload.get("scope") != "generic_semantic_plan_reuse"
                or {
                    key: value for key, value in record.payload.items()
                    if key != "scope"
                } != expected
            ):
                raise ValueError("PROMOTION_CANDIDATE_LEDGER_MISMATCH")
        return candidate

    def promotion_candidates(
        self, *, ledger: GovernedRuntimeLedger | None = None,
    ) -> tuple[GenericPlanPromotionCandidate, ...]:
        return tuple(
            self._load_candidate(path, ledger=ledger)
            for path in sorted(self.candidates_root.glob("*.json"))
        )
