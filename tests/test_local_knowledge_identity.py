"""Synthetic helper closure for focused MCP release validation."""
from copy import deepcopy


from tests.test_local_knowledge_draft import spec


def graph_spec(tmp_path):
    value=spec(tmp_path)
    components=value['profile']['components']
    components.append({'kind':'predicate','id':'peer','label':'Related reading','description':'Explicit synthetic link',
        'subject_type':{'component_id':'reading'},'target_type':{'component_id':'reading'},'value_kind':'object',
        'role':'peer','quantity_semantics':'not_applicable','value_semantics':'not_applicable',
        'cardinality':'many','allowed_operators':['eq','ne']})
    first=value['records'][0];second=deepcopy(first)
    second.update(object_id='second',logical_id='another-reading',title='Another reading')
    for record,target in ((first,'second'),(second,'reading')):
        link=deepcopy(record['assertions'][0]);link.update(id='peer',predicate_id='peer',
            value={'kind':'object','target_object_id':target},statement='A synthetic relation is declared.',
            assertion_kind='interpretation')
        link['conditions']=[{'statement':'The other record has this exact text.',
            'evidence':deepcopy(link['evidence']),
            'atoms':[{'subject_object_id':target,'predicate_id':'original','operator':'eq',
                      'value':deepcopy(record['assertions'][0]['value'])}],
            'expression':{'operator':'filter','filter_index':0}}]
        record['body']+='\n'+link['statement'];record['assertions'].append(link)
    value['records'].append(second)
    return value
