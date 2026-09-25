"""Typed asset navigation, never request interpretation or answer approval."""
import copy
import json


def recorded_assessment_view(assessment):
    """Share identical original quotations in a record view, without summarizing.

    Each judgment keeps its target, label, reason and other fields. References
    resolve inside this response; they are neither knowledge IDs nor new proof.
    The immutable original assessment remains available through detail_read.
    """
    result=copy.deepcopy(assessment)
    if not isinstance(result,dict) or 'shared_evidence' in result:return result
    claims=result.get('claims',[])
    if not isinstance(claims,list):return result
    groups={}
    for claim in claims:
        if not isinstance(claim,dict) or 'evidence_ref' in claim:return copy.deepcopy(assessment)
        evidence=claim.get('evidence')
        if not isinstance(evidence,list) or not evidence:continue
        key=json.dumps(evidence,ensure_ascii=False,sort_keys=True,separators=(',',':'))
        groups.setdefault(key,[]).append(claim)
    shared={}
    for key,owners in groups.items():
        if len(owners)<2:continue
        ref=str(len(shared));pointer='/shared_evidence/'+ref
        if (len(owners)-1)*len(key)<=len(owners)*(len(pointer)+20):continue
        shared[ref]=owners[0]['evidence']
        for owner in owners:
            del owner['evidence'];owner['evidence_ref']=pointer
    if shared:result['shared_evidence']=shared
    return result


def process_review_target(content):
    """Recognize the existing source-review envelope, not an approval."""
    from ..governed_runtime.semantic_binding_contract import RevisionRef
    if not isinstance(content,dict):return None
    observation=content.get('source_observation');assessment=content.get('source_assessment');check=content.get('check')
    if (not isinstance(observation,dict) or not isinstance(observation.get('attempts'),list)
            or not isinstance(assessment,dict) or not isinstance(assessment.get('claims'),list)
            or not isinstance(check,dict)):
        return None
    try:return RevisionRef.model_validate(check.get('candidate_revision')).model_dump(mode='json')
    except (TypeError,ValueError):return None


def review_meaning_selection_view(record):
    """Place recorded judgments beside their exact candidate, once.

    This joins existing revision/pointer identities, not question words or
    semantic similarity. No parent, sibling, or other revision inherits a
    judgment. Unmatched judgments and all review limits remain visible.
    """
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    result=copy.deepcopy(record)
    assessment=result.get('review',{}).get('source_assessment',{})
    claims=assessment.get('claims')
    indexes=result.get('meaning_indexes',[])
    if (len(indexes)!=1 or not isinstance(claims,list) or not claims
            or 'review_claim_layout' in result
            or any(k in assessment for k in ('unmapped_claims','claim_order'))):return result
    index=indexes[0]
    declared=result.get('definition_revisions',result.get('review',{}).get('definition_revisions',[]))
    if declared!=[index.get('definition_revision')]:return result
    candidates={}
    for position,candidate in enumerate(index.get('meaning_candidates',[])):
        if 'recorded_judgments' in candidate:return result
        candidates.setdefault(candidate.get('target_pointer'),[]).append((position,candidate))
    unmapped=[];order=[]
    for claim in claims:
        matches=(candidates.get(claim['target_pointer'],[])
            if isinstance(claim,dict) and isinstance(claim.get('target_pointer'),str) else [])
        if len(matches)!=1:
            unmapped.append(claim);order.append(None)
            continue
        position,candidate=matches[0];order.append(position)
        candidate.setdefault('recorded_judgments',[]).append({k:v for k,v in claim.items() if k!='target_pointer'})
    del assessment['claims']
    assessment.update(claim_order=order,unmapped_claims=unmapped)
    result['review_claim_layout']={'layout':'candidate_local_ordered','claims_digest':semantic_digest(claims),
        'scope':'Recorded judgments apply only to their exact candidate pointer in this revision. '
            'All reasons, evidence references and limits are retained. They are not current use approval; '
            'preparation still checks selected meanings, dependencies and original evidence.'}
    return result


def restore_review_meaning_selection_view(record):
    """Restore the exact recorded claim order for existing consumers, no reads."""
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    result=copy.deepcopy(record)
    layout=result.pop('review_claim_layout',None)
    if layout is None:return result
    if layout.get('layout')!='candidate_local_ordered' or len(result['meaning_indexes'])!=1:
        raise ValueError('MEANING_REVIEW_LAYOUT_INVALID')
    assessment=result['review']['source_assessment'];order=assessment.pop('claim_order')
    unmapped=iter(assessment.pop('unmapped_claims'));candidates=result['meaning_indexes'][0]['meaning_candidates']
    remaining={i:iter(c.pop('recorded_judgments',[])) for i,c in enumerate(candidates)}
    claims=[]
    try:
        for position in order:
            if position is None:claims.append(next(unmapped));continue
            if type(position) is not int or position not in remaining:
                raise ValueError('MEANING_REVIEW_LAYOUT_INVALID')
            judgment=next(remaining[position])
            if 'target_pointer' in judgment:raise ValueError('MEANING_REVIEW_LAYOUT_INVALID')
            claims.append({'target_pointer':candidates[position]['target_pointer'],**judgment})
    except StopIteration:raise ValueError('MEANING_REVIEW_LAYOUT_INVALID') from None
    if list(unmapped) or any(list(values) for values in remaining.values()):
        raise ValueError('MEANING_REVIEW_LAYOUT_INVALID')
    assessment['claims']=claims
    if semantic_digest(assessment['claims'])!=layout['claims_digest']:
        raise ValueError('MEANING_REVIEW_LAYOUT_INVALID')
    return result


def native_review_record_view(intake,principal,stored,*,include_meanings=False):
    """Read existing review decisions without replaying their model input.

    This is a record projection, not a new opinion or a current use authority.
    The unchanged prompt, schema and complete observation remain addressable
    through the same revision's explicit asset read. Consumers still validate
    actual selected meanings and current dependencies at composition/execution.
    """
    from ..governed_runtime.native_observation import _json,read_native_observation
    from ..governed_runtime.native_definition_context import NativeDefinitionReview,scoped_native_review_model
    from ..governed_runtime.source_envelope import byte_digest
    if stored['asset']['kind']!='pack':return None
    try:content=_json(stored['asset']['content_json'])
    except (ValueError,TypeError):return None
    target=process_review_target(content)
    if target is not None:
        from ..governed_runtime.semantic_binding_contract import RevisionRef
        authorization,work=intake._work(principal)
        if not any(d.get('revision')==target and d.get('required',True) for d in stored['asset'].get('dependencies',[])):
            raise ValueError('PROCESS_REVIEW_DECLARED_DEPENDENCY_REQUIRED')
        indexes=[work.assets.meaning_index(authorization=authorization,revision=RevisionRef.model_validate(target))] if include_meanings else []
        return {'view':'process_review_record','revision':stored['revision'],
            'definition_revisions':[target],
            'review':{'source_assessment':recorded_assessment_view(content['source_assessment']),
                'recorded_check':{k:copy.deepcopy(content['check'][k]) for k in ('candidate_revision','source_fidelity','reuse_status') if k in content['check']}},
            **({'meaning_indexes':indexes} if include_meanings else {}),
            'available_user_views':available_user_views(stored),
            'use_authority':'Recorded original-source judgments; exact inputs and current scope checked during preparation.',
            'whole_definition_approved':False,'new_model_runs':0,
            'detail_read':{'tool':'boi_knowledge_read','arguments':{'revision':stored['revision'],'view':'asset','lane':'provisional'}}}
    if (not isinstance(content,dict)
            or content.get('contract_version')!='boi/native-agent-observation@1'):
        return None
    request=content.get('request',{})
    if not isinstance(request,dict) or request.get('review_contract_version') not in (
            'boi/native-definition-review@1','boi/native-definition-review@2','boi/native-definition-review@3'):
        return None
    authorization,work=intake._work(principal)
    observation=read_native_observation(work,authorization,stored['revision'])
    value=observation['value']
    model=(NativeDefinitionReview if request['review_contract_version']=='boi/native-definition-review@1'
        else scoped_native_review_model(request['review_contract_version']))
    review=model.model_validate(value)
    if value['contract_version']!=request['review_contract_version']:
        raise ValueError('NATIVE_DEFINITION_REVIEW_CONTRACT_MISMATCH')
    request_ref={k:copy.deepcopy(v) for k,v in observation['request'].items()
        if k not in ('prompt','output_schema_json')}
    request_ref.update(prompt_digest=byte_digest(request['prompt'].encode()),
        output_schema_digest=byte_digest(request['output_schema_json'].encode()))
    # Reuse the same revision/parser index used by explicit meaning reads.
    # Selection stays with the host; a review's disposition never filters out
    # contrary candidates or promotes every indexed node to approved meaning.
    indexes=([work.assets.meaning_index(authorization=authorization,revision=revision)
        for revision in dict.fromkeys(review.definition_revisions)] if include_meanings else [])
    return {**{k:copy.deepcopy(stored[k]) for k in ('revision','logical_id','namespace','title',
            'description','sources','definition_reading_ref','knowledge_reading_status','status',
            'canonical_projection_eligible','available_user_views') if k in stored},
        'view':'native_review_record','review':copy.deepcopy(value),
        **({'meaning_indexes':indexes,
            'meaning_selection_scope':{'selection_complete':False,'source_text_provided':False,
                'meaning_support_inherited':False,
                'continuation':'Choose from these existing meanings for the current request and pass their exact references as meaning_selection to answer preparation. No separate index read is needed for the same revisions; expand evidence only when this scope is insufficient.'}} if include_meanings else {}),
        'request_reference':request_ref,'provenance':copy.deepcopy(observation['provenance']),
        'use_authority':'recorded_judgment_only; current selected meaning, source and dependency checks occur at composition or execution',
        'whole_definition_approved':False,'new_model_runs':0,
        'detail_read':{'tool':'boi_knowledge_read','arguments':{
            'revision':copy.deepcopy(stored['revision']),'view':'asset','lane':'provisional'}}}


def read_meaning_index(intake, principal, revision):
    """One existing read view for a definition or its recorded review scope."""
    from ..governed_runtime.domain_asset_store import DomainAssetStore
    authorization=intake._authorization(principal)
    assets=DomainAssetStore(intake.source_intake)
    record=assets._record_metadata(authorization,revision,metadata_only=True)
    if record.payload.get('kind')=='definition':
        return assets.meaning_index(authorization=authorization,revision=revision)
    stored=assets.read(authorization=authorization,revision=revision,lane='provisional')
    stored['available_user_views']=[v for v in available_user_views(stored) if v['tool']!='boi_knowledge_read']
    result=native_review_record_view(intake,principal,stored,include_meanings=True)
    if result is None:raise ValueError('MEANING_INDEX_DEFINITION_OR_REVIEW_REQUIRED')
    return review_meaning_selection_view(result)


def _definition_review_targets(request, value):
    if value['contract_version']=='boi/native-definition-review@1':
        # Legacy observations reviewed every declared input as a definition.
        return copy.deepcopy(request.get('input_revisions',[])) \
            if request.get('input_revisions')==value.get('definition_revisions') else []
    from ..governed_runtime.native_definition_context import scoped_native_review_model
    from ..governed_runtime.semantic_binding_contract import RevisionRef
    try:
        review=scoped_native_review_model(value.get('contract_version')).model_validate(value)
        inputs=tuple(RevisionRef.model_validate(x) for x in request.get('input_revisions',[]))
    except (TypeError,ValueError):
        return []
    current=review.definition_revisions
    if not inputs or inputs[0]!=current[0] or len(set(inputs))!=len(inputs):
        return []
    prior=review.scope.prior_review_revision
    if prior is None:
        if inputs!=current:return []
    elif len(inputs) not in (2,3) or inputs[1]!=prior or prior==current[0]:
        return []
    # The remaining input, when present, is the historical candidate used for
    # carry-forward. Its relationship, source scope and authority are verified
    # by the scoped-review reader, not by this navigation metadata projection.
    return [revision.model_dump(mode='json') for revision in current]


def available_user_views(asset_read):
    try:
        content=json.loads(asset_read['asset']['content_json'])
    except (KeyError,TypeError,ValueError):
        return []
    if not isinstance(content,dict):return []
    readers={
        'boi/process-user-result@2':'boi_process_answer',
        'boi/process-user-result@3':'boi_process_answer',
        'boi/native-source-answer-delivery@1':'boi_native_answer',
        'boi/native-source-answer-delivery@2':'boi_native_answer',
        'boi/native-answer-delivery@1':'boi_native_answer',
        'boi/native-answer-delivery@2':'boi_native_answer',
    }
    contract=content.get('contract_version')
    if asset_read.get('asset',{}).get('kind')=='definition' and contract=='boi/knowledge-content@1':
        # This envelope is consumed by the published document reader. Its
        # legacy definition/source reader has different source authority and
        # must not be advertised as the way to open a published document.
        # Navigation is not publication, source access, or use qualification.
        arguments={'revision':copy.deepcopy(asset_read['revision']),'view':'document'}
        scope='Navigation only. The document reader checks current publication and access; source and use authority remain separate.'
        body={'tool':'boi_knowledge_read','arguments':arguments,
            'purpose':'Read the published body, complete selected meanings, conditions and current use limits. Original fields require a separate source permission.',
            'scope':scope}
        meaning=content.get('meaning')
        if isinstance(meaning,dict) and meaning.get('contract_version')=='boi/typed-knowledge-meaning@1':
            return [{'tool':'boi_knowledge_read',
                'arguments':{**copy.deepcopy(arguments),'document_options':{'include_sources':True}},
                'purpose':'Read selected meanings, their complete declared dependencies and separately authorized original fields together. Reuse the returned source_bundle without repeating source reads. If source access is denied, the body-only document view may still be permitted.',
                'scope':scope},body]
        return [body]
    if asset_read.get('asset',{}).get('kind') in ('definition','source') and contract not in readers:
        candidates=([{'tool':'boi_knowledge_read',
            'arguments':{'revision':copy.deepcopy(asset_read['revision']),'view':'meaning_index'},
            'purpose':'Select existing meanings and qualifiers before answer preparation; no original field text.',
            'scope':'Candidate declarations, not verified support or approval.'}]
            if asset_read['asset']['kind']=='definition' else [])
        return candidates+[{'tool':'boi_knowledge_read',
            'arguments':{'revision':copy.deepcopy(asset_read['revision']),'view':'definition_sources'},
            'purpose':'Read original fields, exact evidence links, candidate meanings and source scope for this definition.',
            'scope':'Original evidence access, not scientific truth or current execution approval.'}]
    process_target=process_review_target(content) if asset_read.get('asset',{}).get('kind')=='pack' else None
    if not isinstance(contract,str) and process_target is None:return []
    definition_review=False
    if contract=='boi/native-agent-observation@1':
        request=content.get('request')
        try:
            value=json.loads(content.get('value_json',''))
        except (TypeError,ValueError):
            value=None
        definition_review=(isinstance(request,dict) and isinstance(value,dict)
            and request.get('review_contract_version') in ('boi/native-definition-review@1','boi/native-definition-review@2','boi/native-definition-review@3')
            and value.get('contract_version')==request.get('review_contract_version'))
    if definition_review or process_target is not None:
        definition_targets=([process_target] if process_target is not None else _definition_review_targets(request,value))
        return [{'tool':'boi_knowledge_read',
            'definition_revisions':definition_targets,
            'arguments':{'revision':copy.deepcopy(asset_read['revision']),'view':'meaning_index'},
            'purpose':'Read this review and the existing meanings of its definition revisions together, then select meanings for answer preparation. A separate definition index read repeats these same meanings.',
            'scope':'Declared meaning and recorded node judgments remain distinct; no whole-definition approval or source absence proof.'},
            {'tool':'boi_native_answer',
            'definition_revisions':definition_targets,
            'arguments':{'composition':{'definition_review_revision':copy.deepcopy(asset_read['revision'])}},
            'required_arguments':['composition.question'],
            'purpose':'Prepare a new answer after selecting this definition for the current user request. Supply the current question; read the returned original sources and meaning targets, then submit the authored draft in the same composition.',
            'scope':'Navigation only. Selection relevance, review validity and source applicability are not established by this link. The composition reader validates authority; binding is not semantic review or final delivery.'}]
    tool=readers.get(contract)
    if tool is None:return []
    views=[{'tool':tool,
        'arguments':{'revision':copy.deepcopy(asset_read['revision'])},
        'purpose':'Read this result with its statement-bound sources and user-facing presentation.',
        'scope':'Navigation only. The result reader validates the stored result; current request fit and final delivery remain unverified.'}]
    if contract in ('boi/process-user-result@2','boi/process-user-result@3'):
        views.append({'tool':'boi_process_result',
            'arguments':{'revision':copy.deepcopy(asset_read['revision'])},
            'purpose':'Read the original source fields, conditions and meaning links behind this answer for the current question.',
            'scope':'Evidence navigation only; the prior answer and its review do not establish current request fulfillment or scientific truth.'})
    return views
