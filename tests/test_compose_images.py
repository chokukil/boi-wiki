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

    assert 'profiles: ["local-full", "local-full-datalake", "local-full-legacy-db-demo", "full"]' in compose
    assert 'profiles: ["data-lake-bundled", "local-full-datalake", "local-full-legacy-db-demo"]' in compose
    assert 'profiles: ["local-full-legacy-db-demo"]' in compose
    assert 'profiles: ["core", "local-full", "local-full-datalake", "local-full-legacy-db-demo", "pilot-external", "full"]' in compose
    assert 'profiles: ["local-full", "local-full-datalake", "local-full-legacy-db-demo", "pilot-external", "full"]' in compose
    assert "DEPLOY_PROFILE: ${DEPLOY_PROFILE:-local-full}" in compose
    assert "KAFKA_MODE: ${KAFKA_MODE:-local}" in compose
    assert "LANGFLOW_MODE: ${LANGFLOW_MODE:-local}" in compose
    assert "KAFKA_SECURITY_PROTOCOL: ${KAFKA_SECURITY_PROTOCOL:-PLAINTEXT}" in compose
    assert "EVENT_ROUTER_AIOKAFKA_LOG_LEVEL: ${EVENT_ROUTER_AIOKAFKA_LOG_LEVEL:-CRITICAL}" in compose
    assert "BOI_AUTO_PUSH: ${BOI_AUTO_PUSH:-false}" in compose
    assert "BOI_CONTENT_SAFE_DIRECTORY: ${BOI_CONTENT_SAFE_DIRECTORY:-}" in compose
    assert "BOI_RUNTIME_HISTORY_SEED_ROOT: ${BOI_RUNTIME_HISTORY_SEED_ROOT:-}" in compose
    assert "BOI_INBOX_REPORT_AUTO_GENERATE: ${BOI_INBOX_REPORT_AUTO_GENERATE:-true}" in compose
    assert "BOI_INBOX_REPORT_BACKFILL_SCOPE: ${BOI_INBOX_REPORT_BACKFILL_SCOPE:-all}" in compose
    assert "BOI_SEARCH_AUTO_SYNC: ${BOI_SEARCH_AUTO_SYNC:-true}" in compose
    assert "BOI_DATALAKE_MODE: ${BOI_DATALAKE_MODE:-bundled}" in compose
    assert "BOI_KNOWLEDGE_HEALTH_ENABLED: ${BOI_KNOWLEDGE_HEALTH_ENABLED:-true}" in compose
    assert "BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS: ${BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS:-1}" in compose
    assert "git config --global --add safe.directory" in compose
    assert '"${BOI_API_PORT:-28000}:8000"' in compose
    assert "${BOI_CONTENT_HOST_PATH:-./data/boi}:${BOI_CONTENT_MOUNT_PATH:-/data/boi}" in compose
    assert "EVENT_ROUTER_STARTUP_DELAY_SECONDS: ${EVENT_ROUTER_STARTUP_DELAY_SECONDS:-0}" in compose
    assert "EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS: ${EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS:-60}" in compose
    assert "EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS: ${EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS:-0}" in compose
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS: ${BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS:-3}" in compose
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY: ${BOI_AGENT_LLM_MAX_CONCURRENCY:-1}" in compose
    assert "BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS: ${BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS:-600}" in compose
    assert "OPENAI_API_KEY: ${BOI_GPT55_TEST_API_KEY:-}" in compose
    assert "condition: service_completed_successfully" not in compose

    assert "KAFKA_MODE=local" in local_env
    assert "LANGFLOW_MODE=local" in local_env
    assert "BOI_API_PORT=28000" in local_env
    assert "BOI_EXTERNAL_URL=http://localhost:28000" in local_env
    assert "BOI_CONTENT_ROOT=/workspace/data/boi" in local_env
    assert "BOI_CONTENT_SAFE_DIRECTORY=/workspace" in local_env
    assert "BOI_RUNTIME_HISTORY_SEED_ROOT=/workspace/data" in local_env
    assert "BOI_INBOX_REPORT_AUTO_GENERATE=true" in local_env
    assert "BOI_SEARCH_AUTO_SYNC=true" in local_env
    assert "BOI_DATALAKE_MODE=bundled" in local_env
    assert "BOI_KNOWLEDGE_HEALTH_ENABLED=true" in local_env
    assert "BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS=1" in local_env
    assert "BOI_CONTENT_HOST_PATH=." in local_env
    assert "BOI_CONTENT_MOUNT_PATH=/workspace" in local_env
    assert "KAFKA_BOOTSTRAP=kafka:9092" in local_env
    assert "KAFKA_SMOKE_BOOTSTRAP=localhost:9094" in local_env
    assert "EVENT_ROUTER_AIOKAFKA_LOG_LEVEL=CRITICAL" in local_env
    assert "EVENT_ROUTER_STARTUP_DELAY_SECONDS=5" in local_env
    assert "EVENT_ROUTER_TOPIC_READY_TIMEOUT_SECONDS=60" in local_env
    assert "EVENT_ROUTER_POST_TOPIC_READY_DELAY_SECONDS=5" in local_env
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=3" in local_env
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY=1" in local_env
    assert "BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS=600" in local_env
    assert "BOI_GPT55_TEST_MODE=false" in local_env
    assert "BOI_GPT55_TEST_API_KEY=" in local_env
    assert "KAFKA_MODE=external" in pilot_env
    assert "LANGFLOW_MODE=external" in pilot_env
    assert "BOI_API_PORT=28000" in pilot_env
    assert "BOI_CONTENT_ROOT=/content/data/boi" in pilot_env
    assert "BOI_CONTENT_SAFE_DIRECTORY=/content" in pilot_env
    assert "BOI_RUNTIME_HISTORY_SEED_ROOT=/content/data" in pilot_env
    assert "BOI_INBOX_REPORT_BACKFILL_SCOPE=all" in pilot_env
    assert "BOI_SEARCH_AUTO_SYNC=true" in pilot_env
    assert "BOI_DATALAKE_MODE=bundled" in pilot_env
    assert "BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS=1" in pilot_env
    assert "BOI_CONTENT_HOST_PATH=/srv/boi-wiki/content" in pilot_env
    assert "BOI_CONTENT_MOUNT_PATH=/content" in pilot_env
    assert "KAFKA_SECURITY_PROTOCOL=SASL_SSL" in pilot_env
    assert "BOI_AUTO_PUSH=true" in pilot_env
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=3" in pilot_env
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY=1" in pilot_env
    assert "BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS=600" in pilot_env
    assert "BOI_GPT55_TEST_MODE=false" in pilot_env
    assert "BOI_GPT55_TEST_API_KEY=" in pilot_env
    assert "KAFKA_MODE=local" in env_example
    assert "BOI_API_PORT=28000" in env_example
    assert "BOI_CONTENT_ROOT=/workspace/data/boi" in env_example
    assert "BOI_RUNTIME_HISTORY_SEED_ROOT=/workspace/data" in env_example
    assert "BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS=1" in env_example
    assert "BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=3" in env_example
    assert "BOI_AGENT_LLM_MAX_CONCURRENCY=1" in env_example


def test_dev_api_script_defaults_to_repo_content_and_tmp_runtime():
    script = Path("scripts/start_dev_api.sh").read_text(encoding="utf-8")

    assert "PORT=\"${BOI_DEV_API_PORT:-8765}\"" in script
    assert 'CONTENT_ROOT="${BOI_DEV_CONTENT_ROOT:-${ROOT}/data/boi}"' in script
    assert 'RUNTIME_ROOT="${BOI_DEV_RUNTIME_ROOT:-${ROOT}/.tmp/boi-runtime}"' in script
    assert 'HISTORY_SEED_ROOT="${BOI_DEV_HISTORY_SEED_ROOT:-${ROOT}/data}"' in script
    assert 'CALLER_CONTENT_ROOT_SET="${BOI_CONTENT_ROOT+x}"' in script
    assert "never execute the file as shell code" in script
    assert "BOI_RUNTIME_HISTORY_SEED_ROOT" in script
    assert "BOI_DEV_API_RESTART=1" in script
    assert "markdown files" in script
    assert "history seed root" in script
    assert 'OPENAI_API_KEY=""' in script
    assert 'KAFKA_BOOTSTRAP="localhost:${KAFKA_EXTERNAL_PORT:-9094}"' in script
    assert 'BOI_DEV_START_KAFKA:-1' in script
    assert "docker compose --profile local-full up -d kafka kafka-init kafka-ui" in script
    assert 'DATALAKE_MODE="${BOI_DATALAKE_MODE:-bundled}"' in script
    assert "docker compose --profile data-lake-bundled up -d data-lake-minio" in script
    assert 'CALLER_DATALAKE_ENDPOINT_SET="${BOI_DATALAKE_MINIO_ENDPOINT+x}"' in script
    assert 'BOI_DATALAKE_MINIO_ENDPOINT="http://127.0.0.1:${BOI_DATALAKE_MINIO_PORT:-19000}"' in script
    assert '"http://data-lake-minio:9000"' in script
    assert '/minio/health/live' in script
    assert 'for _ in $(seq 1 20)' in script
    assert 'the API will start in degraded mode' in script
    assert 'BOI_DEV_START_MCP:-1' in script
    assert "boi_wiki_mcp.app.main:app" in script
    assert 'BOI_API_URL="http://${HOST}:${PORT}"' in script
    assert "check_private_content_writable.sh" in script

    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "BOI_DATALAKE_MINIO_ENDPOINT: ${BOI_DATALAKE_MINIO_ENDPOINT:-http://data-lake-minio:9000}" in compose


def test_local_starts_preserve_host_ownership_for_private_boi_content():
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")
    dockerfile = Path("boi_api/Dockerfile").read_text(encoding="utf-8")
    local_start = Path("scripts/start_local_full.sh").read_text(encoding="utf-8")
    agent_start = Path("scripts/start_agent_v2_stack.sh").read_text(encoding="utf-8")
    preflight = Path("scripts/check_private_content_writable.sh").read_text(encoding="utf-8")
    local_env = Path(".env.local-full.example").read_text(encoding="utf-8")
    pilot_env = Path(".env.pilot-external.example").read_text(encoding="utf-8")

    assert 'user: "${BOI_API_RUN_AS:-0:0}"' in compose
    assert "HOME=/tmp/boi-home" in dockerfile
    assert "chmod 1777 /data /runtime /tmp/boi-home" in dockerfile
    assert 'BOI_API_RUN_AS="${BOI_API_RUN_AS:-$(id -u):$(id -g)}"' in local_start
    assert 'BOI_API_RUN_AS="${BOI_API_RUN_AS:-$(id -u):$(id -g)}"' in agent_start
    assert "check_private_content_writable.sh" in local_start
    assert "check_private_content_writable.sh" in agent_start
    assert "sudo chown -R" in preflight
    assert "BOI_API_RUN_AS=1000:1000" in local_env
    assert "BOI_API_RUN_AS=1000:1000" in pilot_env


def test_agent_v2_stack_starts_its_event_broker_dependencies():
    script = Path("scripts/start_agent_v2_stack.sh").read_text(encoding="utf-8")

    assert "--profile local-full" in script
    assert "kafka kafka-init event-router" in script


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
