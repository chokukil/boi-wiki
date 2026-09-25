"""Independent AST/closed-DSL preview interpreters; never executes Python/SQL.

Observations are explicitly supplied preview data, not live sensor readings.
Missingness uses three-valued logic; time rules must be explicitly supplied.
Compilation identity is checked, but an unsigned digest is not attestation.
"""
import ast
from datetime import datetime
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import operator
from pydantic import field_validator
from .formula_preview import UnitDefinition, compile_formula, decimal_text
from .semantic_binding_contract import semantic_digest,FrozenContract,Ref,RevisionRef
from .formula_numeric import exact_number,bounded,combine_dimensions

UNKNOWN = (None, None)


def _number(value):
    if isinstance(value, bool):raise ValueError('FORMULA_NONFINITE_VALUE')
    try:n = Decimal(str(value))
    except (InvalidOperation, ValueError):raise ValueError('FORMULA_NONFINITE_VALUE') from None
    if not n.is_finite():raise ValueError('FORMULA_NONFINITE_VALUE')
    return n


def _time(value):
    try:result = datetime.fromisoformat(value.replace('Z','+00:00'))
    except (AttributeError, ValueError):raise ValueError('FORMULA_TIME_INVALID') from None
    if result.tzinfo is None:raise ValueError('FORMULA_TIME_ZONE_REQUIRED')
    return result


class FormulaObservation(FrozenContract):
    """The same four fields consumed by both interpreters; null remains missing."""
    value: str | int | float | None
    unit: Ref
    revision: RevisionRef
    observed_at: str | None

    @field_validator('value',mode='before')
    @classmethod
    def finite_value(cls,value):
        if value is not None:_number(value)
        return value

    @field_validator('observed_at')
    @classmethod
    def zoned_time(cls,value):
        if value is not None:_time(value)
        return value


class FormulaScenarioValue(FrozenContract):
    """Caller supplied hypothetical number; it has no observation timestamp."""
    value: str | int | float | None
    unit: Ref
    revision: RevisionRef

    @field_validator('value',mode='before')
    @classmethod
    def finite_value(cls,value):
        if value is not None:_number(value)
        return value


class FormulaTimePolicy(FrozenContract):
    """Explicit preview evaluation time and freshness limits, never inferred."""
    now: str
    max_age_seconds: str | int | float | None
    max_skew_seconds: str | int | float | None

    @field_validator('now')
    @classmethod
    def zoned_time(cls,value):
        _time(value);return value

    @field_validator('max_age_seconds','max_skew_seconds',mode='before')
    @classmethod
    def nonnegative_duration(cls,value):
        if value is not None and _number(value)<0:raise ValueError('FORMULA_TIME_POLICY_INVALID')
        return value


class _Inputs:
    def __init__(self, compiled, observations, policy, unit_definitions=(), *, scenario=False):
        body = {k:v for k,v in compiled.items() if k!='compilation_digest'}
        if semantic_digest(body)!=compiled.get('compilation_digest'):
            raise ValueError('FORMULA_COMPILATION_CHANGED')
        catalog = {semantic_digest(v):v for v in compiled['parameters'].values()}
        rebuilt = compile_formula(compiled['formula'],catalog=list(catalog.values()),unit_definitions=compiled['unit_definitions'])
        if rebuilt != compiled:raise ValueError('FORMULA_COMPILATION_CHANGED')
        self.extended=compiled['formula']['contract_version']=='boi/formula-preview@2'
        if scenario:
            if policy is not None:raise ValueError('FORMULA_SCENARIO_TIME_POLICY_FORBIDDEN')
            now=None
        elif policy is None and self.extended and not compiled['parameters']:
            now=None
        else:
            if not isinstance(policy,dict) or set(policy)!={'now','max_age_seconds','max_skew_seconds'}:raise ValueError('FORMULA_TIME_POLICY_INVALID')
            now = _time(policy['now'])
            for name in ('max_age_seconds','max_skew_seconds'):
                if policy[name] is not None and _number(policy[name]) < 0:raise ValueError('FORMULA_TIME_POLICY_INVALID')
        self.compiled=compiled
        self.units={u['unit_id']:u for u in compiled['unit_definitions']}
        # Explicit observation units supplement the compiled expression's units.
        # They cannot replace a definition already bound to that expression.
        supplied = [UnitDefinition.model_validate(u).model_dump(mode='json') for u in unit_definitions]
        if len({u['unit_id'] for u in supplied}) != len(supplied):
            raise ValueError('FORMULA_UNIT_AMBIGUOUS')
        for definition in supplied:
            unit_id = definition['unit_id']
            if unit_id in self.units and UnitDefinition.model_validate(self.units[unit_id]) != UnitDefinition.model_validate(definition):
                raise ValueError('FORMULA_OBSERVATION_UNIT_DEFINITION_CONFLICT')
            self.units[unit_id] = definition
        self.parameters={}
        self.reasons=set()
        self.scenario=scenario
        timestamps=[]
        for name, parameter in compiled['parameters'].items():
            sample=observations.get(name)
            if sample is None:
                self.parameters[name]=UNKNOWN;self.reasons.add('missing');continue
            expected={'value','unit','revision'} if scenario else {'value','unit','revision','observed_at'}
            if set(sample)!=expected:raise ValueError('FORMULA_SCENARIO_VALUE_INVALID' if scenario else 'FORMULA_OBSERVATION_INVALID')
            if sample['revision']!=parameter['revision']:raise ValueError('FORMULA_OBSERVATION_REVISION_MISMATCH')
            if sample['unit'] not in self.units:raise ValueError('FORMULA_UNIT_NOT_FOUND')
            if self.units[sample['unit']]['dimension'] != self.units[parameter['unit']]['dimension']:
                raise ValueError('FORMULA_OBSERVATION_UNIT_MISMATCH')
            semantics=parameter.get('semantic_descriptor',{}).get('value_semantics','absolute')
            value=UNKNOWN if sample['value'] is None else self.quantity(sample['value'],sample['unit'],semantics)
            if scenario:
                # A hypothetical number is mathematically evaluable under the
                # selected definitions, but has no evidence of time or device.
                pass
            elif sample['observed_at'] is None:
                value=UNKNOWN;self.reasons.add('missing_time')
            else:
                time=_time(sample['observed_at']);age=_number((now-time).total_seconds());timestamps.append(time)
                if age<0:value=UNKNOWN;self.reasons.add('future_observation')
                elif policy['max_age_seconds'] is None:value=UNKNOWN;self.reasons.add('freshness_policy_missing')
                elif age>_number(policy['max_age_seconds']):value=UNKNOWN;self.reasons.add('stale')
                scope=parameter.get('semantic_descriptor',{}).get('scope',{})
                start,end=scope.get('effective_from'),scope.get('effective_until')
                # Definition applicability is [from, until) at observation time,
                # independently of freshness at evaluation time. Unspecified
                # bounds add no constraint; they do not attest temporal coverage.
                if ((start is not None and time<_time(start)) or
                        (end is not None and time>=_time(end))):
                    value=UNKNOWN;self.reasons.add('definition_time_out_of_scope')
            if sample['value'] is None:self.reasons.add('null')
            self.parameters[name]=value
        self.alignment_unknown=False
        if not scenario and len(compiled['parameters'])>1:
            if policy['max_skew_seconds'] is None:self.alignment_unknown=True;self.reasons.add('alignment_policy_missing')
            elif len(timestamps)>1 and _number((max(timestamps)-min(timestamps)).total_seconds())>_number(policy['max_skew_seconds']):
                self.alignment_unknown=True;self.reasons.add('unaligned')

    def quantity(self, value, unit, semantics='absolute'):
        if unit not in self.units:raise ValueError('FORMULA_UNIT_NOT_FOUND')
        definition=self.units[unit]
        if self.extended:
            result=bounded(exact_number(value)*exact_number(definition['scale']))
            result=bounded(result/exact_number(definition['scale_denominator']))
            if semantics!='interval':result=bounded(result+exact_number(definition['offset']))
            return result,definition['dimension']
        return (Fraction(_number(value))*Fraction(_number(definition['scale'])) /
                Fraction(_number(definition['scale_denominator'])) + (0 if semantics=='interval' else Fraction(_number(definition['offset']))),
                definition['dimension'])

    def result(self, value):
        if self.alignment_unknown:value=UNKNOWN
        val,dimension=value
        return {'status':'unknown' if val is None else 'known',
                **({'input_mode':'hypothetical','definition_time_verified':False}
                    if self.scenario else {}),
                **({'value_semantics':self.compiled['result_value_semantics']} if 'result_value_semantics' in self.compiled else {}),
                'value':str(val) if isinstance(val,Fraction) else decimal_text(val) if isinstance(val,Decimal) else val,
                'dimension':self.compiled['result_dimension'] if val is None else dimension,
                'reasons':sorted(self.reasons) if val is None else [],
                'live_execution_ready':False,'canonical_projection_eligible':False}


def evaluate_ast(compiled, observations, policy, *, unit_definitions=(), scenario=False):
    env=_Inputs(compiled,observations,policy,unit_definitions,scenario=scenario)
    def visit(node):
        kind=node['kind']
        if kind=='quantity':return env.quantity(node['value'],node['unit'],node.get('value_semantics','absolute'))
        if kind=='scalar':return exact_number(node['value']),'dimensionless'
        if kind=='parameter':return env.parameters[node['binding']]
        if kind=='arithmetic':
            a,b=visit(node['left']),visit(node['right']);op=node['operator']
            if op=='divide' and b[0]==0:raise ValueError('FORMULA_DIVISION_BY_ZERO')
            if a[0] is None or b[0] is None:return UNKNOWN
            if op=='add':value,dimension=a[0]+b[0],a[1]
            elif op=='subtract':value,dimension=a[0]-b[0],a[1]
            elif op=='multiply':value,dimension=a[0]*b[0],combine_dimensions(a[1],b[1])
            else:value,dimension=a[0]/b[0],combine_dimensions(a[1],b[1],divide=True)
            return bounded(value),dimension
        if kind=='compare':
            a,b=visit(node['left']),visit(node['right'])
            if a[0] is None or b[0] is None:return UNKNOWN
            op=node['operator'];x,y=a[0],b[0]
            if op=='lt':value=x<y
            elif op=='le':value=x<=y
            elif op=='eq':value=x==y
            elif op=='ne':value=x!=y
            elif op=='ge':value=x>=y
            else:value=x>y
            return (value,'boolean')
        if kind=='not':
            v=visit(node['argument'])[0]
            return UNKNOWN if v is None else (not v,'boolean')
        if kind=='boolean':
            values=[visit(n)[0] for n in node['arguments']]
            if node['operator']=='and':
                if False in values:return (False,'boolean')
                if None in values:return UNKNOWN
                return (True,'boolean')
            if True in values:return (True,'boolean')
            if None in values:return UNKNOWN
            return (False,'boolean')
        if kind=='if':
            condition=visit(node['condition'])[0]
            if condition is None:return UNKNOWN
            return visit(node['when_true'] if condition else node['when_false'])
        raise ValueError('FORMULA_NODE_UNSUPPORTED')
    return env.result(visit(compiled['formula']['expression']))


def evaluate_dsl(compiled, observations, policy, *, unit_definitions=(), scenario=False):
    """Interpret parsed DSL syntax directly, without reconstructing or walking AST."""
    env=_Inputs(compiled,observations,policy,unit_definitions,scenario=scenario)
    try:root=ast.parse(compiled['dsl'],mode='eval').body
    except (SyntaxError, RecursionError):raise ValueError('FORMULA_DSL_INVALID') from None
    def execute(node):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Name) or node.keywords:
            raise ValueError('FORMULA_DSL_INVALID')
        name=node.func.id;args=node.args
        def strings(count):
            if len(args)!=count or any(not isinstance(n,ast.Constant) or not isinstance(n.value,str) for n in args):raise ValueError('FORMULA_DSL_INVALID')
            return [n.value for n in args]
        if name=='quantity':return env.quantity(*strings(2))
        if name=='interval_quantity':return env.quantity(*strings(2),semantics='interval')
        if name=='parameter':return env.parameters[strings(1)[0]]
        if name=='scalar':return exact_number(strings(1)[0]),'dimensionless'
        if name=='choose':
            if len(args)!=3:raise ValueError('FORMULA_DSL_INVALID')
            c=execute(args[0])[0]
            if c is None:return UNKNOWN
            return execute(args[1] if c else args[2])
        values=[execute(n) for n in args]
        if name in ('add','subtract','multiply','divide'):
            if len(values)!=2:raise ValueError('FORMULA_DSL_INVALID')
            (left,ld),(right,rd)=values
            if name=='divide' and right==0:raise ValueError('FORMULA_DIVISION_BY_ZERO')
            if left is None or right is None:return UNKNOWN
            operations={'add':operator.add,'subtract':operator.sub,'multiply':operator.mul,'divide':operator.truediv}
            dimension=ld if name in ('add','subtract') else combine_dimensions(ld,rd,divide=name=='divide')
            return bounded(operations[name](left,right)),dimension
        if name in ('lt','le','eq','ne','ge','gt'):
            if len(values)!=2:raise ValueError('FORMULA_DSL_INVALID')
            left,right=values[0][0],values[1][0]
            if left is None or right is None:return UNKNOWN
            # Comparison dispatch is independent from the typed-tree visitor.
            operators={'lt':operator.lt,'le':operator.le,'eq':operator.eq,
                       'ne':operator.ne,'ge':operator.ge,'gt':operator.gt}
            return (operators[name](left,right),'boolean')
        if name=='negate':
            if len(values)!=1:raise ValueError('FORMULA_DSL_INVALID')
            value=values[0][0]
            return UNKNOWN if value is None else (value is False,'boolean')
        if name in ('all_of','any_of'):
            if len(values)<2:raise ValueError('FORMULA_DSL_INVALID')
            decisive=False if name=='all_of' else True
            if any(v[0] is decisive for v in values):return (decisive,'boolean')
            if any(v[0] is None for v in values):return UNKNOWN
            return (not decisive,'boolean')
        raise ValueError('FORMULA_DSL_INVALID')
    return env.result(execute(root))
