from __future__ import annotations

import os
from typing import Any

import httpx


class BoiV2Client:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 120):
        self.base_url = (base_url or os.getenv("BOI_BASE_URL") or "http://localhost:28000").rstrip("/")
        self.token = token or os.getenv("BOI_PAT") or ""
        if not self.token.startswith("boi_pat_"):
            raise ValueError("BOI_PAT must be a BoI Wiki personal access token")
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(path, json=payload)
        response.raise_for_status()
        return response.json()

    def _patch(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.patch(path, json=payload)
        response.raise_for_status()
        return response.json()

    def bootstrap(self, page_ref: str = "") -> dict[str, Any]:
        return self._get("/api/v2/bootstrap", page_ref=page_ref)

    def search(
        self,
        query: str = "",
        *,
        view: str = "ranked",
        source_ref: str = "",
        target_ref: str = "",
        depth: int = 2,
        include_history: bool = False,
        limit: int = 8,
    ) -> dict[str, Any]:
        if view == "ranked":
            return self._get("/api/v2/search", q=query, include_history=include_history, limit=limit)
        if view not in {"neighbors", "path", "impact", "tour"}:
            raise ValueError("view must be ranked, neighbors, path, impact, or tour")
        return self._get(
            "/api/v2/knowledge-graph/explore",
            view=view,
            source_ref=source_ref,
            target_ref=target_ref,
            q=query,
            depth=depth,
            limit=limit,
        )

    def agent(
        self,
        question: str,
        *,
        work_session_id: str = "",
        page_ref: str = "",
        task_ref: str = "",
        capability_id: str = "",
        external_ai_summary: str = "",
        external_artifact_refs: list[str] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "question": question,
            "work_session_id": work_session_id or None,
            "page_ref": page_ref,
            "task_ref": task_ref,
            "external_ai_summary": external_ai_summary,
            "external_artifact_refs": external_artifact_refs or [],
        }
        if capability_id:
            payload["capability_id"] = capability_id
        return self._post(
            "/api/v2/agent/turns",
            payload,
        )

    def plan(self, capability_id: str, goal: str, *, page_ref: str = "", task_ref: str = "") -> dict[str, Any]:
        return self._post(
            f"/api/v2/capabilities/{capability_id}/plan",
            {"goal": goal, "page_ref": page_ref, "task_ref": task_ref, "input": {}},
        )

    def confirm(self, plan_id: str, reason: str) -> dict[str, Any]:
        return self._post(
            f"/api/v2/plans/{plan_id}/confirm",
            {"confirmation": "confirm", "reason": reason},
        )

    def job(self, job_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/deep-jobs/{job_id}")

    def work_run(self, work_run_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/work-runs/{work_run_id}")

    def continue_work_run(
        self,
        work_run_id: str,
        *,
        expected_revision: int,
        kind: str,
        summary: str,
        ref: str = "",
        confirm: bool = False,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/v2/work-runs/{work_run_id}/continue",
            {
                "expected_revision": expected_revision,
                "confirmation": "confirm" if confirm else None,
                "delta": {"kind": kind, "summary": summary, "ref": ref},
            },
        )

    def knowledge_candidates(self, status: str = "") -> dict[str, Any]:
        return self._get("/api/v2/knowledge-candidates", status=status)

    def review_knowledge_candidate(self, candidate_id: str, expected_revision: int) -> dict[str, Any]:
        return self._patch(
            f"/api/v2/knowledge-candidates/{candidate_id}",
            {"expected_revision": expected_revision, "status": "reviewed"},
        )

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "BoiV2Client":
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()
