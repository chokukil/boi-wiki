#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
network_name="${BOI_AGENT_PLAYGROUND_VALIDATION_NETWORK:-boi-langflow-111-validation-net}"
compose_file="$repo_root/validation/agent-playground-mainline/docker-compose.yml"
langflow_file="$repo_root/docker-compose.langflow-1.11-validation.yml"
langflow_embedded_file="$repo_root/validation/agent-playground-mainline/docker-compose.langflow-browser-embedded-sso.yml"

if ! docker network inspect "$network_name" >/dev/null 2>&1; then
  docker network create "$network_name" >/dev/null
fi

docker compose -f "$langflow_file" -f "$langflow_embedded_file" config --quiet
docker compose -f "$compose_file" config --quiet
docker compose -f "$langflow_file" -f "$langflow_embedded_file" up -d
LANGFLOW_BROWSER_AUTH_MODE=embedded_sso \
LANGFLOW_BROWSER_ISOLATED_EMPLOYEE=100002 \
docker compose -f "$compose_file" up -d --build

curl --fail --silent --show-error --retry 30 --retry-all-errors --retry-delay 1 http://localhost:28005/health >/dev/null
curl --fail --silent --show-error --retry 30 --retry-all-errors --retry-delay 1 http://localhost:18205/health >/dev/null
curl --fail --silent --show-error --retry 30 --retry-all-errors --retry-delay 1 http://localhost:7867/health >/dev/null

printf '%s\n' "BoI Agent Playground mainline validation is ready:"
printf '%s\n' "  BoI:      http://localhost:28005/playground"
printf '%s\n' "  Langflow browser SSO: http://localhost:17867"
printf '%s\n' "  Langflow raw API:     http://localhost:7867"
printf '%s\n' "  Gateway:  http://localhost:18105"
printf '%s\n' "  Wiki MCP: http://localhost:18205/mcp/v2"
