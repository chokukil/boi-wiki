from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, IntInput, Output, StrInput
from lfx.schema import Data


class BoIUniversalSimulatorAgent(Component):
    display_name = "BoI Universal Simulator Agent"
    description = "Run the agentic BoI Wiki tool loop for Universal Simulator actions."
    icon = "bot-message-square"
    name = "boi_universal_simulator_agent"

    inputs = [
        DataInput(name="work_context", display_name="WorkContext", required=False),
        DataInput(name="simulation_agent", display_name="Precomputed Agent Context", required=False),
        DataInput(name="prior_results", display_name="Prior Results", required=False),
        StrInput(name="action_key", display_name="Fallback Action Key", value="", required=False),
        StrInput(name="employee_id", display_name="Employee ID", value="100001"),
        StrInput(name="boi_api_url", display_name="BoI API URL", value="http://boi-api:8000"),
        IntInput(name="max_iterations", display_name="Max Agent Iterations", value=5),
    ]
    outputs = [Output(name="agent_result", display_name="Agent Result", method="run_agent")]

    def _headers(self) -> dict[str, str]:
        token = os.getenv("BOI_API_SERVICE_TOKEN") or os.getenv("SERVICE_TOKEN") or ""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["x-service-token"] = token
        return headers

    def _as_dict(self, value: Any) -> dict[str, Any]:
        if not value:
            return {}
        if hasattr(value, "data"):
            return value.data or {}
        if isinstance(value, dict):
            return value
        return {"value": str(value)}

    def _as_list(self, value: Any) -> list[dict[str, Any]]:
        if not value:
            return []
        if hasattr(value, "data"):
            value = value.data
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []

    def _event_from_context(self, context: dict[str, Any]) -> dict[str, Any]:
        event = context.get("event")
        if isinstance(event, dict) and event:
            return event
        return {
            "event_type": context.get("event_type") or "manual.input.v1",
            "trace_id": context.get("trace_id") or "",
            "payload": context.get("payload") if isinstance(context.get("payload"), dict) else {},
        }

    def _fallback_result(self, error: str, body: dict[str, Any]) -> Data:
        return Data(
            data={
                "ok": False,
                "status": "universal_simulator_agent_failed",
                "error": error,
                "request": body,
                "agent_iterations": 0,
                "tool_calls": [],
                "coverage_report": {"coverage_score": 0, "missing_context": ["agent_failed"], "passed": False},
            }
        )

    def run_agent(self) -> Data:
        context = self._as_dict(self.work_context)
        precomputed = self._as_dict(self.simulation_agent) or self._as_dict(context.get("simulation_agent"))
        if precomputed and precomputed.get("ok") is not False:
            precomputed.setdefault("agent_iterations", ((precomputed.get("agent") or {}).get("agent_iterations") or 1))
            precomputed.setdefault("tool_calls", precomputed.get("tool_calls") or [])
            return Data(data=precomputed)

        event = self._event_from_context(context)
        payload = context.get("payload") if isinstance(context.get("payload"), dict) else event.get("payload") or {}
        action_key = (
            context.get("action_key")
            or payload.get("action_key")
            or event.get("action_key")
            or self.action_key
        )
        if not action_key:
            return self._fallback_result("action_key is required", {"event": event, "payload": payload})

        body = {
            "action_key": action_key,
            "employee_id": context.get("employee_id") or self.employee_id,
            "event": event,
            "payload": payload,
            "prior_results": self._as_list(context.get("prior_results") or self.prior_results),
            "workflow_key": context.get("workflow_key") or "",
            "sop_ref": context.get("sop_ref") or "",
            "sop_stage_id": context.get("sop_stage_id") or "",
            "simulation_depth": context.get("simulation_depth") or "stage_prerequisites",
            "max_rounds": min(max(int(self.max_iterations or 5), 1), 5),
        }
        url = f"{self.boi_api_url.rstrip('/')}/api/simulations/universal-agent"
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                if isinstance(result, dict):
                    result.setdefault("agent_iterations", ((result.get("agent") or {}).get("agent_iterations") or 1))
                    result.setdefault("tool_calls", result.get("tool_calls") or [])
                    return Data(data=result)
                return self._fallback_result("unexpected non-object response", body)
        except Exception as exc:
            return self._fallback_result(repr(exc), body)
