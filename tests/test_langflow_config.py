from __future__ import annotations

import json
from pathlib import Path


def test_env_example_contains_openai_compatible_gemma_defaults():
    env_text = Path(".env.example").read_text(encoding="utf-8")

    assert "BOI_LLM_BASE_URL=http://llm-gateway.example:1236/v1" in env_text
    assert "BOI_LLM_MODEL=google/gemma-4-26b-a4b-qat" in env_text
    assert "BOI_LLM_API_KEY=not-needed" in env_text
    assert "BOI_AGENT_ROUTER_MODE=llm_first" in env_text
    assert "BOI_AGENT_ROUTER_LLM_ENABLED=auto" in env_text
    assert "BOI_AGENT_ROUTER_MODEL=google/gemma-4-26b-a4b-qat" in env_text
    assert "BOI_AGENT_ROUTER_API_KEY=boi-router-dummy-key" in env_text
    assert "BOI_AGENT_STATUS_LLM_ENABLED=auto" in env_text
    assert "BOI_AGENT_STATUS_REQUIRED=1" in env_text
    assert "BOI_AGENT_STATUS_MODEL=google/gemma-4-26b-a4b-qat" in env_text
    assert "BOI_AGENT_STATUS_API_KEY=boi-router-dummy-key" in env_text
    assert "BOI_AGENT_STATUS_TIMEOUT_SECONDS=12" in env_text
    assert "BOI_AGENT_STATUS_MAX_TOKENS=1536" in env_text
    assert "BOI_AGENT_CACHE_WARMUP_ON_STARTUP=1" in env_text
    assert "LANGFLOW_SECRET_KEY=Ym9pLXdpa2ktcG9jLWRldi1zZWNyZXQta2V5LTIwMjY=" in env_text
    assert "LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true" in env_text


def test_docker_compose_passes_llm_settings_to_langflow_and_gateway():
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "BOI_LLM_BASE_URL: ${BOI_LLM_BASE_URL:-http://llm-gateway.example:1236/v1}" in compose_text
    assert "BOI_LLM_MODEL: ${BOI_LLM_MODEL:-google/gemma-4-26b-a4b-qat}" in compose_text
    assert "BOI_LLM_API_KEY: ${BOI_LLM_API_KEY:-not-needed}" in compose_text
    assert "BOI_AGENT_ROUTER_MODE: ${BOI_AGENT_ROUTER_MODE:-llm_first}" in compose_text
    assert "BOI_AGENT_ROUTER_LLM_ENABLED: ${BOI_AGENT_ROUTER_LLM_ENABLED:-auto}" in compose_text
    assert "BOI_AGENT_ROUTER_BASE_URL: ${BOI_AGENT_ROUTER_BASE_URL:-http://llm-gateway.example:1236/v1}" in compose_text
    assert "BOI_AGENT_STATUS_LLM_ENABLED: ${BOI_AGENT_STATUS_LLM_ENABLED:-auto}" in compose_text
    assert "BOI_AGENT_STATUS_REQUIRED: ${BOI_AGENT_STATUS_REQUIRED:-1}" in compose_text
    assert "BOI_AGENT_STATUS_BASE_URL: ${BOI_AGENT_STATUS_BASE_URL:-http://llm-gateway.example:1236/v1}" in compose_text
    assert "BOI_AGENT_STATUS_TIMEOUT_SECONDS: ${BOI_AGENT_STATUS_TIMEOUT_SECONDS:-12}" in compose_text
    assert "BOI_AGENT_STATUS_MAX_TOKENS: ${BOI_AGENT_STATUS_MAX_TOKENS:-1536}" in compose_text
    assert "BOI_AGENT_CACHE_WARMUP_ON_STARTUP: ${BOI_AGENT_CACHE_WARMUP_ON_STARTUP:-1}" in compose_text
    assert "LANGFLOW_SECRET_KEY: ${LANGFLOW_SECRET_KEY:-Ym9pLXdpa2ktcG9jLWRldi1zZWNyZXQta2V5LTIwMjY=}" in compose_text
    assert "LANGFLOW_SKIP_AUTH_AUTO_LOGIN: ${LANGFLOW_SKIP_AUTH_AUTO_LOGIN:-true}" in compose_text
    assert "BOI_API_SERVICE_TOKEN: ${SERVICE_TOKEN:-dev-service-token-change-me}" in compose_text
    assert "LANGFLOW_AUTH_MODE: ${LANGFLOW_AUTH_MODE:-api-key}" in compose_text


def test_langflow_reference_flow_manifest_is_importable_metadata():
    manifest = json.loads(Path("langflow/flows/boi_reference_flow.manifest.json").read_text(encoding="utf-8"))
    flow = json.loads(Path(manifest["flow_file"]).read_text(encoding="utf-8"))

    assert manifest["endpoint_name"] == "boi-reference-flow"
    assert manifest["model"] == "google/gemma-4-26b-a4b-qat"
    assert manifest["base_url"] == "http://llm-gateway.example:1236/v1"
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
    assert "/api/v1/flows/{flow_id}" in script
    assert "/api/v1/run/" in script
    assert "/api/v1/auto_login" in script
    assert "resolve_smoke_target" in script
    assert "boi-reference-flow" in script
    assert "BoI Agent Flow" in script
    assert "boi-agent" in script
    assert "LANGFLOW_BOI_AGENT_ENDPOINT" in script
    assert "create_boi_agent_flow" in script
    assert "native Agent" in script
    assert "BoI Universal Action Simulator Flow" in script
    assert "boi-universal-action-simulator" in script
    assert "BoIPromptComposer-boi" in script
    assert "BoIResultComposer-boi" in script
    assert "BoISimulationAgent-boi" in script
    assert "BoIUniversalSimulatorAgent-boi" in script
    assert "create_universal_agent_simulator_flow" in script
    assert "smoke_input_for_endpoint" in script
    assert "direct_development.quality_response_trend.simulate" in script
    assert "trace-langflow-smoke-universal" in script
    assert "manual.direct_development.decide_cross_section" not in script


def test_langflow_audit_script_checks_runtime_connected_boi_components():
    script = Path("scripts/audit_langflow_flows.py").read_text(encoding="utf-8")

    assert "BoI Equipment Stage Analysis Flow" in script
    assert "BoI Agent Flow" in script
    assert "boi-agent" in script
    assert "require_native_agent" in script
    assert "BoI Agent Flow is missing native Agent" in script
    assert "BoI Agent Flow is missing tool connection" in script
    assert "BoI Universal Action Simulator Flow" in script
    assert "boi-universal-action-simulator" in script
    assert "require_boi_components" in script
    assert "require_simulation_agent" in script
    assert "BoI Universal Simulator is missing BoI Universal Simulator Agent" in script
    assert "BoI Universal Simulator Agent is not connected to final result composer" in script
    assert "BoI custom components are disconnected" in script
    assert "BoI Prompt Composer is not connected to the Gemma LLM input path" in script
    assert "BoI Result Composer is not connected to ChatOutput" in script
    assert "hardcoded manual.direct_development.decide_cross_section" in script
    assert "/api/v1/flows/" in script


def test_langflow_custom_components_include_prompt_result_and_simulation_agent():
    prompt = Path("langflow/custom_components/boi/boi_prompt_composer.py").read_text(encoding="utf-8")
    result = Path("langflow/custom_components/boi/boi_result_composer.py").read_text(encoding="utf-8")
    simulation_agent = Path("langflow/custom_components/boi/boi_simulation_agent.py").read_text(encoding="utf-8")
    universal_agent = Path("langflow/custom_components/boi/boi_universal_simulator_agent.py").read_text(encoding="utf-8")
    context = Path("langflow/custom_components/boi/boi_context_normalizer.py").read_text(encoding="utf-8")
    init = Path("langflow/custom_components/boi/__init__.py").read_text(encoding="utf-8")

    assert "class BoIPromptComposer" in prompt
    assert "class BoIResultComposer" in result
    assert "class BoISimulationAgent" in simulation_agent
    assert "class BoIUniversalSimulatorAgent" in universal_agent
    assert "agent_iterations" in universal_agent
    assert "tool_calls" in universal_agent
    assert "coverage_score" in universal_agent
    assert "/api/simulations/universal-agent" in simulation_agent
    assert "/api/simulations/universal-agent" in universal_agent
    assert "simulation_agent" in context
    assert "Action key:" in context
    assert "json_payload" in context
    assert "\"payload\": payload" in context
    assert "context.get(\"action_key\")" in simulation_agent
    assert "BoIUniversalSimulatorAgent" in init
    assert "BoIPromptComposer" in init
    assert "BoIResultComposer" in init
    assert "BoISimulationAgent" in init


def test_langflow_reader_writer_attach_boi_api_service_token():
    reader = Path("langflow/custom_components/boi/boi_wiki_reader.py").read_text(encoding="utf-8")
    writer = Path("langflow/custom_components/boi/boi_wiki_writer.py").read_text(encoding="utf-8")

    assert 'os.getenv("BOI_API_SERVICE_TOKEN")' in reader
    assert 'headers=self._headers()' in reader
    assert 'os.getenv("BOI_API_SERVICE_TOKEN")' in writer
    assert '"x-service-token"' in writer


def test_equipment_sop_smoke_script_supports_sso_auth_headers():
    script = Path("scripts/run_equipment_sop_poc.py").read_text(encoding="utf-8")

    assert 'os.getenv("SERVICE_TOKEN", "")' in script
    assert 'os.getenv("BOI_AUTH_BEARER", "")' in script
    assert '"x-service-token"' in script
    assert '"Authorization"' in script
    assert "request_headers(content_type=True)" in script
