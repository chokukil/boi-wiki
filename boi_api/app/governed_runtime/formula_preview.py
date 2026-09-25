"""Typed, non-executing Formula preview compiler.

The DSL below is a closed preview language, not an equipment vendor language.
Unit definitions are explicit candidate inputs with pinned revisions. Their
physical meaning/scale requires source review; compilation proves type checks,
not unit-definition truth, semantic intent, policy approval or live binding.
"""
from __future__ import annotations
from decimal import Decimal
import ast
import json
from typing import Annotated, Literal, Union
from pydantic import Field, TypeAdapter, model_validator
from .semantic_binding_contract import FrozenContract, Ref, RevisionRef, semantic_digest
from .svid_contract import ParameterSelection, resolve_parameter


class UnitDefinition(FrozenContract):
    unit_id: Ref
    dimension: Ref
    scale: Decimal = Field(gt=0, allow_inf_nan=False)
    scale_denominator: Decimal = Field(default=Decimal(1), gt=0, allow_inf_nan=False)
    offset: Decimal = Field(allow_inf_nan=False)
    revision: RevisionRef


class Quantity(FrozenContract):
    kind: Literal['quantity']
    value: Decimal = Field(allow_inf_nan=False)
    unit: Ref
    value_semantics: Literal['absolute','interval'] = Field(default='absolute',exclude_if=lambda v:v=='absolute')


class Parameter(FrozenContract):
    kind: Literal['parameter']
    binding: Ref


class Scalar(FrozenContract):
    kind: Literal['scalar']
    value: Decimal = Field(allow_inf_nan=False)


class Arithmetic(FrozenContract):
    kind: Literal['arithmetic']
    operator: Literal['add','subtract','multiply','divide']
    left: Expression
    right: Expression


class Compare(FrozenContract):
    kind: Literal['compare']
    operator: Literal['lt','le','eq','ne','ge','gt']
    left: Expression
    right: Expression


class Boolean(FrozenContract):
    kind: Literal['boolean']
    operator: Literal['and','or']
    arguments: tuple[Expression, ...] = Field(min_length=2, max_length=64)


class Negate(FrozenContract):
    kind: Literal['not']
    argument: Expression


class Choose(FrozenContract):
    kind: Literal['if']
    condition: Expression
    when_true: Expression
    when_false: Expression


Expression = Annotated[Union[Quantity,Parameter,Scalar,Arithmetic,Compare,Boolean,Negate,Choose],Field(discriminator='kind')]
for _model in (Arithmetic, Compare, Boolean, Negate, Choose):
    _model.model_rebuild()


class Formula(FrozenContract):
    contract_version: Literal['boi/formula-preview@1','boi/formula-preview@2']
    parameters: dict[Ref, ParameterSelection]
    expression: Expression

    @model_validator(mode='before')
    @classmethod
    def expression_limits(cls,value):
        if not isinstance(value,dict):return value
        extended=value.get('contract_version')=='boi/formula-preview@2'
        stack=[(value.get('expression'),0)];count=0
        while stack:
            node,depth=stack.pop()
            if hasattr(node,'model_dump'):node=node.model_dump(mode='json')
            if not isinstance(node,dict):continue
            count+=1
            if count>(256 if extended else 2048) or depth>(16 if extended else 64):
                raise ValueError('FORMULA_COMPLEXITY_LIMIT')
            if node.get('kind') in ('scalar','arithmetic') and not extended:
                raise ValueError('FORMULA_V2_REQUIRED')
            if extended and node.get('kind') in ('scalar','quantity'):
                from .formula_numeric import exact_number
                exact_number(node.get('value'))
            for key in ('left','right','argument','condition','when_true','when_false'):
                if key in node:stack.append((node[key],depth+1))
            stack.extend((child,depth+1) for child in node.get('arguments',()))
        return value


def decimal_text(value):
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return '0' if Decimal(text) == 0 else text


def parse_formula_dsl(dsl):
    """Read only the declared preview grammar, without evaluating Python."""
    if not isinstance(dsl, str) or len(dsl) > 262144:
        raise ValueError('FORMULA_DSL_INVALID')
    try:
        root = ast.parse(dsl, mode='eval').body
    except (SyntaxError, RecursionError):
        raise ValueError('FORMULA_DSL_INVALID') from None
    count = 0
    def read(node, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > 2048:
            raise ValueError('FORMULA_COMPLEXITY_LIMIT')
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name) or node.keywords:
            raise ValueError('FORMULA_DSL_INVALID')
        name, args = node.func.id, node.args
        def text_args(length):
            if len(args) != length or any(not isinstance(n, ast.Constant) or not isinstance(n.value, str) for n in args):
                raise ValueError('FORMULA_DSL_INVALID')
            return [n.value for n in args]
        if name in ('quantity','interval_quantity'):
            value, unit = text_args(2)
            return {'kind':'quantity', 'value':value, 'unit':unit,
                **({'value_semantics':'interval'} if name=='interval_quantity' else {})}
        if name == 'parameter':
            return {'kind':'parameter', 'binding':text_args(1)[0]}
        if name == 'scalar':
            return {'kind':'scalar','value':text_args(1)[0]}
        children = [read(n, depth+1) for n in args]
        if name in ('add','subtract','multiply','divide') and len(children)==2:
            return {'kind':'arithmetic','operator':name,'left':children[0],'right':children[1]}
        if name in ('lt','le','eq','ne','ge','gt') and len(children) == 2:
            return {'kind':'compare', 'operator':name, 'left':children[0], 'right':children[1]}
        if name in ('all_of','any_of') and len(children) >= 2:
            return {'kind':'boolean', 'operator':'and' if name=='all_of' else 'or', 'arguments':children}
        if name == 'negate' and len(children) == 1:
            return {'kind':'not', 'argument':children[0]}
        if name == 'choose' and len(children) == 3:
            return {'kind':'if', 'condition':children[0], 'when_true':children[1], 'when_false':children[2]}
        raise ValueError('FORMULA_DSL_INVALID')
    return TypeAdapter(Expression).validate_python(read(root)).model_dump(mode='json')


def compile_formula(formula, *, catalog, unit_definitions):
    formula = Formula.model_validate(formula)
    definitions = [UnitDefinition.model_validate(d) for d in unit_definitions]
    units = {d.unit_id:d for d in definitions}
    if len(units) != len(definitions):
        raise ValueError('FORMULA_UNIT_AMBIGUOUS')
    # Every binding is exact and ACL must already have been checked by Wiki.
    parameters = {k:resolve_parameter(catalog, v.model_dump(mode='json'))['parameter']
                  for k,v in formula.parameters.items()}
    used_parameters, used_units = set(), set()
    count = 0
    uses_interval = False
    extended=formula.contract_version=='boi/formula-preview@2'
    if extended:
        from .formula_numeric import exact_number
        for definition in definitions:
            for field in ('scale','scale_denominator','offset'):exact_number(getattr(definition,field))
    def unit(name):
        if name not in units:
            raise ValueError('FORMULA_UNIT_NOT_FOUND')
        used_units.add(name)
        return units[name]
    def walk(node, depth=0):
        nonlocal count, uses_interval
        count += 1
        if depth > (16 if extended else 64) or count > (256 if extended else 2048):
            raise ValueError('FORMULA_COMPLEXITY_LIMIT')
        def child(n):return walk(n, depth+1)
        def numeric_pair(left, right):
            if left[0] not in ('quantity','interval_quantity') or right[0] not in ('quantity','interval_quantity') or left[1] != right[1]:
                raise ValueError('FORMULA_DIMENSION_MISMATCH')
            if left[0]!=right[0]:raise ValueError('FORMULA_VALUE_SEMANTICS_MISMATCH')
        if isinstance(node, Quantity):
            dimension = unit(node.unit).dimension
            kind='interval_quantity' if node.value_semantics=='interval' else 'quantity'
            if node.value_semantics=='interval':uses_interval=True
            return (kind, dimension, kind+'('+json.dumps(str(node.value) if extended else decimal_text(node.value))+','+json.dumps(node.unit)+')',
                node.value_semantics=='absolute' and units[node.unit].offset!=0)
        if isinstance(node, Scalar):
            return ('quantity','dimensionless','scalar('+json.dumps(str(node.value))+')',False)
        if isinstance(node, Parameter):
            if node.binding not in parameters:
                raise ValueError('FORMULA_PARAMETER_NOT_FOUND')
            used_parameters.add(node.binding)
            u = unit(parameters[node.binding]['unit'])
            meaning=parameters[node.binding].get('semantic_descriptor')
            if meaning and meaning['unit_semantics']=='declared':
                if meaning['unit_ref']!=u.unit_id:raise ValueError('FORMULA_PARAMETER_UNIT_REFERENCE_MISMATCH')
                if meaning['unit_revision_digest']!=u.revision.revision_digest:
                    raise ValueError('FORMULA_PARAMETER_UNIT_REVISION_MISMATCH')
            elif meaning:
                if meaning['unit_semantics']=='unknown':raise ValueError('FORMULA_PARAMETER_UNIT_UNRESOLVED')
                if meaning['unit_semantics']=='not_applicable':raise ValueError('FORMULA_PARAMETER_NUMERIC_UNIT_NOT_APPLICABLE')
                if u.dimension!='dimensionless':raise ValueError('FORMULA_PARAMETER_DIMENSIONLESS_UNIT_REQUIRED')
            semantics=meaning['value_semantics'] if meaning else 'absolute'
            if semantics not in ('absolute','interval'):raise ValueError('FORMULA_PARAMETER_VALUE_SEMANTICS_UNRESOLVED')
            if semantics=='interval':uses_interval=True
            return ('interval_quantity' if semantics=='interval' else 'quantity', u.dimension, 'parameter('+json.dumps(node.binding)+')',
                semantics=='absolute' and u.offset!=0)
        if isinstance(node, Arithmetic):
            from .formula_numeric import combine_dimensions
            left,right=child(node.left),child(node.right)
            if left[0] not in ('quantity','interval_quantity') or right[0] not in ('quantity','interval_quantity'):
                raise ValueError('FORMULA_NUMERIC_REQUIRED')
            affine=left[3] or right[3]
            if node.operator in ('add','subtract'):
                if left[1]!=right[1]:raise ValueError('FORMULA_DIMENSION_MISMATCH')
                dimension=left[1]
                if node.operator=='add':
                    if affine and left[0]==right[0]=='quantity':raise ValueError('FORMULA_AFFINE_ADDITION_INVALID')
                    kind='interval_quantity' if left[0]==right[0]=='interval_quantity' else 'quantity'
                else:
                    if left[0]=='interval_quantity' and right[0]=='quantity':raise ValueError('FORMULA_VALUE_SEMANTICS_MISMATCH')
                    kind='quantity' if left[0]=='quantity' and right[0]=='interval_quantity' else 'interval_quantity'
                    if kind=='interval_quantity':affine=False
            else:
                if affine:raise ValueError('FORMULA_AFFINE_PRODUCT_INVALID')
                dimension=combine_dimensions(left[1],right[1],divide=node.operator=='divide')
                kind=(left[0] if right[1]=='dimensionless' else right[0]
                    if left[1]=='dimensionless' and node.operator=='multiply' else 'quantity')
            return (kind,dimension,node.operator+'('+left[2]+','+right[2]+')',affine)
        if isinstance(node, Compare):
            left, right = child(node.left), child(node.right)
            numeric_pair(left, right)
            return ('boolean', 'boolean', node.operator+'('+left[2]+','+right[2]+')',False)
        if isinstance(node, Boolean):
            args = [child(n) for n in node.arguments]
            if any(a[0] != 'boolean' for a in args):raise ValueError('FORMULA_BOOLEAN_REQUIRED')
            return ('boolean', 'boolean', ('all_of' if node.operator=='and' else 'any_of')+'('+','.join(a[2] for a in args)+')',False)
        if isinstance(node, Negate):
            arg = child(node.argument)
            if arg[0] != 'boolean':raise ValueError('FORMULA_BOOLEAN_REQUIRED')
            return ('boolean', 'boolean', 'negate('+arg[2]+')',False)
        if isinstance(node, Choose):
            condition, yes, no = child(node.condition), child(node.when_true), child(node.when_false)
            if condition[0] != 'boolean':raise ValueError('FORMULA_BOOLEAN_REQUIRED')
            if yes[:2] != no[:2]:raise ValueError('FORMULA_BRANCH_TYPE_MISMATCH')
            return (*yes[:2], 'choose('+condition[2]+','+yes[2]+','+no[2]+')',yes[3] or no[3])
        raise ValueError('FORMULA_NODE_UNSUPPORTED')
    result_type, dimension, dsl, _ = walk(formula.expression)
    if used_parameters != set(parameters):raise ValueError('FORMULA_UNUSED_PARAMETER')
    selected_units = [u.model_dump(mode='json') for u in definitions if u.unit_id in used_units]
    # Decimal lexical scale (1.00 vs 1) is not a Formula numeric-value change.
    # Keep the original typed input in the compilation record; compare typed
    # nodes so units/operators/references remain exact without string equality.
    if TypeAdapter(Expression).validate_python(parse_formula_dsl(dsl)) != formula.expression:
        raise ValueError('FORMULA_ROUNDTRIP_MISMATCH')
    result = {'contract_version':'boi/formula-compilation@2','dsl_contract':'boi/formula-preview-dsl@3' if extended else 'boi/formula-preview-dsl@2' if uses_interval else 'boi/formula-preview-dsl@1',
              'formula':formula.model_dump(mode='json'), 'dsl':dsl, 'result_type':'quantity' if result_type=='interval_quantity' else result_type,
              **({'result_value_semantics':'interval'} if result_type=='interval_quantity' else {}),
              'result_dimension':dimension, 'parameters':parameters, 'unit_definitions':selected_units,
              'unit_revisions':[u['revision'] for u in selected_units],
              'live_execution_ready':False, 'canonical_projection_eligible':False}
    return {**result, 'compilation_digest':semantic_digest(result)}
