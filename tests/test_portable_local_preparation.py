"""Actual isolated installed-kit execution, distinct from user/semantic acceptance."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from agent_kit.python.boi_local_bundle_archive import pack_bundle
from agent_kit.python.boi_local_knowledge_draft import assemble
from scripts.build_boi_local_runtime import release_files
from tests.test_domain_kit_install import KIT, load_installer
from tests.test_local_knowledge_draft import spec, assessment


def with_negative_fixture_reviews(value):
    """Supplied test opinions, not generated product qualification."""
    value['assessments'] = []
    for record in value['records']:
        opinion = assessment(value, 'unsupported')
        opinion['target_object_id'] = record['object_id']
        opinion['uses'][0]['judgments'][0]['evidence'] = [
            {'source_object_id': record['source_object_id'],
             'source_byte_digest': value['sources'][record['source_object_id']]['byte_digest'],
             **q, 'quote_occurrence': q.get('quote_occurrence', 0)}
            for q in record['assertions'][0]['evidence']]
        value['assessments'].append(opinion)
    return value


def test_release_is_exact_canonical_bytes_and_has_no_server_runtime():
    files = release_files()
    for name, raw in files.items():
        assert (KIT/'runtime'/name).read_bytes() == raw
    provenance = json.loads(files['provenance.json'])
    assert 15 <= len(provenance['source_sha256']) <= 29
    assert not any('/ledger.py' in n or 'provider' in n or 'evaluation' in n
                   for n in provenance['source_sha256'])


def test_release_query_host_is_importable_from_archive_alone(tmp_path):
    """The evaluated published-query entrypoint must ship to installed users."""
    archive=tmp_path/'local-contracts.zip'
    archive.write_bytes(release_files()['local-contracts.zip'])
    code=';'.join((
        'import sys',
        'sys.path.insert(0,%r)' % str(archive),
        'from agent_kit.python.boi_ontology_query_host import '
            'PUBLISHED_USER_ENTRYPOINT_CONTRACT,deterministic_formula_delivery',
        'assert PUBLISHED_USER_ENTRYPOINT_CONTRACT=="boi/published-user-answer-entrypoint@1"',
        'assert callable(deterministic_formula_delivery)'))
    result=subprocess.run([sys.executable,'-I','-c',code],cwd=tmp_path,
        capture_output=True,text=True,timeout=30)
    assert result.returncode==0,(result.stdout,result.stderr)


def test_installed_profile_cli_reaches_cited_answer_from_empty_directory(tmp_path):
    """The distributed kit, not repository imports, owns the complete Profile path."""
    installer = load_installer()
    target = tmp_path/'installed'
    installer.install(KIT, target, 'codex')
    empty = tmp_path/'empty';empty.mkdir()
    command=[sys.executable,str(target/'scripts/boi_local.py')]
    env=dict(os.environ,PYTHONPATH='/does-not-exist')
    def save(name,value):
        path=tmp_path/name;path.write_text(json.dumps(value,ensure_ascii=False));return path
    def call(*args):
        response=subprocess.run([*command,*map(str,args)],cwd=empty,env=env,
            capture_output=True,text=True,timeout=60)
        assert response.returncode==0,(response.stdout,response.stderr)
        return json.loads(response.stdout)
    revision={'ref':'KnowledgeRevision:sha256:'+'a'*64,
        'revision_digest':'sha256:'+'a'*64}
    profile={'contract_version':'boi/knowledge-profile@1','profile_id':'maintenance',
      'schema_ref':'maintenance@1','label':'Maintenance','description':'work orders','components':[
      {'kind':'object_type','id':'work-order','label':'Work order','description':'record',
       'metadata_constraints':[]},
      {'kind':'predicate','id':'status','label':'Status','description':'result status',
       'subject_type':{'component_id':'work-order'},'value_kind':'text','target_type':None,
       'role':'status','quantity_semantics':'not_applicable','value_semantics':'not_applicable',
       'cardinality':'one','allowed_operators':['eq']},
      {'kind':'predicate','id':'asset','label':'Asset','description':'asset identifier',
       'subject_type':{'component_id':'work-order'},'value_kind':'text','target_type':None,
       'role':'asset','quantity_semantics':'not_applicable','value_semantics':'not_applicable',
       'cardinality':'one','allowed_operators':['eq']}]}
    rows=[('status','asset'),('closed','PUMP-07'),('monitoring','MFC-12')]
    records=[{'record_locator':f'sheet:Work:row:{index}','fields':[
        {'text':status,'value_kind':'string','span_ref':f'cell:A{index}',
         'structural_metadata':{'sheet':'Work','excel_column':'A'}},
        {'text':asset,'value_kind':'string','span_ref':f'cell:B{index}',
         'structural_metadata':{'sheet':'Work','excel_column':'B'}}]}
        for index,(status,asset) in enumerate(rows,1)]
    material={'profiles':[{'revision':revision,'declaration':profile,
        'allowed_domains':['maintenance'],'package_ids':['maintenance'],
        'can_anchor_extension':True}],
        'admission':{'semantic_identity_decided':False,'release_authority_granted':False},
        'profile_catalog_scope_status':'complete'}
    preparation=tmp_path/'preparation.json'
    call('profile-prepare','--records',save('records.json',records),
        '--profile-material',save('material.json',material),
        '--source-scope',save('scope.json',{'artifact_ref':'Artifact:one'}),
        '--output',preparation)
    prepared=json.loads(preparation.read_text())
    assert 'MFC-12' not in prepared['candidate_prompt']
    candidate=tmp_path/'candidate.json'
    call('profile-candidates','--preparation',preparation,'--observation',save('candidate-observation.json',{
        'contract_version':'boi/profile-candidate-observation@1','domain':'maintenance',
        'dispositions':[{'revision':revision,'disposition':'selected',
            'reason':'the complete profile must be compared'}]}),'--output',candidate)
    session=tmp_path/'session.json'
    call('profile-route','--candidate-stage',candidate,'--observation',save('route-observation.json',{
        'contract_version':'boi/profile-routing-observation@1','branch':'reuse','domain':'maintenance',
        'selected_profile_revision':revision,'feature_dispositions':[
          {'feature_id':'workbook:Work:A','disposition':'mapped','component_id':'status',
           'evidence_refs':['cell:A1'],'reason':'reviewed status role'},
          {'feature_id':'workbook:Work:B','disposition':'mapped','component_id':'asset',
           'evidence_refs':['cell:B1'],'reason':'reviewed asset role'}],
        'rejected_profiles':[],'proposed_profile':None,'confidence':'high','ambiguity_notes':[]}),
        '--output',session)
    layout_preparation=tmp_path/'layout-preparation.json'
    call('profile-layout-prepare','--session',session,'--output',layout_preparation)
    layout=tmp_path/'layout.json'
    call('profile-layout-complete','--preparation',layout_preparation,
        '--observation',save('layout-observation.json',{
          'contract_version':'boi/profile-record-layout-observation@1','dispositions':[
          {'record_index':0,'role':'header','evidence_refs':['cell:A1','cell:B1'],'reason':'headers'},
          {'record_index':1,'role':'domain_record','evidence_refs':['cell:A2','cell:B2'],'reason':'record'},
          {'record_index':2,'role':'domain_record','evidence_refs':['cell:A3','cell:B3'],'reason':'record'}]}),
        '--output',layout)
    layout_value=json.loads(layout.read_text())
    layout_review=save('layout-review.json',{
      'contract_version':'boi/profile-record-layout-review@1',
      'layout_digest':layout_value['layout']['layout_digest'],
      'source_snapshot_digest':layout_value['source_snapshot_digest'],'decision':'accepted',
      'reviewer_ref':'source-owner','reason':'confirmed supplied header row'})
    query=tmp_path/'query.json'
    call('profile-query-prepare','--session',layout,'--question','monitoring 상태인 자산은?',
        '--layout-review',layout_review,'--output',query)
    query_value=json.loads(query.read_text())
    assert 'MFC-12' not in query_value['query_prompt']
    execution=tmp_path/'execution.json'
    call('profile-query-execute','--preparation',query,'--plan',save('plan.json',{
        'contract_version':'boi/profile-query-plan@1',
        'filters':[{'component_id':'status','operator':'eq','value':'monitoring'}],
        'select':['asset','status'],'limit':50}),'--output',execution)
    display=tmp_path/'display.json'
    call('profile-query-render','--preparation',query,'--execution',execution,
        '--source-name','maintenance.xlsx','--output',display)
    answer=json.loads(display.read_text())['answer']
    assert 'Asset: MFC-12' in answer
    assert 'maintenance.xlsx · sheet:Work:row:3' in answer


@pytest.mark.parametrize('host', ['codex', 'claude'])
def test_installed_cli_authoring_review_and_archive_from_empty_directory(tmp_path, host):
    python = os.environ.get('BOI_PORTABLE_PYTHON', sys.executable)
    probe = subprocess.run([python, '-I', '-c', 'import pydantic;assert pydantic.__version__=="2.13.4"'],
                           capture_output=True)
    if probe.returncode:
        pytest.skip('Set BOI_PORTABLE_PYTHON to a dedicated pinned environment')
    installer = load_installer()
    archive = tmp_path/'download.zip'
    installer.bundle(KIT, archive)
    with zipfile.ZipFile(archive) as value:
        value.extractall(tmp_path/'download')
    target = tmp_path/'installed'
    installer.install(tmp_path/'download/boi-agent-kit', target, host)
    empty = tmp_path/'empty'; empty.mkdir()
    value = with_negative_fixture_reviews(spec(tmp_path))
    spec_file = tmp_path/'meaning.json'
    spec_file.write_text(json.dumps(value))
    command = [python, '-I', str(target/'scripts/boi_local.py')]
    env = dict(os.environ, PYTHONPATH='/does-not-exist', PYTHONNOUSERSITE='1')
    def call(*args, success=True):
        response = subprocess.run([*command, *map(str,args)], cwd=empty, env=env,
                                  capture_output=True, text=True, timeout=60)
        assert response.returncode == (0 if success else 1), response.stderr
        return json.loads(response.stdout)
    assert call('doctor')['repository_checkout_required'] is False
    call('schema','--output',tmp_path/'contracts.json')
    schemas=json.loads((tmp_path/'contracts.json').read_text())
    mapping=schemas['authoring_input']
    assert 'boi/source-relation-review@1' in mapping['relation_traversal_mapping']
    versions=schemas['LocalKnowledgeAssessment']['$defs']['LocalStatementReview']['properties']['contract_version']['enum']
    assert versions==['boi/source-statement-review@1','boi/source-statement-review@2','boi/source-relation-review@1']
    assert 'context_fields' in mapping['record_fields']
    assert 'review_note' in mapping['context_mapping'] and 'subject_object_id' in mapping['assertion_mapping']
    assert call('inspect','--source',tmp_path/'source.xlsx','--output',tmp_path/'fields.json')['fields'] > 0
    old_manifest = json.loads((tmp_path/'inventory/manifest.json').read_text())
    layout = tmp_path/'layout.json';layout.write_text(json.dumps(old_manifest['layout']))
    inventory = call('inventory','--source',tmp_path/'source.xlsx','--layout',layout,'--output',tmp_path/'fresh-inventory')
    assert inventory['source_digest'] == old_manifest['source_digest']
    value['sources']['workbook']['inventory'] = str(tmp_path/'fresh-inventory')
    spec_file.write_text(json.dumps(value))
    result = call('assemble','--spec',spec_file,'--output',tmp_path/'out')
    assert result['local_only'] and not result['qualification_granted']
    assert result['use_preparation']['status'] == 'reviews_present'
    incomplete = deepcopy(value)
    incomplete.pop('assessments')
    missing = tmp_path / 'missing-reviews.json'
    missing.write_text(json.dumps(incomplete))
    draft = call('assemble', '--spec', missing, '--output', tmp_path / 'missing-reviews')
    assert draft['use_preparation']['status'] == 'incomplete'
    failure = call('pack', '--bundle', tmp_path / 'missing-reviews',
                   '--output', tmp_path / 'missing.boi-bundle.zip', success=False)
    assert failure['error'] == 'LOCAL_PREPARATION_INCOMPLETE'
    assert failure['use_preparation']['gaps'][0]['purpose'] == 'explain'
    assert not (tmp_path / 'missing.boi-bundle.zip').exists()
    assert call('review','--spec',spec_file,'--bundle',tmp_path/'out','--output',tmp_path/'review.html')['local_only']
    assert 'The source contains a decimal string.' in (tmp_path/'review.html').read_text()
    packed = tmp_path/'prepared.boi-bundle.zip'
    report = call('pack','--bundle',tmp_path/'out','--output',packed)
    assert not report['confirmation_recorded']
    with zipfile.ZipFile(packed) as bundle:
        assert bundle.read('manifest.json') == (tmp_path/'out/manifest.json').read_bytes()
        assert bundle.read('objects/workbook.blob') == (tmp_path/'source.xlsx').read_bytes()
        assert bundle.read('objects/reading.blob') == (tmp_path/'out/reading.blob').read_bytes()
        assert all(i.compress_type == zipfile.ZIP_STORED for i in bundle.infolist())
    # Same server type checker rejects a typed-value mismatch in the installed kit.
    value['records'][0]['assertions'][0]['value'] = {'kind':'boolean','value':True}
    spec_file.write_text(json.dumps(value))
    error = call('assemble','--spec',spec_file,'--output',tmp_path/'bad',success=False)
    assert error['error'] == 'LOCAL_AUTHORING_ASSERTION_TYPE_MISMATCH'
    assert not (tmp_path/'bad').exists()
    from tests.test_local_knowledge_identity import graph_spec
    graph=tmp_path/'graph';graph.mkdir()
    spec_file.write_text(json.dumps(with_negative_fixture_reviews(graph_spec(graph))))
    linked=call('assemble','--spec',spec_file,'--output',tmp_path/'linked')
    assert linked['authored_knowledge_objects']==2 and linked['selected_source_records']==1
    call('review','--spec',spec_file,'--bundle',tmp_path/'linked','--output',tmp_path/'linked.html')
    call('pack','--bundle',tmp_path/'linked','--output',tmp_path/'linked.boi-bundle.zip')
    from tests.test_local_authoring_context import context_spec
    surrounding=tmp_path/'surrounding';surrounding.mkdir()
    spec_file.write_text(json.dumps(with_negative_fixture_reviews(context_spec(surrounding))))
    contextual=call('assemble','--spec',spec_file,'--output',tmp_path/'contextual')
    assert contextual['explicit_review_note_sources']==['workbook']
    call('review','--spec',spec_file,'--bundle',tmp_path/'contextual','--output',tmp_path/'contextual.html')
    assert '제공된 보완 기록' in (tmp_path/'contextual.html').read_text()
    (target/'runtime/local-contracts.zip').write_bytes(b'changed')
    assert call('doctor',success=False)['error'] == 'LOCAL_RUNTIME_RELEASE_CHANGED'


def test_archive_refuses_changed_bytes_and_preserves_existing_output(tmp_path):
    value = with_negative_fixture_reviews(spec(tmp_path))
    assemble(value, output=tmp_path/'out')
    destination = tmp_path/'prepared.boi-bundle.zip'
    pack_bundle(tmp_path/'out', destination)
    original = destination.read_bytes()
    with pytest.raises(FileExistsError):
        pack_bundle(tmp_path/'out', destination)
    assert destination.read_bytes() == original
    (tmp_path/'out/workbook.blob').write_bytes(b'changed')
    with pytest.raises(ValueError,match='OBJECT_CHANGED'):
        pack_bundle(tmp_path/'out', tmp_path/'bad.boi-bundle.zip')
    assert not (tmp_path/'bad.boi-bundle.zip').exists()
