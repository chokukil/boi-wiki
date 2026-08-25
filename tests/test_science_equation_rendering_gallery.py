from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from scripts.build_science_equation_rendering_gallery import (
    GalleryBuildError,
    build_gallery,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RENDERER = REPO_ROOT / "scripts/science_equation_renderer.mjs"


def test_gallery_qualifies_every_required_renderer_category_without_authority() -> None:
    gallery = build_gallery(REPO_ROOT)

    assert gallery.pdf_bytes.startswith(b"%PDF-")
    assert gallery.manifest["schema_version"] == (
        "science-equation-renderer-qualification/0.1"
    )
    assert gallery.manifest["artifact_kind"] == (
        "renderer_qualification_non_authoritative"
    )
    assert gallery.manifest["verdict_effect"] == "none"
    assert gallery.manifest["red_mark_effect"] == "none"
    assert gallery.manifest["pdf_sha256"] == (
        "sha256:" + hashlib.sha256(gallery.pdf_bytes).hexdigest()
    )
    assert [item["category"] for item in gallery.manifest["expressions"]] == [
        "fraction",
        "exponent_subscript_greek",
        "summation",
        "integral_differential",
        "vector",
        "matrix",
        "chemical_reaction_arrow",
        "korean_adjacent_explanation",
    ]
    for item in gallery.manifest["expressions"]:
        assert set(item) == {
            "category",
            "latex",
            "plain_text",
            "accessibility_reading",
            "adjacent_explanation",
            "svg_digest",
        }
        assert item["latex"]
        assert item["plain_text"]
        assert item["accessibility_reading"]
        assert item["svg_digest"].startswith("sha256:")
    korean = gallery.manifest["expressions"][-1]
    assert korean["adjacent_explanation"] == (
        "수식은 설명 옆에 표시되며, 이 갤러리는 과학적 판정 근거가 아닙니다."
    )


def test_gallery_pdf_and_manifest_are_byte_deterministic() -> None:
    first = build_gallery(REPO_ROOT)
    second = build_gallery(REPO_ROOT)

    assert first.pdf_bytes == second.pdf_bytes
    assert first.manifest == second.manifest


def test_gallery_cli_writes_the_exact_pdf_and_json_manifest(tmp_path: Path) -> None:
    pdf_path = tmp_path / "qualification.pdf"
    manifest_path = tmp_path / "qualification.json"
    completed = subprocess.run(
        [
            "python3.11",
            str(REPO_ROOT / "scripts/build_science_equation_rendering_gallery.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--pdf-output",
            str(pdf_path),
            "--manifest-output",
            str(manifest_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    status = json.loads(completed.stdout)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert status == {
        "artifact_kind": "renderer_qualification_non_authoritative",
        "expression_count": 8,
        "pdf_sha256": "sha256:" + hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "verdict_effect": "none",
        "red_mark_effect": "none",
    }
    assert manifest["pdf_sha256"] == status["pdf_sha256"]
    assert manifest_path.read_bytes().endswith(b"\n")


def test_gallery_fails_closed_when_renderer_digest_is_tampered(tmp_path: Path) -> None:
    tampered_renderer = tmp_path / "tampered-renderer.mjs"
    tampered_renderer.write_text(
        "\n".join(
            [
                'import { readFileSync } from "node:fs";',
                f'import {{ renderEquation }} from "{RENDERER.as_uri()}";',
                'const payload = renderEquation(JSON.parse(readFileSync(0, "utf8")));',
                'payload.svg_digest = `sha256:${"0".repeat(64)}`;',
                "process.stdout.write(`${JSON.stringify(payload)}\\n`);",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(GalleryBuildError, match="validation or drawing failed"):
        build_gallery(REPO_ROOT, renderer=tampered_renderer)


def test_gallery_failure_does_not_create_plaintext_only_outputs(tmp_path: Path) -> None:
    failed_renderer = tmp_path / "failed-renderer.mjs"
    failed_renderer.write_text(
        'process.stderr.write("renderer unavailable\\n"); process.exit(2);\n',
        encoding="utf-8",
    )
    pdf_path = tmp_path / "must-not-exist.pdf"
    manifest_path = tmp_path / "must-not-exist.json"

    completed = subprocess.run(
        [
            "python3.11",
            str(REPO_ROOT / "scripts/build_science_equation_rendering_gallery.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--renderer",
            str(failed_renderer),
            "--pdf-output",
            str(pdf_path),
            "--manifest-output",
            str(manifest_path),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert not pdf_path.exists()
    assert not manifest_path.exists()
    assert "renderer failed closed" in completed.stderr
