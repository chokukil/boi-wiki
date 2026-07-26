#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "53912644c443b0a2af0e5c367901575a111b18ae"
AGENT_HUB_ROOT = Path("/home/chokukil/agent-hub-pr25-validation")
AGENT_HUB_SHA = "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
ALLOWED_PREFIXES = (
    ".env.example",
    ".gitignore",
    "README.md",
    "action_gateway/",
    "boi_api/",
    "boi_wiki_mcp/",
    "data/boi/",
    "docker-compose",
    "docs/",
    "infra/keycloak/",
    "langflow/",
    "mock_hcp/",
    "package-lock.json",
    "package.json",
    "scripts/",
    "tests/",
    "validation/",
)
FORBIDDEN_ADDED_MARKERS = (
    "from boi_api.app.v2",
    "from .v2.models",
    "from .v2.service",
    "from .v2.storage",
    "import boi_api.app.v2",
    "AgentV2Service",
    "PatService",
    "semantic_kernel",
    "agent_workspace_v2",
)


def run(*args: str, cwd: Path = ROOT, check: bool = True) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def check(name: str, ok: bool, detail: object) -> dict[str, object]:
    return {"name": name, "ok": ok, "detail": detail}


def main() -> int:
    tracked_changed = [
        line
        for line in run("git", "diff", "--name-only", BASE, "--").splitlines()
        if line
    ]
    untracked = [
        line
        for line in run(
            "git", "ls-files", "--others", "--exclude-standard"
        ).splitlines()
        if line
    ]
    changed = sorted(set(tracked_changed + untracked))
    disallowed = [
        path
        for path in changed
        if not any(path == prefix or path.startswith(prefix) for prefix in ALLOWED_PREFIXES)
    ]
    production_sources = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in (
            ROOT / "boi_api" / "app" / "main.py",
            ROOT / "boi_api" / "app" / "agent_playground.py",
            ROOT / "boi_api" / "app" / "agent_playground_credentials.py",
            ROOT / "action_gateway" / "app" / "main.py",
            ROOT / "boi_wiki_mcp" / "app" / "main.py",
            ROOT / "boi_wiki_mcp" / "app" / "v2.py",
        )
    )
    added_lines = production_sources
    forbidden = [marker for marker in FORBIDDEN_ADDED_MARKERS if marker in added_lines]
    main_source = (ROOT / "boi_api" / "app" / "main.py").read_text(encoding="utf-8")
    playground_html = (
        ROOT / "boi_api" / "app" / "templates" / "agent_playground.html"
    ).read_text(encoding="utf-8")
    playground_js = (
        ROOT / "boi_api" / "app" / "static" / "agent_playground.js"
    ).read_text(encoding="utf-8")
    docs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT
            / "data"
            / "boi"
            / "public"
            / "boi-wiki-manual"
            / "langflow"
            / "agent-playground-onboarding.md",
            ROOT
            / "data"
            / "boi"
            / "public"
            / "boi-wiki-manual"
            / "operations"
            / "agent-playground-operator-runbook.md",
        )
    )
    pet_surface = (playground_html + playground_js + docs).lower()

    results = [
        check(
            "base_is_ancestor",
            run("git", "merge-base", "HEAD", BASE) == BASE,
            BASE,
        ),
        check("changed_path_allowlist", not disallowed, disallowed),
        check("no_agent_v2_added", not forbidden, forbidden),
        check(
            "pet_default_disabled",
            'BOI_PET_AGENT_ENABLED = env_flag("BOI_PET_AGENT_ENABLED", "false")'
            in main_source,
            "BOI_PET_AGENT_ENABLED=false",
        ),
        check(
            "playground_explicitly_hides_pet",
            'title="Agent Playground"' in main_source
            and "hide_pet_agent=True" in main_source,
            "/playground hide_pet_agent=True",
        ),
        check(
            "playground_surface_has_no_pet_assets",
            not any(
                marker in pet_surface
                for marker in ("pet_agent.js", "pet-agent", "pet agent", "boi-agent-root")
            ),
            "html/js/wiki guides",
        ),
    ]
    if AGENT_HUB_ROOT.exists():
        hub_head = run("git", "rev-parse", "HEAD", cwd=AGENT_HUB_ROOT)
        hub_dirty = run("git", "status", "--short", cwd=AGENT_HUB_ROOT)
        results.extend(
            (
                check("agent_hub_fixed_sha", hub_head == AGENT_HUB_SHA, hub_head),
                check("agent_hub_clean", not hub_dirty, hub_dirty),
            )
        )

    payload = {
        "ok": all(item["ok"] for item in results),
        "base": BASE,
        "changed_files": changed,
        "checks": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
