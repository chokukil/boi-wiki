from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI


DEFAULT_PERMISSIONS: dict[str, dict[str, Any]] = {
    "100001": {
        "teams": ["aix-tf", "platform"],
        "roles": [
            "boi.viewer",
            "boi.editor",
            "boi.promoter",
            "boi.workflow_runner",
            "boi.action_invoker",
            "boi.admin",
        ],
        "projects": ["boi-wiki", "langflow"],
    },
    "100002": {
        "teams": ["aix-tf"],
        "roles": ["boi.viewer", "boi.editor", "boi.workflow_runner"],
        "projects": ["boi-wiki"],
    },
    "100003": {
        "teams": ["platform"],
        "roles": ["boi.viewer", "boi.editor", "boi.workflow_runner"],
        "projects": ["boi-wiki"],
    },
}


def load_permissions() -> dict[str, dict[str, Any]]:
    configured = os.getenv("HCP_PERMISSIONS_JSON", "")
    if not configured:
        return DEFAULT_PERMISSIONS
    try:
        parsed = json.loads(configured)
    except json.JSONDecodeError:
        return DEFAULT_PERMISSIONS
    if not isinstance(parsed, dict):
        return DEFAULT_PERMISSIONS
    return {str(key): value for key, value in parsed.items() if isinstance(value, dict)}


app = FastAPI(title="Mock HCP Authorization")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/permissions")
async def permissions(employee_id: str) -> dict[str, Any]:
    item = load_permissions().get(employee_id)
    if item is None:
        return {"employee_id": employee_id, "teams": [], "roles": ["boi.viewer"], "projects": []}
    return {"employee_id": employee_id, **item}

