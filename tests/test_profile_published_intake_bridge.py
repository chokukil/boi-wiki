from copy import deepcopy

import pytest

import agent_kit.python.boi_profile_intake_host as module
import agent_kit.python.boi_ontology_query_host as ontology
from agent_kit.python.boi_profile_intake_host import bridge_profile_workflow_to_published_question
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


REVISION={'ref':'KnowledgeRevision:sha256:'+'a'*64,'revision_digest':'sha256:'+'a'*64}
SECOND_REVISION={'ref':'KnowledgeRevision:sha256:'+'d'*64,'revision_digest':'sha256:'+'d'*64}
RECIPIENT={'actor':'employee:published-user','auth_source':'pat'}
MANIFEST_DIGEST='sha256:'+'1'*64
PUBLICATION_DIGEST='sha256:'+'2'*64
BUNDLE_REF='local-bundle:sha256:'+'3'*64
UNIT_ID='publication-unit:sha256:'+'4'*64


def workflow(status='ready_for_question',branch='reuse'):
    return {'contract_version':'boi/profile-workflow-result@1','status':status,
        'session':{'contract_version':'boi/profile-layout-session@1',
            'session_digest':'sha256:'+'9'*64,
            'layout_session_digest':'sha256:'+'b'*64,
            'source_snapshot_digest':'sha256:'+'c'*64,
            'route':{'branch':branch}},
        'publication_authority_granted':False}


def binding(value=None,**changes):
    value=deepcopy(value or workflow())
    objects=[('actual','svid-actual',REVISION),('setpoint','svid-setpoint',SECOND_REVISION)]
    preparation={'contract_version':'boi/profile-relation-authoring-preparation@1',
        'session_digest':value['session']['session_digest'],
        'source_snapshot_digest':value['session']['source_snapshot_digest'],
        'authoring_spec_fields':{'records':[]},
        'relation_target_object_ids':[item[0] for item in objects],
        'publication_authority_granted':False,'semantic_truth_proven':False}
    preparation['preparation_digest']=semantic_digest(preparation)
    changes_manifest=[{'object_id':object_id,'namespace':'svid','logical_id':logical_id,
        'kind':'definition','title':object_id} for object_id,logical_id,_ in objects]
    published=[];validated=[]
    for object_id,logical_id,revision in objects:
        published.append({'object_id':object_id,
            'stable_id':'domain-asset-head:'+semantic_digest([RECIPIENT['actor'],'svid',logical_id]),
            'title':object_id,'revision':deepcopy(revision),'document_url':'https://example.test/'+object_id})
        validated.append({'object_id':object_id,'state':'completed',
            'report':{'target_revision':deepcopy(revision)}})
    status={'contract_version':'boi/local-publication@1','bundle_ref':BUNDLE_REF,
        'manifest_digest':MANIFEST_DIGEST,'manifest':{'changes':changes_manifest},
        'state':'published','basis_current':True,'publication_committed':True,
        'confirmation_context':deepcopy(RECIPIENT),'publication_progress':{
            'publication_committed':True,'units':[{'unit_id':UNIT_ID,'state':'published',
                'publication_digest':PUBLICATION_DIGEST}]}}
    publish={'bundle_ref':BUNDLE_REF,'unit_id':UNIT_ID,'publication_digest':PUBLICATION_DIGEST,
        'state':'published','publication_committed':True,'confirmation_context':deepcopy(RECIPIENT),
        'receipt':{'operation_id':PUBLICATION_DIGEST,'manifest_digest':PUBLICATION_DIGEST,
            'application_store_durable':True},'published_items':published}
    evidence={'contract_version':'boi/profile-server-publication-evidence@1',
        'relation_preparation':preparation,'bundle_status':status,
        'validation_receipt':{'bundle_ref':BUNDLE_REF,'items':validated},
        'publish_receipt':publish,'expected_manifest_digest':MANIFEST_DIGEST,
        'expected_recipient':deepcopy(RECIPIENT)}
    for path,replacement in changes.items():
        target=evidence
        parts=path.split('.')
        for part in parts[:-1]:target=target[part]
        target[parts[-1]]=replacement
    return evidence


def readback(item,**changes):
    result={'revision':deepcopy(item['revision']),'stable_id':item['stable_id'],
        'publication_state':'published','is_current_revision':True,'claims':[]}
    result.update(changes)
    return result


def test_review_or_publication_boundary_stops_without_calling_published_host(monkeypatch):
    monkeypatch.setattr(module,'run_published_user_request',lambda *a,**k:(_ for _ in ()).throw(
        AssertionError('must not query before publication')))
    review=bridge_profile_workflow_to_published_question(workflow_result=workflow('review_required'),
        question='설명해줘')
    ready=bridge_profile_workflow_to_published_question(workflow_result=workflow(),question='설명해줘')
    assert review['status']=='review_required' and not review['published_question_executed']
    assert ready['status']=='publication_required' and not ready['published_question_executed']
    assert ready['publication_authority_granted'] is False


@pytest.mark.parametrize(('path','replacement','error'),[
    ('relation_preparation.session_digest','sha256:'+'0'*64,'PREPARATION_MISMATCH'),
    ('relation_preparation.source_snapshot_digest','sha256:'+'0'*64,'PREPARATION_MISMATCH'),
    ('bundle_status.basis_current',False,'STATUS_MISMATCH'),
    ('publish_receipt.publication_committed',False,'SERVER_RECEIPT_MISMATCH'),
    ('publish_receipt.confirmation_context',{'actor':'other','auth_source':'pat'},'RECIPIENT_MISMATCH')])
def test_receipts_must_match_exact_session_current_basis_commit_and_recipient(path,replacement,error):
    value=workflow()
    with pytest.raises(ValueError,match=error):
        bridge_profile_workflow_to_published_question(workflow_result=workflow(),
            publication_binding=binding(value,**{path:replacement}),question='설명해줘',host_arguments={})


@pytest.mark.parametrize('branch',['reuse','extend','new'])
def test_every_route_branch_uses_common_entrypoint_and_must_rediscover_same_revision(
        monkeypatch,branch):
    calls=[]
    publication=binding(workflow(branch=branch))
    published_items=publication['publish_receipt']['published_items']
    def published(question,**kwargs):
        calls.append((question,kwargs))
        return {'final_delivery_observed':True,'final_answer':'출처 있는 답변',
            'raw':{'journal':[{'tool':'boi_knowledge_read','error':None,
                'arguments':{'revision':deepcopy(item['revision'])},'result':readback(item)}
                for item in published_items]}}
    monkeypatch.setattr(module,'run_published_user_request',published)
    result=bridge_profile_workflow_to_published_question(workflow_result=workflow(branch=branch),
        publication_binding=publication,question='자연어 질문',host_arguments={'schemas':[]})
    assert result['status']=='answer_ready' and result['published_revision_discovered']
    assert result['result']['final_answer']=='출처 있는 답변'
    assert calls[0][1]['request_context']['channel']=='profile_intake_bridge'
    assert calls[0][1]['request_context']['published_revisions']==[REVISION,SECOND_REVISION]
    assert calls[0][1]['request_context']['server_receipt_digest'].startswith('sha256:')
    assert result['publication_authority_granted'] is False
    assert result['server_publication_receipt_verified'] is True


def test_different_discovered_revision_is_not_accepted(monkeypatch):
    monkeypatch.setattr(module,'run_published_user_request',lambda *a,**k:{
        'final_delivery_observed':True,'raw':{'journal':[{'tool':'boi_knowledge_read','error':None,
            'arguments':{'revision':deepcopy(REVISION)}}]}})
    result=bridge_profile_workflow_to_published_question(workflow_result=workflow(),
        publication_binding=binding(workflow()),question='질문')
    assert result['status']=='published_revision_not_discovered'
    assert result['publication_authority_granted'] is False


@pytest.mark.parametrize(('field','replacement'),[
    ('revision',SECOND_REVISION),('stable_id','domain-asset-head:sha256:'+'0'*64),
    ('publication_state','draft'),('is_current_revision',False)])
def test_requested_revision_without_matching_current_published_readback_is_not_discovery(
        monkeypatch,field,replacement):
    publication=binding()
    items=publication['publish_receipt']['published_items']
    def published(*_args,**_kwargs):
        return {'final_delivery_observed':True,'final_answer':'답변이 전달됨',
            'raw':{'journal':[{'tool':'boi_knowledge_read','error':None,
                'arguments':{'revision':deepcopy(item['revision'])},
                'result':readback(item,**({field:replacement} if item is items[0] else {}))}
                for item in items]}}
    monkeypatch.setattr(module,'run_published_user_request',published)
    result=bridge_profile_workflow_to_published_question(workflow_result=workflow(),
        publication_binding=publication,question='질문')
    assert result['status']=='published_revision_not_discovered'
    assert result['published_revision_discovered'] is False


def test_common_entrypoint_accepts_only_well_formed_server_binding_trace(monkeypatch):
    monkeypatch.setattr(ontology,'run_ontology_host',lambda *a,**k:{'final_delivery_observed':False,
        'raw':{'journal':[],'task_route':{'mode':'explanation'}}})
    context={'channel':'profile_intake_bridge','server_receipt_digest':'sha256:'+'1'*64,
        'published_revisions':[deepcopy(REVISION)]}
    result=ontology.run_published_user_request('설명해줘',request_context=context,
        schemas=[],decide=lambda *_:None,call=lambda *_:None)
    assert result['raw']['entrypoint_trace']['request_context']==context
    with pytest.raises(ValueError,match='CONTEXT_INVALID'):
        ontology.run_published_user_request('설명해줘',request_context={**context,
            'published_revisions':[{'ref':REVISION['ref'],'revision_digest':'sha256:bad'}]},
            schemas=[],decide=lambda *_:None,call=lambda *_:None)
