from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "science_equation_renderer.mjs"


def _render(latex: str, reading: str = "검증된 수식") -> dict[str, object]:
    completed = subprocess.run(
        ["node", str(RENDERER)],
        cwd=ROOT,
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
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


@pytest.mark.parametrize(
    "latex",
    [
        r"I=\frac{V}{R}",
        r"\sigma=q(n\mu_n+p\mu_p)",
        r"\sum_{i=1}^{n}x_i",
        r"\int_0^L E(x)\,\mathrm{d}x",
        r"\begin{bmatrix}a&b\\c&d\end{bmatrix}",
        r"\vec{F}=m\vec{a}",
        r"\ce{2H2 + O2 -> 2H2O}",
    ],
)
def test_local_renderer_covers_required_scientific_notation(latex: str) -> None:
    rendered = _render(latex)

    svg = str(rendered["svg"])
    root = ElementTree.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["aria-label"] == "검증된 수식"
    assert rendered["renderer"] == {
        "engine": "MathJax",
        "version": "4.1.3",
        "output": "sanitized-svg-paths",
        "font": "MathJax-Newcm 4.1.3 with Mhchem extension 4.1.3",
    }
    assert rendered["svg_digest"] == "sha256:" + hashlib.sha256(
        svg.encode("utf-8")
    ).hexdigest()
    assert "<path" in svg
    assert "data-latex" not in svg
    assert "<script" not in svg.lower()
    assert "foreignObject" not in svg
    assert "http://" not in svg.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in svg


def test_renderer_is_byte_deterministic_for_same_input() -> None:
    first = _render(r"h\propto\omega^{-1/2}", "두께는 각속도의 제곱근 역수에 비례")
    second = _render(r"h\propto\omega^{-1/2}", "두께는 각속도의 제곱근 역수에 비례")

    assert first == second


@pytest.mark.parametrize(
    "latex",
    [
        r"\href{https://example.invalid}{x}",
        r"\url{file:///etc/passwd}",
        r"\require{html}",
        r"\include{secret}",
        r"\input{secret}",
        r"\class{evil}{x}",
        r"\style{background:url(https://example.invalid)}{x}",
        r"\notARegisteredScienceCommand{x}",
        r"\begin{bmatrix}a&b",
        "x" * 4097,
    ],
)
def test_renderer_rejects_unsafe_or_unbounded_latex(latex: str) -> None:
    completed = subprocess.run(
        ["node", str(RENDERER)],
        cwd=ROOT,
        input=json.dumps(
            {"latex": latex, "accessibility_reading": "unsafe", "display": True}
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 2
    error = json.loads(completed.stderr)
    assert error["code"] == "science_equation_render_failed"
    assert error["rendering_effect"] == "none"
    assert error["verdict_effect"] == "none"
    assert error["red_mark_effect"] == "none"


def test_math_renderer_dependencies_are_exactly_pinned() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))

    assert package["devDependencies"]["@mathjax/src"] == "4.1.3"
    assert (
        package["devDependencies"]["@mathjax/mathjax-mhchem-font-extension"]
        == "4.1.3"
    )
