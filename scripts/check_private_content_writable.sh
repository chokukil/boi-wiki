#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIVATE_ROOT="${1:-${ROOT}/data/boi/private}"
TARGET_UID="${BOI_CONTENT_OWNER_UID:-$(id -u)}"
TARGET_GID="${BOI_CONTENT_OWNER_GID:-$(id -g)}"

nearest_existing_parent() {
  local path="$1"
  while [ ! -e "$path" ] && [ "$path" != "/" ]; do
    path="$(dirname "$path")"
  done
  printf '%s\n' "$path"
}

if [ ! -e "$PRIVATE_ROOT" ]; then
  parent="$(nearest_existing_parent "$PRIVATE_ROOT")"
  if [ -d "$parent" ] && [ -w "$parent" ] && [ -x "$parent" ]; then
    exit 0
  fi
  echo "Private BoI root cannot be created: $PRIVATE_ROOT" >&2
  echo "Nearest existing parent is not writable: $parent" >&2
  exit 4
fi

if [ ! -d "$PRIVATE_ROOT" ]; then
  echo "Private BoI root is not a directory: $PRIVATE_ROOT" >&2
  exit 4
fi

mapfile -t unwritable_paths < <(
  find "$PRIVATE_ROOT" -xdev \( -type d ! -writable -o -type f ! -writable \) -print
)

if [ "${#unwritable_paths[@]}" -eq 0 ]; then
  exit 0
fi

echo "Private BoI content is not writable by $(id -un) ($(id -u):$(id -g))." >&2
echo "Affected paths: ${#unwritable_paths[@]}" >&2
for path in "${unwritable_paths[@]:0:10}"; do
  owner="$(stat -c '%U:%G mode=%a' "$path" 2>/dev/null || printf unknown)"
  echo "- $path ($owner)" >&2
done
if [ "${#unwritable_paths[@]}" -gt 10 ]; then
  echo "- ... and $((${#unwritable_paths[@]} - 10)) more" >&2
fi
printf 'Repair explicitly, then restart:\n  sudo chown -R %q:%q %q\n' "$TARGET_UID" "$TARGET_GID" "$PRIVATE_ROOT" >&2
exit 4
