#!/usr/bin/env python3
"""Build the non-authoritative Science equation renderer QA gallery.

The gallery qualifies only the local presentation renderer.  It is not
Science Knowledge, Evidence, a Rule, or a verdict input.  Every expression
must render to a digest-valid path-only SVG and then convert to a real
ReportLab drawing; there is deliberately no plain-text-only success path.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Final

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.science.equation_rendering import (  # noqa: E402
    safe_equation_svg_to_drawing,
    validate_equation_svg,
)


ARTIFACT_KIND: Final = "renderer_qualification_non_authoritative"
SCHEMA_VERSION: Final = "science-equation-renderer-qualification/0.1"
EXPECTED_RENDERER: Final = {
    "engine": "MathJax",
    "version": "4.1.3",
    "output": "sanitized-svg-paths",
    "font": "MathJax-Newcm 4.1.3 with Mhchem extension 4.1.3",
}
_PDF_FONT: Final = "HYSMyeongJo-Medium"
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT: Final = 42.0
_RIGHT: Final = 42.0
_TOP: Final = 46.0
_BOTTOM: Final = 42.0


class GalleryBuildError(RuntimeError):
    """The renderer qualification gallery could not be built exactly."""


@dataclass(frozen=True, slots=True)
class QAExpression:
    category: str
    latex: str
    plain_text: str
    accessibility_reading: str
    adjacent_explanation: str = ""


@dataclass(frozen=True, slots=True)
class RenderedQAExpression:
    specification: QAExpression
    svg_digest: str
    drawing: Drawing


@dataclass(frozen=True, slots=True)
class GalleryArtifact:
    pdf_bytes: bytes
    manifest: dict[str, Any]


QA_EXPRESSIONS: Final = (
    QAExpression(
        category="fraction",
        latex=r"I=\frac{V}{R}",
        plain_text="I = V / R",
        accessibility_reading="전류 I는 전압 V를 저항 R로 나눈 값",
    ),
    QAExpression(
        category="exponent_subscript_greek",
        latex=r"\sigma=q(n\mu_n+p\mu_p)",
        plain_text="sigma = q (n mu_n + p mu_p)",
        accessibility_reading=(
            "전도도 시그마는 전하량 q와 전자 및 정공 이동도 항의 합의 곱"
        ),
    ),
    QAExpression(
        category="summation",
        latex=r"\sum_{i=1}^{n}x_i",
        plain_text="sum from i = 1 to n of x_i",
        accessibility_reading="i가 1부터 n까지인 x 아래첨자 i의 합",
    ),
    QAExpression(
        category="integral_differential",
        latex=r"\int_0^L E(x)\,\mathrm{d}x",
        plain_text="integral from 0 to L of E(x) dx",
        accessibility_reading="0부터 L까지 E x를 x에 대해 적분",
    ),
    QAExpression(
        category="vector",
        latex=r"\vec{F}=m\vec{a}",
        plain_text="vector F = m vector a",
        accessibility_reading="힘 벡터 F는 질량 m과 가속도 벡터 a의 곱",
    ),
    QAExpression(
        category="matrix",
        latex=r"\begin{bmatrix}a&b\\c&d\end{bmatrix}",
        plain_text="2 by 2 matrix [a b; c d]",
        accessibility_reading="첫째 행 a b, 둘째 행 c d인 2 곱하기 2 행렬",
    ),
    QAExpression(
        category="chemical_reaction_arrow",
        latex=r"\ce{2H2 + O2 -> 2H2O}",
        plain_text="2 H2 + O2 -> 2 H2O",
        accessibility_reading="수소 두 분자와 산소 한 분자가 물 두 분자를 생성",
    ),
    QAExpression(
        category="korean_adjacent_explanation",
        latex=r"h\propto\omega^{-1/2}",
        plain_text="h is proportional to omega to the power minus one half",
        accessibility_reading="두께 h는 각속도 오메가의 제곱근 역수에 비례",
        adjacent_explanation=(
            "수식은 설명 옆에 표시되며, 이 갤러리는 과학적 판정 근거가 아닙니다."
        ),
    ),
)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _invoke_renderer(renderer: Path, specification: QAExpression) -> dict[str, Any]:
    request = json.dumps(
        {
            "latex": specification.latex,
            "accessibility_reading": specification.accessibility_reading,
            "display": True,
        },
        ensure_ascii=False,
    )
    try:
        completed = subprocess.run(
            ["node", str(renderer)],
            input=request,
            text=True,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise GalleryBuildError("local renderer failed closed") from error
    if completed.returncode != 0:
        raise GalleryBuildError("local renderer failed closed")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise GalleryBuildError("local renderer returned invalid JSON") from error
    if not isinstance(payload, dict):
        raise GalleryBuildError("local renderer returned a non-object payload")
    return payload


def _render_expression(
    renderer: Path,
    specification: QAExpression,
) -> RenderedQAExpression:
    payload = _invoke_renderer(renderer, specification)
    if payload.get("renderer") != EXPECTED_RENDERER:
        raise GalleryBuildError(
            "local renderer identity does not match the reviewed pin"
        )
    svg = payload.get("svg")
    svg_digest = payload.get("svg_digest")
    if not isinstance(svg, str) or not isinstance(svg_digest, str):
        raise GalleryBuildError("local renderer omitted the SVG or SVG digest")

    # This safe boundary must succeed for every gallery entry.  Returning None
    # aborts the entire gallery; plain text is never treated as qualification.
    drawing = safe_equation_svg_to_drawing(svg, svg_digest)
    if drawing is None:
        raise GalleryBuildError("equation SVG validation or drawing failed closed")
    try:
        validated = validate_equation_svg(svg, svg_digest)
    except Exception as error:
        raise GalleryBuildError(
            "equation SVG validation or drawing failed closed"
        ) from error
    if validated.accessibility_reading != specification.accessibility_reading:
        raise GalleryBuildError("equation SVG accessibility reading drifted")
    return RenderedQAExpression(
        specification=specification,
        svg_digest=svg_digest,
        drawing=drawing,
    )


def _wrap_text(text: str, font_size: float, width: float) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for character in text:
        candidate = current + character
        if current and pdfmetrics.stringWidth(candidate, _PDF_FONT, font_size) > width:
            lines.append(current)
            current = character
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _render_pdf(expressions: tuple[RenderedQAExpression, ...]) -> bytes:
    if _PDF_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(_PDF_FONT))
    output = BytesIO()
    document = canvas.Canvas(
        output,
        pagesize=A4,
        invariant=1,
        pageCompression=1,
    )
    document.setTitle("Science equation renderer qualification gallery")
    document.setAuthor("BoI Wiki Science Verifier")
    usable_width = _PAGE_WIDTH - _LEFT - _RIGHT
    page_number = 1
    y = _PAGE_HEIGHT - _TOP

    def finish_page() -> None:
        document.setFont(_PDF_FONT, 7)
        document.drawString(
            _LEFT,
            20,
            f"{ARTIFACT_KIND} · verdict_effect=none · red_mark_effect=none",
        )
        document.drawRightString(_PAGE_WIDTH - _RIGHT, 20, str(page_number))

    def next_page() -> None:
        nonlocal y, page_number
        finish_page()
        document.showPage()
        page_number += 1
        y = _PAGE_HEIGHT - _TOP

    document.setFont(_PDF_FONT, 15)
    document.drawString(_LEFT, y, "Science Equation Renderer Qualification Gallery")
    y -= 22
    document.setFont(_PDF_FONT, 8)
    for line in _wrap_text(
        "비권위 렌더러 표시 자격 검증. Science Knowledge, Evidence, Rule 또는 판정이 아닙니다.",
        8,
        usable_width,
    ):
        document.drawString(_LEFT, y, line)
        y -= 11
    y -= 8

    for index, rendered in enumerate(expressions, start=1):
        specification = rendered.specification
        drawing = rendered.drawing
        max_drawing_height = 72.0
        scale = min(
            1.0,
            usable_width / float(drawing.width),
            max_drawing_height / float(drawing.height),
        )
        rendered_height = float(drawing.height) * scale
        text_lines = [
            f"{index}. {specification.category}",
            f"Plain: {specification.plain_text}",
            f"Accessibility: {specification.accessibility_reading}",
        ]
        if specification.adjacent_explanation:
            text_lines.append(specification.adjacent_explanation)
        wrapped_lines = [
            line for text in text_lines for line in _wrap_text(text, 8.0, usable_width)
        ]
        required_height = 13.0 * len(wrapped_lines) + rendered_height + 20.0
        if y - required_height < _BOTTOM:
            next_page()

        for line_number, line in enumerate(wrapped_lines):
            document.setFont(_PDF_FONT, 9 if line_number == 0 else 8)
            document.drawString(_LEFT, y, line)
            y -= 13
        document.saveState()
        try:
            document.translate(_LEFT, y - rendered_height)
            document.scale(scale, scale)
            renderPDF.draw(drawing, document, 0, 0)
        except Exception as error:
            raise GalleryBuildError(
                "ReportLab equation drawing failed closed"
            ) from error
        finally:
            document.restoreState()
        y -= rendered_height + 17.0

    try:
        finish_page()
        document.save()
    except Exception as error:
        raise GalleryBuildError("ReportLab gallery PDF failed closed") from error
    pdf_bytes = output.getvalue()
    if not pdf_bytes.startswith(b"%PDF-"):
        raise GalleryBuildError("ReportLab returned an invalid gallery PDF")
    return pdf_bytes


def build_gallery(
    repo_root: Path,
    *,
    renderer: Path | None = None,
) -> GalleryArtifact:
    """Build the complete gallery in memory or raise without an artifact."""

    resolved_root = repo_root.resolve()
    renderer_path = (
        renderer.resolve()
        if renderer is not None
        else resolved_root / "scripts/science_equation_renderer.mjs"
    )
    rendered = tuple(
        _render_expression(renderer_path, specification)
        for specification in QA_EXPRESSIONS
    )
    pdf_bytes = _render_pdf(rendered)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "artifact_kind": ARTIFACT_KIND,
        "renderer": dict(EXPECTED_RENDERER),
        "expressions": [
            {
                "category": item.specification.category,
                "latex": item.specification.latex,
                "plain_text": item.specification.plain_text,
                "accessibility_reading": item.specification.accessibility_reading,
                "adjacent_explanation": item.specification.adjacent_explanation,
                "svg_digest": item.svg_digest,
            }
            for item in rendered
        ],
        "pdf_sha256": _sha256(pdf_bytes),
        "verdict_effect": "none",
        "red_mark_effect": "none",
    }
    return GalleryArtifact(pdf_bytes=pdf_bytes, manifest=manifest)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--renderer", type=Path)
    parser.add_argument("--pdf-output", type=Path)
    parser.add_argument("--manifest-output", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    pdf_output = (
        args.pdf_output.resolve()
        if args.pdf_output
        else repo_root
        / "artifacts/science-verifier/equation-renderer-qualification.pdf"
    )
    manifest_output = (
        args.manifest_output.resolve()
        if args.manifest_output
        else repo_root
        / "artifacts/science-verifier/equation-renderer-qualification.json"
    )
    try:
        artifact = build_gallery(repo_root, renderer=args.renderer)
    except GalleryBuildError as error:
        print(str(error), file=sys.stderr)
        return 1

    pdf_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    pdf_output.write_bytes(artifact.pdf_bytes)
    manifest_output.write_text(
        json.dumps(artifact.manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "artifact_kind": ARTIFACT_KIND,
                "expression_count": len(QA_EXPRESSIONS),
                "pdf_sha256": artifact.manifest["pdf_sha256"],
                "verdict_effect": "none",
                "red_mark_effect": "none",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
