"""Attributed local source assessments and scoped source-reported use evidence.

An assessment is an authenticated author's opinion, not proof that a model ran,
an independent review, a physical binding or scientific truth. Only the server
can combine it with exact inputs/checks into a scoped use qualification.
"""
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .knowledge_content import ContentContract, meaning_pointer
from .semantic_binding_contract import Digest, Ref, RevisionRef, semantic_digest
from .local_bundle_contract import LocalId
from .source_envelope import ArtifactEnvelope
from .typed_knowledge_meaning import TypedKnowledgeMeaning


from .knowledge_use_purpose import UsePurpose


class AssessmentInputObject(ContentContract):
    object_id: LocalId
    byte_digest: Digest


class LocalSourceQuotation(ContentContract):
    source_object_id: LocalId | None = None
    existing_source: ArtifactEnvelope | None = None
    source_byte_digest: Digest
    field_locator: str = Field(max_length=2048)
    quote: str = Field(min_length=1,max_length=32000)
    quote_occurrence: int = Field(ge=0,strict=True)

    @model_validator(mode='after')
    def exact_source(self):
        if (self.source_object_id is None) == (self.existing_source is None):
            raise ValueError('KNOWLEDGE_ASSESSMENT_EXACT_SOURCE_REQUIRED')
        if self.existing_source and self.existing_source.digest != self.source_byte_digest:
            raise ValueError('KNOWLEDGE_ASSESSMENT_SOURCE_CHANGED')
        return self

    @model_serializer(mode='wrap')
    def preserve_existing_wire(self, handler):
        value = handler(self)
        if self.existing_source is None:
            value.pop('existing_source', None)
        if self.source_object_id is None:
            value.pop('source_object_id', None)
        return value


class LocalMeaningJudgment(ContentContract):
    # Meaning-relative pointers refer to the complete original proposal's
    # content.meaning, before only declared reference tokens are rewritten.
    pointer: str = Field(max_length=2048)
    label: Literal['supported','contradicted','unsupported']
    reason: str = Field(min_length=1,max_length=16000)
    evidence: tuple[LocalSourceQuotation,...] = Field(min_length=1,max_length=64)


class LocalUnresolvedReview(ContentContract):
    index: int = Field(ge=0, strict=True)
    item_digest: Digest
    label: Literal['supported', 'contradicted', 'unsupported']
    reason: str = Field(min_length=1, max_length=16000)
    evidence: tuple[LocalSourceQuotation, ...] = Field(min_length=1, max_length=64)


class LocalStatementReview(ContentContract):
    contract_version: Literal['boi/source-statement-review@1', 'boi/source-statement-review@2', 'boi/source-relation-review@1']
    claim_basis: Literal['reported_statement_exists']
    inventory_digest: Digest
    items: tuple[LocalUnresolvedReview, ...] = Field(default=(), max_length=1000)

    @model_validator(mode='after')
    def exact_inventory_indexes(self):
        if len({item.index for item in self.items}) != len(self.items):
            raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_DUPLICATE_ITEM')
        return self


class LocalFormulaReview(ContentContract):
    contract_version: Literal['boi/source-formula-review@1']
    claim_basis: Literal['caller_supplied_definition_scenario']
    inventory_digest: Digest
    items: tuple[LocalUnresolvedReview,...] = Field(default=(),max_length=1000)

    @model_validator(mode='after')
    def unique_indexes(self):
        if len({v.index for v in self.items})!=len(self.items):
            raise ValueError('FORMULA_REVIEW_DUPLICATE_ITEM')
        return self


class LocalUseAssessment(ContentContract):
    purpose: UsePurpose
    requested_pointers: tuple[str,...] = Field(min_length=1,max_length=256)
    judgments: tuple[LocalMeaningJudgment,...] = Field(min_length=1,max_length=2000)
    limitations: tuple[str,...] = Field(min_length=1,max_length=256)
    statement_review: LocalStatementReview | None = None
    formula_review: LocalFormulaReview | None = Field(default=None,exclude_if=lambda v:v is None)

    @model_validator(mode='after')
    def exact_scope(self):
        if self.formula_review is not None and (self.purpose!='formula_input' or self.statement_review is not None):
            raise ValueError('FORMULA_REVIEW_PURPOSE_REQUIRED')
        if (len(set(self.requested_pointers)) != len(self.requested_pointers)
                or len({j.pointer for j in self.judgments}) != len(self.judgments)):
            raise ValueError('KNOWLEDGE_ASSESSMENT_DUPLICATE_SCOPE')
        if self.statement_review is not None:
            expected = ('traverse' if self.statement_review.contract_version ==
                'boi/source-relation-review@1' else 'filter')
            if self.purpose != expected:
                raise ValueError('KNOWLEDGE_STATEMENT_REVIEW_' + expected.upper() + '_PURPOSE_REQUIRED')
        return self

    @model_serializer(mode='wrap')
    def preserve_legacy_wire(self, handler):
        value = handler(self)
        if self.statement_review is None:
            value.pop('statement_review', None)
        return value


class LocalKnowledgeAssessment(ContentContract):
    contract_version: Literal['boi/local-knowledge-assessment@1'] = 'boi/local-knowledge-assessment@1'
    target_object_id: LocalId
    target_byte_digest: Digest
    input_objects: tuple[AssessmentInputObject,...] = Field(min_length=1,max_length=1100)
    existing_revisions: tuple[RevisionRef,...] = Field(default=(),max_length=1000)
    agent_session_ref: Ref
    reported_reviewer_relationship: Literal['unknown','same_session','independent'] = 'unknown'
    uses: tuple[LocalUseAssessment,...] = Field(min_length=1,max_length=6)
    execution_attested: Literal[False] = False
    reviewer_relationship_verified: Literal[False] = False
    semantic_truth_proven: Literal[False] = False

    @model_validator(mode='after')
    def unique_inputs(self):
        if (len({i.object_id for i in self.input_objects}) != len(self.input_objects)
                or len(set(self.existing_revisions)) != len(self.existing_revisions)
                or len({u.purpose for u in self.uses}) != len(self.uses)):
            raise ValueError('KNOWLEDGE_ASSESSMENT_DUPLICATE_INPUT')
        return self


def typed_use_closure(content, use):
    """Expand selected fields to complete assertions and their derivation DAG.

    Whole assertion values retain polarity, modality, conditions, exceptions,
    applicability, time and dependencies. Leaf approval never approves the rest.
    This is typed structure selection, with no question/name/keyword routing.
    """
    meaning = TypedKnowledgeMeaning.model_validate(content.meaning)
    by_id = {a.id:i for i,a in enumerate(meaning.assertions)}
    roots, parameter_roots = set(), set()
    for selected in use.required_meaning_pointers:
        meaning_pointer(content.meaning,selected)
        matches = [i for i in range(len(meaning.assertions))
                   if selected == f'/assertions/{i}' or selected.startswith(f'/assertions/{i}/')]
        parameters = [i for i in range(len(meaning.parameters))
                      if selected == f'/parameters/{i}' or selected.startswith(f'/parameters/{i}/')]
        if len(matches)+len(parameters) != 1:
            raise ValueError('KNOWLEDGE_USE_ASSERTION_SCOPE_REQUIRED')
        if matches:roots.add(matches[0])
        else:parameter_roots.add(parameters[0])
    closure = set()
    def visit(index):
        if index in closure:
            return
        closure.add(index)
        for dependency in meaning.assertions[index].depends_on:
            visit(by_id[dependency])
    for index in roots:
        visit(index)
    for index in parameter_roots:
        for dependency in meaning.parameters[index].depends_on:visit(by_id[dependency])
    parameters={str(i):meaning.parameters[i].model_dump(mode='json') for i in sorted(parameter_roots)}
    return {'roots':tuple(f'/assertions/{i}' for i in sorted(roots))+tuple(f'/parameters/{i}' for i in sorted(parameter_roots)),
        'closure':tuple(f'/assertions/{i}' for i in sorted(closure))+tuple(f'/parameters/{i}' for i in sorted(parameter_roots)),
        'nodes':{**{f'/assertions/{i}':meaning.assertions[i].model_dump(mode='json') for i in sorted(closure)},
                 **{f'/parameters/{i}':p for i,p in parameters.items()}},
        'scope_digest':semantic_digest({'purpose':use.purpose,'contract':use.model_dump(mode='json'),
            'object_type':meaning.object_type.model_dump(mode='json'),
            **({'parameters':parameters} if parameters else {}),
            'assertions':{str(i):meaning.assertions[i].model_dump(mode='json') for i in sorted(closure)}})}
