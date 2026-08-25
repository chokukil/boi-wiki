from __future__ import annotations

import json
import hashlib
import re
import shutil
import subprocess
import sys
from datetime import datetime
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


def test_g5_passes_only_for_release_bound_externally_trusted_sealed_holdout(
    tmp_path: Path,
) -> None:
    from boi_api.app.science.catalog import release_decision_material_digest
    from boi_api.app.science.digests import sha256_digest

    copied_root = tmp_path / "boi"
    shutil.copytree(BOI_ROOT, copied_root)
    catalog = ScienceCatalog(copied_root)
    release = catalog.resolve_release(RELEASE_ID)
    metadata, body = split_frontmatter(
        (copied_root / HOLDOUT_MANIFEST_PATH.relative_to(BOI_ROOT)).read_text(
            encoding="utf-8"
        )
    )
    result = {
        "schema_version": "science-holdout-result/0.1",
        "status": "passed",
        "qualification_gate": "G5",
        "release_id": release.release_id,
        "frozen_release_content_hash": release.content_hash,
        "decision_material_digest": release_decision_material_digest(release),
        "rule_digests": {
            component.ref: component.semantic_digest
            for component in release.components
            if component.kind == "rule"
        },
        "component_digests": release.component_digests,
        "case_set_digest": "sha256:" + "7" * 64,
        "sealed_case_count": 88,
    }
    result["result_digest"] = sha256_digest(result)
    metadata["status"] = "reviewed"
    metadata["review"] = {
        "reviewer": "holdout-reviewer-1",
        "reviewed_at": "2026-08-25T23:00:00+09:00",
        "review_status": "reviewed",
        "required_role": "independent_science_reviewer",
        "authorized_review_events": [],
    }
    metadata["science_holdout"] = {
        "manifest_version": "science-holdout/0.1",
        "release_id": release.release_id,
        "state": "sealed_independent_holdout",
        "external_acl_url": "boi-private://science-verifier/holdouts/science-release-0.1.0.json",
        "sealed_sha256": "sha256:" + "9" * 64,
        "rule_freeze_commit": "a" * 40,
        "reviewer": {"type": "human", "user_id": "holdout-reviewer-1"},
        "reviewer_role": "independent_science_reviewer",
        "reviewed_at": "2026-08-25T23:00:00+09:00",
        "result": result,
    }
    path = copied_root / HOLDOUT_MANIFEST_PATH.relative_to(BOI_ROOT)
    path.write_text(
        "---\n"
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + "\n---\n"
        + body.lstrip("\n"),
        encoding="utf-8",
    )
    manifest_digest = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    untrusted = qualify_release_candidate(copied_root, RELEASE_ID)
    assert untrusted.gates["G5"].status == "FAIL"

    def reviewer_roles(actor: dict[str, str]) -> set[str]:
        if actor == {"type": "human", "user_id": "holdout-reviewer-1"}:
            return {"science.independent_holdout_reviewer"}
        return set()

    def trusted_holdout(query: dict[str, str]) -> dict[str, str] | None:
        if query != {
            "release_id": release.release_id,
            "frozen_release_content_hash": release.content_hash,
        }:
            return None
        return {
            **query,
            "manifest_digest": manifest_digest,
            "rule_freeze_commit": "a" * 40,
        }

    result = qualify_release_candidate(
        copied_root,
        RELEASE_ID,
        reviewer_role_resolver=reviewer_roles,
        trusted_holdout_resolver=trusted_holdout,
        trusted_clock=lambda: datetime.fromisoformat("2026-08-25T23:30:00+09:00"),
    )

    assert result.gates["G5"].status == "PASS", result.gates["G5"].summary
    assert result.activation_eligible is False


def test_caller_provided_holdout_path_cannot_change_pending_g5(
    tmp_path: Path,
) -> None:
    asserted = tmp_path / "caller-asserted-holdout.json"
    asserted.write_text('{"status":"passed"}', encoding="utf-8")

    result = qualify_release_candidate(
        BOI_ROOT,
        RELEASE_ID,
        holdout_path=asserted,
    )

    assert result.gates["G5"].status == "PENDING"
    assert "no qualification authority" in result.gates["G5"].summary


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
