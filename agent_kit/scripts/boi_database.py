#!/usr/bin/env python3
"""Portable, resumable DB evidence intake through the official HTTP/MCP API.

Private state is outside the package. This performs no semantic approval and
does not turn captured data into published knowledge by itself.
"""
import argparse
import base64
import json
import os
from pathlib import Path

from boi_knowledge_work import KnowledgeWorkClient, WorkError, digest, json_bytes

BASE = '/api/v2/domain-intake/native-queries/'


def save(path, value):
    raw=json_bytes(value)
    if path.exists():
        if path.read_bytes()!=raw:raise WorkError('DATABASE_STATE_CONFLICT')
        return
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())


def prepare_authoring_sources(output, pages):
    """Reuse captured server artifacts and exact spans in the existing assembler."""
    from boi_local import runtime
    runtime()
    from boi_api.app.governed_runtime.database_source_projection import database_fields
    from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
    from agent_kit.python.boi_source_inventory import write_inventory_bundle
    sources={}
    for entry in pages:
        page=json.loads((output/entry['file']).read_text())
        raw=base64.b64decode(page['source_bytes_b64'],validate=True)
        if digest(raw)!=page['source']['digest']:raise WorkError('DATABASE_SOURCE_BYTES_CHANGED')
        identity=Path(entry['file']).stem
        directory=output/(identity+'-authoring');directory.mkdir(exist_ok=True,mode=0o700)
        path=directory/'source.json'
        if path.exists() and path.read_bytes()!=raw:raise WorkError('DATABASE_SOURCE_BYTES_CHANGED')
        if not path.exists():
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as stream:stream.write(raw)
        fields=[{'field_locator':f.locator,'record_locator':f.record_locator,'role':'source',
            'role_reason':'Authorized DB source field','state':f.state,'value_kind':f.value_kind,
            'text':f.text,'text_digest':digest(f.text.encode()),'structural_metadata':f.structural_metadata}
            for f in database_fields(raw)]
        inventory={'contract_version':'boi/local-source-inventory@1','source_digest':digest(raw),'fields':fields,
            'role_record_counts':{'source':len(page['records'])},'role_field_counts':{'source':len(fields)}}
        inventory['inventory_digest']=semantic_digest(inventory)
        inv=directory/'inventory'
        if not inv.exists():write_inventory_bundle(inventory,inv)
        spans={f['field_locator']:{'span':{'ref':f['span_ref'],
            'revision_digest':'sha256:'+f['span_ref'].split('sha256:')[-1]},
            'source_revision_digest':page['source']['digest']} for r in page['records'] for f in r['fields']}
        sources[identity]={'path':str(path.resolve()),'inventory':str(inv.resolve()),
            'byte_digest':digest(raw),'media_type':'application/json','source_role':page['source']['role'],
            'existing_artifact':page['source'],'existing_field_spans':spans}
    save(output/'authoring-sources.json',sources)
    return sources


def capture_database(client, *, source_id, tables, output, page_size=100):
    output=Path(output);output.mkdir(parents=True,exist_ok=True,mode=0o700)
    schema=client._post(BASE+'source_schema',{'source_id':source_id})
    declared={t['name'] for t in schema['tables']}
    if not tables or len(tables)!=len(set(tables)) or not set(tables)<=declared:
        raise WorkError('DATABASE_TABLE_SELECTION_INVALID')
    state={'contract_version':'boi/database-intake-state@1','source_id':source_id,
           'endpoint':client.base_url,'snapshot_digest':schema['snapshot_digest'],
           'tables':tables,'page_size':page_size}
    # A new snapshot must use a new state directory; old work is never replaced.
    save(output/'state.json',state)
    save(output/'schema.json',schema)
    pages=[];records=[]
    for table_index,table in enumerate(tables):
        offset=0
        while offset is not None:
            request={'source_id':source_id,'table':table,'snapshot_digest':schema['snapshot_digest'],
                     'offset':offset,'limit':page_size}
            path=output/f'page-{table_index:03d}-{offset:010d}.json'
            # Re-read through current authorization even on resume. The server
            # preserves the same artifact/projection instead of creating another.
            page=client._post(BASE+'source_capture',request)
            if (page.get('source_id')!=source_id or page.get('table')!=table
                    or page.get('snapshot_digest')!=schema['snapshot_digest']
                    or page.get('offset')!=offset or page.get('record_count')!=len(page.get('records',[]))):
                raise WorkError('DATABASE_PAGE_BINDING_INVALID')
            nxt=page['next_offset']
            if nxt is not None and (type(nxt) is not int or nxt!=offset+page['record_count'] or nxt<=offset):
                raise WorkError('DATABASE_PAGE_CONTINUATION_INVALID')
            save(path,page)
            pages.append({'file':path.name,'digest':digest(path.read_bytes()),'source':page['source']})
            records.extend(page['records']);offset=nxt
    save(output/'source-records.json',records)
    prepare_authoring_sources(output,pages)
    scope={'contract_version':'boi/database-intake-scope@1','source_id':source_id,
           'snapshot_digest':schema['snapshot_digest'],'tables':tables,
           'sources':[p['source'] for p in pages], 'record_count':len(records),
           'identity_semantics':'source_records_not_business_entities'}
    save(output/'source-scope.json',scope)
    result={'contract_version':'boi/database-intake-result@1','scope':scope,'pages':pages,
            'complete':True,'semantic_preparation_complete':False,'publication_committed':False,
            'next_step':'Read admitted Profiles and run profile-prepare with source-records.json and source-scope.json.'}
    save(output/'result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default=os.environ.get('BOI_BASE_URL'))
    parser.add_argument('--source-id',required=True)
    parser.add_argument('--table',action='append',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--page-size',type=int,default=100,choices=range(1,1001),metavar='1..1000')
    args=parser.parse_args()
    client=KnowledgeWorkClient(args.base_url,os.environ.get('BOI_PAT',''))
    result=capture_database(client,source_id=args.source_id,tables=args.table,
                            output=args.output_dir,page_size=args.page_size)
    print(json.dumps({'complete':result['complete'],'record_count':result['scope']['record_count'],
        'output_dir':str(args.output_dir),'next_step':result['next_step']},ensure_ascii=False))


if __name__=='__main__':main()
