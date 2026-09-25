"""Authenticated native Formula preview boundary; no inference or equipment IO."""
from typing import Any
from pydantic import Field, StrictBool, model_validator
from ..governed_runtime.semantic_binding_contract import FrozenContract, Ref, RevisionRef, semantic_digest
from ..governed_runtime.formula_preview import Formula, UnitDefinition, compile_formula
from ..governed_runtime.formula_evaluation import (evaluate_ast, evaluate_dsl,
    FormulaObservation, FormulaScenarioValue, FormulaTimePolicy)
from ..governed_runtime.formula_definition_context import FormulaScenarioInput,evaluate_calculation_context
from ..governed_runtime.svid_contract import read_native_svid_parameter,KnowledgeParameterIdentity
from .native_formula_timing import request_timing, stage_timing, timed_call
from .store_connections import request_store_connections


class NativeFormulaRequest(FrozenContract):
    formula: Formula
    parameter_reviews: dict[Ref, RevisionRef] = Field(default_factory=dict,max_length=64)
    knowledge_qualifications: dict[Ref,RevisionRef] = Field(default_factory=dict,max_length=64,exclude_if=lambda v:not v)
    unit_definitions: tuple[UnitDefinition, ...] = Field(default=(), max_length=128)
    unit_definition_reviews: dict[Ref, RevisionRef] | None = Field(default=None, max_length=128, exclude_if=lambda v:v is None)
    unit_definition_readings: dict[Ref, RevisionRef] | None = Field(default=None, max_length=128, exclude_if=lambda v:v is None)
    result_unit: Ref | None = Field(default=None, exclude_if=lambda v:v is None)
    observations: dict[str, FormulaObservation] | None = Field(default=None, max_length=64)
    time_policy: FormulaTimePolicy | None = None
    scenario_values: dict[str, FormulaScenarioValue] | None = Field(default=None, max_length=64)
    scenario_inputs: dict[Ref,FormulaScenarioInput] = Field(default_factory=dict,max_length=64,exclude_if=lambda v:not v)
    conditional_definition_scenario: StrictBool = Field(default=False,
        description='For supplied hypothetical values only: evaluate conditionally under every '
            'current published definition assumption. This does not attest world applicability.',
        exclude_if=lambda v:not v)

    @model_validator(mode='after')
    def exact_inputs(self):
        if self.unit_definition_readings is not None and not set(self.unit_definition_readings) <= set(self.unit_definition_reviews or {}):
            raise ValueError('NATIVE_FORMULA_UNIT_READING_BINDINGS_MISMATCH')
        if self.unit_definitions and self.unit_definition_reviews is not None and set(self.unit_definition_reviews) != {u.unit_id for u in self.unit_definitions}:
            raise ValueError('NATIVE_FORMULA_UNIT_REVIEW_BINDINGS_MISMATCH')
        knowledge={name for name,p in self.formula.parameters.items() if isinstance(p.identity,KnowledgeParameterIdentity)}
        if set(self.knowledge_qualifications)!=knowledge or set(self.parameter_reviews) != set(self.formula.parameters)-knowledge:
            raise ValueError('NATIVE_FORMULA_REVIEW_BINDINGS_MISMATCH')
        pure_evaluation=(self.formula.contract_version=='boi/formula-preview@2'
            and not self.formula.parameters and self.observations=={} and self.time_policy is None)
        if (self.observations is None) != (self.time_policy is None) and not pure_evaluation:
            raise ValueError('NATIVE_FORMULA_EVALUATION_INPUTS_REQUIRED')
        if self.scenario_values is not None and (self.observations is not None or self.time_policy is not None):
            raise ValueError('NATIVE_FORMULA_INPUT_MODES_EXCLUSIVE')
        if not self.unit_definitions and not self.unit_definition_reviews and self.formula.contract_version=='boi/formula-preview@1':
            raise ValueError('NATIVE_FORMULA_UNIT_DEFINITIONS_REQUIRED')
        if self.observations is not None and not set(self.observations) <= set(self.formula.parameters):
            raise ValueError('NATIVE_FORMULA_UNKNOWN_OBSERVATION')
        if self.scenario_values is not None and not set(self.scenario_values) <= set(self.formula.parameters):
            raise ValueError('NATIVE_FORMULA_UNKNOWN_SCENARIO_VALUE')
        if not set(self.scenario_inputs)<=knowledge:
            raise ValueError('NATIVE_FORMULA_CONTEXT_BINDINGS_MISMATCH')
        if self.conditional_definition_scenario and (
                self.formula.contract_version!='boi/formula-preview@2'
                or not self.scenario_values
                or set(self.scenario_values)!=set(self.formula.parameters)
                or self.scenario_inputs):
            raise ValueError('NATIVE_FORMULA_CONDITIONAL_SCENARIO_INPUTS_REQUIRED')
        return self


def _calculation_context_for_request(request,resolved):
    """Bind opted-in hypothetical inputs to definitions resolved in this call."""
    supplied=request.scenario_inputs
    if request.conditional_definition_scenario:
        supplied={}
        for name,value in request.scenario_values.items():
            resolution=resolved[name]
            context=resolution.get('calculation_context')
            parameter=resolution.get('parameter')
            sample=value.model_dump(mode='json')
            if (not isinstance(context,dict) or not isinstance(parameter,dict)
                    or sample.get('revision')!=parameter.get('revision')
                    or sample.get('unit')!=parameter.get('unit')):
                raise ValueError('NATIVE_FORMULA_CONDITIONAL_CONTEXT_UNAVAILABLE')
            definition=context.get('definition') or {}
            assumptions=definition.get('assumptions')
            scope=context.get('input_scope')
            if (not isinstance(assumptions,list) or not assumptions
                    or not isinstance(scope,list) or not scope):
                raise ValueError('NATIVE_FORMULA_CONDITIONAL_CONTEXT_UNAVAILABLE')
            supplied[name]=FormulaScenarioInput.model_validate({
                'contract_digest':context['contract_digest'],
                'origin':'caller_supplied_scenario',
                'statement':'Caller opted into a conditional calculation under the exact '
                    'current published definition; no live binding or world applicability is attested.',
                'assumptions':{item['id']:True for item in assumptions},
                'context_values':{item['id']:item['expected_value'] for item in scope}})
    context=evaluate_calculation_context(resolved,supplied)
    if request.conditional_definition_scenario:
        if context is None or context['status']!='satisfied':
            raise ValueError('NATIVE_FORMULA_CONDITIONAL_CONTEXT_UNSATISFIED')
        context={**context,'input_provenance':'engine_assembled_conditional_current_definition'}
    return context


@stage_timing('unit_definition_authority')
def read_native_unit_definition(work, authorization, *, review_revision, unit=None, unit_id=None, require_current=True,
        knowledge_reading_ref=None):
    """Match a unit to its actual reviewed candidate revision, never to an ID alone."""
    from ..governed_runtime.native_definition_context import read_native_definition_authority
    from ..governed_runtime.native_observation import _json
    from ..governed_runtime.knowledge_formula_contract import definition_meaning
    requested=UnitDefinition.model_validate(unit) if unit is not None else None
    if requested is None and unit_id is None:
        raise ValueError('NATIVE_FORMULA_UNIT_SELECTION_REQUIRED')
    # A supplementary current reading does not rewrite the old source opinion.
    # Historical validation still enforces source/ACL/content integrity. Before
    # use below, the fresh protected context must contain this exact unit and
    # its dependencies, under its actual namespace's complete current fence.
    authority,context=read_native_definition_authority(work,authorization,review_revision,
        require_current=require_current if knowledge_reading_ref is None else False)
    if requested is not None and requested.revision not in authority.definition_revisions:
        raise ValueError('NATIVE_FORMULA_UNIT_NOT_REVIEWED')
    if requested is not None:
        asset=next(a for a in context.assets if a.revision==requested.revision)
    else:
        # Select only an exact declared ID in the currently authorized review.
        # A label match neither supplies a conversion nor approves a candidate.
        candidates=[]
        for candidate in context.assets:
            value=definition_meaning(_json(candidate.content_json))
            if (candidate.revision in authority.definition_revisions and isinstance(value,dict)
                    and value.get('contract_version')=='boi/native-unit-interpretation@1'
                    and isinstance(value.get('unit_definition'),dict)
                    and value['unit_definition'].get('unit_id')==unit_id):
                candidates.append(candidate)
        if len(candidates)!=1:
            raise ValueError('NATIVE_FORMULA_UNIT_REVIEW_SELECTION_NOT_UNIQUE')
        asset=candidates[0]
    value=definition_meaning(_json(asset.content_json))
    if not isinstance(value,dict) or value.get('contract_version')!='boi/native-unit-interpretation@1':
        raise ValueError('NATIVE_FORMULA_UNIT_CONTRACT_REQUIRED')
    payload=value.get('unit_definition')
    if not isinstance(payload,dict) or 'revision' in payload:
        raise ValueError('NATIVE_FORMULA_UNIT_PAYLOAD_INVALID')
    declared=UnitDefinition.model_validate({**payload,'revision':asset.revision})
    if requested is not None and declared!=requested:
        raise ValueError('NATIVE_FORMULA_UNIT_DEFINITION_MISMATCH')
    current_reading = None
    if knowledge_reading_ref is not None:
        from .native_unit_review_reuse import validate_current_unit_reading
        current_reading = validate_current_unit_reading(work, authorization, asset,
            review_revision=review_revision, reading_ref=knowledge_reading_ref,
            require_current=require_current)
    return {'unit_definition':declared.model_dump(mode='json'),'definition_content':value,
        'reviewed_definition_authority':authority.model_dump(mode='json'),
        **({'current_knowledge_reading':current_reading} if current_reading is not None else {}),
        'semantic_truth_proven':False}


def resolve_native_units(work, authorization, request, *, require_current=True):
    """Reuse unit payloads from pinned reviews; retain the explicit-input path."""
    if request.unit_definition_reviews is None:
        return request.unit_definitions, {}
    supplied={unit.unit_id:unit for unit in request.unit_definitions}
    resolutions={name:read_native_unit_definition(work,authorization,
        review_revision=review,require_current=require_current,
        **({'knowledge_reading_ref':request.unit_definition_readings[name]}
            if name in (request.unit_definition_readings or {}) else {}),
        **({'unit':supplied[name]} if supplied else {'unit_id':name}))
        for name,review in request.unit_definition_reviews.items()}
    definitions={name:UnitDefinition.model_validate(item['unit_definition']) for name,item in resolutions.items()}
    frames={}
    for name,unit in definitions.items():
        reference=resolutions[name].get('definition_content',{}).get('reference_unit')
        if reference is None:continue
        # A reviewed conversion explicitly declares its reference frame. Its
        # identity conversion is mathematical, not a guessed unit dictionary.
        identity=UnitDefinition(unit_id=reference,dimension=unit.dimension,scale=1,offset=0,revision=unit.revision)
        existing=frames.get(unit.dimension)
        if existing is not None and existing['reference']!=identity.unit_id:
            raise ValueError('NATIVE_FORMULA_UNIT_REFERENCE_BASIS_CONFLICT')
        frames.setdefault(unit.dimension,{'reference':identity.unit_id,'sources':[]})['sources'].append(name)
    for dimension,frame in sorted(frames.items()):
        reference=frame['reference'];names=sorted(frame['sources']);origin=definitions[names[0]]
        if reference in definitions:
            explicit=definitions[reference]
            if (explicit.dimension!=dimension or explicit.scale!=explicit.scale_denominator or explicit.offset!=0):
                raise ValueError('NATIVE_FORMULA_UNIT_REFERENCE_IDENTITY_CONFLICT')
            continue
        identity=UnitDefinition(unit_id=reference,dimension=dimension,scale=1,offset=0,revision=origin.revision)
        definitions[reference]=identity
        resolutions[reference]={
            'unit_definition':identity.model_dump(mode='json'),
            'definition_content':resolutions[names[0]]['definition_content'],
            'reviewed_definition_authority':resolutions[names[0]]['reviewed_definition_authority'],
            'derivation':{'kind':'declared_reference_unit_identity','source_unit_ids':names,
                'source_revisions':[definitions[name].revision.model_dump(mode='json') for name in names],
                'definition_pointer':'/reference_unit'},'semantic_truth_proven':False}
    if len(definitions)>128:raise ValueError('NATIVE_FORMULA_UNIT_RESOLUTION_LIMIT')
    return tuple(definitions.values()),resolutions


def quantity_result(compiled, evaluation, definitions, result_unit):
    """Express the computed quantity in an explicitly selected compatible unit.

    The stored engine value stays in its common dimension basis. An interval
    never receives the unit's absolute offset, including unknown results.
    """
    if result_unit is None:
        return None
    from fractions import Fraction
    from ..governed_runtime.formula_numeric import exact_number, bounded
    unit=next((unit for unit in definitions if unit.unit_id==result_unit),None)
    if unit is None:
        raise ValueError('FORMULA_RESULT_UNIT_NOT_FOUND')
    if compiled['result_type']!='quantity' or compiled['result_dimension']!=unit.dimension:
        raise ValueError('FORMULA_RESULT_UNIT_DIMENSION_MISMATCH')
    interval=compiled.get('result_value_semantics')=='interval'
    value=None
    if evaluation is not None and evaluation['status']=='known':
        value=bounded(Fraction(evaluation['value']))
        if not interval:value=bounded(value-exact_number(unit.offset))
        value=bounded(bounded(value*exact_number(unit.scale_denominator))/exact_number(unit.scale))
    return {'value':str(value) if value is not None else None,
        'status':'not_evaluated' if evaluation is None else evaluation['status'],
        'unit':unit.unit_id,'unit_revision':unit.revision.model_dump(mode='json'),
        'dimension':unit.dimension,'value_semantics':'interval' if interval else 'absolute'}


def preview_native_formula(work, authorization, request):
    request = NativeFormulaRequest.model_validate(request)
    resolved = {name: resolve_formula_parameter(work, authorization,request,name,selection)
        for name, selection in request.formula.parameters.items()}
    definitions,unit_resolutions=resolve_native_units(work,authorization,request)
    for resolution in resolved.values():
        check_parameter_quantity(resolution, definitions)
    # Bindings carry separate observations and authority checks, but can share
    # one exact definition. Keep differing records so the compiler still rejects
    # conflicting candidates with the same identity and revision.
    catalog = []
    for resolution in resolved.values():
        if resolution['parameter'] not in catalog:
            catalog.append(resolution['parameter'])
    compiled = timed_call('compile', compile_formula, request.formula,
        catalog=catalog,
        unit_definitions=definitions)
    displayed=quantity_result(compiled,None,definitions,request.result_unit)
    calculation_context=_calculation_context_for_request(request,resolved)
    evaluation = None
    if request.observations is not None or request.scenario_values is not None:
        scenario=request.scenario_values is not None
        supplied=request.scenario_values if scenario else request.observations
        observations={key:value.model_dump(mode='json') for key,value in supplied.items()}
        policy=request.time_policy.model_dump(mode='json') if request.time_policy is not None else None
        evaluation = timed_call('evaluate_ast', evaluate_ast, compiled, observations, policy,
            unit_definitions=definitions,scenario=scenario)
        if evaluation != timed_call('evaluate_dsl', evaluate_dsl, compiled, observations, policy,
                unit_definitions=definitions,scenario=scenario):
            raise ValueError('NATIVE_FORMULA_INTERPRETERS_DISAGREE')
        if calculation_context is not None and calculation_context['status']!='satisfied':
            evaluation={**evaluation,'status':'unknown','value':None,
                'reasons':sorted(set(evaluation.get('reasons',[]))|set(calculation_context['reasons']))}
        displayed=quantity_result(compiled,evaluation,definitions,request.result_unit)
    revalidate_knowledge_parameters(work,authorization,request,resolved)
    return {'contract_version':'boi/native-formula-preview-result@1',
        'request_digest':semantic_digest(request), 'parameter_resolutions':resolved,
        'compilation':compiled, 'evaluation':evaluation,
        **({'calculation_context':calculation_context} if calculation_context is not None else {}),
        **({'result_quantity':displayed} if displayed is not None else {}),
        'observation_unit_definitions':[u.model_dump(mode='json') for u in definitions]
            if request.observations is not None else [],
        'scenario_unit_definitions':[u.model_dump(mode='json') for u in definitions]
            if request.scenario_values is not None else [],
        'unit_definition_authority':'reviewed_candidate' if unit_resolutions else 'caller_supplied_candidate',
        'unit_definition_resolutions':unit_resolutions,
        'observation_origin':('caller_supplied_hypothetical' if request.scenario_values is not None
            else 'caller_supplied_preview'),
        'time_policy_authority':('not_applicable_hypothetical' if request.scenario_values is not None
            else 'caller_supplied_preview'),
        'status':'PROVISIONAL', 'equipment_execution':False,
        'canonical_projection_eligible':False, 'semantic_truth_proven':False}


def check_parameter_quantity(resolution, definitions):
    """Check an actual shared definition against the resolved unit before math."""
    quantity = resolution.get('quantity_definition_resolution')
    if quantity is None:
        return  # Historical native parameters retain their existing contract.
    descriptor = resolution['parameter']['semantic_descriptor']
    if quantity['quantity_ref'] != descriptor['quantity_kind_ref']:
        raise ValueError('NATIVE_FORMULA_QUANTITY_DEFINITION_MISMATCH')
    dimension = quantity['concept'].get('quantity_dimension')
    if dimension is None:
        raise ValueError('NATIVE_FORMULA_QUANTITY_DIMENSION_UNRESOLVED')
    unit = next((u for u in definitions if u.unit_id == resolution['parameter']['unit']), None)
    if unit is None or unit.dimension != dimension:
        raise ValueError('NATIVE_FORMULA_QUANTITY_UNIT_DIMENSION_MISMATCH')
    if resolution.get('required_unit_definition') is not None and unit.model_dump(mode='json')!=resolution['required_unit_definition']:
        raise ValueError('NATIVE_FORMULA_PARAMETER_UNIT_REVISION_MISMATCH')


@stage_timing('parameter_definition_authority')
def resolve_formula_parameter(work,authorization,request,name,selection,*,require_current=True):
    if isinstance(selection.identity,KnowledgeParameterIdentity):
        from .knowledge_formula import read_knowledge_parameter
        return read_knowledge_parameter(work,authorization,selection=selection,
            qualification_revision=request.knowledge_qualifications[name],require_current=require_current)
    return read_native_svid_parameter(work,authorization,
        review_revision=request.parameter_reviews[name],selection=selection,require_current=require_current)


@stage_timing('knowledge_parameter_revalidation')
def revalidate_knowledge_parameters(work,authorization,request,resolved,*,require_current=True):
    for name,selection in request.formula.parameters.items():
        if not isinstance(selection.identity,KnowledgeParameterIdentity):continue
        current=resolve_formula_parameter(work,authorization,request,name,selection,require_current=require_current)
        for key in ('parameter','knowledge_qualification','required_unit_definition','quantity_definition_resolution'):
            if current[key]!=resolved[name][key]:
                raise ValueError('NATIVE_FORMULA_KNOWLEDGE_CHANGED_DURING_EXECUTION')
        if current.get('calculation_context')!=resolved[name].get('calculation_context'):
            raise ValueError('NATIVE_FORMULA_CONTEXT_CHANGED_DURING_EXECUTION')


@request_timing('preview')
@request_store_connections()
def preview_for_principal(intake, principal, request):
    # Each current authority/source read keeps its own transaction. Reuse only
    # idle connections in this synchronous worker, never data or permissions.
    authorization, work = timed_call('work_authorization', intake._work, principal)
    request=NativeFormulaRequest.model_validate(request)
    # Standalone compile/preview retains caller-defined candidate units. The
    # authenticated product path must consume current source-reviewed knowledge;
    # an unrelated SVID revision cannot attest an invented conversion scale.
    if request.unit_definitions and not request.unit_definition_reviews:
        raise ValueError('NATIVE_FORMULA_UNIT_REVIEW_REQUIRED')
    result=preview_native_formula(work, authorization, request)
    from .native_definition_sources import read_definition_sources
    from .domain_intake import DomainAssetReadRequest
    from ..public_links import configured_public_links
    import os
    views={}
    for resolution in result['parameter_resolutions'].values():
        if 'knowledge_qualification' in resolution:
            from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader
            reader=PublishedKnowledgeReader(work.knowledge_spaces,
                current_authorization=work.current_knowledge_authorization,public_links=configured_public_links())
            view=timed_call('definition_evidence', reader.read, actor_id=principal.employee_id,
                    request={'revision':resolution['parameter']['revision'],
                        'meaning_pointer':resolution['knowledge_qualification']['meaning_pointer']},model_input=True)
            resolution['definition_evidence']={'definition_revision':resolution['parameter']['revision'],
                'url':view['document_url'],'evidence_bindings':resolution['evidence_bindings']}
            continue
        revision=resolution['parameter']['revision']
        digest=revision['revision_digest']
        if digest not in views:
            view=timed_call('definition_evidence', read_definition_sources, intake,principal,
                DomainAssetReadRequest(revision=revision,lane='provisional'),
                source_base_url=os.environ.get('BOI_EXTERNAL_URL'))
            views[digest]={k:view[k] for k in ('definition_revision','url','evidence_bindings','source_scopes','page_role','scope')}
        resolution['definition_evidence']=views[digest]
    for resolution in result['unit_definition_resolutions'].values():
        revision=resolution['unit_definition']['revision']
        digest=revision['revision_digest']
        if getattr(work,'knowledge_spaces',None) is not None:
            from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader
            reader=PublishedKnowledgeReader(work.knowledge_spaces,current_authorization=work.current_knowledge_authorization,
                public_links=configured_public_links())
            if reader.is_published(RevisionRef.model_validate(revision)):
                view=timed_call('definition_evidence', reader.read,
                    actor_id=principal.employee_id,request={'revision':revision},model_input=True)
                resolution['definition_evidence']={'definition_revision':revision,'url':view['document_url'],
                    'source_bindings':[b for claim in view['claims'] for b in claim['source_bindings']]}
                continue
        if digest not in views:
            view=timed_call('definition_evidence', read_definition_sources, intake,principal,
                DomainAssetReadRequest(revision=revision,lane='provisional'),
                source_base_url=os.environ.get('BOI_EXTERNAL_URL'))
            views[digest]={k:view[k] for k in ('definition_revision','url','evidence_bindings','source_scopes','page_role','scope')}
            from .native_answer_composition import literal_source_group
            original={(s['source']['digest'],f['span_ref']):f for s in view['sources'] for f in s['fields']}
            bindings=[]
            for entry in view['evidence_bindings']:
                if entry['status']!='located':continue
                evidence=entry['evidence'];field=original[(evidence['source_revision_digest'],evidence['span_ref'])]
                start=field['text'].index(evidence['quote'])
                bindings.append({**evidence,'start':start,'end':start+len(evidence['quote'])})
            group=literal_source_group(revision,bindings,view['url'])
            if group is not None:
                if intake.source_intake.objects.put(group['bytes'])!=group['ref']:
                    raise ValueError('ANSWER_GROUP_OBJECT_MISMATCH')
                views[digest]['url']=group['url']
        resolution['definition_evidence']=views[digest]
    revalidate_knowledge_parameters(work,authorization,request,result['parameter_resolutions'])
    result['execution_ref']=retain_formula_execution(work,authorization,request,result.copy())
    result['result_url']=formula_result_url(result['execution_ref'])
    return result


def preview_for_principal_scoped(intake, principal, request):
    """Own structural read caches for exactly one synchronous Formula request."""
    from ..governed_runtime.ledger import request_ledger_decoding
    from ..governed_runtime.domain_context_service import request_context_decoding
    with request_ledger_decoding(), request_context_decoding():
        return preview_for_principal(intake, principal, request)


def formula_result_url(digest):
    import os
    from urllib.parse import urlsplit
    origin=os.environ.get('BOI_EXTERNAL_URL','').rstrip('/')
    parsed=urlsplit(origin)
    return (origin if parsed.scheme in ('http','https') and parsed.netloc else '')+'/native-formulas/'+digest.removeprefix('sha256:')


@request_timing('result')
@request_store_connections()
def read_formula_for_principal(intake,principal,digest):
    """Open the recorded result and its original dependencies with present rights."""
    authorization,work=timed_call('work_authorization', intake._work, principal)
    record=read_recorded_formula_execution(work,authorization,digest)
    saved_inputs=record['request']
    scenario=saved_inputs.get('scenario_values')
    preview_inputs=({'observations':None,'time_policy':None,
        'scenario_values':scenario,'origin':'caller_supplied_hypothetical'}
        if scenario is not None else
        {'observations':saved_inputs.get('observations'),
         'time_policy':saved_inputs.get('time_policy'),
         'origin':'caller_supplied_preview'})
    return {**record['result'],'execution_ref':digest,'result_url':formula_result_url(digest),
        'preview_inputs':preview_inputs,
        'read_scope':{'purpose':'recorded','current_request_applicability_verified':False,
            'current_data_freshness_verified':False}}


def read_current_formula_execution(work,authorization,digest):
    """Revalidate current binding authority for one owned retained execution."""
    return _read_validated_formula_execution(work,authorization,digest,require_current=True)


def read_recorded_formula_execution(work,authorization,digest):
    """Reauthorize pinned source/review closures, without requiring today's heads.

    The owned immutable record pins all parameter and unit review references.
    Historical access still validates their exact original source and selected
    dependencies; it grants no authority to reuse or execute them today.
    """
    return _read_validated_formula_execution(work,authorization,digest,require_current=False)


@stage_timing('recorded_definition_authority')
def _read_validated_formula_execution(work,authorization,digest,*,require_current):
    record=read_formula_execution(work,authorization,digest)
    request=NativeFormulaRequest.model_validate(record['request'])
    parameter_resolutions=[]
    context_resolutions={}
    for name,selection in request.formula.parameters.items():
        resolved=resolve_formula_parameter(work,authorization,request,name,selection,require_current=require_current)
        prior=record['result'].get('parameter_resolutions',{}).get(name,{})
        if prior.get('parameter')!=resolved['parameter']:
            raise ValueError('NATIVE_FORMULA_PARAMETER_DEFINITION_MISMATCH')
        if prior.get('quantity_definition_resolution') != resolved.get('quantity_definition_resolution'):
            raise ValueError('NATIVE_FORMULA_QUANTITY_DEFINITION_MISMATCH')
        if prior.get('calculation_context') != resolved.get('calculation_context'):
            raise ValueError('NATIVE_FORMULA_CONTEXT_DEFINITION_MISMATCH')
        parameter_resolutions.append(resolved)
        context_resolutions[name]=resolved
    # Recheck retained assumptions and exact scope against the pinned request;
    # reading a result never repeats its numerical calculation.
    context=_calculation_context_for_request(request,context_resolutions)
    if record['result'].get('calculation_context') != context:
        raise ValueError('NATIVE_FORMULA_CONTEXT_RESULT_MISMATCH')
    definitions,resolutions=resolve_native_units(work,authorization,request,require_current=require_current)
    for resolution in parameter_resolutions:
        check_parameter_quantity(resolution,definitions)
    if request.unit_definition_reviews is not None:
        retained=record['result'].get('unit_definition_resolutions',{})
        for unit in definitions:
            current=resolutions[unit.unit_id];prior=retained.get(unit.unit_id)
            # Legacy results could not consume an implicit reference unit. Do
            # not invalidate their unchanged computation merely by adding this
            # now-derived identity; still compare each original frame below.
            if prior is None and current.get('derivation',{}).get('kind')=='declared_reference_unit_identity':continue
            if ((prior or {}).get('unit_definition')!=unit.model_dump(mode='json')
                    or (prior or {}).get('definition_content',{}).get('reference_unit')!=current.get('definition_content',{}).get('reference_unit')
                    or (prior or {}).get('current_knowledge_reading')!=current.get('current_knowledge_reading')):
                raise ValueError('NATIVE_FORMULA_UNIT_DEFINITION_MISMATCH')
    revalidate_knowledge_parameters(work,authorization,request,record['result']['parameter_resolutions'],require_current=require_current)
    return record


def readable_exact_quantity(value):
    """Display terminating rationals as decimals without rounding the result."""
    from fractions import Fraction
    number=Fraction(value);remaining=number.denominator;twos=fives=0
    while remaining % 2==0:twos+=1;remaining//=2
    while remaining % 5==0:fives+=1;remaining//=5
    if remaining!=1:return str(number)
    places=max(twos,fives)
    if not places:return str(number.numerator)
    scaled=abs(number.numerator)*(2**(places-twos))*(5**(places-fives))
    digits=str(scaled).zfill(places+1)
    return ('-' if number<0 else '')+digits[:-places]+'.'+digits[-places:]


def render_formula_result(result):
    import html,json
    esc=lambda value:html.escape(str(value),quote=True)
    def expression(node):
        kind=node['kind']
        if kind=='scalar':return str(node['value'])
        if kind=='quantity':return str(node['value'])+' '+node['unit']
        if kind=='parameter':return node['binding']
        if kind=='arithmetic':
            op={'add':'+','subtract':'−','multiply':'×','divide':'÷'}[node['operator']]
            return '('+expression(node['left'])+' '+op+' '+expression(node['right'])+')'
        if kind=='compare':
            op={'lt':'<','le':'≤','eq':'=','ne':'≠','ge':'≥','gt':'>'}[node['operator']]
            return '('+expression(node['left'])+' '+op+' '+expression(node['right'])+')'
        if kind=='not':return 'NOT ('+expression(node['argument'])+')'
        if kind=='boolean':return '('+(' AND ' if node['operator']=='and' else ' OR ').join(expression(n) for n in node['arguments'])+')'
        return '('+expression(node['condition'])+' ? '+expression(node['when_true'])+' : '+expression(node['when_false'])+')'
    evaluation=result.get('evaluation')
    text='식만 준비됨' if evaluation is None else readable_exact_quantity(evaluation['value']) if evaluation['status']=='known' else '입력 정보가 부족해 값을 확정할 수 없습니다.'
    if evaluation is not None and evaluation['status']=='known' and type(evaluation['value']) is bool:
        text='조건을 만족합니다.' if evaluation['value'] else '조건을 만족하지 않습니다.'
    dimension=(evaluation or {}).get('dimension',result['compilation']['result_dimension'])
    label={'dimensionless':'무차원','boolean':'조건 판정'}.get(dimension,str(dimension))
    displayed=result.get('result_quantity')
    if displayed is not None:
        if displayed['status']=='known':text=readable_exact_quantity(displayed['value'])+' '+displayed['unit']
        label=str(displayed['dimension'])+(' · 변화량' if displayed['value_semantics']=='interval' else '')
    if result.get('calculation_context') is not None:
        text='명시한 가정을 전제로 한 계산: '+text
        label+=' · 실제 장비 적용 여부는 미확인'
    unit_links=[]
    for name,resolution in result.get('unit_definition_resolutions',{}).items():
        url=resolution.get('definition_evidence',{}).get('url')
        if url:unit_links.append('<a data-unit-source href="'+esc(url)+'">'+esc(name)+' 단위 근거</a>')
    unit_sources='<p>'+ ' · '.join(unit_links)+'</p>' if unit_links else ''
    input_rows=[]
    inputs=result.get('preview_inputs',{})
    hypothetical=inputs.get('scenario_values') is not None
    if hypothetical and inputs.get('observations') is not None:
        raise ValueError('NATIVE_FORMULA_INPUT_MODES_EXCLUSIVE')
    supplied=inputs.get('scenario_values') if hypothetical else inputs.get('observations')
    for binding,parameter in result['compilation'].get('parameters',{}).items():
        observed=(supplied or {}).get(binding)
        name=parameter.get('parameter_name') or binding
        value='입력 없음' if observed is None or observed.get('value') is None else str(observed['value'])+' '+str(observed['unit'])
        timestamp=('해당 없음(가상 입력)' if hypothetical else
            (observed or {}).get('observed_at') or '시각 미상')
        url=result.get('parameter_resolutions',{}).get(binding,{}).get('definition_evidence',{}).get('url')
        title=('<a href="'+esc(url)+'">'+esc(name)+'</a>') if url else esc(name)
        role=(parameter.get('semantic_descriptor') or {}).get('role')
        role_label={'measurement':'측정값','setpoint':'설정값','upper_limit':'상한','lower_limit':'하한','computed':'계산값'}.get(role,role or '미상')
        quantity_label=result.get('parameter_resolutions',{}).get(binding,{}).get('quantity_definition_resolution',{}).get('concept',{}).get('label',parameter.get('quantity',''))
        input_rows.append('<article data-formula-input><h3>'+title+'</h3><dl><dt>식의 입력</dt><dd>'+esc(binding)
            +'</dd><dt>역할</dt><dd>'+esc(role_label)
            +'</dd><dt>대상·물리량</dt><dd>'+esc(parameter.get('component',''))+' · '+esc(quantity_label)
            +'</dd><dt>'+('가상 입력값' if hypothetical else '제공된 값')+'</dt><dd>'+esc(value)
            +'</dd><dt>'+('관측 시각' if hypothetical else '제공된 시각')+'</dt><dd>'
            +esc(timestamp)+'</dd></dl></article>')
    input_section=('<section><h2>'+('계산에 사용한 가상 입력' if hypothetical else '계산에 사용한 입력')
        +'</h2><p>'+('호출자가 제공한 가상 시나리오 값입니다. 관측 시각이 없으며 장비 실측값이 아닙니다.'
            if hypothetical else '호출자가 제공한 미리보기 입력입니다. 장비 실측값을 확인한 기록이 아닙니다.')+'</p>'
        +''.join(input_rows)+'</section>') if input_rows else ''
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Formula 계산 결과</title><style>body{font-family:system-ui;max-width:900px;margin:auto;padding:24px;line-height:1.7;overflow-wrap:anywhere}pre{white-space:pre-wrap}details{margin-top:24px}</style>'
        '<body><h1>계산 결과</h1><p data-formula-value>'+esc(text)+'</p><p data-formula-dimension>'+esc(label)+'</p>'
        '<p data-formula-expression>'+esc(expression(result['compilation']['formula']['expression']))+'</p>'
        +unit_sources+input_section+
        '<p>저장 당시의 입력과 정의로 계산한 결과입니다. 현재 정의의 적용 가능성이나 장비의 현재 관측값을 확인한 결과는 아닙니다.</p>'
        '<details data-formula-details><summary>식·단위·입력과 실행 기록</summary><pre>'+esc(json.dumps(result,ensure_ascii=False,indent=2))+'</pre></details></body></html>')


@stage_timing('result_storage')
def retain_formula_execution(work, authorization, request, result):
    """Server-only writer using the existing atomic store; never a caller upload."""
    from .atomic_store_contract import AtomicWrite
    request=NativeFormulaRequest.model_validate(request)
    if result.get('request_digest')!=semantic_digest(request):
        raise ValueError('NATIVE_FORMULA_EXECUTION_REQUEST_MISMATCH')
    record={'contract_version':'boi/native-formula-execution@1',
        'principal':authorization.principal,'policy_digest':authorization.policy_digest,
        'request':request.model_dump(mode='json'),'result':result}
    import json
    record=json.loads(json.dumps(record,ensure_ascii=False))
    digest=semantic_digest(record)
    old=work.store.get('native_formula_executions',digest)
    if old is not None and old.get('record')!=record:
        raise ValueError('NATIVE_FORMULA_EXECUTION_CONFLICT')
    if old is None and not work.store.atomic_compare_and_write((AtomicWrite('native_formula_executions',digest,None,{'record':record}),)):
        if (work.store.get('native_formula_executions',digest) or {}).get('record')!=record:
            raise ValueError('NATIVE_FORMULA_EXECUTION_CONFLICT')
    return digest


@stage_timing('stored_record_read')
def read_formula_execution(work, authorization, digest):
    """Read an owned immutable result, without evaluating the Formula again."""
    row=work.store.get('native_formula_executions',digest)
    record=row.get('record') if row else None
    if (record is None or record.get('principal')!=authorization.principal
            or record.get('policy_digest')!=authorization.policy_digest):
        raise ValueError('NATIVE_FORMULA_EXECUTION_NOT_ACCESSIBLE')
    if semantic_digest(record)!=digest:
        raise ValueError('NATIVE_FORMULA_EXECUTION_DIGEST_MISMATCH')
    request=NativeFormulaRequest.model_validate(record['request'])
    if record.get('contract_version')!='boi/native-formula-execution@1' or record['result']['request_digest']!=semantic_digest(request):
        raise ValueError('NATIVE_FORMULA_EXECUTION_REQUEST_MISMATCH')
    return record
