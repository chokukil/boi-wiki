#!/usr/bin/env bash
set -euo pipefail
set +x

APP_DIR="${APP_DIR:-/volume1/docker/boi-wiki/app}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.nas.yml}"
ENV_FILE="${ENV_FILE:-.env}"
LOCK_DIR="${LOCK_DIR:-/tmp/boi-wiki-nas-auto-pull.lock}"
DOCKER_COMPOSE_BIN="${DOCKER_COMPOSE_BIN:-/usr/local/bin/docker-compose}"
SUDO_BIN="${SUDO_BIN:-sudo}"
NAS_DOCKER_PATH="${NAS_DOCKER_PATH:-/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin}"
NAS_AUTO_PULL_DRY_RUN="${NAS_AUTO_PULL_DRY_RUN:-0}"

DEPLOY_STATUS="failed"
LOCK_OWNED="0"

log() {
  printf '[%s] %s\n' "$(date -Iseconds)" "$*"
}

finish() {
  local rc=$?
  if [[ "$LOCK_OWNED" == "1" ]]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
  fi
  if [[ "$rc" -ne 0 && "$DEPLOY_STATUS" == "running" ]]; then
    DEPLOY_STATUS="failed"
  fi
  printf 'DEPLOY_STATUS=%s\n' "$DEPLOY_STATUS"
}
trap finish EXIT

blocked() {
  DEPLOY_STATUS="blocked"
  log "blocked: $*"
  exit 2
}

is_hot_reload_path() {
  local path="$1"
  case "$path" in
    data/boi/*|data/event_catalog/*|data/action_catalog/*|docs/*|README.md)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

needs_compose_recreate() {
  local path
  for path in "$@"; do
    if ! is_hot_reload_path "$path"; then
      return 0
    fi
  done
  return 1
}

if [[ "${1:-}" == "--classify-only" ]]; then
  trap - EXIT
  shift
  if needs_compose_recreate "$@"; then
    printf 'compose_required\n'
  else
    printf 'hot_reload\n'
  fi
  exit 0
fi

DEPLOY_STATUS="running"

mkdir -p "$(dirname "$LOCK_DIR")"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  blocked "another NAS auto-pull deployment is already running: $LOCK_DIR"
fi
LOCK_OWNED="1"

cd "$APP_DIR"

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  blocked "current branch is '$current_branch', expected '$BRANCH'"
fi

git update-index -q --refresh || true
if ! git diff --quiet -- .; then
  blocked "tracked working tree changes exist; refusing to pull"
fi
if ! git diff --cached --quiet -- .; then
  blocked "staged tracked changes exist; refusing to pull"
fi

log "fetching $REMOTE $BRANCH"
git fetch "$REMOTE" "$BRANCH"

current_head="$(git rev-parse --verify HEAD)"
remote_head="$(git rev-parse --verify "$REMOTE/$BRANCH")"

if [[ "$current_head" == "$remote_head" ]]; then
  log "already up to date: $BRANCH@$current_head"
  DEPLOY_STATUS="noop"
  exit 0
fi

if ! git merge-base --is-ancestor "$current_head" "$remote_head"; then
  blocked "remote $REMOTE/$BRANCH is not a fast-forward from local HEAD"
fi

mapfile -t changed_files < <(git diff --name-only "$current_head" "$remote_head")
log "fast-forwarding ${#changed_files[@]} changed path(s)"

git pull --ff-only "$REMOTE" "$BRANCH"

if ! needs_compose_recreate "${changed_files[@]}"; then
  log "hot-reload-only change set; docker compose restart is not required"
  DEPLOY_STATUS="success"
  exit 0
fi

if [[ ! -f "docker-compose.yml" ]]; then
  blocked "docker-compose.yml is missing"
fi

tmp_compose="${COMPOSE_FILE}.tmp.$$"
awk '
  NR == 1 && $0 ~ /^name:[[:space:]]*/ { next }
  { gsub(/service_completed_successfully/, "service_started"); print }
' docker-compose.yml > "$tmp_compose"
mv "$tmp_compose" "$COMPOSE_FILE"
log "generated NAS compose overlay: $COMPOSE_FILE"

if [[ ! -f "$ENV_FILE" ]]; then
  blocked "runtime env file is missing: $ENV_FILE"
fi

if [[ "$NAS_AUTO_PULL_DRY_RUN" == "1" ]]; then
  log "dry run: would run docker-compose up -d --build"
  DEPLOY_STATUS="success"
  exit 0
fi

log "running docker-compose up -d --build"
"$SUDO_BIN" env PATH="$NAS_DOCKER_PATH" "$DOCKER_COMPOSE_BIN" \
  -f "$COMPOSE_FILE" \
  --env-file "$ENV_FILE" \
  up -d --build

DEPLOY_STATUS="success"
