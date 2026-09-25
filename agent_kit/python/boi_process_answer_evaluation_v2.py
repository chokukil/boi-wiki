"""Independent assessment material with separate source and Wiki-state evidence.

Only binding/coverage/integrity is deterministic. Semantic judgments, including
absence within a read scope and correct paraphrase, remain model assessments.
"""
from collections import Counter
from typing import Literal

from pydantic import Field

from agent_kit.python.boi_process_answer_assessment import answer_requirements
from agent_kit.python.boi_process_answer_v2 import (MeaningCitation, SourceCitation, SourceScopeCitation,
    WikiStateCitation, AssetStateCitation, ExecutionResultCitation, bind_process_answers_v2, validate_source_readings)
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract, Ref, semantic_digest
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


class AssessmentContractError(ValueError):
    def __init__(self, code, *, target_pointer):
        super().__init__(code)
        self.protocol_issues=[{'reason_code':code,'target_pointer':target_pointer}]


class StatementAssessment(FrozenContract):
    target_pointer: Ref
    support_relation: Literal['supported','contradicted','unsupported']
    citation_support: Literal['full','partial','none']
    evidence_ids: tuple[Ref,...] = Field(min_length=1)
    reason: Ref


class RequirementAssessment(FrozenContract):
    requirement_id: Ref
    status: Literal['covered','partial','omitted']
    target_pointers: tuple[Ref,...]
    reason: Ref


class AnswerAssessmentV2(FrozenContract):
    contract_version: Literal['boi/process-answer-assessment@2'] = 'boi/process-answer-assessment@2'
    statements: tuple[StatementAssessment,...]
    requirements: tuple[RequirementAssessment,...]
    limitations: tuple[Ref,...] = Field(min_length=1)


def verified_answer_material(*, answers, context, sources, questions, oracle, source_oracle):
    from .boi_process_answer_v2 import request_plan_proposal
    context=TaskKnowledgeContext.model_validate(context)
    if answers.get('contract_version')!='boi/bound-process-answers@2':raise ValueError('ANSWER_EVAL_VERSION_REQUIRED')
    types={'meaning':MeaningCitation,'source_quote':SourceCitation,'source_scope':SourceScopeCitation,
        'wiki_state':WikiStateCitation,'asset_state':AssetStateCitation,'execution_result':ExecutionResultCitation}
    def draft_statement(s):
        return {'text':s['text'],'kind':s['kind'],
            **({'basis_statement_pointers':s['basis_statement_pointers']} if 'basis_statement_pointers' in s else {}),'citations':[
            {k:v for k,v in c.items() if k in types[c['kind']].model_fields} for c in s['citations']]}
    draft={'context_digest':answers['context_digest'],'answers':[{'question_id':a['question_id'],
        **({'request_plan':request_plan_proposal(a['request_plan'])} if a.get('request_plan') else {}),
        **({'layout':a['layout']} if 'layout' in a else {}),
        'sentences':[draft_statement(s) for s in a['sentences']],
        'limitations':[draft_statement(s) for s in a['limitations']]} for a in answers['answers']]}
    rebound=bind_process_answers_v2(draft,context=context,sources=sources,questions=questions,execution_results=answers.get('execution_results'))
    if semantic_digest(rebound)!=semantic_digest(answers):raise ValueError('ANSWER_EVAL_BOUND_MATERIAL_TAMPERED')
    indexed=validate_source_readings(context,sources)
    catalog=[]
    for revision,source in indexed.items():
        for locator,field in source['fields'].items():
            catalog.append({'evidence_id':'field:'+semantic_digest([revision,locator]),'kind':'source_field',
                'source_revision_digest':revision,**field})
    for field in WikiStateCitation.model_fields['field'].annotation.__args__:
        catalog.append({'evidence_id':'state:'+field,'kind':'wiki_state','field':field,
            'context_digest':context.context_digest,'value':getattr(context,field)})
    for asset in context.assets:
        catalog.append({'evidence_id':'authority:'+asset.revision.ref,'kind':'asset_state','field':'authority',
            'asset_revision':asset.revision.model_dump(mode='json'),'value':asset.authority})
    for digest,value in answers.get('execution_results',{}).items():
        catalog.append({'evidence_id':'execution:'+digest,'kind':'execution_result','result_digest':digest,'value':value})
    targets=[]
    for ai,answer in enumerate(answers['answers']):
        for location in ('sentences','limitations'):
            for si,s in enumerate(answer[location]):
                citations=[]
                for citation in s['citations']:
                    value=dict(citation)
                    value['exact_source_texts']=[{
                        'field_locator':b['field_locator'],'source_revision_digest':b['source_revision_digest'],
                        'text':indexed[b['source_revision_digest']]['fields'][b['field_locator']]['text'][b['start']:b['end']],
                        'start':b['start'],'end':b['end']} for b in citation['source_bindings']]
                    citations.append(value)
                targets.append({'target_pointer':f'/answers/{ai}/{location}/{si}','question_id':answer['question_id'],
                    'text':s['text'],'kind':s['kind'],'citations':citations,
                    **({'basis_statement_pointers':s['basis_statement_pointers']} if 'basis_statement_pointers' in s else {})})
    requirements=answer_requirements(oracle,source_oracle)
    if set(q['id'] for q in questions)!=set(q['id'] for q in oracle['questions']):raise ValueError('ANSWER_EVAL_QUESTION_ORACLE_MISMATCH')
    return {'contract_version':'boi/process-answer-evaluation-material@2','questions':questions,
        **({'request_plans':[{'question_id':a['question_id'],'plan':a['request_plan']}
            for a in answers['answers'] if a.get('request_plan')]} if any(a.get('request_plan') for a in answers['answers']) else {}),
        **({'answer_layouts':[{ 'question_id':a['question_id'],'layout':a.get('layout')} for a in answers['answers']]} if any('layout' in a for a in answers['answers']) else {}),
        'targets':targets,'evidence_catalog':catalog,'requirements':requirements,
        'answers_digest':semantic_digest(answers),'context_digest':context.context_digest,
        'source_reading_digests':answers['source_reading_digests'],
        'scope':'Complete supplied source fields and Wiki envelope facts. Neither candidate content nor source prose establishes scientific truth.'}


def check_answer_assessment_v2(assessment, *, material):
    assessment=AnswerAssessmentV2.model_validate(assessment)
    targets={t['target_pointer']:t for t in material['targets']}
    required={r['requirement_id']:r for r in material['requirements']}
    catalog={e['evidence_id']:e for e in material['evidence_catalog']}
    def exact(actual,expected,code):
        if len(set(actual))!=len(actual) or set(actual)!=set(expected):raise ValueError('ANSWER_EVAL_'+code)
    exact([s.target_pointer for s in assessment.statements],targets,'STATEMENT_COVERAGE_INCOMPLETE')
    exact([r.requirement_id for r in assessment.requirements],required,'REQUIREMENT_COVERAGE_INCOMPLETE')
    statements={s.target_pointer:s for s in assessment.statements}
    for item in assessment.statements:
        if not set(item.evidence_ids)<=set(catalog):raise ValueError('ANSWER_EVAL_UNKNOWN_EVIDENCE')
        kinds={catalog[e]['kind'] for e in item.evidence_ids}
        # An accepted positive report must keep its evidence domain. A negative
        # or partial report may cite another domain to EXPLAIN the missing or
        # mixed support; rejecting that diagnostic would conceal the actual
        # answer defect. Such a report still cannot pass the all-full gate.
        if item.support_relation=='supported' and item.citation_support=='full':
            if targets[item.target_pointer]['kind']=='runtime_state':
                if not kinds<={'wiki_state','asset_state','execution_result'}:raise AssessmentContractError('ANSWER_EVAL_RUNTIME_SOURCE_CONFUSION',target_pointer=item.target_pointer)
            elif kinds-{'source_field'}:raise AssessmentContractError('ANSWER_EVAL_SOURCE_RUNTIME_CONFUSION',target_pointer=item.target_pointer)
    for item in assessment.requirements:
        refs=set(item.target_pointers)
        if any(p not in targets or targets[p]['question_id']!=required[item.requirement_id]['question_id'] for p in refs):
            raise ValueError('ANSWER_EVAL_REQUIREMENT_REFERENCE_MISMATCH')
        if item.status=='covered' and (not refs or any(statements[p].support_relation!='supported' for p in refs)):
            raise ValueError('ANSWER_EVAL_UNSUPPORTED_COVERAGE')
    return {'contract_version':'boi/process-answer-evaluation-check@2','assessment_complete':True,
        'statement_counts':dict(Counter(s.support_relation for s in assessment.statements)),
        'citation_counts':dict(Counter(s.citation_support for s in assessment.statements)),
        'requirement_counts':dict(Counter(r.status for r in assessment.requirements)),
        'model_assessment_accepts_answers':all(s.support_relation=='supported' and s.citation_support=='full' for s in assessment.statements)
            and all(r.status=='covered' for r in assessment.requirements),
        'evaluation_material_digest':semantic_digest(material),'answers_digest':material['answers_digest'],
        'deterministic_entailment_proven':False,'scientific_correctness':'not_evaluated',
        'status':'PROVISIONAL','canonical_projection_eligible':False}
