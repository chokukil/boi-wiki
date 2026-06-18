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


DEFAULT_PROJECTS = ["boi-wiki", "langflow"]


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


def load_project_roles() -> dict[str, dict[str, list[str]]]:
    configured = os.getenv("HCP_PROJECT_ROLES_JSON", "")
    if configured:
        try:
            parsed = json.loads(configured)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            result: dict[str, dict[str, list[str]]] = {}
            for project, roles in parsed.items():
                if not isinstance(roles, dict):
                    continue
                result[str(project)] = {
                    "managers": [str(item) for item in roles.get("managers", [])],
                    "deployApprovers": [str(item) for item in roles.get("deployApprovers", [])],
                    "developers": [str(item) for item in roles.get("developers", [])],
                }
            if result:
                return result

    project_roles = {
        project: {"managers": [], "deployApprovers": [], "developers": []}
        for project in DEFAULT_PROJECTS
    }
    for employee_id, permissions in load_permissions().items():
        projects = permissions.get("projects") or []
        roles = permissions.get("roles") or []
        for project in projects:
            project_key = str(project)
            project_roles.setdefault(project_key, {"managers": [], "deployApprovers": [], "developers": []})
            if "boi.admin" in roles:
                project_roles[project_key]["managers"].append(employee_id)
            if "boi.promoter" in roles:
                project_roles[project_key]["deployApprovers"].append(employee_id)
            if "boi.editor" in roles or "boi.workflow_runner" in roles:
                project_roles[project_key]["developers"].append(employee_id)
    return project_roles


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


@app.get("/v1/projects/{project_id}/roles")
async def project_roles(project_id: str) -> dict[str, Any]:
    roles = load_project_roles().get(project_id, {"managers": [], "deployApprovers": [], "developers": []})
    return {"project": project_id, "response": roles}
