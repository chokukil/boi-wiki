from __future__ import annotations

import importlib.util
import hashlib
import json
import re
from pathlib import Path

import yaml

from scripts.build_agent_playground_handoff import secret_scan


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
    assert "BOI_AGENT_STATUS_TIMEOUT_SECONDS=30" in env_text
    assert "BOI_AGENT_STATUS_MAX_TOKENS=1536" in env_text
    assert "BOI_AGENT_SUGGESTIONS_LLM_ENABLED=auto" in env_text
    assert "BOI_AGENT_SUGGESTIONS_REQUIRED=1" in env_text
    assert "BOI_AGENT_SUGGESTIONS_MODEL=google/gemma-4-26b-a4b-qat" in env_text
    assert "BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS=12" in env_text
    assert "BOI_AGENT_COMPOSER_REQUIRED=1" in env_text
    assert "BOI_AGENT_COMPOSER_TIMEOUT_SECONDS=30" in env_text
    assert "BOI_AGENT_COMPOSER_MAX_TOKENS=1536" in env_text
    assert "BOI_AGENT_COMPOSER_MAX_ATTEMPTS=2" in env_text
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
    assert "BOI_AGENT_STATUS_TIMEOUT_SECONDS: ${BOI_AGENT_STATUS_TIMEOUT_SECONDS:-30}" in compose_text
    assert "BOI_AGENT_STATUS_MAX_TOKENS: ${BOI_AGENT_STATUS_MAX_TOKENS:-1536}" in compose_text
    assert "BOI_AGENT_SUGGESTIONS_LLM_ENABLED: ${BOI_AGENT_SUGGESTIONS_LLM_ENABLED:-auto}" in compose_text
    assert "BOI_AGENT_SUGGESTIONS_REQUIRED: ${BOI_AGENT_SUGGESTIONS_REQUIRED:-1}" in compose_text
    assert "BOI_AGENT_SUGGESTIONS_BASE_URL: ${BOI_AGENT_SUGGESTIONS_BASE_URL:-http://llm-gateway.example:1236/v1}" in compose_text
    assert "BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS: ${BOI_AGENT_SUGGESTIONS_TIMEOUT_SECONDS:-12}" in compose_text
    assert "BOI_AGENT_COMPOSER_REQUIRED: ${BOI_AGENT_COMPOSER_REQUIRED:-1}" in compose_text
    assert "BOI_AGENT_COMPOSER_TIMEOUT_SECONDS: ${BOI_AGENT_COMPOSER_TIMEOUT_SECONDS:-30}" in compose_text
    assert "BOI_AGENT_COMPOSER_MAX_TOKENS: ${BOI_AGENT_COMPOSER_MAX_TOKENS:-1536}" in compose_text
    assert "BOI_AGENT_COMPOSER_MAX_ATTEMPTS: ${BOI_AGENT_COMPOSER_MAX_ATTEMPTS:-2}" in compose_text
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


def test_langflow_111_validation_stack_is_isolated_and_user_key_based():
    compose = yaml.safe_load(Path("docker-compose.langflow-1.11-validation.yml").read_text(encoding="utf-8"))
    service = compose["services"]["langflow-111"]
    environment = service["environment"]

    assert service["image"] == (
        "${LANGFLOW_111_IMAGE:-langflowai/langflow:1.11.0@"
        "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf}"
    )
    assert service["container_name"] == "boi-agent-playground-mainline-langflow"
    assert service["ports"] == ["${LANGFLOW_111_PORT:-7867}:7860"]
    assert environment["LANGFLOW_AUTO_LOGIN"] == "False"
    assert environment["LANGFLOW_SKIP_AUTH_AUTO_LOGIN"] == "false"
    assert "LANGFLOW_API_KEY_SOURCE" not in environment
    assert "LANGFLOW_API_KEY" not in environment
    assert "langflow-111-validation-postgres-data:/var/lib/postgresql/data" in compose["services"][
        "langflow-111-postgres"
    ]["volumes"]
    assert (
        compose["volumes"]["langflow-111-validation-postgres-data"]["name"]
        == "boi-agent-playground-mainline-langflow-postgres-data"
    )
    assert "./langflow/custom_components:/app/custom_components:ro" in service["volumes"]


def test_agent_hub_validation_stack_includes_employee_scoped_mock_hcp():
    compose = yaml.safe_load(Path("validation/agent-hub/docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["mock-hcp"]

    assert service["ports"] == ["18083:8080"]
    assert "./mock_hcp.py:/app/mock_hcp.py:ro" in service["volumes"]
    assert service["healthcheck"]["test"][0:2] == ["CMD", "python"]

    spec = importlib.util.spec_from_file_location(
        "mock_hcp",
        Path("validation/agent-hub/mock_hcp.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.PRINCIPALS["100002"]["roles"] == [
        "boi.viewer",
        "boi.editor",
        "boi.workflow_runner",
        "boi.action_invoker",
    ]
    assert module.PRINCIPALS["100003"]["roles"] == ["boi.viewer"]
    assert module.PRINCIPALS["100002"]["projects"] == ["boi-100002"]


def test_boi_wiki_agent_loop_artifact_matches_generator_contract_and_is_secret_free():
    spec = importlib.util.spec_from_file_location(
        "setup_langflow_reference_flows",
        Path("scripts/setup_langflow_reference_flows.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    flow = json.loads(Path("langflow/flows/boi_wiki_agent_loop.json").read_text(encoding="utf-8"))
    data = flow["data"]
    displays = [node["data"]["display_name"] for node in data["nodes"]]

    assert flow["name"] == "BoI Wiki Agent Loop"
    assert flow["endpoint_name"] == "boi-wiki-agent-loop"
    assert displays == [
        "Chat Input",
        "Wiki에서 지식 가져오기",
        "agent_slot",
        "Wiki에 지식 저장하기",
        "Chat Output",
    ]
    assert len(data["edges"]) == 4
    assert data["boi_contract"] == module.canonical_loop_contract()
    serialized_contract = json.dumps(
        data["boi_contract"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert data["boi_contract_sha256"] == hashlib.sha256(serialized_contract.encode("utf-8")).hexdigest()
    serialized_flow = json.dumps(flow, ensure_ascii=False)
    assert re.search(r"boi_(?:pat|run)_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}", serialized_flow) is None
    assert '"employee_id"' not in serialized_flow
    assert "BOI_WIKI_PAT" in serialized_flow
    assert "BOI_RUN_TOKEN" in serialized_flow


def test_agent_playground_facades_keep_identity_and_secrets_out_of_canvas_inputs():
    knowledge = Path("langflow/custom_components/boi/boi_wiki_knowledge.py").read_text(encoding="utf-8")
    save = Path("langflow/custom_components/boi/boi_wiki_save.py").read_text(encoding="utf-8")
    slot = Path("langflow/custom_components/boi/boi_agent_slot.py").read_text(encoding="utf-8")
    init = Path("langflow/custom_components/boi/__init__.py").read_text(encoding="utf-8")

    assert 'name = "BoIWikiKnowledge"' in knowledge
    assert '"boi_search"' in knowledge
    assert '"boi_get"' in knowledge
    assert "resolved_task_seed" in knowledge
    assert '"task_ref": task_ref or str(resolved_task.get("task_id") or "")' in knowledge
    assert '"resolved_task_id": str(resolved_task.get("task_id") or "")' in knowledge
    assert "unwrap_secret_value" in knowledge
    assert 'name = "BoIWikiSave"' in save
    assert '"boi_plan"' in save
    assert '"boi_confirm"' in save
    assert '"knowledge.draft"' in save
    assert '"private_draft"' in save
    assert "unwrap_secret_value" in save
    assert 'name = "BoIAgentSlot"' in slot
    assert "source_references" in slot
    assert "employee_id" not in knowledge
    assert "employee_id" not in save
    assert 'os.getenv("BOI_API_SERVICE_TOKEN")' not in knowledge
    assert 'os.getenv("BOI_API_SERVICE_TOKEN")' not in save
    assert "BoIWikiKnowledge" in init
    assert "BoIWikiSave" in init
    assert "BoIAgentSlot" in init


def test_model_agent_example_is_generated_from_contract_and_keeps_secrets_out_of_flow():
    spec = importlib.util.spec_from_file_location(
        "setup_langflow_reference_flows_model",
        Path("scripts/setup_langflow_reference_flows.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    flow = json.loads(
        Path("langflow/flows/boi_wiki_agent_loop_model_agent.json").read_text(encoding="utf-8")
    )
    data = flow["data"]
    displays = [node["data"]["display_name"] for node in data["nodes"]]

    assert flow["name"] == "BoI Wiki Agent Loop - Model Agent Example"
    assert flow["endpoint_name"] == "boi-wiki-agent-loop-model-agent"
    assert displays == [
        "Chat Input",
        "Wiki에서 지식 가져오기",
        "model_agent",
        "Wiki에 지식 저장하기",
        "Chat Output",
    ]
    assert data["boi_contract"] == module.model_agent_loop_contract()
    assert data["boi_contract"]["agent_kind"] == "openai_compatible_model"
    assert data["boi_contract"]["required_runtime_evidence"] == ["model_trace.real_inference"]
    serialized_contract = json.dumps(
        data["boi_contract"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    assert data["boi_contract_sha256"] == hashlib.sha256(
        serialized_contract.encode("utf-8")
    ).hexdigest()
    serialized_flow = json.dumps(flow, ensure_ascii=False)
    assert "BoIModelAgent" in serialized_flow
    assert "BOI_LLM_API_KEY" in serialized_flow
    assert re.search(r"\bsk-[A-Za-z0-9_-]{20,}\b", serialized_flow) is None
    assert re.search(r"boi_(?:pat|run)_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}", serialized_flow) is None

    component = Path("langflow/custom_components/boi/boi_model_agent.py").read_text(
        encoding="utf-8"
    )
    assert 'name = "BoIModelAgent"' in component
    assert "/chat/completions" in component
    assert '"real_inference": True' in component
    assert "source_references" in component
    assert "ontology_relationships" in component
    assert "BOI_LLM_API_KEY" in component
    assert "BoIModelAgent" in Path("langflow/custom_components/boi/__init__.py").read_text(
        encoding="utf-8"
    )


def test_langflow_external_runtime_boundary_manifest_and_checker():
    manifest = json.loads(
        Path("langflow/compatibility-manifest.json").read_text(encoding="utf-8")
    )
    checker = Path("scripts/check_agent_playground_langflow_boundary.py").read_text(
        encoding="utf-8"
    )
    compose = Path("docker-compose.langflow-1.11-validation.yml").read_text(encoding="utf-8")

    assert manifest["runtime_ownership"] == "external_unmodified"
    assert manifest["supported_versions"] == {
        "minimum": "1.11.0",
        "maximum_exclusive": "1.12.0",
    }
    assert manifest["extension_contract"]["mount_mode"] == "read_only"
    assert manifest["stable_run_api"] == "/api/v1/run/{flow_id}"
    assert manifest["validated_image"] in compose
    assert "./langflow/custom_components:/app/custom_components:ro" in compose
    assert "http://host.docker.internal:1236/v1" in compose
    assert "google/gemma-4-26b-a4b-qat" in compose
    assert "11434" not in compose
    assert "gpt-oss" not in compose
    assert "no_vendored_langflow_source" in checker
    assert "no_langflow_database_access" in checker
    assert "no_runtime_monkey_patch" in checker


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


def test_langflow_universal_simulator_smoke_checks_business_evidence_contract():
    script = Path("scripts/check_langflow_universal_simulator.py").read_text(encoding="utf-8")

    assert "boi-universal-action-simulator" in script
    assert "/api/simulations/universal-agent" in script
    assert "coverage_score" in script
    assert "evidence_packets" in script
    assert "business_context" in script
    assert "equipment_id" in script
    assert "lot_id" in script
    assert "wafer_id" in script
    assert "alarm_code" in script
    assert "outdated component" in script
    assert "LANGFLOW_SIMULATOR_HEALTH_FILE" in script


def test_inbox_narrative_quality_script_blocks_system_terms_and_repetition():
    script = Path("scripts/check_inbox_narrative_quality.py").read_text(encoding="utf-8")

    assert "group_narrative" in script
    assert "narrative_quality" in script
    assert "서로\\s*다른\\s*trace" in script
    assert "같은\\s*Action" in script
    assert "source_ids?" in script
    assert "preview item contexts are repetitive" in script
    assert "check_report_document" in script
    assert "checked_ready_reports" in script
    assert "검증된 보고서 BoI" in script
    assert "report document is missing required section" in script


def test_inbox_narrative_quality_can_require_ready_report_documents():
    script_path = Path("scripts/check_inbox_narrative_quality.py")
    spec = importlib.util.spec_from_file_location("check_inbox_narrative_quality", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.report_sample_errors(0, require_ready_report=True) == ["no ready report documents were checked"]
    assert module.report_sample_errors(0, require_ready_report=False) == []
    assert module.report_sample_errors(1, require_ready_report=True) == []


def test_inbox_narrative_quality_samples_item_reports_not_group_rollups():
    script_path = Path("scripts/check_inbox_narrative_quality.py")
    spec = importlib.util.spec_from_file_location("check_inbox_narrative_quality", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    body = {
        "items": [
            {
                "report_state": "ready",
                "report_boi_url": "/docs/boi:item-report",
                "report_boi_link": {"label": "검증된 보고서 BoI"},
            }
        ],
        "groups": [
            {
                "report_state": "ready",
                "report_boi_url": "/docs/boi:group-rollup",
                "report_boi_link": {"label": "검증된 보고서 BoI"},
            }
        ],
    }

    assert module.report_urls_from_inbox(body, limit=5) == ["/docs/boi:item-report"]


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
    assert "--scenario-profile" in script
    assert "semiconductor-varied" in script
    assert "ETCH-VM-01" in script
    assert "CVD-ALD-02" in script
    assert "MET-OVL-03" in script
    assert "FURN-HT-04" in script
    assert "missing_evidence" in script
    assert "approval_risk" in script


def test_external_runtime_manifest_pins_lm_studio_gemma_and_secure_logging():
    manifest = json.loads(Path("langflow/compatibility-manifest.json").read_text(encoding="utf-8"))
    model = manifest["model_agent_runtime"]
    logging = manifest["logging_contract"]

    assert model["provider_protocol"] == "openai-compatible"
    assert model["validated_provider"] == "LM Studio"
    assert model["base_url_variable"] == "BOI_LLM_BASE_URL"
    assert model["model_variable"] == "BOI_AGENT_EXAMPLE_MODEL"
    assert model["credential_variable"] == "BOI_LLM_API_KEY"
    assert model["validated_base_url"] == "http://host.docker.internal:1236/v1"
    assert model["validated_model"] == "google/gemma-4-26b-a4b-qat"
    assert model["requires_real_inference_trace"] is True
    assert logging["format"] == "json"
    assert logging["trace_locals"] is False
    assert {"authorization", "api_key", "boi_wiki_pat", "boi_run_token"}.issubset(
        logging["redacted_keys"]
    )


def test_handoff_secret_scan_does_not_treat_risk_labels_as_openai_keys(tmp_path):
    (tmp_path / "safe.css").write_text(
        ".risk-policy { color: red; } risk-level risk-medium",
        encoding="utf-8",
    )
    assert secret_scan(tmp_path)["ok"] is True

    (tmp_path / "unsafe.txt").write_text(
        "sk-" + ("a" * 24),
        encoding="utf-8",
    )
    result = secret_scan(tmp_path)
    assert result["ok"] is False
    assert result["matches"][0]["file"] == "unsafe.txt"


def test_patch_regression_uses_only_public_api_and_container_inspection():
    script = Path("scripts/regress_langflow_patch.py").read_text(encoding="utf-8")

    assert "/api/v1/version" in script
    assert "/api/v1/users/whoami" in script
    assert "/api/v1/projects/" in script
    assert "/api/v1/variables/" in script
    assert "/api/v1/run/" in script
    assert '["docker", "inspect", name]' in script
    assert "psycopg" not in script
    assert "sqlalchemy" not in script


def test_bundle_boundary_verifier_compares_pure_and_read_only_catalogs():
    source = Path("scripts/verify_langflow_bundle_boundary.py").read_text(
        encoding="utf-8"
    )

    assert "/api/v1/all" in source
    assert "BoIWikiKnowledge" in source
    assert "BoIWikiSave" in source
    assert "BoIModelAgent" in source
    assert "component_mount" in source
    assert "read_only" in source
    assert "pristine_package_hash" in source
    assert "site-packages/langflow" in source
    assert "import langflow" not in source
    assert "psycopg" not in source
