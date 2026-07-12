#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLIENT=""
TARGET=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --client) CLIENT="${2:-}"; shift 2 ;;
    --target) TARGET="${2:-}"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

case "$CLIENT" in
  codex)
    TARGET="${TARGET:-${CODEX_HOME:-$HOME/.codex}/skills/boi-wiki-v2}"
    SOURCE="$ROOT/agent_kit/codex/SKILL.md"
    ;;
  claude)
    TARGET="${TARGET:-$PWD/.claude/skills/boi-wiki-v2}"
    SOURCE="$ROOT/agent_kit/claude/SKILL.md"
    ;;
  *)
    echo "Usage: $0 --client codex|claude [--target DIR]" >&2
    exit 2
    ;;
esac

mkdir -p "$TARGET"
install -m 0644 "$SOURCE" "$TARGET/SKILL.md"
install -m 0644 "$ROOT/agent_kit/README.md" "$TARGET/README.md"

echo "Installed BoI Wiki v2 Agent Kit: $TARGET"
echo "Set BOI_PAT in an environment variable or secret manager; do not write it into the installed files."
echo "Start with boi_bootstrap or GET /api/v2/bootstrap."
