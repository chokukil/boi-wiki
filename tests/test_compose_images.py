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
