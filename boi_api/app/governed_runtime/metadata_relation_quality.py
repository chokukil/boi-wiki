"""Bounded scalar observation of declared relationship candidates.

The caller owns the protected SQLite session, grant, deadline, and snapshot
checks. This module reads aggregate counts only and confers no semantic or
execution authority on a caller-supplied relationship declaration.
"""

import hashlib
from pathlib import Path

from .cardinality_query_shape import DataQualityReceipt
from .directional_quality_scope import DirectionalQualityScope
from .metadata_mapping_profile import _digest, DeclaredPropertyMappingV2
from .multi_result_query_gateway import _identifier


def _scalar(connection, statement):
    return connection.execute(statement).fetchone()


def _fanout(connection, *, root_table, root_columns, target_table, target_columns):
    root=_identifier(root_table);target=_identifier(target_table)
    nullable=' OR '.join('r.'+_identifier(column)+' IS NULL' for column in root_columns)
    equality=' AND '.join('t.'+_identifier(other)+' = r.'+_identifier(column)
        for column,other in zip(root_columns,target_columns))
    statement=(
        'WITH fanout AS (SELECT CASE WHEN '+nullable+' THEN 0 ELSE '
        '(SELECT COUNT(*) FROM '+target+' t WHERE '+equality+') END AS n FROM '+root+' r), '
        'ranked AS (SELECT n, ROW_NUMBER() OVER (ORDER BY n) AS rn, '
        'COUNT(*) OVER () AS total FROM fanout) '
        'SELECT COALESCE(MIN(n),0), '
        'COALESCE(MAX(CASE WHEN rn=(total+1)/2 THEN n END),0), '
        'COALESCE(MAX(CASE WHEN rn=(total*95+99)/100 THEN n END),0), '
        'COALESCE(MAX(n),0) FROM ranked')
    low,p50,p95,high=_scalar(connection,statement)
    return {'observed_min':int(low),'observed_p50':float(p50),
        'observed_p95':float(p95),'observed_max':int(high)},_digest(statement)


def measure_declared_relation(connection, *, relationship, inputs, grant_digest,
                              principal, purpose, manifest_digest, storage_by_mapping):
    """Return directional receipts or an explicit unmeasured reason.

    One-to-one lacks an explicit FK side, and bridge/temporal contracts need
    their own evaluator. No inferred direction or missing policy is filled in.
    """
    if relationship.cardinality not in {'one_to_many','many_to_one'}:
        return [],['RELATIONSHIP_QUALITY_FK_OR_BRIDGE_CONTRACT_REQUIRED']
    if relationship.temporal_validity.mode!='none':
        return [],['RELATIONSHIP_TEMPORAL_QUALITY_AUDIT_REQUIRED']
    objects={item.object_ref:item for item in inputs.objects}
    properties={item.physical.mapping_ref:item for item in inputs.properties}
    unique_ref=(relationship.left_endpoint_ref if relationship.cardinality=='one_to_many'
        else relationship.right_endpoint_ref)
    fk_ref=(relationship.right_endpoint_ref if relationship.cardinality=='one_to_many'
        else relationship.left_endpoint_ref)
    unique_refs=(relationship.physical_keys.left_mapping_refs if unique_ref==relationship.left_endpoint_ref
        else relationship.physical_keys.right_mapping_refs)
    fk_refs=(relationship.physical_keys.right_mapping_refs if fk_ref==relationship.right_endpoint_ref
        else relationship.physical_keys.left_mapping_refs)
    if tuple(unique_refs)!=tuple(objects[unique_ref].logical_key_mapping_refs):
        return [],['RELATIONSHIP_UNIQUE_ENDPOINT_GRAIN_UNBOUND']
    if any(not isinstance(properties[ref],DeclaredPropertyMappingV2)
           or (storage_by_mapping.get(ref) or {}).get('status')!='pass'
           for ref in (*unique_refs,*fk_refs)):
        return [],['RELATIONSHIP_TYPED_KEY_QUALITY_REQUIRED']
    unique=tuple(properties[ref].physical for ref in unique_refs)
    fk=tuple(properties[ref].physical for ref in fk_refs)
    if (len({item.table for item in unique})!=1 or len({item.table for item in fk})!=1
        or any(properties[left].declared_data_type.casefold()!=properties[right].declared_data_type.casefold()
            or properties[left].logical_primitive_type!=properties[right].logical_primitive_type
            or properties[left].unit_semantics!=properties[right].unit_semantics
            or properties[left].unit_ref!=properties[right].unit_ref
            for left,right in zip(unique_refs,fk_refs))):
        return [],['RELATIONSHIP_KEY_TYPE_OR_TABLE_UNRESOLVED']
    unique_table=unique[0].table;fk_table=fk[0].table
    uq=_identifier(unique_table);ft=_identifier(fk_table)
    unique_columns=tuple(item.column for item in unique)
    fk_columns=tuple(item.column for item in fk)
    fk_null=' OR '.join('f.'+_identifier(column)+' IS NULL' for column in fk_columns)
    unique_null=' OR '.join('u.'+_identifier(column)+' IS NULL' for column in unique_columns)
    equality=' AND '.join('u.'+_identifier(left)+' = f.'+_identifier(right)
        for left,right in zip(unique_columns,fk_columns))
    fk_count=('SELECT COUNT(*), COALESCE(SUM(CASE WHEN '+fk_null+' THEN 1 ELSE 0 END),0), '
        'COALESCE(SUM(CASE WHEN NOT ('+fk_null+') AND EXISTS '
        '(SELECT 1 FROM '+uq+' u WHERE '+equality+') THEN 1 ELSE 0 END),0) FROM '+ft+' f')
    scanned,null_rows,matched=_scalar(connection,fk_count)
    unique_count=('SELECT COUNT(*), COALESCE(SUM(CASE WHEN '+unique_null+
        ' THEN 1 ELSE 0 END),0) FROM '+uq+' u')
    unique_rows,unique_null_rows=_scalar(connection,unique_count)
    nonnull=' AND '.join(_identifier(column)+' IS NOT NULL' for column in unique_columns)
    cols=','.join(_identifier(column) for column in unique_columns)
    duplicate_count=('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM '+uq+
        ' WHERE '+nonnull+' GROUP BY '+cols+' HAVING COUNT(*)>1)')
    duplicate_rows=_scalar(connection,duplicate_count)[0]
    unmatched=scanned-matched;orphans=unmatched-null_rows
    roots=([relationship.left_endpoint_ref] if relationship.direction=='left_to_right'
        else [relationship.right_endpoint_ref] if relationship.direction=='right_to_left'
        else [relationship.left_endpoint_ref,relationship.right_endpoint_ref])
    evaluator='sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    mapping_closure=_digest([(item.mapping_ref,item.revision_digest) for item in (*unique,*fk)])
    receipts=[];policy_reasons=[];attention=[]
    if unique_null_rows or duplicate_rows:
        policy_reasons.append('RELATIONSHIP_UNIQUE_ENDPOINT_KEY_INVALID')
    if null_rows and relationship.null_policy=='BLOCK':
        policy_reasons.append('RELATIONSHIP_NULL_FK_POLICY_VIOLATED')
    if orphans and relationship.orphan_policy=='BLOCK':
        policy_reasons.append('RELATIONSHIP_ORPHAN_POLICY_VIOLATED')
    for root in roots:
        root_unique=root==unique_ref
        fanout,fanout_query_digest=_fanout(connection,
            root_table=unique_table if root_unique else fk_table,
            root_columns=unique_columns if root_unique else fk_columns,
            target_table=fk_table if root_unique else unique_table,
            target_columns=fk_columns if root_unique else unique_columns)
        if (root_unique and fanout['observed_max']>relationship.fanout.budget_per_parent
            and relationship.fanout.budget_action=='BLOCK'):
            policy_reasons.append('RELATIONSHIP_FANOUT_BUDGET_EXCEEDED')
        declared={key:getattr(relationship.fanout,key) for key in (
            'observed_min','observed_p50','observed_p95','observed_max')}
        matches_declared=fanout==declared if root_unique else None
        if matches_declared is False:
            attention.append('RELATIONSHIP_DECLARED_FANOUT_DIFFERS')
        scope=DirectionalQualityScope(root_endpoint_ref=root,
            target_endpoint_ref=fk_ref if root_unique else unique_ref,
            foreign_key_endpoint_ref=fk_ref,unique_endpoint_ref=unique_ref,
            effective_cardinality='one_to_many' if root_unique else 'many_to_one',
            scanned_endpoint_ref=fk_ref,source_snapshot_digest=inputs.source_snapshot_digest,
            physical_schema_digest=inputs.schema_snapshot_digest,
            mapping_closure_digest=mapping_closure,evaluator_code_digest=evaluator,
            acl_propagation=relationship.acl_propagation,
            root_rows=unique_rows if root_unique else scanned,
            unique_endpoint_null_key_rows=unique_null_rows)
        evidence_ref='metadata-relation-quality:'+_digest([manifest_digest,principal,purpose,
            grant_digest,relationship.contract_digest,root])[7:]
        body={'receipt_id':evidence_ref,'relationship_contract_digest':relationship.contract_digest,
            'schema_snapshot_digest':inputs.schema_snapshot_digest,'scanned_rows':scanned,
            'matched_rows':matched,'unmatched_rows':unmatched,'null_fk_rows':null_rows,
            'orphan_rows':orphans,'duplicate_key_rows':duplicate_rows,
            'fanout_distribution':fanout,
            'excluded_rows':unmatched if relationship.orphan_policy in
                {'EXCLUDE_WITH_DISCLOSURE','QUARANTINE'} else 0,
            'coverage_ratio':matched/scanned if scanned else 1.0,
            'applied_orphan_policy':relationship.orphan_policy,
            'evidence_ref':evidence_ref,'directional_scope':scope.model_dump(mode='json')}
        receipt=DataQualityReceipt.model_validate({**body,'evidence_digest':_digest(body)})
        receipts.append({'quality_receipt':receipt.model_dump(mode='json'),
            'quality_receipt_digest':receipt.receipt_digest,
            'protected_query_digests':[_digest(fk_count),_digest(unique_count),
                _digest(duplicate_count),fanout_query_digest],
            'declared_fanout_matches_observation':matches_declared,
            'status':'fail' if policy_reasons else 'measured_candidate_only'})
    return receipts,list(dict.fromkeys([*policy_reasons,*attention]))
