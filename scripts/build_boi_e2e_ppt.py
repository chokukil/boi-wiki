#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SKILL_DIR = Path(
    "/mnt/c/Users/choku/.codex/plugins/cache/openai-primary-runtime/"
    "presentations/26.520.11634/skills/presentations"
)
DEFAULT_WORKSPACE = ROOT / "outputs/manual-20260619/presentations/boi-e2e-evidence"
DEFAULT_OUTPUT = DEFAULT_WORKSPACE / "output/boi-wiki-e2e-evidence-brief.pptx"
DEFAULT_CAPTURE_MANIFEST = ROOT / "artifacts" / "boi-poc" / "capture-manifest.json"
EXPECTED_SLIDE_COUNT = 8


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")


def verify_slide_modules(slides_dir: Path) -> None:
    require_file(slides_dir, "slides directory")
    expected = [slides_dir / f"slide-{index:02d}.mjs" for index in range(1, EXPECTED_SLIDE_COUNT + 1)]
    missing = [path for path in expected if not path.exists()]
    if missing:
        rendered = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Missing slide modules:\n{rendered}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the latest BoI Wiki E2E evidence PPTX with artifact-tool.")
    parser.add_argument("--skill-dir", type=Path, default=Path(os.getenv("PRESENTATIONS_SKILL_DIR", DEFAULT_SKILL_DIR)))
    parser.add_argument("--workspace", type=Path, default=Path(os.getenv("BOI_E2E_PPT_WORKSPACE", DEFAULT_WORKSPACE)))
    parser.add_argument("--out", type=Path, default=Path(os.getenv("BOI_E2E_PPT_OUT", DEFAULT_OUTPUT)))
    parser.add_argument("--capture-manifest", type=Path, default=Path(os.getenv("BOI_CAPTURE_MANIFEST", DEFAULT_CAPTURE_MANIFEST)))
    parser.add_argument("--skip-runtime-check", action="store_true", help="Attempt build without running check_presentation_runtime.mjs first.")
    parser.add_argument("--skip-screenshot-check", action="store_true", help="Build without validating required screenshot evidence first.")
    args = parser.parse_args()

    skill_dir = args.skill_dir.resolve()
    workspace = args.workspace.resolve()
    slides_dir = workspace / "slides"
    out = args.out.resolve()
    preview_dir = workspace / "preview"
    layout_dir = workspace / "layout/final"
    contact_sheet = workspace / "preview/contact-sheet.png"
    qa_dir = workspace / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    require_file(skill_dir / "scripts/build_artifact_deck.mjs", "artifact-tool deck builder")
    verify_slide_modules(slides_dir)

    if not args.skip_screenshot_check:
        screenshot_check = run(
            [
                sys.executable,
                "scripts/insert_poc_screenshots.py",
                "--manifest",
                str(args.capture_manifest.resolve()),
                "--check",
            ]
        )
        (qa_dir / "screenshot-readiness-check.txt").write_text(screenshot_check.stdout, encoding="utf-8")
        if screenshot_check.returncode != 0:
            sys.stderr.write(screenshot_check.stdout)
            sys.stderr.write(
                "\nPPTX export stopped before build: required screenshot evidence is not ready. "
                "Capture the required PNG files or use --skip-screenshot-check only for non-final local drafts.\n"
            )
            return screenshot_check.returncode

    if not args.skip_runtime_check:
        runtime_check = run(
            [
                "node",
                str(skill_dir / "scripts/check_presentation_runtime.mjs"),
                "--workspace",
                str(workspace),
            ]
        )
        (qa_dir / "artifact-runtime-check.txt").write_text(runtime_check.stdout, encoding="utf-8")
        if runtime_check.returncode != 0:
            sys.stderr.write(runtime_check.stdout)
            sys.stderr.write(
                "\nPPTX export stopped before build: artifact-tool runtime is unavailable. "
                "Restore the Codex primary runtime @oai/artifact-tool package, then rerun this script.\n"
            )
            return runtime_check.returncode

    build = run(
        [
            "node",
            str(skill_dir / "scripts/build_artifact_deck.mjs"),
            "--workspace",
            str(workspace),
            "--slides-dir",
            str(slides_dir),
            "--out",
            str(out),
            "--preview-dir",
            str(preview_dir),
            "--layout-dir",
            str(layout_dir),
            "--contact-sheet",
            str(contact_sheet),
            "--slide-count",
            str(EXPECTED_SLIDE_COUNT),
        ]
    )
    (qa_dir / "artifact-build.log").write_text(build.stdout, encoding="utf-8")
    if build.returncode != 0:
        sys.stderr.write(build.stdout)
        return build.returncode
    if not out.exists() or out.stat().st_size <= 0:
        sys.stderr.write(f"Expected non-empty PPTX output was not created: {out}\n")
        return 1

    print(f"Built PPTX: {out}")
    print(f"Contact sheet: {contact_sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
