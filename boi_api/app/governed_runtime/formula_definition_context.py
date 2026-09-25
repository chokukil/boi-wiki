"""Explicit conditional calculation over a reviewed source definition.

An authenticated interpretation is not a source quotation or a live binding.
Caller-supplied assumptions condition the mathematical result; they never settle
the source's unknowns. Unknown scope or assumptions keep evaluation unknown.
"""
from typing import Literal
from pydantic import Field, StrictBool, model_validator

from .semantic_binding_contract import FrozenContract, Ref, Digest, semantic_digest
from .knowledge_projection_contract import ProjectionScalar

CONTEXT_VERSION = 'boi/formula-definition-context@1'
REVIEW_VERSION = 'boi/source-formula-review@1'
SCOPE_VERSION = 'boi/formula-definition-scope@1'
BASIS = 'caller_supplied_definition_scenario'


class FormulaContextAssumption(FrozenContract):
    id: Ref
    statement: Ref
    meaning_pointers: tuple[str, ...] = Field(min_length=1, max_length=256)


class FormulaInputScope(FrozenContract):
    id: Ref
    assertion_id: Ref


class FormulaDefinitionContext(FrozenContract):
    contract_version: Literal['boi/formula-definition-context@1']
    assumptions: tuple[FormulaContextAssumption, ...] = Field(min_length=1, max_length=64)
    input_scope: tuple[FormulaInputScope, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode='after')
    def unique_bindings(self):
        pointers=[p for a in self.assumptions for p in a.meaning_pointers]
        if (len({a.id for a in self.assumptions}) != len(self.assumptions)
                or len({a.id for a in self.input_scope}) != len(self.input_scope)
                or len(set(pointers)) != len(pointers)):
            raise ValueError('FORMULA_CONTEXT_DUPLICATE_BINDING')
        return self


class FormulaScenarioInput(FrozenContract):
    contract_digest: Digest
    origin: Literal['caller_supplied_scenario']
    statement: Ref
    assumptions: dict[Ref, StrictBool | None] = Field(max_length=64)
    context_values: dict[Ref, ProjectionScalar] = Field(max_length=64)


def formula_context_support_contract():
    return {'contract_version':'boi/formula-definition-support@1',
        'review_contract_version':REVIEW_VERSION, 'scope_contract_version':SCOPE_VERSION,
        'purpose':'formula_input', 'claim_basis':BASIS,
        'parameter_assertion_kinds':['source_reported','interpretation'],
        'dependency_assertion_kind':'source_reported',
        'input_scope':'exact_reviewed_assertion_values',
        'assumptions':'explicit_caller_supplied_conditional_calculation',
        'missing_or_mismatched_context':'unknown', 'source_unknowns_resolved':False,
        'scientific_truth_granted':False, 'physical_execution_granted':False}


def context_obligation_pointers(pointer, node):
    return {f'{pointer}/uncertainties/{i}' for i in range(len(node.get('uncertainties', [])))} | {
        f'{pointer}/semantic_descriptor/{group}/{i}'
        for group in ('conditions','exceptions')
        for i in range(len(node['semantic_descriptor'][group]))}


def resolve_calculation_context(scope, pointer):
    node=scope['nodes'][pointer]
    raw=node.get('calculation_context')
    if raw is None:
        return None
    context=FormulaDefinitionContext.model_validate(raw)
    covered={p for a in context.assumptions for p in a.meaning_pointers}
    if covered != context_obligation_pointers(pointer,node):
        raise ValueError('FORMULA_CONTEXT_OBLIGATION_COVERAGE_REQUIRED')
    assertions={v['id']:(p,v) for p,v in scope['nodes'].items() if p.startswith('/assertions/')}
    bindings=[]
    for item in context.input_scope:
        if item.assertion_id not in assertions:
            raise ValueError('FORMULA_CONTEXT_SOURCE_DEPENDENCY_REQUIRED')
        address,assertion=assertions[item.assertion_id]
        if (assertion['assertion_kind']!='source_reported' or assertion['polarity']!='positive'
                or assertion['modality']!='asserted' or assertion['conditions']
                or assertion['exceptions'] or assertion['applicability'] or assertion['uncertainties']
                or assertion['value']['kind']=='object'):
            raise ValueError('FORMULA_CONTEXT_EXPLICIT_SCALAR_SCOPE_REQUIRED')
        bindings.append({'id':item.id, 'assertion_id':item.assertion_id,
            'meaning_pointer':address, 'expected_value':assertion['value'],
            'predicate':assertion['predicate'], 'statement':assertion['statement']})
    return {'contract_digest':semantic_digest(context), 'definition':context.model_dump(mode='json'),
        'input_scope':bindings, 'basis':BASIS, 'world_applicability':'not_verified'}


def evaluate_calculation_context(resolutions, supplied):
    checks,reasons={},[]
    expected={name for name,value in resolutions.items() if value.get('calculation_context') is not None}
    if set(supplied)-expected:
        raise ValueError('FORMULA_CONTEXT_UNEXPECTED_BINDING')
    for name in sorted(expected):
        context=resolutions[name]['calculation_context']
        sample=supplied.get(name)
        if sample is None:
            checks[name]={'status':'unknown','reason':'formula_context_missing'}
            reasons.append('formula_context_missing');continue
        sample=FormulaScenarioInput.model_validate(sample)
        if sample.contract_digest!=context['contract_digest']:
            raise ValueError('FORMULA_CONTEXT_DEFINITION_CHANGED')
        assumption_ids={v['id'] for v in context['definition']['assumptions']}
        scope_ids={v['id'] for v in context['input_scope']}
        if set(sample.assumptions)-assumption_ids or set(sample.context_values)-scope_ids:
            raise ValueError('FORMULA_CONTEXT_UNDECLARED_INPUT')
        assumptions=[{'id':v['id'],'statement':v['statement'],
            'provided':sample.assumptions.get(v['id']),
            'satisfied':sample.assumptions.get(v['id']) is True} for v in context['definition']['assumptions']]
        scope=[]
        for binding in context['input_scope']:
            value=sample.context_values.get(binding['id'])
            provided=value.model_dump(mode='json') if value is not None else None
            scope.append({**binding,'provided':provided,'satisfied':provided==binding['expected_value']})
        satisfied=all(v['satisfied'] for v in assumptions+scope)
        if not satisfied:reasons.append('formula_context_not_satisfied')
        checks[name]={'status':'satisfied' if satisfied else 'unknown',
            'contract_digest':context['contract_digest'],'origin':sample.origin,'statement':sample.statement,
            'assumptions':assumptions,'input_scope':scope}
    if not expected:
        return None
    return {'basis':BASIS,'status':'satisfied' if not reasons else 'unknown',
        'checks':checks,'reasons':sorted(set(reasons)), 'world_applicability':'not_verified',
        'source_unknowns_resolved':False,'live_observation_attested':False}
