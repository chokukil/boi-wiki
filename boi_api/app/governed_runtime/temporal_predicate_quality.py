"""Scalar source-time audit before a cross-object temporal predicate selects roots."""
import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .latest_time_order import TimeOrdering
from .temporal_sql_comparison import temporal_expression


def digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def quote(value):
    if not value or '\x00' in value:
        raise ValueError('TEMPORAL_PREDICATE_IDENTIFIER_INVALID')
    return '"'+value.replace('"','""')+'"'


class TemporalPredicateQualityReceipt(BaseModel):
    model_config=ConfigDict(extra='forbid',frozen=True)
    contract: Literal['boi/temporal-predicate-quality@1']='boi/temporal-predicate-quality@1'
    phase: Literal['AUTHORIZED_ROOT_SCOPE_BEFORE_TEMPORAL_EXISTS']='AUTHORIZED_ROOT_SCOPE_BEFORE_TEMPORAL_EXISTS'
    root_result_set_id: str
    constraint_index: int=Field(ge=0)
    filter_object_ref: str
    temporal_mapping_ref: str
    latest_contract_digest: str=Field(pattern=r'^sha256:[0-9a-f]{64}$')
    source_snapshot_digest: str=Field(pattern=r'^sha256:[0-9a-f]{64}$')
    input_scope_digest: str=Field(pattern=r'^sha256:[0-9a-f]{64}$')
    scanned_rows: int=Field(ge=0)
    null_time_rows: int=Field(ge=0)
    invalid_time_rows: int=Field(ge=0)
    excluded_rows: int=Field(ge=0)
    null_time_policy: Literal['BLOCK','EXCLUDE_WITH_DISCLOSURE']
    time_ordering: TimeOrdering
    receipt_digest: str=Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @model_validator(mode='after')
    def validate_receipt(self):
        if digest(self.model_dump(mode='json',exclude={'receipt_digest'}))!=self.receipt_digest:
            raise ValueError('TEMPORAL_PREDICATE_QUALITY_DIGEST_INVALID')
        if self.null_time_rows+self.invalid_time_rows>self.scanned_rows or self.excluded_rows>self.scanned_rows:
            raise ValueError('TEMPORAL_PREDICATE_QUALITY_COUNT_INVALID')
        if self.invalid_time_rows or self.null_time_policy=='BLOCK' and self.null_time_rows or self.excluded_rows!=self.null_time_rows:
            raise ValueError('TEMPORAL_PREDICATE_POLICY_NOT_SATISFIED')
        return self


def audit_temporal_predicate(connection, *, result_set_id, constraint_index, constraint,
        hop_aliases, root_table, non_temporal_predicates, root_preselection_where,
        bindings, mapping, policy, source_snapshot_digest):
    """Internal compiler input only; scan target rows once using reachability EXISTS."""
    hops=constraint.hops
    outer_alias=hop_aliases[-1]
    # Root filtering happens in its own table namespace before intermediate joins.
    reach_from='(SELECT * FROM '+quote(root_table)+root_preselection_where+') AS '+quote(root_table)
    for index,hop in enumerate(hops[:-1]):
        previous=quote(root_table) if index==0 else hop_aliases[index-1]
        reach_from+=' JOIN '+quote(hop.table)+' AS '+hop_aliases[index]+' ON '+hop_aliases[index]+'.'+quote(hop.child_column)+' = '+previous+'.'+quote(hop.parent_column)
    prior=quote(root_table) if len(hops)==1 else hop_aliases[-2]
    correlation=outer_alias+'.'+quote(hops[-1].child_column)+' = '+prior+'.'+quote(hops[-1].parent_column)
    reachable='EXISTS (SELECT 1 FROM '+reach_from+' WHERE '+correlation+')'
    filters=[*non_temporal_predicates,reachable]
    column=outer_alias+'.'+quote(mapping.column)
    sql=('SELECT COUNT(*),COALESCE(SUM('+column+' IS NULL),0),COALESCE(SUM('+column+
         " IS NOT NULL AND "+temporal_expression(column,policy.time_ordering)+" IS NULL),0) FROM "+
         quote(hops[-1].table)+' AS '+outer_alias+' WHERE '+' AND '.join(filters))
    scanned,null_time,invalid=tuple(connection.execute(sql,bindings).fetchone())
    if invalid:
        raise ValueError('LATEST_TIME_FORMAT_POLICY_MISMATCH')
    if null_time and policy.null_time_policy=='BLOCK':
        raise ValueError('LATEST_NULL_TIME_BLOCKED')
    values=dict(contract='boi/temporal-predicate-quality@1',phase='AUTHORIZED_ROOT_SCOPE_BEFORE_TEMPORAL_EXISTS',
        root_result_set_id=result_set_id,constraint_index=constraint_index,filter_object_ref=constraint.filter_object_ref,
        temporal_mapping_ref=mapping.mapping_ref,latest_contract_digest=policy.contract_digest,
        source_snapshot_digest=source_snapshot_digest,input_scope_digest=digest({'sql':sql,'bindings':bindings}),
        scanned_rows=scanned,null_time_rows=null_time,invalid_time_rows=invalid,excluded_rows=null_time,
        null_time_policy=policy.null_time_policy,time_ordering=policy.time_ordering)
    return TemporalPredicateQualityReceipt(**values,receipt_digest=digest(values))


class MappingTemporalQualityReceipt(BaseModel):
    """Mapping-owned time validation; historical EXISTS receipts stay unchanged."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract: Literal['boi/mapping-temporal-quality@1'] = 'boi/mapping-temporal-quality@1'
    phase: Literal['AUTHORIZED_SCOPE_BEFORE_TEMPORAL_SELECTION'] = 'AUTHORIZED_SCOPE_BEFORE_TEMPORAL_SELECTION'
    result_set_id: str
    temporal_mapping_ref: str
    mapping_revision_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    encoding_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    source_snapshot_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    input_scope_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')
    scanned_rows: int = Field(ge=0)
    null_time_rows: Literal[0]
    invalid_time_rows: Literal[0]
    null_time_policy: Literal['BLOCK']
    time_ordering: TimeOrdering
    receipt_digest: str = Field(pattern=r'^sha256:[0-9a-f]{64}$')

    @model_validator(mode='after')
    def validate_receipt(self):
        if digest(self.model_dump(mode='json', exclude={'receipt_digest'})) != self.receipt_digest:
            raise ValueError('MAPPING_TEMPORAL_QUALITY_DIGEST_INVALID')
        return self


def audit_mapping_temporal_input(connection, *, result_set_id, table,
        preselection_where, bindings, mapping, source_snapshot_digest):
    """Check the authorized, linked business scope before a time filter/ordering.

    Parent keys and non-temporal predicates remain in the scope. Time predicates
    cannot hide NULL or malformed source values from the mapping's BLOCK policy.
    Only scalar counts cross the source connection.
    """
    encoding = mapping.temporal_encoding
    column = quote(mapping.column)
    sql = ('SELECT COUNT(*),COALESCE(SUM(' + column + ' IS NULL),0),'
           'COALESCE(SUM(' + column + ' IS NOT NULL AND '
           + temporal_expression(column, encoding.representation)
           + ' IS NULL),0) FROM ' + quote(table) + preselection_where)
    scanned, null_time, invalid = tuple(connection.execute(sql, bindings).fetchone())
    if invalid:
        raise ValueError('MAPPING_TEMPORAL_FORMAT_POLICY_MISMATCH')
    if null_time:
        raise ValueError('MAPPING_TEMPORAL_NULL_BLOCKED')
    values = dict(contract='boi/mapping-temporal-quality@1',
        phase='AUTHORIZED_SCOPE_BEFORE_TEMPORAL_SELECTION',
        result_set_id=result_set_id, temporal_mapping_ref=mapping.mapping_ref,
        mapping_revision_digest=mapping.revision_digest,
        encoding_digest=digest(encoding.model_dump(mode='json')),
        source_snapshot_digest=source_snapshot_digest,
        input_scope_digest=digest({'sql': sql, 'bindings': bindings}),
        scanned_rows=scanned, null_time_rows=0, invalid_time_rows=0,
        null_time_policy=encoding.null_policy, time_ordering=encoding.representation)
    return MappingTemporalQualityReceipt(**values, receipt_digest=digest(values))
