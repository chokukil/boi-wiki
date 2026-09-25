"""Operational source/citation review of a user's answer, without answer keys.

The existing binder and assessment integrity checker are reused. Only original
questions define usefulness requirements; no evaluation fixture enters here.
Model judgments remain provisional and cannot alter Wiki authority metadata.
"""
import asyncio
import copy
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field
from agent_kit.python.boi_process_answer_layout import AnswerLayout

from agent_kit.python.boi_process_answer_evaluation_v2 import (
    verified_answer_material, check_answer_assessment_v2)
from .boi_response_record_alignment import AnswerAssessmentV2, LegacyAssessment, legacy_assessment, record_alignment_failures
from agent_kit.python.boi_process_answer_v2 import (
    SourceStatement, GapStatement, MeaningCitation, SourceCitation, SourceScopeCitation, RequestPlan, RequestFacet)
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract, Ref, Digest, semantic_digest


REVIEW_INSTRUCTIONS_V3 = (
    'Review the proposed answer against the supplied original source fields, exact citations and user questions. '
    'Assess every selected statement for source support and whether its actual attached citations support the '
    'whole statement, including identity, conditions, negation, scope and historical revision. Valid paraphrase '
    'is supported. A source-scoped gap is valid only within the source scope actually read. Do not label an '
    'unestablished addition scientifically false. Do not require general scientific facts absent from the source. '
    'Assess the original user question for useful coverage; needless refusal of available information is a failure. '
    'A supported statement with partial citations still needs repair. Cite evidence IDs from the catalog. '
    'There are no expected answers, labels, external sources or evaluation fixtures. This is a model review, '
    'not scientific proof or expert validation. Explain reasons in Korean. ')

REVIEW_INSTRUCTIONS = REVIEW_INSTRUCTIONS_V3 + (
    'Question coverage must be present in user-visible answer text, not only in a citation graph or the original source. '
    'For a request for reasons, distinguish the stated outcome or difficulty from the source-reported causal mechanism '
    'or constraint explaining it. Mark partial when that necessary explanation is omitted even if all written '
    'statements are supported. Do not require irrelevant source details or identical terminology. '
    'If the output token limit is reached the response is truncated and invalid; keep internal reasoning minimal '
    'and output the required single JSON object completely. ')
RESPONSE_REVIEW_VERSION = 'boi/process-response-review@9'
SUPPORTED_RESPONSE_REVIEW_VERSIONS = ('boi/process-response-review@3', 'boi/process-response-review@4', 'boi/process-response-review@5', 'boi/process-response-review@6', 'boi/process-response-review@7', 'boi/process-response-review@8', RESPONSE_REVIEW_VERSION)


def recorded_provider_failure(output_dir, error):
    """Keep a provider's recorded failure distinct from an implementation error."""
    from boi_api.app.governed_runtime.source_envelope import byte_digest
    root=Path(output_dir);path=root/'run.json'
    if not isinstance(error,ValueError) or not path.is_file():raise error
    run=json.loads(path.read_text())
    if run.get('status')=='completed' or str(error)!='STRUCTURED_PROVIDER_'+str(run.get('status')).upper():raise error
    if any(byte_digest((root/name).read_bytes())!=run.get(key) for name,key in
            (('prompt.txt','prompt_digest'),('schema.json','schema_digest'))):raise error
    return run


def response_context_view(context, *, source_readings=None):
    """Read definitions/contracts without nesting old answers or assessments.

    The full Wiki read and original revisions remain recorded by the caller.
    Current answer targets/citations and selected unchanged judgments are the
    only answer/review representations sent to this operational assessor.
    """
    from agent_kit.python.boi_process_claim_review import process_context_view
    view=process_context_view(context,source_readings=source_readings)
    for asset in view['assets']:
        content=asset['read_projection']
        historical=content.get('contract_version') in (
            'boi/process-user-result@1','boi/process-user-result@2','boi/process-user-result@3')
        historical_review=asset['kind']=='pack' and 'check' in content and any(
            key in content for key in ('assessment','source_assessment'))
        native_history=source_readings is not None and asset['kind']=='pack' and content.get('contract_version') in (
            'boi/native-agent-observation@1','boi/native-agent-failure@1',
            'boi/native-source-answer-delivery@1','boi/native-source-answer-delivery@2',
            'boi/native-answer-delivery@1','boi/native-answer-delivery@2')
        if historical or historical_review or native_history:
            projection={'omitted_from_current_review':'historical_answer_or_assessment',
                'history_preserved_in_exact_wiki_revision':True}
            if historical_review:
                projection['operative_review_check']=content['check']
            asset.update(read_projection=projection,projection_digest=semantic_digest(projection))
    view['contract_version']='boi/process-response-read-presentation@2'
    view['historical_answer_assessments_omitted']=True
    return view


def response_material(*, answers, context, sources, questions):
    # The compatibility checker calls these parameters oracle/source_oracle.
    # They contain ONLY the incoming user request, never an evaluation key.
    requirements = {'questions': [{'id': q['id'], 'required_propositions': [],
        'boundaries': [{'id': 'requested_information', 'text': q['question']+
            ('\nLatest response request: '+q['response_request'] if q.get('response_request') else '')}]} for q in questions]}
    material = verified_answer_material(answers=answers, context=context, sources=sources,
        questions=questions, oracle=requirements, source_oracle={'records': []})
    material['requirements_origin'] = 'original_user_questions_only'
    return material


def response_check(assessment, *, material, version=RESPONSE_REVIEW_VERSION):
    value = AnswerAssessmentV2.model_validate(assessment)
    checked = check_answer_assessment_v2(legacy_assessment(value), material=material)
    failures = []
    for statement in value.statements:
        if statement.support_relation != 'supported' or statement.citation_support != 'full':
            failures.append({'target_pointer': statement.target_pointer,
                'failure_kind': 'source_conflict' if statement.support_relation == 'contradicted' else
                    'unestablished_meaning' if statement.support_relation == 'unsupported' else 'incomplete_citation',
                'support_relation': statement.support_relation, 'citation_support': statement.citation_support,
                'reason': statement.reason, 'evidence_ids': list(statement.evidence_ids)})
    requirements = {r['requirement_id']: r for r in material['requirements']}
    missing = []
    for requirement in value.requirements:
        if requirement.status != 'covered':
            missing.append({'question_id': requirements[requirement.requirement_id]['question_id'],
                'requirement_id': requirement.requirement_id, 'status': requirement.status,
                'target_pointers': list(requirement.target_pointers), 'reason': requirement.reason})
    if version not in SUPPORTED_RESPONSE_REVIEW_VERSIONS:raise ValueError('UNKNOWN_RESPONSE_REVIEW_VERSION')
    if version!=RESPONSE_REVIEW_VERSION:
        return {**checked, 'failures':failures, 'unanswered_requests':missing,
            'operational_review':True, 'scientific_source_correction':'requires_separate_evidence'}
    alignment_failures=record_alignment_failures(value,material)
    failures.extend(alignment_failures)
    if alignment_failures:checked['model_assessment_accepts_answers']=False
    scope_available=all(e.get('record_locator') for e in material['evidence_catalog'] if e['kind']=='source_field')
    return {**checked, 'record_scope_identity_complete':scope_available,
        'record_alignment_complete':not alignment_failures and scope_available,
        'record_relation_semantically_verified':False, 'failures': failures, 'unanswered_requests': missing,
        'operational_review': True, 'scientific_source_correction': 'requires_separate_evidence'}


def response_proposal(bound):
    from .boi_process_answer_v2 import request_plan_proposal,WikiStateCitation,AssetStateCitation,ExecutionResultCitation
    kinds = {'meaning': MeaningCitation, 'source_quote': SourceCitation, 'source_scope': SourceScopeCitation,
        'wiki_state':WikiStateCitation,'asset_state':AssetStateCitation,'execution_result':ExecutionResultCitation}
    def statement(value):
        return {'kind': value['kind'], 'text': value['text'],
            **({'basis_statement_pointers':value['basis_statement_pointers']} if 'basis_statement_pointers' in value else {}), 'citations': [
            {k: v for k, v in c.items() if k in kinds[c['kind']].model_fields} for c in value['citations']]}
    return {'contract_version': 'boi/source-explanation-proposal@1', 'context_digest': bound['context_digest'],
        'answers': [{'question_id': a['question_id'],
            **({'request_plan':request_plan_proposal(a['request_plan'])} if a.get('request_plan') else {}),
            **({'layout':a['layout']} if 'layout' in a else {}),
            'sentences': [statement(s) for s in a['sentences']],
            'limitations': [statement(s) for s in a['limitations']]} for a in bound['answers']]}


def unchanged_answer_disagreement(packet,answer,review):
    """Label disagreement is an unresolved observation, not a semantic verdict.

    Used only for explicit same-source/definition saved-answer revalidation.
    Changed answers or review contracts are assessed on their own evidence.
    """
    prior=packet.get('response_review',{})
    if (prior.get('review_contract_version')!=review.get('review_contract_version')
            or response_proposal(packet['answer'])['answers']!=response_proposal(answer)['answers']
            or not prior.get('attempts') or not review.get('attempts')):return []
    before=prior['attempts'][-1];after=review['attempts'][-1]
    if not before.get('check',{}).get('assessment_complete') or not after.get('check',{}).get('assessment_complete'):
        return []
    old={s['target_pointer']:s for s in before['review']['statements']}
    disagreements=[{'target_pointer':s['target_pointer'],'prior_judgment':old[s['target_pointer']],
        'new_judgment':s,'reason':'Unchanged answer and review contract received different model judgments.'}
        for s in after['review']['statements'] if s['target_pointer'] in old and any(
            s[k]!=old[s['target_pointer']][k] for k in ('support_relation','citation_support'))]
    prior_requirements={r['requirement_id']:r for r in before['review']['requirements']}
    disagreements.extend({'requirement_id':r['requirement_id'],'target_pointers':r['target_pointers'],
        'prior_judgment':prior_requirements[r['requirement_id']],'new_judgment':r,
        'reason':'Unchanged answer and review contract received different question-coverage judgments.'}
        for r in after['review']['requirements'] if r['requirement_id'] in prior_requirements
        and r['status']!=prior_requirements[r['requirement_id']]['status'])
    return disagreements


class StatementRepair(FrozenContract):
    target_pointer: Ref
    replacement: Annotated[SourceStatement | GapStatement, Field(discriminator='kind')]


class AnswerAddition(FrozenContract):
    question_id: Ref
    location: Literal['sentences', 'limitations']
    statement: Annotated[SourceStatement | GapStatement, Field(discriminator='kind')]


class AnswerRepairGap(FrozenContract):
    target_pointer: Ref
    reason: Ref
    needed_evidence: Ref


class QualityAnswerReplacement(FrozenContract):
    # Same writer contract, scoped to a question with a mandatory quality issue.
    question_id: Ref
    sentences: tuple[Annotated[SourceStatement | GapStatement, Field(discriminator='kind')], ...] = Field(min_length=1)
    limitations: tuple[Annotated[SourceStatement | GapStatement, Field(discriminator='kind')], ...] = ()
    layout: AnswerLayout | None = Field(default=None,exclude_if=lambda v:v is None)
    request_plan: RequestPlan | None = Field(default=None,exclude_if=lambda v:v is None,
        description='When replacing an answer that has a request plan, supply its source-bound facets mapped to the replacement statements. The existing binder checks these references again.')


class ResponseRepair(FrozenContract):
    context_digest: Digest
    base_proposal_digest: Digest
    replacements: tuple[StatementRepair, ...] = ()
    additions: tuple[AnswerAddition, ...] = ()
    unresolved: tuple[AnswerRepairGap, ...] = ()
    quality_answers: tuple[QualityAnswerReplacement, ...] = ()


class FacetRepair(FrozenContract):
    target_pointer: Ref
    replacement: RequestFacet


class ScopedResponseRepair(ResponseRepair):
    facet_replacements: tuple[FacetRepair, ...] = ()


def response_repair_schema(*, version='boi/process-response-repair-presentation@6'):
    # Old receipt schemas remain byte-equivalent to their original contract.
    contract = ScopedResponseRepair if version=='boi/process-response-repair-presentation@6' else ResponseRepair
    return contract.model_json_schema()


def dependent_repair_facets(proposal, check):
    failed={f['target_pointer'] for f in check['failures']}
    return {f'/answers/{ai}/request_plan/facets/{fi}':(ai,fi,facet)
        for ai,answer in enumerate(proposal['answers'])
        for fi,facet in enumerate((answer.get('request_plan') or {}).get('facets',[]))
        if any(f'/answers/{ai}'+pointer in failed for pointer in facet['statement_pointers'])}


def apply_response_repair(proposal, patch, *, check, version='boi/process-response-repair-presentation@6'):
    """Only failed statements and questions with missing information may change."""
    from agent_kit.python.boi_process_user_result import SourceExplanation
    contract = ScopedResponseRepair if version=='boi/process-response-repair-presentation@6' else ResponseRepair
    patch = contract.model_validate(patch)
    if patch.context_digest != proposal['context_digest'] or patch.base_proposal_digest != semantic_digest(proposal):
        raise ValueError('PROCESS_RESPONSE_REPAIR_BASE_MISMATCH')
    failed = {f['target_pointer'] for f in check['failures']}
    missing = {r['question_id'] for r in check['unanswered_requests']}
    if version in ('boi/process-response-repair-presentation@3','boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5','boi/process-response-repair-presentation@6'):
        missing.update(r['question_id'] for r in check.get('quality_failures',[]))
    lookup = {f'/answers/{ai}/{location}/{si}': (ai, location, si)
        for ai, answer in enumerate(proposal['answers']) for location in ('sentences', 'limitations')
        for si, _ in enumerate(answer[location])}
    result = copy.deepcopy(proposal); changed = set(); seen = set()
    for repair in patch.replacements:
        pointer = repair.target_pointer
        if pointer in seen or pointer not in failed or pointer not in lookup:
            raise ValueError('PROCESS_RESPONSE_REPAIR_UNRELATED_STATEMENT')
        seen.add(pointer); ai, location, si = lookup[pointer]
        result['answers'][ai][location][si] = repair.replacement.model_dump(mode='json')
        changed.add(pointer)
    answers = {a['question_id']: (i, a) for i, a in enumerate(result['answers'])}
    for addition in patch.additions:
        if addition.question_id not in missing or addition.question_id not in answers:
            raise ValueError('PROCESS_RESPONSE_REPAIR_UNRELATED_QUESTION')
        ai, answer = answers[addition.question_id]
        pointer=f'/{addition.location}/{len(answer[addition.location])}'
        changed.add(f'/answers/{ai}'+pointer)
        answer[addition.location].append(addition.statement.model_dump(mode='json'))
        if version in ('boi/process-response-repair-presentation@3','boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5','boi/process-response-repair-presentation@6') and answer.get('layout'):
            # Proposed layout, before both independent reviews; never a
            # post-review display insertion or a new unreviewed explanation.
            answer['layout'].append({'kind':'paragraph','statements':[pointer]})
    quality_questions={f['question_id'] for f in check.get('quality_failures',[])}
    replaced=set()
    for replacement in patch.quality_answers:
        q=replacement.question_id
        if q not in quality_questions or q not in answers or q in replaced:
            raise ValueError('PROCESS_RESPONSE_REPAIR_UNRELATED_QUALITY_QUESTION')
        ai,_=answers[q]
        if (version in ('boi/process-response-repair-presentation@5','boi/process-response-repair-presentation@6')
                and proposal['answers'][ai].get('request_plan') and replacement.request_plan is None):
            raise ValueError('PROCESS_RESPONSE_REPAIR_REQUEST_PLAN_REQUIRED')
        if any(ptr.startswith(f'/answers/{ai}/') for ptr in changed):
            raise ValueError('PROCESS_RESPONSE_REPAIR_OVERLAPPING_PATCH')
        result['answers'][ai]=replacement.model_dump(mode='json');replaced.add(q)
        changed.add(f'/answers/{ai}')
    changed_facets=set()
    eligible=dependent_repair_facets(proposal,check)
    for repair in getattr(patch,'facet_replacements',()):
        pointer=repair.target_pointer
        if pointer in changed_facets or pointer not in eligible:
            raise ValueError('PROCESS_RESPONSE_REPAIR_UNRELATED_FACET')
        ai,fi,original=eligible[pointer]
        if proposal['answers'][ai]['question_id'] in replaced:
            raise ValueError('PROCESS_RESPONSE_REPAIR_OVERLAPPING_FACET')
        replacement=repair.replacement.model_dump(mode='json')
        # Interpretations/evidence may change; the original request and linkage
        # cannot be rewritten to turn a different question into a passing one.
        if any(replacement[key]!=original[key] for key in ('aspect','request_quote','statement_pointers')):
            raise ValueError('PROCESS_RESPONSE_REPAIR_FACET_SCOPE_CHANGED')
        result['answers'][ai]['request_plan']['facets'][fi]=replacement
        changed_facets.add(pointer)
    unresolved_allowed = {f'/answers/{answers[q][0]}' for q in quality_questions} | failed | {r['requirement_id'] for r in check['unanswered_requests']}
    if version=='boi/process-response-repair-presentation@6':unresolved_allowed.update(eligible)
    if any(item.target_pointer not in unresolved_allowed for item in patch.unresolved):
        raise ValueError('PROCESS_RESPONSE_REPAIR_UNKNOWN_FAILURE')
    return SourceExplanation.model_validate(result).model_dump(mode='json'), {
        'changed_statements': sorted(changed), **({'changed_facets':sorted(changed_facets)} if changed_facets else {}), 'unresolved': [u.model_dump(mode='json') for u in patch.unresolved]}


def rebase_recorded_patch(patch,old_proposal,current_proposal):
    """Reuse exact admitted repair content; only refresh its binding envelope."""
    if (patch['context_digest']!=old_proposal['context_digest']
            or patch['base_proposal_digest']!=semantic_digest(old_proposal)
            or old_proposal['answers']!=current_proposal['answers']):
        raise ValueError('PROCESS_RECORDED_PATCH_ANSWER_CHANGED')
    return {**copy.deepcopy(patch),'context_digest':current_proposal['context_digest'],
        'base_proposal_digest':semantic_digest(current_proposal)}


def response_review_selection(material, *, previous_material=None, previous_assessment=None):
    if previous_material is None:
        return {'targets': material['targets'], 'requirements': material['requirements'],
            'carry_forward_statements': [], 'carry_forward_requirements': []}
    prior = {t['target_pointer']: t for t in previous_material['targets']}
    judgments = {s['target_pointer']: s for s in previous_assessment['statements']}
    # The same sentence/citation may answer a different relation, negation or
    # time after a request/facet revision. Reuse the review's existing exact
    # request links as dependencies; do not infer equivalence from keywords.
    prior_links = {v['target_pointer']: v for v in request_claim_links(previous_material)}
    current_links = {v['target_pointer']: v for v in request_claim_links(material)}
    selected = [t for t in material['targets'] if t['target_pointer'] not in prior or
        prior_links.get(t['target_pointer']) != current_links[t['target_pointer']] or
        semantic_digest(t) != semantic_digest(prior[t['target_pointer']]) or
        judgments[t['target_pointer']]['support_relation'] != 'supported' or
        judgments[t['target_pointer']]['citation_support'] != 'full']
    current_pointers={t['target_pointer'] for t in material['targets']}
    questions = {t['question_id'] for t in selected} | {t['question_id'] for p,t in prior.items() if p not in current_pointers}
    old_layouts={a['question_id']:a.get('layout') for a in previous_material.get('answer_layouts',[])}
    new_layouts={a['question_id']:a.get('layout') for a in material.get('answer_layouts',[])}
    questions.update(q for q in old_layouts.keys()|new_layouts.keys() if old_layouts.get(q)!=new_layouts.get(q))
    old_plans={a['question_id']:a['plan'] for a in previous_material.get('request_plans',[])}
    new_plans={a['question_id']:a['plan'] for a in material.get('request_plans',[])}
    questions.update(q for q in old_plans.keys()|new_plans.keys() if old_plans.get(q)!=new_plans.get(q))
    prior_requirements = {r['requirement_id']: r for r in previous_assessment['requirements']}
    prior_requirement_material={r['requirement_id']:r for r in previous_material['requirements']}
    current_requirement_ids={r['requirement_id'] for r in material['requirements']}
    requirements = [r for r in material['requirements'] if r['question_id'] in questions or
        prior_requirement_material.get(r['requirement_id'])!=r or
        prior_requirements.get(r['requirement_id'],{}).get('status') != 'covered']
    pointers = {t['target_pointer'] for t in selected}; ids = {r['requirement_id'] for r in requirements}
    return {'targets': selected, 'requirements': requirements,
        'carry_forward_statements': [s for s in previous_assessment['statements'] if s['target_pointer'] not in pointers and s['target_pointer'] in current_pointers],
        'carry_forward_requirements': [r for r in previous_assessment['requirements']
            if r['requirement_id'] not in ids and r['requirement_id'] in current_requirement_ids]}


def merge_response_review(assessment, *, selection):
    value = AnswerAssessmentV2.model_validate(assessment).model_dump(mode='json',exclude_none=True)
    def exact(actual, expected):
        return len(actual) == len(set(actual)) and set(actual) == set(expected)
    if not exact([s['target_pointer'] for s in value['statements']], [t['target_pointer'] for t in selection['targets']]) or not exact(
        [r['requirement_id'] for r in value['requirements']], [r['requirement_id'] for r in selection['requirements']]):
        raise ValueError('PROCESS_RESPONSE_REVIEW_SELECTED_SET_MISMATCH')
    value['statements'] += selection['carry_forward_statements']
    value['requirements'] += selection['carry_forward_requirements']
    return value


RESPONSE_ASSESSMENT_SCHEMA_VERSION='boi/process-response-assessment-schema@4'


def response_review_schema(*, selection, material, version=RESPONSE_REVIEW_VERSION):
    """Constrain transport references to this read request, not its answer key.

    Grounding graph nodes are evidence, not additional answer statements.
    The normal integrity checker still requires exact coverage after decoding.
    """
    if version not in SUPPORTED_RESPONSE_REVIEW_VERSIONS:raise ValueError('UNKNOWN_RESPONSE_REVIEW_VERSION')
    schema = (AnswerAssessmentV2 if version==RESPONSE_REVIEW_VERSION else LegacyAssessment).model_json_schema()
    pointers = [t['target_pointer'] for t in selection['targets']]
    requirements = [r['requirement_id'] for r in selection['requirements']]
    for name, values, definition, field in (
        ('statements', pointers, 'StatementAssessment', 'target_pointer'),
        ('requirements', requirements, 'RequirementAssessment', 'requirement_id')):
        schema['properties'][name].update(minItems=len(values), maxItems=len(values))
        if values: schema['$defs'][definition]['properties'][field]['enum'] = values
    all_pointers = [t['target_pointer'] for t in material['targets']]
    if all_pointers:
        schema['$defs']['RequirementAssessment']['properties']['target_pointers']['items']['enum'] = all_pointers
    evidence_ids=[item['evidence_id'] for item in material['evidence_catalog']]
    if evidence_ids:
        schema['$defs']['StatementAssessment']['properties']['evidence_ids']['items']['enum']=evidence_ids
    # Encode the existing evidence-domain integrity rule, not a support verdict.
    # Negative/partial assessments can still cite mixed domains diagnostically.
    branches=[]
    base=schema['$defs']['StatementAssessment']
    def branch(targets,relations,citations,ids):
        if not targets or not ids:return
        item=copy.deepcopy(base)
        for key,values in [('target_pointer',targets),('support_relation',relations),('citation_support',citations)]:
            item['properties'][key]['enum']=values
        item['properties']['evidence_ids']['items']['enum']=ids
        branches.append(item)
    source_pointers=[t['target_pointer'] for t in selection['targets'] if t['kind']!='runtime_state']
    runtime_pointers=[t['target_pointer'] for t in selection['targets'] if t['kind']=='runtime_state']
    branch(source_pointers,['supported'],['full'],[e['evidence_id'] for e in material['evidence_catalog'] if e['kind']=='source_field'])
    branch(runtime_pointers,['supported'],['full'],[e['evidence_id'] for e in material['evidence_catalog'] if e['kind'] in ('wiki_state','asset_state','execution_result')])
    branch(pointers,['contradicted','unsupported'],['full','partial','none'],evidence_ids)
    branch(pointers,['supported'],['partial','none'],evidence_ids)
    if branches:schema['properties']['statements']['items']={'anyOf':branches}
    return schema


RESPONSE_PRESENTATION_VERSION='boi/process-response-review-presentation@9'


def response_prompt_context(context,*,presentation_version=RESPONSE_PRESENTATION_VERSION,uses_meaning=True,projection_root="/read_definitions_and_contracts"):
    """Preserve read domain meaning; link repeated or operational-only records."""
    if presentation_version not in ('boi/process-response-review-presentation@3','boi/process-response-review-presentation@4','boi/process-response-review-presentation@5','boi/process-response-review-presentation@6','boi/process-response-review-presentation@7','boi/process-response-review-presentation@8',RESPONSE_PRESENTATION_VERSION):
        raise ValueError('UNKNOWN_RESPONSE_PRESENTATION_VERSION')
    read_context=response_context_view(context)
    if presentation_version!='boi/process-response-review-presentation@3':
        seen={}
        for index,asset in enumerate(read_context['assets']):
            if asset['kind'] not in ('definition','profile') or (presentation_version in ('boi/process-response-review-presentation@5','boi/process-response-review-presentation@6','boi/process-response-review-presentation@7','boi/process-response-review-presentation@8',RESPONSE_PRESENTATION_VERSION) and not uses_meaning):
                projection={'operational_record_in_exact_revision':True,
                    'review_scope':'Original sources, all read domain definitions and profiles, current answer, question and the explicit review contract in this prompt.'}
                if presentation_version in ('boi/process-response-review-presentation@5','boi/process-response-review-presentation@6','boi/process-response-review-presentation@7','boi/process-response-review-presentation@8',RESPONSE_PRESENTATION_VERSION) and not uses_meaning:
                    projection['review_scope']='No meaning citations in the answer. Full source evidence and all answer statements remain in the review material; unused definitions are retained in the exact authorized reading.'
                asset.update(read_projection=projection,projection_digest=semantic_digest(projection))
            else:
                projection=asset['read_projection'];digest=semantic_digest(projection)
                if digest in seen:
                    prior,original=seen[digest]
                    if original!=projection:raise ValueError('RESPONSE_PROJECTION_DIGEST_COLLISION')
                    projection={'identical_read_projection_reference':f'{projection_root}/assets/{prior}/read_projection',
                        'referenced_projection_digest':digest}
                    asset.update(read_projection=projection,projection_digest=semantic_digest(projection))
                else:seen[digest]=(index,projection)
    return read_context


def _select_process_meaning_projection(read_context,evidence):
    """Reuse already bound dependency graphs; retain every original source field.

    This selects by exact typed references, never by wording or relevance guesses.
    Unknown definition formats remain whole. Selected values are checked against
    the read candidate, whose correctness still requires independent raw evidence.
    """
    from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
    nodes={}
    for target in evidence:
        for citation in target['citations']:
            if citation['kind']!='meaning':continue
            for node in citation.get('graph_evidence',[]):
                revision=node.get('asset_revision',citation['asset_revision'])
                nodes.setdefault(semantic_digest(revision),[]).append(node)
    for asset in read_context['assets']:
        projection=asset['read_projection']
        selected=nodes.get(semantic_digest(asset.get('revision')))
        if (asset['kind']!='definition' or not selected
                or not isinstance(projection.get('draft'),dict)
                or projection['draft'].get('contract_version')!='boi/process-meaning@1'):continue
        draft=ProcessKnowledgeDraft.model_validate(projection['draft']).model_dump(mode='json')
        originals={f'/records/{ri}/{kind}/{i}':node for ri,record in enumerate(draft['records'])
            for kind in ('terms','assertions') for i,node in enumerate(record[kind])}
        unique={}
        for node in selected:
            pointer=node['target_pointer']
            if originals.get(pointer)!=node['value']:
                raise ValueError('RESPONSE_MEANING_GRAPH_VALUE_MISMATCH')
            unique[pointer]={'target_pointer':pointer,'value':copy.deepcopy(node['value'])}
        projection={k:copy.deepcopy(v) for k,v in projection.items() if k!='draft'}
        projection.update(draft_metadata={k:v for k,v in draft.items() if k!='records'},
            selected_meaning_nodes=list(unique.values()),
            selected_record_metadata=[{'record_pointer':f'/records/{ri}',
                **{k:v for k,v in record.items() if k not in ('terms','assertions')}}
                for ri,record in enumerate(draft['records']) if any(p.startswith(f'/records/{ri}/') for p in unique)],
            review_scope='selected_meaning_dependencies_not_whole_ontology',
            omitted_nodes_in_exact_revision=True,
            source_comparison='All raw source fields remain in evidence_catalog. Graph roles and qualifier bindings remain in current statement/plan citations. Candidate meaning is not source truth.')
        asset.update(read_projection=projection,projection_digest=semantic_digest(projection))


def response_prompt_material(material,selection,context,*,presentation_version=RESPONSE_PRESENTATION_VERSION):
    evidence=[*material['targets'],*[f for p in material.get('request_plans',[]) for f in p['plan']['facets']]]
    uses_meaning=any(c['kind']=='meaning' for t in evidence for c in t['citations'])
    read_context=response_prompt_context(context,presentation_version=presentation_version,uses_meaning=uses_meaning)
    if presentation_version in ('boi/process-response-review-presentation@8',RESPONSE_PRESENTATION_VERSION):
        read_context = copy.deepcopy(read_context)
        for asset in read_context['assets']:
            if asset['kind'] != 'profile':
                continue
            projection = asset['read_projection']
            removed = {key: projection[key] for key in ('meaning_schema', 'definition_node_schema') if key in projection}
            if removed:
                projection = {key: value for key, value in projection.items() if key not in removed}
                projection['schema_definitions_in_exact_revision'] = {
                    key: semantic_digest(value) for key, value in removed.items()
                }
                asset.update(read_projection=projection, projection_digest=semantic_digest(projection))
        if presentation_version==RESPONSE_PRESENTATION_VERSION:
            _select_process_meaning_projection(read_context,evidence)
        # Shared profile projections refer to the current projection, whose
        # digest changes when schema-only payload is moved out of the review.
        for asset in read_context['assets']:
            projection = asset['read_projection']
            reference = projection.get('identical_read_projection_reference')
            if reference:
                original = read_context
                for part in reference.removeprefix('/read_definitions_and_contracts/').split('/'):
                    original = original[int(part)] if isinstance(original, list) else original[part]
                projection['referenced_projection_digest'] = semantic_digest(original)
                asset['projection_digest'] = semantic_digest(projection)
    result={**material,'presentation_contract_version':presentation_version,
        'targets':[{'target_pointer':t['target_pointer']} for t in selection['targets']],
        'requirements':selection['requirements'],
        'all_current_statements_for_question_coverage':material['targets'],
        'unchanged_judgments':selection['carry_forward_statements'],
        'read_definitions_and_contracts':read_context}
    return result


def _compact_response_bindings(result):
    # Repeated exact EvidenceSpan bindings are transport duplication, not
    # separate evidence. The first full object and all quotes remain here.
    seen={}
    def visit(value,path):
        if isinstance(value,dict):
            if 'span_ref' in value and 'quote_digest' in value and 'offset_basis' in value:
                digest=semantic_digest(value)
                if digest in seen:
                    prior,original=seen[digest]
                    if original!=value:raise ValueError('RESPONSE_BINDING_DIGEST_COLLISION')
                    return {'identical_source_binding_reference':prior,'referenced_binding_digest':digest}
                seen[digest]=(path,value)
            return {k:visit(v,path+'/'+k.replace('~','~0').replace('/','~1')) for k,v in value.items()}
        if isinstance(value,list):return [visit(v,path+'/'+str(i)) for i,v in enumerate(value)]
        return value
    result=visit(result,'')
    return result


def _shared_response_values(material):
    """Lossless in-input sharing; all values and evidence identities stay present.

    The input's existing digest binds the entire material. Pool entries add no
    authority or evidence and do not select an answer or supporting relation.
    """
    from collections import Counter
    counts=Counter(); originals={}
    def scan(value):
        if isinstance(value,(dict,list)):
            encoded=json.dumps(value,ensure_ascii=False,separators=(',',':'))
            if len(encoded)>128:
                digest=semantic_digest(value)
                if digest in originals and originals[digest]!=value:
                    raise ValueError('RESPONSE_VALUE_DIGEST_COLLISION')
                originals[digest]=value;counts[digest]+=1
        if isinstance(value,dict):
            for child in value.values():scan(child)
        elif isinstance(value,list):
            for child in value:scan(child)
    scan(material);catalog=[];indices={}
    def encode(value):
        digest=semantic_digest(value) if isinstance(value,(dict,list)) else None
        if counts[digest]>1 and digest in indices:return {'review_value_ref':indices[digest]}
        result=({key:encode(child) for key,child in value.items()} if isinstance(value,dict)
            else [encode(child) for child in value] if isinstance(value,list) else value)
        if counts[digest]>1:
            indices[digest]=len(catalog);catalog.append(result)
            return {'review_value_ref':indices[digest]}
        return result
    result=encode(material)
    result['review_value_catalog']=catalog
    return result


def request_claim_links(material):
    """Expose exact request-to-sentence links without deciding semantic equality.

    A plan is the writer's interpretation, not evidence that its relation is
    correct. Reviewers must compare it with the original question and sources.
    """
    if not material['targets']:return []
    questions={q['id']:q for q in material['questions']}
    plans={p['question_id']:p['plan']['facets'] for p in material.get('request_plans',[])}
    links=[]
    for target in material['targets']:
        question=questions[target['question_id']]
        local='/'+'/'.join(target['target_pointer'].split('/')[3:])
        links.append({'target_pointer':target['target_pointer'],
            'question':question['question'],
            **({'response_request':question['response_request']} if question.get('response_request') else {}),
            'facets':[copy.deepcopy(f) for f in plans.get(target['question_id'],[])
                if local in f['statement_pointers'] or target['target_pointer'] in f['statement_pointers']],
            'semantic_alignment':'requires_source_comparison'})
    return links


def source_record_scopes(material):
    """Expose supplied record boundaries, without deriving identity or applicability."""
    groups={}
    for field in material['evidence_catalog']:
        if field['kind']!='source_field':continue
        # Missing record identity stays field-scoped; never merge unknown records.
        locator=field.get('record_locator') or field.get('field_locator') or field['evidence_id']
        key=(field['source_revision_digest'],locator)
        if key not in groups:groups[key]={'source_revision_digest':key[0],
            'record_locator':locator,'evidence_ids':[]}
        groups[key]['evidence_ids'].append(field['evidence_id'])
    return list(groups.values())


def response_review_prompt(material, selection, context, *, version=RESPONSE_REVIEW_VERSION,presentation_version=RESPONSE_PRESENTATION_VERSION):
    """Exact operational review input, also used for Wiki receipt verification."""
    prompt_material = response_prompt_material(material, selection, context,presentation_version=presentation_version)
    if version in ('boi/process-response-review@6', 'boi/process-response-review@7', 'boi/process-response-review@8', RESPONSE_REVIEW_VERSION):
        prompt_material['claim_request_links']=request_claim_links(material)
    if version in ('boi/process-response-review@7', 'boi/process-response-review@8', RESPONSE_REVIEW_VERSION):
        prompt_material['source_record_scopes']=source_record_scopes(material)
    if presentation_version=='boi/process-response-review-presentation@6':prompt_material=_compact_response_bindings(prompt_material)
    elif presentation_version in ('boi/process-response-review-presentation@7','boi/process-response-review-presentation@8',RESPONSE_PRESENTATION_VERSION):prompt_material=_shared_response_values(prompt_material)
    if version not in SUPPORTED_RESPONSE_REVIEW_VERSIONS:raise ValueError('UNKNOWN_RESPONSE_REVIEW_VERSION')
    instructions=REVIEW_INSTRUCTIONS_V3 if version=='boi/process-response-review@3' else REVIEW_INSTRUCTIONS
    if version in ('boi/process-response-review@6', 'boi/process-response-review@7', 'boi/process-response-review@8', RESPONSE_REVIEW_VERSION):
        instructions+=(
            'Use claim_request_links to compare the original requested relation, the writer interpretation, '
            'the source relation and the final sentence. A shared target or broad predicate does not establish the requested relation. '
            'Compare subject, relation direction, scope, time, negation, conditions, numerical role and unit; '
            'do not promote evaluation to application, usage to introduction, source-present to actual current, '
            'or a partial search to a complete list. The request plan itself is not truth. '
            'Explain a relation mismatch in the affected statement judgment using actual source evidence; '
            'mark an unsupported overstatement unsupported even when citations exist. '
            'Keep supported answers to other parts; assess omitted requested information separately. '
            'These semantic judgments remain provisional, not deterministic entailment. ')
    if version in ('boi/process-response-review@7', 'boi/process-response-review@8', RESPONSE_REVIEW_VERSION):
        instructions+=(
            'Question coverage is covered only when its referenced answer statements are supported '
            'with full citation support; an unsupported answer mentioning the requested words does not '
            'establish covered information. Mark such coverage partial or missing as appropriate. '
            'Use source_record_scopes to distinguish records even inside the SAME document revision. '
            'In each multi-record statement reason, explicitly identify the different record subjects/scopes '
            'and quote the source passage establishing their claimed connection. If no such passage exists, '
            'say the connection is not established and mark the composite unsupported; individually matching '
            'clauses cannot substitute for this missing connection. '
            'For each statement using multiple source records, separate its factual clauses and identify '
            'the subject and applicability of the record supporting each clause. Before combining those '
            'clauses into one subject, role or process sequence, require source evidence for the connecting '
            'identity or relation within the claimed scope. Shared terminology, a shared document/revision '
            'or individually supported clauses do not establish that connection. A role, condition or '
            'ordering in one record cannot be transferred to another record without this evidence. '
            'When the connection is missing, mark only the affected composite statement unsupported and '
            'explain the missing link with evidence IDs; retain supported clauses scoped to their own records. '
            'Do not reject multi-source comparison or synthesis when the source-supported link exists, '
            'or when the answer explicitly keeps the records and their applicability separate. '
            'The user question may contain an unverified premise and is not evidence for a connection. ')
    if version in ('boi/process-response-review@8', RESPONSE_REVIEW_VERSION):
        instructions+=(
            'An interpretation label is not evidence of applicability. Apply the same source-support '
            'and record-link checks to interpretation and source_reported_fact statements. '
            'Distinguish a clearly hypothetical possibility from an assertion that a role or condition '
            'actually applies: the former must remain explicitly unestablished and cannot cover a '
            'request for established applicability; the latter requires source support for that link. '
            'Do not let an interpretation label, request facet, citation count or shared method supply '
            'the missing relation. State which passage supports the link, or identify the missing link '
            'and keep the affected applicability unconfirmed. ')
    if version==RESPONSE_REVIEW_VERSION:
        instructions+=(
            'For supported/full statements spanning multiple source records, provide record_alignment. '
            'Map every non-whitespace part of the answer, in order, through clauses containing exact answer_quote, '
            'evidence_id and source_quote. Include every cited record. Use separate only when the sentence '
            'actually keeps record subjects/applicability separate. Use connected when it asserts a shared '
            'subject, role, applicability or sequence; links must quote the source establishing that connection. '
            'If that link is absent, mark the composite unsupported and retain independent supported clauses. '
            'An interpretation label never supplies a link. Quotes and the alignment mode remain provisional '
            'semantic judgments: selecting unrelated real quotes or mislabeling a connected sentence separate '
            'is a review failure, even if the integrity checks pass. Do not reject legitimate separate comparison, '
            'source-supported synthesis or ordinary single-record answers. ')
    prompt = instructions + (
        'targets lists selected target_pointer references into all_current_statements_for_question_coverage, '
        'which contains each complete statement, conditions and citations once. Output judgments only for those selected '
        'targets and requirements. For question coverage read ALL current statements, including carried unchanged ones. '
        'A statement excluded from re-review is not missing answer content.\n')
    if presentation_version=='boi/process-response-review-presentation@6':
        prompt+='identical_source_binding_reference is a JSON pointer to the identical full EvidenceSpan binding in this input; follow it with its unchanged digest.\n'
    if presentation_version in ('boi/process-response-review-presentation@7','boi/process-response-review-presentation@8',RESPONSE_PRESENTATION_VERSION):
        prompt+='A sole review_value_ref member is an index into review_value_catalog in this same input. Recursively resolve it to the complete identical value. Catalog entries may refer only to earlier entries. This lossless sharing preserves every statement, quotation, graph role, condition, source identity, revision and EvidenceSpan; it does not add evidence.\n'
    if material.get('answer_layouts'):
        prompt+='The answer_layouts are part of the final reviewed answer. Resolve their statement pointers into the targets. Assess headings, table column associations, ordering and latest response_request under requested_information coverage; a misleading table/header or unmet requested format is not covered. All facts still require their own citations.\n'
    return prompt + json.dumps(prompt_material, ensure_ascii=False,**(
        {'separators':(',',':')} if presentation_version!='boi/process-response-review-presentation@3' else {}))


RESPONSE_REPAIR_PRESENTATION_VERSION='boi/process-response-repair-presentation@6'


def response_repair_prompt(proposal,check,sources,context,questions,*,attempt_number,max_repairs,presentation_version=RESPONSE_REPAIR_PRESENTATION_VERSION):
    instructions = (
        'Correct only the reported statement/citation failures and missing parts of the original user questions. '
        'Use only the supplied original fields, read definitions and answer. No evaluation key or outside knowledge. '
        'The existing statement and its original citations are in base_proposal. Add exact identity/scope evidence '
        'where needed; do not rewrite accepted unrelated statements or invent missing evidence. '
        'If a problem cannot be resolved, state the required evidence in unresolved. Wiki authority and '
        'verification status do not belong in source answer prose. '
        f'This is bounded repair attempt {attempt_number} of {max_repairs}.\n')
    if presentation_version in ('boi/process-response-repair-presentation@1','boi/process-response-repair-presentation@2','boi/process-response-repair-presentation@3','boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5',RESPONSE_REPAIR_PRESENTATION_VERSION):
        instructions+=('Respect the statement evidence kinds: source_reported_fact and interpretation use positive '
            'source/meaning citations; evidence_gap uses the complete source_scope. A mixed positive/gap statement '
            'cannot be repaired by quoting every field or provenance value as positive evidence of absence. '
            'Rephrase only the failed statement within its evidence kind. Preserve necessary qualifications; '
            'when an unchanged statement already states a qualification or gap, do not duplicate it in the failed '
            'statement. Use unresolved if the allowed patch cannot preserve the requested information. '
            'Choose the precise supporting passage; titles and metadata are not substitutes for claim evidence.\n')
        context_presentation='boi/process-response-review-presentation@4'
    else:context_presentation=presentation_version
    if presentation_version in ('boi/process-response-repair-presentation@2','boi/process-response-repair-presentation@3','boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5',RESPONSE_REPAIR_PRESENTATION_VERSION):
        instructions+=('Assess each quality failure at its reported output location, reason and user impact. '
            'quality_answers may replace the complete answer only for a question with a mandatory quality failure; '
            'use that path for ordering, paragraph/list/table changes or repetition that a statement patch cannot fix. '
            'Preserve the supported meaning, conditions, uncertainty, and exact evidence; use short independently '
            'readable table labels and cells and place necessary longer explanation in prose. Do not force a table '
            'for every comparison. Do not combine a whole-answer replacement with statement patches for that question. '
            'All changed content and structure will undergo independent source and quality re-review. '
            'Optional editorial preferences do not authorize a repair or an extra call.\n')
    if presentation_version in ('boi/process-response-repair-presentation@3','boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5',RESPONSE_REPAIR_PRESENTATION_VERSION):
        instructions+=('A mandatory quality failure also authorizes an addition to its affected question, for example a missing necessary condition. Use the smallest sufficient patch; a full-answer replacement is needed only for structure or broader wording changes. Source-stated applicability restrictions remain answer evidence even when stored in a provenance field; distinguish them from runtime authority or identifiers.\n')
    current=presentation_version in ('boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5',RESPONSE_REPAIR_PRESENTATION_VERSION)
    uses_meaning=any(c['kind']=='meaning' for answer in proposal['answers'] for location in ('sentences','limitations') for statement in answer[location] for c in statement['citations'])
    if presentation_version in ('boi/process-response-repair-presentation@5',RESPONSE_REPAIR_PRESENTATION_VERSION):
        uses_meaning=uses_meaning or any(c['kind']=='meaning' for answer in proposal['answers']
            for facet in (answer.get('request_plan') or {}).get('facets',[]) for c in facet['citations'])
    if presentation_version==RESPONSE_REPAIR_PRESENTATION_VERSION:
        instructions+=('Repair a failed statement and its affected request facets together when the failure changes their interpretation. '
            'facet_replacements may change only facets listed in repairable_request_facets. Keep their aspect, exact request_quote '
            'and statement_pointers unchanged; correct interpretation, citations and unresolved_reason using the original sources. '
            'A label such as interpretation does not establish applicability across records. Preserve supported independent statements '
            'and facets. Return unresolved for a dependent facet that cannot be repaired within this contract. '
            'All changed facets and linked statements require re-review; this patch is not acceptance.\n')
    material={'base_proposal':proposal,
        **({'quality_failures':check.get('quality_failures',[])} if presentation_version in ('boi/process-response-repair-presentation@2','boi/process-response-repair-presentation@3','boi/process-response-repair-presentation@4','boi/process-response-repair-presentation@5',RESPONSE_REPAIR_PRESENTATION_VERSION) else {}),
        'base_proposal_digest':semantic_digest(proposal),'context_digest':proposal['context_digest'],
        'failures':check['failures'],'unanswered_requests':check['unanswered_requests'],
        'original_sources':sources,'read_definitions_and_contracts':response_prompt_context(context,
            presentation_version='boi/process-response-review-presentation@6' if current else context_presentation,
            uses_meaning=uses_meaning if current else True),
        'questions':questions}
    if presentation_version==RESPONSE_REPAIR_PRESENTATION_VERSION:
        material['repairable_request_facets']=list(dependent_repair_facets(proposal,check))
    if current:
        material=_compact_response_bindings(material)
        instructions+='identical_source_binding_reference points to the identical full EvidenceSpan binding in this input; follow it with its unchanged digest. Unused definitions remain in the exact authorized reading.\n'
    return instructions + json.dumps(material,ensure_ascii=False,**({'separators':(',',':')} if presentation_version!='boi/process-response-review-presentation@3' else {}))


COMBINED_REVIEW_VERSION='boi/process-combined-response-review@1'


def combined_response_review_input(material, selection, context, quality_scope):
    """One source inventory; preserve both existing rubrics and checker schemas."""
    from .boi_process_explanation_quality import ExplanationQuality,quality_prompt,quality_material
    prompt_selection=copy.deepcopy(selection)
    prompt_selection['carry_forward_statements']=[]
    source_prompt=response_review_prompt(material,prompt_selection,context)
    instructions,source_json=source_prompt.rsplit('\n',1)
    quality_text=quality_prompt(quality_material(material,quality_scope))
    quality_instructions,quality_json=quality_text.rsplit('\n',1)
    quality_payload=json.loads(quality_json)
    pool=quality_payload.pop('review_value_catalog',[])
    expanded=[]
    def expand(value):
        if isinstance(value,dict):
            if set(value)=={'review_value_ref'}:return copy.deepcopy(expanded[value['review_value_ref']])
            return {k:expand(v) for k,v in value.items()}
        if isinstance(value,list):return [expand(v) for v in value]
        return value
    for entry in pool:expanded.append(expand(entry))
    quality_payload=expand(quality_payload)
    # These are the SAME verified objects, not a separately shortened source set.
    quality_payload.pop('material')
    # Preserve the quality view's exact prose/evidence numbering. Replace only
    # duplicate citation objects with explicit addresses in the shared targets.
    targets={t['target_pointer']:t for t in material['targets']}
    for answer in quality_payload['rendered_answers']:
        for evidence in answer.get('attached_evidence',[]):
            pointer=evidence['statement_pointer']
            citation=evidence.pop('citation')
            evidence['citation_from_source_target']={'target_pointer':pointer,
                'citation_index':targets[pointer]['citations'].index(citation)}
    quality_payload['question_ids']=quality_scope['question_ids']
    source_payload=json.loads(source_json)
    source_payload.pop('unchanged_judgments',None)
    payload={'contract_version':COMBINED_REVIEW_VERSION,'source_review_material':source_payload,
        'quality_view':quality_payload,
        'shared_evidence':'Quality uses the same questions, current statements, exact citations, original fields and request plans in source_review_material. Actual clicked links and final host display remain unobserved.'}
    source_schema=response_review_schema(selection=selection,material=material)
    quality_schema=ExplanationQuality.model_json_schema()
    definitions=source_schema.pop('$defs',{})
    for key,value in quality_schema.pop('$defs',{}).items():
        if key in definitions and definitions[key]!=value:raise ValueError('COMBINED_REVIEW_SCHEMA_NAME_CONFLICT')
        definitions[key]=value
    schema={'type':'object','properties':{'source_review':source_schema,'quality_review':quality_schema},
        'required':['source_review','quality_review'],'additionalProperties':False,'$defs':definitions}
    prompt=(instructions+'\nQUALITY RUBRIC (same response, separate checker): '+quality_instructions+
        '\nReturn source_review AND quality_review in one object. Do not substitute one opinion for the other. '
        'The source_review_material owns its review_value_catalog; quality_view is expanded. '
        'citation_from_source_target addresses that target_pointer in all_current_statements_for_question_coverage and its zero-based citations index; resolve the identical full evidence there. '
        'All original scope boundaries and six quality axes remain required.\n'+json.dumps(payload,ensure_ascii=False,separators=(',',':')))
    return prompt,schema


def _provider_completed(run):
    """Accept only a known successful provider completion."""
    return (isinstance(run,dict) and run.get('status')=='completed' and not run.get('error')
        and run.get('finish_reasons') in (None,['stop']))


def _persisted_provider_completed(run):
    """Validate a completed leaf through only locally recognized stored wrappers."""
    seen=set()
    while isinstance(run,dict):
        marker=id(run)
        if marker in seen:return False
        seen.add(marker)
        if run.get('error') or run.get('finish_reasons') not in (None,['stop']):return False
        if run.get('status')=='completed':return True
        if run.get('status') not in ('stored_completed_observation','stored_completed_patch_observation'):
            return False
        run=run.get('prior_provider')
    return False



def _provider_execution_unknown(run):
    """Summarize uncertainty without changing receipt validity or failure classes."""
    seen=set()
    while isinstance(run,dict):
        marker=id(run)
        if marker in seen:return True
        seen.add(marker)
        status=run.get('status')
        if run.get('error') or status in (None,'unknown','timeout','timed_out','budget_unresolved','error'):
            return True
        if status not in ('stored_completed_observation','stored_completed_patch_observation',
                'stored_observation_rejected','stored_patch_observation_rejected'):
            # An incomplete/length result is a known failure, not an uncertain call.
            return False
        run=run.get('prior_provider')
    return True


def _rejected_stored_provider(status, prior_provider, **metadata):
    return {'status':status,'new_model_dispatch':False,'prior_provider':copy.deepcopy(prior_provider),
        'stored_provider_completion_validated':False,**metadata}


async def review_response(*, bound, context, sources, questions, output_dir, infer,
        validate_repair, provider='codex', max_repairs=1, reading_ref=None, stored_failure=None,
        combined_review=False, request_budget=None):
    """Review once and repair only recorded failures within a fixed budget.

    The caller persists these attempted answers/reviews as candidate history.
    A failed repair leaves the last bound answer and its unresolved review
    available; it is never reported as an accepted answer.
    """
    from agent_kit.python.boi_process_explanation_quality import (ExplanationQuality, quality_prompt,
        quality_selection, quality_material, merge_quality, with_quality, QUALITY_VERSION, QUALITY_PRESENTATION_VERSION)
    if not 0 <= max_repairs <= 2:
        raise ValueError('PROCESS_RESPONSE_REPAIR_BUDGET_REQUIRED')
    if combined_review and (request_budget is None or stored_failure is not None or max_repairs>1):
        raise ValueError('COMBINED_REVIEW_REQUEST_BUDGET_AND_FRESH_CANDIDATE_REQUIRED')
    if request_budget is not None:infer=request_budget
    root = Path(output_dir); root.mkdir(parents=True, exist_ok=False)
    def save(name, value):
        import os,uuid
        temporary=root/(name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('x') as stream:
            json.dump(value,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
        temporary.replace(root/name)
    current = bound; previous_material = previous_assessment = previous_quality = None; attempts = []
    for index in range(max_repairs + 1):
        material = response_material(answers=current, context=context, sources=sources, questions=questions)
        selection = response_review_selection(material, previous_material=previous_material,
            previous_assessment=previous_assessment)
        prompt = response_review_prompt(material,selection,context)
        schema=response_review_schema(selection=selection,material=material)
        combined_quality=None
        if combined_review:
            quality_scope=quality_selection(material,previous_material=previous_material,previous_quality=previous_quality)
            prompt,schema=combined_response_review_input(material,selection,context,quality_scope)
        save(f'review-input-{index}.json',{'prompt':prompt,'schema':schema})
        source_observation_reused=False
        try:
            if index==0 and stored_failure is not None:
                # This is an existing observation, never a new review receipt.
                assessed=stored_failure['assessment']
                prior_provider=stored_failure.get('prior_provider')
                source_observation_reused=_persisted_provider_completed(prior_provider)
                if source_observation_reused:
                    run={'status':'stored_completed_observation','new_model_dispatch':False,
                        'source_answer_revision':stored_failure['source_answer_revision'],
                        'prior_provider':copy.deepcopy(prior_provider),'observation_replayed':True}
                else:
                    run=_rejected_stored_provider('stored_observation_rejected',prior_provider,
                        source_answer_revision=stored_failure['source_answer_revision'],observation_replayed=False)
            else:
                assessed, run = await asyncio.to_thread(infer, provider=provider,
                    prompt=prompt,
                    schema=schema, output_dir=root / f'review-{index}',
                    **({'knowledge_reading_ref':reading_ref} if reading_ref else {}))
        except ValueError as exc:
            run=recorded_provider_failure(root/f'review-{index}',exc)
            attempt={'answer':current,'review':None,'provider':run,'selection':selection,
                'material_digest':semantic_digest(material),'check':{'assessment_complete':False,
                    'model_assessment_accepts_answers':False,'review_failure':'external_result_unknown'
                        if run['status']=='timed_out' else 'provider_failed',
                    'unreviewed_target_pointers':[t['target_pointer'] for t in selection['targets']],
                    'diagnostic':str(exc),'scientific_correctness':'not_evaluated'}}
            attempts.append(attempt);save(f'attempt-{index}.json',attempt);save(f'material-{index}.json',material)
            break
        if combined_review:
            save(f'combined-output-{index}.json',{'assessment':assessed,'provider':run})
            combined_quality=assessed.get('quality_review') if isinstance(assessed,dict) else None
            assessed=assessed.get('source_review') if isinstance(assessed,dict) else None
        try:
            if not source_observation_reused and not _provider_completed(run):
                raise ValueError('COMBINED_REVIEW_PROVIDER_NOT_COMPLETED' if combined_review else 'REVIEW_PROVIDER_NOT_COMPLETED')
            merged = merge_response_review(assessed, selection=selection)
            check = response_check(merged, material=material)
        except ValueError as exc:
            merged = assessed
            check = {'assessment_complete': False, 'diagnostic': str(exc),
                'model_assessment_accepts_answers': False, 'review_failure': 'invalid_assessment',
                'scientific_correctness': 'not_evaluated'}
        quality_record=None
        if check.get('assessment_complete'):
            quality_scope=quality_selection(material,previous_material=previous_material,previous_quality=previous_quality)
            quality_input=quality_material(material,quality_scope)
            quality_value=quality_run=None
            quality_observation_reused=False
            try:
                if (index==0 and stored_failure is not None and not stored_failure.get('refresh_quality')
                        and stored_failure['quality_review']['contract_version']==QUALITY_VERSION):
                    quality_record=stored_failure['quality_review']
                    quality_value=quality_record['assessment']
                    prior_provider=quality_record.get('provider')
                    quality_observation_reused=_persisted_provider_completed(prior_provider)
                    if not quality_observation_reused:
                        quality_run=_rejected_stored_provider('stored_observation_rejected',prior_provider,
                            source_answer_revision=stored_failure['source_answer_revision'],observation_replayed=False)
                        raise ValueError('STORED_QUALITY_PROVIDER_NOT_COMPLETED')
                    quality_run={'status':'stored_completed_observation','new_model_dispatch':False,
                        'source_answer_revision':stored_failure['source_answer_revision'],
                        'prior_provider':copy.deepcopy(prior_provider),'observation_replayed':True}
                    quality_merged=quality_value
                elif combined_review:
                    quality_value=combined_quality
                    quality_run={**run,'combined_with_source_review':True,'additional_model_dispatch':False}
                    quality_merged=merge_quality(quality_value,material=material,selection=quality_scope)
                elif not quality_scope['question_ids']:
                    quality_merged=previous_quality
                    quality_run={'status':'unchanged_quality_carried','new_model_dispatch':False}
                else:
                    quality_value,quality_run=await asyncio.to_thread(infer,provider=provider,
                        prompt=quality_prompt(quality_input),schema=ExplanationQuality.model_json_schema(),
                        output_dir=root/f'quality-{index}',
                        **({'knowledge_reading_ref':reading_ref} if reading_ref else {}))
                    if not _provider_completed(quality_run):
                        raise ValueError('QUALITY_PROVIDER_NOT_COMPLETED')
                    quality_merged=merge_quality(quality_value,material=material,selection=quality_scope)
                check=with_quality(check,quality_merged,material=material)
                quality_record={'assessment':quality_merged,'provider':quality_run,'selection':quality_scope,
                    'material_digest':semantic_digest(quality_input),'contract_version':QUALITY_VERSION,
                    'presentation_contract_version':(stored_failure['quality_review'].get('presentation_contract_version','boi/process-explanation-quality-presentation@1') if quality_observation_reused else QUALITY_PRESENTATION_VERSION)}
            except ValueError as exc:
                if quality_run is None:quality_run=recorded_provider_failure(root/f'quality-{index}',exc)
                quality_record={'assessment':quality_value,'provider':quality_run,'selection':quality_scope,
                    'material_digest':semantic_digest(quality_input),'contract_version':QUALITY_VERSION,
                    'presentation_contract_version':(stored_failure['quality_review'].get('presentation_contract_version','boi/process-explanation-quality-presentation@1') if quality_observation_reused else QUALITY_PRESENTATION_VERSION)}
                check={**check,'assessment_complete':False,'model_assessment_accepts_answers':False,
                    'review_failure':'quality_provider_unresolved' if quality_run.get('status')!='completed' else 'invalid_quality_assessment',
                    'diagnostic':str(exc)}
        attempt = {'answer': current, 'review': merged, 'check': check, 'provider': run,
            'material_digest': semantic_digest(material), 'selection': selection, 'quality_review':quality_record}
        attempts.append(attempt)
        save(f'attempt-{index}.json', attempt); save(f'material-{index}.json', material)
        if check.get('model_assessment_accepts_answers') or not check['assessment_complete'] or index == max_repairs:
            break
        proposal = response_proposal(current)
        compact_packet = None
        repair_observation_reused=False
        repair_run=None
        try:
            if index==0 and stored_failure and stored_failure.get('reusable_invalid_patch'):
                prior_patch=stored_failure['reusable_invalid_patch']
                prior_provider=prior_patch.get('provider')
                repair_observation_reused=_persisted_provider_completed(prior_provider)
                if not repair_observation_reused:
                    repair_run=_rejected_stored_provider('stored_patch_observation_rejected',prior_provider,
                        source_answer_revision=stored_failure['source_answer_revision'],
                        original_patch_digest=semantic_digest(prior_patch['patch']))
                    raise ValueError('STORED_REPAIR_PROVIDER_NOT_COMPLETED')
                patch=rebase_recorded_patch(prior_patch['patch'],prior_patch['base_proposal'],proposal)
                repair_run={'status':'stored_completed_patch_observation','new_model_dispatch':False,
                    'source_answer_revision':stored_failure['source_answer_revision'],
                    'prior_provider':copy.deepcopy(prior_provider),'original_patch_digest':semantic_digest(prior_patch['patch'])}
            else:
                repair_prompt=response_repair_prompt(proposal,check,sources,context,questions,attempt_number=index+1,max_repairs=max_repairs)
                repair_schema=response_repair_schema()
                if combined_review:
                    from .boi_compact_source_repair import prepare_source_repair,source_repair_prompt
                    try:
                        compact_packet=prepare_source_repair(proposal,check=check,context=context,sources=sources,questions=questions)
                    except ValueError as exc:
                        if str(exc) not in {'SOURCE_REPAIR_ORIGINAL_ONLY',
                                'SOURCE_REPAIR_FULL_QUALITY_CONTRACT_REQUIRED',
                                'SOURCE_REPAIR_RECORDED_STATEMENT_FAILURE_REQUIRED',
                                'SOURCE_REPAIR_MISSING_REQUEST_FULL_CONTRACT_REQUIRED',
                                'SOURCE_REPAIR_DEPENDENT_FACET_FULL_CONTRACT_REQUIRED'}:raise
                        save(f'compact-repair-fallback-{index}.json',{'reason':str(exc),'new_model_dispatch':False})
                    if compact_packet is not None:
                        save(f'compact-repair-input-{index}.json',compact_packet)
                        repair_prompt=source_repair_prompt(compact_packet)
                        repair_schema=compact_packet['schema']
                patch, repair_run = await asyncio.to_thread(infer, provider=provider,
                    prompt=repair_prompt, schema=repair_schema, output_dir=root / f'repair-{index}',
                    **({'knowledge_reading_ref':reading_ref} if reading_ref else {}))
        except ValueError as exc:
            provider_record=(repair_run if isinstance(repair_run,dict) and
                repair_run.get('status')=='stored_patch_observation_rejected' else
                recorded_provider_failure(root/f'repair-{index}',exc))
            repair_record={'provider':provider_record,
                'status':'external_repair_unresolved','diagnostic':str(exc)}
            attempt['repair']=repair_record;save(f'repair-check-{index}.json',repair_record);break
        repair_record = {'provider': repair_run, 'patch': patch}
        attempt['repair'] = repair_record
        try:
            if not repair_observation_reused and not _provider_completed(repair_run):
                raise ValueError('COMBINED_REPAIR_PROVIDER_NOT_COMPLETED' if combined_review else 'REPAIR_PROVIDER_NOT_COMPLETED')
            if compact_packet is not None:
                from .boi_compact_source_repair import parse_saved_source_repair,expand_source_repair
                repair_record['compact_wire_result']=patch
                value,transformations=parse_saved_source_repair(json.dumps(patch,ensure_ascii=False),packet=compact_packet)
                patch=expand_source_repair(value,packet=compact_packet,proposal=proposal,check=check)
                repair_record.update(patch=patch,transport_reconciliation=transformations,
                    repair_contract=compact_packet['contract_version'])
            repaired, delta = apply_response_repair(proposal, patch, check=check)
            repair_record['delta'] = delta
            if semantic_digest(repaired) == semantic_digest(proposal):
                repair_record['status'] = 'unresolved_no_change'
                save(f'repair-check-{index}.json', repair_record); break
            rebound = validate_repair(repaired)
        except ValueError as exc:
            repair_record.update(status='invalid_repair', diagnostic=str(exc))
            save(f'repair-check-{index}.json', repair_record); break
        repair_record['status'] = 'bound_for_revalidation'
        save(f'repair-check-{index}.json', repair_record)
        previous_material, previous_assessment, previous_quality = material, merged, quality_record['assessment']
        current = rebound
    providers=[a['provider'] for a in attempts]
    providers.extend(record['provider'] for a in attempts
        for record in (a.get('repair'),a.get('quality_review')) if record and 'provider' in record)
    report = {'status': 'accepted_by_model_review' if attempts[-1]['check'].get('model_assessment_accepts_answers')
        else 'unresolved_answer_review', 'max_repairs': max_repairs, 'attempts': attempts,
        'external_execution_state':'unknown' if any(_provider_execution_unknown(p) for p in providers) else 'known',
        'review_contract_version': RESPONSE_REVIEW_VERSION, 'presentation_contract_version':RESPONSE_PRESENTATION_VERSION,
        'assessment_schema_version':RESPONSE_ASSESSMENT_SCHEMA_VERSION,
        'repair_presentation_contract_version':RESPONSE_REPAIR_PRESENTATION_VERSION,
        'scientific_correctness': 'not_evaluated', 'whole_plan_qualified': False}
    if combined_review:report['review_mode']='combined_source_and_quality'
    if request_budget is not None:
        report['request_budget']=request_budget.snapshot()
        if report['request_budget'].get('unresolved_attempt_ids'):
            report['external_execution_state']='unknown'
    save('report.json', report)
    return current, report


def partition_response_review(selection, *, max_targets_per_call):
    """Bound output targets; callers retain the same full source/answer material.

    The last partition assesses whole-request coverage without prior approval
    opinions. Returned selections never claim omitted targets were assessed.
    """
    if isinstance(max_targets_per_call,bool) or not isinstance(max_targets_per_call,int) or max_targets_per_call<1:
        raise ValueError('PROCESS_RESPONSE_BATCH_SIZE_INVALID')
    targets=selection['targets'];requirements=selection['requirements']
    if len(targets)<=max_targets_per_call:return [copy.deepcopy(selection)]
    batches=[{'targets':copy.deepcopy(targets[i:i+max_targets_per_call]),'requirements':[],
        'carry_forward_statements':[],'carry_forward_requirements':[]}
        for i in range(0,len(targets),max_targets_per_call)]
    if requirements:
        batches.append({'targets':[],'requirements':copy.deepcopy(requirements),
            'carry_forward_statements':[],'carry_forward_requirements':[]})
    return batches
