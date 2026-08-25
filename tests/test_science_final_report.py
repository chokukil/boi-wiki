from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_final_report_separates_implementation_from_release_activation(tmp_path: Path) -> None:
    output = tmp_path / "report"
    subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/build_science_verification_report.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output),
            "--git-commit",
            "fixture-commit",
            "--generated-at",
            "2026-08-25T20:00:00+09:00",
            "--science-tests",
            "1390",
            "--mcp-tests",
            "14",
            "--browser-checks",
            "16",
            "--full-regression-tests",
            "1",
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    markdown = (output / "qualification-report.md").read_text(encoding="utf-8")
    pdf = (output / "qualification-report.pdf").read_bytes()
    manifest = json.loads((output / "verification-manifest.json").read_text())

    assert "구현 상태: VERIFIED" in markdown
    assert "Science Knowledge Release: NOT ACTIVE" in markdown
    assert "G5 | PENDING" in markdown
    assert "G6 | PENDING" in markdown
    assert "G7 | PENDING" in markdown
    assert "Activation eligible: `false`" in markdown
    assert "Qwen 연결 불가 / timeout / 빈 content / invalid JSON / schema mismatch" in markdown
    assert pdf.startswith(b"%PDF") and len(pdf) > 10_000
    assert manifest["activation_eligible"] is False
    assert manifest["gates"] == {
        "G0": "PASS",
        "G1": "PASS",
        "G2": "PASS",
        "G3": "PASS",
        "G4": "PASS",
        "G5": "PENDING",
        "G6": "PENDING",
        "G7": "PENDING",
    }
