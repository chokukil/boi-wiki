"""Bind fresh process answers to the exact meaning assets actually delivered.

Sentences carry citations individually. Binding verifies reference/evidence
provenance and body length; sentence entailment remains a separate assessment.
"""
import json
from typing import Literal
from pydantic import Field

from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref,RevisionRef
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


class ProcessAnswerCitation(FrozenContract):
    asset_revision:RevisionRef
    target_pointer:Ref = Field(description='Pointer relative to the stored process draft: /records/{i}/assertions/{j} or /records/{i}/terms/{j}.')


class ProcessAnswerSentence(FrozenContract):
    text:Ref
    kind:Literal['source_reported_fact','evidence_gap','interpretation']
    citations:tuple[ProcessAnswerCitation,...] = Field(min_length=1)


class ProcessQuestionAnswer(FrozenContract):
    question_id:Ref
    sentences:tuple[ProcessAnswerSentence,...] = Field(min_length=1)
    limitations:tuple[Ref,...] = ()

    @property
    def body(self):return ' '.join(s.text for s in self.sentences)


class ProcessAnswerDraft(FrozenContract):
    context_digest:Ref
    answers:tuple[ProcessQuestionAnswer,...] = Field(min_length=1)


def bind_process_answers(draft, *, context, questions):
    draft=ProcessAnswerDraft.model_validate(draft);context=TaskKnowledgeContext.model_validate(context)
    if draft.context_digest!=context.context_digest:raise ValueError('PROCESS_ANSWER_CONTEXT_MISMATCH')
    expected={q['id']:q for q in questions}
    if len(expected)!=len(questions):raise ValueError('PROCESS_ANSWER_DUPLICATE_QUESTION')
    ids=[a.question_id for a in draft.answers]
    if len(set(ids))!=len(ids) or set(ids)!=set(expected):raise ValueError('PROCESS_ANSWER_QUESTION_COVERAGE_MISMATCH')
    assets={a.revision:json.loads(a.content_json) for a in context.assets if a.kind=='definition'}
    outputs=[]
    for answer in draft.answers:
        limit=expected[answer.question_id].get('max_body_characters')
        if limit is not None and len(answer.body)>limit:
            raise ValueError('PROCESS_ANSWER_BODY_TOO_LONG')
        sentences=[]
        for sentence in answer.sentences:
            citations=[]
            for citation in sentence.citations:
                asset=assets.get(citation.asset_revision)
                if not asset or asset.get('contract_version')!='boi/bound-process-meaning@1':
                    raise ValueError('PROCESS_ANSWER_ASSET_NOT_READ')
                targets={f'/records/{ri}/{kind}/{i}' for ri,r in enumerate(asset['draft']['records'])
                    for kind in ('assertions','terms') for i,_ in enumerate(r[kind])}
                if citation.target_pointer not in targets:raise ValueError('PROCESS_ANSWER_TARGET_UNAVAILABLE')
                # Match the complete pointer component boundary, not prefix 1/10.
                bindings=[b for b in asset['bindings'] if b['target_pointer'].startswith(citation.target_pointer+'/')]
                if not bindings:raise ValueError('PROCESS_ANSWER_TARGET_WITHOUT_EVIDENCE')
                citations.append({'asset_revision':citation.asset_revision.model_dump(mode='json'),
                    'target_pointer':citation.target_pointer,'source_bindings':bindings})
            sentences.append({'text':sentence.text,'kind':sentence.kind,'citations':citations,
                'semantic_support':'not_evaluated'})
        outputs.append({'question_id':answer.question_id,'body':answer.body,'body_characters':len(answer.body),
            'sentences':sentences,'limitations':list(answer.limitations)})
    return {'contract_version':'boi/bound-process-answers@1','context_digest':context.context_digest,'answers':outputs,
        'reference_binding':'pass','source_fidelity':'not_evaluated','scientific_correctness':'not_evaluated',
        'status':'PROVISIONAL','canonical_projection_eligible':False}
