"""Optional native-query presentation; never an execution or authority contract.

The API retains its full records. This view removes repeated planning context and
replaces byte-equivalent JSON structures with local references. It does not rank
meanings, shorten definitions, select rows or alter the input submitted for planning.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any, Literal


ResponseView = Literal['full', 'agent']
_CONTRACTS = {
    'prepare': 'boi/native-query-preparation@1',
    'plan': 'boi/native-query-host-plan@1',
    'execute': 'boi/native-query-host-execution@1',
    'result': 'boi/native-query-host-result@1',
}


def _pointer(path: str, key: Any) -> str:
    return path + '/' + str(key).replace('~', '~0').replace('/', '~1')


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def _reserved_reference(value: Any) -> bool:
    if isinstance(value, dict):
        return (set(value) == {'response_ref'} or 'logical_payload_ref' in value
                or any(_reserved_reference(item) for item in value.values()))
    return isinstance(value, list) and any(_reserved_reference(item) for item in value)


class _References:
    """Only equal JSON objects/arrays can share a local presentation reference."""

    def __init__(self):
        self.seen: dict[str, str] = {}

    def seed(self, value: Any, path: str) -> None:
        if not isinstance(value, (dict, list)):
            return
        encoded = _json(value)
        if len(encoded) >= 300:
            self.seen.setdefault(encoded, path)
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for key, item in items:
            self.seed(item, _pointer(path, key))

    def compact(self, value: Any, path: str, protected: set[str]) -> Any:
        if path in protected:
            return value
        if not isinstance(value, (dict, list)):
            return value
        encoded = _json(value)
        if len(encoded) >= 300:
            previous = self.seen.get(encoded)
            if previous is not None and previous != path:
                return {'response_ref': previous}
            self.seen.setdefault(encoded, path)
        if isinstance(value, dict):
            return {key: self.compact(item, _pointer(path, key), protected)
                    for key, item in value.items()}
        return [self.compact(item, _pointer(path, index), protected)
                for index, item in enumerate(value)]


def _prepare(value: dict[str, Any]) -> None:
    bundle = value.get('semantic_bundle')
    native = value.get('native_input')
    if not isinstance(bundle, dict) or not isinstance(native, dict):
        return
    # Keep every capability, availability, quality receipt and unselected entry.
    # Only exact overlapping logical payload fields move to the already intact
    # native_input. Unknown/new payload fields stay alongside that reference.
    contexts = native.get('logical_context')
    entries = bundle.get('domain_entries')
    if isinstance(contexts, list) and isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('payload'), dict):
                continue
            for index, context in enumerate(contexts):
                if (not isinstance(context, dict)
                        or context.get('entry_id') != entry.get('entry_id')
                        or context.get('revision_digest') != entry.get('revision_digest')
                        or not isinstance(context.get('logical_payload'), dict)):
                    continue
                payload = entry['payload']
                logical = context['logical_payload']
                # Partial equality must not silently hide a conflicting condition.
                if not logical or any(key not in payload or payload[key] != item
                                      for key, item in logical.items()):
                    continue
                entry['payload'] = {key: item for key, item in payload.items() if key not in logical}
                entry['logical_payload_ref'] = f'#/native_input/logical_context/{index}/logical_payload'
                break
    value['profile_context'] = value.pop('semantic_bundle')


def _plan(value: dict[str, Any], omitted: list[str]) -> None:
    planned = value.get('planned')
    if not isinstance(planned, dict):
        return
    context = planned.get('planning_context')
    if isinstance(context, dict):
        # The exact preparation supplied these definitions. Keep the current
        # context's identity, policy and availability; do not repeat its entire
        # inventory or the physical catalog in the agent's plan confirmation.
        bundle = context.get('bundle')
        if isinstance(bundle, dict):
            for key in ('domain_entries', 'mapping_entries', 'query_entries'):
                if key in bundle:
                    omitted.append(f'#/planned/planning_context/bundle/{key}')
                    del bundle[key]
        catalog = context.get('catalog')
        if isinstance(catalog, dict) and isinstance(catalog.get('sources'), list):
            for index, source in enumerate(catalog['sources']):
                if isinstance(source, dict) and 'tables' in source:
                    omitted.append(f'#/planned/planning_context/catalog/sources/{index}/tables')
                    del source['tables']
    binding = planned.get('physical_binding')
    if isinstance(binding, dict):
        for key in ('physical_mappings', 'result_sets'):
            if key in binding:
                omitted.append(f'#/planned/physical_binding/{key}')
                del binding[key]


def native_query_response_view(action: str, response: dict[str, Any],
                               response_view: ResponseView = 'full') -> dict[str, Any]:
    """Present an already authorized API response without changing its records."""
    if response_view not in ('full', 'agent'):
        raise ValueError('NATIVE_QUERY_RESPONSE_VIEW_INVALID')
    if response_view == 'full' or action == 'discover':
        return response
    if response.get('contract_version') != _CONTRACTS.get(action):
        # Do not project new/error response contracts using assumptions from @1.
        return response
    if 'presentation' in response or _reserved_reference(response):
        return response
    value = deepcopy(response)
    omitted: list[str] = []
    if action == 'prepare':
        _prepare(value)
    elif action == 'plan':
        _plan(value, omitted)
    else:
        # Result rows, column meaning, completeness and quality stay fully inline.
        # The artifact and result-set forms are NOT interchangeable merely because
        # their rows agree. Only the demonstrably identical receipt is referenced.
        execution = value.get('execution')
        if (isinstance(execution, dict) and isinstance(execution.get('receipt'), dict)
                and execution.get('exploration_receipt') == execution['receipt']):
            execution['exploration_receipt'] = {'response_ref': '#/execution/receipt'}
        else:
            return response
    if action in ('prepare', 'plan'):
        refs = _References()
        protected = {'#/native_input', '#/submission_schema', '#/submission_guidance',
                     '#/planned/semantic_plan'}
        for path in protected:
            cursor: Any = value
            for key in path.removeprefix('#/').split('/'):
                cursor = cursor.get(key) if isinstance(cursor, dict) else None
            if cursor is not None:
                refs.seed(cursor, path)
        value = refs.compact(value, '#', protected)
    presentation: dict[str, Any] = {
        'contract_version': 'boi/native-query-agent-view@1',
        'response_view': 'agent',
        'references': 'Objects containing only response_ref point to the exact value at that JSON Pointer in this response. Resolve before interpreting; presentation references grant no authority.',
        'omitted_paths': omitted,
        'full_response': 'response_view=full returns the original representation. Use result with execution_ref for saved results; never re-execute an unknown run.',
    }
    if action == 'prepare':
        presentation['profile_payload'] = ('Domain entry payload plus logical_payload_ref reconstructs its full payload. '
            'native_input, input_digest and submission schema/guidance are unchanged.')
    elif action == 'plan':
        presentation['limits'] = ('Use the exact prepare definitions with this plan. Omitted paths are repeated '
            'Profile inventory or server physical details. Candidate, semantic plan, policy, reasons, selected '
            'shape, quality and authority remain; planning does not prove execution or truth.')
    value['presentation'] = presentation
    return value
