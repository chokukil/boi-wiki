"""Scoped source-reported uses from confirmed local assessments and server checks.

The policy permits attributed source opinions for bounded knowledge uses, as in
the existing native process review. It does not certify scientific truth, reviewer
independence, physical mappings, executable domain code or a whole document.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from .domain_asset_staging import StagedDomainAsset
from .knowledge_content import decode_knowledge_content, meaning_pointer
from .knowledge_definition_checks import required_definition_capabilities
from .knowledge_profile_projector import ADAPTER_REVISION, KnowledgeProfileProjector, native_identity
from .knowledge_projection_contract import ProjectionPublication, PublicationChange
from .knowledge_use_contract import LocalKnowledgeAssessment, typed_use_closure
from .knowledge_statement_contract import statement_support_contract, traversal_support_contract, modal_statement_support_contract
from .formula_definition_context import formula_context_support_contract
from .formula_context_qualification import formula_unresolved_decision
from .knowledge_unresolved_scope import overlaps, statement_unresolved_decision
from .ledger import RecordKind, record_digest
from .knowledge_use_decisions import predecessor, require_current, decision_write, source_opinion_reasons
from .local_bundle_checks import LocalBundleChecks, CHECKS
from .local_bundle_contract import LocalBundleObject, LocalBundleQualifyRequest, LocalUseSupersession
from .local_bundle_json import LocalJsonDocument
from .native_knowledge_checks import shipped_checker_release
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import byte_digest
from ..v2.atomic_store_contract import AtomicWrite


QUALIFICATIONS = 'knowledge_use_qualifications'
REQUESTS = 'knowledge_use_qualification_requests'
USE_POLICY = {'contract_version':'boi/source-reported-use-policy@1',
    'purposes':['explain','compare','filter','aggregate','formula_input','traverse'],
    'assertion_kind':'source_reported', 'assessment_basis':'authenticated_local_source_opinion',
    'independent_review_required':False, 'full_field_coverage_granted':False,
    'scientific_truth_granted':False,'physical_execution_granted':False,
    'statement_consumption':statement_support_contract(),
    'modal_statement_consumption':modal_statement_support_contract(),
    'traversal_consumption':traversal_support_contract(),
    'formula_consumption':formula_context_support_contract()}

_IMPLEMENTATION = {name:byte_digest((Path(__file__).parent / name).read_bytes())
    for name in ('local_knowledge_qualification.py','knowledge_use_contract.py','knowledge_use_purpose.py',
                 'knowledge_use_decisions.py','knowledge_formula_contract.py','knowledge_definition_checks.py',
                 'knowledge_unresolved_scope.py','knowledge_unresolved_contract.py','knowledge_profile_projector.py','../v2/knowledge_formula.py',
                 'published_knowledge_qualification.py','published_knowledge_context.py',
                 'published_knowledge_contract.py','published_native_checks.py','knowledge_source_access.py',
                 'knowledge_prepared_postgres.py','knowledge_assertion_set_sql.py',
                 'knowledge_statement_contract.py','knowledge_content.py','knowledge_query.py',
                 'typed_knowledge_meaning.py','knowledge_use_reader.py','knowledge_statement_evidence.py',
                 'knowledge_relation_traversal.py','formula_definition_context.py','formula_context_qualification.py')}


def qualification_policy():
    if any(byte_digest((Path(__file__).parent / name).read_bytes()) != digest for name,digest in _IMPLEMENTATION.items()):
        raise ValueError('KNOWLEDGE_USE_LOADED_POLICY_STALE')
    return {**USE_POLICY,'implementation_manifest':dict(_IMPLEMENTATION)}


def qualification_key(revision, purpose):
    return 'knowledge-use:' + semantic_digest([revision.model_dump(mode='json'),purpose])


class LocalKnowledgeQualification:
    def __init__(self, importer, *, prepared_store=None, prepare_queries=True):
        self.checks = LocalBundleChecks(importer)
        self.importer, self.intake, self.store = importer, importer.intake, importer.store
        from ..v2.store import PostgresAgentV2Store
        from .knowledge_prepared_postgres import PostgresKnowledgePreparedStore
        if prepare_queries and prepared_store is None and isinstance(self.store,PostgresAgentV2Store):
            prepared_store=PostgresKnowledgePreparedStore(self.store)
        if prepared_store is not None and (not isinstance(prepared_store,PostgresKnowledgePreparedStore)
                or prepared_store.authority_store is not self.store):
            raise ValueError('KNOWLEDGE_PREPARED_AUTHORITY_STORE_MISMATCH')
        self.prepared_store=prepared_store

    def _assessment(self, auth, row, object_id):
        obj = next((o for o in row['manifest']['objects'] if o['object_id'] == object_id),None)
        if not obj or obj['purpose'] != 'check_evidence':
            raise ValueError('KNOWLEDGE_ASSESSMENT_OBJECT_REQUIRED')
        raw = self.importer._raw(auth,row,LocalBundleObject.model_validate(obj))
        # Strict parser preserves duplicate/non-finite rejection before Pydantic.
        LocalJsonDocument(raw,require_content=False)
        assessment = LocalKnowledgeAssessment.model_validate_json(raw)
        target = next((o for o in row['manifest']['objects'] if o['object_id'] == assessment.target_object_id),None)
        if not target or target['purpose'] != 'native_proposal' or target['byte_digest'] != assessment.target_byte_digest:
            raise ValueError('KNOWLEDGE_ASSESSMENT_TARGET_CHANGED')
        # Reconstruct the transitive local source/Profile input DAG declared at
        # confirmation. The review cannot substitute a different source or omit
        # an input whose token replacement affects the assessed native content.
        required = {assessment.target_object_id}
        while True:
            added = {b['target_object_id'] for b in row['manifest']['references'] if b['object_id'] in required}
            if added <= required:
                break
            required.update(added)
        expected = {o['object_id']:o['byte_digest'] for o in row['manifest']['objects'] if o['object_id'] in required}
        if {i.object_id:i.byte_digest for i in assessment.input_objects} != expected:
            raise ValueError('KNOWLEDGE_ASSESSMENT_INPUT_CLOSURE_CHANGED')
        original = self.importer._raw(auth,row,LocalBundleObject.model_validate(target))
        return assessment, obj, json.loads(original)['content']

    def _mechanical(self, auth, row, object_id, handle):
        release = shipped_checker_release()
        binding = self.checks._input(row,object_id,handle,release)
        key = 'native-mechanical-execution:' + semantic_digest(binding)
        saved = self.store.get(CHECKS,key)
        if not saved or saved.get('state') != 'completed':
            raise ValueError('KNOWLEDGE_USE_COMPLETED_SERVER_CHECK_REQUIRED')
        read = self.checks._reader(auth,row)
        self.checks._current_result(read,{'object_id':object_id},key,saved,binding)
        report = self.checks._receipt(saved,binding)
        _,asset=read(handle.revision)
        content=decode_knowledge_content(json.loads(asset.content_json))
        required=required_definition_capabilities(content,qualified_use=True)
        satisfied = {c['capability'] for c in report['checks'] if c['outcome'] == 'satisfied'}
        if report['outcome'] != 'completed' or not required <= satisfied:
            raise ValueError('KNOWLEDGE_USE_MECHANICAL_PROPERTIES_REQUIRED')
        return read, saved, AtomicWrite(CHECKS,key,saved,saved)

    def _evidence(self, row, content, node_pointer, judgment):
        bindings = [b for b in content.evidence_bindings
                    if b.meaning_pointer == node_pointer or b.meaning_pointer.startswith(node_pointer + '/')]
        required = {(b.source_revision_digest,b.field_locator) for b in bindings}
        if not required:
            raise ValueError('KNOWLEDGE_USE_NODE_EVIDENCE_REQUIRED')
        observed = set()
        receipts = []
        for quote in judgment.evidence:
            if quote.existing_source is not None:
                source = quote.existing_source.model_dump(mode='json')
                if source not in row['manifest']['existing_sources']:
                    raise ValueError('KNOWLEDGE_ASSESSMENT_UNDECLARED_EXISTING_SOURCE')
                # Current draft/source authorization and exact native evidence
                # were checked above. Retain the original artifact and spans;
                # correcting a Wiki explanation does not recapture its source.
            else:
                obj = next((o for o in row['manifest']['objects'] if o['object_id'] == quote.source_object_id),None)
                if not obj or obj['purpose'] != 'raw_source' or obj['byte_digest'] != quote.source_byte_digest:
                    raise ValueError('KNOWLEDGE_ASSESSMENT_SOURCE_CHANGED')
                source = self.importer._saved(row,quote.source_object_id)['result']['source']
            matches = []
            for binding in bindings:
                span = self.intake.ledger.read(binding.span.ref)
                if (span.payload.get('artifact_ref') == source['artifact_ref']
                        and binding.field_locator == quote.field_locator):
                    matches.append((binding,span))
            if not matches:
                raise ValueError('KNOWLEDGE_ASSESSMENT_QUOTE_OUTSIDE_NODE_EVIDENCE')
            binding, span = matches[0]
            raw = self.intake.objects.get(span.payload['field_object_ref'])
            if byte_digest(raw) != span.payload['content_digest']:
                raise ValueError('KNOWLEDGE_ASSESSMENT_SOURCE_FIELD_CHANGED')
            text, start = raw.decode('utf-8'), -1
            for _ in range(quote.quote_occurrence + 1):
                start = text.find(quote.quote,start + 1)
                if start < 0:
                    raise ValueError('KNOWLEDGE_ASSESSMENT_QUOTE_OCCURRENCE_MISSING')
            observed.add((binding.source_revision_digest,binding.field_locator))
            receipts.append({'quote':quote.model_dump(mode='json'),'span':binding.span.model_dump(mode='json'),
                'field_digest':span.payload['content_digest'],'source_revision_digest':binding.source_revision_digest})
        if not required <= observed:
            raise ValueError('KNOWLEDGE_ASSESSMENT_NODE_SOURCE_CLOSURE_MISSING')
        return receipts

    def _unresolved_evidence(self, row, content, item, judgment):
        # An assertion leaf is reviewed with its complete source context. Global
        # entries require all bound source fields unless exact spans were authored.
        from .knowledge_unresolved_scope import unresolved_evidence_bindings
        bindings = unresolved_evidence_bindings(content, item)
        selected = content.model_copy(update={'evidence_bindings':tuple(bindings)})
        return self._evidence(row, selected, '', judgment)

    def _predecessors(self, supersedes, revision, purposes, stable_id):
        predecessors = {}
        for item in supersedes:
            if item.purpose not in purposes:
                raise ValueError('KNOWLEDGE_USE_SUPERSESSION_BINDING_MISMATCH')
            previous = predecessor(self.intake.ledger,item.qualification_ref,
                revision=revision,purpose=item.purpose,stable_id=stable_id)
            predecessors[item.purpose] = (item, previous)
        return predecessors

    def current(self, *, authorization, bundle_ref, assessment_object_id):
        """Discover exact current decisions within the still-open bundle context.

        Old policy decisions remain inspectable so an agent can request an exact
        refresh. This read does not grant use or reopen a published bundle.
        """
        row, _ = self.checks._context(authorization,bundle_ref)
        assessment, _, _ = self._assessment(authorization,row,assessment_object_id)
        policy, release = qualification_policy(), shipped_checker_release()
        handle = self.checks._handles(row)[assessment.target_object_id]
        record, _ = self.checks._reader(authorization,row)(handle.revision)
        entries, uses = [], []
        for use in assessment.uses:
            key = qualification_key(handle.revision,use.purpose)
            entry = self.store.get(QUALIFICATIONS,key)
            if entry is None:
                uses.append({'purpose':use.purpose,'qualification_ref':None,'status':'not_assessed'})
            else:
                item = LocalUseSupersession(purpose=use.purpose,
                    qualification_ref=entry['qualification_ref'],reason='Inspect current decision')
                previous = self._predecessors((item,),handle.revision,
                    {use.purpose},native_identity(record))[use.purpose][1]
                self._entry_matches(previous,entry,handle.revision,use.purpose)
                value = previous.payload
                uses.append({'purpose':use.purpose,'qualification_ref':entry['qualification_ref'],
                    'status':value['status'], 'reasons':value['reasons'], 'limitations':value['limitations'],
                    'supersedes':value.get('supersedes'),
                    'policy_current':value['qualification_policy_digest'] == semantic_digest(policy),
                    'checker_current':value['checker_release_digest'] == semantic_digest(release)})
            entries.append((key,entry))
        current, _ = self.checks._context(authorization,bundle_ref)
        if (current != row or qualification_policy() != policy or shipped_checker_release() != release
                or any(self.store.get(QUALIFICATIONS,key) != entry for key,entry in entries)):
            raise ValueError('KNOWLEDGE_USE_CURRENT_CONTEXT_CHANGED')
        return {'bundle_ref':bundle_ref,'target_revision':handle.revision.model_dump(mode='json'),
            'uses':uses,'publication_committed':False,'use_granted':False}

    @staticmethod
    def _entry_matches(record, entry, revision, purpose):
        if record.payload['knowledge_revision'] != revision.model_dump(mode='json') or record.payload['purpose'] != purpose:
            raise ValueError('KNOWLEDGE_USE_SUPERSESSION_BINDING_MISMATCH')
        require_current(record,entry)

    def qualify(self, *, authorization, bundle_ref, assessment_object_id, supersedes=()):
        options = LocalBundleQualifyRequest(bundle_ref=bundle_ref,
            assessment_object_id=assessment_object_id, supersedes=supersedes)
        row, _ = self.checks._context(authorization,bundle_ref)
        policy = qualification_policy()
        assessment, obj, original = self._assessment(authorization,row,assessment_object_id)
        # Multiple opinions must be reconciled explicitly; selecting the positive
        # one while ignoring another confirmed assessment is not qualification.
        for candidate in row['manifest']['objects']:
            if candidate['purpose'] != 'check_evidence' or candidate['object_id'] == assessment_object_id:
                continue
            raw = self.importer._raw(authorization,row,LocalBundleObject.model_validate(candidate))
            value = json.loads(raw)
            if (isinstance(value,dict) and value.get('contract_version') == assessment.contract_version
                    and value.get('target_object_id') == assessment.target_object_id):
                raise ValueError('KNOWLEDGE_ASSESSMENTS_REQUIRE_RECONCILIATION')
        imported = self.importer._saved(row,assessment.target_object_id)
        handle = StagedDomainAsset.model_validate(imported['result']['staged'])
        read, mechanical, check_fence = self._mechanical(authorization,row,assessment.target_object_id,handle)
        record, asset = read(handle.revision)
        content = decode_knowledge_content(json.loads(asset.content_json))
        if asset.kind != 'definition' or content is None:
            raise ValueError('KNOWLEDGE_USE_DEFINITION_REQUIRED')
        declared = {d.revision for d in asset.dependencies if d.required}
        local_refs = {h.revision for h in self.checks._handles(row).values()}
        if set(assessment.existing_revisions) != declared - local_refs:
            raise ValueError('KNOWLEDGE_ASSESSMENT_EXISTING_REVISION_CLOSURE_CHANGED')
        manifest = ProjectionPublication(scope_id=self.importer.scope(row),principal_id=authorization.principal,
            base_generation=0,policy_digest=authorization.policy_digest,confirmation_ref=self.importer.scope(row),
            source_manifest_digest=record.payload['source_manifest_digest'],adapter_revision=ADAPTER_REVISION,
            changes=(PublicationChange(stable_id=native_identity(record),operation='upsert',
                previous_revision=handle.previous_revision.model_dump(mode='json') if handle.previous_revision else None,
                revision=handle.revision.model_dump(mode='json')),))
        batch,registry = KnowledgeProfileProjector(read_revision=read).materialize_with_registry(manifest)
        projection = batch.objects[0]
        predecessors = self._predecessors(options.supersedes, handle.revision,
            {use.purpose for use in assessment.uses}, native_identity(record))
        request_input = {'bundle_ref':bundle_ref,'confirmation_ref':self.importer.scope(row),
            'assessment_byte_digest':obj['byte_digest'],'target_revision':handle.revision.model_dump(mode='json'),
            'mechanical_check_ref':mechanical['check_ref'],'qualification_policy_digest':semantic_digest(policy)}
        if predecessors:
            request_input['supersedes'] = [predecessors[purpose][0].model_dump(mode='json')
                for purpose in sorted(predecessors)]
        request_key = 'knowledge-use-request:' + semantic_digest(request_input)
        request = self.store.get(REQUESTS,request_key)
        if request is None:
            _, fences = self.checks._context(authorization,bundle_ref)
            created = {'employee_id':authorization.principal,'input':request_input,
                'occurred_at':datetime.now(timezone.utc).isoformat()}
            if not self.store.atomic_compare_and_write((*fences,AtomicWrite(REQUESTS,request_key,None,created))):
                raise ValueError('KNOWLEDGE_USE_REQUEST_STATE_CHANGED')
            request = self.store.get(REQUESTS,request_key)
        if not request or request.get('input') != request_input or request.get('employee_id') != authorization.principal:
            raise ValueError('KNOWLEDGE_USE_REQUEST_BINDING_CHANGED')
        contracts = {u.purpose:u for u in content.use_contracts}
        entries, results, prepared_qualifications = [], [], []
        for use in assessment.uses:
            contract = contracts.get(use.purpose)
            if (use.purpose not in row['manifest']['intended_uses'] or contract is None
                    or set(use.requested_pointers) != set(contract.required_meaning_pointers)):
                raise ValueError('KNOWLEDGE_ASSESSMENT_USE_SCOPE_CHANGED')
            scope = typed_use_closure(content,contract)
            judgments = {j.pointer:j for j in use.judgments}
            if set(judgments) != set(scope['closure']):
                raise ValueError('KNOWLEDGE_ASSESSMENT_FULL_NODE_CLOSURE_REQUIRED')
            report=self.intake.ledger.read(mechanical['check_ref']['ref']).payload['report']
            evidence = []
            for pointer, node in scope['nodes'].items():
                # Checking the pointer in original bytes confirms what the local
                # assessment names. Native values may differ only through the
                # separately verified importer token replacement receipt.
                old_value = meaning_pointer(original['meaning'],pointer)
                judgment = judgments[pointer]
                evidence.append({'pointer':pointer,'original_value_digest':semantic_digest(old_value),
                    'native_value_digest':semantic_digest(node),'judgment':judgment.model_dump(mode='json'),
                    'source_bindings':self._evidence(row,content,pointer,judgment)})
            statement_scope = None
            if use.statement_review is not None:
                statement_scope = statement_unresolved_decision(content, scope,
                    review=use.statement_review, original_unresolved=original.get('unresolved', []),
                    evidence_validator=lambda item, judgment:self._unresolved_evidence(row,content,item,judgment),
                    projection=projection, registry=registry)
                statement_scope['binding'] = {
                    'knowledge_revision':handle.revision.model_dump(mode='json'),
                    'source_manifest_digest':record.payload['source_manifest_digest'],
                    'assessment_byte_digest':obj['byte_digest'],
                    'qualification_policy_digest':semantic_digest(policy),
                    'checker_release_digest':mechanical['input']['checker_release_digest']}
            formula_scope=None
            if use.formula_review is not None:
                formula_scope=formula_unresolved_decision(content,scope,review=use.formula_review,
                    original_unresolved=original.get('unresolved',[]),
                    evidence_validator=lambda item,judgment:self._unresolved_evidence(row,content,item,judgment),
                    projection=projection,registry=registry)
                formula_scope['binding']={
                    'knowledge_revision':handle.revision.model_dump(mode='json'),
                    'source_manifest_digest':record.payload['source_manifest_digest'],
                    'assessment_byte_digest':obj['byte_digest'],
                    'qualification_policy_digest':semantic_digest(policy),
                    'checker_release_digest':mechanical['input']['checker_release_digest']}
            reasons = source_opinion_reasons(policy,use.purpose,contract,scope,judgments,
                mechanical_report=report,statement_scope=statement_scope,formula_scope=formula_scope)
            if statement_scope is not None and reasons:
                statement_scope['eligible_fact_bindings'] = []
            payload = {'contract_version':'boi/knowledge-use-qualification@1','status':'not_qualified' if reasons else 'usable_with_limits',
                'stable_id':native_identity(record),'knowledge_revision':handle.revision.model_dump(mode='json'),
                'purpose':use.purpose,'scope_digest':scope['scope_digest'],'roots':list(scope['roots']),
                'closure':list(scope['closure']), 'fact_bindings':[{'meaning_pointer':f.meaning_pointer,'fact_digest':semantic_digest(f)}
                    for f in projection.facts if f.meaning_pointer in scope['roots']],
                'policy_digest':authorization.policy_digest,'source_manifest_digest':record.payload['source_manifest_digest'],
                'qualification_policy':policy,'qualification_policy_digest':semantic_digest(policy),
                'mechanical_check_ref':mechanical['check_ref'],'checker_release_digest':mechanical['input']['checker_release_digest'],
                'bundle_ref':bundle_ref,'confirmation_ref':self.importer.scope(row),'manifest_digest':row['manifest_digest'],
                'assessment_object_id':assessment_object_id,'assessment_byte_digest':obj['byte_digest'],
                'native_import_receipt_ref':imported['receipt_ref'],'assessed_nodes':evidence,
                'provenance':{'authenticated_principal':authorization.principal,'agent_session_ref':assessment.agent_session_ref,
                    'reported_reviewer_relationship':assessment.reported_reviewer_relationship,
                    'execution_attested':False,'reviewer_relationship_verified':False},
                'limitations':list(use.limitations),'unresolved':list(projection.unresolved),
                'reasons':list(dict.fromkeys(reasons)),'full_document_qualified':False,'field_coverage_qualified':False,
                'population_completeness_qualified':False,
                'scientific_truth_proven':False,'physical_execution_granted':False,'publication_granted':False}
            if statement_scope is not None:
                payload['statement_scope'] = statement_scope
            if formula_scope is not None:
                payload['formula_scope']=formula_scope
            if use.purpose in predecessors:
                item, previous = predecessors[use.purpose]
                payload['supersedes'] = {'qualification_ref':item.qualification_ref.model_dump(mode='json'),
                    'payload_digest':semantic_digest(previous.payload), 'reason':item.reason}
            receipt = self.intake.ledger.append(RecordKind.KNOWLEDGE_USE_QUALIFICATION,payload,
                authority='qualification_service',occurred_at=request['occurred_at'])
            ref = RevisionRef(ref=receipt.record_id,revision_digest=record_digest(receipt.record_id))
            previous = predecessors[use.purpose][1] if use.purpose in predecessors else None
            entry,current_value = decision_write(self.store,receipt,previous=previous)
            entries.append(entry)
            prepared_qualifications.append((receipt,current_value))
            results.append({'purpose':use.purpose,'status':payload['status'],'qualification_ref':ref.model_dump(mode='json'),
                'roots':payload['roots'],'reasons':payload['reasons'],'limitations':payload['limitations'],
                'field_coverage_qualified':False,'scientific_truth_proven':False})
        if self.prepared_store is not None and registry is not None:
            self.prepared_store.stage(projection=projection,registry=registry,native_record=record,
                mechanical={'saved':mechanical,'report':self.checks._receipt(mechanical,mechanical['input'])},
                qualification_records=prepared_qualifications,read_revision=read)
        current, fences = self.checks._context(authorization,bundle_ref)
        if (current != row or qualification_policy() != policy
                or semantic_digest(shipped_checker_release()) != mechanical['input']['checker_release_digest']):
            raise ValueError('KNOWLEDGE_USE_CURRENT_CONTEXT_CHANGED')
        # Revalidate native/source inputs after constructing the assessment, then
        # join exact current confirmation/head/check fences to index publication.
        self.checks._current_result(read,{'object_id':assessment.target_object_id},'',mechanical,mechanical['input'])
        if not self.store.atomic_compare_and_write((*fences,*read.identity_fences(),check_fence,
                AtomicWrite(REQUESTS,request_key,request,request),*entries)):
            raise ValueError('KNOWLEDGE_USE_COMMIT_STATE_CHANGED')
        self.checks._context(authorization,bundle_ref)
        for receipt,_ in prepared_qualifications:
            require_current(receipt,self.store.get(QUALIFICATIONS,qualification_key(handle.revision,receipt.payload['purpose'])))
        return {'bundle_ref':bundle_ref,'target_revision':handle.revision.model_dump(mode='json'),'uses':results,
            'basis':'authenticated_source_opinion_and_server_mechanical_checks','publication_committed':False,
            'reviewer_relationship_verified':False,'scientific_truth_proven':False}
