"""Token-bounded Pi routing and exception-only Codex review contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re


SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class LocalModelPolicy:
    model_id: str = "ninfer-local/qwen3.8-27b"
    max_atomic_claims_per_shard: int = 4
    max_serialized_input_bytes: int = 11_264
    max_concurrency: int = 2
    max_retries: int = 1


@dataclass(frozen=True)
class LocalModelRunIdentity:
    healthy: bool
    model_id: str
    model_digest: str
    role_digest: str
    prompt_digest: str


@dataclass(frozen=True)
class PiShard:
    shard_id: str
    atomic_claims: tuple[str, ...]
    serialized_input: bytes


@dataclass(frozen=True)
class PiExecutionDecision:
    status: str
    reason_codes: tuple[str, ...]
    codex_fallback_allowed: bool = False


@dataclass(frozen=True)
class CodexReviewRequest:
    exception_id: str
    audit_sample_id: str
    evidence_spans: tuple[str, ...]
    full_document: str | None


def validate_pi_batch(
    shards: tuple[PiShard, ...],
    *,
    concurrency: int,
    retry_count: int,
    policy: LocalModelPolicy,
) -> tuple[PiShard, ...]:
    if concurrency < 1 or concurrency > policy.max_concurrency:
        raise ValueError("PI_CONCURRENCY_LIMIT")
    if retry_count < 0 or retry_count > policy.max_retries:
        raise ValueError("PI_RETRY_LIMIT")
    for shard in shards:
        if not shard.atomic_claims or len(shard.atomic_claims) > policy.max_atomic_claims_per_shard:
            raise ValueError(f"PI_SHARD_CLAIM_LIMIT:{shard.shard_id}")
        if len(shard.serialized_input) > policy.max_serialized_input_bytes:
            raise ValueError(f"PI_SHARD_BYTE_LIMIT:{shard.shard_id}")
    return shards


def decide_pi_execution(
    identity: LocalModelRunIdentity,
    policy: LocalModelPolicy,
) -> PiExecutionDecision:
    reasons: list[str] = []
    if not identity.healthy:
        reasons.append("LOCAL_MODEL_UNHEALTHY")
    if identity.model_id != policy.model_id:
        reasons.append("LOCAL_MODEL_ID_MISMATCH")
    if not SHA256_RE.fullmatch(identity.model_digest):
        reasons.append("MODEL_DIGEST_MISSING")
    if not SHA256_RE.fullmatch(identity.role_digest):
        reasons.append("ROLE_DIGEST_MISSING")
    if not SHA256_RE.fullmatch(identity.prompt_digest):
        reasons.append("PROMPT_DIGEST_MISSING")
    return PiExecutionDecision(
        status="BLOCKED" if reasons else "READY",
        reason_codes=tuple(reasons),
        codex_fallback_allowed=False,
    )


def content_addressed_cache_key(
    *,
    claim: str,
    evidence_digest: str,
    kb_revision: str,
    contract_digest: str,
    identity: LocalModelRunIdentity,
) -> str:
    payload = {
        "claim": claim,
        "evidence_digest": evidence_digest,
        "kb_revision": kb_revision,
        "contract_digest": contract_digest,
        "model_id": identity.model_id,
        "model_digest": identity.model_digest,
        "role_digest": identity.role_digest,
        "prompt_digest": identity.prompt_digest,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def codex_review_context(request: CodexReviewRequest) -> dict[str, object]:
    exception_id = request.exception_id.strip()
    audit_sample_id = request.audit_sample_id.strip()
    if bool(exception_id) == bool(audit_sample_id):
        raise ValueError("CODEX_REVIEW_ID_REQUIRED")
    if request.full_document is not None:
        raise ValueError("FULL_DOCUMENT_FORBIDDEN")
    spans = [span.strip() for span in request.evidence_spans if span.strip()]
    if not spans:
        raise ValueError("EVIDENCE_SPAN_REQUIRED")
    return {
        "review_id": exception_id or audit_sample_id,
        "review_kind": "exception" if exception_id else "audit_sample",
        "evidence_spans": spans,
    }
