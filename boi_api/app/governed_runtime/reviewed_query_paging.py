"""Typed, evidence-bound pages for reviewed provisional query answers."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from .governed_answer_artifact import ArtifactField, ArtifactRow, ArtifactResultSet
from .semantic_binding_contract import Digest, FrozenContract, Ref, semantic_digest


class ReviewedQueryAnswerPage(FrozenContract):
    contract_version: Literal['boi/reviewed-query-answer-page@1'] = (
        'boi/reviewed-query-answer-page@1'
    )
    execution_classification: Literal['PROVISIONAL'] = 'PROVISIONAL'
    authority: Literal['REVIEWED_CANDIDATE'] = 'REVIEWED_CANDIDATE'
    canonical: Literal[False] = False
    preparation_receipt_digest: Digest
    answer_artifact_semantic_digest: Digest
    protected_artifact_digest: Digest
    execution_receipt_digest: Digest
    grant_digest: Digest
    page_access_receipt_digest: Digest
    logical_plan_digest: Digest
    source_snapshot_digest: Digest
    result_set_id: Ref
    paging_ref: Ref
    paging_policy_digest: Digest
    total_row_count: int = Field(ge=0)
    returned_row_count: int = Field(ge=0,le=1000)
    page_size: int = Field(ge=1,le=1000)
    offset: int = Field(ge=0)
    end_offset_exclusive: int = Field(ge=0)
    final_page: bool
    complete_delivery: bool
    next_cursor: str | None = Field(default=None,max_length=4000)
    row_identity_outputs: tuple[str,...] = Field(min_length=1)
    fields: tuple[ArtifactField,...] = Field(min_length=1)
    rows: tuple[ArtifactRow,...]
    page_result_digest: Digest
    page_receipt_digest: Digest
    response_digest: Digest

    @model_validator(mode='after')
    def exact_page(self):
        outputs=tuple(item.output_name for item in self.fields)
        if len(outputs)!=len(set(outputs)):
            raise ValueError('REVIEWED_QUERY_PAGE_FIELD_DUPLICATE')
        if (self.returned_row_count!=len(self.rows)
            or self.end_offset_exclusive!=self.offset+self.returned_row_count
            or self.end_offset_exclusive>self.total_row_count
            or self.final_page!=(
                self.end_offset_exclusive==self.total_row_count)
            or self.complete_delivery!=(
                self.offset==0 and self.end_offset_exclusive==self.total_row_count)
            or (self.next_cursor is None)!=(
                self.end_offset_exclusive==self.total_row_count)):
            raise ValueError('REVIEWED_QUERY_PAGE_COUNT_INVALID')
        expected_identity=set(self.row_identity_outputs)
        for row in self.rows:
            if set(row.values)!=set(outputs):
                raise ValueError('REVIEWED_QUERY_PAGE_ROW_SCHEMA_MISMATCH')
            if tuple(name for name,_ in row.identity)!=self.row_identity_outputs:
                raise ValueError('REVIEWED_QUERY_PAGE_ROW_IDENTITY_MISMATCH')
            if any(name not in expected_identity or value!=str(row.values[name])
                    for name,value in row.identity):
                raise ValueError('REVIEWED_QUERY_PAGE_ROW_IDENTITY_MISMATCH')
        if self.page_result_digest!=semantic_digest(
                [row.values for row in self.rows]):
            raise ValueError('REVIEWED_QUERY_PAGE_RESULT_DIGEST_MISMATCH')
        unsigned=self.model_dump(mode='json',exclude={'response_digest'})
        if self.response_digest!=semantic_digest(unsigned):
            raise ValueError('REVIEWED_QUERY_PAGE_RESPONSE_DIGEST_MISMATCH')
        return self


def build_reviewed_query_answer_page(*,prepared: dict[str,Any],answer_digest: str,
        protected_artifact_digest: str,execution_receipt_digest: str,
        grant_digest: str,page_access_receipt_digest: str,
        result_set: ArtifactResultSet,page: dict[str,Any]
        ) -> ReviewedQueryAnswerPage:
    """Project protected page rows through the already-built answer field contract."""
    if result_set.paging is None:
        raise ValueError('REVIEWED_QUERY_PAGE_NOT_DECLARED')
    outputs=tuple(field.output_name for field in result_set.fields)
    raw_rows=tuple(dict(row) for row in page['rows'])
    if any(set(row)!=set(outputs) for row in raw_rows):
        raise ValueError('REVIEWED_QUERY_PAGE_ROW_SCHEMA_MISMATCH')
    rows=tuple(ArtifactRow(
        identity=tuple((name,str(row[name])) for name in result_set.row_identity_outputs),
        values={name:row[name] for name in outputs},
    ) for row in raw_rows)
    body={
        'contract_version':'boi/reviewed-query-answer-page@1',
        'execution_classification':'PROVISIONAL',
        'authority':'REVIEWED_CANDIDATE',
        'canonical':False,
        'preparation_receipt_digest':prepared['receipt_digest'],
        'answer_artifact_semantic_digest':answer_digest,
        'protected_artifact_digest':protected_artifact_digest,
        'execution_receipt_digest':execution_receipt_digest,
        'grant_digest':grant_digest,
        'page_access_receipt_digest':page_access_receipt_digest,
        'logical_plan_digest':page['logical_plan_digest'],
        'source_snapshot_digest':page['source_snapshot_digest'],
        'result_set_id':page['result_set_id'],
        'paging_ref':page['paging_ref'],
        'paging_policy_digest':result_set.paging.policy_digest,
        'total_row_count':page['total_row_count'],
        'returned_row_count':page['returned_row_count'],
        'page_size':result_set.paging.page_size,
        'offset':page['offset'],
        'end_offset_exclusive':page['end_offset_exclusive'],
        'final_page':page['end_offset_exclusive']==page['total_row_count'],
        'complete_delivery':page['complete_delivery'],
        'next_cursor':page['next_cursor'],
        'row_identity_outputs':result_set.row_identity_outputs,
        'fields':tuple(field.model_dump(mode='json') for field in result_set.fields),
        'rows':tuple(row.model_dump(mode='json') for row in rows),
        'page_result_digest':page['page_result_digest'],
        'page_receipt_digest':page['receipt_digest'],
    }
    return ReviewedQueryAnswerPage.model_validate({
        **body,'response_digest':semantic_digest(body),
    })


__all__=['ReviewedQueryAnswerPage','build_reviewed_query_answer_page']
