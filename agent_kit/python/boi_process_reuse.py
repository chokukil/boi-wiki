"""Resolve proposed definition-node uses against complete authorized readings.

The model compares meaning/scope. This tool binds exactly what was compared and
used; it never infers equivalence from a name, node hash or successful lint.
"""
import json

from pydantic import ValidationError

from agent_kit.python.boi_process_answer_v2 import _meaning_evidence,validate_source_readings
from agent_kit.python.boi_process_lint import bind_process_meaning
from boi_api.app.governed_runtime.domain_work_contract import DomainHarnessContract,DomainToolReport
from boi_api.app.governed_runtime.knowledge_node_contract import KnowledgeNodeRef
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
from boi_api.app.governed_runtime.process_reuse_contract import ProcessDefinitionUse,ProcessReuseProposal
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


def definition_node_inventory(context):
    context=TaskKnowledgeContext.model_validate(context)
    result=[]
    for asset in context.assets:
        if asset.kind!='definition' or asset.authority=='legacy_unbound':continue
        value=json.loads(asset.content_json)
        if value.get('contract_version') not in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):continue
        draft=ProcessKnowledgeDraft.model_validate(value['draft'])
        for ri,record in enumerate(draft.records):
            for kind,items in (('terms',record.terms),('assertions',record.assertions)):
                for i,item in enumerate(items):
                    eligible=(item.proposed_definition is not None if kind=='terms' else item.category=='definition')
                    if not eligible:continue
                    pointer=f'/records/{ri}/{kind}/{i}'
                    node=item.model_dump(mode='json')
                    result.append({'node_ref':KnowledgeNodeRef(asset_revision=asset.revision,node_pointer=pointer,
                        node_digest=semantic_digest(node)).model_dump(mode='json'),
                        'kind':'term_definition' if kind=='terms' else 'definition_assertion','value':node,
                        'source_revision_digest':draft.source_revision_digest,
                        'process_identity':next(t.model_dump(mode='json') for t in record.terms if t.term_id==record.process_ref),
                        'record_applicability':[a.model_dump(mode='json') for a in record.assertions if a.category=='applicability'],
                        'authority':asset.authority,'source_fidelity':'not_evaluated'})
    return result


def definition_node_evidence(asset,node_ref,indexed,*,assets=None,trail=frozenset(),include_record_applicability=True):
    """Rebind a specific definition and its record scope, never cached offsets."""
    node_ref=KnowledgeNodeRef.model_validate(node_ref)
    if asset.revision!=node_ref.asset_revision or asset.kind!='definition' or asset.authority=='legacy_unbound':
        raise ValueError('PROCESS_REUSE_DEFINITION_AUTHORITY_OR_REVISION_MISMATCH')
    value=json.loads(asset.content_json)
    if value.get('contract_version') not in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
        raise ValueError('PROCESS_REUSE_DEFINITION_CONTRACT_UNSUPPORTED')
    draft=ProcessKnowledgeDraft.model_validate(value['draft'])
    eligible={f'/records/{ri}/{kind}/{i}':(ri,item) for ri,r in enumerate(draft.records)
        for kind,items in (('terms',r.terms),('assertions',r.assertions)) for i,item in enumerate(items)
        if (item.proposed_definition is not None if kind=='terms' else item.category=='definition')}
    entry=eligible.get(node_ref.node_pointer)
    if entry is None or semantic_digest(entry[1].model_dump(mode='json'))!=node_ref.node_digest:
        raise ValueError('PROCESS_REUSE_NODE_NOT_READ_OR_CHANGED')
    closure=_meaning_evidence(asset,node_ref.node_pointer,indexed,assets=assets,trail=trail)
    seen={(g.get('asset_revision',asset.revision.model_dump(mode='json'))['ref'],g['target_pointer']) for g in closure}
    for ai,claim in enumerate(draft.records[entry[0]].assertions):
        if claim.category=='applicability' and include_record_applicability:
            for node in _meaning_evidence(asset,f'/records/{entry[0]}/assertions/{ai}',indexed,assets=assets,trail=trail):
                key=(node.get('asset_revision',asset.revision.model_dump(mode='json'))['ref'],node['target_pointer'])
                if key not in seen:
                    closure.append({**node,'role':'definition_record_applicability'});seen.add(key)
    return closure


def bind_process_reuse(proposal, *, evidence, context, sources=None):
    from .boi_process_categories import declared_proposal_schema_errors
    value=proposal.model_dump(mode='json') if hasattr(proposal,'model_dump') else proposal
    if declared_proposal_schema_errors(value,context):
        raise ValueError('PROCESS_DECLARED_PROFILE_SCHEMA_MISMATCH')
    if value.get('contract_version')=='boi/process-definition-reuse-proposal@2':
        return bind_process_reuse_v2(proposal,evidence=evidence,context=context,sources=sources)
    return _bind_process_reuse_legacy(proposal,evidence=evidence,context=context,sources=sources)


def _bind_process_reuse_legacy(proposal, *, evidence, context, sources=None):
    """Internal reference projection, not admission of a second public schema."""
    proposal=ProcessReuseProposal.model_validate(proposal)
    context=TaskKnowledgeContext.model_validate(context)
    if context.context_digest!=proposal.context_digest:raise ValueError('PROCESS_REUSE_CONTEXT_MISMATCH')
    sources=sources if sources is not None else [evidence]
    indexed=validate_source_readings(context,sources)
    nodes={KnowledgeNodeRef.model_validate(n['node_ref']):n for n in definition_node_inventory(context)}
    assets={a.revision:a for a in context.assets}
    draft=proposal.draft.model_dump(mode='json')
    terms={f'/records/{ri}/terms/{ti}':t for ri,r in enumerate(draft['records']) for ti,t in enumerate(r['terms'])}
    uses=[];applied=set();compared=set()
    for use in proposal.definition_uses:
        if use.term_pointer not in terms:raise ValueError('PROCESS_REUSE_LOCAL_TERM_MISSING')
        if use.definition_node not in nodes:raise ValueError('PROCESS_REUSE_NODE_NOT_READ_OR_CHANGED')
        target=nodes[use.definition_node]
        asset=assets[use.definition_node.asset_revision]
        closure=definition_node_evidence(asset,use.definition_node,indexed,assets=assets)
        compared.add(asset.revision)
        if use.application=='interpret_term':
            terms[use.term_pointer]['reused_definition']=asset.revision.model_dump(mode='json')
            applied.add(asset.revision)
        body={**use.model_dump(mode='json'),'definition_value':target['value'],'definition_authority':asset.authority,
            'definition_evidence':closure,'semantic_relation_status':'model_proposed','application_scope':'provisional_task_only'}
        uses.append({**body,'use_digest':semantic_digest(body)})
    draft['definition_revisions_used']=[r.model_dump(mode='json') for r in sorted(applied,key=lambda r:r.ref)]
    bound=bind_process_meaning(draft,evidence=evidence,extraction_context=context,version=2,source_readings=sources)
    for use in uses:
        use['local_bindings']=[b for b in bound['bindings'] if b['target_pointer'].startswith(use['term_pointer']+'/evidence/')]
        use['use_digest']=semantic_digest({k:v for k,v in use.items() if k!='use_digest'})
    bound['definition_uses']=uses
    bound['definition_comparison_revisions']=[r.model_dump(mode='json') for r in sorted(compared,key=lambda r:r.ref)]
    bound['transformation']['reference_projection']={'kind':'exact_definition_node_reference_projection',
        'proposal_digest':semantic_digest(proposal.model_dump(mode='json')),
        'used_node_refs':[u.definition_node.model_dump(mode='json') for u in proposal.definition_uses if u.application=='interpret_term'],
        'semantic_equivalence_proven':False}
    return bound


def bind_process_reuse_v2(proposal, *, evidence, context, sources=None):
    from agent_kit.python.boi_process_scope import bind_scope_facets
    from boi_api.app.governed_runtime.process_reuse_scope_contract import ProcessReuseProposalV2
    proposal=ProcessReuseProposalV2.model_validate(proposal)
    from .boi_process_categories import declared_proposal_schema_errors
    if declared_proposal_schema_errors(proposal.model_dump(mode='json'),context):
        raise ValueError('PROCESS_DECLARED_PROFILE_SCHEMA_MISMATCH')
    context=TaskKnowledgeContext.model_validate(context)
    indexed=validate_source_readings(context,sources if sources is not None else [evidence])
    # Reuse the established node/reference/quote gate. Its old use fields are
    # only a read projection and are not retained as a second scope authority.
    bound=_bind_process_reuse_legacy(proposal.legacy_projection(),evidence=evidence,context=context,sources=sources)
    assets={a.revision:a for a in context.assets}
    uses=[]
    for use,legacy in zip(proposal.definition_uses,bound['definition_uses']):
        resolved=bind_scope_facets(use,draft=proposal.draft,definition_asset=assets[use.definition_node.asset_revision],indexed=indexed)
        metadata={k:v for k,v in legacy.items() if k not in (*ProcessDefinitionUse.model_fields,'use_digest')}
        metadata['definition_evidence']=definition_node_evidence(assets[use.definition_node.asset_revision],use.definition_node,
            indexed,assets=assets,include_record_applicability=False)
        body={**use.model_dump(mode='json'),**metadata,'resolved_scope':resolved}
        uses.append({**body,'use_digest':semantic_digest(body)})
    bound['definition_uses']=uses
    bound['transformation']['reference_projection'].update(
        proposal_digest=semantic_digest(proposal.model_dump(mode='json')),
        scope_representation='explicit_facet_decisions@2; no independent presence/absence label')
    return bound


def process_reuse_profile(*,version=1):
    from boi_api.app.governed_runtime.process_reuse_scope_contract import ProcessReuseProposalV2
    if version not in (1,2,3):raise ValueError('PROCESS_REUSE_PROFILE_VERSION_UNSUPPORTED')
    from .boi_process_categories import category_semantics
    return {'contract_version':f'boi/process-reuse-profile@{version}','meaning_schema':(ProcessReuseProposal if version==1 else ProcessReuseProposalV2).model_json_schema(),
        'purpose':'Interpret a new process draft using exact previously stored definition nodes.',
        'definition_node_schema':KnowledgeNodeRef.model_json_schema(),
        **({'category_semantics':category_semantics(),'category_contract_scope':'This exact profile revision applies to the new extraction. Historical definition nodes retain their original profile semantics.'} if version==3 else {}),
        'rules':['Read the whole context and original source. Use exact inventory node references.',
            'Compare meaning, applicability, conditions and exceptions; similarity is discovery, not equivalence.',
            'Keep the legacy draft revision-use fields empty. The tool projects verified node references into those fields.',
            *(['Account for every typed scope facet in both process records; select applies/not_applicable/unresolved with reasons. '
                'All qualifiers are candidates for consideration, not automatically global constraints. '
                'Do not claim no conditions while selecting a condition: presence is computed from your explicit references.'] if version>=2 else []),
            'A definition category alone does not prove semantic completeness or scientific correctness.'],
        'canonical_projection_eligible':False}


def process_reuse_harness(*, namespace, tool_revision,version=1):
    return DomainHarnessContract(namespace=namespace,title='Process definition node reuse',
        purpose='Bind new process meaning to exact definitions and both sides of source evidence.',
        stages=({'stage_id':'reuse','purpose':'Compare and bind previously read definition nodes',
            'instructions':'Read the process reuse profile, original fields and complete definition context. '
                'Propose meaning and scoped node uses, then execute the declared external tool unchanged.',
            'tools':[{'tool_revision':tool_revision,'input_names':['draft','evidence','context']+(['sources'] if version>=2 else []),
                'input_kinds':{'draft':'proposal','evidence':'source_projection','context':'context',
                    **({'sources':'source_projection_bundle'} if version>=2 else {})},
                'checks':[{'check_id':'process_definition_node_binding','accepted_statuses':['pass']}]}]},))


def execute_process_reuse(inputs):
    if not {'draft','evidence','context'}<=set(inputs) or set(inputs)-{'draft','evidence','context','sources'}:
        raise ValueError('PROCESS_REUSE_INPUT_SET_MISMATCH')
    values={k:json.loads(v) for k,v in inputs.items()}
    source=values['evidence']['source']['artifact_ref']
    try:
        from .boi_process_categories import declared_proposal_schema_errors
        schema_errors=declared_proposal_schema_errors(values['draft'],values['context'])
        if schema_errors:raise ValueError('PROCESS_DECLARED_PROFILE_SCHEMA_MISMATCH')
        result=bind_process_reuse(values['draft'],evidence=values['evidence'],context=values['context'],sources=values.get('sources'))
    except (ValueError,ValidationError) as exc:
        if isinstance(exc,ValidationError):
            diagnostics=[{'path':list(e['loc']),'message':e['msg']} for e in exc.errors(include_input=False,include_url=False)]
            reason='PROCESS_REUSE_TYPED_PROPOSAL_INVALID'
        else:
            reason=str(exc)
            if not reason.startswith(('PROCESS_','ANSWER_','TASK_')):raise
            diagnostics=schema_errors if reason=='PROCESS_DECLARED_PROFILE_SCHEMA_MISMATCH' else [{'message':reason}]
        return DomainToolReport(checks=[{'check_id':'process_definition_node_binding','status':'fail',
            'subject_ref':source,'reason_code':reason,'evidence_refs':[source]}],result={'diagnostics':diagnostics,
                'source_fidelity':'not_evaluated','status':'PROVISIONAL','canonical_projection_eligible':False}).model_dump(mode='json')
    return DomainToolReport(checks=[{'check_id':'process_definition_node_binding','status':'pass','subject_ref':source,
        'reason_code':'PROCESS_NODE_USES_BOUND_SEMANTICS_UNASSESSED','evidence_refs':[source]}],result=result).model_dump(mode='json')
