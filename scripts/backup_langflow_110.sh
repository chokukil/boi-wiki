#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 OUTPUT_DIRECTORY"
  echo "Backs up the running 1.10 PostgreSQL database and LANGFLOW_SECRET_KEY without stopping it."
}

if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
fi
if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

backup_dir=$1
if [[ -e "$backup_dir" && ! -d "$backup_dir" ]]; then
  echo "backup target is not a directory: $backup_dir" >&2
  exit 2
fi
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

postgres_container=${LANGFLOW_110_POSTGRES_CONTAINER:-boi-langflow-postgres}
langflow_container=${LANGFLOW_110_CONTAINER:-boi-langflow}
postgres_user=${LANGFLOW_POSTGRES_USER:-langflow}
postgres_db=${LANGFLOW_POSTGRES_DB:-langflow}

docker inspect "$postgres_container" >/dev/null
docker inspect "$langflow_container" >/dev/null
docker exec "$postgres_container" pg_dump -U "$postgres_user" -d "$postgres_db" -Fc >"$backup_dir/langflow-1.10.pgdump"
docker inspect "$langflow_container" --format '{{.Config.Image}}' >"$backup_dir/langflow-image.txt"
docker inspect "$langflow_container" --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | sed -n 's/^LANGFLOW_SECRET_KEY=//p' >"$backup_dir/LANGFLOW_SECRET_KEY"
if [[ ! -s "$backup_dir/LANGFLOW_SECRET_KEY" ]]; then
  echo "LANGFLOW_SECRET_KEY was not found in $langflow_container" >&2
  exit 1
fi
chmod 600 "$backup_dir/LANGFLOW_SECRET_KEY" "$backup_dir/langflow-1.10.pgdump"
sha256sum "$backup_dir/langflow-1.10.pgdump" "$backup_dir/LANGFLOW_SECRET_KEY" >"$backup_dir/SHA256SUMS"
echo "Backup written to $backup_dir. Keep it outside source control."
