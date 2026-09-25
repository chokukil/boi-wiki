"""Server-owned exact-preparation execution grants; never inferred from quality grants."""
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
import hashlib
from pydantic import Field,model_serializer,model_validator
from .semantic_binding_contract import FrozenContract,Digest,Ref,semantic_digest


class ReviewedQueryExecutionGrant(FrozenContract):
    contract_version: Literal[
        'boi/reviewed-query-execution-grant@1',
        'boi/reviewed-query-execution-grant@2',
    ]
    grant_id: Ref
    revision: int = Field(ge=1)
    principal_ids: tuple[Ref,...] = Field(min_length=1)
    purposes: tuple[Ref,...] = Field(min_length=1)
    preparation_receipt_digests: tuple[Digest,...] = Field(min_length=1,max_length=100)
    source_id: Ref
    source_snapshot_digest: Digest
    schema_snapshot_digest: Digest
    source_policy_digest: Digest
    maximum_rows: int = Field(ge=1,le=1000)
    paging_policy_digests: tuple[Digest,...] = Field(default=(),max_length=100)
    maximum_total_rows: int | None = Field(default=None,ge=1,le=1_000_000)
    effective_from: datetime
    stale_after: datetime

    @model_serializer(mode='wrap')
    def preserve_v1_wire(self,handler):
        value=handler(self)
        if self.contract_version=='boi/reviewed-query-execution-grant@1':
            value.pop('paging_policy_digests',None)
            value.pop('maximum_total_rows',None)
        return value

    @model_validator(mode='after')
    def exact_scope(self):
        if any('*' in value for value in (*self.principal_ids,*self.purposes,self.source_id)):
            raise ValueError('REVIEWED_QUERY_GRANT_EXPLICIT_SCOPE_REQUIRED')
        for values in (self.principal_ids,self.purposes,self.preparation_receipt_digests):
            if len(values)!=len(set(values)):raise ValueError('REVIEWED_QUERY_GRANT_DUPLICATE_SCOPE')
        if len(self.paging_policy_digests)!=len(set(self.paging_policy_digests)):
            raise ValueError('REVIEWED_QUERY_GRANT_DUPLICATE_SCOPE')
        paging_v2=self.contract_version=='boi/reviewed-query-execution-grant@2'
        if paging_v2 != bool(self.paging_policy_digests) or paging_v2 != (self.maximum_total_rows is not None):
            raise ValueError('REVIEWED_QUERY_GRANT_PAGING_REVISION_INVALID')
        if (self.effective_from.tzinfo is None or self.stale_after.tzinfo is None
            or self.stale_after<=self.effective_from):
            raise ValueError('REVIEWED_QUERY_GRANT_WINDOW_INVALID')
        return self


class ReviewedQueryGrantDecision(FrozenContract):
    contract_version: Literal['boi/reviewed-query-grant-decision@1']='boi/reviewed-query-grant-decision@1'
    grant_digest: Digest
    grant: ReviewedQueryExecutionGrant
    principal: Ref
    purpose: Ref
    preparation_receipt_digest: Digest
    source_snapshot_digest: Digest
    allowed: Literal[True]=True

    @model_validator(mode='after')
    def binds_grant(self):
        if (self.grant_digest!=semantic_digest(self.grant) or self.principal not in self.grant.principal_ids
            or self.purpose not in self.grant.purposes
            or self.preparation_receipt_digest not in self.grant.preparation_receipt_digests
            or self.source_snapshot_digest!=self.grant.source_snapshot_digest):
            raise ValueError('REVIEWED_QUERY_GRANT_DECISION_MISMATCH')
        return self


def authorize_reviewed_query(grant,principal,prepared,*,at=None):
    grant=ReviewedQueryExecutionGrant.model_validate(grant.model_dump(mode='json'))
    at=at or datetime.now(timezone.utc)
    if semantic_digest({k:v for k,v in prepared.items() if k!='receipt_digest'})!=prepared['receipt_digest']:
        raise ValueError('REVIEWED_QUERY_GRANT_PREPARATION_TAMPERED')
    mapping=prepared['semantic_context']['declared_mapping_inputs']
    authority=prepared['logical_plan']['candidate_authority']
    if not grant.effective_from<=at<grant.stale_after:
        raise ValueError('REVIEWED_QUERY_GRANT_STALE')
    paging_sets=[item for item in prepared['logical_plan']['result_sets']
        if item.get('paging_policy') is not None]
    paging_valid=True
    if paging_sets:
        from .snapshot_result_paging import SnapshotPagingPolicy
        paging_valid=(grant.contract_version=='boi/reviewed-query-execution-grant@2'
            and all(SnapshotPagingPolicy.model_validate(item['paging_policy']).policy_digest
                in grant.paging_policy_digests for item in paging_sets)
            and all(SnapshotPagingPolicy.model_validate(item['paging_policy']).page_size
                <=grant.maximum_rows for item in paging_sets))
    if (principal.employee_id not in grant.principal_ids or authority['principal']!=principal.employee_id
        or authority['purpose'] not in grant.purposes
        or prepared['receipt_digest'] not in grant.preparation_receipt_digests
        or (mapping['source_id'],mapping['source_snapshot_digest'],mapping['schema_snapshot_digest'],mapping['policy_digest'])
        !=(grant.source_id,grant.source_snapshot_digest,grant.schema_snapshot_digest,grant.source_policy_digest)
        or any(r['result_row_limit']>grant.maximum_rows for r in prepared['logical_plan']['result_sets'])
        or not paging_valid):
        raise ValueError('REVIEWED_QUERY_GRANT_SCOPE_MISMATCH')
    return ReviewedQueryGrantDecision(grant_digest=semantic_digest(grant),grant=grant,principal=principal.employee_id,
        purpose=authority['purpose'],preparation_receipt_digest=prepared['receipt_digest'],
        source_snapshot_digest=mapping['source_snapshot_digest'])


def authorize_reviewed_paging(grant,prepared,*,result_set_id,paging_policy_digest,
        page_size,total_row_count):
    """Check the exact reviewed paging policy and bounded total for every phase."""
    grant=ReviewedQueryExecutionGrant.model_validate(grant.model_dump(mode='json'))
    if grant.contract_version!='boi/reviewed-query-execution-grant@2':
        raise ValueError('REVIEWED_QUERY_PAGING_GRANT_REQUIRED')
    selected=next((item for item in prepared['logical_plan']['result_sets']
        if item['result_set_id']==result_set_id),None)
    if selected is None or selected.get('row_limit_policy')!='SNAPSHOT_PAGED':
        raise ValueError('REVIEWED_QUERY_PAGING_RESULT_SET_NOT_AUTHORIZED')
    from .snapshot_result_paging import SnapshotPagingPolicy
    policy=SnapshotPagingPolicy.model_validate(selected.get('paging_policy'))
    if (policy.policy_digest!=paging_policy_digest
        or policy.policy_digest not in grant.paging_policy_digests
        or policy.page_size!=page_size
        or page_size>grant.maximum_rows
        or selected['result_row_limit']>grant.maximum_rows
        or (total_row_count is not None
            and total_row_count>int(grant.maximum_total_rows or 0))):
        raise ValueError('REVIEWED_QUERY_PAGING_GRANT_SCOPE_MISMATCH')


def reviewed_query_authorizer_from_environment(environ,*,clock=None):
    """Explicit opt-in, bounded reads and exact file digest, refreshed for every access."""
    if str(environ.get('BOI_REVIEWED_QUERY_ENABLED','')).lower() not in {'true','1','yes','on'}:return None
    path=environ.get('BOI_REVIEWED_QUERY_GRANT_PATH','');expected=environ.get('BOI_REVIEWED_QUERY_GRANT_DIGEST','')
    if not path or not expected:raise ValueError('REVIEWED_QUERY_GRANT_CONFIGURATION_REQUIRED')
    def resolve():
        try:
            with Path(path).open('rb') as handle:raw=handle.read(131073)
            if len(raw)>131072 or 'sha256:'+hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('drift')
            return ReviewedQueryExecutionGrant.model_validate_json(raw)
        except (OSError,ValueError):raise ValueError('REVIEWED_QUERY_GRANT_INVALID_OR_CHANGED') from None
    resolve()
    return lambda principal,prepared:authorize_reviewed_query(resolve(),principal,prepared,
        at=clock() if clock else None)
