#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${BOI_ENV_FILE:-.env.local-full.example}"
OVERLAY_ENV_FILE="${BOI_ENV_OVERLAY_FILE:-.env}"
PROFILE="${BOI_COMPOSE_PROFILE:-local-full}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-boi-poc}"

if [ "${1:-}" = "--env-file" ]; then
  ENV_FILE="${2:?missing env file after --env-file}"
  shift 2
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "env file not found: $ENV_FILE" >&2
  exit 2
fi

ENV_FILES=("$ENV_FILE")
if [ -f "$OVERLAY_ENV_FILE" ] && [ "$OVERLAY_ENV_FILE" != "$ENV_FILE" ]; then
  ENV_FILES+=("$OVERLAY_ENV_FILE")
fi

read_env_value_from_file() {
  local key="$1"
  local file="$2"
  awk -F= -v key="$key" '
    $1 == key {
      value=$0
      sub("^[^=]*=", "", value)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
      print value
    }
  ' "$file" | tail -n 1
}

read_env_value() {
  local key="$1"
  local index
  for (( index=${#ENV_FILES[@]}-1; index>=0; index-- )); do
    value="$(read_env_value_from_file "$key" "${ENV_FILES[$index]}")"
    if [ -n "$value" ]; then
      printf '%s\n' "$value"
      return 0
    fi
  done
}

PORT="${BOI_API_PORT:-$(read_env_value BOI_API_PORT)}"
PORT="${PORT:-28000}"

if [ -z "${BOI_BUILD_REVISION:-}" ]; then
  BOI_BUILD_REVISION="$(git rev-parse --short HEAD 2>/dev/null || true)"
  export BOI_BUILD_REVISION="${BOI_BUILD_REVISION:-dev}"
fi

compose_cmd=(docker compose)
for file in "${ENV_FILES[@]}"; do
  compose_cmd+=(--env-file "$file")
done
compose_cmd+=(--profile "$PROFILE")

echo "BoI Wiki local-full start"
echo "- env files: ${ENV_FILES[*]}"
echo "- profile: $PROFILE"
echo "- web port: $PORT"
echo "- build revision: $BOI_BUILD_REVISION"

port_owners="$(docker ps --filter "publish=$PORT" --format '{{.ID}} {{.Names}} {{.Label "com.docker.compose.project"}}' || true)"
if [ -n "$port_owners" ]; then
  unknown_owners="$(printf '%s\n' "$port_owners" | awk -v project="$PROJECT_NAME" '$3 != project {print}')"
  if [ -n "$unknown_owners" ] && [ "${BOI_FORCE_PORT_RECLAIM:-0}" != "1" ]; then
    echo "port $PORT is already used by another Docker container:" >&2
    printf '%s\n' "$unknown_owners" >&2
    echo "Set BOI_FORCE_PORT_RECLAIM=1 to stop those containers, or set BOI_API_PORT to another port." >&2
    exit 3
  fi
  if [ -n "$unknown_owners" ]; then
    printf '%s\n' "$unknown_owners" | awk '{print $1}' | xargs -r docker stop
  fi
fi

"${compose_cmd[@]}" down --remove-orphans
"${compose_cmd[@]}" up -d --build

echo "BoI Wiki is expected at http://localhost:${PORT}/?employee_id=100001"
