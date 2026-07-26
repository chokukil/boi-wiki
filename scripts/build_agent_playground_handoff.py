#!/usr/bin/env python3
"""Build a secret-scanned, checksum-pinned Agent Playground handoff package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON evidence must be an object: {path}")
    return payload


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def git_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip(),
        "branch": subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=path, text=True
        ).strip(),
        "porcelain": subprocess.check_output(
            ["git", "status", "--short"], cwd=path, text=True
        ).splitlines(),
    }


def safe_browser_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "passed": payload.get("passed"),
        "run_id": payload.get("run_id"),
        "runner": payload.get("runner"),
        "agent_hub": payload.get("agent_hub"),
        "langflow": payload.get("langflow"),
        "boi_sso": payload.get("boi_sso"),
        "boi_sso_viewer": payload.get("boi_sso_viewer"),
        "boi_logout": payload.get("boi_logout"),
        "boi_action": payload.get("boi_action"),
        "exact_chain": payload.get("exact_chain"),
        "expected_http_errors": payload.get("expected_http_errors"),
        "unexpected_http_errors": payload.get("unexpected_http_errors"),
        "console_errors": payload.get("console_errors"),
        "ignored_console_warnings": payload.get("ignored_console_warnings"),
        "ignored_auth_bootstrap_errors": payload.get(
            "ignored_auth_bootstrap_errors"
        ),
        "page_errors": payload.get("page_errors"),
        "started_at": payload.get("started_at"),
        "finished_at": payload.get("finished_at"),
    }


def safe_model_validation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": payload.get("ok"),
        "run_id": payload.get("run_id"),
        "oidc": payload.get("oidc"),
        "model_flow": payload.get("model_flow"),
        "incompatible_flow": payload.get("incompatible_flow"),
        "expected_http_errors": payload.get("expected_http_errors"),
        "unexpected_http_errors": payload.get("unexpected_http_errors"),
        "console_errors": payload.get("console_errors"),
        "page_errors": payload.get("page_errors"),
    }


def flow_validation(
    runtime_root: Path,
    employee_id: str,
    flow_id: str,
) -> dict[str, Any]:
    state = read_json(
        runtime_root / "agent-playground" / "users" / f"{employee_id}.json"
    )
    registry = next(
        (
            item
            for item in reversed(state.get("flow_registry") or [])
            if isinstance(item, dict) and str(item.get("flow_id") or "") == flow_id
        ),
        None,
    )
    if registry is None:
        raise RuntimeError(f"Flow validation state was not found: {flow_id}")
    return {
        key: registry.get(key)
        for key in (
            "endpoint_id",
            "project_id",
            "flow_id",
            "name",
            "endpoint_name",
            "artifact_version",
            "artifact_checksum",
            "deployment_id",
            "validation_status",
            "failure_reason",
            "validated_at",
            "validation_history",
        )
    }


def build_bundle(target: Path) -> None:
    paths = [
        *sorted((ROOT / "langflow" / "custom_components" / "boi").glob("*.py")),
        ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json",
        ROOT / "langflow" / "flows" / "boi_wiki_agent_loop_model_agent.json",
        ROOT / "langflow" / "compatibility-manifest.json",
        ROOT / "langflow" / "agent_hub" / "README.md",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(ROOT))


def secret_scan(root: Path) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    text_suffixes = {
        ".json",
        ".jsonl",
        ".md",
        ".txt",
        ".yaml",
        ".yml",
        ".py",
        ".js",
        ".mjs",
        ".css",
        ".html",
    }
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                matches.append(
                    {
                        "file": str(path.relative_to(root)),
                        "pattern": pattern.pattern,
                    }
                )
    return {"ok": not matches, "matches": matches}


def write_checksums(root: Path) -> None:
    rows = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "SHA256SUMS":
            continue
        rows.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root)}"
        )
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-evidence-root", type=Path, required=True)
    parser.add_argument("--fresh-onboarding-dir", required=True)
    parser.add_argument("--canonical-dir", required=True)
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--negative-recovery-dir", default="")
    parser.add_argument("--cross-author-dir", default="")
    parser.add_argument("--action-abstraction-dir", default="")
    parser.add_argument("--wiki-docs-dir", default="")
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument(
        "--langflow-regression-evidence",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--langflow-migration-evidence-dir",
        type=Path,
        default=None,
    )
    parser.add_argument("--bundle-boundary-evidence", type=Path, default=None)
    parser.add_argument("--full-pytest-log", type=Path, default=None)
    parser.add_argument("--connector-regression-log", type=Path, default=None)
    parser.add_argument("--incompatible-flow-evidence", type=Path, default=None)
    parser.add_argument(
        "--agent-hub-checkout",
        type=Path,
        default=Path("/home/chokukil/agent-hub-pr25-validation"),
    )
    parser.add_argument("--feature-commit", default="")
    parser.add_argument(
        "--live-audit",
        action="store_true",
        help="Include live isolated-stack and immutable checkout checks.",
    )
    args = parser.parse_args()

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    browser_root = output / "browser"
    copy_tree(
        args.source_evidence_root / args.fresh_onboarding_dir,
        browser_root / "fresh-onboarding",
    )
    copy_tree(
        args.source_evidence_root / args.canonical_dir,
        browser_root / "canonical-exact-e2e",
    )
    copy_tree(
        args.source_evidence_root / args.model_dir,
        browser_root / "model-agent-exact-e2e",
    )
    if args.negative_recovery_dir:
        copy_tree(
            args.source_evidence_root / args.negative_recovery_dir,
            browser_root / "negative-recovery",
        )
    if args.cross_author_dir:
        copy_tree(
            args.source_evidence_root / args.cross_author_dir,
            browser_root / "cross-author-adoption",
        )
    if args.action_abstraction_dir:
        copy_tree(
            args.source_evidence_root / args.action_abstraction_dir,
            browser_root / "action-abstraction",
        )
    if args.wiki_docs_dir:
        copy_tree(
            args.source_evidence_root / args.wiki_docs_dir,
            browser_root / "wiki-onboarding-docs",
        )

    canonical = read_json(
        browser_root / "canonical-exact-e2e" / "playwright-result.json"
    )
    model_root = browser_root / "model-agent-exact-e2e"
    model_result_path = model_root / "playwright-result.json"
    if not model_result_path.exists():
        model_result_path = model_root / "model-incompatible-result.json"
    model = read_json(model_result_path)
    fresh = read_json(
        browser_root / "fresh-onboarding" / "fresh-onboarding-result.json"
    )
    negative = (
        read_json(
            browser_root / "negative-recovery" / "negative-recovery-result.json"
        )
        if args.negative_recovery_dir
        else {}
    )
    cross_author = (
        read_json(
            browser_root
            / "cross-author-adoption"
            / "cross-author-adoption-result.json"
        )
        if args.cross_author_dir
        else {}
    )
    action_abstraction = (
        read_json(
            browser_root / "action-abstraction" / "action-abstraction-result.json"
        )
        if args.action_abstraction_dir
        else {}
    )
    wiki_docs = (
        read_json(
            browser_root
            / "wiki-onboarding-docs"
            / "wiki-onboarding-docs-result.json"
        )
        if args.wiki_docs_dir
        else {}
    )
    model_passed = bool(model.get("passed") or model.get("ok"))
    if not all((fresh.get("ok"), canonical.get("passed"), model_passed)):
        raise RuntimeError("one or more required browser evidence chains did not pass")
    if args.negative_recovery_dir and not negative.get("ok"):
        raise RuntimeError("negative/recovery browser evidence did not pass")
    if args.cross_author_dir and not cross_author.get("ok"):
        raise RuntimeError("cross-author Agent Hub adoption evidence did not pass")
    if args.action_abstraction_dir and not action_abstraction.get("ok"):
        raise RuntimeError("connector-neutral Action browser evidence did not pass")
    if args.wiki_docs_dir and not wiki_docs.get("ok"):
        raise RuntimeError("Wiki onboarding document browser evidence did not pass")

    canonical_flow_id = str(
        canonical.get("agent_hub", {}).get("deployment", {}).get("flow_id") or ""
    )
    model_flow_id = str(
        model.get("agent_hub", {}).get("deployment", {}).get("flow_id")
        or model.get("model_flow", {}).get("flow_id")
        or ""
    )
    validation = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fresh_onboarding": fresh,
        "negative_recovery": negative,
        "cross_author_adoption": cross_author,
        "action_abstraction": action_abstraction,
        "wiki_onboarding_docs": wiki_docs,
        "canonical": safe_browser_summary(canonical),
        "model_agent": (
            safe_browser_summary(model)
            if model.get("passed") is not None
            else safe_model_validation_summary(model)
        ),
        "flow_validation": {
            "canonical": flow_validation(
                args.runtime_root, "100002", canonical_flow_id
            ),
            "model_agent": flow_validation(
                args.runtime_root, "100002", model_flow_id
            ),
        },
    }
    (output / "validation-summary.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for path in (
        ROOT / "langflow" / "flows" / "boi_wiki_agent_loop.json",
        ROOT / "langflow" / "flows" / "boi_wiki_agent_loop_model_agent.json",
        ROOT / "langflow" / "compatibility-manifest.json",
        ROOT / "langflow" / "agent_hub" / "README.md",
        ROOT / "docs" / "AGENT_PLAYGROUND_INTEGRATION.md",
        ROOT / "validation" / "agent-hub" / "COMPLETION_AUDIT.md",
        ROOT / "validation" / "agent-hub" / "CORPORATE_SSO_HANDOFF.md",
    ):
        copy_file(path, output / "delivery" / path.relative_to(ROOT))
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
    ):
        copy_file(path, output / "delivery" / "wiki" / path.name)
    build_bundle(output / "delivery" / "boi-langflow-1.11-bundle.zip")
    copy_file(
        ROOT
        / "validation"
        / "agent-playground"
        / "assets"
        / "shared_evidence_priority_selector.py",
        output
        / "delivery"
        / "agent-hub-examples"
        / "shared_evidence_priority_selector.py",
    )

    boundary = json.loads(
        subprocess.check_output(
            ["python3", "scripts/check_agent_playground_langflow_boundary.py"],
            cwd=ROOT,
            text=True,
        )
    )
    (output / "regression").mkdir(parents=True, exist_ok=True)
    (output / "regression" / "langflow-boundary.json").write_text(
        json.dumps(boundary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mainline_boundary = json.loads(
        subprocess.check_output(
            ["python3", "scripts/check_agent_playground_mainline_boundary.py"],
            cwd=ROOT,
            text=True,
        )
    )
    (output / "regression" / "mainline-boundary.json").write_text(
        json.dumps(mainline_boundary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.langflow_regression_evidence:
        copy_file(
            args.langflow_regression_evidence.resolve(),
            output / "regression" / "langflow-patch-compatibility.json",
        )
    if args.langflow_migration_evidence_dir:
        migration_root = args.langflow_migration_evidence_dir.resolve()
        for name in (
            "langflow-110-import-runtime-proof.json",
            "langflow-110-clean-import.json",
            "langflow-111-final-regression.json",
            "langflow-migration-summary.json",
            "langflow-migration-rollback-revalidation.json",
        ):
            source = migration_root / name
            if source.exists():
                copy_file(source, output / "regression" / name)
    if args.bundle_boundary_evidence:
        copy_file(
            args.bundle_boundary_evidence.resolve(),
            output / "regression" / "langflow-bundle-boundary.json",
        )
    if args.full_pytest_log:
        copy_file(
            args.full_pytest_log.resolve(),
            output / "regression" / "full-pytest.log",
        )
    if args.connector_regression_log:
        copy_file(
            args.connector_regression_log.resolve(),
            output / "regression" / "action-gateway-connectors.log",
        )
    if args.incompatible_flow_evidence:
        copy_file(
            args.incompatible_flow_evidence.resolve(),
            output / "regression" / "incompatible-flow-validation.json",
        )

    states = {
        "feature": git_state(ROOT),
        "agent_hub": git_state(args.agent_hub_checkout),
    }
    base_commit = "53912644c443b0a2af0e5c367901575a111b18ae"
    states["feature"]["base"] = base_commit
    states["feature"]["commits"] = subprocess.check_output(
        ["git", "rev-list", "--reverse", f"{base_commit}..HEAD"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    states["agent_hub"]["expected_head"] = (
        "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
    )
    states["agent_hub"]["clean"] = not states["agent_hub"]["porcelain"]
    (output / "source-state.json").write_text(
        json.dumps(states, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    commits = (
        [args.feature_commit]
        if args.feature_commit
        else states["feature"]["commits"]
    )
    if not commits:
        commits = [states["feature"]["head"]]
    cherry_pick_rows = [
        f"{index}. `{commit}`을 cherry-pick한다."
        for index, commit in enumerate(commits, start=1)
    ]
    next_step = len(cherry_pick_rows) + 1
    (output / "CHERRY_PICK_ORDER.md").write_text(
        "\n".join(
            [
                "# Agent Playground 사내 적용 순서",
                "",
                *cherry_pick_rows,
                f"{next_step}. DB migration이 포함된 경우 기존 사내 절차로 적용한다.",
                f"{next_step + 1}. Keycloak `boi-wiki` client와 `empno` claim, callback/origin을 등록한다.",
                f"{next_step + 2}. 공식 Langflow 1.11 이미지는 수정하지 않고 BoI bundle을 read-only mount한다.",
                f"{next_step + 3}. `scripts/regress_langflow_patch.py`로 public API와 bundle 호환성을 확인한다.",
                f"{next_step + 4}. 온보딩 → Agent Hub 배포 → exact Flow → Action E2E를 재실행한다.",
                "",
                "Agent Hub PR #25 checkout은 cherry-pick하거나 수정하지 않는다.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "\n".join(
            [
                "# BoI Agent Playground handoff",
                "",
                "이 패키지는 Langflow와 Agent Hub 소스를 수정하지 않고 검증한 인수 증거다.",
                "",
                f"- canonical exact Flow: `{canonical_flow_id}`",
                f"- LM Studio Gemma exact Flow: `{model_flow_id}`",
                "- Langflow image: `"
                + str(
                    next(
                        check["detail"]
                        for check in boundary["checks"]
                        if check["name"] == "official_image_digest"
                    )
                )
                + "`",
                "- 브라우저 체인: `browser/`",
                "- 타 작성자 승인 Flow·Component 재사용: `browser/cross-author-adoption/`",
                "- connector-neutral Action과 Langflow binding 분리: `browser/action-abstraction/`",
                "- 시작·운영 Wiki 문서 desktop/mobile: `browser/wiki-onboarding-docs/`",
                "- 연결 실패·복구·endpoint 독립성: `browser/negative-recovery/`",
                "- Flow·bundle·Wiki 문서: `delivery/`",
                "- 공개 API·read-only extension 회귀: `regression/`",
                "- 요구사항별 자동 완료 감사: `regression/mainline-completion-audit.json`",
                "- exact deployment·Action·Wiki 실행 요약: `validation-summary.json`",
                "- 적용 순서: `CHERRY_PICK_ORDER.md`",
                "- 전체 파일 checksum: `SHA256SUMS`",
                "",
                "다른 작성자의 Agent Hub 승인 자산도 개인 endpoint/project로 배포한 뒤",
                "동일한 exact Flow 검증을 통과하면 Action으로 연결할 수 있다.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # The completion audit consumes the package secret-scan result. Generate a
    # preliminary scan first, then rerun it after adding the audit itself.
    scan = secret_scan(output)
    (output / "secret-scan.json").write_text(
        json.dumps(scan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not scan["ok"]:
        raise RuntimeError("handoff package secret scan failed")
    audit_command = [
        "python3",
        "scripts/audit_agent_playground_mainline_completion.py",
        "--handoff-root",
        str(output),
        "--output",
        str(output / "regression" / "mainline-completion-audit.json"),
        "--agent-hub-checkout",
        str(args.agent_hub_checkout.resolve()),
    ]
    if args.live_audit:
        audit_command.append("--live")
    subprocess.run(audit_command, cwd=ROOT, check=True)

    scan = secret_scan(output)
    (output / "secret-scan.json").write_text(
        json.dumps(scan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not scan["ok"]:
        raise RuntimeError("handoff package secret scan failed after completion audit")
    write_checksums(output)
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "canonical_flow_id": canonical_flow_id,
                "model_flow_id": model_flow_id,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
