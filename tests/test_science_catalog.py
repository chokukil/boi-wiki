from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml


EXPECTED_FOUNDATION_RELEASE_HASH = "sha256:e0f12bb1b3547d7df22da6738087f72470412161213e258bf4cf646a4eb9465b"


def _normalized_for_oracle(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalized_for_oracle(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalized_for_oracle(item) for item in value]
    return value


def _canonical_digest(metadata: dict, body: str) -> str:
    payload = {"metadata": _normalized_for_oracle(metadata), "body": body.replace("\r\n", "\n")}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _release_manifest_digest(metadata: dict, body: str) -> str:
    manifest = deepcopy(metadata)
    del manifest["science"]["content_hash"]
    return _canonical_digest(manifest, body)


def _metadata(science_type: str, science: dict, *, boi_id: str) -> dict:
    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "sci_profile_version": "0.1",
        "type": science_type,
        "title": boi_id,
        "description": "Science catalog fixture",
        "timestamp": "2026-08-25T09:00:00+09:00",
        "boi_id": boi_id,
        "visibility": "public",
        "classification": "internal",
        "owner": "science-admin",
        "acl_policy": "acl:public",
        "status": "reviewed",
        "review": {"reviewer": "science-reviewer"},
        "science": science,
    }
    if science_type in {"boi/science-knowledge", "boi/science-rule"}:
        metadata["source_refs"] = [{"type": "boi", "ref": ref} for ref in science["evidence_refs"]]
    else:
        metadata["source_refs"] = [{"type": "boi", "ref": "sci:evidence:fixture"}]
    return metadata


def _write_document(boi_root: Path, relative: str, metadata: dict, body: str = "# Science fixture\n") -> Path:
    path = boi_root / "public" / "science" / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + "---\n" + body, encoding="utf-8")
    return path


def _write_release(boi_root: Path, relative: str, metadata: dict, body: str = "# Science fixture\n") -> Path:
    metadata = deepcopy(metadata)
    metadata["science"]["content_hash"] = _release_manifest_digest(metadata, "\n" + body)
    return _write_document(boi_root, relative, metadata, body)


def _object_metadata() -> dict[str, tuple[str, dict, str]]:
    return {
        "source": (
            "boi/science-source",
            {"source_id": "sci:source:fixture", "source_role": "normative_definition", "original_url": "https://example.test/source", "content_hash": "sha256:source"},
            "sources/source.md",
        ),
        "evidence": (
            "boi/science-evidence",
            {"evidence_id": "sci:evidence:fixture", "source_id": "sci:source:fixture", "locator": {"section": "1"}, "original_text": "Source text.", "original_text_hash": "sha256:" + hashlib.sha256(b"Source text.").hexdigest(), "reviewed_translation": "원문"},
            "evidence/evidence.md",
        ),
        "knowledge": (
            "boi/science-knowledge",
            {"knowledge_id": "sci:knowledge:fixture", "pack_id": "sci-pack:fixture", "knowledge_kind": "definition", "assurance_basis": "formal_theorem", "statement": "Fixture knowledge.", "assumptions": [], "applicability": {}, "limitations": [], "evidence_refs": ["sci:evidence:fixture"]},
            "knowledge/knowledge.md",
        ),
        "rule": (
            "boi/science-rule",
            {"rule_id": "sci:rule:fixture", "pack_id": "sci-pack:fixture", "rule_kind": "directional_relation", "inputs": ["sci:concept:input", "sci:concept:response"], "outcomes": ["VIOLATION", "CONSISTENT"], "subject_concept_id": "sci:concept:input", "object_concept_id": "sci:concept:response", "relation_kind": "monotonic_direction", "expected_predicate": "decreases", "contradiction_predicates": ["increases"], "knowledge_refs": ["sci:knowledge:fixture"], "evidence_refs": ["sci:evidence:fixture"]},
            "rules/rule.md",
        ),
        "binding": (
            "boi/science-ontology-binding",
            {"binding_id": "sci:binding:fixture", "ontology_release_id": "sci:ontology:fixture", "concept_id": "sci:concept:fixture", "aliases": ["fixture"], "meaning": "Fixture meaning.", "domain": "test"},
            "ontology-bindings/binding.md",
        ),
        "matrix": (
            "boi/science-qualification-matrix",
            {"matrix_id": "sci:qualification:fixture", "rule_id": "sci:rule:fixture", "cases": [{"case_id": "case:second", "case_kind": "boundary", "claim_packet": {"claim_id": "claim:second"}}, {"case_id": "case:first", "case_kind": "violation", "claim_packet": {"claim_id": "claim:first"}}], "release_refs": ["sci-release:0.1.0"]},
            "qualification/matrix.md",
        ),
        "pack": (
            "boi/science-pack",
            {"pack_id": "sci-pack:fixture", "name": "fixture-pack", "version": "0.1.0", "dependencies": [], "knowledge_refs": ["sci:knowledge:fixture"], "rule_refs": ["sci:rule:fixture"], "qualification_refs": ["sci:qualification:fixture"]},
            "packs/pack.md",
        ),
    }


def _add_release(boi_root: Path, *, release_id: str = "sci-release:0.1.0", status: str = "active", components: list[str] | None = None, component_digests: dict[str, str] | None = None, last_safe_release_id: str | None = None, active: bool | None = None) -> None:
    science = {
        "release_id": release_id,
        "schema_version": "sci-profile/0.1",
        "content_hash": "",
        "status": status,
        "component_digests": component_digests or {},
        "known_limitations": ["fixture-only"],
        "components": components or [],
        "qualification_report": "sci:report:fixture",
    }
    if last_safe_release_id is not None:
        science["last_safe_release_id"] = last_safe_release_id
    if active is not None:
        science["active"] = active
    _write_release(boi_root, f"releases/{release_id.replace(':', '-')}.md", _metadata("boi/science-release", science, boi_id=release_id))


@pytest.fixture
def science_tree(tmp_path: Path) -> Path:
    boi_root = tmp_path / "boi"
    for name, (science_type, science, relative) in _object_metadata().items():
        _write_document(boi_root, relative, _metadata(science_type, science, boi_id=f"boi:public:science:{name}"))
    _add_release(boi_root)
    return boi_root


def _component_digest(boi_root: Path, relative: str) -> str:
    path = boi_root / "public" / "science" / relative
    frontmatter, body = path.read_text(encoding="utf-8").split("---", 2)[1:]
    return _canonical_digest(yaml.safe_load(frontmatter), body)


def _add_pack(
    boi_root: Path,
    *,
    pack_id: str,
    dependencies: list[dict[str, str]],
) -> str:
    relative = f"packs/{pack_id.replace(':', '-')}.md"
    science = {
        "pack_id": pack_id,
        "name": pack_id,
        "version": "0.1.0",
        "dependencies": dependencies,
        "knowledge_refs": [],
        "rule_refs": [],
        "qualification_refs": [],
    }
    _write_document(
        boi_root,
        relative,
        _metadata("boi/science-pack", science, boi_id=f"boi:public:science:{pack_id}"),
    )
    return relative


def _replace_release_components(
    boi_root: Path,
    release_id: str,
    components: dict[str, str],
) -> None:
    relative = f"releases/{release_id.replace(':', '-')}.md"
    path = boi_root / "public/science" / relative
    metadata = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["components"] = list(components)
    metadata["science"]["component_digests"] = components
    _write_release(boi_root, relative, metadata)


def test_release_resolver_rejects_digest_drift(science_tree: Path):
    """Changing a release-pinned rule must make its former digest unusable."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    digest = _component_digest(science_tree, "rules/rule.md")
    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["components"] = ["sci:rule:fixture"]
    metadata["science"]["component_digests"] = {"sci:rule:fixture": digest}
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)

    assert ScienceCatalog(science_tree).resolve_release("sci-release:0.1.0").release_id == "sci-release:0.1.0"

    rule_path = science_tree / "public/science/rules/rule.md"
    rule_metadata = yaml.safe_load(rule_path.read_text(encoding="utf-8").split("---", 2)[1])
    _write_document(science_tree, "rules/rule.md", rule_metadata, body="# Changed rule\n")
    with pytest.raises(ScienceCatalogError, match="component digest mismatch: sci:rule:fixture"):
        ScienceCatalog(science_tree).resolve_release("sci-release:0.1.0")


@pytest.mark.parametrize(
    "mutation",
    [
        "status",
        "known_limitations",
        "qualification_report",
        "components",
        "body",
    ],
)
def test_release_manifest_hash_rejects_every_pinned_manifest_mutation(science_tree: Path, mutation: str):
    """Changing a pinned manifest field or body without its hash must reject the Release."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    body = "# Science fixture\n"
    if mutation == "status":
        metadata["science"]["status"] = "release_candidate"
    elif mutation == "known_limitations":
        metadata["science"]["known_limitations"] = ["changed"]
    elif mutation == "qualification_report":
        metadata["science"]["qualification_report"] = "sci:report:changed"
    elif mutation == "components":
        metadata["science"].update({"components": ["sci:rule:fixture"], "component_digests": {"sci:rule:fixture": _component_digest(science_tree, "rules/rule.md")}})
    else:
        body = "# Changed release body\n"
    _write_document(science_tree, "releases/sci-release-0.1.0.md", metadata, body=body)

    with pytest.raises(ScienceCatalogError, match="release content hash mismatch: sci-release:0.1.0"):
        ScienceCatalog(science_tree).resolve_release("sci-release:0.1.0")


def test_release_manifest_hash_is_canonical_and_independent_of_metadata_key_order(science_tree: Path):
    """Reordering YAML keys must preserve the fixed, independently derived Release digest."""
    from boi_api.app.science.catalog import ScienceCatalog

    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata, body = release.read_text(encoding="utf-8").split("---", 2)[1:]
    parsed = yaml.safe_load(metadata)
    reversed_metadata = {key: parsed[key] for key in reversed(parsed)}
    reversed_metadata["science"] = {key: parsed["science"][key] for key in reversed(parsed["science"])}

    assert _release_manifest_digest(parsed, body) == EXPECTED_FOUNDATION_RELEASE_HASH
    _write_document(science_tree, "releases/sci-release-0.1.0.md", reversed_metadata, body=body.lstrip("\n"))

    assert ScienceCatalog(science_tree).resolve_release("sci-release:0.1.0").content_hash == EXPECTED_FOUNDATION_RELEASE_HASH


def test_catalog_indexes_only_science_ids_and_exposes_typed_accessors(science_tree: Path):
    """Replacing a lookup ID with an unindexed path must not escape the science catalog."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    catalog = ScienceCatalog(science_tree)

    assert catalog.source("sci:source:fixture").source_id == "sci:source:fixture"
    assert catalog.evidence("sci:evidence:fixture").evidence_id == "sci:evidence:fixture"
    assert catalog.knowledge("sci:knowledge:fixture").knowledge_id == "sci:knowledge:fixture"
    assert catalog.rule("sci:rule:fixture").rule_id == "sci:rule:fixture"
    assert catalog.ontology_binding("sci:binding:fixture").binding_id == "sci:binding:fixture"
    assert catalog.pack("sci-pack:fixture").pack_id == "sci-pack:fixture"
    assert catalog.pack_by_name("fixture-pack").pack_id == "sci-pack:fixture"
    assert catalog.qualification_matrix("sci:qualification:fixture").matrix_id == "sci:qualification:fixture"
    with pytest.raises(ScienceCatalogError, match="unknown science rule"):
        catalog.rule("../../rules/rule.md")


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "error"),
    [
        ("boi_id", "", "missing required metadata: boi_id"),
        ("review", {}, "team/public BoI requires reviewer"),
        ("status", "unreviewed", "status must be draft/reviewed/approved/deprecated"),
        ("visibility", "internet", "visibility must be private/team/public"),
        ("acl_policy", "acl:team:science", "public BoI acl_policy must be acl:public"),
    ],
)
def test_catalog_rejects_science_documents_that_fail_okf_or_boi_validation(
    science_tree: Path, field_name: str, invalid_value: object, error: str
):
    """Invalid core/profile/review/status/visibility/ACL metadata must never reach the index."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    source = science_tree / "public/science/sources/source.md"
    metadata = yaml.safe_load(source.read_text(encoding="utf-8").split("---", 2)[1])
    metadata[field_name] = invalid_value
    _write_document(science_tree, "sources/source.md", metadata)

    with pytest.raises(ScienceCatalogError, match=error):
        ScienceCatalog(science_tree)


def test_accessor_results_cannot_mutate_the_catalog_index(science_tree: Path):
    """Mutating a returned object must not alter the immutable indexed Science record."""
    from boi_api.app.science.catalog import ScienceCatalog

    catalog = ScienceCatalog(science_tree)
    returned_rule = catalog.rule("sci:rule:fixture")
    returned_rule.knowledge_refs.append("sci:knowledge:attacker")

    assert catalog.rule("sci:rule:fixture").knowledge_refs == ["sci:knowledge:fixture"]


def test_qualification_case_queries_and_release_sets_are_deterministic(science_tree: Path):
    """Reordering documents must not change resolved releases or qualification case order."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.models import ReleaseSelection

    digest = _component_digest(science_tree, "rules/rule.md")
    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["component_digests"] = {"sci:rule:fixture": digest}
    metadata["science"]["components"] = ["sci:rule:fixture"]
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)
    catalog = ScienceCatalog(science_tree)

    assert [case.case_id for case in catalog.qualification_cases("sci:rule:fixture")] == ["case:first", "case:second"]
    assert [case.case_id for case in catalog.qualification_cases_for_pack("sci-pack:fixture")] == ["case:first", "case:second"]
    assert catalog.claim_fixture("case:first") == {"claim_id": "claim:first"}
    resolved = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )
    assert resolved.foundation_release.release_id == "sci-release:0.1.0"
    assert resolved.domain_releases == ()
    assert resolved.application_releases == ()


def test_catalog_produces_digest_bound_typed_rule_set(science_tree: Path):
    """A resolved Rule must bind its typed semantics to the exact pinned OKF component."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.digests import sha256_digest
    from boi_api.app.science.models import ReleaseSelection

    digest = _component_digest(science_tree, "rules/rule.md")
    release_path = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release_path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["component_digests"] = {"sci:rule:fixture": digest}
    metadata["science"]["components"] = ["sci:rule:fixture"]
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    rule_set = catalog.resolve_rule_set(release_set)

    assert rule_set.release_set_digest == release_set.combined_digest
    assert len(rule_set.rules) == 1
    released = rule_set.rules[0]
    component = next(
        item for item in release_set.components if item.ref == released.rule.rule_id
    )
    assert released.component_digest == component.actual_digest == digest
    assert released.semantic_digest == component.semantic_digest == sha256_digest(released.rule)


@pytest.mark.parametrize("status", ["release_candidate", "superseded", "withdrawn"])
def test_active_release_rejects_when_no_active_release_exists(science_tree: Path, status: str):
    """Promoting a non-active release must not silently make it the current release."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["status"] = status
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)

    with pytest.raises(ScienceOperationalError, match="exactly one active Science release"):
        ScienceCatalog(science_tree).active_release()


def test_active_release_rejects_multiple_active_releases(science_tree: Path):
    """A second active release must not make selection depend on filesystem order."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _add_release(science_tree, release_id="sci-release:0.2.0", status="active")

    with pytest.raises(ScienceOperationalError, match="exactly one active Science release"):
        ScienceCatalog(science_tree).active_release()


def test_active_release_rejects_a_status_active_release_alongside_an_explicit_pointer(science_tree: Path):
    """An explicit marker must not hide a second status-active operational release."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _add_release(
        science_tree,
        release_id="sci-release:pointer",
        status="withdrawn",
        active=True,
        last_safe_release_id="sci-release:0.1.0",
    )

    with pytest.raises(ScienceOperationalError, match="exactly one active Science release"):
        ScienceCatalog(science_tree).active_release()


def test_withdrawn_active_pointer_resolves_only_declared_safe_release(science_tree: Path):
    """A withdrawn pointer must use its explicit safe release, never a candidate fallback."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _add_release(science_tree, release_id="sci-release:safe", status="withdrawn")
    _add_release(science_tree, release_id="sci-release:pointer", status="withdrawn", last_safe_release_id="sci-release:safe", active=True)
    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["status"] = "release_candidate"
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)

    with pytest.raises(ScienceOperationalError, match="last safe release is withdrawn"):
        ScienceCatalog(science_tree).active_release()


def test_withdrawn_active_pointer_resolves_a_declared_safe_superseded_release(science_tree: Path):
    """A single withdrawn marker may explicitly fall back to its last safe operational Release."""
    from boi_api.app.science.catalog import ScienceCatalog

    _add_release(science_tree, release_id="sci-release:safe", status="superseded")
    _add_release(
        science_tree,
        release_id="sci-release:pointer",
        status="withdrawn",
        active=True,
        last_safe_release_id="sci-release:safe",
    )
    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["status"] = "release_candidate"
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)

    assert ScienceCatalog(science_tree).active_release().release_id == "sci-release:safe"


def test_withdrawn_active_pointer_reports_missing_declared_safe_release_as_operational_failure(science_tree: Path):
    """A missing safe Release is unavailable operationally, not a catalog programming error."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _add_release(
        science_tree,
        release_id="sci-release:pointer",
        status="withdrawn",
        active=True,
        last_safe_release_id="sci-release:missing",
    )
    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["status"] = "release_candidate"
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)

    with pytest.raises(ScienceOperationalError, match="last safe release is unavailable: sci-release:missing"):
        ScienceCatalog(science_tree).active_release()


def test_explicit_active_pointer_rejects_a_nonactive_nonwithdrawn_release(science_tree: Path):
    """A stale explicit pointer must not select a superseded release as active."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"].update({"status": "superseded", "active": True})
    metadata["science"]["components"] = ["sci:rule:fixture"]
    metadata["science"]["component_digests"] = {"sci:rule:fixture": _component_digest(science_tree, "rules/rule.md")}
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)

    with pytest.raises(ScienceOperationalError, match="active pointer has invalid status"):
        ScienceCatalog(science_tree).active_release()


def test_catalog_rejects_duplicate_ids_and_broken_component_references(science_tree: Path):
    """Duplicate IDs and dangling release components must stop immutable resolution."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    duplicate = deepcopy(_object_metadata()["rule"])
    _write_document(science_tree, "rules/duplicate.md", _metadata(duplicate[0], duplicate[1], boi_id="boi:public:science:duplicate"))
    with pytest.raises(ScienceCatalogError, match="duplicate science rule ID: sci:rule:fixture"):
        ScienceCatalog(science_tree)

    (science_tree / "public/science/rules/duplicate.md").unlink()
    release = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["components"] = ["sci:rule:missing"]
    metadata["science"]["component_digests"] = {"sci:rule:missing": "sha256:missing"}
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)
    with pytest.raises(ScienceCatalogError, match="unknown science component: sci:rule:missing"):
        ScienceCatalog(science_tree).resolve_release("sci-release:0.1.0")


def test_catalog_rejects_an_id_reused_by_different_science_object_kinds(science_tree: Path):
    """A release component ID must not be ambiguous between two indexed object kinds."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    science_type, science, _relative = _object_metadata()["source"]
    conflicting_source = deepcopy(science)
    conflicting_source["source_id"] = "sci:rule:fixture"
    _write_document(science_tree, "sources/conflicting-source.md", _metadata(science_type, conflicting_source, boi_id="boi:public:science:conflicting-source"))

    with pytest.raises(ScienceCatalogError, match="duplicate science ID: sci:rule:fixture"):
        ScienceCatalog(science_tree)


def test_catalog_does_not_index_a_science_document_without_profile_version(science_tree: Path):
    """Bypassing direct lint must not let an unversioned Science object enter the catalog."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    source = science_tree / "public/science/sources/source.md"
    metadata = yaml.safe_load(source.read_text(encoding="utf-8").split("---", 2)[1])
    del metadata["sci_profile_version"]
    _write_document(science_tree, "sources/source.md", metadata)

    with pytest.raises(ScienceCatalogError, match="sci_profile_version must be exactly string '0.1'"):
        ScienceCatalog(science_tree)


def test_catalog_rejects_a_pack_dependency_without_typed_relation(science_tree: Path):
    """Catalog reference checks must not treat a bare Pack ref as a dependency edge."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError

    pack = science_tree / "public/science/packs/pack.md"
    metadata = yaml.safe_load(pack.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["dependencies"] = ["sci-pack:fixture"]
    _write_document(science_tree, "packs/pack.md", metadata)

    with pytest.raises(ScienceCatalogError, match="typed relationship edges"):
        ScienceCatalog(science_tree)


def test_resolved_release_set_preserves_roles_and_builds_deterministic_combined_rules(
    science_tree: Path,
):
    """Dropping role, digest, component, or rule composition must break the release boundary."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.models import ReleaseSelection, ResolvedReleaseSet

    foundation_components = {
        "sci-pack:fixture": _component_digest(science_tree, "packs/pack.md"),
        "sci:rule:fixture": _component_digest(science_tree, "rules/rule.md"),
    }
    _replace_release_components(
        science_tree, "sci-release:0.1.0", foundation_components
    )
    domain_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:domain",
        dependencies=[{"relation": "depends_on", "ref": "sci-pack:fixture"}],
    )
    _add_release(science_tree, release_id="sci-release:domain", status="release_candidate")
    _replace_release_components(
        science_tree,
        "sci-release:domain",
        {"sci-pack:domain": _component_digest(science_tree, domain_relative)},
    )
    application_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:application",
        dependencies=[{"relation": "specializes", "ref": "sci-pack:domain"}],
    )
    _add_release(
        science_tree, release_id="sci-release:application", status="release_candidate"
    )
    _replace_release_components(
        science_tree,
        "sci-release:application",
        {"sci-pack:application": _component_digest(science_tree, application_relative)},
    )
    selection = ReleaseSelection(
        foundation="sci-release:0.1.0",
        domains=["sci-release:domain"],
        applications=["sci-release:application"],
    )
    catalog = ScienceCatalog(science_tree)

    resolved = catalog.resolve_release_set(selection)
    rule_set = catalog.resolve_rule_set(resolved)

    assert isinstance(resolved, ResolvedReleaseSet)
    assert resolved.selection == selection
    assert resolved.foundation_release.release_id == selection.foundation
    assert [release.release_id for release in resolved.domain_releases] == selection.domains
    assert [release.release_id for release in resolved.application_releases] == selection.applications
    assert resolved.compatibility.compatible is True
    assert resolved.release_digests == {
        release_id: resolved_release.content_hash
        for release_id, resolved_release in [
            (resolved.foundation_release.release_id, resolved.foundation_release),
            (resolved.domain_releases[0].release_id, resolved.domain_releases[0]),
            (resolved.application_releases[0].release_id, resolved.application_releases[0]),
        ]
    }
    assert [component.ref for component in resolved.components] == [
        "sci-pack:application",
        "sci-pack:domain",
        "sci-pack:fixture",
        "sci:rule:fixture",
    ]
    assert [component.ref for component in resolved.rule_components] == ["sci:rule:fixture"]
    assert resolved.combined_digest.startswith("sha256:")
    assert rule_set.release_set_digest == resolved.combined_digest
    assert [released.rule.rule_id for released in rule_set.rules] == ["sci:rule:fixture"]
    assert catalog.resolve_release_set(selection).combined_digest == resolved.combined_digest


def test_release_set_rejects_duplicate_components_across_release_roles(science_tree: Path):
    """The same component must not be silently relabeled as both Foundation and Domain."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    digest = _component_digest(science_tree, "packs/pack.md")
    _replace_release_components(science_tree, "sci-release:0.1.0", {"sci-pack:fixture": digest})
    _add_release(science_tree, release_id="sci-release:domain", status="release_candidate")
    _replace_release_components(science_tree, "sci-release:domain", {"sci-pack:fixture": digest})

    with pytest.raises(ScienceOperationalError, match="duplicate component across releases"):
        ScienceCatalog(science_tree).resolve_release_set(
            ReleaseSelection(
                foundation="sci-release:0.1.0", domains=["sci-release:domain"]
            )
        )


def test_release_set_rejects_pack_dependency_absent_from_selection(science_tree: Path):
    """A globally indexed Pack cannot satisfy a dependency unless its Release is selected."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    foundation_digest = _component_digest(science_tree, "packs/pack.md")
    _replace_release_components(
        science_tree, "sci-release:0.1.0", {"sci-pack:fixture": foundation_digest}
    )
    _add_pack(science_tree, pack_id="sci-pack:unselected", dependencies=[])
    domain_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:domain",
        dependencies=[{"relation": "uses", "ref": "sci-pack:unselected"}],
    )
    _add_release(science_tree, release_id="sci-release:domain", status="release_candidate")
    _replace_release_components(
        science_tree,
        "sci-release:domain",
        {"sci-pack:domain": _component_digest(science_tree, domain_relative)},
    )

    with pytest.raises(ScienceOperationalError, match="incompatible Pack dependency"):
        ScienceCatalog(science_tree).resolve_release_set(
            ReleaseSelection(
                foundation="sci-release:0.1.0", domains=["sci-release:domain"]
            )
        )


def test_catalog_to_engine_cross_task_proof_uses_exact_full_release_selection(
    science_tree: Path,
):
    """Breaking any stored-object, release, rule, grounding, or role boundary must fail E2E."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.engine import verify_claim
    from boi_api.app.science.models import ClaimPacket, PrimaryVerdict, ReleaseSelection

    foundation_components = {
        "sci:source:fixture": _component_digest(science_tree, "sources/source.md"),
        "sci:evidence:fixture": _component_digest(science_tree, "evidence/evidence.md"),
        "sci:knowledge:fixture": _component_digest(science_tree, "knowledge/knowledge.md"),
        "sci:rule:fixture": _component_digest(science_tree, "rules/rule.md"),
        "sci-pack:fixture": _component_digest(science_tree, "packs/pack.md"),
    }
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        foundation_components,
    )
    domain_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:domain-proof",
        dependencies=[{"relation": "uses", "ref": "sci-pack:fixture"}],
    )
    _add_release(
        science_tree, release_id="sci-release:domain-proof", status="release_candidate"
    )
    _replace_release_components(
        science_tree,
        "sci-release:domain-proof",
        {"sci-pack:domain-proof": _component_digest(science_tree, domain_relative)},
    )
    application_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:application-proof",
        dependencies=[{"relation": "specializes", "ref": "sci-pack:domain-proof"}],
    )
    _add_release(
        science_tree,
        release_id="sci-release:application-proof",
        status="release_candidate",
    )
    _replace_release_components(
        science_tree,
        "sci-release:application-proof",
        {
            "sci-pack:application-proof": _component_digest(
                science_tree, application_relative
            )
        },
    )
    selection = ReleaseSelection(
        foundation="sci-release:0.1.0",
        domains=["sci-release:domain-proof"],
        applications=["sci-release:application-proof"],
    )
    claim = ClaimPacket.model_validate(
        {
            "claim_id": "claim:cross-task-proof",
            "document_ref": "boi:public:science:document:proof",
            "document_digest": "sha256:document-proof",
            "source_span": {
                "start": 0,
                "end": len("input increases response"),
                "exact": "input increases response",
            },
            "normalized_claim": {
                "subject_concept_id": "sci:concept:input",
                "relation_kind": "monotonic_direction",
                "predicate": "increases",
                "object_concept_id": "sci:concept:response",
                "polarity": "positive",
                "quantities": [],
                "conditions": [],
                "process_stage": None,
                "material_state": None,
            },
            "interpretation": {
                "ontology_refs": ["sci:concept:input", "sci:concept:response"],
                "ambiguity_ids": [],
                "user_confirmed": True,
            },
        }
    )
    catalog = ScienceCatalog(science_tree)

    release_set = catalog.resolve_release_set(selection)
    rule_set = catalog.resolve_rule_set(release_set)
    packet = verify_claim(claim, release_set, rule_set=rule_set)

    assert packet.verdict is PrimaryVerdict.VIOLATION
    assert packet.decisive_rule_ids == ["sci:rule:fixture"]
    assert packet.knowledge_refs == ["sci:knowledge:fixture"]
    assert packet.evidence_refs == ["sci:evidence:fixture"]
    assert packet.releases.selection == selection
    assert packet.releases.digests == release_set.release_digests
    assert packet.releases.combined_digest == release_set.combined_digest
