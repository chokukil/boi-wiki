from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILDER = PROJECT_ROOT / "scripts/build_science_verification_report.py"


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


def _junit(path: Path, *, commit: str, tests: int = 4, failures: int = 0) -> None:
    path.write_text(
        f'''<?xml version="1.0" encoding="utf-8"?>
<testsuites tests="{tests}" failures="{failures}" errors="0" skipped="0">
  <properties><property name="git_commit" value="{commit}" /></properties>
  <testsuite name="suite" tests="{tests}" failures="{failures}" errors="0" skipped="0" />
</testsuites>
''',
        encoding="utf-8",
    )


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
    _git(repo, "add", "qualification.md")
    _git(repo, "commit", "-m", "qualification fixture")
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
                    {"check_id": "desktop-review", "status": "passed"},
                    {"check_id": "manual-correction", "status": "passed"},
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


def _refresh_commit_bindings(bundle: dict[str, Path | str]) -> str:
    repo = bundle["repo"]
    assert isinstance(repo, Path)
    commit = _git(repo, "rev-parse", "HEAD")
    bundle["commit"] = commit
    for name in ("science", "mcp", "full"):
        summary = bundle[name]
        assert isinstance(summary, Path)
        _junit(summary, commit=commit)
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
    assert evidence["science_tests"]["tests"] == 4
    assert evidence["full_regression"]["sha256"] == _sha256(bundle["full"])
    assert evidence["browser"]["checks"] == 2
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


def test_critical_independent_review_fails_closed(tmp_path: Path) -> None:
    bundle = _fixture_bundle(tmp_path)
    review = bundle["review"]
    assert isinstance(review, Path)
    review_data = json.loads(review.read_text(encoding="utf-8"))
    review_data["findings"]["critical"] = 1
    review.write_text(json.dumps(review_data) + "\n", encoding="utf-8")

    completed = _run(bundle, tmp_path / "report")

    assert completed.returncode == 2
    assert (
        "independent_review:critical_findings"
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
