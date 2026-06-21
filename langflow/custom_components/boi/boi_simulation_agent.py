from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from lfx.custom import Component
from lfx.io import DataInput, IntInput, Output, StrInput
from lfx.schema import Data


class BoISimulationAgent(Component):
    display_name = "BoI Simulation Agent"
    description = "Run the bounded BoI Wiki retrieval agent for SIMULATED action dry-runs."
    icon = "bot"
    name = "boi_simulation_agent"

    inputs = [
        DataInput(name="work_context", display_name="WorkContext", required=False),
        DataInput(name="prior_results", display_name="Prior Results", required=False),
        StrInput(name="action_key", display_name="Action Key", required=True),
        StrInput(name="employee_id", display_name="Employee ID", value="100001"),
        StrInput(name="boi_api_url", display_name="BoI API URL", value="http://boi-api:8000"),
        IntInput(name="max_rounds", display_name="Max Retrieval Rounds", value=4),
    ]
    outputs = [Output(name="agent_context", display_name="Simulation Agent Context", method="run_agent")]

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

    def run_agent(self) -> Data:
        context = self._as_dict(self.work_context)
        event = context.get("event") if isinstance(context.get("event"), dict) else context
        payload = event.get("payload") if isinstance(event, dict) and isinstance(event.get("payload"), dict) else {}
        body = {
            "action_key": self.action_key,
            "employee_id": self.employee_id,
            "event": event,
            "payload": payload,
            "prior_results": self._as_list(self.prior_results),
            "max_rounds": int(self.max_rounds or 4),
        }
        url = f"{self.boi_api_url.rstrip('/')}/api/simulations/universal-agent"
        req = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return Data(data=json.loads(resp.read().decode("utf-8")))
        except Exception as exc:
            return Data(data={"ok": False, "status": "simulation_agent_failed", "error": repr(exc), "request": body})
