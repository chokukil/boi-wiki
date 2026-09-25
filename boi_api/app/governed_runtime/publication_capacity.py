"""Early impossibility check for native + initial-space atomic publication.

This lower bound rejects known oversized units before confirmation/preparation.
Passing it is NOT a capacity proof: actual coalesced native, policy, permission,
qualification, dependency and coordinator writes still need exact preflight.
It does not split a semantic unit or expose partially committed head writes.
"""
from ..v2.atomic_store_contract import MAX_ATOMIC_WRITES


def initial_publication_capacity(changes):
    changes = tuple(changes)
    namespaces = {c.namespace for c in changes}
    definitions = {c.namespace for c in changes if c.kind == 'definition'}
    count = len(changes)
    components = {'native_heads':count,'native_revision_indexes':count,'native_staging_fences':count,
        'space_heads':count,'space_entries':count,'namespace_catalogs':len(namespaces),
        'definition_catalogs':len(definitions),'space_epoch':1,'publication_commit_records':3,'bundle_confirmation_fence':1}
    minimum = sum(components.values())
    return {'contract_version':'boi/initial-publication-capacity@1','maximum_atomic_writes':MAX_ATOMIC_WRITES,
        'known_minimum_writes':minimum,'components':components,
        'status':'atomic_unit_plan_required' if minimum > MAX_ATOMIC_WRITES else 'exact_composite_preflight_required',
        'fits_proven':False,'remaining_checks':['current_rights_and_use_qualification_fences',
            'selected_definition_and_dependency_fences','deduplicated_final_write_set','serialized_bytes_and_runtime_budget'],
        'atomic_unit_planner_available':False}
