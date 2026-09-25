"""Native source explanation and same-session opinion, without query artifacts."""
from typing import Literal
from pydantic import Field,model_validator
from .semantic_binding_contract import FrozenContract,Ref,Digest,RevisionRef,semantic_digest
from .native_observation import read_native_observation,_json
from .native_definition_context import read_native_definition_authority
from .domain_asset_store import DomainAssetStore
from .source_envelope import ArtifactEnvelope


class NativeReviewedSourceAnswer(FrozenContract):
    contract_version: Literal['boi/native-reviewed-source-answer@1']='boi/native-reviewed-source-answer@1'
    question: Ref
    body_markdown: Ref
    body_digest: Digest
    definition_review_revision: RevisionRef
    disposition: Literal['supported_with_limits','needs_revision','unknown']
    findings: tuple[Ref,...]=Field(min_length=1)
    limitations: tuple[Ref,...]=Field(min_length=1)
    errors: tuple[Ref,...]
    reviewer_relationship: Literal['same_session']='same_session'
    execution_authority_granted: Literal[False]=False
    semantic_truth_proven: Literal[False]=False

    @model_validator(mode='after')
    def preserved_body_and_opinion(self):
        if semantic_digest(self.body_markdown)!=self.body_digest:
            raise ValueError('NATIVE_SOURCE_ANSWER_BODY_MISMATCH')
        if self.errors and self.disposition=='supported_with_limits':
            raise ValueError('NATIVE_SOURCE_ANSWER_UNRESOLVED_ERRORS')
        return self


def read_native_source_answer(work,authorization,revision,*,historical=False):
    observation=read_native_observation(work,authorization,revision)
    value=NativeReviewedSourceAnswer.model_validate(observation['value']);request=observation['request']
    if (request['review_contract_version']!=value.contract_version or
        semantic_digest(_json(request['output_schema_json']))!=semantic_digest(NativeReviewedSourceAnswer.model_json_schema())):
        raise ValueError('NATIVE_SOURCE_ANSWER_CONTRACT_MISMATCH')
    authority,context=read_native_definition_authority(work,authorization,value.definition_review_revision,
        process_semantic_basis={},
        **({'require_current':False} if historical else {}))
    expected=(value.definition_review_revision,*authority.definition_revisions)
    if tuple(RevisionRef.model_validate(r) for r in request['input_revisions'])!=expected:
        raise ValueError('NATIVE_SOURCE_ANSWER_INPUT_MISMATCH')
    if request['source_manifest_digest']!=authority.source_manifest_digest:
        raise ValueError('NATIVE_SOURCE_ANSWER_SOURCE_MISMATCH')
    stored=DomainAssetStore(work.intake).read(authorization=authorization,
        revision=RevisionRef.model_validate(revision),lane='provisional')
    return {'answer_text':{'question':value.question,'body_markdown':value.body_markdown,'body_digest':value.body_digest},
        'review':value.model_dump(mode='json',include={'disposition','findings','limitations','errors','reviewer_relationship'}),
        'sources':stored['sources'],'provenance':observation['provenance'],
        'definition_authority':authority.model_dump(mode='json'),'classification':'PROVISIONAL',
        'historical':historical,'current_review_reusable':not historical,
        'answer_admission_changed':False,'execution_authority_granted':False}


def _verified_source_only_dependencies(work, authorization, request, material, assessment, check, sources):
    """Positive saved binder/reviewer correspondence, never an empty-basis guess.

    This intentionally excludes used meaning/execution, absence/search-scope and
    unestablished/legacy paths. The final review is already reconstructed and
    its original evidence re-read before this predicate is used.
    """
    basis = material.get('semantic_basis')
    required = {'request_plans', 'request_plan_links', 'nodes', 'statement_links',
        'statement_kinds', 'statement_kind_authority', 'source_only_statements',
        'unresolved_meaning_links', 'origin', 'semantic_truth_proven', 'scope'}
    if (not isinstance(basis, dict) or set(basis) != required
            or basis['origin'] != 'existing_bound_answer'
            or basis['statement_kind_authority'] != 'author_proposed_not_verified'
            or any(basis[key] for key in ('nodes','statement_links','request_plan_links','unresolved_meaning_links'))
            or not check.get('assessment_complete') or not check.get('model_accepts_final')):
        return False
    # Both the authored statements and the actual final claims must positively
    # use originals. Host-observed exchanges stay in the immutable material;
    # their presence is not consumption. Units may use only original evidence
    # IDs below, and the request plan may bind only original source quotations.
    # Missing or unsupported classifications cannot open reuse.
    declarations = basis['statement_kinds']
    plans = basis['request_plans']
    units = assessment.get('units', [])
    evidence_ids = {e['evidence_id'] for e in material['evidence']}
    if (not isinstance(declarations, list) or not isinstance(plans, list)
            or not isinstance(basis['source_only_statements'], list)
            or any(not isinstance(d, dict) for d in declarations)
            or any(not isinstance(p, dict) for p in plans)
            or not declarations or len(plans) != 1 or not units
            or any(u.get('purpose') != 'domain_claim' or u.get('relation') != 'supported'
                or u.get('citation_support') != 'full' or u.get('meaning_node_ids')
                or not u.get('evidence_ids') or not set(u['evidence_ids']) <= evidence_ids for u in units)):
        return False
    question_id = plans[0].get('question_id')
    pointers = [d.get('statement_pointer') for d in declarations]
    if (any(not isinstance(pointer, str) for pointer in [*pointers,*basis['source_only_statements']])
            or any(d.get('kind') not in ('source_reported_fact', 'interpretation')
            or d.get('question_id') != question_id for d in declarations)
            or len(set(pointers)) != len(pointers)
            or len(set(basis['source_only_statements'])) != len(basis['source_only_statements'])
            or set(pointers) != set(basis['source_only_statements'])):
        return False
    from agent_kit.python.boi_final_source_review import _quote_text_reference
    if not material['citations'] or any(c.get('role') == 'source_scope' or not c.get('quotes')
            or any(_quote_text_reference(q, c.get('source', {}), material['evidence']) is None
                for q in c['quotes']) for c in material['citations']):
        return False
    from agent_kit.python.boi_process_answer_v2 import (
        RequestPlan, SourceCitation, request_plan_proposal, _source_binding, validate_source_readings)
    plan = plans[0].get('plan', {})
    try:
        RequestPlan.model_validate(request_plan_proposal(plan))
        reading_ref = RevisionRef.model_validate(request.get('knowledge_reading_ref'))
    except (ValueError, KeyError, TypeError, AttributeError):
        return False
    context = work.contexts.validate_reading(authorization=authorization,
        revision=reading_ref,
        sources=tuple(ArtifactEnvelope.model_validate(s['source']) for s in sources), require_current=False)
    indexed = validate_source_readings(context, sources)
    if plan.get('request_digest') != semantic_digest({'id':question_id,
            'question':material['user_request'], 'max_body_characters':None}):
        return False
    covered = set()
    for facet in plan.get('facets', []):
        if (facet.get('aspect') == 'time' or facet.get('unresolved_reason')
                or not facet.get('request_quote') or facet['request_quote'] not in material['user_request']
                or not facet.get('citations')):
            return False
        for citation in facet['citations']:
            if citation.get('kind') != 'source_quote':return False
            try:
                value = SourceCitation.model_validate({k:v for k,v in citation.items() if k in SourceCitation.model_fields})
                bound = {**value.model_dump(mode='json'),
                    'source_bindings':[_source_binding(indexed, value.source_revision_digest, value.quotation)]}
                bound['evidence_digest'] = semantic_digest(bound)
            except (ValueError, KeyError, TypeError):
                return False
            if citation != bound:return False
        covered.update('/answers/0' + pointer for pointer in facet.get('statement_pointers', []))
    return covered == set(pointers)


def read_native_independent_source_answer(work, authorization, revision, *,
        definition_review_revision, material, sources, historical=False, _delivery_reading_ref=None,execution_refs=(),
        additional_definition_review_revisions=()):
    """Consume the original independent observation without rewriting its output."""
    from agent_kit.python.boi_final_source_review import final_review_prompt, final_review_schema, check_final_review
    observation = read_native_observation(work, authorization, revision)
    request = observation['request']
    execution_ids={e['evidence_id'] for e in material.get('execution_evidence',[])}
    selected_execution_ids=set().union(*(execution_ids.intersection(unit.get('evidence_ids',[]))
        for unit in observation['value'].get('units',[])))
    if selected_execution_ids:
        if not execution_refs:raise ValueError('NATIVE_SOURCE_FINAL_EXECUTION_REQUIRES_BOUND_RESULT_DELIVERY')
        from ..v2.native_formula import read_current_formula_execution,read_recorded_formula_execution
        from agent_kit.python.boi_final_source_review import formula_preview_material
        retained={}
        for ref in execution_refs:
            reader=read_recorded_formula_execution if historical else read_current_formula_execution
            record=reader(work,authorization,ref)
            if record['result'].get('evaluation') is None:
                raise ValueError('NATIVE_SOURCE_FINAL_EXECUTION_NOT_EVALUATED')
            value={'request':record['request'],'result':record['result']}
            retained[semantic_digest(value)]=formula_preview_material(value['request'],value['result'])
        used=set()
        for evidence in material.get('execution_evidence',[]):
            if evidence['evidence_id'] not in selected_execution_ids:continue
            matches=[digest for digest,preview in retained.items() if preview==evidence.get('formula_preview')
                and evidence.get('result_digest',digest)==digest]
            if len(matches)!=1:raise ValueError('NATIVE_SOURCE_FINAL_EXECUTION_MISMATCH')
            used.update(matches)
        if used!=retained.keys():raise ValueError('NATIVE_SOURCE_FINAL_UNUSED_EXECUTION')
    elif execution_refs:
        raise ValueError('NATIVE_SOURCE_FINAL_UNUSED_EXECUTION')
    if request['prompt'] != final_review_prompt(material):
        raise ValueError('NATIVE_SOURCE_FINAL_REVIEW_PROMPT_MISMATCH')
    from agent_kit.python.boi_structured_provider import strict_output_schema
    if semantic_digest(_json(request['output_schema_json'])) != semantic_digest(strict_output_schema(final_review_schema(material, segmented=True))):
        raise ValueError('NATIVE_SOURCE_FINAL_REVIEW_SCHEMA_MISMATCH')
    from .domain_asset_store import source_manifest_digest
    from .source_envelope import ArtifactEnvelope
    original = {(s['source']['digest'], f['span_ref']): (s['source'], f)
                for s in sources for f in s['fields']}
    for evidence in material['evidence']:
        key = (evidence['source']['digest'], evidence['field']['span_ref'])
        if key not in original:
            raise ValueError('NATIVE_SOURCE_FINAL_EVIDENCE_NOT_READ')
        source, field = original[key]
        if (source != evidence['source'] or evidence['text'] != field['text']
                or evidence['field'] != {k:v for k,v in field.items() if k != 'text'}):
            raise ValueError('NATIVE_SOURCE_FINAL_EVIDENCE_CHANGED')
    check = check_final_review(observation['value'], material=material)
    # The private optimization is derived after authenticating the exact prompt,
    # output, original fields and final claim review, not from caller flags.
    source_only = (not historical and _verified_source_only_dependencies(
        work, authorization, request, material, observation['value'], check, sources))
    if _delivery_reading_ref is not None:
        work.contexts.validate_reading(authorization=authorization, revision=_delivery_reading_ref,
            sources=tuple(ArtifactEnvelope.model_validate(s['source']) for s in sources),
            require_current=not historical,
            **({'_source_only_saved_answer':True} if source_only else {}))
    definition_review_revision = RevisionRef.model_validate(definition_review_revision)
    additional_authorities=[]
    if additional_definition_review_revisions:
        from ..v2.native_process_review import (read_native_process_review_for_work,
            check_native_process_semantic_basis,native_process_review_authority)
        reviews=(definition_review_revision,*[RevisionRef.model_validate(r) for r in additional_definition_review_revisions])
        if len(reviews)!=len(set(reviews)):raise ValueError('NATIVE_DELIVERY_DUPLICATE_DEFINITION_REVIEW')
        bindings=[read_native_process_review_for_work(work,authorization,r,require_current=not historical) for r in reviews]
        check_native_process_semantic_basis(material.get('semantic_basis',{}),bindings[0],additional_bindings=bindings[1:])
        authorities=[native_process_review_authority(b,authorization)[0] for b in bindings]
        authority=authorities[0];additional_authorities=authorities[1:]
        # The existing DAG resolver detects conflicts across individually valid
        # scopes; no aggregate approval or authority object is fabricated.
        from ..v2.native_answer_composition import combined_review_context
        envelopes=[]
        for b in bindings:
            for s in b['sources']:
                if s['source'] not in envelopes:envelopes.append(s['source'])
        combined_review_context(bindings,authorization,envelopes)
        bound_source_digest=source_manifest_digest(envelopes)
        expected=(*reviews,*[r for a in authorities for r in a.definition_revisions])
    else:
        authority, context = read_native_definition_authority(work, authorization, definition_review_revision,
            process_semantic_basis=material.get('semantic_basis',{}),
            **({'require_current': False} if historical else {}),
            **({'_source_only_saved_answer':True} if source_only else {}))
        expected = (definition_review_revision, *authority.definition_revisions)
        bound_source_digest=authority.source_manifest_digest
    if tuple(RevisionRef.model_validate(r) for r in request['input_revisions']) != expected:
        raise ValueError('NATIVE_SOURCE_ANSWER_INPUT_MISMATCH')
    if request['source_manifest_digest'] != bound_source_digest:
        raise ValueError('NATIVE_SOURCE_ANSWER_SOURCE_MISMATCH')
    if source_manifest_digest(tuple(ArtifactEnvelope.model_validate(s['source']) for s in sources)) != bound_source_digest:
        raise ValueError('NATIVE_SOURCE_FINAL_READING_SOURCE_MISMATCH')
    disposition = ('supported_with_limits' if check['assessment_complete'] and check['model_accepts_final']
                   else 'needs_revision')
    return {'answer_text': {'question': material['user_request'], 'body_markdown': material['final_text'],
                'body_digest': semantic_digest(material['final_text'])},
            'review': {'disposition': disposition, 'findings': [check['coverage_reason']],
                'limitations': list(check.get('missing_information', [])),
                'errors': check['issues'], 'reviewer_relationship': 'independent'},
            'independent_review_check': check, 'independent_review_output': observation['value'],
            'independent_review_material': material,
            'authorized_execution_refs': list(execution_refs),
            'sources': [s['source'] for s in sources], 'provenance': observation['provenance'],
            'definition_authority': authority.model_dump(mode='json'), 'classification': 'PROVISIONAL',
            **({'additional_definition_authorities':[a.model_dump(mode='json') for a in additional_authorities]}
               if additional_authorities else {}),
            'historical': historical, 'current_review_reusable': not historical,
            'answer_admission_changed': False, 'execution_authority_granted': False}
