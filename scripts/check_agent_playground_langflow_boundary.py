#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "langflow" / "compatibility-manifest.json"
COMPOSE_PATH = ROOT / "docker-compose.langflow-1.11-validation.yml"
SERVICE_PATH = ROOT / "boi_api" / "app" / "agent_playground.py"
COMPONENT_ROOT = ROOT / "langflow" / "custom_components" / "boi"
ALLOWED_LANGFLOW_ROOTS = {"agent_hub", "custom_components", "flows"}
FORBIDDEN_RUNTIME_MARKERS = (
    "sys.modules",
    "site-packages",
    "site_packages",
    "monkeypatch",
    "importlib.util.spec_from_file_location",
)
FORBIDDEN_DATABASE_MARKERS = (
    "LANGFLOW_DATABASE_URL",
    "psycopg",
    "sqlalchemy",
    "alembic",
)


def result(name: str, ok: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    compose = COMPOSE_PATH.read_text(encoding="utf-8")
    service = SERVICE_PATH.read_text(encoding="utf-8")
    component_sources = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(COMPONENT_ROOT.glob("*.py"))
    }
    checks: list[dict[str, Any]] = []

    checks.append(
        result(
            "external_runtime_manifest",
            manifest.get("runtime_ownership") == "external_unmodified",
            manifest.get("runtime_ownership"),
        )
    )
    expected_image = str(manifest.get("validated_image") or "")
    checks.append(result("official_image_digest", expected_image in compose, expected_image))
    checks.append(
        result(
            "read_only_component_mount",
            "./langflow/custom_components:/app/custom_components:ro" in compose
            and "LANGFLOW_COMPONENTS_PATH: /app/custom_components" in compose,
            "LANGFLOW_COMPONENTS_PATH + :ro",
        )
    )

    unexpected_roots = sorted(
        path.name
        for path in (ROOT / "langflow").iterdir()
        if path.name != MANIFEST_PATH.name and path.name not in ALLOWED_LANGFLOW_ROOTS
    )
    checks.append(result("no_vendored_langflow_source", not unexpected_roots, unexpected_roots))

    runtime_markers = {
        marker: sorted(
            name for name, source in component_sources.items() if marker.lower() in source.lower()
        )
        for marker in FORBIDDEN_RUNTIME_MARKERS
    }
    runtime_markers = {key: value for key, value in runtime_markers.items() if value}
    checks.append(result("no_runtime_monkey_patch", not runtime_markers, runtime_markers))

    database_markers = [
        marker for marker in FORBIDDEN_DATABASE_MARKERS if marker.lower() in service.lower()
    ]
    checks.append(result("no_langflow_database_access", not database_markers, database_markers))

    component_names = []
    for source in component_sources.values():
        component_names.extend(
            re.findall(r"^class\s+([A-Za-z0-9_]+)\s*\(\s*Component\s*\)", source, re.MULTILINE)
        )
    invalid_names = sorted(name for name in component_names if not name.startswith("BoI"))
    checks.append(result("boi_component_namespace", not invalid_names, invalid_names))

    syntax_tree = ast.parse(service)
    adapter_class = next(
        (
            node
            for node in syntax_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "LangflowPublicApiV1"
        ),
        None,
    )
    adapter_nodes = list(ast.walk(adapter_class)) if adapter_class is not None else []
    route_literals = sorted(
        {
            node.value
            for node in adapter_nodes
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and (node.value == "/health" or node.value.startswith("/api/v1/"))
        }
    )
    disallowed_routes = [
        route
        for route in route_literals
        if not any(
            token in route
            for token in (
                "/health",
                "/api/v1/version",
                "/api/v1/users/whoami",
                "/api/v1/all",
                "/api/v1/projects/",
                "/api/v1/flows/",
                "/api/v1/variables/",
                "/api/v1/run/",
            )
        )
    ]
    checks.append(
        result(
            "public_api_only",
            adapter_class is not None and not disallowed_routes,
            {
                "adapter": getattr(adapter_class, "name", ""),
                "routes": route_literals,
                "disallowed": disallowed_routes,
            },
        )
    )

    payload = {
        "ok": all(check["ok"] for check in checks),
        "manifest": str(MANIFEST_PATH.relative_to(ROOT)),
        "checks": checks,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
