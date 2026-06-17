from __future__ import annotations

import json
from pathlib import Path


def test_env_example_contains_openai_compatible_gemma_defaults():
    env_text = Path(".env.example").read_text(encoding="utf-8")

    assert "BOI_LLM_BASE_URL=http://mangugil.iptime.org:1236/v1" in env_text
    assert "BOI_LLM_MODEL=google/gemma-4-26b-a4b-qat" in env_text
    assert "BOI_LLM_API_KEY=not-needed" in env_text
    assert "LANGFLOW_SECRET_KEY=Ym9pLXdpa2ktcG9jLWRldi1zZWNyZXQta2V5LTIwMjY=" in env_text
    assert "LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true" in env_text


def test_docker_compose_passes_llm_settings_to_langflow_and_gateway():
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "BOI_LLM_BASE_URL: ${BOI_LLM_BASE_URL:-http://mangugil.iptime.org:1236/v1}" in compose_text
    assert "BOI_LLM_MODEL: ${BOI_LLM_MODEL:-google/gemma-4-26b-a4b-qat}" in compose_text
    assert "BOI_LLM_API_KEY: ${BOI_LLM_API_KEY:-not-needed}" in compose_text
    assert "LANGFLOW_SECRET_KEY: ${LANGFLOW_SECRET_KEY:-Ym9pLXdpa2ktcG9jLWRldi1zZWNyZXQta2V5LTIwMjY=}" in compose_text
    assert "LANGFLOW_SKIP_AUTH_AUTO_LOGIN: ${LANGFLOW_SKIP_AUTH_AUTO_LOGIN:-true}" in compose_text


def test_langflow_reference_flow_manifest_is_importable_metadata():
    manifest = json.loads(Path("langflow/flows/boi_reference_flow.manifest.json").read_text(encoding="utf-8"))
    flow = json.loads(Path(manifest["flow_file"]).read_text(encoding="utf-8"))

    assert manifest["endpoint_name"] == "boi-reference-flow"
    assert manifest["model"] == "google/gemma-4-26b-a4b-qat"
    assert manifest["base_url"] == "http://mangugil.iptime.org:1236/v1"
    assert Path(manifest["flow_file"]).exists()
    assert flow["data"]["nodes"]
    assert "google/gemma-4-26b-a4b-qat" in json.dumps(flow, ensure_ascii=False)
    assert "BoI Event Input" in json.dumps(flow, ensure_ascii=False)


def compact_handle(value: dict) -> str:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return rendered.replace('"', "œ")


def test_langflow_reference_flow_edges_match_rendered_handle_ids():
    manifest = json.loads(Path("langflow/flows/boi_reference_flow.manifest.json").read_text(encoding="utf-8"))
    flow = json.loads(Path(manifest["flow_file"]).read_text(encoding="utf-8"))
    nodes = {node["id"] for node in flow["data"]["nodes"]}
    edges = flow["data"]["edges"]

    assert len(edges) == 3
    for edge in edges:
        assert edge["source"] in nodes
        assert edge["target"] in nodes
        assert edge["sourceHandle"] == compact_handle(edge["data"]["sourceHandle"])
        assert edge["targetHandle"] == compact_handle(edge["data"]["targetHandle"])
        assert ": " not in edge["sourceHandle"]
        assert ": " not in edge["targetHandle"]


def test_langflow_setup_script_documents_upload_and_smoke_endpoints():
    script = Path("scripts/setup_langflow_reference_flows.py").read_text(encoding="utf-8")

    assert "/api/v1/flows/upload/" in script
    assert "/api/v1/run/" in script
    assert "/api/v1/auto_login" in script
    assert "resolve_smoke_target" in script
    assert "boi-reference-flow" in script
