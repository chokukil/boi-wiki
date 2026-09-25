"""Validate a source-to-Profile routing observation before ontology authoring.

The model may propose reuse, extension, or a new Profile, but this module owns
coverage, source evidence, profile identity, and non-destructive extension
checks. A ready result is still a provisional authoring route, never Release
or semantic approval.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from boi_api.app.governed_runtime.knowledge_profile import (
    KnowledgeProfileDeclaration, ObjectTypeDeclaration, PredicateDeclaration)
from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef, semantic_digest
from agent_kit.package_contract import dependency_order


class SourceFeature(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    feature_id: str = Field(min_length=1, max_length=512)
    label: str = Field(min_length=1, max_length=2048)
    value_kinds: tuple[Literal['text', 'decimal', 'integer', 'boolean', 'empty', 'unknown'], ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    required_for_reuse: bool = True
    source_path: str | None = Field(default=None, min_length=1, max_length=1024)


class AvailableProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    revision: RevisionRef
    declaration: KnowledgeProfileDeclaration
    allowed_domains: tuple[str, ...] = Field(min_length=1)
    package_ids: tuple[str, ...] = ()
    can_anchor_extension: bool = True


class FeatureDisposition(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    feature_id: str
    disposition: Literal['mapped', 'unresolved', 'evidence_context', 'outside_scope']
    component_id: str | None = None
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=4000)

    @model_validator(mode='after')
    def component_boundary(self):
        if (self.disposition == 'mapped') != (self.component_id is not None):
            raise ValueError('PROFILE_ROUTE_COMPONENT_DISPOSITION_MISMATCH')
        return self


class RejectedProfile(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    revision: RevisionRef
    missing_feature_ids: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=4000)


class ProfileExtensionDelta(BaseModel):
    """Additive proposal pinned to an exact base Profile revision."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-extension-delta@1']
    base_profile_revision: RevisionRef
    additive_components: tuple[ObjectTypeDeclaration | PredicateDeclaration, ...] = Field(min_length=1)


class ProfileRoutingObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-routing-observation@1']
    branch: Literal['reuse', 'extend', 'new']
    domain: str = Field(min_length=1, max_length=256)
    selected_profile_revision: RevisionRef | None = None
    feature_dispositions: tuple[FeatureDisposition, ...] = Field(min_length=1)
    rejected_profiles: tuple[RejectedProfile, ...] = ()
    proposed_profile: KnowledgeProfileDeclaration | ProfileExtensionDelta | None = None
    confidence: Literal['high', 'medium', 'low']
    ambiguity_notes: tuple[str, ...] = ()


class ProfileCandidateDisposition(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    revision: RevisionRef
    disposition: Literal['selected', 'deferred_incompatible', 'deferred_insufficient_summary']
    reason: str = Field(min_length=1, max_length=2000)


class ProfileCandidateObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-candidate-observation@1']
    domain: str = Field(min_length=1, max_length=256)
    dispositions: tuple[ProfileCandidateDisposition, ...] = Field(min_length=1)


def available_profiles_from_package_admissions(*, profile_assets, package_catalog, domain):
    """Bind current visible Profiles to an exact server-returned package closure.

    Package admissions are availability policy, not semantic identity. This function
    replaces filename/namespace heuristics and never makes an unlisted Profile eligible.
    """
    packages=list(package_catalog)
    package_map={item.get('id'):item for item in packages if isinstance(item,dict)}
    if len(package_map)!=len(packages) or domain not in package_map:
        raise ValueError('PROFILE_ROUTE_PACKAGE_CATALOG_INVALID')
    closure=dependency_order(packages,[domain])
    admissions={}
    for package in closure:
        for item in package.get('profile_admissions') or ():
            key=(item['namespace'],item['profile_id'])
            value=admissions.setdefault(key,{'package_ids':[],'can_anchor_extension':False,'roles':[]})
            value['package_ids'].append(package['id']);value['roles'].append(item['role'])
            if package['id']==domain and item['role']=='root' and item['can_anchor_extension']:
                value['can_anchor_extension']=True
    assets={}
    for raw in profile_assets:
        if not isinstance(raw,dict):raise ValueError('PROFILE_ROUTE_PROFILE_ASSET_INVALID')
        declaration=KnowledgeProfileDeclaration.model_validate(raw.get('declaration'))
        key=(raw.get('namespace'),declaration.profile_id)
        if key in assets:raise ValueError('PROFILE_ROUTE_ADMITTED_PROFILE_AMBIGUOUS')
        assets[key]=(raw,declaration)
    available=[]
    for key,policy in admissions.items():
        found=assets.get(key)
        if found is None:continue
        raw,declaration=found
        available.append(AvailableProfile(revision=RevisionRef.model_validate(raw.get('revision')),
            declaration=declaration,allowed_domains=(domain,),
            package_ids=tuple(dict.fromkeys(policy['package_ids'])),
            can_anchor_extension=policy['can_anchor_extension']))
    if not available:raise ValueError('PROFILE_ROUTE_NO_VISIBLE_ADMITTED_PROFILE')
    receipt={'contract_version':'boi/profile-package-admission@1','domain':domain,
        'package_closure':[item['id'] for item in closure],
        'declared_admission_count':len(admissions),'visible_admitted_count':len(available),
        'unavailable_admissions':[{'namespace':key[0],'profile_id':key[1]}
            for key in admissions if key not in assets],
        'semantic_identity_decided':False,'release_authority_granted':False}
    receipt['admission_digest']=semantic_digest(receipt)
    return available,receipt


def available_profile_catalog_from_package_admissions(*, profile_assets, package_catalog):
    """Build the complete model-facing catalog from explicit package policy."""
    packages=list(package_catalog)
    combined={}; domain_receipts=[]
    for package in packages:
        domain=package.get('id') if isinstance(package,dict) else None
        if not isinstance(domain,str):raise ValueError('PROFILE_ROUTE_PACKAGE_CATALOG_INVALID')
        try:
            available,receipt=available_profiles_from_package_admissions(
                profile_assets=profile_assets,package_catalog=packages,domain=domain)
        except ValueError as exc:
            if str(exc)=='PROFILE_ROUTE_NO_VISIBLE_ADMITTED_PROFILE':continue
            raise
        domain_receipts.append(receipt)
        for item in available:
            key=(item.revision.ref,item.revision.revision_digest)
            current=combined.get(key)
            if current is None:
                combined[key]=item
                continue
            if current.declaration != item.declaration:
                raise ValueError('PROFILE_ROUTE_ADMITTED_PROFILE_REVISION_CONFLICT')
            combined[key]=current.model_copy(update={
                'allowed_domains':tuple(dict.fromkeys((*current.allowed_domains,*item.allowed_domains))),
                'package_ids':tuple(dict.fromkeys((*current.package_ids,*item.package_ids))),
                'can_anchor_extension':current.can_anchor_extension or item.can_anchor_extension})
    if not combined:raise ValueError('PROFILE_ROUTE_ADMITTED_CATALOG_EMPTY')
    receipt={'contract_version':'boi/profile-package-catalog@1',
        'profile_count':len(combined),'domains':[item['domain'] for item in domain_receipts],
        'domain_admission_digests':[item['admission_digest'] for item in domain_receipts],
        'semantic_identity_decided':False,'release_authority_granted':False}
    receipt['catalog_digest']=semantic_digest(receipt)
    return list(combined.values()),receipt


def _component_map(profile):
    return {component.id: component.model_dump(mode='json', exclude_none=True)
            for component in profile.components}


def workbook_source_features(records):
    """Build a neutral sheet/column inventory from preserved workbook fields.

    The first observed non-empty value is only a display label candidate. This
    function never calls it a header and never infers a domain or predicate.
    """
    if any('database_table' in (field.get('structural_metadata') or {})
           for row in records for field in row.get('fields') or ()):
        return database_profile_inventory(records)[0]
    columns = {}
    for record in records:
        for field in record.get('fields') or ():
            metadata = field.get('structural_metadata') or {}
            sheet, column = metadata.get('sheet'), metadata.get('excel_column')
            if not isinstance(sheet, str) or not isinstance(column, str):
                continue
            key = (sheet, column)
            entry = columns.setdefault(key, {'values': [], 'kinds': set(), 'refs': []})
            kind = {'string': 'text', 'number': 'decimal', 'integer': 'integer',
                    'boolean': 'boolean', 'empty': 'empty'}.get(field.get('value_kind'), 'unknown')
            entry['kinds'].add(kind)
            if field.get('span_ref'):
                entry['refs'].append(field['span_ref'])
            text = str(field.get('text') or '').strip()
            if text and len(entry['values']) < 3:
                entry['values'].append(text[:500])
    result = []
    for (sheet, column), entry in sorted(columns.items()):
        if not entry['refs']:
            continue
        samples = entry['values']
        result.append(SourceFeature(
            feature_id='workbook:%s:%s' % (sheet, column),
            label=(samples[0] if samples else '%s %s' % (sheet, column)),
            value_kinds=tuple(sorted(entry['kinds'])) or ('unknown',),
            evidence_refs=tuple(dict.fromkeys(entry['refs'])),
            required_for_reuse=True,
            source_path='workbook:%s:%s' % (sheet, column)))
    if not result:
        raise ValueError('PROFILE_ROUTE_WORKBOOK_FEATURES_EMPTY')
    return result


def workbook_profile_records(records):
    """Flatten preserved workbook rows by stable sheet/column paths.

    No row is called a header or data row here. Other sheets and partial rows remain
    present so the later Profile projection can reject an incomplete selected region
    instead of silently filling it or dropping a source value.
    """
    if any('database_table' in (field.get('structural_metadata') or {})
           for row in records for field in row.get('fields') or ()):
        return database_profile_inventory(records)[1]
    output=[]
    for record in records:
        values={}; evidence={}; unmapped=[]; record_refs=[]
        for field in record.get('fields') or ():
            metadata=field.get('structural_metadata') or {}
            sheet,column=metadata.get('sheet'),metadata.get('excel_column')
            span_ref=field.get('span_ref')
            if isinstance(span_ref,str):record_refs.append(span_ref)
            if not isinstance(sheet,str) or not isinstance(column,str) or not isinstance(span_ref,str):
                if isinstance(span_ref,str):
                    unmapped.append({'field_locator':field.get('field_locator'),
                        'value_kind':field.get('value_kind'),'text':field.get('text'),
                        'span_ref':span_ref})
                continue
            path='workbook:%s:%s' % (sheet,column)
            if path in values:
                raise ValueError('PROFILE_ROUTE_WORKBOOK_DUPLICATE_COLUMN_IN_RECORD')
            values[path]=field.get('text')
            evidence[path]=[span_ref]
        if values or unmapped:
            output.append({**values,'__source_record_locator__':record.get('record_locator'),
                '__evidence_refs__':evidence,'__record_evidence_refs__':record_refs,
                '__unmapped_fields__':unmapped})
    if not output:
        raise ValueError('PROFILE_ROUTE_WORKBOOK_RECORDS_EMPTY')
    return output


def database_profile_inventory(records):
    """DB field inventory for the same Profile workflow; no spreadsheet roles.

    Source adapters supply verified field spans. Labels remain navigation, not
    semantic identity. Snapshot ordinals retain duplicate physical occurrences.
    """
    columns = {}; output = []; seen = set(); snapshots = {}
    for row in records:
        locator = row.get('record_locator')
        if not isinstance(locator, str) or locator in seen:
            raise ValueError('PROFILE_DATABASE_RECORD_ID_INVALID')
        seen.add(locator); values = {}; evidence = {}; refs = []
        for field in row.get('fields') or ():
            meta = field.get('structural_metadata') or {}
            keys = ('database_source', 'database_table', 'database_column', 'database_value_path',
                    'database_snapshot')
            if any(not isinstance(meta.get(k), str) or not meta[k] for k in keys) \
                    or not isinstance(field.get('span_ref'), str) or not isinstance(field.get('text'), str):
                raise ValueError('PROFILE_DATABASE_FIELD_INVALID')
            source, table, column, value_path, snapshot = (meta[k] for k in keys)
            if source in snapshots and snapshots[source] != snapshot:
                raise ValueError('PROFILE_DATABASE_MIXED_SNAPSHOT')
            snapshots[source] = snapshot
            path = 'database:'+semantic_digest([source, table, value_path])
            if path in values:
                raise ValueError('PROFILE_DATABASE_DUPLICATE_FIELD')
            values[path] = field['text']; evidence[path] = [field['span_ref']]
            refs.append(field['span_ref'])
            kind = {'string': 'text', 'number': 'decimal', 'integer': 'integer',
                    'boolean': 'boolean', 'null': 'empty', 'empty': 'empty'}.get(field.get('value_kind'), 'unknown')
            entry = columns.setdefault(path, {'label': table+'.'+column,
                'kinds': set(), 'refs': []})
            entry['kinds'].add(kind); entry['refs'].append(field['span_ref'])
        if not values:
            raise ValueError('PROFILE_DATABASE_RECORD_EMPTY')
        output.append({**values, '__source_record_locator__': locator,
                       '__evidence_refs__': evidence, '__record_evidence_refs__': refs,
                       '__unmapped_fields__': []})
    if not output:
        raise ValueError('PROFILE_DATABASE_RECORDS_EMPTY')
    features = [SourceFeature(feature_id=key, source_path=key, label=v['label'],
        value_kinds=tuple(sorted(v['kinds'])), evidence_refs=tuple(dict.fromkeys(v['refs'])))
        for key, v in columns.items()]
    return features, output


def routing_prompt(*, features, available_profiles, source_scope, domain_guidance=None):
    """Build question-independent material for one structured routing call."""
    feature_values = [SourceFeature.model_validate(item) for item in features]
    profiles = [AvailableProfile.model_validate(item) for item in available_profiles]
    features = []
    for item in feature_values:
        value = item.model_dump(mode='json')
        value['evidence_ref_count'] = len(value['evidence_refs'])
        value['evidence_refs'] = value['evidence_refs'][:5]
        features.append(value)
    def profile_summary(item):
        declaration = item.declaration
        base = {'revision': item.revision.model_dump(mode='json'),
            'contract_version': declaration.contract_version,
            'allowed_domains': list(item.allowed_domains), 'package_ids': list(item.package_ids),
            'can_anchor_extension': item.can_anchor_extension}
        base.update(profile_id=declaration.profile_id, schema_ref=declaration.schema_ref,
            label=declaration.label, description=declaration.description,
            components=[{key:value for key,value in component.model_dump(mode='json', exclude_none=True).items()
                if key in ('kind','id','label','description','role','value_kind','cardinality','allowed_operators')}
                for component in declaration.components])
        return base
    packet = {
        'source_scope': source_scope,
        'source_features': features,
        'available_profiles': [profile_summary(item) for item in profiles],
        'output_schema': ProfileRoutingObservation.model_json_schema(),
        **({'domain_guidance': domain_guidance} if domain_guidance is not None else {})
    }
    return '''Choose a provisional ontology Profile route for the complete preserved source inventory below.
Return exactly one object matching boi/profile-routing-observation@1. Compare the actual semantic roles and source
scope with every available Profile. Use reuse only when the existing components cover every required source feature.
Use extend when a compatible Profile exists but needs additive components. For a boi/knowledge-profile@1 base,
return proposed_profile as boi/profile-extension-delta@1 with the exact selected base_profile_revision and only
complete, valid additive_components; never copy the base components. A predicate subject_type must reference the
exact existing or newly added object_type component_id.
For text/boolean/object predicates use quantity_semantics and value_semantics "not_applicable". For decimal
predicates use "unknown" unless the source itself establishes stronger quantity/value semantics. Include target_type,
quantity_revision and unit_revision as null when absent. subject_type is {"component_id":"exact-id"}.
Use new only after explicitly rejecting every available Profile with source-feature gaps. Map each source feature
exactly once as mapped, unresolved, evidence_context, or outside_scope, and quote only its supplied representative evidence refs. A filename, sheet
name, vendor, sample ID, or similar spelling alone cannot establish a domain or identity. Keep ambiguity unresolved.
For a new tabular record Profile, every mapped source field, including an identity field, must map to its own
predicate whose subject_type is the record object_type. The object_type classifies records; mapping a source field
to it does not make that field filterable, comparable, or answerable.
Use evidence_context for guide, correction, review-note, and provenance columns that must remain available to the
domain authoring and correction loop but do not define a reusable object or predicate. Use outside_scope only when a
feature is truly excluded from this route; its source bytes remain preserved and outside_scope requires review.
If every feature is mapped or evidence_context, choose reuse. Never add a Profile component for evidence_context.
Use exactly these top-level keys: contract_version, branch, domain, selected_profile_revision, feature_dispositions,
rejected_profiles, proposed_profile, confidence, ambiguity_notes. Each feature disposition uses feature_id,
disposition, component_id when mapped, evidence_refs, and reason. Profile references always contain ref and
revision_digest. ambiguity_notes contains only specific unresolved uncertainties, never a decision rationale; use an
empty array when confidence is high and every feature is mapped or evidence_context. Do not echo source_scope and do
not rename these keys.
Only a Profile with can_anchor_extension=true may be the selected basis of extend. A common reference Profile with
can_anchor_extension=false may still be a dependency of later authoring, but it cannot become the root of a new
domain record merely because one source field is a quantity, unit, or concept.
The result is a candidate route and grants no publication, approval, Release, or canonical authority.\n\nMATERIAL:\n''' + __import__('json').dumps(packet, ensure_ascii=False)


def profile_candidate_prompt(*, features, available_profiles, source_scope, domain_guidance=None,
                             maximum_selected=8):
    """Build a compact, complete-catalog first pass before loading full Profiles."""
    feature_values = [SourceFeature.model_validate(item) for item in features]
    profiles = [AvailableProfile.model_validate(item) for item in available_profiles]
    index = []
    for item in profiles:
        declaration = item.declaration
        summary = {'profile_id': declaration.profile_id, 'label': declaration.label,
            'description': declaration.description,
            'components': [{'id': component.id, 'kind': component.kind,
                'label': component.label, 'description': component.description[:300]}
                for component in declaration.components]}
        index.append({'revision': item.revision.model_dump(mode='json'),
            'allowed_domains':list(item.allowed_domains),'package_ids':list(item.package_ids),
            'can_anchor_extension':item.can_anchor_extension,**summary})
    guidance = None
    if domain_guidance:
        guidance = {key: domain_guidance[key] for key in (
            'package_id', 'manifest_digest', 'description', 'content_contracts',
            'semantic_responsibilities', 'dependencies') if key in domain_guidance}
    packet = {'source_scope': source_scope,
        'source_features': [{'feature_id': item.feature_id, 'label': item.label,
            'value_kinds': list(item.value_kinds)} for item in feature_values],
        'profile_catalog': index, 'domain_guidance': guidance,
        'maximum_selected': maximum_selected,
        'output_schema':ProfileCandidateObservation.model_json_schema()}
    return '''Select the smallest Profile candidate set that could cover this complete source-feature inventory.
Return exactly one boi/profile-candidate-observation@1 JSON object with only contract_version, domain, dispositions.
Each disposition has only revision, disposition, reason; revision has exactly ref and revision_digest. Include every
catalog revision exactly once. Infer domain from the source feature roles and server-owned allowed_domains/package_ids
when no domain_guidance is supplied; do not infer semantic identity from admission metadata alone.
Mark at most the stated maximum as selected. Defer as incompatible only when the compact declaration establishes a
semantic mismatch. Use deferred_insufficient_summary when full Profile content is needed to decide. Names alone do
not prove identity. This pass only limits material for full comparison; it grants no semantic or publication authority.
MATERIAL:\n''' + __import__('json').dumps(packet, ensure_ascii=False)


def adjudicate_profile_candidates(*, available_profiles, observation, maximum_selected=8):
    profiles = tuple(AvailableProfile.model_validate(item) for item in available_profiles)
    observed = ProfileCandidateObservation.model_validate(observation)
    profile_map = {item.revision.ref: item for item in profiles}
    dispositions = {item.revision.ref: item for item in observed.dispositions}
    if len(profile_map) != len(profiles) or len(dispositions) != len(observed.dispositions):
        raise ValueError('PROFILE_CANDIDATE_DUPLICATE_REVISION')
    if set(dispositions) != set(profile_map):
        raise ValueError('PROFILE_CANDIDATE_CATALOG_COVERAGE_INCOMPLETE')
    for ref, item in dispositions.items():
        if item.revision != profile_map[ref].revision:
            raise ValueError('PROFILE_CANDIDATE_REVISION_MISMATCH')
    selected = [profile_map[ref] for ref,item in dispositions.items()
                if item.disposition in {'selected', 'deferred_insufficient_summary'}]
    if not selected or len(selected) > maximum_selected:
        raise ValueError('PROFILE_CANDIDATE_SELECTION_SIZE_INVALID')
    return selected, {
        'contract_version': 'boi/profile-candidate-selection@1',
        'catalog_count': len(profiles), 'selected_count': len(selected),
        'direct_selected_count': sum(item.disposition == 'selected'
                                     for item in dispositions.values()),
        'insufficient_summary_count': sum(item.disposition == 'deferred_insufficient_summary'
                                          for item in dispositions.values()),
        'selected_revisions': [item.revision.model_dump(mode='json') for item in selected],
        'full_catalog_compared': True, 'full_profile_content_compared': False,
        'new_profile_auto_eligible': False,
    }


def domain_admitted_profile_candidates(*, available_profiles, domain, maximum_selected=12):
    """Conservative fallback when a model fails the complete-catalog contract.

    ``allowed_domains`` is server-owned admission metadata. It can safely rule
    out a Profile that is unavailable to this domain, but it cannot establish
    semantic identity. Every admitted Profile therefore remains
    ``deferred_insufficient_summary`` and must undergo the full comparison.
    """
    profiles = tuple(AvailableProfile.model_validate(item) for item in available_profiles)
    admitted = [item for item in profiles if domain in item.allowed_domains]
    if not admitted or len(admitted) > maximum_selected:
        raise ValueError('PROFILE_CANDIDATE_DOMAIN_ADMISSION_SIZE_INVALID')
    observation = ProfileCandidateObservation(
        contract_version='boi/profile-candidate-observation@1',
        domain=domain,
        dispositions=tuple(
            ProfileCandidateDisposition(
                revision=item.revision,
                disposition=('deferred_insufficient_summary' if item in admitted
                             else 'deferred_incompatible'),
                reason=('Server-owned domain admission permits full semantic comparison; '
                        'admission does not establish identity.' if item in admitted else
                        'Server-owned allowed_domains excludes this Profile from the requested domain.'))
            for item in profiles))
    selected, receipt = adjudicate_profile_candidates(
        available_profiles=profiles, observation=observation, maximum_selected=maximum_selected)
    return observation, selected, receipt | {
        'selection_method': 'server_domain_admission_fallback',
        'semantic_identity_decided': False,
    }


def normalize_redundant_profile_extension(*, raw_observation, available_profiles):
    """Discard a claimed extension that contains exactly the selected base IDs.

    This normalization never accepts or repairs the model's component semantics.
    It replaces the whole invalid/redundant proposal with the pinned current
    Profile, and only when every mapped feature already targets that Profile.
    """
    raw = deepcopy(raw_observation)
    if not isinstance(raw, dict) or raw.get('branch') not in {'extend', 'reuse'}:
        return raw, None
    try:
        profiles = tuple(AvailableProfile.model_validate(item) for item in available_profiles)
    except Exception:
        return raw, None
    selected_value = raw.get('selected_profile_revision')
    if not isinstance(selected_value, dict):
        return raw, None
    selected = next((item for item in profiles
                     if item.revision.model_dump(mode='json') == selected_value), None)
    if selected is None:
        return raw, None
    dispositions = raw.get('feature_dispositions')
    if not isinstance(dispositions, list) or not dispositions:
        return raw, None
    allowed = {'mapped', 'evidence_context', 'outside_scope'}
    if any(not isinstance(item, dict) or item.get('disposition') not in allowed
           for item in dispositions):
        return raw, None
    base_ids = set(_component_map(selected.declaration))
    mapped_ids = {item.get('component_id') for item in dispositions
                  if item.get('disposition') == 'mapped'}
    if None in mapped_ids or not mapped_ids <= base_ids:
        return raw, None
    proposal = raw.get('proposed_profile')
    if not isinstance(proposal, dict):
        return raw, None
    raw_components = proposal.get('components')
    raw_entries = proposal.get('entries')
    if isinstance(raw_components, list):
        proposal_ids = [item.get('id') for item in raw_components if isinstance(item, dict)]
    elif isinstance(raw_entries, list):
        proposal_ids = [item.get('entry_id') for item in raw_entries if isinstance(item, dict)]
    else:
        return raw, None
    if (len(proposal_ids) != len(set(proposal_ids)) or None in proposal_ids
            or set(proposal_ids) != base_ids):
        return raw, None
    raw['branch'] = 'reuse'
    raw['proposed_profile'] = None
    return raw, {
        'code': ('redundant_extension_removed' if raw_observation.get('branch') == 'extend'
                 else 'redundant_reuse_profile_copy_removed'),
        'selected_profile_revision': selected.revision.model_dump(mode='json'),
        'discarded_component_ids': sorted(proposal_ids),
        'semantic_changes_accepted': False,
    }


def normalize_profile_extension_delta(raw_observation):
    """Normalize only structural omissions and conservative unknown semantics."""
    raw = deepcopy(raw_observation)
    if not isinstance(raw, dict) or raw.get('branch') != 'extend':
        return raw, None
    proposal = raw.get('proposed_profile')
    if not isinstance(proposal, dict) or 'base_profile_revision' not in proposal \
            or not isinstance(proposal.get('additive_components'), list):
        return raw, None
    changes=[]
    if proposal.get('contract_version') != 'boi/profile-extension-delta@1':
        proposal['contract_version']='boi/profile-extension-delta@1';changes.append('contract_version')
    for index,component in enumerate(proposal['additive_components']):
        if not isinstance(component,dict) or component.get('kind')!='predicate':
            continue
        subject=component.get('subject_type')
        if isinstance(subject,str):
            component['subject_type']={'component_id':subject};changes.append(f'{index}.subject_type')
        for key in ('target_type','quantity_revision','unit_revision'):
            if key not in component:
                component[key]=None;changes.append(f'{index}.{key}')
        if component.get('value_kind')=='decimal':
            if component.get('quantity_semantics') not in {'dimensionless','declared','unknown'}:
                component['quantity_semantics']='unknown';changes.append(f'{index}.quantity_semantics')
            if component.get('value_semantics') not in {'absolute','interval','unknown'}:
                component['value_semantics']='unknown';changes.append(f'{index}.value_semantics')
        else:
            for key in ('quantity_semantics','value_semantics'):
                if component.get(key)!='not_applicable':
                    component[key]='not_applicable';changes.append(f'{index}.{key}')
    return raw, ({'code':'extension_delta_structural_normalization',
                  'changes':changes,'semantic_claims_added':False} if changes else None)


def normalize_empty_profile_extension(*, raw_observation, available_profiles):
    """Collapse an empty extension only when every mapping already exists in its exact base."""
    raw=deepcopy(raw_observation)
    proposal=raw.get('proposed_profile') if isinstance(raw,dict) else None
    if (raw.get('branch')!='extend' or not isinstance(proposal,dict)
            or proposal.get('contract_version')!='boi/profile-extension-delta@1'
            or proposal.get('additive_components')!=[]):
        return raw,None
    selected_value=raw.get('selected_profile_revision')
    selected=None
    for item in map(AvailableProfile.model_validate,available_profiles):
        if item.revision.model_dump(mode='json')==selected_value:selected=item;break
    if selected is None or proposal.get('base_profile_revision')!=selected_value:
        return raw,None
    base_ids=set(_component_map(selected.declaration))
    dispositions=raw.get('feature_dispositions') or ()
    if (not dispositions or any(not isinstance(item,dict) for item in dispositions)
            or any(item.get('disposition')=='mapped' and item.get('component_id') not in base_ids
                   for item in dispositions)):
        return raw,None
    raw['branch']='reuse';raw['proposed_profile']=None
    return raw,{'code':'empty_extension_collapsed_to_reuse',
        'selected_profile_revision':selected_value,'semantic_changes_accepted':False}


def normalize_new_profile_structure(raw_observation):
    """Fill contract structure and conservative semantics for a new candidate."""
    raw=deepcopy(raw_observation)
    if not isinstance(raw,dict) or raw.get('branch')!='new':return raw,None
    proposal=raw.get('proposed_profile')
    if not isinstance(proposal,dict) or not isinstance(proposal.get('components'),list):
        return raw,None
    changes=[]
    if proposal.get('contract_version')!='boi/knowledge-profile@1':
        proposal['contract_version']='boi/knowledge-profile@1';changes.append('contract_version')
    for index,component in enumerate(proposal['components']):
        if not isinstance(component,dict):continue
        if component.get('kind')=='object_type':
            if 'metadata_constraints' not in component:
                component['metadata_constraints']=[];changes.append(f'{index}.metadata_constraints')
            continue
        if component.get('kind')!='predicate':continue
        subject=component.get('subject_type')
        if isinstance(subject,str):
            component['subject_type']={'component_id':subject};changes.append(f'{index}.subject_type')
        for key in ('target_type','quantity_revision','unit_revision'):
            if key not in component:
                component[key]=None;changes.append(f'{index}.{key}')
        if component.get('value_kind')=='decimal':
            if component.get('quantity_semantics') not in {'dimensionless','declared','unknown'}:
                component['quantity_semantics']='unknown';changes.append(f'{index}.quantity_semantics')
            if component.get('value_semantics') not in {'absolute','interval','unknown'}:
                component['value_semantics']='unknown';changes.append(f'{index}.value_semantics')
        else:
            for key in ('quantity_semantics','value_semantics'):
                if component.get(key)!='not_applicable':
                    component[key]='not_applicable';changes.append(f'{index}.{key}')
    return raw, ({'code':'new_profile_structural_normalization','changes':changes,
                  'semantic_claims_added':False} if changes else None)


def _materialize_profile_extension(selected, proposal):
    if not isinstance(proposal, ProfileExtensionDelta):
        return proposal, None
    if proposal.base_profile_revision != selected.revision:
        raise ValueError('PROFILE_ROUTE_EXTENSION_BASE_REVISION_MISMATCH')
    base = selected.declaration
    base_ids = {item.id for item in base.components}
    additions = proposal.additive_components
    addition_ids = {item.id for item in additions}
    if len(addition_ids) != len(additions) or base_ids & addition_ids:
        raise ValueError('PROFILE_ROUTE_EXTENSION_COMPONENT_ID_CONFLICT')
    object_ids = {item.id for item in (*base.components, *additions)
                  if isinstance(item, ObjectTypeDeclaration)}
    for item in additions:
        if not isinstance(item, PredicateDeclaration):
            continue
        for link in (item.subject_type, item.target_type):
            if link is not None and hasattr(link, 'component_id') and link.component_id not in object_ids:
                raise ValueError('PROFILE_ROUTE_EXTENSION_LOCAL_TYPE_UNAVAILABLE')
    delta_digest = semantic_digest(proposal).removeprefix('sha256:')[:16]
    materialized = KnowledgeProfileDeclaration(
        profile_id=base.profile_id + '-extension-' + delta_digest,
        schema_ref=base.schema_ref + '-extension-candidate-' + delta_digest,
        label=base.label + ' 확장 후보',
        description=('Exact base Profile plus a source-grounded additive candidate; semantic review and '
                     'publication are still required.'),
        level_scheme=base.level_scheme,
        components=(*base.components, *additions))
    return materialized, proposal.model_dump(mode='json')


def validate_or_repair_routing_observation(*, first_value, repair, max_repairs=1):
    """Validate the top-level object and allow one bounded schema repair call."""
    value = first_value
    errors = []
    for attempt in range(max_repairs + 1):
        try:
            return ProfileRoutingObservation.model_validate(value), errors
        except Exception as exc:
            errors.append({'attempt': attempt + 1, 'error': type(exc).__name__ + ':' + str(exc)[:4000]})
            if attempt >= max_repairs:
                raise ValueError('PROFILE_ROUTE_OBSERVATION_INVALID') from exc
            value = repair(value, errors[-1]['error'])


def adjudicate_profile_route(*, features, available_profiles, observation):
    """Return a deterministic route receipt or raise on an unsafe observation."""
    features = tuple(SourceFeature.model_validate(item) for item in features)
    profiles = tuple(AvailableProfile.model_validate(item) for item in available_profiles)
    proposed = ProfileRoutingObservation.model_validate(observation)
    feature_map = {item.feature_id: item for item in features}
    if len(feature_map) != len(features):
        raise ValueError('PROFILE_ROUTE_DUPLICATE_SOURCE_FEATURE')
    dispositions = {item.feature_id: item for item in proposed.feature_dispositions}
    if len(dispositions) != len(proposed.feature_dispositions) or set(dispositions) != set(feature_map):
        raise ValueError('PROFILE_ROUTE_SOURCE_COVERAGE_INCOMPLETE')
    for feature_id, item in dispositions.items():
        if not set(item.evidence_refs) <= set(feature_map[feature_id].evidence_refs):
            raise ValueError('PROFILE_ROUTE_EVIDENCE_OUTSIDE_SOURCE_FEATURE')
    profile_map = {item.revision.ref: item for item in profiles}
    if len(profile_map) != len(profiles):
        raise ValueError('PROFILE_ROUTE_DUPLICATE_AVAILABLE_PROFILE')
    rejected = {item.revision.ref: item for item in proposed.rejected_profiles}
    if len(rejected) != len(proposed.rejected_profiles) or not set(rejected) <= set(profile_map):
        raise ValueError('PROFILE_ROUTE_REJECTED_PROFILE_UNAVAILABLE')
    selected = None
    if proposed.selected_profile_revision is not None:
        selected = profile_map.get(proposed.selected_profile_revision.ref)
        if selected is None or selected.revision != proposed.selected_profile_revision:
            raise ValueError('PROFILE_ROUTE_SELECTED_PROFILE_UNAVAILABLE')
        if proposed.domain not in selected.allowed_domains:
            raise ValueError('PROFILE_ROUTE_DOMAIN_NOT_ALLOWED')
    mapped = [item for item in dispositions.values() if item.disposition == 'mapped']
    unresolved = [item for item in dispositions.values() if item.disposition == 'unresolved']
    evidence_context = [item for item in dispositions.values() if item.disposition == 'evidence_context']
    outside = [item for item in dispositions.values() if item.disposition == 'outside_scope']
    if proposed.branch == 'reuse':
        if selected is None or proposed.proposed_profile is not None:
            raise ValueError('PROFILE_ROUTE_REUSE_PROFILE_REQUIRED')
        if unresolved:
            raise ValueError('PROFILE_ROUTE_REUSE_REQUIRED_FEATURE_UNCOVERED')
        components = _component_map(selected.declaration)
        if any(item.component_id not in components for item in mapped):
            raise ValueError('PROFILE_ROUTE_COMPONENT_UNAVAILABLE')
        if set(rejected) & {selected.revision.ref}:
            raise ValueError('PROFILE_ROUTE_SELECTED_PROFILE_REJECTED')
    elif proposed.branch == 'extend':
        if selected is None or proposed.proposed_profile is None:
            raise ValueError('PROFILE_ROUTE_EXTENSION_BASIS_REQUIRED')
        if not selected.can_anchor_extension:
            raise ValueError('PROFILE_ROUTE_EXTENSION_ANCHOR_NOT_ALLOWED')
        materialized, extension_delta = _materialize_profile_extension(selected, proposed.proposed_profile)
        base = _component_map(selected.declaration)
        extension = _component_map(materialized)
        if any(item.component_id not in extension for item in mapped):
            raise ValueError('PROFILE_ROUTE_COMPONENT_UNAVAILABLE')
        if any(extension.get(key) != value for key, value in base.items()):
            raise ValueError('PROFILE_ROUTE_EXTENSION_MUTATES_BASE_COMPONENT')
        added = sorted(set(extension) - set(base))
        if not added:
            raise ValueError('PROFILE_ROUTE_EXTENSION_ADDS_NOTHING')
        if not unresolved and not any(item.component_id in added for item in mapped):
            raise ValueError('PROFILE_ROUTE_EXTENSION_WITHOUT_SOURCE_GAP')
    else:
        if (selected is not None or proposed.proposed_profile is None
                or isinstance(proposed.proposed_profile, ProfileExtensionDelta)):
            raise ValueError('PROFILE_ROUTE_NEW_PROFILE_BOUNDARY')
        if profiles and set(rejected) != set(profile_map):
            raise ValueError('PROFILE_ROUTE_NEW_REQUIRES_ALL_PROFILE_COMPARISONS')
        proposed_components = _component_map(proposed.proposed_profile)
        if any(item.component_id not in proposed_components for item in mapped):
            raise ValueError('PROFILE_ROUTE_COMPONENT_UNAVAILABLE')
        object_component_ids = {
            component.id for component in proposed.proposed_profile.components
            if isinstance(component, ObjectTypeDeclaration)
        }
        object_mappings = [item for item in mapped if item.component_id in object_component_ids]
        if object_mappings:
            raise ValueError('PROFILE_ROUTE_NEW_FIELDS_REQUIRE_PREDICATES')
        if not mapped:
            raise ValueError('PROFILE_ROUTE_NEW_WITHOUT_MAPPED_FEATURES')
        if not unresolved and not mapped:
            raise ValueError('PROFILE_ROUTE_NEW_REQUIRES_SOURCE_GAP')
    needs_review = (proposed.branch != 'reuse' or proposed.confidence != 'high' or bool(proposed.ambiguity_notes)
                    or bool(unresolved) or bool(outside))
    route = {
        'contract_version': 'boi/profile-intake-route@1',
        'branch': proposed.branch,
        'domain': proposed.domain,
        'status': 'requires_semantic_review' if needs_review else 'ready_for_domain_authoring',
        'selected_profile_revision': (proposed.selected_profile_revision.model_dump(mode='json')
                                      if proposed.selected_profile_revision else None),
        'proposed_profile': ((materialized if proposed.branch == 'extend' else proposed.proposed_profile)
            .model_dump(mode='json', exclude_none=True) if proposed.proposed_profile else None),
        'extension_delta': (extension_delta if proposed.branch == 'extend' else None),
        'coverage': {
            'total': len(features), 'mapped': len(mapped), 'unresolved': len(unresolved),
            'evidence_context': len(evidence_context), 'outside_scope': len(outside),
            'complete': len(dispositions) == len(features)
        },
        'feature_dispositions': [item.model_dump(mode='json') for item in proposed.feature_dispositions],
        'rejected_profiles': [item.model_dump(mode='json') for item in proposed.rejected_profiles],
        'release_authority_granted': False,
        'canonical_projection_eligible': False,
        'semantic_truth_proven': False
    }
    route['route_digest'] = semantic_digest(route)
    return route


def routing_output_schema():
    """Schema for a bounded structured model observation."""
    return ProfileRoutingObservation.model_json_schema()
