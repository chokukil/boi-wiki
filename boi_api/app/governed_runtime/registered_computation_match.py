"""Exact semantic gate for registered or attested computations.

Natural-language family routing may identify candidates for inspection, but it
cannot authorize a registered computation.  This module compares the complete
question-local semantic closure fixed before execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .answer_contract_v2 import AnswerGoalContract


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _is_digest(value: str) -> bool:
    return (
        len(value) == 71
        and value.startswith("sha256:")
        and all(character in "0123456789abcdef" for character in value[7:])
    )


def answer_goal_semantic_closure(
    goal: AnswerGoalContract, *, result_shape: str
) -> dict[str, Any]:
    """Exclude wording and parameter values, preserve every execution semantic."""

    payload = goal.model_dump(mode="json")
    payload.pop("schema_name", None)
    payload.pop("question_digest", None)
    payload["typed_parameters"] = [
        {
            "parameter_ref": item.parameter_ref,
            "value_type": item.value_type,
            "unit": item.unit,
        }
        for item in goal.typed_parameters
    ]
    payload["result_shape"] = result_shape
    return payload


class RegisteredParameterContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    value_type: Literal["string", "integer", "number", "boolean", "date", "datetime"]
    required: bool = True

    @field_validator("name")
    @classmethod
    def require_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("REGISTERED_PARAMETER_NAME_REQUIRED")
        return value


class RegisteredComputationSemanticContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-registered-computation-semantic-contract/v1"] = (
        "boi-registered-computation-semantic-contract/v1"
    )
    query_spec_id: str
    logical_plan_digest: str
    result_shape: Literal[
        "ObjectSet",
        "LinkedObjectSet",
        "NestedCollection",
        "Aggregate",
        "FlatRelation",
        "AttestedComputation",
    ]
    semantic_closure: dict[str, Any]
    semantic_closure_digest: str
    parameter_contracts: tuple[RegisteredParameterContract, ...]
    contract_digest: str

    @classmethod
    def create(
        cls,
        *,
        query_spec_id: str,
        logical_plan_digest: str,
        result_shape: str,
        answer_goal: AnswerGoalContract,
        parameter_contracts: Sequence[RegisteredParameterContract],
    ) -> "RegisteredComputationSemanticContract":
        closure = answer_goal_semantic_closure(
            answer_goal, result_shape=result_shape
        )
        base = {
            "schema_name": "boi-registered-computation-semantic-contract/v1",
            "query_spec_id": query_spec_id,
            "logical_plan_digest": logical_plan_digest,
            "result_shape": result_shape,
            "semantic_closure": closure,
            "semantic_closure_digest": _digest(closure),
            "parameter_contracts": [
                item.model_dump(mode="json") for item in parameter_contracts
            ],
        }
        return cls.model_validate({**base, "contract_digest": _digest(base)})

    @model_validator(mode="after")
    def validate_contract(self) -> "RegisteredComputationSemanticContract":
        if not self.query_spec_id.strip():
            raise ValueError("REGISTERED_QUERY_SPEC_ID_REQUIRED")
        if not all(
            _is_digest(value)
            for value in (
                self.logical_plan_digest,
                self.semantic_closure_digest,
                self.contract_digest,
            )
        ):
            raise ValueError("REGISTERED_COMPUTATION_DIGEST_INVALID")
        if self.semantic_closure.get("result_shape") != self.result_shape:
            raise ValueError("REGISTERED_RESULT_SHAPE_CLOSURE_MISMATCH")
        if self.semantic_closure_digest != _digest(self.semantic_closure):
            raise ValueError("REGISTERED_SEMANTIC_CLOSURE_DIGEST_MISMATCH")
        names = tuple(item.name for item in self.parameter_contracts)
        if len(names) != len(set(names)):
            raise ValueError("REGISTERED_PARAMETER_DUPLICATE")
        unsigned = self.model_dump(mode="json", exclude={"contract_digest"})
        if self.contract_digest != _digest(unsigned):
            raise ValueError("REGISTERED_COMPUTATION_CONTRACT_DIGEST_MISMATCH")
        return self


class RegisteredComputationMatchReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-registered-computation-match-receipt/v1"] = (
        "boi-registered-computation-match-receipt/v1"
    )
    query_spec_id: str
    status: Literal["EXACT_MATCH", "NO_MATCH"]
    reason_codes: tuple[str, ...]
    contract_digest: str
    observed_semantic_closure_digest: str
    observed_parameter_digest: str
    runtime_binding_digest: str
    receipt_digest: str

    @model_validator(mode="after")
    def validate_receipt(self) -> "RegisteredComputationMatchReceipt":
        if not all(
            _is_digest(value)
            for value in (
                self.contract_digest,
                self.observed_semantic_closure_digest,
                self.observed_parameter_digest,
                self.runtime_binding_digest,
                self.receipt_digest,
            )
        ):
            raise ValueError("REGISTERED_MATCH_RECEIPT_DIGEST_INVALID")
        if self.status == "EXACT_MATCH" and self.reason_codes:
            raise ValueError("REGISTERED_EXACT_MATCH_REASON_FORBIDDEN")
        if self.status == "NO_MATCH" and not self.reason_codes:
            raise ValueError("REGISTERED_NO_MATCH_REASON_REQUIRED")
        unsigned = self.model_dump(mode="json", exclude={"receipt_digest"})
        if self.receipt_digest != _digest(unsigned):
            raise ValueError("REGISTERED_MATCH_RECEIPT_DIGEST_MISMATCH")
        return self


def _value_matches(value: Any, value_type: str) -> bool:
    if value_type == "string":
        return isinstance(value, str)
    if value_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if value_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if value_type == "boolean":
        return isinstance(value, bool)
    if value_type in {"date", "datetime"}:
        return isinstance(value, str) and bool(value.strip())
    return False


def match_registered_computation(
    *,
    contract: RegisteredComputationSemanticContract,
    answer_goal: AnswerGoalContract,
    result_shape: str,
    parameters: Mapping[str, Any],
    logical_plan_digest: str,
    active_release_digest: str,
    profile_closure_digest: str,
    acl_policy_digest: str,
    logical_parameter_contracts: Sequence[RegisteredParameterContract] | None = None,
) -> RegisteredComputationMatchReceipt:
    closure = answer_goal_semantic_closure(answer_goal, result_shape=result_shape)
    reasons: list[str] = []
    if logical_plan_digest != contract.logical_plan_digest:
        reasons.append("REGISTERED_LOGICAL_PLAN_MISMATCH")
    if (
        logical_parameter_contracts is not None
        and tuple(logical_parameter_contracts) != contract.parameter_contracts
    ):
        reasons.append("REGISTERED_DECLARED_PARAMETER_SCHEMA_MISMATCH")
    if _digest(closure) != contract.semantic_closure_digest:
        reasons.append("REGISTERED_SEMANTIC_CLOSURE_MISMATCH")
    runtime_binding = {
        "active_release_digest": active_release_digest,
        "profile_closure_digest": profile_closure_digest,
        "acl_policy_digest": acl_policy_digest,
    }
    if any(not _is_digest(value) for value in runtime_binding.values()):
        reasons.append("REGISTERED_RUNTIME_BINDING_MISSING")
    elif any(
        closure.get(key) != value for key, value in runtime_binding.items()
    ):
        reasons.append("REGISTERED_RUNTIME_BINDING_MISMATCH")
    required = {item.name for item in contract.parameter_contracts if item.required}
    all_names = {item.name for item in contract.parameter_contracts}
    if not required <= set(parameters) or not set(parameters) <= all_names:
        reasons.append("REGISTERED_PARAMETER_CLOSURE_MISMATCH")
    by_name = {item.name: item for item in contract.parameter_contracts}
    if any(
        name in by_name and not _value_matches(value, by_name[name].value_type)
        for name, value in parameters.items()
    ):
        reasons.append("REGISTERED_PARAMETER_TYPE_MISMATCH")
    goal_parameters = {
        item.parameter_ref.rsplit(":", 1)[-1]: item.value
        for item in answer_goal.typed_parameters
    }
    if goal_parameters != dict(parameters):
        reasons.append("REGISTERED_PARAMETER_VALUE_MISMATCH")
    base = {
        "schema_name": "boi-registered-computation-match-receipt/v1",
        "query_spec_id": contract.query_spec_id,
        "status": "NO_MATCH" if reasons else "EXACT_MATCH",
        "reason_codes": list(dict.fromkeys(reasons)),
        "contract_digest": contract.contract_digest,
        "observed_semantic_closure_digest": _digest(closure),
        "observed_parameter_digest": _digest(dict(parameters)),
        "runtime_binding_digest": _digest(runtime_binding),
    }
    return RegisteredComputationMatchReceipt.model_validate(
        {**base, "receipt_digest": _digest(base)}
    )


__all__ = [
    "RegisteredComputationMatchReceipt",
    "RegisteredComputationSemanticContract",
    "RegisteredParameterContract",
    "answer_goal_semantic_closure",
    "match_registered_computation",
]
