"""Bounded local-Pi worker for candidate-only ontology migration skills."""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Awaitable, Callable, Literal
from urllib import request

from .local_model_routing import (
    LocalModelPolicy,
    LocalModelRunIdentity,
    PiShard,
    decide_pi_execution,
    validate_pi_batch,
)
from .ontology_migration_skills import (
    MigrationSkillContract,
    ontology_migration_skill_registry,
)
from .token_routing_metrics import TokenRoutingMetrics


PiMigrationStatus = Literal["READY", "BLOCKED", "REJECTED"]
PiMigrationInvoker = Callable[
    [MigrationSkillContract, PiShard], Awaitable[dict[str, object]]
]
JsonTransport = Callable[[str, str, dict[str, Any] | None, float], dict[str, Any]]

_FORBIDDEN_MODEL_OUTPUT_KEYS = frozenset(
    {
        "sql",
        "raw_sql",
        "repaired_sql",
        "compiled_sql",
        "executed_sql",
        "credential",
        "credentials",
        "password",
        "secret",
        "token",
        "verdict",
        "approved",
        "released",
        "active_release",
    }
)


def _digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class PiMigrationOutputError(ValueError):
    """Raised when a model response violates the closed candidate schema."""


def _default_transport(
    method: str,
    url: str,
    payload: dict[str, Any] | None,
    timeout: float,
) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode()
    call = request.Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(call, timeout=timeout) as response:  # noqa: S310
        decoded = json.loads(response.read().decode())
    if not isinstance(decoded, dict):
        raise ValueError("LOCAL_MODEL_RESPONSE_NOT_OBJECT")
    return decoded


def _validate_output_value(value: object, *, path: str) -> None:
    if isinstance(value, dict):
        for raw_key, child in value.items():
            key = str(raw_key).strip()
            if not key or key.lower() in _FORBIDDEN_MODEL_OUTPUT_KEYS:
                raise PiMigrationOutputError(f"PI_OUTPUT_FORBIDDEN_FIELD:{path}.{key}")
            _validate_output_value(child, path=f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_output_value(child, path=f"{path}[{index}]")
        return
    if isinstance(value, (str, int, float, bool)) or value is None:
        return
    raise PiMigrationOutputError(f"PI_OUTPUT_VALUE_INVALID:{path}")


def _nonempty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_evidence_refs(value: object) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(_nonempty_string(item) for item in value)
    )


def _validate_domain_candidates(value: object) -> None:
    if not isinstance(value, list):
        raise PiMigrationOutputError("PI_DOMAIN_CANDIDATE_SCHEMA_INVALID")
    required = {
        "candidate_id",
        "kind",
        "name",
        "definition",
        "evidence_span_refs",
    }
    kinds = {"Term", "ObjectType", "PropertyDefinition", "Rule", "Metric"}
    for candidate in value:
        if (
            not isinstance(candidate, dict)
            or set(candidate) != required
            or not _nonempty_string(candidate.get("candidate_id"))
            or candidate.get("kind") not in kinds
            or not _nonempty_string(candidate.get("name"))
            or not _nonempty_string(candidate.get("definition"))
            or not _valid_evidence_refs(candidate.get("evidence_span_refs"))
        ):
            raise PiMigrationOutputError("PI_DOMAIN_CANDIDATE_SCHEMA_INVALID")


def _validate_match_candidates(value: object) -> None:
    if not isinstance(value, list):
        raise PiMigrationOutputError("PI_MATCH_CANDIDATE_SCHEMA_INVALID")
    required = {
        "candidate_id",
        "decision",
        "existing_concept_id",
        "explanation",
        "evidence_span_refs",
    }
    decisions = {"reuse", "evidence_addition", "extend", "new"}
    for candidate in value:
        existing_id = (
            candidate.get("existing_concept_id")
            if isinstance(candidate, dict)
            else None
        )
        if (
            not isinstance(candidate, dict)
            or set(candidate) != required
            or not _nonempty_string(candidate.get("candidate_id"))
            or candidate.get("decision") not in decisions
            or (existing_id is not None and not _nonempty_string(existing_id))
            or not _nonempty_string(candidate.get("explanation"))
            or not _valid_evidence_refs(candidate.get("evidence_span_refs"))
        ):
            raise PiMigrationOutputError("PI_MATCH_CANDIDATE_SCHEMA_INVALID")


def _validate_string_list(value: object, *, code: str) -> None:
    if not isinstance(value, list) or not all(_nonempty_string(item) for item in value):
        raise PiMigrationOutputError(code)


def _normalize_output(
    *, skill: MigrationSkillContract, output: dict[str, object]
) -> dict[str, object]:
    if not isinstance(output, dict):
        raise PiMigrationOutputError("PI_OUTPUT_OBJECT_REQUIRED")
    expected = set(skill.outputs)
    if set(output) != expected:
        raise PiMigrationOutputError("PI_OUTPUT_SCHEMA_MISMATCH")
    normalized: dict[str, object] = {}
    for key in skill.outputs:
        value = output[key]
        if not isinstance(value, list):
            raise PiMigrationOutputError(f"PI_OUTPUT_LIST_REQUIRED:{key}")
        _validate_output_value(value, path=key)
        normalized[key] = value
    if skill.skill_id == "domain-ontology-draft":
        _validate_domain_candidates(normalized["domain_candidates"])
        _validate_string_list(
            normalized["uncertainties"], code="PI_UNCERTAINTY_SCHEMA_INVALID"
        )
    elif skill.skill_id == "existing-concept-match":
        _validate_match_candidates(normalized["match_candidates"])
        _validate_string_list(
            normalized["duplicate_risks"], code="PI_DUPLICATE_RISK_SCHEMA_INVALID"
        )
    return normalized


class NinferMigrationShardClient:
    """NInfer tool-call client for candidate-only migration shard outputs."""

    ROLE = (
        "You draft candidate-only ontology semantics from bounded evidence spans. "
        "When one evidence span describes one physical table, propose exactly one "
        "sparse ObjectType for the real-world entity, event, or observation; do not "
        "copy the physical table name and do not expand properties in this step. "
        "Use only the supplied claims and evidence. Never emit SQL, credentials, "
        "approval, verdict, Release, or execution instructions. Uncertainty stays "
        "explicit and every candidate cites an evidence span reference."
    )
    PROMPT_CONTRACT = (
        "For domain-ontology-draft return only domain_candidates and uncertainties. "
        "For existing-concept-match return only match_candidates and duplicate_risks. "
        "Do not infer a match when evidence is insufficient. Submit exactly one "
        "closed tool object."
    )

    _DOMAIN_CANDIDATE_SCHEMA: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "candidate_id": {"type": "string"},
            "kind": {
                "type": "string",
                "enum": ["Term", "ObjectType", "PropertyDefinition", "Rule", "Metric"],
            },
            "name": {"type": "string"},
            "definition": {"type": "string"},
            "evidence_span_refs": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": [
            "candidate_id",
            "kind",
            "name",
            "definition",
            "evidence_span_refs",
        ],
    }
    _MATCH_CANDIDATE_SCHEMA: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "candidate_id": {"type": "string"},
            "decision": {
                "type": "string",
                "enum": ["reuse", "evidence_addition", "extend", "new"],
            },
            "existing_concept_id": {"type": ["string", "null"]},
            "explanation": {"type": "string"},
            "evidence_span_refs": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
            },
        },
        "required": [
            "candidate_id",
            "decision",
            "existing_concept_id",
            "explanation",
            "evidence_span_refs",
        ],
    }

    def __init__(
        self,
        *,
        base_url: str,
        model_id: str,
        model_digest: str,
        timeout_seconds: float = 60.0,
        transport: JsonTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.model_digest = model_digest
        self.timeout_seconds = timeout_seconds
        self.transport = transport or _default_transport

    def probe_identity(self) -> LocalModelRunIdentity:
        healthy = False
        try:
            response = self.transport(
                "GET", f"{self.base_url}/models", None, self.timeout_seconds
            )
            data = response.get("data")
            healthy = isinstance(data, list) and any(
                isinstance(item, dict) and item.get("id") == self.model_id
                for item in data
            )
        except Exception:
            healthy = False
        return LocalModelRunIdentity(
            healthy=healthy,
            model_id=f"ninfer-local/{self.model_id}",
            model_digest=self.model_digest,
            role_digest=_digest(self.ROLE),
            prompt_digest=_digest(self.PROMPT_CONTRACT),
        )

    @classmethod
    def _schema_for(
        cls,
        skill: MigrationSkillContract,
        *,
        sparse_object_only: bool = False,
    ) -> dict[str, Any]:
        if skill.skill_id == "domain-ontology-draft":
            candidate_schema = json.loads(json.dumps(cls._DOMAIN_CANDIDATE_SCHEMA))
            if sparse_object_only:
                candidate_schema["properties"]["kind"]["enum"] = ["ObjectType"]
            properties = {
                "domain_candidates": {
                    "type": "array",
                    "items": candidate_schema,
                    **(
                        {"minItems": 1, "maxItems": 1}
                        if sparse_object_only
                        else {}
                    ),
                },
                "uncertainties": {"type": "array", "items": {"type": "string"}},
            }
        elif skill.skill_id == "existing-concept-match":
            properties = {
                "match_candidates": {
                    "type": "array",
                    "items": cls._MATCH_CANDIDATE_SCHEMA,
                },
                "duplicate_risks": {"type": "array", "items": {"type": "string"}},
            }
        else:
            raise ValueError("PI_SKILL_NOT_MODEL_ENABLED")
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
            "required": list(skill.outputs),
        }

    async def __call__(
        self,
        skill: MigrationSkillContract,
        shard: PiShard,
    ) -> dict[str, object]:
        if not skill.local_model_allowed:
            raise ValueError("PI_SKILL_NOT_MODEL_ENABLED")
        try:
            evidence_input = shard.serialized_input.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("PI_SERIALIZED_INPUT_UTF8_REQUIRED") from error
        try:
            bounded_payload = json.loads(evidence_input)
        except json.JSONDecodeError as error:
            raise ValueError("PI_SERIALIZED_INPUT_JSON_REQUIRED") from error
        domain_context = (
            bounded_payload.get("domain_context")
            if isinstance(bounded_payload, dict)
            else None
        )
        sparse_object_only = bool(
            isinstance(domain_context, dict)
            and domain_context.get("candidate_scope")
            == "sparse_object_type_per_evidence_span"
        )
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": f"{self.ROLE}\n\n{self.PROMPT_CONTRACT}"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "skill_id": skill.skill_id,
                            "atomic_claims": list(shard.atomic_claims),
                            "bounded_evidence": evidence_input,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ],
            "reasoning_effort": "low",
            "max_tokens": 2048,
            "temperature": 0,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "submit_migration_candidates",
                        "description": "Submit bounded candidate-only ontology output.",
                        "parameters": self._schema_for(
                            skill,
                            sparse_object_only=sparse_object_only,
                        ),
                    },
                }
            ],
            "tool_choice": "required",
        }
        response = await asyncio.to_thread(
            self.transport,
            "POST",
            f"{self.base_url}/chat/completions",
            payload,
            self.timeout_seconds,
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1:
            raise PiMigrationOutputError("PI_MODEL_SINGLE_CHOICE_REQUIRED")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        calls = message.get("tool_calls") if isinstance(message, dict) else None
        if not isinstance(calls, list) or len(calls) != 1:
            raise PiMigrationOutputError("PI_MODEL_TOOL_CALL_REQUIRED")
        function = calls[0].get("function") if isinstance(calls[0], dict) else None
        if (
            not isinstance(function, dict)
            or function.get("name") != "submit_migration_candidates"
        ):
            raise PiMigrationOutputError("PI_MODEL_TOOL_CALL_REQUIRED")
        arguments = function.get("arguments")
        if not isinstance(arguments, str):
            raise PiMigrationOutputError("PI_MODEL_TOOL_ARGUMENTS_INVALID")
        try:
            decoded = json.loads(arguments)
        except json.JSONDecodeError as error:
            raise PiMigrationOutputError("PI_MODEL_TOOL_ARGUMENTS_INVALID") from error
        if not isinstance(decoded, dict):
            raise PiMigrationOutputError("PI_MODEL_TOOL_ARGUMENTS_INVALID")
        return _normalize_output(skill=skill, output=decoded)


@dataclass(frozen=True)
class PiMigrationShardResult:
    shard_id: str
    status: PiMigrationStatus
    attempts: int
    reason_codes: tuple[str, ...]
    output_digest: str
    output: dict[str, object] | None

    def receipt(self) -> dict[str, object]:
        return {
            "shard_id": self.shard_id,
            "status": self.status,
            "attempts": self.attempts,
            "reason_codes": list(self.reason_codes),
            "output_digest": self.output_digest,
        }


@dataclass(frozen=True)
class PiMigrationBatchResult:
    skill_id: str
    results: tuple[PiMigrationShardResult, ...]
    identity_digest: str
    metrics_digest: str
    batch_receipt_digest: str
    codex_fallback_allowed: bool = False
    release_authority: bool = False
    active_release_transition: bool = False

    def receipt(self) -> dict[str, object]:
        return {
            "schema": "boi-ontology-migration-pi-batch-receipt/v1",
            "skill_id": self.skill_id,
            "results": [item.receipt() for item in self.results],
            "identity_digest": self.identity_digest,
            "metrics_digest": self.metrics_digest,
            "batch_receipt_digest": self.batch_receipt_digest,
            "codex_fallback_allowed": self.codex_fallback_allowed,
            "release_authority": self.release_authority,
            "active_release_transition": self.active_release_transition,
        }

    def receipt_json(self) -> str:
        return json.dumps(
            self.receipt(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )


class OntologyMigrationPiWorker:
    """Execute only model-enabled migration shards under deterministic limits."""

    MAX_BATCH_OBJECTS = 100

    def __init__(
        self,
        *,
        identity: LocalModelRunIdentity,
        policy: LocalModelPolicy,
        metrics: TokenRoutingMetrics,
    ) -> None:
        self.identity = identity
        self.policy = policy
        self.metrics = metrics

    async def run(
        self,
        *,
        skill_id: str,
        shards: tuple[PiShard, ...],
        invoke: PiMigrationInvoker,
        concurrency: int,
        retry_count: int,
    ) -> PiMigrationBatchResult:
        skill = ontology_migration_skill_registry().get(skill_id)
        if skill is None or not skill.local_model_allowed:
            raise ValueError("PI_SKILL_NOT_MODEL_ENABLED")
        object_count = sum(len(shard.atomic_claims) for shard in shards)
        if object_count > self.MAX_BATCH_OBJECTS:
            raise ValueError("MIGRATION_BATCH_OBJECT_LIMIT")
        validate_pi_batch(
            shards,
            concurrency=concurrency,
            retry_count=retry_count,
            policy=self.policy,
        )
        self.metrics.record_deterministic(items=object_count)

        identity_values = asdict(self.identity)
        identity_digest = _digest(identity_values)
        decision = decide_pi_execution(self.identity, self.policy)
        if decision.status == "BLOCKED":
            results = tuple(
                PiMigrationShardResult(
                    shard_id=shard.shard_id,
                    status="BLOCKED",
                    attempts=0,
                    reason_codes=decision.reason_codes,
                    output_digest="",
                    output=None,
                )
                for shard in shards
            )
            for shard in shards:
                self.metrics.record_pi(
                    input_bytes=len(shard.serialized_input), status="BLOCKED"
                )
            return self._batch_result(
                skill_id=skill_id,
                results=results,
                identity_digest=identity_digest,
            )

        semaphore = asyncio.Semaphore(concurrency)

        async def execute(shard: PiShard) -> PiMigrationShardResult:
            invalid_output = False
            for attempt in range(1, retry_count + 2):
                try:
                    async with semaphore:
                        output = await invoke(skill, shard)
                    normalized = _normalize_output(skill=skill, output=output)
                except PiMigrationOutputError:
                    invalid_output = True
                except Exception:
                    invalid_output = False
                else:
                    self.metrics.record_pi(
                        input_bytes=len(shard.serialized_input), status="READY"
                    )
                    return PiMigrationShardResult(
                        shard_id=shard.shard_id,
                        status="READY",
                        attempts=attempt,
                        reason_codes=(),
                        output_digest=_digest(normalized),
                        output=normalized,
                    )
            status: PiMigrationStatus = "REJECTED" if invalid_output else "BLOCKED"
            reason = (
                "LOCAL_MODEL_OUTPUT_INVALID"
                if invalid_output
                else "LOCAL_MODEL_EXECUTION_FAILED"
            )
            self.metrics.record_pi(
                input_bytes=len(shard.serialized_input), status=status
            )
            return PiMigrationShardResult(
                shard_id=shard.shard_id,
                status=status,
                attempts=retry_count + 1,
                reason_codes=(reason,),
                output_digest="",
                output=None,
            )

        results = tuple(await asyncio.gather(*(execute(shard) for shard in shards)))
        return self._batch_result(
            skill_id=skill_id,
            results=results,
            identity_digest=identity_digest,
        )

    def _batch_result(
        self,
        *,
        skill_id: str,
        results: tuple[PiMigrationShardResult, ...],
        identity_digest: str,
    ) -> PiMigrationBatchResult:
        metrics_digest = self.metrics.snapshot().metrics_digest
        receipt_values = {
            "schema": "boi-ontology-migration-pi-batch-receipt/v1",
            "skill_id": skill_id,
            "results": [item.receipt() for item in results],
            "identity_digest": identity_digest,
            "metrics_digest": metrics_digest,
            "codex_fallback_allowed": False,
            "release_authority": False,
            "active_release_transition": False,
        }
        return PiMigrationBatchResult(
            skill_id=skill_id,
            results=results,
            identity_digest=identity_digest,
            metrics_digest=metrics_digest,
            batch_receipt_digest=_digest(receipt_values),
        )


class NinferBulkMigrationPiRunner:
    """Synchronous adapter from the shared pipeline to the bounded Pi worker.

    Each invocation is one already-bounded unresolved shard.  It performs one
    frozen inference, never retries, and exposes no Codex or static fallback.
    """

    def __init__(
        self,
        *,
        client: NinferMigrationShardClient,
        policy: LocalModelPolicy | None = None,
        metrics: TokenRoutingMetrics | None = None,
    ) -> None:
        self.client = client
        self.policy = policy or LocalModelPolicy()
        self.metrics = metrics or TokenRoutingMetrics()
        self.identity = client.probe_identity()

    def __call__(
        self,
        skill_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:
        evidence = payload.get("evidence_spans") or ()
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("PI_EVIDENCE_SPAN_REQUIRED")
        atomic_claims = tuple(
            str(item.get("evidence_span_ref") or "")
            for item in evidence
            if isinstance(item, dict) and str(item.get("evidence_span_ref") or "")
        )
        if not atomic_claims:
            raise ValueError("PI_ATOMIC_CLAIM_REQUIRED")
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        shard = PiShard(
            shard_id="pi-shard:" + _digest(
                {
                    "skill_id": skill_id,
                    "atomic_claims": list(atomic_claims),
                    "payload_digest": _digest(payload),
                }
            ).split(":", 1)[1][:24],
            atomic_claims=atomic_claims,
            serialized_input=serialized,
        )
        worker = OntologyMigrationPiWorker(
            identity=self.identity,
            policy=self.policy,
            metrics=self.metrics,
        )
        batch = asyncio.run(
            worker.run(
                skill_id=skill_id,
                shards=(shard,),
                invoke=self.client,
                concurrency=1,
                retry_count=0,
            )
        )
        result = batch.results[0]
        if result.status != "READY" or result.output is None:
            raise RuntimeError(
                "LOCAL_MODEL_EXECUTION_FAILED:"
                + ",".join(result.reason_codes or (result.status,))
            )
        return result.output
