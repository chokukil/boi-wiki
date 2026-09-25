"""Native-authored profile projection into existing planner inputs.

Projection is data, not an inference runner. The authorized reader revalidates
Wiki dependencies; this module never grants database access or semantic truth.
"""
from .diagnostic_timing import stage_timing
from typing import Literal
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, Ref, Digest, RevisionRef, semantic_digest
from .semantic_profile_loader import LoadedProfileEntry, PhysicalProfileBinding, SemanticContextBundle
from .native_definition_context import read_native_definition_authority
from .native_observation import _json
from .domain_asset_store import DomainAssetStore, source_manifest_digest
from .source_envelope import ArtifactEnvelope
from .semantic_authority import NativeProcessReviewAuthority
from .knowledge_content import meaning_pointer


class NativeProfileEntry(FrozenContract):
    entry_id: Ref
    category: Literal['domain','mapping','query']
    definition_revision: RevisionRef
    payload_json: Ref
    physical: PhysicalProfileBinding | None = None
    source_revision: RevisionRef | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode='after')
    def closed_payload(self):
        if not isinstance(_json(self.payload_json),dict):
            raise ValueError('NATIVE_PROFILE_PAYLOAD_REQUIRED')
        if (self.category=='mapping') != (self.physical is not None):
            raise ValueError('NATIVE_PROFILE_PHYSICAL_SCOPE_INVALID')
        if self.source_revision is not None and self.category != 'mapping':
            raise ValueError('NATIVE_PROFILE_SOURCE_MAPPING_ONLY')
        return self


class NativeProfileProjection(FrozenContract):
    contract_version: Literal['boi/native-profile-projection@1']='boi/native-profile-projection@1'
    definition_review_revision: RevisionRef
    definition_revisions: tuple[RevisionRef,...] = Field(min_length=1)
    catalog_snapshot_digest: Digest
    schema_digest: Digest
    entries: tuple[NativeProfileEntry,...] = Field(min_length=1)
    semantic_equivalence_proven: Literal[False]=False
    execution_authority_granted: Literal[False]=False

    @model_validator(mode='after')
    def unique_entries(self):
        if len({e.entry_id for e in self.entries})!=len(self.entries):
            raise ValueError('NATIVE_PROFILE_DUPLICATE_ENTRY')
        return self


class NativeScopedProfileEntry(NativeProfileEntry):
    # The entire entry payload is consumed from this reviewed node. Extra fields,
    # conditions and exceptions cannot be dropped through selective leaf binding.
    definition_pointer: str = Field(max_length=2048)


class NativeProfileProjectionV2(NativeProfileProjection):
    contract_version: Literal['boi/native-profile-projection@2'] = 'boi/native-profile-projection@2'
    definition_revisions: tuple[RevisionRef, ...] = Field(min_length=1, max_length=1)
    entries: tuple[NativeScopedProfileEntry, ...] = Field(min_length=1, max_length=500)


@stage_timing('profile_projection_validation')
def native_profile_projection(value):
    if isinstance(value, (NativeProfileProjection, NativeProfileProjectionV2)):
        value = value.model_dump(mode='json')
    cls = NativeProfileProjectionV2 if value.get('contract_version') == 'boi/native-profile-projection@2' else NativeProfileProjection
    return cls.model_validate(value)


@stage_timing('build_native_profile_bundle')
def build_native_profile_bundle(*,authority,context,catalog,projection,profile_revision,source_profiles=None,
        source_bundles=None):
    """Pure structural projection; use the authorized reader for admission."""
    projection=native_profile_projection(projection)
    profile_revision=RevisionRef.model_validate(profile_revision)
    if (projection.definition_review_revision!=authority.review_revision
            or projection.definition_revisions!=authority.definition_revisions
            or context.context_digest!=authority.definition_context_digest):
        raise ValueError('NATIVE_PROFILE_REVIEW_CONTEXT_MISMATCH')
    if (projection.catalog_snapshot_digest!=catalog.snapshot_digest
            or projection.schema_digest!=catalog.schema_digest):
        raise ValueError('NATIVE_PROFILE_CATALOG_MISMATCH')
    physical={(s.source_id,t.name,c.name) for s in catalog.sources for t in s.tables for c in t.columns}
    entries=[]
    scoped = isinstance(authority, NativeProcessReviewAuthority)
    if scoped and not isinstance(projection, NativeProfileProjectionV2):
        raise ValueError('NATIVE_PROFILE_SELECTED_BINDINGS_REQUIRED')
    if isinstance(projection, NativeProfileProjectionV2) and not scoped:
        raise ValueError('NATIVE_PROFILE_SELECTED_AUTHORITY_REQUIRED')
    definitions = {a.revision: a for a in context.assets} if scoped else {}
    definition_payloads={}
    source_projections={}
    for item in projection.entries:
        if item.definition_revision not in authority.definition_revisions:
            raise ValueError('NATIVE_PROFILE_DEFINITION_NOT_REVIEWED')
        if item.physical and (item.physical.source,item.physical.table,item.physical.column) not in physical:
            raise ValueError('NATIVE_PROFILE_PHYSICAL_COLUMN_UNAVAILABLE')
        payload=_json(item.payload_json)
        if scoped:
            if item.definition_pointer not in authority.selected_target_pointers:
                raise ValueError('NATIVE_PROFILE_POINTER_NOT_SELECTED')
            asset = definitions.get(item.definition_revision)
            if asset is None:
                raise ValueError('NATIVE_PROFILE_DEFINITION_NOT_IN_CONTEXT')
            if item.definition_revision not in definition_payloads:
                definition_payloads[item.definition_revision] = _json(asset.content_json)
            selected = meaning_pointer(definition_payloads[item.definition_revision], item.definition_pointer)
            if semantic_digest(selected) != semantic_digest(payload):
                raise ValueError('NATIVE_PROFILE_SELECTED_PAYLOAD_MISMATCH')
            if item.physical is not None and payload.get('physical') != item.physical.model_dump(mode='json'):
                raise ValueError('NATIVE_PROFILE_SELECTED_PHYSICAL_MISMATCH')
        declared=payload.get({'domain':'id','mapping':'mapping_id','query':'query_spec_id'}[item.category])
        if declared!=item.entry_id:
            raise ValueError('NATIVE_PROFILE_ENTRY_ID_MISMATCH')
        entry_revision = profile_revision
        if item.source_revision is not None:
            source = (source_profiles or {}).get(item.source_revision)
            if source is None:
                raise ValueError('NATIVE_PROFILE_SOURCE_REVISION_REQUIRED')
            if item.source_revision not in source_projections:
                source_projections[item.source_revision] = native_profile_projection(source)
            source = source_projections[item.source_revision]
            if (source.catalog_snapshot_digest != projection.catalog_snapshot_digest
                or source.schema_digest != projection.schema_digest):
                raise ValueError('NATIVE_PROFILE_SOURCE_CONTEXT_MISMATCH')
            same_definition = (source.definition_review_revision == projection.definition_review_revision
                and source.definition_revisions == projection.definition_revisions)
            if not same_definition:
                # A later relationship definition can reuse already issued key
                # mappings without making the definition hash depend on itself.
                # Both scoped reviews must be read independently under the
                # current principal/source grant; equal payloads alone are not
                # review authority or permission to reuse another profile.
                admitted = (source_bundles or {}).get(item.source_revision)
                prior_authority = getattr(admitted, 'reviewed_definition_authority', None)
                if (not scoped or not isinstance(source, NativeProfileProjectionV2)
                    or not isinstance(prior_authority, NativeProcessReviewAuthority)
                    or prior_authority.review_revision != source.definition_review_revision
                    or prior_authority.definition_revisions != source.definition_revisions
                    or any(getattr(prior_authority, key) != getattr(authority, key)
                        for key in ('principal', 'acl_policy_digest', 'source_manifest_digest'))
                    or admitted.principal_id != authority.principal
                    or admitted.catalog_snapshot_digest != catalog.snapshot_digest
                    or admitted.schema_digest != catalog.schema_digest):
                    raise ValueError('NATIVE_PROFILE_SOURCE_CONTEXT_MISMATCH')
                admitted_entry = next((e for e in admitted.mapping_entries
                    if e.entry_id == item.entry_id), None)
                if (admitted_entry is None
                    or admitted_entry.revision_id != item.source_revision.ref
                    or admitted_entry.revision_digest != item.source_revision.revision_digest
                    or admitted_entry.physical != item.physical
                    or semantic_digest(admitted_entry.payload) != semantic_digest(payload)):
                    raise ValueError('NATIVE_PROFILE_SOURCE_ENTRY_MISMATCH')
            prior = next((e for e in source.entries if e.entry_id == item.entry_id), None)
            excluded = {'source_revision'} if same_definition else {
                'source_revision', 'definition_revision', 'definition_pointer'}
            if (prior is None or prior.source_revision is not None
                or semantic_digest(prior.model_dump(mode='json',exclude=excluded))
                != semantic_digest(item.model_dump(mode='json',exclude=excluded))):
                raise ValueError('NATIVE_PROFILE_SOURCE_ENTRY_MISMATCH')
            entry_revision = item.source_revision
        entries.append(LoadedProfileEntry(entry_id=item.entry_id,category=item.category,
            revision_id=entry_revision.ref,revision_digest=entry_revision.revision_digest,
            boi_id=item.entry_id,visibility='private',
            evidence_resources=(item.definition_revision.ref,authority.review_revision.ref),
            payload=payload,physical=item.physical,availability='bound' if item.physical else 'not_applicable'))
    domain=[e for e in entries if e.category=='domain'];mapping=[e for e in entries if e.category=='mapping'];query=[e for e in entries if e.category=='query']
    domain_ids={e.entry_id for e in domain}
    if any(e.payload.get('domain_ref') not in domain_ids for e in mapping):
        raise ValueError('NATIVE_PROFILE_MAPPING_DOMAIN_UNAVAILABLE')
    bound={e.payload['domain_ref'] for e in mapping}
    body=dict(release_id=None,active_release_digest=None,qualification_receipt_id=None,
        reviewed_definition_authority=authority.model_dump(mode='json'),principal_id=authority.principal,purpose=authority.purpose,
        catalog_snapshot_digest=catalog.snapshot_digest,schema_digest=catalog.schema_digest,capability_digest=catalog.capability_digest,
        domain_profile_digest=semantic_digest([e.model_dump(mode='json') for e in domain]),mapping_profile_digest=semantic_digest([e.model_dump(mode='json') for e in mapping]),
        query_profile_digest=semantic_digest([e.model_dump(mode='json') for e in query]),acl_projection_digest=semantic_digest(authority),
        retrieval_index_digest=semantic_digest([e.model_dump(mode='json') for e in domain]),domain_entries=[e.model_dump(mode='json') for e in domain],
        mapping_entries=[e.model_dump(mode='json') for e in mapping],query_entries=[e.model_dump(mode='json') for e in query],
        excluded_revision_ids=[],non_profile_revision_ids=[],unavailable_logical_ids=sorted(e.entry_id for e in domain
            if e.payload.get('kind')=='PropertyDefinition' and e.entry_id not in bound),body_bytes_exposed_to_context=0)
    return SemanticContextBundle.model_validate({**body,'bundle_digest':semantic_digest(body)})


def read_native_profile_bundle(work,authorization,*,review_revision,profile_revision,catalog,
        _profile_ancestors=()):
    """Existing Wiki source/asset authorization and current-context fences."""
    bundle, _ = _read_native_profile_bundle(work,authorization,review_revision=review_revision,
        profile_revision=profile_revision,catalog=catalog,_profile_ancestors=_profile_ancestors)
    return bundle


@stage_timing('read_native_profile_bundle')
def _read_native_profile_bundle(work,authorization,*,review_revision,profile_revision,catalog,
        _profile_ancestors=(),_parent_source_manifest=None):
    # Each recursive admission reads and validates its own exact profile once.
    # No read or authority decision survives this call or a later current fence.
    profile_revision=RevisionRef.model_validate(profile_revision)
    if profile_revision in _profile_ancestors or len(_profile_ancestors) >= 16:
        raise ValueError('NATIVE_PROFILE_SOURCE_CYCLE_OR_DEPTH_LIMIT')
    assets=getattr(work,'assets',None) or DomainAssetStore(work.intake)
    stored=assets.read(authorization=authorization,revision=profile_revision,lane='provisional')
    source_child = _parent_source_manifest is not None
    if stored['asset']['kind']!='profile':
        raise ValueError('NATIVE_PROFILE_SOURCE_KIND_INVALID' if source_child else 'NATIVE_PROFILE_KIND_REQUIRED')
    sources=tuple(ArtifactEnvelope.model_validate(s) for s in stored['sources'])
    manifest=source_manifest_digest(sources)
    if source_child and manifest!=_parent_source_manifest:
        raise ValueError('NATIVE_PROFILE_SOURCE_MANIFEST_MISMATCH')
    if not stored['definition_reading_ref']:
        raise ValueError('NATIVE_PROFILE_SOURCE_READING_REQUIRED' if source_child else 'NATIVE_PROFILE_CURRENT_READING_REQUIRED')
    projection=native_profile_projection(_json(stored['asset']['content_json']))
    if source_child:
        review_revision=projection.definition_review_revision
    uses = ({'definition_use':{'revision':projection.definition_revisions[0],
            'target_pointers':tuple(dict.fromkeys(e.definition_pointer for e in projection.entries))}}
            if isinstance(projection,NativeProfileProjectionV2) else {})
    authority,context=read_native_definition_authority(work,authorization,review_revision,**uses)
    if manifest!=authority.source_manifest_digest:
        raise ValueError('NATIVE_PROFILE_SOURCE_MISMATCH')
    reading=work.contexts.validate_reading(authorization=authorization,
        revision=RevisionRef.model_validate(stored['definition_reading_ref']),sources=sources,require_current=True)
    source_refs={e.source_revision for e in projection.entries if e.source_revision is not None}
    required={authority.review_revision,*authority.definition_revisions,*source_refs}
    dependencies={RevisionRef.model_validate(d['revision']) for d in stored['asset']['dependencies'] if d['required']}
    if not required<=dependencies & {a.revision for a in reading.assets}:
        raise ValueError('NATIVE_PROFILE_DEPENDENCY_NOT_READ')
    source_profiles={}
    source_bundles={}
    for ref in sorted(source_refs, key=lambda value: (value.ref, value.revision_digest)):
        source_bundles[ref],source_profiles[ref]=_read_native_profile_bundle(work,authorization,
            review_revision=None,profile_revision=ref,catalog=catalog,
            _profile_ancestors=(*_profile_ancestors,profile_revision),
            _parent_source_manifest=authority.source_manifest_digest)
    bundle=build_native_profile_bundle(authority=authority,context=context,catalog=catalog,
        projection=projection,profile_revision=profile_revision,source_profiles=source_profiles,
        source_bundles=source_bundles)
    return bundle,projection
