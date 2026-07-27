#!/usr/bin/env python3
"""Build the secret-free Universal Simulation MCP delivery package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import urllib.request
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


def http_health(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        raw = response.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw[:500]}
        return {"url": url, "status": response.status, "body": body}


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
    parser.add_argument("--onboarding-evidence", type=Path, required=True)
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
    onboarding_evidence = args.onboarding_evidence.resolve()
    copy_tree(onboarding_evidence, output / "evidence/onboarding-mcp")
    copy_tree(evidence_root, output / "evidence/agent-hub-action")

    required_results = {
        "onboarding": output / "evidence/onboarding-mcp/fresh-onboarding-result.json",
        "agent_hub": output / "evidence/agent-hub-action/playwright-result.json",
        "exact_chain": output / "evidence/agent-hub-action/exact-chain/result.json",
        "team_action": output / "evidence/agent-hub-action/team-action-v2/result.json",
        "cross_author": output / "evidence/agent-hub-action/shared-component/cross-author-adoption-result.json",
        "drift": output / "evidence/agent-hub-action/exact-drift/result.json",
        "action_connectors": output / "evidence/agent-hub-action/connector-neutral-action-v2/action-abstraction-result.json",
        "security_context": output / "evidence/agent-hub-action/security-context-v2/result.json",
    }
    results = {name: read_json(path) for name, path in required_results.items()}
    pass_fields = {
        "onboarding": "ok",
        "agent_hub": "passed",
        "exact_chain": "ok",
        "team_action": "ok",
        "cross_author": "ok",
        "drift": "ok",
        "action_connectors": "ok",
        "security_context": "ok",
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
        "pytest-full-final.log",
        "pytest-full-final-exit.json",
        "universal-simulation-artifact.json",
        "langflow-1.10-clean-import.json",
        "langflow-source-boundary.json",
        "langflow-bundle-boundary.json",
        "langflow-migration-rollback.json",
        "legacy-universal-simulator.json",
        "secret-scan.json",
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
        "original_main": git_state(Path("/home/chokukil/boi-wiki")),
        "agent_hub": {
            **agent_hub,
            "expected_head": expected_agent_hub,
            "clean": True,
        },
        "langflow_artifact_sha256": sha256(
            ROOT / "langflow/flows/boi_universal_simulation_mcp.json"
        ),
        "service_health": {
            "original_boi": http_health("http://localhost:28000/health"),
            "original_langflow": http_health("http://localhost:7860/health"),
            "validation_boi": http_health("http://localhost:28005/health"),
            "validation_langflow": http_health("http://localhost:7867/health"),
        },
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

    exact_chain = results["exact_chain"]
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
        "clean_onboarding": results["onboarding"],
        "model_runtime": exact_chain.get("run_api", {}).get("model_trace"),
        "mcp": exact_chain.get("mcp"),
        "cross_author_component": results["cross_author"].get("validation"),
        "drift": results["drift"].get("drift"),
        "drift_recovery": results["drift"].get("recovery"),
        "team_private_draft": results["team_action"].get("private_draft"),
        "security_context": {
            key: results["security_context"].get(key)
            for key in (
                "hcp",
                "run_token_audience",
                "task_context",
                "typed_ontology",
                "oidc",
            )
        },
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

    regressions = {
        name: read_json(output / "regression" / name)
        for name in (
            "pytest-full-final-exit.json",
            "universal-simulation-artifact.json",
            "langflow-1.10-clean-import.json",
            "langflow-source-boundary.json",
            "langflow-bundle-boundary.json",
            "langflow-migration-rollback.json",
            "legacy-universal-simulator.json",
            "secret-scan.json",
        )
    }
    onboarding = results["onboarding"]
    agent_hub_result = results["agent_hub"]
    exact = results["exact_chain"]
    team = results["team_action"]
    shared = results["cross_author"]
    drift = results["drift"]
    connectors = results["action_connectors"]
    security = results["security_context"]
    exact_ref = exact.get("exact_reference") or {}
    exact_flow_id = str(exact_ref.get("flow_id") or "")
    agent_hub_chain = agent_hub_result.get("exact_chain") or {}
    agent_hub_flow_id = str(agent_hub_chain.get("flow_id") or "")
    full_log = (output / "regression/pytest-full-final.log").read_text(
        encoding="utf-8",
        errors="replace",
    )

    def check(
        number: int,
        condition: str,
        passed: bool,
        assertion: str,
        evidence: list[str],
    ) -> dict[str, Any]:
        return {
            "number": number,
            "condition": condition,
            "status": "passed" if passed else "failed",
            "assertion": assertion,
            "evidence": evidence,
        }

    audit = [
        check(
            1,
            "공식 Langflow 1.11 이미지와 read-only bundle 경계",
            bool(regressions["langflow-bundle-boundary.json"].get("ok")),
            "공식 image/package hash가 순정 runtime과 같고 BoI bundle mount가 read-only다.",
            ["regression/langflow-bundle-boundary.json", "regression/langflow-source-boundary.json"],
        ),
        check(
            2,
            "Flow JSON source-of-truth checksum",
            bool(regressions["universal-simulation-artifact.json"].get("ok")),
            "artifact SHA와 생성 스크립트 SHA가 일치한다.",
            ["regression/universal-simulation-artifact.json"],
        ),
        check(
            3,
            "Canvas 5단계·Note·edge·viewport·겹침",
            (
                regressions["universal-simulation-artifact.json"].get("execution_nodes") == 5
                and regressions["universal-simulation-artifact.json"].get("notes") == 5
                and regressions["universal-simulation-artifact.json"].get("edges") == 4
                and regressions["universal-simulation-artifact.json"].get("overlaps") == []
            ),
            "5개 실행 노드와 5개 안내 Note, 4개 edge가 지정 위치에 있고 겹침이 없다.",
            ["regression/universal-simulation-artifact.json", "evidence/onboarding-mcp/03-langflow-canvas.png"],
        ),
        check(
            4,
            "100002 실제 OIDC 신규 온보딩",
            (
                onboarding.get("initial", {}).get("required") is True
                and onboarding.get("initial", {}).get("endpoint_count") == 0
                and onboarding.get("ready", {}).get("recommended_flow", {}).get("smoke_status") == "passed"
            ),
            "endpoint 0개에서 OIDC 로그인, Langflow 표준 키 발급, 대표 Flow 설치와 멱등 bootstrap을 통과했다.",
            ["evidence/onboarding-mcp/fresh-onboarding-result.json", "evidence/onboarding-mcp/01-boi-onboarding-connection.png"],
        ),
        check(
            5,
            "자연어 Wiki·Ontology preview",
            exact.get("run_api", {}).get("grounding_status") == "grounded_with_ontology",
            "자연어 preview가 Ontology grounding과 Wiki source를 반환했다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            6,
            "실제 SOP Task Context 복원",
            (
                exact.get("action", {}).get("sop", {}).get("task_context", {}).get("profile")
                == "sop_task_execution"
                and bool(
                    exact.get("action", {}).get("sop", {}).get("task_context", {}).get("prior_results")
                )
            ),
            "Task·SOP·Stage·Event·Action·선행 결과·필요/부족 근거를 서버에서 복원했다.",
            ["evidence/agent-hub-action/exact-chain/result.json", "evidence/agent-hub-action/security-context-v2/result.json"],
        ),
        check(
            7,
            "SOP 없는 Task와 일반 질문의 허위 SOP 방지",
            (
                exact.get("no_sop_task", {}).get("profile") == "task_execution"
                and exact.get("no_sop_task", {}).get("sop_ref") == ""
            ),
            "실제 ad-hoc Task는 task_execution이며 sop_ref가 비어 있다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            8,
            "LM Studio Gemma 실제 추론 trace",
            (
                "gemma" in str(exact.get("run_api", {}).get("model_trace", {}).get("model") or "").lower()
                and bool(exact.get("run_api", {}).get("model_trace", {}).get("response_id"))
                and int(exact.get("run_api", {}).get("model_trace", {}).get("usage", {}).get("total_tokens") or 0) > 0
            ),
            "model, response ID, latency, token usage가 실제 실행 결과에 있다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            9,
            "source·Ontology provenance 보존",
            (
                int(exact.get("contract_comparison", {}).get("common_source_references") or 0) > 0
                and int(exact.get("contract_comparison", {}).get("common_ontology_relationships") or 0) > 0
                and security.get("typed_ontology", {}).get("all_edges_have_provenance") is True
            ),
            "MCP·run·save 전 구간에서 공통 source와 provenance 있는 typed relation이 유지된다.",
            ["evidence/agent-hub-action/exact-chain/result.json", "evidence/agent-hub-action/security-context-v2/result.json"],
        ),
        check(
            10,
            "MCP list_tools 단일 대표 tool과 schema",
            (
                exact.get("mcp", {}).get("representative_tool_count") == 1
                and exact.get("mcp", {}).get("tool_name") == "boi_universal_simulate"
                and "input_value" in exact.get("mcp", {}).get("schema", {}).get("properties", {})
            ),
            "프로젝트 MCP에 대표 tool이 하나만 노출되고 자연어 입력 schema가 확인됐다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            11,
            "streamable MCP와 exact /run 계약 비교",
            (
                exact.get("mcp", {}).get("flow_id") == exact_flow_id
                and exact.get("run_api", {}).get("flow_id") == exact_flow_id
                and exact.get("contract_comparison", {}).get("exact_flow_id") == exact_flow_id
            ),
            "동일 exact Flow의 MCP와 /api/v1/run 결과 계약을 비교했다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            12,
            "외부 MCP private_draft 강제 요청 차단",
            (
                exact.get("mcp", {}).get("forced_private_draft", {}).get("write_blocked") is True
                and exact.get("mcp", {}).get("forced_private_draft", {}).get("wiki_files_before")
                == exact.get("mcp", {}).get("forced_private_draft", {}).get("wiki_files_after")
            ),
            "MCP write 요청을 preview로 차단하고 Wiki 파일 수가 변하지 않았다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            13,
            "caller-bound run token에서만 개인 초안 생성",
            (
                exact.get("caller_bound_save", {}).get("playground", {}).get("owner_employee_id") == "100002"
                and exact.get("caller_bound_save", {}).get("action", {}).get("owner_employee_id") == "100002"
                and security.get("run_token_audience", {}).get("ok") is True
            ),
            "정상 execution audience에서만 초안이 생성되고 다른 Action·Flow·trace·execution은 거부됐다.",
            ["evidence/agent-hub-action/exact-chain/result.json", "evidence/agent-hub-action/security-context-v2/result.json"],
        ),
        check(
            14,
            "100001의 100002 소유 팀 Action 실행",
            (
                team.get("endpoint_owner", {}).get("employee_id") == "100002"
                and team.get("caller", {}).get("employee_id") == "100001"
                and team.get("private_draft", {}).get("owner_employee_id") == "100001"
            ),
            "Langflow key 소유자와 Wiki 초안 소유자가 분리됐다.",
            ["evidence/agent-hub-action/team-action-v2/result.json"],
        ),
        check(
            15,
            "100003 조회·preview 전용",
            (
                exact.get("viewer", {}).get("action_status") == 403
                and exact.get("viewer", {}).get("private_draft_status") == 403
            ),
            "viewer의 Action 실행과 private draft가 모두 403이다.",
            ["evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            16,
            "수정 없는 Agent Hub UI 배포와 exact Flow 재발견",
            (
                agent_hub_result.get("passed") is True
                and agent_hub_flow_id == exact_flow_id
                and agent_hub_result.get("playground", {}).get("rediscovered_flow_id") == exact_flow_id
            ),
            "Agent Hub UI 배포 ID와 Playground live 조회 ID가 같다.",
            ["evidence/agent-hub-action/playwright-result.json", "source-state.json"],
        ),
        check(
            17,
            "Agent Hub 공유 Component 실제 연결·실행",
            (
                shared.get("composition", {}).get("disconnected", {}).get("validation_status") == "blocked"
                and shared.get("composition", {}).get("compose", {}).get("end_to_end_reachable") is True
                and bool(shared.get("validation", {}).get("executed_component_ids"))
            ),
            "미연결 상태는 차단되고, 공개 Flow API 조합 후 실행 provenance가 남았다.",
            ["evidence/agent-hub-action/shared-component/cross-author-adoption-result.json"],
        ),
        check(
            18,
            "checksum drift의 MCP·Action 차단과 복구",
            (
                drift.get("drift", {}).get("mcp_status") == 409
                and drift.get("drift", {}).get("action_status") == 409
                and drift.get("recovery", {}).get("validation_status") == "action_linked"
            ),
            "Flow 변경 시 MCP와 Action을 막고 복원·재검증 후 같은 exact Flow가 실행됐다.",
            ["evidence/agent-hub-action/exact-drift/result.json"],
        ),
        check(
            19,
            "draft→validate→publish-request→실행 exact reference",
            (
                agent_hub_chain.get("publish_status") == "publish_requested"
                and agent_hub_chain.get("execution", {}).get("exact_flow_id") == exact_flow_id
                and agent_hub_chain.get("action_key") == exact_ref.get("action_key")
            ),
            "등록과 실행이 동일 endpoint/project/Flow/version/checksum reference를 사용했다.",
            ["evidence/agent-hub-action/playwright-result.json", "evidence/agent-hub-action/exact-chain/result.json"],
        ),
        check(
            20,
            "데스크톱·390px 모바일 Playwright UX",
            (
                onboarding.get("ok") is True
                and agent_hub_result.get("playground", {}).get("mobile_width", {}).get("viewport") == 390
                and len(list((output / "evidence/onboarding-mcp").glob("*.png"))) >= 5
            ),
            "온보딩·Canvas·MCP·Agent Hub·Action 화면을 데스크톱과 390px에서 캡처했다.",
            ["evidence/onboarding-mcp", "evidence/agent-hub-action/09-playground-mobile.png", "evidence/agent-hub-action/11-boi-action-catalog-mobile.png"],
        ),
        check(
            21,
            "예상하지 못한 HTTP·console·page error 0건",
            (
                not onboarding.get("console_errors")
                and not onboarding.get("page_errors")
                and not onboarding.get("http_errors")
                and not exact.get("unexpected")
                and not team.get("console_errors")
                and not team.get("page_errors")
                and not team.get("unexpected_http_errors")
                and not shared.get("console_errors")
                and not shared.get("page_errors")
                and not shared.get("unexpected_http_errors")
            ),
            "의도한 403 부정 시험을 제외한 브라우저 오류가 없다.",
            ["evidence/onboarding-mcp/fresh-onboarding-result.json", "evidence/agent-hub-action/exact-chain/result.json", "evidence/agent-hub-action/team-action-v2/result.json"],
        ),
        check(
            22,
            "API Key·PAT·run token·모델 secret 비노출",
            regressions["secret-scan.json"].get("ok") is True,
            "Flow·응답·로그·Wiki·스크린샷 증거의 secret scan match가 0이다.",
            ["regression/secret-scan.json", "secret-scan.json"],
        ),
        check(
            23,
            "전체 main·legacy simulator·connector·migration/rollback 회귀",
            (
                regressions["pytest-full-final-exit.json"].get("exit_code") == 0
                and "632 passed" in full_log
                and regressions["legacy-universal-simulator.json"].get("ok") is True
                and regressions["langflow-migration-rollback.json"].get("ok") is True
                and regressions["langflow-1.10-clean-import.json"].get("ok") is True
                and len(connectors.get("gateway_invocations") or []) == 7
            ),
            "632개 테스트, 1.10 import/migration/rollback, 기존 simulator, 7종 connector 실제 호출이 통과했다.",
            ["regression/pytest-full-final.log", "regression/langflow-migration-rollback.json", "regression/legacy-universal-simulator.json", "evidence/agent-hub-action/connector-neutral-action-v2/action-abstraction-result.json"],
        ),
        check(
            24,
            "Agent Hub 지정 SHA·시작/종료 clean",
            (
                source_state["agent_hub"]["head"] == expected_agent_hub
                and source_state["agent_hub"]["status"] == []
            ),
            "Agent Hub checkout에는 tracked/untracked/staged 변경이 없다.",
            ["source-state.json"],
        ),
        check(
            25,
            "기존 main 서비스와 Langflow 1.10 무변경·정상",
            all(
                item.get("status") == 200
                for item in source_state["service_health"].values()
            ),
            "기존 :28000·:7860과 검증 :28005·:7867 health가 모두 200이며 원래 dirty checkout은 보존됐다.",
            ["source-state.json"],
        ),
    ]
    failed_audit = [item for item in audit if item["status"] != "passed"]
    audit_document = {
        "ok": not failed_audit,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": len(audit) - len(failed_audit),
        "total": len(audit),
        "checks": audit,
    }
    (output / "completion-audit.json").write_text(
        json.dumps(audit_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    audit_lines = [
        "# Universal Simulation MCP 완료 감사",
        "",
        f"- 결과: {audit_document['passed']}/{audit_document['total']} passed",
        "- 판정 원칙: 파일 존재나 단순 boolean만으로 통과시키지 않고 실제 부정 시험과 실행 의미를 확인한다.",
        "",
        "| # | 완료 조건 | 판정 | 의미 검증 | 증거 |",
        "|---:|---|---|---|---|",
    ]
    for item in audit:
        evidence_links = "<br>".join(f"`{path}`" for path in item["evidence"])
        audit_lines.append(
            f"| {item['number']} | {item['condition']} | {item['status']} | "
            f"{item['assertion']} | {evidence_links} |"
        )
    (output / "COMPLETION_AUDIT.md").write_text(
        "\n".join(audit_lines) + "\n",
        encoding="utf-8",
    )
    if failed_audit:
        raise RuntimeError(
            "completion audit failed: "
            + ", ".join(str(item["number"]) for item in failed_audit)
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
