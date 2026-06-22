from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from lfx.custom import Component
from lfx.io import Output, StrInput
from pydantic import BaseModel, Field


class OntologySearchArgs(BaseModel):
    query: str = Field(..., description="Business question or search query.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")
    scope: str = Field("all", description="all|boi|sop|event|action|dictionary")


class BoiGetArgs(BaseModel):
    boi_id: str = Field(..., description="BoI ID or OKF path.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")


class WorkflowStatusArgs(BaseModel):
    workflow_key: str = Field(..., description="Workflow key from SOP metadata.")
    trace_id: str = Field(..., description="Trace ID.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")


class AgentInboxArgs(BaseModel):
    employee_id: str = Field("100001", description="Employee ID used for ACL.")
    limit: int = Field(5, description="Maximum inbox items.")


class ManualHandoffCompleteArgs(BaseModel):
    task_id: str = Field(..., description="Inbox task id.")
    note: str = Field(..., description="Human completion note.")
    outcome: Literal["completed", "not_needed", "blocked"] = "completed"
    employee_id: str = Field("100001", description="Employee ID used for ACL.")
    user_confirmed: bool = Field(False, description="Must be true for mutation.")


class MemoryRecallArgs(BaseModel):
    query: str = Field("", description="Memory search query.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")
    limit: int = Field(5, description="Maximum memory items.")


class BoIAgentTools(Component):
    display_name = "BoI Agent Tools"
    description = "Langflow native Agent tools for BoI Wiki ontology search, documents, workflow status, inbox, handoff completion, and memory recall."
    icon = "wrench"
    name = "boi_agent_tools"

    inputs = [
        StrInput(name="boi_api_url", display_name="BoI API URL", value="http://boi-api:8000"),
    ]
    outputs = [
        Output(name="ontology_search_tool", display_name="ontology_search", method="ontology_search_tool"),
        Output(name="boi_get_tool", display_name="boi_get", method="boi_get_tool"),
        Output(name="workflow_status_tool", display_name="workflow_status", method="workflow_status_tool"),
        Output(name="agent_inbox_tool", display_name="agent_inbox", method="agent_inbox_tool"),
        Output(name="manual_handoff_complete_tool", display_name="manual_handoff_complete", method="manual_handoff_complete_tool"),
        Output(name="memory_recall_tool", display_name="memory_recall", method="memory_recall_tool"),
    ]

    def _headers(self) -> dict[str, str]:
        token = os.getenv("BOI_API_SERVICE_TOKEN") or os.getenv("SERVICE_TOKEN") or ""
        headers = {"Content-Type": "application/json"}
        if token:
            headers["x-service-token"] = token
        return headers

    def _request(self, method: str, path: str, *, params: dict[str, Any] | None = None, payload: dict[str, Any] | None = None) -> str:
        base = str(self.boi_api_url or "http://boi-api:8000").rstrip("/")
        query = urllib.parse.urlencode(params or {})
        url = f"{base}{path}{'?' + query if query else ''}"
        data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if method != "GET" else None
        req = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            return json.dumps({"ok": False, "error": repr(exc), "url": url}, ensure_ascii=False)

    def _ontology_search(self, query: str, employee_id: str = "100001", scope: str = "all") -> str:
        return self._request("GET", "/api/search/ontology", params={"q": query, "employee_id": employee_id, "scope": scope})

    def _boi_get(self, boi_id: str, employee_id: str = "100001") -> str:
        return self._request("GET", f"/api/docs/{urllib.parse.quote(boi_id, safe='')}/metadata-fragment", params={"employee_id": employee_id})

    def _workflow_status(self, workflow_key: str, trace_id: str, employee_id: str = "100001") -> str:
        return self._request("GET", f"/api/workflows/{workflow_key}/status", params={"employee_id": employee_id, "trace_id": trace_id, "format": "json"})

    def _agent_inbox(self, employee_id: str = "100001", limit: int = 5) -> str:
        return self._request("GET", "/api/agents/boi-wiki/inbox", params={"employee_id": employee_id, "limit": limit})

    def _manual_handoff_complete(
        self,
        task_id: str,
        note: str,
        outcome: str = "completed",
        employee_id: str = "100001",
        user_confirmed: bool = False,
    ) -> str:
        if not user_confirmed:
            return json.dumps({"ok": False, "status": "confirmation_required", "message": "user_confirmed=true is required"}, ensure_ascii=False)
        return self._request(
            "POST",
            "/api/agents/boi-wiki/manual-handoffs/complete",
            params={"employee_id": employee_id},
            payload={"task_id": task_id, "note": note, "outcome": outcome, "user_confirmed": True},
        )

    def _memory_recall(self, query: str = "", employee_id: str = "100001", limit: int = 5) -> str:
        return self._request("GET", "/api/agents/boi-wiki/memory", params={"employee_id": employee_id, "q": query, "limit": limit})

    def ontology_search_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name="ontology_search",
            description="Search BoI Wiki ontology groups across SOP, Event Types, Actions, documents, dictionary, and runtime evidence.",
            func=self._ontology_search,
            args_schema=OntologySearchArgs,
        )

    def boi_get_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name="boi_get",
            description="Read a specific BoI document metadata/body fragment by BoI ID or OKF path.",
            func=self._boi_get,
            args_schema=BoiGetArgs,
        )

    def workflow_status_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name="workflow_status",
            description="Read workflow status for a trace.",
            func=self._workflow_status,
            args_schema=WorkflowStatusArgs,
        )

    def agent_inbox_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name="agent_inbox",
            description="Return open manual/approval/follow-up action tasks for an employee.",
            func=self._agent_inbox,
            args_schema=AgentInboxArgs,
        )

    def manual_handoff_complete_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name="manual_handoff_complete",
            description="Append a user-confirmed manual handoff completion row. Requires user_confirmed=true.",
            func=self._manual_handoff_complete,
            args_schema=ManualHandoffCompleteArgs,
        )

    def memory_recall_tool(self) -> StructuredTool:
        return StructuredTool.from_function(
            name="memory_recall",
            description="Search private Agent Memory BoI documents for answer preferences and domain context.",
            func=self._memory_recall,
            args_schema=MemoryRecallArgs,
        )
