"""Synthetic helper closure for focused MCP release validation."""
import json


import pytest


from boi_api.app.governed_runtime.domain_work_service import DomainWorkService


from boi_api.app.governed_runtime.ledger import record_digest


from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


from tests.test_source_field_projection import captured


@pytest.fixture
def sample(tmp_path):
    raw = json.dumps({'process':'Coating','description':'Apply film. If cold, voids may form.'}).encode()
    intake, auth, source, projector = captured(tmp_path,raw)
    source = {'kind':'artifact_ref',**{k:source[k] for k in ('artifact_ref','digest','role')}}
    manifest = projector.project(authorization=auth,reference=source)
    context = dict(principal_id=auth.principal,policy_digest=auth.policy_digest,purpose='extract',
        source_manifest_digest=semantic_digest([source]),lane='provisional',assets=(),selections=(),
        dependency_completeness='complete',source_fidelity='not_evaluated',domain_verdict='not_evaluated',
        task_readiness='not_evaluated',display_status='PROVISIONAL',contract_version='boi/task-knowledge-context@1')
    context = TaskKnowledgeContext(**context,context_digest=semantic_digest(context))
    spec = {'kind':'source_projection','name':'evidence','source':source,
        'manifest_revision':{'ref':manifest['manifest_ref'],'revision_digest':record_digest(manifest['manifest_ref'])}}
    work = DomainWorkService(intake)
    _, material = work._input(auth,spec,{'sources':[source]},context)
    evidence = json.loads(material)
    def quote(value):return {'field_locator':'/description','quote':value}
    draft = {'source_revision_digest':source['digest'],'extraction_context_digest':context.context_digest,
        'records':[{'process_ref':'coat','source_description_fields':['/description'],
            'terms':[{'term_id':'coat','label':'Coating','category':'process',
                'evidence':[{'field_locator':'/process','quote':'Coating'}]}],
            'assertions':[{'assertion_id':'action','subject_ref':'coat','predicate':'applies','object_text':'film',
                'statement':'필름을 도포한다.','category':'action','polarity':'positive','modality':'asserted',
                'evidence':[quote('Apply film.')]},
                {'assertion_id':'risk','subject_ref':'coat','predicate':'may_cause','object_text':'voids',
                'statement':'추우면 기공이 생길 수 있다.','category':'conditional_effect','polarity':'positive','modality':'possible',
                'conditions':[{'statement':'cold','evidence':[quote('If cold')]}],
                'evidence':[quote('If cold, voids may form.')]}]}]}
    return dict(intake=intake,auth=auth,source=source,spec=spec,work=work,evidence=evidence,context=context,draft=draft)
