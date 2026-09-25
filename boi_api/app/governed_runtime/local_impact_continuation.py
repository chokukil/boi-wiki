"""Bounded proof of changes made by this exact confirmed bundle."""
from .knowledge_space_store import KnowledgeSpaceStore
from .local_bundle_index import read_bundle_index
from .local_publication_state import UNITS, committed_unit, unit_key


def continuation(store, row, original_contexts):
    contexts=[dict(binding) for binding in original_contexts]
    if not row.get('confirmation'):
        return contexts, (), ()
    plan=row['preview'].get('publication_plan')
    # A v1 bundle can be admitted and prepared without a publication unit plan.
    # It has no unit commits to account for in the original impact snapshot.
    if plan is None:
        if row['manifest']['contract_version'] != 'boi/local-bundle-manifest@1':
            raise ValueError('LOCAL_PUBLICATION_PLAN_REQUIRED')
        return contexts, (), ()
    units=plan['units']
    rows=read_bundle_index(store,UNITS,(unit_key(row['bundle_ref'],u['unit_id']) for u in units))
    partition=KnowledgeSpaceStore.partition(row['manifest']['target_space'],row['employee_id'])
    transitions, events, fences, published = [], [], [], set()
    for unit in units:
        key=unit_key(row['bundle_ref'],unit['unit_id'])
        item=rows.get(key)
        if not item:
            continue
        proof=committed_unit(store,row,unit,item,proof_reads=fences)
        if not proof:
            continue
        published.add(unit['position'])
        steps=proof.get('space_transitions',[])
        if (len(steps)!=1 or steps[0]['key']!=partition
                or type(steps[0]['before_epoch']) is not int
                or type(steps[0]['after_epoch']) is not int
                or steps[0]['after_epoch']!=steps[0]['before_epoch']+1):
            raise ValueError('LOCAL_PUBLICATION_SPACE_CHAIN_CHANGED')
        transitions.extend(steps)
        digest=proof['publication_digest']
        events.append({'receipt':digest,'collection':'knowledge_publication_receipts','key':digest})
        for change in proof['publication']['changes']:
            stable=change['stable_id']
            for collection,event_key in (
                ('domain_asset_heads',stable),('knowledge_space_heads',stable),
                ('domain_knowledge_assets',change['revision']['ref']),
                ('knowledge_space_entries',KnowledgeSpaceStore.entry_key(partition,stable))):
                events.append({'receipt':digest,'collection':collection,'key':event_key})
    if any(not set(u['predecessor_positions'])<=published for u in units if u['position'] in published):
        raise ValueError('LOCAL_PUBLICATION_PREDECESSOR_PROOF_MISSING')
    binding=next((b for b in contexts if b['partition']==partition),None)
    if binding is None:
        raise ValueError('LOCAL_BUNDLE_IMPACT_SCOPE_CHANGED')
    for step in sorted(transitions,key=lambda s:s['before_epoch']):
        if binding['epoch']!=step['before_epoch']:
            raise ValueError('LOCAL_PUBLICATION_SPACE_CHAIN_CHANGED')
        binding['epoch']=step['after_epoch']
    return contexts, tuple(events), tuple(fences)
