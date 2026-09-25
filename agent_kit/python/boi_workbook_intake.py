"""Reusable native workbook preservation through the existing BoI MCP intake.

Registers every source row in bounded source assets, with exact evidence refs.
It never chooses a domain, normalizes a unit or approves an interpretation.
The caller's existing domain harness consumes these source assets afterwards.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path

from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.spreadsheet_source_projection import workbook_fields
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


def workbook_records(raw,manifest):
    """Verify host decoding against server-owned field identities before indexing."""
    fields=workbook_fields(raw)
    indexed={f['field_locator']:f for f in manifest['fields']}
    if len(indexed)!=len(fields):raise ValueError('WORKBOOK_FIELD_INVENTORY_MISMATCH')
    records={}
    for field in fields:
        stored=indexed.get(field.locator)
        if (stored is None or stored['content_digest']!=byte_digest(field.text.encode())
                or stored['field_state']!=field.state or stored['value_kind']!=field.value_kind
                or stored.get('structural_metadata')!=field.structural_metadata):
            raise ValueError('WORKBOOK_FIELD_PROJECTION_MISMATCH')
        record=records.setdefault(field.record_locator,{'record_locator':field.record_locator,'fields':[]})
        record['fields'].append({**stored,'text':field.text})
    return list(records.values())


def source_batches(records,max_characters=48000):
    """Partition complete source records by transport size, not business meaning."""
    batch=[];size=0
    for record in records:
        length=len(json.dumps(record,ensure_ascii=False))
        if length>max_characters:
            if batch:yield batch;batch=[];size=0
            # A large original row is kept intact; source readers remain paged.
            yield [record];continue
        if batch and size+length>max_characters:yield batch;batch=[];size=0
        batch.append(record);size+=length
    if batch:yield batch


async def publish_workbook_index(client,*,file_name,namespace,source,manifest,records,assets):
    batches=list(source_batches(records))
    if len(batches)!=len(assets):raise ValueError('WORKBOOK_INDEX_BATCH_COVERAGE_MISMATCH')
    sheets={}
    for record in records:
        for field in record['fields']:
            metadata=field.get('structural_metadata')
            if metadata:
                sheet=sheets.setdefault(metadata['sheet'],{'sheet':metadata['sheet'],'row_count':0,'cell_count':0})
                sheet['row_count']=max(sheet['row_count'],metadata['excel_row']);sheet['cell_count']+=1
    content={'contract_version':'boi/workbook-source-index@1','file_name':file_name,
        'source':source,'manifest_ref':manifest['manifest_ref'],'sheets':list(sheets.values()),
        'record_count':len(records),'field_count':manifest['field_count'],
        'parts':[{'revision':ref,'first_record':batch[0]['record_locator'],
            'last_record':batch[-1]['record_locator'],'record_count':len(batch)} for ref,batch in zip(assets,batches)],
        'scope':'Complete source inventory. All sheets, including guides and correction ledgers, '
            'are preserved. No inferred cell value is automatically verified; domain interpretation remains separate.'}
    draft={'logical_id':'workbook-index:'+source['digest'],'namespace':namespace,
        'kind':'source','title':file_name+' · 전체 시트와 원문 위치',
        'description':'원본 파일·시트·셀·자료형·보완 이력의 전체 적재 인덱스. 업무 의미와 실행 바인딩은 별도 검토.',
        'content_json':json.dumps(content,ensure_ascii=False),'sources':[source],
        'dependencies':[{'revision':ref,'role':'source_inventory_part','reason':'Exact preserved source records.',
            'stages':['explain'],'required':False} for ref in assets]}
    return await client.propose_asset(draft,idempotency_key='workbook-index:'+semantic_digest(draft))


async def intake_workbook(client,*,path,namespace,output_dir):
    path=Path(path);out=Path(output_dir);out.mkdir(parents=True,exist_ok=True)
    raw=path.read_bytes();digest=byte_digest(raw)
    def save(name,value):
        target=out/name;encoded=json.dumps(value,ensure_ascii=False,indent=2)
        if target.exists():
            prior=json.loads(target.read_text())
            # Idempotent replay changes only this transport observation. Keep
            # the original publication response, including its first-run flag.
            compare=lambda item:{k:v for k,v in item.items() if k!='replayed'} if isinstance(item,dict) else item
            if compare(prior)!=compare(value):raise ValueError('WORKBOOK_INTAKE_RECORD_CONFLICT')
        else:target.write_text(encoded)
    original=out/path.name
    if original.exists() and original.read_bytes()!=raw:raise ValueError('WORKBOOK_ORIGINAL_CONFLICT')
    if not original.exists():original.write_bytes(raw)
    source=await client.capture_file(path,role='corporate_metadata',idempotency_key='workbook:'+digest)
    save('source.json',source)
    existing_manifest=(json.loads((out/'manifest.json').read_text()) if (out/'manifest.json').exists() else None)
    manifest=await client.project(source,**({'manifest_ref':existing_manifest['manifest_ref']} if existing_manifest else {}))
    save('manifest.json',manifest)
    records=workbook_records(raw,manifest)
    save('source-records.json',records)
    saved=[]
    for index,batch in enumerate(source_batches(records)):
        content={'contract_version':'boi/workbook-source-records@1','file_name':path.name,
            'workbook_digest':digest,'manifest_ref':manifest['manifest_ref'],
            'records':batch,'interpretation_status':'not_interpreted',
            'scope':'Original cell values and annotations, not verified domain definitions. '
                'Rows and styles are source locations, not business relationships. '
                'Other source batches in this workbook retain guides and correction history.'}
        identity=semantic_digest({'namespace':namespace,'source':source,'records':[r['record_locator'] for r in batch]})
        draft={'logical_id':'workbook-source:'+identity,'namespace':namespace,'kind':'source',
            'title':path.name+' · '+batch[0]['record_locator']+' … '+batch[-1]['record_locator'],
            'description':'원문 셀·자료형·위치 보존. 업무 의미 미해석; 같은 파일의 안내·보완내역과 함께 확인.',
            'content_json':json.dumps(content,ensure_ascii=False),'sources':[source],
            'evidence_spans':[{'ref':f['span_ref'],'revision_digest':'sha256:'+f['span_ref'].rsplit(':',1)[-1]}
                for r in batch for f in r['fields']]}
        prior_draft=out/f'asset-{index:04d}-draft.json'
        if prior_draft.exists():
            preserved=json.loads(prior_draft.read_text())
            # A restored ledger projection may order JSON object keys
            # differently. Compare every value, then retain the first serialized
            # draft and its idempotency key rather than issuing another revision.
            comparable=lambda d:{**d,'content_json':json.loads(d['content_json'])}
            if comparable(preserved)!=comparable(draft):raise ValueError('WORKBOOK_INTAKE_RECORD_CONFLICT')
            draft=preserved
        save(f'asset-{index:04d}-draft.json',draft)
        result=await client.propose_asset(draft,idempotency_key='workbook-source:'+semantic_digest(draft))
        save(f'asset-{index:04d}-saved.json',result);saved.append(result)
        print(json.dumps({'source_batch':index+1,'records_stored':len(batch),'revision':result['revision']},ensure_ascii=False),flush=True)
    index=await publish_workbook_index(client,file_name=path.name,namespace=namespace,source=source,
        manifest=manifest,records=records,assets=[v['revision'] for v in saved])
    save('index-saved.json',index)
    result={'source':source,'source_index_revision':index['revision'],'file_name':path.name,'field_count':manifest['field_count'],
        'record_count':len(records),'assets':[v['revision'] for v in saved],
        'source_preserved':True,'domain_interpretation_complete':False,'model_calls':0}
    outcome_name='outcome.json'
    if (out/'outcome.json').exists() and json.loads((out/'outcome.json').read_text())!=result:
        outcome_name='outcome-'+semantic_digest(result).removeprefix('sha256:')+'.json'
    save(outcome_name,result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path);parser.add_argument('--namespace',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--mcp-url',required=True)
    args=parser.parse_args()
    async def run():
        from .boi_domain_mcp import connect
        async with connect(args.mcp_url,os.environ['BOI_MCP_TOKEN']) as client:
            return await intake_workbook(client,path=args.path,namespace=args.namespace,output_dir=args.output_dir)
    print(json.dumps(asyncio.run(run()),ensure_ascii=False))


if __name__=='__main__':main()
