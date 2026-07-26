#!/usr/bin/env python3
"""Apply a publish-requested Agent Playground Action to an isolated catalog.

This is a validation/operator helper, not a production API. It refuses to
materialize an Action unless the registration draft and Playground deployment
carry the same immutable endpoint/project/Flow/version/checksum reference.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")
CHECKSUM = re.compile(r"^[0-9a-f]{64}$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to read validation state: {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"validation state must be an object: {path}")
    return payload


def atomic_text(path: Path, value: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def exact_reference(connector: dict[str, Any]) -> dict[str, str]:
    return {
        "endpoint_connection_id": str(connector.get("endpoint_connection_id") or ""),
        "deployment_id": str(connector.get("deployment_id") or ""),
        "project_id": str(connector.get("project_id") or ""),
        "flow_id": str(connector.get("flow_id") or ""),
        "artifact_version": str(connector.get("artifact_version") or ""),
        "artifact_checksum": str(connector.get("artifact_checksum") or ""),
    }


def catalog_input_schema(request: dict[str, Any]) -> dict[str, Any]:
    raw_schema = request.get("input_schema") if isinstance(request.get("input_schema"), dict) else {}
    properties: dict[str, dict[str, Any]] = {}
    required: list[str] = []
    for field_name, raw_spec in raw_schema.items():
        if not isinstance(raw_spec, dict):
            continue
        name = str(field_name or "").strip()
        if not name or not SAFE_ID.fullmatch(name):
            continue
        spec = {
            key: value
            for key, value in raw_spec.items()
            if key in {"type", "enum", "default", "title", "description"}
        }
        spec.setdefault("type", "string")
        spec.setdefault("title", name.replace("_", " "))
        properties[name] = spec
        if raw_spec.get("required") is True:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


def apply_fixture(
    *,
    runtime_root: Path,
    catalog_root: Path,
    employee_id: str,
    draft_id: str,
    evidence_file: Path | None = None,
) -> dict[str, Any]:
    if not SAFE_ID.fullmatch(employee_id) or not SAFE_ID.fullmatch(draft_id):
        raise RuntimeError("employee_id and draft_id must be explicit safe identifiers")
    draft_path = runtime_root / "drafts" / "registration_drafts" / f"{draft_id}.json"
    user_path = runtime_root / "agent-playground" / "users" / f"{employee_id}.json"
    draft = read_json(draft_path)
    user = read_json(user_path)
    if str(draft.get("created_by") or "") != employee_id:
        raise RuntimeError("registration draft owner does not match the requested employee")
    if str(draft.get("entry_kind") or "") != "action":
        raise RuntimeError("only Action registration drafts can be materialized")
    if str(draft.get("status") or "") != "publish_requested":
        raise RuntimeError("registration draft must be publish_requested")
    validation = draft.get("validation") if isinstance(draft.get("validation"), dict) else {}
    if not validation.get("valid"):
        raise RuntimeError("registration draft validation must pass")
    request = draft.get("request") if isinstance(draft.get("request"), dict) else {}
    connector = request.get("connector_config") if isinstance(request.get("connector_config"), dict) else {}
    action_contract = request.get("action_contract") if isinstance(request.get("action_contract"), dict) else {}
    connector_binding = request.get("connector_binding") if isinstance(request.get("connector_binding"), dict) else {}
    if str(action_contract.get("schema_version") or "") != "boi.action-contract.v1":
        raise RuntimeError("connector-neutral Action contract is missing")
    if str(connector_binding.get("kind") or "") != "langflow":
        raise RuntimeError("Agent Playground connector binding must use the Langflow adapter")
    if str(connector_binding.get("execution_mode") or "") != "gateway":
        raise RuntimeError("Agent Playground Action must execute through Action Gateway")
    reference = exact_reference(connector)
    if str(connector.get("connection_source") or "") != "agent_playground":
        raise RuntimeError("registration draft is not backed by Agent Playground")
    if not all(reference.values()):
        raise RuntimeError("immutable deployment reference is incomplete")
    if not CHECKSUM.fullmatch(reference["artifact_checksum"]):
        raise RuntimeError("artifact checksum must be a lowercase SHA-256")

    deployment = next(
        (
            item
            for item in user.get("deployments") or []
            if isinstance(item, dict)
            and str(item.get("deployment_id") or "") == reference["deployment_id"]
        ),
        None,
    )
    if deployment is None:
        raise RuntimeError("referenced Playground deployment was not found")
    expected = {
        "endpoint_connection_id": str(deployment.get("endpoint_id") or ""),
        "deployment_id": str(deployment.get("deployment_id") or ""),
        "project_id": str(deployment.get("project_id") or ""),
        "flow_id": str(deployment.get("flow_id") or ""),
        "artifact_version": str(deployment.get("asset_version") or ""),
        "artifact_checksum": str(deployment.get("artifact_checksum") or ""),
    }
    if reference != expected:
        raise RuntimeError("registration draft and Playground deployment references do not match")
    if str(deployment.get("action_draft_id") or "") != draft_id:
        raise RuntimeError("Playground deployment is linked to a different Action draft")
    if str(deployment.get("status") or "") != "action_linked":
        raise RuntimeError("Playground deployment is not action_linked")

    patch = draft.get("catalog_patch_proposal") if isinstance(draft.get("catalog_patch_proposal"), dict) else {}
    action_key = str(patch.get("action_key") or request.get("action_key") or "")
    if not action_key:
        raise RuntimeError("Action key is missing")
    action = {
        "action_key": action_key,
        "name_ko": str(patch.get("title") or request.get("title") or "BoI Wiki Agent Loop"),
        "description": str(request.get("description") or request.get("business_goal") or ""),
        "type": "langflow_run",
        "connector_kind": "langflow",
        "execution_mode": "gateway",
        "connection_source": "agent_playground",
        "enabled": True,
        "auto_dispatch": False,
        "dry_run": False,
        "event_types": list(request.get("linked_event_types") or ["agent.playground.requested.v1"]),
        "flow_id": reference["flow_id"],
        "endpoint_name": str(connector.get("endpoint_name") or "boi-wiki-agent-loop"),
        "connector_config": dict(connector),
        "action_contract": dict(action_contract),
        "connector_binding": dict(connector_binding),
        "input_schema": catalog_input_schema(request),
        "body": {
            "input_value": "${payload}",
            "input_type": "chat",
            "output_type": "chat",
        },
        "risk_level": str(request.get("risk_level") or "low"),
        "approval_required": bool(request.get("approval_required")),
        "validation_provenance": {
            "draft_id": draft_id,
            "validated_by": str(validation.get("validated_by") or employee_id),
            "checks": list(validation.get("checks") or []),
            **reference,
        },
    }
    catalog_path = catalog_root / f"agent-playground-{draft_id}.yaml"
    atomic_text(
        catalog_path,
        yaml.safe_dump({"actions": [action]}, allow_unicode=True, sort_keys=False),
    )

    applied_at = now_iso()
    draft.update(
        {
            "catalog_applied": True,
            "catalog_applied_at": applied_at,
            "catalog_applied_by": "validation_operator",
            "catalog_fixture_file": catalog_path.name,
        }
    )
    atomic_text(draft_path, json.dumps(draft, ensure_ascii=False, indent=2, default=str))
    action_state = user.get("action") if isinstance(user.get("action"), dict) else {}
    if str(action_state.get("draft_id") or "") == draft_id:
        action_state.update(
            {
                "status": "catalog_applied",
                "catalog_applied": True,
                "action_key": action_key,
                "updated_at": applied_at,
            }
        )
        user["action"] = action_state
    for collection_name in ("deployments", "flow_registry"):
        for item in user.get(collection_name) or []:
            if isinstance(item, dict) and str(item.get("action_draft_id") or "") == draft_id:
                item["action_draft_status"] = "catalog_applied"
                item["action_catalog_applied"] = True
                item["action_key"] = action_key
                if collection_name == "deployments":
                    item["status"] = "action_linked"
                else:
                    item["validation_status"] = "action_linked"
    atomic_text(user_path, json.dumps(user, ensure_ascii=False, indent=2, default=str))

    result = {
        "ok": True,
        "operator_mode": "validation_only",
        "employee_id": employee_id,
        "draft_id": draft_id,
        "action_key": action_key,
        "catalog_file": str(catalog_path),
        "applied_at": applied_at,
        "deployment_reference": reference,
    }
    if evidence_file is not None:
        atomic_text(evidence_file, json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--employee-id", required=True)
    parser.add_argument("--draft-id", required=True)
    parser.add_argument("--evidence-file", type=Path)
    args = parser.parse_args()
    result = apply_fixture(
        runtime_root=args.runtime_root,
        catalog_root=args.catalog_root,
        employee_id=args.employee_id,
        draft_id=args.draft_id,
        evidence_file=args.evidence_file,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
