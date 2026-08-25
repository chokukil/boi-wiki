#!/usr/bin/env python3
"""Build a hash-bound implementation verification report without activating knowledge."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
GATE_RE = re.compile(r"^- (G[0-7]) \| ([A-Z_]+) \| (.+)$", re.MULTILINE)
REQUIRED_QUALIFICATION_GATES = tuple(f"G{i}" for i in range(5))
ALL_QUALIFICATION_GATES = tuple(f"G{i}" for i in range(8))
MANDATORY_BROWSER_CHECK_IDS = frozenset(
    {
        "page_loaded",
        "candidate_not_operational",
        "nav_order",
        "inactive_release_has_no_red",
        "deterministic_aliases_visible",
        "manual_claim_editor_visible",
        "qwen_is_separate_experimental_action",
        "default_used_deterministic_non_qwen_path",
        "manual_claim_confirmed_without_llm_or_verdict",
        "ascii_alias_token_boundary",
        "qwen_failure_matrix_has_no_red",
        "invalid_claim_matrix_has_no_red",
        "external_clients_submit_same_claim",
        "red_gate_requires_active_rule_conditions_and_exact_evidence",
        "prohibited_ui_absent",
        "actions_separated_and_focusable",
        "desktop_no_overflow",
        "mobile_single_column",
        "wiki_selection_handoff",
        "wiki_local_revision_preserves_lineage",
        "console_clean",
    }
)
EXPECTED_JUNIT_SUITE_IDS = {
    "science_tests": "science-tests",
    "mcp_tests": "science-mcp",
    "full_regression": "full-regression",
}
EXPECTED_JUNIT_PYTEST_ARGS = {
    "science_tests": ["tests", "-k", "science and not mcp"],
    "mcp_tests": ["tests/test_science_mcp.py"],
    "full_regression": ["tests"],
}
ALLOWED_FULL_REGRESSION_SKIPS = frozenset(
    {
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_internal_success_skips_external_probe",
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_network_failure_falls_back_and_apply_verify_rollback_are_hash_bound",
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_internal_auth_failure_never_probes_external",
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_offline_existing_keeps_origin_and_blocks_update",
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_origin_drift_invalidates_approved_plan",
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_candidate_mirror_may_advance_when_it_contains_current_stable",
        "tests.test_repository_source_and_mcp.RepositorySourceContractTests::test_diverged_mirror_history_blocks_switch",
        "tests.test_repository_source_and_mcp.McpConnectionContractTests::test_codex_preview_apply_and_rollback_preserve_unrelated_config_and_token",
        "tests.test_repository_source_and_mcp.McpConnectionContractTests::test_verify_runs_initialize_and_tools_list_without_private_content",
    }
)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path.resolve())


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at", required=True)
    parser.add_argument("--science-test-summary", type=Path)
    parser.add_argument("--mcp-test-summary", type=Path)
    parser.add_argument("--full-regression-summary", type=Path)
    parser.add_argument("--browser-capture-manifest", type=Path)
    parser.add_argument("--qualification-result", type=Path)
    parser.add_argument("--independent-review", type=Path)
    return parser.parse_args()


def _git_state(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        status_bytes = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo_root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return {
            "commit": None,
            "dirty": True,
            "status_digest": sha256_bytes(b"git-state-unavailable"),
        }, ["git:state_unavailable"]
    state = {
        "commit": commit,
        "dirty": bool(status_bytes),
        "status_digest": sha256_bytes(status_bytes),
    }
    return state, ["git:dirty_worktree"] if status_bytes else []


def _base_evidence(
    path: Path | None, repo_root: Path
) -> tuple[dict[str, Any], bytes | None]:
    if path is None or not path.is_file():
        return {
            "available": False,
            "path": None if path is None else display_path(path, repo_root),
        }, None
    data = path.read_bytes()
    return {
        "available": True,
        "path": display_path(path, repo_root),
        "sha256": sha256_bytes(data),
    }, data


def _nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean is not an integer count")
    number = int(value)
    if number < 0:
        raise ValueError("negative count")
    return number


def _test_suite_contract(
    repo_root: Path,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    path = repo_root / "config/science-verifier-test-suites.json"
    record, data = _base_evidence(path, repo_root)
    if data is None:
        return record, {}, ["test_suite_contract:missing"]
    try:
        payload = json.loads(data)
        if not isinstance(payload, dict) or set(payload) != {
            "schema_version",
            "identity_format",
            "suites",
        }:
            raise ValueError("suite contract must be a closed object")
        if payload["schema_version"] != "science-test-suite-contract/0.1":
            raise ValueError("unsupported suite contract schema")
        if payload["identity_format"] != "pytest-junit-classname::name":
            raise ValueError("unsupported testcase identity format")
        suites = payload["suites"]
        if not isinstance(suites, dict) or set(suites) != set(EXPECTED_JUNIT_SUITE_IDS):
            raise ValueError("exact suite set is required")
        normalized: dict[str, dict[str, Any]] = {}
        for name in EXPECTED_JUNIT_SUITE_IDS:
            suite = suites[name]
            if not isinstance(suite, dict) or set(suite) != {
                "suite_id",
                "pytest_args",
                "collected",
                "testcase_identity_digest",
            }:
                raise ValueError("suite definition must be closed")
            if isinstance(suite["collected"], bool) or not isinstance(
                suite["collected"], int
            ):
                raise ValueError("suite collected count must be an integer")
            collected = suite["collected"]
            digest = suite["testcase_identity_digest"]
            if collected <= 0:
                raise ValueError("suite contract cannot be empty")
            if suite["suite_id"] != EXPECTED_JUNIT_SUITE_IDS[name]:
                raise ValueError("suite ID does not match the fixed report input")
            if suite["pytest_args"] != EXPECTED_JUNIT_PYTEST_ARGS[name]:
                raise ValueError("pytest collect-only arguments do not match")
            if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
                raise ValueError("invalid testcase identity digest")
            normalized[name] = {
                "suite_id": suite["suite_id"],
                "pytest_args": list(suite["pytest_args"]),
                "collected": collected,
                "testcase_identity_digest": digest,
            }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        record.update({"valid": False, "passed": False})
        return record, {}, ["test_suite_contract:invalid"]
    record.update(
        {
            "valid": True,
            "passed": True,
            "schema_version": payload["schema_version"],
            "identity_format": payload["identity_format"],
            "suites": normalized,
        }
    )
    return record, normalized, []


def _junit_evidence(
    name: str,
    path: Path | None,
    repo_root: Path,
    current_commit: str | None,
    suite_contract: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[str]]:
    record, data = _base_evidence(path, repo_root)
    if data is None:
        return record, [f"{name}:missing"]
    try:
        root = ET.fromstring(data)
        if root.tag not in {"testsuite", "testsuites"}:
            raise ValueError("not a JUnit root")
        if root.tag == "testsuites" and root.get("tests") is None:
            suites = root.findall("./testsuite")
            counts = {
                key: sum(_nonnegative_int(suite.get(key, "0")) for suite in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
        else:
            counts = {
                key: _nonnegative_int(root.get(key, "0"))
                for key in ("tests", "failures", "errors", "skipped")
            }
        if counts["failures"] + counts["errors"] + counts["skipped"] > counts["tests"]:
            raise ValueError("JUnit result counts are inconsistent")
        commits = {
            prop.get("value", "")
            for prop in root.findall(".//property[@name='git_commit']")
            if prop.get("value")
        }
        if len(commits) != 1:
            raise ValueError("exactly one git_commit property is required")
        evidence_commit = commits.pop()
        suite_ids = {
            prop.get("value", "")
            for prop in root.findall(".//property[@name='suite_id']")
            if prop.get("value")
        }
        if len(suite_ids) != 1:
            raise ValueError("exactly one suite_id property is required")
        suite_id = suite_ids.pop()
        testcase_nodes = root.findall(".//testcase")
        testcase_identities: list[str] = []
        skipped_cases: set[str] = set()
        for case in testcase_nodes:
            classname = case.get("classname")
            case_name = case.get("name")
            if not isinstance(classname, str) or not classname:
                raise ValueError("every testcase needs a classname")
            if not isinstance(case_name, str) or not case_name:
                raise ValueError("every testcase needs a name")
            identity = f"{classname}::{case_name}"
            testcase_identities.append(identity)
            if case.find("skipped") is not None:
                skipped_cases.add(identity)
        if len(testcase_identities) != len(set(testcase_identities)):
            raise ValueError("testcase identities must be unique")
        if len(testcase_identities) != counts["tests"]:
            raise ValueError("declared test count must equal testcase node count")
        if len(skipped_cases) != counts["skipped"]:
            raise ValueError("every skipped test needs an identifiable testcase")
        testcase_identity_digest = canonical_digest(sorted(testcase_identities))
    except (ET.ParseError, TypeError, ValueError):
        record.update({"format": "junit-xml", "valid": False})
        return record, [f"{name}:invalid"]

    expected_suite_id = (
        suite_contract["suite_id"] if suite_contract else EXPECTED_JUNIT_SUITE_IDS[name]
    )
    expected_count = suite_contract["collected"] if suite_contract else None
    expected_identity_digest = (
        suite_contract["testcase_identity_digest"] if suite_contract else None
    )
    count_matches = counts["tests"] == expected_count
    identity_digest_matches = testcase_identity_digest == expected_identity_digest
    executed = counts["tests"] - counts["skipped"]
    allowed_skips = (
        ALLOWED_FULL_REGRESSION_SKIPS if name == "full_regression" else frozenset()
    )
    unexpected_skips = skipped_cases - allowed_skips
    record.update(
        {
            "format": "junit-xml",
            "valid": True,
            **counts,
            "git_commit": evidence_commit,
            "suite_id": suite_id,
            "testcase_count": len(testcase_identities),
            "testcase_identity_digest": testcase_identity_digest,
            "contract_collected": expected_count,
            "contract_testcase_identity_digest": expected_identity_digest,
            "executed": executed,
            "passed": counts["tests"] > 0
            and counts["failures"] == 0
            and counts["errors"] == 0
            and suite_contract is not None
            and suite_id == expected_suite_id
            and count_matches
            and identity_digest_matches
            and executed > 0
            and not unexpected_skips,
            "skip_policy": "none"
            if name != "full_regression"
            else "powershell-wsl-exact-allowlist/0.1",
            "skipped_cases": sorted(skipped_cases),
            "unexpected_skipped_cases": sorted(unexpected_skips),
        }
    )
    failures: list[str] = []
    if counts["tests"] == 0:
        failures.append(f"{name}:zero_tests")
    if counts["failures"] or counts["errors"]:
        failures.append(f"{name}:test_failures")
    if suite_contract is None:
        failures.append(f"{name}:suite_contract_unavailable")
    if suite_id != expected_suite_id:
        failures.append(f"{name}:suite_id_mismatch")
    if not count_matches:
        failures.append(f"{name}:testcase_count_mismatch")
    if not identity_digest_matches:
        failures.append(f"{name}:testcase_identity_digest_mismatch")
    if executed <= 0:
        failures.append(f"{name}:no_executed_tests")
    if unexpected_skips:
        failures.append(f"{name}:unexpected_skipped_tests")
    if evidence_commit != current_commit:
        failures.append(f"{name}:git_commit_mismatch")
    return record, failures


def _browser_evidence(
    path: Path | None, repo_root: Path, current_commit: str | None
) -> tuple[dict[str, Any], list[str]]:
    record, data = _base_evidence(path, repo_root)
    if data is None:
        return record, ["browser:missing"]
    try:
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("manifest must be an object")
        if payload.get("schema_version") != "science-browser-capture-manifest/0.1":
            raise ValueError("unsupported schema")
        commit = payload.get("git_commit")
        if not isinstance(commit, str) or not commit:
            raise ValueError("git commit is required")
        checks = payload.get("checks")
        captures = payload.get("captures")
        if not isinstance(checks, list) or not checks:
            raise ValueError("checks are required")
        if not isinstance(captures, list) or not captures:
            raise ValueError("captures are required")
        check_ids: set[str] = set()
        checks_passed = True
        for check in checks:
            if not isinstance(check, dict):
                raise ValueError("invalid check")
            check_id = check.get("check_id")
            if not isinstance(check_id, str) or not check_id or check_id in check_ids:
                raise ValueError("check IDs must be unique")
            check_ids.add(check_id)
            checks_passed = checks_passed and check.get("status") == "passed"
        mandatory_checks_match = check_ids == MANDATORY_BROWSER_CHECK_IDS
        assert path is not None
        manifest_root = path.resolve().parent
        capture_records: list[dict[str, str]] = []
        capture_digests_match = True
        for capture in captures:
            if not isinstance(capture, dict):
                raise ValueError("invalid capture")
            relative = capture.get("path")
            expected = capture.get("sha256")
            if (
                not isinstance(relative, str)
                or not relative
                or not isinstance(expected, str)
            ):
                raise ValueError("capture path and digest are required")
            capture_path = (manifest_root / relative).resolve()
            if (
                capture_path != manifest_root
                and manifest_root not in capture_path.parents
            ):
                raise ValueError("capture escapes manifest directory")
            if not capture_path.is_file() or not DIGEST_RE.fullmatch(expected):
                capture_digests_match = False
                actual = None
            else:
                actual = sha256_bytes(capture_path.read_bytes())
                capture_digests_match = capture_digests_match and actual == expected
            capture_records.append(
                {"path": relative, "sha256": expected, "actual_sha256": actual}
            )
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        record.update({"valid": False})
        return record, ["browser:invalid"]

    record.update(
        {
            "valid": True,
            "git_commit": commit,
            "checks": len(checks),
            "captures": len(captures),
            "check_results": checks,
            "mandatory_check_ids": sorted(MANDATORY_BROWSER_CHECK_IDS),
            "missing_check_ids": sorted(MANDATORY_BROWSER_CHECK_IDS - check_ids),
            "unexpected_check_ids": sorted(check_ids - MANDATORY_BROWSER_CHECK_IDS),
            "capture_files": capture_records,
            "passed": checks_passed
            and mandatory_checks_match
            and capture_digests_match
            and commit == current_commit,
        }
    )
    failures: list[str] = []
    if commit != current_commit:
        failures.append("browser:git_commit_mismatch")
    if not checks_passed:
        failures.append("browser:failed_checks")
    if not mandatory_checks_match:
        failures.append("browser:mandatory_checks_mismatch")
    if not capture_digests_match:
        failures.append("browser:capture_digest_mismatch")
    return record, failures


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        raise ValueError("JSON frontmatter required")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    value = json.loads(text[4:end])
    if not isinstance(value, dict):
        raise ValueError("frontmatter must be an object")
    return value


def _qualification_evidence(
    path: Path | None, repo_root: Path
) -> tuple[dict[str, Any], list[str]]:
    record, data = _base_evidence(path, repo_root)
    if data is None:
        return record, ["qualification:missing"]
    try:
        text = data.decode("utf-8")
        metadata = _frontmatter(text)
        science = metadata.get("science_qualification")
        if not isinstance(science, dict):
            raise ValueError("science_qualification is required")
        release_id = science.get("release_id")
        release_digest = science.get("release_digest")
        result_digest = science.get(
            "qualification_result_digest", science.get("result_digest")
        )
        lifecycle = science.get("lifecycle")
        activation_eligible = science.get("activation_eligible")
        public_case_count = _nonnegative_int(science.get("public_case_count"))
        if not isinstance(release_id, str) or not release_id:
            raise ValueError("release ID is required")
        if not isinstance(release_digest, str) or not DIGEST_RE.fullmatch(
            release_digest
        ):
            raise ValueError("invalid release digest")
        if not isinstance(result_digest, str) or not DIGEST_RE.fullmatch(result_digest):
            raise ValueError("invalid result digest")
        if lifecycle != "release_candidate" or activation_eligible is not False:
            raise ValueError("qualification must not activate a release")
        if public_case_count == 0:
            raise ValueError("qualification needs cases")
        gate_matches = GATE_RE.findall(text)
        gates: dict[str, dict[str, str]] = {}
        for gate, status, detail in gate_matches:
            if gate in gates:
                raise ValueError("duplicate gate")
            gates[gate] = {"status": status, "detail": detail}
        if set(gates) != set(ALL_QUALIFICATION_GATES):
            raise ValueError("all qualification gates are required")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        record.update({"valid": False})
        return record, ["qualification:invalid"]

    record.update(
        {
            "valid": True,
            "release_id": release_id,
            "release_digest": release_digest,
            "qualification_result_digest": result_digest,
            "lifecycle": lifecycle,
            "activation_eligible": activation_eligible,
            "public_case_count": public_case_count,
            "gates": gates,
            "passed": all(
                gates[gate]["status"] == "PASS" for gate in REQUIRED_QUALIFICATION_GATES
            ),
        }
    )
    failures = [
        f"qualification:{gate}_not_passed"
        for gate in REQUIRED_QUALIFICATION_GATES
        if gates[gate]["status"] != "PASS"
    ]
    return record, failures


def _review_evidence(
    path: Path | None, repo_root: Path, current_commit: str | None
) -> tuple[dict[str, Any], list[str]]:
    record, data = _base_evidence(path, repo_root)
    if data is None:
        return record, ["independent_review:missing"]
    try:
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("review must be an object")
        if payload.get("schema_version") != "science-independent-review/0.1":
            raise ValueError("unsupported schema")
        reviewed_commit = payload.get("reviewed_git_commit")
        status = payload.get("status")
        findings = payload.get("findings")
        if not isinstance(reviewed_commit, str) or not reviewed_commit:
            raise ValueError("reviewed commit is required")
        if not isinstance(status, str):
            raise ValueError("review status is required")
        if not isinstance(findings, dict) or set(findings) != {
            "critical",
            "important",
            "advisory",
        }:
            raise ValueError("finding counts are required")
        normalized_findings = {
            key: _nonnegative_int(findings[key])
            for key in ("critical", "important", "advisory")
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        record.update({"valid": False})
        return record, ["independent_review:invalid"]

    record.update(
        {
            "valid": True,
            "reviewed_git_commit": reviewed_commit,
            "status": status,
            "findings": normalized_findings,
            "passed": status == "passed"
            and normalized_findings["critical"] == 0
            and normalized_findings["important"] == 0
            and reviewed_commit == current_commit,
        }
    )
    failures: list[str] = []
    if reviewed_commit != current_commit:
        failures.append("independent_review:git_commit_mismatch")
    if status != "passed":
        failures.append("independent_review:not_passed")
    if normalized_findings["critical"]:
        failures.append("independent_review:critical_findings")
    if normalized_findings["important"]:
        failures.append("independent_review:important_findings")
    return record, failures


def _knowledge_counts(repo_root: Path, public_case_count: int | None) -> dict[str, int]:
    root = repo_root / "data/boi/public/science"
    return {
        "knowledge": len(list((root / "knowledge").glob("*/sci-*-*.md"))),
        "evidence": len(
            [
                path
                for path in (root / "evidence").glob("*/*.md")
                if path.name != "index.md"
            ]
        ),
        "rules": len(list((root / "rules").glob("*/r-*-*.md"))),
        "packs": len(list((root / "packs").glob("*.md"))),
        "ontology_bindings": len(list((root / "ontology-bindings").glob("*/*.md"))),
        "qualification_case_families": len(
            list((root / "qualification/cases").glob("*/q-*-*.md"))
        ),
        "public_cases": public_case_count or 0,
    }


def _status_for(record: dict[str, Any]) -> str:
    return "VERIFIED" if record.get("passed") is True else "UNVERIFIED"


def _markdown(record: dict[str, Any]) -> str:
    evidence = record["evidence"]
    qualification = evidence["qualification"]
    gates = qualification.get("gates", {})
    gate_rows = (
        "\n".join(
            f"| {gate} | {entry['status']} | {entry['detail']} |"
            for gate, entry in sorted(gates.items())
        )
        or "| - | UNVERIFIED | 유효한 qualification 결과 없음 |"
    )
    source_rows: list[str] = []
    for key, label in (
        ("test_suite_contract", "Tracked pytest suite contract"),
        ("science_tests", "Science 회귀 JUnit"),
        ("mcp_tests", "MCP 계약 JUnit"),
        ("full_regression", "전체 저장소 회귀 JUnit"),
        ("browser", "브라우저 캡처 manifest"),
        ("qualification", "Candidate qualification"),
        ("independent_review", "독립 코드 리뷰"),
    ):
        item = evidence[key]
        if key == "test_suite_contract":
            result = f"schema={item.get('schema_version', 'unknown')}, suites={len(item.get('suites', {}))}"
        elif key.endswith("tests") or key == "full_regression":
            result = f"tests={item.get('tests', 0)}, failures={item.get('failures', 0)}, errors={item.get('errors', 0)}, skipped={item.get('skipped', 0)}"
        elif key == "browser":
            result = (
                f"checks={item.get('checks', 0)}, captures={item.get('captures', 0)}"
            )
        elif key == "qualification":
            result = f"cases={item.get('public_case_count', 0)}, lifecycle={item.get('lifecycle', 'unknown')}"
        else:
            result = f"status={item.get('status', 'unknown')}, findings={item.get('findings', {})}"
        source_rows.append(
            f"| {label} | {_status_for(item)} | {result} | `{item.get('sha256', 'missing')}` |"
        )
    failures = (
        "\n".join(f"- `{reason}`" for reason in record["failure_reasons"]) or "- 없음"
    )
    counts = record["counts"]
    return f"""# Science Verifier 구현 검증 보고서

> **구현 상태: {record["implementation_status"]}**<br>
> **보고서 상태: {record["report_state"]}**<br>
> **Science Knowledge Release: NOT ACTIVE — 사람 Admin 승인과 독립 holdout 대기**

이 보고서는 AI나 호출자 제공 숫자를 신뢰하지 않는다. 현재 Git 상태와 기계 산출 JUnit, 브라우저 캡처 manifest, Candidate qualification, 독립 리뷰를 검증하고 각 원본 파일의 SHA-256을 묶어 구현 상태를 계산한다.

## 검증 식별자

- 생성 시각: `{record["generated_at"]}`
- 검증 코드 revision: `{record["git"]["commit"]}`
- Git dirty: `{str(record["git"]["dirty"]).lower()}`
- Git status digest: `{record["git"]["status_digest"]}`
- Evidence bundle digest: `{record["evidence_bundle_digest"]}`
- Report record digest: `{record["report_record_digest"]}`
- Release: `{qualification.get("release_id", "unavailable")}` (`{qualification.get("lifecycle", "unavailable")}`, `active=false`)
- Release digest: `{qualification.get("release_digest", "unavailable")}`
- Qualification result digest: `{qualification.get("qualification_result_digest", "unavailable")}`
- Activation eligible: `false`

## 기계 검증 증거

| 증빙 | 파생 상태 | 기계 결과 | 파일 SHA-256 |
|---|---|---|---|
{chr(10).join(source_rows)}

## 상태 하향 사유

{failures}

## Candidate 지식 자산

| 자산 | 파일/결과 수량 |
|---|---:|
| Science Knowledge | {counts["knowledge"]} |
| Evidence | {counts["evidence"]} |
| Deterministic Rules | {counts["rules"]} |
| Knowledge Packs | {counts["packs"]} |
| Ontology bindings | {counts["ontology_bindings"]} |
| Qualification families | {counts["qualification_case_families"]} |
| Public qualification cases | {counts["public_cases"]} |

## Release Gate

| Gate | 기계 산출 상태 | 근거/대기 사항 |
|---|---|---|
{gate_rows}

G5·G6·G7 또는 사람 Admin 승인 대기를 종합점수로 상쇄하지 않는다. 구현 보고서가 FINAL이어도 Science Knowledge Release의 승인·활성화·과학적 진실·공정 또는 안전 승인을 의미하지 않는다.
"""


def _styles() -> dict[str, ParagraphStyle]:
    font_path = Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc")
    font_name = "WQY"
    if font_path.exists():
        pdfmetrics.registerFont(TTFont(font_name, str(font_path), subfontIndex=0))
    else:
        font_name = "Helvetica"
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "TitleK",
            parent=base["Title"],
            fontName=font_name,
            fontSize=22,
            leading=28,
            textColor=colors.HexColor("#111827"),
            alignment=TA_LEFT,
        ),
        "status": ParagraphStyle(
            "StatusK",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=12,
            leading=18,
            textColor=colors.HexColor("#5B21B6"),
        ),
        "h1": ParagraphStyle(
            "H1K",
            parent=base["Heading1"],
            fontName=font_name,
            fontSize=14,
            leading=20,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "BodyK",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=8.5,
            leading=13,
            textColor=colors.HexColor("#374151"),
        ),
        "cell": ParagraphStyle(
            "CellK", parent=base["BodyText"], fontName=font_name, fontSize=7, leading=9
        ),
        "center": ParagraphStyle(
            "CenterK",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=7,
            leading=9,
            alignment=TA_CENTER,
        ),
        "header": ParagraphStyle(
            "HeaderK",
            parent=base["BodyText"],
            fontName=font_name,
            fontSize=7,
            leading=9,
            textColor=colors.white,
        ),
    }


def _table(
    rows: list[list[Any]], widths: list[float], styles: dict[str, ParagraphStyle]
) -> Table:
    data = [
        [
            Paragraph(
                str(value),
                styles["header"]
                if row_index == 0
                else styles["center"]
                if column == 1
                else styles["cell"],
            )
            for column, value in enumerate(row)
        ]
        for row_index, row in enumerate(rows)
    ]
    table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D1D5DB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F9FAFB")],
                ),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _pdf(path: Path, record: dict[str, Any]) -> None:
    styles = _styles()
    document = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=17 * mm,
        rightMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        title="Science Verifier 구현 검증 보고서",
        author="BoI Wiki Science Verifier",
    )
    evidence_rows: list[list[Any]] = [["증빙", "상태", "기계 결과"]]
    for key, label in (
        ("test_suite_contract", "Suite contract"),
        ("science_tests", "Science JUnit"),
        ("mcp_tests", "MCP JUnit"),
        ("full_regression", "Full regression"),
        ("browser", "Browser captures"),
        ("qualification", "Qualification"),
        ("independent_review", "Independent review"),
    ):
        item = record["evidence"][key]
        if key == "test_suite_contract":
            result = f"schema={item.get('schema_version', 'unknown')}, suites={len(item.get('suites', {}))}"
        elif key.endswith("tests") or key == "full_regression":
            result = f"tests={item.get('tests', 0)}, failures={item.get('failures', 0)}, errors={item.get('errors', 0)}, skipped={item.get('skipped', 0)}"
        elif key == "browser":
            result = (
                f"checks={item.get('checks', 0)}, captures={item.get('captures', 0)}"
            )
        elif key == "qualification":
            result = f"cases={item.get('public_case_count', 0)}"
        else:
            result = (
                f"status={item.get('status', 'unknown')}, "
                f"critical={item.get('findings', {}).get('critical', 'unknown')}, "
                f"important={item.get('findings', {}).get('important', 'unknown')}"
            )
        evidence_rows.append([label, _status_for(item), result])
    gate_rows = [["Gate", "상태", "근거"]]
    for gate, entry in sorted(
        record["evidence"]["qualification"].get("gates", {}).items()
    ):
        gate_rows.append([gate, entry["status"], entry["detail"]])
    if len(gate_rows) == 1:
        gate_rows.append(["-", "UNVERIFIED", "유효한 qualification 결과 없음"])
    failure_text = "<br/>".join(record["failure_reasons"]) or "없음"
    story: list[Any] = [
        Paragraph("SCIENCE VERIFIER", styles["body"]),
        Paragraph("구현 검증 보고서", styles["title"]),
        Paragraph(
            f"구현 상태: {record['implementation_status']} · 보고서: {record['report_state']} · Science Knowledge Release: NOT ACTIVE",
            styles["status"],
        ),
        Paragraph(
            "호출자 숫자가 아니라 Git 상태와 해시로 묶인 기계 증빙에서 구현 상태를 계산했습니다. 이 결과는 지식 Release 활성화나 과학적 진실 보증이 아닙니다.",
            styles["body"],
        ),
        Spacer(1, 4 * mm),
        _table(evidence_rows, [48 * mm, 32 * mm, 94 * mm], styles),
        Paragraph("검증 식별자", styles["h1"]),
        Paragraph(
            f"Code revision: {record['git']['commit']}<br/>Git dirty: {record['git']['dirty']}<br/>Git status digest: {record['git']['status_digest']}<br/>Evidence bundle: {record['evidence_bundle_digest']}<br/>Report record: {record['report_record_digest']}",
            styles["body"],
        ),
        Paragraph("상태 하향 사유", styles["h1"]),
        Paragraph(failure_text, styles["body"]),
        Paragraph("Release Gate", styles["h1"]),
        _table(gate_rows, [18 * mm, 28 * mm, 128 * mm], styles),
        Paragraph("완료 경계", styles["h1"]),
        Paragraph(
            "사람 Admin 승인과 독립 sealed holdout이 없으면 Candidate를 활성화하거나 운영 검증 완료로 표현하지 않습니다.",
            styles["body"],
        ),
    ]
    document.build(story)


def _collect(args: argparse.Namespace) -> dict[str, Any]:
    git, failures = _git_state(args.repo_root)
    evidence: dict[str, Any] = {}
    evidence["test_suite_contract"], suite_contracts, source_failures = (
        _test_suite_contract(args.repo_root)
    )
    failures.extend(source_failures)
    for name, path in (
        ("science_tests", args.science_test_summary),
        ("mcp_tests", args.mcp_test_summary),
        ("full_regression", args.full_regression_summary),
    ):
        evidence[name], source_failures = _junit_evidence(
            name,
            path,
            args.repo_root,
            git["commit"],
            suite_contracts.get(name),
        )
        failures.extend(source_failures)
    evidence["browser"], source_failures = _browser_evidence(
        args.browser_capture_manifest, args.repo_root, git["commit"]
    )
    failures.extend(source_failures)
    evidence["qualification"], source_failures = _qualification_evidence(
        args.qualification_result, args.repo_root
    )
    failures.extend(source_failures)
    evidence["independent_review"], source_failures = _review_evidence(
        args.independent_review, args.repo_root, git["commit"]
    )
    failures.extend(source_failures)
    failure_reasons = sorted(set(failures))
    status = "VERIFIED" if not failure_reasons else "UNVERIFIED"
    report_state = "FINAL" if status == "VERIFIED" else "DRAFT"
    qualification = evidence["qualification"]
    record: dict[str, Any] = {
        "report_version": "science-verifier-implementation-qualification/0.2.0",
        "generated_at": args.generated_at,
        "report_state": report_state,
        "implementation_status": status,
        "knowledge_release_status": "not_active",
        "activation_eligible": False,
        "failure_reasons": failure_reasons,
        "git": git,
        "evidence": evidence,
        "counts": _knowledge_counts(
            args.repo_root, qualification.get("public_case_count")
        ),
    }
    record["evidence_bundle_digest"] = canonical_digest(
        {"git": git, "evidence": evidence}
    )
    record["report_record_digest"] = canonical_digest(record)
    return record


def main() -> int:
    args = _args()
    record = _collect(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = args.output_dir / "qualification-report.md"
    pdf_path = args.output_dir / "qualification-report.pdf"
    markdown_path.write_text(_markdown(record), encoding="utf-8")
    _pdf(pdf_path, record)
    qualification = record["evidence"]["qualification"]
    manifest = {
        "schema_version": "science-verifier-evidence-manifest/0.2",
        "report_state": record["report_state"],
        "implementation_status": record["implementation_status"],
        "failure_reasons": record["failure_reasons"],
        "git": record["git"],
        "evidence": record["evidence"],
        "evidence_bundle_digest": record["evidence_bundle_digest"],
        "report_record_digest": record["report_record_digest"],
        "release_id": qualification.get("release_id"),
        "release_digest": qualification.get("release_digest"),
        "qualification_result_digest": qualification.get("qualification_result_digest"),
        "activation_eligible": False,
        "gates": {
            gate: entry["status"]
            for gate, entry in qualification.get("gates", {}).items()
        },
        "markdown": {
            "path": display_path(markdown_path, args.repo_root),
            "sha256": sha256_bytes(markdown_path.read_bytes()),
        },
        "pdf": {
            "path": display_path(pdf_path, args.repo_root),
            "sha256": sha256_bytes(pdf_path.read_bytes()),
        },
    }
    manifest_path = args.output_dir / "verification-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if record["implementation_status"] == "VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
