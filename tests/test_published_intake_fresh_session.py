from copy import deepcopy

import pytest

import agent_kit.python.boi_profile_intake_host as module
from agent_kit.python.boi_profile_intake_host import bridge_profile_workflow_to_published_question
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


OLD={'ref':'KnowledgeRevision:sha256:'+'1'*64,'revision_digest':'sha256:'+'1'*64}
NEW={'ref':'KnowledgeRevision:sha256:'+'2'*64,'revision_digest':'sha256:'+'2'*64}
RECIPIENT={'actor':'employee:fresh-user','auth_source':'pat'}


def workflow(session_digest,source_digest,condition,unrelated='B unchanged'):
    return {'contract_version':'boi/profile-workflow-result@1','status':'ready_for_question',
        'session':{'contract_version':'boi/profile-layout-session@1',
            'session_digest':session_digest,'layout_session_digest':session_digest,
            'source_snapshot_digest':source_digest,
            'route':{'branch':'reuse'},'fixture_values':{
                'A_condition':condition,'B_unrelated':unrelated}},
        'publication_authority_granted':False}


def binding(value,revision,current=True):
    session=value['session'];object_id='corrected-parameter'
    preparation={'contract_version':'boi/profile-relation-authoring-preparation@1',
        'session_digest':session_digest_under_layout(session),
        'source_snapshot_digest':session['source_snapshot_digest'],
        'authoring_spec_fields':{'records':[]},
        'relation_target_object_ids':[object_id],
        'publication_authority_granted':False,'semantic_truth_proven':False}
    preparation['preparation_digest']=semantic_digest(preparation)
    manifest_digest='sha256:'+'3'*64;publication_digest='sha256:'+'4'*64
    bundle_ref='local-bundle:sha256:'+'5'*64;unit_id='publication-unit:sha256:'+'6'*64
    change={'object_id':object_id,'namespace':'svid','logical_id':'corrected',
        'kind':'definition','title':'corrected'}
    published={'object_id':object_id,
        'stable_id':'domain-asset-head:'+semantic_digest([RECIPIENT['actor'],'svid','corrected']),
        'title':'corrected','revision':deepcopy(revision),'document_url':'https://example.test/corrected'}
    status={'contract_version':'boi/local-publication@1','bundle_ref':bundle_ref,
        'manifest_digest':manifest_digest,'manifest':{'changes':[change]},
        'state':'published','basis_current':current,'publication_committed':True,
        'confirmation_context':deepcopy(RECIPIENT),'publication_progress':{
            'publication_committed':True,'units':[{'unit_id':unit_id,'state':'published',
                'publication_digest':publication_digest}]}}
    publish={'bundle_ref':bundle_ref,'unit_id':unit_id,'publication_digest':publication_digest,
        'state':'published','publication_committed':True,'confirmation_context':deepcopy(RECIPIENT),
        'receipt':{'operation_id':publication_digest,'manifest_digest':publication_digest,
            'application_store_durable':True},'published_items':[published]}
    return {'contract_version':'boi/profile-server-publication-evidence@1',
        'relation_preparation':preparation,'bundle_status':status,
        'validation_receipt':{'bundle_ref':bundle_ref,'items':[{'object_id':object_id,
            'state':'completed','report':{'target_revision':deepcopy(revision)}}]},
        'publish_receipt':publish,'expected_manifest_digest':manifest_digest,
        'expected_recipient':deepcopy(RECIPIENT)}


def session_digest_under_layout(session):
    return session.get('session_digest') or session['layout_session_digest']


def test_fresh_session_uses_corrected_current_revision_and_preserves_unrelated_answer(monkeypatch):
    old=workflow('sha256:'+'a'*64,'sha256:'+'b'*64,'scope unknown')
    new=workflow('sha256:'+'c'*64,'sha256:'+'d'*64,'applies when chamber is cold')
    current={'revision':NEW,'condition':'applies when chamber is cold','unrelated':'B unchanged'}
    def published(question,**_):
        answer=current['condition'] if question=='A 조건은?' else current['unrelated']
        return {'final_delivery_observed':True,'final_answer':answer,
            'raw':{'journal':[{'tool':'boi_knowledge_read','error':None,
                'arguments':{'revision':deepcopy(current['revision'])},
                'result':{'revision':deepcopy(current['revision']),
                    'stable_id':binding(new,NEW)['publish_receipt']['published_items'][0]['stable_id'],
                    'publication_state':'published','is_current_revision':True,
                    'value':answer}}]}}
    monkeypatch.setattr(module,'run_published_user_request',published)
    related=bridge_profile_workflow_to_published_question(workflow_result=new,
        publication_binding=binding(new,NEW),question='A 조건은?')
    unrelated=bridge_profile_workflow_to_published_question(workflow_result=new,
        publication_binding=binding(new,NEW),question='B는?')
    assert related['result']['final_answer']=='applies when chamber is cold'
    assert unrelated['result']['final_answer']=='B unchanged'
    assert old['session']['fixture_values']=={
        'A_condition':'scope unknown','B_unrelated':'B unchanged'}
    assert new['session']['fixture_values']['B_unrelated']==old['session']['fixture_values']['B_unrelated']


def test_old_binding_cannot_be_presented_as_current_after_correction(monkeypatch):
    old=workflow('sha256:'+'a'*64,'sha256:'+'b'*64,'scope unknown')
    monkeypatch.setattr(module,'run_published_user_request',lambda *a,**k:(_ for _ in ()).throw(
        AssertionError('stale binding must fail before query')))
    with pytest.raises(ValueError,match='STATUS_MISMATCH'):
        bridge_profile_workflow_to_published_question(workflow_result=old,
            publication_binding=binding(old,OLD,current=False),
            question='A 조건은?')


def test_late_old_request_is_bound_to_old_revision_and_not_accepted_for_new_session(monkeypatch):
    new=workflow('sha256:'+'c'*64,'sha256:'+'d'*64,'new condition')
    def old_result(*_args,**_kwargs):
        return {'final_delivery_observed':True,'final_answer':'scope unknown',
            'raw':{'journal':[{'tool':'boi_knowledge_read','error':None,
                'arguments':{'revision':deepcopy(OLD)}}]}}
    monkeypatch.setattr(module,'run_published_user_request',old_result)
    result=bridge_profile_workflow_to_published_question(workflow_result=new,
        publication_binding=binding(new,NEW),question='A 조건은?')
    assert result['status']=='published_revision_not_discovered'
    assert result['result']['final_answer']=='scope unknown'
    assert result['publication_authority_granted'] is False
