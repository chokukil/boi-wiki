"""Independent assessment of proposed definition relations, never production matching.

The checker reproduces the material by re-binding and checks full assessment
coverage and quotations. Semantic judgments remain the external assessor's claims.
"""
import json
from collections import Counter
from typing import Literal

from pydantic import Field

from agent_kit.python.boi_process_answer_v2 import _source_binding, validate_source_readings
from agent_kit.python.boi_process_reuse import bind_process_reuse, definition_node_inventory
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessQuotation
from boi_api.app.governed_runtime.semantic_binding_contract import Digest, FrozenContract, Ref, semantic_digest
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


class ReuseQuotation(FrozenContract):
    source_revision_digest: Digest
    quotation: ProcessQuotation


class ReuseDimensionAssessment(FrozenContract):
    dimension: Literal['relation_and_application','meaning','applicability','conditions','exceptions']
    label: Literal['supported','contradicted','unsupported','inconclusive']
    reason: Ref
    evidence: tuple[ReuseQuotation,...] = Field(min_length=1)


class ReuseUseAssessment(FrozenContract):
    use_pointer: Ref
    judgments: tuple[ReuseDimensionAssessment,...] = Field(min_length=5,max_length=5)


class ProcessReuseAssessment(FrozenContract):
    contract_version: Literal['boi/process-reuse-assessment@1'] = 'boi/process-reuse-assessment@1'
    uses: tuple[ReuseUseAssessment,...]
    limitations: tuple[Ref,...] = Field(min_length=1)


def verified_reuse_material(*, proposal, bound, evidence, context, sources=None):
    """Input bytes must be read from the completed authorized tool invocation.

    This is offline reproducibility, not fresh ACL admission or reauthorization.
    """
    sources=sources if sources is not None else [evidence]
    replay=bind_process_reuse(proposal,evidence=evidence,context=context,sources=sources)
    if semantic_digest(replay)!=semantic_digest(bound):
        raise ValueError('PROCESS_REUSE_EVAL_BOUND_REPLAY_MISMATCH')
    ctx=TaskKnowledgeContext.model_validate(context)
    nodes={semantic_digest(n['node_ref']):n for n in definition_node_inventory(ctx)}
    records={f'/records/{ri}/terms/{ti}':r for ri,r in enumerate(bound['draft']['records'])
        for ti,_ in enumerate(r['terms'])}
    assets={semantic_digest(a.revision.model_dump(mode='json')):a for a in ctx.assets}
    targets=[]
    for i,use in enumerate(replay['definition_uses']):
        node=nodes[semantic_digest(use['definition_node'])]
        prior=json.loads(assets[semantic_digest(use['definition_node']['asset_revision'])].content_json)
        # Pointer membership was checked by the typed domain inventory above.
        prior_ri=int(use['definition_node']['node_pointer'].split('/')[2])
        targets.append({'use_pointer':f'/definition_uses/{i}', 'proposed_use':use,
            'local_record':records[use['term_pointer']], 'definition_inventory_entry':node,
            'definition_record':prior['draft']['records'][prior_ri]})
    return {'contract_version':'boi/process-reuse-evaluation-material@1','targets':targets,
        'sources':sources,'context':ctx.model_dump(mode='json'),
        'proposal_digest':semantic_digest(proposal),'bound_digest':semantic_digest(bound),
        'read_scope':'The complete delivered source fields and authorized context of this historical invocation only.',
        'semantic_equivalence_proven':False,'scientific_correctness':'not_evaluated'}


def check_reuse_assessment(assessment, *, material):
    value=ProcessReuseAssessment.model_validate(assessment)
    targets={t['use_pointer']:t for t in material['targets']}
    actual=[u.use_pointer for u in value.uses]
    if len(set(actual))!=len(actual) or set(actual)!=set(targets):
        raise ValueError('PROCESS_REUSE_EVAL_USE_COVERAGE_INCOMPLETE')
    indexed=validate_source_readings(material['context'],material['sources'])
    expected={'relation_and_application','meaning','applicability','conditions','exceptions'}
    bindings=[]
    for item in value.uses:
        if {j.dimension for j in item.judgments}!=expected:
            raise ValueError('PROCESS_REUSE_EVAL_DIMENSION_COVERAGE_INCOMPLETE')
        target=targets[item.use_pointer]['proposed_use']
        required_sources={b['source_revision_digest'] for b in target['local_bindings']}
        required_sources.update(b['source_revision_digest'] for n in target['definition_evidence'] for b in n['source_bindings'])
        for judgment in item.judgments:
            for q in judgment.evidence:
                bindings.append({'use_pointer':item.use_pointer,'dimension':judgment.dimension,
                    **_source_binding(indexed,q.source_revision_digest,q.quotation)})
            if judgment.label=='supported' and not required_sources<={q.source_revision_digest for q in judgment.evidence}:
                raise ValueError('PROCESS_REUSE_EVAL_POSITIVE_COMPARISON_MISSING_SOURCE_SIDE')
    labels=[j.label for u in value.uses for j in u.judgments]
    return {'contract_version':'boi/process-reuse-assessment-check@1','assessment_complete':True,
        'use_count':len(value.uses),'judgment_counts':dict(Counter(labels)),'quotation_bindings':bindings,
        'model_assessment_accepts_definition_uses':bool(value.uses) and all(x=='supported' for x in labels),
        'semantic_judgment_method':'independent_external_model_against_complete_supplied_sources',
        'independent_domain_expert_review':False,'deterministic_entailment_proven':False,
        'scientific_correctness':'not_evaluated','canonical_projection_eligible':False,
        'status':'PROVISIONAL','whole_plan_qualified':False,'material_digest':semantic_digest(material)}
