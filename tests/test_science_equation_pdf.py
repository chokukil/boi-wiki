from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pypdfium2 as pdfium
import pytest
from reportlab.graphics.shapes import Drawing

from boi_api.app.science.equation_rendering import (
    EquationSVGConversionError,
    EquationSVGValidationError,
    equation_svg_to_drawing,
    render_equation_pdf,
    safe_equation_svg_to_drawing,
    validate_equation_svg,
)


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts" / "science_equation_renderer.mjs"


def _render(latex: str, reading: str = "검증된 수식") -> tuple[str, str]:
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
    payload = json.loads(completed.stdout)
    return str(payload["svg"]), str(payload["svg_digest"])


@pytest.mark.parametrize(
    "latex",
    [
        r"I=\frac{V}{R}",  # fraction
        r"x^2+x_i",  # exponent and subscript
        r"\Delta E=\hbar\omega",  # Greek
        r"\sum_{i=1}^{n}x_i",  # summation
        r"\int_0^L E(x)\,\mathrm{d}x",  # integral and differential
        r"\begin{bmatrix}a&b\\c&d\end{bmatrix}",  # matrix
        r"\vec{F}=m\vec{a}",  # vector
        r"\ce{2H2 + O2 -> 2H2O}",  # chemical reaction
    ],
)
def test_real_mathjax_svg_converts_to_reportlab_drawing(latex: str) -> None:
    svg, digest = _render(latex)

    drawing = equation_svg_to_drawing(svg, digest)
    pdf = render_equation_pdf(svg, digest)

    assert isinstance(drawing, Drawing)
    assert drawing.width > 0
    assert drawing.height > 0
    assert len(drawing.contents) > 0
    assert pdf.startswith(b"%PDF-")


def test_validated_svg_preserves_exact_bytes_and_digest() -> None:
    first_svg, first_digest = _render(
        r"h\propto\omega^{-1/2}",
        "두께는 각속도의 제곱근 역수에 비례",
    )
    second_svg, second_digest = _render(
        r"h\propto\omega^{-1/2}",
        "두께는 각속도의 제곱근 역수에 비례",
    )

    validated = validate_equation_svg(first_svg, first_digest)

    assert first_svg.encode("utf-8") == validated.svg_bytes
    assert first_digest == second_digest == validated.svg_digest
    assert first_svg == second_svg
    assert first_digest == "sha256:" + hashlib.sha256(
        first_svg.encode("utf-8")
    ).hexdigest()
    assert validated.accessibility_reading == "두께는 각속도의 제곱근 역수에 비례"


def test_real_equation_drawing_is_embedded_on_one_pdf_page() -> None:
    svg, digest = _render(
        r"\sigma=q(n\mu_n+p\mu_p)",
        "전도도는 전하량과 전자 및 정공 이동도 항의 합의 곱",
    )

    pdf = render_equation_pdf(svg, digest)
    document = pdfium.PdfDocument(pdf)
    page = document[0]
    bitmap = page.render(scale=1)
    image = bitmap.to_pil().convert("L")

    assert pdf.startswith(b"%PDF-")
    assert len(document) == 1
    assert image.getextrema()[0] < 250


def _digest(svg: str | bytes) -> str:
    raw = svg.encode("utf-8") if isinstance(svg, str) else svg
    return "sha256:" + hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    "svg",
    [
        '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>',
        '<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><image href="file:///etc/passwd"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><a href="https://example.invalid"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><use href="#glyph"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path style="fill:red" d="M0 0"/></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path unknown="x" d="M0 0"/></svg>',
        '<svg xmlns="https://example.invalid/svg"><path d="M0 0"/></svg>',
        '<?xml-stylesheet href="https://example.invalid/x.css"?>'
        '<svg xmlns="http://www.w3.org/2000/svg"/>',
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:evil="https://example.invalid"/>',
        '<svg xmlns="http://www.w3.org/2000/svg"><!-- hidden --></svg>',
        '<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/>text</svg>',
    ],
)
def test_malicious_or_referential_svg_is_rejected(svg: str) -> None:
    with pytest.raises(EquationSVGValidationError):
        validate_equation_svg(svg, _digest(svg))


@pytest.mark.parametrize(
    "preamble",
    [
        '<!DOCTYPE svg SYSTEM "file:///etc/passwd">',
        '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>',
        '<!ENTITY xxe SYSTEM "file:///etc/passwd">',
    ],
)
def test_doctype_and_entity_declarations_are_rejected(preamble: str) -> None:
    svg = f'{preamble}<svg xmlns="http://www.w3.org/2000/svg"/>'

    with pytest.raises(EquationSVGValidationError):
        validate_equation_svg(svg, _digest(svg))


def test_oversize_svg_is_rejected_before_xml_conversion() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" aria-label="x">'
        + (" " * (512 * 1024))
        + "</svg>"
    )

    with pytest.raises(EquationSVGValidationError, match="512 KiB"):
        validate_equation_svg(svg, _digest(svg))


def test_tampered_or_malformed_digest_is_rejected() -> None:
    svg, digest = _render(r"E=mc^2")

    with pytest.raises(EquationSVGValidationError, match="digest mismatch"):
        validate_equation_svg(svg + " ", digest)
    with pytest.raises(EquationSVGValidationError, match="digest format"):
        validate_equation_svg(svg, "not-a-digest")


def test_invalid_utf8_and_malformed_xml_are_rejected() -> None:
    invalid_utf8 = b"\xff\xfe"
    malformed = '<svg xmlns="http://www.w3.org/2000/svg">'

    with pytest.raises(EquationSVGValidationError, match="UTF-8"):
        validate_equation_svg(invalid_utf8, _digest(invalid_utf8))
    with pytest.raises(EquationSVGValidationError, match="well-formed"):
        validate_equation_svg(malformed, _digest(malformed))


def test_svglib_conversion_failure_is_wrapped_and_safe_path_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svg, digest = _render(r"V=IR")

    monkeypatch.setattr(
        "boi_api.app.science.equation_rendering._load_svg_converter",
        lambda: (lambda *_args, **_kwargs: None),
    )

    with pytest.raises(EquationSVGConversionError):
        equation_svg_to_drawing(svg, digest)
    assert safe_equation_svg_to_drawing(svg, digest) is None


def test_missing_optional_svglib_fails_only_the_safe_presentation_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svg, digest = _render(r"V=IR")

    def missing_converter():
        raise ModuleNotFoundError("svglib is not installed")

    monkeypatch.setattr(
        "boi_api.app.science.equation_rendering._load_svg_converter",
        missing_converter,
    )

    with pytest.raises(EquationSVGConversionError):
        equation_svg_to_drawing(svg, digest)
    assert safe_equation_svg_to_drawing(svg, digest) is None


def test_safe_conversion_failure_has_no_verdict_or_red_mark_side_effect() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><script/></svg>'
    verdict_state = {"verdict": "CONTRADICTED", "red_mark": True}

    drawing = safe_equation_svg_to_drawing(svg, _digest(svg))

    assert drawing is None
    assert verdict_state == {"verdict": "CONTRADICTED", "red_mark": True}
