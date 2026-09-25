"""Usage feedback routed to the existing identity owner with current rights.

The ledger preserves the report. Its indexed state changes only in the same
transaction that publishes a linked correction. Submission grants no truth,
source access, automatic publication or permission to edit the document.
"""
from pydantic import Field

from .knowledge_published_read import PublishedKnowledgeReader, document_url
from .knowledge_space_store import HEADS, KnowledgeSpacePolicy
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import FrozenContract, RevisionRef, semantic_digest
from ..v2.atomic_store_contract import AtomicWrite

COLLECTION = 'knowledge_document_feedback'
CONTRACT = 'boi/published-knowledge-feedback@1'


class DocumentFeedbackSubmit(FrozenContract):
    revision: RevisionRef
    comment: str = Field(min_length=1,max_length=8000)
    idempotency_key: str = Field(min_length=1,max_length=240)


class DocumentFeedbackInbox(FrozenContract):
    after: str = Field(default='',max_length=2048)
    limit: int = Field(default=20,ge=1,le=50,strict=True)


class DocumentFeedbackRead(FrozenContract):
    feedback_ref: RevisionRef


def read_feedback(store, ledger, reference):
    ref = RevisionRef.model_validate(reference)
    row = store.get(COLLECTION, ref.ref)
    if not row or row.get('feedback_ref') != ref.model_dump(mode='json'):
        raise ValueError('KNOWLEDGE_FEEDBACK_NOT_AVAILABLE')
    event = ledger.read(ref.ref)
    if (event.kind != RecordKind.RUN or event.authority != 'executor'
            or record_digest(event.record_id) != ref.revision_digest
            or event.payload.get('contract_version') != CONTRACT
            or semantic_digest(event.payload) != row.get('payload_digest')
            or any(row.get(k) != v for k,v in event.payload.items())):
        raise ValueError('KNOWLEDGE_FEEDBACK_BINDING_CHANGED')
    resolution = row.get('resolution')
    if resolution:
        policy_ref = RevisionRef.model_validate(resolution['policy_revision'])
        record = ledger.read(policy_ref.ref)
        policy = KnowledgeSpacePolicy.model_validate(record.payload)
        if (record.kind != RecordKind.KNOWLEDGE_SPACE_POLICY
                or record_digest(record.record_id) != policy_ref.revision_digest
                or policy.identity.stable_id != row['stable_id']
                or policy.content_revision.model_dump(mode='json') != resolution['revision']
                or not policy.content_correction or ref not in policy.content_correction.feedback_refs
                or not store.get('knowledge_publication_receipts',policy.publication_manifest_digest)):
            raise ValueError('KNOWLEDGE_FEEDBACK_RESOLUTION_CHANGED')
    return row


def correction_feedback_rows(assets, auth, change, policy):
    rows = []
    for ref in change.correction.feedback_refs:
        row = read_feedback(assets.store,assets.ledger,ref)
        if (row['stable_id'] != policy.identity.stable_id or row['employee_id'] != auth.principal
                or RevisionRef.model_validate(row['revision']) not in (policy.content_revision,*policy.visible_history)
                or row.get('resolution') is not None):
            raise ValueError('KNOWLEDGE_CORRECTION_FEEDBACK_TARGET_CHANGED')
        rows.append((ref,row))
    return rows


class PublishedKnowledgeFeedback:
    def __init__(self, spaces):
        self.spaces,self.intake,self.store=spaces,spaces.intake,spaces.store
        self.reader=PublishedKnowledgeReader(spaces)

    @staticmethod
    def view(row):
        return {k:row[k] for k in ('feedback_ref','stable_id','revision','comment','reported_by','created_at','resolution')} | {
            'state':'correction_published' if row.get('resolution') else 'open',
            'document_url':document_url(RevisionRef.model_validate(row['revision'])),
            'resolution_url':document_url(RevisionRef.model_validate(row['resolution']['revision'])) if row.get('resolution') else None,
            'approval_required':False,'semantic_truth_proven':False}

    def _authorize(self, actor_id, row, *, inbox=False):
        if actor_id == row['reported_by'] and not inbox:
            purpose='read'
        elif actor_id == row['employee_id']:
            purpose='edit'
        else:
            raise ValueError('KNOWLEDGE_FEEDBACK_ACCESS_DENIED')
        self.spaces.authorize(actor_id=actor_id,stable_id=row['stable_id'],revision=row['revision'],purpose=purpose)

    def read(self, *, actor_id, request):
        req=DocumentFeedbackRead.model_validate(request)
        row=read_feedback(self.store,self.intake.ledger,req.feedback_ref)
        self._authorize(actor_id,row)
        return self.view(row)

    def inbox(self, *, actor_id, request):
        req=DocumentFeedbackInbox.model_validate(request)
        self.spaces._actor(actor_id)
        page=self.store.list_key_page(COLLECTION,employee_id=actor_id,after_key=req.after,limit=req.limit)
        items=[]
        for item in page:
            row=read_feedback(self.store,self.intake.ledger,item['value']['feedback_ref'])
            try:self._authorize(actor_id,row,inbox=True)
            except ValueError as error:
                if str(error) in ('KNOWLEDGE_SPACE_ACCESS_DENIED','KNOWLEDGE_FEEDBACK_ACCESS_DENIED',
                        'KNOWLEDGE_SPACE_SOURCE_POLICY_CHANGED','KNOWLEDGE_SPACE_CONTENT_USE_NOT_AUTHORIZED'):
                    continue
                raise
            items.append(self.view(row))
        # Recheck every returned target at delivery; no whole corpus scan.
        for item in items:
            self._authorize(actor_id,read_feedback(self.store,self.intake.ledger,item['feedback_ref']),inbox=True)
        return {'items':items,'next_after':page[-1]['key'] if len(page)==req.limit else None,
            'responsibility':'current_identity_owner','approval_required':False}

    def submit(self, *, actor_id, request):
        req=DocumentFeedbackSubmit.model_validate(request)
        if not req.comment.strip():raise ValueError('KNOWLEDGE_FEEDBACK_COMMENT_REQUIRED')
        stable_id=self.reader.stable_id(req.revision)
        access,_=self.spaces.authorize(actor_id=actor_id,stable_id=stable_id,revision=req.revision,purpose='read')
        key='document-feedback:'+semantic_digest([actor_id,req.idempotency_key])
        fingerprint=semantic_digest(req)
        previous=self.store.get('agent_task_idempotency',key)
        if previous:
            if previous['fingerprint']!=fingerprint:raise ValueError('KNOWLEDGE_FEEDBACK_IDEMPOTENCY_CONFLICT')
            return self.read(actor_id=actor_id,request={'feedback_ref':previous['feedback_ref']})
        head=self.store.get(HEADS,stable_id)
        if not head or head['policy_revision']!=access.policy_revision.model_dump(mode='json'):
            raise ValueError('KNOWLEDGE_FEEDBACK_TARGET_CHANGED')
        payload={'contract_version':CONTRACT,'employee_id':access.identity.identity_creator,
            'reported_by':actor_id,'stable_id':stable_id,'revision':req.revision.model_dump(mode='json'),
            'comment':req.comment,'created_at':self.intake.clock().isoformat()}
        event=self.intake.ledger.append(RecordKind.RUN,payload,authority='executor',occurred_at=payload['created_at'])
        ref=RevisionRef(ref=event.record_id,revision_digest=record_digest(event.record_id))
        row={**payload,'feedback_ref':ref.model_dump(mode='json'),'payload_digest':semantic_digest(event.payload),'resolution':None}
        self.spaces.authorize(actor_id=actor_id,stable_id=stable_id,revision=req.revision,purpose='read')
        writes=(AtomicWrite(HEADS,stable_id,head,head),AtomicWrite(COLLECTION,ref.ref,None,row),
            AtomicWrite('agent_task_idempotency',key,None,{'employee_id':actor_id,'fingerprint':fingerprint,'feedback_ref':ref.model_dump(mode='json')}))
        if not self.store.atomic_compare_and_write(writes):
            saved=self.store.get('agent_task_idempotency',key)
            if saved and saved['fingerprint']==fingerprint:
                return self.read(actor_id=actor_id,request={'feedback_ref':saved['feedback_ref']})
            raise ValueError('KNOWLEDGE_FEEDBACK_TARGET_CHANGED')
        return self.read(actor_id=actor_id,request={'feedback_ref':ref})
