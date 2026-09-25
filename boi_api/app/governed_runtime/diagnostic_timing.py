"""Lazy timing adapter: domain modules do not import the web router at load time."""
from functools import wraps

def stage_timing(stage):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            from ..v2.native_formula_timing import timed_call
            return timed_call(stage, function, *args, **kwargs)
        return measured
    return decorate
