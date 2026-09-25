"""Evaluate completeness of a model assessment, not semantic truth by rules.

The judge's reasoning and quotations remain reviewable model evidence. Literal
checks here verify coverage, references, and precommitted contrast expectations.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Literal
from pydantic import Field

from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft, ProcessQuotation
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract, Ref


class ClaimAssessment(FrozenContract):
    target_pointer: Ref
    label: Literal['supported','contradicted','unsupported']
    reason: Ref
    evidence: tuple[ProcessQuotation, ...] = Field(min_length=1)


class PropositionAssessment(FrozenContract):
    proposition_id: Ref
    status: Literal['covered','partial','omitted']
    target_pointers: tuple[Ref, ...]
    reason: Ref


class ContrastAssessment(FrozenContract):
    case_id: Ref
    label: Literal['supported','contradicted','unsupported']
    reason: Ref
    evidence: tuple[ProcessQuotation, ...] = Field(min_length=1)


class ProcessFidelityAssessment(FrozenContract):
    contract_version: Literal['boi/process-fidelity-assessment@1'] = 'boi/process-fidelity-assessment@1'
    claims: tuple[ClaimAssessment, ...]
    propositions: tuple[PropositionAssessment, ...]
    contrasts: tuple[ContrastAssessment, ...]
    limitations: tuple[Ref, ...] = Field(min_length=1)


SOURCE_EVALUATION_VERSION = 'boi/process-source-evaluation-material@2'
SOURCE_EVALUATION_INSTRUCTIONS = '''Evaluate each target's source meaning against the supplied original fields.
The meaning graph retains all semantic fields: term labels, proposed definitions and categories;
assertion subject/object references, statement, category, polarity, modality, conditions, exceptions,
applicability, dependencies and uncertainties. Resolve local references using the complete graph.
Read structured fields and prose together; a correct statement does not excuse an incompatible subject or category.
Supported includes normal paraphrase, translation and a classification entailed by the supplied context.
Do not require the source to spell out an ontology category label verbatim. Conversely, mere occurrence of
a token does not support an invented expansion, incompatible type, unstated property, broader scope or condition.
Contradicted means incompatible source facts. Unsupported means an unestablished addition or expansion;
explain whether it is a scope/condition problem. Absent support does not establish scientific falsity.
Machine provenance is provided separately for traceability. Revision IDs, digests and reused_definition
links are not source propositions and need not occur in the source text. This source assessment neither
validates nor invalidates those links; exact reference binding and cross-definition reuse have separate checks.
A linked definition does not by itself establish new local meaning or expand the supplied source's scope.
Assess every fixed required proposition: covered needs supported semantic targets, partial means only some
meaning is represented, omitted means no representation. Quotation presence alone is not extracted coverage.
Covered cannot cite a target you judged unsupported or contradicted; report partial or omitted instead.
Assess contrast texts without expected labels. Use exact field_locator/quote/zero-based occurrence evidence.
No tools, external factual knowledge, repairs or changed expected requirements. Explain in Korean.
This is an external model assessment, not expert validation, deterministic entailment or scientific proof.
'''


def source_evaluation_material(*, draft, evidence, oracle):
    """Separate nonsemantic provenance without hiding any typed meaning.

    The original draft remains immutable and is still used by check_assessment.
    This projection is only for the offline evaluator, never an intake contract.
    """
    graph = ProcessKnowledgeDraft.model_validate(draft).model_dump(mode='json')
    provenance = {name: graph.pop(name) for name in (
        'contract_version', 'source_revision_digest', 'extraction_context_digest',
        'definition_revisions_used')}
    links = []
    for ri, record in enumerate(graph['records']):
        for ti, term in enumerate(record['terms']):
            links.append({'target_pointer': f'/records/{ri}/terms/{ti}',
                          'reused_definition': term.pop('reused_definition')})
    provenance['term_definition_links'] = links
    targets = deepcopy(assessment_targets(draft, include_all_terms=True))
    for target in targets:
        target['value'].pop('reused_definition', None)
    return {'contract_version': SOURCE_EVALUATION_VERSION,
        'original_fields': deepcopy(evidence['fields']), 'meaning_graph': graph,
        'targets': targets, 'machine_provenance': provenance,
        'required_propositions': [deepcopy(p) for r in oracle['records'] for p in r['required_propositions']],
        'contrast_cases': contrast_cases(oracle),
        'reference_binding_and_definition_reuse': 'separately_evaluated',
        'scientific_correctness': 'not_evaluated', 'production_input': False}


def assessment_targets(draft, *, include_all_terms=False):
    draft=ProcessKnowledgeDraft.model_validate(draft)
    targets=[]
    for ri, record in enumerate(draft.records):
        for ti, term in enumerate(record.terms):
            if include_all_terms:
                targets.append({'target_pointer':f'/records/{ri}/terms/{ti}',
                    'kind':'term_definition' if term.proposed_definition is not None else 'term',
                    'value':term.model_dump(mode='json')})
            elif term.proposed_definition is not None:
                targets.append({'target_pointer':f'/records/{ri}/terms/{ti}/proposed_definition',
                    'kind':'term_definition','value':term.model_dump(mode='json')})
        for ai, assertion in enumerate(record.assertions):
            targets.append({'target_pointer':f'/records/{ri}/assertions/{ai}',
                'kind':'definition_assertion' if include_all_terms and assertion.category=='definition' else 'assertion',
                'value':assertion.model_dump(mode='json')})
    return targets


def contrast_cases(oracle, *, include_labels=False):
    result=[]
    for ri, record in enumerate(oracle['records']):
        for ci, case in enumerate(record['contrast_cases']):
            value={'case_id':f'contrast:{ri}:{ci}','process':record['process'],'text':case['text']}
            if include_labels:value['expected_label']=case['label']
            result.append(value)
    return result


def check_assessment(assessment, *, draft, evidence, oracle):
    value=ProcessFidelityAssessment.model_validate(assessment)
    target_inventory={t['target_pointer']:t for t in assessment_targets(draft,
        include_all_terms=oracle.get('contract_version')=='boi/process-sample-oracle@2')}
    targets=set(target_inventory)
    required={p['id'] for r in oracle['records'] for p in r['required_propositions']}
    cases={c['case_id']:c for c in contrast_cases(oracle,include_labels=True)}
    def exact_set(items, expected, code):
        if len(set(items)) != len(items) or set(items) != expected:
            raise ValueError('PROCESS_FIDELITY_'+code)
    exact_set([c.target_pointer for c in value.claims],targets,'CLAIM_COVERAGE_INCOMPLETE')
    exact_set([p.proposition_id for p in value.propositions],required,'PROPOSITION_COVERAGE_INCOMPLETE')
    exact_set([c.case_id for c in value.contrasts],set(cases),'CONTRAST_COVERAGE_INCOMPLETE')
    supported={c.target_pointer for c in value.claims if c.label=='supported'}
    for proposition in value.propositions:
        if not set(proposition.target_pointers) <= targets:
            raise ValueError('PROCESS_FIDELITY_UNKNOWN_CLAIM_REFERENCE')
        if proposition.status=='covered' and (not proposition.target_pointers or not set(proposition.target_pointers) <= supported):
            raise ValueError('PROCESS_FIDELITY_COVERAGE_WITHOUT_SUPPORTED_CLAIM')
        expectation=next(p for r in oracle['records'] for p in r['required_propositions'] if p['id']==proposition.proposition_id)
        allowed=expectation.get('allowed_target_kinds')
        if allowed and proposition.status=='covered':
            def kind(pointer):
                target=target_inventory[pointer]
                return 'definition_assertion' if target['kind']=='assertion' and target['value']['category']=='definition' else target['kind']
            if not any(kind(pointer) in allowed for pointer in proposition.target_pointers):
                raise ValueError('PROCESS_FIDELITY_REPRESENTATION_COVERAGE_MISSING')
    fields={f['field_locator']:f['text'] for f in evidence['fields']}
    for item in (*value.claims,*value.contrasts):
        for quote in item.evidence:
            text=fields.get(quote.field_locator,'');start=-1
            for _ in range(quote.occurrence+1):
                start=text.find(quote.quote,start+1)
                if start<0:raise ValueError('PROCESS_FIDELITY_QUOTE_NOT_IN_SOURCE')
    errors=[{'case_id':c.case_id,'expected':cases[c.case_id]['expected_label'],'actual':c.label}
        for c in value.contrasts if c.label!=cases[c.case_id]['expected_label']]
    claim_counts=dict(Counter(c.label for c in value.claims))
    coverage_counts=dict(Counter(p.status for p in value.propositions))
    return {'contract_version':'boi/process-fidelity-check@1','assessment_coverage':'complete',
        'evidence_quotation_binding':'pass','claim_counts':claim_counts,'proposition_counts':coverage_counts,
        'contrast_count':len(cases),'contrast_errors':errors,
        'model_assessment_accepts_source_fidelity':all(c.label=='supported' for c in value.claims)
            and all(p.status=='covered' for p in value.propositions) and not errors,
        'semantic_judgment_method':'external_model_assessment_with_independent_precommitted_oracle',
        'deterministic_entailment_proven':False,'scientific_correctness':'not_evaluated',
        'canonical_projection_eligible':False,'status':'PROVISIONAL'}
