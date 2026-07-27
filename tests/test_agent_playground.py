from __future__ import annotations

import copy
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi import HTTPException

from boi_api.app.agent_playground import (
    AgentPlaygroundService,
    PlaygroundBootstrapRequest,
    PlaygroundConnectRequest,
    PlaygroundDeploymentRequest,
    PlaygroundEndpointCreateRequest,
    PlaygroundEndpointTestRequest,
    PlaygroundEndpointUpdateRequest,
    PlaygroundFlowTestRequest,
    PlaygroundFlowValidationRequest,
    PlaygroundHubAdoptionBeginRequest,
    PlaygroundHubAdoptionComposeRequest,
    PlaygroundHubAdoptionConfirmRequest,
    SecretCipher,
    normalize_langflow_endpoint,
    require_langflow_111,
)
from boi_api.app.agent_playground_credentials import (
    PlaygroundCredentialService,
    TokenCreateRequest,
)
from boi_api.app.auth import AuthIdentity


ROOT = Path(__file__).resolve().parents[1]


def principal(
    employee_id: str,
    *,
    roles: list[str],
    auth_source: str = "dev",
) -> AuthIdentity:
    return AuthIdentity(
        employee_id=employee_id,
        display_name=f"User {employee_id}",
        teams=["platform"],
        roles=roles,
        auth_source=auth_source,
    )


def test_langflow_111_version_and_endpoint_contract():
    assert normalize_langflow_endpoint("https://langflow.example/api/v1/run/flow-1") == "https://langflow.example"
    assert normalize_langflow_endpoint("http:/localhost:7861/flow/flow-1?x=1#trace") == "http://localhost:7861"
    assert normalize_langflow_endpoint('"Langflow.Example:7860/some/path"') == "https://langflow.example:7860"
    require_langflow_111("1.11.0")
    require_langflow_111("1.11.9")

    with pytest.raises(HTTPException) as old:
        require_langflow_111("1.10.4")
    assert old.value.status_code == 409

    with pytest.raises(HTTPException) as beta:
        require_langflow_111("1.12.0")
    assert beta.value.status_code == 409


def test_secret_cipher_is_owner_bound():
    cipher = SecretCipher("dedicated-playground-secret")
    encrypted = cipher.encrypt("lf-api-key", owner="100001")

    assert encrypted != "lf-api-key"
    assert cipher.decrypt(encrypted, owner="100001") == "lf-api-key"
    with pytest.raises(Exception):
        cipher.decrypt(encrypted, owner="100002")


def test_flow_display_snapshot_is_secret_free_and_follows_graph_order():
    def node(node_id: str, component_name: str, display_name: str) -> dict:
        return {
            "id": node_id,
            "data": {
                "type": component_name,
                "display_name": display_name,
                "node": {
                    "name": component_name,
                    "display_name": display_name,
                    "template": {
                        "code": {
                            "value": "secret source must never be returned"
                        }
                    },
                },
            },
        }

    flow = {
        "name": "Grounded Action Flow",
        "description": "Uses boi_pat_0123456789abcdef_abcdefghijklmnopqrstuvwxyz",
        "endpoint_name": "grounded-action",
        "data": {
            # Deliberately not serialized in execution order.
            "nodes": [
                node("output", "ChatOutput", "Chat Output"),
                node("agent", "Agent", "Model Agent"),
                node("input", "ChatInput", "Chat Input"),
                node("knowledge", "BoIWikiKnowledge", "Wiki·Ontology 지식"),
            ],
            "edges": [
                {"source": "knowledge", "target": "agent"},
                {"source": "input", "target": "knowledge"},
                {"source": "agent", "target": "output"},
            ],
        },
    }

    snapshot = AgentPlaygroundService.flow_display_snapshot(flow)

    assert snapshot["description"] == "[비밀값 제거됨]"
    assert [item["role"] for item in snapshot["nodes"]] == [
        "input",
        "knowledge",
        "agent",
        "output",
    ]
    assert snapshot["end_to_end_reachable"] is True
    serialized = json.dumps(snapshot, ensure_ascii=False)
    assert "secret source" not in serialized
    assert "boi_pat_" not in serialized
    assert "template" not in serialized


def test_action_flow_view_hides_personal_links_from_shared_viewer(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv(
        "BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY",
        "test-playground-encryption",
    )
    monkeypatch.setenv("LANGFLOW_EXTERNAL_URL", "http://localhost:7867")
    owner = principal(
        "100002",
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    teammate = principal(
        "100001",
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    credentials = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda employee_id: owner,
    )
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, credentials)
    flow = {
        "id": "flow-shared",
        "name": "Team Grounded Flow",
        "description": "Ontology grounded team Action",
        "endpoint_name": "team-grounded-flow",
        "folder_id": "project-100002",
        "data": {
            "nodes": [
                {
                    "id": "input",
                    "data": {
                        "type": "ChatInput",
                        "display_name": "Chat Input",
                        "node": {"name": "ChatInput"},
                    },
                },
                {
                    "id": "output",
                    "data": {
                        "type": "ChatOutput",
                        "display_name": "Chat Output",
                        "node": {"name": "ChatOutput"},
                    },
                },
            ],
            "edges": [{"source": "input", "target": "output"}],
        },
    }
    checksum = service._runtime_flow_checksum(flow)
    endpoint_id = "ep-owner"
    deployment_id = "hub-shared"
    service._write(
        owner.employee_id,
        {
            "employee_id": owner.employee_id,
            "endpoints": [
                {
                    "endpoint_id": endpoint_id,
                    "name": "Owner Langflow",
                    "base_url": "http://langflow.example",
                    "endpoint": "http://langflow.example",
                    "api_key_encrypted": service.cipher.encrypt(
                        "lf-owner-key",
                        owner=owner.employee_id,
                    ),
                    "active": True,
                }
            ],
            "endpoint_setups": {
                endpoint_id: {
                    "project": {
                        "id": "project-100002",
                        "name": "boi-100002",
                    }
                }
            },
            "deployments": [
                {
                    "deployment_id": deployment_id,
                    "endpoint_id": endpoint_id,
                    "project_id": "project-100002",
                    "flow_id": flow["id"],
                    "flow_name": flow["name"],
                    "asset_version": "1.1.0",
                    "artifact_checksum": checksum,
                    "validated_checksum": checksum,
                    "checksum_state": "matched",
                    "status": "action_linked",
                }
            ],
        },
    )
    monkeypatch.setattr(service.langflow, "flow", lambda endpoint, api_key, flow_id: flow)
    snapshot = service.flow_display_snapshot(flow)
    action = {
        "action_key": "team.grounded",
        "connector_kind": "langflow",
        "owner_employee_id": owner.employee_id,
        "connector_binding": {
            "kind": "langflow",
            "deployment_reference": {
                "endpoint_connection_id": endpoint_id,
                "deployment_id": deployment_id,
                "project_id": "project-100002",
                "flow_id": flow["id"],
                "artifact_version": "1.1.0",
                "artifact_checksum": checksum,
            },
            "config": {
                "connection_source": "agent_playground",
                "flow_display_snapshot": snapshot,
            },
        },
    }

    owner_view = service.action_flow_view(owner, action)
    shared_view = service.action_flow_view(teammate, action)

    assert owner_view["flow"]["name"] == "Team Grounded Flow"
    assert owner_view["links"]["playground"].startswith("/playground?")
    assert owner_view["links"]["langflow"].startswith("http://localhost:7867/")
    assert owner_view["technical"]["flow_id"] == flow["id"]
    assert shared_view["owner_label"] == "공유된 Action Flow"
    assert shared_view["links"] == {"playground": "", "langflow": ""}
    assert shared_view["technical"] == {}
    assert json.dumps(shared_view, ensure_ascii=False).find("lf-owner-key") == -1


def test_permanent_pat_and_single_execution_run_token(tmp_path):
    current = principal(
        "100002",
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="stable-pat-hash-secret",
        identity_provider=lambda employee_id: current,
    )
    store = pats.store

    issued = pats.create(
        current,
        TokenCreateRequest(
            name="Agent Playground",
            scopes=["boi.read", "boi.draft"],
            expires_in_days=None,
        ),
    )
    stored = store.get("tokens", issued["token_id"])
    assert issued["expires_at"] is None
    assert stored is not None
    assert stored["expires_at"] is None
    assert stored["token_hash"] != issued["token"]
    assert issued["token"] not in json.dumps(stored)
    assert pats.authenticate(issued["token"]).identity.employee_id == "100002"

    run = pats.create_run_token(
        current,
        action_key="agent-playground.100002.boi-wiki-agent-loop",
        flow_id="flow-100002",
        trace_id="trace-1",
        scopes=["boi.read", "boi.draft"],
        ttl_seconds=60,
    )
    authenticated = pats.authenticate_run_token(run["token"])
    assert authenticated is not None
    assert authenticated.identity.employee_id == "100002"
    assert authenticated.identity.auth_source == "run_token"
    assert store.get("run_tokens", run["token_id"])["flow_id"] == "flow-100002"
    assert pats.consume_run_token(run["token_id"]) is True
    assert pats.authenticate_run_token(run["token"]) is None
    assert pats.consume_run_token(run["token_id"]) is False


def test_other_authors_approved_agent_hub_flow_and_components_are_adopted_by_exact_runtime_change(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    monkeypatch.setenv("AGENT_HUB_API_URL", "http://agent-hub.example")
    monkeypatch.setenv("AGENT_HUB_EXTERNAL_URL", "http://agent-hub.example/AgentHub.html")
    developer = principal(
        "100002",
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    project = {"id": "project-100002", "name": "boi-100002"}
    flows = [
        {
            "id": "flow-existing",
            "name": "Work in progress",
            "folder_id": project["id"],
            "data": {"nodes": ["ChatInput"], "edges": []},
        }
    ]
    assets = {
        "11111111-1111-1111-1111-111111111111": {
            "id": "11111111-1111-1111-1111-111111111111",
            "title": "Other Author Grounded Flow",
            "type": "json",
            "description": "An approved Flow from another employee",
            "category": "agent",
            "version": "1.4.0",
            "min_langflow_ver": "1.11.0",
            "max_langflow_ver": "1.11.9",
            "tested_versions": ["1.11.0"],
            "tags": ["grounded"],
            "is_standard": True,
            "status": "approved",
            "author": {
                "employee_id": "100001",
                "name": "Other Author",
                "team": "platform",
                "org": "AIX",
            },
            "updated_at": "2026-07-26T00:00:00Z",
        },
        "22222222-2222-2222-2222-222222222222": {
            "id": "22222222-2222-2222-2222-222222222222",
            "title": "Other Author Rich Tool",
            "type": "py",
            "description": "A reusable custom component",
            "category": "tool",
            "version": "2.1.0",
            "min_langflow_ver": "1.11.0",
            "max_langflow_ver": "1.11.9",
            "tested_versions": ["1.11.0"],
            "tags": ["custom"],
            "is_standard": False,
            "status": "approved",
            "component_contract": {
                "schema_version": "boi.agent-slot.v1",
                "inputs": ["agent_context"],
                "outputs": ["agent_result"],
            },
            "author": {
                "employee_id": "100001",
                "name": "Other Author",
                "team": "platform",
                "org": "AIX",
            },
            "updated_at": "2026-07-26T00:00:00Z",
        },
        "33333333-3333-3333-3333-333333333333": {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "Ambiguous Multi Port Tool",
            "type": "py",
            "description": "A component that must be connected manually",
            "category": "tool",
            "version": "1.0.0",
            "min_langflow_ver": "1.11.0",
            "max_langflow_ver": "1.11.9",
            "tested_versions": ["1.11.0"],
            "tags": ["custom"],
            "is_standard": False,
            "status": "approved",
            "component_contract": {
                "schema_version": "vendor.multi-port.v1",
                "inputs": ["query", "context"],
                "outputs": ["answer", "debug"],
            },
            "author": {
                "employee_id": "100001",
                "name": "Other Author",
                "team": "platform",
                "org": "AIX",
            },
            "updated_at": "2026-07-26T00:00:00Z",
        },
    }
    patch_calls: list[str] = []

    def hub_request(path, *, params=None, expected=None):
        if path.startswith("/api/v1/components/"):
            return dict(assets[path.rsplit("/", 1)[-1]])
        rows = list(assets.values())
        if params and params.get("search"):
            query = str(params["search"]).lower()
            rows = [item for item in rows if query in item["title"].lower()]
        if params and params.get("type"):
            rows = [item for item in rows if item["type"] == params["type"]]
        return {"items": rows, "total": len(rows), "limit": 1000, "offset": 0}

    def response(payload, status=200):
        return httpx.Response(status, json=payload)

    def fake_request(method, endpoint, path, api_key, **kwargs):
        assert endpoint == "http://langflow.example:7860"
        assert api_key == "lf-key-100002"
        if path == "/health":
            return response({"status": "ok"})
        if path == "/api/v1/version":
            return response({"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return response(
                {
                    "id": "lf-user-100002",
                    "username": "100002",
                    "is_active": True,
                }
            )
        if path == "/api/v1/projects/":
            return response([project])
        if path == "/api/v1/flows/":
            return response(
                [
                    {
                        key: value
                        for key, value in item.items()
                        if key != "data"
                    }
                    for item in flows
                ]
            )
        if path.startswith("/api/v1/flows/") and method == "GET":
            flow_id = path.rsplit("/", 1)[-1]
            return response(dict(next(item for item in flows if item["id"] == flow_id)))
        if path.startswith("/api/v1/flows/") and method == "PATCH":
            patch_calls.append(path)
            flow_id = path.rsplit("/", 1)[-1]
            target = next(item for item in flows if item["id"] == flow_id)
            target.update(copy.deepcopy(kwargs["json"]))
            return response(dict(target))
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_agent_hub_request", hub_request)
    monkeypatch.setattr(service, "_request", fake_request)
    endpoint_id = service.create_endpoint(
        developer,
        PlaygroundEndpointCreateRequest(
            name="Personal Langflow",
            base_url="http://langflow.example:7860",
            api_key="lf-key-100002",
            make_default=True,
        ),
    )["endpoint"]["endpoint_id"]

    started = service.begin_hub_adoption(
        developer,
        PlaygroundHubAdoptionBeginRequest(
            endpoint_id=endpoint_id,
            project_id=project["id"],
            asset_ids=list(assets),
            validation_profile="boi_knowledge_draft",
        ),
    )["adoption"]
    assert started["snapshot"]["flow_ids"] == ["flow-existing"]
    assert {item["author"]["employee_id"] for item in started["source_assets"]} == {"100001"}

    imported = json.loads(
        (ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json").read_text(
            encoding="utf-8"
        )
    )
    imported.update(
        {
            "id": "flow-imported-exact",
            "name": "Other Author Grounded Flow",
            "endpoint_name": "other-author-grounded-flow",
            "folder_id": project["id"],
            "project_id": project["id"],
        }
    )
    imported["data"]["nodes"].append(
        {
            "id": "OtherAuthorRichTool-flow-imported-exact",
            "type": "genericNode",
            "data": {
                "type": "OtherAuthorRichTool",
                "display_name": "Other Author Rich Tool",
                "node": {
                    "name": "OtherAuthorRichTool",
                    "display_name": "Other Author Rich Tool",
                    "metadata": {},
                    "template": {
                        "agent_context": {
                            "name": "agent_context",
                            "input_types": ["Data", "JSON"],
                            "type": "other",
                        }
                    },
                    "outputs": [
                        {
                            "name": "agent_result",
                            "types": ["Data", "JSON"],
                        }
                    ],
                },
            },
        }
    )
    flows.append(imported)
    discovered = service.discover_hub_adoption(developer, started["adoption_id"])
    assert discovered["candidates"] == [
        {
            "flow_id": "flow-imported-exact",
            "name": "Other Author Grounded Flow",
            "endpoint_name": "other-author-grounded-flow",
            "runtime_checksum": discovered["candidates"][0]["runtime_checksum"],
            "updated_at": "",
            "change_kind": "created",
        }
    ]
    confirmed = service.confirm_hub_adoption(
        developer,
        started["adoption_id"],
        PlaygroundHubAdoptionConfirmRequest(flow_id="flow-imported-exact"),
    )
    deployment = confirmed["deployment"]
    assert deployment["employee_id"] == "100002"
    assert deployment["origin"] == "agent_hub_approved_asset"
    assert deployment["flow_id"] == "flow-imported-exact"
    assert deployment["artifact_checksum"] == discovered["candidates"][0]["runtime_checksum"]
    assert deployment["validation_profile"] == "boi_knowledge_draft"
    assert {item["asset_id"] for item in deployment["source_assets"]} == set(assets)
    assert {item["author"]["employee_id"] for item in deployment["source_assets"]} == {"100001"}
    before_compose = service._graph_health(imported)
    assert "OtherAuthorRichTool-flow-imported-exact" in before_compose["disconnected_nodes"]

    manual = service.compose_hub_adoption(
        developer,
        started["adoption_id"],
        PlaygroundHubAdoptionComposeRequest(
            flow_id="flow-imported-exact",
            component_asset_id="33333333-3333-3333-3333-333333333333",
            replace_agent_slot=True,
        ),
    )
    assert manual["status"] == "manual_required"
    assert manual["reason"] == "component_contract_incompatible"
    assert manual["actual_contract"]["inputs"] == ["query", "context"]
    assert patch_calls == []

    composed = service.compose_hub_adoption(
        developer,
        started["adoption_id"],
        PlaygroundHubAdoptionComposeRequest(
            flow_id="flow-imported-exact",
            component_asset_id="22222222-2222-2222-2222-222222222222",
            replace_agent_slot=True,
        ),
    )
    assert composed["status"] == "connected", composed
    assert composed["previous_checksum"] != composed["live_checksum"]
    assert composed["graph_health"]["end_to_end_reachable"] is True
    assert composed["graph_health"]["connected_component_ids"] == [
        "22222222-2222-2222-2222-222222222222"
    ]
    assert patch_calls == ["/api/v1/flows/flow-imported-exact"]
    assert "BoIAgentSlot-boi-wiki-agent-loop" not in {
        node["id"] for node in imported["data"]["nodes"]
    }

    record = service._read("100002")
    stored = next(
        item
        for item in record["deployments"]
        if item["deployment_id"] == deployment["deployment_id"]
    )
    stored["status"] = "action_ready"
    service._write("100002", record)
    draft = service.action_draft_payload(developer, deployment["deployment_id"])
    assert draft["connector_config"]["flow_id"] == "flow-imported-exact"
    assert draft["connector_config"]["source_origin"] == "agent_hub_approved_asset"
    assert {
        item["asset_id"]
        for item in draft["connector_config"]["source_assets"]
    } == set(assets)
    assert all(
        item["update_available"] is False
        for item in draft["connector_config"]["source_assets"]
    )


def test_agent_hub_component_update_is_detected_but_unapproved_asset_is_blocked(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    monkeypatch.setenv("AGENT_HUB_API_URL", "http://agent-hub.example")
    developer = principal("100002", roles=["boi.viewer", "boi.editor"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    project = {"id": "project-100002", "name": "boi-100002"}
    flow = {
        "id": "flow-existing",
        "name": "Work in progress",
        "folder_id": project["id"],
        "data": {"nodes": ["ChatInput"], "edges": []},
    }
    approved_id = "33333333-3333-3333-3333-333333333333"
    pending_id = "44444444-4444-4444-4444-444444444444"
    approved = {
        "id": approved_id,
        "title": "Rich Shared Component",
        "type": "py",
        "version": "1.0.0",
        "min_langflow_ver": "1.11.0",
        "max_langflow_ver": "1.11.9",
        "status": "approved",
        "author": {"employee_id": "100001", "name": "Other Author"},
    }
    pending = {**approved, "id": pending_id, "title": "Pending Component", "status": "pending"}

    def hub_request(path, *, params=None, expected=None):
        if path.endswith(approved_id):
            return dict(approved)
        if path.endswith(pending_id):
            return dict(pending)
        rows = [approved]
        if params and params.get("search"):
            rows = [
                item
                for item in rows
                if str(params["search"]).lower() in item["title"].lower()
            ]
        return {"items": rows, "total": len(rows)}

    def fake_request(method, endpoint, path, api_key, **kwargs):
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return httpx.Response(
                200,
                json={"id": "lf-user-100002", "username": "100002", "is_active": True},
            )
        if path == "/api/v1/projects/":
            return httpx.Response(200, json=[project])
        if path == "/api/v1/flows/":
            return httpx.Response(
                200,
                json=[{key: value for key, value in flow.items() if key != "data"}],
            )
        if path == "/api/v1/flows/flow-existing":
            return httpx.Response(200, json=dict(flow))
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_agent_hub_request", hub_request)
    monkeypatch.setattr(service, "_request", fake_request)
    endpoint_id = service.create_endpoint(
        developer,
        PlaygroundEndpointCreateRequest(
            name="Personal Langflow",
            base_url="http://langflow.example:7860",
            api_key="lf-key-100002",
            make_default=True,
        ),
    )["endpoint"]["endpoint_id"]
    with pytest.raises(HTTPException) as denied:
        service.agent_hub_asset(developer, pending_id)
    assert denied.value.status_code == 409
    assert denied.value.detail["code"] == "agent_hub_asset_not_approved"

    adoption = service.begin_hub_adoption(
        developer,
        PlaygroundHubAdoptionBeginRequest(
            endpoint_id=endpoint_id,
            project_id=project["id"],
            asset_ids=[approved_id],
            validation_profile="generic_action",
        ),
    )["adoption"]
    flow["data"]["nodes"].append("RichSharedComponent")
    discovered = service.discover_hub_adoption(developer, adoption["adoption_id"])
    assert len(discovered["candidates"]) == 1
    assert discovered["candidates"][0]["flow_id"] == "flow-existing"
    assert discovered["candidates"][0]["change_kind"] == "updated"
    confirmed = service.confirm_hub_adoption(
        developer,
        adoption["adoption_id"],
        PlaygroundHubAdoptionConfirmRequest(flow_id="flow-existing"),
    )
    assert confirmed["deployment"]["validation_profile"] == "generic_action"
    assert confirmed["deployment"]["source_assets"][0]["type"] == "py"


def test_viewer_bootstrap_gets_read_only_pat_and_secret_free_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    viewer = principal("100003", roles=["boi.viewer"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda employee_id: viewer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    variables: list[dict] = []
    projects: list[dict] = []
    flows: list[dict] = []

    def response(payload, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=payload)

    def fake_request(method, endpoint, path, api_key, **kwargs):
        assert api_key == "lf-key-100003"
        assert endpoint == "http://langflow.example:7860"
        if path == "/health":
            return response({"status": "ok"})
        if path == "/api/v1/version":
            return response({"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return response(
                {
                    "id": "lf-user-100003",
                    "username": "100003",
                    "is_active": True,
                    "is_superuser": False,
                }
            )
        if path == "/api/v1/projects/" and method == "GET":
            return response(projects)
        if path == "/api/v1/projects/" and method == "POST":
            project = {"id": "project-100003", "name": "boi-100003"}
            projects.append(project)
            return response(project, 201)
        if path == "/api/v1/all" and method == "GET":
            return response(
                {
                    "custom_components": [
                        "BoIWikiKnowledge",
                        "BoIWikiSave",
                        "BoIModelAgent",
                    ]
                }
            )
        if path == "/api/v1/variables/" and method == "GET":
            return response(variables)
        if path == "/api/v1/variables/" and method == "POST":
            body = dict(kwargs["json"])
            assert body["name"] == "BOI_WIKI_PAT"
            assert body["value"].startswith("boi_pat_")
            variables.append({"id": "variable-100003", "name": body["name"], "type": "Credential"})
            return response(variables[-1], 201)
        if path == "/api/v1/flows/" and method == "GET":
            return response(flows)
        if path == "/api/v1/flows/" and method == "POST":
            assert kwargs["json"]["folder_id"] == "project-100003"
            assert kwargs["json"]["project_id"] == "project-100003"
            assert isinstance(kwargs["json"]["data"], dict)
            flow = {
                "id": "flow-100003",
                "name": "BoI Wiki Agent Loop",
                "endpoint_name": "boi-wiki-agent-loop",
                "folder_id": "project-100003",
                "description": str(kwargs["json"].get("description") or ""),
                "data": copy.deepcopy(kwargs["json"]["data"]),
            }
            flows.append(flow)
            return response(flow, 201)
        if path == "/api/v1/flows/flow-100003" and method == "GET":
            return response(copy.deepcopy(flows[0]))
        if path == "/api/v1/run/flow-100003" and method == "POST":
            body = kwargs["json"]
            assert '"save_mode": "preview"' in body["input_value"]
            return response({"session_id": "flow-100003", "outputs": []})
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)

    connected = service.connect(
        viewer,
        PlaygroundConnectRequest(endpoint="http://langflow.example:7860", api_key="lf-key-100003"),
    )
    assert connected["connection"]["langflow_user_id"] == "lf-user-100003"
    assert "api_key_encrypted" not in connected["connection"]
    state_path = tmp_path / "runtime" / "agent-playground" / "users" / "100003.json"
    assert "lf-key-100003" not in state_path.read_text(encoding="utf-8")

    bootstrapped = service.bootstrap(viewer, PlaygroundBootstrapRequest())
    state = bootstrapped["state"]
    assert state["project"]["name"] == "boi-100003"
    assert state["flow"]["id"] == "flow-100003"
    assert state["wiki"]["pat_expires_at"] is None
    assert state["onboarding"]["required"] is False
    assert state["onboarding"]["status"] == "ready"
    assert state["journey"]["current_stage"] == "create"
    assert state["journey"]["next_action"]["id"] == "open_langflow"
    assert state["journey"]["completed_stages"] == ["onboarding", "create"]
    assert state["hub_onboarding"] == {
        "required": True,
        "status": "not_started",
        "next_action": "open_agent_hub",
        "message": "첫 배포 전에 endpoint 연결과 프로젝트 선택을 안내합니다.",
    }
    rerun = service.bootstrap(viewer, PlaygroundBootstrapRequest())["state"]
    assert rerun["project"]["id"] == state["project"]["id"]
    assert rerun["flow"]["id"] == state["flow"]["id"]
    listed = service.flows(
        viewer,
        state["default_endpoint_id"],
        state["project"]["id"],
    )["flows"]
    assert len(listed) == 1
    assert listed[0]["validation_status"] == "runtime_validated"
    assert listed[0]["checksum_state"] == "matched"
    rerun_record = service._read("100003")
    assert listed[0]["live_checksum"] == (
        rerun_record["endpoint_setups"][state["default_endpoint_id"]]
        ["canonical_flow"]["validated_checksum"]
    )
    journey_record = service._read("100003")
    journey_record.setdefault("flow_registry", []).append(
        {
            "endpoint_id": state["default_endpoint_id"],
            "project_id": state["project"]["id"],
            "flow_id": state["flow"]["id"],
            "validation_status": "action_ready",
        },
    )
    service._write("100003", journey_record)
    ready_for_hub = service.state(viewer)
    assert ready_for_hub["journey"]["current_stage"] == "hub"
    assert ready_for_hub["journey"]["next_action"]["id"] == "open_agent_hub"
    assert state["endpoint_setups"][state["default_endpoint_id"]]["smoke"]["status"] == "passed"
    assert state["endpoint_setups"][state["default_endpoint_id"]]["bundle"] == {
        "version": "1.1.0",
        "mode": "read_only_extension",
        "verified": True,
        "components": {
            "BoIWikiKnowledge": True,
            "BoIWikiSave": True,
            "BoIModelAgent": True,
        },
    }
    token = store.get("tokens", service._read("100003")["wiki_credential"]["token_id"])
    assert token is not None
    assert token["scopes"] == ["boi.read"]

    with pytest.raises(HTTPException) as denied:
        service.test_flow(
            viewer,
            "flow-100003",
            PlaygroundFlowTestRequest(
                question="private draft should be denied",
                save_mode="private_draft",
            ),
        )
    assert denied.value.status_code == 403

    bundle = service.artifact_bundle(viewer, "flow-100003")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = set(archive.namelist())
        assert "langflow/custom_components/boi/__init__.py" in names
        assert "langflow/custom_components/boi/boi_wiki_knowledge.py" in names
        assert "langflow/custom_components/boi/boi_wiki_save.py" in names
        assert "langflow/flows/boi_wiki_agent_loop.json" in names
        payload = b"\n".join(archive.read(name) for name in sorted(names)).decode("utf-8", errors="ignore")
    assert re.search(r"boi_(?:pat|run)_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}", payload) is None


def test_canonical_bundle_uses_checksum_identity_when_agent_hub_renames_flow(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    viewer = principal("100003", roles=["boi.viewer"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: viewer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    projects: list[dict] = []
    flows: list[dict] = []

    def response(payload, status: int = 200) -> httpx.Response:
        return httpx.Response(status, json=payload)

    def fake_request(method, endpoint, path, api_key, **kwargs):
        if path == "/health":
            return response({"status": "ok"})
        if path == "/api/v1/version":
            return response({"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return response({"id": "lf-user-100003", "username": "100003", "is_active": True})
        if path == "/api/v1/projects/" and method == "GET":
            return response(projects)
        if path == "/api/v1/projects/" and method == "POST":
            project = {"id": "project-100003", "name": "boi-100003"}
            projects.append(project)
            return response(project, 201)
        if path == "/api/v1/all" and method == "GET":
            return response(
                {
                    "custom_components": [
                        "BoIWikiKnowledge",
                        "BoIWikiSave",
                        "BoIModelAgent",
                    ]
                }
            )
        if path == "/api/v1/variables/" and method == "GET":
            return response([])
        if path == "/api/v1/variables/" and method == "POST":
            return response({"id": "variable-100003", "name": "BOI_WIKI_PAT", "type": "Credential"}, 201)
        if path == "/api/v1/flows/" and method == "GET":
            return response(flows)
        if path == "/api/v1/flows/" and method == "POST":
            flow = {
                "id": "flow-100003",
                "name": "BoI Wiki Agent Loop",
                "endpoint_name": "boi-wiki-agent-loop",
                "folder_id": "project-100003",
            }
            flows.append(flow)
            return response(flow, 201)
        if path == "/api/v1/run/flow-100003" and method == "POST":
            return response({"session_id": "flow-100003", "outputs": []})
        if path == "/api/v1/flows/flow-100003" and method == "GET":
            return response(flows[0])
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)
    service.connect(
        viewer,
        PlaygroundConnectRequest(endpoint="http://langflow.example:7860", api_key="lf-key-100003"),
    )
    service.bootstrap(viewer, PlaygroundBootstrapRequest())
    flows[0]["name"] = "BoI Wiki Agent Loop 1.1.0 · Task Ontology Contract"
    flows[0]["endpoint_name"] = ""

    bundle = service.artifact_bundle(viewer, "flow-100003")
    with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
        names = set(archive.namelist())
        assert "langflow/flows/boi_wiki_agent_loop.json" in names
        manifest = json.loads(archive.read("langflow/agent_hub/flow.manifest.json"))
        bundled_flow = archive.read("langflow/flows/boi_wiki_agent_loop.json")

    canonical_flow = (ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json").read_bytes()
    assert bundled_flow == canonical_flow
    assert manifest["name"] == "BoI Wiki Agent Loop"
    assert manifest["endpoint_name"] == "boi-wiki-agent-loop"
    assert manifest["artifact_checksum"] == hashlib.sha256(canonical_flow).hexdigest()


def test_langflow_user_cannot_be_shared_between_employees(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    principals = {
        "100001": principal("100001", roles=["boi.viewer", "boi.editor"]),
        "100002": principal("100002", roles=["boi.viewer", "boi.editor"]),
    }
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda employee_id: principals[employee_id],
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)

    def fake_request(method, endpoint, path, api_key, **kwargs):
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            employee_id = "100001" if api_key == "lf-key-100001" else "100002"
            return httpx.Response(
                200,
                json={
                    "id": "shared-langflow-user",
                    "username": employee_id,
                    "is_active": True,
                },
            )
        if path == "/api/v1/projects/":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)
    service.connect(
        principals["100001"],
        PlaygroundConnectRequest(endpoint="http://langflow.example:7860", api_key="lf-key-100001"),
    )
    with pytest.raises(HTTPException) as conflict:
        service.connect(
            principals["100002"],
            PlaygroundConnectRequest(endpoint="http://langflow.example:7860", api_key="lf-key-100002"),
        )
    assert conflict.value.status_code == 409


def test_endpoint_collection_enforces_limit_keeps_existing_key_and_never_returns_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    developer = principal("100002", roles=["boi.viewer", "boi.editor", "boi.action_invoker"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)

    def fake_request(method, endpoint, path, api_key, **kwargs):
        host = endpoint.split("//", 1)[-1]
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return httpx.Response(
                200,
                json={"id": f"lf-user-{host}", "username": "100002", "is_active": True},
            )
        if path == "/api/v1/projects/":
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)
    created = []
    for index in range(5):
        created.append(
            service.create_endpoint(
                developer,
                PlaygroundEndpointCreateRequest(
                    name=f"Endpoint {index + 1}",
                    base_url=f"http://langflow-{index + 1}.example:7860",
                    api_key=f"lf-key-100002-{index + 1}",
                    make_default=index == 0,
                ),
            )["endpoint"]
        )
    with pytest.raises(HTTPException) as limit:
        service.create_endpoint(
            developer,
            PlaygroundEndpointCreateRequest(
                name="Endpoint 6",
                base_url="http://langflow-6.example:7860",
                api_key="lf-key-100002-6",
            ),
        )
    assert limit.value.status_code == 409

    endpoint_id = created[0]["endpoint_id"]
    tested = service.test_unsaved_endpoint(
        developer,
        PlaygroundEndpointTestRequest(
            base_url="http://langflow-1.example:7860",
            api_key="lf-key-100002-1",
        ),
    )
    assert tested["connection"]["has_api_key"] is False
    updated = service.update_endpoint(
        developer,
        endpoint_id,
        PlaygroundEndpointUpdateRequest(name="Primary 1.11"),
    )
    assert updated["endpoint"]["name"] == "Primary 1.11"
    assert updated["endpoint"]["has_api_key"] is True
    serialized = json.dumps(service.endpoints(developer), ensure_ascii=False)
    assert "lf-key-100002" not in serialized
    state_file = tmp_path / "runtime" / "agent-playground" / "users" / "100002.json"
    assert "lf-key-100002" not in state_file.read_text(encoding="utf-8")


def test_onboarding_is_endpoint_scoped_and_legacy_state_migrates_without_asset_loss(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    developer = principal("100002", roles=["boi.viewer", "boi.editor", "boi.action_invoker"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    canonical_checksum = hashlib.sha256(
        (ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json").read_bytes()
    ).hexdigest()
    endpoint_one = {
        "endpoint_id": "ep-one",
        "name": "Primary",
        "base_url": "http://langflow-one.example:7860",
        "endpoint": "http://langflow-one.example:7860",
        "api_key_encrypted": service.cipher.encrypt("lf-key-one", owner="100002"),
        "api_key_fingerprint": "fingerprint1",
        "langflow_user_id": "lf-user-one",
        "langflow_username": "100002",
        "version": "1.11.0",
        "status": "connected",
        "active": True,
    }
    endpoint_two = {
        "endpoint_id": "ep-two",
        "name": "Secondary",
        "base_url": "http://langflow-two.example:7860",
        "endpoint": "http://langflow-two.example:7860",
        "api_key_encrypted": service.cipher.encrypt("lf-key-two", owner="100002"),
        "api_key_fingerprint": "fingerprint2",
        "langflow_user_id": "lf-user-two",
        "langflow_username": "100002",
        "version": "1.11.0",
        "status": "connected",
        "active": True,
    }
    legacy_project = {"id": "project-one", "name": "boi-100002", "endpoint_id": "ep-one"}
    legacy_flow = {
        "id": "flow-one",
        "name": "BoI Wiki Agent Loop",
        "endpoint_name": "boi-wiki-agent-loop",
        "version": "1.1.0",
        "endpoint_id": "ep-one",
        "project_id": "project-one",
        "flow_url": "http://langflow-one.example:7860/flow/flow-one",
    }
    credential = {
        "token_id": "token-one",
        "variable_name": "BOI_WIKI_PAT",
        "expires_at": None,
    }
    service._write(
        "100002",
        {
            "employee_id": "100002",
            "created_at": "2026-07-25T00:00:00+00:00",
            "endpoints": [endpoint_one, endpoint_two],
            "default_endpoint_id": "ep-one",
            "project": legacy_project,
            "canonical_flow": legacy_flow,
            "canonical_flows": [legacy_flow],
            "wiki_credential": credential,
            "wiki_credentials": {"ep-one": credential},
            "flow_registry": [
                {
                    "endpoint_id": "ep-one",
                    "project_id": "project-one",
                    "flow_id": "flow-one",
                    "artifact_version": "1.1.0",
                    "artifact_checksum": canonical_checksum,
                    "validation_status": "runtime_validated",
                }
            ],
            "last_test": {
                "status": "passed",
                "mode": "preview",
                "tested_at": "2026-07-25T00:05:00+00:00",
                "endpoint_id": "ep-one",
                "project_id": "project-one",
                "flow_id": "flow-one",
            },
        },
    )

    state = service.state(developer, live=False)
    assert state["onboarding"]["required"] is True
    assert state["endpoint_setups"]["ep-one"]["readiness"]["ready"] is False
    assert state["endpoint_setups"]["ep-one"]["readiness"]["checks"]["bundle"] is False
    assert state["endpoint_setups"]["ep-one"]["canonical_flow"]["id"] == "flow-one"
    assert state["endpoint_setups"]["ep-two"]["readiness"]["ready"] is False
    assert state["endpoint_setups"]["ep-two"]["onboarding"]["current_step"] == "knowledge"
    persisted = service._read("100002")
    assert persisted["project"] == legacy_project
    assert persisted["canonical_flow"]["id"] == "flow-one"
    assert set(persisted["endpoint_setups"]) == {"ep-one", "ep-two"}


def test_bootstrap_failure_records_recoverable_onboarding_step(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    developer = principal("100002", roles=["boi.viewer", "boi.editor", "boi.action_invoker"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    project_reads = 0

    def fake_request(method, endpoint, path, api_key, **kwargs):
        nonlocal project_reads
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return httpx.Response(
                200,
                json={"id": "lf-user-100002", "username": "100002", "is_active": True},
            )
        if path == "/api/v1/projects/" and method == "GET":
            project_reads += 1
            if project_reads <= 2:
                return httpx.Response(200, json=[])
            raise HTTPException(status_code=502, detail="project API unavailable")
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)
    endpoint = service.create_endpoint(
        developer,
        PlaygroundEndpointCreateRequest(
            name="Personal 1.11",
            base_url="http://langflow.example:7860",
            api_key="lf-key-100002",
            make_default=True,
        ),
    )["endpoint"]
    with pytest.raises(HTTPException):
        service.bootstrap(
            developer,
            PlaygroundBootstrapRequest(endpoint_id=endpoint["endpoint_id"]),
        )
    state = service.state(developer, live=False)
    assert state["onboarding"]["status"] == "error"
    assert state["onboarding"]["current_step"] == "knowledge"
    assert state["onboarding"]["next_action"] == "retry_bootstrap"
    assert "project API unavailable" in state["onboarding"]["last_error"]


def test_each_discovered_flow_is_validated_independently_and_incompatible_flow_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    developer = principal("100002", roles=["boi.viewer", "boi.editor", "boi.action_invoker"])
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    projects = [{"id": "project-100002", "name": "boi-100002"}]
    flows = [
        {
            "id": "flow-canonical",
            "name": "BoI Wiki Agent Loop",
            "endpoint_name": "boi-wiki-agent-loop",
            "folder_id": "project-100002",
        },
        {
            "id": "flow-variant",
            "name": "BoI Wiki Agent Loop - SOP Decision",
            "endpoint_name": "boi-wiki-agent-loop-sop-decision",
            "folder_id": "project-100002",
        },
        {
            "id": "flow-incompatible",
            "name": "Plain Chat",
            "endpoint_name": "plain-chat",
            "folder_id": "project-100002",
        },
    ]
    canonical_data = json.loads(
        (ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json").read_text(encoding="utf-8")
    )["data"]

    def fake_request(method, endpoint, path, api_key, **kwargs):
        assert endpoint == "http://langflow.example:7860"
        assert api_key == "lf-key-100002"
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return httpx.Response(
                200,
                json={"id": "lf-user-100002", "username": "100002", "is_active": True},
            )
        if path == "/api/v1/projects/":
            return httpx.Response(200, json=projects)
        if path == "/api/v1/flows/":
            return httpx.Response(200, json=flows)
        if path.startswith("/api/v1/flows/") and method == "GET":
            flow_id = path.rsplit("/", 1)[-1]
            selected = dict(next(item for item in flows if item["id"] == flow_id))
            if flow_id != "flow-incompatible":
                selected["data"] = {
                    "nodes": (
                        ["BoIWikiKnowledge", "AgentHubRichCustomTool", "BoIWikiSave"]
                        if flow_id == "flow-variant"
                        else ["BoIWikiKnowledge", "BoIAgentSlot", "BoIWikiSave"]
                    ),
                    "boi_contract": canonical_data["boi_contract"],
                    "boi_contract_sha256": canonical_data["boi_contract_sha256"],
                }
            else:
                selected["data"] = {"nodes": ["ChatInput", "ChatOutput"]}
            return httpx.Response(200, json=selected)
        if path.startswith("/api/v1/run/") and method == "POST":
            run_input = json.loads(kwargs["json"]["input_value"])
            return httpx.Response(
                200,
                json={
                    "source_references": [{"ref": "boi:public:sop:test"}],
                    "ontology_relationships": [
                        {
                            "source_id": "task:test",
                            "target_id": "sop:test",
                            "relation": "단계",
                            "provenance": "extracted",
                            "source_refs": ["boi:public:sop:test"],
                        }
                    ],
                    "grounding_status": "grounded_with_ontology",
                    "provenance": {"document_refs": ["boi:public:sop:test"]},
                    "context_profile": (
                        "sop_task_execution" if run_input.get("task_ref") else "knowledge_lookup"
                    ),
                    "task_context": {
                        "profile": "sop_task_execution",
                        "task_ref": run_input.get("task_ref", ""),
                        "sop_ref": "boi:public:sop:equipment-abnormal-response",
                        "sop_stage": "analyze",
                        "event_ref": "evt:root-cause",
                        "action_ref": "langflow.equipment.stage_analysis",
                        "prior_results": [{"source_id": "action:trend"}],
                        "required_evidence": ["trend_history", "raw_data"],
                        "missing_evidence": ["raw_data"],
                    },
                },
            )
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)
    endpoint = service.create_endpoint(
        developer,
        PlaygroundEndpointCreateRequest(
            name="Personal 1.11",
            base_url="http://langflow.example:7860",
            api_key="lf-key-100002",
            make_default=True,
        ),
    )["endpoint"]
    endpoint_id = endpoint["endpoint_id"]
    deployment_ids = {}
    for flow in flows:
        deployment = service.record_deployment(
            developer,
            PlaygroundDeploymentRequest(
                endpoint_id=endpoint_id,
                project_id="project-100002",
                flow_id=flow["id"],
                endpoint_name=flow["endpoint_name"],
                asset_version="1.1.0",
            ),
        )["deployment"]
        deployment_ids[flow["id"]] = deployment["deployment_id"]

    for flow_id in ("flow-canonical", "flow-variant"):
        validation = service.validate_flow(
            developer,
            flow_id,
            PlaygroundFlowValidationRequest(
                endpoint_id=endpoint_id,
                project_id="project-100002",
                task_ref="task:test",
            ),
        )
        assert validation["validation_status"] == "action_ready"
        draft_payload = service.action_draft_payload(developer, deployment_ids[flow_id])
        assert draft_payload["connector_config"]["flow_id"] == flow_id
        assert draft_payload["execution_mode"] == "gateway"
        assert "execution_kind" not in draft_payload
        assert draft_payload["action_contract"]["schema_version"] == "boi.action-contract.v1"
        assert draft_payload["connector_binding"]["kind"] == "langflow"
        assert draft_payload["connector_binding"]["adapter"] == "agent_playground.langflow"
        assert draft_payload["connector_binding"]["deployment_reference"]["flow_id"] == flow_id
        if flow_id == "flow-canonical":
            service.record_action_draft(
                developer,
                deployment_ids[flow_id],
                {"draft_id": "draft-canonical", "status": "draft"},
            )
            revalidated = service.validate_flow(
                developer,
                flow_id,
                PlaygroundFlowValidationRequest(
                    endpoint_id=endpoint_id,
                    project_id="project-100002",
                    task_ref="task:test",
                ),
            )
            assert revalidated["validation_status"] == "action_linked"
            assert revalidated["ok"] is True
            service.test_flow(
                developer,
                flow_id,
                PlaygroundFlowTestRequest(
                    endpoint_id=endpoint_id,
                    project_id="project-100002",
                    question="Action 연결 후 runtime 재시험",
                    save_mode="preview",
                ),
            )
            linked = next(
                item
                for item in service._read("100002")["flow_registry"]
                if item["flow_id"] == flow_id
            )
            assert linked["validation_status"] == "action_linked"

    blocked = service.validate_flow(
        developer,
        "flow-incompatible",
        PlaygroundFlowValidationRequest(
            endpoint_id=endpoint_id,
            project_id="project-100002",
            task_ref="task:test",
        ),
    )
    assert blocked["validation_status"] == "blocked"
    assert "BoIWikiKnowledge" in blocked["failure_reason"]
    with pytest.raises(HTTPException) as denied:
        service.action_draft_payload(developer, deployment_ids["flow-incompatible"])
    assert denied.value.status_code == 409


def test_live_flow_drift_merge_does_not_erase_concurrent_action_draft(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    developer = principal(
        "100002",
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    endpoint_id = "ep-race"
    project_id = "project-race"
    flow_id = "flow-race"
    deployment_id = "hub-race"
    service._write(
        developer.employee_id,
        {
            "employee_id": developer.employee_id,
            "endpoints": [
                {
                    "endpoint_id": endpoint_id,
                    "name": "Race endpoint",
                    "base_url": "http://langflow.example:7860",
                    "endpoint": "http://langflow.example:7860",
                    "api_key_encrypted": service.cipher.encrypt(
                        "lf-key-race",
                        owner=developer.employee_id,
                    ),
                    "api_key_fingerprint": "race",
                    "status": "connected",
                    "active": True,
                }
            ],
            "default_endpoint_id": endpoint_id,
            "flow_registry": [
                {
                    "endpoint_id": endpoint_id,
                    "project_id": project_id,
                    "flow_id": flow_id,
                    "artifact_version": "1.1.0",
                    "artifact_checksum": "registered-checksum",
                    "validation_status": "action_ready",
                    "deployment_id": deployment_id,
                }
            ],
            "deployments": [
                {
                    "deployment_id": deployment_id,
                    "endpoint_id": endpoint_id,
                    "project_id": project_id,
                    "flow_id": flow_id,
                    "asset_version": "1.1.0",
                    "artifact_checksum": "registered-checksum",
                    "status": "action_ready",
                }
            ],
        },
    )
    monkeypatch.setattr(
        service,
        "projects",
        lambda *_args, **_kwargs: {
            "projects": [{"id": project_id, "name": "boi-100002"}]
        },
    )
    monkeypatch.setattr(
        service,
        "_flows",
        lambda *_args, **_kwargs: [
            {
                "id": flow_id,
                "name": "Race Flow",
                "folder_id": project_id,
            }
        ],
    )
    draft_recorded = False

    def live_flow_with_concurrent_draft(*_args, **_kwargs):
        nonlocal draft_recorded
        if not draft_recorded:
            draft_recorded = True
            service.record_action_draft(
                developer,
                deployment_id,
                {"draft_id": "draft-written-during-live-read", "status": "draft"},
            )
        return {
            "id": flow_id,
            "name": "Race Flow",
            "folder_id": project_id,
            "data": {"nodes": [], "edges": []},
        }

    monkeypatch.setattr(service.langflow, "flow", live_flow_with_concurrent_draft)

    response = service.flows(developer, endpoint_id, project_id)

    assert response["flows"][0]["checksum_state"] == "drifted"
    persisted = service._read(developer.employee_id)
    deployment = next(
        item
        for item in persisted["deployments"]
        if item["deployment_id"] == deployment_id
    )
    registry = next(
        item
        for item in persisted["flow_registry"]
        if item["flow_id"] == flow_id
    )
    assert deployment["action_draft_id"] == "draft-written-during-live-read"
    assert registry["action_draft_id"] == "draft-written-during-live-read"
    assert deployment["status"] == "blocked"
    assert registry["validation_status"] == "blocked"


def test_model_runtime_contract_accepts_save_facade_nested_agent_provenance():
    contract = AgentPlaygroundService._model_runtime_contract(
        {
            "source_references": [{"ref": "boi:public:doc"}],
            "grounding_status": "grounded_with_ontology",
            "answer": "Gemma가 근거를 정리했습니다.",
            "provenance": {
                "knowledge_provenance": {
                    "model_agent": {
                        "provider": "openai-compatible",
                        "model": "google/gemma-4-26b-a4b-qat",
                        "response_id": "chatcmpl-validation",
                        "latency_ms": 1200.0,
                        "real_inference": True,
                    }
                }
            },
        }
    )

    assert contract["ok"] is True
    assert contract["model"] == "google/gemma-4-26b-a4b-qat"
    assert contract["response_id"] == "chatcmpl-validation"


def test_generic_agent_hub_flow_uses_dynamic_action_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("BOI_AUTH_MODE", "dev")
    monkeypatch.setenv("BOI_AGENT_PLAYGROUND_ENCRYPTION_KEY", "test-playground-encryption")
    developer = principal(
        "100002",
        roles=["boi.viewer", "boi.editor", "boi.action_invoker"],
    )
    pats = PlaygroundCredentialService(
        tmp_path / "runtime",
        hash_secret="test-pat-secret",
        identity_provider=lambda _employee_id: developer,
    )
    store = pats.store
    service = AgentPlaygroundService(tmp_path / "runtime", ROOT, pats)
    project = {"id": "project-100002", "name": "boi-100002"}
    flow = {
        "id": "flow-generic-rich",
        "name": "Shared Rich Analysis",
        "endpoint_name": "shared-rich-analysis",
        "folder_id": project["id"],
        "data": {
            "nodes": ["ChatInput", "OtherAuthorRichCustomComponent", "ChatOutput"],
            "edges": [],
        },
    }

    def fake_request(method, endpoint, path, api_key, **kwargs):
        if path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        if path == "/api/v1/version":
            return httpx.Response(200, json={"version": "1.11.0"})
        if path == "/api/v1/users/whoami":
            return httpx.Response(
                200,
                json={"id": "lf-user-100002", "username": "100002", "is_active": True},
            )
        if path == "/api/v1/projects/":
            return httpx.Response(200, json=[project])
        if path == "/api/v1/flows/":
            return httpx.Response(
                200,
                json=[{key: value for key, value in flow.items() if key != "data"}],
            )
        if path == f"/api/v1/flows/{flow['id']}":
            return httpx.Response(200, json=flow)
        if path == f"/api/v1/run/{flow['id']}":
            return httpx.Response(
                200,
                json={
                    "outputs": [
                        {
                            "outputs": [
                                {
                                    "results": {
                                        "message": {
                                            "text": "공용 커스텀 컴포넌트가 분석한 결과입니다."
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                },
            )
        raise AssertionError(f"unexpected Langflow call: {method} {path}")

    monkeypatch.setattr(service, "_request", fake_request)
    endpoint_id = service.create_endpoint(
        developer,
        PlaygroundEndpointCreateRequest(
            name="Personal 1.11",
            base_url="http://langflow.example:7860",
            api_key="lf-key-100002",
            make_default=True,
        ),
    )["endpoint"]["endpoint_id"]
    deployment = service.record_deployment(
        developer,
        PlaygroundDeploymentRequest(
            endpoint_id=endpoint_id,
            project_id=project["id"],
            flow_id=flow["id"],
            endpoint_name=flow["endpoint_name"],
            asset_version="2.4.0",
        ),
    )["deployment"]
    record = service._read("100002")
    stored = next(
        item
        for item in record["deployments"]
        if item["deployment_id"] == deployment["deployment_id"]
    )
    stored["validation_profile"] = "generic_action"
    service._write("100002", record)

    validated = service.validate_flow(
        developer,
        flow["id"],
        PlaygroundFlowValidationRequest(
            endpoint_id=endpoint_id,
            project_id=project["id"],
        ),
    )
    assert validated["validation_status"] == "action_ready"
    assert validated["validation_profile"] == "generic_action"
    assert validated["artifact_version"] == "2.4.0"
    assert validated["structural"]["manifest_contract"]["inferred"] is True
    assert validated["history"][-2]["details"]["wiki_task_contract"] == "not_required"
    live_flow = service.flows(developer, endpoint_id, project["id"])["flows"][0]
    assert live_flow["validation_status"] == "action_ready"
    assert live_flow["artifact_version"] == "2.4.0"
    assert live_flow["deployment_id"] == deployment["deployment_id"]

    draft = service.action_draft_payload(developer, deployment["deployment_id"])
    assert draft["title"] == "Shared Rich Analysis Action"
    assert draft["input_fields"] == ["question"]
    assert draft["output_fields"] == ["answer"]
    assert draft["connector_config"]["validation_profile"] == "generic_action"
    assert draft["execution_mode"] == "gateway"
    assert "execution_kind" not in draft
    assert draft["action_contract"]["profile"] == "generic_action"
    assert draft["action_contract"]["inputs"]["fields"] == ["question"]
    assert draft["connector_binding"]["kind"] == "langflow"
    assert draft["connector_binding"]["execution_mode"] == "gateway"
    assert draft["risk_level"] == "medium"
    team_draft = service.action_draft_payload(
        developer,
        deployment["deployment_id"],
        scope="team",
        team_id="platform",
    )
    assert team_draft["scope"] == "team"
    assert team_draft["folder"] == "team/platform/action-drafts"
    with pytest.raises(HTTPException) as wrong_team:
        service.action_draft_payload(
            developer,
            deployment["deployment_id"],
            scope="team",
            team_id="aix-tf",
        )
    assert wrong_team.value.status_code == 403

    flow["description"] = "Drift after Action registration"
    with pytest.raises(HTTPException) as drifted:
        service.action_draft_payload(developer, deployment["deployment_id"])
    assert drifted.value.status_code == 409
    assert drifted.value.detail["code"] == "flow_checksum_drift"
    stored_after_drift = service.deployment(developer, deployment["deployment_id"])
    assert stored_after_drift["status"] == "blocked"
    assert stored_after_drift["checksum_state"] == "drifted"
    assert draft["approval_required"] is True
    assert "save_mode" not in draft["input_schema"]


def test_boi_read_only_profile_requires_knowledge_and_forbids_save():
    inputs = [
        "question",
        "business_context",
        "task_ref",
        "page_ref",
        "context_id",
        "sop_ref",
        "sop_stage",
        "event_ref",
        "action_ref",
        "prior_results",
        "required_evidence",
        "missing_evidence",
    ]
    outputs = [
        "answer",
        "task_context",
        "source_references",
        "ontology_relationships",
        "grounding_status",
        "provenance",
    ]
    contract = {
        "version": "1.1.0",
        "inputs": inputs,
        "outputs": outputs,
        "agent_kind": "contract_agent",
    }
    digest = hashlib.sha256(
        json.dumps(
            contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    read_only_flow = {
        "data": {
            "nodes": ["ChatInput", "BoIWikiKnowledge", "ChatOutput"],
            "boi_contract": contract,
            "boi_contract_sha256": digest,
        }
    }
    valid = AgentPlaygroundService._flow_contract(read_only_flow, "boi_knowledge")
    assert valid["ok"] is True
    assert valid["components"]["required"] == ["BoIWikiKnowledge"]

    with_save = json.loads(json.dumps(read_only_flow))
    with_save["data"]["nodes"].append("BoIWikiSave")
    blocked = AgentPlaygroundService._flow_contract(with_save, "boi_knowledge")
    assert blocked["ok"] is False
    assert blocked["components"]["present_forbidden"] == ["BoIWikiSave"]


def test_flow_contract_uses_canvas_node_identity_not_stale_serialized_metadata():
    canonical = json.loads(
        (ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json").read_text(
            encoding="utf-8"
        )
    )
    data = canonical["data"]
    removed_ids = {
        str(node.get("id") or "")
        for node in data["nodes"]
        if "BoIWikiSave" in json.dumps(node, ensure_ascii=False)
    }
    assert removed_ids
    data["nodes"] = [
        node
        for node in data["nodes"]
        if str(node.get("id") or "") not in removed_ids
    ]
    data["edges"] = [
        edge
        for edge in data["edges"]
        if str(edge.get("source") or "") not in removed_ids
        and str(edge.get("target") or "") not in removed_ids
    ]
    # Langflow exports can retain stale component names in unrelated metadata.
    # Those strings must not make a deleted Canvas node appear present.
    data["legacy_frontend_metadata"] = {
        "removed_component_display_name": "BoIWikiSave"
    }

    contract = AgentPlaygroundService._flow_contract(
        canonical,
        "boi_knowledge_draft",
    )
    assert contract["ok"] is False
    assert contract["components"]["missing"] == ["BoIWikiSave"]


def test_component_asset_matching_prefers_the_most_specific_node_identity():
    nodes = [
        {
            "id": "built-in-slot",
            "data": {
                "type": "BoIAgentSlot",
                "display_name": "Agent Slot",
                "node": {
                    "name": "BoIAgentSlot",
                    "display_name": "Agent Slot",
                },
            },
        },
        {
            "id": "incompatible-slot",
            "data": {
                "type": "IncompatibleAgentSlot",
                "display_name": "Incompatible Agent Slot",
                "node": {
                    "name": "IncompatibleAgentSlot",
                    "display_name": "Incompatible Agent Slot",
                },
            },
        },
    ]

    matches = AgentPlaygroundService._component_nodes_for_asset(
        nodes,
        asset_title="Incompatible Agent Slot 20260727",
        required_contract={
            "contract_id": "boi.agent-slot.v1",
            "inputs": ["agent_context"],
            "outputs": ["agent_result"],
        },
    )

    assert [item["id"] for item in matches] == ["incompatible-slot"]
