"""Mechanical parameter-definition adapter; no inferred units or live values."""
import json

from .common_knowledge_contract import resolve_quantity_concept
from .formula_preview import UnitDefinition
from .knowledge_content import decode_knowledge_content


CAPABILITY = 'formula_parameter_definitions'


def definition_meaning(value):
    content=decode_knowledge_content(value)
    return content.meaning if content is not None else value


def check_parameter_definitions(parameter, asset, read_revision):
    """Read the exact declared dependencies through the caller's authority."""
    for revision,role in ((parameter.unit_definition,'semantic_unit_definition'),
                          (parameter.quantity_definition,'semantic_quantity_definition')):
        if not any(d.revision==revision and d.required and d.role==role
                   and {'review','explain','execute'}<=set(d.stages) for d in asset.dependencies):
            raise ValueError('KNOWLEDGE_FORMULA_REQUIRED_DEPENDENCY_MISSING')
    _,unit_asset=read_revision(parameter.unit_definition)
    _,quantity_asset=read_revision(parameter.quantity_definition)
    value=definition_meaning(json.loads(unit_asset.content_json))
    if (unit_asset.kind!='definition' or quantity_asset.kind!='definition'
            or not isinstance(value,dict) or value.get('contract_version')!='boi/native-unit-interpretation@1'
            or not isinstance(value.get('unit_definition'),dict) or 'revision' in value['unit_definition']):
        raise ValueError('KNOWLEDGE_FORMULA_UNIT_DEFINITION_REQUIRED')
    unit=UnitDefinition.model_validate({**value['unit_definition'],'revision':unit_asset.revision})
    descriptor=parameter.semantic_descriptor
    if (unit.unit_id!=descriptor.unit_ref or unit.revision!=parameter.unit_definition
            or unit.revision.revision_digest!=descriptor.unit_revision_digest):
        raise ValueError('KNOWLEDGE_FORMULA_UNIT_DEFINITION_MISMATCH')
    quantity=resolve_quantity_concept(definition_meaning(json.loads(quantity_asset.content_json)),quantity_asset.revision,parameter.quantity)
    if quantity['concept'].get('quantity_dimension')!=unit.dimension:
        raise ValueError('KNOWLEDGE_FORMULA_QUANTITY_DIMENSION_MISMATCH')
    if quantity['conditions']:
        raise ValueError('KNOWLEDGE_FORMULA_QUANTITY_CONTEXT_UNSUPPORTED')
    return unit,quantity


def formula_scope_reasons(scope):
    """Check explicit numeric definitions and declared calculation obligations.

    Conditional definitions also need a registered full-inventory review and
    explicit caller context at execution. Neither proves world applicability.
    """
    reasons=[]
    if not scope['roots'] or any(not p.startswith('/parameters/') for p in scope['roots']):
        reasons.append('FORMULA_PARAMETER_ROOT_REQUIRED')
    for pointer,node in scope['nodes'].items():
        contextual=pointer.startswith('/parameters/') and node.get('calculation_context') is not None
        if contextual:
            from .formula_definition_context import resolve_calculation_context
            try:resolve_calculation_context(scope,pointer)
            except ValueError as exc:reasons.append(str(exc))
        if node.get('uncertainties') and not contextual:
            reasons.append('FORMULA_DEFINITION_UNCERTAINTY_UNRESOLVED')
        if pointer.startswith('/parameters/'):
            descriptor=node['semantic_descriptor'];time=descriptor['scope']
            if descriptor['role'] not in ('measurement','setpoint','upper_limit','lower_limit','computed'):
                reasons.append('FORMULA_NUMERIC_ROLE_REQUIRED')
            if ((descriptor['conditions'] or descriptor['exceptions']) and not contextual
                    or time['effective_from'] is not None or time['effective_until'] is not None):
                reasons.append('FORMULA_CONTEXT_EVALUATOR_REQUIRED')
        elif (node['polarity']!='positive' or node['modality']!='asserted'
                or node['conditions'] or node['exceptions'] or node['applicability']
                or node['valid_time']['state']=='interval'):
            reasons.append('FORMULA_CONTEXT_EVALUATOR_REQUIRED')
    return list(dict.fromkeys(reasons))
