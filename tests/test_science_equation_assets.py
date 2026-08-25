from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.equation_assets import (
    EquationAssetManifest,
    default_equation_asset_manifest_path,
    equation_asset_index,
    load_equation_asset_manifest,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_committed_equation_assets_are_reproducible_and_non_authoritative() -> None:
    completed = subprocess.run(
        [
            "python3.11",
            str(REPO_ROOT / "scripts/build_science_equation_assets.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--check",
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    status = json.loads(completed.stdout)
    assert status == {
        "asset_count": 6,
        "manifest_digest": load_equation_asset_manifest().manifest_digest,
        "verdict_effect": "none",
        "red_mark_effect": "none",
    }


def test_every_asset_matches_one_exact_catalog_equation() -> None:
    catalog = ScienceCatalog(REPO_ROOT / "data/boi")
    index = equation_asset_index()

    assert len(index) == 6
    for (equation_id, equation_digest), asset in index.items():
        equation = catalog.equation(equation_id).equation
        assert equation.equation_digest == equation_digest
        assert asset.display_latex == equation.display_latex
        assert asset.plain_text == equation.plain_text
        assert asset.accessibility_reading == equation.accessibility_reading
        assert asset.renderer.engine == "MathJax"
        assert asset.renderer.version == "4.1.3"


@pytest.mark.parametrize("mutation", ["svg", "digest", "equation"])
def test_asset_manifest_rejects_render_or_equation_identity_drift(
    mutation: str,
) -> None:
    payload = json.loads(default_equation_asset_manifest_path().read_text("utf-8"))
    if mutation == "svg":
        payload["assets"][0]["sanitized_svg"] += "<!-- drift -->"
    elif mutation == "digest":
        payload["assets"][0]["svg_digest"] = "sha256:" + "0" * 64
    else:
        payload["assets"][0]["equation_digest"] = "sha256:" + "1" * 64

    with pytest.raises(ValueError):
        EquationAssetManifest.model_validate(payload)
