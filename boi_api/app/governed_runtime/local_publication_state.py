"""Exact committed units explain changes to a confirmed bundle's original basis."""
from .local_bundle_index import read_bundle_index
from .knowledge_projection_contract import ProjectionPublication
from .semantic_binding_contract import semantic_digest
from ..v2.atomic_store_contract import AtomicWrite

UNITS='knowledge_local_publication_units'
PREPARATIONS='knowledge_local_publication_preparations'


def preparation_key(bundle_ref,unit_id,publication_digest):
    return 'local-publication-preparation:'+semantic_digest([bundle_ref,unit_id,publication_digest])


def unit_key(bundle_ref,unit_id):
    return 'local-publication-unit:'+semantic_digest([bundle_ref,unit_id])


def unit_binding(row,unit):
    return {'bundle_ref':row['bundle_ref'],'manifest_digest':row['manifest_digest'],
        'plan_digest':row['preview']['publication_plan']['plan_digest'],'unit_id':unit['unit_id'],
        'employee_id':row['employee_id'],'policy_digest':row['policy']['policy_digest']}


def committed_unit(store,row,unit,item,*,proof_reads=None):
    if not item or item.get('binding')!=unit_binding(row,unit):
        raise ValueError('LOCAL_PUBLICATION_UNIT_BINDING_CHANGED')
    if item.get('state') not in ('prepared','published'):
        raise ValueError('LOCAL_PUBLICATION_UNIT_STATE_INVALID')
    if item['state']!='published':return None
    manifest=ProjectionPublication.model_validate(item['publication'])
    receipt=store.get('knowledge_publication_receipts',manifest.digest)
    saved=store.get('knowledge_publication_manifests',manifest.digest)
    if (not receipt or receipt.get('manifest_digest')!=manifest.digest or not saved
            or saved.get('manifest')!=manifest.model_dump(mode='json')
            or item.get('publication_digest')!=manifest.digest
            or manifest.principal_id!=row['employee_id'] or manifest.policy_digest!=row['policy']['policy_digest']
            or manifest.confirmation_ref!='local-confirmation:'+semantic_digest([row['bundle_ref'],row['confirmation']])):
        raise ValueError('LOCAL_PUBLICATION_UNIT_COMMIT_PROOF_REQUIRED')
    revisions=item.get('revisions',{})
    if set(revisions)!=set(unit['object_ids']):
        raise ValueError('LOCAL_PUBLICATION_UNIT_CLOSURE_CHANGED')
    changes={c['object_id']:c for c in row['manifest']['changes']}
    expected={'domain-asset-head:'+semantic_digest([row['employee_id'],changes[x]['namespace'],changes[x]['logical_id']]):ref
        for x,ref in revisions.items()}
    if {c.stable_id:c.revision.model_dump(mode='json') for c in manifest.changes}!=expected:
        raise ValueError('LOCAL_PUBLICATION_UNIT_CLOSURE_CHANGED')
    if proof_reads is not None:
        proof_reads.extend((AtomicWrite(UNITS,unit_key(row['bundle_ref'],unit['unit_id']),item,item),
            AtomicWrite('knowledge_publication_receipts',manifest.digest,receipt,receipt),
            AtomicWrite('knowledge_publication_manifests',manifest.digest,saved,saved)))
    return {**item,'committed_generation':receipt['generation']}


def effective_bundle_basis(store,row):
    """Only a unit committed with native heads can advance the preview basis."""
    # The confirmed snapshot is immutable. Only these small per-head/catalog
    # records are updated while applying committed transitions; references and
    # all other confirmed metadata remain unchanged.
    original=row['preview']['basis']
    basis={**original,'heads':[dict(head) for head in original['heads']],
        'catalogs':[dict(catalog) for catalog in original['catalogs']]}
    plan=row['preview'].get('publication_plan')
    if not plan:return basis
    rows=read_bundle_index(store,UNITS,(unit_key(row['bundle_ref'],u['unit_id']) for u in plan['units']))
    heads={h['key']:h for h in basis['heads']}
    catalogs={c['key']:c for c in basis['catalogs']}
    committed_items=[]
    for unit in plan['units']:
        item=rows.get(unit_key(row['bundle_ref'],unit['unit_id']))
        if not item:continue
        committed=committed_unit(store,row,unit,item)
        if committed is None:continue
        committed_items.append((unit,committed))
    published={u['position'] for u,_ in committed_items}
    # Independent units may commit in a different order after a failed unit is
    # explicitly aborted. Apply namespace catalog transitions in actual durable
    # generation order, preserving the declared dependency requirements.
    committed_items.sort(key=lambda pair:(pair[1]['publication']['scope_id'],pair[1]['committed_generation']))
    for unit,committed in committed_items:
        if not set(unit['predecessor_positions'])<=published:
            raise ValueError('LOCAL_PUBLICATION_PREDECESSOR_PROOF_MISSING')
        for change in committed['publication']['changes']:
            head=heads[change['stable_id']]
            if head['revision']!=change['previous_revision']:
                raise ValueError('LOCAL_PUBLICATION_PREVIOUS_REVISION_CHANGED')
            head['revision']=change['revision']
        for transition in committed['catalog_transitions']:
            catalog=catalogs.get(transition['key'])
            if catalog is None or catalog['epoch']!=transition['before_epoch']:
                raise ValueError('LOCAL_PUBLICATION_CATALOG_CHAIN_CHANGED')
            catalog['epoch']=transition['after_epoch']
    return basis


def unit_progress(store,row):
    plan=row['preview'].get('publication_plan')
    if not plan:return None
    rows=read_bundle_index(store,UNITS,(unit_key(row['bundle_ref'],u['unit_id']) for u in plan['units']))
    operations=read_bundle_index(store,'knowledge_projection_outbox',
        dict.fromkeys(item['publication_digest'] for item in rows.values()))
    items=[]
    for unit in plan['units']:
        item=rows.get(unit_key(row['bundle_ref'],unit['unit_id']))
        committed=committed_unit(store,row,unit,item) if item else None
        state='published' if committed else 'prepared' if item else 'pending'
        operation=operations.get(item['publication_digest']) if item else None
        if operation:
            manifest=ProjectionPublication.model_validate(item['publication'])
            if (operation.get('operation_id')!=manifest.digest or item['publication_digest']!=manifest.digest
                    or operation.get('scope_id')!=manifest.scope_id
                    or operation.get('status') not in ('reserved','prepared','published','aborting','aborted')):
                raise ValueError('LOCAL_PUBLICATION_UNIT_OPERATION_BINDING_CHANGED')
            if not committed and operation['status']=='published':
                # A commit may have occurred between the two bounded metadata
                # reads. Refresh this exact unit, never infer success from outbox.
                item=store.get(UNITS,unit_key(row['bundle_ref'],unit['unit_id']))
                committed=committed_unit(store,row,unit,item)
                if committed is None:raise ValueError('LOCAL_PUBLICATION_UNIT_COMMIT_PROOF_REQUIRED')
                state='published'
            elif not committed:
                state={'prepared':'projection_prepared'}.get(operation['status'],operation['status'])
        items.append({'unit_id':unit['unit_id'],'position':unit['position'],'object_count':len(unit['object_ids']),
            'state':state,
            'publication_digest':item['publication_digest'] if item else None,
            'published_generation':committed['committed_generation'] if committed else None})
    published=sum(i['state']=='published' for i in items)
    return {'units':items,'published_units':published,'remaining_units':len(items)-published,
        'aborted_units':sum(i['state']=='aborted' for i in items),
        'active_units':sum(i['state'] in ('prepared','reserved','projection_prepared','aborting') for i in items),
        'publication_committed':bool(items) and published==len(items),
        'visibility':'atomic_per_unit','query_qualification':'purpose_and_revision_specific'}


def publication_status(fallback,progress):
    if fallback=='stopped' or progress is None:return fallback
    if progress['publication_committed']:return 'published'
    if progress['aborted_units']:return 'publication_needs_attention'
    if progress['published_units']:return 'publication_partial'
    if progress['active_units']:return 'publication_in_progress'
    return fallback
