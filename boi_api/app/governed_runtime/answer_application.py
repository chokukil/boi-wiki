"""Channel-neutral persistence boundary for qualified answer envelopes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .answer_quality import (
    AnswerQualificationReceipt,
    AnswerQualityEvaluator,
    AnswerRequirementContract,
    DeterministicAnswerComposer,
    FrozenAnswerResultSet,
    VerifiedAnswerEnvelope,
)


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class AnswerApplicationError(ValueError):
    """The requested answer operation violates owner or digest authority."""


class AnswerStore(Protocol):
    def put(self, collection: str, key: str, value: dict) -> None: ...
    def get(self, collection: str, key: str): ...
    def list(self, collection: str, *, limit: int = 100): ...


class QueryClarificationReply(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    challenge_ref: str = Field(min_length=1, max_length=240)
    option_id: str = Field(min_length=1, max_length=100)


class VerifiedAnswerQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=1, max_length=240)
    parameters: dict[str, object] = Field(default_factory=dict)
    purpose: str = Field(default="verified-answer", min_length=1, max_length=240)
    clarification_response: QueryClarificationReply | None = None


class PreparedAnswerExecution(BaseModel):
    """Trusted frozen-result input registered by the governed query runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-prepared-answer-execution/v1"] = (
        "boi-prepared-answer-execution/v1"
    )
    input_ref: str
    owner_principal: str
    run_id: str
    requirement: AnswerRequirementContract
    frozen_result_sets: tuple[FrozenAnswerResultSet, ...]
    execution_classification: Literal["ATTESTED", "PROVISIONAL", "BLOCKED"]
    execution_result_digest: str
    renderer_code_digest: str
    evaluator_code_digest: str
    acl_evidence_digest: str
    execution_receipt_ref: str
    snapshot_notice: str
    quality_measurements: dict[str, int]
    quality_evidence_digests: dict[str, str]
    input_digest: str

    @classmethod
    def create(
        cls,
        *,
        input_ref: str,
        owner_principal: str,
        run_id: str,
        requirement: AnswerRequirementContract,
        frozen_result_sets: Sequence[FrozenAnswerResultSet],
        execution_classification: Literal["ATTESTED", "PROVISIONAL", "BLOCKED"],
        execution_result_digest: str,
        renderer_code_digest: str,
        evaluator_code_digest: str,
        acl_evidence_digest: str,
        execution_receipt_ref: str,
        snapshot_notice: str,
        quality_measurements: Mapping[str, int],
        quality_evidence_digests: Mapping[str, str],
    ) -> "PreparedAnswerExecution":
        unsigned = {
            "schema_name": "boi-prepared-answer-execution/v1",
            "input_ref": input_ref,
            "owner_principal": owner_principal,
            "run_id": run_id,
            "requirement": requirement.model_dump(mode="json"),
            "frozen_result_sets": [
                item.model_dump(mode="json") for item in frozen_result_sets
            ],
            "execution_classification": execution_classification,
            "execution_result_digest": execution_result_digest,
            "renderer_code_digest": renderer_code_digest,
            "evaluator_code_digest": evaluator_code_digest,
            "acl_evidence_digest": acl_evidence_digest,
            "execution_receipt_ref": execution_receipt_ref,
            "snapshot_notice": snapshot_notice,
            "quality_measurements": dict(quality_measurements),
            "quality_evidence_digests": dict(quality_evidence_digests),
        }
        return cls.model_validate({**unsigned, "input_digest": _digest(unsigned)})

    @model_validator(mode="after")
    def validate_prepared_execution(self) -> "PreparedAnswerExecution":
        if not self.input_ref or not self.owner_principal or not self.run_id:
            raise ValueError("PREPARED_ANSWER_IDENTITY_REQUIRED")
        if not self.frozen_result_sets:
            raise ValueError("PREPARED_ANSWER_RESULT_REQUIRED")
        if self.requirement.acl_policy_digest != self.acl_evidence_digest:
            raise ValueError("PREPARED_ANSWER_ACL_MISMATCH")
        required_quality = set(self.requirement.required_quality_disclosures)
        if not required_quality <= set(self.quality_measurements) or not required_quality <= set(
            self.quality_evidence_digests
        ):
            raise ValueError("PREPARED_ANSWER_QUALITY_CLOSURE_INCOMPLETE")
        unsigned = self.model_dump(mode="json", exclude={"input_digest"})
        if self.input_digest != _digest(unsigned):
            raise ValueError("PREPARED_ANSWER_DIGEST_MISMATCH")
        return self


class VerifiedAnswerRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-verified-answer-record/v1"] = (
        "boi-verified-answer-record/v1"
    )
    answer_id: str
    owner_principal: str
    run_id: str
    answer_semantic_digest: str
    envelope: VerifiedAnswerEnvelope
    qualification_receipt: AnswerQualificationReceipt
    ui_url: str
    safe_mcp_reproduction_ref: str
    record_digest: str

    @model_validator(mode="after")
    def validate_record(self) -> "VerifiedAnswerRecord":
        if self.answer_semantic_digest != self.envelope.answer_semantic_digest:
            raise ValueError("ANSWER_SEMANTIC_DIGEST_MISMATCH")
        if self.qualification_receipt.answer_envelope_digest != self.answer_semantic_digest:
            raise ValueError("ANSWER_RECEIPT_BINDING_MISMATCH")
        unsigned = self.model_dump(mode="json", exclude={"record_digest"})
        if self.record_digest != _digest(unsigned):
            raise ValueError("ANSWER_RECORD_DIGEST_MISMATCH")
        return self


class AnswerApplicationService:
    """Store one semantic answer record and channel-specific invocation evidence."""

    def __init__(self, store: AnswerStore):
        self.store = store

    @staticmethod
    def _idempotency_id(principal: str, key: str) -> str:
        return _digest({"principal": principal, "idempotency_key": key})

    @staticmethod
    def _answer_id(principal: str, run_id: str, idempotency_key: str) -> str:
        identity = _digest(
            {
                "principal": principal,
                "run_id": run_id,
                "idempotency_key": idempotency_key,
            }
        )
        return "answer_" + identity.removeprefix("sha256:")[:32]

    def publish(
        self,
        *,
        principal: str,
        run_id: str,
        idempotency_key: str,
        channel: Literal["ui", "mcp", "rest"],
        envelope: VerifiedAnswerEnvelope,
        qualification_receipt: AnswerQualificationReceipt,
    ) -> VerifiedAnswerRecord:
        if not principal or not run_id or not idempotency_key:
            raise AnswerApplicationError("ANSWER_PUBLISH_IDENTITY_REQUIRED")
        if qualification_receipt.answer_envelope_digest != envelope.answer_semantic_digest:
            raise AnswerApplicationError("ANSWER_RECEIPT_BINDING_MISMATCH")
        idem_id = self._idempotency_id(principal, idempotency_key)
        existing_idem = self.store.get("verified_answer_idempotency", idem_id)
        if existing_idem:
            record = self.get(
                principal=principal, answer_id=str(existing_idem["answer_id"])
            )
            if (
                record.run_id != run_id
                or record.answer_semantic_digest != envelope.answer_semantic_digest
            ):
                raise AnswerApplicationError("ANSWER_IDEMPOTENCY_CONFLICT")
            self._record_invocation(record, channel, cache_hit=True)
            return record

        answer_id = self._answer_id(principal, run_id, idempotency_key)
        unsigned = {
            "schema_name": "boi-verified-answer-record/v1",
            "answer_id": answer_id,
            "owner_principal": principal,
            "run_id": run_id,
            "answer_semantic_digest": envelope.answer_semantic_digest,
            "envelope": envelope.model_dump(mode="json"),
            "qualification_receipt": qualification_receipt.model_dump(mode="json"),
            "ui_url": f"/ontology/answers/{answer_id}",
            "safe_mcp_reproduction_ref": f"boi_get:{answer_id}",
        }
        record = VerifiedAnswerRecord.model_validate(
            {**unsigned, "record_digest": _digest(unsigned)}
        )
        self.store.put(
            "verified_answers", answer_id, record.model_dump(mode="json")
        )
        self._bind_idempotency(record, idem_id)
        self._record_invocation(record, channel, cache_hit=False)
        return record

    def _bind_idempotency(
        self, record: VerifiedAnswerRecord, idem_id: str
    ) -> None:
        existing = self.store.get("verified_answer_idempotency", idem_id)
        if existing and (
            str(existing.get("answer_id") or "") != record.answer_id
            or str(existing.get("record_digest") or "") != record.record_digest
        ):
            raise AnswerApplicationError("ANSWER_IDEMPOTENCY_CONFLICT")
        if not existing:
            self.store.put(
                "verified_answer_idempotency",
                idem_id,
                {
                    "answer_id": record.answer_id,
                    "record_digest": record.record_digest,
                },
            )

    def register_prepared_execution(
        self, *, principal: str, prepared: PreparedAnswerExecution
    ) -> PreparedAnswerExecution:
        if prepared.owner_principal != principal:
            raise AnswerApplicationError("ANSWER_PREPARED_OWNER_FORBIDDEN")
        existing = self.store.get("prepared_answer_executions", prepared.input_ref)
        if existing:
            existing_payload = dict(existing)
            existing_payload.pop("updated_at", None)
            registered = PreparedAnswerExecution.model_validate(existing_payload)
            if registered.input_digest != prepared.input_digest:
                raise AnswerApplicationError("ANSWER_PREPARED_REF_CONFLICT")
            return registered
        self.store.put(
            "prepared_answer_executions",
            prepared.input_ref,
            prepared.model_dump(mode="json"),
        )
        return prepared

    def answer_question(
        self,
        *,
        principal: str,
        question: str,
        prepared_answer_ref: str,
        idempotency_key: str,
        channel: Literal["ui", "mcp", "rest"],
    ) -> VerifiedAnswerRecord:
        raw = self.store.get("prepared_answer_executions", prepared_answer_ref)
        if not raw:
            raise AnswerApplicationError("ANSWER_PREPARED_NOT_FOUND")
        payload = dict(raw)
        payload.pop("updated_at", None)
        prepared = PreparedAnswerExecution.model_validate(payload)
        if prepared.owner_principal != principal:
            raise AnswerApplicationError("ANSWER_PREPARED_OWNER_FORBIDDEN")
        if _digest(question) != prepared.requirement.question_digest:
            raise AnswerApplicationError("ANSWER_QUESTION_DIGEST_MISMATCH")
        cache = self.store.get(
            "verified_answer_result_cache", prepared.input_digest
        )
        if cache:
            if str(cache.get("owner_principal") or "") != principal:
                raise AnswerApplicationError("ANSWER_PREPARED_OWNER_FORBIDDEN")
            record = self.get(
                principal=principal, answer_id=str(cache.get("answer_id") or "")
            )
            if record.answer_semantic_digest != str(
                cache.get("answer_semantic_digest") or ""
            ):
                raise AnswerApplicationError("ANSWER_RESULT_CACHE_MISMATCH")
            self._bind_idempotency(
                record, self._idempotency_id(principal, idempotency_key)
            )
            self._record_invocation(record, channel, cache_hit=True)
            return record
        answer_id = self._answer_id(principal, prepared.run_id, idempotency_key)
        envelope = DeterministicAnswerComposer.compose(
            requirement=prepared.requirement,
            result_sets=prepared.frozen_result_sets,
            execution_classification=prepared.execution_classification,
            execution_receipt_ref=prepared.execution_receipt_ref,
            snapshot_notice=prepared.snapshot_notice,
            quality_measurements=prepared.quality_measurements,
            quality_evidence_digests=prepared.quality_evidence_digests,
            ui_url=f"/ontology/answers/{answer_id}",
            safe_mcp_reproduction_ref=f"boi_get:{answer_id}",
        )
        receipt = AnswerQualityEvaluator.evaluate(
            requirement=prepared.requirement,
            envelope=envelope,
            frozen_result_sets=prepared.frozen_result_sets,
            execution_result_digest=prepared.execution_result_digest,
            renderer_code_digest=prepared.renderer_code_digest,
            evaluator_code_digest=prepared.evaluator_code_digest,
            acl_evidence_digest=prepared.acl_evidence_digest,
            surface_answer_digests={
                surface: envelope.answer_semantic_digest
                for surface in ("ui", "mcp", "rest")
            },
        )
        record = self.publish(
            principal=principal,
            run_id=prepared.run_id,
            idempotency_key=idempotency_key,
            channel=channel,
            envelope=envelope,
            qualification_receipt=receipt,
        )
        self.store.put(
            "verified_answer_result_cache",
            prepared.input_digest,
            {
                "owner_principal": principal,
                "prepared_answer_ref": prepared.input_ref,
                "prepared_input_digest": prepared.input_digest,
                "answer_id": record.answer_id,
                "answer_semantic_digest": record.answer_semantic_digest,
                "record_digest": record.record_digest,
            },
        )
        return record

    def _record_invocation(
        self,
        record: VerifiedAnswerRecord,
        channel: Literal["ui", "mcp", "rest"],
        *,
        cache_hit: bool,
    ) -> None:
        invocation = {
            "answer_id": record.answer_id,
            "owner_principal": record.owner_principal,
            "channel": channel,
            "answer_semantic_digest": record.answer_semantic_digest,
            "record_digest": record.record_digest,
            "cache_hit": cache_hit,
        }
        invocation_id = _digest(
            {
                **invocation,
                "sequence": len(
                    [
                        item
                        for item in self.store.list(
                            "verified_answer_invocations", limit=1_000_000
                        )
                        if item.get("answer_id") == record.answer_id
                    ]
                ),
            }
        )
        self.store.put("verified_answer_invocations", invocation_id, invocation)

    def get(self, *, principal: str, answer_id: str) -> VerifiedAnswerRecord:
        raw = self.store.get("verified_answers", answer_id)
        if not raw:
            raise AnswerApplicationError("ANSWER_NOT_FOUND")
        semantic_record = dict(raw)
        semantic_record.pop("updated_at", None)
        record = VerifiedAnswerRecord.model_validate(semantic_record)
        if record.owner_principal != principal:
            raise AnswerApplicationError("ANSWER_OWNER_FORBIDDEN")
        return record


__all__ = [
    "AnswerApplicationError",
    "AnswerApplicationService",
    "PreparedAnswerExecution",
    "VerifiedAnswerQuestionRequest",
    "VerifiedAnswerRecord",
]
