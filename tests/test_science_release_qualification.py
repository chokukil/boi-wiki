from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from boi_api.app.okf import split_frontmatter
from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.qualification import qualify_release_candidate

REPO_ROOT = Path(__file__).resolve().parents[1]
BOI_ROOT = REPO_ROOT / "data" / "boi"
RELEASE_ID = "sci-release:0.1.0"
RELEASE_PATH = BOI_ROOT / "public" / "science" / "releases" / "science-release-0.1.0.md"
HOLDOUT_MANIFEST_PATH = (
    BOI_ROOT / "public" / "science" / "qualification" / "holdouts" / "manifest.md"
)
PREFLIGHT_PATH = (
    BOI_ROOT
    / "public"
    / "science"
    / "qualification"
    / "reports"
    / "release-gate-preflight-science-release-0.1.0.md"
)


def test_release_candidate_pins_every_v01_science_component() -> None:
    catalog = ScienceCatalog(BOI_ROOT)
    release = catalog.resolve_release(RELEASE_ID)

    expected_refs = {
        object_id
        for kind in (
            "source",
            "evidence",
            "knowledge",
            "rule",
            "ontology_binding",
            "qualification_matrix",
            "pack",
        )
        for object_id in catalog._objects[kind]
    }
    assert release.status == "release_candidate"
    assert {component.ref for component in release.components} == expected_refs
    assert set(release.component_digests) == expected_refs
    assert release.known_limitations

    metadata, _body = split_frontmatter(RELEASE_PATH.read_text(encoding="utf-8"))
    assert metadata["status"] == "draft"
    assert metadata["review"]["review_status"] == "pending_review"
    assert metadata["review"]["authorized_review_events"] == []
    assert metadata["science"]["active"] is False
    assert metadata["science"]["last_safe_release_id"] is None
    assert metadata["science"]["supported_scopes"]
    assert metadata["science"]["partial_scopes"]
    assert metadata["science"]["unsupported_scopes"]


def test_release_preflight_has_no_compensating_score() -> None:
    result = qualify_release_candidate(BOI_ROOT, RELEASE_ID)

    assert list(result.gates) == [f"G{number}" for number in range(8)]
    assert result.aggregate_score is None
    assert [result.gates[f"G{number}"].status for number in range(5)] == ["PASS"] * 5
    assert result.gates["G5"].status == "PENDING"
    assert result.gates["G6"].status == "PENDING"
    assert result.gates["G7"].status == "PENDING"
    assert result.activation_eligible is False
    assert result.release_status == "release_candidate"
    assert result.public_case_count == 440
    assert result.missed_violations == []
    assert result.false_red_cases == []
    assert result.wrong_interpretations == []
    assert result.validity_range_errors == []
    assert result.unsupported_scope_errors == []
    assert result.broken_evidence_locators == []
    assert result.ungrounded_explanation_facts == []
    assert result.nondeterministic_cases == []
    assert len(result.case_results) == 440


def test_release_preflight_preserves_closed_pack_relationships() -> None:
    result = qualify_release_candidate(BOI_ROOT, RELEASE_ID)

    assert result.pack_dependencies == {
        "sci-pack:science-foundation/0.1.0": [],
        "sci-pack:physical-principles/0.1.0": [
            {"relation": "depends_on", "ref": "sci-pack:science-foundation/0.1.0"}
        ],
        "sci-pack:chemical-principles/0.1.0": [
            {"relation": "depends_on", "ref": "sci-pack:science-foundation/0.1.0"}
        ],
        "sci-pack:circuit-principles/0.1.0": [
            {"relation": "depends_on", "ref": "sci-pack:science-foundation/0.1.0"}
        ],
        "sci-pack:materials-science/0.1.0": [
            {"relation": "depends_on", "ref": "sci-pack:science-foundation/0.1.0"}
        ],
        "sci-pack:semiconductor-devices/0.1.0": [
            {"relation": "depends_on", "ref": "sci-pack:materials-science/0.1.0"}
        ],
        "sci-pack:spin-coating/0.1.0": [
            {"relation": "depends_on", "ref": "sci-pack:physical-principles/0.1.0"},
            {"relation": "depends_on", "ref": "sci-pack:chemical-principles/0.1.0"},
            {"relation": "depends_on", "ref": "sci-pack:materials-science/0.1.0"},
        ],
    }


def test_pending_holdout_manifest_is_explicit_and_non_authorizing() -> None:
    metadata, body = split_frontmatter(
        HOLDOUT_MANIFEST_PATH.read_text(encoding="utf-8")
    )
    holdout = metadata["science_holdout"]

    assert metadata["status"] == "draft"
    assert holdout["state"] == "pending_independent_commission"
    assert holdout["external_acl_url"].startswith("boi-private://")
    assert holdout["sealed_sha256"] is None
    assert holdout["rule_freeze_commit"] is None
    assert holdout["reviewer_role"] == "independent_science_reviewer"
    assert holdout["minimum_cases_per_rule"] == 2
    assert holdout["expected_minimum_case_count"] == 88
    assert holdout["required_non_spin_majority"] is True
    assert "actual holdout claims are not stored" in body.lower()


def test_qualification_cli_writes_reproducible_preflight_report(tmp_path: Path) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "qualify_science_release.py"),
        "--boi-root",
        str(BOI_ROOT),
        "--release-id",
        RELEASE_ID,
    ]
    first_run = subprocess.run(
        [*command, "--output", str(first)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    second_run = subprocess.run(
        [*command, "--output", str(second)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert first_run.returncode == 0, first_run.stderr
    assert second_run.returncode == 0, second_run.stderr
    assert first.read_bytes() == second.read_bytes()
    report = first.read_text(encoding="utf-8")
    assert "G0 | PASS" in report
    assert "G4 | PASS" in report
    assert "G5 | PENDING" in report
    assert "G7 | PENDING" in report
    assert "Aggregate score" not in report
    assert "False-red: 0" in report
    assert "Broken Evidence locators: 0" in report
    assert "Ungrounded explanation facts: 0" in report
    assert "Nondeterministic cases: 0" in report
    assert re.search(r"Release digest: `sha256:[0-9a-f]{64}`", report)


def test_committed_preflight_report_matches_current_release() -> None:
    result = qualify_release_candidate(BOI_ROOT, RELEASE_ID)
    report = PREFLIGHT_PATH.read_text(encoding="utf-8")

    assert result.release_digest in report
    assert result.result_digest in report
    assert "Public cases: 440" in report
    assert "G5 | PENDING" in report
    assert "G6 | PENDING" in report
    assert "G7 | PENDING" in report
    assert json.dumps(result.component_digests, sort_keys=True) not in report
    assert "activation_eligible: false" in report


def test_release_frontmatter_is_canonical_json_not_yaml_implicit_types() -> None:
    raw = RELEASE_PATH.read_text(encoding="utf-8")
    frontmatter = raw.split("---", 2)[1]
    parsed = yaml.safe_load(frontmatter)

    assert json.loads(frontmatter) == parsed
    assert parsed["science"]["status"] == "release_candidate"


def _rewrite_json_frontmatter(path: Path, mutate) -> None:
    metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
    mutate(metadata)
    path.write_text(
        "---\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n---\n"
        + body.lstrip("\n"),
        encoding="utf-8",
    )


def test_candidate_builder_rejects_malformed_locator_before_repinning(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "boi"
    shutil.copytree(BOI_ROOT, copied_root)
    evidence_path = (
        copied_root
        / "public"
        / "science"
        / "evidence"
        / "common"
        / "quantity-unit-dimension.md"
    )
    _rewrite_json_frontmatter(
        evidence_path,
        lambda metadata: metadata["science"].update({"locator": {"junk": "x"}}),
    )

    run = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "build_science_release_candidate.py"),
            "--boi-root",
            str(copied_root),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert run.returncode != 0
    assert "closed medium-specific Evidence locator" in run.stderr


def test_candidate_builder_rejects_short_source_hash_before_repinning(
    tmp_path: Path,
) -> None:
    copied_root = tmp_path / "boi"
    shutil.copytree(BOI_ROOT, copied_root)
    source_path = (
        copied_root
        / "public"
        / "science"
        / "sources"
        / "bipm-si-brochure-9-v4-01.md"
    )
    _rewrite_json_frontmatter(
        source_path,
        lambda metadata: metadata["science"].update(
            {"content_hash": "sha256:deadbeef"}
        ),
    )

    run = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "build_science_release_candidate.py"),
            "--boi-root",
            str(copied_root),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert run.returncode != 0
    assert "exact SHA-256 digest" in run.stderr
