"""Synthetic helper closure for focused MCP release validation."""
import copy


from agent_kit.python.boi_process_lint import bind_process_meaning


from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


from tests.test_process_knowledge import sample


def material(sample):
    import json
    bound=bind_process_meaning(sample['draft'],evidence=sample['evidence'],extraction_context=sample['context'])
    revision={'ref':'sample:meaning','revision_digest':semantic_digest(bound)}
    asset={'revision':revision,'kind':'definition','content_json':json.dumps(bound),'content_digest':semantic_digest(bound),
        'authority':'candidate','dependencies':[],'evidence':[],'conflicts_with':[],'supersedes':[]}
    context=sample['context'].model_dump(mode='json',exclude={'context_digest'})
    context['assets']=[asset]
    context['selections']=[{'parent':None,'requirement':{'revision':revision,'role':'existing_definition',
        'reason':'Read meaning for the answer.','stages':['explain'],'required':True},'status':'selected','reason_code':None}]
    context['context_digest']=semantic_digest(context)
    draft={'context_digest':context['context_digest'],'answers':[{'question_id':'q','sentences':[
        {'text':'필름을 도포한다.','kind':'source_reported_fact','citations':[
            {'asset_revision':copy.deepcopy(revision),'target_pointer':'/records/0/assertions/0'}]}]}]}
    return context,draft,[{'id':'q','question':'What is applied?','max_body_characters':400}]
