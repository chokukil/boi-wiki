#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Remember path values supplied by the caller. The repository .env is also
# consumed by Docker Compose, so its container paths must not become local
# filesystem paths merely because the dev script loads model credentials.
CALLER_CONTENT_ROOT_SET="${BOI_CONTENT_ROOT+x}"
CALLER_CONTENT_ROOT="${BOI_CONTENT_ROOT:-}"
CALLER_DATA_ROOT_SET="${DATA_ROOT+x}"
CALLER_DATA_ROOT="${DATA_ROOT:-}"
CALLER_RUNTIME_ROOT_SET="${BOI_RUNTIME_ROOT+x}"
CALLER_RUNTIME_ROOT="${BOI_RUNTIME_ROOT:-}"
CALLER_HISTORY_ROOT_SET="${BOI_RUNTIME_HISTORY_SEED_ROOT+x}"
CALLER_HISTORY_ROOT="${BOI_RUNTIME_HISTORY_SEED_ROOT:-}"
CALLER_KAFKA_BOOTSTRAP_SET="${KAFKA_BOOTSTRAP+x}"
CALLER_KAFKA_BOOTSTRAP="${KAFKA_BOOTSTRAP:-}"
CALLER_DATALAKE_ENDPOINT_SET="${BOI_DATALAKE_MINIO_ENDPOINT+x}"
CALLER_DATALAKE_ENDPOINT="${BOI_DATALAKE_MINIO_ENDPOINT:-}"

# Local development uses the same configuration file as Compose. Parse only
# dotenv KEY=VALUE rows: never execute the file as shell code, and preserve
# variables explicitly supplied by the caller.
if [ "${BOI_DEV_LOAD_DOTENV:-1}" = "1" ] && [ -f "${ROOT}/.env" ]; then
  while IFS= read -r -d '' entry; do
    key="${entry%%=*}"
    value="${entry#*=}"
    if [ -z "${!key+x}" ]; then
      printf -v "$key" '%s' "$value"
      export "$key"
    fi
  done < <(python - "${ROOT}/.env" <<'PY'
from pathlib import Path
import re
import sys

assignment = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#"):
        continue
    match = assignment.match(line)
    if not match:
        continue
    key, value = match.groups()
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    sys.stdout.buffer.write(f"{key}={value}".encode("utf-8") + b"\0")
PY
  )
fi

if [ "${BOI_GPT55_TEST_MODE:-false}" != "true" ]; then
  OPENAI_API_KEY=""
  OPENAI_API_MODEL=""
  export OPENAI_API_KEY OPENAI_API_MODEL
fi

PORT="${BOI_DEV_API_PORT:-8765}"
HOST="${BOI_DEV_API_HOST:-127.0.0.1}"
if [ "$CALLER_CONTENT_ROOT_SET" = "x" ]; then
  CONTENT_ROOT="$CALLER_CONTENT_ROOT"
elif [ "$CALLER_DATA_ROOT_SET" = "x" ]; then
  CONTENT_ROOT="$CALLER_DATA_ROOT"
else
  CONTENT_ROOT="${BOI_DEV_CONTENT_ROOT:-${ROOT}/data/boi}"
fi
if [ "$CALLER_RUNTIME_ROOT_SET" = "x" ]; then
  RUNTIME_ROOT="$CALLER_RUNTIME_ROOT"
else
  RUNTIME_ROOT="${BOI_DEV_RUNTIME_ROOT:-${ROOT}/.tmp/boi-runtime}"
fi
if [ "$CALLER_HISTORY_ROOT_SET" = "x" ]; then
  HISTORY_SEED_ROOT="$CALLER_HISTORY_ROOT"
else
  HISTORY_SEED_ROOT="${BOI_DEV_HISTORY_SEED_ROOT:-${ROOT}/data}"
fi
EMPLOYEE_ID="${DEMO_EMPLOYEE_ID:-100001}"
if [ "$CALLER_KAFKA_BOOTSTRAP_SET" = "x" ]; then
  KAFKA_BOOTSTRAP="$CALLER_KAFKA_BOOTSTRAP"
elif [ "${KAFKA_MODE:-local}" = "local" ] && [ "${KAFKA_BOOTSTRAP:-kafka:9092}" = "kafka:9092" ]; then
  KAFKA_BOOTSTRAP="localhost:${KAFKA_EXTERNAL_PORT:-9094}"
fi
export KAFKA_BOOTSTRAP

DATALAKE_MODE="${BOI_DATALAKE_MODE:-bundled}"
if [ "$CALLER_DATALAKE_ENDPOINT_SET" = "x" ]; then
  BOI_DATALAKE_MINIO_ENDPOINT="$CALLER_DATALAKE_ENDPOINT"
elif [ "$DATALAKE_MODE" = "bundled" ] && {
  [ -z "${BOI_DATALAKE_MINIO_ENDPOINT:-}" ] ||
  [ "${BOI_DATALAKE_MINIO_ENDPOINT%/}" = "http://data-lake-minio:9000" ];
}; then
  BOI_DATALAKE_MINIO_ENDPOINT="http://127.0.0.1:${BOI_DATALAKE_MINIO_PORT:-19000}"
fi
export BOI_DATALAKE_MODE="$DATALAKE_MODE"
export BOI_DATALAKE_MINIO_ENDPOINT

if [ ! -d "$CONTENT_ROOT" ]; then
  echo "content root not found: $CONTENT_ROOT" >&2
  echo "expected repo content root: ${ROOT}/data/boi" >&2
  exit 2
fi

markdown_count="$(find "$CONTENT_ROOT" -type f -name '*.md' | wc -l | tr -d ' ')"
if [ "${BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS:-1}" != "0" ] && [ "${markdown_count:-0}" -lt "${BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS:-1}" ]; then
  echo "content root has ${markdown_count} markdown files: $CONTENT_ROOT" >&2
  echo "expected at least ${BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS:-1}; check BOI_CONTENT_ROOT/DATA_ROOT." >&2
  exit 2
fi

"${ROOT}/scripts/check_private_content_writable.sh" "${CONTENT_ROOT}/private"

count_history_rows() {
  python - "$1" "$2" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
prefix = sys.argv[2]
if not root.exists():
    print(0)
    raise SystemExit
indexed = {path.name[:-4] for path in root.glob(f"{prefix}-*.jsonl.idx")}
count = 0
for index_path in root.glob(f"{prefix}-*.jsonl.idx"):
    try:
        count += len(index_path.read_text(encoding="utf-8").splitlines())
    except Exception:
        pass
for path in root.glob(f"{prefix}-*.jsonl"):
    if path.name in indexed:
        continue
    if path.stat().st_size > 64 * 1024 * 1024:
        continue
    try:
        with path.open("rb") as handle:
            line_count = 0
            last = b""
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                line_count += chunk.count(b"\n")
                last = chunk[-1:]
            if path.stat().st_size and last != b"\n":
                line_count += 1
            count += line_count
    except Exception:
        pass
print(count)
PY
}

existing_pids="$(pgrep -f "uvicorn .*boi_api\\.app\\.main:app.*--port ${PORT}" || true)"
if [ -n "$existing_pids" ]; then
  echo "BoI dev API is already running on port ${PORT}: ${existing_pids}"
  for pid in $existing_pids; do
    if [ -r "/proc/${pid}/environ" ]; then
      tr '\0' '\n' < "/proc/${pid}/environ" | grep -E '^(DATA_ROOT|BOI_CONTENT_ROOT|BOI_RUNTIME_ROOT|BOI_RUNTIME_HISTORY_SEED_ROOT|BOI_DATALAKE_MODE|BOI_DATALAKE_MINIO_ENDPOINT)=' || true
    fi
  done
  if [ "${BOI_DEV_API_RESTART:-0}" != "1" ]; then
    echo "Set BOI_DEV_API_RESTART=1 to stop it and restart with ${CONTENT_ROOT}." >&2
    exit 3
  fi
  kill $existing_pids
fi

if [ "${KAFKA_MODE:-local}" = "local" ] && [ "${BOI_DEV_START_KAFKA:-1}" = "1" ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "Starting local Kafka for Event and scheduled-work flows"
    docker compose --profile local-full up -d kafka kafka-init kafka-ui
  else
    echo "Docker is unavailable; Event publishing requires a reachable KAFKA_BOOTSTRAP=${KAFKA_BOOTSTRAP}." >&2
  fi
fi

if [ "$DATALAKE_MODE" = "bundled" ] && [ "${BOI_DEV_START_DATALAKE:-1}" = "1" ]; then
  if command -v docker >/dev/null 2>&1; then
    echo "Starting bundled document storage"
    docker compose --profile data-lake-bundled up -d data-lake-minio
    export BOI_DATALAKE_ENABLED="${BOI_DATALAKE_ENABLED:-true}"
    export BOI_DATALAKE_PROFILE="${BOI_DATALAKE_PROFILE:-bundled}"
    export BOI_DATALAKE_REQUIRED="${BOI_DATALAKE_REQUIRED:-true}"
  else
    echo "Docker is unavailable; document uploads require BOI_DATALAKE_MODE=external and a reachable endpoint." >&2
  fi
elif [ "$DATALAKE_MODE" = "external" ]; then
  export BOI_DATALAKE_ENABLED="${BOI_DATALAKE_ENABLED:-true}"
  export BOI_DATALAKE_PROFILE="${BOI_DATALAKE_PROFILE:-external}"
fi

if [ "$DATALAKE_MODE" = "bundled" ] && [ -n "${BOI_DATALAKE_MINIO_ENDPOINT:-}" ]; then
  datalake_health_url="${BOI_DATALAKE_MINIO_ENDPOINT%/}/minio/health/live"
  datalake_ready=0
  if command -v curl >/dev/null 2>&1; then
    for _ in $(seq 1 20); do
      if curl -fsS --max-time 1 "$datalake_health_url" >/dev/null 2>&1; then
        datalake_ready=1
        break
      fi
      sleep 1
    done
  fi
  if [ "$datalake_ready" = "1" ]; then
    echo "Bundled document storage is ready: ${BOI_DATALAKE_MINIO_ENDPOINT}"
  else
    echo "Document storage is not ready yet; the API will start in degraded mode and enable uploads after recovery." >&2
  fi
fi

mkdir -p "$RUNTIME_ROOT"

MCP_PORT="${BOI_WIKI_MCP_PORT:-8200}"
MCP_HOST="${BOI_DEV_MCP_HOST:-127.0.0.1}"
MCP_STATUS_URL="http://${MCP_HOST}:${MCP_PORT}/status"
if [ "${BOI_DEV_START_MCP:-1}" = "1" ]; then
  if curl -fsS --max-time 2 "$MCP_STATUS_URL" >/dev/null 2>&1; then
    echo "Using the running BoI MCP v2 service on ${MCP_STATUS_URL}"
  elif pgrep -f "uvicorn .*boi_wiki_mcp\.app\.main:app.*--port ${MCP_PORT}" >/dev/null 2>&1; then
    echo "BoI MCP v2 is starting on port ${MCP_PORT}"
  else
    echo "Starting BoI MCP v2 for Codex and Claude"
    (
      cd "$ROOT"
      BOI_API_URL="http://${HOST}:${PORT}" \
      BOI_WIKI_MCP_EXTERNAL_URL="http://${MCP_HOST}:${MCP_PORT}" \
      nohup python -m uvicorn boi_wiki_mcp.app.main:app --host "$MCP_HOST" --port "$MCP_PORT" \
        > "${RUNTIME_ROOT}/mcp-v2.log" 2>&1 < /dev/null &
      echo $! > "${RUNTIME_ROOT}/mcp-v2.pid"
    )
  fi
fi

export DATA_ROOT="$CONTENT_ROOT"
export BOI_CONTENT_ROOT="$CONTENT_ROOT"
export BOI_RUNTIME_ROOT="$RUNTIME_ROOT"
export BOI_RUNTIME_HISTORY_SEED_ROOT="$HISTORY_SEED_ROOT"
export BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS="${BOI_EXPECT_MIN_MARKDOWN_DOCUMENTS:-1}"
export BOI_BUILD_REVISION="${BOI_BUILD_REVISION:-$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || printf dev-local)}"
export BOI_AGENT_V2_ENABLED="${BOI_AGENT_V2_ENABLED:-true}"
export BOI_AGENT_V2_DEFAULT="${BOI_AGENT_V2_DEFAULT:-true}"
export BOI_INBOX_REPORT_AUTO_GENERATE="${BOI_INBOX_REPORT_AUTO_GENERATE:-true}"
export BOI_INBOX_REPORT_BACKFILL_SCOPE="${BOI_INBOX_REPORT_BACKFILL_SCOPE:-all}"
export BOI_SEARCH_AUTO_SYNC="${BOI_SEARCH_AUTO_SYNC:-true}"

seed_event_rows=0
seed_action_rows=0
inbox_report_docs=0
if [ -n "$BOI_RUNTIME_HISTORY_SEED_ROOT" ]; then
  seed_event_rows="$(count_history_rows "${BOI_RUNTIME_HISTORY_SEED_ROOT}/events" "events")"
  seed_action_rows="$(count_history_rows "${BOI_RUNTIME_HISTORY_SEED_ROOT}/actions" "actions")"
fi
if [ -d "${CONTENT_ROOT}/private" ]; then
  inbox_report_docs="$(find "${CONTENT_ROOT}/private" -path '*/inbox-reports/*.md' -type f | wc -l | tr -d ' ')"
fi

echo "BoI dev API start"
echo "- content root: $BOI_CONTENT_ROOT (${markdown_count} markdown files)"
echo "- runtime root: $BOI_RUNTIME_ROOT"
echo "- history seed root: ${BOI_RUNTIME_HISTORY_SEED_ROOT:-disabled} (${seed_event_rows} event rows, ${seed_action_rows} action rows, ${inbox_report_docs} inbox reports)"
echo "- Agent v2: ${BOI_AGENT_V2_ENABLED} (default UI: ${BOI_AGENT_V2_DEFAULT})"
if [ "${BOI_LMSTUDIO_REQUIRE_PRELOADED_MODELS:-false}" = "true" ]; then
  echo "- LM Studio models: external/manual residency required; app load/unload disabled (native API: ${BOI_LMSTUDIO_NATIVE_BASE_URL:-auto})"
else
  echo "- LM Studio models: local preload guard disabled"
fi
echo "- Event broker: ${KAFKA_BOOTSTRAP}"
echo "- Document storage: ${BOI_DATALAKE_MODE} (${BOI_DATALAKE_MINIO_ENDPOINT:-not configured})"
if [ "${BOI_DEV_START_MCP:-1}" = "1" ]; then
  echo "- External Agent MCP: http://${MCP_HOST}:${MCP_PORT}/mcp/v2"
else
  echo "- External Agent MCP: disabled for this start"
fi
if [ -n "${BOI_AGENT_V2_DATABASE_URL:-${BOI_PGVECTOR_DSN:-}}" ]; then
  echo "- Agent v2 store: Postgres configured"
else
  echo "- Agent v2 store: memory fallback; use scripts/start_agent_v2_stack.sh for durable local development"
fi
echo "- URL: http://${HOST}:${PORT}/?employee_id=${EMPLOYEE_ID}"

cd "$ROOT"
exec python -m uvicorn boi_api.app.main:app --host "$HOST" --port "$PORT"
