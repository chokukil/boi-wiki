"""Pure renderers for immutable Science Verification Reports."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from boi_api.app.science.models import (
    EvidenceLink,
    EvidenceLocator,
    GroundedAnnotation,
    VerificationReport,
)
from boi_api.app.science.equation_rendering import safe_equation_svg_to_drawing

_PDF_FONT = "HYSMyeongJo-Medium"
_PAGE_WIDTH, _PAGE_HEIGHT = A4
_LEFT = 42.0
_RIGHT = 42.0
_TOP = 46.0
_BOTTOM = 44.0


def _require_stored_report(report: VerificationReport) -> VerificationReport:
    if not isinstance(report, VerificationReport):
        raise TypeError("report renderer requires a stored VerificationReport")
    return report


def _locator_text(locator: EvidenceLocator) -> str:
    values = [
        locator.heading,
        locator.section,
        locator.equation,
        locator.figure,
        locator.printed_page,
        f"PDF page {locator.pdf_page_index + 1}"
        if locator.pdf_page_index is not None
        else None,
        locator.sentence_label,
        locator.field_path,
        locator.record_path,
    ]
    return " / ".join(value for value in values if value) or "reviewed locator"


def _annotations_by_claim(
    annotations: Iterable[GroundedAnnotation],
) -> dict[str, list[GroundedAnnotation]]:
    grouped: dict[str, list[GroundedAnnotation]] = {}
    for annotation in annotations:
        grouped.setdefault(annotation.claim_id, []).append(annotation)
    return grouped


def _explanations_by_claim(report: VerificationReport) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for explanation in getattr(report, "explanations", []):
        grouped.setdefault(explanation.claim_id, []).append(explanation)
    return grouped


def _equation_asset_index(report: VerificationReport) -> dict[tuple[str, str], Any]:
    return {
        (asset.equation_id, asset.equation_digest): asset
        for asset in getattr(report, "equation_assets", [])
    }


def _identity_text(reference: Any) -> str:
    return f"`{reference.object_id}` (`{reference.object_digest}`)"


def _plain_identity_text(reference: Any) -> str:
    return f"{reference.object_id} ({reference.object_digest})"


def _dimension_text(variable: Any) -> str:
    dimension = variable.dimension.model_dump(mode="python")
    nonzero = [f"{name}={exponent}" for name, exponent in dimension.items() if exponent]
    return ", ".join(nonzero) or "dimensionless"


def _boundary_condition_text(condition: Any) -> str:
    details: list[str] = []
    if condition.variable_id:
        details.append(f"variable={condition.variable_id}")
    details.append(f"operator={condition.operator}")
    if condition.value is not None:
        details.append(f"value={condition.value}")
    if condition.minimum is not None:
        bracket = "inclusive" if condition.minimum_inclusive else "exclusive"
        details.append(f"minimum={condition.minimum} ({bracket})")
    if condition.maximum is not None:
        bracket = "inclusive" if condition.maximum_inclusive else "exclusive"
        details.append(f"maximum={condition.maximum} ({bracket})")
    if condition.unit:
        details.append(f"unit={condition.unit}")
    return f"{condition.condition_id}: {condition.statement} ({'; '.join(details)})"


def _markdown_evidence(link: EvidenceLink) -> list[str]:
    return [
        f"  - Evidence: `{link.evidence_id}`",
        f"  - Source: [{link.source_id}]({link.url})",
        f"  - Locator: {_locator_text(link.locator)}",
        f"  - Evidence digest: `{link.evidence_digest}`",
        f"  - Exact quote hash: `{link.quote_hash}`",
    ]


def _markdown_equation(asset: Any, equation_ref: Any) -> list[str]:
    lines = [
        "##### Reviewed equation",
        "",
        "$$",
        asset.display_latex,
        "$$",
        "",
        f"Plain-text fallback: `{asset.plain_text}`",
        "",
        f"- Equation: `{asset.equation_id}` (`{asset.equation_digest}`)",
        f"- Knowledge: `{asset.knowledge_id}` (`{asset.knowledge_digest}`)",
        f"- Scientific role: `{asset.scientific_role}`",
        f"- Decision use: `{asset.decision_use}`",
        (f"- Rule: `{equation_ref.rule_id}` (`{equation_ref.rule_digest}`)"),
        (
            f"- Evaluator: `{equation_ref.evaluator_id}` "
            f"version `{equation_ref.evaluator_version}` "
            f"(`{equation_ref.evaluator_digest}`)"
        ),
        f"- Rule binding digest: `{equation_ref.binding_digest}`",
        "- Variables:",
    ]
    for variable in asset.variables:
        lines.append(
            "  - "
            f"`{variable.symbol}` (`{variable.variable_id}`): {variable.definition}; "
            f"concept `{variable.concept_ref}`; quantity `{variable.quantity_kind}`; "
            f"dimension `{_dimension_text(variable)}`; unit `{variable.unit}`; "
            f"domain `{variable.domain}`; sign `{variable.sign_constraint}`"
        )
    lines.append("- Claim-variable mapping:")
    for mapping in equation_ref.variable_mappings:
        lines.append(
            "  - "
            f"`{mapping.equation_variable_id}` → claim quantity "
            f"`{mapping.claim_quantity_kind}` at `{mapping.constraint_operand}`"
        )
    for heading, values in (
        ("Assumptions", asset.assumptions),
        ("Applicability", asset.applicability),
        ("Invalid outside", asset.invalid_outside),
    ):
        lines.append(f"- {heading}:")
        lines.extend(f"  - {value}" for value in values)
    lines.append("- Boundary conditions:")
    if asset.boundary_conditions:
        lines.extend(
            f"  - {_boundary_condition_text(condition)}"
            for condition in asset.boundary_conditions
        )
    else:
        lines.append("  - none declared")
    lines.append("- Equation Evidence:")
    for link in asset.evidence_links:
        lines.extend(_markdown_evidence(link))
    return lines


def _markdown_explanation(
    explanation: Any, assets: dict[tuple[str, str], Any]
) -> list[str]:
    lines = [f"Grounded explanation fact: `{explanation.fact_id}`", ""]
    for block in sorted(explanation.blocks, key=lambda item: item.sequence):
        label = block.block_kind.replace("_", " ").title()
        lines.extend([f"**{block.sequence}. {label}** — {block.text}"])
        if block.knowledge_refs:
            lines.append(
                "- Knowledge references: "
                + ", ".join(_identity_text(item) for item in block.knowledge_refs)
            )
        if block.rule_refs:
            lines.append(
                "- Rule references: "
                + ", ".join(_identity_text(item) for item in block.rule_refs)
            )
        if block.evidence_refs:
            lines.append(
                "- Evidence references: "
                + ", ".join(_identity_text(item) for item in block.evidence_refs)
            )
        lines.append("")
    for equation_ref in explanation.equation_refs:
        asset = assets.get((equation_ref.equation_id, equation_ref.equation_digest))
        if asset is None:
            lines.extend(
                [
                    "##### Reviewed equation",
                    "",
                    (
                        f"Presentation unavailable for `{equation_ref.equation_id}` "
                        f"(`{equation_ref.equation_digest}`). The stored verdict is unchanged."
                    ),
                    "",
                ]
            )
            continue
        lines.extend(_markdown_equation(asset, equation_ref))
        lines.append("")
    lines.append("Grounded Evidence:")
    for link in explanation.evidence_links:
        lines.extend(_markdown_evidence(link))
    lines.append("")
    return lines


def render_report_markdown(report: VerificationReport) -> str:
    """Render one stored report without recomputation or language generation."""

    stored = _require_stored_report(report)
    claims = {claim.claim_id: claim for claim in stored.confirmed_claims}
    annotations = _annotations_by_claim(stored.annotations)
    explanations = _explanations_by_claim(stored)
    equation_assets = _equation_asset_index(stored)
    lines = [
        "# Science Verification Report",
        "",
        (
            "> This report preserves a deterministic verdict from an immutable "
            "Science Release. It is not an AI confidence score."
        ),
        "",
        f"- Report ID: `{stored.report_id}`",
        f"- Report digest: `{stored.report_digest}`",
        f"- Document: `{stored.document_ref or 'submitted-text'}`",
        f"- Document digest: `{stored.document_digest}`",
        f"- Created: `{stored.created_at.isoformat()}`",
        f"- Created by: `{stored.created_by}`",
        "",
        "## Pinned Science Releases",
        "",
    ]
    for release_id, digest in sorted(stored.release_digests.items()):
        lines.append(f"- `{release_id}` — `{digest}`")

    lines.extend(["", "## Claim Review", ""])
    for index, verdict in enumerate(stored.verdict_packets, start=1):
        claim = claims[verdict.claim_id]
        lines.extend(
            [
                f"### {index}. {verdict.verdict.value}",
                "",
                f"> {claim.source_span.exact}",
                "",
                f"- Claim ID: `{claim.claim_id}`",
                f"- Claim Packet digest: `{verdict.claim_packet_digest}`",
                "- Ontology references: "
                + (
                    ", ".join(
                        f"`{reference}`"
                        for reference in claim.interpretation.ontology_refs
                    )
                    or "none"
                ),
                "- Decisive rules: "
                + (
                    ", ".join(f"`{rule_id}`" for rule_id in verdict.decisive_rule_ids)
                    or "none"
                ),
            ]
        )
        if verdict.corrected_claim:
            lines.extend(["", "#### Correction", "", verdict.corrected_claim])
        lines.extend(["", "#### Scientific explanation", ""])
        claim_annotations = annotations.get(verdict.claim_id, [])
        if claim_annotations:
            for annotation in claim_annotations:
                lines.extend(
                    [
                        annotation.text,
                        "",
                        (
                            f"- Knowledge: `{annotation.knowledge_id}` "
                            f"(`{annotation.knowledge_digest}`)"
                        ),
                    ]
                )
                for link in annotation.evidence_links:
                    lines.extend(_markdown_evidence(link))
                lines.append("")
        else:
            lines.extend(
                [
                    "No grounded explanation fact is stored for this claim.",
                    "",
                ]
            )
        for explanation in explanations.get(verdict.claim_id, []):
            lines.extend(_markdown_explanation(explanation, equation_assets))
        if verdict.limitations:
            lines.extend(["#### Limits", ""])
            lines.extend(f"- {limitation}" for limitation in verdict.limitations)
            lines.append("")
    lines.extend(
        [
            "## Verdict boundary",
            "",
            (
                "`CONSISTENT` means no released rule contradicted the confirmed "
                "claim within the pinned scope. It does not prove universal truth, "
                "safety, or process approval."
            ),
            "",
        ]
    )
    return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class _PDFEquation:
    asset: Any


def _pdf_equation_lines(asset: Any, equation_ref: Any) -> list[tuple[str, float]]:
    lines: list[tuple[str, float]] = [
        (f"Plain-text fallback: {asset.plain_text}", 9),
        (f"Equation: {asset.equation_id} ({asset.equation_digest})", 7),
        (f"Knowledge: {asset.knowledge_id} ({asset.knowledge_digest})", 7),
        (f"Scientific role: {asset.scientific_role}", 8),
        (f"Decision use: {asset.decision_use}", 8),
        (f"Rule: {equation_ref.rule_id} ({equation_ref.rule_digest})", 7),
        (
            f"Evaluator: {equation_ref.evaluator_id} "
            f"version {equation_ref.evaluator_version} "
            f"({equation_ref.evaluator_digest})",
            7,
        ),
        (f"Rule binding digest: {equation_ref.binding_digest}", 7),
        ("Variables", 9),
    ]
    for variable in asset.variables:
        lines.append(
            (
                f"{variable.symbol} ({variable.variable_id}): {variable.definition}; "
                f"concept {variable.concept_ref}; quantity {variable.quantity_kind}; "
                f"dimension {_dimension_text(variable)}; unit {variable.unit}; "
                f"domain {variable.domain}; sign {variable.sign_constraint}",
                7,
            )
        )
    lines.append(("Claim-variable mapping", 9))
    lines.extend(
        (
            f"{mapping.equation_variable_id} -> claim quantity "
            f"{mapping.claim_quantity_kind} at {mapping.constraint_operand}",
            7,
        )
        for mapping in equation_ref.variable_mappings
    )
    for heading, values in (
        ("Assumptions", asset.assumptions),
        ("Applicability", asset.applicability),
        ("Invalid outside", asset.invalid_outside),
    ):
        lines.append((heading, 9))
        lines.extend((f"• {value}", 8) for value in values)
    lines.append(("Boundary conditions", 9))
    lines.extend(
        [
            (_boundary_condition_text(condition), 8)
            for condition in asset.boundary_conditions
        ]
        or [("none declared", 8)]
    )
    lines.append(("Equation Evidence", 9))
    for link in asset.evidence_links:
        lines.extend(
            [
                (f"Evidence: {link.evidence_id}", 8),
                (f"Source: {link.url}", 7),
                (f"Locator: {_locator_text(link.locator)}", 8),
                (f"Evidence digest: {link.evidence_digest}", 7),
                (f"Exact quote hash: {link.quote_hash}", 7),
            ]
        )
    return lines


def _pdf_explanation_items(
    explanation: Any,
    assets: dict[tuple[str, str], Any],
) -> list[tuple[str, float] | _PDFEquation]:
    items: list[tuple[str, float] | _PDFEquation] = [
        (f"Grounded explanation fact: {explanation.fact_id}", 9)
    ]
    for block in sorted(explanation.blocks, key=lambda item: item.sequence):
        label = block.block_kind.replace("_", " ").title()
        items.append((f"{block.sequence}. {label}: {block.text}", 9))
        if block.knowledge_refs:
            items.append(
                (
                    "Knowledge references: "
                    + ", ".join(
                        _plain_identity_text(item) for item in block.knowledge_refs
                    ),
                    7,
                )
            )
        if block.rule_refs:
            items.append(
                (
                    "Rule references: "
                    + ", ".join(_plain_identity_text(item) for item in block.rule_refs),
                    7,
                )
            )
        if block.evidence_refs:
            items.append(
                (
                    "Evidence references: "
                    + ", ".join(
                        _plain_identity_text(item) for item in block.evidence_refs
                    ),
                    7,
                )
            )
    for equation_ref in explanation.equation_refs:
        asset = assets.get((equation_ref.equation_id, equation_ref.equation_digest))
        if asset is None:
            items.append(
                (
                    f"Equation presentation unavailable: {equation_ref.equation_id} "
                    f"({equation_ref.equation_digest}); stored verdict unchanged.",
                    8,
                )
            )
            continue
        items.extend([("Reviewed equation", 11), _PDFEquation(asset)])
        items.extend(_pdf_equation_lines(asset, equation_ref))
    items.append(("Grounded Evidence", 9))
    for link in explanation.evidence_links:
        items.extend(
            [
                (f"Evidence: {link.evidence_id}", 8),
                (f"Source: {link.url}", 7),
                (f"Locator: {_locator_text(link.locator)}", 8),
                (f"Evidence digest: {link.evidence_digest}", 7),
                (f"Exact quote hash: {link.quote_hash}", 7),
            ]
        )
    return items


def _pdf_items(report: VerificationReport) -> list[tuple[str, float] | _PDFEquation]:
    claims = {claim.claim_id: claim for claim in report.confirmed_claims}
    annotations = _annotations_by_claim(report.annotations)
    explanations = _explanations_by_claim(report)
    equation_assets = _equation_asset_index(report)
    lines: list[tuple[str, float] | _PDFEquation] = [
        ("Science Verification Report", 16),
        (f"Report ID: {report.report_id}", 9),
        (f"Report digest: {report.report_digest}", 8),
        (f"Document digest: {report.document_digest}", 8),
        ("Pinned Science Releases", 12),
    ]
    lines.extend(
        (f"{release_id} — {digest}", 8)
        for release_id, digest in sorted(report.release_digests.items())
    )
    for index, verdict in enumerate(report.verdict_packets, start=1):
        claim = claims[verdict.claim_id]
        lines.extend(
            [
                (f"{index}. {verdict.verdict.value}", 13),
                (claim.source_span.exact, 10),
                (f"Claim ID: {claim.claim_id}", 8),
                (
                    "Ontology: " + ", ".join(claim.interpretation.ontology_refs),
                    8,
                ),
            ]
        )
        if verdict.corrected_claim:
            lines.extend([("Correction", 11), (verdict.corrected_claim, 10)])
        lines.append(("Scientific explanation", 11))
        for annotation in annotations.get(verdict.claim_id, []):
            lines.extend(
                [
                    (annotation.text, 9),
                    (
                        (
                            f"Knowledge: {annotation.knowledge_id} "
                            f"({annotation.knowledge_digest})"
                        ),
                        7,
                    ),
                ]
            )
            for link in annotation.evidence_links:
                lines.extend(
                    [
                        (f"Evidence: {link.evidence_id}", 8),
                        (f"Source: {link.url}", 7),
                        (f"Locator: {_locator_text(link.locator)}", 8),
                        (f"Evidence digest: {link.evidence_digest}", 7),
                        (f"Exact quote hash: {link.quote_hash}", 7),
                    ]
                )
        if verdict.limitations:
            lines.append(("Limits", 11))
            lines.extend((f"• {limitation}", 9) for limitation in verdict.limitations)
        for explanation in explanations.get(verdict.claim_id, []):
            lines.extend(_pdf_explanation_items(explanation, equation_assets))
    lines.extend(
        [
            ("Verdict boundary", 11),
            (
                (
                    "CONSISTENT is not universal truth, safety approval, or "
                    "process approval."
                ),
                8,
            ),
        ]
    )
    return lines


def _pdf_lines(report: VerificationReport) -> list[tuple[str, float]]:
    """Backward-compatible text projection used by older callers and tests."""

    return [item for item in _pdf_items(report) if isinstance(item, tuple)]


def _wrap_pdf_text(text: str, font_size: float, width: float) -> list[str]:
    if not text:
        return [""]
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


def render_report_pdf(report: VerificationReport) -> bytes:
    """Render deterministic PDF bytes from the same immutable report model."""

    stored = _require_stored_report(report)
    if _PDF_FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(_PDF_FONT))
    output = BytesIO()
    document = canvas.Canvas(
        output,
        pagesize=A4,
        invariant=1,
        pageCompression=1,
    )
    document.setTitle("Science Verification Report")
    document.setAuthor("BoI Wiki Science Verifier")
    y = _PAGE_HEIGHT - _TOP
    usable_width = _PAGE_WIDTH - _LEFT - _RIGHT
    page_number = 1

    def next_page() -> None:
        nonlocal y, page_number
        document.setFont(_PDF_FONT, 7)
        document.drawRightString(
            _PAGE_WIDTH - _RIGHT,
            20,
            f"{page_number}",
        )
        document.showPage()
        page_number += 1
        y = _PAGE_HEIGHT - _TOP

    for item in _pdf_items(stored):
        if isinstance(item, _PDFEquation):
            asset = item.asset
            drawing = None
            if asset.sanitized_svg is not None and asset.svg_digest is not None:
                drawing = safe_equation_svg_to_drawing(
                    asset.sanitized_svg,
                    asset.svg_digest,
                )
            if drawing is None:
                fallback = (
                    "Equation rendering unavailable — plain text: "
                    f"{asset.plain_text} (stored verdict unchanged)"
                )
                font_size = 9.0
                spacing = max(font_size * 1.45, 11)
                wrapped = _wrap_pdf_text(fallback, font_size, usable_width)
                if y - spacing * len(wrapped) < _BOTTOM:
                    next_page()
                document.setFont(_PDF_FONT, font_size)
                for line in wrapped:
                    document.drawString(_LEFT, y, line)
                    y -= spacing
                y -= 2.0
                continue
            max_equation_height = 82.0
            scale = min(
                1.0,
                usable_width / float(drawing.width),
                max_equation_height / float(drawing.height),
            )
            rendered_height = float(drawing.height) * scale
            if y - rendered_height < _BOTTOM:
                next_page()
            draw_failed = False
            document.saveState()
            try:
                document.translate(_LEFT, y - rendered_height)
                document.scale(scale, scale)
                renderPDF.draw(drawing, document, 0, 0)
            except Exception:
                draw_failed = True
            finally:
                document.restoreState()
            if draw_failed:
                fallback = (
                    "Equation rendering unavailable — plain text: "
                    f"{asset.plain_text} (stored verdict unchanged)"
                )
                document.setFont(_PDF_FONT, 9)
                for line in _wrap_pdf_text(fallback, 9, usable_width):
                    document.drawString(_LEFT, y, line)
                    y -= 13
            else:
                y -= rendered_height + 6.0
            continue
        text, font_size = item
        spacing = max(font_size * 1.45, 11)
        wrapped = _wrap_pdf_text(text, font_size, usable_width)
        if y - spacing * len(wrapped) < _BOTTOM:
            next_page()
        document.setFont(_PDF_FONT, font_size)
        for line in wrapped:
            document.drawString(_LEFT, y, line)
            y -= spacing
        y -= max(2.0, font_size * 0.25)
    document.setFont(_PDF_FONT, 7)
    document.drawRightString(_PAGE_WIDTH - _RIGHT, 20, f"{page_number}")
    document.save()
    return output.getvalue()
