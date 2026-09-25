"""Installed kit + real HTTP MCP. Authored fixture opinions are not model evaluation."""
import asyncio
from copy import deepcopy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import threading
import time

import pytest
import uvicorn

from tests.test_domain_intake_transport import transport, v2_service, principal
from tests.test_local_bundle_hotl import hotl_client, admission
from tests.test_local_bundle_transport import upload_url
from tests.test_domain_kit_install import KIT, load_installer
from examples.database.generate import generate


def authored_spec(sources, page, *, namespace, field_name, label):
    source_id=next(k for k,v in sources.items() if v['existing_artifact']==page['source'])
    row=page['records'][0]
    f=next(f for f in row['fields'] if f['structural_metadata']['database_column']==field_name)
    quote=f['text']
    return {'namespace':namespace,'profile_logical_id':'profile','title':label,
        'description':'Generated DB protocol example','author_session_ref':'synthetic-test-author',
        'sources':{source_id:sources[source_id]},'profile':{
            'profile_id':namespace,'schema_ref':namespace+'@1','label':label,'description':'Source reported field',
            'components':[{'kind':'object_type','id':'record','label':'Record','description':'Source record'},
                {'kind':'predicate','id':'statement','label':label,'description':'Original source text',
                 'subject_type':{'component_id':'record'},'value_kind':'text','role':'source_description',
                 'quantity_semantics':'not_applicable','value_semantics':'not_applicable','cardinality':'one','allowed_operators':['eq','ne']}]},
        'records':[{'object_id':'record','logical_id':'record','source_object_id':source_id,
            'source_record_locator':row['record_locator'],'object_type_id':'record','title':label,
            'description':'Source reported field','frontmatter':{'okf_version':'0.2','type':'source-record'},'body':quote,
            'assertions':[{'id':'statement','predicate_id':'statement','value':{'kind':'text','value':quote},
                'statement':quote,'assertion_kind':'source_reported','polarity':'positive','modality':'asserted',
                'conditions':[],'exceptions':[],'applicability':[],'valid_time':{'state':'unknown'},'depends_on':[],
                'uncertainties':[],'evidence':[{'field_locator':f['field_locator'],'quote':quote}]}],
            'unresolved':[],'use_contracts':[{'purpose':'explain','required_meaning_pointers':['/assertions/0']}],
            'coverage_disposition':{'status':'partial'}}],
        'intended_uses':['read','explain'],'unresolved':[],
        'assessments':[{'target_object_id':'record','agent_session_ref':'synthetic-test-author',
            'reported_reviewer_relationship':'same_session','uses':[{'purpose':'explain','requested_pointers':['/assertions/0'],
                'limitations':['Synthetic fixture source fidelity; no independent model evaluation.'],
                'judgments':[{'pointer':'/assertions/0','label':'supported','reason':'Exact original field retained verbatim',
                    'evidence':[{'source_object_id':source_id,'source_byte_digest':page['source']['digest'],
                        'field_locator':f['field_locator'],'quote':quote,'quote_occurrence':0}]}]}]}]}


def add_source_fields(spec,page,columns):
    """Explicit authored fixture claims preserve role/value/condition columns separately."""
    record=spec['records'][0];profile=spec['profile'];use=record['use_contracts'][0]
    opinion=spec['assessments'][0]['uses'][0]
    for column in columns:
        field=next(f for f in page['records'][0]['fields'] if f['structural_metadata']['database_column']==column)
        if field['field_state'] in ('null','empty'):
            record['unresolved'].append({'reason_code':'source_blank','description':column+' 원천 필드는 공란이다.'})
            continue
        index=len(record['assertions']);predicate=deepcopy(profile['components'][1])
        predicate.update(id=column,label=column,role='original_field')
        profile['components'].append(predicate)
        assertion=deepcopy(record['assertions'][0]);assertion.update(id=column,predicate_id=column,
            value={'kind':'text','value':field['text']},statement=column+': '+field['text'],
            evidence=[{'field_locator':field['field_locator'],'quote':field['text']}])
        record['assertions'].append(assertion);record['body']+='\n'+assertion['statement']
        pointer='/assertions/'+str(index);use['required_meaning_pointers'].append(pointer)
        opinion['requested_pointers'].append(pointer)
        judgment=deepcopy(opinion['judgments'][0]);judgment['pointer']=pointer
        judgment['evidence'][0].update(field_locator=field['field_locator'],quote=field['text'])
        opinion['judgments'].append(judgment)
    return spec


def authored_relations(sources,pages):
    """Explicit fixture interpretation: stored route rows point to component records."""
    from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
    components=[p for p in pages if p['table']=='components']
    routes=[p for p in pages if p['table']=='route_steps']
    spec=authored_spec(sources,components[0],namespace='synthetic-relations',field_name='label',label='모듈 공정 연결')
    spec['sources']=sources
    spec['records']=[];spec['assessments']=[];spec['intended_uses']=['read','explain','traverse']
    profile=spec['profile']
    profile['components'].append({'kind':'predicate','id':'component','label':'연결된 모듈',
        'description':'Stored route row refers to its declared component key',
        'subject_type':{'component_id':'record'},'target_type':{'component_id':'record'},
        'value_kind':'object','role':'component_link','quantity_semantics':'not_applicable',
        'value_semantics':'not_applicable','cardinality':'one','allowed_operators':['eq','ne']})
    targets={}
    for index,(page,row) in enumerate((p,r) for p in components for r in p['records']):
        one=authored_spec(sources,{**page,'records':[row]},namespace=spec['namespace'],field_name='label',label='모듈')
        record=one['records'][0];identity='module-'+str(index)
        record.update(object_id=identity,logical_id=identity,title=record['body'])
        key=next(f['text'] for f in row['fields'] if f['structural_metadata']['database_column']=='component_key')
        targets[key]=identity
        spec['records'].append(record)
        opinion=one['assessments'][0];opinion['target_object_id']=identity;spec['assessments'].append(opinion)
    for index,(page,row) in enumerate((p,r) for p in routes for r in p['records']):
        one=authored_spec(sources,{**page,'records':[row]},namespace=spec['namespace'],field_name='component_key',label='연결 행')
        record=one['records'][0];identity='route-'+str(index)
        record.update(object_id=identity,logical_id=identity,title='연결 행 '+str(index+1))
        record['assertions'][0].update(predicate_id='component',value={'kind':'object','target_object_id':targets[record['body']]})
        record['use_contracts']=[{'purpose':'traverse','required_meaning_pointers':['/assertions/0/value']}]
        spec['records'].append(record)
        opinion=one['assessments'][0];opinion['target_object_id']=identity
        use=opinion['uses'][0];use.update(purpose='traverse',requested_pointers=['/assertions/0/value'])
        use['statement_review']={'contract_version':'boi/source-relation-review@1',
            'claim_basis':'reported_statement_exists','inventory_digest':semantic_digest([]),'items':[]}
        spec['assessments'].append(opinion)
    return spec


@pytest.mark.skipif(not os.environ.get("BOI_RELEASE_TEST_PG_DSN"),reason="Isolated PostgreSQL required for real correction impact fences")
@pytest.mark.asyncio
async def test_installed_db_capture_publish_fresh_mcp_read(transport,principal,monkeypatch,tmp_path):
    client,source,service,_=hotl_client(transport,principal)
    source.current_source_policy=lambda:'sha256:'+'a'*64
    path=generate(tmp_path/'generated.sqlite',variant=47)
    registry=tmp_path/'sources.json'
    registry.write_text(json.dumps({'sources':[{'source_id':'synthetic-new-db','title':'Generated example',
        'principals':[principal.employee_id],'allowed_tables':['procedures','telemetry','components','route_steps'],
        'sqlite_path':str(path)}]}))
    monkeypatch.setenv('BOI_DATABASE_SOURCES_PATH',str(registry))
    target=tmp_path/'installed';load_installer().install(KIT,target,'codex')
    installed=importlib.util.spec_from_file_location('installed_mcp',target/'scripts/boi_mcp.py')
    module=importlib.util.module_from_spec(installed);installed.loader.exec_module(module)
    mcp=importlib.reload(importlib.import_module('boi_wiki_mcp.app.v2'))
    running=[]
    def start(app):
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen()
        server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,loop='asyncio',ws='none'))
        thread=threading.Thread(target=lambda:server.run(sockets=[sock]),daemon=True)
        running.append((server,thread,sock));thread.start()
        return server,f'http://127.0.0.1:{sock.getsockname()[1]}'
    async def ready(server):
        until=time.monotonic()+10
        while not server.started and time.monotonic()<until:await asyncio.sleep(.02)
        assert server.started
    async def command(*args,**env):
        proc=await asyncio.create_subprocess_exec(sys.executable,*map(str,args),cwd=tmp_path,
            env={**os.environ,'PYTHONPATH':'/absent',**env},stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await proc.communicate()
        assert proc.returncode==0,(stdout.decode(),stderr.decode())
        return stdout.decode()
    try:
        api,api_url=start(client.app);await ready(api)
        monkeypatch.setattr(mcp,'BOI_API_URL',api_url);monkeypatch.setattr(mcp,'BOI_API_PAT','')
        monkeypatch.setattr(mcp,'MCP_V2_REQUIRE_PAT',True)
        app=mcp.mcp_v2_http_app();app.add_middleware(mcp.McpV2AuthContextMiddleware)
        server,url=start(app);await ready(server)
        token=client.headers['authorization'].removeprefix('Bearer ')
        async with module.connect(url+'/mcp/v2',token) as agent:
            discovery=await agent.call('boi_native_query',{'action':'source_discover'})
            assert discovery['sources'][0]['tables']==['procedures','telemetry','components','route_steps']
            assert 'sqlite_path' not in str(discovery) and 'restricted_notes' not in str(discovery)
            schema=await agent.call('boi_native_query',{'action':'source_schema','request':{'source_id':'synthetic-new-db'}})
            request={'source_id':'synthetic-new-db','table':'procedures','snapshot_digest':schema['snapshot_digest']}
            page=await agent.call('boi_native_query',{'action':'source_capture','request':request})
            assert page['records'][0]['fields']
        state=tmp_path/'intake'
        args=[target/'scripts/boi_database.py','--base-url',api_url,'--source-id','synthetic-new-db',
            '--table','procedures','--table','telemetry','--table','components','--table','route_steps','--output-dir',state,'--page-size','2']
        await command(*args,BOI_PAT=token)
        count=source.ledger.verify().record_count
        await command(*args,BOI_PAT=token)
        assert source.ledger.verify().record_count==count
        sources=json.loads((state/'authoring-sources.json').read_text())
        async def publish_spec(spec,tag):
            spec_file=tmp_path/(tag+'-spec.json');spec_file.write_text(json.dumps(spec,ensure_ascii=False))
            bundle=tmp_path/(tag+'-bundle')
            await command(target/'scripts/boi_local.py','assemble','--spec',spec_file,'--output',bundle)
            manifest=json.loads((bundle/'manifest.json').read_text())
            async with module.connect(url+'/mcp/v2',token) as agent:
                async def phase(name,payload):
                    try:return await agent.knowledge_work('publication',{'phase':name,'payload':payload})
                    except module.BoiMcpToolError as exc:raise AssertionError((name,exc.reason_code)) from None
                value=await phase('preview',{'manifest':manifest,'idempotency_key':tag})
                impact=await phase('impact',{'bundle_ref':value['bundle_ref'],'preview_digest':value['preview_digest']})
                await phase('admit',admission(value,impact_ref=impact['impact_ref']))
                for obj in manifest['objects']:
                    raw=(bundle/(obj['object_id']+'.blob')).read_bytes()
                    response=client.put(upload_url(value,obj['object_id']),content=raw,headers={
                        'Content-Type':'application/octet-stream','X-Boi-Chunk-Digest':obj['byte_digest']})
                    assert response.status_code==200,response.text
                for name in ('prepare','validate'):
                    for _ in range(10):
                        result=await phase(name,{'bundle_ref':value['bundle_ref'],'limit':10})
                        if not result['state'].endswith('_partial'):break
                    else:raise AssertionError('Preparation did not finish its bounded work')
                for obj in manifest['objects']:
                    if obj['purpose']=='check_evidence':
                        qualification=await phase('qualify',{'bundle_ref':value['bundle_ref'],'assessment_object_id':obj['object_id']})
                        assert all(use['status']=='usable_with_limits' for use in qualification['uses']),qualification
                for unit in value['preview']['publication_plan']['units']:
                    payload={'bundle_ref':value['bundle_ref'],'unit_id':unit['unit_id']}
                    preflight=await phase('preflight',payload)
                    result=await phase('publish',{**payload,'publication_digest':preflight['publication_digest']})
                    assert result['publication_committed']
        published=[]
        for index,(table,field,label) in enumerate([('procedures','condition','OPER 수행 조건'),
                ('telemetry','range_note','SVID 범위 설명'),('components','label','DEXA 객체 설명')]):
            page=json.loads(next(state.glob(f'page-{index:03d}-*.json')).read_text())
            spec=authored_spec(sources,page,namespace='synthetic-'+table,field_name=field,label=label)
            if table=='procedures':add_source_fields(spec,page,['purpose','checkpoint','procedure_key'])
            elif table=='telemetry':add_source_fields(spec,page,['signal_key','equipment','role','unit','value','lower_limit','upper_limit'])
            await publish_spec(spec,table)
            published.append((spec['namespace'],[a['statement'] for a in spec['records'][0]['assertions']]))
        # New HTTP sessions discover current revisions themselves; no revision/answer pointers passed in.
        documents={}
        for namespace,expected in published:
            async with module.connect(url+'/mcp/v2',token) as fresh:
                question={'synthetic-procedures':'RINSE-47 수행 조건 목적 관리점',
                    'synthetic-telemetry':'ORBIT-47 범위 설명',
                    'synthetic-components':'DEXA 객체 설명'}[namespace]
                catalog=await fresh.call('boi_knowledge_catalog',{'query':question,'kind':'definition',
                    'text_match_mode':'ranked_candidates'})
                assert catalog['items'],catalog
                item=catalog['items'][0]
                document=await fresh.call('boi_knowledge_read',{'revision':item['revision'],'view':'document','document_options':{'include_source_labels':True}})
                assert document['is_current_revision'] and document['claims'],document
                assert all(part in json.dumps(document,ensure_ascii=False) for part in expected)
                assert document['claims'][0]['source_bindings']
                documents[namespace]=(item,document)
                # Actual final renderer consumes the current MCP result, never fixture text.
                from agent_kit.python.boi_ontology_query_host import published_claim_selection_catalog, validate_published_claim_part_map, published_answer_contract
                journal=[{'step':0,'tool':'boi_knowledge_read','result':document,'error':None}]
                candidates=published_claim_selection_catalog(journal,[0])
                question='원천 설명을 알려줘'
                selected=validate_published_claim_part_map({'request_parts':[{'question_quote':'원천 설명','evidence_indexes':[item['index'] for item in candidates]}],
                    'unresolved_request_quotes':[]},question,candidates,required_quotes=['원천 설명'])
                answer=published_answer_contract(journal,selected)
                assert all(part in answer['answer'] for part in expected) and answer['evidence']
        relation_spec=authored_relations(sources,[json.loads(p.read_text()) for p in sorted(state.glob('page-*.json'))])
        await publish_spec(relation_spec,'relations')
        async with module.connect(url+'/mcp/v2',token) as fresh:
            catalog=await fresh.call('boi_knowledge_catalog',{'namespace':'synthetic-relations','kind':'definition','limit':100})
            assert len(catalog['items'])==4, catalog  # Two stored duplicate links, two modules including an unlinked module.
            profiles=await fresh.call('boi_knowledge_catalog',{'namespace':'synthetic-relations','kind':'profile'})
            predicate={'revision':profiles['items'][0]['revision'],'pointer':'/components/2'}
            edges=[];module_revisions=[]
            for item in catalog['items']:
                if item['title'].startswith('연결 행'):
                    result=await fresh.call('boi_knowledge_query',{'operation':'traverse','request':{
                        'start_revision':item['revision'],'predicates':[predicate],'max_depth':1}})
                    assert result['status']=='completed',result
                    assert len(result['edges'])==1,result
                    edges.extend(result['edges'])
                else:module_revisions.append(item['revision'])
            assert len(edges)==2 and len(module_revisions)==2
            assert edges[0]!=edges[1]  # Identical source values do not merge stored rows.
        previous=documents['synthetic-procedures']
        with sqlite3.connect(path) as db:
            db.execute('UPDATE procedures SET condition=?',('덮개 온도가 28 C 미만일 때 수행한다.',))
        changed=tmp_path/'changed-intake'
        await command(target/'scripts/boi_database.py','--base-url',api_url,'--source-id','synthetic-new-db',
            '--table','procedures','--output-dir',changed,BOI_PAT=token)
        new_sources=json.loads((changed/'authoring-sources.json').read_text())
        new_page=json.loads(next(changed.glob('page-000-*.json')).read_text())
        spec=authored_spec(new_sources,new_page,namespace='synthetic-procedures',field_name='condition',label='OPER 수행 조건')
        async with module.connect(url+'/mcp/v2',token) as fresh:
            profiles=await fresh.call('boi_knowledge_catalog',{'namespace':'synthetic-procedures','kind':'profile'})
        add_source_fields(spec,new_page,['purpose','checkpoint','procedure_key'])
        spec['existing_profile_revision']=profiles['items'][0]['revision']
        record=spec['records'][0]
        record['previous_revision']=previous[0]['revision']
        record['correction']={'expected_policy_revision':previous[1]['policy_revision'],
            'reason':'원천 DB의 수행 조건 변경','source_difference':'온도 조건이 35 C 미만에서 28 C 미만으로 변경됨'}
        record['existing_sources']=[v['existing_artifact'] for v in sources.values() if 'procedures' in Path(v['path']).read_text()]
        await publish_spec(spec,'corrected-procedures')
        async with module.connect(url+'/mcp/v2',token) as fresh:
            current=await fresh.call('boi_knowledge_catalog',{'namespace':'synthetic-procedures','kind':'definition'})
            assert current['items'][0]['revision']!=previous[0]['revision']
            doc=await fresh.call('boi_knowledge_read',{'revision':current['items'][0]['revision'],'view':'document'})
            assert doc['is_current_revision'] and '28 C' in json.dumps(doc['claims'],ensure_ascii=False)
            for namespace in ('synthetic-telemetry','synthetic-components'):
                current=await fresh.call('boi_knowledge_catalog',{'namespace':namespace,'kind':'definition'})
                assert current['items'][0]['revision']==documents[namespace][0]['revision']

        assert source.ledger.verify().ok
    finally:
        for server,thread,sock in reversed(running):
            server.should_exit=True;thread.join(timeout=5);sock.close()
