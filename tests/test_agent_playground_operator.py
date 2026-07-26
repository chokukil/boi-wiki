from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.apply_agent_playground_action_fixture import apply_fixture


def validation_state(tmp_path: Path, *, draft_checksum: str | None = None) -> tuple[Path, Path, str]:
    runtime_root = tmp_path / "runtime"
    catalog_root = tmp_path / "catalog"
    draft_id = "action-registration-validation-1"
    checksum = "a" * 64
    connector = {
        "connection_source": "agent_playground",
        "endpoint_connection_id": "ep-validation",
        "deployment_id": "deployment-validation",
        "project_id": "project-validation",
        "flow_id": "flow-validation",
        "endpoint_name": "boi-wiki-agent-loop",
        "endpoint": "/api/v1/run/flow-validation",
        "artifact_version": "1.1.0",
        "artifact_checksum": draft_checksum or checksum,
        "default_mode": "preview",
    }
    draft = {
        "draft_id": draft_id,
        "entry_kind": "action",
        "created_by": "100002",
        "status": "publish_requested",
        "validation": {
            "valid": True,
            "checks": ["schema", "dedupe", "rbac", "secret_scan"],
            "validated_by": "100002",
        },
        "catalog_applied": False,
        "request": {
            "title": "BoI Wiki Agent Loop Action",
            "business_goal": "Wiki와 Ontology를 근거로 답합니다.",
            "description": "exact Flow validation",
            "connector_kind": "langflow",
            "connector_config": connector,
            "execution_mode": "gateway",
            "action_contract": {
                "schema_version": "boi.action-contract.v1",
                "action_key": "agent-playground.100002.flow-validation",
                "inputs": {"fields": ["question", "task_ref", "save_mode"]},
                "outputs": {"fields": ["answer", "source_references"]},
            },
            "connector_binding": {
                "schema_version": "boi.connector-binding.v1",
                "kind": "langflow",
                "adapter": "agent_playground.langflow",
                "execution_mode": "gateway",
                "config": connector,
            },
            "input_schema": {
                "question": {"type": "string", "required": True},
                "task_ref": {"type": "string"},
                "save_mode": {
                    "type": "string",
                    "enum": ["preview", "private_draft"],
                    "default": "preview",
                },
            },
            "action_key": "agent-playground.100002.flow-validation",
            "risk_level": "low",
            "approval_required": False,
        },
        "catalog_patch_proposal": {
            "action_key": "agent-playground.100002.flow-validation",
            "title": "BoI Wiki Agent Loop Action",
        },
    }
    user = {
        "employee_id": "100002",
        "action": {"draft_id": draft_id, "status": "publish_requested"},
        "deployments": [
            {
                "endpoint_id": "ep-validation",
                "deployment_id": "deployment-validation",
                "project_id": "project-validation",
                "flow_id": "flow-validation",
                "asset_version": "1.1.0",
                "artifact_checksum": checksum,
                "status": "action_linked",
                "action_draft_id": draft_id,
            }
        ],
        "flow_registry": [
            {
                "endpoint_id": "ep-validation",
                "project_id": "project-validation",
                "flow_id": "flow-validation",
                "action_draft_id": draft_id,
            }
        ],
    }
    draft_path = runtime_root / "drafts" / "registration_drafts" / f"{draft_id}.json"
    user_path = runtime_root / "agent-playground" / "users" / "100002.json"
    draft_path.parent.mkdir(parents=True)
    user_path.parent.mkdir(parents=True)
    draft_path.write_text(json.dumps(draft), encoding="utf-8")
    user_path.write_text(json.dumps(user), encoding="utf-8")
    return runtime_root, catalog_root, draft_id


def test_validation_operator_applies_only_exact_publish_requested_flow(tmp_path):
    runtime_root, catalog_root, draft_id = validation_state(tmp_path)
    evidence = tmp_path / "evidence" / "exact-action-chain.json"

    result = apply_fixture(
        runtime_root=runtime_root,
        catalog_root=catalog_root,
        employee_id="100002",
        draft_id=draft_id,
        evidence_file=evidence,
    )

    catalog = yaml.safe_load(Path(result["catalog_file"]).read_text(encoding="utf-8"))
    action = catalog["actions"][0]
    assert action["flow_id"] == "flow-validation"
    assert action["connector_config"]["deployment_id"] == "deployment-validation"
    assert action["execution_mode"] == "gateway"
    assert action["action_contract"]["schema_version"] == "boi.action-contract.v1"
    assert action["connector_binding"]["kind"] == "langflow"
    assert action["input_schema"]["required"] == ["question"]
    assert set(action["input_schema"]["properties"]) == {"question", "task_ref", "save_mode"}
    assert action["validation_provenance"]["artifact_checksum"] == "a" * 64
    assert "api_key" not in json.dumps(catalog)
    assert json.loads(evidence.read_text(encoding="utf-8"))["action_key"] == action["action_key"]
    applied = json.loads(
        (runtime_root / "drafts" / "registration_drafts" / f"{draft_id}.json").read_text(encoding="utf-8")
    )
    assert applied["catalog_applied"] is True
    user = json.loads(
        (runtime_root / "agent-playground" / "users" / "100002.json").read_text(encoding="utf-8")
    )
    assert user["action"]["status"] == "catalog_applied"
    assert user["deployments"][0]["status"] == "action_linked"
    assert user["flow_registry"][0]["validation_status"] == "action_linked"
    assert user["deployments"][0]["action_key"] == action["action_key"]


def test_validation_operator_rejects_checksum_mismatch_without_catalog_write(tmp_path):
    runtime_root, catalog_root, draft_id = validation_state(tmp_path, draft_checksum="b" * 64)

    with pytest.raises(RuntimeError, match="do not match"):
        apply_fixture(
            runtime_root=runtime_root,
            catalog_root=catalog_root,
            employee_id="100002",
            draft_id=draft_id,
        )

    assert not catalog_root.exists()
