from __future__ import annotations

from pathlib import Path


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
