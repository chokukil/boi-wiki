"""Published refresh context for external-agent decisions and source metadata.

Both native knowledge and captured source rights must permit model input.
Ordinary internal deterministic source reads can retain their derive-only use.
"""
from .knowledge_profile_projector import native_identity
from .knowledge_source_access import KnowledgeSourceAccess
from .knowledge_space_store import HEADS
from .semantic_binding_contract import RevisionRef, semantic_digest
from ..v2.atomic_store_contract import AtomicWrite


class PublishedKnowledgeContext:
    def __init__(self,spaces,*,actor_id,revision,current_authorization):
        self.spaces,self.actor_id,self.revision=spaces,actor_id,revision
        self.authorization=current_authorization()
        self.current_authorization=current_authorization
        self.sources=KnowledgeSourceAccess(spaces,current_authorization=current_authorization)
        self.observed={}
        self.source_observed={}
        index=spaces.store.get('domain_knowledge_assets',revision.ref)
        if not index:
            raise ValueError('KNOWLEDGE_REFRESH_REVISION_UNAVAILABLE')
        self.stable_id='domain-asset-head:'+semantic_digest([index['employee_id'],index['namespace'],index['logical_id']])
        self.editor,_=spaces.authorize(actor_id=actor_id,stable_id=self.stable_id,revision=revision,purpose='edit')
        head=spaces.store.get(HEADS,self.stable_id)
        if head['content_revision']!=revision.model_dump(mode='json'):
            raise ValueError('KNOWLEDGE_REFRESH_CURRENT_REVISION_REQUIRED')
        pending=[revision];visited=set()
        while pending:
            current=pending.pop()
            if current in visited:continue
            visited.add(current)
            _,asset=self.read(current)
            pending.extend(item.revision for item in asset.dependencies if item.required)

    def resolve_identity(self,stable_id):
        head=self.spaces.store.get(HEADS,stable_id)
        if not head:raise ValueError('KNOWLEDGE_REFRESH_IDENTITY_UNAVAILABLE')
        revision=RevisionRef.model_validate(head['content_revision'])
        self.spaces.authorize(actor_id=self.actor_id,stable_id=stable_id,revision=revision,purpose='model_input')
        return revision

    def observe_identity_targets(self,content):
        """Bind the direct targets used by native type checks before reservation.

        Target contents are read for their type, not recursively traversed as a
        graph. read() retains the same bounded source and current-policy fences.
        """
        from .typed_knowledge_meaning import TypedKnowledgeMeaning
        if content.meaning.get('contract_version')!='boi/typed-knowledge-meaning@1':return
        meaning=TypedKnowledgeMeaning.model_validate(content.meaning)
        identities=set()
        for assertion in meaning.assertions:
            if assertion.value.kind=='object':identities.add(assertion.value.value)
            for group in (assertion.conditions,assertion.exceptions,assertion.applicability):
                for clause in group:
                    for atom in clause.atoms:
                        if atom.subject_ref!='self':identities.add(atom.subject_ref)
                        if atom.value.kind=='object':identities.add(atom.value.value)
        for stable_id in sorted(identities):
            revision=self.resolve_identity(stable_id)
            record,_=self.read(revision)
            if native_identity(record)!=stable_id:
                raise ValueError('KNOWLEDGE_REFRESH_NATIVE_IDENTITY_CHANGED')

    def read(self,revision):
        revision=RevisionRef.model_validate(revision.model_dump(mode='json'))
        if revision not in self.observed and len(self.observed)>=128:
            raise ValueError('KNOWLEDGE_REFRESH_DEPENDENCY_LIMIT')
        index=self.spaces.store.get('domain_knowledge_assets',revision.ref)
        if not index:
            raise ValueError('KNOWLEDGE_REFRESH_REVISION_UNAVAILABLE')
        stable_id='domain-asset-head:'+semantic_digest([index['employee_id'],index['namespace'],index['logical_id']])
        head=self.spaces.store.get(HEADS,stable_id)
        access,record,asset=self.spaces.read(actor_id=self.actor_id,stable_id=stable_id,revision=revision,purpose='model_input')
        if native_identity(record)!=stable_id:
            raise ValueError('KNOWLEDGE_REFRESH_NATIVE_IDENTITY_CHANGED')
        for source in record.payload['sources']:
            if source['artifact_ref'] not in self.source_observed and len(self.source_observed)>=256:
                raise ValueError('KNOWLEDGE_REFRESH_SOURCE_LIMIT')
            _,receipt=self.sources.read(actor_id=self.actor_id,source=source,model_input=True)
            key=source['artifact_ref']
            if key in self.source_observed and self.source_observed[key]!=receipt:
                raise ValueError('KNOWLEDGE_REFRESH_SOURCE_CHANGED')
            self.source_observed[key]=receipt
        native_head=self.spaces.store.get('domain_asset_heads',stable_id)
        policy=self.spaces.intake.ledger.read(access.policy_revision.ref)
        receipt_key=policy.payload['publication_manifest_digest']
        receipt=self.spaces.store.get('knowledge_publication_receipts',receipt_key)
        observed={'access':access,'head':head,'native_index':index,'native_head':native_head,
            'publication_receipt_key':receipt_key,'publication_receipt':receipt,
            'source_manifest_digest':record.payload['source_manifest_digest']}
        if revision in self.observed and self.observed[revision]!=observed:
            raise ValueError('KNOWLEDGE_REFRESH_AUTHORITY_CHANGED')
        self.observed[revision]=observed
        return record,asset

    def fences(self):
        editor,_=self.spaces.authorize(actor_id=self.actor_id,stable_id=self.stable_id,
            revision=self.revision,purpose='edit')
        if editor!=self.editor or self.current_authorization()!=self.authorization:
            raise ValueError('KNOWLEDGE_REFRESH_AUTHORITY_CHANGED')
        for revision in tuple(self.observed):self.read(revision)
        writes={}
        for revision,item in self.observed.items():
            stable_id=item['access'].identity.stable_id
            for collection,key,value in ((HEADS,stable_id,item['head']),
                    ('domain_knowledge_assets',revision.ref,item['native_index']),
                    ('domain_asset_heads',stable_id,item['native_head']),
                    ('knowledge_publication_receipts',item['publication_receipt_key'],item['publication_receipt'])):
                writes[collection,key]=AtomicWrite(collection,key,value,value)
        for key,item in self.source_observed.items():
            writes['bulk_migration_source_artifacts',key]=AtomicWrite('bulk_migration_source_artifacts',key,item['index'],item['index'])
        return tuple(writes.values())

    def binding(self):
        self.fences()
        return {'editor_authority':self.editor.authority_digest,
            'native_authorities':{ref.ref:item['access'].authority_digest for ref,item in self.observed.items()},
            'source_authorities':{key:item['authority_digest'] for key,item in self.source_observed.items()}}
