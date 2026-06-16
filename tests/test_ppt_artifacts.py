from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from scripts.insert_poc_screenshots import load_manifest, missing_screenshots


def test_capture_manifest_lists_required_executive_screenshots():
    manifest = load_manifest(Path("artifacts/boi-poc/capture-manifest.json"))

    assert manifest["capture_dir"] == "captures/boi-poc"
    assert len(manifest["required"]) == 8
    assert [entry["file"] for entry in manifest["required"][:3]] == [
        "01-boi-wiki-home.png",
        "02-sop-library.png",
        "03-event-type-catalog.png",
    ]
    assert any(entry["id"] == "langflow" and "7860" in entry["url"] for entry in manifest["required"])
    assert any(entry["id"] == "kafka_ui" and "8081" in entry["url"] for entry in manifest["required"])


def test_insert_script_detects_missing_screenshots_before_final_output():
    manifest = load_manifest(Path("artifacts/boi-poc/capture-manifest.json"))

    missing = missing_screenshots(manifest)

    assert missing
    assert missing[0].name == "01-boi-wiki-home.png"


def test_executive_ppt_contains_capture_slot_and_technical_appendix():
    prs = Presentation("artifacts/boi-poc/boi-wiki-poc-executive-brief.pptx")
    all_text = "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text"))

    assert len(prs.slides) == 15
    assert "실제 화면 캡처 삽입 계획" in all_text
    assert "Appendix A. 기술 구성" in all_text
    assert "google/gemma-4-26b-a4b-qat" in all_text
