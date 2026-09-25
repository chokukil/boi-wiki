"""Record-local scope candidates and exact source bindings for reuse@2.

The inventory does not decide which qualifiers constrain a definition. The
agent must account for the complete typed record inventory, including exclusions.
"""
import json

from agent_kit.python.boi_process_answer_v2 import _source_binding
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
from boi_api.app.governed_runtime.process_reuse_scope_contract import ProcessDefinitionUseV2
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


def scope_facet_inventory(draft,target_pointer):
    draft=ProcessKnowledgeDraft.model_validate(draft)
    record_by_target={f'/records/{ri}/{kind}/{i}':(ri,r) for ri,r in enumerate(draft.records)
        for kind,items in (('terms',r.terms),('assertions',r.assertions)) for i,_ in enumerate(items)}
    if target_pointer not in record_by_target:raise ValueError('PROCESS_REUSE_SCOPE_TARGET_NOT_READ')
    ri,record=record_by_target[target_pointer]
    facets=[]
    for ai,claim in enumerate(record.assertions):
        parent=f'/records/{ri}/assertions/{ai}'
        if claim.category=='applicability':
            facets.append({'target_pointer':parent,'dimension':'applicability',
                'parent_pointer':parent,'parent_assertion':claim.model_dump(mode='json'),
                'value':claim.model_dump(mode='json')})
        for dimension in ('applicability','conditions','exceptions'):
            for qi,qualifier in enumerate(getattr(claim,dimension)):
                facets.append({'target_pointer':f'{parent}/{dimension}/{qi}','dimension':dimension,
                    'parent_pointer':parent,'parent_assertion':claim.model_dump(mode='json'),
                    'value':qualifier.model_dump(mode='json')})
    return {'target_pointer':target_pointer,'record_pointer':f'/records/{ri}',
        'source_revision_digest':draft.source_revision_digest,'facets':facets,
        'inventory_digest':semantic_digest(facets),'selection_authority':'model_proposed',
        'scope':'all typed qualifiers and explicit applicability assertions in the selected process record'}


def _facet_evidence(draft,facet,indexed):
    """Bind the parent/dependency graph without recursively applying reuse again."""
    draft=ProcessKnowledgeDraft.model_validate(draft)
    ri=int(facet['parent_pointer'].split('/')[2]);record=draft.records[ri]
    terms={t.term_id:(i,t) for i,t in enumerate(record.terms)}
    claims={a.assertion_id:(i,a) for i,a in enumerate(record.assertions)}
    nodes=[];seen=set()
    def term(ref):
        i,t=terms[ref];pointer=f'/records/{ri}/terms/{i}'
        if pointer not in seen:
            seen.add(pointer);nodes.append((pointer,'scope_identity',t,t.evidence))
    def claim(ref):
        i,a=claims[ref];pointer=f'/records/{ri}/assertions/{i}'
        if pointer in seen:return
        seen.add(pointer)
        quotes=(*a.evidence,*(q for dim in ('conditions','exceptions','applicability') for f in getattr(a,dim) for q in f.evidence))
        nodes.append((pointer,'scope_parent',a,quotes))
        term(record.process_ref);term(a.subject_ref)
        for obj in a.object_refs:term(obj)
        for dep in a.depends_on:claim(dep)
    claim(facet['parent_assertion']['assertion_id'])
    return [{'target_pointer':p,'role':role,'value':value.model_dump(mode='json'),
        'source_bindings':[_source_binding(indexed,draft.source_revision_digest,q) for q in quotes]}
        for p,role,value,quotes in nodes]


def bind_scope_facets(use, *, draft, definition_asset, indexed):
    use=ProcessDefinitionUseV2.model_validate(use)
    prior=json.loads(definition_asset.content_json)['draft']
    inventories={'local':scope_facet_inventory(draft,use.term_pointer),
        'definition':scope_facet_inventory(prior,use.definition_node.node_pointer)}
    resolved=[]
    for comparison in use.scope_assessments:
        sides={}
        for side,inventory in inventories.items():
            facets={f['target_pointer']:f for f in inventory['facets'] if f['dimension']==comparison.dimension}
            decisions=getattr(comparison,side)
            if {d.target_pointer for d in decisions}!=set(facets):
                raise ValueError('PROCESS_REUSE_SCOPE_FACET_ACCOUNTING_INCOMPLETE:'+side+':'+comparison.dimension)
            sides[side]=[{'decision':d.model_dump(mode='json'),'facet':facets[d.target_pointer],
                'source_revision_digest':inventory['source_revision_digest'],
                'graph_evidence':_facet_evidence(draft if side=='local' else prior,facets[d.target_pointer],indexed)}
                for d in decisions]
        resolved.append({'dimension':comparison.dimension,'relation':comparison.projection().relation,
            'local':sides['local'],'definition':sides['definition'],
            'semantic_alignment':'model_proposed','selection_fidelity':'not_evaluated'})
    return {'contract_version':'boi/bound-process-reuse-scope@2','comparisons':resolved,
        'inventory_digests':{k:v['inventory_digest'] for k,v in inventories.items()},
        'scope_presence':'derived_from_explicit_facet_decisions','semantic_equivalence_proven':False}


def definition_inventory_with_scope(context):
    from agent_kit.python.boi_process_reuse import definition_node_inventory
    from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext
    context=TaskKnowledgeContext.model_validate(context)
    assets={a.revision.ref:a for a in context.assets}
    return [{**n,'scope_inventory':scope_facet_inventory(
        json.loads(assets[n['node_ref']['asset_revision']['ref']].content_json)['draft'],n['node_ref']['node_pointer'])}
        for n in definition_node_inventory(context)]
