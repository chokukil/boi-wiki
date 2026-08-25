from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw
from pptx import Presentation


REPO_ROOT = Path(__file__).resolve().parents[1]
DECK_ROOT = REPO_ROOT / "artifacts/science-verifier/deck"
DECK_BUILDER = REPO_ROOT / "scripts/build_science_verifier_deck.mjs"
DEFAULT_NODE_MODULES = Path(
    "/mnt/c/Users/choku/.cache/codex-runtimes/codex-primary-runtime/"
    "dependencies/node/node_modules"
)
REQUIRED_BROWSER_CHECK_IDS = [
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
    "equation_committed_asset_renders_exact_svg",
    "equation_identity_and_evidence_visible",
    "equation_details_copy_and_accessibility",
    "equation_failures_keep_plain_fallback_without_red",
    "equation_mobile_scroll_is_contained",
    "equation_qa_is_explicitly_non_operational",
    "wiki_selection_handoff",
    "wiki_local_revision_preserves_lineage",
    "console_clean",
]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _node_can_load(module: Path) -> bool:
    result = subprocess.run(
        ["node", "-e", f"require({json.dumps(str(module))})"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _deck_node_modules(repo: Path) -> Path:
    configured = Path(os.getenv("CODEX_NODE_MODULES", DEFAULT_NODE_MODULES))
    if _node_can_load(configured / "pptxgenjs") and _node_can_load(
        configured / "sharp"
    ):
        return configured

    sharp_packages = []
    for pattern in (
        "*/node_modules/sharp/package.json",
        "*/*/node_modules/sharp/package.json",
        ".nvm/versions/node/*/lib/node_modules/*/node_modules/sharp/package.json",
    ):
        sharp_packages.extend(Path.home().glob(pattern))
    sharp = next(
        (
            package.parent
            for package in sharp_packages
            if _node_can_load(package.parent)
        ),
        None,
    )
    if sharp is None or not _node_can_load(configured / "pptxgenjs"):
        raise RuntimeError("tests require loadable pptxgenjs and Linux sharp modules")

    node_modules = repo / ".test-node-modules"
    node_modules.mkdir()
    (node_modules / "pptxgenjs").symlink_to(
        configured / "pptxgenjs", target_is_directory=True
    )
    (node_modules / "sharp").symlink_to(sharp, target_is_directory=True)
    return node_modules


def _science_deck_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "deck-repo"
    assets = repo / "artifacts/science-verifier/deck/assets"
    assets.mkdir(parents=True)
    (repo / "tracked-source.txt").write_text("reviewed\n", encoding="utf-8")
    _git(repo, "init")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "Science Deck Tests")
    _git(repo, "add", "tracked-source.txt")
    _git(repo, "commit", "-m", "fixture")
    commit = _git(repo, "rev-parse", "HEAD")

    Image.new("RGB", (160, 90), "#dbeafe").save(assets / "science-integrity-layer.png")
    ui_path = assets / "review-canvas-desktop.png"
    Image.new("RGB", (120, 180), "#0f766e").save(ui_path)
    stale_report = assets / "final-qualification-report.png"
    Image.new("RGB", (13, 17), "#ff00ff").save(stale_report)

    report_pdf = repo / "artifacts/science-verifier/qualification-report.pdf"
    report_page = Image.new("RGB", (240, 320), "white")
    draw = ImageDraw.Draw(report_page)
    draw.rectangle((20, 20, 220, 120), fill="#111827")
    draw.rectangle((20, 150, 220, 300), fill="#16a34a")
    report_page.save(report_pdf, "PDF", resolution=72.0)

    ui_digest = _sha256(ui_path)
    manifest = {
        "schema_version": "science-verifier-evidence-manifest/0.2",
        "report_state": "FINAL",
        "implementation_status": "VERIFIED",
        "failure_reasons": [],
        "git": {"commit": commit, "dirty": False},
        "activation_eligible": False,
        "evidence": {
            "browser": {
                "passed": True,
                "check_results": [
                    {"check_id": check_id, "status": "passed"}
                    for check_id in REQUIRED_BROWSER_CHECK_IDS
                ],
                "capture_files": [
                    {
                        "path": "review-canvas-desktop.png",
                        "sha256": ui_digest,
                        "actual_sha256": ui_digest,
                    }
                ],
            },
            "qualification": {
                "lifecycle": "release_candidate",
                "activation_eligible": False,
                "public_case_count": 1,
            },
            "independent_review": {
                "passed": True,
                "findings": {"critical": 0, "important": 0, "advisory": 0},
            },
        },
        "gates": {
            "G0": "PASS",
            "G1": "PASS",
            "G2": "PASS",
            "G3": "PASS",
            "G4": "PASS",
            "G5": "PENDING",
            "G6": "PENDING",
            "G7": "PENDING",
        },
        "qualification_result_digest": "sha256:" + "1" * 64,
        "report_record_digest": "sha256:" + "2" * 64,
        "pdf": {
            "path": "artifacts/science-verifier/qualification-report.pdf",
            "sha256": _sha256(report_pdf),
        },
    }
    verification_path = repo / "artifacts/science-verifier/verification-manifest.json"
    verification_path.write_text(json.dumps(manifest), encoding="utf-8")
    return repo, stale_report


def _run_deck_builder(
    repo: Path, *, python: str | None = None
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["BOI_PYTHON"] = python or shutil.which("python3.11") or "python3.11"
    environment["CODEX_NODE_MODULES"] = str(_deck_node_modules(repo))
    dependencies = str(REPO_ROOT.parent / ".py311deps")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (dependencies, environment.get("PYTHONPATH", "")) if part
    )
    return subprocess.run(
        ["node", str(DECK_BUILDER), str(repo)],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_science_deck_builder_is_fail_closed_and_manifest_bound() -> None:
    source = DECK_BUILDER.read_text(encoding="utf-8")

    assert 'verification.report_state === "FINAL"' in source
    assert 'verification.implementation_status === "VERIFIED"' in source
    assert "requiredBrowserCheckIds" in source
    assert "browserCheckIds.size === requiredBrowserCheckIds.length" in source
    assert "reviewEvidence?.findings?.important === 0" in source
    assert "verification.git?.commit === currentCommit" in source
    assert "qualification report PDF does not match verification manifest" in source
    assert 'pptx.layout = "LAYOUT_WIDE"' in source
    assert "slide_count: 3" in source
    assert "visual inspection: PENDING" in source
    assert "visual inspection: PASS" not in source


def test_science_deck_builder_rejects_tracked_changes_but_allows_untracked_outputs(
    tmp_path: Path,
) -> None:
    repo, _ = _science_deck_repo(tmp_path)
    (repo / "tracked-source.txt").write_text("tampered\n", encoding="utf-8")

    result = _run_deck_builder(repo)

    assert result.returncode != 0
    assert "tracked files differ from HEAD" in result.stderr
    assert not (repo / "artifacts/science-verifier/deck/build-manifest.json").exists()


def test_science_deck_builder_rejects_tampered_desktop_capture(
    tmp_path: Path,
) -> None:
    repo, _ = _science_deck_repo(tmp_path)
    Image.new("RGB", (120, 180), "#dc2626").save(
        repo / "artifacts/science-verifier/deck/assets/review-canvas-desktop.png"
    )

    result = _run_deck_builder(repo)

    assert result.returncode != 0
    assert "desktop UI capture does not match browser evidence" in result.stderr
    assert not (repo / "artifacts/science-verifier/deck/build-manifest.json").exists()


def test_science_deck_builder_rejects_missing_equation_browser_check(
    tmp_path: Path,
) -> None:
    repo, _ = _science_deck_repo(tmp_path)
    verification_path = repo / "artifacts/science-verifier/verification-manifest.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8"))
    verification["evidence"]["browser"]["check_results"] = [
        check
        for check in verification["evidence"]["browser"]["check_results"]
        if check["check_id"] != "equation_failures_keep_plain_fallback_without_red"
    ]
    verification_path.write_text(json.dumps(verification), encoding="utf-8")

    result = _run_deck_builder(repo)

    assert result.returncode != 0
    assert "non-final or unbound verification manifest" in result.stderr
    assert not (repo / "artifacts/science-verifier/deck/build-manifest.json").exists()


def test_science_deck_builder_overwrites_stale_report_png_from_verified_pdf(
    tmp_path: Path,
) -> None:
    repo, report_png = _science_deck_repo(tmp_path)
    stale_digest = _sha256(report_png)

    result = _run_deck_builder(repo)

    assert result.returncode == 0, result.stderr
    assert _sha256(report_png) != stale_digest
    with Image.open(report_png) as rendered:
        assert rendered.size == (480, 640)
        red, green, blue = rendered.convert("RGB").getpixel((240, 450))
        assert green > red * 2
        assert green > blue * 2
    build_manifest = json.loads(
        (repo / "artifacts/science-verifier/deck/build-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert build_manifest["inputs"]["report"]["sha256"] == _sha256(report_png)


def test_science_deck_builder_fails_closed_when_python_override_is_invalid(
    tmp_path: Path,
) -> None:
    repo, report_png = _science_deck_repo(tmp_path)
    stale_digest = _sha256(report_png)

    result = _run_deck_builder(repo, python=str(repo / "missing-python"))

    assert result.returncode != 0
    assert _sha256(report_png) == stale_digest
    assert not (repo / "artifacts/science-verifier/deck/build-manifest.json").exists()


def test_generated_science_evidence_deck_when_explicitly_requested() -> None:
    if os.getenv("BOI_VERIFY_GENERATED_SCIENCE_ARTIFACTS") != "1":
        return
    pptx_path = DECK_ROOT / "science-verifier-evidence.pptx"
    manifest = json.loads((DECK_ROOT / "build-manifest.json").read_text())
    verification = json.loads(
        (
            REPO_ROOT / "artifacts/science-verifier/verification-manifest.json"
        ).read_text()
    )
    presentation = Presentation(pptx_path)

    assert len(presentation.slides) == 3
    assert manifest["slide_count"] == 3
    assert manifest["release_status"] == "release_candidate"
    assert manifest["activation_eligible"] is False
    assert manifest["evidence_binding"]["git_commit"] == verification["git"]["commit"]
    assert (
        manifest["evidence_binding"]["report_record_digest"]
        == verification["report_record_digest"]
    )
    assert manifest["evidence_binding"]["browser_checks"] == len(
        REQUIRED_BROWSER_CHECK_IDS
    )
    assert manifest["evidence_binding"]["public_cases"] == 440
    assert "G5" in " ".join(
        shape.text
        for slide in presentation.slides
        for shape in slide.shapes
        if hasattr(shape, "text")
    )

    for number in (1, 2, 3):
        path = DECK_ROOT / f"rendered/slide-{number}.png"
        with Image.open(path) as image:
            assert image.size == (1600, 900)

    assert (DECK_ROOT / "rendered/whole-deck.png").stat().st_size > 50_000
    assert (
        DECK_ROOT / "rendered/representative-evidence-slide.png"
    ).stat().st_size > 50_000
