"""Explicit v2 scalar-only relationship profiling; old profiler is unchanged.

FK repetition is not duplicate entity identity. Cardinality owns the unique side;
traversal orientation owns fanout. This service measures already authorized keys,
never creates relations, repairs mappings, sends rows to a model or activates assets.
"""
import hashlib
import math
from pathlib import Path
import sqlite3
import time

from .cardinality_query_shape import DataQualityReceipt, CardinalityAwareQueryShapeSolver, _digest
from .directional_quality_scope import DirectionalQualityScope
from .multi_result_query_gateway import capture_multi_result_sqlite_schema, _identifier


def profile_directional_sqlite_relationship_quality(path=None, *, schema, relationship,
        physical_mappings, root_endpoint_ref, evidence_ref, foreign_key_endpoint_ref=None,
        timeout_seconds=30, planner_catalog=None, source_adapter=None):
    if relationship.cardinality == "stored_row_association":
        from .stored_row_association import profile_stored_row_association
        if foreign_key_endpoint_ref is not None:
            raise ValueError("STORED_ROW_ASSOCIATION_HAS_NO_UNIQUE_FK_ENDPOINT")
        return profile_stored_row_association(path,schema=schema,relationship=relationship,
            physical_mappings=physical_mappings,root_endpoint_ref=root_endpoint_ref,evidence_ref=evidence_ref,
            timeout_seconds=timeout_seconds,planner_catalog=planner_catalog,source_adapter=source_adapter)
    if not 0 < timeout_seconds <= 30:
        raise ValueError('RELATIONSHIP_SCAN_TIMEOUT_INVALID')
    if (path is None) == (source_adapter is None):
        raise ValueError('RELATIONSHIP_EXACT_SOURCE_REQUIRED')
    if path is not None:
        path = path.resolve(strict=True)
    def capture_schema():
        return (source_adapter.capture_schema(allowed_tables=schema.allowed_tables)
            if source_adapter is not None else
            capture_multi_result_sqlite_schema(path,allowed_tables=schema.allowed_tables))
    target = CardinalityAwareQueryShapeSolver._traversable_neighbor(root_endpoint_ref,relationship)
    if target is None:
        raise ValueError('RELATIONSHIP_DIRECTION_NOT_AUTHORIZED')
    endpoints=(relationship.left_endpoint_ref,relationship.right_endpoint_ref)
    if relationship.cardinality == 'many_to_many':
        raise ValueError('RELATIONSHIP_BRIDGE_PROFILE_REQUIRED')
    implied_fk = (endpoints[1] if relationship.cardinality == 'one_to_many' else
                  endpoints[0] if relationship.cardinality == 'many_to_one' else None)
    if implied_fk and foreign_key_endpoint_ref not in {None,implied_fk}:
        raise ValueError('RELATIONSHIP_FK_ENDPOINT_CONFLICT')
    fk_ref = implied_fk or foreign_key_endpoint_ref
    if fk_ref not in endpoints:
        raise ValueError('RELATIONSHIP_FK_ENDPOINT_REQUIRED')
    unique_ref = next(item for item in endpoints if item != fk_ref)
    current=capture_schema()
    if current.schema_digest != schema.schema_digest:
        raise ValueError('SCHEMA_DRIFT')
    if current.source_snapshot_digest != schema.source_snapshot_digest:
        raise ValueError('SOURCE_SNAPSHOT_DRIFT')
    contract_schema_digest=schema.schema_digest
    if planner_catalog is not None:
        from .semantic_query_execution import capture_sqlite_planner_catalog
        source_ids={m.source_id for m in physical_mappings}
        if len(source_ids)!=1:
            raise ValueError('QUALITY_PLANNER_SOURCE_SCOPE_INVALID')
        captured=(source_adapter.capture_planner_catalog(allowed_tables=schema.allowed_tables,
            captured_at=planner_catalog.captured_at) if source_adapter is not None else
            capture_sqlite_planner_catalog(path,source_id=next(iter(source_ids)),
                allowed_tables=schema.allowed_tables,captured_at=planner_catalog.captured_at))
        if source_adapter is not None and source_ids != {source_adapter.binding.source_id}:
            raise ValueError('QUALITY_PLANNER_SOURCE_SCOPE_INVALID')
        if captured != planner_catalog:
            raise ValueError('QUALITY_PLANNER_CATALOG_MISMATCH')
        contract_schema_digest=captured.schema_digest
    if relationship.schema_snapshot_digest != contract_schema_digest:
        raise ValueError('RELATIONSHIP_SCHEMA_MISMATCH')
    by_ref={m.mapping_ref:m for m in physical_mappings}
    if len(by_ref)!=len(physical_mappings):
        raise ValueError('DUPLICATE_AUTHORIZED_MAPPING')
    refs={endpoints[0]:relationship.physical_keys.left_mapping_refs,
          endpoints[1]:relationship.physical_keys.right_mapping_refs}
    try:
        keys={e:tuple(by_ref[r] for r in refs[e]) for e in endpoints}
    except KeyError as error:
        raise ValueError('RELATIONSHIP_PHYSICAL_KEY_NOT_AUTHORIZED') from error
    selected=tuple(m for values in keys.values() for m in values)
    if len({m.source_id for m in selected})!=1:
        raise ValueError('RELATIONSHIP_CROSS_SOURCE_FORBIDDEN')
    tables={}
    for endpoint,mappings in keys.items():
        if len({m.table for m in mappings})!=1:
            raise ValueError('RELATIONSHIP_KEY_TABLE_AMBIGUOUS')
        tables[endpoint]=mappings[0].table
        for m in mappings:
            table=current.table(m.table)
            if table is None or m.column not in {c.name for c in table.columns}:
                raise ValueError('RELATIONSHIP_PHYSICAL_KEY_NOT_FOUND')
    def col(alias,mapping): return alias+'.'+_identifier(mapping.column)
    def join(a,alias_a,b,alias_b):
        return ' AND '.join(col(alias_a,l)+' = '+col(alias_b,r) for l,r in zip(keys[a],keys[b],strict=True))
    fk_null=' OR '.join(col('f',m)+' IS NULL' for m in keys[fk_ref])
    unique_null=' OR '.join(col('u',m)+' IS NULL' for m in keys[unique_ref])
    match='EXISTS (SELECT 1 FROM '+_identifier(tables[unique_ref])+' AS u WHERE '+join(fk_ref,'f',unique_ref,'u')+')'
    duplicate_sql=lambda e: ('SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) AS n FROM '+_identifier(tables[e])+
        ' WHERE '+' AND '.join(_identifier(m.column)+' IS NOT NULL' for m in keys[e])+
        ' GROUP BY '+','.join(_identifier(m.column) for m in keys[e])+' HAVING COUNT(*)>1)')
    if source_adapter is not None and {m.source_id for m in selected} != {source_adapter.binding.source_id}:
        raise ValueError('RELATIONSHIP_CROSS_SOURCE_FORBIDDEN')
    deadline=time.monotonic()+timeout_seconds
    progress=lambda:int(time.monotonic()>deadline)
    connection=(source_adapter.open_session(progress) if source_adapter is not None else
        sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=timeout_seconds))
    try:
        if source_adapter is None:
            connection.execute('PRAGMA query_only=ON')
            connection.execute('BEGIN')
            connection.set_progress_handler(progress,100)
        scanned,null_fk,matched=connection.execute('SELECT COUNT(*), COALESCE(SUM('+fk_null+'),0), '+
            'COALESCE(SUM(NOT ('+fk_null+') AND '+match+'),0) FROM '+_identifier(tables[fk_ref])+' AS f').fetchone()
        duplicate=connection.execute(duplicate_sql(unique_ref)).fetchone()[0]
        if relationship.cardinality=='one_to_one':
            duplicate+=connection.execute(duplicate_sql(fk_ref)).fetchone()[0]
        unique_null_count=connection.execute('SELECT COUNT(*) FROM '+_identifier(tables[unique_ref])+' AS u WHERE '+unique_null).fetchone()[0]
        # Histogram only: no FK/entity/result rows materialized in application memory.
        histogram=connection.execute('SELECT fanout,COUNT(*) FROM (SELECT (SELECT COUNT(*) FROM '+
            _identifier(tables[target])+' AS t WHERE '+join(root_endpoint_ref,'r',target,'t')+
            ') AS fanout FROM '+_identifier(tables[root_endpoint_ref])+' AS r) GROUP BY fanout ORDER BY fanout').fetchall()
    except sqlite3.Error as error:
        raise ValueError('RELATIONSHIP_SCAN_REJECTED_OR_TIMEOUT') from error
    finally:
        connection.close()
    final=capture_schema()
    if final.schema_digest!=schema.schema_digest:
        raise ValueError('SCHEMA_DRIFT')
    if final.source_snapshot_digest!=schema.source_snapshot_digest:
        raise ValueError('SOURCE_SNAPSHOT_DRIFT')
    root_rows=sum(n for _,n in histogram)
    def percentile(p):
        needed=max(1,math.ceil(root_rows*p));cumulative=0
        for fanout,count in histogram:
            cumulative+=count
            if cumulative>=needed:return float(fanout)
        return 0.0
    distribution=dict(observed_min=histogram[0][0] if histogram else 0,observed_max=histogram[-1][0] if histogram else 0,
                      observed_p50=percentile(.5),observed_p95=percentile(.95))
    scope=DirectionalQualityScope(root_endpoint_ref=root_endpoint_ref,target_endpoint_ref=target,
        foreign_key_endpoint_ref=fk_ref,unique_endpoint_ref=unique_ref,scanned_endpoint_ref=fk_ref,
        effective_cardinality=CardinalityAwareQueryShapeSolver._effective_cardinality(root_endpoint_ref,relationship),
        source_snapshot_digest=schema.source_snapshot_digest,
        physical_schema_digest=schema.schema_digest if planner_catalog is not None else None,
        mapping_closure_digest=_digest([m.model_dump(mode='json') for m in selected]),
        evaluator_code_digest=_digest({name:'sha256:'+hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ('directional_relationship_quality.py','directional_quality_scope.py','cardinality_query_shape.py',
                         'multi_result_query_gateway.py','sqlite_source_snapshot.py',
                         *(('query_source_action.py',) if source_adapter is not None else ()),
                         *(('semantic_query_execution.py','semantic_query_planner.py') if planner_catalog is not None else ()))}),
        acl_propagation=relationship.acl_propagation,root_rows=root_rows,unique_endpoint_null_key_rows=unique_null_count)
    unmatched=scanned-matched
    values=dict(receipt_id='quality:v2:'+_digest([relationship.contract_digest,scope.model_dump(mode='json')])[7:],
        relationship_contract_digest=relationship.contract_digest,schema_snapshot_digest=contract_schema_digest,
        scanned_rows=scanned,matched_rows=matched,unmatched_rows=unmatched,null_fk_rows=null_fk,orphan_rows=unmatched-null_fk,
        duplicate_key_rows=duplicate,fanout_distribution=distribution,
        excluded_rows=unmatched if relationship.orphan_policy in {'EXCLUDE_WITH_DISCLOSURE','QUARANTINE'} else 0,
        coverage_ratio=matched/scanned if scanned else 1.,applied_orphan_policy=relationship.orphan_policy,
        evidence_ref=evidence_ref,directional_scope=scope.model_dump(mode='json'))
    return DataQualityReceipt(**values,evidence_digest=_digest(values))
