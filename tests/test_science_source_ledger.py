from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from boi_api.app.okf import split_frontmatter
from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.profile import validate_sci_profile_metadata

EXPECTED_SOURCE_IDS = {
    "sci-source:bipm-si-brochure-9-v4-01",
    "sci-source:jcgm-vim-3-2012",
    "sci-source:nist-tn-1297",
    "sci-source:nasa-std-7009b",
    "sci-source:nist-statistics-handbook",
    "sci-source:iupac-gold-book",
    "sci-source:feynman-lectures",
    "sci-source:mit-8-01sc",
    "sci-source:mit-2-25",
    "sci-source:mit-5-111",
    "sci-source:chem1-virtual-textbook",
    "sci-source:mit-6-002",
    "sci-source:all-about-circuits",
    "sci-source:mit-3-091",
    "sci-source:mit-3-091sc-2010",
    "sci-source:mit-3-012",
    "sci-source:mit-3-024",
    "sci-source:mit-6-012",
    "sci-source:chenming-hu-devices",
    "sci-source:emslie-1958",
    "sci-source:meyerhofer-1978",
    "sci-source:merck-az-125nxt-01-24",
    "sci-source:microchemicals-spin-coating-photoresist",
    "sci-source:nistir-5851-1997",
}


EXPECTED_EVIDENCE_IDS = {
    *(f"sci-evidence:common:{name}" for name in (
        "quantity-unit-dimension", "celsius-kelvin", "measurand-result",
        "uncertainty-error", "accuracy-precision", "repeatability-reproducibility",
        "model-validity", "correlation-causation", "steady-state", "equilibrium",
        "system-balance",
    )),
    *(f"sci-evidence:physics:{name}" for name in (
        "rotation-angular-speed", "force-momentum", "work-energy-power",
        "viscosity-flow", "control-volume-flux",
    )),
    *(f"sci-evidence:chemistry:{name}" for name in (
        "amount-concentration", "substance-phase", "evaporation-vapor-pressure",
        "reaction-equilibrium", "catalyst-kinetics",
    )),
    *(f"sci-evidence:circuits:{name}" for name in (
        "kcl-law", "kvl-law", "ohm-model", "electric-power", "series-parallel",
        "capacitor-inductor", "measurement-loading",
    )),
    *(f"sci-evidence:materials:{name}" for name in (
        "structure-grain", "defects-microstructure", "phase-transformation",
        "diffusion-arrhenius", "bulk-thin-film",
    )),
    *(f"sci-evidence:semiconductor-devices:{name}" for name in (
        "bands-fermi-level", "carrier-conductivity", "drift-diffusion",
        "pn-junction", "mos-capacitor", "mos-gate-ideal-model",
        "mos-gate-real-leakage", "transistor-operating-region",
    )),
    *(f"sci-evidence:spin-coating:{name}" for name in (
        "emslie-model", "meyerhofer-model", "vendor-spin-time-guidance",
        "vendor-spin-curve-observation", "microchemicals-spin-mechanism",
        "microchemicals-spin-speed-direction", "microchemicals-film-state-change",
        "microchemicals-equipment-influence",
    )),
    "sci-evidence:materials:nist-thin-film-bulk-difference",
}


def test_task3_authoritative_spans_are_pdf_hash_bound_and_narrowly_scoped() -> None:
    catalog = ScienceCatalog(_science_root().parents[1])
    spin = catalog.evidence(
        "sci-evidence:spin-coating:microchemicals-spin-speed-direction"
    )
    mechanism = catalog.evidence(
        "sci-evidence:spin-coating:microchemicals-spin-mechanism"
    )
    state_change = catalog.evidence(
        "sci-evidence:spin-coating:microchemicals-film-state-change"
    )
    equipment = catalog.evidence(
        "sci-evidence:spin-coating:microchemicals-equipment-influence"
    )
    material = catalog.evidence(
        "sci-evidence:materials:nist-thin-film-bulk-difference"
    )

    assert spin.locator["content_hash"] == (
        "sha256:3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7"
    )
    assert spin.locator["pdf_page_index"] == 0
    assert "reciprocal square root of the spin speed" in spin.original_text
    assert spin.claim_scope["allowed_claims"][0]["claim_family"] == (
        "spin_coating.spin_speed_thickness_direction.drying_limited_process"
    )
    assert "centrifugal force" in mechanism.original_text
    assert "solvent evaporates" in mechanism.original_text
    assert mechanism.claim_scope["allowed_claims"][0]["claim_family"] == (
        "spin_coating.mechanism.centrifugal_spreading_solvent_evaporation"
    )
    assert state_change.locator["pdf_page_index"] == 1
    assert "measured immediately after spin-coating" in state_change.original_text
    assert state_change.claim_scope["allowed_claims"][0]["claim_family"] == (
        "spin_coating.film_thickness.process_state_difference"
    )
    assert equipment.locator["pdf_page_index"] == 2
    assert equipment.original_text == (
        "The equipment itself has a great influence on the coating result:"
    )
    assert equipment.claim_scope["allowed_claims"][0]["claim_family"] == (
        "spin_coating.equipment.coating_result_influence"
    )
    assert material.locator["content_hash"] == (
        "sha256:7f4e939b3fd4dc621ffd6a534773b08da687d4052b2148c865436ac30b9b854b"
    )
    assert material.locator["pdf_page_index"] == 24
    assert "same chemical composition" in material.original_text
    assert material.claim_scope["allowed_claims"][0]["claim_family"] == (
        "materials.thin_film_bulk_property_nontransferability"
    )


def test_exact_pdf_evidence_preserves_the_verified_page_and_source_text() -> None:
    catalog = ScienceCatalog(_science_root().parents[1])
    viscosity = catalog.evidence("sci-evidence:physics:viscosity-flow")
    model = catalog.evidence("sci-evidence:common:model-validity")
    equilibrium = catalog.evidence("sci-evidence:chemistry:reaction-equilibrium")
    force = catalog.evidence("sci-evidence:physics:force-momentum")

    assert viscosity.locator["pdf_page_index"] == 11
    assert viscosity.locator["printed_page"] == "printed/PDF page 12"
    assert model.original_text == (
        "A record of the domain of validation of the validated M&S shall be maintained."
    )
    assert equilibrium.original_text.startswith("K = is the equilibrium constant.")
    assert force.original_text.endswith("system of objects as")
    for evidence in (viscosity, model, equilibrium, force):
        assert evidence.original_text_hash == "sha256:" + hashlib.sha256(
            evidence.original_text.encode("utf-8")
        ).hexdigest()


def test_evidence_scopes_do_not_substitute_attestation_or_visual_inference_for_source_operands() -> None:
    catalog = ScienceCatalog(_science_root().parents[1])
    diffusion = catalog.evidence("sci-evidence:materials:diffusion-arrhenius")
    conductivity = catalog.evidence(
        "sci-evidence:semiconductor-devices:carrier-conductivity"
    )
    vendor_figure = catalog.evidence(
        "sci-evidence:spin-coating:vendor-spin-curve-observation"
    )

    diffusion_keys = {
        condition["key"]
        for condition in diffusion.claim_scope["allowed_claims"][0]["required_conditions"]
    }
    conductivity_keys = {
        condition["key"]
        for condition in conductivity.claim_scope["allowed_claims"][0]["required_conditions"]
    }
    assert "material_parameters_known" not in diffusion_keys
    assert "carrier_state_parameters_known" not in conductivity_keys

    vendor_claim = vendor_figure.claim_scope["allowed_claims"][0]
    assert vendor_claim == {
        "claim_family": "locator_bound.spin_coating.vendor_figure_labels",
        "purpose": (
            "Film Thickness (µm) Spin Speed (rpm) AZ 125nXT-10 B AZ 125nXT-7 B"
        ),
        "required_conditions": [],
    }
    assert "spin_coating.rpm_thickness_direction" in vendor_figure.claim_scope[
        "forbidden_claim_families"
    ]
    assert vendor_figure.figure_observation == {
        "x_axis": {"label": "Spin Speed", "unit": "rpm"},
        "y_axis": {"label": "Film Thickness", "unit": "µm"},
        "series_labels": ["AZ 125nXT-10 B", "AZ 125nXT-7 B"],
        "extraction_method": (
            "manual visual transcription of axis and legend labels from PDF page 10; "
            "no curve interpretation or digitization"
        ),
        "review_method": "agent visual transcription pending authorized Admin review",
        "limits": [
            "the exact span stores labels only",
            "no curve direction, range, individual point, interpolation, or extrapolation is asserted",
        ],
    }


def _science_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "boi" / "public" / "science"


def _science_documents(science_root: Path):
    for path in sorted(science_root.rglob("*.md")):
        metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
        if metadata.get("type") in {"boi/science-source", "boi/science-evidence"}:
            yield path, metadata, body


def test_ledger_declares_the_complete_v01_source_and_evidence_inventory() -> None:
    science_root = _science_root()
    ledger = yaml.safe_load((science_root / "source-evidence-ledger-v0.1.yaml").read_text(encoding="utf-8"))

    assert ledger["ledger_version"] == "0.1"
    assert {item["source_id"] for item in ledger["sources"]} == EXPECTED_SOURCE_IDS
    assert {item["evidence_id"] for item in ledger["evidence"]} == EXPECTED_EVIDENCE_IDS


def test_every_ledger_evidence_is_a_hash_verified_pending_review_okf_span() -> None:
    science_root = _science_root()
    ledger = yaml.safe_load((science_root / "source-evidence-ledger-v0.1.yaml").read_text(encoding="utf-8"))
    catalog = ScienceCatalog(science_root.parents[1])

    for item in ledger["evidence"]:
        evidence = catalog.evidence(item["evidence_id"])
        source = catalog.source(item["source_id"])
        assert evidence.source_id == item["source_id"]
        assert evidence.original_text_hash == "sha256:" + hashlib.sha256(
            evidence.original_text.encode("utf-8")
        ).hexdigest()
        assert evidence.reviewed_translation.strip()
        assert len(evidence.original_text) <= 320
        assert len(evidence.original_text.split()) <= 55
        locator_hash = evidence.locator.get("content_hash")
        assert isinstance(locator_hash, str) and locator_hash.startswith("sha256:") and len(locator_hash) == 71
        resource_url = evidence.locator.get("resource_url")
        if resource_url:
            parsed_resource = urlparse(resource_url)
            assert parsed_resource.scheme == "https" and parsed_resource.netloc
        else:
            assert locator_hash == source.content_hash
        assert any(
            evidence.locator.get(field)
            for field in ("section", "page", "equation", "figure", "term_id", "heading")
        )
        assert evidence.decision_eligibility in {"pending_review", "inactive"}
        if evidence.decision_eligibility == "inactive":
            assert evidence.access_limitation.strip()
        else:
            assert source.retrieval_status == "verified"
            assert evidence.access_limitation == ""


def test_source_records_are_https_versioned_and_retrieval_bound() -> None:
    science_root = _science_root()
    ledger = yaml.safe_load((science_root / "source-evidence-ledger-v0.1.yaml").read_text(encoding="utf-8"))
    catalog = ScienceCatalog(science_root.parents[1])

    for item in ledger["sources"]:
        source = catalog.source(item["source_id"])
        parsed = urlparse(source.original_url)
        assert parsed.scheme == "https" and parsed.netloc
        if source.doi_url:
            assert source.doi_url.startswith("https://doi.org/")
        assert source.edition_or_version.strip()
        assert source.retrieved_at.startswith("2026-08-25T")
        assert source.content_hash.startswith("sha256:") and len(source.content_hash) == 71
        assert source.access_note.strip()
        assert source.license_note.strip()
        assert source.retrieval_status in {"verified", "access_limited"}
        for field in ("requested_url", "resolved_url"):
            parsed_url = urlparse(getattr(source, field))
            assert parsed_url.scheme == "https" and parsed_url.netloc
        assert source.preservation_status == "checksum_only_no_archived_copy"
        assert source.retrieval_actor == {"type": "agent", "agent_id": "codex"}
        assert source.curation_actor == {"type": "agent", "agent_id": "codex"}
        assert source.release_eligibility == "blocked_pending_authorized_admin_review"


def test_science_source_and_evidence_documents_use_exact_profile_version_and_valid_metadata() -> None:
    for path, metadata, _body in _science_documents(_science_root()):
        assert metadata.get("sci_profile_version") == "0.1", path
        assert validate_sci_profile_metadata(metadata) == [], path


def test_agent_curated_documents_cannot_claim_human_approval_or_release_eligibility() -> None:
    for path, metadata, _body in _science_documents(_science_root()):
        assert metadata["author"] == {"type": "agent", "agent_id": "codex"}, path
        assert metadata["status"] == "draft", path
        review = metadata["review"]
        assert review == {
            "review_status": "pending_review",
            "required_role": "Admin",
            "authorized_review_events": [],
        }, path
        science = metadata["science"]
        assert science["curation_actor"] == metadata["author"], path
        assert science["release_eligibility"] == "blocked_pending_authorized_admin_review", path
        assert datetime.fromisoformat(science["curated_at"]) >= datetime.fromisoformat(metadata["timestamp"]), path
        if metadata["type"] == "boi/science-evidence":
            assert science["decision_eligibility"] != "eligible", path


def test_review_events_if_present_are_temporal_authorized_and_not_self_approvals() -> None:
    for path, metadata, _body in _science_documents(_science_root()):
        author = metadata["author"]
        authored_at = datetime.fromisoformat(metadata["timestamp"])
        for event in metadata["review"]["authorized_review_events"]:
            assert event["role"] == "Admin", path
            assert event["actor"] != author, path
            assert datetime.fromisoformat(event["occurred_at"]) >= authored_at, path


def test_ledger_paths_and_eligibility_match_stored_documents() -> None:
    science_root = _science_root()
    ledger = yaml.safe_load((science_root / "source-evidence-ledger-v0.1.yaml").read_text(encoding="utf-8"))
    catalog = ScienceCatalog(science_root.parents[1])

    for kind, id_field, resolver in (
        ("sources", "source_id", catalog.source),
        ("evidence", "evidence_id", catalog.evidence),
    ):
        for item in ledger[kind]:
            obj = resolver(item[id_field])
            assert obj.path == (science_root / item["document"]).resolve()
            if kind == "evidence":
                assert item["decision_eligibility"] == obj.decision_eligibility


def test_evidence_locators_are_medium_specific_and_reproducible() -> None:
    science_root = _science_root()
    ledger = yaml.safe_load((science_root / "source-evidence-ledger-v0.1.yaml").read_text(encoding="utf-8"))
    catalog = ScienceCatalog(science_root.parents[1])

    for item in ledger["evidence"]:
        evidence = catalog.evidence(item["evidence_id"])
        locator = evidence.locator
        for field in ("requested_url", "resolved_url", "resource_url", "content_hash", "hash_scope", "preservation_status"):
            assert locator.get(field), (evidence.object_id, field)
        if locator["medium"] == "pdf":
            assert isinstance(locator.get("pdf_page_index"), int), evidence.object_id
            assert locator.get("printed_page") or locator.get("section"), evidence.object_id
        elif locator["medium"] == "html":
            for field in ("heading", "sentence_ordinal", "prefix", "suffix"):
                assert locator.get(field) not in (None, ""), (evidence.object_id, field)
            window = locator["prefix"] + "\n" + evidence.original_text + "\n" + locator["suffix"]
            assert locator["content_hash"] == "sha256:" + hashlib.sha256(window.encode("utf-8")).hexdigest()
            assert locator["hash_scope"] == "utf8_sha256_prefix_lf_original_lf_suffix"
        elif locator["medium"] == "api_json":
            assert locator.get("record_path") and locator.get("field_path"), evidence.object_id
            assert evidence.decision_eligibility == "inactive", evidence.object_id
        else:
            raise AssertionError(f"unsupported locator medium: {locator['medium']}")


def test_vendor_source_separates_publisher_from_accessible_mirror() -> None:
    source = ScienceCatalog(_science_root().parents[1]).source("sci-source:merck-az-125nxt-01-24")
    assert source.publisher_url == "https://www.emdgroup.com/en/expertise/semiconductors/offering/thick-film-resists.html"
    assert source.original_url == source.publisher_url
    assert source.accessible_copy_url == (
        "https://www.microchemicals.com/dokumente/datenblaetter/tds/merck/en/tds_az_125nxt_serie.pdf"
    )
    assert source.hash_scope == "accessible_copy_pdf_bytes"


def test_jcgm_translation_is_unofficial_and_original_controls() -> None:
    catalog = ScienceCatalog(_science_root().parents[1])
    source = catalog.source("sci-source:jcgm-vim-3-2012")
    assert source.translation_policy == {
        "status": "permission_not_recorded",
        "repository_translation_status": "unofficial_internal_draft_pending_admin_review",
        "original_controls": True,
    }
    for evidence_id in (
        "sci-evidence:common:measurand-result",
        "sci-evidence:common:uncertainty-error",
        "sci-evidence:common:accuracy-precision",
        "sci-evidence:common:repeatability-reproducibility",
    ):
        translation = catalog.evidence(evidence_id).translation
        assert translation["status"] == "unofficial_internal_draft"
        assert translation["permission_status"] == "not_recorded"
        assert translation["original_controls"] is True


def test_claim_scope_manifest_blocks_active_release_and_constrains_critical_claims() -> None:
    science_root = _science_root()
    manifest = yaml.safe_load((science_root / "evidence-claim-scope-v0.1.yaml").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == "0.1"
    assert manifest["sci_profile_version"] == "0.1"
    assert manifest["review"] == {
        "review_status": "pending_review",
        "required_role": "Admin",
        "authorized_review_events": [],
    }
    mappings = {item["evidence_id"]: item for item in manifest["mappings"]}
    assert set(mappings) == EXPECTED_EVIDENCE_IDS
    assert all(item["may_enter_active_release"] is False for item in mappings.values())
    assert all(
        item["claim_scope"]["allowed_claims"] == []
        for item in mappings.values()
        if item["qualification_status"] == "inactive"
    )
    catalog = ScienceCatalog(science_root.parents[1])
    for evidence_id, item in mappings.items():
        evidence = catalog.evidence(evidence_id)
        assert item["allowed_original_text_hash"] == evidence.original_text_hash
        assert item["claim_scope"] == evidence.claim_scope
        assert item["claim_scope_hash"] == evidence.claim_scope_hash
        assert evidence.claim_scope["limitations"] == evidence.contextual_limitations
    assert mappings["sci-evidence:spin-coating:vendor-spin-time-guidance"]["claim_scope"][
        "forbidden_claim_families"
    ] == [
        "spin_coating.rpm_thickness_direction",
        "spin_coating.spin_speed_thickness_direction",
    ]
    observation_scope = mappings[
        "sci-evidence:spin-coating:vendor-spin-curve-observation"
    ]["claim_scope"]
    assert observation_scope["allowed_claims"][0]["claim_family"] == (
        "locator_bound.spin_coating.vendor_figure_labels"
    )
    assert observation_scope["allowed_claims"][0]["required_conditions"] == []
    assert mappings["sci-evidence:common:uncertainty-error"]["claim_scope"]["allowed_claims"][0]["claim_family"] == (
        "measurement.uncertainty_definition_only"
    )
    assert mappings["sci-evidence:common:repeatability-reproducibility"]["claim_scope"]["allowed_claims"][0]["claim_family"] == (
        "measurement.reproducibility_definition_only"
    )


def test_kcl_claim_scope_requires_lumped_no_accumulation_model() -> None:
    """The node equation must not be presented without its lumped-model continuity limit."""
    evidence = ScienceCatalog(_science_root().parents[1]).evidence(
        "sci-evidence:circuits:kcl-law"
    )
    claim = evidence.claim_scope["allowed_claims"][0]

    assert claim["required_conditions"] == [
        {
            "key": "current_reference_convention",
            "operator": "eq",
            "value": "consistent",
        },
        {"key": "circuit_model", "operator": "eq", "value": "lumped_matter"},
        {"key": "node_charge_accumulation", "operator": "eq", "value": "none"},
    ]
    assert any("lumped-matter" in item for item in evidence.claim_scope["limitations"])


def test_science_task_files_have_one_terminal_newline_without_blank_tail() -> None:
    paths = [*_science_root().rglob("*.md"), *_science_root().glob("*.yaml"), Path(__file__)]
    for path in paths:
        raw = path.read_bytes()
        assert raw.endswith(b"\n"), path
        assert not raw.endswith(b"\n\n"), path


def test_repository_stores_only_metadata_and_contextual_spans_not_source_bodies() -> None:
    for path, metadata, body in _science_documents(_science_root()):
        if metadata["type"] == "boi/science-source":
            assert len(body.encode("utf-8")) <= 2_500, path
            assert "## Full text" not in body, path
        else:
            assert metadata["science"]["original_text"] not in body, path
