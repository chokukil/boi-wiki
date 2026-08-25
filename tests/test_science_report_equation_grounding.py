from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.models import (
    EvidenceLink,
    EvidenceLocator,
    ReleaseSelection,
    SourceLookupIdentity,
)
from boi_api.app.science.service import ScienceService
from boi_api.app.science.source_identity import _build_reviewed_source_url_profile


REPO_ROOT = Path(__file__).resolve().parents[1]
BOI_ROOT = REPO_ROOT / "data/boi"


def _service(catalog: ScienceCatalog) -> ScienceService:
    return ScienceService(
        catalog=catalog,
        runtime_store=SimpleNamespace(),
        llm_client=None,
        dictionary_release_id="fixture-dictionary",
        ontology_release_id="fixture-ontology",
        ontology_binding_ids=[],
        document_access_check=lambda *_args: True,
    )


def _evidence_links(
    catalog: ScienceCatalog,
    release_set,
    evidence_ids: list[str],
) -> list[EvidenceLink]:
    links: list[EvidenceLink] = []
    for evidence_id in evidence_ids:
        evidence = catalog.evidence(evidence_id)
        source = catalog.source(evidence.source_id)
        locator = EvidenceLocator.model_validate(evidence.locator)
        lookup_payload = {
            "source_id": source.object_id,
            "source_digest": source.digest,
            "boi_id": source.boi_id,
            "versioned_path": source.path.relative_to(catalog.boi_root).as_posix(),
            "visibility": source.visibility,
            "classification": source.classification,
            "acl_policy": source.acl_policy,
        }
        source_lookup = SourceLookupIdentity(
            **lookup_payload,
            lookup_digest=sha256_digest(lookup_payload),
        )
        reviewed_source = _build_reviewed_source_url_profile(
            qualification_state="active",
            release_set_digest=release_set.combined_digest,
            source_id=source.object_id,
            source_digest=source.digest,
            evidence_id=evidence.object_id,
            evidence_digest=evidence.digest,
            canonical_source_url=source.original_url,
            locator=locator,
        )
        links.append(
            EvidenceLink(
                evidence_id=evidence.object_id,
                evidence_digest=evidence.digest,
                source_id=source.object_id,
                source_digest=source.digest,
                original_text_hash=evidence.original_text_hash,
                quote_hash=evidence.original_text_hash,
                url=source.original_url,
                locator=locator,
                source_lookup=source_lookup,
                reviewed_source=reviewed_source,
            )
        )
    return links


@pytest.mark.parametrize(
    ("rule_id", "equation_id"),
    [
        (
            "sci-rule:physics:003",
            "sci:equation:physics:applied-work-kinetic-energy-change",
        ),
        (
            "sci-rule:chemistry:001",
            "sci:equation:chemistry:molar-concentration-definition",
        ),
        (
            "sci-rule:circuits:002",
            "sci:equation:circuits:kvl-loop-balance",
        ),
    ],
)
def test_report_grounding_uses_exact_released_equation_rule_and_asset(
    rule_id: str,
    equation_id: str,
) -> None:
    catalog = ScienceCatalog(BOI_ROOT)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )
    service = _service(catalog)
    rule, rule_digest = service._released_rule(release_set, rule_id)
    resolved_equation = catalog.equation(equation_id)
    evidence_ids = [
        item.evidence_ref for item in resolved_equation.equation.evidence_uses
    ]

    refs, assets = service._equation_grounding(
        rule=rule,
        rule_digest=rule_digest,
        release_set=release_set,
        evidence_links=_evidence_links(catalog, release_set, evidence_ids),
    )

    assert len(refs) == len(assets) == 1
    reference = refs[0]
    asset = assets[0]
    assert (
        (reference.equation_id, reference.equation_digest)
        == (
            asset.equation_id,
            asset.equation_digest,
        )
        == (
            resolved_equation.equation.equation_id,
            resolved_equation.equation.equation_digest,
        )
    )
    assert reference.rule_id == rule_id
    assert reference.rule_digest == rule_digest
    assert reference.knowledge_id == resolved_equation.knowledge_id
    assert reference.knowledge_digest == resolved_equation.knowledge_digest
    assert reference.decision_use == asset.decision_use == "deterministic_rule"
    assert {item.evidence_id for item in asset.evidence_links} == set(evidence_ids)
    assert asset.sanitized_svg is not None
    assert asset.svg_digest is not None


@pytest.mark.parametrize(
    "equation_id",
    [
        "sci:equation:semiconductor:low-field-conductivity",
        "sci:equation:materials:arrhenius-diffusion",
        "sci:equation:spin-coating:drying-limited-power-law",
    ],
)
def test_explanation_only_equations_have_no_decisive_rule_binding(
    equation_id: str,
) -> None:
    catalog = ScienceCatalog(BOI_ROOT)
    resolved = catalog.equation(equation_id)

    assert resolved.equation.decision_use == "explanation_only"
    assert all(
        getattr(rule, "equation_binding", None) is None
        or getattr(rule, "equation_binding").get("equation_id") != equation_id
        for rule in catalog._objects["rule"].values()
    )
