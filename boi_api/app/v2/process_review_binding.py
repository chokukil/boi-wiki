"""Wiki-owned linkage of a stored process review to admitted model observations.

Reuses immutable asset/context/task/tool-evidence services. This read issues no
new receipt and proves neither source entailment nor scientific correctness.
"""
import json
import copy
from contextlib import contextmanager
from contextvars import ContextVar
from ..governed_runtime.diagnostic_timing import stage_timing

from ..governed_runtime.semantic_binding_contract import FrozenContract,RevisionRef,Ref,semantic_digest
from ..governed_runtime.source_envelope import ArtifactEnvelope,byte_digest
from ..governed_runtime.domain_asset_store import source_manifest_digest
from ..governed_runtime.domain_work_contract import DomainToolEvidenceRequest


class NativeProcessReviewPreparation(FrozenContract):
    knowledge_reading_ref:RevisionRef
    target_pointers:tuple[Ref,...]|None=None
    field_locators:tuple[str,...]=()
    prior_review_revision:RevisionRef|None=None


class ProcessReviewBindingRequest(FrozenContract):
    candidate_revision:RevisionRef
    review_revision:RevisionRef|None=None
    preparation:NativeProcessReviewPreparation|None=None


_request_full_source_reads = ContextVar('request_full_source_reads', default=None)


@contextmanager
def request_full_source_read_reuse():
    """Share complete source readings within one synchronous native query."""
    token = _request_full_source_reads.set({})
    try:
        yield
    finally:
        _request_full_source_reads.reset(token)


@stage_timing('review_read_sources_full')
def read_sources(intake,principal,sources):
    from .domain_intake import SourceProjectRequest
    from .native_formula_timing import timed_call
    from ..governed_runtime.source_field_read_contract import SourceFieldBatchReadRequest
    from ..governed_runtime.source_field_projection import SourceFieldProjectionService
    projections=[]
    cache=_request_full_source_reads.get()
    for ref in sources:
        source=ArtifactEnvelope.model_validate(ref)
        envelope=source.model_dump(mode='json')
        key=(id(intake),id(principal),semantic_digest(envelope))
        cached=cache.get(key) if cache is not None else None
        if cached is not None and cached[0] is intake and cached[1] is principal:
            authorization=intake._authorization(principal)
            if authorization.policy_digest==cached[2]['manifest']['policy_digest']:
                # Rights and original bytes are checked again on every reuse.
                SourceFieldProjectionService(intake.source_intake)._authorize(
                    authorization,envelope,model_input=True)
                projections.append(copy.deepcopy(cached[2]))
                continue
        manifest=timed_call('review_full_source_project',intake.project,
            principal,SourceProjectRequest(reference=source));fields=[]
        for start in range(0,len(manifest['fields']),128):
            group=manifest['fields'][start:start+128]
            texts={field['span_ref']:'' for field in group}
            pending=SourceFieldBatchReadRequest(reference=source,
                fields=[{'span_ref':field['span_ref'],'limit':8192} for field in group],
                max_characters=65536)
            while pending is not None:
                # Each bounded batch uses the existing current source grant,
                # immutable span bindings and content-digest checks. Preserve
                # the complete legacy manifest, field order and Unicode text.
                batch=timed_call('review_full_source_batch_read',intake.read_field,
                    principal,pending)
                for part in batch['fields']:
                    span=part['span_ref']
                    if span not in texts or part['offset']!=len(texts[span]):
                        raise ValueError('PROCESS_SOURCE_PAGE_INVALID')
                    texts[span]+=part['text']
                    if part['next_offset'] is not None and part['next_offset']<=part['offset']:
                        raise ValueError('PROCESS_SOURCE_PAGE_INVALID')
                following=batch['continuation']
                next_request=SourceFieldBatchReadRequest.model_validate(following) if following else None
                if next_request==pending:raise ValueError('PROCESS_SOURCE_PAGE_INVALID')
                pending=next_request
            for field in group:
                text=texts[field['span_ref']]
                if len(text)!=field['character_count'] or byte_digest(text.encode('utf-8'))!=field['content_digest']:
                    raise ValueError('PROCESS_SOURCE_FIELD_INCOMPLETE_OR_CHANGED')
                fields.append({**field,'text':text})
        projection={'source':envelope,'manifest':manifest,'fields':fields}
        if cache is not None and isinstance(manifest.get('policy_digest'),str):
            cache[key]=(intake,principal,copy.deepcopy(projection))
        projections.append(projection)
    return projections



@stage_timing('review_read_recorded_sources')
def read_recorded_sources(intake,principal,sources,recorded):
    """Restore recorded source projections; never replace old spans by new ones."""
    from ..governed_runtime.source_field_projection import SourceFieldProjectionService
    anchors={}
    def visit(value):
        if isinstance(value,dict):
            if isinstance(value.get('source_revision_digest'),str) and isinstance(value.get('span_ref'),str):
                anchors.setdefault(value['source_revision_digest'],value['span_ref'])
            for child in value.values():visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(recorded)
    projector=SourceFieldProjectionService(intake.source_intake)
    authorization=intake._authorization(principal);result=[]
    for source in sources:
        envelope=ArtifactEnvelope.model_validate(source).model_dump(mode='json')
        anchor=anchors.get(envelope['digest'])
        result.append(projector.restore_projection_from_span(authorization=authorization,
            reference=envelope,span_ref=anchor) if anchor else read_sources(intake,principal,[source])[0])
    if 'source_reading_digests' in recorded and [semantic_digest(s) for s in result]!=recorded['source_reading_digests']:
        raise ValueError('PROCESS_RESULT_RECORDED_SOURCE_READING_MISMATCH')
    return result


class RequestSourceReader:
    """Reuse only reads obtained by this request's intake and principal.

    No caller-supplied projection or cross-request cache is accepted. Complete
    envelopes distinguish revisions, references and roles; failed reads are not
    retained. Copies prevent consumers from changing the next consumer's source.
    """
    def __init__(self, intake, principal):
        self._intake = intake
        self._principal = principal
        self._reads = {}
        self._source_names = {}

    def source_display_names(self):
        # Navigation labels are not part of the original reading digest or
        # a new claim. Reuse the inventory already authorized by this reader.
        return {digest:next(iter(names)) for digest,names in self._source_names.items()
            if len(names)==1}

    def read(self, intake, principal, sources):
        import copy
        if intake is not self._intake or principal is not self._principal:
            raise ValueError('SOURCE_REUSE_REQUEST_MISMATCH')
        result = []
        for ref in sources:
            envelope = ArtifactEnvelope.model_validate(ref).model_dump(mode='json')
            key = semantic_digest(envelope)
            if key not in self._reads:
                self._reads[key] = read_sources(intake, principal, [envelope])[0]
            result.append(copy.deepcopy(self._reads[key]))
        return result

    @stage_timing('review_source_read_for_assets')
    def read_for_assets(self, intake, principal, sources, assets, *, additional_field_refs=None,
            meaning_closures=None):
        """Use source-record dependencies of actual authorized definitions.

        Sources without importer provenance retain the complete projection,
        restoring recorded spans when available. Mixed declarations cannot
        silently narrow such a source.
        """
        import copy
        from ..governed_runtime.source_field_projection import SourceFieldProjectionService
        if intake is not self._intake or principal is not self._principal:
            raise ValueError('SOURCE_REUSE_REQUEST_MISMATCH')
        # Retain the current space-policy reader for published assets. A bare
        # native store intentionally rejects them, even for their owner. Source
        # projection below still enforces its separate original-source grant.
        auth,work=intake._work(principal)
        store=work.assets
        stored=[store.read(authorization=auth,revision=RevisionRef.model_validate(
            asset.revision if hasattr(asset,'revision') else asset),lane='provisional') for asset in assets]
        result=[]
        for source in sources:
            envelope=ArtifactEnvelope.model_validate(source).model_dump(mode='json')
            owners=[asset for asset in stored if envelope in asset['sources']]
            published=[]
            for asset in owners:
                content=json.loads(asset['asset']['content_json'])
                if (isinstance(content,dict) and content.get('contract_version')=='boi/knowledge-content@1'
                        and getattr(work,'knowledge_spaces',None) is not None):
                    from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader
                    if PublishedKnowledgeReader(work.knowledge_spaces).is_published(
                            RevisionRef.model_validate(asset['revision'])):
                        published.append(asset)
            if published:
                if len(published)!=len(owners):
                    raise ValueError('SOURCE_MIXED_CONTRACT_REQUIRES_SEPARATE_READING')
                from .published_original_reading import read_published_original_fields
                result.append(read_published_original_fields(work,principal,auth,published,envelope,
                    extra_refs=(additional_field_refs or {}).get(envelope['digest'],()),
                    meaning_closures=meaning_closures))
                continue
            projections=[]
            for asset in owners:
                content=json.loads(asset['asset']['content_json'])
                record=content.get('source_record') if isinstance(content,dict) else None
                if not isinstance(record,dict):
                    projections=[];break
                dependencies=[d for d in asset['asset']['dependencies'] if d['role']=='source_inventory']
                if len(dependencies)!=1:raise ValueError('SOURCE_RECORD_INVENTORY_AMBIGUOUS')
                inventory=store.read(authorization=auth,
                    revision=RevisionRef.model_validate(dependencies[0]['revision']),lane='provisional')
                index=json.loads(inventory['asset']['content_json'])
                if (inventory['asset']['kind']!='source' or index.get('contract_version')!='boi/workbook-source-index@1'
                        or inventory['sources']!=[envelope] or index.get('source')!=envelope):
                    raise ValueError('SOURCE_RECORD_INVENTORY_MISMATCH')
                if isinstance(index.get('file_name'),str) and index['file_name'].strip():
                    self._source_names.setdefault(envelope['digest'],set()).add(index['file_name'])
                refs=[*record['field_refs'],*record['context_refs'],
                    *[e['ref'] for e in asset['asset']['evidence']]]
                projections.append((index['manifest_ref'],refs,record['record_locator'],record['field_refs']))
                # Explicitly quoted comparison records retain their complete
                # local fields and correction context, with independent source
                # membership. This is evidence access, not scope inheritance.
                for related in content.get('source_record_dependencies',[]):
                    if (related.get('role')!='quoted_source_context' or related.get('scope_inherited') is not False
                            or related.get('semantic_relation_verified') is not False
                            or not related.get('evidence_use_pointers')):
                        raise ValueError('SOURCE_RELATED_RECORD_SCOPE_INVALID')
                    projections.append((index['manifest_ref'],[*related['field_refs'],*related['context_refs']],
                        related['record_locator'],related['field_refs']))
            if not projections:
                # Native definitions already cite immutable source spans. Use
                # the existing complete-projection restorer instead of trying
                # to append the same fields and rechecking the entire ledger
                # on every authority fence. No recorded anchor means the
                # original full-source path; an invalid anchor fails closed.
                key=semantic_digest(['complete_recorded_projection',envelope,
                    [asset['revision'] for asset in owners]])
                if key not in self._reads:
                    recorded={'assets':[json.loads(asset['asset']['content_json']) for asset in owners]}
                    self._reads[key]=read_recorded_sources(intake,principal,[envelope],recorded)[0]
                result.append(copy.deepcopy(self._reads[key]));continue
            if len({p[0] for p in projections})!=1:
                raise ValueError('SOURCE_RECORD_PROJECTION_AMBIGUOUS')
            refs=list(dict.fromkeys(ref for _,values,_,_ in projections for ref in values))
            # Protected literal citation groups may address another field in
            # this same immutable source. Keep the definition's full record and
            # declared context, then add only those exact fields. The manifest
            # reader checks source membership and current rights for the union.
            refs=list(dict.fromkeys([*refs, *(additional_field_refs or {}).get(envelope['digest'], ())]))
            key=semantic_digest([envelope,projections[0][0],refs])
            if key not in self._reads:
                projector=SourceFieldProjectionService(intake.source_intake)
                reading=projector.read_selected_fields(
                    authorization=auth,reference=envelope,manifest_ref=projections[0][0],span_refs=refs,
                    required_records=[(locator, own) for _, _, locator, own in projections])
                fields={f['span_ref']:f for f in reading['fields']}
                for _,_,locator,own in projections:
                    if not own or any(fields[ref]['record_locator']!=locator for ref in own):
                        raise ValueError('SOURCE_RECORD_MEMBERSHIP_MISMATCH')
                self._reads[key]=reading
            result.append(copy.deepcopy(self._reads[key]))
        return result

def validate_reuse_review_prompt(prompt,material):
    from agent_kit.python.boi_process_claim_review import definition_reuse_review_prompt,reuse_review_view
    from ..governed_runtime.native_observation import _json
    instructions,separator,payload=prompt.partition('\n')
    expected=definition_reuse_review_prompt(material).partition('\n')[0]
    if not separator or instructions!=expected:
        raise ValueError('review_reuse_instructions_mismatch')
    # Source serialization can reorder keys across API/context boundaries.
    # Keep exact instructions and complete JSON values, rejecting duplicate keys.
    if _json(payload)!=reuse_review_view(material):
        raise ValueError('review_reuse_delivered_scope_mismatch')


def native_reuse_material(content, *, evidence, context, sources):
    """Recompute saved input against ACL-read sources and acknowledged context.

    The caller must supply the immutable candidate and authoritative reads.
    Matching output proves reproducibility only, never historical execution.
    """
    from agent_kit.python.boi_process_reuse import bind_process_reuse
    from agent_kit.python.boi_process_reuse_evaluation import verified_reuse_material
    record=content.get('native_binding_input')
    if (not isinstance(record,dict) or
            set(record)!={'contract_version','proposal','proposal_digest','bound_digest','execution_attested'} or
            record['contract_version']!='boi/native-process-binding-input@1' or
            record['execution_attested'] is not False or content.get('execution_refs')!=[]):
        raise ValueError('review_native_binding_input_invalid_or_ambiguous')
    if semantic_digest(record['proposal'])!=record['proposal_digest']:
        raise ValueError('review_native_binding_proposal_digest_mismatch')
    bound=bind_process_reuse(record['proposal'],evidence=evidence,context=context,sources=sources)
    if (semantic_digest(bound)!=record['bound_digest'] or
            any(content.get(k)!=v for k,v in bound.items())):
        raise ValueError('review_native_candidate_replay_mismatch')
    return verified_reuse_material(proposal=record['proposal'],bound=bound,
        evidence=evidence,context=context,sources=sources)


def read_process_review_binding(intake,principal,request,*,_trail=()):
    from .domain_intake import DomainAssetReadRequest
    from agent_kit.python.boi_process_claim_review import (assessment_targets,source_review_selection,dependent_nodes,
        SourceNodeJudgment,SourceFieldCoverage)
    from agent_kit.python.boi_process_review_observation import observe_source_review
    from agent_kit.python.boi_process_user_result import review_asset_binding_errors

    authorization,work=intake._work(principal)
    if request.preparation is not None:
        if request.review_revision is not None:raise ValueError('PROCESS_REVIEW_INPUT_MODE_AMBIGUOUS')
        from .published_native_process_review import (
            is_published_native_process_review, prepare_published_native_process_review,
        )
        if is_published_native_process_review(intake,principal,request.candidate_revision):
            prepared=prepare_published_native_process_review(intake,principal,
                definition_revision=request.candidate_revision,
                **request.preparation.model_dump(mode='json'))
        else:
            from .native_process_review import prepare_native_process_review
            prepared=prepare_native_process_review(intake,principal,definition_revision=request.candidate_revision,
                **request.preparation.model_dump(mode='json'))
        return {'status':'review_prepared',**{k:prepared[k] for k in ('definition_revision','scope','request')},
            **({'review_contract_kind':prepared['review_contract_kind']}
               if 'review_contract_kind' in prepared else {}),
            'review_required':bool(prepared['scope']['target_pointers'] or prepared['scope']['field_locators']),
            'scope_kind':'internal_native_caller_selected_roots_and_required_closure',
            'new_model_runs':0,'new_review_receipts':0,'whole_plan_qualified':False}
    native=None
    if request.review_revision is not None:
        native=intake.read_asset(principal,DomainAssetReadRequest(revision=request.review_revision,lane='provisional'))
        value=json.loads(native['asset']['content_json'])
        if isinstance(value,dict) and value.get('contract_version')=='boi/native-agent-observation@1':
            review_contract=json.loads(value['value_json']).get('contract_version')
            if review_contract in ('boi/native-definition-review@2','boi/native-definition-review@3'):
                from .native_process_review import read_native_process_review_binding
                result=read_native_process_review_binding(intake,principal,request.review_revision)
                if result['candidate_revision']!=request.candidate_revision.model_dump(mode='json'):
                    raise ValueError('NATIVE_PROCESS_REVIEW_CANDIDATE_MISMATCH')
                return {k:v for k,v in result.items() if k not in ('context','sources','candidate_content')}
            if review_contract=='boi/native-definition-review@4':
                from .published_native_process_review import read_published_native_process_review_binding
                result=read_published_native_process_review_binding(intake,principal,request.review_revision)
                if result['candidate_revision']!=request.candidate_revision.model_dump(mode='json'):
                    raise ValueError('PUBLISHED_NATIVE_REVIEW_DEFINITION_MISMATCH')
                return {k:v for k,v in result.items() if k not in ('context','sources','candidate_content')}
    def asset(ref):return intake.read_asset(principal,DomainAssetReadRequest(revision=ref,lane='provisional'))
    candidate=asset(request.candidate_revision);content=json.loads(candidate['asset']['content_json'])
    problems=[];executions=[];nodes=[];native_observations=[]
    if not isinstance(content,dict):
        problems.append('candidate_content_not_an_object');content={}
    draft=content.get('draft')
    if draft:
        try:nodes=assessment_targets(draft,include_all_terms=True)
        except (ValueError,TypeError,KeyError):problems.append('candidate_process_draft_invalid')
    pointers=[n['target_pointer'] for n in nodes]
    review=native
    material=json.loads(review['asset']['content_json']) if review else {}
    if material.get('contract_version')=='boi/process-source-meaning-alignment@2':
        from .process_coverage import read_repaired_review_binding
        return read_repaired_review_binding(intake,principal,candidate,review,_trail=_trail)
    problems.extend(review_asset_binding_errors(candidate,review,material))
    base={'contract_version':'boi/process-review-binding@1','candidate_revision':candidate['revision'],
        'review_revision':review['revision'] if review else None,'status':'unconfirmed','reason_codes':problems,
        'usable_node_pointers':[],'quarantined_node_pointers':pointers,'execution_refs':executions,
        'native_observation_provenance':native_observations,
        'authority':'wiki_reference_check','source_fidelity':'model_opinion_only',
        'scientific_correctness':'not_evaluated','canonical_projection_eligible':False,
        'new_model_runs':0,'new_review_receipts':0,'whole_plan_qualified':False}
    if problems:return base
    if request.candidate_revision.ref in _trail or len(_trail)>=16:
        problems.append('review_history_cycle_or_limit');return base
    if not draft:
        problems.append('process_candidate_draft_missing');return base

    sources=[ArtifactEnvelope.model_validate(s) for s in candidate['sources']]
    source_views=read_recorded_sources(intake,principal,sources,content)
    evidence=next((s for s in source_views if s['source']['digest']==draft['source_revision_digest']),None)
    if evidence is None:
        problems.append('primary_source_revision_not_in_candidate');return base

    def reading(ref,refs):
        return work.contexts.validate_reading(authorization=authorization,revision=RevisionRef.model_validate(ref),
            sources=[ArtifactEnvelope.model_validate(s) for s in refs],require_current=False).model_dump(mode='json')

    def observed(run):
        """Resolve recorded bytes; preserve the difference between origin types."""
        if 'native_observation_revision' in run:
            if 'wiki_execution_ref' in run:raise ValueError('review_observation_origin_ambiguous')
            from ..governed_runtime.native_observation import read_native_observation
            native=read_native_observation(work,authorization,run['native_observation_revision'])
            data=native['request'];value=native['value']
            native_observations.append(native['provenance'])
        else:
            execution=work.read_evidence(authorization=authorization,
                request=DomainToolEvidenceRequest(execution_ref=run['wiki_execution_ref']))
            body=execution['execution']['signed_execution']['body']
            if body['outcome']!='completed':raise ValueError('review_execution_not_completed')
            result=json.loads(execution['output_json'])['result']
            if result.get('contract_version')!='boi/model-observation@1' or result['provider_run']['status']!='completed':
                raise ValueError('review_model_observation_not_completed')
            package=work._package(authorization,body['invocation']['task_revision']['ref'],require_current=False)
            inputs=package['domain_execution_contract']['inputs']
            data=json.loads(next(i['content_json'] for i in inputs if i['kind']=='proposal' and i['name']=='request'))
            if (result['input_digest']!=semantic_digest(data) or
                    result['provider_run']['prompt_digest']!=byte_digest(data['prompt'].encode()) or
                    result['provider_run']['output_digest']!=byte_digest(result['value_json'].encode())):
                raise ValueError('review_observation_input_or_output_digest_mismatch')
            value=json.loads(result['value_json'])
            executions.append(execution['execution_ref'])
        if (candidate['revision'] not in data['input_revisions'] or content['harness_revision'] not in data['input_revisions'] or
                data['source_manifest_digest']!=source_manifest_digest(sources)):
            raise ValueError('review_execution_candidate_or_source_mismatch')
        context=reading(data['knowledge_reading_ref'],candidate['sources'])
        context_refs=[a['revision'] for a in context['assets']]
        required=[candidate['revision'],content['harness_revision'],*content.get('definition_comparison_revisions',[])]
        if any(ref not in context_refs for ref in required):raise ValueError('review_required_revision_not_read')
        return value,data

    try:
        candidate_context=reading(candidate['definition_reading_ref'],candidate['sources'])
        review_context=reading(review['definition_reading_ref'],review['sources'])
        if candidate['revision'] not in [a['revision'] for a in review_context['assets']]:
            raise ValueError('review_candidate_missing_from_acknowledged_reading')
        if candidate_context['context_digest']!=draft['extraction_context_digest']:
            raise ValueError('candidate_extraction_reading_mismatch')
        record=material['source_observation'];attempts=record['attempts']
        if record['candidate_draft_digest']!=semantic_digest(draft):raise ValueError('review_candidate_draft_digest_mismatch')
        if not 1<=len(attempts)<=3:raise ValueError('review_attempt_scope_missing_or_excessive')
        supported_raw={};field_raw={}
        from agent_kit.python.boi_process_claim_review import (source_review_material,source_review_prompt,
            SOURCE_REVIEW_INSTRUCTIONS,ProcessSourceReview)
        from agent_kit.python.boi_structured_provider import strict_output_schema
        expected=json.loads(json.dumps(source_review_material(draft,evidence,candidate_context)))
        expected['review_instructions_version']=record['review_instructions_version']
        if record['review_instructions_version']=='boi/process-source-review-instructions@9':
            from agent_kit.python.boi_process_claim_review import source_review_history_delivery
            expected=source_review_history_delivery(expected)
        prior_ref=material['check'].get('source_review',{}).get('prior_review_revision')
        if prior_ref:
            prior_asset=asset(RevisionRef.model_validate(prior_ref))
            prior_material=json.loads(prior_asset['asset']['content_json'])
            prior_candidate=asset(RevisionRef.model_validate(prior_material['check']['candidate_revision']))
            if candidate['previous_revision']!=prior_candidate['revision']:
                raise ValueError('review_carried_candidate_not_previous_revision')
            prior_binding=read_process_review_binding(intake,principal,ProcessReviewBindingRequest(
                candidate_revision=prior_candidate['revision'],review_revision=prior_asset['revision']),
                _trail=(*_trail,request.candidate_revision.ref))
            prior_content=json.loads(prior_candidate['asset']['content_json'])
            prior_context=reading(prior_candidate['definition_reading_ref'],prior_candidate['sources'])
            relevant=lambda ctx:[a for a in ctx['assets'] if a['kind'] in ('definition','harness','profile','skill')]
            # No semantic equivalence is inferred across changed definitions or
            # contracts. Carry only byte-identical nodes in the same read scope.
            if (relevant(prior_context)==relevant(candidate_context) and prior_binding['status'] in ('bound','partially_bound')
                    and prior_material.get('source_observation',{}).get('review_instructions_version')==record['review_instructions_version']):
                prior_nodes={n['target_pointer']:n for n in assessment_targets(prior_content['draft'],include_all_terms=True)}
                same_nodes={n['target_pointer'] for n in nodes if prior_nodes.get(n['target_pointer'])==n}
                usable=set(prior_binding['usable_node_pointers']) & same_nodes
                supported_raw={c['target_pointer']:c for c in prior_material['source_assessment']['claims'] if c['target_pointer'] in usable}
                prior_sources=read_recorded_sources(intake,principal,prior_candidate['sources'],json.loads(prior_candidate['asset']['content_json']))
                prior_evidence=next(s for s in prior_sources if s['source']['digest']==prior_content['draft']['source_revision_digest'])
                prior_fields={f['field_locator']:f['text'] for f in prior_evidence['fields']}
                same_fields={f['field_locator'] for f in evidence['fields'] if prior_fields.get(f['field_locator'])==f['text']}
                field_raw={f['field_locator']:f for f in prior_material['source_assessment']['fields']
                    if f['field_locator'] in same_fields and set(f['target_pointers'])<=usable
                    and f['field_locator'] not in prior_binding.get('unbound_field_locators',[])}
                executions.extend(prior_binding['execution_refs'])
                native_observations.extend(prior_binding.get('native_observation_provenance',[]))
        def resolved_attempts():
            """Verify every batch receipt; batching never relaxes review scope."""
            for attempt_index,attempt in enumerate(attempts):
                run=attempt['provider']
                if run.get('method')!='bounded_source_review':
                    raw,data=observed(run)
                    yield attempt_index,attempt,raw,data,ProcessSourceReview.model_json_schema()
                    continue
                limit=run.get('max_targets_per_call')
                if (run.get('batch_contract_version')!='boi/source-review-batches@1'
                        or type(limit) is not int or not 1<=limit<=16):
                    raise ValueError('review_batch_contract_invalid')
                selected=attempt['selection'];targets=selected['targets'];fields=selected['fields']
                groups=[(targets[i:i+limit],[]) for i in range(0,len(targets),limit)]
                groups.extend(([],fields[i:i+limit]) for i in range(0,len(fields),limit))
                batches=run['batches']
                if not groups or len(batches)!=len(groups):raise ValueError('review_batch_coverage_mismatch')
                merged={'contract_version':'boi/process-operational-source-review@1','claims':[],'fields':[],'limitations':[]}
                for index,(batch,(nodes,locators)) in enumerate(zip(batches,groups)):
                    pointers=[n['target_pointer'] for n in nodes]
                    if batch['index']!=index or batch['target_pointers']!=pointers or batch['field_locators']!=locators:
                        raise ValueError('review_batch_partition_mismatch')
                    raw,data=observed(batch['provider'])
                    if (raw.get('contract_version',merged['contract_version'])!=merged['contract_version']
                            or any(c['target_pointer'] not in pointers for c in raw.get('claims',[]))
                            or any(f['field_locator'] not in locators for f in raw.get('fields',[]))):
                        raise ValueError('review_batch_observation_scope_mismatch')
                    carried=list(selected['carry_forward_nodes'])
                    if locators:carried.extend(c['target_pointer'] for c in merged['claims'])
                    part={**attempt,'selection':{**selected,'targets':nodes,'fields':locators,'carry_forward_nodes':carried},
                        'observation':{'raw_assessment':raw}}
                    schema=ProcessSourceReview.model_json_schema()
                    schema['properties']['claims']['maxItems']=len(nodes)
                    schema['properties']['fields']['maxItems']=len(locators)
                    yield attempt_index,part,raw,data,schema
                    for key in ('claims','fields','limitations'):merged[key].extend(raw.get(key,[]))
                if merged!=attempt['observation']['raw_assessment']:
                    raise ValueError('review_batch_aggregate_not_admitted_outputs')

        for attempt_index,attempt,raw,data,expected_schema in resolved_attempts():
            if data['review_contract_version']!=record['review_instructions_version']:
                raise ValueError('review_contract_version_mismatch')
            if raw!=attempt['observation']['raw_assessment'] or attempt['candidate_draft_digest']!=semantic_digest(draft):
                raise ValueError('review_stored_observation_not_admitted_output')
            # This versioned producer emits its complete structured material
            # after one instruction paragraph. Compare data, not prose keywords.
            delivered=json.loads(data['prompt'].split('\n',1)[1])
            if record['review_instructions_version'] not in SOURCE_REVIEW_INSTRUCTIONS or data['prompt']!=source_review_prompt(delivered,version=record['review_instructions_version']):
                raise ValueError('review_instructions_not_exact_supported_contract')
            if record['review_instructions_version'] in ('boi/process-source-review-instructions@8','boi/process-source-review-instructions@9'):
                from agent_kit.python.boi_process_claim_review import source_review_contract_delivery
                delivered=source_review_contract_delivery(delivered,expand=True)
            if record['review_instructions_version'] in ('boi/process-source-review-instructions@6','boi/process-source-review-instructions@7','boi/process-source-review-instructions@8','boi/process-source-review-instructions@9'):
                from agent_kit.python.boi_process_claim_review import source_review_delivery
                delivered=source_review_delivery(delivered,expand=True)
            if json.loads(data['output_schema_json'])!=strict_output_schema(expected_schema):
                raise ValueError('review_output_schema_not_exact_contract')
            allowed=set(expected)|{'all_current_nodes_for_field_coverage','carried_node_judgments','field_locators_to_assess'}
            if attempt_index:allowed|={'previous_review_protocol_errors','correction_scope'}
            if set(delivered)!=allowed:raise ValueError('review_material_field_contract_mismatch')
            for key in set(expected)-{'targets','read_definitions_and_contracts'}:
                if delivered.get(key)!=expected[key]:raise ValueError('review_delivered_'+key+'_mismatch')
            if delivered['all_current_nodes_for_field_coverage']!=expected['targets']:
                raise ValueError('review_complete_coverage_node_scope_mismatch')
            carried=delivered['carried_node_judgments']
            carry_pointers=set(attempt['selection']['carry_forward_nodes'])
            if len({c['target_pointer'] for c in carried})!=len(carried) or {c['target_pointer']:c for c in carried}!={p:c for p,c in supported_raw.items() if p in carry_pointers}:
                raise ValueError('review_delivered_carried_judgments_unbound')
            actual_assets=delivered['read_definitions_and_contracts']['assets']
            expected_assets=expected['read_definitions_and_contracts']['assets']
            if sorted(semantic_digest(a['revision']) for a in actual_assets)!=sorted(semantic_digest(a['revision']) for a in expected_assets):
                raise ValueError('review_delivered_asset_inventory_mismatch')
            for key in ('context_digest','source_manifest_digest','selections'):
                if delivered['read_definitions_and_contracts'][key]!=expected['read_definitions_and_contracts'][key]:
                    raise ValueError('review_delivered_read_scope_mismatch')
            for item in expected_assets:
                if record['review_instructions_version']=='boi/process-source-review-instructions@9':
                    matches=[a for a in actual_assets if a['revision']==item['revision']]
                    if matches!=[item]:raise ValueError('review_delivered_asset_projection_mismatch')
                    continue
                if item['kind'] in ('definition','harness','profile','skill'):
                    matches=[a for a in actual_assets if a['revision']==item['revision']]
                    if len(matches)!=1 or matches[0]['original_content_digest']!=item['original_content_digest'] or matches[0]['read_projection']!=item['read_projection']:
                        raise ValueError('review_delivered_definition_or_contract_mismatch')
            selected=attempt['selection'];selected_pointers={n['target_pointer'] for n in selected['targets']}
            if delivered['targets']!=[n for n in expected['targets'] if n['target_pointer'] in selected_pointers]:
                raise ValueError('review_selected_node_scope_mismatch')
            if delivered['field_locators_to_assess']!=selected['fields']:raise ValueError('review_selected_field_scope_mismatch')
            for claim in raw.get('claims',[]):
                try:normalized=SourceNodeJudgment.model_validate(claim).model_dump(mode='json')
                except ValueError:continue
                supported_raw[normalized['target_pointer']]=normalized
            for field in raw.get('fields',[]):
                try:normalized=SourceFieldCoverage.model_validate(field).model_dump(mode='json')
                except ValueError:continue
                field_raw[normalized['field_locator']]=normalized
        final=material['source_assessment']
        # Partial corrections must retain actual preceding observations. A
        # carried judgment without its receipt cannot qualify another node.
        unbound=[c['target_pointer'] for c in final['claims'] if supported_raw.get(c['target_pointer'])!=c]
        unbound_fields=[f['field_locator'] for f in final['fields'] if field_raw.get(f['field_locator'])!=f]
        validated=observe_source_review(final,draft=draft,evidence=evidence,selection=source_review_selection(draft,evidence),
            reference_contract_version=record.get('reference_contract_version','boi/source-coverage-references@1'))
        check=validated['check'];quarantined=dependent_nodes(draft,[*check['quarantined_node_pointers'],*unbound])
        if unbound:problems.append('carried_node_observation_binding_missing')
        if unbound_fields:problems.append('carried_field_observation_binding_missing')
        # Definition-use review qualification remains a separate mandatory
        # check. Never turn absent evidence for proposed uses into no failures.
        uses=content.get('definition_uses',[])
        failed_uses=[];reuse_check={'assessment_complete':True,'model_assessment_accepts_definition_uses':True}
        if uses:
            try:
                from agent_kit.python.boi_process_reuse_evaluation import verified_reuse_material,check_reuse_assessment,ProcessReuseAssessment
                raw,data=observed(material['check']['provider_run'])
                if raw!=material['assessment']:raise ValueError('review_reuse_observation_not_admitted_output')
                if 'native_binding_input' in content:
                    reuse_material=native_reuse_material(content,evidence=evidence,
                        context=candidate_context,sources=source_views)
                    base['candidate_structural_binding']={
                        'method':'authoritative_input_recomputation',
                        'proposal_digest':reuse_material['proposal_digest'],
                        'bound_digest':reuse_material['bound_digest'],
                        'execution_attested':False,'semantic_truth_proven':False}
                else:
                    extraction=work.read_evidence(authorization=authorization,
                        request=DomainToolEvidenceRequest(execution_ref=content['execution_refs'][0]))
                    extraction_body=extraction['execution']['signed_execution']['body']
                    extracted=json.loads(extraction['output_json'])
                    if extraction_body['outcome']!='completed' or not extracted.get('checks') or any(c['status']!='pass' for c in extracted['checks']):
                        raise ValueError('review_candidate_binding_execution_not_completed')
                    bound=extracted['result']
                    if any(content.get(k)!=v for k,v in bound.items()):
                        raise ValueError('review_candidate_not_admitted_binding_output')
                    package=work._package(authorization,extraction_body['invocation']['task_revision']['ref'],require_current=False)
                    proposal=json.loads(next(i['content_json'] for i in package['domain_execution_contract']['inputs']
                        if i['kind']=='proposal' and i['name']=='draft'))
                    # Reproduce the admitted tool's exact projection payload. A
                    # current source-read response adds manifest_ref/digest envelope
                    # fields that were not part of that historical tool input.
                    # Hashing that response instead changes the source partition.
                    # Existing input resolution still checks present access, the
                    # pinned manifest revision and every original field digest.
                    from ..governed_runtime.task_knowledge import TaskKnowledgeContext
                    execution_contract=package['domain_execution_contract']
                    invocation=extraction_body['invocation']
                    def projection_input(name,kind):
                        spec=next(i for i in execution_contract['inputs'] if i['name']==name and i['kind']==kind)
                        expected_input=next(i for i in invocation['inputs'] if i['name']==name)
                        revision,payload=work._input(authorization,spec,execution_contract,
                            TaskKnowledgeContext.model_validate(candidate_context),
                            task_revision=RevisionRef.model_validate(invocation['task_revision']))
                        if revision.model_dump(mode='json')!=expected_input['revision'] or byte_digest(payload)!=expected_input['content_digest']:
                            raise ValueError('review_projection_input_not_admitted_bytes')
                        return json.loads(payload)
                    execution_evidence=projection_input('evidence','source_projection')
                    execution_sources=(projection_input('sources','source_projection_bundle')
                        if any(i['name']=='sources' for i in execution_contract['inputs']) else [execution_evidence])
                    reuse_material=verified_reuse_material(proposal=proposal,bound=bound,evidence=execution_evidence,
                        context=candidate_context,sources=execution_sources)
                validate_reuse_review_prompt(data['prompt'],reuse_material)
                if json.loads(data['output_schema_json'])!=strict_output_schema(ProcessReuseAssessment.model_json_schema()):
                    raise ValueError('review_reuse_output_schema_mismatch')
                reuse_check=check_reuse_assessment(raw,material=reuse_material)
                if 'native_observation_revision' in material['check']['provider_run']:
                    reuse_check['semantic_judgment_method']='current_session_native_opinion_against_complete_supplied_sources'
                failed_uses=[u['use_pointer'] for u in raw['uses'] if any(j['label']!='supported' for j in u['judgments'])]
            except (ValueError,KeyError,StopIteration,TypeError) as exc:
                failed_uses=[f'/definition_uses/{i}' for i in range(len(uses))]
                reuse_check={'assessment_complete':False,'model_assessment_accepts_definition_uses':False}
                problems.append('definition_use_execution_binding_unconfirmed')
                if isinstance(exc,ValueError) and str(exc) in {
                    'review_reuse_observation_not_admitted_output','review_reuse_delivered_scope_mismatch',
                    'review_reuse_instructions_mismatch','review_reuse_output_schema_mismatch',
                    'PROCESS_REUSE_EVAL_USE_COVERAGE_INCOMPLETE','PROCESS_REUSE_EVAL_DIMENSION_COVERAGE_INCOMPLETE',
                    'PROCESS_REUSE_EVAL_POSITIVE_COMPARISON_MISSING_SOURCE_SIDE'}:
                    problems.append(str(exc))
            quarantined=dependent_nodes(draft,[*quarantined,*[u['term_pointer'] for i,u in enumerate(uses)
                if f'/definition_uses/{i}' in failed_uses and u['application']=='interpret_term']])
        if unbound or unbound_fields:
            check={**check,'assessment_complete':False,'model_assessment_accepts_source_fidelity':False}
        base.update(status='bound' if not problems else 'partially_bound',
            source_review=check,usable_node_pointers=sorted(set(check['usable_node_pointers'])-set(quarantined)),
            quarantined_node_pointers=quarantined,unbound_field_locators=unbound_fields,
            check={**reuse_check,'candidate_revision':candidate['revision'],'failed_use_pointers':failed_uses,
                'source_review':{**check,'quarantined_node_pointers':quarantined,
                    'usable_node_pointers':sorted(set(check['usable_node_pointers'])-set(quarantined))}},
            review_contract_version=record['review_instructions_version'],
            historical_reading=True,review_execution_binding=(
                'authenticated_native_observation_and_exact_inputs' if native_observations
                else 'admitted_output_and_exact_structured_inputs'))
    except (ValueError,KeyError,StopIteration,TypeError) as exc:
        # No rejected source values or inaccessible content in the response.
        code=str(exc) if isinstance(exc,ValueError) and str(exc).startswith(('review_','candidate_')) else 'review_binding_material_unavailable_or_invalid'
        problems.append(code)
    return base
