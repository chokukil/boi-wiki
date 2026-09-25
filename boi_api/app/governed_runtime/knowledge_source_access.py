"""Current reads under explicit captured source rights, separate from Wiki sharing.

This does not broaden or edit source rights. Private sources remain owner-only.
Team/public use requires that scope and org_share in the persisted rights and in
the current server authorization, with current product audience evaluation.
"""
from ..access_policy import knowledge_access_policy
from .ledger import RecordKind
from .semantic_binding_contract import semantic_digest
from .source_envelope import ArtifactEnvelope, byte_digest


class KnowledgeSourceAccess:
    def __init__(self, spaces, *, current_authorization):
        self.spaces,self.intake=spaces,spaces.intake
        self.current_authorization=current_authorization

    def read(self, *, actor_id, source, model_input=False, cite=False):
        source=ArtifactEnvelope.model_validate(source)
        actor=self.spaces._actor(actor_id)
        authorization=self.current_authorization()
        policy=self.intake._policy(authorization)
        if (authorization.principal!=actor_id or 'derive' not in authorization.allowed_uses
                or self.spaces.current_source_policy()!=authorization.policy_digest):
            raise ValueError('KNOWLEDGE_SOURCE_CURRENT_AUTHORITY_REQUIRED')
        if model_input and 'model_input' not in authorization.allowed_uses:
            raise ValueError('KNOWLEDGE_SOURCE_MODEL_INPUT_NOT_AUTHORIZED')
        if cite and 'cite' not in authorization.allowed_uses:
            raise ValueError('KNOWLEDGE_SOURCE_CITE_NOT_AUTHORIZED')
        artifact=self.intake.ledger.read(source.artifact_ref); value=artifact.payload
        if (artifact.kind!=RecordKind.SOURCE_ARTIFACT or artifact.authority!='intake_service'
                or value.get('contract_version')!='boi/source-artifact-intake@0.1.0'
                or value.get('content_digest')!=source.digest or value.get('role')!=source.role
                or value.get('policy_digest')!=authorization.policy_digest):
            raise ValueError('KNOWLEDGE_SOURCE_BINDING_CHANGED')
        rights=self.intake.ledger.read(value['rights_record_ref']); grant=rights.payload
        if (rights.kind!=RecordKind.SOURCE_RIGHTS_RECORD or rights.authority!='rights_service'
                or grant.get('contract_version')!='boi/source-use-policy@0.1.0'
                or grant.get('principal')!=value.get('owner')
                or grant.get('visibility')!=value.get('visibility')
                or grant.get('content_digest')!=source.digest
                or grant.get('source_capture_ref')!=value.get('source_capture_ref')
                or any(grant.get(key)!=item for key,item in policy.items() if key!='principal')):
            raise ValueError('KNOWLEDGE_SOURCE_RIGHTS_CHANGED')
        if actor_id!=value['owner'] and ('org_share' not in grant['allowed_uses']
                or grant['visibility'] not in ('team','public')):
            raise ValueError('KNOWLEDGE_SOURCE_ACCESS_DENIED')
        visibility,team=grant['visibility'],grant['team_id']
        access=knowledge_access_policy({'visibility':visibility,'owner':value['owner'],'team_id':team,
            'classification':'internal','acl_policy':{'private':'acl:private:'+value['owner'],
                'team':'acl:team:'+str(team),'public':'acl:public'}[visibility]},
            identity_owner=value['owner'],employee_id=actor_id,teams=actor.teams,roles=actor.roles)
        if not access.can_read or 'body' in access.redactions:
            raise ValueError('KNOWLEDGE_SOURCE_ACCESS_DENIED')
        index=self.intake.store.get('bulk_migration_source_artifacts',source.artifact_ref)
        expected={'artifact_ref':source.artifact_ref,'employee_id':value['owner'],'digest':source.digest,
            'role':source.role,'object_ref':value['object_ref'],'rights_record_ref':rights.record_id,
            'outbox_ref':value['source_capture_ref'],'canonical_projection_eligible':False}
        if index is None or any(index.get(k)!=v for k,v in expected.items()):
            raise ValueError('KNOWLEDGE_SOURCE_INDEX_CHANGED')
        raw=self.intake.objects.get(value['object_ref'])
        if byte_digest(raw)!=source.digest or len(raw)!=value['byte_length']:
            raise ValueError('KNOWLEDGE_SOURCE_BYTES_CHANGED')
        fresh=self.spaces._actor(actor_id)
        if (self.current_authorization()!=authorization or self.spaces.current_source_policy()!=authorization.policy_digest
                or sorted(fresh.teams)!=sorted(actor.teams) or sorted(fresh.roles)!=sorted(actor.roles)
                or self.intake.store.get('bulk_migration_source_artifacts',source.artifact_ref)!=index):
            raise ValueError('KNOWLEDGE_SOURCE_AUTHORITY_CHANGED')
        return raw, {'reference':source.model_dump(mode='json'),'rights_ref':rights.record_id,
            'authority_digest':semantic_digest({'actor_id':actor_id,'policy':policy,'model_input':model_input,'cite':cite,'teams':sorted(actor.teams),
                'roles':sorted(actor.roles),'rights_ref':rights.record_id}),'index':index}
