"""Synthetic helper closure for focused MCP release validation."""
from agent_kit.python.boi_source_inventory import inventory_workbook, write_inventory_bundle


from boi_api.app.governed_runtime.source_envelope import byte_digest


from tests.test_local_source_inventory import layout


from tests.test_spreadsheet_source_projection import workbook


def spec(tmp_path):
    raw=workbook();source=tmp_path/'source.xlsx';source.write_bytes(raw)
    inventory=tmp_path/'inventory';write_inventory_bundle(inventory_workbook(raw,layout(raw)),inventory)
    statement='The source contains a decimal string.'
    quote='0.1234567890123456789'
    return {'namespace':'local-example','profile_logical_id':'measurement-profile','title':'Locally authored reading',
        'description':'Synthetic local data and explicit author opinion, no publication.','author_session_ref':'synthetic-author',
        'sources':{'workbook':{'path':str(source),'inventory':str(inventory),'byte_digest':byte_digest(raw),
            'media_type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','source_role':'corporate_metadata'}},
        'profile':{'profile_id':'measurement','schema_ref':'measurement@1','label':'Measurement description',
            'description':'Explicit opaque source value, not a qualified quantity',
            'components':[{'kind':'object_type','id':'reading','label':'Reading','description':'Source reading'},
                {'kind':'predicate','id':'original','label':'Original text','description':'No numeric interpretation',
                    'subject_type':{'component_id':'reading'},'value_kind':'text','role':'original_text',
                    'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'one',
                    'allowed_operators':['eq','ne']}]},
        'records':[{'object_id':'reading','logical_id':'reading-A2','source_object_id':'workbook',
            'source_record_locator':'/sheets/raw/rows/2','object_type_id':'reading','title':'Raw reading',
            'description':'Retained exact decimal text','frontmatter':{'okf_version':'0.2','type':'reading'},
            'body':statement+'\n\n@local:knowledge_revision:literal-body-text',
            'assertions':[{'id':'original','predicate_id':'original','value':{'kind':'text','value':quote},
                'statement':statement,'assertion_kind':'source_reported','polarity':'positive','modality':'asserted',
                'conditions':[],'exceptions':[],'applicability':[],'valid_time':{'state':'unknown'},
                'depends_on':[],'uncertainties':['unit not declared'],
                'evidence':[{'field_locator':'/sheets/raw/cells/A2','quote':quote}]}],
            'unresolved':[],'use_contracts':[{'purpose':'explain','required_meaning_pointers':['/assertions/0']}],
            'coverage_disposition':{'status':'partial'}}],
        'intended_uses':['read','explain'],'unresolved':['Synthetic test only']}


def assessment(value,label='unsupported'):
    return {'target_object_id':'reading','agent_session_ref':'synthetic-author',
        'reported_reviewer_relationship':'same_session','uses':[{'purpose':'explain',
            'requested_pointers':['/assertions/0'],'limitations':['No scientific validation'],
            'judgments':[{'pointer':'/assertions/0','label':label,'reason':'Explicit synthetic opinion retained unchanged',
                'evidence':[{'source_object_id':'workbook','source_byte_digest':value['sources']['workbook']['byte_digest'],
                    'field_locator':'/sheets/raw/cells/A2','quote':'0.1234567890123456789','quote_occurrence':0}]}]}]}
