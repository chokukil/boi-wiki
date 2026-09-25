"""Native revision refresh inputs contain no new source rights or passed flags."""
from typing import Literal
from pydantic import Field, model_serializer, model_validator

from .local_bundle_contract import LocalUseSupersession
from .knowledge_use_contract import LocalStatementReview,LocalFormulaReview
from .semantic_binding_contract import FrozenContract, RevisionRef, Ref


class PublishedStatementReview(FrozenContract):
    purpose: Literal['filter','traverse']
    review: LocalStatementReview
    agent_session_ref: Ref
    reported_reviewer_relationship: Literal['unknown','same_session','independent'] = 'unknown'

    @model_validator(mode='after')
    def exact_native_review(self):
        expected='traverse' if self.review.contract_version=='boi/source-relation-review@1' else 'filter'
        if self.purpose!=expected:
            raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_PURPOSE_REQUIRED')
        if any(quote.existing_source is None for item in self.review.items for quote in item.evidence):
            raise ValueError('KNOWLEDGE_REFRESH_EXISTING_SOURCE_REQUIRED')
        return self


class PublishedQualificationRead(FrozenContract):
    revision: RevisionRef


class PublishedFormulaReview(FrozenContract):
    purpose: Literal['formula_input']
    review: LocalFormulaReview
    agent_session_ref: Ref
    reported_reviewer_relationship: Literal['unknown','same_session','independent'] = 'unknown'

    @model_validator(mode='after')
    def native_sources(self):
        if any(q.existing_source is None for item in self.review.items for q in item.evidence):
            raise ValueError('KNOWLEDGE_REFRESH_EXISTING_SOURCE_REQUIRED')
        return self


class PublishedQualificationRefresh(PublishedQualificationRead):
    supersedes: tuple[LocalUseSupersession,...] = Field(min_length=1,max_length=6)
    reuse_statement_reviews: tuple[Literal['filter','traverse'],...] = Field(default=(),max_length=2,exclude_if=lambda v:not v,description='Explicitly revalidate the exact predecessor recorded review with current source rights, full inventory, mechanical checks and policy. Does not create a new semantic opinion.')
    statement_reviews: tuple[PublishedStatementReview,...] = Field(default=(),max_length=2)
    formula_reviews: tuple[PublishedFormulaReview,...] = Field(default=(),max_length=1,exclude_if=lambda v:not v)

    @model_validator(mode='after')
    def unique_purposes(self):
        if len({item.purpose for item in self.supersedes})!=len(self.supersedes):
            raise ValueError('KNOWLEDGE_USE_SUPERSESSION_DUPLICATE_PURPOSE')
        reviews=(*self.statement_reviews,*self.formula_reviews)
        purposes={item.purpose for item in reviews}
        if len(purposes)!=len(reviews) or not purposes<={item.purpose for item in self.supersedes}:
            raise ValueError('KNOWLEDGE_REFRESH_REVIEW_SUPERSESSION_REQUIRED')
        reused=set(self.reuse_statement_reviews)
        if (len(reused)!=len(self.reuse_statement_reviews) or reused & purposes
                or not reused<={item.purpose for item in self.supersedes}):
            raise ValueError('KNOWLEDGE_REFRESH_RECORDED_REVIEW_PURPOSE_CONFLICT')
        return self

    @model_serializer(mode='wrap')
    def legacy_wire(self, handler):
        value=handler(self)
        if not self.statement_reviews:
            value.pop('statement_reviews',None)
        return value
