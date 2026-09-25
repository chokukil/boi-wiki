"""Exact Published explain qualifications admitted into the shared answer context.

Reading a document, a filter decision or a prior composition grants no explain
authority. Each invocation checks the current actor, policy, checker, sources
and full selected assertion closure, then fences those observations.
"""
from ..governed_runtime.semantic_binding_contract import FrozenContract, RevisionRef, semantic_digest
from ..governed_runtime.task_knowledge import TaskMeaningUse
from ..governed_runtime.knowledge_content import ContentUseContract
from ..governed_runtime.knowledge_use_contract import typed_use_closure


class PublishedMeaningSelection(FrozenContract):
    revision: RevisionRef
    qualification_ref: RevisionRef


class PublishedAnswerMeaning:
    def __init__(self, spaces, actor_id, *, current_authorization=None):
        from ..governed_runtime.knowledge_use_reader import KnowledgeUseReader
        from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader
        from ..governed_runtime.knowledge_source_access import KnowledgeSourceAccess
        self.current_authorization = current_authorization
        self.authorization = current_authorization() if current_authorization is not None else None
        self.sources = KnowledgeSourceAccess(spaces,current_authorization=current_authorization) if current_authorization else None
        self.source_receipts = {}
        self.actor_id = actor_id
        self.reader = KnowledgeUseReader(spaces)
        self.documents = PublishedKnowledgeReader(spaces)

    def read(self, selection, pointers=None):
        selected = PublishedMeaningSelection.model_validate(selection)
        current, before = self.reader._current(self.actor_id, selected.revision, 'explain')
        if current is None or current[0]['status'] != 'usable_with_limits':
            raise ValueError('ANSWER_EXPLAIN_QUALIFICATION_REQUIRED')
        value, reference = current
        if reference != selected.qualification_ref:
            raise ValueError('ANSWER_EXPLAIN_QUALIFICATION_CHANGED')
        access, native, content = self.documents._read(self.actor_id, selected.revision, 'model_input')
        if self.sources is not None:
            for source in native.payload['sources']:
                _, receipt = self.sources.read(actor_id=self.actor_id,source=source,model_input=True)
                key=source['artifact_ref']
                if key in self.source_receipts and self.source_receipts[key][1]!=receipt:
                    raise ValueError('ANSWER_EXPLAIN_SOURCE_AUTHORITY_CHANGED')
                self.source_receipts[key]=(source,receipt)
        roots = tuple(value['roots']) if pointers is None else tuple(pointers)
        if not roots or not set(roots) <= set(value['roots']):
            raise ValueError('ANSWER_EXPLAIN_SCOPE_NOT_QUALIFIED')
        scope = typed_use_closure(content, ContentUseContract(purpose='explain', required_meaning_pointers=roots))
        if scope['roots'] != roots:
            # Selection order is not meaning. Binding recomputes the digest from
            # the normalized roots, so the same set must fence identically.
            scope = typed_use_closure(content, ContentUseContract(purpose='explain', required_meaning_pointers=scope['roots']))
        if not set(scope['closure']) <= set(value['closure']):
            raise ValueError('ANSWER_EXPLAIN_SCOPE_CLOSURE_NOT_QUALIFIED')
        assessed = {item['pointer']: item for item in value['assessed_nodes']}
        if any(p not in assessed or assessed[p]['native_value_digest'] != semantic_digest(node)
               or assessed[p]['judgment']['label'] != 'supported' for p, node in scope['nodes'].items()):
            raise ValueError('ANSWER_EXPLAIN_SCOPE_ASSESSMENT_CHANGED')
        self.documents._fence(self.actor_id, selected.revision, access)
        _, after = self.reader._current(self.actor_id, selected.revision, 'explain')
        if before != after:
            raise ValueError('ANSWER_EXPLAIN_AUTHORITY_CHANGED_DURING_READ')
        identity = (self.actor_id, selected.revision, 'explain')
        if identity in self.reader.observed and self.reader.observed[identity] != before:
            raise ValueError('ANSWER_EXPLAIN_AUTHORITY_CHANGED_DURING_READ')
        self.reader.observed[identity] = before
        return TaskMeaningUse(revision=selected.revision, qualification_ref=reference,
            content_digest=native.payload['content_digest'], roots=scope['roots'],
            closure=scope['closure'], scope_digest=scope['scope_digest'],
            limitations=tuple(value.get('limitations', ())))

    def revalidate(self):
        self.reader.revalidate()
        if self.current_authorization is not None and self.current_authorization()!=self.authorization:
            raise ValueError('ANSWER_EXPLAIN_CURRENT_AUTHORITY_CHANGED')
        for source, expected in self.source_receipts.values():
            _, receipt=self.sources.read(actor_id=self.actor_id,source=source,model_input=True)
            if receipt!=expected:raise ValueError('ANSWER_EXPLAIN_SOURCE_AUTHORITY_CHANGED')
