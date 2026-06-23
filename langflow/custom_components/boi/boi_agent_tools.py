from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from lfx.base.langchain_utilities.model import LCToolComponent
from lfx.field_typing import Tool
from lfx.io import StrInput
from lfx.schema.data import Data
from pydantic import BaseModel, Field


class OntologySearchArgs(BaseModel):
    query: str = Field(..., description="Business question or search query.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")
    scope: str = Field("all", description="all|boi|sop|event|action|dictionary")


class BoiAnswerArgs(BaseModel):
    question: str = Field(..., description="User question to answer from BoI Wiki.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")
    current_url: str = Field("", description="Current BoI Wiki page URL.")


class BoiGetArgs(BaseModel):
    boi_id: str = Field(..., description="BoI ID or OKF path.")
    employee_id: str = Field("100001", description="Employee ID used for ACL.")


class ActionSpecLookupArgs(BaseModel):
    action_key: str = Field(..., description="Action key to look up.")
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


class BoIAgentTools(LCToolComponent):
    display_name = "BoI Agent Tools"
    description = "Langflow native Agent tools for BoI Wiki ontology search, documents, workflow status, inbox, handoff completion, and memory recall."
    icon = "wrench"
    name = "boi_agent_tools"

    inputs = [
        StrInput(name="boi_api_url", display_name="BoI API URL", value="http://boi-api:8000"),
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

    def _boi_answer(self, question: str, employee_id: str = "100001", current_url: str = "") -> str:
        raw = self._ontology_search(question, employee_id=employee_id, scope="all")
        try:
            payload = json.loads(raw)
        except Exception:
            return json.dumps(
                {
                    "answer_markdown": "BoI Wiki 검색 결과를 읽지 못했습니다.",
                    "links": [],
                    "citations": [],
                    "suggested_questions": ["다른 키워드로 검색해줘", "SOP를 검색해줘"],
                    "context_summary": {"source": "boi_answer", "current_url": current_url},
                },
                ensure_ascii=False,
            )

        links: list[dict[str, str]] = []
        lines = ["### BoI Wiki 검색 결과"]
        knowledge = payload.get("knowledge_panel") if isinstance(payload, dict) else {}
        candidates: list[dict[str, Any]] = []
        if isinstance(knowledge, dict):
            for key in ("top_sop", "top_event_types", "top_actions", "top_documents"):
                value = knowledge.get(key)
                if isinstance(value, list):
                    candidates.extend(item for item in value if isinstance(item, dict))
        if not candidates and isinstance(payload, dict):
            best = payload.get("best_matches")
            if isinstance(best, list):
                candidates.extend(item for item in best if isinstance(item, dict))
            groups = payload.get("groups")
            if isinstance(groups, dict):
                for value in groups.values():
                    if isinstance(value, list):
                        candidates.extend(item for item in value if isinstance(item, dict))

        seen: set[str] = set()
        for item in candidates[:5]:
            title = str(item.get("title") or item.get("label") or item.get("event_type") or item.get("action_key") or item.get("boi_id") or "Untitled")
            href = str(item.get("href") or item.get("url") or "")
            boi_id = str(item.get("boi_id") or item.get("doc_ref") or "")
            if not href and boi_id.startswith("boi:"):
                href = f"/docs/{urllib.parse.quote(boi_id, safe=':')}?employee_id={urllib.parse.quote(employee_id)}"
            key = href or title
            if key in seen:
                continue
            seen.add(key)
            description = str(item.get("description") or item.get("match_reason") or "").strip()
            if href:
                lines.append(f"- [{title}]({href})")
                links.append({"label": title, "href": href})
            else:
                lines.append(f"- {title}")
            if description:
                lines.append(f"  - {description[:180]}")

        if len(lines) == 1:
            lines.append("관련 결과를 찾지 못했습니다. 다른 업무 용어나 Event/SOP 이름으로 다시 물어보세요.")
        return json.dumps(
            {
                "answer_markdown": "\n".join(lines),
                "links": links,
                "citations": links[:3],
                "suggested_questions": [
                    "이 SOP의 Event와 Action 흐름을 요약해줘",
                    "관련 Action Spec을 찾아줘",
                    "내가 처리해야 할 Action이 있는지 확인해줘",
                ],
                "context_summary": {
                    "source": "boi_answer",
                    "current_url": current_url,
                    "query_expansion": payload.get("query_expansion") if isinstance(payload, dict) else [],
                },
            },
            ensure_ascii=False,
        )

    def _boi_get(self, boi_id: str, employee_id: str = "100001") -> str:
        return self._request("GET", f"/api/docs/{urllib.parse.quote(boi_id, safe='')}/metadata-fragment", params={"employee_id": employee_id})

    def _action_spec_lookup(self, action_key: str, employee_id: str = "100001") -> str:
        raw = self._request("GET", "/api/actions/catalog", params={"employee_id": employee_id})
        try:
            payload = json.loads(raw)
            items = payload.get("items") if isinstance(payload, dict) else []
            for item in items or []:
                if str(item.get("action_key") or "") == action_key:
                    doc_ref = str(item.get("doc_ref") or "")
                    doc = self._boi_get(doc_ref, employee_id) if doc_ref else ""
                    return json.dumps({"ok": True, "item": item, "doc_ref": doc_ref, "doc": doc}, ensure_ascii=False)
            return json.dumps({"ok": False, "status": "not_found", "action_key": action_key}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": repr(exc), "raw": raw[:1200]}, ensure_ascii=False)

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

    def run_model(self) -> list[Data]:
        tools = self.build_tool()
        self.status = f"{len(tools)} BoI Agent tools available"
        return [Data(data={"tools": [tool.name for tool in tools]})]

    def build_tool(self) -> list[Tool]:
        return [
            self.boi_answer_tool(),
            self.ontology_search_tool(),
            self.boi_get_tool(),
            self.action_spec_lookup_tool(),
            self.workflow_status_tool(),
            self.agent_inbox_tool(),
            self.manual_handoff_complete_tool(),
            self.memory_recall_tool(),
        ]

    def boi_answer_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="boi_answer",
            description="Fallback: make a compact JSON answer from ontology search when deeper tool-loop reasoning is unnecessary.",
            func=self._boi_answer,
            args_schema=BoiAnswerArgs,
            return_direct=False,
        )

    def ontology_search_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="ontology_search",
            description="Search BoI Wiki ontology groups across SOP, Event Types, Actions, documents, dictionary, and runtime evidence.",
            func=self._ontology_search,
            args_schema=OntologySearchArgs,
        )

    def boi_get_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="boi_get",
            description="Read a specific BoI document metadata/body fragment by BoI ID or OKF path.",
            func=self._boi_get,
            args_schema=BoiGetArgs,
        )

    def action_spec_lookup_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="action_spec_lookup",
            description="Look up an Action catalog entry and its BoI Action Spec document by action_key.",
            func=self._action_spec_lookup,
            args_schema=ActionSpecLookupArgs,
        )

    def workflow_status_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="workflow_status",
            description="Read workflow status for a trace.",
            func=self._workflow_status,
            args_schema=WorkflowStatusArgs,
        )

    def agent_inbox_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="agent_inbox",
            description="Return open manual/approval/follow-up action tasks for an employee.",
            func=self._agent_inbox,
            args_schema=AgentInboxArgs,
        )

    def manual_handoff_complete_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="manual_handoff_complete",
            description="Append a user-confirmed manual handoff completion row. Requires user_confirmed=true.",
            func=self._manual_handoff_complete,
            args_schema=ManualHandoffCompleteArgs,
        )

    def memory_recall_tool(self) -> Tool:
        return StructuredTool.from_function(
            name="memory_recall",
            description="Search private Agent Memory BoI documents for answer preferences and domain context.",
            func=self._memory_recall,
            args_schema=MemoryRecallArgs,
        )
