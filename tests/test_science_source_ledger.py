from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import yaml

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.profile import validate_sci_profile_metadata
from boi_api.app.okf import split_frontmatter


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
        "vendor-spin-curve-observation",
    )),
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
    assert all(item["allowed_claims"] == [] for item in mappings.values() if item["qualification_status"] == "inactive")
    catalog = ScienceCatalog(science_root.parents[1])
    for evidence_id, item in mappings.items():
        evidence = catalog.evidence(evidence_id)
        assert item["allowed_original_text_hash"] == evidence.original_text_hash
        assert item["binding_contextual_limitations"] == evidence.contextual_limitations
    assert mappings["sci-evidence:spin-coating:vendor-spin-time-guidance"]["forbidden_claim_families"] == [
        "spin_coating.rpm_thickness_direction"
    ]
    assert mappings["sci-evidence:spin-coating:vendor-spin-curve-observation"]["allowed_claims"][0][
        "claim_family"
    ] == "spin_coating.rpm_thickness_direction.product_scoped_figure_observation"
    assert mappings["sci-evidence:common:uncertainty-error"]["allowed_claims"][0]["claim_family"] == (
        "measurement.uncertainty_definition_only"
    )
    assert mappings["sci-evidence:common:repeatability-reproducibility"]["allowed_claims"][0]["claim_family"] == (
        "measurement.reproducibility_definition_only"
    )


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
