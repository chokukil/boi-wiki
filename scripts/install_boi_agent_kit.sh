#!/usr/bin/env bash
set -euo pipefail

BOI_KIT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${BOI_KIT_PYTHON:-python3}" "$BOI_KIT_ROOT/agent_kit/install.py" "$@"
