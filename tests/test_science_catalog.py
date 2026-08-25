from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml

EXPECTED_FOUNDATION_RELEASE_HASH = "sha256:e801dfbe0f2ef880ad97cee1cf278da9e19fcc9fcf3c8359f8713432d80b1e21"


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


def _fixture_claim_scope() -> dict:
    return {
        "schema_version": "0.1",
        "allowed_claims": [
            {
                "claim_family": "fixture.direction",
                "purpose": "Support only the fixture directional relation.",
                "required_conditions": [
                    {"key": "fixture_scope", "operator": "eq", "value": "controlled"}
                ],
            }
        ],
        "forbidden_claim_families": ["fixture.unbounded"],
        "limitations": ["This Evidence supports only a test fixture."],
    }


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
    if science_type in {"boi/science-source", "boi/science-evidence"}:
        metadata.update(
            {
                "author": {"type": "agent", "agent_id": "fixture-author"},
                "status": "draft",
                "review": {
                    "review_status": "pending_review",
                    "required_role": "Admin",
                    "authorized_review_events": [],
                },
            }
        )
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
    claim_scope = _fixture_claim_scope()
    return {
        "source": (
            "boi/science-source",
            {"source_id": "sci:source:fixture", "source_role": "normative_definition", "original_url": "https://example.test/source", "content_hash": "sha256:" + "1" * 64, "retrieval_status": "verified", "retrieved_at": "2026-08-25T09:05:00+09:00", "curated_at": "2026-08-25T09:10:00+09:00", "release_eligibility": "blocked_pending_authorized_admin_review"},
            "sources/source.md",
        ),
        "evidence": (
            "boi/science-evidence",
            {"evidence_id": "sci:evidence:fixture", "source_id": "sci:source:fixture", "locator": {"medium": "pdf", "resource_url": "https://example.test/source.pdf", "requested_url": "https://example.test/source.pdf", "resolved_url": "https://example.test/source.pdf", "content_hash": "sha256:" + "2" * 64, "retrieved_at": "2026-08-25T09:05:00+09:00", "exact": True, "hash_scope": "retrieved_pdf_bytes", "section": "1", "pdf_page_index": 0, "printed_page": "1"}, "original_text": "Source text.", "original_text_hash": "sha256:" + hashlib.sha256(b"Source text.").hexdigest(), "reviewed_translation": "원문", "decision_eligibility": "pending_review", "curated_at": "2026-08-25T09:10:00+09:00", "release_eligibility": "blocked_pending_authorized_admin_review", "claim_scope": claim_scope, "claim_scope_hash": "sha256:" + hashlib.sha256(json.dumps(claim_scope, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()},
            "evidence/evidence.md",
        ),
        "knowledge": (
            "boi/science-knowledge",
            {"knowledge_id": "sci:knowledge:fixture", "pack_id": "sci-pack:fixture", "knowledge_kind": "definition", "assurance_basis": "formal_theorem", "statement": "Fixture knowledge.", "assumptions": [], "applicability": {}, "limitations": [], "evidence_refs": ["sci:evidence:fixture"]},
            "knowledge/knowledge.md",
        ),
        "rule": (
            "boi/science-rule",
            {"rule_id": "sci:rule:fixture", "pack_id": "sci-pack:fixture", "rule_kind": "directional_relation", "inputs": ["sci:concept:input", "sci:concept:response"], "outcomes": ["VIOLATION", "CONSISTENT"], "subject_concept_id": "sci:concept:input", "object_concept_id": "sci:concept:response", "relation_kind": "monotonic_direction", "expected_predicate": "decreases", "contradiction_predicates": ["increases"], "required_conditions": [{"key": "fixture_scope", "operator": "eq", "value": "controlled"}], "knowledge_refs": ["sci:knowledge:fixture"], "evidence_refs": ["sci:evidence:fixture"], "evidence_uses": [{"evidence_ref": "sci:evidence:fixture", "claim_family": "fixture.direction", "purpose": "Support only the fixture directional relation."}]},
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
        "holdout_manifest_ref": (
            "boi:public:science:holdout-manifest:"
            + release_id.removeprefix("sci-release:")
        ),
    }
    if last_safe_release_id is not None:
        science["last_safe_release_id"] = last_safe_release_id
    if active is not None:
        science["active"] = active
    if status in {"active", "superseded"}:
        science["frozen_release_content_hash"] = "sha256:" + "0" * 64
        science["decision_material_digest"] = "sha256:" + "0" * 64
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


def _approve_decision_document(
    boi_root: Path,
    relative: str,
    *,
    reviewer_id: str = "reviewer-1",
    occurred_at: str = "2026-08-25T09:30:00+09:00",
) -> None:
    path = boi_root / "public" / "science" / relative
    metadata = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["author"] = {"type": "agent", "agent_id": "fixture-author"}
    metadata["status"] = "approved"
    metadata["review"] = {
        "reviewer": reviewer_id,
        "reviewed_at": occurred_at,
        "review_status": "approved",
        "required_role": "Admin",
        "authorized_review_events": [
            {
                "decision": "approved",
                "actor": {"type": "human", "user_id": reviewer_id},
                "occurred_at": occurred_at,
                "role": "Admin",
            }
        ],
    }
    metadata["science"]["release_eligibility"] = "active_release_eligible"
    if metadata["type"] == "boi/science-evidence":
        metadata["science"]["decision_eligibility"] = "eligible"
    _write_document(boi_root, relative, metadata)


def _trusted_admin_roles(actor: dict[str, str]) -> set[str]:
    if actor == {"type": "human", "user_id": "reviewer-1"}:
        return {"science.admin"}
    if actor == {"type": "human", "user_id": "holdout-reviewer-1"}:
        return {"science.independent_holdout_reviewer"}
    return set()


def _trusted_clock() -> datetime:
    return datetime.fromisoformat("2026-08-25T10:00:00+09:00")


def _activate_release_document(
    boi_root: Path,
    release_id: str = "sci-release:0.1.0",
    *,
    reviewer_id: str = "reviewer-1",
    approved_at: str = "2026-08-25T09:30:00+09:00",
    activated_at: str = "2026-08-25T09:40:00+09:00",
) -> None:
    from boi_api.app.science.catalog import (
        ScienceCatalog,
        release_decision_material_digest,
    )

    relative = f"releases/{release_id.replace(':', '-')}.md"
    path = boi_root / "public" / "science" / relative
    frozen_release = ScienceCatalog(boi_root).resolve_release(release_id)
    metadata = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["author"] = {"type": "agent", "agent_id": "fixture-release-author"}
    metadata["status"] = "approved"
    metadata["review"] = {
        "reviewer": reviewer_id,
        "reviewed_at": approved_at,
        "review_status": "approved",
        "required_role": "Admin",
        "authorized_review_events": [
            {
                "decision": "approved",
                "actor": {"type": "human", "user_id": reviewer_id},
                "occurred_at": approved_at,
            }
        ],
    }
    target_status = (
        "superseded" if frozen_release.status == "superseded" else "active"
    )
    metadata["activation"] = {
        "activation_status": target_status,
        "authorized_activation_events": [
            {
                "decision": "activated",
                "actor": {"type": "human", "user_id": reviewer_id},
                "occurred_at": activated_at,
            }
        ],
    }
    metadata["science"]["status"] = target_status
    metadata["science"]["frozen_release_content_hash"] = frozen_release.content_hash
    metadata["science"]["decision_material_digest"] = (
        release_decision_material_digest(frozen_release)
    )
    metadata["science"]["release_eligibility"] = "active_release_eligible"
    _write_release(boi_root, relative, metadata)


def _freeze_release_document(
    boi_root: Path, release_id: str = "sci-release:0.1.0"
) -> None:
    relative = f"releases/{release_id.replace(':', '-')}.md"
    path = boi_root / "public" / "science" / relative
    metadata = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["status"] = "release_candidate"
    metadata["science"].pop("frozen_release_content_hash", None)
    metadata["science"].pop("decision_material_digest", None)
    metadata.pop("activation", None)
    _write_release(boi_root, relative, metadata)


def _write_sealed_holdout(
    boi_root: Path,
    release_id: str = "sci-release:0.1.0",
    *,
    reviewer_id: str = "holdout-reviewer-1",
    rule_freeze_commit: str = "a" * 40,
    result_status: str = "passed",
) -> Path:
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.digests import sha256_digest

    from boi_api.app.science.catalog import release_decision_material_digest

    release = ScienceCatalog(boi_root).resolve_release(release_id)
    result = {
        "schema_version": "science-holdout-result/0.1",
        "status": result_status,
        "qualification_gate": "G5",
        "release_id": release.release_id,
        "frozen_release_content_hash": release.content_hash,
        "decision_material_digest": release_decision_material_digest(release),
        "rule_digests": {
            component.ref: component.semantic_digest
            for component in release.components
            if component.kind == "rule"
        },
        "component_digests": release.component_digests,
        "case_set_digest": "sha256:" + "7" * 64,
        "sealed_case_count": 2,
    }
    result["result_digest"] = sha256_digest(result)
    suffix = release_id.removeprefix("sci-release:")
    metadata = {
        "okf_version": "0.1",
        "boi_profile_version": "0.1",
        "type": "boi/report",
        "title": f"{release_id} sealed independent holdout",
        "description": "Immutable independent holdout result fixture",
        "tags": ["ScienceVerifier", "Holdout"],
        "timestamp": "2026-08-25T09:35:00+09:00",
        "boi_id": f"boi:public:science:holdout-manifest:{suffix}",
        "visibility": "public",
        "classification": "internal",
        "owner": "science-admin",
        "author": {"type": "agent", "agent_id": "holdout-recorder"},
        "acl_policy": "acl:public",
        "status": "reviewed",
        "source_refs": [{"type": "boi", "ref": release_id}],
        "review": {
            "reviewer": reviewer_id,
            "reviewed_at": "2026-08-25T09:35:00+09:00",
            "review_status": "reviewed",
            "required_role": "independent_science_reviewer",
            "authorized_review_events": [],
        },
        "science_holdout": {
            "manifest_version": "science-holdout/0.1",
            "release_id": release.release_id,
            "state": "sealed_independent_holdout",
            "external_acl_url": f"boi-private://science-verifier/holdouts/{suffix}.json",
            "sealed_sha256": "sha256:" + "9" * 64,
            "rule_freeze_commit": rule_freeze_commit,
            "reviewer": {"type": "human", "user_id": reviewer_id},
            "reviewer_role": "independent_science_reviewer",
            "reviewed_at": "2026-08-25T09:35:00+09:00",
            "result": result,
        },
    }
    path = (
        boi_root
        / "public"
        / "science"
        / "qualification"
        / "holdouts"
        / f"{release_id.replace(':', '-')}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
        + "---\n# Sealed independent holdout\n",
        encoding="utf-8",
    )
    return path


def _trusted_holdout_resolver_snapshot(boi_root: Path):
    from boi_api.app.okf import split_frontmatter

    registry: dict[tuple[str, str], dict[str, str]] = {}
    holdout_root = boi_root / "public" / "science" / "qualification" / "holdouts"
    for path in sorted(holdout_root.glob("*.md")):
        raw = path.read_bytes()
        metadata, _body = split_frontmatter(raw.decode("utf-8"))
        holdout = metadata.get("science_holdout", {})
        result = holdout.get("result", {})
        release_id = result.get("release_id")
        frozen_release_content_hash = result.get("frozen_release_content_hash")
        if isinstance(release_id, str) and isinstance(frozen_release_content_hash, str):
            registry[(release_id, frozen_release_content_hash)] = {
                "release_id": release_id,
                "frozen_release_content_hash": frozen_release_content_hash,
                "manifest_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "rule_freeze_commit": holdout["rule_freeze_commit"],
            }

    def resolve(query: dict[str, str]) -> dict[str, str] | None:
        value = registry.get(
            (query["release_id"], query["frozen_release_content_hash"])
        )
        return deepcopy(value) if value is not None else None

    return resolve


def _fully_approved_operational_fixture(science_tree: Path) -> dict[str, str]:
    paths = {
        "sci:source:fixture": "sources/source.md",
        "sci:evidence:fixture": "evidence/evidence.md",
        "sci:knowledge:fixture": "knowledge/knowledge.md",
        "sci:rule:fixture": "rules/rule.md",
        "sci:binding:fixture": "ontology-bindings/binding.md",
        "sci:qualification:fixture": "qualification/matrix.md",
        "sci-pack:fixture": "packs/pack.md",
    }
    for relative in paths.values():
        _approve_decision_document(science_tree, relative)
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            object_id: _component_digest(science_tree, relative)
            for object_id, relative in paths.items()
        },
    )
    _freeze_release_document(science_tree)
    _write_sealed_holdout(science_tree)
    _activate_release_document(science_tree)
    return paths


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

    rule_set = catalog.resolve_qualification_rule_set(release_set)

    assert rule_set.release_set_digest == release_set.combined_digest
    assert len(rule_set.rules) == 1
    released = rule_set.rules[0]
    component = next(
        item for item in release_set.components if item.ref == released.rule.rule_id
    )
    assert released.component_digest == component.actual_digest == digest
    assert released.semantic_digest == component.semantic_digest == sha256_digest(released.rule)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("claim_family", "outside allowed claim scope"),
        ("purpose", "purpose does not match"),
        ("required_conditions", "does not enforce required Evidence condition"),
        ("forbidden_family", "forbidden claim family"),
    ],
)
def test_catalog_rejects_rule_evidence_use_outside_embedded_hashed_scope(
    science_tree: Path, mutation: str, message: str
):
    """The engine must never receive a Rule whose Evidence use exceeds stored authority."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceCatalogError
    from boi_api.app.science.models import ReleaseSelection

    rule_path = science_tree / "public/science/rules/rule.md"
    metadata = yaml.safe_load(rule_path.read_text(encoding="utf-8").split("---", 2)[1])
    use = metadata["science"]["evidence_uses"][0]
    if mutation == "claim_family":
        use["claim_family"] = "fixture.other"
    elif mutation == "purpose":
        use["purpose"] = "Use the span for a broader conclusion."
    elif mutation == "required_conditions":
        metadata["science"]["required_conditions"] = []
    else:
        use["claim_family"] = "fixture.unbounded.direction"
    _write_document(science_tree, "rules/rule.md", metadata)
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {"sci:rule:fixture": _component_digest(science_tree, "rules/rule.md")},
    )
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceCatalogError, match=message):
        catalog.resolve_qualification_rule_set(release_set)


@pytest.mark.parametrize(
    "claim_family",
    [
        "spin_coating.rpm_thickness_direction",
        "spin_coating.rpm_thickness_direction.product_scoped",
        "spin_coating.spin_speed_thickness_direction",
        "spin_coating.spin_speed_thickness_direction.product_scoped",
    ],
)
def test_spin_time_evidence_cannot_authorize_any_spin_speed_direction_family(
    science_tree: Path, claim_family: str
):
    """The spin-time prose must never be repurposed as RPM-to-thickness Evidence."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.digests import sha256_digest
    from boi_api.app.science.exceptions import ScienceCatalogError
    from boi_api.app.science.models import ReleaseSelection

    evidence_path = science_tree / "public/science/evidence/evidence.md"
    evidence_metadata = yaml.safe_load(
        evidence_path.read_text(encoding="utf-8").split("---", 2)[1]
    )
    scope = {
        "schema_version": "0.1",
        "allowed_claims": [
            {
                "claim_family": "spin_coating.spin_time_thinning.product_scoped",
                "purpose": "Support only product-scoped spin-time thinning.",
                "required_conditions": [
                    {"key": "source_revision", "operator": "eq", "value": "fixture"}
                ],
            }
        ],
        "forbidden_claim_families": [
            "spin_coating.rpm_thickness_direction",
            "spin_coating.spin_speed_thickness_direction",
        ],
        "limitations": ["This prose contains no RPM direction."],
    }
    evidence_metadata["science"]["claim_scope"] = scope
    evidence_metadata["science"]["claim_scope_hash"] = sha256_digest(scope)
    _write_document(science_tree, "evidence/evidence.md", evidence_metadata)

    rule_path = science_tree / "public/science/rules/rule.md"
    rule_metadata = yaml.safe_load(
        rule_path.read_text(encoding="utf-8").split("---", 2)[1]
    )
    rule_metadata["science"]["evidence_uses"][0] = {
        "evidence_ref": "sci:evidence:fixture",
        "claim_family": claim_family,
        "purpose": "Claim a spin-speed thickness direction.",
    }
    _write_document(science_tree, "rules/rule.md", rule_metadata)
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {"sci:rule:fixture": _component_digest(science_tree, "rules/rule.md")},
    )
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceCatalogError, match="forbidden claim family"):
        catalog.resolve_qualification_rule_set(release_set)


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


def test_active_release_accepts_trusted_admin_reviewed_source_and_evidence(science_tree: Path):
    """Only an externally resolved science.admin approval may activate decision material."""
    from boi_api.app.science.catalog import ScienceCatalog

    _approve_decision_document(science_tree, "sources/source.md")
    _approve_decision_document(science_tree, "evidence/evidence.md")
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            "sci:source:fixture": _component_digest(science_tree, "sources/source.md"),
            "sci:evidence:fixture": _component_digest(science_tree, "evidence/evidence.md"),
        },
    )
    _activate_release_document(science_tree)

    release = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_clock=_trusted_clock,
    ).active_release()

    assert {component.ref for component in release.components} == {
        "sci:source:fixture",
        "sci:evidence:fixture",
    }


def test_direct_catalog_resolution_of_active_decision_release_fails_closed(
    science_tree: Path,
):
    """Calling resolve_release directly must not bypass active-release governance."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            "sci:source:fixture": _component_digest(science_tree, "sources/source.md"),
            "sci:evidence:fixture": _component_digest(science_tree, "evidence/evidence.md"),
        },
    )

    from boi_api.app.science.models import ReleaseSelection

    catalog = ScienceCatalog(science_tree)
    assert catalog.resolve_release("sci-release:0.1.0").release_id == "sci-release:0.1.0"
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )
    with pytest.raises(ScienceOperationalError, match="trusted reviewer-role resolver"):
        catalog.resolve_operational_rule_set(release_set)


def test_active_evidence_requires_its_exact_pinned_source_component(
    science_tree: Path,
):
    """A globally indexed Source must not silently ground active Evidence."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _approve_decision_document(science_tree, "evidence/evidence.md")
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {"sci:evidence:fixture": _component_digest(science_tree, "evidence/evidence.md")},
    )
    _activate_release_document(science_tree)

    with pytest.raises(ScienceOperationalError, match="requires its pinned Source"):
        ScienceCatalog(
            science_tree,
            reviewer_role_resolver=_trusted_admin_roles,
            trusted_clock=_trusted_clock,
        ).active_release()


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("no_resolver", "trusted reviewer-role resolver"),
        ("draft", "must be approved"),
        ("pending_review", "authorized approved review"),
        ("inactive", "decision eligibility"),
        ("blocked", "release eligibility"),
        ("missing_event", "authorized approved review"),
        ("approval_before_curation", "temporally invalid"),
        ("missing_author", "author actor is invalid"),
        ("self_approval", "self-approval"),
        ("fake_admin_role", "not authorized as science.admin"),
        ("resolver_not_admin", "not authorized as science.admin"),
    ],
)
def test_active_release_rejects_untrusted_or_ineligible_decision_components(
    science_tree: Path, case: str, message: str
):
    """Caller-written role claims and stale workflow labels must never activate Evidence."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError

    _approve_decision_document(science_tree, "sources/source.md")
    _approve_decision_document(science_tree, "evidence/evidence.md")
    target = "evidence/evidence.md"
    path = science_tree / "public" / "science" / target
    metadata = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    resolver = _trusted_admin_roles
    if case == "no_resolver":
        resolver = None
    elif case == "draft":
        metadata["status"] = "draft"
    elif case == "pending_review":
        metadata["review"]["review_status"] = "pending_review"
    elif case == "inactive":
        metadata["science"]["decision_eligibility"] = "inactive"
    elif case == "blocked":
        metadata["science"]["release_eligibility"] = "blocked_pending_authorized_admin_review"
    elif case == "missing_event":
        metadata["review"]["authorized_review_events"] = []
    elif case == "approval_before_curation":
        metadata["review"]["authorized_review_events"][0]["occurred_at"] = (
            "2026-08-25T09:06:00+09:00"
        )
    elif case == "missing_author":
        del metadata["author"]
    elif case == "self_approval":
        metadata["author"] = {"type": "human", "user_id": "reviewer-1"}
    elif case == "fake_admin_role":
        metadata["review"]["authorized_review_events"][0]["actor"] = {
            "type": "human",
            "user_id": "not-an-admin",
        }
    else:
        def resolver(_actor: str) -> set[str]:
            return {"science.power_user"}
    _write_document(science_tree, target, metadata)
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            "sci:source:fixture": _component_digest(science_tree, "sources/source.md"),
            "sci:evidence:fixture": _component_digest(science_tree, "evidence/evidence.md"),
        },
    )
    _activate_release_document(science_tree)

    with pytest.raises(ScienceOperationalError, match=message):
        ScienceCatalog(
            science_tree,
            reviewer_role_resolver=resolver,
            trusted_clock=_trusted_clock,
        ).active_release()


def test_candidate_may_resolve_pending_evidence_but_cannot_become_an_active_rule_set(
    science_tree: Path,
):
    """Draft Evidence may be assembled for review, never evaluated as operational truth."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    release_path = science_tree / "public/science/releases/sci-release-0.1.0.md"
    metadata = yaml.safe_load(release_path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["science"]["status"] = "release_candidate"
    _write_release(science_tree, "releases/sci-release-0.1.0.md", metadata)
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            "sci:evidence:fixture": _component_digest(science_tree, "evidence/evidence.md"),
            "sci:rule:fixture": _component_digest(science_tree, "rules/rule.md"),
        },
    )
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    assert release_set.foundation_release.status == "release_candidate"
    qualification = catalog.resolve_qualification_rule_set(release_set)
    assert type(qualification).__name__ == "QualificationRuleSet"
    with pytest.raises(ScienceOperationalError, match="cannot be evaluated as active"):
        catalog.resolve_rule_set(release_set)


def test_catalog_issues_opaque_operational_attestation_only_after_complete_active_gate(
    science_tree: Path,
):
    """The public Engine accepts only the immutable Catalog capability, not qualification data."""
    import copy
    import pickle

    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.engine import verify_claim
    from boi_api.app.science.models import ClaimPacket, PrimaryVerdict, ReleaseSelection
    from boi_api.app.science.operational import (
        OperationalVerification,
        _open_operational_verification,
    )

    _fully_approved_operational_fixture(science_tree)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_holdout_resolver=_trusted_holdout_resolver_snapshot(science_tree),
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )
    qualification = catalog.resolve_qualification_rule_set(release_set)
    operational = catalog.resolve_operational_rule_set(release_set)
    claim = ClaimPacket.model_validate(
        {
            "claim_id": "claim:operational-capability",
            "document_ref": "boi:public:science:document:proof",
            "document_digest": "sha256:document-proof",
            "source_span": {"start": 0, "end": 24, "exact": "input increases response"},
            "normalized_claim": {
                "subject_concept_id": "sci:concept:input",
                "relation_kind": "monotonic_direction",
                "predicate": "increases",
                "object_concept_id": "sci:concept:response",
                "polarity": "positive",
                "quantities": [],
                "conditions": [
                    {"condition_id": "fixture_scope", "value": "controlled"}
                ],
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

    assert isinstance(operational, OperationalVerification)
    assert operational.attestation_digest.startswith("sha256:")
    assert operational.rule_set_digest.startswith("sha256:")
    _sealed_release_set, _sealed_rule_set, attestation = (
        _open_operational_verification(operational)
    )
    assert attestation["release_set_digest"] == release_set.combined_digest
    assert attestation["releases"] == [
        {
            "release_id": release_set.foundation_release.release_id,
            "status": "active",
            "content_hash": release_set.foundation_release.content_hash,
            "component_digests": release_set.foundation_release.component_digests,
        }
    ]
    assert len(attestation["approval_snapshot"]) == 10
    assert any(
        item["event_kind"] == "sealed_independent_holdout"
        and item["release_id"] == "sci-release:0.1.0"
        for item in attestation["approval_snapshot"]
    )
    assert attestation["rule_set_digest"] == operational.rule_set_digest
    assert verify_claim(claim, operational).verdict is PrimaryVerdict.VIOLATION
    with pytest.raises(TypeError, match="Catalog-issued operational verification"):
        verify_claim(claim, qualification)
    status_forged_qualification = qualification.model_copy(
        update={"status": "active"}
    )
    with pytest.raises(TypeError, match="Catalog-issued operational verification"):
        verify_claim(claim, status_forged_qualification)
    with pytest.raises(AttributeError, match="immutable"):
        operational._attestation_digest = "sha256:forged"
    with pytest.raises(TypeError, match="cannot be copied"):
        copy.copy(operational)
    with pytest.raises(TypeError, match="cannot be serialized"):
        pickle.dumps(operational)


def test_operational_rule_capability_rejects_locally_authored_holdout_without_trust(
    science_tree: Path,
) -> None:
    """A perfect-looking local file must not mint G5 authority by itself."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    _fully_approved_operational_fixture(science_tree)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(
        ScienceOperationalError, match="trusted independent holdout resolver"
    ):
        catalog.resolve_operational_rule_set(release_set)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "sealed independent holdout manifest"),
        ("tampered", "immutable manifest digest"),
        ("self_reviewed", "independent holdout reviewer"),
        ("wrong_release", "release binding"),
        ("wrong_freeze", "trusted rule freeze"),
        ("failed", "passing result"),
        ("reviewed_after_activation", "precede Release activation"),
    ],
)
def test_operational_rule_capability_fails_closed_on_invalid_independent_holdout(
    science_tree: Path, mutation: str, message: str
) -> None:
    """Missing or mutable holdout assertions never authorize deterministic verdicts."""
    from boi_api.app.okf import split_frontmatter
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.digests import sha256_digest
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    _fully_approved_operational_fixture(science_tree)
    trusted_resolver = _trusted_holdout_resolver_snapshot(science_tree)
    path = next(
        (science_tree / "public/science/qualification/holdouts").glob("*.md")
    )
    if mutation == "missing":
        path.unlink()
    else:
        metadata, body = split_frontmatter(path.read_text(encoding="utf-8"))
        holdout = metadata["science_holdout"]
        if mutation == "tampered":
            body += "\nTampered after the trusted digest was recorded.\n"
        elif mutation == "self_reviewed":
            holdout["reviewer"]["user_id"] = "reviewer-1"
        elif mutation == "wrong_release":
            holdout["result"]["release_id"] = "sci-release:other"
        elif mutation == "wrong_freeze":
            holdout["rule_freeze_commit"] = "b" * 40
        elif mutation == "failed":
            holdout["result"]["status"] = "failed"
        elif mutation == "reviewed_after_activation":
            holdout["reviewed_at"] = "2026-08-25T09:45:00+09:00"
        if mutation in {
            "self_reviewed",
            "wrong_release",
            "failed",
            "reviewed_after_activation",
        }:
            result = holdout["result"]
            result["result_digest"] = sha256_digest(
                {key: value for key, value in result.items() if key != "result_digest"}
            )
        path.write_text(
            "---\n"
            + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True)
            + "---\n"
            + body.lstrip("\n"),
            encoding="utf-8",
        )
        if mutation in {
            "self_reviewed",
            "wrong_release",
            "failed",
            "reviewed_after_activation",
        }:
            trusted_resolver = _trusted_holdout_resolver_snapshot(science_tree)
        elif mutation == "wrong_freeze":
            current_resolver = _trusted_holdout_resolver_snapshot(science_tree)

            def trusted_resolver(query: dict[str, str]) -> dict[str, str] | None:
                identity = current_resolver(query)
                if identity is not None:
                    identity["rule_freeze_commit"] = "a" * 40
                return identity

    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_holdout_resolver=trusted_resolver,
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceOperationalError, match=message):
        catalog.resolve_operational_rule_set(release_set)


def test_operational_holdout_rejects_decision_material_changed_after_rule_freeze(
    science_tree: Path,
) -> None:
    """Activation lifecycle may change, but post-freeze scientific content may not."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    paths = _fully_approved_operational_fixture(science_tree)
    trusted_resolver = _trusted_holdout_resolver_snapshot(science_tree)
    rule_path = science_tree / "public/science/rules/rule.md"
    metadata = yaml.safe_load(
        rule_path.read_text(encoding="utf-8").split("---", 2)[1]
    )
    _write_document(
        science_tree,
        "rules/rule.md",
        metadata,
        body="# Changed after the independent holdout was sealed\n",
    )
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            object_id: _component_digest(science_tree, relative)
            for object_id, relative in paths.items()
        },
    )
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_holdout_resolver=trusted_resolver,
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceOperationalError, match="release binding"):
        catalog.resolve_operational_rule_set(release_set)


def test_catalog_rejects_arbitrary_superseded_release_for_new_operational_verdict(
    science_tree: Path,
):
    """Only the exact active pointer (or its declared last-safe target) may mint authority."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    _fully_approved_operational_fixture(science_tree)
    _add_release(
        science_tree,
        release_id="sci-release:arbitrary-superseded",
        status="superseded",
    )
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_holdout_resolver=_trusted_holdout_resolver_snapshot(science_tree),
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:arbitrary-superseded")
    )

    with pytest.raises(ScienceOperationalError, match="cannot be evaluated as active"):
        catalog.resolve_operational_rule_set(release_set)


@pytest.mark.parametrize(
    ("scope_name", "missing_key"),
    [
        ("kcl", "circuit_model"),
        ("kcl", "node_charge_accumulation"),
        ("figure", "product_grade"),
        ("figure", "source_revision"),
        ("figure", "spin_speed_rpm"),
    ],
)
def test_typed_evidence_scope_conditions_are_nondecisive_when_claim_input_is_missing(
    science_tree: Path, scope_name: str, missing_key: str
):
    """Critical KCL and Figure limits remain executable from Evidence through verdict."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.digests import sha256_digest
    from boi_api.app.science.engine import verify_claim
    from boi_api.app.science.models import ClaimPacket, PrimaryVerdict, ReleaseSelection

    profiles = {
        "kcl": {
            "claim_family": "circuits.kcl.algebraic_current_sum_zero",
            "purpose": "Use KCL only in the declared lumped no-accumulation model.",
            "constraints": [
                {"key": "current_reference_convention", "operator": "eq", "value": "consistent"},
                {"key": "circuit_model", "operator": "eq", "value": "lumped_matter"},
                {"key": "node_charge_accumulation", "operator": "eq", "value": "none"},
            ],
            "conditions": [
                {"condition_id": "current_reference_convention", "value": "consistent"},
                {"condition_id": "circuit_model", "value": "lumped_matter"},
                {"condition_id": "node_charge_accumulation", "value": "none"},
            ],
        },
        "figure": {
            "claim_family": "spin_coating.rpm_thickness_direction.product_scoped_figure_observation",
            "purpose": "Use only the product revision and common plotted marker range.",
            "constraints": [
                {"key": "product_family", "operator": "eq", "value": "AZ 125nXT"},
                {
                    "key": "product_grade",
                    "operator": "in",
                    "values": ["AZ 125nXT-10 B", "AZ 125nXT-7 B"],
                },
                {"key": "source_revision", "operator": "eq", "value": "01/24"},
                {
                    "key": "spin_speed_rpm",
                    "operator": "range",
                    "range": {"minimum": 600, "maximum": 2300},
                    "unit": "rpm",
                },
                {
                    "key": "evidence_use_mode",
                    "operator": "eq",
                    "value": "plotted_markers_only",
                },
            ],
            "conditions": [
                {"condition_id": "product_family", "value": "AZ 125nXT"},
                {"condition_id": "product_grade", "value": "AZ 125nXT-10 B"},
                {"condition_id": "source_revision", "value": "01/24"},
                {"condition_id": "spin_speed_rpm", "value": 1000, "unit": "rpm"},
                {"condition_id": "evidence_use_mode", "value": "plotted_markers_only"},
            ],
        },
    }
    profile = profiles[scope_name]
    evidence_path = science_tree / "public" / "science" / "evidence/evidence.md"
    evidence_metadata = yaml.safe_load(
        evidence_path.read_text(encoding="utf-8").split("---", 2)[1]
    )
    scope = {
        "schema_version": "0.1",
        "allowed_claims": [
            {
                "claim_family": profile["claim_family"],
                "purpose": profile["purpose"],
                "required_conditions": profile["constraints"],
            }
        ],
        "forbidden_claim_families": ["unbounded_or_unqualified_claims"],
        "limitations": evidence_metadata["science"]["claim_scope"]["limitations"],
    }
    evidence_metadata["science"]["claim_scope"] = scope
    evidence_metadata["science"]["claim_scope_hash"] = sha256_digest(scope)
    _write_document(science_tree, "evidence/evidence.md", evidence_metadata)

    rule_path = science_tree / "public" / "science" / "rules/rule.md"
    rule_metadata = yaml.safe_load(
        rule_path.read_text(encoding="utf-8").split("---", 2)[1]
    )
    rule_metadata["science"]["required_conditions"] = profile["constraints"]
    rule_metadata["science"]["evidence_uses"] = [
        {
            "evidence_ref": "sci:evidence:fixture",
            "claim_family": profile["claim_family"],
            "purpose": profile["purpose"],
        }
    ]
    _write_document(science_tree, "rules/rule.md", rule_metadata)

    _fully_approved_operational_fixture(science_tree)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_holdout_resolver=_trusted_holdout_resolver_snapshot(science_tree),
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )
    operational = catalog.resolve_operational_rule_set(release_set)
    conditions = [
        condition
        for condition in profile["conditions"]
        if condition["condition_id"] != missing_key
    ]
    claim = ClaimPacket.model_validate(
        {
            "claim_id": f"claim:{scope_name}:missing:{missing_key}",
            "document_ref": "boi:public:science:document:missing-condition",
            "document_digest": "sha256:document-missing-condition",
            "source_span": {"start": 0, "end": 24, "exact": "input increases response"},
            "normalized_claim": {
                "subject_concept_id": "sci:concept:input",
                "relation_kind": "monotonic_direction",
                "predicate": "increases",
                "object_concept_id": "sci:concept:response",
                "polarity": "positive",
                "quantities": [],
                "conditions": conditions,
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

    packet = verify_claim(claim, operational)
    assert packet.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert any(
        condition.condition_id == missing_key
        and condition.reason_code == "MISSING_CONDITION_VALUE"
        for condition in packet.condition_evaluations
    )


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("knowledge/knowledge.md", "must be approved"),
        ("rules/rule.md", "must be approved"),
        ("ontology-bindings/binding.md", "must be approved"),
        ("qualification/matrix.md", "must be approved"),
        ("packs/pack.md", "must be approved"),
    ],
)
def test_operational_gate_rejects_every_draft_decision_bearing_component(
    science_tree: Path, target: str, message: str
):
    """No omitted component kind may ride through an otherwise approved active Release."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    paths = _fully_approved_operational_fixture(science_tree)
    path = science_tree / "public" / "science" / target
    metadata = yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1])
    metadata["status"] = "draft"
    metadata["review"] = {
        "review_status": "pending_review",
        "required_role": "Admin",
        "authorized_review_events": [],
    }
    metadata["science"]["release_eligibility"] = "blocked_pending_authorized_admin_review"
    _write_document(science_tree, target, metadata)
    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            object_id: _component_digest(science_tree, relative)
            for object_id, relative in paths.items()
        },
    )
    _activate_release_document(science_tree)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceOperationalError, match=message):
        catalog.resolve_operational_rule_set(release_set)


def test_operational_gate_requires_an_injected_trusted_clock(science_tree: Path):
    """Filesystem timestamps never substitute for a trusted operational clock."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    _fully_approved_operational_fixture(science_tree)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceOperationalError, match="injected trusted clock"):
        catalog.resolve_operational_rule_set(release_set)


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("draft_release", "Release must be approved"),
        ("missing_activation", "authorized activation"),
        ("dual_author", "author actor is invalid"),
        ("dual_approver", "review actor is invalid"),
        ("future_approval", "approval occurs after trusted clock"),
        ("approval_after_activation", "approval occurs after Release activation"),
        ("future_activation", "activation occurs after trusted clock"),
    ],
)
def test_operational_gate_closes_actor_and_time_schema(
    science_tree: Path, case: str, message: str
):
    """Actor identities and approval time order come only from closed trusted inputs."""
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.exceptions import ScienceOperationalError
    from boi_api.app.science.models import ReleaseSelection

    paths = _fully_approved_operational_fixture(science_tree)
    target = science_tree / "public" / "science" / "knowledge/knowledge.md"
    metadata = yaml.safe_load(target.read_text(encoding="utf-8").split("---", 2)[1])
    if case == "dual_author":
        metadata["author"] = {
            "type": "agent",
            "agent_id": "fixture-author",
            "user_id": "reviewer-1",
        }
    elif case == "dual_approver":
        metadata["review"]["authorized_review_events"][0]["actor"] = {
            "type": "human",
            "user_id": "reviewer-1",
            "agent_id": "fixture-author",
        }
    elif case == "future_approval":
        metadata["review"]["authorized_review_events"][0]["occurred_at"] = (
            "2099-01-01T00:00:00+09:00"
        )
    elif case == "approval_after_activation":
        metadata["review"]["authorized_review_events"][0]["occurred_at"] = (
            "2026-08-25T09:50:00+09:00"
        )
    if case in {"dual_author", "dual_approver", "future_approval", "approval_after_activation"}:
        _write_document(science_tree, "knowledge/knowledge.md", metadata)
        _replace_release_components(
            science_tree,
            "sci-release:0.1.0",
            {
                object_id: _component_digest(science_tree, relative)
                for object_id, relative in paths.items()
            },
        )
        _activate_release_document(science_tree)
    release_path = science_tree / "public" / "science" / "releases/sci-release-0.1.0.md"
    release_metadata = yaml.safe_load(
        release_path.read_text(encoding="utf-8").split("---", 2)[1]
    )
    if case == "draft_release":
        release_metadata["status"] = "draft"
        release_metadata["review"]["review_status"] = "pending_review"
    elif case == "missing_activation":
        del release_metadata["activation"]
    elif case == "future_activation":
        release_metadata["activation"]["authorized_activation_events"][0][
            "occurred_at"
        ] = "2099-01-01T00:00:00+09:00"
    _write_release(science_tree, "releases/sci-release-0.1.0.md", release_metadata)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    with pytest.raises(ScienceOperationalError, match=message):
        catalog.resolve_operational_rule_set(release_set)


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

    _activate_release_document(science_tree, "sci-release:safe")
    assert ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_clock=_trusted_clock,
    ).active_release().release_id == "sci-release:safe"


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
    rule_set = catalog.resolve_qualification_rule_set(resolved)

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

    _approve_decision_document(science_tree, "sources/source.md")
    _approve_decision_document(science_tree, "evidence/evidence.md")
    _approve_decision_document(science_tree, "knowledge/knowledge.md")
    _approve_decision_document(science_tree, "rules/rule.md")
    _approve_decision_document(science_tree, "packs/pack.md")
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
    _freeze_release_document(science_tree)
    _write_sealed_holdout(science_tree)
    _activate_release_document(science_tree)
    domain_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:domain-proof",
        dependencies=[{"relation": "uses", "ref": "sci-pack:fixture"}],
    )
    _add_release(
        science_tree, release_id="sci-release:domain-proof", status="active"
    )
    _replace_release_components(
        science_tree,
        "sci-release:domain-proof",
        {"sci-pack:domain-proof": _component_digest(science_tree, domain_relative)},
    )
    _approve_decision_document(science_tree, domain_relative)
    _replace_release_components(
        science_tree,
        "sci-release:domain-proof",
        {"sci-pack:domain-proof": _component_digest(science_tree, domain_relative)},
    )
    _freeze_release_document(science_tree, "sci-release:domain-proof")
    _write_sealed_holdout(science_tree, "sci-release:domain-proof")
    _activate_release_document(science_tree, "sci-release:domain-proof")
    application_relative = _add_pack(
        science_tree,
        pack_id="sci-pack:application-proof",
        dependencies=[{"relation": "specializes", "ref": "sci-pack:domain-proof"}],
    )
    _add_release(
        science_tree,
        release_id="sci-release:application-proof",
        status="active",
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
    _approve_decision_document(science_tree, application_relative)
    _replace_release_components(
        science_tree,
        "sci-release:application-proof",
        {
            "sci-pack:application-proof": _component_digest(
                science_tree, application_relative
            )
        },
    )
    _freeze_release_document(science_tree, "sci-release:application-proof")
    _write_sealed_holdout(science_tree, "sci-release:application-proof")
    _activate_release_document(science_tree, "sci-release:application-proof")
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
                "conditions": [
                    {"condition_id": "fixture_scope", "value": "controlled"}
                ],
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
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_holdout_resolver=_trusted_holdout_resolver_snapshot(science_tree),
        trusted_clock=_trusted_clock,
    )

    release_set = catalog.resolve_release_set(selection)
    operational = catalog.resolve_operational_rule_set(release_set)
    packet = verify_claim(claim, operational)

    assert packet.verdict is PrimaryVerdict.VIOLATION
    assert packet.decisive_rule_ids == ["sci:rule:fixture"]
    assert packet.knowledge_refs == ["sci:knowledge:fixture"]
    assert packet.evidence_refs == ["sci:evidence:fixture"]
    assert packet.releases.selection == selection
    assert packet.releases.digests == release_set.release_digests
    assert packet.releases.combined_digest == release_set.combined_digest


def test_catalog_issues_release_bound_reviewed_source_url_identity(
    science_tree: Path,
):
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.models import ReleaseSelection
    from boi_api.app.science.source_identity import (
        ReviewedSourceURLIdentity,
        _open_reviewed_source_url_identity,
    )

    _fully_approved_operational_fixture(science_tree)
    catalog = ScienceCatalog(
        science_tree,
        reviewer_role_resolver=_trusted_admin_roles,
        trusted_clock=_trusted_clock,
    )
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    identity = catalog.resolve_reviewed_source_url_identity(
        release_set, "sci:evidence:fixture"
    )
    profile = _open_reviewed_source_url_identity(identity)

    assert type(identity) is ReviewedSourceURLIdentity
    assert profile.qualification_state == "active"
    assert profile.release_set_digest == release_set.combined_digest
    assert profile.source_id == "sci:source:fixture"
    assert profile.evidence_id == "sci:evidence:fixture"
    assert profile.canonical_source_url == "https://example.test/source"


def test_catalog_candidate_source_url_preview_has_no_operational_authority(
    science_tree: Path,
):
    from boi_api.app.science.catalog import ScienceCatalog
    from boi_api.app.science.models import ReleaseSelection
    from boi_api.app.science.source_identity import _issue_reviewed_source_url_identity

    _replace_release_components(
        science_tree,
        "sci-release:0.1.0",
        {
            "sci:source:fixture": _component_digest(science_tree, "sources/source.md"),
            "sci:evidence:fixture": _component_digest(
                science_tree, "evidence/evidence.md"
            ),
        },
    )
    catalog = ScienceCatalog(science_tree)
    release_set = catalog.resolve_release_set(
        ReleaseSelection(foundation="sci-release:0.1.0")
    )

    preview = catalog.preview_reviewed_source_url_profile(
        release_set, "sci:evidence:fixture"
    )

    assert preview.qualification_state == "candidate"
    with pytest.raises(TypeError, match="direct Source identity issuance is forbidden"):
        _issue_reviewed_source_url_identity(preview)
