"""Shared-cache runner for separate source-reading and comparison steps.

Internal integration building block, not a public authority entrypoint. The
caller supplies the same verified source/definition/ACL context as the existing
metadata stages. Neither step creates an approved Domain candidate.
"""
from dataclasses import replace
from .semantic_inference_cache import SemanticInferenceRequestV2, canonical
from .semantic_binding_contract import semantic_digest
from .source_meaning_comparison import SourceReading, MeaningComparison, bind_source_reading, bind_comparison, append_source_reading


def run_frozen_source_meaning(*, cache, payload, request_context, attempt, identity,
                             policy, build_wire, invoke_wire, verify_context, allow_inference=True,
                             materialize_domain=False,source_reading_model=SourceReading,max_reading_passes=1,
                             plan_contract_graph=False,qualify_source=False,ground_subject_facets=False):
    """Persist reading before comparison; each network call has its own cache key.

    verify_context must recheck the caller's current authorization and source
    closure. Worker verification can set allow_inference=False for both steps.
    """
    if type(max_reading_passes) is not int or not 1<=max_reading_passes<=4:
        raise ValueError('SOURCE_READING_PASS_LIMIT_INVALID')
    if type(plan_contract_graph) is not bool or (plan_contract_graph and not materialize_domain):
        raise ValueError('CONTRACT_GRAPH_MODE_INVALID')
    if type(qualify_source) is not bool or (qualify_source and not plan_contract_graph):
        raise ValueError('SOURCE_QUALIFIER_MODE_INVALID')
    if type(ground_subject_facets) is not bool or (ground_subject_facets and not qualify_source):
        raise ValueError('SOURCE_SUBJECT_FACET_MODE_INVALID')
    outcomes=[];receipt_refs=[];source=None;comparison=None;domain=None;domain_outcome=None;preflight_reasons=[];reading_passes=0;dependency_check=None
    graph_receipt=None;graph=None;contract_source=None;qualifier_receipt=None;facet_receipt=None

    def publish(stage, receipt, outcome):
        verify_context()
        value={'employee_id':request_context.principal_id,'run_id':attempt.run_ref,
            'shard_id':attempt.shard_ref,'stage_id':stage,
            'evidence_span_refs':list(attempt.evidence_span_refs),
            'evidence_closure_digest':attempt.evidence_closure_digest,
            'request_digest':outcome.cache_key,'inference_outcome_digest':outcome.outcome_digest,
            'receipt':receipt,'production_changed':False}
        ref='source-meaning:'+semantic_digest(value)
        cache._immutable('bulk_migration_receipts',ref,value)
        receipt_refs.append(ref)

    stages=[('domain-ontology-draft',source_reading_model)]
    if plan_contract_graph:
        from .source_contract_graph import SourceContractGraph,SourceContractGraphV2,SourceContractGraphV3,contract_graph_receipt,graph_binding_projection
        stages.append(('source-contract-graph',SourceContractGraphV3 if ground_subject_facets else
            SourceContractGraphV2 if qualify_source else SourceContractGraph))
    if ground_subject_facets:
        from .source_subject_facets import SourceSubjectFacetReading,bind_subject_facets,subject_facet_projection
        stages.append(('source-subject-facets',SourceSubjectFacetReading))
    if qualify_source:
        from .semantic_qualifier import SourceQualifierReading,qualifier_catalog,bind_qualifier_reading
        stages.append(('source-qualifier-reading',SourceQualifierReading))
    stages.append(('existing-concept-match',MeaningComparison))
    if materialize_domain:
        from .metadata_atomic_draft import MetadataLogicalDraft
        stages.append(('source-grounded-domain',MetadataLogicalDraft))
    for position,(stage, model) in enumerate(stages):
        verify_context()
        semantic_source=contract_source or source
        value=payload if source is None else {
            'source_receipt':semantic_source,'existing_definitions':payload['existing_definitions']}
        if stage=='domain-ontology-draft' and source is not None:
            value={**payload,'prior_reading':source['reading'],'prior_reading_receipt_digest':source['receipt_digest'],
                   'continuation_contract':'boi/source-reading-continuation@1'}
        if stage=='source-contract-graph':
            value={**payload,'source_reading':source['reading'],'source_reading_receipt_digest':source['receipt_digest']}
        if stage=='source-subject-facets':
            value={**payload,'source_graph_receipt_digest':graph_receipt['receipt_digest'],
                'node_subjects':[{'node_ref':node.local_id,'reading':{k:v for k,v in node.reading.model_dump(mode='json').items()
                    if k not in {'unit_status','time_status','time_basis'}}} for node in graph.nodes]}
        if stage=='source-qualifier-reading':
            value={**payload,'source_reading':semantic_source['reading'],
                'source_reading_receipt_digest':semantic_source['receipt_digest'],
                'contract_bindings':graph_binding_projection(graph),'qualifier_catalog':qualifier_catalog(semantic_source)}
        if stage=='source-grounded-domain':
            if any(atom.get('contract_kind')=='unknown' for atom in semantic_source['reading']['atoms']):
                preflight_reasons.append('SOURCE_MEANING_KIND_UNRESOLVED')
                break
            if any(atom['role']=='unknown' for atom in semantic_source['reading']['atoms']):
                preflight_reasons.append('SOURCE_MEANING_ROLE_UNRESOLVED')
                break
            value={'source_reading':semantic_source['reading'],'comparison':comparison['comparison'],
                'source_reading_receipt_digest':semantic_source['receipt_digest'],
                'comparison_receipt_digest':comparison['receipt_digest'],
                'semantic_namespace':payload['semantic_namespace'],
                'existing_definitions':payload['existing_definitions']}
            if graph is not None:value.update(contract_bindings=graph_binding_projection(graph),
                contract_graph_receipt_digest=graph_receipt['receipt_digest'])
            if qualifier_receipt is not None:value.update(qualifier_contracts=qualifier_receipt['qualifier_contracts'],
                source_qualifier_receipt_digest=qualifier_receipt['receipt_digest'])
            if facet_receipt is not None:value.update(subject_facet_bindings=subject_facet_projection(facet_receipt),
                source_facet_receipt_digest=facet_receipt['receipt_digest'])
        wire=build_wire(stage,value,model)
        input_bytes=len(canonical(value));wire_bytes=len(canonical(wire))
        if input_bytes>11264 or wire_bytes>32768:
            preflight_reasons.append('SOURCE_MEANING_INPUT_BYTE_LIMIT' if input_bytes>11264
                                     else 'SOURCE_MEANING_WIRE_BYTE_LIMIT')
            break
        stage_identity=replace(identity,
            role_digest=semantic_digest(wire['messages'][0]),
            prompt_digest=semantic_digest({'stage':stage,'wire_digest':semantic_digest(wire)}))
        context=request_context.model_dump(mode='json')
        context.pop('contract_version')
        context.update(skill_id='domain-ontology-draft' if stage in {
            'source-grounded-domain','source-contract-graph','source-subject-facets','source-qualifier-reading'} else stage,
            output_contract_digest=semantic_digest(model.model_json_schema()),
            role_digest=stage_identity.role_digest,prompt_digest=stage_identity.prompt_digest,
            input_digest=semantic_digest(value),input_bytes=input_bytes,
            wire_request_digest=semantic_digest(wire),wire_input_bytes=wire_bytes)
        request=SemanticInferenceRequestV2.model_validate(context)
        frozen_reading_digest=semantic_source['receipt_digest'] if semantic_source else None

        def invoke(_):
            verify_context()
            parsed=model.model_validate(invoke_wire(wire,model))
            if stage=='source-grounded-domain':
                from .source_grounded_domain import validate_grounded_domain
                validate_grounded_domain(parsed,value)
            elif stage=='domain-ontology-draft':
                merged=append_source_reading(source['reading'] if source else None,parsed)
                bind_source_reading(merged,payload)
            elif stage=='source-contract-graph':
                contract_graph_receipt(parsed,source,payload)
            elif stage=='source-subject-facets':
                bind_subject_facets(parsed,graph_receipt,payload)
            elif stage=='source-qualifier-reading':
                bind_qualifier_reading(parsed,semantic_source)
            else:
                bind_comparison(parsed,semantic_source,payload,expected_reading_digest=frozen_reading_digest)
            verify_context()
            return parsed.model_dump(mode='json')

        outcome=cache.run_frozen(request=request,attempt=attempt,payload=value,
            identity=stage_identity,policy=policy,invoke=invoke,output_model=model,
            allow_inference=allow_inference,model_request=wire)
        outcomes.append(outcome)
        if outcome.status!='PROVISIONAL':
            break
        parsed=model.model_validate(outcome.output)
        if stage=='source-grounded-domain':
            from .source_grounded_domain import validate_grounded_domain
            validate_grounded_domain(parsed,value)
            domain=parsed.model_dump(mode='json');domain_outcome=outcome.outcome_digest
            if source['reading']['contract_version']=='boi/source-meaning-reading@3':
                from .source_grounded_domain import source_draft_dependency_check
                dependency_check=source_draft_dependency_check(parsed,value)
                preflight_reasons.extend(dependency_check['reason_codes'])
            publish(stage,{'domain_draft':domain,'source_reading_receipt_digest':semantic_source['receipt_digest'],
                'comparison_receipt_digest':comparison['receipt_digest'],
                **({'contract_graph_receipt_digest':graph_receipt['receipt_digest']} if graph_receipt is not None else {}),
                **({'source_qualifier_receipt_digest':qualifier_receipt['receipt_digest']} if qualifier_receipt is not None else {}),
                **({'source_facet_receipt_digest':facet_receipt['receipt_digest']} if facet_receipt is not None else {}),
                **({'dependency_check':dependency_check} if dependency_check is not None else {})},outcome)
        elif stage=='domain-ontology-draft':
            merged=append_source_reading(source['reading'] if source else None,parsed)
            source=bind_source_reading(merged,payload);reading_passes+=1
            publish(stage,source,outcome)
            if merged.remaining_claims:
                if reading_passes<max_reading_passes and len(merged.atoms)<4:
                    stages.insert(position+1,(stage,model))
                else:preflight_reasons.append('SOURCE_READING_CONTINUATION_LIMIT')
        elif stage=='source-contract-graph':
            graph=parsed;graph_receipt=contract_graph_receipt(graph,source,payload)
            contract_source=graph_receipt['derived_reading_receipt']
            publish(stage,graph_receipt,outcome)
            if graph_receipt['status']=='partial':
                preflight_reasons.extend(graph_receipt['reason_codes']);break
        elif stage=='source-subject-facets':
            facet_receipt=bind_subject_facets(parsed,graph_receipt,payload)
            contract_source=facet_receipt['derived_reading_receipt']
            publish(stage,facet_receipt,outcome)
            preflight_reasons.extend(facet_receipt['reason_codes'])
        elif stage=='source-qualifier-reading':
            qualifier_receipt=bind_qualifier_reading(parsed,semantic_source)
            publish(stage,qualifier_receipt,outcome)
            preflight_reasons.extend(qualifier_receipt['reason_codes'])
        else:
            comparison=bind_comparison(parsed,semantic_source,payload,expected_reading_digest=frozen_reading_digest)
            publish(stage,comparison,outcome)
    result={'source_receipt':source,'comparison_receipt':comparison,'receipt_refs':receipt_refs,
        'inference_outcome_refs':[o.outcome_digest for o in outcomes],
        'model_invocation_count':sum(o.invocation_count for o in outcomes),
        'model_input_bytes':sum(o.input_bytes*o.invocation_count for o in outcomes),
        'cache_hit_count':sum(o.cache_hit_count for o in outcomes),
        'reason_codes':preflight_reasons+[o.reason_code for o in outcomes if o.reason_code],
        'status':'PROVISIONAL' if (domain if materialize_domain else comparison) and not source['reading']['remaining_claims'] and not preflight_reasons else 'partial',
        'semantic_validated':False,'production_changed':False}
    if materialize_domain:result.update(domain_draft=domain,domain_outcome_digest=domain_outcome)
    if dependency_check is not None:result['dependency_check']=dependency_check
    if graph_receipt is not None:result.update(contract_graph_receipt=graph_receipt,contract_reading_receipt=contract_source)
    if qualifier_receipt is not None:result['source_qualifier_receipt']=qualifier_receipt
    if facet_receipt is not None:result['source_facet_receipt']=facet_receipt
    return result
