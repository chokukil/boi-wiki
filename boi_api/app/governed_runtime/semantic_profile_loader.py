"""ACL-first loader for profile revisions in the exact active Release."""

from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter, model_validator

from .ledger import GovernedRuntimeLedger, RecordKind, record_digest
from .okf_v02 import validate_boi_profile_v02
from .qualification_contract import QualificationContractError, validate_qualification_receipt_payload
from .release_rebuild import KnowledgeObjectStore, ReleaseRebuildError
from .semantic_binding_contract import ConceptLookupClosure, Digest, Ref, semantic_digest
from .semantic_authority import SemanticAuthorityFields


_DOCUMENT_RE = re.compile(r"\A---\n(?P<header>.*?)\n---\n(?P<body>.*)\Z", re.DOTALL)
_PROFILE_DOCUMENT_DECODE = ContextVar('profile_document_decode', default=None)


@contextmanager
def request_profile_document_decoding():
    """Reuse only parsed/strictly validated bytes within one query action."""
    token = _PROFILE_DOCUMENT_DECODE.set({})
    try:
        yield
    finally:
        _PROFILE_DOCUMENT_DECODE.reset(token)


_PROFILE_KEYS = {
    "boi/domain@0.1.0": ("domain", "domain"),
    "boi/domain@0.2.0": ("domain", "domain"),
    "boi/domain@0.3.0": ("domain", "domain"),
    "boi/domain@0.4.0": ("domain", "domain"),
    "boi/domain@0.5.0": ("domain", "domain"),
    "boi/data-mapping@0.1.0": ("data_mapping", "mapping"),
    "boi/data-mapping@0.2.0": ("data_mapping", "mapping"),
    "boi/query@0.1.0": ("query", "query"),
    "boi/query@0.2.0": ("query", "query"),
    "boi/query@0.3.0": ("query", "query"),
    "boi/query@0.4.0": ("query", "query"),
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


class ActiveProfileLoadError(RuntimeError):
    pass


class ProfilePrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: str
    team_ids: tuple[str, ...] = ()


class ProfileCatalogSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    snapshot_digest: str
    schema_digest: str
    capability_digest: str
    authorized_source_ids: tuple[str, ...]
    captured_at: str


class PhysicalProfileBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str
    table: str
    column: str


class LoadedProfileEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entry_id: str
    category: Literal["domain", "mapping", "query"]
    revision_id: str
    revision_digest: str
    boi_id: str
    visibility: Literal["private", "team", "public"]
    evidence_resources: tuple[str, ...]
    payload: dict[str, Any]
    availability: Literal["bound", "unbound", "not_applicable"] = "not_applicable"
    physical: PhysicalProfileBinding | None = None


class SemanticContextBundle(SemanticAuthorityFields):
    model_config = ConfigDict(extra="forbid", frozen=True)

    release_id: str | None
    active_release_digest: str | None
    qualification_receipt_id: str | None
    principal_id: str
    purpose: str
    catalog_snapshot_digest: str
    schema_digest: str
    capability_digest: str
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    acl_projection_digest: str
    retrieval_index_digest: str
    domain_entries: tuple[LoadedProfileEntry, ...]
    mapping_entries: tuple[LoadedProfileEntry, ...]
    query_entries: tuple[LoadedProfileEntry, ...]
    excluded_revision_ids: tuple[str, ...]
    non_profile_revision_ids: tuple[str, ...]
    unavailable_logical_ids: tuple[str, ...]
    body_bytes_exposed_to_context: Literal[0] = 0
    bundle_digest: str

    @model_validator(mode='after')
    def reviewed_context_is_not_a_release(self):
        authority = self.reviewed_definition_authority
        if authority is None:
            if self.release_id is None or self.qualification_receipt_id is None:
                raise ValueError('SEMANTIC_RELEASE_IDENTIFIERS_REQUIRED')
        elif (self.release_id is not None or self.qualification_receipt_id is not None
                or self.principal_id != authority.principal or self.purpose != authority.purpose):
            raise ValueError('REVIEWED_SEMANTIC_CONTEXT_AUTHORITY_MISMATCH')
        return self


class ActiveDefinitionSnapshot(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/active-definition-snapshot@1'] = 'boi/active-definition-snapshot@1'
    active_release_digest: Digest
    qualification_receipt_id: str
    lookup: ConceptLookupClosure
    entries: tuple[LoadedProfileEntry, ...]
    read_at: datetime
    reason_codes: tuple[str, ...]
    body_bytes_exposed_to_context: Literal[0] = 0
    semantic_equivalence_decided: Literal[False] = False
    snapshot_digest: Digest


class ActiveReleaseProfileLoader:
    def __init__(self, ledger: GovernedRuntimeLedger, object_store: KnowledgeObjectStore):
        self.ledger = ledger
        self.object_store = object_store

    @staticmethod
    def _visible(metadata: dict[str, Any], principal: ProfilePrincipal) -> bool:
        visibility = metadata.get("visibility")
        if visibility == "public":
            return True
        if visibility == "private":
            return metadata.get("owner") == principal.principal_id
        if visibility == "team":
            return metadata.get("team_id") in principal.team_ids
        return False

    @staticmethod
    def _metadata(payload: bytes) -> dict[str, Any]:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ActiveProfileLoadError("PROFILE_DOCUMENT_NOT_UTF8") from exc
        match = _DOCUMENT_RE.match(text)
        if match is None:
            raise ActiveProfileLoadError("PROFILE_DOCUMENT_FRONTMATTER_INVALID")
        metadata = yaml.safe_load(match.group("header")) or {}
        if not isinstance(metadata, dict):
            raise ActiveProfileLoadError("PROFILE_DOCUMENT_FRONTMATTER_NOT_MAPPING")
        return metadata

    @staticmethod
    def _validate_visible_metadata(metadata: dict[str, Any]) -> None:
        validation = validate_boi_profile_v02(metadata)
        if not validation.ok:
            codes = ",".join(sorted({item.code for item in validation.errors}))
            raise ActiveProfileLoadError(f"PROFILE_DOCUMENT_STRICT_VALIDATION_FAILED:{codes}")

    @staticmethod
    def _entry(
        metadata: dict[str, Any], revision_id: str, profile: str,
        catalog: ProfileCatalogSnapshot | None,
    ) -> LoadedProfileEntry:
        payload_key, category = _PROFILE_KEYS[profile]
        payload = dict(metadata[payload_key])
        if category == "domain":
            entry_id = str(payload["id"])
            availability: Literal["bound", "unbound", "not_applicable"] = "not_applicable"
            physical = None
        elif category == "mapping":
            entry_id = str(payload["mapping_id"])
            availability = payload.get("availability", "bound")
            physical_value = payload.get("physical")
            physical = PhysicalProfileBinding.model_validate(physical_value) if physical_value else None
            if availability == "bound":
                if catalog is None:
                    raise ActiveProfileLoadError("MAPPING_CATALOG_REQUIRED")
                if payload.get("schema_snapshot_digest") != catalog.schema_digest:
                    raise ActiveProfileLoadError("MAPPING_SCHEMA_DIGEST_MISMATCH")
                if physical is None or physical.source not in catalog.authorized_source_ids:
                    raise ActiveProfileLoadError("MAPPING_SOURCE_NOT_AUTHORIZED")
        else:
            entry_id = str(payload["query_spec_id"])
            availability = "not_applicable"
            physical = None
            if metadata.get("type") == "Attested Computation":
                payload["attested_contract"] = {
                    "runtime": metadata.get("runtime"),
                    "executor": metadata.get("executor"),
                    "attester": metadata.get("attester"),
                }
        sources = metadata.get("sources") or []
        return LoadedProfileEntry(
            entry_id=entry_id,
            category=category,
            revision_id=revision_id,
            revision_digest=record_digest(revision_id),
            boi_id=str(metadata["boi_id"]),
            visibility=metadata["visibility"],
            evidence_resources=tuple(str(item["resource"]) for item in sources),
            payload=payload,
            availability=availability,
            physical=physical,
        )

    @staticmethod
    def _dependencies(entry: LoadedProfileEntry) -> set[str]:
        payload = entry.payload
        values: list[Any] = []
        for key in (
            "depends_on", "identity_property_ref", "properties", "property_refs",
            "logical_grain", "left_property_ref",
            "right_property_ref", "numerator_ref", "denominator_ref",
            "left_property_refs", "right_property_refs", "relationship_identity_ref",
            "value_type_ref", "unit_ref", "unit_property_ref",
        ):
            if key in payload:
                values.append(payload[key])
        logical_plan = payload.get("logical_plan")
        if isinstance(logical_plan, dict) and "depends_on" in logical_plan:
            values.append(logical_plan["depends_on"])
        dependencies: set[str] = set()
        from .latest_selection_contract import latest_contract_dependencies
        dependencies.update(latest_contract_dependencies(payload))
        for value in values:
            if isinstance(value, str):
                dependencies.add(value)
            elif isinstance(value, list):
                dependencies.update(str(item) for item in value)
        return dependencies

    def _read_active_entries(
        self, *, principal: ProfilePrincipal, purpose: str,
        at: datetime, catalog_snapshot: ProfileCatalogSnapshot | None,
        category_filter: str | None = None,
        namespace_filter: str | None = None,
    ):
        from ..v2.native_formula_timing import timed_call
        if not purpose.strip():
            raise ActiveProfileLoadError("PURPOSE_REQUIRED")
        if at.utcoffset() is None:
            raise ActiveProfileLoadError("PROFILE_READ_TIME_OFFSET_REQUIRED")
        pointer = self.ledger.active_pointer()
        if pointer is None or pointer.get("status") != "ACTIVE":
            raise ActiveProfileLoadError("ACTIVE_RELEASE_POINTER_ABSENT")
        # Query-time authority depends on the complete event chain and the
        # active release's closed qualified record set.  A separate full ledger
        # audit also checks inactive historical bodies; keeping that maintenance
        # scan off this path prevents repository history from setting latency.
        # Selected records are revalidated by read(), and the active pointer is
        # fenced before and after this scope read.
        if not timed_call('active_release_integrity_verification',
                self.ledger.verify_active_release, pointer,
                reuse_request_audit=True).ok:
            raise ActiveProfileLoadError("LEDGER_VERIFICATION_FAILED")
        release_id = str(pointer.get("release_id") or "")
        if pointer.get("release_manifest_digest") != record_digest(release_id):
            raise ActiveProfileLoadError("ACTIVE_POINTER_RELEASE_DIGEST_MISMATCH")
        release = self.ledger.read(release_id)
        if release.kind is not RecordKind.RELEASE_MANIFEST:
            raise ActiveProfileLoadError("ACTIVE_POINTER_NOT_RELEASE_MANIFEST")
        receipt_id = str(release.payload.get("qualification_receipt_id") or "")
        receipt = self.ledger.read(receipt_id)
        revision_ids = list(release.payload.get("revision_ids") or [])
        try:
            if receipt.kind is not RecordKind.QUALIFICATION_RECEIPT:
                raise QualificationContractError("not a QualificationReceipt")
            validate_qualification_receipt_payload(receipt.payload)
        except QualificationContractError as exc:
            raise ActiveProfileLoadError("ACTIVE_RELEASE_NOT_EXACTLY_QUALIFIED") from exc
        if revision_ids != list(receipt.payload.get("revision_ids") or []):
            raise ActiveProfileLoadError("ACTIVE_RELEASE_NOT_EXACTLY_QUALIFIED")

        entries: list[LoadedProfileEntry] = []
        excluded: list[str] = []
        non_profile: list[str] = []
        for revision_id in revision_ids:
            revision = self.ledger.read(revision_id)
            if revision.kind is not RecordKind.KNOWLEDGE_REVISION:
                raise ActiveProfileLoadError("RELEASE_CONTAINS_NON_KNOWLEDGE_REVISION")
            object_id = str(revision.payload.get("document_object_id") or "")
            try:
                payload = timed_call('active_release_object_read',
                    self.object_store.get, object_id)
            except ReleaseRebuildError as exc:
                raise ActiveProfileLoadError("PROFILE_OBJECT_INVALID") from exc
            document_digest = "sha256:" + hashlib.sha256(payload).hexdigest()
            if document_digest != revision.payload.get("document_digest"):
                raise ActiveProfileLoadError("PROFILE_REVISION_DOCUMENT_DIGEST_MISMATCH")
            decode_cache = _PROFILE_DOCUMENT_DECODE.get()
            cached = decode_cache.get(document_digest) if decode_cache is not None else None
            if cached is None:
                metadata = timed_call('active_release_metadata_parse', self._metadata, payload)
                if decode_cache is not None:
                    if len(decode_cache) >= 512:
                        decode_cache.clear()
                    decode_cache[document_digest] = (metadata, False)
            else:
                metadata = cached[0]
            selected = [profile for profile in metadata.get("profiles", ()) if profile in _PROFILE_KEYS]
            if not selected:
                non_profile.append(revision_id)
                continue
            if len(selected) != 1:
                raise ActiveProfileLoadError("PROFILE_ENTRY_CATEGORY_AMBIGUOUS")
            if category_filter and _PROFILE_KEYS[selected[0]][1] != category_filter:
                continue
            if not self._visible(metadata, principal):
                excluded.append(revision_id)
                continue
            if namespace_filter is not None:
                namespace = self._definition_namespace(metadata.get('domain') or {})
                if namespace is not None and namespace != namespace_filter:
                    continue
            if cached is None or not cached[1]:
                timed_call('active_release_profile_validation',
                    self._validate_visible_metadata, metadata)
                if decode_cache is not None:
                    decode_cache[document_digest] = (metadata, True)
            stale_after = datetime.fromisoformat(str(metadata["stale_after"]).replace("Z", "+00:00"))
            if stale_after <= at:
                raise ActiveProfileLoadError("PROFILE_REVISION_STALE")
            entries.append(self._entry(metadata, revision_id, selected[0], catalog_snapshot))

        entries.sort(key=lambda item: (item.category, item.entry_id, item.revision_id))
        keys = [(entry.category, entry.entry_id) for entry in entries]
        if len(keys) != len(set(keys)):
            raise ActiveProfileLoadError("DUPLICATE_ACTIVE_PROFILE_ENTRY_ID")
        if self.ledger.active_pointer() != pointer:
            raise ActiveProfileLoadError("ACTIVE_POINTER_CHANGED_DURING_READ")
        return release_id, receipt_id, entries, excluded, non_profile

    @staticmethod
    def _definition_namespace(payload: dict[str, Any]) -> str | None:
        semantic = payload.get('semantic_contract')
        scope = semantic.get('scope') if isinstance(semantic, dict) else None
        namespace = scope.get('namespace') if isinstance(scope, dict) else None
        return namespace if isinstance(namespace, str) and namespace.strip() else None

    def load_definition_scope(
        self, *, principal: ProfilePrincipal, purpose: str, namespace: str,
        policy_digest: str, at: datetime,
    ) -> ActiveDefinitionSnapshot:
        """Complete authorized namespace read, independent of ranking or SQL.

        Uses exactly the same active pointer, ledger/receipt/document integrity,
        ACL and freshness checks as query loading. Missing legacy namespaces
        remain explicit partial scope; they never become an absence claim.
        """
        namespace = TypeAdapter(Ref).validate_python(namespace)
        policy_digest = TypeAdapter(Digest).validate_python(policy_digest)
        release_id, receipt_id, entries, _excluded, _non_profile = self._read_active_entries(
            principal=principal, purpose=purpose, at=at, catalog_snapshot=None,
            category_filter='domain', namespace_filter=namespace)
        unresolved_namespace = any(self._definition_namespace(entry.payload) is None for entry in entries)
        closure = semantic_digest({'active_release_digest':record_digest(release_id),
            'principal_id':principal.principal_id, 'team_ids':sorted(principal.team_ids),
            'policy_digest':policy_digest, 'namespace':namespace,
            'revisions':[(entry.entry_id,entry.revision_digest) for entry in entries]})
        lookup = ConceptLookupClosure(principal_id=principal.principal_id, policy_digest=policy_digest,
            namespace=namespace, index_revision_digest=closure,
            query_scope_digest=semantic_digest({'namespace':namespace,'scope_policy':'exact-authorized-namespace@1'}),
            profile_closure_digest=closure, status='partial' if unresolved_namespace else 'complete',
            concept_revision_digests=tuple(entry.revision_digest for entry in entries))
        values = dict(contract_version='boi/active-definition-snapshot@1',
            active_release_digest=record_digest(release_id), qualification_receipt_id=receipt_id,
            lookup=lookup.model_dump(mode='json'), entries=[entry.model_dump(mode='json') for entry in entries],
            read_at=at.astimezone(timezone.utc), reason_codes=['DEFINITION_NAMESPACE_MIGRATION_REQUIRED'] if unresolved_namespace else [],
            body_bytes_exposed_to_context=0, semantic_equivalence_decided=False)
        snapshot = ActiveDefinitionSnapshot(**values, snapshot_digest='sha256:' + '0' * 64)
        # Seal the exact normalized wire representation, not an intermediate
        # datetime string (+00:00 and Z otherwise hash differently).
        return snapshot.model_copy(update={'snapshot_digest':semantic_digest(
            snapshot.model_dump(mode='json', exclude={'snapshot_digest'}))})

    def load(
        self, *, principal: ProfilePrincipal, purpose: str,
        catalog_snapshot: ProfileCatalogSnapshot,
    ) -> SemanticContextBundle:
        release_id, receipt_id, entries, excluded, non_profile = self._read_active_entries(
            principal=principal, purpose=purpose, catalog_snapshot=catalog_snapshot,
            at=datetime.fromisoformat(catalog_snapshot.captured_at.replace('Z', '+00:00')))
        domains = tuple(entry for entry in entries if entry.category == "domain")
        mappings = tuple(entry for entry in entries if entry.category == "mapping")
        queries = tuple(entry for entry in entries if entry.category == "query")

        domain_ids = {entry.entry_id for entry in domains}
        for entry in mappings:
            if str(entry.payload["domain_ref"]) not in domain_ids:
                raise ActiveProfileLoadError("MAPPING_DOMAIN_REF_NOT_IN_ACTIVE_ACL_PROJECTION")
        for entry in (*domains, *queries):
            if self._dependencies(entry) - domain_ids:
                raise ActiveProfileLoadError("LOGICAL_DEPENDENCY_NOT_IN_ACTIVE_ACL_PROJECTION")

        mapped_refs = {str(entry.payload["domain_ref"]) for entry in mappings if entry.availability == "bound"}
        unavailable = {
            str(entry.payload["domain_ref"]) for entry in mappings if entry.availability == "unbound"
        }
        unavailable.update(
            entry.entry_id
            for entry in domains
            if entry.payload.get("kind") == "PropertyDefinition" and entry.entry_id not in mapped_refs
        )
        changed = True
        while changed:
            changed = False
            for entry in (*domains, *queries):
                if entry.entry_id not in unavailable and self._dependencies(entry) & unavailable:
                    unavailable.add(entry.entry_id)
                    changed = True

        category_ids = {
            "domain": [entry.revision_id for entry in domains],
            "mapping": [entry.revision_id for entry in mappings],
            "query": [entry.revision_id for entry in queries],
        }
        acl_projection = {
            "principal_id": principal.principal_id,
            "team_ids": sorted(principal.team_ids),
            "purpose": purpose,
            "included": [entry.revision_id for entry in entries],
            "excluded": sorted(excluded),
        }
        base = {
            "release_id": release_id,
            "active_release_digest": record_digest(release_id),
            "qualification_receipt_id": receipt_id,
            "principal_id": principal.principal_id,
            "purpose": purpose,
            "catalog_snapshot_digest": catalog_snapshot.snapshot_digest,
            "schema_digest": catalog_snapshot.schema_digest,
            "capability_digest": catalog_snapshot.capability_digest,
            "domain_profile_digest": _digest(category_ids["domain"]),
            "mapping_profile_digest": _digest(category_ids["mapping"]),
            "query_profile_digest": _digest(category_ids["query"]),
            "acl_projection_digest": _digest(acl_projection),
            "retrieval_index_digest": _digest({"entries": [(e.category, e.entry_id, e.revision_id) for e in entries]}),
            "domain_entries": domains,
            "mapping_entries": mappings,
            "query_entries": queries,
            "excluded_revision_ids": tuple(sorted(excluded)),
            "non_profile_revision_ids": tuple(sorted(non_profile)),
            "unavailable_logical_ids": tuple(sorted(unavailable)),
            "body_bytes_exposed_to_context": 0,
        }
        serializable = {
            key: [item.model_dump(mode="json") for item in value] if key.endswith("_entries") else value
            for key, value in base.items()
        }
        return SemanticContextBundle(**base, bundle_digest=_digest(serializable))
