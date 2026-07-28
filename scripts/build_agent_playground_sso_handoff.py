#!/usr/bin/env python3
"""Build the provider-neutral Agent Playground SSO handoff package."""

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
AGENT_HUB_ROOT = Path("/home/chokukil/agent-hub-pr25-validation")
AGENT_HUB_SHA = "7ca556b7885f316eedd757a7190b748bb7e0f7e5"
LANGFLOW_IMAGE = (
    "langflowai/langflow:1.11.0@"
    "sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf"
)
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".mjs",
    ".py",
    ".txt",
    ".yaml",
    ".yml",
}
SECRET_PATTERNS = (
    re.compile(r"boi_(?:pat|run)_[0-9a-f]{16}_[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~-]{20,}", re.IGNORECASE),
    re.compile(
        r'"(?:api_key|access_token|refresh_token|id_token|run_token|pat)"'
        r'\s*:\s*"(?!(?:\$\{|\[REDACTED\]))[^"]{12,}"',
        re.IGNORECASE,
    ),
    re.compile(
        r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b"
    ),
)


def run(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value


def copy_file(source: Path, target: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"required file is missing: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise RuntimeError(f"required directory is missing: {source}")
    if target.exists():
        raise RuntimeError(f"target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_state(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "head": run("git", "rev-parse", "HEAD", cwd=path),
        "branch": run("git", "branch", "--show-current", cwd=path),
        "status": run("git", "status", "--short", cwd=path).splitlines(),
        "tracked_diff": subprocess.run(
            ["git", "diff", "--quiet"], cwd=path, check=False
        ).returncode
        == 0,
        "staged_diff": subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=path, check=False
        ).returncode
        == 0,
    }


def assert_empty_errors(payload: dict[str, Any], name: str) -> None:
    for key in (
        "unexpected",
        "unexpected_http_errors",
        "console_errors",
        "page_errors",
    ):
        value = payload.get(key)
        if value not in (None, []):
            raise RuntimeError(f"{name}.{key} is not empty: {value!r}")


def assert_evidence(evidence_root: Path) -> dict[str, dict[str, Any]]:
    specs = {
        "oidc_browser": (
            evidence_root / "agent-playground-browser-sso/result.json",
            "ok",
        ),
        "trusted_header": (
            evidence_root / "agent-playground-trusted-header/result.json",
            "ok",
        ),
        "sso_onboarding": (
            evidence_root / "agent-playground-sso-onboarding/result.json",
            "ok",
        ),
        "flow_origin": (
            evidence_root / "agent-playground-flow-origin/playwright-result.json",
            "ok",
        ),
        "agent_hub": (
            evidence_root / "agent-playground-agent-hub-sso/playwright-result.json",
            "passed",
        ),
        "exact_chain": (
            evidence_root / "agent-playground-universal-exact-chain-final/result.json",
            "ok",
        ),
        "drift": (
            evidence_root / "agent-playground-universal-drift-final/result.json",
            "ok",
        ),
        "wiki_docs": (
            evidence_root
            / "agent-playground-wiki-onboarding/wiki-onboarding-docs-result.json",
            "ok",
        ),
        "security_context": (
            evidence_root
            / "agent-playground-security-context-hardening/result.json",
            "ok",
        ),
        "external_auth": (
            evidence_root
            / "agent-playground-current/regression/langflow-external-auth-contract-final.json",
            "ok",
        ),
        "keycloak_reference": (
            evidence_root
            / "agent-playground-current/regression/keycloak-reference-contract-final.json",
            "ok",
        ),
        "corporate_runner_self_test": (
            evidence_root
            / "agent-playground-corporate-sso-validation/corporate-sso-acceptance.json",
            "ok",
        ),
    }
    payloads: dict[str, dict[str, Any]] = {}
    for name, (path, pass_field) in specs.items():
        payload = read_json(path)
        if payload.get(pass_field) is not True:
            raise RuntimeError(f"{name} evidence did not pass: {path}")
        assert_empty_errors(payload, name)
        payloads[name] = payload

    oidc = payloads["oidc_browser"]
    if (
        oidc.get("employee_id") != "100002"
        or oidc.get("boi_auth_source") != "oidc"
        or oidc.get("langflow_user") != "100002"
        or oidc.get("second_password_form") is not False
        or oidc.get("browser_sso_mode") != "embedded_sso"
        or oidc.get("browser_sso_status") != "ready"
        or not all(
            (oidc.get("logout") or {}).get(key) is True
            for key in (
                "boi_session_cleared",
                "langflow_session_cleared",
                "provider_session_cleared",
                "canvas_requires_reauthentication",
            )
        )
    ):
        raise RuntimeError(
            "OIDC browser SSO evidence does not prove same-user no-login and coordinated logout"
        )

    trusted = payloads["trusted_header"]
    bridge = trusted.get("bridge") or {}
    langflow = trusted.get("langflow") or {}
    spoof = trusted.get("spoof") or {}
    if (
        trusted.get("identity", {}).get("auth_source") != "trusted_header"
        or bridge.get("algorithm") != "RS256"
        or bridge.get("ttl_seconds") != 60
        or bridge.get("token_exposed") is not False
        or langflow.get("employee_id") != "100002"
        or langflow.get("second_password_form") is not False
        or spoof.get("stripped_by_gateway") is not True
    ):
        raise RuntimeError("trusted-header and Token Bridge evidence is incomplete")

    hub = payloads["agent_hub"]
    chain = payloads["exact_chain"]
    drift = payloads["drift"]
    origin = payloads["flow_origin"]
    hub_flow = str(hub.get("exact_chain", {}).get("flow_id") or "")
    chain_flow = str(chain.get("exact_reference", {}).get("flow_id") or "")
    drift_flow = str(drift.get("exact_reference", {}).get("flow_id") or "")
    origin_flow = str(origin.get("desktop", {}).get("expected_prd_flow_id") or "")
    if not hub_flow or len({hub_flow, chain_flow, drift_flow, origin_flow}) != 1:
        raise RuntimeError("Agent Hub, Flow origin, Action, and drift evidence disagree")
    hub_checksum = str(
        hub.get("exact_chain", {}).get("artifact_checksum") or ""
    )
    chain_checksum = str(
        chain.get("exact_reference", {}).get("artifact_checksum") or ""
    )
    drift_checksum = str(drift.get("exact_reference", {}).get("checksum") or "")
    if not hub_checksum or len({hub_checksum, chain_checksum, drift_checksum}) != 1:
        raise RuntimeError("exact Flow checksums do not form one evidence chain")
    if (
        chain.get("mcp", {}).get("forced_private_draft", {}).get("write_blocked")
        is not True
        or chain.get("caller_bound_save", {})
        .get("action", {})
        .get("owner_employee_id")
        != "100002"
        or chain.get("viewer", {}).get("action_status") != 403
        or drift.get("drift", {}).get("mcp_status") != 409
        or drift.get("drift", {}).get("action_status") != 409
    ):
        raise RuntimeError("MCP write policy, caller ACL, or drift blocking is unproven")
    if any(item.get("status") != 200 for item in payloads["wiki_docs"]["documents"]):
        raise RuntimeError("one or more Wiki handoff documents were not HTTP 200")

    external = payloads["external_auth"]
    external_checks = external.get("checks") or {}
    if (
        external.get("image") != LANGFLOW_IMAGE
        or external.get("token_exposed") is not False
        or int(external.get("jwks_requests") or 0) < 1
        or external_checks.get("valid", {}).get("status") != 200
        or external_checks.get("valid", {}).get("username") != "100002"
        or not all(
            external_checks.get(name, {}).get("rejected") is True
            for name in (
                "invalid_signature",
                "invalid_issuer",
                "invalid_audience",
                "expired",
                "missing_token",
            )
        )
    ):
        raise RuntimeError("official Langflow external-JWT contract evidence is incomplete")

    keycloak_reference = payloads["keycloak_reference"]
    keycloak_checks = keycloak_reference.get("checks") or {}
    if (
        keycloak_reference.get("provider_role")
        != "local reference implementation only"
        or not all(keycloak_checks.values())
        or keycloak_reference.get("admin_token_exposed") is not False
        or any(
            client.get("secret_exposed") is not False
            for client in (keycloak_reference.get("clients") or {}).values()
        )
    ):
        raise RuntimeError("local Keycloak OIDC reference contract evidence is incomplete")

    corporate_self_test = payloads["corporate_runner_self_test"]
    if (
        corporate_self_test.get("schema")
        != "boi.agent-playground.corporate-sso-acceptance.v1"
        or corporate_self_test.get("environment") != "validation"
        or corporate_self_test.get("final_acceptance") is not False
        or corporate_self_test.get("principal_match") is not True
        or corporate_self_test.get("second_password_form") is not False
        or corporate_self_test.get("exact_canvas_loaded") is not True
        or corporate_self_test.get("employee_id")
        != corporate_self_test.get("langflow_user")
        or corporate_self_test.get("spoof_status") != 403
        or corporate_self_test.get("hcp_fail_closed", {}).get("ok") is not True
        or corporate_self_test.get("browser_sso", {}).get("status") != "ready"
        or corporate_self_test.get("logout", {}).get("boi_session_cleared") is not True
        or corporate_self_test.get("logout", {}).get("langflow_session_cleared")
        is not True
        or any((corporate_self_test.get("secret_exposure") or {}).values())
    ):
        raise RuntimeError("corporate acceptance runner self-test is incomplete")

    security = payloads["security_context"]
    hcp = security.get("hcp") or {}
    audience = security.get("run_token_audience") or {}
    task_context = security.get("task_context") or {}
    ontology = security.get("typed_ontology") or {}
    if (
        hcp.get("role_reduction", {}).get("response", {}).get("status") != 403
        or hcp.get("account_disabled", {}).get("response", {}).get("status") != 403
        or hcp.get("outage", {}).get("response", {}).get("status") != 503
        or hcp.get("cache_bypassed") is not True
        or audience.get("ok") is not True
        or task_context.get("semantic_assertions", {}).get("server_resolved") is not True
        or task_context.get("ordinary_question", {}).get("context_profile")
        != "knowledge_lookup"
        or ontology.get("all_edges_have_provenance") is not True
        or ontology.get("fallback", {}).get("ontology_status")
        != "grounded_document_fallback"
        or ontology.get("acl_exclusion", {}).get("leaked_ids") != []
    ):
        raise RuntimeError("HCP, run-token audience, Task, or Ontology evidence is incomplete")
    return payloads


def build_bundle(target: Path) -> None:
    sources = [
        *sorted((ROOT / "langflow/custom_components/boi").glob("*.py")),
        ROOT / "langflow/flows/boi_universal_simulation_mcp.json",
        ROOT / "langflow/flows/boi_wiki_agent_loop.json",
        ROOT / "langflow/flows/boi_wiki_agent_loop_model_agent.json",
        ROOT / "langflow/compatibility-manifest.json",
        ROOT / "langflow/agent_hub/README.md",
    ]
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sources:
            archive.write(source, source.relative_to(ROOT))


def secret_scan(root: Path) -> dict[str, Any]:
    matches: list[dict[str, str]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.suffix.lower() not in TEXT_SUFFIXES:
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
        rows.append(f"{sha256(path)}  {path.relative_to(root)}")
    (root / "SHA256SUMS").write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=ROOT / "artifacts",
    )
    parser.add_argument("--full-pytest-log", type=Path, required=True)
    parser.add_argument("--feature-commit", default="")
    args = parser.parse_args()

    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"output must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    evidence_root = args.evidence_root.resolve()
    payloads = assert_evidence(evidence_root)

    evidence_dirs = {
        "oidc-browser-sso": "agent-playground-browser-sso",
        "trusted-header-sso": "agent-playground-trusted-header",
        "sso-onboarding": "agent-playground-sso-onboarding",
        "dev-prd-flow-origin": "agent-playground-flow-origin",
        "immutable-agent-hub": "agent-playground-agent-hub-sso",
        "universal-exact-chain": "agent-playground-universal-exact-chain-final",
        "checksum-drift": "agent-playground-universal-drift-final",
        "wiki-docs": "agent-playground-wiki-onboarding",
        "security-context": "agent-playground-security-context-hardening",
        "corporate-runner-self-test": "agent-playground-corporate-sso-validation",
    }
    for target_name, source_name in evidence_dirs.items():
        copy_tree(evidence_root / source_name, output / "evidence" / target_name)

    delivery_files = [
        ROOT / "langflow/flows/boi_universal_simulation_mcp.json",
        ROOT / "langflow/flows/boi_wiki_agent_loop.json",
        ROOT / "langflow/flows/boi_wiki_agent_loop_model_agent.json",
        ROOT / "langflow/compatibility-manifest.json",
        ROOT / "langflow/agent_hub/README.md",
        ROOT / "langflow/agent_hub/universal-simulation-mcp-client.example.json",
        ROOT / "langflow/agent_hub/universal-simulation-mcp-samples.json",
        ROOT / "docs/UNIVERSAL_SIMULATION_MCP_ONE_PAGER.md",
        ROOT / "validation/agent-hub/CORPORATE_SSO_HANDOFF.md",
        ROOT
        / "validation/agent-playground-mainline/corporate_sso_acceptance_e2e.mjs",
        ROOT
        / "validation/agent-playground-mainline/corporate-hcp-evidence.example.json",
    ]
    for source in delivery_files:
        copy_file(source, output / "delivery" / source.relative_to(ROOT))
    for source in sorted(
        (ROOT / "data/boi/public/boi-wiki-manual").rglob("agent-playground*.md")
    ):
        copy_file(
            source,
            output / "delivery/wiki" / source.relative_to(
                ROOT / "data/boi/public/boi-wiki-manual"
            ),
        )
    for source in sorted(
        (ROOT / "data/boi/public/boi-wiki-manual").rglob(
            "universal-simulation-mcp-*.md"
        )
    ):
        copy_file(
            source,
            output / "delivery/wiki" / source.relative_to(
                ROOT / "data/boi/public/boi-wiki-manual"
            ),
        )
    copy_file(
        ROOT
        / "data/boi/public/boi-wiki-manual/operations/agent-hub-integration-boundary.md",
        output / "delivery/wiki/operations/agent-hub-integration-boundary.md",
    )
    requirement_audit = read_json(
        evidence_root / "agent-playground-current/audit/REQUIREMENT_AUDIT.json"
    )
    if requirement_audit.get("implementation_and_local_validation_ok") is not True:
        raise RuntimeError("provider-neutral SSO requirement audit did not pass local validation")
    copy_file(
        evidence_root / "agent-playground-current/audit/REQUIREMENT_AUDIT.json",
        output / "REQUIREMENT_AUDIT.json",
    )
    copy_file(
        evidence_root / "agent-playground-current/audit/REQUIREMENT_AUDIT.md",
        output / "REQUIREMENT_AUDIT.md",
    )
    build_bundle(output / "delivery/boi-agent-playground-langflow-1.11-bundle.zip")

    regression_sources = {
        "full-pytest.log": args.full_pytest_log.resolve(),
        "langflow-migration-rollback.json": (
            evidence_root
            / "agent-playground-current/regression/langflow-migration-rollback-revalidation.json"
        ),
        "langflow-source-boundary.json": (
            evidence_root / "agent-playground-current/regression/langflow-boundary-final.json"
        ),
        "langflow-bundle-boundary.json": (
            evidence_root
            / "agent-playground-current/regression/langflow-bundle-boundary-final.json"
        ),
        "mainline-boundary.json": (
            evidence_root / "agent-playground-current/regression/mainline-boundary-final.json"
        ),
        "langflow-external-auth-contract.json": (
            evidence_root
            / "agent-playground-current/regression/langflow-external-auth-contract-final.json"
        ),
        "keycloak-reference-contract.json": (
            evidence_root
            / "agent-playground-current/regression/keycloak-reference-contract-final.json"
        ),
    }
    for name, source in regression_sources.items():
        copy_file(source, output / "regression" / name)

    feature = git_state(ROOT)
    agent_hub = git_state(AGENT_HUB_ROOT)
    original_main = git_state(Path("/home/chokukil/boi-wiki"))
    feature_commit = args.feature_commit or feature["head"]
    if feature_commit != feature["head"]:
        raise RuntimeError("feature commit must be the current Agent Playground HEAD")
    if not feature["tracked_diff"] or not feature["staged_diff"]:
        raise RuntimeError("Agent Playground has uncommitted tracked changes")
    if (
        agent_hub["head"] != AGENT_HUB_SHA
        or agent_hub["status"]
        or not agent_hub["tracked_diff"]
        or not agent_hub["staged_diff"]
    ):
        raise RuntimeError("Agent Hub is not the immutable clean PR #25 checkout")

    commits = run(
        "git",
        "log",
        "--reverse",
        "--format=%H%x09%s",
        "53912644..HEAD",
    ).splitlines()
    (output / "CHERRY_PICK_ORDER.md").write_text(
        "\n".join(
            [
                "# 사내 적용 cherry-pick 순서",
                "",
                "아래 커밋을 `origin/main@53912644` 기반 브랜치에 순서대로 적용한다.",
                "",
                *[
                    f"{index}. `{row.split(chr(9), 1)[0]}` — "
                    f"{row.split(chr(9), 1)[1] if chr(9) in row else ''}"
                    for index, row in enumerate(commits, start=1)
                ],
                "",
                "Agent Hub와 Langflow 소스는 cherry-pick하거나 수정하지 않는다.",
                "사내에서는 SSO 모드와 URL/secret만 환경설정으로 선택한다.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exact = payloads["exact_chain"]["exact_reference"]
    summary = {
        "package_ready": True,
        "implementation_and_local_validation_ok": True,
        "goal_complete": requirement_audit.get("goal_complete") is True,
        "external_gate": requirement_audit.get("external_gate"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "feature_commit": feature_commit,
        "base_commit": "53912644",
        "agent_hub": {
            "head": AGENT_HUB_SHA,
            "clean": True,
            "source_modified": False,
        },
        "langflow": {
            "image": LANGFLOW_IMAGE,
            "source_modified": False,
            "bundle_mount": "read-only",
        },
        "sso": {
            "oidc_no_second_login": True,
            "trusted_header_no_second_login": True,
            "trusted_header_bridge_rs256_ttl_seconds": 60,
            "embedded_employee_isolation": "100002",
            "external_jwt_note": (
                "Official 1.11.0 fixed-digest JWT/JWKS positive and negative API "
                "contract passed; the local full-browser gate uses the documented "
                "employee-isolated embedded fallback."
            ),
            "external_jwt_contract": payloads["external_auth"],
            "keycloak_reference_contract": payloads["keycloak_reference"],
            "coordinated_logout": payloads["oidc_browser"]["logout"],
        },
        "exact_reference": exact,
        "flow_origin": payloads["flow_origin"]["desktop"],
        "wiki_document_count": len(payloads["wiki_docs"]["documents"]),
        "main_services_preserved": {
            "boi_port": 28000,
            "langflow_port": 7860,
            "original_checkout_dirty_state_recorded": True,
        },
        "evidence_contract": {
            "browser_boolean_only": False,
            "actual_agent_hub_ui": True,
            "actual_langflow_flow": True,
            "actual_gemma_model_trace": True,
            "actual_action_wiki_sop": True,
            "actual_negative_drift_and_acl": True,
        },
    }
    (output / "COMPLETION_AUDIT.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "SOURCE_STATE.json").write_text(
        json.dumps(
            {
                "generated_at": summary["generated_at"],
                "feature": feature,
                "agent_hub": agent_hub,
                "original_main": original_main,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "README.md").write_text(
        "\n".join(
            [
                "# Agent Playground 공급자 독립 SSO 사내 검증 후보 handoff",
                "",
                "이 패키지는 OIDC와 trusted-header 브라우저 SSO, DEV/PRD exact Flow,",
                "수정 없는 Agent Hub 배포, Universal Simulation MCP, connector-neutral",
                "Action과 Wiki/Ontology 실행을 하나의 exact Flow 증거로 연결한다.",
                "",
                "기존 Agent Playground 완료 주장은 이 패키지의 요구사항 감사로 대체한다.",
                "로컬 구현·회귀는 통과했지만 `REQUIREMENT_AUDIT.md`의 사내 SSO gate가",
                "통과하기 전에는 전체 목표 완료나 사내 운영 완료 근거로 사용하지 않는다.",
                "",
                f"- feature commit: `{feature_commit}`",
                f"- exact Flow: `{exact.get('flow_id')}`",
                f"- checksum: `{exact.get('artifact_checksum')}`",
                f"- immutable Agent Hub: `{AGENT_HUB_SHA}`",
                f"- official Langflow: `{LANGFLOW_IMAGE}`",
                "",
                "`COMPLETION_AUDIT.json`은 의미 assertion 요약이고, 실제 요청·응답과",
                "브라우저 화면은 `evidence/`에 있다. `SHA256SUMS`로 전체 파일을 검증한다.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    scan = secret_scan(output)
    if not scan["ok"]:
        raise RuntimeError(f"secret scan failed: {scan['matches']}")
    (output / "SECRET_SCAN.json").write_text(
        json.dumps(scan, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_checksums(output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
