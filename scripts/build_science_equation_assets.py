#!/usr/bin/env python3
"""Render deterministic, non-authoritative SVG assets for Science equations."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.science.catalog import ScienceCatalog  # noqa: E402
from boi_api.app.science.digests import sha256_digest  # noqa: E402
from boi_api.app.science.equation_assets import (  # noqa: E402
    EquationAssetManifest,
    EquationPresentationAsset,
)


def _render(renderer: Path, latex: str, reading: str) -> dict:
    completed = subprocess.run(
        ["node", str(renderer)],
        input=json.dumps(
            {
                "latex": latex,
                "accessibility_reading": reading,
                "display": True,
            },
            ensure_ascii=False,
        ),
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError("local Equation renderer failed closed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("local Equation renderer returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("local Equation renderer returned invalid output")
    return payload


def build_manifest(repo_root: Path) -> EquationAssetManifest:
    catalog = ScienceCatalog(repo_root / "data/boi")
    renderer = repo_root / "scripts/science_equation_renderer.mjs"
    equation_ids = sorted(catalog._equations)
    assets: list[dict] = []
    for equation_id in equation_ids:
        equation = catalog.equation(equation_id).equation
        rendered = _render(
            renderer, equation.display_latex, equation.accessibility_reading
        )
        asset = {
            "equation_id": equation.equation_id,
            "equation_digest": equation.equation_digest,
            "display_latex": equation.display_latex,
            "plain_text": equation.plain_text,
            "accessibility_reading": equation.accessibility_reading,
            "sanitized_svg": rendered.get("svg"),
            "svg_digest": rendered.get("svg_digest"),
            "renderer": rendered.get("renderer"),
            "asset_digest": "",
        }
        asset["asset_digest"] = sha256_digest(
            {key: value for key, value in asset.items() if key != "asset_digest"}
        )
        assets.append(
            EquationPresentationAsset.model_validate(asset).model_dump(mode="json")
        )
    payload = {
        "schema_version": "science-equation-assets/0.1",
        "assets": assets,
        "manifest_digest": "",
    }
    payload["manifest_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "manifest_digest"}
    )
    return EquationAssetManifest.model_validate(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output = (
        args.output.resolve()
        if args.output
        else repo_root / "boi_api/app/static/science-equations.json"
    )
    manifest = build_manifest(repo_root)
    rendered = (
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=2)
        + "\n"
    )
    if args.check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError:
            current = ""
        if current != rendered:
            print("Science Equation presentation assets are stale", file=sys.stderr)
            return 1
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "asset_count": len(manifest.assets),
                "manifest_digest": manifest.manifest_digest,
                "verdict_effect": "none",
                "red_mark_effect": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
