"""Request-local storage-operation counts; never keys, payloads or authority."""
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from .native_formula_timing import collect_stage_timings

_observers = ContextVar('boi_store_read_observers', default=())


def record_store_read(collection, operation):
    for counts in _observers.get():
        counts[(collection, operation)] += 1


@contextmanager
def observe_store_reads():
    counts = Counter()
    token = _observers.set((*_observers.get(), counts))
    try:
        yield counts
    finally:
        _observers.reset(token)


def observe_native_result(operation):
    """Attach counters after result construction; never alter a stored receipt.

    This is one server operation, excluding external agent work and delivery.
    Only adapter calls are counted; no inference/embedding count is invented.
    """
    started = perf_counter()
    with observe_store_reads() as reads, collect_stage_timings() as stages:
        result = operation()
    return {**result, 'runtime_observation': {
        'server_seconds': perf_counter() - started,
        'stages': stages,
        'stage_times_are_not_additive': True,
        'catalog_head_scan_calls': reads[('domain_asset_heads', 'list')]
            + reads[('domain_asset_heads', 'list_key_page')],
        'catalog_head_point_read_calls': reads[('domain_asset_heads', 'get')],
        'catalog_namespace_page_calls': reads[('domain_asset_catalogs', 'list_key_page')],
        'measurement_basis': 'request_local_store_adapter_calls',
        'scope': 'This server operation only; not final answer latency, complete candidate relevance, '
                 'embedding telemetry or semantic quality. Stored answer and evidence are unchanged.'}}
