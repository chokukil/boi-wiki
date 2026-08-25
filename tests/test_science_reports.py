from __future__ import annotations

from datetime import UTC, datetime

import pytest

from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.models import (
    ClaimInterpretation,
    ClaimPacket,
    EvidenceLink,
    EvidenceLocator,
    GroundedAnnotation,
    GroundedEquationRef,
    GroundedEquationVariableMapping,
    GroundedExplanation,
    GroundedExplanationBlock,
    GroundedObjectRef,
    NormalizedClaim,
    PrimaryVerdict,
    RelationKind,
    ReleaseSelection,
    ReportEquationAsset,
    ReviewedSourceURLProfile,
    SourceLookupIdentity,
    SourceSpan,
    VerdictPacket,
    VerdictReleaseSet,
    VerificationReport,
)
from boi_api.app.science.equation_assets import load_equation_asset_manifest
from boi_api.app.science.equations import DimensionVector, EquationVariable


def _stored_report() -> VerificationReport:
    claim_text = "final spin RPM을 높이면 건조막 두께가 증가한다."
    claim = ClaimPacket(
        claim_id="claim:spin:001",
        document_ref="boi:private:science:test-document",
        document_digest="sha256:" + "1" * 64,
        source_span=SourceSpan(
            start=0,
            end=len(claim_text),
            exact=claim_text,
        ),
        normalized_claim=NormalizedClaim(
            subject_concept_id="sci:concept:final-spin-speed",
            relation_kind=RelationKind.MONOTONIC_DIRECTION,
            predicate="increases",
            object_concept_id="sci:concept:dry-film-thickness",
            polarity="positive",
            quantities=[],
            conditions=[],
            process_stage="final_spin",
            material_state="dry_film",
        ),
        interpretation=ClaimInterpretation(
            ontology_refs=["sci:ontology-binding:spin-speed"],
            ambiguity_ids=[],
            user_confirmed=True,
        ),
    )
    selection = ReleaseSelection(foundation="sci-release:0.1.0")
    verdict = VerdictPacket(
        claim_id=claim.claim_id,
        claim_packet_digest="sha256:" + "2" * 64,
        verifier_version="science-kernel/0.1",
        releases=VerdictReleaseSet(
            selection=selection,
            digests={selection.foundation: "sha256:" + "3" * 64},
            combined_digest="sha256:" + "4" * 64,
        ),
        verdict=PrimaryVerdict.VIOLATION,
        reason_codes=["DIRECTION_CONTRADICTION"],
        condition_evaluations=[],
        decisive_rule_ids=["sci:rule:spin:direction"],
        knowledge_refs=["sci:knowledge:spin:mechanism"],
        evidence_refs=["sci:evidence:spin:curve"],
        corrected_claim=(
            "동일 조건에서는 final spin RPM이 높을수록 건조막 두께가 감소한다."
        ),
        explanation_facts=[],
        limitations=["정량 지수는 resist와 장비의 검증 범위에 따라 달라진다."],
    )
    locator = EvidenceLocator(section="Spin coating", equation="Eq. 12")
    source_lookup_payload = {
        "source_id": "sci:source:spin",
        "source_digest": "sha256:" + "5" * 64,
        "boi_id": "boi:public:science:source:spin",
        "versioned_path": "public/science/sources/spin.md",
        "visibility": "public",
        "classification": "internal",
        "acl_policy": "boi-public",
    }
    source_lookup = SourceLookupIdentity(
        **source_lookup_payload,
        lookup_digest=sha256_digest(source_lookup_payload),
    )
    source_url = "https://example.org/reviewed-spin-source"
    reviewed_source_payload = {
        "schema_version": "science-reviewed-source-url/0.1",
        "qualification_state": "active",
        "release_set_digest": "sha256:" + "6" * 64,
        "source_id": source_lookup.source_id,
        "source_digest": source_lookup.source_digest,
        "evidence_id": "sci:evidence:spin:curve",
        "evidence_digest": "sha256:" + "7" * 64,
        "canonical_source_url": source_url,
        "canonical_source_url_digest": sha256_digest(source_url),
        "locator": locator,
        "locator_digest": sha256_digest(locator),
        "locator_url_digests": {},
    }
    reviewed_source = ReviewedSourceURLProfile(
        **reviewed_source_payload,
        profile_digest=sha256_digest(reviewed_source_payload),
    )
    link = EvidenceLink(
        evidence_id="sci:evidence:spin:curve",
        evidence_digest="sha256:" + "7" * 64,
        source_id=source_lookup.source_id,
        source_digest=source_lookup.source_digest,
        original_text_hash="sha256:" + "8" * 64,
        quote_hash="sha256:" + "8" * 64,
        url=source_url,
        locator=locator,
        source_lookup=source_lookup,
        reviewed_source=reviewed_source,
    )
    annotation = GroundedAnnotation.model_construct(
        claim_id=claim.claim_id,
        fact_id="sci:fact:spin:radial-outflow",
        text=(
            "회전 속도가 증가하면 점성 액막의 방사 방향 유출이 강화되어 "
            "동일한 검증 조건에서 최종 막이 얇아진다."
        ),
        knowledge_id="sci:knowledge:spin:mechanism",
        knowledge_digest="sha256:" + "9" * 64,
        evidence_links=[link],
    )
    presentation = load_equation_asset_manifest().assets[0]
    equation_variable = EquationVariable(
        variable_id="concentration",
        symbol="c",
        concept_ref="sci:concept:molar-concentration",
        quantity_kind="molar_concentration",
        dimension=DimensionVector(
            length=-3,
            amount_of_substance=1,
        ),
        unit="mol/m^3",
        definition="Amount of solute per solution volume.",
        domain="real",
        sign_constraint="nonnegative",
    )
    equation_asset = ReportEquationAsset(
        **presentation.model_dump(mode="python"),
        knowledge_id="sci:knowledge:chemistry:molar-concentration",
        knowledge_digest="sha256:" + "b" * 64,
        scientific_role="definition",
        decision_use="deterministic_rule",
        variables=[equation_variable],
        assumptions=["The solution volume is defined for the stated state."],
        applicability=["Homogeneous solution at the stated temperature."],
        invalid_outside=["Do not substitute solvent volume for solution volume."],
        boundary_conditions=[],
        evidence_links=[link],
    )
    equation_ref = GroundedEquationRef(
        equation_id=presentation.equation_id,
        equation_digest=presentation.equation_digest,
        knowledge_id=equation_asset.knowledge_id,
        knowledge_digest=equation_asset.knowledge_digest,
        rule_id="sci:rule:chemistry:molar-concentration",
        rule_digest="sha256:" + "c" * 64,
        decision_use="deterministic_rule",
        evaluator_id="sci-evaluator:closed-arithmetic-relation",
        evaluator_version="0.1.0",
        evaluator_digest="sha256:" + "d" * 64,
        binding_digest="sha256:" + "e" * 64,
        variable_mappings=[
            GroundedEquationVariableMapping(
                equation_variable_id="concentration",
                claim_quantity_kind="molar_concentration",
                constraint_operand="left",
            )
        ],
    )
    explanation = GroundedExplanation(
        claim_id=claim.claim_id,
        fact_id="sci:fact:chemistry:concentration-definition",
        knowledge_refs=[
            GroundedObjectRef(
                object_id=equation_asset.knowledge_id,
                object_digest=equation_asset.knowledge_digest,
            )
        ],
        equation_refs=[equation_ref],
        rule_refs=[
            GroundedObjectRef(
                object_id=equation_ref.rule_id,
                object_digest=equation_ref.rule_digest,
            )
        ],
        evidence_links=[link],
        blocks=[
            GroundedExplanationBlock(
                sequence=1,
                block_kind="applied_principle",
                text=("검토된 정의와 조건을 주장에 적용해 결정론적 귀결을 확인했다."),
                knowledge_refs=[
                    GroundedObjectRef(
                        object_id=equation_asset.knowledge_id,
                        object_digest=equation_asset.knowledge_digest,
                    )
                ],
                equation_refs=[equation_ref],
                rule_refs=[
                    GroundedObjectRef(
                        object_id=equation_ref.rule_id,
                        object_digest=equation_ref.rule_digest,
                    )
                ],
                evidence_refs=[
                    GroundedObjectRef(
                        object_id=link.evidence_id,
                        object_digest=link.evidence_digest,
                    )
                ],
            )
        ],
    )
    return VerificationReport.model_construct(
        report_id="sci-report:test",
        document_ref=claim.document_ref,
        document_digest=claim.document_digest,
        release_selection=selection,
        release_digests=verdict.releases.digests,
        interpretation_ids=["sci-interpretation:test"],
        confirmed_claims=[claim],
        verdict_packets=[verdict],
        unresolved_ambiguities=[],
        annotations=[annotation],
        explanations=[explanation],
        equation_assets=[equation_asset],
        created_at=datetime(2026, 8, 25, tzinfo=UTC),
        created_by="100001",
        report_digest="sha256:" + "a" * 64,
        operation_binding=None,
    )


def test_markdown_and_pdf_render_only_the_stored_report() -> None:
    from boi_api.app.science.reports import render_report_markdown, render_report_pdf

    report = _stored_report()
    markdown = render_report_markdown(report)
    pdf = render_report_pdf(report)

    assert report.report_digest in markdown
    assert "VIOLATION" in markdown
    assert "동일 조건에서는 final spin RPM" in markdown
    assert "회전 속도가 증가하면" in markdown
    assert "https://example.org/reviewed-spin-source" in markdown
    assert "Spin coating / Eq. 12" in markdown
    assert "sci:ontology-binding:spin-speed" in markdown
    assert "Aggregate score" not in markdown
    assert "DOE" not in markdown
    assert pdf.startswith(b"%PDF")
    assert render_report_markdown(report) == markdown
    assert render_report_pdf(report) == pdf


def test_markdown_preserves_grounded_equation_and_rule_identity() -> None:
    from boi_api.app.science.reports import render_report_markdown

    report = _stored_report()
    markdown = render_report_markdown(report)
    asset = report.equation_assets[0]
    equation_ref = report.explanations[0].equation_refs[0]

    assert f"$$\n{asset.display_latex}\n$$" in markdown
    assert f"Plain-text fallback: `{asset.plain_text}`" in markdown
    assert asset.equation_id in markdown
    assert asset.equation_digest in markdown
    assert asset.knowledge_id in markdown
    assert asset.knowledge_digest in markdown
    assert equation_ref.rule_id in markdown
    assert equation_ref.rule_digest in markdown
    assert equation_ref.evaluator_id in markdown
    assert equation_ref.evaluator_digest in markdown
    assert equation_ref.binding_digest in markdown
    assert "`c` (`concentration`)" in markdown
    assert "`mol/m^3`" in markdown
    assert "length=-3" in markdown
    assert "amount_of_substance=1" in markdown
    assert "Homogeneous solution at the stated temperature." in markdown
    assert "Do not substitute solvent volume" in markdown
    assert "sci:evidence:spin:curve" in markdown
    assert "Spin coating / Eq. 12" in markdown
    assert "검토된 정의와 조건을 주장에 적용" in markdown


def test_pdf_draws_reviewed_svg_as_vector_and_is_byte_deterministic(
    monkeypatch,
) -> None:
    from boi_api.app.science import reports

    report = _stored_report()
    real_draw = reports.renderPDF.draw
    vector_draws: list[tuple[float, float]] = []
    rendered_text: list[str] = []
    real_draw_string = reports.canvas.Canvas.drawString

    def recording_draw(drawing, pdf_canvas, x, y):
        vector_draws.append((x, y))
        return real_draw(drawing, pdf_canvas, x, y)

    def recording_draw_string(pdf_canvas, x, y, text, *args, **kwargs):
        rendered_text.append(text)
        return real_draw_string(pdf_canvas, x, y, text, *args, **kwargs)

    monkeypatch.setattr(reports.renderPDF, "draw", recording_draw)
    monkeypatch.setattr(reports.canvas.Canvas, "drawString", recording_draw_string)

    first = reports.render_report_pdf(report)
    second = reports.render_report_pdf(report)

    assert first.startswith(b"%PDF-")
    assert first == second
    assert vector_draws == [(0, 0), (0, 0)]
    exported_text = "".join(rendered_text)
    asset = report.equation_assets[0]
    equation_ref = report.explanations[0].equation_refs[0]
    for exact_value in (
        asset.plain_text,
        asset.equation_id,
        asset.equation_digest,
        asset.knowledge_id,
        asset.knowledge_digest,
        equation_ref.rule_id,
        equation_ref.rule_digest,
        equation_ref.evaluator_id,
        equation_ref.evaluator_digest,
        equation_ref.binding_digest,
        "mol/m^3",
        "Homogeneous solution at the stated temperature.",
        "sci:evidence:spin:curve",
        "검토된 정의와 조건",
    ):
        assert exact_value in exported_text


def test_pdf_uses_non_authoritative_plain_text_fallback_when_svg_fails(
    monkeypatch,
) -> None:
    from boi_api.app.science import reports

    report = _stored_report()
    rendered_text: list[str] = []
    real_draw_string = reports.canvas.Canvas.drawString

    def recording_draw_string(pdf_canvas, x, y, text, *args, **kwargs):
        rendered_text.append(text)
        return real_draw_string(pdf_canvas, x, y, text, *args, **kwargs)

    monkeypatch.setattr(reports, "safe_equation_svg_to_drawing", lambda *_: None)
    monkeypatch.setattr(reports.canvas.Canvas, "drawString", recording_draw_string)

    pdf = reports.render_report_pdf(report)

    assert pdf.startswith(b"%PDF-")
    assert any("Equation rendering unavailable" in line for line in rendered_text)
    assert any(report.equation_assets[0].plain_text in line for line in rendered_text)
    assert any("검토된 정의와 조건" in line for line in rendered_text)
    assert report.verdict_packets[0].verdict is PrimaryVerdict.VIOLATION


def test_report_renderers_reject_unvalidated_mappings() -> None:
    from boi_api.app.science.reports import render_report_markdown, render_report_pdf

    with pytest.raises(TypeError, match="stored VerificationReport"):
        render_report_markdown({"report_id": "forged"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="stored VerificationReport"):
        render_report_pdf({"report_id": "forged"})  # type: ignore[arg-type]


def test_report_scientific_digest_excludes_only_renderer_artifacts() -> None:
    from boi_api.app.science.equation_assets import EquationRendererIdentity
    from boi_api.app.science.models import verification_report_scientific_payload

    report = _stored_report()
    original = report.equation_assets[0]
    changed_presentation = original.model_copy(
        update={
            "sanitized_svg": "<presentation-version-changed/>",
            "svg_digest": "sha256:" + "0" * 64,
            "renderer": EquationRendererIdentity(
                engine="future-local-renderer",
                version="99.0",
                output="svg-paths",
                font="future-font",
            ),
            "asset_digest": "sha256:" + "1" * 64,
        }
    )
    presentation_changed_report = report.model_copy(
        update={"equation_assets": [changed_presentation]}
    )

    assert verification_report_scientific_payload(
        presentation_changed_report
    ) == verification_report_scientific_payload(report)

    changed_science = original.model_copy(update={"plain_text": "forged equation"})
    science_changed_report = report.model_copy(
        update={"equation_assets": [changed_science]}
    )
    assert verification_report_scientific_payload(
        science_changed_report
    ) != verification_report_scientific_payload(report)
