from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException

from ..task_completion import normalise_task_completion
from .domain import DomainServiceGateway
from .harness import HarnessRegistry
from .models import (
    AgentTaskCancelRequest,
    AgentTaskClaimRequest,
    AgentTaskHeartbeatRequest,
    AgentTaskMaterializeRequest,
    AgentTaskReleaseRequest,
    AgentTaskSubmitRequest,
    AgentTaskVerifyRequest,
    EventRuntimeActivationRequest,
    EventRuntimeDefinitionPreviewRequest,
    EventRuntimeSignalRequest,
    Principal,
)
from .repository import KnowledgeRepository
from .store import AgentV2Store, now_iso


EVENT_NATIVE_DISPATCH_ACTION_REF = "action:boi.event-native.dispatch"


def _stable_id(prefix: str, *parts: str) -> str:
    value = ":".join(str(item) for item in parts)
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:32]}"


def _checksum(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class HarnessPlatformRuntime:
    """Agent-independent Event and external Task execution contracts.

    Domain side effects stay in the injected legacy services used by Web/API.
    This layer owns the shared v2 plan, ACL, lease, idempotency and evidence
    semantics consumed by BoI Agent and external clients.
    """

    def __init__(
        self,
        *,
        store: AgentV2Store,
        repository: KnowledgeRepository,
        harnesses: HarnessRegistry,
        domain_services: DomainServiceGateway,
        harness_package_provider: Callable[[], dict[str, Any]] | None = None,
        runtime_relation_notifier: Callable[[Principal], dict[str, Any]] | None = None,
    ) -> None:
        self.store = store
        self.repository = repository
        self.harnesses = harnesses
        self.domain_services = domain_services
        self.harness_package_provider = harness_package_provider
        self.runtime_relation_notifier = runtime_relation_notifier
        self._lock = threading.RLock()
        from ..governed_runtime.bulk_migration_tasks import BulkMigrationTaskService
        self.bulk_migration_tasks = BulkMigrationTaskService(store)
        self._event_runtime_degraded: dict[str, Any] = {}
        self._ontology_runtime_degraded: dict[str, Any] = {}

    def _notify_runtime_relations(self, principal: Principal) -> None:
        """Refresh the shared Ontology read model after durable work changes.

        Runtime writers own this refresh. Read requests must never trigger a
        graph rebuild merely to hide stale execution relations.
        """

        if self.runtime_relation_notifier is None:
            return
        try:
            self.runtime_relation_notifier(principal)
            self._ontology_runtime_degraded = {}
        except Exception as exc:
            # The Event/Task result is already durable. Keep it observable and
            # expose the projection dependency as degraded instead of claiming
            # that the whole operation never happened.
            self._ontology_runtime_degraded = {
                "error_type": type(exc).__name__,
                "observed_at": now_iso(),
            }

    @staticmethod
    def _require_owner(
        principal: Principal,
        row: dict[str, Any] | None,
        *,
        label: str,
        mutation: bool = False,
    ) -> dict[str, Any]:
        if not row:
            raise HTTPException(status_code=404, detail=f"{label} not found")
        owner = str(row.get("employee_id") or "")
        if owner != principal.employee_id and (mutation or not principal.is_admin):
            raise HTTPException(status_code=403, detail=f"{label} belongs to another employee")
        return row

    def readiness(self) -> dict[str, Any]:
        operations = {
            name: self.domain_services.supports(name)
            for name in (
                "event.runtime.preview",
                "event.runtime.activate",
                "event.runtime.evaluate",
            )
        }
        declarative_fallback = "declarative_event_native"
        dependency_ready = all(operations.values())
        degraded = bool(self._event_runtime_degraded) or not dependency_ready
        return {
            "state": "degraded" if degraded else "ready",
            "ready": True,
            "event_runtime": {
                "state": "degraded" if degraded else "ready",
                "ready": True,
                "operations": operations,
                "fallback": declarative_fallback,
                "degraded_dependency": dict(self._event_runtime_degraded),
            },
            "external_task_runtime": {
                "state": "ready",
                "ready": True,
                "lease_seconds": 900,
                "task_run_materialization": True,
            },
            "ontology_runtime_projection": {
                "state": "degraded" if self._ontology_runtime_degraded else "ready",
                "ready": not bool(self._ontology_runtime_degraded),
                "degraded_dependency": dict(self._ontology_runtime_degraded),
            },
        }

    @staticmethod
    def _signal_value(signal: dict[str, Any], path: str) -> Any:
        """Resolve a declarative field from the normalized signal envelope."""

        clean = str(path or "").strip()
        if not clean:
            return None
        parts = [item for item in clean.split(".") if item]
        if parts and parts[0] in {"payload", "signal"}:
            parts = parts[1:]
        value: Any = signal
        for part in parts:
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value

    def _declarative_detector_decision(
        self,
        definition: dict[str, Any],
        signal: dict[str, Any],
    ) -> str:
        contract = (
            definition.get("detector_contract")
            if isinstance(definition.get("detector_contract"), dict)
            else {}
        )
        decision_field = str(contract.get("decision_field") or "").strip()
        if not decision_field:
            return ""
        raw = self._signal_value(signal, decision_field)
        decision = str(raw or "").strip()
        allowed = {
            str(item).strip()
            for item in contract.get("decision_values") or []
            if str(item).strip()
        }
        return decision if decision and decision in allowed else ""

    def _signal_fingerprint(
        self,
        definition: dict[str, Any],
        signal: dict[str, Any],
    ) -> str:
        values = [
            {
                "field": str(path),
                "value": self._signal_value(signal, str(path)),
            }
            for path in definition.get("fingerprint_fields") or []
        ]
        return _checksum(
            {
                "definition_id": str(definition.get("definition_id") or ""),
                "values": values,
            }
        )

    async def preview_event_definition(
        self,
        principal: Principal,
        request: EventRuntimeDefinitionPreviewRequest,
    ) -> dict[str, Any]:
        if not self.domain_services.supports("event.runtime.preview"):
            raise HTTPException(status_code=503, detail="Event runtime preview is unavailable")
        domain = await self.domain_services.execute_async(
            "event.runtime.preview",
            principal,
            request.model_dump(mode="json"),
        )
        definition = domain.get("definition") if isinstance(domain.get("definition"), dict) else {}
        definition = {
            **request.model_dump(mode="json", exclude={"idempotency_key"}),
            **definition,
            "definition_id": request.definition_id,
            "workflow_engine": request.workflow_engine,
            "workflow_ref": request.workflow_ref,
            "status": "draft",
        }
        errors: list[str] = []
        if request.workflow_engine == "event_native" and not request.workflow_ref:
            errors.append("event_native workflow requires workflow_ref")
        if not definition.get("fingerprint_fields"):
            errors.append("fingerprint_fields are required for durable detector state")
        detector_contract = (
            definition.get("detector_contract")
            if isinstance(definition.get("detector_contract"), dict)
            else {}
        )
        decision_field = str(detector_contract.get("decision_field") or "").strip()
        decision_values = {
            str(item).strip()
            for item in detector_contract.get("decision_values") or []
            if str(item).strip()
        }
        allowed_decisions = {
            "published",
            "suppressed",
            "aggregated",
            "pending_confirmation",
            "ignored",
            "failed",
        }
        if detector_contract and not decision_field:
            errors.append("detector_contract.decision_field is required")
        if detector_contract and (
            not decision_values or not decision_values.issubset(allowed_decisions)
        ):
            errors.append("detector_contract.decision_values contains an unsupported decision")
        domain_validation = domain.get("validation") if isinstance(domain.get("validation"), dict) else {}
        errors.extend(str(item) for item in domain_validation.get("errors") or [] if str(item))
        validation = {
            "status": "passed" if not errors else "failed",
            "errors": list(dict.fromkeys(errors)),
            "warnings": [
                str(item) for item in domain_validation.get("warnings") or [] if str(item)
            ],
        }
        plan_id = _stable_id(
            "eventplan",
            principal.employee_id,
            request.definition_id,
            request.idempotency_key,
        )
        existing = self.store.get("event_runtime_plans", plan_id)
        if existing:
            return {
                "plan_id": plan_id,
                "definition_id": request.definition_id,
                "status": str(existing.get("status") or "draft"),
                "validation": existing.get("validation") or validation,
                "definition": existing.get("definition") or definition,
                "production_changed": False,
                "replayed": True,
            }
        plan = {
            "plan_id": plan_id,
            "employee_id": principal.employee_id,
            "definition_id": request.definition_id,
            "definition": definition,
            "validation": validation,
            "status": "draft",
            "revision": 1,
            "idempotency_key": request.idempotency_key,
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        self.store.put("event_runtime_plans", plan_id, plan)
        return {
            "plan_id": plan_id,
            "definition_id": request.definition_id,
            "status": "draft",
            "validation": validation,
            "definition": definition,
            "production_changed": False,
            "replayed": False,
        }

    async def activate_event_definition(
        self,
        principal: Principal,
        plan_id: str,
        request: EventRuntimeActivationRequest,
    ) -> dict[str, Any]:
        with self._lock:
            plan = self._require_owner(
                principal,
                self.store.get("event_runtime_plans", plan_id),
                label="event runtime plan",
                mutation=True,
            )
            revision = int(plan.get("revision") or 1)
            if request.expected_revision is not None and request.expected_revision != revision:
                raise HTTPException(
                    status_code=409,
                    detail={"code": "revision_conflict", "current_revision": revision},
                )
            if (plan.get("validation") or {}).get("status") != "passed":
                raise HTTPException(status_code=409, detail="event definition validation has not passed")
        if not self.domain_services.supports("event.runtime.activate"):
            raise HTTPException(status_code=503, detail="Event runtime activation is unavailable")
        domain = await self.domain_services.execute_async(
            "event.runtime.activate",
            principal,
            {
                "definition": plan["definition"],
                "confirmation": request.confirmation,
                "reason": request.reason,
            },
        )
        definition = domain.get("definition") if isinstance(domain.get("definition"), dict) else {}
        definition = {
            **plan["definition"],
            **definition,
            "definition_id": plan["definition_id"],
            "employee_id": principal.employee_id,
            "status": "active",
            "revision": revision + 1,
            "activated_at": now_iso(),
        }
        self.store.put("event_runtime_definitions", str(plan["definition_id"]), definition)
        plan.update(
            {
                "status": "active",
                "revision": revision + 1,
                "activation_reason": request.reason,
                "activated_at": definition["activated_at"],
                "updated_at": now_iso(),
            }
        )
        self.store.put("event_runtime_plans", plan_id, plan)
        return {
            "plan_id": plan_id,
            "definition_id": plan["definition_id"],
            "status": "active",
            "revision": plan["revision"],
            "definition": definition,
            "production_changed": True,
        }

    async def evaluate_signal(
        self,
        principal: Principal,
        request: EventRuntimeSignalRequest,
    ) -> dict[str, Any]:
        definition = self._require_owner(
            principal,
            self.store.get("event_runtime_definitions", request.definition_id),
            label="event runtime definition",
            mutation=True,
        )
        if definition.get("status") != "active":
            raise HTTPException(status_code=409, detail="event runtime definition is not active")
        replay_key = _stable_id(
            "eventreplay",
            principal.employee_id,
            request.definition_id,
            request.idempotency_key,
        )
        replay = self.store.get("event_runtime_idempotency", replay_key)
        if replay and isinstance(replay.get("response"), dict):
            return {**replay["response"], "replayed": True}
        declarative_decision = self._declarative_detector_decision(
            definition,
            request.signal,
        )
        domain: dict[str, Any] = {}
        dependency_failure: Exception | None = None
        event_native_local = bool(
            declarative_decision
            and str(definition.get("workflow_engine") or "event_native")
            == "event_native"
        )
        if event_native_local:
            # The declarative detector and event-native workflow are the core
            # runtime. Kafka or another external broker may mirror the event,
            # but it is not on the critical path and must not be contacted in
            # order to decide or execute the local workflow.
            domain = {
                "decision": declarative_decision,
                "reason": "선언형 Detector 계약으로 판정하고 event-native runtime에서 실행했습니다.",
                "broker": {
                    "status": "accepted",
                    "mode": "event_native_local",
                },
            }
            self._event_runtime_degraded = {}
        elif self.domain_services.supports("event.runtime.evaluate"):
            try:
                domain = await self.domain_services.execute_async(
                    "event.runtime.evaluate",
                    principal,
                    {
                        **request.model_dump(mode="json"),
                        "definition": definition,
                    },
                )
                self._event_runtime_degraded = {}
            except Exception as exc:  # connector failure is capability-scoped
                dependency_failure = exc
        elif not declarative_decision:
            raise HTTPException(status_code=503, detail="Event runtime evaluation is unavailable")
        if dependency_failure is not None:
            if not declarative_decision:
                raise dependency_failure
            self._event_runtime_degraded = {
                "operation": "event.runtime.evaluate",
                "error_type": type(dependency_failure).__name__,
                "fallback": "declarative_event_native",
                "observed_at": now_iso(),
            }
            domain = {
                "decision": declarative_decision,
                "reason": (
                    "선언형 Detector 계약으로 판정했습니다. 외부 Event Broker는 "
                    "degraded 상태이며 event-native runtime이 로컬 실행을 계속합니다."
                ),
                "broker": {
                    "status": "degraded",
                    "mode": "declarative_event_native",
                },
            }
        decision = str(
            declarative_decision
            or domain.get("decision")
            or domain.get("detector_decision")
            or "failed"
        )
        allowed_decisions = {
            "published",
            "suppressed",
            "aggregated",
            "pending_confirmation",
            "ignored",
            "failed",
        }
        if decision not in allowed_decisions:
            decision = "failed"
        event = domain.get("event") if isinstance(domain.get("event"), dict) else {}
        event_occurrence_id = str(event.get("event_id") or "")
        if not event_occurrence_id:
            event_occurrence_id = _stable_id(
                "eventocc",
                request.definition_id,
                request.idempotency_key,
            )
        trace_id = str(event.get("trace_id") or request.trace_id or "")
        fingerprint = str(
            domain.get("fingerprint")
            or self._signal_fingerprint(definition, request.signal)
        )
        decision_id = _stable_id("detector", request.definition_id, request.idempotency_key)
        decision_row = {
            "decision_id": decision_id,
            "employee_id": principal.employee_id,
            "definition_id": request.definition_id,
            "event_occurrence_id": event_occurrence_id,
            "decision": decision,
            "fingerprint": fingerprint,
            "count": max(1, int(domain.get("count") or 0)),
            "state": str(domain.get("state") or ""),
            "first_observed_at": str(domain.get("first_observed_at") or now_iso()),
            "last_observed_at": str(domain.get("last_observed_at") or now_iso()),
            "summary": str(domain.get("reason") or ""),
            "source_ref": str(definition.get("source_name") or request.definition_id),
            "correlation_id": request.correlation_id,
            "causation_id": request.causation_id,
            "trace_id": trace_id,
            "raw_payload_stored": False,
            "created_at": now_iso(),
        }
        self.store.put("event_detector_decisions", decision_id, decision_row)
        workflow_run_id = ""
        outcome_ref = ""
        task_run_id = ""
        action_run_id = ""
        executor_result_ref = ""
        completion_record_ref = ""
        next_event_ref = ""
        evidence_ledger_ref = _stable_id("ledger", decision_id)
        if decision == "published":
            workflow_run_id = _stable_id("workflowrun", event_occurrence_id)
            outcome_id = _stable_id("outcome", workflow_run_id)
            outcome_ref = f"boi:runtime:outcome:{outcome_id}"
            task_run_id = _stable_id("taskrun", workflow_run_id, "event-native-dispatch")
            action_run_id = _stable_id("actionrun", task_run_id, request.idempotency_key)
            executor_result_ref = _stable_id("executorresult", task_run_id)
            next_event_id = _stable_id("nextevent", outcome_id)
            next_event_ref = f"boi:runtime:next-event:{next_event_id}"
            broker = domain.get("broker") if isinstance(domain.get("broker"), dict) else {}
            event_native_local = str(
                definition.get("workflow_engine") or "event_native"
            ) == "event_native"
            broker_ready = str(broker.get("status") or "") in {
                "published",
                "queued",
                "accepted",
            }
            execution_ready = bool(event_native_local or broker_ready)
            completion_record_ref = (
                _stable_id("completion", task_run_id)
                if execution_ready
                else ""
            )
            workflow_status = "completed" if event_native_local else (
                "queued" if broker_ready else "waiting_worker"
            )
            self.store.put(
                "event_occurrences",
                event_occurrence_id,
                {
                    "event_occurrence_id": event_occurrence_id,
                    "employee_id": principal.employee_id,
                    "definition_id": request.definition_id,
                    "event_type": definition.get("target_event_type"),
                    "trace_id": trace_id,
                    "correlation_id": request.correlation_id,
                    "causation_id": request.causation_id,
                    "detector_decision_ref": decision_id,
                    "occurred_at": str(event.get("occurred_at") or request.occurred_at or now_iso()),
                    "raw_payload_stored": False,
                },
            )
            self.store.put(
                "workflow_runs",
                workflow_run_id,
                {
                    "workflow_run_id": workflow_run_id,
                    "employee_id": principal.employee_id,
                    "definition_id": request.definition_id,
                    "workflow_ref": definition.get("workflow_ref") or definition.get("sop_ref") or "",
                    "workflow_engine": definition.get("workflow_engine") or "event_native",
                    "event_occurrence_id": event_occurrence_id,
                    "status": workflow_status,
                    "checkpoint": {
                        "stage": "event_published",
                        "pending_interrupt": "" if broker_ready else "worker_unavailable",
                        "detector_decision_ref": decision_id,
                    },
                    "task_run_ids": [task_run_id],
                    "action_run_ids": [action_run_id],
                    "executor_result_refs": [executor_result_ref],
                    "revision": 1,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
            self.store.put(
                "task_runs",
                task_run_id,
                {
                    "task_run_id": task_run_id,
                    "employee_id": principal.employee_id,
                    "workflow_run_id": workflow_run_id,
                    "workflow_ref": definition.get("workflow_ref") or "",
                    "task_id": "event-native-dispatch",
                    "task_ref": f"{definition.get('workflow_ref') or request.definition_id}#event-native-dispatch",
                    "task_mode": "autopilot",
                    "executor_binding": "action",
                    "executor_ref": "system:boi-event-native-runtime",
                    "status": "completed" if execution_ready else "waiting_agent",
                    "current_state": "completed" if execution_ready else "waiting_agent",
                    "result_ref": executor_result_ref,
                    "completion_record_ref": completion_record_ref,
                    "provenance": "operational_verified",
                    "revision": 1,
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
            self.store.put(
                "action_runs",
                action_run_id,
                {
                    "action_run_id": action_run_id,
                    "employee_id": principal.employee_id,
                    "action_ref": EVENT_NATIVE_DISPATCH_ACTION_REF,
                    "action_key": EVENT_NATIVE_DISPATCH_ACTION_REF.removeprefix("action:"),
                    "event_occurrence_id": event_occurrence_id,
                    "workflow_run_id": workflow_run_id,
                    "task_run_id": task_run_id,
                    "executor_ref": "system:boi-event-native-runtime",
                    "execution_mode": "deterministic",
                    "status": "completed" if execution_ready else "waiting_agent",
                    "result_ref": executor_result_ref,
                    "evidence_refs": [decision_id],
                    "evidence_ledger_ids": [evidence_ledger_ref],
                    "idempotency_key": request.idempotency_key,
                    "production_changed": execution_ready,
                    "provenance": "operational_verified",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
            self.store.put(
                "external_work_results",
                executor_result_ref,
                {
                    "external_work_result_id": executor_result_ref,
                    "employee_id": principal.employee_id,
                    "task_run_id": task_run_id,
                    "workflow_run_id": workflow_run_id,
                    "work_run_id": workflow_run_id,
                    "executor_kind": "deterministic_action",
                    "executor_ref": "system:boi-event-native-runtime",
                    "result": {
                        "status": "accepted" if execution_ready else "waiting_worker",
                        "summary": (
                            "Event-native runtime이 결정론적 Action으로 Workflow 단계를 완료했습니다."
                            if event_native_local
                            else "Event runtime이 Workflow 실행을 인수했습니다."
                        ),
                    },
                    "evidence_refs": [decision_id],
                    "verification_status": "verified" if execution_ready else "pending",
                    "raw_prompt_stored": False,
                    "created_at": now_iso(),
                },
            )
            if execution_ready:
                completion_summary = (
                    "Event-native runtime이 DetectorDecision 근거와 결정론적 "
                    "Action 결과를 검증해 Task를 완료했습니다."
                )
                self.store.put(
                    "completion_records",
                    completion_record_ref,
                    {
                        "completion_id": completion_record_ref,
                        "employee_id": principal.employee_id,
                        "work_run_id": workflow_run_id,
                        "context_id": event_occurrence_id,
                        "task_ref": f"runtime-task:{task_run_id}",
                        "workflow_ref": definition.get("workflow_ref") or "",
                        "task_mode": "autopilot",
                        "decision": "complete",
                        "summary": completion_summary,
                        "evidence_refs": [decision_id, executor_result_ref],
                        "used_evidence_refs": [decision_id, executor_result_ref],
                        "evidence_ledger_ids": [evidence_ledger_ref],
                        "execution_result": completion_summary,
                        "completion_criteria": {
                            "status": "passed",
                            "source": "event_native_runtime",
                            "criteria": [
                                {
                                    "check_id": "detector_decision_verified",
                                    "status": "passed",
                                },
                                {
                                    "check_id": "deterministic_action_completed",
                                    "status": "passed",
                                },
                            ],
                        },
                        "exceptions": [],
                        "incomplete_items": [],
                        "next_work_lesson": (
                            "같은 Event 정의와 idempotency 계약으로 검증된 "
                            "결과를 재사용합니다."
                        ),
                        "outcome_id": outcome_id,
                        "outcome_ref": outcome_ref,
                        "verifier": "system:boi-event-native-runtime",
                        "provenance": "operational_verified",
                        "created_at": now_iso(),
                    },
                )
            self.store.put(
                "outcomes",
                outcome_id,
                {
                    "outcome_id": outcome_id,
                    "boi_ref": outcome_ref,
                    "employee_id": principal.employee_id,
                    "workflow_run_id": workflow_run_id,
                    "event_occurrence_id": event_occurrence_id,
                    "status": workflow_status,
                    "quality_state": (
                        "verified" if execution_ready else "pending_verification"
                    ),
                    "verifier": "event-native-runtime",
                    "task_run_ids": [task_run_id],
                    "action_run_ids": [action_run_id],
                    "executor_result_refs": [executor_result_ref],
                    "completion_record_id": completion_record_ref,
                    "evidence_ledger_ids": [evidence_ledger_ref],
                    "result_summary": (
                        "Event-native runtime이 결정론적 Action으로 Workflow 단계를 완료했습니다."
                        if execution_ready
                        else "Event runtime이 Workflow 실행을 인수했습니다."
                    ),
                    "next_work_lesson": (
                        "검증된 Event·Action 결과와 idempotency 계약을 다음 업무에 재사용합니다."
                        if execution_ready
                        else ""
                    ),
                    "visibility": "private",
                    "allowed_employee_ids": [principal.employee_id],
                    "allowed_team_ids": list(principal.teams),
                    "provenance": "operational_verified",
                    "next_event_ref": next_event_ref,
                    "evidence_ledger_ref": evidence_ledger_ref,
                    "created_at": now_iso(),
                },
            )
            self.store.put(
                "next_events",
                next_event_id,
                {
                    "next_event_id": next_event_id,
                    "boi_ref": next_event_ref,
                    "employee_id": principal.employee_id,
                    "workflow_run_id": workflow_run_id,
                    "outcome_ref": outcome_ref,
                    "event_type": f"{definition.get('target_event_type') or 'business.event'}.workflow.result",
                    "status": "planned",
                    "causation_id": event_occurrence_id,
                    "trace_id": trace_id,
                    "provenance": "deterministic_extracted",
                    "created_at": now_iso(),
                },
            )
            usage_id = _stable_id("usage", workflow_run_id, principal.employee_id)
            self.store.put(
                "usage_records",
                usage_id,
                {
                    "usage_id": usage_id,
                    "employee_id": principal.employee_id,
                    "person_ref": f"person:{principal.employee_id}",
                    "task_ref": f"runtime-task:{task_run_id}",
                    "work_run_id": workflow_run_id,
                    "agent_definition_ref": "",
                    "agent_deployment_ref": "",
                    "system_ref": "system:boi-wiki",
                    "connector_refs": [f"connector:{definition.get('source_kind') or 'event'}"],
                    "action_refs": [EVENT_NATIVE_DISPATCH_ACTION_REF],
                    "skill_refs": [],
                    "harness_refs": ["harness:event.lifecycle"],
                    "purpose": str(definition.get("name") or definition.get("target_event_type") or "업무 이벤트 처리"),
                    "version": "event-runtime/v1",
                    "result_refs": [action_run_id, outcome_id],
                    "source": "event_run",
                    "provenance": "operational_verified",
                    "visibility": "private",
                    "allowed_employee_ids": [principal.employee_id],
                    "allowed_team_ids": list(principal.teams),
                    "occurred_at": now_iso(),
                },
            )
        self.store.put(
            "evidence_ledger",
            evidence_ledger_ref,
            {
                "ledger_id": evidence_ledger_ref,
                "employee_id": principal.employee_id,
                "work_run_id": workflow_run_id,
                "evidence_id": decision_id,
                "kind": "detector_decision",
                "title": f"DetectorDecision {decision}",
                "summary": decision_row["summary"],
                "source": "event_runtime",
                "authority": "operational",
                "verification": "verified" if decision != "failed" else "failed",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            },
        )
        response = {
            "definition_id": request.definition_id,
            "detector_decision": decision,
            "detector_decision_ref": decision_id,
            "event_occurrence_id": event_occurrence_id,
            "workflow_run_id": workflow_run_id,
            "workflow_status": (
                (self.store.get("workflow_runs", workflow_run_id) or {}).get("status")
                if workflow_run_id
                else ""
            ),
            "result_boi_ref": outcome_ref,
            "task_run_id": task_run_id,
            "action_run_id": action_run_id,
            "executor_result_ref": executor_result_ref,
            "completion_record_ref": completion_record_ref,
            "next_event_ref": next_event_ref,
            "evidence_ledger_ref": evidence_ledger_ref,
            "trace_id": trace_id,
            "raw_payload_stored": False,
            "replayed": False,
        }
        self.store.put(
            "event_runtime_idempotency",
            replay_key,
            {
                "idempotency_id": replay_key,
                "employee_id": principal.employee_id,
                "operation": "signal.evaluate",
                "response": response,
                "created_at": now_iso(),
            },
        )
        if decision == "published":
            self._notify_runtime_relations(principal)
        return response

    def get_event_occurrence(
        self,
        principal: Principal,
        event_occurrence_id: str,
    ) -> dict[str, Any]:
        occurrence = self._require_owner(
            principal,
            self.store.get("event_occurrences", event_occurrence_id),
            label="event occurrence",
        )
        decision = self._require_owner(
            principal,
            self.store.get(
                "event_detector_decisions",
                str(occurrence.get("detector_decision_ref") or ""),
            ),
            label="detector decision",
        )
        return {
            "event_occurrence": occurrence,
            "detector_decision": decision,
            "raw_signal_state": {
                "fingerprint": str(decision.get("fingerprint") or ""),
                "count": int(decision.get("count") or 0),
                "state": str(decision.get("state") or ""),
                "first_observed_at": str(decision.get("first_observed_at") or ""),
                "last_observed_at": str(decision.get("last_observed_at") or ""),
                "source_ref": str(decision.get("source_ref") or ""),
                "raw_payload_stored": False,
            },
        }

    def get_workflow_run(
        self,
        principal: Principal,
        workflow_run_id: str,
    ) -> dict[str, Any]:
        workflow = self._require_owner(
            principal,
            self.store.get("workflow_runs", workflow_run_id),
            label="workflow run",
        )
        task_runs = [
            item
            for item in self.store.list(
                "task_runs",
                employee_id=str(workflow.get("employee_id") or principal.employee_id),
                limit=10_000,
            )
            if str(item.get("workflow_run_id") or "") == workflow_run_id
        ]
        executor_results = [
            item
            for item in self.store.list(
                "external_work_results",
                employee_id=str(workflow.get("employee_id") or principal.employee_id),
                limit=10_000,
            )
            if str(item.get("workflow_run_id") or "") == workflow_run_id
        ]
        action_runs = [
            item
            for item in self.store.list(
                "action_runs",
                employee_id=str(workflow.get("employee_id") or principal.employee_id),
                limit=10_000,
            )
            if str(item.get("workflow_run_id") or "") == workflow_run_id
        ]
        return {
            "workflow_run": {
                **workflow,
                "engine": str(workflow.get("workflow_engine") or "event_native"),
            },
            "task_runs": task_runs,
            "action_runs": action_runs,
            "executor_results": executor_results,
        }

    def get_task_run(
        self,
        principal: Principal,
        task_run_ref: str,
    ) -> dict[str, Any]:
        """Return one ACL-checked runtime Task and its typed execution lineage."""

        requested = str(task_run_ref or "").strip()
        task_run_id = requested.removeprefix("runtime-task:")
        task_run = self.store.get("task_runs", task_run_id)
        if not task_run and requested:
            visible_matches = [
                item
                for item in self.store.list("task_runs", limit=10_000)
                if str(item.get("task_ref") or "") == requested
                and (
                    str(item.get("employee_id") or "") == principal.employee_id
                    or principal.is_admin
                )
            ]
            if len(visible_matches) > 1:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "task_run_selection_required",
                        "task_run_refs": [
                            f"runtime-task:{item.get('task_run_id')}"
                            for item in visible_matches[:20]
                        ],
                    },
                )
            task_run = visible_matches[0] if visible_matches else None
        task_run = self._require_owner(principal, task_run, label="task run")
        task_run_id = str(task_run.get("task_run_id") or "")
        workflow_run_id = str(task_run.get("workflow_run_id") or "")
        workflow_run = None
        lineage_warnings: list[str] = []
        if workflow_run_id:
            stored_workflow = self.store.get("workflow_runs", workflow_run_id)
            if stored_workflow is None:
                # Older externally materialized TaskPackages could retain a
                # caller-supplied workflow_run_id without a corresponding
                # WorkflowRun. Keep their verified Task/Outcome evidence
                # readable, but expose the incomplete lineage explicitly.
                lineage_warnings.append("workflow_run_missing")
            else:
                workflow_run = self._require_owner(
                    principal,
                    stored_workflow,
                    label="workflow run",
                )
        event_occurrence_id = str((workflow_run or {}).get("event_occurrence_id") or "")
        event_occurrence = (
            self._require_owner(
                principal,
                self.store.get("event_occurrences", event_occurrence_id),
                label="event occurrence",
            )
            if event_occurrence_id
            else None
        )
        action_runs = [
            item
            for item in self.store.list(
                "action_runs",
                employee_id=str(task_run.get("employee_id") or principal.employee_id),
                limit=10_000,
            )
            if str(item.get("task_run_id") or "") == task_run_id
        ]
        result_ref = str(
            task_run.get("external_work_result_ref")
            or task_run.get("result_ref")
            or ""
        )
        executor_result = (
            self._require_owner(
                principal,
                self.store.get("external_work_results", result_ref),
                label="external work result",
            )
            if result_ref
            else None
        )
        outcomes = [
            item
            for item in self.store.list(
                "outcomes",
                employee_id=str(task_run.get("employee_id") or principal.employee_id),
                limit=10_000,
            )
            if task_run_id in {
                str(value) for value in item.get("task_run_ids") or []
            }
            or (
                workflow_run_id
                and str(item.get("workflow_run_id") or "") == workflow_run_id
            )
        ]
        outcomes.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        outcome = outcomes[0] if outcomes else None
        ledger_refs = list(
            dict.fromkeys(
                str(value)
                for value in [
                    (outcome or {}).get("evidence_ledger_ref"),
                    *((outcome or {}).get("evidence_ledger_ids") or []),
                    *(
                        value
                        for action in action_runs
                        for value in action.get("evidence_ledger_ids") or []
                    ),
                ]
                if value is not None and str(value).strip()
            )
        )
        evidence_ledgers = [
            self._require_owner(
                principal,
                self.store.get("evidence_ledger", ledger_ref),
                label="evidence ledger",
            )
            for ledger_ref in ledger_refs
        ]
        completion_record_ref = str(task_run.get("completion_record_ref") or "")
        completion_record = (
            self._require_owner(
                principal,
                self.store.get("completion_records", completion_record_ref),
                label="completion record",
            )
            if completion_record_ref
            else None
        )
        return {
            "task_run": task_run,
            "workflow_run": workflow_run,
            "event_occurrence": event_occurrence,
            "action_runs": action_runs,
            "executor_result": executor_result,
            "outcome": outcome,
            "evidence_ledgers": evidence_ledgers,
            "completion_record": completion_record,
            "lineage_status": "partial" if lineage_warnings else "complete",
            "lineage_warnings": lineage_warnings,
        }

    def get_outcome(
        self,
        principal: Principal,
        outcome_ref: str,
    ) -> dict[str, Any]:
        outcome_id = str(outcome_ref or "").removeprefix("boi:runtime:outcome:")
        outcome = self._require_owner(
            principal,
            self.store.get("outcomes", outcome_id),
            label="outcome",
        )
        next_event_ref = str(outcome.get("next_event_ref") or "")
        next_event_id = next_event_ref.removeprefix("boi:runtime:next-event:")
        next_event = (
            self._require_owner(
                principal,
                self.store.get("next_events", next_event_id),
                label="next event",
            )
            if next_event_id
            else None
        )
        ledger_refs = list(
            dict.fromkeys(
                str(item)
                for item in [
                    outcome.get("evidence_ledger_ref"),
                    *(outcome.get("evidence_ledger_ids") or []),
                ]
                if item is not None and str(item).strip()
            )
        )
        ledgers = [
            self._require_owner(
                principal,
                self.store.get("evidence_ledger", ledger_ref),
                label="evidence ledger",
            )
            for ledger_ref in ledger_refs
        ]
        return {
            "outcome": outcome,
            "next_event": next_event,
            "evidence_ledger": ledgers[0] if ledgers else None,
            "evidence_ledgers": ledgers,
        }

    def list_detector_decisions(
        self,
        principal: Principal,
        definition_id: str,
    ) -> dict[str, Any]:
        self._require_owner(
            principal,
            self.store.get("event_runtime_definitions", definition_id),
            label="event runtime definition",
        )
        decisions = [
            item
            for item in self.store.list(
                "event_detector_decisions",
                employee_id=principal.employee_id,
                limit=10_000,
            )
            if str(item.get("definition_id") or "") == definition_id
        ]
        decisions.sort(key=lambda item: str(item.get("created_at") or ""))
        return {
            "definition_id": definition_id,
            "count": len(decisions),
            "decision_kinds": sorted(
                {
                    str(item.get("decision") or "")
                    for item in decisions
                    if str(item.get("decision") or "")
                }
            ),
            "items": decisions,
        }

    def _task_candidates(self, principal: Principal) -> list[dict[str, Any]]:
        task_harness = self.harnesses.definition("task.runtime").public_payload()
        package_identity = (
            self.harness_package_provider()
            if self.harness_package_provider is not None
            else {}
        )
        package_release = str(package_identity.get("release") or "")
        package_checksum = str(package_identity.get("checksum") or "")
        package_signature = str(package_identity.get("signature") or "")
        packages: list[dict[str, Any]] = []
        for record in self.repository.authoritative_records(principal, include_drafts=False):
            raw_tasks: list[dict[str, Any]] = []
            raw_tasks.extend(
                item for item in record.metadata.get("tasks") or [] if isinstance(item, dict)
            )
            workflow = record.metadata.get("workflow") if isinstance(record.metadata.get("workflow"), dict) else {}
            raw_tasks.extend(
                item for item in workflow.get("stages") or [] if isinstance(item, dict)
            )
            for index, task in enumerate(raw_tasks):
                if str(task.get("executor_readiness") or "ready").lower() != "ready":
                    continue
                mode = str(task.get("task_mode") or task.get("execution_mode") or "copilot").lower()
                explicit_binding = str(task.get("executor_binding") or "").lower()
                executor_binding = explicit_binding or (
                    "hybrid" if mode == "copilot" else "external_manual" if mode == "manual" else ""
                )
                if executor_binding not in {"agent_claim", "hybrid"}:
                    continue
                task_id = str(task.get("task_id") or task.get("id") or f"task-{index + 1}")
                normalized = normalise_task_completion(task)
                package_id = _stable_id(
                    "taskpkg",
                    principal.employee_id,
                    record.record_id,
                    task_id,
                )
                task_contract_checksum = _checksum(
                    {
                        "harness": task_harness,
                        "completion_design": normalized.get("completion_design") or {},
                        "task_mode": mode,
                        "executor_binding": executor_binding,
                    }
                )
                action_refs = list(
                    dict.fromkeys(
                        str(item)
                        for item in [
                            *(task.get("action_refs") or []),
                            *(task.get("actions") or []),
                            *(task.get("automated_actions") or []),
                        ]
                        if str(item)
                    )
                )
                skill_refs = list(
                    dict.fromkeys(
                        str(item)
                        for item in [*(task.get("skill_refs") or []), *(task.get("skills") or [])]
                        if str(item)
                    )
                )
                packages.append(
                    {
                        "task_package_id": package_id,
                        "employee_id": principal.employee_id,
                        "task_id": task_id,
                        "task_ref": f"{record.record_id}#{task_id}",
                        "workflow_ref": record.record_id,
                        "goal": str(task.get("stage_goal") or task.get("purpose") or task.get("name") or task_id),
                        "current_state": "available",
                        "status": "available",
                        "task_mode": mode,
                        "executor_binding": executor_binding,
                        "inputs": {
                            "source_ref": record.record_id,
                            "entry_event": str(task.get("entry_event") or ""),
                        },
                        "evidence_refs": [record.record_id],
                        "context_manifest_ref": "",
                        "harness_bindings": [
                            {
                                "harness_id": task_harness["harness_id"],
                                "version": task_harness["version"],
                            }
                        ],
                        "harness_release": package_release,
                        "harness_checksum": package_checksum or task_contract_checksum,
                        "harness_signature": package_signature,
                        "task_contract_checksum": task_contract_checksum,
                        "allowed_actions": action_refs,
                        "allowed_skills": skill_refs,
                        "allowed_connectors": [],
                        "completion_contract": normalized.get("completion_design") or {},
                        "risk": "high" if task.get("approval_required") else "medium",
                        "approval_required": mode != "autopilot" or bool(task.get("approval_required")),
                        "result_schema": {
                            "type": "object",
                            "required": ["status", "summary"],
                            "properties": {
                                "status": {"type": "string"},
                                "summary": {"type": "string"},
                            },
                        },
                        "lease": {},
                        "revision": 1,
                        "idempotency_required": True,
                        "manual_fallback": {
                            "available": True,
                            "executor_binding": "external_manual",
                        },
                        "orphan_workers": 0,
                        "state_history": [
                            {"state": "available", "at": now_iso()}
                        ],
                        "created_at": now_iso(),
                        "updated_at": now_iso(),
                    }
                )
        return packages

    def _task_package(self, principal: Principal, task_package_id: str) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_view(principal,task_package_id)
        stored = self.store.get("agent_task_packages", task_package_id)
        if stored:
            return self._require_owner(principal, stored, label="agent task package")
        candidate = next(
            (
                item
                for item in self._task_candidates(principal)
                if item["task_package_id"] == task_package_id
            ),
            None,
        )
        if not candidate:
            raise HTTPException(status_code=404, detail="agent task package not found")
        return candidate

    def materialize_agent_task(
        self,
        principal: Principal,
        request: AgentTaskMaterializeRequest,
    ) -> dict[str, Any]:
        """Create an externally claimable package for one concrete TaskRun."""

        if not principal.is_admin and "boi.workflow_runner" not in principal.roles:
            raise HTTPException(
                status_code=403,
                detail="workflow runner permission is required to materialize a task",
            )
        candidate = next(
            (
                item
                for item in self._task_candidates(principal)
                if item.get("workflow_ref") == request.workflow_ref
                and item.get("task_id") == request.task_id
            ),
            None,
        )
        if not candidate:
            raise HTTPException(
                status_code=404,
                detail="claimable task definition not found",
            )
        package_id = _stable_id(
            "taskpkg",
            principal.employee_id,
            request.task_run_id,
            str(candidate.get("task_ref") or ""),
        )
        with self._lock:
            existing = self.store.get("agent_task_packages", package_id)
            if existing:
                existing = self._require_owner(
                    principal,
                    existing,
                    label="agent task package",
                    mutation=True,
                )
                if (
                    existing.get("materialization_idempotency_key")
                    != request.idempotency_key
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="task run was materialized with a different idempotency key",
                    )
                return {**existing, "replayed": True}
            task_run = self.store.get("task_runs", request.task_run_id)
            if task_run:
                self._require_owner(
                    principal,
                    task_run,
                    label="task run",
                    mutation=True,
                )
                raise HTTPException(
                    status_code=409,
                    detail="task run already has a different package",
                )
            created_at = now_iso()
            candidate_binding = str(candidate.get("executor_binding") or "hybrid")
            executor_binding = str(request.executor_binding or candidate_binding)
            if candidate_binding != "hybrid" and executor_binding != candidate_binding:
                raise HTTPException(
                    status_code=409,
                    detail="materialization cannot widen the task executor binding",
                )
            initial_status = (
                "waiting_agent"
                if executor_binding == "agent_claim" and not request.agent_available
                else "available"
            )
            workflow_run_id = str(request.workflow_run_id or "").strip() or _stable_id(
                "workflowrun",
                principal.employee_id,
                request.workflow_ref,
                request.task_run_id,
            )
            workflow_run = self.store.get("workflow_runs", workflow_run_id)
            if workflow_run:
                workflow_run = self._require_owner(
                    principal,
                    workflow_run,
                    label="workflow run",
                    mutation=True,
                )
                if str(workflow_run.get("workflow_ref") or "") not in {
                    "",
                    request.workflow_ref,
                }:
                    raise HTTPException(
                        status_code=409,
                        detail="workflow run belongs to a different workflow",
                    )
                task_run_ids = list(
                    dict.fromkeys(
                        [
                            *list(workflow_run.get("task_run_ids") or []),
                            request.task_run_id,
                        ]
                    )
                )
                workflow_run.update(
                    {
                        "workflow_ref": request.workflow_ref,
                        "task_run_ids": task_run_ids,
                        "status": "running",
                        "revision": int(workflow_run.get("revision") or 0) + 1,
                        "updated_at": created_at,
                    }
                )
            else:
                workflow_run = {
                    "workflow_run_id": workflow_run_id,
                    "employee_id": principal.employee_id,
                    "workflow_ref": request.workflow_ref,
                    "workflow_engine": "external_orchestrator",
                    "event_occurrence_id": "",
                    "status": "running",
                    "checkpoint": {
                        "stage": "task_materialized",
                        "pending_interrupt": "",
                    },
                    "task_run_ids": [request.task_run_id],
                    "action_run_ids": [],
                    "executor_result_refs": [],
                    "revision": 1,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            package = {
                **candidate,
                "task_package_id": package_id,
                "task_run_id": request.task_run_id,
                "workflow_run_id": workflow_run_id,
                "executor_binding": executor_binding,
                "status": initial_status,
                "current_state": initial_status,
                "lease": {},
                "revision": 1,
                "agent_available": request.agent_available,
                "materialization_idempotency_key": request.idempotency_key,
                "state_history": [{"state": initial_status, "at": created_at}],
                "created_at": created_at,
                "updated_at": created_at,
            }
            self.store.put("workflow_runs", workflow_run_id, workflow_run)
            self.store.put(
                "task_runs",
                request.task_run_id,
                {
                    "task_run_id": request.task_run_id,
                    "employee_id": principal.employee_id,
                    "workflow_run_id": workflow_run_id,
                    "workflow_ref": request.workflow_ref,
                    "task_id": request.task_id,
                    "task_ref": candidate.get("task_ref") or "",
                    "task_package_id": package_id,
                    "task_mode": candidate.get("task_mode") or "copilot",
                    "executor_binding": executor_binding,
                    "status": "waiting_agent",
                    "revision": 1,
                    "created_at": created_at,
                    "updated_at": created_at,
                },
            )
            stored = self.store.put("agent_task_packages", package_id, package)
            return {**stored, "replayed": False}

    def _expire_lease(self, package: dict[str, Any]) -> dict[str, Any]:
        if package.get("status") not in {"claimed", "running"}:
            return package
        lease = package.get("lease") if isinstance(package.get("lease"), dict) else {}
        expires_at = _parse_time(str(lease.get("expires_at") or ""))
        if expires_at is None or expires_at > datetime.now(timezone.utc):
            return package
        package.update(
            {
                "status": "expired",
                "current_state": "expired",
                "stop_reason": "lease_expired",
                "revision": int(package.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        stored = self.store.put(
            "agent_task_packages",
            str(package["task_package_id"]),
            package,
        )
        self._sync_task_run(stored)
        return stored

    def _sync_task_run(self, package: dict[str, Any], *, store=None) -> None:
        """Keep a materialized TaskRun aligned with its claimable package."""

        task_run_id = str(package.get("task_run_id") or "")
        if not task_run_id:
            return
        target_store = store or self.store
        task_run = target_store.get("task_runs", task_run_id)
        if not task_run:
            return
        task_run.update(
            {
                "status": str(package.get("status") or task_run.get("status") or ""),
                "current_state": str(
                    package.get("current_state")
                    or package.get("status")
                    or task_run.get("current_state")
                    or ""
                ),
                "task_package_revision": int(package.get("revision") or 1),
                "work_run_id": str(package.get("work_run_id") or ""),
                "external_work_result_ref": str(
                    package.get("external_work_result_ref") or ""
                ),
                "evidence_ledger_ref": str(package.get("evidence_ledger_ref") or ""),
                "completion_record_ref": str(
                    package.get("completion_record_ref") or ""
                ),
                "outcome_id": str(package.get("outcome_id") or ""),
                "outcome_ref": str(package.get("outcome_ref") or ""),
                "stop_reason": str(package.get("stop_reason") or ""),
                "revision": int(task_run.get("revision") or 1) + 1,
                "updated_at": now_iso(),
            }
        )
        target_store.put("task_runs", task_run_id, task_run)

    def list_agent_tasks(
        self,
        principal: Principal,
        *,
        status: str = "",
        limit: int = 20,
        run_id: str = "",
        cursor: str = "",
    ) -> dict[str, Any]:
        stored = [
            self._expire_lease(item)
            for item in self.store.list(
                "agent_task_packages",
                employee_id=principal.employee_id,
                limit=1000,
            )
        ]
        stored_ids = {str(item.get("task_package_id") or "") for item in stored}
        candidates = [
            item for item in self._task_candidates(principal) if item["task_package_id"] not in stored_ids
        ]
        bulk = [self._bulk_task_view(principal,str(item['task_package_id']))
                for item in self.store.list('bulk_migration_task_packages',
                    employee_id=principal.employee_id,limit=1000000)]
        items = [*stored, *candidates, *bulk]
        if run_id:
            items = [item for item in items if item.get('run_id') == run_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        items.sort(key=lambda item: (str(item.get("status") or ""), str(item.get("task_ref") or ""),
                                    str(item.get('task_package_id') or '')))
        snapshot = _checksum({'principal':principal.employee_id,'run_id':run_id,'status':status,
            'items':[(item['task_package_id'],item.get('revision'),item.get('status'),
                      item.get('input_fingerprint')) for item in items]})
        offset = 0
        if cursor:
            try:
                if len(cursor)>100:raise ValueError()
                bound,number = cursor.split(':')
                offset = int(number)
                if bound != snapshot or offset<0 or offset>len(items):raise ValueError()
            except ValueError as error:
                raise HTTPException(status_code=409,detail={'code':'TASK_PAGE_SNAPSHOT_STALE'}) from error
        page = items[offset:offset+max(1,min(limit,100))]
        next_offset = offset+len(page)
        return {'count':len(page),'items':page,'total_count':len(items),'snapshot_digest':'sha256:'+snapshot,
                'next_cursor':f'{snapshot}:{next_offset}' if next_offset<len(items) else None,
                'ui_url':f'/ontology/migrations/{run_id}' if run_id else '/ontology/migrations'}

    def get_agent_task(self, principal: Principal, task_package_id: str) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_view(principal,task_package_id)
        return self._expire_lease(self._task_package(principal, task_package_id))

    def _bulk_task_view(self, principal, task_package_id):
        from ..governed_runtime.bulk_migration import BulkMigrationPolicyError
        try:
            return self.bulk_migration_tasks.view(principal.employee_id,task_package_id)
        except BulkMigrationPolicyError as error:
            code = str(error)
            raise HTTPException(status_code=404 if 'ACCESS_DENIED' in code else 409,
                                detail={'code':code}) from error

    def _bulk_task_control(self, principal, task_package_id, operation, request):
        from ..governed_runtime.bulk_migration import BulkMigrationPolicyError
        try:
            return self.bulk_migration_tasks.control(principal.employee_id,task_package_id,operation,request)
        except ValueError as error:
            # Do not re-emit arbitrary submitted content from a validation error.
            code = str(error) if isinstance(error,BulkMigrationPolicyError) else 'BULK_TASK_OUTPUT_CONTRACT_INVALID'
            raise HTTPException(status_code=404 if 'ACCESS_DENIED' in code else 409,
                                detail={'code':code}) from error

    def _task_replay(
        self,
        *,
        package_id: str,
        operation: str,
        idempotency_key: str,
        principal_id: str,
        request,
        store=None,
    ) -> dict[str, Any] | None:
        fingerprint = self._task_request_fingerprint(principal_id, request)
        key = _stable_id("taskreplay", package_id, operation, idempotency_key)
        row = (store or self.store).get("agent_task_idempotency", key)
        if row and isinstance(row.get("response"), dict):
            if row.get('request_fingerprint') is None:
                raise HTTPException(status_code=409, detail={'code':'TASK_REPLAY_LEGACY_UNBOUND'})
            if row['request_fingerprint'] != fingerprint:
                raise HTTPException(status_code=409, detail={'code':'TASK_IDEMPOTENCY_BODY_CONFLICT'})
            return {**row["response"], "replayed": True}
        return None

    @staticmethod
    def _task_request_fingerprint(principal_id, request):
        from ..governed_runtime.semantic_binding_contract import semantic_digest
        try:
            return semantic_digest({'contract_version':'boi/task-request-binding@1',
                'principal_id':principal_id, 'request_type':type(request).__name__,
                # Validate before Pydantic's JSON projection can turn NaN into
                # null, which would collide with a different submitted body.
                'body':request.model_dump(mode='python')})
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail={'code':'TASK_REQUEST_NOT_CANONICAL_JSON'}) from None

    def _store_task_replay(
        self,
        *,
        package: dict[str, Any],
        operation: str,
        idempotency_key: str,
        principal_id: str,
        request,
        response: dict[str, Any],
        store=None,
    ) -> None:
        key = _stable_id(
            "taskreplay",
            str(package["task_package_id"]),
            operation,
            idempotency_key,
        )
        (store or self.store).put(
            "agent_task_idempotency",
            key,
            {
                "idempotency_id": key,
                "employee_id": package["employee_id"],
                "task_package_id": package["task_package_id"],
                "operation": operation,
                "request_fingerprint": self._task_request_fingerprint(principal_id, request),
                "response": response,
                "created_at": now_iso(),
            },
        )

    @staticmethod
    def _revision(package: dict[str, Any], expected_revision: int) -> int:
        revision = int(package.get("revision") or 1)
        if revision != expected_revision:
            raise HTTPException(
                status_code=409,
                detail={"code": "revision_conflict", "current_revision": revision},
            )
        return revision

    def claim_agent_task(
        self,
        principal: Principal,
        task_package_id: str,
        request: AgentTaskClaimRequest,
    ) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_control(principal,task_package_id,'claim',request)
        with self._lock:
            from ..governed_runtime.bulk_migration_transaction import MigrationWriteSet
            buffer = MigrationWriteSet(self.store)
            buffer.get('agent_task_packages',task_package_id)
            package = self._require_owner(
                principal,
                self._task_package(principal, task_package_id),
                label="agent task package",
                mutation=True,
            )
            replay = self._task_replay(
                package_id=task_package_id,
                operation="claim",
                idempotency_key=request.idempotency_key,
                principal_id=principal.employee_id,
                request=request,
                store=buffer,
            )
            if replay:
                return replay
            revision = self._revision(package, request.expected_revision)
            if package.get("status") not in {"available", "waiting_agent", "released", "expired"}:
                raise HTTPException(status_code=409, detail="agent task is not available")
            claimed_at = datetime.now(timezone.utc)
            lease_id = _stable_id("lease", task_package_id, request.idempotency_key)
            package.update(
                {
                    "status": "claimed",
                    "current_state": "claimed",
                    "claimed_by": principal.employee_id,
                    "work_run_id": _stable_id("externalrun", task_package_id, lease_id),
                    "lease": {
                        "lease_id": lease_id,
                        "claimed_at": claimed_at.isoformat(),
                        "expires_at": (
                            claimed_at + timedelta(seconds=request.lease_seconds)
                        ).isoformat(),
                        "heartbeat_at": claimed_at.isoformat(),
                    },
                    "revision": revision + 1,
                    "updated_at": now_iso(),
                    "state_history": [
                        *list(package.get("state_history") or []),
                        {"state": "claimed", "at": now_iso()},
                    ],
                }
            )
            package = buffer.put("agent_task_packages", task_package_id, package)
            self._sync_task_run(package,store=buffer)
            response = {**package, "replayed": False}
            self._store_task_replay(
                package=package,
                operation="claim",
                idempotency_key=request.idempotency_key,
                principal_id=principal.employee_id,
                request=request,
                response=response,
                store=buffer,
            )
            if not self.store.atomic_compare_and_write(buffer.writes()):
                raise HTTPException(status_code=409,detail={'code':'task_claim_revision_conflict'})
            self._notify_runtime_relations(principal)
            return response

    def _active_lease(
        self,
        package: dict[str, Any],
        *,
        lease_id: str,
    ) -> dict[str, Any]:
        package = self._expire_lease(package)
        if package.get("status") == "expired":
            raise HTTPException(status_code=409, detail="agent task lease has expired")
        lease = package.get("lease") if isinstance(package.get("lease"), dict) else {}
        if str(lease.get("lease_id") or "") != lease_id:
            raise HTTPException(status_code=403, detail="agent task lease does not match")
        return lease

    def heartbeat_agent_task(
        self,
        principal: Principal,
        task_package_id: str,
        request: AgentTaskHeartbeatRequest,
    ) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_control(principal,task_package_id,'heartbeat',request)
        with self._lock:
            package = self._require_owner(
                principal,
                self.store.get("agent_task_packages", task_package_id),
                label="agent task package",
                mutation=True,
            )
            revision = self._revision(package, request.expected_revision)
            lease = self._active_lease(package, lease_id=request.lease_id)
            heartbeat_at = datetime.now(timezone.utc)
            package.update(
                {
                    "status": "running",
                    "current_state": "running",
                    "lease": {
                        **lease,
                        "heartbeat_at": heartbeat_at.isoformat(),
                        "expires_at": (
                            heartbeat_at + timedelta(seconds=request.extend_seconds)
                        ).isoformat(),
                    },
                    "revision": revision + 1,
                    "updated_at": now_iso(),
                }
            )
            stored = self.store.put("agent_task_packages", task_package_id, package)
            self._sync_task_run(stored)
            return stored

    def _verified_source_refs(
        self,
        principal: Principal,
        refs: list[str],
    ) -> tuple[list[str], list[str]]:
        canonical = {
            item.record_id
            for item in self.repository.authoritative_records(principal, include_drafts=False)
        }
        operational: set[str] = set()
        for collection, key_field in (
            ("artifacts", "artifact_id"),
            ("outcomes", "boi_ref"),
            ("event_occurrences", "event_occurrence_id"),
            ("completion_records", "completion_id"),
        ):
            operational.update(
                str(item.get(key_field) or "")
                for item in self.store.list(
                    collection,
                    employee_id=principal.employee_id,
                    limit=10_000,
                )
                if str(item.get(key_field) or "")
            )
        verified = list(dict.fromkeys(ref for ref in refs if ref in canonical or ref in operational))
        rejected = list(dict.fromkeys(ref for ref in refs if ref not in set(verified)))
        return verified, rejected

    def submit_agent_task(
        self,
        principal: Principal,
        task_package_id: str,
        request: AgentTaskSubmitRequest,
    ) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_control(principal,task_package_id,'submit',request)
        domain_package = self.store.get('agent_task_packages',task_package_id)
        if domain_package and domain_package.get('domain_execution_contract'):
            self._require_owner(principal,domain_package,label='agent task package',mutation=True)
            raise HTTPException(status_code=409,detail={'code':'DOMAIN_TASK_EXECUTION_RECEIPTS_REQUIRED'})
        with self._lock:
            package = self._require_owner(
                principal,
                self.store.get("agent_task_packages", task_package_id),
                label="agent task package",
                mutation=True,
            )
            replay = self._task_replay(
                package_id=task_package_id,
                operation="submit",
                idempotency_key=request.idempotency_key,
                principal_id=principal.employee_id,
                request=request,
            )
            if replay:
                return replay
            revision = self._revision(package, request.expected_revision)
            if package.get("status") not in {"claimed", "running"}:
                raise HTTPException(status_code=409, detail="agent task cannot be submitted in this state")
            self._active_lease(package, lease_id=request.lease_id)
            summary = str(request.result.get("summary") or "").strip()
            result_status = str(request.result.get("status") or "").strip()
            if not summary or not result_status:
                raise HTTPException(
                    status_code=422,
                    detail="external result requires status and summary",
                )
            verified_refs, rejected_refs = self._verified_source_refs(
                principal,
                request.evidence_refs,
            )
            if rejected_refs or not verified_refs:
                stop_reason = "missing_evidence" if not request.evidence_refs else "invalid_evidence"
                package.update(
                    {
                        "status": "revision_required",
                        "current_state": "revision_required",
                        "stop_reason": stop_reason,
                        "evidence_rejection": {
                            "rejected_refs": rejected_refs,
                            "submitted_count": len(request.evidence_refs),
                        },
                        "revision": revision + 1,
                        "updated_at": now_iso(),
                        "state_history": [
                            *list(package.get("state_history") or []),
                            {
                                "state": "revision_required",
                                "reason": stop_reason,
                                "at": now_iso(),
                            },
                        ],
                    }
                )
                package = self.store.put("agent_task_packages", task_package_id, package)
                self._sync_task_run(package)
                response = {**package, "replayed": False}
                self._store_task_replay(
                    package=package,
                    operation="submit",
                    idempotency_key=request.idempotency_key,
                    principal_id=principal.employee_id,
                    request=request,
                    response=response,
                )
                return response
            external_result_id = _stable_id(
                "externalresult",
                task_package_id,
                request.idempotency_key,
            )
            ledger_id = _stable_id("ledger", external_result_id)
            self.store.put(
                "external_work_results",
                external_result_id,
                {
                    "external_work_result_id": external_result_id,
                    "employee_id": principal.employee_id,
                    "task_package_id": task_package_id,
                    "work_run_id": package.get("work_run_id") or "",
                    "agent_ref": request.agent_ref or f"external-agent:{principal.auth_source}",
                    "result": request.result,
                    "evidence_refs": verified_refs,
                    "verification_status": "harness_verifying",
                    "raw_prompt_stored": False,
                    "created_at": now_iso(),
                },
            )
            self.store.put(
                "evidence_ledger",
                ledger_id,
                {
                    "ledger_id": ledger_id,
                    "employee_id": principal.employee_id,
                    "work_run_id": package.get("work_run_id") or "",
                    "evidence_id": external_result_id,
                    "kind": "external_work_result",
                    "title": "외부 Agent 제출 결과",
                    "summary": summary,
                    "source": "external_agent",
                    "authority": "submitted_for_verification",
                    "verification": "pending_harness_verification",
                    "created_at": now_iso(),
                    "updated_at": now_iso(),
                },
            )
            usage_id = _stable_id("usage", external_result_id, principal.employee_id)
            self.store.put(
                "usage_records",
                usage_id,
                {
                    "usage_id": usage_id,
                    "employee_id": principal.employee_id,
                    "person_ref": f"person:{principal.employee_id}",
                    "task_ref": str(package.get("task_ref") or ""),
                    "work_run_id": str(package.get("work_run_id") or ""),
                    "agent_definition_ref": "",
                    "agent_deployment_ref": request.agent_ref or f"agent-deployment:external:{principal.auth_source}",
                    "system_ref": "system:boi-wiki",
                    "connector_refs": [],
                    "action_refs": list(package.get("allowed_actions") or []),
                    "skill_refs": list(package.get("allowed_skills") or []),
                    "harness_refs": ["harness:task.runtime"],
                    "purpose": str(package.get("goal") or "외부 Agent Task 수행"),
                    "version": "task-package/v1",
                    "result_refs": [external_result_id],
                    "source": "external_result",
                    "provenance": "operational_verified",
                    "visibility": "private",
                    "allowed_employee_ids": [principal.employee_id],
                    "allowed_team_ids": list(principal.teams),
                    "occurred_at": now_iso(),
                },
            )
            package.update(
                {
                    # The response below exposes the accepted `submitted`
                    # transition while the durable package immediately moves
                    # to the separately observable harness verification state.
                    "status": "harness_verifying",
                    "current_state": "harness_verifying",
                    "external_work_result_ref": external_result_id,
                    "evidence_ledger_ref": ledger_id,
                    "completion_record_ref": "",
                    "submission_idempotency_key": request.idempotency_key,
                    "stop_reason": "",
                    "orphan_workers": 0,
                    "revision": revision + 1,
                    "updated_at": now_iso(),
                    "state_history": [
                        *list(package.get("state_history") or []),
                        {"state": "submitted", "at": now_iso()},
                        {"state": "harness_verifying", "at": now_iso()},
                    ],
                }
            )
            package = self.store.put("agent_task_packages", task_package_id, package)
            self._sync_task_run(package)
            response = {
                **package,
                "status": "submitted",
                "current_state": "submitted",
                "persisted_status": "harness_verifying",
                "replayed": False,
            }
            self._store_task_replay(
                package=package,
                operation="submit",
                idempotency_key=request.idempotency_key,
                principal_id=principal.employee_id,
                request=request,
                response=response,
            )
            return response

    def verify_agent_task(
        self,
        principal: Principal,
        task_package_id: str,
        request: AgentTaskVerifyRequest,
    ) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            self._bulk_task_view(principal,task_package_id)
            raise HTTPException(status_code=403,detail={'code':'BULK_TASK_DETERMINISTIC_EVALUATOR_REQUIRED'})
        domain_package = self.store.get('agent_task_packages',task_package_id)
        if domain_package and domain_package.get('domain_execution_contract'):
            self._require_owner(principal,domain_package,label='agent task package',mutation=True)
            raise HTTPException(status_code=409,detail={'code':'DOMAIN_TASK_EXECUTION_RECEIPTS_REQUIRED'})
        with self._lock:
            package = self._require_owner(
                principal,
                self.store.get("agent_task_packages", task_package_id),
                label="agent task package",
                mutation=True,
            )
            revision = self._revision(package, request.expected_revision)
            if package.get("status") != "harness_verifying":
                raise HTTPException(
                    status_code=409,
                    detail="agent task is not waiting for harness verification",
                )
            external_result_id = str(package.get("external_work_result_ref") or "")
            ledger_id = str(package.get("evidence_ledger_ref") or "")
            external_result = self.store.get("external_work_results", external_result_id)
            ledger = self.store.get("evidence_ledger", ledger_id)
            if not external_result or not ledger:
                raise HTTPException(
                    status_code=409,
                    detail="submitted result evidence is unavailable",
                )
            if request.decision != "accept":
                next_status = "revision_required" if request.decision == "revise" else "failed"
                stop_reason = (
                    "harness_revision_required"
                    if request.decision == "revise"
                    else "harness_verification_rejected"
                )
                external_result.update(
                    {
                        "verification_status": next_status,
                        "verification_note": request.note,
                        "verified_at": now_iso(),
                    }
                )
                ledger.update(
                    {
                        "verification": "rejected",
                        "updated_at": now_iso(),
                    }
                )
                self.store.put("external_work_results", external_result_id, external_result)
                self.store.put("evidence_ledger", ledger_id, ledger)
                package.update(
                    {
                        "status": next_status,
                        "current_state": next_status,
                        "stop_reason": stop_reason,
                        "revision": revision + 1,
                        "updated_at": now_iso(),
                        "state_history": [
                            *list(package.get("state_history") or []),
                            {"state": next_status, "reason": stop_reason, "at": now_iso()},
                        ],
                    }
                )
                stored = self.store.put("agent_task_packages", task_package_id, package)
                self._sync_task_run(stored)
                return stored

            verified_refs = list(external_result.get("evidence_refs") or [])
            if not verified_refs:
                raise HTTPException(status_code=409, detail="verified evidence is required")
            completion_id = _stable_id("completion", external_result_id)
            outcome_id = _stable_id("outcome", external_result_id, completion_id)
            outcome_ref = f"boi:runtime:outcome:{outcome_id}"
            completed_at = now_iso()
            result_summary = str(
                (external_result.get("result") or {}).get("summary") or ""
            )
            external_result.update(
                {
                    "verification_status": "completed",
                    "verification_note": request.note,
                    "verified_by": principal.employee_id,
                    "verified_at": completed_at,
                    "outcome_id": outcome_id,
                    "outcome_ref": outcome_ref,
                }
            )
            ledger.update(
                {
                    "authority": "verified_submission",
                    "verification": "verified",
                    "updated_at": now_iso(),
                }
            )
            self.store.put("external_work_results", external_result_id, external_result)
            self.store.put("evidence_ledger", ledger_id, ledger)
            self.store.put(
                "completion_records",
                completion_id,
                {
                    "completion_id": completion_id,
                    "employee_id": principal.employee_id,
                    "work_run_id": package.get("work_run_id") or "",
                    "task_ref": package.get("task_ref") or "",
                    "task_mode": package.get("task_mode") or "copilot",
                    "decision": "complete",
                    "summary": result_summary,
                    "evidence_refs": verified_refs,
                    "used_evidence_refs": verified_refs,
                    "evidence_ledger_ids": [ledger_id],
                    "external_work_result_id": external_result_id,
                    "verifier": principal.employee_id,
                    "execution_result": result_summary,
                    "completion_criteria": {
                        "status": "passed",
                        "source": "external_agent_harness_verification",
                    },
                    "exceptions": [],
                    "incomplete_items": [],
                    "next_work_lesson": result_summary,
                    "outcome_id": outcome_id,
                    "outcome_ref": outcome_ref,
                    "created_at": completed_at,
                },
            )
            self.store.put(
                "outcomes",
                outcome_id,
                {
                    "outcome_id": outcome_id,
                    "boi_ref": outcome_ref,
                    "employee_id": principal.employee_id,
                    "work_run_id": package.get("work_run_id") or "",
                    "workflow_run_id": package.get("workflow_run_id") or "",
                    "task_ref": package.get("task_ref") or "",
                    "task_run_ids": [package.get("task_run_id")]
                    if package.get("task_run_id")
                    else [],
                    "status": "completed",
                    "quality_state": "verified",
                    "verifier": f"person:{principal.employee_id}",
                    "completion_record_id": completion_id,
                    "evidence_ledger_ids": [ledger_id],
                    "executor_result_refs": [external_result_id],
                    "result_summary": result_summary,
                    "next_work_lesson": result_summary,
                    "visibility": "private",
                    "allowed_employee_ids": [principal.employee_id],
                    "allowed_team_ids": list(principal.teams),
                    "provenance": "human_verified",
                    "created_at": completed_at,
                },
            )
            usage_id = _stable_id("usage", external_result_id, principal.employee_id)
            usage = self.store.get("usage_records", usage_id) or {}
            usage["result_refs"] = list(
                dict.fromkeys(
                    [
                        *list(usage.get("result_refs") or []),
                        external_result_id,
                        completion_id,
                        outcome_id,
                    ]
                )
            )
            self.store.put("usage_records", usage_id, usage)
            package.update(
                {
                    "status": "completed",
                    "current_state": "completed",
                    "completion_record_ref": completion_id,
                    "outcome_id": outcome_id,
                    "outcome_ref": outcome_ref,
                    "stop_reason": "",
                    "orphan_workers": 0,
                    "revision": revision + 1,
                    "updated_at": now_iso(),
                    "state_history": [
                        *list(package.get("state_history") or []),
                        {"state": "completed", "at": now_iso()},
                    ],
                }
            )
            stored = self.store.put("agent_task_packages", task_package_id, package)
            self._sync_task_run(stored)
            submission_key = str(package.get("submission_idempotency_key") or "")
            if submission_key:
                replay_key = _stable_id(
                    "taskreplay",
                    task_package_id,
                    "submit",
                    submission_key,
                )
                replay_row = self.store.get("agent_task_idempotency", replay_key)
                if replay_row and isinstance(replay_row.get("response"), dict):
                    replay_row["response"] = {
                        **replay_row["response"],
                        "completion_record_ref": completion_id,
                        "verification_status": "completed",
                    }
                    self.store.put("agent_task_idempotency", replay_key, replay_row)
            self._notify_runtime_relations(principal)
            return stored

    def release_agent_task(
        self,
        principal: Principal,
        task_package_id: str,
        request: AgentTaskReleaseRequest,
    ) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_control(principal,task_package_id,'release',request)
        with self._lock:
            package = self._require_owner(
                principal,
                self.store.get("agent_task_packages", task_package_id),
                label="agent task package",
                mutation=True,
            )
            revision = self._revision(package, request.expected_revision)
            if package.get("status") not in {"claimed", "running"}:
                raise HTTPException(status_code=409, detail="agent task cannot be released in this state")
            self._active_lease(package, lease_id=request.lease_id)
            package.update(
                {
                    "status": "released",
                    "current_state": "released",
                    "release_reason": request.reason,
                    "lease": {},
                    "revision": revision + 1,
                    "updated_at": now_iso(),
                }
            )
            stored = self.store.put("agent_task_packages", task_package_id, package)
            self._sync_task_run(stored)
            return stored

    def cancel_agent_task(
        self,
        principal: Principal,
        task_package_id: str,
        request: AgentTaskCancelRequest,
    ) -> dict[str, Any]:
        if self.store.get('bulk_migration_task_packages',task_package_id) is not None:
            return self._bulk_task_control(principal,task_package_id,'cancel',request)
        with self._lock:
            package = self._require_owner(
                principal,
                self.store.get("agent_task_packages", task_package_id),
                label="agent task package",
                mutation=True,
            )
            revision = self._revision(package, request.expected_revision)
            package.update(
                {
                    "status": "cancelled",
                    "current_state": "cancelled",
                    "stop_reason": "user_cancelled",
                    "cancel_reason": request.reason,
                    "revision": revision + 1,
                    "updated_at": now_iso(),
                }
            )
            stored = self.store.put("agent_task_packages", task_package_id, package)
            self._sync_task_run(stored)
            return stored
