#!/usr/bin/env bash
set -euo pipefail
set +x

APP_DIR="${APP_DIR:-/volume1/docker/boi-wiki/app}"
LOG_DIR="${LOG_DIR:-/volume1/docker/boi-wiki/deploy-logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/autopull.log}"
LOG_MAX_BYTES="${LOG_MAX_BYTES:-10485760}"
LOG_ROTATE_KEEP="${LOG_ROTATE_KEEP:-5}"
DEPLOY_SCRIPT="${DEPLOY_SCRIPT:-scripts/nas_auto_pull_deploy.sh}"

DEPLOY_CALLED="0"
ROTATED="0"
ROTATED_SIZE="0"

is_uint() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

normalize_settings() {
  if ! is_uint "$LOG_MAX_BYTES" || [[ "$LOG_MAX_BYTES" == "0" ]]; then
    LOG_MAX_BYTES="10485760"
  fi
  if ! is_uint "$LOG_ROTATE_KEEP"; then
    LOG_ROTATE_KEEP="5"
  fi
}

rotate_logs() {
  mkdir -p "$LOG_DIR"

  if [[ ! -f "$LOG_FILE" ]]; then
    return 0
  fi

  local size
  size="$(wc -c < "$LOG_FILE" | tr -d '[:space:]')"
  if ! is_uint "$size" || (( size < LOG_MAX_BYTES )); then
    return 0
  fi

  ROTATED="1"
  ROTATED_SIZE="$size"

  if (( LOG_ROTATE_KEEP == 0 )); then
    : > "$LOG_FILE"
    return 0
  fi

  rm -f "${LOG_FILE}.${LOG_ROTATE_KEEP}"

  local i
  for ((i = LOG_ROTATE_KEEP - 1; i >= 1; i--)); do
    if [[ -f "${LOG_FILE}.${i}" ]]; then
      mv "${LOG_FILE}.${i}" "${LOG_FILE}.$((i + 1))"
    fi
  done

  mv "$LOG_FILE" "${LOG_FILE}.1"
}

finish() {
  local rc=$?
  if [[ "$rc" -ne 0 && "$DEPLOY_CALLED" == "0" ]]; then
    printf 'DEPLOY_STATUS=failed\n'
  fi
}

normalize_settings
rotate_logs

exec >> "$LOG_FILE" 2>&1
trap finish EXIT

printf '[%s] TASK_START app_dir=%s log_file=%s\n' "$(date -Iseconds)" "$APP_DIR" "$LOG_FILE"
if [[ "$ROTATED" == "1" ]]; then
  printf '[%s] LOG_ROTATED bytes=%s keep=%s\n' "$(date -Iseconds)" "$ROTATED_SIZE" "$LOG_ROTATE_KEEP"
fi

cd "$APP_DIR"
if [[ ! -f "$DEPLOY_SCRIPT" ]]; then
  printf '[%s] deploy script is missing: %s\n' "$(date -Iseconds)" "$DEPLOY_SCRIPT"
  printf 'DEPLOY_STATUS=failed\n'
  exit 1
fi

DEPLOY_CALLED="1"
/usr/bin/env bash "$DEPLOY_SCRIPT"
