#!/usr/bin/env python3
"""Build the secret-free Universal Simulation MCP delivery package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SECRET_PATTERNS = (
    re.compile(r"boi_(?:pat|run)_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~-]{20,}", re.IGNORECASE),
    re.compile(r'"(?:api_key|access_token|refresh_token)"\s*:\s*"(?!(?:\\$\\{|\[REDACTED\]))[^"]{12,}"', re.IGNORECASE),
)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def copy_file(source: Path, target: Path) -> None:
    if not source.exists():
        raise RuntimeError(f"required handoff file is missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"required evidence directory is missing: {source}")
    if target.exists():
        raise RuntimeError(f"handoff target already exists: {target}")
    shutil.copytree(source, target)


def git_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=path, text=True
        ).strip(),
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=path, text=True
        ).strip(),
        "status": subprocess.check_output(
            ["git", "status", "--short"], cwd=path, text=True
        ).splitlines(),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_bundle(target: Path) -> None:
    sources = [
        *sorted((ROOT / "langflow/custom_components/boi").glob("*.py")),
        ROOT / "langflow/flows/boi_universal_simulation_mcp.json",
        ROOT / "langflow/compatibility-manifest.json",
        ROOT / "langflow/agent_hub/README.md",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources:
            archive.write(source, source.relative_to(ROOT))


def scan(root: Path) -> dict[str, Any]:
    suffixes = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml", ".py", ".js", ".mjs", ".html", ".css"}
    matches: list[dict[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.suffix.lower() not in suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                matches.append(
                    {"file": str(path.relative_to(root)), "pattern": pattern.pattern}
                )
    return {"ok": not matches, "matches": matches}


def write_sums(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "SHA256SUMS":
            continue
        rows.append(f"{sha256(path)}  {path.relative_to(root)}")
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument(
        "--agent-hub-checkout",
        type=Path,
        default=Path("/home/chokukil/agent-hub-pr25-validation"),
    )
    parser.add_argument("--feature-commit", default="")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    evidence_root = args.evidence_root.resolve()

    evidence_dirs = {
        "onboarding-mcp-canvas": "browser-final",
        "agent-hub-action": "agent-hub-action",
        "team-action": "team-action",
        "cross-author-component": "cross-author-component",
        "cross-team-action": "cross-team-action",
        "incompatible-component": "incompatible-component",
        "checksum-drift": "checksum-drift",
        "action-connectors": "action-abstraction",
    }
    for target_name, source_name in evidence_dirs.items():
        copy_tree(
            evidence_root / source_name,
            output / "evidence" / target_name,
        )

    required_results = {
        "onboarding": output / "evidence/onboarding-mcp-canvas/result.json",
        "agent_hub": output / "evidence/agent-hub-action/playwright-result.json",
        "team_action": output / "evidence/team-action/result.json",
        "cross_author": output / "evidence/cross-author-component/cross-author-adoption-result.json",
        "cross_team": output / "evidence/cross-team-action/result.json",
        "incompatible": output / "evidence/incompatible-component/result.json",
        "drift": output / "evidence/checksum-drift/result.json",
        "action_connectors": output / "evidence/action-connectors/action-abstraction-result.json",
    }
    results = {name: read_json(path) for name, path in required_results.items()}
    pass_fields = {
        "onboarding": "ok",
        "agent_hub": "passed",
        "team_action": "ok",
        "cross_author": "ok",
        "cross_team": "ok",
        "incompatible": "ok",
        "drift": "ok",
        "action_connectors": "ok",
    }
    failed = [
        name
        for name, field in pass_fields.items()
        if results[name].get(field) is not True
    ]
    if failed:
        raise RuntimeError(f"browser evidence did not pass: {failed}")

    deliverables = (
        ROOT / "langflow/flows/boi_universal_simulation_mcp.json",
        ROOT / "langflow/compatibility-manifest.json",
        ROOT / "langflow/agent_hub/README.md",
        ROOT / "langflow/agent_hub/universal-simulation-mcp-client.example.json",
        ROOT / "langflow/agent_hub/universal-simulation-mcp-samples.json",
        ROOT / "docs/UNIVERSAL_SIMULATION_MCP_ONE_PAGER.md",
    )
    for source in deliverables:
        copy_file(source, output / "delivery" / source.relative_to(ROOT))
    copy_file(
        ROOT / "validation/agent-playground/assets/shared_gemma_simulation_agent.py",
        output / "delivery/agent-hub-examples/shared_gemma_simulation_agent.py",
    )
    docs_root = ROOT / "data/boi/public/boi-wiki-manual"
    for source in sorted((docs_root / "langflow").glob("universal-simulation-mcp-*.md")):
        copy_file(source, output / "delivery/wiki" / source.name)
    copy_file(
        docs_root / "operations/agent-hub-integration-boundary.md",
        output / "delivery/wiki/agent-hub-integration-boundary.md",
    )
    build_bundle(output / "delivery/boi-universal-simulation-mcp-langflow-1.11-bundle.zip")

    regression_dir = evidence_root / "regression"
    for name in (
        "pytest-full-final.txt",
        "langflow-patch-regression.json",
        "langflow-static-boundary.json",
        "langflow-bundle-boundary.json",
        "langflow-migration-rollback.json",
    ):
        copy_file(regression_dir / name, output / "regression" / name)

    feature = git_state(ROOT)
    agent_hub = git_state(args.agent_hub_checkout.resolve())
    expected_agent_hub = "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
    if agent_hub["head"] != expected_agent_hub or agent_hub["status"]:
        raise RuntimeError("Agent Hub checkout is not at the immutable clean baseline")
    source_state = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature": feature,
        "agent_hub": {
            **agent_hub,
            "expected_head": expected_agent_hub,
            "clean": True,
        },
        "langflow_artifact_sha256": sha256(
            ROOT / "langflow/flows/boi_universal_simulation_mcp.json"
        ),
    }
    (output / "source-state.json").write_text(
        json.dumps(source_state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    commit = args.feature_commit or feature["head"]
    (output / "CHERRY_PICK_ORDER.md").write_text(
        "\n".join(
            [
                "# Universal Simulation MCP 사내 적용 순서",
                "",
                f"1. `{commit}`을 `origin/main` 기반 사내 브랜치에 cherry-pick한다.",
                "2. 공식 Langflow 1.11 이미지는 수정하지 않고 BoI bundle을 read-only mount한다.",
                "3. `boi-wiki` Keycloak client와 `empno` claim, callback/origin을 사내 값으로 등록한다.",
                "4. Playground에서 Langflow API Key를 연결하고 자동 bootstrap을 실행한다.",
                "5. 수정 없는 Agent Hub UI에서 대표 Flow를 개인 프로젝트에 배포한다.",
                "6. exact Flow 재발견, MCP preview, Action 일반/SOP/private draft 검증을 재실행한다.",
                "",
                "Agent Hub 소스·DB schema·API는 cherry-pick하거나 수정하지 않는다.",
            ]
        ) + "\n",
        encoding="utf-8",
    )

    exact_chain = results["agent_hub"].get("exact_chain") or {}
    summary = {
        "ok": True,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "representative_flow": {
            "name": "BoI Universal Simulation MCP",
            "endpoint_name": "boi-universal-simulation-mcp",
            "version": "1.0.0",
            "mcp_tool": "boi_universal_simulate",
            "artifact_sha256": source_state["langflow_artifact_sha256"],
        },
        "exact_chain": exact_chain,
        "model_runtime": results["onboarding"].get("representative_flow", {}).get("runtime"),
        "mcp": results["onboarding"].get("mcp"),
        "cross_author_component": results["cross_author"].get("validation"),
        "drift": results["drift"].get("drift"),
        "drift_recovery": results["drift"].get("revalidation"),
        "team_private_draft": results["team_action"].get("private_draft"),
        "connector_neutral_actions": results["action_connectors"].get(
            "gateway_invocations"
        ),
        "agent_hub_unmodified": True,
        "langflow_unmodified": True,
    }
    (output / "validation-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "\n".join(
            [
                "# BoI Universal Simulation MCP handoff",
                "",
                "Langflow와 Agent Hub 소스 수정 없이 검증한 대표 Flow 전달 패키지다.",
                "",
                "- 대표 Flow·bundle·MCP 설정 예시: `delivery/`",
                "- OIDC·Gemma·MCP·Canvas·Agent Hub·Action 증거: `evidence/`",
                "- 전체 회귀·Langflow 경계·migration 결과: `regression/`",
                "- exact 실행 사슬: `validation-summary.json`",
                "- 사내 적용 순서: `CHERRY_PICK_ORDER.md`",
                "- 전체 checksum: `SHA256SUMS`",
            ]
        ) + "\n",
        encoding="utf-8",
    )

    secret_result = scan(output)
    (output / "secret-scan.json").write_text(
        json.dumps(secret_result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not secret_result["ok"]:
        raise RuntimeError("handoff secret scan failed")
    write_sums(output)
    print(json.dumps({"ok": True, "output": str(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
