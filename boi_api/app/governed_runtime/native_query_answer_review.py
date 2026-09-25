"""Bind native full-answer opinions to exact readable text and authorized results.

This consumes the existing NativeObservation ledger. It does not perform review,
turn an opinion into semantic proof, or change an answer's admission state.
"""
from typing import Literal
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, Ref, Digest, RevisionRef, semantic_digest
from .native_observation import read_native_observation, _json
from .domain_asset_store import DomainAssetStore, source_manifest_digest
from .source_envelope import ArtifactEnvelope
from .native_query_answer import NativeGovernedAnswerArtifact, build_native_query_answer


class NativeQueryAnswerText(FrozenContract):
    contract_version: Literal['boi/native-query-answer-text@1']='boi/native-query-answer-text@1'
    artifact_revision: RevisionRef
    artifact_semantic_digest: Digest
    question_digest: Digest
    body_markdown: Ref
    body_digest: Digest

    @model_validator(mode='after')
    def exact_body(self):
        if semantic_digest(self.body_markdown)!=self.body_digest:
            raise ValueError('NATIVE_ANSWER_TEXT_DIGEST_MISMATCH')
        return self


class NativeQueryAnswerReview(FrozenContract):
    contract_version: Literal['boi/native-query-answer-review@1']='boi/native-query-answer-review@1'
    artifact_revision: RevisionRef
    text_revision: RevisionRef
    artifact_semantic_digest: Digest
    question_digest: Digest
    body_digest: Digest
    disposition: Literal['supported_with_limits','needs_revision','unknown']
    findings: tuple[Ref,...]=Field(min_length=1)
    limitations: tuple[Ref,...]=Field(min_length=1)
    errors: tuple[Ref,...]
    reviewer_relationship: Literal['same_session']='same_session'
    semantic_truth_proven: Literal[False]=False
    execution_authority_granted: Literal[False]=False

    @model_validator(mode='after')
    def unresolved_errors(self):
        if self.errors and self.disposition=='supported_with_limits':
            raise ValueError('NATIVE_ANSWER_REVIEW_UNRESOLVED_ERRORS')
        return self


def bind_native_answer_review(*,artifact,text,review,artifact_revision,text_revision):
    text=NativeQueryAnswerText.model_validate(text)
    review=NativeQueryAnswerReview.model_validate(review)
    if text.artifact_revision!=review.artifact_revision:
        raise ValueError('NATIVE_ANSWER_REVIEW_BINDING_MISMATCH')
    if (text.artifact_revision!=RevisionRef.model_validate(artifact_revision)
        or review.text_revision!=RevisionRef.model_validate(text_revision)
        or not (text.artifact_semantic_digest==review.artifact_semantic_digest==artifact.artifact_semantic_digest)
        or not (text.question_digest==review.question_digest==artifact.question_digest)
        or text.body_digest!=review.body_digest):
        raise ValueError('NATIVE_ANSWER_REVIEW_BINDING_MISMATCH')
    return review


def read_native_query_answer_record(work,authorization,*,review_revision,artifact_revision,text_revision):
    """Read the exact stored snapshot/opinion with current Wiki authorization.

    Display is not query reexecution or current data validation. Consumers that
    reuse execution must additionally use read_native_query_answer_review.
    """
    observation=read_native_observation(work,authorization,review_revision)
    req=observation['request']
    review=NativeQueryAnswerReview.model_validate(observation['value'])
    if (req['review_contract_version']!=review.contract_version
        or semantic_digest(_json(req['output_schema_json']))!=semantic_digest(NativeQueryAnswerReview.model_json_schema())):
        raise ValueError('NATIVE_ANSWER_REVIEW_CONTRACT_MISMATCH')
    refs=tuple(RevisionRef.model_validate(x) for x in (artifact_revision,text_revision))
    if tuple(RevisionRef.model_validate(x) for x in req['input_revisions'])!=refs:
        raise ValueError('NATIVE_ANSWER_REVIEW_INPUT_MISMATCH')
    store=DomainAssetStore(work.intake)
    stored=store.read(authorization=authorization,revision=RevisionRef.model_validate(review_revision),lane='provisional')
    sources=tuple(ArtifactEnvelope.model_validate(s) for s in stored['sources'])
    context=work.contexts.validate_reading(authorization=authorization,
        revision=RevisionRef.model_validate(req['knowledge_reading_ref']),sources=sources,require_current=True)
    assets={a.revision:a for a in context.assets}
    if any(ref not in assets or assets[ref].kind!='pack' or assets[ref].authority!='candidate' for ref in refs):
        raise ValueError('NATIVE_ANSWER_REVIEW_KIND_OR_SCOPE_MISMATCH')
    artifact=NativeGovernedAnswerArtifact.model_validate(_json(assets[refs[0]].content_json))
    text=NativeQueryAnswerText.model_validate(_json(assets[refs[1]].content_json))
    if source_manifest_digest(sources)!=artifact.candidate_authority.definition_authority.source_manifest_digest:
        raise ValueError('NATIVE_ANSWER_REVIEW_SOURCE_MISMATCH')
    bound=bind_native_answer_review(artifact=artifact,text=text,review=review,
        artifact_revision=refs[0],text_revision=refs[1])
    return {'answer_text':text.model_dump(mode='json'),'review':bound.model_dump(mode='json'),
        'provenance':observation['provenance'],'classification':'PROVISIONAL',
        'artifact':artifact.model_dump(mode='json'),'sources':[s.model_dump(mode='json') for s in sources],
        'answer_admission_changed':False,'execution_authority_granted':False}


def read_native_query_answer_review(work,authorization,*,review_revision,artifact_revision,text_revision,
                                  gateway,outcome,request,execution):
    """Revalidate both stored bindings and current protected-result authority."""
    record=read_native_query_answer_record(work,authorization,review_revision=review_revision,
        artifact_revision=artifact_revision,text_revision=text_revision)
    artifact=NativeGovernedAnswerArtifact.model_validate(record['artifact'])
    current=build_native_query_answer(gateway=gateway,outcome=outcome,request=request,execution=execution)
    if artifact!=current:
        raise ValueError('NATIVE_ANSWER_REVIEW_RESULT_MISMATCH')
    return {k:v for k,v in record.items() if k not in ('artifact','sources')}
