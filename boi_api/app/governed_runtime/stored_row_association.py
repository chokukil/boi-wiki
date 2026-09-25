"""Explicit stored-row bags. Ordinals identify only occurrences in one result.
No entity uniqueness, canonical record, source row locator or business identity is
inferred. This module is used inside the existing authorized native gateway.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class StoredRowSemantics(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    contract: Literal["boi/stored-row-association@1"]
    equality: Literal["TYPED_BINARY_EQUALITY"]
    occurrence_identity: Literal["RESULT_SNAPSHOT_ORDINAL"]
    unmatched_roots: Literal["PRESERVE"]
    multiplicity: Literal["ALL_PAIRS"]

class StoredRowAssociationScope(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    contract: Literal["boi/stored-row-association-quality@1"]="boi/stored-row-association-quality@1"
    root_endpoint_ref: str
    target_endpoint_ref: str
    effective_cardinality: Literal["stored_row_association"]="stored_row_association"
    source_snapshot_digest: str=Field(pattern=r"^sha256:[0-9a-f]{64}$")
    physical_schema_digest: str | None=Field(default=None,exclude_if=lambda v:v is None)
    mapping_closure_digest: str=Field(pattern=r"^sha256:[0-9a-f]{64}$")
    evaluator_code_digest: str=Field(pattern=r"^sha256:[0-9a-f]{64}$")
    acl_propagation: Literal["INTERSECTION"]
    root_rows: int=Field(ge=0)
    target_rows: int=Field(ge=0)
    budget_per_root: int=Field(gt=0)
    root_mapping_refs: tuple[str,...]=Field(min_length=1)
    target_mapping_refs: tuple[str,...]=Field(min_length=1)
    candidate_pair_count: int=Field(ge=0)
    unmatched_root_rows: int=Field(ge=0)
    root_null_key_rows: int=Field(ge=0)
    root_duplicate_key_rows: int=Field(ge=0)
    target_duplicate_key_rows: int=Field(ge=0)

class OccurrencePair(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    root_ordinal: int=Field(ge=0)
    target_ordinal: int=Field(ge=0)

class OccurrenceAssociation(BaseModel):
    model_config=ConfigDict(extra="forbid",frozen=True)
    relationship_ref: str
    run_id: str
    root_result_set_id: str
    target_result_set_id: str
    identity_semantics: Literal["RESULT_SNAPSHOT_ORDINAL"]="RESULT_SNAPSHOT_ORDINAL"
    equality: Literal["TYPED_BINARY_EQUALITY"]="TYPED_BINARY_EQUALITY"
    canonical_identity: Literal["UNKNOWN"]="UNKNOWN"
    root_occurrence_count: int
    target_occurrence_count: int
    candidate_pair_count: int
    target_candidate_counts: tuple[int,...]
    unmatched_root_ordinals: tuple[int,...]
    pairs: tuple[OccurrencePair,...]

def _key(row, columns):
    values=tuple(row[c] for c in columns)
    if any(v is None for v in values):
        return None
    if any(type(v) not in (str,int,float,bytes) for v in values):
        raise ValueError("BAG_KEY_TYPE_UNSUPPORTED")
    return tuple((type(v).__name__,v) for v in values)

def build_occurrence_association(*,run_id,relationship_ref,root_result_set_id,
        target_result_set_id,roots,targets,root_keys,target_keys,max_pairs,max_fanout,
        progress=lambda:False):
    if not root_keys or len(root_keys)!=len(target_keys):
        raise ValueError("BAG_KEY_ARITY_INVALID")
    index={}
    for ordinal,row in enumerate(targets):
        if progress():raise ValueError("BAG_EXECUTION_INTERRUPTED")
        key=_key(row,target_keys)
        if key is not None:index.setdefault(key,[]).append(ordinal)
    count=0
    unmatched=[]
    # Check all budgets before allocating pair output.
    for ordinal,row in enumerate(roots):
        if progress():raise ValueError("BAG_EXECUTION_INTERRUPTED")
        matches=index.get(_key(row,root_keys),())
        if len(matches)>max_fanout:raise ValueError("BAG_FANOUT_BUDGET_EXCEEDED")
        count+=len(matches)
        if count>max_pairs:raise ValueError("BAG_OUTPUT_BUDGET_EXCEEDED")
        if not matches:unmatched.append(ordinal)
    pairs=[]
    target_counts=[0]*len(targets)
    for ordinal,row in enumerate(roots):
        if progress():raise ValueError("BAG_EXECUTION_INTERRUPTED")
        for t in index.get(_key(row,root_keys),()):
            if progress():raise ValueError("BAG_EXECUTION_INTERRUPTED")
            pairs.append(OccurrencePair(root_ordinal=ordinal,target_ordinal=t))
            target_counts[t]+=1
    if progress():raise ValueError("BAG_EXECUTION_INTERRUPTED")
    return OccurrenceAssociation(relationship_ref=relationship_ref,run_id=run_id,
        root_result_set_id=root_result_set_id,target_result_set_id=target_result_set_id,
        root_occurrence_count=len(roots),target_occurrence_count=len(targets),
        candidate_pair_count=count,target_candidate_counts=tuple(target_counts),
        unmatched_root_ordinals=tuple(unmatched),pairs=tuple(pairs))

def profile_stored_row_association(path=None, *,schema,relationship,physical_mappings,
        root_endpoint_ref,evidence_ref,timeout_seconds=30,planner_catalog=None,source_adapter=None):
    import hashlib,math,sqlite3,time
    from pathlib import Path
    from .cardinality_query_shape import DataQualityReceipt,CardinalityAwareQueryShapeSolver,_digest
    from .multi_result_query_gateway import capture_multi_result_sqlite_schema,_identifier
    if not 0<timeout_seconds<=30:raise ValueError("RELATIONSHIP_SCAN_TIMEOUT_INVALID")
    if (path is None)==(source_adapter is None):raise ValueError("RELATIONSHIP_EXACT_SOURCE_REQUIRED")
    if path is not None:path=path.resolve(strict=True)
    target=CardinalityAwareQueryShapeSolver._traversable_neighbor(root_endpoint_ref,relationship)
    if target is None:raise ValueError("RELATIONSHIP_DIRECTION_NOT_AUTHORIZED")
    def capture():
        return source_adapter.capture_schema(allowed_tables=schema.allowed_tables) if source_adapter else capture_multi_result_sqlite_schema(path,allowed_tables=schema.allowed_tables)
    current=capture()
    def check():
        actual=capture()
        if actual.schema_digest!=schema.schema_digest:raise ValueError("SCHEMA_DRIFT")
        if actual.source_snapshot_digest!=schema.source_snapshot_digest:raise ValueError("SOURCE_SNAPSHOT_DRIFT")
    check()
    contract_schema=schema.schema_digest
    if planner_catalog is not None:
        from .semantic_query_execution import capture_sqlite_planner_catalog
        source_ids={m.source_id for m in physical_mappings}
        if len(source_ids)!=1:raise ValueError("QUALITY_PLANNER_SOURCE_SCOPE_INVALID")
        captured=(source_adapter.capture_planner_catalog(allowed_tables=schema.allowed_tables,captured_at=planner_catalog.captured_at)
            if source_adapter else capture_sqlite_planner_catalog(path,source_id=next(iter(source_ids)),allowed_tables=schema.allowed_tables,captured_at=planner_catalog.captured_at))
        if captured!=planner_catalog:raise ValueError("QUALITY_PLANNER_CATALOG_MISMATCH")
        contract_schema=captured.schema_digest
    if relationship.schema_snapshot_digest!=contract_schema:raise ValueError("RELATIONSHIP_SCHEMA_MISMATCH")
    by_ref={m.mapping_ref:m for m in physical_mappings}
    if len(by_ref)!=len(physical_mappings):raise ValueError("DUPLICATE_AUTHORIZED_MAPPING")
    refs={relationship.left_endpoint_ref:relationship.physical_keys.left_mapping_refs,
          relationship.right_endpoint_ref:relationship.physical_keys.right_mapping_refs}
    try:keys={e:tuple(by_ref[r] for r in values) for e,values in refs.items()}
    except KeyError as exc:raise ValueError("RELATIONSHIP_PHYSICAL_KEY_NOT_AUTHORIZED") from exc
    selected=tuple(m for mappings in keys.values() for m in mappings)
    if len({m.source_id for m in selected})!=1:raise ValueError("RELATIONSHIP_CROSS_SOURCE_FORBIDDEN")
    if source_adapter and {m.source_id for m in selected}!={source_adapter.binding.source_id}:raise ValueError("RELATIONSHIP_CROSS_SOURCE_FORBIDDEN")
    tables={}
    for endpoint,mappings in keys.items():
        if len({m.table for m in mappings})!=1:raise ValueError("RELATIONSHIP_KEY_TABLE_AMBIGUOUS")
        tables[endpoint]=mappings[0].table
        for m in mappings:
            table=current.table(m.table)
            if table is None or m.column not in {c.name for c in table.columns}:raise ValueError("RELATIONSHIP_PHYSICAL_KEY_NOT_FOUND")
    def col(alias,m):return alias+"."+_identifier(m.column)
    def join(a,aa,b,ba):
        return " AND ".join("typeof("+col(aa,l)+") = typeof("+col(ba,r)+") AND "+col(aa,l)+" COLLATE BINARY = "+col(ba,r)+" COLLATE BINARY"
            for l,r in zip(keys[a],keys[b],strict=True))
    deadline=time.monotonic()+timeout_seconds
    progress=lambda:int(time.monotonic()>deadline)
    db=source_adapter.open_session(progress) if source_adapter else sqlite3.connect("file:"+str(path)+"?mode=ro",uri=True)
    try:
        if not source_adapter:
            db.execute("PRAGMA query_only=ON");db.execute("BEGIN");db.set_progress_handler(progress,100)
        hist=db.execute("SELECT fanout, COUNT(*) FROM (SELECT (SELECT COUNT(*) FROM "+_identifier(tables[target])+" t WHERE "+join(root_endpoint_ref,"r",target,"t")+") fanout FROM "+_identifier(tables[root_endpoint_ref])+" r) GROUP BY fanout ORDER BY fanout").fetchall()
        nulls={}
        duplicates={}
        totals={}
        for e in keys:
            table=_identifier(tables[e])
            null=" OR ".join(_identifier(m.column)+" IS NULL" for m in keys[e])
            totals[e],nulls[e]=db.execute("SELECT COUNT(*),COALESCE(SUM("+null+"),0) FROM "+table).fetchone()
            groups=",".join("typeof("+_identifier(m.column)+"),"+_identifier(m.column)+" COLLATE BINARY" for m in keys[e])
            duplicates[e]=db.execute("SELECT COALESCE(SUM(n-1),0) FROM (SELECT COUNT(*) n FROM "+table+" WHERE NOT ("+null+") GROUP BY "+groups+" HAVING COUNT(*)>1)").fetchone()[0]
        matched=db.execute("SELECT COUNT(*) FROM "+_identifier(tables[target])+" t WHERE EXISTS (SELECT 1 FROM "+_identifier(tables[root_endpoint_ref])+" r WHERE "+join(root_endpoint_ref,"r",target,"t")+")").fetchone()[0]
    except sqlite3.Error as exc:raise ValueError("RELATIONSHIP_SCAN_REJECTED_OR_TIMEOUT") from exc
    finally:db.close()
    check()
    root_rows=totals[root_endpoint_ref]
    def percentile(p):
        n=max(1,math.ceil(root_rows*p));seen=0
        for fanout,count in hist:
            seen+=count
            if seen>=n:return float(fanout)
        return 0.
    scope=StoredRowAssociationScope(root_endpoint_ref=root_endpoint_ref,target_endpoint_ref=target,
        source_snapshot_digest=schema.source_snapshot_digest,physical_schema_digest=schema.schema_digest if planner_catalog else None,
        mapping_closure_digest=_digest([m.model_dump(mode="json") for m in selected]),
        evaluator_code_digest="sha256:"+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        acl_propagation=relationship.acl_propagation,root_rows=root_rows,target_rows=totals[target],budget_per_root=relationship.fanout.budget_per_parent,
        root_mapping_refs=refs[root_endpoint_ref],target_mapping_refs=refs[target],
        candidate_pair_count=sum(f*n for f,n in hist),unmatched_root_rows=next((n for f,n in hist if f==0),0),
        root_null_key_rows=nulls[root_endpoint_ref],root_duplicate_key_rows=duplicates[root_endpoint_ref],target_duplicate_key_rows=duplicates[target])
    unmatched=totals[target]-matched
    values=dict(receipt_id="quality:bag:"+_digest([relationship.contract_digest,scope.model_dump(mode="json")])[7:],
        relationship_contract_digest=relationship.contract_digest,schema_snapshot_digest=contract_schema,
        scanned_rows=totals[target],matched_rows=matched,unmatched_rows=unmatched,null_fk_rows=nulls[target],
        orphan_rows=unmatched-nulls[target],duplicate_key_rows=duplicates[root_endpoint_ref],
        fanout_distribution=dict(observed_min=hist[0][0] if hist else 0,observed_max=hist[-1][0] if hist else 0,observed_p50=percentile(.5),observed_p95=percentile(.95)),
        excluded_rows=0,coverage_ratio=matched/totals[target] if totals[target] else 1.,
        applied_orphan_policy=relationship.orphan_policy,evidence_ref=evidence_ref,directional_scope=scope.model_dump(mode="json"))
    return DataQualityReceipt(**values,evidence_digest=_digest(values))
