"""Fail-closed validation and PDF conversion for pre-rendered equations.

The SVG is a presentation artifact, never a source of a scientific verdict.
Only byte-identical, locally rendered, path-based SVG is accepted.  Callers
that use :func:`safe_equation_svg_to_drawing` get ``None`` on every rendering
failure and must keep the already stored verdict and annotation state intact.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from io import BytesIO
import math
import re
from typing import Final
from xml.etree import ElementTree

from reportlab.graphics import renderPDF
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg


MAX_SVG_BYTES: Final = 512 * 1024
_SVG_NAMESPACE: Final = "http://www.w3.org/2000/svg"
_DIGEST_PATTERN: Final = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DECLARATION_PATTERN: Final = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.I)
_UNSUPPORTED_XML_MARKUP: Final = re.compile(br"(?:<\?|<!--|\bxmlns\s*:)", re.I)
_SAFE_GEOMETRY: Final = re.compile(r"[A-Za-z0-9+.,()\-\s]*\Z")
_SAFE_COLOR: Final = re.compile(
    r"(?:currentColor|none|transparent|#[0-9a-f]{3,8})\Z", re.I
)
_ALLOWED_TAGS: Final = frozenset(
    {
        "svg",
        "g",
        "path",
        "rect",
        "line",
        "polyline",
        "polygon",
        "circle",
        "ellipse",
    }
)
_ALLOWED_ATTRIBUTES: Final = frozenset(
    {
        "width",
        "height",
        "role",
        "focusable",
        "viewBox",
        "preserveAspectRatio",
        "aria-label",
        "stroke",
        "fill",
        "stroke-width",
        "transform",
        "d",
        "x",
        "y",
        "x1",
        "x2",
        "y1",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "points",
    }
)
_MAX_ELEMENTS: Final = 50_000
_MAX_DEPTH: Final = 256


class EquationSVGValidationError(ValueError):
    """The SVG is not an exact, safe local-renderer artifact."""


class EquationSVGConversionError(RuntimeError):
    """A validated SVG could not be converted to a ReportLab drawing."""


@dataclass(frozen=True, slots=True)
class ValidatedEquationSVG:
    """Exact SVG bytes plus presentation metadata recovered from the root."""

    svg_bytes: bytes
    svg_digest: str
    accessibility_reading: str


def _as_exact_bytes(svg: str | bytes) -> bytes:
    if isinstance(svg, str):
        return svg.encode("utf-8")
    if isinstance(svg, bytes):
        return svg
    raise EquationSVGValidationError("SVG must be UTF-8 text or bytes")


def _assert_digest(svg_bytes: bytes, expected_digest: str) -> None:
    if not isinstance(expected_digest, str) or not _DIGEST_PATTERN.fullmatch(
        expected_digest
    ):
        raise EquationSVGValidationError("invalid SVG digest format")
    actual = "sha256:" + hashlib.sha256(svg_bytes).hexdigest()
    if not hmac.compare_digest(actual, expected_digest):
        raise EquationSVGValidationError("SVG digest mismatch")


def _split_svg_tag(tag: object) -> tuple[str, str]:
    if not isinstance(tag, str) or not tag.startswith("{") or "}" not in tag:
        raise EquationSVGValidationError("every SVG element must use the SVG namespace")
    namespace, local_name = tag[1:].split("}", 1)
    return namespace, local_name


def _validate_attribute(name: str, value: str) -> None:
    if name not in _ALLOWED_ATTRIBUTES:
        raise EquationSVGValidationError(f"SVG attribute is not allowed: {name}")
    lowered = name.lower()
    if lowered == "style" or lowered == "href" or lowered.startswith("on"):
        raise EquationSVGValidationError(f"external-capable SVG attribute: {name}")
    if name == "role" and value != "img":
        raise EquationSVGValidationError("SVG role must be img")
    if name == "focusable" and value != "false":
        raise EquationSVGValidationError("SVG focusable must be false")
    if name == "aria-label":
        if not value.strip() or len(value) > 1000:
            raise EquationSVGValidationError("SVG accessibility reading is invalid")
        if any(ord(character) < 32 and character not in "\t\n\r" for character in value):
            raise EquationSVGValidationError("SVG accessibility reading has control text")
        return
    if name in {"stroke", "fill"}:
        if not _SAFE_COLOR.fullmatch(value):
            raise EquationSVGValidationError(f"unsafe SVG color in {name}")
        return
    if name in {"role", "focusable", "preserveAspectRatio"}:
        if not _SAFE_GEOMETRY.fullmatch(value):
            raise EquationSVGValidationError(f"unsafe SVG value in {name}")
        return
    if not _SAFE_GEOMETRY.fullmatch(value):
        raise EquationSVGValidationError(f"unsafe SVG geometry in {name}")


def _validate_tree(root: ElementTree.Element) -> str:
    stack: list[tuple[ElementTree.Element, int]] = [(root, 1)]
    element_count = 0
    while stack:
        element, depth = stack.pop()
        element_count += 1
        if element_count > _MAX_ELEMENTS:
            raise EquationSVGValidationError("SVG contains too many elements")
        if depth > _MAX_DEPTH:
            raise EquationSVGValidationError("SVG nesting is too deep")

        namespace, local_name = _split_svg_tag(element.tag)
        if namespace != _SVG_NAMESPACE:
            raise EquationSVGValidationError("unexpected SVG namespace")
        if local_name not in _ALLOWED_TAGS:
            raise EquationSVGValidationError(f"SVG element is not allowed: {local_name}")
        if element is not root and local_name == "svg":
            raise EquationSVGValidationError("nested SVG roots are not allowed")
        if element.text and element.text.strip():
            raise EquationSVGValidationError("SVG text nodes are not allowed")
        if element.tail and element.tail.strip():
            raise EquationSVGValidationError("SVG tail text is not allowed")

        for name, value in element.attrib.items():
            # Namespaced attributes (including xlink:href and xml:base) never
            # appear in the local renderer's path-only output.
            if name.startswith("{"):
                raise EquationSVGValidationError("namespaced SVG attributes are not allowed")
            _validate_attribute(name, value)
        stack.extend((child, depth + 1) for child in reversed(list(element)))

    root_namespace, root_name = _split_svg_tag(root.tag)
    if root_namespace != _SVG_NAMESPACE or root_name != "svg":
        raise EquationSVGValidationError("document root must be SVG")
    if root.attrib.get("role") != "img":
        raise EquationSVGValidationError("SVG root is missing role=img")
    if root.attrib.get("focusable") != "false":
        raise EquationSVGValidationError("SVG root is missing focusable=false")
    reading = root.attrib.get("aria-label", "")
    if not reading.strip():
        raise EquationSVGValidationError("SVG root is missing an accessibility reading")
    for required in ("width", "height", "viewBox"):
        if required not in root.attrib:
            raise EquationSVGValidationError(f"SVG root is missing {required}")
    return reading


def validate_equation_svg(
    svg: str | bytes,
    expected_digest: str,
) -> ValidatedEquationSVG:
    """Validate an exact local-renderer SVG without normalizing its bytes."""

    svg_bytes = _as_exact_bytes(svg)
    if len(svg_bytes) > MAX_SVG_BYTES:
        raise EquationSVGValidationError("SVG exceeds the 512 KiB limit")
    if _DECLARATION_PATTERN.search(svg_bytes):
        raise EquationSVGValidationError("DOCTYPE and ENTITY declarations are forbidden")
    if _UNSUPPORTED_XML_MARKUP.search(svg_bytes):
        raise EquationSVGValidationError(
            "processing instructions, comments, and prefixed namespaces are forbidden"
        )
    _assert_digest(svg_bytes, expected_digest)
    try:
        svg_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise EquationSVGValidationError("SVG must be valid UTF-8") from error
    try:
        root = ElementTree.fromstring(svg_bytes)
    except ElementTree.ParseError as error:
        raise EquationSVGValidationError("SVG must be well-formed XML") from error
    reading = _validate_tree(root)
    return ValidatedEquationSVG(
        svg_bytes=svg_bytes,
        svg_digest=expected_digest,
        accessibility_reading=reading,
    )


def equation_svg_to_drawing(
    svg: str | bytes,
    expected_digest: str,
) -> Drawing:
    """Strictly validate SVG and convert it with svglib 2.x."""

    validated = validate_equation_svg(svg, expected_digest)
    try:
        drawing = svg2rlg(BytesIO(validated.svg_bytes))
    except Exception as error:  # svglib/lxml/reportlab failures are presentation-only
        raise EquationSVGConversionError("svglib could not convert the equation SVG") from error
    if not isinstance(drawing, Drawing):
        raise EquationSVGConversionError("svglib returned no equation drawing")
    if (
        not math.isfinite(float(drawing.width))
        or not math.isfinite(float(drawing.height))
        or drawing.width <= 0
        or drawing.height <= 0
        or not drawing.contents
    ):
        raise EquationSVGConversionError("svglib returned an empty equation drawing")
    return drawing


def safe_equation_svg_to_drawing(
    svg: str | bytes,
    expected_digest: str,
) -> Drawing | None:
    """Return ``None`` on failure without changing any scientific state."""

    try:
        return equation_svg_to_drawing(svg, expected_digest)
    except Exception:
        # Fail closed at the presentation boundary.  The function has no
        # access to verdicts, rules, evidence, annotations, or red-mark state.
        return None


def render_equation_pdf(
    svg: str | bytes,
    expected_digest: str,
    *,
    page_size: tuple[float, float] = A4,
) -> bytes:
    """Place one validated equation Drawing on one real PDF page."""

    drawing = equation_svg_to_drawing(svg, expected_digest)
    page_width, page_height = page_size
    margin = 36.0
    available_width = max(page_width - (2 * margin), 1.0)
    available_height = max(page_height - (2 * margin), 1.0)
    scale = min(
        1.0,
        available_width / float(drawing.width),
        available_height / float(drawing.height),
    )
    x = margin
    y = page_height - margin - (float(drawing.height) * scale)

    output = BytesIO()
    try:
        pdf = canvas.Canvas(output, pagesize=page_size, invariant=True)
        pdf.setTitle("Science Verifier equation rendering check")
        pdf.saveState()
        pdf.translate(x, y)
        pdf.scale(scale, scale)
        renderPDF.draw(drawing, pdf, 0, 0)
        pdf.restoreState()
        pdf.showPage()
        pdf.save()
    except Exception as error:
        raise EquationSVGConversionError("ReportLab could not render the equation PDF") from error
    rendered = output.getvalue()
    if not rendered.startswith(b"%PDF-"):
        raise EquationSVGConversionError("ReportLab returned an invalid PDF")
    return rendered


__all__ = [
    "EquationSVGConversionError",
    "EquationSVGValidationError",
    "MAX_SVG_BYTES",
    "ValidatedEquationSVG",
    "equation_svg_to_drawing",
    "render_equation_pdf",
    "safe_equation_svg_to_drawing",
    "validate_equation_svg",
]
