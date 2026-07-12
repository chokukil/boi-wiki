from __future__ import annotations

import json
import uuid
from typing import Any

from .model_gateway import ModelGateway
from .models import Principal
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
            "evidence": evidence[:12],
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
                prompt=json.dumps(review_payload, ensure_ascii=False, default=str)[:24000],
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
                        "criterion": str(item.get("criterion") or "")[:500],
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
                        "message": str(item.get("message") or "")[:1200],
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
                "summary": str(generated.get("summary") or "")[:2000],
                "criteria": criteria[:20],
                "findings": findings[:20],
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
