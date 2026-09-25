"""Current-space reads of exact source-reported qualifications for typed queries.

Create one reader per query. Its authorization wrapper rechecks every consumed
qualification at the engine's final fence. Saved-result consumers must reconstruct
and recheck their used references too; this class is not a result-access grant.
"""
from .knowledge_projection_contract import ProjectionRevision
from .knowledge_query import KnowledgeFactUse
from .knowledge_space_store import KnowledgeSpaceStore
from .ledger import RecordKind, record_digest
from .local_bundle_checks import CHECKS
from .local_knowledge_qualification import QUALIFICATIONS, qualification_key, qualification_policy
from .native_knowledge_checks import shipped_checker_release
from .semantic_binding_contract import RevisionRef, semantic_digest


class KnowledgeUseReader:
    def __init__(self, spaces):
        if not isinstance(spaces,KnowledgeSpaceStore):
            raise ValueError('KNOWLEDGE_USE_CURRENT_SPACE_READER_REQUIRED')
        self.spaces, self.store, self.ledger = spaces, spaces.store, spaces.intake.ledger
        self.observed = {}

    def _access(self, actor_id, revision):
        native = self.ledger.read(revision.ref)
        if native.kind != RecordKind.KNOWLEDGE_REVISION or record_digest(native.record_id) != revision.revision_digest:
            raise ValueError('KNOWLEDGE_USE_NATIVE_REVISION_REQUIRED')
        value = native.payload
        stable_id = 'domain-asset-head:' + semantic_digest([value.get('employee_id'),value.get('namespace'),value.get('logical_id')])
        access, record = self.spaces.authorize(actor_id=actor_id,stable_id=stable_id,revision=revision,purpose='model_input')
        if (access.actor_id != actor_id or access.content_revision != revision
                or record.record_id != native.record_id):
            raise ValueError('KNOWLEDGE_USE_CURRENT_ACTOR_REQUIRED')
        return access, record

    def _current(self, actor_id, revision, purpose, *, recorded_reference=None):
        access, native = self._access(actor_id,revision)
        key = qualification_key(revision,purpose)
        entry = self.store.get(QUALIFICATIONS,key)
        if recorded_reference is not None:
            from .knowledge_use_decisions import decision_entry
            entry=decision_entry(self.ledger.read(recorded_reference.ref))
        if entry is None:
            return None, {'native_authority':access.authority_digest,'entry':None}
        reference = RevisionRef.model_validate(entry['qualification_ref'])
        record = self.ledger.read(reference.ref)
        value = record.payload
        if (record.kind != RecordKind.KNOWLEDGE_USE_QUALIFICATION or record.authority != 'qualification_service'
                or record_digest(record.record_id) != reference.revision_digest
                or semantic_digest(value) != entry['payload_digest']
                or entry['revision'] != revision.model_dump(mode='json') or entry['purpose'] != purpose
                or value.get('contract_version') != 'boi/knowledge-use-qualification@1'
                or value.get('knowledge_revision') != entry['revision'] or value.get('purpose') != purpose
                or value.get('stable_id') != access.identity.stable_id
                or value.get('status') != entry['status']
                or value.get('policy_digest') != native.payload['policy_digest']
                or value.get('source_manifest_digest') != native.payload['source_manifest_digest']):
            raise ValueError('KNOWLEDGE_USE_QUALIFICATION_BINDING_MISMATCH')
        if recorded_reference is None and (value['qualification_policy'] != qualification_policy()
                or value['qualification_policy_digest'] != semantic_digest(qualification_policy())
                or value['checker_release_digest'] != semantic_digest(shipped_checker_release())):
            raise ValueError('KNOWLEDGE_USE_CURRENT_POLICY_CHANGED')
        check_ref = RevisionRef.model_validate(value['mechanical_check_ref'])
        check = self.ledger.read(check_ref.ref)
        if (check.kind != RecordKind.CHECK or check.authority != 'qualification_service'
                or record_digest(check.record_id) != check_ref.revision_digest):
            raise ValueError('KNOWLEDGE_USE_SERVER_CHECK_REQUIRED')
        report, binding = check.payload['report'], check.payload['input']
        check_key = 'native-mechanical-execution:' + semantic_digest(binding)
        checked = self.store.get(CHECKS,check_key)
        if (not checked or checked.get('state') != 'completed' or checked.get('check_ref') != value['mechanical_check_ref']
                or checked.get('payload_digest') != semantic_digest(check.payload)
                or binding['target_revision'] != revision.model_dump(mode='json')
                or report['checker_release_digest'] != value['checker_release_digest'] or report['outcome'] != 'completed'):
            raise ValueError('KNOWLEDGE_USE_SERVER_CHECK_CHANGED')
        authorities = {revision.ref:access.authority_digest}
        identity_targets={}
        if recorded_reference is None:
            for item in report.get('identity_inputs',[]):
                allowed,_=self.spaces.authorize(actor_id=actor_id,stable_id=item['stable_id'],purpose='model_input')
                if allowed.content_revision.model_dump(mode='json')!=item['revision']:
                    raise ValueError('KNOWLEDGE_USE_IDENTITY_TARGET_CHANGED')
                identity_targets[item['stable_id']]=allowed.authority_digest
        for item in report['native_inputs']:
            dependency = RevisionRef.model_validate(item['revision'])
            allowed, record = self._access(actor_id,dependency)
            if (record.payload['content_digest'] != item['content_digest']
                    or record.payload['source_manifest_digest'] != item['source_manifest_digest']):
                raise ValueError('KNOWLEDGE_USE_DEPENDENCY_CHANGED')
            authorities[dependency.ref] = allowed.authority_digest
        return (value,reference), {'entry':entry,'check':checked,'authorities':authorities,'identity_targets':identity_targets,
            'qualification_policy_digest':value['qualification_policy_digest'],'checker_release_digest':value['checker_release_digest']}

    def fact_uses(self, *, actor_id, revision, purpose, facts, claim_basis='source_reported'):
        from .knowledge_statement_contract import REPORTED_STATEMENT_EXISTS
        from .knowledge_statement_evidence import statement_fact_grants
        revision = RevisionRef.model_validate(revision.model_dump(mode='json'))
        if purpose not in ('filter','aggregate','traverse'):
            raise ValueError('KNOWLEDGE_USE_QUERY_PURPOSE_REQUIRED')
        if purpose == 'traverse' and claim_basis != REPORTED_STATEMENT_EXISTS:
            raise ValueError('KNOWLEDGE_TRAVERSAL_SOURCE_REVIEW_REQUIRED')
        current, before = self._current(actor_id,revision,purpose)
        result = []
        if current is not None:
            value, reference = current
            if value['status'] == 'usable_with_limits':
                statement_digest = None
                if claim_basis == REPORTED_STATEMENT_EXISTS:
                    bindings, statement_digest = statement_fact_grants(value, purpose=purpose)
                elif 'statement_scope' in value or 'statement_review_required' in value:
                    # A purpose-scoped source review cannot upgrade the existing
                    # contract that asks whether recorded conditions apply.
                    bindings = {}
                else:
                    bindings = {b['meaning_pointer']:b['fact_digest'] for b in value['fact_bindings']}
                for fact in facts:
                    if (bindings.get(fact.meaning_pointer) == semantic_digest(fact)
                            and fact.meaning_pointer in value['roots']):
                        result.append(KnowledgeFactUse(knowledge_revision=ProjectionRevision.model_validate(revision.model_dump(mode='json')),
                            meaning_pointer=fact.meaning_pointer,fact_digest=semantic_digest(fact),
                            qualification_refs=(reference,),purpose=purpose,statement_scope_digest=statement_digest))
        _, after = self._current(actor_id,revision,purpose)
        if before != after:
            raise ValueError('KNOWLEDGE_USE_AUTHORITY_CHANGED_DURING_READ')
        identity = (actor_id,revision,purpose)
        if identity in self.observed and self.observed[identity] != before:
            raise ValueError('KNOWLEDGE_USE_CHANGED_DURING_QUERY')
        self.observed[identity] = before
        return result

    def qualify(self, access, query, revision, facts):
        return self.fact_uses(actor_id=access.principal,
            revision=RevisionRef(ref=revision,revision_digest=revision.removeprefix('KnowledgeRevision:')),
            purpose='aggregate' if query.operation == 'count' else 'filter',facts=facts,claim_basis=query.claim_basis)

    def revalidate(self):
        for (actor,revision,purpose), expected in self.observed.items():
            _, current = self._current(actor,revision,purpose)
            if current != expected:
                raise ValueError('KNOWLEDGE_USE_CHANGED_DURING_QUERY')

    def bind_authorizer(self, authorize_population):
        if not callable(authorize_population):
            raise ValueError('KNOWLEDGE_USE_POPULATION_AUTHORITY_REQUIRED')
        def authorize(access, phase):
            self.revalidate()
            return authorize_population(access,phase)
        return authorize
