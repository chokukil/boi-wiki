#!/usr/bin/env bash
set -euo pipefail

SRC="${1:-/home/chokukil/boi-wiki}"
DST="${2:-/mnt/c/Users/choku/boi-wiki-run}"

mkdir -p "$DST"

# Runtime data protection rules. These comments are intentionally kept in
# --protect=<path> form so tests can assert the contract without depending on
# rsync filter shorthand.
# --protect=data/events/*.jsonl
# --protect=data/actions/*.jsonl
# --protect=data/boi/private/*/boi-private-*.md
# --protect=data/boi/team/*/boi-team-*.md
# --protect=data/boi/public/boi-public-*.md
rsync -rltD \
  --omit-dir-times \
  --delete \
  --no-owner \
  --no-group \
  --filter='P data/events/*.jsonl' \
  --filter='P data/actions/*.jsonl' \
  --filter='P data/boi/private/*/boi-private-*.md' \
  --filter='P data/boi/team/*/boi-team-*.md' \
  --filter='P data/boi/public/boi-public-*.md' \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  "$SRC"/ "$DST"/
