from __future__ import annotations

from datetime import UTC, datetime

import pytest

from boi_api.app.science.models import (
    ClaimInterpretation,
    ClaimPacket,
    EvidenceLink,
    EvidenceLocator,
    GroundedAnnotation,
    NormalizedClaim,
    PrimaryVerdict,
    RelationKind,
    ReleaseSelection,
    SourceLookupIdentity,
    SourceSpan,
    VerdictPacket,
    VerdictReleaseSet,
    VerificationReport,
)


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
    source_lookup = SourceLookupIdentity.model_construct(
        source_id="sci:source:spin",
        source_digest="sha256:" + "5" * 64,
        source_boi_id="boi:public:science:source:spin",
        source_path="public/science/sources/spin.md",
        visibility="public",
        classification="internal",
        acl_policy="boi-public",
        lookup_digest="sha256:" + "6" * 64,
    )
    link = EvidenceLink.model_construct(
        evidence_id="sci:evidence:spin:curve",
        evidence_digest="sha256:" + "7" * 64,
        source_id=source_lookup.source_id,
        source_digest=source_lookup.source_digest,
        original_text_hash="sha256:" + "8" * 64,
        quote_hash="sha256:" + "8" * 64,
        url="https://example.org/reviewed-spin-source",
        locator=locator,
        source_lookup=source_lookup,
        reviewed_source=None,
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


def test_report_renderers_reject_unvalidated_mappings() -> None:
    from boi_api.app.science.reports import render_report_markdown, render_report_pdf

    with pytest.raises(TypeError, match="stored VerificationReport"):
        render_report_markdown({"report_id": "forged"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="stored VerificationReport"):
        render_report_pdf({"report_id": "forged"})  # type: ignore[arg-type]
