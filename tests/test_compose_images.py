from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_compose_uses_available_kafka_image_and_matching_cli_path():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "image: apache/kafka:3.7.0" in compose
    assert "/opt/kafka/bin/kafka-topics.sh" in compose
    assert "- -lc" in compose
    assert "bitnami/kafka:3.7" not in compose
    assert "kafka-data:/tmp/kafka-logs" not in compose


def test_langflow_uses_writable_config_directory():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "LANGFLOW_CONFIG_DIR: /tmp/langflow" in compose
    assert "langflow-data:/app/langflow" not in compose


def test_compose_defines_boi_wiki_mcp_service_and_allowed_host():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "boi-wiki-mcp:" in compose
    assert "context: ./boi_wiki_mcp" in compose
    assert "BOI_WIKI_MCP_PORT" in compose
    assert "boi-wiki-mcp" in env_example


def test_compose_declares_pilot_profiles_and_external_service_modes():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")
    local_env = Path(".env.local-full.example").read_text(encoding="utf-8")
    pilot_env = Path(".env.pilot-external.example").read_text(encoding="utf-8")

    assert 'profiles: ["local-full", "full"]' in compose
    assert 'profiles: ["core", "local-full", "pilot-external", "full"]' in compose
    assert 'profiles: ["local-full", "pilot-external", "full"]' in compose
    assert "DEPLOY_PROFILE: ${DEPLOY_PROFILE:-local-full}" in compose
    assert "KAFKA_MODE: ${KAFKA_MODE:-local}" in compose
    assert "LANGFLOW_MODE: ${LANGFLOW_MODE:-local}" in compose
    assert "KAFKA_SECURITY_PROTOCOL: ${KAFKA_SECURITY_PROTOCOL:-PLAINTEXT}" in compose
    assert "EVENT_ROUTER_AIOKAFKA_LOG_LEVEL: ${EVENT_ROUTER_AIOKAFKA_LOG_LEVEL:-CRITICAL}" in compose
    assert "BOI_AUTO_PUSH: ${BOI_AUTO_PUSH:-false}" in compose
    assert "BOI_CONTENT_SAFE_DIRECTORY: ${BOI_CONTENT_SAFE_DIRECTORY:-}" in compose
    assert "git config --global --add safe.directory" in compose
    assert '"${BOI_API_PORT:-28000}:8000"' in compose
    assert "${BOI_CONTENT_HOST_PATH:-./data/boi}:${BOI_CONTENT_MOUNT_PATH:-/data/boi}" in compose
    assert "EVENT_ROUTER_STARTUP_DELAY_SECONDS: ${EVENT_ROUTER_STARTUP_DELAY_SECONDS:-0}" in compose
    assert "EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS: ${EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS:-60}" in compose
    assert "EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS: ${EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS:-0}" in compose
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS: ${BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS:-2}" in compose
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY: ${BOI_AGENT_LLM_MAX_CONCURRENCY:-1}" in compose
    assert "BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS: ${BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS:-120}" in compose
    assert "condition: service_completed_successfully" not in compose

    assert "KAFKA_MODE=local" in local_env
    assert "LANGFLOW_MODE=local" in local_env
    assert "BOI_API_PORT=28000" in local_env
    assert "BOI_EXTERNAL_URL=http://localhost:28000" in local_env
    assert "BOI_CONTENT_ROOT=/workspace/data/boi" in local_env
    assert "BOI_CONTENT_SAFE_DIRECTORY=/workspace" in local_env
    assert "BOI_CONTENT_HOST_PATH=." in local_env
    assert "BOI_CONTENT_MOUNT_PATH=/workspace" in local_env
    assert "KAFKA_BOOTSTRAP=kafka:9092" in local_env
    assert "KAFKA_SMOKE_BOOTSTRAP=localhost:9094" in local_env
    assert "EVENT_ROUTER_AIOKAFKA_LOG_LEVEL=CRITICAL" in local_env
    assert "EVENT_ROUTER_STARTUP_DELAY_SECONDS=5" in local_env
    assert "EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS=60" in local_env
    assert "EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS=5" in local_env
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=2" in local_env
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY=1" in local_env
    assert "BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS=120" in local_env
    assert "KAFKA_MODE=external" in pilot_env
    assert "LANGFLOW_MODE=external" in pilot_env
    assert "BOI_API_PORT=28000" in pilot_env
    assert "BOI_CONTENT_ROOT=/content/boi" in pilot_env
    assert "BOI_CONTENT_SAFE_DIRECTORY=/content" in pilot_env
    assert "BOI_CONTENT_HOST_PATH=/srv/boi-wiki/content" in pilot_env
    assert "BOI_CONTENT_MOUNT_PATH=/content" in pilot_env
    assert "KAFKA_SECURITY_PROTOCOL=SASL_SSL" in pilot_env
    assert "BOI_AUTO_PUSH=true" in pilot_env
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=2" in pilot_env
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY=1" in pilot_env
    assert "BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS=120" in pilot_env
    assert "KAFKA_MODE=local" in env_example
    assert "BOI_API_PORT=28000" in env_example
    assert "BOI_CONTENT_ROOT=/workspace/data/boi" in env_example
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=2" in env_example
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY=1" in env_example


def test_compose_declares_boi_auth_env_and_sso_dev_overlay():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    overlay = Path("docker-compose.sso-dev.yml").read_text(encoding="utf-8")
    env_example = Path(".env.example").read_text(encoding="utf-8")

    assert "BOI_AUTH_MODE" in compose
    assert "KEYCLOAK_SERVER_URL" in compose
    assert "HCP_AUTHZ_URL" in compose
    assert "dk02315/langflow-hynix:v1.10.0-hynix-sso-rc4" in overlay
    assert "docker/langflow-hynix-sso.Dockerfile" in overlay
    assert Path("docker/langflow-hynix-sso.Dockerfile").read_text(encoding="utf-8").count("limits==5.6.0") == 1
    assert "slowapi==0.1.9" in Path("docker/langflow-hynix-sso.Dockerfile").read_text(encoding="utf-8")
    assert "infra/keycloak/boi-dev-realm.json" in overlay
    assert "mock-hcp" in overlay
    assert "KEYCLOAK_HCP_API_URL" in overlay
    assert "KEYCLOAK_ALLOWED_EMPLOYEE" in overlay
    assert "KEYCLOAK_SHARED_USERNAME" in overlay
    assert "KEYCLOAK_ISSUER_URL" in overlay
    assert "/v1/projects/langflow/roles" in overlay
    assert "BOI_AUTH_MODE=dev" in env_example
    assert "KEYCLOAK_CLIENT_ID=boi-wiki" in env_example
    assert "LANGFLOW_HCP_API_URL=http://mock-hcp:8300/v1/projects/langflow/roles" in env_example


def test_mock_hcp_exposes_langflow_hynix_project_roles():
    from mock_hcp.app.main import app

    client = TestClient(app)
    response = client.get("/v1/projects/langflow/roles")

    assert response.status_code == 200
    body = response.json()
    assert "response" in body
    assert "managers" in body["response"]
    assert "developers" in body["response"]
    assert "100001" in body["response"]["managers"]
