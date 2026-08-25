from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from _pytest.junitxml import mangle_test_address


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER = PROJECT_ROOT / "scripts/build_science_verification_report.py"
UI_CHECKER = PROJECT_ROOT / "scripts/check_science_verifier_ui.mjs"
SUITE_CONTRACT_BUILDER = PROJECT_ROOT / "scripts/build_science_test_suite_contract.py"
TRACKED_SUITE_CONTRACT = PROJECT_ROOT / "config/science-verifier-test-suites.json"
SUITE_DEFINITIONS = {
    "science_tests": {
        "suite_id": "science-tests",
        "pytest_args": ["tests", "-k", "science and not mcp"],
        "bundle_key": "science",
    },
    "mcp_tests": {
        "suite_id": "science-mcp",
        "pytest_args": ["tests/test_science_mcp.py"],
        "bundle_key": "mcp",
    },
    "full_regression": {
        "suite_id": "full-regression",
        "pytest_args": ["tests"],
        "bundle_key": "full",
    },
}
MANDATORY_BROWSER_CHECK_IDS = {
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


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_digest(value: object) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


def _identity(testcase: tuple[str, str, bool]) -> str:
    classname, case_name, _ = testcase
    return f"{classname}::{case_name}"


def _default_testcases(suite_name: str, tests: int = 4) -> list[tuple[str, str, bool]]:
    return [(f"fixture.{suite_name}", f"test_{index}", False) for index in range(tests)]


def _junit(
    path: Path,
    *,
    commit: str,
    tests: int = 4,
    failures: int = 0,
    skipped: int = 0,
    skipped_cases: list[tuple[str, str]] | None = None,
    testcases: list[tuple[str, str, bool]] | None = None,
) -> list[tuple[str, str, bool]]:
    suite_name = next(
        name
        for name, definition in SUITE_DEFINITIONS.items()
        if definition["bundle_key"] == path.stem
    )
    suite_id = str(SUITE_DEFINITIONS[suite_name]["suite_id"])
    if testcases is not None:
        tests = len(testcases)
        skipped = sum(is_skipped for _, _, is_skipped in testcases)
    if skipped_cases is not None:
        skipped = len(skipped_cases)
        if skipped > tests:
            raise ValueError("skipped testcase count cannot exceed total tests")
        testcases = [
            (classname, case_name, True) for classname, case_name in skipped_cases
        ] + [
            (f"fixture.{suite_name}", f"test_executed_{index}", False)
            for index in range(tests - skipped)
        ]
    elif testcases is None and skipped:
        skipped_cases = [
            ("fixture.Generic", f"skipped-{index}") for index in range(skipped)
        ]
        testcases = [
            (classname, case_name, True) for classname, case_name in skipped_cases
        ] + [
            (f"fixture.{suite_name}", f"test_executed_{index}", False)
            for index in range(tests - skipped)
        ]
    elif testcases is None:
        testcases = _default_testcases(suite_name, tests)
    cases = "".join(
        f'<testcase classname="{classname}" name="{case_name}">'
        + ('<skipped message="fixture skip" />' if is_skipped else "")
        + "</testcase>"
        for classname, case_name, is_skipped in testcases
    )
    path.write_text(
        f'''<?xml version="1.0" encoding="utf-8"?>
<testsuites tests="{tests}" failures="{failures}" errors="0" skipped="{skipped}">
  <properties><property name="git_commit" value="{commit}" /><property name="suite_id" value="{suite_id}" /></properties>
  <testsuite name="suite" tests="{tests}" failures="{failures}" errors="0" skipped="{skipped}">{cases}</testsuite>
</testsuites>
''',
        encoding="utf-8",
    )
    return testcases


def _write_suite_contract(
    repo: Path,
    testcase_overrides: dict[str, list[tuple[str, str, bool]]] | None = None,
) -> Path:
    testcase_overrides = testcase_overrides or {}
    suites: dict[str, object] = {}
    for suite_name, definition in SUITE_DEFINITIONS.items():
        testcases = testcase_overrides.get(suite_name, _default_testcases(suite_name))
        identities = sorted(_identity(testcase) for testcase in testcases)
        suites[suite_name] = {
            "suite_id": definition["suite_id"],
            "pytest_args": definition["pytest_args"],
            "collected": len(identities),
            "testcase_identity_digest": _canonical_digest(identities),
        }
    contract = {
        "schema_version": "science-test-suite-contract/0.1",
        "identity_format": "pytest-junit-classname::name",
        "suites": suites,
    }
    path = repo / "config/science-verifier-test-suites.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return path


def _qualification_markdown(*, g3: str = "PASS") -> str:
    metadata = {
        "science_qualification": {
            "release_id": "sci-release:test",
            "release_digest": "sha256:" + "1" * 64,
            "qualification_result_digest": "sha256:" + "2" * 64,
            "lifecycle": "release_candidate",
            "activation_eligible": False,
            "public_case_count": 40,
        }
    }
    gates = {f"G{i}": "PASS" if i < 5 else "PENDING" for i in range(8)}
    gates["G3"] = g3
    gate_lines = "\n".join(
        f"- {gate} | {status} | fixture evidence" for gate, status in gates.items()
    )
    return f"---\n{json.dumps(metadata)}\n---\n# Qualification\n{gate_lines}\n"


def _fixture_bundle(tmp_path: Path) -> dict[str, Path | str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "science@example.invalid")
    _git(repo, "config", "user.name", "Science Test")
    qualification = repo / "qualification.md"
    qualification.write_text(_qualification_markdown(), encoding="utf-8")
    contract = _write_suite_contract(repo)
    _git(repo, "add", "qualification.md", str(contract.relative_to(repo)))
    _git(repo, "commit", "-m", "qualification and suite contract fixture")
    commit = _git(repo, "rev-parse", "HEAD")

    evidence = tmp_path / "evidence"
    evidence.mkdir()
    science = evidence / "science.xml"
    mcp = evidence / "mcp.xml"
    full = evidence / "full.xml"
    for summary in (science, mcp, full):
        _junit(summary, commit=commit)

    capture = evidence / "review-canvas.png"
    capture.write_bytes(b"browser-capture-fixture")
    browser = evidence / "browser.json"
    browser.write_text(
        json.dumps(
            {
                "schema_version": "science-browser-capture-manifest/0.1",
                "git_commit": commit,
                "checks": [
                    {"check_id": check_id, "status": "passed"}
                    for check_id in sorted(MANDATORY_BROWSER_CHECK_IDS)
                ],
                "captures": [{"path": capture.name, "sha256": _sha256(capture)}],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    review = evidence / "review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": "science-independent-review/0.1",
                "reviewed_git_commit": commit,
                "status": "passed",
                "findings": {"critical": 0, "important": 0, "advisory": 1},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "repo": repo,
        "commit": commit,
        "qualification": qualification,
        "science": science,
        "mcp": mcp,
        "full": full,
        "browser": browser,
        "capture": capture,
        "review": review,
        "contract": contract,
    }


def _run(
    bundle: dict[str, Path | str],
    output: Path,
    *,
    full: Path | None | object = ...,
) -> subprocess.CompletedProcess[str]:
    full_path = bundle["full"] if full is ... else full
    command = [
        sys.executable,
        str(BUILDER),
        "--repo-root",
        str(bundle["repo"]),
        "--output-dir",
        str(output),
        "--generated-at",
        "2026-08-25T20:00:00+09:00",
        "--science-test-summary",
        str(bundle["science"]),
        "--mcp-test-summary",
        str(bundle["mcp"]),
        "--browser-capture-manifest",
        str(bundle["browser"]),
        "--qualification-result",
        str(bundle["qualification"]),
        "--independent-review",
        str(bundle["review"]),
    ]
    if full_path is not None:
        command += ["--full-regression-summary", str(full_path)]
    return subprocess.run(command, cwd=PROJECT_ROOT, capture_output=True, text=True)


def _manifest(output: Path) -> dict[str, object]:
    return json.loads(
        (output / "verification-manifest.json").read_text(encoding="utf-8")
    )


def _refresh_commit_bindings(
    bundle: dict[str, Path | str],
    testcase_overrides: dict[str, list[tuple[str, str, bool]]] | None = None,
) -> str:
    testcase_overrides = testcase_overrides or {}
    repo = bundle["repo"]
    assert isinstance(repo, Path)
    commit = _git(repo, "rev-parse", "HEAD")
    bundle["commit"] = commit
    for suite_name, definition in SUITE_DEFINITIONS.items():
        summary = bundle[str(definition["bundle_key"])]
        assert isinstance(summary, Path)
        _junit(
            summary,
            commit=commit,
            testcases=testcase_overrides.get(suite_name),
        )
    browser = bundle["browser"]
    review = bundle["review"]
    assert isinstance(browser, Path) and isinstance(review, Path)
    browser_data = json.loads(browser.read_text(encoding="utf-8"))
    browser_data["git_commit"] = commit
    browser.write_text(json.dumps(browser_data, indent=2) + "\n", encoding="utf-8")
    review_data = json.loads(review.read_text(encoding="utf-8"))
    review_data["reviewed_git_commit"] = commit
    review.write_text(json.dumps(review_data, indent=2) + "\n", encoding="utf-8")
    return commit


def _replace_suite_contract(
    bundle: dict[str, Path | str],
    suite_name: str,
    testcases: list[tuple[str, str, bool]],
) -> None:
    repo = bundle["repo"]
    assert isinstance(repo, Path)
    _write_suite_contract(repo, {suite_name: testcases})
    _git(repo, "add", "config/science-verifier-test-suites.json")
    _git(repo, "commit", "-m", f"replace {suite_name} contract fixture")
    _refresh_commit_bindings(bundle, {suite_name: testcases})


def test_verified_is_derived_from_clean_hash_bound_machine_evidence(
    tmp_path: Path,
) -> None:
    bundle = _fixture_bundle(tmp_path)
    output = tmp_path / "report"

    completed = _run(bundle, output)

    assert completed.returncode == 0, completed.stderr
    manifest = _manifest(output)
    markdown = (output / "qualification-report.md").read_text(encoding="utf-8")
    assert manifest["schema_version"] == "science-verifier-evidence-manifest/0.2"
    assert manifest["report_state"] == "FINAL"
    assert manifest["implementation_status"] == "VERIFIED"
    assert manifest["failure_reasons"] == []
    assert manifest["git"] == {
        "commit": bundle["commit"],
        "dirty": False,
        "status_digest": "sha256:" + hashlib.sha256(b"").hexdigest(),
    }
    evidence = manifest["evidence"]
    assert evidence["test_suite_contract"]["passed"] is True
    assert evidence["test_suite_contract"]["sha256"] == _sha256(bundle["contract"])
    assert evidence["science_tests"]["tests"] == 4
    assert evidence["science_tests"]["testcase_count"] == 4
    assert evidence["science_tests"]["testcase_identity_digest"] == _canonical_digest(
        sorted(_identity(testcase) for testcase in _default_testcases("science_tests"))
    )
    assert evidence["full_regression"]["sha256"] == _sha256(bundle["full"])
    assert evidence["browser"]["checks"] == 21
    assert evidence["browser"]["captures"] == 1
    assert evidence["qualification"]["public_case_count"] == 40
    assert evidence["qualification"]["passed"] is True
    assert evidence["independent_review"]["findings"]["critical"] == 0
    assert manifest["evidence_bundle_digest"] == _canonical_digest(
        {"git": manifest["git"], "evidence": manifest["evidence"]}
    )
    assert manifest["markdown"]["sha256"] == _sha256(output / "qualification-report.md")
    assert manifest["pdf"]["sha256"] == _sha256(output / "qualification-report.pdf")
    assert "구현 상태: VERIFIED" in markdown
    assert f"검증 코드 revision: `{bundle['commit']}`" in markdown
    assert "Science Knowledge Release: NOT ACTIVE" in markdown


def test_mandatory_browser_checks_match_the_ui_checker_contract() -> None:
    source = UI_CHECKER.read_text(encoding="utf-8")
    checks_block = source.split("    const checks = {", 1)[1].split(
        "\n    };\n    const report", 1
    )[0]
    produced_ids = set(re.findall(r"^      ([a-z0-9_]+):", checks_block, re.MULTILINE))

    assert len(produced_ids) == 21
    assert produced_ids == MANDATORY_BROWSER_CHECK_IDS


def test_tracked_suite_contract_matches_exact_pytest_collect_only(
    tmp_path: Path,
) -> None:
    generated = tmp_path / "science-verifier-test-suites.json"

    subprocess.run(
        [
            sys.executable,
            str(SUITE_CONTRACT_BUILDER),
            "--repo-root",
            str(PROJECT_ROOT),
            "--output",
            str(generated),
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(generated.read_text(encoding="utf-8")) == json.loads(
        TRACKED_SUITE_CONTRACT.read_text(encoding="utf-8")
    )


def test_collect_only_mangle_matches_actual_parametrized_pytest_junit(
    tmp_path: Path,
) -> None:
    target = (
        "tests/test_science_authorization.py::"
        "test_access_mode_uses_only_the_complete_resolved_role_list"
    )
    collected = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "--capture=no",
            target,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    node_ids = [
        line.strip()
        for line in collected.stdout.splitlines()
        if line.startswith("tests/") and "::" in line
    ]
    assert len(node_ids) > 1
    assert any("[" in node_id and "]" in node_id for node_id in node_ids)
    expected = set()
    for node_id in node_ids:
        address = mangle_test_address(node_id)
        expected.add(f"{'.'.join(address[:-1])}::{address[-1]}")

    junit = tmp_path / "parametrized.xml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--capture=no",
            f"--junitxml={junit}",
            target,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    root = ET.parse(junit).getroot()
    actual = {
        f"{case.get('classname')}::{case.get('name')}"
        for case in root.findall(".//testcase")
    }

    assert actual == expected


def test_arbitrary_single_browser_check_cannot_qualify(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    browser = bundle["browser"]
    assert isinstance(browser, Path)
    browser_data = json.loads(browser.read_text(encoding="utf-8"))
    browser_data["checks"] = [{"check_id": "arbitrary-check", "status": "passed"}]
    browser.write_text(json.dumps(browser_data) + "\n", encoding="utf-8")

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    manifest = _manifest(tmp_path / "report")
    assert manifest["implementation_status"] == "UNVERIFIED"
    assert "browser:mandatory_checks_mismatch" in manifest["failure_reasons"]


@pytest.mark.parametrize("mode", ["missing", "zero", "failure"])
def test_full_regression_missing_zero_or_failure_fails_closed(
    tmp_path: Path, mode: str
) -> None:
    bundle = _fixture_bundle(tmp_path)
    full = bundle["full"]
    assert isinstance(full, Path)
    full_arg: Path | None = full
    if mode == "missing":
        full_arg = None
    elif mode == "zero":
        _junit(full, commit=str(bundle["commit"]), tests=0)
    else:
        _junit(full, commit=str(bundle["commit"]), tests=4, failures=1)
    output = tmp_path / "report"

    completed = _run(bundle, output, full=full_arg)

    assert completed.returncode == 2
    manifest = _manifest(output)
    assert manifest["report_state"] == "DRAFT"
    assert manifest["implementation_status"] == "UNVERIFIED"
    assert any(
        reason.startswith("full_regression:") for reason in manifest["failure_reasons"]
    )
    assert "구현 상태: UNVERIFIED" in (output / "qualification-report.md").read_text(
        encoding="utf-8"
    )


def test_unexpected_skipped_junit_test_fails_closed(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    full = bundle["full"]
    assert isinstance(full, Path)
    _junit(full, commit=str(bundle["commit"]), skipped=1)

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    manifest = _manifest(tmp_path / "report")
    assert manifest["evidence"]["full_regression"]["passed"] is False
    assert "full_regression:unexpected_skipped_tests" in manifest["failure_reasons"]


def test_exact_allowlisted_all_skipped_suite_fails_closed(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    testcases = [
        (
            "tests.test_repository_source_and_mcp.RepositorySourceContractTests",
            "test_internal_success_skips_external_probe",
            True,
        )
    ]
    _replace_suite_contract(bundle, "full_regression", testcases)

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    manifest = _manifest(tmp_path / "report")
    assert manifest["evidence"]["full_regression"]["executed"] == 0
    assert "full_regression:no_executed_tests" in manifest["failure_reasons"]


def test_exact_allowlisted_partial_skip_is_allowed_when_contract_matches(
    tmp_path: Path,
) -> None:
    bundle = _fixture_bundle(tmp_path)
    testcases = [
        (
            "tests.test_repository_source_and_mcp.RepositorySourceContractTests",
            "test_internal_success_skips_external_probe",
            True,
        ),
        ("fixture.full_regression", "test_executed", False),
    ]
    _replace_suite_contract(bundle, "full_regression", testcases)

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 0, completed.stderr
    evidence = _manifest(tmp_path / "report")["evidence"]["full_regression"]
    assert evidence["passed"] is True
    assert evidence["skipped"] == 1
    assert evidence["executed"] == 1
    assert evidence["skip_policy"] == "powershell-wsl-exact-allowlist/0.1"


@pytest.mark.parametrize("severity", ["critical", "important"])
def test_blocking_independent_review_findings_fail_closed(
    tmp_path: Path, severity: str
) -> None:
    bundle = _fixture_bundle(tmp_path)
    review = bundle["review"]
    assert isinstance(review, Path)
    review_data = json.loads(review.read_text(encoding="utf-8"))
    review_data["findings"][severity] = 1
    review.write_text(json.dumps(review_data) + "\n", encoding="utf-8")

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert (
        f"independent_review:{severity}_findings"
        in _manifest(tmp_path / "report")["failure_reasons"]
    )


def test_dirty_checkout_and_stale_junit_revision_fail_closed(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    repo = bundle["repo"]
    assert isinstance(repo, Path)
    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    science = bundle["science"]
    assert isinstance(science, Path)
    _junit(science, commit="0" * 40)

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    reasons = _manifest(tmp_path / "report")["failure_reasons"]
    assert "git:dirty_worktree" in reasons
    assert "science_tests:git_commit_mismatch" in reasons


def test_mismatched_junit_suite_identity_fails_closed(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    science = bundle["science"]
    assert isinstance(science, Path)
    science.write_text(
        science.read_text(encoding="utf-8").replace(
            'name="suite_id" value="science-tests"',
            'name="suite_id" value="full-regression"',
        ),
        encoding="utf-8",
    )

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert (
        "science_tests:suite_id_mismatch"
        in _manifest(tmp_path / "report")["failure_reasons"]
    )


def test_altered_junit_testcase_identity_digest_fails_closed(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    science = bundle["science"]
    assert isinstance(science, Path)
    science.write_text(
        science.read_text(encoding="utf-8").replace(
            'name="test_0"', 'name="test_altered"', 1
        ),
        encoding="utf-8",
    )

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert (
        "science_tests:testcase_identity_digest_mismatch"
        in _manifest(tmp_path / "report")["failure_reasons"]
    )


def test_duplicate_junit_testcase_identity_is_invalid(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    science = bundle["science"]
    assert isinstance(science, Path)
    science.write_text(
        science.read_text(encoding="utf-8").replace(
            'name="test_1"', 'name="test_0"', 1
        ),
        encoding="utf-8",
    )

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert "science_tests:invalid" in _manifest(tmp_path / "report")["failure_reasons"]


@pytest.mark.parametrize(
    "mutation",
    ["schema", "suite_id", "digest_format", "count_type", "negative_count"],
)
def test_invalid_tracked_suite_contract_fails_closed(
    tmp_path: Path, mutation: str
) -> None:
    bundle = _fixture_bundle(tmp_path)
    repo = bundle["repo"]
    contract = bundle["contract"]
    assert isinstance(repo, Path) and isinstance(contract, Path)
    payload = json.loads(contract.read_text(encoding="utf-8"))
    if mutation == "schema":
        payload["schema_version"] = "science-test-suite-contract/untrusted"
    elif mutation == "suite_id":
        payload["suites"]["science_tests"]["suite_id"] = "full-regression"
    elif mutation == "digest_format":
        payload["suites"]["science_tests"]["testcase_identity_digest"] = "sha256:short"
    elif mutation == "count_type":
        payload["suites"]["science_tests"]["collected"] = "4"
    else:
        payload["suites"]["science_tests"]["collected"] = -1
    contract.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", "config/science-verifier-test-suites.json")
    _git(repo, "commit", "-m", f"invalid {mutation} contract fixture")
    _refresh_commit_bindings(bundle)

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert (
        "test_suite_contract:invalid"
        in _manifest(tmp_path / "report")["failure_reasons"]
    )


def test_junit_testcase_count_must_equal_tracked_contract(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    repo = bundle["repo"]
    contract = bundle["contract"]
    assert isinstance(repo, Path) and isinstance(contract, Path)
    payload = json.loads(contract.read_text(encoding="utf-8"))
    payload["suites"]["science_tests"]["collected"] += 1
    contract.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _git(repo, "add", "config/science-verifier-test-suites.json")
    _git(repo, "commit", "-m", "mismatched suite count fixture")
    _refresh_commit_bindings(bundle)

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert (
        "science_tests:testcase_count_mismatch"
        in _manifest(tmp_path / "report")["failure_reasons"]
    )


def test_tampered_browser_capture_and_failed_qualification_gate_fail_closed(
    tmp_path: Path,
) -> None:
    bundle = _fixture_bundle(tmp_path)
    qualification = bundle["qualification"]
    repo = bundle["repo"]
    browser = bundle["browser"]
    assert (
        isinstance(qualification, Path)
        and isinstance(repo, Path)
        and isinstance(browser, Path)
    )
    qualification.write_text(_qualification_markdown(g3="FAIL"), encoding="utf-8")
    _git(repo, "add", "qualification.md")
    _git(repo, "commit", "-m", "failed qualification fixture")
    _refresh_commit_bindings(bundle)
    browser_data = json.loads(browser.read_text(encoding="utf-8"))
    browser_data["captures"][0]["sha256"] = "sha256:" + "0" * 64
    browser.write_text(json.dumps(browser_data) + "\n", encoding="utf-8")

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    reasons = _manifest(tmp_path / "report")["failure_reasons"]
    assert "browser:capture_digest_mismatch" in reasons
    assert "qualification:G3_not_passed" in reasons


def test_legacy_raw_counts_cannot_assert_verification(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(BUILDER),
            "--repo-root",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "report"),
            "--generated-at",
            "2026-08-25T20:00:00+09:00",
            "--full-regression-tests",
            "9999",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "unrecognized arguments" in completed.stderr
