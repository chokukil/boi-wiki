"""One existing-store allowance shared by revision branches and resumed hosts."""
from ..v2.atomic_store_contract import AtomicWrite
from .semantic_binding_contract import semantic_digest


def budget_refs(task_ref, unit):
    return unit.get('budget_refs') or ['knowledge-unit-budget:' + semantic_digest([task_ref, unit['unit_id']])]


def budget_rows(service, principal, task_ref, unit):
    rows = []
    for key in budget_refs(task_ref, unit):
        saved = service.store.get('agent_task_idempotency', key)
        initial = {'record_type': 'knowledge_unit_budget', 'employee_id': principal,
            'used': unit['attempts'], 'limit': service.MAX_ATTEMPTS_PER_UNIT,
            'attempt_refs': list(unit.get('attempt_refs', []))}
        if saved is not None and (saved.get('record_type') != initial['record_type'] or saved.get('employee_id') != principal):
            raise ValueError('KNOWLEDGE_WORK_BUDGET_ACCESS_DENIED')
        rows.append((key, saved, saved if saved is not None else initial))
    return rows


def remaining(service, principal, task_ref, unit):
    return min(max(0, row['limit'] - row['used']) for _, _, row in budget_rows(service, principal, task_ref, unit))


def reserve(service, auth, task_ref, unit, attempt_ref):
    writes = []
    rows = budget_rows(service, auth.principal, task_ref, unit)
    for key, saved, row in rows:
        if row['used'] >= row['limit']:
            raise ValueError('KNOWLEDGE_WORK_BUDGET_EXHAUSTED')
        writes.append(AtomicWrite('agent_task_idempotency', key, saved,
            {**row, 'used': row['used'] + 1, 'attempt_refs': [*row['attempt_refs'], attempt_ref]}))
    return tuple(writes)


def inherit(service, auth, previous, units):
    """Seed old tasks' allowances once; never multiply them when a unit splits."""
    writes = {}
    for unit in units:
        for key, saved, row in budget_rows(service, auth.principal, previous['task_package_id'], unit):
            writes[key] = AtomicWrite('agent_task_idempotency', key, saved,
                {**row, 'limit': min(row['limit'], previous['max_attempts_per_unit'])})
    return tuple(writes.values())
