"""Completeness and evidence checks for an external answer fidelity assessor."""
from collections import Counter
from typing import Literal
from pydantic import Field

from boi_api.app.governed_runtime.process_knowledge_contract import ProcessQuotation
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref


class SentenceAssessment(FrozenContract):
    target_pointer:Ref
    source_relation:Literal['supported','contradicted','unsupported']
    citation_support:Literal['full','partial','none','not_applicable']
    reason:Ref
    evidence:tuple[ProcessQuotation,...] = Field(min_length=1)


class AnswerRequirementAssessment(FrozenContract):
    requirement_id:Ref
    status:Literal['covered','partial','omitted']
    target_pointers:tuple[Ref,...]
    reason:Ref


class ProcessAnswerAssessment(FrozenContract):
    claims:tuple[SentenceAssessment,...]
    requirements:tuple[AnswerRequirementAssessment,...]
    limitations:tuple[Ref,...] = Field(min_length=1)


def answer_targets(answers):
    targets=[]
    for ai,answer in enumerate(answers['answers']):
        for si,sentence in enumerate(answer['sentences']):
            targets.append({'target_pointer':f'/answers/{ai}/sentences/{si}',
                'question_id':answer['question_id'],'kind':'sentence','value':sentence})
        for li,limitation in enumerate(answer['limitations']):
            targets.append({'target_pointer':f'/answers/{ai}/limitations/{li}',
                'question_id':answer['question_id'],'kind':'limitation','value':limitation})
    return targets


def answer_requirements(oracle,source_oracle):
    propositions={p['id']:p for r in source_oracle['records'] for p in r['required_propositions']}
    requirements=[]
    for question in oracle['questions']:
        for identity in question['required_propositions']:
            requirements.append({'requirement_id':question['id']+':'+identity,'question_id':question['id'],**propositions[identity]})
        for boundary in question['boundaries']:
            requirements.append({'requirement_id':question['id']+':'+boundary['id'],'question_id':question['id'],**boundary})
    return requirements


def check_answer_assessment(assessment,*,answers,evidence,oracle,source_oracle):
    assessment=ProcessAnswerAssessment.model_validate(assessment)
    targets={t['target_pointer']:t for t in answer_targets(answers)}
    requirements={r['requirement_id']:r for r in answer_requirements(oracle,source_oracle)}
    ids=[c.target_pointer for c in assessment.claims]
    if len(set(ids))!=len(ids) or set(ids)!=set(targets):raise ValueError('ANSWER_ASSESSMENT_CLAIM_COVERAGE_INCOMPLETE')
    ids=[r.requirement_id for r in assessment.requirements]
    if len(set(ids))!=len(ids) or set(ids)!=set(requirements):raise ValueError('ANSWER_ASSESSMENT_REQUIREMENT_COVERAGE_INCOMPLETE')
    claims={c.target_pointer:c for c in assessment.claims}
    for item in assessment.requirements:
        pointers=set(item.target_pointers)
        if any(p not in targets or targets[p]['question_id']!=requirements[item.requirement_id]['question_id'] for p in pointers):
            raise ValueError('ANSWER_ASSESSMENT_REQUIREMENT_REFERENCE_MISMATCH')
        if item.status=='covered' and (not pointers or any(claims[p].source_relation!='supported' for p in pointers)):
            raise ValueError('ANSWER_ASSESSMENT_UNSUPPORTED_COVERAGE')
    fields={f['field_locator']:f['text'] for f in evidence['fields']}
    for item in assessment.claims:
        if targets[item.target_pointer]['kind']=='sentence' and item.citation_support=='not_applicable':
            raise ValueError('ANSWER_ASSESSMENT_SENTENCE_CITATION_SKIPPED')
        for quote in item.evidence:
            source=fields.get(quote.field_locator,'');start=-1
            for _ in range(quote.occurrence+1):
                start=source.find(quote.quote,start+1)
                if start<0:raise ValueError('ANSWER_ASSESSMENT_QUOTE_NOT_IN_SOURCE')
    accepted=all(c.source_relation=='supported' and (c.citation_support=='full' or targets[c.target_pointer]['kind']=='limitation')
        for c in assessment.claims) and all(r.status=='covered' for r in assessment.requirements)
    return {'claim_counts':dict(Counter(c.source_relation for c in assessment.claims)),
        'citation_counts':dict(Counter(c.citation_support for c in assessment.claims)),
        'requirement_counts':dict(Counter(r.status for r in assessment.requirements)),
        'assessment_complete':True,'model_assessment_accepts_answers':accepted,
        'method':'Independent external model assessment with precommitted question requirements',
        'deterministic_entailment_proven':False,'scientific_correctness':'not_evaluated','status':'PROVISIONAL'}
