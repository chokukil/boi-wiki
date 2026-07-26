#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx

sys.path.insert(0, "/app")

from app.main import (
    AGENT_PLAYGROUND_CREDENTIALS,
    SERVICE_TOKEN,
    credential_identity_for_employee,
)


BASE_URL = os.getenv("BOI_LIVE_INTERNAL_URL", "http://127.0.0.1:8000").rstrip("/")
EMPLOYEE_ID = os.getenv("BOI_VALIDATION_EMPLOYEE_ID", "100002")
TASK_REF = str(os.getenv("BOI_VALIDATION_TASK_REF") or "").strip()


def main() -> int:
    if not TASK_REF.startswith("task:"):
        raise RuntimeError("BOI_VALIDATION_TASK_REF must be an actual task reference")
    identity = credential_identity_for_employee(EMPLOYEE_ID)
    audience = {
        "action_key": "agent-playground.validation.audience",
        "deployment_id": "deployment-live-audience",
        "endpoint_id": "endpoint-live-audience",
        "project_id": f"boi-{EMPLOYEE_ID}",
        "flow_id": "flow-live-audience",
        "trace_id": "trace-live-audience",
        "execution_id": "execution-live-audience",
    }
    issued = AGENT_PLAYGROUND_CREDENTIALS.create_run_token(
        identity,
        action_key=audience["action_key"],
        deployment_id=audience["deployment_id"],
        endpoint_id=audience["endpoint_id"],
        project_id=audience["project_id"],
        flow_id=audience["flow_id"],
        trace_id=audience["trace_id"],
        execution_id=audience["execution_id"],
        allowed_capabilities=["boi.search", "boi.get", "knowledge.draft"],
        scopes=["boi.read", "boi.draft"],
        ttl_seconds=180,
    )
    raw_token = str(issued["token"])

    def headers(
        *,
        token: str = raw_token,
        overrides: dict[str, str] | None = None,
    ) -> dict[str, str]:
        values = {**audience, **(overrides or {})}
        return {
            "x-service-token": SERVICE_TOKEN,
            "authorization": f"Bearer {token}",
            "x-boi-action-key": values["action_key"],
            "x-boi-deployment-id": values["deployment_id"],
            "x-boi-endpoint-id": values["endpoint_id"],
            "x-boi-project-id": values["project_id"],
            "x-boi-flow-id": values["flow_id"],
            "x-boi-trace-id": values["trace_id"],
            "x-boi-execution-id": values["execution_id"],
        }

    result: dict[str, Any] = {
        "same_execution_statuses": [],
        "mismatches": {},
        "after_execution": {},
    }
    fields = (
        "action_key",
        "deployment_id",
        "endpoint_id",
        "project_id",
        "flow_id",
        "trace_id",
        "execution_id",
    )
    with httpx.Client(timeout=30) as client:
        for field in fields:
            response = client.get(
                f"{BASE_URL}/internal/agent-playground/wiki/search",
                headers=headers(overrides={field: f"wrong-{field}"}),
                params={"q": "audience mismatch", "limit": 1},
            )
            result["mismatches"][field] = {"status": response.status_code}

        capability_token = AGENT_PLAYGROUND_CREDENTIALS.create_run_token(
            identity,
            action_key=audience["action_key"],
            deployment_id=audience["deployment_id"],
            endpoint_id=audience["endpoint_id"],
            project_id=audience["project_id"],
            flow_id=audience["flow_id"],
            trace_id=audience["trace_id"],
            execution_id=audience["execution_id"],
            allowed_capabilities=["boi.search"],
            scopes=["boi.read"],
            ttl_seconds=180,
        )
        capability_response = client.get(
            f"{BASE_URL}/internal/agent-playground/wiki/get",
            headers=headers(token=str(capability_token["token"])),
            params={
                "ref": "boi:public:boi-wiki-manual:langflow:agent-playground-onboarding"
            },
        )
        result["mismatches"]["capability"] = {
            "status": capability_response.status_code
        }
        AGENT_PLAYGROUND_CREDENTIALS.consume_run_token(
            str(capability_token["token_id"])
        )

        search = client.get(
            f"{BASE_URL}/internal/agent-playground/wiki/search",
            headers=headers(),
            params={
                "q": "실제 Task의 SOP 단계와 근거",
                "task_ref": TASK_REF,
                "limit": 4,
            },
        )
        result["same_execution_statuses"].append(search.status_code)

        detail = client.get(
            f"{BASE_URL}/internal/agent-playground/wiki/get",
            headers=headers(),
            params={
                "ref": "boi:public:boi-wiki-manual:langflow:agent-playground-onboarding"
            },
        )
        result["same_execution_statuses"].append(detail.status_code)

        plan = client.post(
            f"{BASE_URL}/internal/agent-playground/wiki/plans",
            headers=headers(),
            json={
                "capability_id": "knowledge.draft",
                "goal": "run-token audience live validation",
                "task_ref": TASK_REF,
                "input": {
                    "title": "Run token audience validation draft",
                    "body": "This isolated draft proves that one execution may plan and confirm.",
                    "source_refs": [
                        {
                            "ref": "boi:public:boi-wiki-manual:langflow:agent-playground-onboarding"
                        }
                    ],
                    "provenance": {
                        "flow_id": audience["flow_id"],
                        "trace_id": audience["trace_id"],
                    },
                },
            },
        )
        result["same_execution_statuses"].append(plan.status_code)
        plan_id = str((plan.json() if plan.status_code == 200 else {}).get("plan_id") or "")

        confirm = client.post(
            f"{BASE_URL}/internal/agent-playground/wiki/plans/{plan_id}/confirm",
            headers=headers(),
            json={"reason": "isolated live audience validation"},
        )
        result["same_execution_statuses"].append(confirm.status_code)

        AGENT_PLAYGROUND_CREDENTIALS.consume_run_token(str(issued["token_id"]))
        after = client.get(
            f"{BASE_URL}/internal/agent-playground/wiki/search",
            headers=headers(),
            params={"q": "consumed token", "limit": 1},
        )
        result["after_execution"] = {"status": after.status_code}

    result["ok"] = (
        result["same_execution_statuses"] == [200, 200, 200, 200]
        and all(
            item["status"] == 403
            for item in result["mismatches"].values()
        )
        and result["after_execution"]["status"] == 401
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
