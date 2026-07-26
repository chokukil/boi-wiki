#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 BACKUP_DIRECTORY"
  echo "Restores a 1.10 pg_dump into the isolated 1.11 validation database only."
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
dump_file="$backup_dir/langflow-1.10.pgdump"
secret_file="$backup_dir/LANGFLOW_SECRET_KEY"
if [[ ! -f "$dump_file" || ! -f "$secret_file" ]]; then
  echo "backup directory must contain langflow-1.10.pgdump and LANGFLOW_SECRET_KEY" >&2
  exit 2
fi

validation_db=${LANGFLOW_111_POSTGRES_CONTAINER:-}
validation_app=${LANGFLOW_111_CONTAINER:-}
postgres_user=${LANGFLOW_111_POSTGRES_USER:-langflow}
postgres_db=${LANGFLOW_111_POSTGRES_DB:-langflow}

if [[ -z "$validation_db" || -z "$validation_app" ]]; then
  echo "LANGFLOW_111_POSTGRES_CONTAINER and LANGFLOW_111_CONTAINER must name an isolated clone stack" >&2
  exit 2
fi
if [[ $validation_db == "boi-langflow-postgres" || $validation_app == "boi-langflow" ]]; then
  echo "refusing to target the main 1.10 containers" >&2
  exit 2
fi

docker stop "$validation_app" >/dev/null 2>&1 || true
docker inspect "$validation_db" >/dev/null
docker exec "$validation_db" dropdb -U "$postgres_user" --if-exists "$postgres_db"
docker exec "$validation_db" createdb -U "$postgres_user" "$postgres_db"
docker cp "$dump_file" "$validation_db:/tmp/langflow-1.10.pgdump"
docker exec "$validation_db" pg_restore -U "$postgres_user" -d "$postgres_db" --no-owner --no-privileges /tmp/langflow-1.10.pgdump
echo "Clone restored. Restart 1.11 with LANGFLOW_111_SECRET_KEY set to the backed-up secret."
