from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from scripts.collect_poc_evidence import build_capture_targets
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


def test_capture_targets_resolve_latest_private_boi_and_langflow_urls():
    evidence = {
        "collected_at": "2026-06-17T00:00:00+00:00",
        "git_commit": "abc123",
        "boi_docs": {
            "items": [
                {
                    "event_type": "corrective_action.requested.v1",
                    "uri": "/private/100001/boi-private-corrective.md",
                }
            ]
        },
        "langflow_smoke": {"flow": {"id": "flow-123"}},
    }

    targets = build_capture_targets(
        evidence,
        Path("artifacts/boi-poc/capture-manifest.json"),
        "http://localhost:8000",
        "http://localhost:7860",
    )
    by_id = {target["id"]: target for target in targets["targets"]}

    assert by_id["private_boi"]["url"] == "http://localhost:8000/docs/private/100001/boi-private-corrective.md"
    assert by_id["langflow"]["url"] == "http://localhost:7860/flow/flow-123"
    assert "<latest" not in by_id["private_boi"]["url"]
    assert "<latest" not in by_id["langflow"]["url"]


def test_e2e_ppt_build_script_preserves_artifact_tool_boundary():
    script = Path("scripts/build_boi_e2e_ppt.py").read_text(encoding="utf-8")
    status = Path("artifacts/boi-poc/ppt-production-status.md").read_text(encoding="utf-8")

    assert "check_presentation_runtime.mjs" in script
    assert "build_artifact_deck.mjs" in script
    assert "--slide-count" in script
    assert "EXPECTED_SLIDE_COUNT = 8" in script
    assert "python scripts/build_boi_e2e_ppt.py" in status
    assert "artifact-tool runtime preflight" in status


def test_capture_targets_point_to_latest_sso_e2e_trace():
    manifest = Path("artifacts/boi-poc/capture-manifest.json").read_text(encoding="utf-8")
    targets = Path("artifacts/boi-poc/capture-targets.json").read_text(encoding="utf-8")
    docs_manifest = Path("docs/POC_SCREENSHOT_MANIFEST.md").read_text(encoding="utf-8")
    combined = "\n".join([manifest, targets, docs_manifest])

    assert "trace-609660cf137c4946aaa833c891f704b7" in combined
    assert "boi:private:100001:20260619014436:7ff90d" in combined
    assert "422fa3e4-d09b-4d51-b323-e652a13f2792" in combined
    assert "3aba3309-89a8-4171-a153-00db6b16dcba" not in combined
    assert "boi-private-100001-20260618012251-15654c.md" not in combined


def test_capture_target_preflight_checks_boi_langflow_and_kafka_urls():
    script = Path("scripts/check_poc_capture_targets.py").read_text(encoding="utf-8")

    assert "x-service-token" in script
    assert "/api/v1/flows/" in script
    assert "flow id not found in Langflow API" in script
    assert "trace-609660cf137c4946aaa833c891f704b7" in script
    assert "boi:private:100001:20260619014436:7ff90d" in script
