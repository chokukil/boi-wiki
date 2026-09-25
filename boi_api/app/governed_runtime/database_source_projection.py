"""Pure DB page projection shared by the server and installed authoring kit."""
import json
from decimal import Decimal
from .source_field_value import ProjectedField, _pointer
from .semantic_binding_contract import semantic_digest


def database_fields(raw):
    def unique(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('DATABASE_PAGE_DUPLICATE_KEY')
            result[key]=value
        return result
    page=json.loads(raw,parse_float=Decimal,object_pairs_hook=unique)
    if page.get('contract_version')!='boi/database-source-page@1':
        raise ValueError('DATABASE_PAGE_CONTRACT_REQUIRED')
    names=[c['name'] for c in page['schema']['columns']]
    if len(names)!=len(set(names)) or page['schema']['name']!=page['table']:
        raise ValueError('DATABASE_PAGE_SCHEMA_INVALID')
    fields=[]
    def walk(value,path,record,metadata):
        if isinstance(value,dict) and value:
            for key,child in value.items():walk(child,[*path,key],record,metadata)
            return
        if value is None:kind,text,state='null','null','null'
        elif isinstance(value,bool):kind,text,state='boolean',str(value).lower(),'present'
        elif isinstance(value,(int,Decimal)):
            if not Decimal(value).is_finite():raise ValueError('DATABASE_PAGE_NONFINITE')
            kind,text,state='number',str(value),'present'
        elif isinstance(value,str):kind,text,state='string',value,'empty' if value=='' else 'present'
        else:raise ValueError('DATABASE_PAGE_VALUE_INVALID')
        fields.append(ProjectedField(_pointer(path),record,state,kind,text,
            structural_metadata={**metadata,'database_value_path':_pointer(path[3:])[1:]}))
    for index,row in enumerate(page['rows']):
        if row['ordinal']!=page['offset']+index or set(row['values'])!=set(names):
            raise ValueError('DATABASE_PAGE_ROW_INVALID')
        record=semantic_digest([page['source_id'],page['snapshot_digest'],page['table'],row['ordinal']])
        for column in names:
            walk(row['values'][column],['rows',index,'values',column],record,{
                'database_source':page['source_id'],'database_table':page['table'],
                'database_column':column,'database_snapshot':page['snapshot_digest'],
                'database_ordinal':row['ordinal']})
    return tuple(fields)
