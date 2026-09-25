"""Synthetic helper closure for focused MCP release validation."""
import copy


import json


from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


from tests.test_process_answer_v2 import inputs


from tests.test_process_knowledge import sample


def native_inputs(sample, contract='external/science-profile@1'):
    draft, args = inputs(sample)
    source = args['sources'][0]
    field = next(f for f in source['fields'] if f['field_locator']=='/description')
    evidence = {'source_revision_digest':source['source']['digest'], 'span_ref':field['span_ref'],
                'field_locator':field['field_locator'], 'quote':field['text']}
    content = {'contract_version':contract, 'claims':[
        {'statement':'Coating applies film.', 'conditions':['recorded operation'], 'evidence':[evidence]},
        {'statement':'Voids may form.', 'conditions':['cold'], 'evidence':[copy.deepcopy(evidence)]}]}
    asset = args['context']['assets'][0]
    asset.update(content_json=json.dumps(content), content_digest=semantic_digest(content))
    args['context']['context_digest'] = semantic_digest({k:v for k,v in args['context'].items() if k!='context_digest'})
    draft['context_digest'] = args['context']['context_digest']
    draft['answers'][0]['sentences'][0]['citations'][0]['target_pointer'] = '/claims/0'
    return draft, args
