"""Request-local Formula timings, outside retained computation identities.

Only server-selected stage names, counters and durations are emitted. Inputs,
identities, paths, exception messages and source content never enter the log.
"""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import json
import logging
import time
import uuid

_CURRENT = ContextVar('native_formula_timing', default=None)


def timed_call(stage, function, *args, **kwargs):
    timings = _CURRENT.get()
    if timings is None:
        return function(*args, **kwargs)
    started = time.perf_counter()
    failed = True
    try:
        result = function(*args, **kwargs)
        failed = False
        return result
    finally:
        entry = timings.setdefault(stage, {'calls': 0, 'seconds': 0.0, 'failures': 0})
        entry['calls'] += 1
        entry['seconds'] += time.perf_counter() - started
        entry['failures'] += int(failed)


def stage_timing(stage):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            return timed_call(stage, function, *args, **kwargs)
        return measured
    return decorate


def request_timing(action):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            stages = {}
            token = _CURRENT.set(stages)
            started = time.perf_counter()
            request_id = str(uuid.uuid4())
            outcome = 'error'
            try:
                result = function(*args, **kwargs)
                outcome = 'returned'
            finally:
                _CURRENT.reset(token)
                timing = {'contract_version': 'boi/native-formula-timing@1',
                    'request_id': request_id, 'action': action, 'outcome': outcome,
                    'native_dispatch_seconds': time.perf_counter() - started,
                    'stages': stages, 'nested_stage_times_are_not_additive': True,
                    'excludes': 'MCP transport, external agent and final user delivery'}
                try:
                    logging.getLogger(__name__).info('native_formula_timing %s', json.dumps(timing))
                except Exception:
                    # A failed telemetry handler must not hide the real error
                    # or report a persisted computation as a failed execution.
                    timing['logging_failed'] = True
            # The underlying function has already persisted or read the exact
            # execution. Timing must not mutate that object or its digest.
            return {**result, 'timing': timing}
        return measured
    return decorate


@contextmanager
def collect_stage_timings():
    """Collect only named stage counters; never cache source/authority data."""
    stages = {}
    token = _CURRENT.set(stages)
    try:
        yield stages
    finally:
        _CURRENT.reset(token)
