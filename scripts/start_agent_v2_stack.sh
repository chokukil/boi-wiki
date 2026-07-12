#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export BOI_AGENT_V2_ENABLED="${BOI_AGENT_V2_ENABLED:-true}"
export BOI_AGENT_V2_DEFAULT="${BOI_AGENT_V2_DEFAULT:-true}"
export BOI_API_RUN_AS="${BOI_API_RUN_AS:-$(id -u):$(id -g)}"

"${ROOT}/scripts/check_private_content_writable.sh" "${BOI_LOCAL_PRIVATE_ROOT:-${ROOT}/data/boi/private}"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for the durable Agent v2 stack." >&2
  exit 2
fi

echo "Starting BoI Agent v2: Kafka, Event Router, pgvector, API, DeepAgents worker, Action Gateway, and MCP"
docker compose --profile local-full up -d --build \
  kafka kafka-init event-router boi-postgres boi-api boi-agent-worker action-gateway boi-wiki-mcp

base_url="${BOI_EXTERNAL_URL:-http://localhost:${BOI_API_PORT:-28000}}"
for _ in $(seq 1 60); do
  if curl -fsS "${base_url%/}/api/v2/system/readiness" >/tmp/boi-agent-v2-readiness.json 2>/dev/null; then
    if ! python - /tmp/boi-agent-v2-readiness.json <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if payload.get("ready") else 1)
PY
    then
      sleep 2
      continue
    fi
    mcp_base="${BOI_WIKI_MCP_EXTERNAL_URL:-http://localhost:${BOI_WIKI_MCP_PORT:-8200}}"
    mcp_url="${mcp_base%/}"
    if [[ "$mcp_url" != */mcp/v2 ]]; then
      mcp_url="${mcp_url}/mcp/v2"
    fi
    echo "BoI Agent v2 is available: ${base_url%/}/agent"
    echo "Readiness: ${base_url%/}/api/v2/system/readiness"
    echo "MCP: ${mcp_url}"
    python - /tmp/boi-agent-v2-readiness.json <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
index = ((payload.get("search") or {}).get("index") or {})
print(f"Search sync: {index.get('sync_state', 'unknown')} ({index.get('pending_changes', 0)} pending)")
PY
    if curl -fsS "${base_url%/}/api/v2/harness/acceptance" >/tmp/boi-agent-v2-acceptance.json 2>/dev/null; then
      python - /tmp/boi-agent-v2-acceptance.json <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
print(f"Core acceptance: {payload.get('core_accepted')}")
print(f"Full acceptance: {payload.get('full_accepted')}")
if not payload.get("full_accepted"):
    failed = [name for name, passed in (payload.get("full_checks") or {}).items() if not passed]
    print("Full acceptance pending: " + ", ".join(failed))
PY
    fi
    exit 0
  fi
  sleep 2
done

echo "Agent v2 did not become ready within 120 seconds." >&2
docker compose ps >&2
exit 1
