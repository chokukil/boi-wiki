"""Exception-only, evidence-bounded Codex review call site.

The dispatcher is deliberately outside evaluator and Release authority.  It
stores only digests and counters in the common ledger; bounded span text is
passed to the injected reviewer once and is never persisted here.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Literal, Protocol

from .ledger import GovernedRuntimeLedger, LedgerError, RecordKind
from .local_model_routing import SHA256_RE, CodexReviewRequest, codex_review_context
from .token_routing_metrics import TokenRoutingMetrics


MAX_CODEX_EVIDENCE_BYTES = 11_264


class CodexReviewDispatchError(RuntimeError):
    """The review packet violates the bounded exception/audit contract."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


@dataclass(frozen=True)
class BoundedEvidenceSpan:
    evidence_span_id: str
    evidence_digest: str
    text: str


@dataclass(frozen=True)
class CodexReviewDispatchReceipt:
    status: str
    review_id: str
    review_kind: str
    packet_digest: str
    result_digest: str | None
    input_bytes: int
    run_id: str
    reason_code: str | None
    codex_fallback_count: int = 0
    release_authority: bool = False
    active_release_transition: bool = False
    idempotent_replay: bool = False


class BulkAttentionRun(Protocol):
    principal: str
    run_id: str
    semantic_digest: str
    attention_refs: tuple[str, ...]


@dataclass(frozen=True)
class CodexReviewAuthorization:
    source_kind: Literal["bulk_attention", "stratified_holdout"]
    principal: str
    source_id: str
    source_digest: str
    authorized_review_ids: tuple[str, ...]
    authorization_digest: str


@dataclass(frozen=True)
class StratifiedAuditCandidate:
    candidate_id: str
    candidate_digest: str
    stratum: str


@dataclass(frozen=True)
class StratifiedAuditSelection:
    candidate_id: str
    candidate_digest: str
    stratum: str
    percent: int
    audit_sample_id: str


def authorize_bulk_attention(
    run: BulkAttentionRun, *, principal: str
) -> CodexReviewAuthorization:
    if run.principal != principal or not run.attention_refs or not SHA256_RE.fullmatch(run.semantic_digest):
        raise CodexReviewDispatchError("bulk Attention authorization is invalid")
    review_ids = tuple(sorted(set(run.attention_refs)))
    values = {
        "source_kind": "bulk_attention",
        "principal": principal,
        "source_id": run.run_id,
        "source_digest": run.semantic_digest,
        "authorized_review_ids": list(review_ids),
    }
    return CodexReviewAuthorization(
        source_kind="bulk_attention",
        principal=principal,
        source_id=run.run_id,
        source_digest=run.semantic_digest,
        authorized_review_ids=review_ids,
        authorization_digest=_digest(values),
    )


def authorize_audit_holdout(
    selections: Sequence[StratifiedAuditSelection],
    *,
    principal: str,
    source_id: str,
    source_digest: str,
) -> CodexReviewAuthorization:
    if not principal.strip() or not source_id.strip() or not SHA256_RE.fullmatch(source_digest):
        raise CodexReviewDispatchError("audit holdout authorization is invalid")
    valid = all(
        item.audit_sample_id
        == "audit-sample:"
        + _digest(
            {
                "candidate_id": item.candidate_id,
                "candidate_digest": item.candidate_digest,
                "stratum": item.stratum,
                "percent": item.percent,
            }
        )
        for item in selections
    )
    review_ids = tuple(sorted({item.audit_sample_id for item in selections}))
    if not valid or not review_ids or len(review_ids) != len(selections):
        raise CodexReviewDispatchError("audit holdout authorization is invalid")
    values = {
        "source_kind": "stratified_holdout",
        "principal": principal,
        "source_id": source_id,
        "source_digest": source_digest,
        "authorized_review_ids": list(review_ids),
    }
    return CodexReviewAuthorization(
        source_kind="stratified_holdout",
        principal=principal,
        source_id=source_id,
        source_digest=source_digest,
        authorized_review_ids=review_ids,
        authorization_digest=_digest(values),
    )


def select_stratified_holdout(
    candidates: Sequence[StratifiedAuditCandidate], *, percent: int = 5
) -> tuple[StratifiedAuditSelection, ...]:
    """Select an exact deterministic percentage by hash rank within each stratum."""

    if isinstance(percent, bool) or not 1 <= percent <= 100:
        raise CodexReviewDispatchError("audit percent must be between 1 and 100")
    by_stratum: dict[str, list[StratifiedAuditCandidate]] = defaultdict(list)
    seen: set[str] = set()
    for candidate in candidates:
        if (
            not candidate.candidate_id.strip()
            or candidate.candidate_id in seen
            or not candidate.stratum.strip()
            or not SHA256_RE.fullmatch(candidate.candidate_digest)
        ):
            raise CodexReviewDispatchError("audit candidate closure is invalid")
        seen.add(candidate.candidate_id)
        by_stratum[candidate.stratum].append(candidate)
    selected: list[StratifiedAuditSelection] = []
    for stratum, group in sorted(by_stratum.items()):
        count = math.ceil(len(group) * percent / 100)
        ranked = sorted(
            group,
            key=lambda item: (
                _digest(
                    {
                        "candidate_id": item.candidate_id,
                        "candidate_digest": item.candidate_digest,
                        "stratum": item.stratum,
                        "percent": percent,
                    }
                ),
                item.candidate_id,
            ),
        )
        for item in ranked[:count]:
            sample_values = {
                "candidate_id": item.candidate_id,
                "candidate_digest": item.candidate_digest,
                "stratum": stratum,
                "percent": percent,
            }
            selected.append(
                StratifiedAuditSelection(
                    candidate_id=item.candidate_id,
                    candidate_digest=item.candidate_digest,
                    stratum=stratum,
                    percent=percent,
                    audit_sample_id="audit-sample:" + _digest(sample_values),
                )
            )
    return tuple(sorted(selected, key=lambda item: (item.stratum, item.candidate_id)))


class CodexReviewDispatcher:
    @staticmethod
    def _prior_run(
        ledger: GovernedRuntimeLedger, packet_digest: str
    ) -> CodexReviewDispatchReceipt | None:
        root = ledger.records_root / RecordKind.RUN.value
        for path in sorted(root.glob("*.json")) if root.exists() else ():
            try:
                stored = json.loads(path.read_text(encoding="utf-8"))
                record = ledger.read(str(stored["record_id"]))
            except (OSError, ValueError, KeyError, LedgerError) as error:
                raise CodexReviewDispatchError("review ledger is invalid") from error
            payload = record.payload
            if payload.get("scope") != "codex-bounded-review" or payload.get("packet_digest") != packet_digest:
                continue
            return CodexReviewDispatchReceipt(
                status=str(payload["status"]),
                review_id=str(payload["review_id"]),
                review_kind=str(payload["review_kind"]),
                packet_digest=packet_digest,
                result_digest=payload.get("result_digest"),
                input_bytes=int(payload["input_bytes"]),
                run_id=record.record_id,
                reason_code=payload.get("reason_code"),
                codex_fallback_count=0,
                release_authority=False,
                active_release_transition=False,
                idempotent_replay=True,
            )
        return None

    @classmethod
    def dispatch(
        cls,
        *,
        request: CodexReviewRequest,
        evidence_spans: Sequence[BoundedEvidenceSpan],
        authorization: CodexReviewAuthorization,
        model_digest: str,
        role_digest: str,
        prompt_digest: str,
        reviewer: Callable[[dict[str, object]], Mapping[str, Any]],
        ledger: GovernedRuntimeLedger,
        metrics: TokenRoutingMetrics,
        occurred_at: str,
    ) -> CodexReviewDispatchReceipt:
        try:
            context = codex_review_context(request)
        except ValueError as error:
            raise CodexReviewDispatchError(str(error)) from error
        review_id = str(context["review_id"])
        expected_kind = "bulk_attention" if context["review_kind"] == "exception" else "stratified_holdout"
        authorization_values = {
            "source_kind": authorization.source_kind,
            "principal": authorization.principal,
            "source_id": authorization.source_id,
            "source_digest": authorization.source_digest,
            "authorized_review_ids": list(authorization.authorized_review_ids),
        }
        if (
            authorization.source_kind != expected_kind
            or not SHA256_RE.fullmatch(authorization.source_digest)
            or authorization.authorization_digest != _digest(authorization_values)
            or review_id not in authorization.authorized_review_ids
        ):
            raise CodexReviewDispatchError("review ID is not authorized by Attention or holdout selection")
        for value in (model_digest, role_digest, prompt_digest):
            if not SHA256_RE.fullmatch(value):
                raise CodexReviewDispatchError("model role and prompt digests are required")
        expected_ids = tuple(str(item) for item in context["evidence_spans"])
        observed_ids = tuple(item.evidence_span_id.strip() for item in evidence_spans)
        if not observed_ids or observed_ids != expected_ids or len(observed_ids) != len(set(observed_ids)):
            raise CodexReviewDispatchError("evidence span closure does not match request")
        materials: list[dict[str, str]] = []
        total_bytes = 0
        for span in evidence_spans:
            if not SHA256_RE.fullmatch(span.evidence_digest) or not span.text.strip():
                raise CodexReviewDispatchError("evidence span closure is invalid")
            encoded = span.text.encode("utf-8")
            total_bytes += len(encoded)
            materials.append(
                {
                    "evidence_span_id": span.evidence_span_id,
                    "evidence_digest": span.evidence_digest,
                    "text": span.text,
                }
            )
        if total_bytes > MAX_CODEX_EVIDENCE_BYTES:
            raise CodexReviewDispatchError("Codex evidence byte limit exceeded")
        packet_values = {
            "review_id": context["review_id"],
            "review_kind": context["review_kind"],
            "evidence_spans": [
                {
                    "evidence_span_id": item["evidence_span_id"],
                    "evidence_digest": item["evidence_digest"],
                    "text_digest": "sha256:"
                    + hashlib.sha256(item["text"].encode("utf-8")).hexdigest(),
                }
                for item in materials
            ],
            "model_digest": model_digest,
            "role_digest": role_digest,
            "prompt_digest": prompt_digest,
            "input_bytes": total_bytes,
            "authorization_digest": authorization.authorization_digest,
        }
        packet_digest = _digest(packet_values)
        prior = cls._prior_run(ledger, packet_digest)
        if prior is not None:
            return prior

        metrics.prepare_codex_review(request)
        model_packet = {
            "review_id": context["review_id"],
            "review_kind": context["review_kind"],
            "evidence_spans": materials,
        }
        status = "COMPLETED"
        reason_code = None
        result_digest = None
        try:
            result = reviewer(model_packet)
            if not isinstance(result, Mapping):
                raise ValueError("reviewer output must be structured")
            result_digest = _digest(dict(result))
        except Exception:  # noqa: BLE001 - failure becomes a fail-closed receipt
            status = "BLOCKED"
            reason_code = "CODEX_REVIEW_FAILED"
        record = ledger.append(
            RecordKind.RUN,
            {
                "scope": "codex-bounded-review",
                "status": status,
                "review_id": context["review_id"],
                "review_kind": context["review_kind"],
                "packet_digest": packet_digest,
                "evidence_span_ids": list(observed_ids),
                "evidence_digests": [item.evidence_digest for item in evidence_spans],
                "model_digest": model_digest,
                "role_digest": role_digest,
                "prompt_digest": prompt_digest,
                "input_bytes": total_bytes,
                "authorization_digest": authorization.authorization_digest,
                "result_digest": result_digest,
                "reason_code": reason_code,
                "codex_fallback_count": 0,
                "release_authority": False,
                "active_release_transition": False,
            },
            authority="executor",
            occurred_at=occurred_at,
        )
        return CodexReviewDispatchReceipt(
            status=status,
            review_id=str(context["review_id"]),
            review_kind=str(context["review_kind"]),
            packet_digest=packet_digest,
            result_digest=result_digest,
            input_bytes=total_bytes,
            run_id=record.record_id,
            reason_code=reason_code,
        )


__all__ = [
    "BoundedEvidenceSpan",
    "CodexReviewAuthorization",
    "CodexReviewDispatcher",
    "CodexReviewDispatchError",
    "CodexReviewDispatchReceipt",
    "MAX_CODEX_EVIDENCE_BYTES",
    "StratifiedAuditCandidate",
    "StratifiedAuditSelection",
    "authorize_audit_holdout",
    "authorize_bulk_attention",
    "select_stratified_holdout",
]
