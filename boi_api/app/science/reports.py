"""Pure renderers for immutable Science Verification Reports."""

from __future__ import annotations

from collections.abc import Iterable
from io import BytesIO

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


def _markdown_evidence(link: EvidenceLink) -> list[str]:
    return [
        f"  - Evidence: `{link.evidence_id}`",
        f"  - Source: [{link.source_id}]({link.url})",
        f"  - Locator: {_locator_text(link.locator)}",
        f"  - Evidence digest: `{link.evidence_digest}`",
        f"  - Exact quote hash: `{link.quote_hash}`",
    ]


def render_report_markdown(report: VerificationReport) -> str:
    """Render one stored report without recomputation or language generation."""

    stored = _require_stored_report(report)
    claims = {claim.claim_id: claim for claim in stored.confirmed_claims}
    annotations = _annotations_by_claim(stored.annotations)
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


def _pdf_lines(report: VerificationReport) -> list[tuple[str, float]]:
    claims = {claim.claim_id: claim for claim in report.confirmed_claims}
    annotations = _annotations_by_claim(report.annotations)
    lines: list[tuple[str, float]] = [
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

    for text, font_size in _pdf_lines(stored):
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
