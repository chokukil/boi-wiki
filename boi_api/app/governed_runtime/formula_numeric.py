"""Exact arithmetic limits and dimensional algebra shared by Formula consumers."""
from decimal import Decimal,InvalidOperation
from fractions import Fraction


def exact_number(value):
    if isinstance(value,bool):raise ValueError('FORMULA_NUMBER_INVALID')
    try:decimal=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError('FORMULA_NUMBER_INVALID') from None
    if not decimal.is_finite():raise ValueError('FORMULA_NONFINITE_VALUE')
    parts=decimal.as_tuple()
    if len(parts.digits)>64:raise ValueError('FORMULA_INPUT_DIGIT_LIMIT')
    # Check the exponent before Fraction can allocate a huge power of ten.
    if abs(parts.exponent)+len(parts.digits)>1233:raise ValueError('FORMULA_INTERMEDIATE_BIT_LIMIT')
    return bounded(Fraction(decimal))


def bounded(value):
    if value.numerator.bit_length()>4096 or value.denominator.bit_length()>4096:
        raise ValueError('FORMULA_INTERMEDIATE_BIT_LIMIT')
    return value


def dimension_terms(dimension):
    if dimension=='dimensionless':return {}
    if isinstance(dimension,str):return {dimension:1}
    return dict(dimension['exponents'])


def combine_dimensions(left,right,*,divide=False):
    result=dimension_terms(left)
    for key,power in dimension_terms(right).items():
        result[key]=result.get(key,0)+(-power if divide else power)
        if not result[key]:del result[key]
    if not result:return 'dimensionless'
    if len(result)==1 and next(iter(result.values()))==1:return next(iter(result))
    return {'exponents':dict(sorted(result.items()))}
