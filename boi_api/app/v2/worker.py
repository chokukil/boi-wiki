from __future__ import annotations

import json
import os
import signal
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .config import AgentV2Settings, deep_subagent_budget_limit
from .model_gateway import begin_model_usage, finish_model_usage, require_lmstudio_models_preloaded
from .models import ArtifactRef, Principal, WorkContextPack, WorkRoutineTriggerRequest
from .service import AgentV2Service, new_id
from .store import now_iso


class DeepJobCancelled(RuntimeError):
    pass


class DeepJobTimedOut(RuntimeError):
    pass


def latest_assistant_text(messages: list[Any]) -> str:
    """Return the newest non-empty assistant text, ignoring terminal tool frames."""

    for message in reversed(messages):
        if isinstance(message, dict):
            message_kind = str(message.get("role") or message.get("type") or "").lower()
            content = message.get("content")
        else:
            message_kind = str(getattr(message, "type", "") or "").lower()
            content = getattr(message, "content", None)
        if message_kind not in {"ai", "assistant"}:
            continue
        if isinstance(content, str):
            if content.strip():
                return content.strip()
            continue
        if not isinstance(content, list):
            continue
        text_blocks: list[str] = []
        for item in content:
            if isinstance(item, str):
                text_blocks.append(item)
                continue
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "") not in {"text", "output_text"}:
                continue
            text_value = item.get("text") or item.get("content")
            if isinstance(text_value, str):
                text_blocks.append(text_value)
        rendered = "\n".join(text_blocks).strip()
        if rendered:
            return rendered
    return ""


def ensure_exact_evidence_ledger(content: str, evidence_ledger: dict[str, dict[str, str]]) -> str:
    if not evidence_ledger or any(evidence_id in content for evidence_id in evidence_ledger):
        return content
    rows = [
        f"- `{evidence_id}` - {str(item.get('title') or '근거 자료')}"
        for evidence_id, item in list(evidence_ledger.items())[:12]
    ]
    return (
        content.rstrip()
        + "\n\n## 근거 모음\n\n"
        + "아래는 이 초안에 제공된 ACL 검증 근거입니다. 주장별 연결은 검토 단계에서 확인합니다.\n\n"
        + "\n".join(rows)
    )


def execute_boi_api_routine_target(
    settings: AgentV2Settings,
    routine: dict[str, Any],
    request: WorkRoutineTriggerRequest,
    principal: Principal,
) -> dict[str, Any]:
    target_kind = str(routine.get("target_kind") or "")
    target_ref = str(routine.get("target_ref") or "")
    if target_kind != "business_event" or not target_ref:
        raise RuntimeError(f"unsupported scheduled system target: {target_kind or 'missing'}")
    if not settings.boi_api_url or not settings.service_token:
        raise RuntimeError("BOI_API_URL and BOI_API_SERVICE_TOKEN are required for scheduled system targets")
    payload = {
        "routine_id": str(routine.get("routine_id") or ""),
        "triggered_at": now_iso(),
        "source_fingerprint": request.source_fingerprint,
        "payload": {**(routine.get("input") or {}), **request.input},
        "employee_id": principal.employee_id,
    }
    try:
        response = httpx.post(
            f"{settings.boi_api_url}/api/internal/business-event-definitions/{target_ref}/scheduled-evaluate",
            headers={"x-service-token": settings.service_token, "Content-Type": "application/json"},
            json=payload,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"scheduled business event API call failed: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"scheduled business event API returned {response.status_code}: {response.text[:500]}")
    try:
        body = response.json()
    except ValueError as exc:
        raise RuntimeError("scheduled business event API returned invalid JSON") from exc
    return body if isinstance(body, dict) else {"status": "failed", "message": "invalid scheduled result"}


class DeepWorkRunner:
    def __init__(self, service: AgentV2Service):
        self.service = service
        self.worker_id = os.getenv("BOI_AGENT_V2_WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"

    def run_once(self) -> bool:
        runtime = self._runtime_status()
        self.service.store.heartbeat(
            self.worker_id,
            {**runtime, "version": "2.0"},
        )
        routine_results = self.service.run_due_work_routines(limit=2)
        job = self.service.store.claim_job(self.worker_id)
        if not job:
            return bool(routine_results)
        job_id = str(job.get("job_id") or "")
        try:
            result = self._execute(job)
            artifact_id = new_id("artifact")
            work_session_id = str(job.get("work_session_id") or "")
            artifact_row = {
                "artifact_id": artifact_id,
                "employee_id": job.get("employee_id"),
                "capability_id": job.get("capability_id"),
                "artifact_type": "deep_work_draft",
                "status": "draft",
                "title": str(result.get("title") or "심층 작업 결과"),
                "draft": result,
                "work_session_id": work_session_id,
                "revision": 1,
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            self.service.store.put(
                "artifacts",
                artifact_id,
                artifact_row,
            )
            job.pop("error", None)
            job.pop("failed_at", None)
            usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}
            job.update(
                {
                    "status": "completed",
                    "artifact_id": artifact_id,
                    "completed_at": now_iso(),
                    "message": "검토 가능한 심층 작업 draft를 만들었습니다.",
                    "independent_review": result.get("independent_review") or {},
                    "usage_ref": str(usage.get("usage_id") or ""),
                    "usage": usage,
                }
            )
            self.service.store.put("jobs", job_id, job)
            principal = self._principal(job)
            if job.get("work_run_id"):
                self.service.learning.finish_deep_job(
                    principal,
                    work_run_id=str(job["work_run_id"]),
                    artifact=artifact_row,
                    result=result,
                )
            if work_session_id:
                session = self.service.store.get("work_sessions", work_session_id)
                if session and self.service._owns(principal, session):
                    artifact_ref = ArtifactRef(
                        artifact_id=artifact_id,
                        artifact_type="deep_work_draft",
                        title=str(result.get("title") or "심층 작업 결과"),
                        status="draft",
                        url=f"/agent?session={work_session_id}&artifact={artifact_id}",
                        preview=str(result.get("body") or "")[:1200],
                        metadata={"capability_id": job.get("capability_id") or "deep.research", "revision": 1},
                    )
                    self.service._append_session_message(
                        principal,
                        work_session_id,
                        role="assistant",
                        display_text="심층 작업 초안이 준비되었습니다. 근거와 내용을 확인해주세요.",
                        run_id=str(job.get("run_id") or ""),
                        capability_id=str(job.get("capability_id") or "deep.research"),
                        artifact_refs=[artifact_ref],
                        next_actions=self.service._next_actions(
                            work_session_id=work_session_id,
                            artifacts=[artifact_ref],
                            evidence=[],
                        ),
                    )
                    session.update(
                        {
                            "active_artifact_id": artifact_id,
                            "revision": int(session.get("revision") or 1) + 1,
                            "updated_at": now_iso(),
                        }
                    )
                    self.service.store.put("work_sessions", work_session_id, session)
            return True
        except DeepJobCancelled:
            current = self.service.store.get("jobs", job_id) or job
            current.update(
                {
                    "status": "cancelled",
                    "cancelled_at": current.get("cancelled_at") or now_iso(),
                    "message": "심층 작업이 취소되었습니다.",
                }
            )
            self.service.store.put("jobs", job_id, current)
            self._fail_work_run(current, "심층 작업이 취소되었습니다.")
            return True
        except DeepJobTimedOut as exc:
            job.update(
                {
                    "status": "failed",
                    "attempt": int(job.get("attempt") or 0) + 1,
                    "error": f"{type(exc).__name__}: {exc}",
                    "failed_at": now_iso(),
                    "message": "심층 작업 제한 시간을 초과했습니다.",
                }
            )
            self.service.store.put("jobs", job_id, job)
            self._fail_work_run(job, "심층 작업 제한 시간을 초과했습니다.")
            return True
        except Exception as exc:
            attempt = int(job.get("attempt") or 0) + 1
            retry = attempt < int(job.get("max_attempts") or 2)
            job.update(
                {
                    "status": "queued" if retry else "failed",
                    "attempt": attempt,
                    "error": f"{type(exc).__name__}: {exc}",
                    "failed_at": now_iso(),
                    "message": "재시도 대기" if retry else "심층 작업을 완료하지 못했습니다.",
                }
            )
            self.service.store.put("jobs", job_id, job)
            if not retry:
                self._fail_work_run(job, "심층 작업을 완료하지 못했습니다.")
            return True

    @staticmethod
    def _principal(job: dict[str, Any]) -> Principal:
        return Principal(
            employee_id=str(job.get("employee_id") or ""),
            display_name=str(job.get("employee_id") or ""),
            teams=[str(item) for item in job.get("principal_teams") or []],
            roles=[str(item) for item in job.get("principal_roles") or []],
            auth_source="deep_worker",
        )

    def _fail_work_run(self, job: dict[str, Any], message: str) -> None:
        work_run_id = str(job.get("work_run_id") or "")
        if not work_run_id:
            return
        try:
            self.service.learning.fail_run(self._principal(job), work_run_id, message)
        except Exception:
            return

    def _runtime_status(self) -> dict[str, Any]:
        try:
            import deepagents  # noqa: F401
            deepagents_ready = True
        except Exception:
            deepagents_ready = False
        provider = self.service.settings.model_provider
        try:
            if provider == "anthropic":
                import langchain_anthropic  # noqa: F401
            else:
                import langchain_openai  # noqa: F401
            model_adapter_ready = True
        except Exception:
            model_adapter_ready = False
        return {
            "deepagents": deepagents_ready,
            "model_adapter": model_adapter_ready,
            "routine_target": bool(self.service.settings.boi_api_url and self.service.settings.service_token),
            "anthropic_adapter": provider == "anthropic" and model_adapter_ready,
            "openai_adapter": provider in {"openai_responses", "openai_compatible"} and model_adapter_ready,
            "deep_max_input_tokens": self.service.settings.deep_max_input_tokens,
        }

    def _deepagents_available(self) -> bool:
        status = self._runtime_status()
        return status["deepagents"] and status["model_adapter"]

    def _deep_model_adapter(self) -> Any:
        settings = self.service.settings
        require_lmstudio_models_preloaded(settings)
        if settings.model_provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            kwargs: dict[str, Any] = {
                "model": settings.deep_model,
                "base_url": settings.model_base_url or None,
                "api_key": settings.model_api_key or None,
                "max_tokens": settings.model_max_output_tokens,
                "timeout": 60,
                "max_retries": 1,
            }
            if "profile" in ChatAnthropic.model_fields:
                kwargs["profile"] = {
                    "max_input_tokens": settings.deep_max_input_tokens,
                    "max_output_tokens": settings.model_max_output_tokens,
                }
            return ChatAnthropic(**kwargs)
        from langchain_openai import ChatOpenAI

        class GuardedChatOpenAI(ChatOpenAI):
            def _generate(self, *args: Any, **kwargs: Any) -> Any:
                require_lmstudio_models_preloaded(settings)
                return super()._generate(*args, **kwargs)

            def _stream(self, *args: Any, **kwargs: Any) -> Any:
                require_lmstudio_models_preloaded(settings)
                return super()._stream(*args, **kwargs)

            async def _agenerate(self, *args: Any, **kwargs: Any) -> Any:
                require_lmstudio_models_preloaded(settings)
                return await super()._agenerate(*args, **kwargs)

            async def _astream(self, *args: Any, **kwargs: Any) -> Any:
                require_lmstudio_models_preloaded(settings)
                async for item in super()._astream(*args, **kwargs):
                    yield item

        kwargs = {
            "model": settings.deep_model,
            "base_url": settings.model_base_url or None,
            "api_key": settings.model_api_key or "not-needed",
            "reasoning_effort": settings.model_reasoning_effort or None,
            "max_completion_tokens": settings.model_max_output_tokens,
            "timeout": 60,
            "max_retries": 1,
            "use_responses_api": False,
        }
        if "profile" in GuardedChatOpenAI.model_fields:
            kwargs["profile"] = {
                "max_input_tokens": settings.deep_max_input_tokens,
                "max_output_tokens": settings.model_max_output_tokens,
                "reasoning_output": bool(settings.model_reasoning_effort not in {"", "none"}),
                "tool_calling": True,
                "structured_output": True,
            }
        return GuardedChatOpenAI(**kwargs)

    def _execute(self, job: dict[str, Any]) -> dict[str, Any]:
        if not self._deepagents_available():
            raise RuntimeError("deepagents package is unavailable")
        from deepagents import (
            GeneralPurposeSubagentProfile,
            HarnessProfile,
            create_deep_agent,
            register_harness_profile,
        )
        from langchain_core.callbacks import UsageMetadataCallbackHandler

        principal = self._principal(job)
        context_row = self.service.store.get("contexts", str(job.get("context_id") or "")) or {}
        context = WorkContextPack.model_validate(context_row)
        pilot_mode = bool(job.get("pilot_mode", True))
        max_tool_calls = max(1, min(int(job.get("max_tool_calls") or 5), 5 if pilot_mode else 12))
        token_budget = max(4000, min(int(job.get("token_budget") or 160000), 200000))
        subagent_budget_limit = deep_subagent_budget_limit(
            token_budget,
            self.service.settings.deep_max_input_tokens,
            hard_limit=2 if pilot_mode else 4,
        )
        max_subagents = max(
            0,
            min(
                int(job.get("max_subagents") if job.get("max_subagents") is not None else 2),
                2 if pilot_mode else 4,
                subagent_budget_limit,
            ),
        )
        max_parallelism = max(1, min(int(job.get("max_parallelism") or 2), max(1, max_subagents), 2 if pilot_mode else 4))
        require_subagent = bool(job.get("require_subagent", False))
        if require_subagent and max_subagents < 1:
            raise RuntimeError("deep-work required subagent is unavailable within the token budget")
        seen_calls: dict[str, int] = {}
        tool_calls = 0
        evidence_ledger: dict[str, dict[str, str]] = {
            item.evidence_id: {
                "evidence_id": item.evidence_id,
                "title": item.title,
                "url": item.url,
            }
            for item in context.evidence_refs
        }

        def ensure_active() -> None:
            current = self.service.store.get("jobs", str(job.get("job_id") or "")) or {}
            if current.get("status") == "cancelled":
                raise DeepJobCancelled("job was cancelled")
            expires_at = str(current.get("expires_at") or job.get("expires_at") or "")
            if expires_at:
                parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                if parsed <= datetime.now(timezone.utc):
                    raise DeepJobTimedOut("job deadline exceeded")

        def boi_search(query: str, include_history: bool = False) -> str:
            """Search ACL-visible BoI knowledge and return compact evidence references."""
            nonlocal tool_calls
            ensure_active()
            if tool_calls >= max_tool_calls:
                return json.dumps(
                    {
                        "status": "stop_and_synthesize",
                        "reason": "tool_budget_exhausted",
                        "evidence_ids": list(evidence_ledger)[:12],
                    },
                    ensure_ascii=False,
                )
            tool_calls += 1
            signature = f"search:{query.strip().lower()}"
            if seen_calls.get(signature, 0) >= 1:
                return json.dumps(
                    {
                        "status": "stop_and_synthesize",
                        "reason": "no_progress_repeated_search",
                        "evidence_ids": list(evidence_ledger)[:12],
                    },
                    ensure_ascii=False,
                )
            seen_calls[signature] = 1
            result = self.service.search.search(
                query,
                principal,
                limit=4 if pilot_mode else 6,
                include_history=include_history,
                page_ref=context.page_ref,
                task_ref=context.task_ref,
            )
            for item in result.items:
                evidence_ledger[item.evidence_id] = {
                    "evidence_id": item.evidence_id,
                    "title": item.title,
                    "url": item.url,
                }
            return json.dumps(
                [
                    {
                        "evidence_id": item.evidence_id,
                        "title": item.title,
                        "summary": item.summary[:240],
                        "url": item.url,
                    }
                    for item in result.items
                ],
                ensure_ascii=False,
            )

        def boi_get(evidence_id: str) -> str:
            """Read one ACL-visible evidence item by identifier without mutating it."""
            nonlocal tool_calls
            ensure_active()
            if tool_calls >= max_tool_calls:
                return json.dumps(
                    {
                        "status": "stop_and_synthesize",
                        "reason": "tool_budget_exhausted",
                        "evidence_ids": list(evidence_ledger)[:12],
                    },
                    ensure_ascii=False,
                )
            tool_calls += 1
            signature = f"get:{evidence_id}"
            if seen_calls.get(signature, 0) >= 1:
                return json.dumps(
                    {
                        "status": "stop_and_synthesize",
                        "reason": "no_progress_repeated_evidence_read",
                        "evidence_ids": list(evidence_ledger)[:12],
                    },
                    ensure_ascii=False,
                )
            seen_calls[signature] = 1
            record = self.service._record_for_ref(principal, evidence_id)
            if not record:
                return json.dumps({"status": "not_found", "evidence_id": evidence_id}, ensure_ascii=False)
            evidence_ledger[record.record_id] = {
                "evidence_id": record.record_id,
                "title": record.title,
                "url": record.url,
            }
            return json.dumps(
                {
                    "evidence_id": record.record_id,
                    "title": record.title,
                    "description": record.description,
                    "content": record.text[:2500],
                    "url": record.url,
                    "source": record.source,
                },
                ensure_ascii=False,
            )

        completion_labels = [item.label for item in (context.completion_design.checks if context.completion_design else [])]
        context_brief = {
            "goal": context.goal,
            "current_page": context.page_anchor.model_dump(mode="json") if context.page_anchor else None,
            "goal_anchor": context.goal_anchor.model_dump(mode="json") if context.goal_anchor else None,
            "task_ref": context.task_ref,
            "task_mode": context.task_mode.value,
            "completion_checks": completion_labels,
            "required_evidence": context.required_evidence,
            "selected_evidence": [
                {
                    "evidence_id": item.evidence_id,
                    "title": item.title,
                    "summary": item.summary[:240],
                }
                for item in context.evidence_refs[:6]
            ],
            "external_ai_summary": context.external_ai_summary[:1000],
            "external_refs": (context.context_manifest.external_refs if context.context_manifest else []),
        }
        system_prompt = (
            "You are the BoI Wiki deep-work engine. Use only boi_search and boi_get. "
            "Never mutate production data. Produce a Korean draft with an evidence ledger. "
            f"Every claim must cite an evidence_id. Use at most {max_tool_calls} tool calls and stop if "
            "additional searching makes no progress. When a tool returns status=stop_and_synthesize, do not call "
            "another tool; finish the draft from the evidence already collected. Treat the supplied current page as an "
            "interpretation anchor, while searching the full ACL-visible Wiki when needed. "
            "Set boi_search include_history=true only when past cases are relevant to the current goal. "
            f"Delegate at most {max_subagents} distinct isolated tasks and never run more than {max_parallelism} delegations in one step."
            " Return only the essential synthesis under 500 words; keep raw search results out of the final draft."
        )
        if require_subagent:
            system_prompt += (
                " The caller explicitly requires isolated verification: delegate exactly one focused evidence review "
                "before writing the final synthesis, and incorporate that review without copying its raw context."
            )
        system_prompt += " Cite exact, complete evidence_id values from the supplied ledger in the final draft."
        self.service.store.put(
            "checkpoints",
            f"{job['job_id']}:start",
            {"job_id": job["job_id"], "employee_id": job.get("employee_id"), "state": "started", "created_at": now_iso()},
        )
        model_adapter = self._deep_model_adapter()
        from langchain.agents import create_agent
        from langchain.agents.middleware import ModelCallLimitMiddleware

        def compiled_subagent(name: str, description: str, prompt: str) -> dict[str, Any]:
            runnable = create_agent(
                model=model_adapter,
                tools=[boi_search, boi_get],
                system_prompt=prompt,
                middleware=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="end")],
                name=name,
            )
            return {"name": name, "description": description, "runnable": runnable}

        subagents: list[dict[str, Any]] = []
        if max_subagents >= 1:
            subagents.append(
                compiled_subagent(
                    "evidence-researcher",
                    "Finds and compares ACL-visible BoI evidence for one focused question.",
                    "Work in an isolated context. Use only boi_search and boi_get. Return a concise Korean evidence memo "
                    "under 350 words with real evidence_id values, missing evidence, and no production changes.",
                )
            )
        if max_subagents >= 2:
            subagents.append(
                compiled_subagent(
                    "workflow-reviewer",
                    "Reviews SOP, Task, Event and Action relationships against retrieved evidence.",
                    "Work in an isolated context. Use only boi_search and boi_get. Return a concise Korean review of "
                    "workflow gaps, completion evidence, and safe next checks under 350 words. Never execute or mutate anything.",
                )
            )
        # DeepAgents otherwise adds a general-purpose subagent even when no
        # subagents were supplied. Disable that implicit path so the BoI token
        # budget and the tools exposed to the model remain the same contract.
        provider_profile = "anthropic" if self.service.settings.model_provider == "anthropic" else "openai"
        register_harness_profile(
            provider_profile,
            HarnessProfile(
                general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
            ),
        )
        parent_model_call_limit = max(
            8,
            min(max_tool_calls * 2 + 4, 14 if pilot_mode else 24),
        )
        graph_recursion_limit = min(
            64,
            max(32, parent_model_call_limit * 6 + max_subagents * 4),
        )
        agent = create_deep_agent(
            model=model_adapter,
            tools=[boi_search, boi_get],
            system_prompt=system_prompt,
            subagents=subagents,
            middleware=[
                ModelCallLimitMiddleware(
                    run_limit=parent_model_call_limit,
                    exit_behavior="error",
                )
            ],
        )
        ensure_active()
        timeout_seconds = max(30, min(int(job.get("timeout_seconds") or 900), 3600))
        previous_handler = None
        timer_enabled = threading.current_thread() is threading.main_thread() and hasattr(signal, "setitimer")
        if timer_enabled:
            previous_handler = signal.getsignal(signal.SIGALRM)

            def timeout_handler(_signum, _frame):
                raise DeepJobTimedOut(f"job exceeded {timeout_seconds} seconds")

            signal.signal(signal.SIGALRM, timeout_handler)
            signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
        usage_callback = UsageMetadataCallbackHandler()
        try:
            response = agent.invoke(
                {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"요청: {job.get('goal') or ''}\n\n"
                                "검증된 업무 맥락:\n"
                                + json.dumps(context_brief, ensure_ascii=False, default=str)
                            ),
                        }
                    ]
                },
                {
                    "recursion_limit": graph_recursion_limit,
                    "callbacks": [usage_callback],
                },
            )
        finally:
            if timer_enabled:
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
        ensure_active()
        messages = response.get("messages") if isinstance(response, dict) else []
        delegation_count = 0
        for message in messages or []:
            tool_calls_for_message = getattr(message, "tool_calls", None)
            if not isinstance(tool_calls_for_message, list) and isinstance(message, dict):
                tool_calls_for_message = message.get("tool_calls")
            task_calls = []
            for item in tool_calls_for_message or []:
                if not isinstance(item, dict):
                    continue
                function = item.get("function") if isinstance(item.get("function"), dict) else {}
                if str(item.get("name") or function.get("name") or "") == "task":
                    task_calls.append(item)
            if len(task_calls) > max_parallelism:
                raise RuntimeError("deep-work subagent parallelism budget exceeded")
            delegation_count += len(task_calls)
        if delegation_count > max_subagents:
            raise RuntimeError("deep-work subagent budget exceeded")
        if require_subagent and delegation_count < 1:
            raise RuntimeError("deep-work required subagent was not delegated")
        content = latest_assistant_text(list(messages or []))
        if not content:
            raise RuntimeError("DeepAgents returned an empty artifact")
        content = ensure_exact_evidence_ledger(content, evidence_ledger)
        if "evidence" not in content.lower() and "근거" not in content:
            raise RuntimeError("DeepAgents artifact is missing an evidence ledger")
        input_tokens = 0
        output_tokens = 0
        callback_usage = getattr(usage_callback, "usage_metadata", {})
        for usage in callback_usage.values() if isinstance(callback_usage, dict) else []:
            if not isinstance(usage, dict):
                continue
            input_tokens += int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0)
            output_tokens += int(usage.get("output_tokens") or usage.get("completion_tokens") or 0)
        for message in messages or []:
            usage_metadata = getattr(message, "usage_metadata", None)
            if not isinstance(usage_metadata, dict) and isinstance(message, dict):
                usage_metadata = message.get("usage_metadata")
            if not isinstance(usage_metadata, dict):
                continue
            if not callback_usage:
                input_tokens += int(usage_metadata.get("input_tokens") or 0)
                output_tokens += int(usage_metadata.get("output_tokens") or 0)
        accounting = "actual" if input_tokens or output_tokens else "estimated"
        if accounting == "estimated":
            input_tokens = max(1, len(json.dumps(context_brief, ensure_ascii=False, default=str)) // 4)
            output_tokens = max(1, len(content) // 4)
        deep_tokens = input_tokens + output_tokens
        if deep_tokens > token_budget:
            usage_id = new_id("usage")
            failed_usage = {
                "usage_id": usage_id,
                "employee_id": principal.employee_id,
                "job_id": str(job.get("job_id") or ""),
                "work_run_id": str(job.get("work_run_id") or ""),
                "status": "failed",
                "error": "deep-work token budget exceeded",
                "accounting": accounting,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": deep_tokens,
                "token_budget": token_budget,
                "tool_calls": tool_calls,
                "subagent_calls": delegation_count,
                "max_subagents": max_subagents,
                "subagent_budget_limit": subagent_budget_limit,
                "max_parallelism": max_parallelism,
                "max_input_tokens_per_call": self.service.settings.deep_max_input_tokens,
                "pilot_mode": pilot_mode,
                "created_at": now_iso(),
            }
            self.service.store.put("usage_ledgers", usage_id, failed_usage)
            job["usage_ref"] = usage_id
            raise RuntimeError("deep-work token budget exceeded")

        remaining_budget = max(4000, token_budget - deep_tokens)
        usage_id = new_id("usage")
        usage_token = begin_model_usage(usage_id, remaining_budget)
        self.service.evaluator.model = self.service.model
        independent_review = self.service.evaluator.evaluate(
            principal,
            artifact_kind="deep_work_draft",
            goal=str(job.get("goal") or ""),
            artifact={"title": "심층 작업 결과", "body": content},
            evidence=list(evidence_ledger.values()),
            rubric=[
                "요청한 업무 목표에 직접 답하는가",
                "핵심 주장마다 실제 evidence_id가 있는가",
                "불확실성, 누락 정보, 다음 검증 단계를 구분했는가",
                "초안이 production 변경이나 승인을 가장하지 않는가",
            ],
            work_run_id=str(job.get("work_run_id") or ""),
            require_evidence_refs=True,
        )
        review_usage = finish_model_usage(usage_token)
        review_tokens = int(review_usage.get("total_tokens") or review_usage.get("total_tokens_estimate") or 0)
        total_tokens = deep_tokens + review_tokens
        if total_tokens > token_budget:
            failed_usage = {
                "usage_id": usage_id,
                "employee_id": principal.employee_id,
                "job_id": str(job.get("job_id") or ""),
                "work_run_id": str(job.get("work_run_id") or ""),
                "status": "failed",
                "error": "deep-work token budget exceeded during independent review",
                "accounting": accounting,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "review_tokens": review_tokens,
                "total_tokens": total_tokens,
                "token_budget": token_budget,
                "tool_calls": tool_calls,
                "subagent_calls": delegation_count,
                "max_subagents": max_subagents,
                "subagent_budget_limit": subagent_budget_limit,
                "max_parallelism": max_parallelism,
                "max_input_tokens_per_call": self.service.settings.deep_max_input_tokens,
                "pilot_mode": pilot_mode,
                "created_at": now_iso(),
            }
            self.service.store.put("usage_ledgers", usage_id, failed_usage)
            job["usage_ref"] = usage_id
            raise RuntimeError("deep-work token budget exceeded during independent review")
        usage = {
            "usage_id": usage_id,
            "employee_id": principal.employee_id,
            "job_id": str(job.get("job_id") or ""),
            "work_run_id": str(job.get("work_run_id") or ""),
            "accounting": (
                accounting
                if review_usage.get("model_calls", 0) == 0
                else "actual"
                if accounting == "actual" and review_usage.get("accounting") == "actual"
                else "mixed"
            ),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "review_tokens": review_tokens,
            "review_tokens_estimate": int(review_usage.get("total_tokens_estimate") or review_tokens),
            "total_tokens": total_tokens,
            "token_budget": token_budget,
            "remaining_tokens": max(0, token_budget - total_tokens),
            "tool_calls": tool_calls,
            "subagent_calls": delegation_count,
            "max_subagents": max_subagents,
            "max_parallelism": max_parallelism,
            "max_input_tokens_per_call": self.service.settings.deep_max_input_tokens,
            "pilot_mode": pilot_mode,
            "created_at": now_iso(),
        }
        self.service.store.put("usage_ledgers", usage_id, usage)
        self.service.store.put(
            "checkpoints",
            f"{job['job_id']}:complete",
            {
                "job_id": job["job_id"],
                "employee_id": job.get("employee_id"),
                "state": "completed",
                "tool_calls": tool_calls,
                "usage_ref": usage_id,
                "review_status": independent_review.get("status") or "unavailable",
                "created_at": now_iso(),
            },
        )
        return {
            "title": "심층 작업 결과",
            "body": content,
            "status": "draft",
            "evidence_ledger_required": True,
            "evidence_ledger": list(evidence_ledger.values()),
            "tool_calls": tool_calls,
            "subagent_calls": delegation_count,
            "pilot_mode": pilot_mode,
            "independent_review": independent_review,
            "usage": usage,
        }

    def run_forever(self) -> None:
        interval = max(0.2, float(os.getenv("BOI_AGENT_V2_WORKER_POLL_SECONDS", "1") or "1"))
        while True:
            worked = self.run_once()
            if not worked:
                time.sleep(interval)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    settings = AgentV2Settings.from_environment(repo_root=repo_root)
    service = AgentV2Service(
        settings,
        routine_target_executor=lambda routine, request, principal: execute_boi_api_routine_target(
            settings,
            routine,
            request,
            principal,
        ),
    )
    service.ensure_model_residency()
    DeepWorkRunner(service).run_forever()


if __name__ == "__main__":
    main()
