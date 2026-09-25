"""Wiki-side binding of stored answer reviews and bounded correction chains.

Verify admitted review/patch observations, exact prior failures and carried
judgments through authorized historical reads. Execution identity, assessment
validity and semantic/scientific truth remain separate. Unsupported, incomplete
or tampered chains stay unconfirmed; reading never dispatches model work.
"""
import json
from ..governed_runtime.semantic_binding_contract import RevisionRef, semantic_digest
from ..governed_runtime.source_envelope import byte_digest, ArtifactEnvelope
from ..governed_runtime.domain_asset_store import source_manifest_digest
from ..governed_runtime.domain_work_contract import DomainToolEvidenceRequest


def _verified_provider_output(work,authorization,stored,packet,observation,execution_ref):
    """A raw artifact may prove the historical universal-newline conversion.

    Never waive a digest mismatch. The artifact must match the original signed
    provider digest, and its only transformation must produce the exact stored
    string. A new answer revision records this supplemental provenance.
    """
    text=observation['value_json'];expected=observation['provider_run']['output_digest']
    if byte_digest(text.encode('utf-8'))==expected:return None
    proof=packet.get('provider_output_recovery')
    if (not isinstance(proof,dict) or proof.get('contract_version')!='boi/provider-output-byte-recovery@1'
            or proof.get('transformation')!='python-universal-newlines'
            or proof.get('execution_ref')!=execution_ref
            or proof.get('base_answer_revision')!=stored.get('previous_revision')):
        raise ValueError('answer_review_raw_output_evidence_required')
    source=ArtifactEnvelope.model_validate(proof['raw_output_source'])
    if source.digest!=expected:raise ValueError('answer_review_raw_output_digest_mismatch')
    raw=work.intake.resolve_bytes(authorization=authorization,reference=source.model_dump(mode='json'))
    if byte_digest(raw)!=expected:raise ValueError('answer_review_raw_output_bytes_changed')
    decoded=raw.decode('utf-8')
    if decoded.replace('\r\n','\n').replace('\r','\n')!=text or json.loads(decoded)!=json.loads(text):
        raise ValueError('answer_review_output_transform_not_exact')
    return {'kind':'verified_historical_newline_conversion','source':source.model_dump(mode='json'),
        'execution_ref':execution_ref,'historical_receipt_rewritten':False,'new_model_calls':0}


def answer_review_binding(work,authorization,stored,packet,context,sources,*,read_asset=None,_seen=()):
    from agent_kit.python.boi_process_response_review import (SUPPORTED_RESPONSE_REVIEW_VERSIONS,response_material,
        response_review_selection,response_review_prompt,merge_response_review,response_check)
    result={'status':'unconfirmed','reason_codes':[],'model_assessment_accepts_answers':False,
        'authority':'wiki_reference_check','scientific_correctness':'not_evaluated','new_model_runs':0}
    report=packet.get('response_review',{});attempts=report.get('attempts',[])
    if read_asset is not None and report.get('review_contract_version') in SUPPORTED_RESPONSE_REVIEW_VERSIONS and (len(attempts)>1 or any(a.get('repair') or 'native_observation_revision' in a.get('provider',{}) or a.get('provider',{}).get('status')=='stored_completed_observation' for a in attempts)):
        try:
            return _repair_chain_binding(work,authorization,stored,packet,context,sources,read_asset=read_asset,seen=_seen)
        except (KeyError,ValueError,TypeError,StopIteration):
            result['reason_codes']=['answer_review_repair_chain_unconfirmed'];return result
    if report.get('review_contract_version') not in SUPPORTED_RESPONSE_REVIEW_VERSIONS or len(attempts)!=1 or attempts[0].get('repair'):
        result['reason_codes']=['answer_review_contract_or_chain_not_supported'];return result
    try:
        attempt=attempts[0]
        if attempt['answer']!=packet['answer']:raise ValueError('answer_review_target_changed')
        material=response_material(answers=packet['answer'],context=context,sources=sources,questions=packet['questions'])
        selection=response_review_selection(material)
        if attempt['material_digest']!=semantic_digest(material) or attempt['selection']!=selection:
            raise ValueError('answer_review_material_changed')
        evidence=work.read_evidence(authorization=authorization,request=DomainToolEvidenceRequest(
            execution_ref=RevisionRef.model_validate(attempt['provider']['wiki_execution_ref'])))
        body=evidence['execution']['signed_execution']['body'];observation=json.loads(evidence['output_json'])['result']
        if body['outcome']!='completed' or observation.get('contract_version')!='boi/model-observation@1' or observation['provider_run']['status']!='completed':
            raise ValueError('answer_review_observation_not_completed')
        package=work._package(authorization,body['invocation']['task_revision']['ref'],require_current=False)
        data=json.loads(next(i['content_json'] for i in package['domain_execution_contract']['inputs'] if i['kind']=='proposal' and i['name']=='request'))
        refs=[d['revision'] for d in stored['asset']['dependencies'] if d['role'] in ('requested_process_meaning','requested_source_note','review')]
        if (any(r not in data['input_revisions'] for r in refs) or data['knowledge_reading_ref']!=stored['definition_reading_ref']
                or data['source_manifest_digest']!=source_manifest_digest([ArtifactEnvelope.model_validate(s) for s in stored['sources']])
                or data['review_contract_version']!=report['review_contract_version']):
            raise ValueError('answer_review_input_binding_mismatch')
        prompt=response_review_prompt(material,selection,context,version=report['review_contract_version'],
            presentation_version=report.get('presentation_contract_version','boi/process-response-review-presentation@3'))
        if (data['prompt']!=prompt or observation['input_digest']!=semantic_digest(data)
                or observation['provider_run']['prompt_digest']!=byte_digest(prompt.encode())):
            raise ValueError('answer_review_execution_digest_mismatch')
        recovery=_verified_provider_output(work,authorization,stored,packet,observation,evidence['execution_ref'])
        schema=json.loads(data['output_schema_json'])
        identifiers=schema['$defs']['StatementAssessment']['properties']['evidence_ids']['items']
        enum=identifiers.get('enum')
        inventory=[entry['evidence_id'] for entry in material['evidence_catalog']]
        reference_schema={'mode':'unbounded_identifiers' if enum is None else
            ('exact_inventory_enum' if enum==inventory else 'other_identifier_constraint'),
            'schema_digest':byte_digest(data['output_schema_json'].encode()),'origin':'admitted_model_work_input'}
        if reference_schema['mode']=='exact_inventory_enum' and 'anyOf' in schema['properties']['statements']['items']:
            from agent_kit.python.boi_process_response_review import response_review_schema
            from agent_kit.python.boi_structured_provider import strict_output_schema
            expected=strict_output_schema(response_review_schema(selection=selection,material=material,version=report['review_contract_version']))
            reference_schema['mode']='typed_inventory_enum' if schema['properties']['statements']['items']==expected['properties']['statements']['items'] else 'other_identifier_constraint'
        if report.get('assessment_schema_version')=='boi/process-response-assessment-schema@2' and reference_schema['mode']!='exact_inventory_enum':
            raise ValueError('answer_review_reference_schema_changed')
        if report.get('assessment_schema_version') in ('boi/process-response-assessment-schema@3','boi/process-response-assessment-schema@4') and reference_schema['mode']!='typed_inventory_enum':
            raise ValueError('answer_review_reference_schema_changed')
        merged=merge_response_review(json.loads(observation['value_json']),selection=selection)
        # Execution identity and assessment validity are separate. Preserve the
        # exact historical invalid-assessment record while confirming its real
        # producer; an invalid assessment can never become an accepted answer.
        protocol_issues=[]
        try:
            checked=response_check(merged,material=material,version=report['review_contract_version'])
        except ValueError as exc:
            checked={'assessment_complete':False,'diagnostic':str(exc),
                'model_assessment_accepts_answers':False,'review_failure':'invalid_assessment',
                'scientific_correctness':'not_evaluated'}
            protocol_issues=getattr(exc,'protocol_issues',[])
        checked,_,quality_executions=_quality_binding(work,authorization,stored,report,attempt,material,checked)
        if quality_executions:
            quality_origins=_observation_provenance(quality_executions)
            result['quality_execution_refs']=quality_origins['chain_execution_refs']
            if quality_origins['native_observation_provenance']:
                result['native_observation_provenance']=quality_origins['native_observation_provenance']
        if merged!=attempt['review'] or checked!=attempt['check']:
            raise ValueError('answer_review_observation_changed')
        if recovery:result['output_integrity_recovery']=recovery
        result.update(status='bound',check=checked,execution_ref=evidence['execution_ref'],
            assessment_reference_schema=reference_schema,
            assessment_status='complete' if checked.get('assessment_complete') else 'invalid_assessment',
            protocol_issues=protocol_issues,
            model_assessment_accepts_answers=checked.get('model_assessment_accepts_answers',False))
    except (KeyError,ValueError,TypeError,StopIteration):
        # Do not leak backend errors, titles or inaccessible input material.
        result['reason_codes']=['answer_review_admitted_link_unconfirmed']
    return result


def _same_json_payload_prompt(actual,expected):
    """Only object member order may vary; text, lists and duplicate keys cannot."""
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('answer_chain_duplicate_prompt_key')
            result[key]=value
        return result
    # Instructions may span lines. The payload begins at the generated JSON
    # object's opening brace, not necessarily after the first instruction line.
    actual_header,separator,actual_json=actual.partition('\n{')
    expected_header,expected_separator,expected_json=expected.partition('\n{')
    return (separator==expected_separator=='\n{' and actual_header==expected_header
        and semantic_digest(json.loads('{'+actual_json,object_pairs_hook=unique))==semantic_digest(json.loads('{'+expected_json,object_pairs_hook=unique)))


def _observation_provenance(origins):
    """Never put authored asset revisions into signed execution reference fields."""
    native=[o['native_observation_provenance'] for o in origins if o and 'native_observation_provenance' in o]
    signed=[o for o in origins if o and 'native_observation_provenance' not in o]
    return {'execution_ref':signed[-1] if signed else None,'chain_execution_refs':signed,
        'native_observation_provenance':native,
        'review_execution_binding':'authenticated_native_observation_and_exact_inputs' if native else 'admitted_output_and_exact_structured_inputs'}


def _observed_value(work,authorization,stored,provider,*,version,prompt,allow_json_member_order=False,expected_schema=None,allow_failure=False):
    """Verify one recorded worker result; never dispatch or accept prose authority."""
    failure_ref=provider.get('native_failure_observation_revision')
    if failure_ref and not allow_failure:raise ValueError('answer_failure_is_not_assessment')
    if 'native_observation_revision' in provider or failure_ref:
        if 'wiki_execution_ref' in provider or (failure_ref and 'native_observation_revision' in provider):raise ValueError('answer_observation_origin_ambiguous')
        from ..governed_runtime.native_observation import read_native_observation,read_native_failure_observation
        from agent_kit.python.boi_structured_provider import strict_output_schema
        native=(read_native_failure_observation(work,authorization,failure_ref) if failure_ref else
            read_native_observation(work,authorization,provider['native_observation_revision']))
        data=native['request']
        refs=[d['revision'] for d in stored['asset']['dependencies'] if d['role'] in ('requested_process_meaning','requested_source_note','review','prior_answer')]
        same_prompt=data['prompt']==prompt or (allow_json_member_order and _same_json_payload_prompt(data['prompt'],prompt))
        if (not all(r in data['input_revisions'] for r in refs)
                or data['knowledge_reading_ref']!=stored['definition_reading_ref']
                or data['source_manifest_digest']!=source_manifest_digest(stored['sources'])
                or data['review_contract_version']!=version or not same_prompt
                or expected_schema is None or json.loads(data['output_schema_json'])!=strict_output_schema(expected_schema)):
            raise ValueError('answer_native_observation_input_mismatch')
        return (native if failure_ref else native['value']),{'native_observation_provenance':native['provenance']}
    evidence=work.read_evidence(authorization=authorization,request=DomainToolEvidenceRequest(
        execution_ref=RevisionRef.model_validate(provider['wiki_execution_ref'])))
    body=evidence['execution']['signed_execution']['body'];observation=json.loads(evidence['output_json'])['result']
    if body['outcome']!='completed' or observation.get('contract_version')!='boi/model-observation@1' or observation['provider_run']['status']!='completed':
        raise ValueError('answer_chain_observation_incomplete')
    package=work._package(authorization,body['invocation']['task_revision']['ref'],require_current=False)
    data=json.loads(next(i['content_json'] for i in package['domain_execution_contract']['inputs'] if i['kind']=='proposal' and i['name']=='request'))
    refs=[d['revision'] for d in stored['asset']['dependencies'] if d['role'] in ('requested_process_meaning','requested_source_note','review','prior_answer')]
    same_prompt=data['prompt']==prompt
    if allow_json_member_order and not same_prompt:
        same_prompt=_same_json_payload_prompt(data['prompt'],prompt)
    checks={
        'input_revisions':all(r in data['input_revisions'] for r in refs),
        'reading':data['knowledge_reading_ref']==stored['definition_reading_ref'],
        'sources':data['source_manifest_digest']==source_manifest_digest([ArtifactEnvelope.model_validate(s) for s in stored['sources']]),
        'version':data['review_contract_version']==version,'prompt':same_prompt,
        'input_digest':observation['input_digest']==semantic_digest(data),
        'prompt_digest':observation['provider_run']['prompt_digest']==byte_digest(data['prompt'].encode()),
        'output_digest':observation['provider_run']['output_digest']==byte_digest(observation['value_json'].encode())}
    for key,valid in checks.items():
        if not valid:raise ValueError('answer_chain_execution_'+key+'_mismatch')
    return json.loads(observation['value_json']),evidence['execution_ref']


def _quality_binding(work,authorization,stored,report,attempt,material,checked,*,previous_material=None,previous_quality=None,historical=None):
    """Verify the separate external opinion; the Wiki does not judge prose."""
    if report['review_contract_version']!='boi/process-response-review@5' or not checked.get('assessment_complete'):
        return checked,None,[]
    from agent_kit.python.boi_process_explanation_quality import (SUPPORTED_QUALITY_VERSIONS,ExplanationQuality,ExplanationQualityV2,quality_selection,
        quality_material,quality_prompt,merge_quality,with_quality)
    record=attempt['quality_review']
    if record.get('assessment') is not None and record['assessment'].get('contract_version')!=record['contract_version']:
        raise ValueError('answer_quality_version_relabelled')
    selection=quality_selection(material,previous_material=previous_material,previous_quality=previous_quality)
    selected=quality_material(material,selection)
    if (record['contract_version'] not in SUPPORTED_QUALITY_VERSIONS or record['selection']!=selection
            or record['material_digest']!=semantic_digest(selected)):
        raise ValueError('answer_quality_selection_changed')
    provider=record['provider'];executions=[]
    if provider.get('native_failure_observation_revision'):
        observed,execution=_observed_value(work,authorization,stored,provider,allow_failure=True,
            version=report['review_contract_version'],prompt=quality_prompt(selected,version=record['contract_version'],
                presentation_version=record.get('presentation_contract_version','boi/process-explanation-quality-presentation@1')),
            expected_schema=(ExplanationQualityV2 if record['contract_version']=='boi/process-explanation-quality@2' else ExplanationQuality).model_json_schema())
        if (provider.get('status')!=observed['failure_kind'] or record.get('assessment') is not None
                or provider.get('output_digest')!=observed['raw_output_digest']):
            raise ValueError('answer_quality_failure_observation_changed')
        return {**checked,'assessment_complete':False,'model_assessment_accepts_answers':False,
            'review_failure':'quality_provider_unresolved','diagnostic':'STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE'},None,[execution]
    if provider.get('status')=='stored_completed_observation':
        if historical is None or provider['prior_provider']!=historical['provider']:
            raise ValueError('answer_quality_historical_observation_changed')
        if provider['source_answer_revision']!=attempt['provider']['source_answer_revision'] or not provider['observation_replayed']:
            raise ValueError('answer_quality_original_revision_changed')
        value=historical['assessment']
    elif provider.get('status')=='unchanged_quality_carried':
        if selection['question_ids'] or previous_quality is None:raise ValueError('answer_quality_unreviewed_carry')
        value=previous_quality
    else:
        observed,execution=_observed_value(work,authorization,stored,provider,
            version=report['review_contract_version'],prompt=quality_prompt(selected,version=record['contract_version'],
                presentation_version=record.get('presentation_contract_version','boi/process-explanation-quality-presentation@1')),
            expected_schema=(ExplanationQualityV2 if record['contract_version']=='boi/process-explanation-quality@2' else ExplanationQuality).model_json_schema())
        executions.append(execution)
        try:value=merge_quality(observed,material=material,selection=selection)
        except ValueError as exc:
            if observed!=record['assessment']:raise ValueError('answer_quality_invalid_observation_changed')
            return {**checked,'assessment_complete':False,'model_assessment_accepts_answers':False,
                'review_failure':'invalid_quality_assessment','diagnostic':str(exc)},observed,executions
    if value!=record['assessment']:raise ValueError('answer_quality_observation_changed')
    return with_quality(checked,value,material=material),value,executions


def _repair_chain_binding(work,authorization,stored,packet,context,sources,*,read_asset,seen):
    from agent_kit.python.boi_process_response_review import (response_material,response_review_selection,
        response_review_prompt,response_review_schema,ResponseRepair,response_repair_schema,response_repair_prompt,response_check,response_proposal,merge_response_review,apply_response_repair,rebase_recorded_patch)
    from agent_kit.python.boi_process_answer_v2 import bind_process_answers_v2
    report=packet['response_review'];attempts=report['attempts'];version=report['review_contract_version']
    if stored['revision']['ref'] in seen or len(seen)>=8 or not 0<=len(attempts)-1<=report['max_repairs']<=2 or sum(bool(a.get('repair')) for a in attempts)>report['max_repairs']:
        raise ValueError('answer_chain_budget_or_cycle')
    seen=(*seen,stored['revision']['ref']);previous_material=previous_assessment=previous_quality=None;expected_answer=None;executions=[]
    protocol_issues=[];terminal_repair=None
    def bind(proposal):
        proposal={**proposal,'contract_version':'boi/process-answer-draft@2','context_digest':context['context_digest']}
        return bind_process_answers_v2(proposal,context=context,sources=sources,questions=packet['questions'])
    if packet.get('revalidation'):
        rv=packet['revalidation'];base=read_asset(rv['base_answer_revision']);base_packet=json.loads(base['asset']['content_json'])
        request={k:rv[k] for k in ('base_answer_revision','review_contract_version','max_repairs','purpose')}
        if rv['purpose']=='repair_recorded_answer_failures':
            request.update({k:rv[k] for k in ('repair_from_revision','repair_operation_version')})
            if rv['repair_operation_version']!='boi/process-stored-failure-repair@1':raise ValueError('answer_chain_repair_contract_unknown')
        elif rv['purpose']=='explicit_explanation_quality_revalidation':
            request.update(quality_contract_version=rv['quality_contract_version'])
            if 'quality_presentation_version' in rv:
                request['quality_presentation_version']=rv['quality_presentation_version']
                if rv['quality_presentation_version']!=attempts[0]['quality_review']['presentation_contract_version']:
                    raise ValueError('answer_chain_quality_presentation_changed')
            if 'execution_isolation_version' in rv:
                if rv['execution_isolation_version']!='boi/codex-no-plugins@1':raise ValueError('answer_quality_isolation_unknown')
                request['execution_isolation_version']=rv['execution_isolation_version']
            if rv['quality_contract_version']!=attempts[0]['quality_review']['contract_version']:raise ValueError('answer_chain_quality_contract_changed')
        elif rv['purpose']!='explicit_saved_answer_revalidation':raise ValueError('answer_chain_revalidation_purpose_unknown')
        if 'completed_source_observation_revision' in rv:
            if rv['purpose']!='explicit_saved_answer_revalidation' or rv['max_repairs']!=0:
                raise ValueError('answer_chain_completed_source_scope')
            request['completed_source_observation_revision']=rv['completed_source_observation_revision']
            if attempts[0]['provider'].get('native_observation_revision')!=rv['completed_source_observation_revision']:
                raise ValueError('answer_chain_completed_source_observation_changed')
        if (rv['request_digest']!=semantic_digest(request) or rv['max_repairs']!=report['max_repairs']
                or rv['review_contract_version']!=version or base['revision']!=stored['previous_revision']
                or base['logical_id']!=stored['logical_id'] or base['sources']!=stored['sources']
                or rv['prior_reading_receipt']!=base['definition_reading_ref'] or rv['new_reading_receipt']!=stored['definition_reading_ref']
                or rv['original_answer_digest']!=semantic_digest(base_packet['answer'])
                or rv['rebound_answer_digest']!=semantic_digest(bind(response_proposal(base_packet['answer'])))
                or attempts[0]['answer']!=bind(response_proposal(base_packet['answer']))):
            raise ValueError('answer_chain_revalidation_identity_changed')
    for index,attempt in enumerate(attempts):
        if expected_answer is not None and attempt['answer']!=expected_answer:raise ValueError('answer_chain_patch_target_changed')
        material=response_material(answers=attempt['answer'],context=context,sources=sources,questions=packet['questions'])
        selection=response_review_selection(material,previous_material=previous_material,previous_assessment=previous_assessment)
        if attempt['material_digest']!=semantic_digest(material) or attempt['selection']!=selection:
            raise ValueError('answer_chain_selection_changed')
        provider=attempt['provider'];historical_quality=None
        if provider.get('status')=='stored_completed_observation':
            if index!=0 or not provider.get('observation_replayed'):raise ValueError('answer_chain_carried_observation_invalid')
            revalidation=packet['revalidation'];base=read_asset(revalidation['base_answer_revision'])
            if base['revision']!=stored['previous_revision'] or base['logical_id']!=stored['logical_id'] or base['sources']!=stored['sources']:
                raise ValueError('answer_chain_base_revision_changed')
            failure=base;visited=set()
            while failure['revision']!=revalidation.get('repair_from_revision',revalidation['base_answer_revision']):
                if failure['revision']['ref'] in visited or not failure.get('previous_revision'):raise ValueError('answer_chain_failure_not_ancestor')
                visited.add(failure['revision']['ref']);failure=read_asset(failure['previous_revision'])
                if failure['logical_id']!=base['logical_id']:raise ValueError('answer_chain_failure_identity_changed')
            old=json.loads(failure['asset']['content_json']);base_packet=json.loads(base['asset']['content_json'])
            if (provider['source_answer_revision']!=failure['revision'] or old['questions']!=packet['questions']
                    or response_proposal(old['answer'])['answers']!=response_proposal(base_packet['answer'])['answers']
                    or bind(response_proposal(old['answer']))!=attempt['answer']):
                raise ValueError('answer_chain_original_answer_changed')
            old_context=work.contexts.validate_reading(authorization=authorization,
                revision=RevisionRef.model_validate(failure['definition_reading_ref']),
                sources=[ArtifactEnvelope.model_validate(s) for s in failure['sources']],require_current=False).model_dump(mode='json')
            prior=answer_review_binding(work,authorization,failure,old,old_context,sources,read_asset=read_asset,_seen=seen)
            old_attempt=old['response_review']['attempts'][-1]
            quality_refresh=revalidation['purpose']=='explicit_explanation_quality_revalidation'
            source_accepted=prior.get('check',{}).get('model_assessment_accepts_source_answers',prior.get('model_assessment_accepts_answers'))
            from agent_kit.python.boi_process_quality_resume import quality_isolation_revalidation_allowed
            isolation_refresh=quality_refresh and revalidation.get('execution_isolation_version')=='boi/codex-no-plugins@1' and quality_isolation_revalidation_allowed(old,prior)
            if (prior['status']!='bound' or (not isolation_refresh and not prior['check'].get('assessment_complete'))
                    or (not isolation_refresh and (not source_accepted if quality_refresh else prior['model_assessment_accepts_answers'])) or provider['prior_provider']!=old_attempt['provider']
                    or old['response_review']['review_contract_version']!=version):
                raise ValueError('answer_chain_original_failure_unconfirmed')
            old_material=response_material(answers=old['answer'],context=old_context,sources=sources,questions=old['questions'])
            old_catalog={e['evidence_id']:e for e in old_material['evidence_catalog']};catalog={e['evidence_id']:e for e in material['evidence_catalog']}
            # Failed statements are carried as historical diagnostics and must
            # be re-reviewed after the patch. Only accepted unchanged judgments
            # carry evidentiary support into the new reading.
            carried=[a for a in old_attempt['review']['statements']
                if a['support_relation']=='supported' and a['citation_support']=='full']
            if any(catalog.get(e)!=old_catalog[e] for a in carried for e in a['evidence_ids']):
                raise ValueError('answer_chain_carried_evidence_changed')
            merged=old_attempt['review'];executions.append(prior['execution_ref'])
            executions.extend(prior.get('quality_execution_refs',[]))
            executions.extend({'native_observation_provenance':n} for n in prior.get('native_observation_provenance',[]))
            historical_quality=old_attempt.get('quality_review')
        else:
            observed,execution=_observed_value(work,authorization,stored,provider,version=version,
                prompt=response_review_prompt(material,selection,context,version=version,
                    presentation_version=report.get('presentation_contract_version','boi/process-response-review-presentation@3')),
                expected_schema=response_review_schema(selection=selection,material=material,version=report['review_contract_version']))
            merged=merge_response_review(observed,selection=selection);executions.append(execution)
        try:checked=response_check(merged,material=material,version=report['review_contract_version'])
        except ValueError as exc:
            checked={'assessment_complete':False,'diagnostic':str(exc),'model_assessment_accepts_answers':False,
                'review_failure':'invalid_assessment','scientific_correctness':'not_evaluated'}
            protocol_issues=getattr(exc,'protocol_issues',[])
        checked,current_quality,quality_executions=_quality_binding(work,authorization,stored,report,attempt,material,checked,
            previous_material=previous_material,previous_quality=previous_quality,historical=historical_quality)
        executions.extend(quality_executions)
        if merged!=attempt['review'] or checked!=attempt['check']:raise ValueError('answer_chain_assessment_changed')
        if index<len(attempts)-1 or attempt.get('repair'):
            if not checked.get('assessment_complete') or checked.get('model_assessment_accepts_answers'):
                raise ValueError('answer_chain_unneeded_repair')
            repair=attempt['repair'];proposal=response_proposal(attempt['answer'])
            repair_version=report.get('repair_presentation_contract_version',report.get('presentation_contract_version','boi/process-response-review-presentation@3'))
            if repair['provider'].get('status')=='stored_completed_patch_observation':
                old_asset=read_asset(repair['provider']['source_answer_revision']);old_packet=json.loads(old_asset['asset']['content_json'])
                if old_asset['revision']!=stored['previous_revision'] or old_asset['sources']!=stored['sources']:
                    raise ValueError('answer_chain_stored_patch_base_changed')
                old_context=work.contexts.validate_reading(authorization=authorization,
                    revision=RevisionRef.model_validate(old_asset['definition_reading_ref']),
                    sources=[ArtifactEnvelope.model_validate(s) for s in old_asset['sources']],require_current=False).model_dump(mode='json')
                old_binding=answer_review_binding(work,authorization,old_asset,old_packet,old_context,sources,read_asset=read_asset,_seen=seen)
                old_attempt=old_packet['response_review']['attempts'][-1];old_repair=old_attempt['repair']
                if (old_binding['status']!='bound' or not old_binding.get('terminal_repair',{}).get('verified_invalid_patch')
                        or old_packet['response_review'].get('repair_presentation_contract_version')==repair_version
                        or repair['provider']['prior_provider']!=old_repair['provider']
                        or repair['provider']['original_patch_digest']!=semantic_digest(old_repair['patch'])):
                    raise ValueError('answer_chain_stored_patch_unconfirmed')
                observed=rebase_recorded_patch(old_repair['patch'],response_proposal(old_attempt['answer']),proposal)
                if 'native_observation_revision' in old_repair['provider']:
                    execution={'native_observation_provenance':next(n for n in old_binding['native_observation_provenance']
                        if n['observation_revision']==old_repair['provider']['native_observation_revision'])}
                else:execution=old_repair['provider']['wiki_execution_ref']
            else:
                observed,execution=_observed_value(work,authorization,stored,repair['provider'],version=version,
                    prompt=response_repair_prompt(proposal,checked,sources,context,packet['questions'],attempt_number=index+1,max_repairs=report['max_repairs'],
                        presentation_version=repair_version),allow_json_member_order=True,expected_schema=response_repair_schema(version=repair_version))
            if observed!=repair['patch']:raise ValueError('answer_chain_repair_observation_changed')
            if repair['status']=='invalid_repair' and index==len(attempts)-1:
                try:
                    proposed,_=apply_response_repair(proposal,observed,check=checked,version=repair_version)
                    bind(proposed)
                except ValueError as exc:
                    if str(exc)!=repair['diagnostic']:raise ValueError('answer_chain_invalid_patch_diagnosis_changed')
                    terminal_repair={'verified_invalid_patch':True,'diagnostic':str(exc),**_observation_provenance([execution]),
                        'repair_contract_version':repair_version,'new_model_runs':0}
                else:raise ValueError('answer_chain_invalid_patch_not_reproduced')
            else:
                if repair['status']!='bound_for_revalidation' or index==len(attempts)-1:
                    raise ValueError('answer_chain_repair_not_revalidated')
                proposed,delta=apply_response_repair(proposal,observed,check=checked,version=repair_version)
                if delta!=repair['delta']:raise ValueError('answer_chain_repair_delta_changed')
                expected_answer=bind(proposed)
            executions.append(execution)
        previous_material,previous_assessment,previous_quality=material,merged,current_quality
    if attempts[-1]['answer']!=packet['answer']:raise ValueError('answer_chain_final_answer_changed')
    return {'status':'bound','check':checked,**_observation_provenance(executions),
        **({'terminal_repair':terminal_repair} if terminal_repair else {}),
        'assessment_status':'complete' if checked.get('assessment_complete') else 'invalid_assessment',
        'protocol_issues':protocol_issues,'model_assessment_accepts_answers':checked.get('model_assessment_accepts_answers',False),
        'authority':'wiki_reference_check','scientific_correctness':'not_evaluated','new_model_runs':0,'reason_codes':[]}
