from __future__ import annotations

import json
import uuid
from typing import Any

from .model_gateway import ModelGateway
from .models import GroundedClaim, Principal
from .store import AgentV2Store, now_iso


class IndependentArtifactEvaluator:
    """Reviews a draft in a fresh context; deterministic Harnesses remain authoritative."""

    def __init__(self, store: AgentV2Store, model: ModelGateway, *, enabled: bool = True):
        self.store = store
        self.model = model
        self.enabled = enabled

    def evaluate(
        self,
        principal: Principal,
        *,
        artifact_kind: str,
        goal: str,
        artifact: dict[str, Any],
        evidence: list[dict[str, Any]],
        rubric: list[str],
        work_run_id: str = "",
        require_evidence_refs: bool = False,
    ) -> dict[str, Any]:
        evaluation_id = f"evaluation_{uuid.uuid4().hex}"
        available_refs = {
            str(item.get("evidence_id") or item.get("source_ref") or "")
            for item in evidence
            if isinstance(item, dict)
        }
        base = {
            "evaluation_id": evaluation_id,
            "employee_id": principal.employee_id,
            "work_run_id": work_run_id,
            "artifact_kind": artifact_kind,
            "review_context": "fresh",
            "authoritative_for_completion": False,
            "evidence_reference_required": require_evidence_refs,
            "created_at": now_iso(),
        }
        if not self.enabled or not self.model.readiness().get("generation"):
            row = {
                **base,
                "status": "unavailable",
                "summary": "독립 검토 모델을 사용할 수 없어 코드 Harness 검증만 적용했습니다.",
                "criteria": [],
                "findings": [],
            }
            return self.store.put("evaluations", evaluation_id, row)

        schema = {
            "type": "object",
            "required": ["status", "summary", "criteria", "findings"],
            "properties": {
                "status": {"type": "string", "enum": ["pass", "needs_revision"]},
                "summary": {"type": "string"},
                "criteria": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["criterion", "status", "evidence_refs"],
                        "properties": {
                            "criterion": {"type": "string"},
                            "status": {"type": "string", "enum": ["pass", "warning", "fail"]},
                            "evidence_refs": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "findings": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["severity", "message", "evidence_refs"],
                        "properties": {
                            "severity": {"type": "string", "enum": ["warning", "blocking"]},
                            "message": {"type": "string"},
                            "evidence_refs": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
            },
        }
        review_payload = {
            "goal": goal,
            "artifact_kind": artifact_kind,
            "rubric": rubric,
            "artifact": artifact,
            "evidence": evidence,
        }
        try:
            generated = self.model.generate_structured(
                system=(
                    "You are an independent BoI Wiki quality reviewer with no access to the authoring conversation. "
                    "Review only the supplied artifact, rubric, and evidence ledger. Do not infer missing evidence, "
                    "do not expose chain-of-thought, and do not claim that production was changed. Return concise "
                    "Korean findings. A qualitative review can request revision but can never complete an Autopilot "
                    "Task or override deterministic Harness, RBAC, or human confirmation."
                    " When evidence references are required, use the exact full evidence_id values supplied in the ledger."
                ),
                prompt=json.dumps(review_payload, ensure_ascii=False, default=str),
                schema=schema,
            )
            missing = [key for key in schema["required"] if key not in generated]
            if missing:
                raise ValueError("review output is missing: " + ", ".join(missing))
            status = str(generated.get("status") or "needs_revision")
            if status not in {"pass", "needs_revision"}:
                status = "needs_revision"

            def clean_refs(value: Any) -> list[str]:
                return [str(item) for item in value or [] if str(item) in available_refs]

            criteria = []
            for item in generated.get("criteria") or []:
                if not isinstance(item, dict):
                    continue
                criteria.append(
                    {
                        "criterion": str(item.get("criterion") or ""),
                        "status": str(item.get("status") or "warning"),
                        "evidence_refs": clean_refs(item.get("evidence_refs")),
                    }
                )
            findings = []
            for item in generated.get("findings") or []:
                if not isinstance(item, dict):
                    continue
                findings.append(
                    {
                        "severity": str(item.get("severity") or "warning"),
                        "message": str(item.get("message") or ""),
                        "evidence_refs": clean_refs(item.get("evidence_refs")),
                    }
                )
            cited_refs = {
                ref
                for item in [*criteria, *findings]
                for ref in item.get("evidence_refs") or []
            }
            if require_evidence_refs and (not available_refs or not cited_refs):
                status = "needs_revision"
                findings.append(
                    {
                        "severity": "blocking",
                        "message": (
                            "독립 검토가 제공된 Evidence Ledger의 실제 근거 ID를 인용하지 못했습니다."
                            if available_refs
                            else "독립 검토에 사용할 Evidence Ledger가 비어 있습니다."
                        ),
                        "evidence_refs": [],
                    }
                )
            row = {
                **base,
                "status": status,
                "summary": str(generated.get("summary") or ""),
                "criteria": criteria,
                "findings": findings,
            }
        except Exception as exc:
            row = {
                **base,
                "status": "unavailable",
                "summary": f"독립 검토를 완료하지 못해 코드 Harness 검증만 적용했습니다: {type(exc).__name__}",
                "criteria": [],
                "findings": [],
            }
        return self.store.put("evaluations", evaluation_id, row)


class IndependentClaimEvaluator:
    """Evaluate claim entailment in fresh context using only bound internal chunks."""

    def __init__(self, store: AgentV2Store, model: ModelGateway, *, enabled: bool = True):
        self.store = store
        self.model = model
        self.enabled = enabled

    @staticmethod
    def _needs_review(
        claim: GroundedClaim,
        *,
        policy: dict[str, Any],
        user_effect: str,
        operation: str,
    ) -> bool:
        if claim.claim_kind in set(policy.get("always_review_claim_kinds") or []):
            return True
        if claim.support_status in set(policy.get("review_support_statuses") or []):
            return True
        minimum_confidence = float(policy.get("min_support_confidence") or 0.0)
        if claim.support_status == "supported" and float(claim.confidence or 0.0) < minimum_confidence:
            return True
        if user_effect in set(policy.get("risky_user_effects") or []):
            return True
        return operation in set(policy.get("risky_operations") or [])

    def evaluate(
        self,
        principal: Principal,
        *,
        claims: list[GroundedClaim],
        supporting_text: dict[str, list[str]],
        policy: dict[str, Any],
        user_effect: str = "read",
        operation: str = "understand",
        work_run_id: str = "",
        model: ModelGateway | None = None,
    ) -> tuple[list[GroundedClaim], dict[str, Any]]:
        active_model = model or self.model
        selected = [
            item
            for item in claims
            if item.support_status == "supported"
            and self._needs_review(
                item,
                policy=policy,
                user_effect=user_effect,
                operation=operation,
            )
        ]
        evaluation_id = f"evaluation_{uuid.uuid4().hex}"
        base = {
            "evaluation_id": evaluation_id,
            "employee_id": principal.employee_id,
            "work_run_id": work_run_id,
            "artifact_kind": "grounded_claims",
            "review_context": "fresh",
            "authoritative_for_completion": False,
            "created_at": now_iso(),
        }
        if not selected:
            row = {
                **base,
                "status": "not_required",
                "summary": "Versioned Harness policy did not require a semantic evaluator for these claims.",
                "criteria": [],
                "findings": [],
            }
            return claims, self.store.put("evaluations", evaluation_id, row)

        readiness = active_model.readiness()
        provider = str(readiness.get("provider") or getattr(active_model, "provider", ""))
        allowed_providers = set(policy.get("allowed_providers") or [])
        available = bool(
            self.enabled
            and readiness.get("generation")
            and provider in allowed_providers
        )
        if not available:
            if bool(policy.get("fail_closed", True)):
                for item in selected:
                    item.support_status = "unsupported"
                    item.confidence = 0.0
            row = {
                **base,
                "status": "unavailable",
                "summary": "Fresh-context internal claim evaluation was unavailable; risky claims failed closed.",
                "criteria": [],
                "findings": [],
                "provider": provider,
            }
            return claims, self.store.put("evaluations", evaluation_id, row)

        schema = {
            "type": "object",
            "required": ["verdicts"],
            "properties": {
                "verdicts": {
                    "type": "array",
                    "minItems": len(selected),
                    "maxItems": len(selected),
                    "items": {
                        "type": "object",
                        "required": ["claim_id", "support_status", "confidence"],
                        "properties": {
                            "claim_id": {"type": "string"},
                            "support_status": {
                                "type": "string",
                                "enum": ["supported", "unsupported", "conflicting"],
                            },
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                        "additionalProperties": False,
                    },
                }
            },
            "additionalProperties": False,
        }
        prompt = json.dumps(
            {
                "instruction": (
                    "For each claim, decide only whether every supplied internal excerpt directly entails it. "
                    "If any bound excerpt is unrelated or insufficient, mark the claim unsupported. "
                    "Do not use model memory, external facts, likely meanings, or omitted context. "
                    "Use conflicting only when the supplied excerpts directly disagree with the claim."
                ),
                "claims": [
                    {
                        "claim_id": item.claim_id,
                        "claim": item.text,
                        "claim_kind": item.claim_kind,
                        "internal_excerpts": supporting_text.get(item.claim_id) or [],
                    }
                    for item in selected
                ],
            },
            ensure_ascii=False,
        )
        try:
            generated = active_model.generate_structured(
                system=(
                    "You are a fresh-context internal evidence evaluator. Use only the supplied BoI excerpts. "
                    "Never use external knowledge and return only the requested schema."
                ),
                prompt=prompt,
                schema=schema,
            )
            verdicts = {
                str(item.get("claim_id") or ""): item
                for item in generated.get("verdicts") or []
                if isinstance(item, dict)
            }
            for item in selected:
                verdict = verdicts.get(item.claim_id) or {}
                status = str(verdict.get("support_status") or "unsupported")
                item.support_status = (
                    status if status in {"supported", "unsupported", "conflicting"} else "unsupported"
                )
                item.confidence = max(0.0, min(1.0, float(verdict.get("confidence") or 0.0)))
            row = {
                **base,
                "status": "pass" if all(item.support_status == "supported" for item in selected) else "needs_revision",
                "summary": "Fresh-context claim entailment evaluation completed.",
                "criteria": [item.model_dump(mode="json") for item in selected],
                "findings": [],
                "provider": provider,
                "verifier_facts": {
                    "selected_claim_count": len(selected),
                    "verdicts": [
                        {
                            "claim_id": item.claim_id,
                            "support_status": item.support_status,
                            "confidence": item.confidence,
                        }
                        for item in selected
                    ],
                },
            }
        except Exception as exc:
            if bool(policy.get("fail_closed", True)):
                for item in selected:
                    item.support_status = "unsupported"
                    item.confidence = 0.0
            row = {
                **base,
                "status": "unavailable",
                "summary": f"Fresh-context claim evaluation failed closed: {type(exc).__name__}",
                "criteria": [],
                "findings": [],
                "provider": provider,
                "verifier_facts": {
                    "selected_claim_count": len(selected),
                    "failure_type": type(exc).__name__,
                    "failure_message": str(exc)[:500],
                },
            }
        return claims, self.store.put("evaluations", evaluation_id, row)
