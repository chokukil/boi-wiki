from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest
import yaml


def valid_boi_metadata(science_type: str) -> dict:
    return {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "sci_profile_version": "0.1",
        "type": science_type,
        "title": "Science fixture",
        "description": "Science profile test fixture",
        "timestamp": "2026-08-25T09:00:00+09:00",
        "boi_id": "boi:public:science:fixture",
        "visibility": "public",
        "classification": "internal",
        "owner": "science-admin",
        "acl_policy": "acl:public",
        "status": "reviewed",
        "source_refs": [{"type": "boi", "ref": "sci:evidence:fixture"}],
        "review": {"reviewer": "science-reviewer"},
    }


def valid_science_metadata(science_type: str) -> dict:
    metadata = valid_boi_metadata(science_type)
    original_text = "The measurement is traceable."
    claim_scope = {
        "schema_version": "0.1",
        "allowed_claims": [
            {
                "claim_family": "fixture.measurement_traceability",
                "purpose": "Support only the locator-bound fixture statement.",
                "required_conditions": ["The exact reviewed locator applies."],
            }
        ],
        "forbidden_claim_families": ["fixture.unbounded"],
        "limitations": ["This fixture does not establish traceability by itself."],
    }
    from boi_api.app.science.digests import sha256_digest

    science_by_type = {
        "boi/science-source": {
            "source_id": "sci-source:fixture",
            "source_role": "normative_definition",
            "original_url": "https://example.test/source",
            "content_hash": "sha256:source",
        },
        "boi/science-evidence": {
            "evidence_id": "sci:evidence:fixture",
            "source_id": "sci-source:fixture",
            "locator": {"section": "1"},
            "original_text": original_text,
            "original_text_hash": "sha256:" + hashlib.sha256(original_text.encode("utf-8")).hexdigest(),
            "reviewed_translation": "측정은 추적 가능하다.",
            "claim_scope": claim_scope,
            "claim_scope_hash": sha256_digest(claim_scope),
        },
        "boi/science-knowledge": {
            "knowledge_id": "sci:knowledge:fixture",
            "pack_id": "sci-pack:fixture",
            "knowledge_kind": "definition",
            "assurance_basis": "formal_theorem",
            "statement": "A fixture statement.",
            "assumptions": [],
            "applicability": {},
            "limitations": [],
            "evidence_refs": ["sci:evidence:fixture"],
        },
        "boi/science-rule": {
            "rule_id": "sci-rule:fixture",
            "pack_id": "sci-pack:fixture",
            "rule_kind": "directional_relation",
            "inputs": ["sci:input:fixture"],
            "outcomes": ["CONSISTENT"],
            "knowledge_refs": ["sci:knowledge:fixture"],
            "evidence_refs": ["sci:evidence:fixture"],
            "evidence_uses": [
                {
                    "evidence_ref": "sci:evidence:fixture",
                    "claim_family": "fixture.measurement_traceability",
                    "purpose": "Support only the locator-bound fixture statement.",
                    "required_conditions": ["The exact reviewed locator applies."],
                }
            ],
        },
        "boi/science-pack": {
            "pack_id": "sci-pack:fixture",
            "version": "0.1.0",
            "dependencies": [],
            "knowledge_refs": ["sci:knowledge:fixture"],
            "rule_refs": ["sci-rule:fixture"],
            "qualification_refs": ["sci:qualification:fixture"],
        },
        "boi/science-ontology-binding": {
            "binding_id": "sci:binding:fixture",
            "ontology_release_id": "sci:ontology:fixture",
            "concept_id": "sci:concept:fixture",
            "aliases": ["fixture"],
            "meaning": "Fixture meaning.",
            "domain": "test",
        },
        "boi/science-qualification-matrix": {
            "matrix_id": "sci:qualification:fixture",
            "rule_id": "sci-rule:fixture",
            "cases": [{"case_id": "case:fixture"}],
            "release_refs": ["sci-release:fixture"],
        },
        "boi/science-release": {
            "release_id": "sci-release:fixture",
            "schema_version": "sci-profile/0.1",
            "content_hash": "sha256:release",
            "status": "release_candidate",
            "component_digests": {"sci-rule:fixture": "sha256:rule"},
            "known_limitations": [],
            "components": ["sci-rule:fixture"],
            "qualification_report": "sci:report:fixture",
        },
    }
    metadata["science"] = science_by_type[science_type]
    if science_type not in {"boi/science-knowledge", "boi/science-rule"}:
        metadata.pop("source_refs")
    return metadata


@pytest.mark.parametrize(
    ("science_type", "required_field"),
    [
        ("boi/science-source", "source_id"),
        ("boi/science-evidence", "reviewed_translation"),
        ("boi/science-knowledge", "evidence_refs"),
        ("boi/science-rule", "knowledge_refs"),
        ("boi/science-pack", "qualification_refs"),
        ("boi/science-ontology-binding", "meaning"),
        ("boi/science-qualification-matrix", "cases"),
        ("boi/science-release", "qualification_report"),
    ],
)
def test_science_stored_object_requires_its_profile_fields(science_type: str, required_field: str):
    """Removing this field would let an incomplete stored Science object pass lint."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata(science_type)
    del metadata["science"][required_field]

    assert f"science.{required_field} is required" in validate_sci_profile_metadata(metadata)


def test_science_knowledge_requires_evidence_and_disallows_confidence():
    """Adding a scalar confidence or omitting provenance must reject Knowledge."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-knowledge")
    metadata["science"]["confidence"] = 0.93
    assert "science.confidence is forbidden" in validate_sci_profile_metadata(metadata)

    del metadata["science"]["evidence_refs"]
    assert "science.evidence_refs is required" in validate_sci_profile_metadata(metadata)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "error"),
    [
        ("knowledge_kind", "confidence", "science.knowledge_kind is invalid"),
        ("assurance_basis", "certain", "science.assurance_basis is invalid"),
    ],
)
def test_science_knowledge_rejects_values_outside_the_spec(field_name: str, invalid_value: str, error: str):
    """An unknown classification must not be accepted as a scientific assurance claim."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-knowledge")
    metadata["science"][field_name] = invalid_value

    assert error in validate_sci_profile_metadata(metadata)


@pytest.mark.parametrize("original_url", ["http://example.test/source", {}, "https://"])
def test_public_source_requires_string_https_url_with_host(original_url: object):
    """A public Source must not accept an insecure, non-string, or hostless URL."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-source")
    metadata["science"]["original_url"] = original_url

    assert "science.original_url must use HTTPS for public sources" in validate_sci_profile_metadata(metadata)


def test_evidence_hash_must_match_its_utf8_original_text():
    """Changing the reviewed original span without its hash must fail validation."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-evidence")
    metadata["science"]["original_text"] = "The measurement is not traceable."

    assert "science.original_text_hash must match original_text UTF-8 SHA-256" in validate_sci_profile_metadata(metadata)


def test_evidence_claim_scope_is_closed_and_hash_bound():
    """Changing executable Evidence scope without its digest must fail the profile."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-evidence")
    metadata["science"]["claim_scope"]["allowed_claims"][0]["purpose"] = "Broader purpose."

    assert "science.claim_scope_hash must match science.claim_scope" in validate_sci_profile_metadata(metadata)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("extra_scope_key", "science.claim_scope has unsupported fields"),
        ("extra_claim_key", "science.claim_scope.allowed_claims items have unsupported fields"),
        ("blank_family", "science.claim_scope.allowed_claims claim_family must be a nonempty string"),
        ("collision", "science.claim_scope cannot both allow and forbid the same claim family"),
    ],
)
def test_evidence_claim_scope_rejects_open_or_ambiguous_authority(mutation: str, error: str):
    """Evidence authorization must remain a small closed vocabulary."""
    from boi_api.app.science.digests import sha256_digest
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-evidence")
    scope = metadata["science"]["claim_scope"]
    if mutation == "extra_scope_key":
        scope["free_form_authority"] = True
    elif mutation == "extra_claim_key":
        scope["allowed_claims"][0]["statement"] = "Detached advisory text."
    elif mutation == "blank_family":
        scope["allowed_claims"][0]["claim_family"] = " "
    else:
        scope["forbidden_claim_families"] = [scope["allowed_claims"][0]["claim_family"]]
    metadata["science"]["claim_scope_hash"] = sha256_digest(scope)

    assert error in validate_sci_profile_metadata(metadata)


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "error"),
    [
        ("original_text", {}, "science.original_text must be a string"),
        ("original_text_hash", {}, "science.original_text_hash must be a string"),
    ],
)
def test_evidence_requires_string_text_and_hash(field_name: str, invalid_value: object, error: str):
    """Replacing either Evidence hash input with an object must not bypass integrity validation."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-evidence")
    metadata["science"][field_name] = invalid_value

    assert error in validate_sci_profile_metadata(metadata)


def test_science_evidence_refs_must_match_okf_source_refs():
    """Changing a science evidence edge must not leave the compatible OKF edge stale."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-rule")
    metadata["science"]["evidence_refs"] = ["sci:evidence:other"]

    assert "science.evidence_refs must match OKF source_refs" in validate_sci_profile_metadata(metadata)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("missing", "science.evidence_uses is required"),
        ("wrong_ref", "science.evidence_uses must exactly match science.evidence_refs"),
        ("duplicate_ref", "science.evidence_refs must be unique"),
        ("extra_key", "science.evidence_uses items have unsupported fields"),
        ("blank_purpose", "science.evidence_uses purpose must be a nonempty string"),
    ],
)
def test_science_rule_profile_validates_closed_typed_evidence_uses(
    mutation: str, error: str
):
    """A malformed Rule use must fail lint before Catalog resolution."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-rule")
    if mutation == "missing":
        del metadata["science"]["evidence_uses"]
    elif mutation == "wrong_ref":
        metadata["science"]["evidence_uses"][0]["evidence_ref"] = "sci:evidence:other"
    elif mutation == "duplicate_ref":
        metadata["science"]["evidence_refs"].append("sci:evidence:fixture")
        metadata["source_refs"].append(
            {"type": "boi", "ref": "sci:evidence:fixture"}
        )
    elif mutation == "extra_key":
        metadata["science"]["evidence_uses"][0]["advisory"] = True
    else:
        metadata["science"]["evidence_uses"][0]["purpose"] = " "

    assert error in validate_sci_profile_metadata(metadata)


@pytest.mark.parametrize(
    ("location", "invalid_value", "error"),
    [
        ("source_refs", {"ref": "sci:evidence:fixture"}, "source_refs must be a list"),
        ("science.evidence_refs", "sci:evidence:fixture", "science.evidence_refs must be a list"),
        ("source_refs", [{}], "source_refs items must be nonempty strings or mappings with ref"),
        ("science.evidence_refs", [{}], "science.evidence_refs items must be nonempty strings or mappings with ref"),
    ],
)
def test_science_evidence_reference_collections_reject_malformed_values(
    location: str, invalid_value: object, error: str
):
    """Malformed reference collections must not collapse to matching empty sets."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-rule")
    if location == "source_refs":
        metadata[location] = invalid_value
    else:
        metadata["science"]["evidence_refs"] = invalid_value

    assert error in validate_sci_profile_metadata(metadata)


def test_lint_markdown_file_includes_science_profile_errors(tmp_path: Path):
    """The general lint entrypoint must enforce Science metadata, not just direct callers."""
    from boi_api.app.okf import lint_markdown_file

    boi_root = tmp_path / "boi"
    path = boi_root / "public" / "science" / "knowledge.md"
    path.parent.mkdir(parents=True)
    metadata = deepcopy(valid_science_metadata("boi/science-knowledge"))
    metadata["science"]["confidence"] = 0.93
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---\n# Fixture\n", encoding="utf-8")

    errors, _edges = lint_markdown_file(path, boi_root=boi_root)

    assert "science.confidence is forbidden" in errors


def test_non_science_documents_do_not_receive_science_errors():
    """Ordinary OKF documents must keep their existing validation behavior."""
    from boi_api.app.science.profile import is_science_document, validate_sci_profile_metadata

    metadata = valid_boi_metadata("boi/test")

    assert not is_science_document(metadata)
    assert validate_sci_profile_metadata(metadata) == []


@pytest.mark.parametrize("profile_version", [None, 0.1, "0.2"])
def test_every_science_document_requires_exact_string_profile_version(profile_version: object):
    """Dropping or loosening the profile version must not admit an unknown Science schema."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-source")
    if profile_version is None:
        del metadata["sci_profile_version"]
    else:
        metadata["sci_profile_version"] = profile_version

    assert "sci_profile_version must be exactly string '0.1'" in validate_sci_profile_metadata(
        metadata
    )


@pytest.mark.parametrize(
    ("dependency", "error"),
    [
        ("sci-pack:foundation", "science.dependencies items must be typed relationship edges"),
        ({"ref": "sci-pack:foundation"}, "science.dependencies relation is required"),
        (
            {"relation": "override", "ref": "sci-pack:foundation"},
            "science.dependencies relation is invalid",
        ),
        (
            {"relation": "custom", "ref": "sci-pack:foundation"},
            "science.dependencies relation is invalid",
        ),
        ({"relation": "uses", "ref": ""}, "science.dependencies ref is invalid"),
        ({"relation": "uses", "ref": "sci-pack:bad ref"}, "science.dependencies ref is invalid"),
        (
            {"relation": "uses", "ref": "sci-pack:foundation", "override": True},
            "science.dependencies items must be typed relationship edges",
        ),
    ],
)
def test_pack_dependencies_require_closed_typed_relationship_edges(dependency: object, error: str):
    """A primitive, missing, malformed, override, or unknown Pack edge must fail profile lint."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-pack")
    metadata["science"]["dependencies"] = [dependency]

    assert error in validate_sci_profile_metadata(metadata)


def test_pack_dependencies_collection_must_be_a_list():
    """A mapping collection must not bypass item-level typed-edge validation."""
    from boi_api.app.science.profile import validate_sci_profile_metadata

    metadata = valid_science_metadata("boi/science-pack")
    metadata["science"]["dependencies"] = {
        "relation": "uses",
        "ref": "sci-pack:foundation",
    }

    assert "science.dependencies must be a list" in validate_sci_profile_metadata(metadata)
