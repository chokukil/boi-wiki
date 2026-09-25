"""Load versioned declarative profile candidates without Release authority."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any, Mapping

import yaml

from .okf_v02 import validate_boi_profile_v02


_SCHEMA = "boi-declarative-profile-candidate-package/v1"
_CATEGORY_CONTRACT = {
    "domain": ("boi/domain@0.1.0", "domain", "id"),
    "mapping": ("boi/data-mapping@0.1.0", "data_mapping", "mapping_id"),
    "query": ("boi/query@0.2.0", "query", "query_spec_id"),
}
_DOMAIN_FORBIDDEN_DEEP = frozenset(
    {"table", "column", "sql", "raw_sql", "dialect", "schema_snapshot", "schema_snapshot_digest"}
)
_QUERY_FORBIDDEN_DEEP = frozenset(
    {
        "table", "column", "physical", "source_id", "sql", "raw_sql",
        "executed_sql", "repaired_sql", "dialect",
    }
)


class DeclarativeProfileCandidateError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _digest(value: Any) -> str:
    encoded = value if isinstance(value, bytes) else _canonical(value)
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _mapping(value: object, code: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise DeclarativeProfileCandidateError(code)
    return dict(value)


def _list(value: object, code: str) -> list[Any]:
    if not isinstance(value, list):
        raise DeclarativeProfileCandidateError(code)
    return value


def _deep_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key).casefold())
            keys.update(_deep_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(_deep_keys(child))
    return keys


@dataclass(frozen=True)
class CandidateSourceReceipt:
    resource: str
    role: str
    local_path: str
    content_digest: str
    repository_commit: str | None
    verified: bool


@dataclass(frozen=True)
class ProfileCandidateDocument:
    entry_id: str
    category: str
    profile: str
    boi_id: str
    evidence_resources: tuple[str, ...]
    payload: dict[str, Any]
    rendered_document: bytes
    document_digest: str
    revision_digest: str


@dataclass(frozen=True)
class DeclarativeProfileCandidatePackage:
    schema: str
    package_id: str
    status: str
    qualification_status: str
    release_id: None
    active_pointer_transition: bool
    canonical_projection_eligible: bool
    source_receipts: tuple[CandidateSourceReceipt, ...]
    documents: tuple[ProfileCandidateDocument, ...]
    profile_counts: dict[str, int]
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    package_digest: str


def _verify_source(source: dict[str, Any]) -> CandidateSourceReceipt:
    resource = str(source.get("resource") or "")
    role = str(source.get("role") or "")
    local_path = Path(str(source.get("local_path") or ""))
    expected = str(source.get("sha256") or "")
    if (
        not resource
        or role not in {"sql", "documentation", "ddl", "query_history", "catalog_snapshot"}
        or not local_path.is_file()
        or not expected.startswith("sha256:")
    ):
        raise DeclarativeProfileCandidateError("SOURCE_ARTIFACT_CONTRACT_INVALID")
    actual = _file_digest(local_path)
    if actual != expected:
        raise DeclarativeProfileCandidateError(
            f"SOURCE_ARTIFACT_DIGEST_MISMATCH:{resource}"
        )
    repository_commit = source.get("repository_commit")
    repository_path = source.get("repository_path")
    if repository_commit is not None or repository_path is not None:
        if not repository_commit or not repository_path:
            raise DeclarativeProfileCandidateError("SOURCE_REPOSITORY_CONTRACT_INVALID")
        completed = subprocess.run(
            ["git", "-C", str(repository_path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 or completed.stdout.strip() != str(repository_commit):
            raise DeclarativeProfileCandidateError(
                f"SOURCE_REPOSITORY_COMMIT_MISMATCH:{resource}"
            )
    return CandidateSourceReceipt(
        resource=resource,
        role=role,
        local_path=str(local_path),
        content_digest=actual,
        repository_commit=str(repository_commit) if repository_commit else None,
        verified=True,
    )


def _render_metadata(metadata: dict[str, Any], body: str) -> bytes:
    header = yaml.safe_dump(
        metadata, allow_unicode=True, sort_keys=False
    ).rstrip()
    return f"---\n{header}\n---\n{body.rstrip()}\n".encode()


def _validate_payload_boundary(category: str, payload: dict[str, Any]) -> None:
    keys = _deep_keys(payload)
    if category == "domain" and keys & _DOMAIN_FORBIDDEN_DEEP:
        raise DeclarativeProfileCandidateError("DOMAIN_PHYSICAL_OR_SQL_FIELD_FORBIDDEN")
    if category == "query" and keys & _QUERY_FORBIDDEN_DEEP:
        raise DeclarativeProfileCandidateError("QUERY_PHYSICAL_OR_SQL_FIELD_FORBIDDEN")


def load_declarative_profile_candidate_package(
    manifest_path: Path | str,
) -> DeclarativeProfileCandidatePackage:
    """Verify and render an inactive declarative candidate package.

    This function has no ledger, qualification, Release, projection, or active
    pointer dependency.  Its output is candidate material only.
    """

    manifest_path = Path(manifest_path)
    manifest = _mapping(
        yaml.safe_load(manifest_path.read_text(encoding="utf-8")),
        "CANDIDATE_MANIFEST_NOT_MAPPING",
    )
    if manifest.get("schema") != _SCHEMA:
        raise DeclarativeProfileCandidateError("CANDIDATE_MANIFEST_SCHEMA_INVALID")
    if (
        manifest.get("status") != "candidate"
        or manifest.get("qualification_status") != "not_run"
        or manifest.get("release_id") is not None
        or manifest.get("active_pointer_transition") is not False
        or manifest.get("canonical_projection_eligible") is not False
    ):
        raise DeclarativeProfileCandidateError("CANDIDATE_AUTHORITY_BOUNDARY_INVALID")

    source_receipts = tuple(
        _verify_source(_mapping(item, "SOURCE_ARTIFACT_NOT_MAPPING"))
        for item in _list(manifest.get("source_artifacts"), "SOURCE_ARTIFACTS_INVALID")
    )
    resources = {item.resource for item in source_receipts}
    if len(resources) != len(source_receipts):
        raise DeclarativeProfileCandidateError("DUPLICATE_SOURCE_RESOURCE")

    defaults = _mapping(manifest.get("document_defaults"), "DOCUMENT_DEFAULTS_INVALID")
    package_id = str(manifest.get("package_id") or "")
    if not package_id:
        raise DeclarativeProfileCandidateError("CANDIDATE_PACKAGE_ID_REQUIRED")

    pending: list[
        tuple[
            str, str, str, tuple[str, ...], dict[str, Any], dict[str, Any], bytes
        ]
    ] = []
    seen: set[tuple[str, str]] = set()
    for raw_entry in _list(manifest.get("entries"), "CANDIDATE_ENTRIES_INVALID"):
        entry = _mapping(raw_entry, "CANDIDATE_ENTRY_NOT_MAPPING")
        category = str(entry.get("category") or "")
        if category not in _CATEGORY_CONTRACT:
            raise DeclarativeProfileCandidateError("CANDIDATE_CATEGORY_INVALID")
        profile, payload_key, id_key = _CATEGORY_CONTRACT[category]
        payload = _mapping(entry.get("payload"), "CANDIDATE_PAYLOAD_INVALID")
        entry_id = str(payload.get(id_key) or "")
        if not entry_id or (category, entry_id) in seen:
            raise DeclarativeProfileCandidateError("DUPLICATE_OR_MISSING_PROFILE_ENTRY_ID")
        seen.add((category, entry_id))
        _validate_payload_boundary(category, payload)

        evidence_resources = entry.get("evidence_resources", defaults.get("evidence_resources"))
        evidence_resources = [str(value) for value in _list(
            evidence_resources, "ENTRY_EVIDENCE_RESOURCES_INVALID"
        )]
        if not evidence_resources or not set(evidence_resources) <= resources:
            raise DeclarativeProfileCandidateError("ENTRY_SOURCE_NOT_IN_VERIFIED_MANIFEST")
        boi_id = str(entry.get("boi_id") or f"boi:public:{category}:{entry_id}")
        metadata = {
            "okf_version": "0.2",
            "boi_profile_version": "0.2",
            "profiles": [profile],
            "type": str(
                entry.get("type")
                or (
                    "boi/Exploratory Query Contract"
                    if category == "query"
                    else "boi/profile-entry"
                )
            ),
            "title": str(entry.get("title") or entry_id),
            "description": str(entry.get("description") or f"Declarative candidate {entry_id}"),
            "boi_id": boi_id,
            "visibility": defaults.get("visibility"),
            "classification": defaults.get("classification"),
            "owner": defaults.get("owner"),
            "acl_policy": defaults.get("acl_policy"),
            "generated": defaults.get("generated"),
            "sources": [
                {"type": "profile-evidence", "resource": resource, "relation": "evidence"}
                for resource in evidence_resources
            ],
            "status": "draft",
            "stale_after": defaults.get("stale_after"),
            payload_key: payload,
        }
        validation = validate_boi_profile_v02(metadata)
        if not validation.ok:
            codes = ",".join(sorted({item.code for item in validation.errors}))
            raise DeclarativeProfileCandidateError(
                f"PROFILE_DOCUMENT_STRICT_VALIDATION_FAILED:{category}:{entry_id}:{codes}"
            )
        rendered = _render_metadata(
            metadata, str(entry.get("body") or "Candidate only; qualification has not run.")
        )
        pending.append((
            entry_id,
            category,
            profile,
            tuple(evidence_resources),
            payload,
            metadata,
            rendered,
        ))

    mapping_entries = {
        entry_id: payload
        for entry_id, category, _profile, _evidence, payload, _metadata, _rendered
        in pending if category == "mapping"
    }
    domain_ids = {
        entry_id
        for entry_id, category, _profile, _evidence, _payload, _metadata, _rendered
        in pending if category == "domain"
    }
    for entry_id, payload in mapping_entries.items():
        if str(payload.get("domain_ref")) not in domain_ids:
            raise DeclarativeProfileCandidateError(
                f"MAPPING_DOMAIN_REF_NOT_IN_PACKAGE:{entry_id}"
            )
        relationship = payload.get("relationship_binding")
        if relationship is None:
            continue
        relationship = _mapping(
            relationship, "RELATIONSHIP_BINDING_NOT_MAPPING"
        )
        refs = {
            str(relationship.get("left_mapping_ref") or ""),
            str(relationship.get("right_mapping_ref") or ""),
        }
        if "" in refs or not refs <= set(mapping_entries):
            raise DeclarativeProfileCandidateError(
                f"RELATIONSHIP_MAPPING_REF_NOT_IN_PACKAGE:{entry_id}"
            )
        if relationship.get("authority_basis") not in {
            "schema_defined", "steward_verified", "usage_observed", "llm_inferred"
        } or not isinstance(relationship.get("physically_validated"), bool):
            raise DeclarativeProfileCandidateError(
                f"RELATIONSHIP_AUTHORITY_CONTRACT_INVALID:{entry_id}"
            )

    documents: list[ProfileCandidateDocument] = []
    for (
        entry_id,
        category,
        profile,
        evidence_resources,
        payload,
        metadata,
        rendered,
    ) in pending:
        document_digest = _digest(rendered)
        revision_digest = _digest(
            {
                "package_id": package_id,
                "entry_id": entry_id,
                "category": category,
                "document_digest": document_digest,
                "status": "candidate",
            }
        )
        documents.append(ProfileCandidateDocument(
            entry_id=entry_id,
            category=category,
            profile=profile,
            boi_id=str(metadata["boi_id"]),
            evidence_resources=evidence_resources,
            payload=payload,
            rendered_document=rendered,
            document_digest=document_digest,
            revision_digest=revision_digest,
        ))
    documents.sort(key=lambda item: (item.category, item.entry_id))
    profile_counts = {
        category: sum(item.category == category for item in documents)
        for category in _CATEGORY_CONTRACT
    }
    profile_digests = {
        category: _digest([
            item.revision_digest for item in documents if item.category == category
        ])
        for category in _CATEGORY_CONTRACT
    }
    package_base = {
        "schema": _SCHEMA,
        "package_id": package_id,
        "status": "candidate",
        "qualification_status": "not_run",
        "release_id": None,
        "active_pointer_transition": False,
        "canonical_projection_eligible": False,
        "source_receipts": [item.__dict__ for item in source_receipts],
        "documents": [
            {
                "entry_id": item.entry_id,
                "category": item.category,
                "document_digest": item.document_digest,
                "revision_digest": item.revision_digest,
            }
            for item in documents
        ],
        "profile_counts": profile_counts,
        "profile_digests": profile_digests,
    }
    return DeclarativeProfileCandidatePackage(
        schema=_SCHEMA,
        package_id=package_id,
        status="candidate",
        qualification_status="not_run",
        release_id=None,
        active_pointer_transition=False,
        canonical_projection_eligible=False,
        source_receipts=source_receipts,
        documents=tuple(documents),
        profile_counts=profile_counts,
        domain_profile_digest=profile_digests["domain"],
        mapping_profile_digest=profile_digests["mapping"],
        query_profile_digest=profile_digests["query"],
        package_digest=_digest(package_base),
    )
