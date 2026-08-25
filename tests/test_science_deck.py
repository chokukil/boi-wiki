from __future__ import annotations

import json
import os
from pathlib import Path

from PIL import Image
from pptx import Presentation


REPO_ROOT = Path(__file__).resolve().parents[1]
DECK_ROOT = REPO_ROOT / "artifacts/science-verifier/deck"
DECK_BUILDER = REPO_ROOT / "scripts/build_science_verifier_deck.mjs"


def test_science_deck_builder_is_fail_closed_and_manifest_bound() -> None:
    source = DECK_BUILDER.read_text(encoding="utf-8")

    assert 'verification.report_state === "FINAL"' in source
    assert 'verification.implementation_status === "VERIFIED"' in source
    assert "browserChecks.length === 20" in source
    assert 'reviewEvidence?.findings?.important === 0' in source
    assert 'verification.git?.commit === currentCommit' in source
    assert "qualification report PDF does not match verification manifest" in source
    assert 'pptx.layout = "LAYOUT_WIDE"' in source
    assert "slide_count: 3" in source


def test_generated_science_evidence_deck_when_explicitly_requested() -> None:
    if os.getenv("BOI_VERIFY_GENERATED_SCIENCE_ARTIFACTS") != "1":
        return
    pptx_path = DECK_ROOT / "science-verifier-evidence.pptx"
    manifest = json.loads((DECK_ROOT / "build-manifest.json").read_text())
    verification = json.loads(
        (REPO_ROOT / "artifacts/science-verifier/verification-manifest.json").read_text()
    )
    presentation = Presentation(pptx_path)

    assert len(presentation.slides) == 3
    assert manifest["slide_count"] == 3
    assert manifest["release_status"] == "release_candidate"
    assert manifest["activation_eligible"] is False
    assert manifest["evidence_binding"]["git_commit"] == verification["git"]["commit"]
    assert manifest["evidence_binding"]["report_record_digest"] == verification["report_record_digest"]
    assert manifest["evidence_binding"]["browser_checks"] == 20
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
    assert (DECK_ROOT / "rendered/representative-evidence-slide.png").stat().st_size > 50_000
