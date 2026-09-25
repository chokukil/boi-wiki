"""Synthetic helper closure for focused MCP release validation."""
import json


from agent_kit.python.boi_source_inventory import inventory_workbook,write_inventory_bundle


from tests.test_local_knowledge_draft import spec


from tests.test_local_source_inventory import layout


def context_spec(tmp_path):
    value=spec(tmp_path);raw=(tmp_path/'source.xlsx').read_bytes();regions=layout(raw)
    regions['regions'][0]['columns']=['A']
    regions['regions'].append({'sheet':'raw','first_row':1,'last_row':1,'columns':['B'],
        'role':'review_note','reason':'Synthetic surrounding note role, explicitly selected'})
    inventory=tmp_path/'context-inventory'
    write_inventory_bundle(inventory_workbook(raw,regions),inventory)
    value['sources']['workbook']['inventory']=str(inventory)
    record=value['records'][0];record['context_fields']=[]
    for column,role in [('A','metadata'),('B','review_note')]:
        locator=f'/sheets/raw/cells/{column}1'
        field=next(json.loads(line) for line in (inventory/(role+'.jsonl')).read_text().splitlines()
            if json.loads(line)['field_locator']==locator)
        record['context_fields'].append({'field_locator':locator,'role':role,'reason':'Explicit surrounding source context'})
        record['assertions'][0]['evidence'].append({'field_locator':locator,'quote':field['text']})
    return value
