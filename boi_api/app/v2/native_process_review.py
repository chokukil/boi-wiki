"""Scoped process review through native observations and existing process checks.

No model dispatch or storage occurs here. Root pointers are internal native
caller selections or a source-correction scope, never required SME input.
"""
import copy
import json

from .native_formula_timing import stage_timing
from ..governed_runtime.domain_asset_store import DomainAssetStore,source_manifest_digest
from ..governed_runtime.native_definition_context import (NativeDefinitionReview,NativeDefinitionReviewV2,
    NativeDefinitionReviewV3,NativeProcessReviewScope,NativeMultiSourceReviewScope,scoped_native_review_model)
from ..governed_runtime.native_observation import NativeObservationInput,read_native_observation,_json
from ..governed_runtime.semantic_binding_contract import RevisionRef,semantic_digest
from ..governed_runtime.source_envelope import ArtifactEnvelope
from ..governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
from .process_review_binding import RequestSourceReader
from agent_kit.python.boi_process_answer_v2 import meaning_citation_targets
from agent_kit.python.boi_process_claim_review import (assessment_targets,source_review_material,
    source_review_delivery,source_review_prompt,source_review_selection)
from agent_kit.python.boi_process_response_review import response_context_view
from agent_kit.python.boi_process_review_observation import observe_source_review


# These are nested timings, not additive work or cached authority decisions.
meaning_citation_targets = stage_timing('review_meaning_graph')(meaning_citation_targets)
response_context_view = stage_timing('review_context_projection')(response_context_view)
source_review_delivery = stage_timing('review_delivery')(source_review_delivery)
source_review_prompt = stage_timing('review_prompt')(source_review_prompt)
observe_source_review = stage_timing('review_assessment')(observe_source_review)


_NATIVE_MEANING_CONTRACTS = frozenset((
    'boi/svid-native-interpretation@1',
    'boi/native-dexa-mapping-basis@1',
    'boi/native-dexa-definition@1',
))


@stage_timing('review_candidate_read')
def _candidate(work,authorization,revision):
    stored=DomainAssetStore(work.intake).read(authorization=authorization,
        revision=RevisionRef.model_validate(revision),lane='provisional')
    content=_json(stored['asset']['content_json'])
    contract = content.get('contract_version')
    if (stored['asset']['kind']!='definition' or stored['asset']['authority']!='candidate'
            or contract not in _NATIVE_MEANING_CONTRACTS | {
                'boi/bound-process-meaning@1','boi/bound-process-meaning@2'}):
        raise ValueError('NATIVE_PROCESS_REVIEW_CANDIDATE_REQUIRED')
    if contract in _NATIVE_MEANING_CONTRACTS:return stored,content,content
    draft=ProcessKnowledgeDraft.model_validate(content['draft']).model_dump(mode='json')
    return stored,content,draft


def _multi_source_review_fields(readings):
    """Address exact authorized fields without merging source identities or text.

    The full read context and source manifest are pinned by the observation.
    These pointers identify field objects in that context, so identical original
    locators in different sources never overwrite one another. Original native
    evidence, source envelopes, span references and text remain unchanged.
    """
    fields=[];catalog=[]
    for source_index,reading in enumerate(readings):
        seen=set()
        for field_index,field in enumerate(reading['fields']):
            original=field['field_locator']
            if original in seen:raise ValueError('NATIVE_REVIEW_SOURCE_FIELD_AMBIGUOUS')
            seen.add(original)
            address=f'/read_definitions_and_contracts/source_readings/{source_index}/fields/{field_index}'
            fields.append({**copy.deepcopy(field),'field_locator':address})
            catalog.append({'field_locator':address,'original_field_locator':original,
                'source':copy.deepcopy(reading['source']), 'span_ref':field['span_ref']})
    return {'fields':fields},catalog


def _prepare_native_meaning_review(intake,principal,work,authorization,candidate,content,*,
        knowledge_reading_ref,target_pointers,field_locators,prior_review_revision,require_current,trail=(),
        exact_metadata_successors=False):
    """Reuse native meaning closures and the existing node judgment protocol.

    The native content stays native; original cell/annotation readings occur
    once. Unbound and unselected nodes never gain authority from disposition.
    """
    from agent_kit.python.boi_process_claim_review import SOURCE_REVIEW_INSTRUCTIONS_VERSION,SOURCE_LABEL_FAILURE_KINDS
    sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
    if not sources:raise ValueError('NATIVE_MEANING_REVIEW_SOURCE_REQUIRED')
    multi_source=len(sources)>1
    context=work.contexts.validate_reading(authorization=authorization,
        revision=RevisionRef.model_validate(knowledge_reading_ref),sources=sources,require_current=require_current,
        _exact_metadata_successors=exact_metadata_successors)
    if candidate['revision'] not in [a.revision.model_dump(mode='json') for a in context.assets]:
        raise ValueError('NATIVE_PROCESS_CANDIDATE_NOT_READ')
    readings=RequestSourceReader(intake,principal).read_for_assets(intake,principal,sources,[candidate['revision']])
    evidence,catalog=_multi_source_review_fields(readings) if multi_source else (readings[0],None)
    graphs=meaning_citation_targets(context=context,sources=readings,asset_revision=candidate['revision'])
    by_pointer={t['target_pointer']:t for t in graphs}
    prior=None;prior_ref=None;prior_binding=None;carry=[];refs=[candidate['revision']]
    if prior_review_revision is not None:
        prior_ref=RevisionRef.model_validate(prior_review_revision).model_dump(mode='json')
        old,_,prior,usable,prior_binding=_prior(intake,principal,work,authorization,prior_ref,candidate,trail=trail)
        for ref in (prior_ref,old['revision']):
            if ref not in refs:refs.append(ref)
        if prior_binding is not None:
            # Compare the same source-resolved node values and qualifier closure
            # as answers. A revision opinion cannot qualify a changed condition,
            # a newly added node or a pending/unsupported old judgment.
            candidates=[p for p in by_pointer if p in usable and by_pointer[p]['binding_status']=='bound']
            carry=_same_reviewed_closures(candidates,old=old,prior_binding=prior_binding,
                candidate=candidate,context=context,readings=readings)
    if any(ref not in [a.revision.model_dump(mode='json') for a in context.assets] for ref in refs):
        raise ValueError('NATIVE_PROCESS_REVIEW_INPUT_NOT_READ')
    roots=list(target_pointers) if target_pointers is not None else [p for p,t in by_pointer.items() if t['binding_status']=='bound']
    if not roots or len(roots)!=len(set(roots)) or not set(roots)<=set(by_pointer):
        raise ValueError('NATIVE_MEANING_REVIEW_ROOTS_INVALID')
    targets=[];closures={};selected=set()
    for pointer,target in by_pointer.items():
        value=content
        for part in pointer.lstrip('/').split('/'):
            part=part.replace('~1','/').replace('~0','~')
            value=value[int(part)] if isinstance(value,list) else value[part]
        targets.append({'target_pointer':pointer,'kind':'native_meaning','value':copy.deepcopy(value)})
        closures[pointer]=[node['target_pointer'] for node in target['graph_evidence']]
        if pointer in roots:
            if target['binding_status']!='bound':raise ValueError('NATIVE_PROCESS_REVIEW_CLOSURE_UNRESOLVED')
            selected.update(closures[pointer])
    if not selected<=set(by_pointer):raise ValueError('NATIVE_PROCESS_REVIEW_CLOSURE_TARGET_UNSUPPORTED')
    carry=[p for p in carry if p in selected]
    fields=list(field_locators)
    if len(fields)!=len(set(fields)) or not set(fields)<={f['field_locator'] for f in evidence['fields']}:
        raise ValueError('NATIVE_PROCESS_REVIEW_FIELD_SCOPE_INVALID')
    selection={'targets':[t for t in targets if t['target_pointer'] in selected-set(carry)],
        'fields':fields,'carry_forward_nodes':carry,'carry_forward_fields':[]}
    scope_model=NativeMultiSourceReviewScope if multi_source else NativeProcessReviewScope
    scope=scope_model(candidate_draft_digest=semantic_digest(content),
        source_revision_digest=sources[0].digest,root_pointers=roots,
        target_pointers=[t['target_pointer'] for t in selection['targets']],field_locators=fields,
        prior_review_revision=prior_ref,
        **({'source_revision_digests':[s.digest for s in sources]} if multi_source else {})).model_dump(mode='json')
    view=response_context_view(context.model_dump(mode='json'),source_readings=readings)
    for asset in view['assets']:
        if asset['revision']==candidate['revision']:
            asset['read_projection']={'draft_reference':'/draft','draft_digest':semantic_digest(content)}
        elif prior_binding is not None and asset['revision']==old['revision']:
            asset['read_projection']={'preserved_revision_reference':asset['revision'],
                'scope':'Historical candidate used by deterministic closure comparison; not evidence for new judgments.'}
        elif asset['kind'] not in ('definition','profile','skill','harness'):
            asset['read_projection']={'preserved_revision_reference':asset['revision'],
                'history_preserved_in_exact_wiki_revision':True,
                'scope':'Original source fields are supplied once in source_readings; stored history is not source evidence.'}
        asset['projection_digest']=semantic_digest(asset['read_projection'])
    material={'review_instructions_version':SOURCE_REVIEW_INSTRUCTIONS_VERSION,
        'review_output_contract':{'allowed_failure_kinds':SOURCE_LABEL_FAILURE_KINDS},
        'draft':copy.deepcopy(content),'targets':copy.deepcopy(selection['targets']),
        'all_current_nodes_for_field_coverage':copy.deepcopy(targets) if fields else [],
        'carried_node_judgments':[copy.deepcopy(c) for c in (prior or {}).get('claims',[]) if c['target_pointer'] in carry],
        'field_locators_to_assess':fields,
        'review_scope':'selected_nodes','native_review_scope':scope,
        'native_meaning_dependencies':closures,
        'unresolved_meaning_targets':[{'target_pointer':p,'reason_code':t.get('reason_code')}
            for p,t in by_pointer.items() if t['binding_status']!='bound'],
        'read_definitions_and_contracts':view,
        'original_fields_reference':'/read_definitions_and_contracts/source_readings/0/fields',
        'primary_source_revision':sources[0].digest,
        'scope':'Source fidelity of selected native meanings only. The native definition is not a process draft. '
            'Original record fields, required headers and reported corrections are retained in source_readings. '
            'Read coverage is declared by that manifest, not the full workbook. Unselected nodes remain unreviewed. '
            'No scientific correctness or live observation is established.'}
    if multi_source:
        material.update(source_review_field_catalog=catalog,
            original_fields_reference='/source_review_field_catalog',
            source_field_addressing=('For source_assessment quote evidence and field coverage, use the exact '
                'field_locator from source_review_field_catalog. It is a JSON pointer to one original field '
                'in read_definitions_and_contracts. Read that field text at that pointer. Preserve the '
                'catalog source envelope and original_field_locator; unqualified original locators are '
                'not review addresses. The primary source is ordering metadata, not sole evidence authority.'))
    if carry:
        material['carried_review_limits']={'review_revision':prior_ref,
            'findings':prior_binding['review']['findings'],'limitations':prior_binding['review']['limitations'],
            'source_assessment_limitations':prior_binding['validated_assessment']['limitations']}
    material=source_review_delivery(material)
    prompt_material=material
    if prior_ref is not None:
        # Prior judgments are retained for binding, not supplied as a preferred
        # answer to the reviewer assessing changed or newly selected meanings.
        prompt_material=copy.deepcopy(material)
        prompt_material.pop('carried_node_judgments',None)
        prompt_material.pop('carried_review_limits',None)
    review_model=NativeDefinitionReviewV3 if multi_source else NativeDefinitionReviewV2
    version=3 if multi_source else 2
    prompt=source_review_prompt(prompt_material)+f'\nReturn NativeDefinitionReview@{version} with the exact envelope below. '
    prompt+='Assess only the selected target and field scope. Whole-candidate disposition does not approve other nodes.\n'
    prompt+=json.dumps({'definition_revisions':[candidate['revision']],'scope':scope},ensure_ascii=False,separators=(',',':'))
    request=NativeObservationInput(prompt=prompt,output_schema_json=json.dumps(review_model.model_json_schema(),ensure_ascii=False),
        source_manifest_digest=source_manifest_digest(sources),input_revisions=refs,
        knowledge_reading_ref=knowledge_reading_ref,review_contract_version=f'boi/native-definition-review@{version}')
    return {'definition_revision':candidate['revision'],'scope':scope,'material':material,
        'request':request.model_dump(mode='json'),'selection':selection,'carried_assessment':prior,
        'sources':readings,'context':context.model_dump(mode='json'),'native_targets':targets,'native_closures':closures,
        'carried_review_limits':material.get('carried_review_limits'),
        'carried_observation_provenance':prior_binding['native_observation_provenance'] if carry else [],
        '_prior_review_reuse_dependencies':([] if prior_ref is None else
            prior_binding.get('review_reuse_dependencies') if prior_binding is not None else None)}


def _prior(intake,principal,work,authorization,revision,candidate,*,trail):
    observation=read_native_observation(work,authorization,revision)
    value=observation['value'];binding=None
    if value.get('contract_version') in ('boi/native-definition-review@2','boi/native-definition-review@3'):
        binding=read_native_process_review_binding(intake,principal,revision,require_current=False,_trail=trail)
        prior_revision=binding['candidate_revision']
        prior=binding['validated_assessment']
        usable=set(binding['source_review']['usable_node_pointers'])
    else:
        legacy=NativeDefinitionReview.model_validate(value)
        if (observation['request']['review_contract_version']!=legacy.contract_version
                or semantic_digest(_json(observation['request']['output_schema_json']))!=semantic_digest(NativeDefinitionReview.model_json_schema())
                or observation['request']['input_revisions']!=[r.model_dump(mode='json') for r in legacy.definition_revisions]):
            raise ValueError('NATIVE_PROCESS_PRIOR_REVIEW_CONTRACT_MISMATCH')
        matches=[r.model_dump(mode='json') for r in legacy.definition_revisions
            if r.model_dump(mode='json') in (candidate['revision'],candidate.get('previous_revision'))]
        if len(matches)!=1:raise ValueError('NATIVE_PROCESS_PRIOR_CANDIDATE_MISMATCH')
        prior_revision=matches[0];prior=None;usable=set()
    if prior_revision not in (candidate['revision'],candidate.get('previous_revision')):
        raise ValueError('NATIVE_PROCESS_PRIOR_CANDIDATE_MISMATCH')
    old,_,draft=_candidate(work,authorization,prior_revision)
    if old['sources']!=candidate['sources']:
        raise ValueError('NATIVE_PROCESS_CARRY_SOURCE_CHANGED')
    return old,draft,prior,usable,binding


def _same_reviewed_closures(pointers,*,old,prior_binding,candidate,context,readings):
    """Reuse exact semantic inputs across the explicit local candidate lineage.

    Local revision addresses may differ; node values, roles, qualifiers, source
    bindings and external definition identities must remain identical.
    """
    if not pointers:return []
    contract_assets=lambda ctx:[{k:a[k] for k in ('revision','content_digest','kind','authority')}
        for a in ctx['assets'] if a['kind'] in ('harness','profile','skill')]
    if contract_assets(prior_binding['context'])!=contract_assets(context.model_dump(mode='json')):return []
    old_graphs=meaning_citation_targets(context=prior_binding['context'],sources=prior_binding['sources'],
        asset_revision=old['revision'],target_pointers=pointers)
    new_graphs=meaning_citation_targets(context=context,sources=readings,
        asset_revision=candidate['revision'],target_pointers=pointers)
    def fingerprint(target,revision):
        if target['binding_status']!='bound':return None
        graph=copy.deepcopy(target['graph_evidence'])
        for node in graph:
            ref=node.get('asset_revision',revision)
            node['asset_revision']='lineage_local_candidate' if ref==revision else ref
        return semantic_digest(graph)
    return [a['target_pointer'] for a,b in zip(old_graphs,new_graphs)
        if fingerprint(a,old['revision']) is not None
        and fingerprint(a,old['revision'])==fingerprint(b,candidate['revision'])]


def _selected_node_material(material,*,draft,pointers,candidate,context,readings):
    """Exact node projection at original paths, not a ProcessKnowledgeDraft.

    Full sources and record context remain. Typed limits and negative claims
    are context, not additional selected review targets. No text is shortened.
    """
    context_roots=[];selected_ids={}
    for ri,record in enumerate(draft['records']):
        selected_ids[ri]={node['term_id' if group=='terms' else 'assertion_id']
            for group in ('terms','assertions') for i,node in enumerate(record[group])
            if f'/records/{ri}/{group}/{i}' in pointers}
    for ri,record in enumerate(draft['records']):
        context_roots.extend(f'/records/{ri}/terms/{ti}' for ti,term in enumerate(record['terms'])
            if term['term_id']==record['process_ref'])
        context_roots.extend(f'/records/{ri}/assertions/{ai}' for ai,claim in enumerate(record['assertions'])
            if selected_ids[ri].intersection((claim['subject_ref'],*claim['object_refs'],*claim['depends_on']))
            and (claim['category']=='applicability' or claim['polarity']=='negative'
                or any(claim[key] for key in ('conditions','exceptions','applicability'))))
    included=set(pointers)
    extra=[p for p in context_roots if p not in included]
    for target in meaning_citation_targets(context=context,sources=readings,
            asset_revision=candidate['revision'],target_pointers=extra) if extra else []:
        # If supplemental context cannot be fully resolved, keep the full
        # candidate presentation; never silently discard an ambiguous limit.
        if target['binding_status']!='bound':return material
        included.update(node['target_pointer'] for node in target['graph_evidence']
            if node.get('asset_revision',candidate['revision'])==candidate['revision'])
    projected={k:copy.deepcopy(v) for k,v in draft.items() if k not in ('contract_version','records')}
    projected['records']={}
    for ri,record in enumerate(draft['records']):
        item={k:copy.deepcopy(v) for k,v in record.items() if k not in ('terms','assertions')}
        for group in ('terms','assertions'):
            item[group]={str(i):copy.deepcopy(node) for i,node in enumerate(record[group])
                if f'/records/{ri}/{group}/{i}' in included}
        projected['records'][str(ri)]=item
    material['draft']=projected
    material['all_current_nodes_for_field_coverage']=[]
    material['carried_node_judgments']=[c for c in material['carried_node_judgments'] if c['target_pointer'] in included]
    material['draft_projection']={'complete_candidate':False,'is_process_knowledge_draft':False,
        'original_contract_version':draft['contract_version'],'original_revision':candidate['revision'],
        'original_draft_digest':semantic_digest(draft),'included_node_pointers':sorted(included),
        'context_only_node_pointers':sorted(included-set(pointers)),
        'scope':'Exact selected closure and typed context at original JSON-pointer paths. Numeric maps preserve original indices. '
            'Full source fields, every record identity/description/uninterpreted span and global limitations remain. '
            'Other candidate nodes and carry judgments remain in their exact stored revisions; this is not full field coverage, '
            'whole-candidate consistency review, or proof of absent relations.'}
    for asset in material['read_definitions_and_contracts']['assets']:
        if asset['revision']==candidate['revision']:
            view=asset['read_projection']
            view.pop('draft_reference',None);view.pop('draft_digest',None)
            view.update(draft_projection_reference='/draft',draft_projection_digest=semantic_digest(projected),
                original_draft_digest=semantic_digest(draft),complete_draft_in_original_revision=True)
            asset['projection_digest']=semantic_digest(view)
    return material


@stage_timing('prepare_native_process_review')
def prepare_native_process_review(intake,principal,*,definition_revision,knowledge_reading_ref,
        target_pointers=None,field_locators=(),prior_review_revision=None,require_current=True,_trail=(),
        _exact_metadata_successors=False):
    """Prepare exact inputs; explicit roots expand via the actual meaning resolver.

    None selects all nodes initially, or changed/failed nodes with an exact prior
    observation. Caller-selected roots are internal references, not user schema.
    Fields outside field_locators intentionally await separate coverage review.
    """
    authorization,work=intake._work(principal)
    candidate,content,draft=_candidate(work,authorization,definition_revision)
    if content.get('contract_version') in _NATIVE_MEANING_CONTRACTS:
        return _prepare_native_meaning_review(intake,principal,work,authorization,candidate,content,
            knowledge_reading_ref=knowledge_reading_ref,target_pointers=target_pointers,
            field_locators=field_locators,prior_review_revision=prior_review_revision,require_current=require_current,trail=_trail,
            exact_metadata_successors=_exact_metadata_successors)
    sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
    context=work.contexts.validate_reading(authorization=authorization,
        revision=RevisionRef.model_validate(knowledge_reading_ref),sources=sources,require_current=require_current,
        _exact_metadata_successors=_exact_metadata_successors)
    if candidate['revision'] not in [a.revision.model_dump(mode='json') for a in context.assets]:
        raise ValueError('NATIVE_PROCESS_CANDIDATE_NOT_READ')
    readings=RequestSourceReader(intake,principal).read(intake,principal,sources)
    evidence=next((s for s in readings if s['source']['digest']==draft['source_revision_digest']),None)
    if evidence is None:raise ValueError('NATIVE_PROCESS_PRIMARY_SOURCE_MISSING')
    all_targets=assessment_targets(draft,include_all_terms=True)
    prior=None;carry=[];old=None;prior_ref=None;prior_binding=None
    refs=[candidate['revision']]
    if prior_review_revision is not None:
        prior_ref=RevisionRef.model_validate(prior_review_revision).model_dump(mode='json')
        old,old_draft,prior,usable,prior_binding=_prior(intake,principal,work,authorization,prior_ref,candidate,trail=_trail)
        for ref in (prior_ref,old['revision']):
            if ref not in refs:refs.append(ref)
        selected=source_review_selection(draft,evidence,previous_draft=old_draft,
            previous_review=prior or {'claims':[],'fields':[]})
        # Node/qualifier changes and typed reverse dependencies invalidate carry.
        carry=[p for p in selected['carry_forward_nodes'] if p in usable]
        if prior_binding is not None:
            carry=_same_reviewed_closures(carry,old=old,prior_binding=prior_binding,
                candidate=candidate,context=context,readings=readings)
        if target_pointers is None:target_pointers=[t['target_pointer'] for t in selected['targets']]
    if target_pointers is None:target_pointers=[t['target_pointer'] for t in all_targets]
    if any(ref not in [a.revision.model_dump(mode='json') for a in context.assets] for ref in refs):
        raise ValueError('NATIVE_PROCESS_REVIEW_INPUT_NOT_READ')
    roots=list(target_pointers)
    graphs=meaning_citation_targets(context=context,sources=readings,asset_revision=candidate['revision'],target_pointers=roots)
    pointers=set()
    for target in graphs:
        if target['binding_status']!='bound':raise ValueError('NATIVE_PROCESS_REVIEW_CLOSURE_UNRESOLVED')
        for node in target['graph_evidence']:
            if node.get('asset_revision',candidate['revision'])==candidate['revision']:
                pointers.add(node['target_pointer'])
    known={t['target_pointer'] for t in all_targets}
    if not pointers<=known:raise ValueError('NATIVE_PROCESS_REVIEW_CLOSURE_TARGET_UNSUPPORTED')
    fields=list(field_locators)
    if len(fields)!=len(set(fields)) or not set(fields)<={f['field_locator'] for f in evidence['fields']}:
        raise ValueError('NATIVE_PROCESS_REVIEW_FIELD_SCOPE_INVALID')
    # An unchanged, previously reviewed root is reusable too. The prior reading
    # and actual observations are independently reconstructed above.
    selected_pointers=pointers-set(carry)
    carry=[p for p in carry if p not in selected_pointers]
    selection={'targets':[t for t in all_targets if t['target_pointer'] in selected_pointers],
        'fields':fields,'carry_forward_nodes':carry,'carry_forward_fields':[]}
    scope=NativeProcessReviewScope(candidate_draft_digest=semantic_digest(draft),
        source_revision_digest=draft['source_revision_digest'],root_pointers=roots,
        target_pointers=[t['target_pointer'] for t in selection['targets']],field_locators=fields,
        prior_review_revision=prior_ref).model_dump(mode='json')
    material=source_review_material(draft,evidence,context.model_dump(mode='json'))
    material.update(draft=copy.deepcopy(draft),targets=copy.deepcopy(selection['targets']),
        all_current_nodes_for_field_coverage=copy.deepcopy(all_targets),
        carried_node_judgments=[copy.deepcopy(c) for c in (prior or {}).get('claims',[]) if c['target_pointer'] in carry],
        field_locators_to_assess=fields,review_scope='selected_nodes',native_review_scope=scope,
        read_definitions_and_contracts=response_context_view(context.model_dump(mode='json'),source_readings=readings))
    material.pop('original_fields')
    index=next(i for i,s in enumerate(readings) if s['source']['digest']==draft['source_revision_digest'])
    material['original_fields_reference']=f'/read_definitions_and_contracts/source_readings/{index}/fields'
    if carry:
        material['carried_review_limits']={'review_revision':prior_ref,
            'findings':prior_binding['review']['findings'],'limitations':prior_binding['review']['limitations'],
            'source_assessment_limitations':prior_binding['validated_assessment']['limitations']}
    for asset in material['read_definitions_and_contracts']['assets']:
        view=asset['read_projection']
        if asset['revision']==candidate['revision'] and view.get('draft')==draft:
            view.pop('draft');view.update(draft_reference='/draft',draft_digest=semantic_digest(draft))
            asset['projection_digest']=semantic_digest(view)
        elif (asset['kind']=='pack' and view.get('contract_version')=='boi/native-agent-observation@1'
                and view.get('request',{}).get('review_contract_version') in ('boi/native-definition-review@1','boi/native-definition-review@2')):
            asset['read_projection']={'historical_observation_reference':asset['revision'],
                'history_preserved_in_exact_wiki_revision':True,
                'scope':'Prior review; applicable carried judgments and limitations are supplied separately.'}
            asset['projection_digest']=semantic_digest(asset['read_projection'])
    if not fields:
        material=_selected_node_material(material,draft=draft,pointers=pointers,candidate=candidate,context=context,readings=readings)
    material=source_review_delivery(material)
    prompt=source_review_prompt(material)+('\nReturn NativeDefinitionReview@2. Copy definition_revisions and scope exactly from '
        'the envelope below; put only the selected target and field judgments in source_assessment. '
        'Unselected nodes and fields are intentionally unreviewed, not omissions from this review response. '
        'Conditions, exceptions and complete original fields remain available through the supplied references. '
        'Whole-candidate disposition is an opinion, never per-node approval.\n')+json.dumps({
            'definition_revisions':[candidate['revision']],'scope':scope},ensure_ascii=False,separators=(',',':'))
    request=NativeObservationInput(prompt=prompt,output_schema_json=json.dumps(NativeDefinitionReviewV2.model_json_schema(),ensure_ascii=False),
        source_manifest_digest=source_manifest_digest(sources),input_revisions=refs,
        knowledge_reading_ref=knowledge_reading_ref,review_contract_version='boi/native-definition-review@2')
    return {'definition_revision':candidate['revision'],'scope':scope,'material':material,'request':request.model_dump(mode='json'),
        'selection':selection,'carried_assessment':prior,'sources':readings,'context':context.model_dump(mode='json'),
        'carried_review_limits':material.get('carried_review_limits'),
        'carried_observation_provenance':prior_binding['native_observation_provenance'] if carry else [],
        '_prior_review_reuse_dependencies':([] if prior_ref is None else
            prior_binding.get('review_reuse_dependencies') if prior_binding is not None else None)}


def _recorded_empty_field_review_input(recorded, current, prepared):
    """Recognize the old resolver's diagnostic for unselected empty fields.

    The candidate, source bytes, selected closures, instructions and judgment
    contract must still be identical. This adapter cannot qualify a formerly
    unresolved selected node or accept arbitrary prompt/material differences.
    """
    if {k:v for k,v in recorded.items() if k!='prompt'}!={k:v for k,v in current.items() if k!='prompt'}:
        return None
    marker='{"review_instructions_version"'
    try:
        old_start=recorded['prompt'].index(marker);new_start=current['prompt'].index(marker)
        old,old_end=json.JSONDecoder().raw_decode(recorded['prompt'][old_start:])
        new,new_end=json.JSONDecoder().raw_decode(current['prompt'][new_start:])
    except (ValueError,KeyError,TypeError):return None
    if (recorded['prompt'][:old_start]!=current['prompt'][:new_start]
            or recorded['prompt'][old_start+old_end:]!=current['prompt'][new_start+new_end:]):return None
    from .native_definition_sources import project_definition_evidence
    groups={}
    for entry in project_definition_evidence(prepared['material']['draft'],prepared['sources'],''):
        owner=entry.get('meaning_context')
        if owner is not None:groups.setdefault(owner['pointer'],[]).append(entry)
    selected=set(prepared['scope']['root_pointers'])|set(prepared['scope']['target_pointers'])
    prior=old.get('native_meaning_dependencies',{});updated=new.get('native_meaning_dependencies',{})
    if not isinstance(prior,dict) or not isinstance(updated,dict) or set(prior)!=set(updated):return None
    changed=[p for p in prior if prior[p]!=updated[p]]
    if not changed or selected.intersection(changed):return None
    normalized=copy.deepcopy(new)
    for pointer in changed:
        entries=groups.get(pointer,[])
        if (prior[pointer]!=[] or updated[pointer]!=[pointer] or not entries
                or not any(e['status']=='located_empty' for e in entries)
                or any(e['status'] not in ('located','located_empty') for e in entries)):
            return None
        normalized['native_meaning_dependencies'][pointer]=[]
    removed=[{'target_pointer':p,'reason_code':'ANSWER_NATIVE_MEANING_EVIDENCE_UNRESOLVED'} for p in changed]
    unresolved=old.get('unresolved_meaning_targets',[])
    if (any(unresolved.count(x)!=1 for x in removed)
            or [x for x in unresolved if x not in removed]!=new.get('unresolved_meaning_targets')):return None
    normalized['unresolved_meaning_targets']=copy.deepcopy(unresolved)
    if normalized!=old:return None
    return {'basis':'historical_unselected_empty_field_diagnostic',
        'changed_unselected_targets':changed,'selected_meanings_unchanged':True,
        'original_review_preserved':True,'review_transferred':False}


@stage_timing('read_native_process_review_binding')
def read_native_process_review_binding(intake,principal,review_revision,*,require_current=True,_trail=()):
    authorization,work=intake._work(principal)
    revision=RevisionRef.model_validate(review_revision)
    if revision.ref in _trail or len(_trail)>=16:raise ValueError('NATIVE_PROCESS_REVIEW_HISTORY_CYCLE_OR_LIMIT')
    observation=read_native_observation(work,authorization,revision)
    review=scoped_native_review_model(observation['value'].get('contract_version')).model_validate(observation['value'])
    prepared=prepare_native_process_review(intake,principal,definition_revision=review.definition_revisions[0],
        knowledge_reading_ref=observation['request']['knowledge_reading_ref'],target_pointers=review.scope.root_pointers,
        field_locators=review.scope.field_locators,prior_review_revision=review.scope.prior_review_revision,
        require_current=require_current,_trail=(*_trail,revision.ref),_exact_metadata_successors=True)
    compatibility=None
    if observation['request']!=prepared['request'] and 'native_targets' in prepared:
        compatibility=_recorded_empty_field_review_input(observation['request'],prepared['request'],prepared)
    if (review.scope.model_dump(mode='json')!=prepared['scope']
            or (observation['request']!=prepared['request'] and compatibility is None)):
        raise ValueError('NATIVE_PROCESS_REVIEW_EXACT_INPUT_MISMATCH')
    candidate,content,draft=_candidate(work,authorization,review.definition_revisions[0])
    evidence=(_multi_source_review_fields(prepared['sources'])[0]
        if review.contract_version=='boi/native-definition-review@3' else
        next(s for s in prepared['sources'] if s['source']['digest']==review.scope.source_revision_digest))
    result=observe_source_review(review.source_assessment.model_dump(mode='json'),draft=draft,evidence=evidence,
        selection=prepared['selection'],previous_review=prepared['carried_assessment'],
        reference_contract_version='boi/source-coverage-references@2',review_scope='selected_nodes',
        **({'native_targets':prepared['native_targets'],'native_closures':prepared['native_closures']}
           if 'native_targets' in prepared else {}))
    check=result['check']
    prior_dependencies=prepared.get('_prior_review_reuse_dependencies')
    reuse_dependencies=([{'review_revision':revision.model_dump(mode='json'),
        'observation_digest':semantic_digest(observation),
        'candidate_revision':candidate['revision'],'candidate_content_digest':semantic_digest(content),
        'knowledge_reading_ref':prepared['request']['knowledge_reading_ref'],
        'context_digest':semantic_digest(prepared['context'])},*prior_dependencies]
        if prior_dependencies is not None else None)
    return {'contract_version':'boi/process-review-binding@1','status':'bound' if check['selected_assessment_complete'] else 'partially_bound',
        'candidate_revision':candidate['revision'],'review_revision':revision.model_dump(mode='json'),
        'knowledge_reading_ref':prepared['request']['knowledge_reading_ref'],
        'source_review':check,'check':{'candidate_revision':candidate['revision'],'source_review':check,'failed_use_pointers':[]},
        'usable_node_pointers':check['usable_node_pointers'],'quarantined_node_pointers':check['quarantined_node_pointers'],
        'validated_assessment':result['validated_assessment'],'review':review.model_dump(mode='json'),
        'context':prepared['context'],'sources':prepared['sources'],'candidate_content':content,
        'review_execution_binding':'authenticated_native_observation_and_exact_inputs',
        'reviewer_relationship_observation':{'relationship':'unknown','author_session_ref':None,
            'reviewer_session_ref':observation['provenance']['agent_session_ref'],
            'reported_relationship':review.reviewer_relationship,'relationship_verified':False,
            'reason':'No authenticated author-session link is present in the candidate contract.'},
        'native_observation_provenance':[observation['provenance'],*prepared['carried_observation_provenance']],
        'carried_review_limits':prepared['carried_review_limits'],
        'scientific_correctness':'not_evaluated','execution_authority_granted':False,'new_model_runs':0,
        'whole_plan_qualified':False,
        **({'review_reuse_dependencies':reuse_dependencies} if reuse_dependencies is not None else {}),
        **({'review_input_compatibility':compatibility} if compatibility is not None else {})}


def _existing_process_review_inputs(intake,principal,revision):
    from .domain_intake import DomainAssetReadRequest
    from .asset_user_views import process_review_target
    authorization,work=intake._work(principal)
    stored=work.assets.read(authorization=authorization,revision=RevisionRef.model_validate(revision),lane='provisional')
    material=_json(stored['asset']['content_json']);target=process_review_target(material)
    if stored['asset']['kind']!='pack' or target is None:raise ValueError('PROCESS_REVIEW_RECORD_REQUIRED')
    candidate,content,_=_candidate(work,authorization,target)
    sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
    context=work.contexts.validate_reading(authorization=authorization,
        revision=RevisionRef.model_validate(stored['definition_reading_ref']),sources=sources,require_current=True,
        _exact_metadata_successors=True)
    if RevisionRef.model_validate(target) not in {a.revision for a in context.assets}:
        raise ValueError('PROCESS_REVIEW_CANDIDATE_NOT_READ')
    return authorization,work,stored,material,candidate,content,context


def read_existing_process_review_binding(intake,principal,revision):
    """Consume existing source judgments through the established validator.

    This adapts verified references for selection; no new observation or
    approval is created, and the original review envelope remains unchanged.
    """
    from .process_review_binding import ProcessReviewBindingRequest,read_process_review_binding,read_recorded_sources
    authorization,work,stored,material,candidate,content,context=_existing_process_review_inputs(intake,principal,revision)
    checked=read_process_review_binding(intake,principal,ProcessReviewBindingRequest(
        candidate_revision=candidate['revision'],review_revision=stored['revision']))
    sources=read_recorded_sources(intake,principal,candidate['sources'],content)
    check=checked.get('check',{'candidate_revision':candidate['revision'],
        'source_review':{'usable_node_pointers':[],'failures':[]},'failed_use_pointers':[]})
    observations=[]
    # Signed legacy executions keep the full validation path. Native records
    # can reuse exact observations after checking their current source rights.
    if not checked.get('execution_refs'):
        for provenance in checked.get('native_observation_provenance',[]):
            ref=provenance['observation_revision']
            observation=read_native_observation(work,authorization,ref)
            observations.append({'revision':ref,'digest':semantic_digest(observation)})
    snapshot={'review_digest':semantic_digest(material),'candidate_digest':semantic_digest(content),
        'context_digest':semantic_digest(context.model_dump(mode='json')),'observations':observations}
    return {**checked,'check':check,'candidate_revision':candidate['revision'],
        'knowledge_reading_ref':stored['definition_reading_ref'],'context':context.model_dump(mode='json'),
        'sources':sources,'candidate_content':content,'review':copy.deepcopy(material),
        'review_summary':{'findings':[], 'limitations':material['source_assessment'].get('limitations',[]),
            'semantic_truth_proven':False,'execution_authority_granted':False},
        'source_review':check.get('source_review',{}),
        'review_execution_binding':checked.get('review_execution_binding','unconfirmed'),
        'reviewer_relationship_observation':{'relationship':'unknown','relationship_verified':False},
        'carried_review_limits':None,
        '_existing_process_review_inputs':snapshot if observations and not checked.get('execution_refs') else None,
        'existing_process_review':True,'scientific_correctness':'not_evaluated'}


def _reuse_existing_process_review(intake,principal,revision,binding):
    snapshot=binding.get('_existing_process_review_inputs')
    if not snapshot:return read_existing_process_review_binding(intake,principal,revision)
    authorization,work,stored,material,candidate,content,context=_existing_process_review_inputs(intake,principal,revision)
    if (stored['revision']!=binding['review_revision'] or candidate['revision']!=binding['candidate_revision']
            or semantic_digest(material)!=snapshot['review_digest'] or semantic_digest(content)!=snapshot['candidate_digest']
            or semantic_digest(context.model_dump(mode='json'))!=snapshot['context_digest']):
        raise ValueError('NATIVE_PREPARED_REVIEW_DEPENDENCIES_CHANGED')
    for item in snapshot['observations']:
        if semantic_digest(read_native_observation(work,authorization,item['revision']))!=item['digest']:
            raise ValueError('NATIVE_PREPARED_REVIEW_CHANGED')
    return copy.deepcopy(binding)


def reuse_native_process_review_binding(intake, principal, revision, binding):
    """Reuse immutable judgments/closure comparisons, retaining admission checks.

    Only a server-protected binding can reach this path. Current candidate
    admission is checked; carried historical candidates retain present access
    and immutable-source validation without requiring them to remain heads.
    Older preparations without complete history fingerprints use the full path.
    """
    expected_revision=RevisionRef.model_validate(revision).model_dump(mode='json')
    if binding.get('existing_process_review'):
        if binding.get('review_revision')!=expected_revision:raise ValueError('NATIVE_PREPARED_REVIEW_CHANGED')
        return _reuse_existing_process_review(intake,principal,revision,binding)
    dependencies=binding.get('review_reuse_dependencies')
    chained=binding.get('review',{}).get('scope',{}).get('prior_review_revision') is not None
    if binding.get('review_revision')!=expected_revision or (chained and not dependencies):
        return read_native_process_review_binding(intake,principal,revision)
    authorization,work=intake._work(principal)
    if dependencies is not None:
        if not 1<=len(dependencies)<=16:
            raise ValueError('NATIVE_PREPARED_REVIEW_HISTORY_INVALID')
        wanted=expected_revision;seen=set()
        for index,dependency in enumerate(dependencies):
            ref=dependency['review_revision']
            if ref!=wanted or ref['ref'] in seen:
                raise ValueError('NATIVE_PREPARED_REVIEW_HISTORY_INVALID')
            seen.add(ref['ref'])
            observation=read_native_observation(work,authorization,ref)
            review=scoped_native_review_model(observation['value'].get('contract_version')).model_validate(observation['value']).model_dump(mode='json')
            if (semantic_digest(observation)!=dependency['observation_digest']
                    or review['definition_revisions']!=[dependency['candidate_revision']]
                    or observation['request']['knowledge_reading_ref']!=dependency['knowledge_reading_ref']):
                raise ValueError('NATIVE_PREPARED_REVIEW_CHANGED')
            candidate,content,_=_candidate(work,authorization,dependency['candidate_revision'])
            sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
            context=work.contexts.validate_reading(authorization=authorization,
                revision=RevisionRef.model_validate(dependency['knowledge_reading_ref']),
                sources=sources,require_current=index==0,_exact_metadata_successors=True)
            if (semantic_digest(content)!=dependency['candidate_content_digest']
                    or semantic_digest(context.model_dump(mode='json'))!=dependency['context_digest']):
                raise ValueError('NATIVE_PREPARED_REVIEW_DEPENDENCIES_CHANGED')
            if index==0 and (review!=binding['review'] or content!=binding['candidate_content']
                    or context.model_dump(mode='json')!=binding['context']):
                raise ValueError('NATIVE_PREPARED_REVIEW_DEPENDENCIES_CHANGED')
            wanted=review['scope']['prior_review_revision']
        if wanted is not None:raise ValueError('NATIVE_PREPARED_REVIEW_HISTORY_INCOMPLETE')
        return copy.deepcopy(binding)
    # Compatibility for earlier unchained protected preparations.
    observation=read_native_observation(work,authorization,revision)
    if scoped_native_review_model(observation['value'].get('contract_version')).model_validate(observation['value']).model_dump(mode='json') != binding['review']:
        raise ValueError('NATIVE_PREPARED_REVIEW_CHANGED')
    candidate,content,_=_candidate(work,authorization,binding['candidate_revision'])
    sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
    context=work.contexts.validate_reading(authorization=authorization,
        revision=RevisionRef.model_validate(binding['knowledge_reading_ref']),sources=sources,require_current=True,
        _exact_metadata_successors=True)
    if content!=binding['candidate_content'] or context.model_dump(mode='json')!=binding['context']:
        raise ValueError('NATIVE_PREPARED_REVIEW_DEPENDENCIES_CHANGED')
    return copy.deepcopy(binding)


def check_native_process_answer(answer,binding,*,review_dependencies=None):
    """Check body AND request-plan closures, including unreviewed foreign assets."""
    from agent_kit.python.boi_process_answer_v2 import answer_evidence_groups
    from agent_kit.python.boi_process_claim_review import (check_answer_review_dependencies,
        prepare_answer_review_dependencies,check_prepared_answer_review_dependencies)
    revisions=[]
    for item in answer['answers']:
        for _,statements in answer_evidence_groups(item):
            for statement in statements:
                for citation in statement['citations']:
                    if citation['kind']!='meaning':continue
                    for ref in [citation['asset_revision'],*[n.get('asset_revision',citation['asset_revision']) for n in citation['graph_evidence']]]:
                        if ref not in revisions:revisions.append(ref)
    for revision in revisions:
        if revision!=binding['candidate_revision']:
            # No proof was supplied for this external definition's node scope.
            check_answer_review_dependencies(answer,asset_revision=revision,asset_content={},review_check={})
    if review_dependencies is None:
        review_dependencies=prepare_answer_review_dependencies(asset_revision=binding['candidate_revision'],
            asset_content=binding['candidate_content'],review_check=binding['check'])
    return check_prepared_answer_review_dependencies(answer,review_dependencies)


def native_process_review_authority(binding,authorization):
    from ..governed_runtime.native_definition_context import NativeProcessReviewAuthority
    from ..governed_runtime.task_knowledge import TaskKnowledgeContext
    context=TaskKnowledgeContext.model_validate(binding['context'])
    return NativeProcessReviewAuthority(principal=authorization.principal,purpose=context.purpose,
        definition_revisions=[binding['candidate_revision']],review_revision=binding['review_revision'],
        knowledge_reading_ref=binding['knowledge_reading_ref'],
        definition_context_digest=context.context_digest,source_manifest_digest=context.source_manifest_digest,
        acl_policy_digest=authorization.policy_digest),context


def check_native_process_answer_scopes(answer,bindings,*,dependencies=None,unscoped_authorized_revisions=()):
    """Apply each independent node scope to every used body/plan dependency.

    A usable node in one definition cannot qualify a node of another definition.
    Multiple opinions for the same revision need an explicit reconciled review.
    """
    from agent_kit.python.boi_process_answer_v2 import answer_evidence_groups
    from agent_kit.python.boi_process_claim_review import (
        prepare_answer_review_dependencies,check_prepared_answer_review_dependencies)
    keys=[b['candidate_revision']['revision_digest'] for b in bindings]
    if len(keys)!=len(set(keys)):raise ValueError('ANSWER_REVIEW_DEFINITION_SCOPE_AMBIGUOUS')
    owned={b['candidate_revision']['revision_digest']:b['candidate_revision'] for b in bindings}
    for ref in unscoped_authorized_revisions:
        if ref['revision_digest'] in owned:
            raise ValueError('ANSWER_REVIEW_DEFINITION_SCOPE_AMBIGUOUS')
        owned[ref['revision_digest']] = ref
    for item in answer['answers']:
        for _,statements in answer_evidence_groups(item):
            for statement in statements:
                for citation in statement['citations']:
                    if citation['kind']!='meaning':continue
                    refs=[citation['asset_revision'],*[n.get('asset_revision',citation['asset_revision']) for n in citation['graph_evidence']]]
                    if any(owned.get(ref['revision_digest'])!=ref for ref in refs):
                        raise ValueError('PROCESS_ANSWER_QUARANTINED_DEPENDENCY:unreviewed_definition')
    prepared=dependencies if dependencies is not None else [prepare_answer_review_dependencies(
        asset_revision=b['candidate_revision'],asset_content=b['candidate_content'],review_check=b['check']) for b in bindings]
    if [d.asset_revision for d in prepared]!=[b['candidate_revision'] for b in bindings]:
        raise ValueError('ANSWER_REVIEW_DEPENDENCY_SCOPE_MISMATCH')
    return [{'review_revision':b['review_revision'],'candidate_revision':b['candidate_revision'],
        'check':check_prepared_answer_review_dependencies(answer,d)} for b,d in zip(bindings,prepared)]


def read_native_process_review_for_work(work,authorization,revision,*,require_current=True):
    """Reuse the reader with the existing work's exact ACL, teams and tool scope."""
    from types import SimpleNamespace
    from .domain_intake import DomainIntakeService
    class ExistingWorkIntake(DomainIntakeService):
        def _work(self,principal):
            return self._authorization(principal),work
    intake=ExistingWorkIntake(work.intake,lambda principal:authorization)
    principal=SimpleNamespace(employee_id=authorization.principal,teams=work.contexts.principal_teams)
    from .asset_user_views import process_review_target
    stored=work.assets.read(authorization=authorization,revision=RevisionRef.model_validate(revision),lane='provisional')
    if stored['asset']['kind']=='pack' and process_review_target(_json(stored['asset']['content_json'])) is not None:
        return read_existing_process_review_binding(intake,principal,revision)
    return read_native_process_review_binding(intake,principal,revision,require_current=require_current)


def check_native_process_semantic_basis(basis,binding,*,additional_bindings=()):
    """Recheck final body/plan uses, not the selectable meaning inventory.

    The existing indexed correspondence is lossless. Reconstruct each used
    graph, verify its full resolver closure and apply the same review gate.
    """
    from .process_citation_display import _index_meaning_graph
    if basis.get('unresolved_meaning_links'):raise ValueError('NATIVE_FINAL_MEANING_UNRESOLVED')
    nodes={};links=copy.deepcopy(basis.get('statement_links',[]))
    for node in basis.get('nodes',[]):
        key=node['node_id']
        if key in nodes and nodes[key]!=node:raise ValueError('NATIVE_FINAL_MEANING_NODE_CONFLICT')
        nodes[key]=copy.deepcopy(node)
    for plan in basis.get('request_plans',[]):
        for facet in plan['plan'].get('facets',[]):
            for citation in facet.get('citations',[]):
                if citation['kind']!='meaning':continue
                if not citation.get('graph_evidence'):raise ValueError('NATIVE_FINAL_MEANING_PLAN_UNBOUND')
                indexed={};uses=_index_meaning_graph(citation,indexed)
                if any(key in nodes and nodes[key]!=value for key,value in indexed.items()):
                    raise ValueError('NATIVE_FINAL_MEANING_NODE_CONFLICT')
                nodes.update(indexed);links.append({'nodes':uses})
    owned={b['candidate_revision']['revision_digest']:b for b in (binding,*additional_bindings)}
    if len(owned)!=1+len(additional_bindings):raise ValueError('ANSWER_REVIEW_DEFINITION_SCOPE_AMBIGUOUS')
    statements=[];roots=[];link_roots=[]
    for link in links:
        graph=[];direct=[]
        for use in link['nodes']:
            node=nodes.get(use['node_id'])
            if node is None or semantic_digest({k:v for k,v in node.items() if k!='node_id'})!=use['node_id']:
                raise ValueError('NATIVE_FINAL_MEANING_NODE_CHANGED_OR_MISSING')
            graph.append({**{k:v for k,v in node.items() if k!='node_id'},**{k:v for k,v in use.items() if k!='node_id'}})
            if use.get('role')=='direct':
                revision=node.get('asset_revision',binding['candidate_revision'])
                if revision['revision_digest'] not in owned or owned[revision['revision_digest']]['candidate_revision']!=revision:
                    raise ValueError('PROCESS_ANSWER_QUARANTINED_DEPENDENCY:unreviewed_definition')
                root=(revision['revision_digest'],node['target_pointer'])
                direct.append(root)
                if root not in roots:roots.append(root)
        if not direct:raise ValueError('NATIVE_FINAL_MEANING_DIRECT_ROOT_REQUIRED')
        statements.append({'citations':[{'kind':'meaning','asset_revision':owned[direct[0][0]]['candidate_revision'],'graph_evidence':graph}]})
        link_roots.append(direct)
    answer={'answers':[{'sentences':statements}]}
    checked=(check_native_process_answer_scopes(answer,[binding,*additional_bindings]) if additional_bindings
        else check_native_process_answer(answer,binding))
    canonical={}
    for digest,current in owned.items():
        pointers=[p for d,p in roots if d==digest]
        targets=meaning_citation_targets(context=current['context'],sources=current['sources'],
            asset_revision=current['candidate_revision'],target_pointers=pointers) if pointers else []
        canonical.update({(digest,t['target_pointer']):t for t in targets})
    for link,direct in zip(links,link_roots):
        expected=[];expected_nodes={}
        for pointer in direct:
            target=canonical[pointer]
            if target['binding_status']!='bound':raise ValueError('NATIVE_FINAL_MEANING_CLOSURE_UNRESOLVED')
            expected.extend(_index_meaning_graph(target,expected_nodes))
        if ({semantic_digest(u) for u in expected}!={semantic_digest(u) for u in link['nodes']}
                or any(nodes.get(key)!=value for key,value in expected_nodes.items())):
            raise ValueError('NATIVE_FINAL_MEANING_CLOSURE_MISMATCH')
    return checked
