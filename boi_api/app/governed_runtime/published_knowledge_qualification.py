"""Requalify an exact published revision from preserved, source-bound opinions.

Current edit and explicit source rights are required. An optional new full
native-inventory review is attributed separately from reused node opinions.
No upload is reopened or truth invented; previous decisions/checks remain intact.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json

from .knowledge_content import decode_knowledge_content
from .knowledge_profile_projector import ADAPTER_REVISION, KnowledgeProfileProjector
from .knowledge_projection_contract import ProjectionPublication, PublicationChange
from .knowledge_use_contract import LocalMeaningJudgment, typed_use_closure
from .knowledge_unresolved_scope import overlaps, statement_unresolved_decision
from .formula_context_qualification import formula_unresolved_decision
from .knowledge_use_decisions import QUALIFICATIONS, decision_key, predecessor, require_current, decision_write, source_opinion_reasons
from .ledger import RecordKind, record_digest
from .local_knowledge_qualification import REQUESTS, qualification_policy
from .native_knowledge_checks import shipped_checker_release
from .published_knowledge_context import PublishedKnowledgeContext
from .published_knowledge_contract import PublishedQualificationRead, PublishedQualificationRefresh
from .published_native_checks import PublishedNativeChecks
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import byte_digest
from ..v2.atomic_store_contract import AtomicWrite


class PublishedKnowledgeQualification:
    def __init__(self,spaces,*,current_authorization,prepared_store=None):
        self.spaces,self.intake,self.store=spaces,spaces.intake,spaces.store
        self.current_authorization=current_authorization
        from .knowledge_prepared_postgres import PostgresKnowledgePreparedStore
        if prepared_store is not None and (not isinstance(prepared_store,PostgresKnowledgePreparedStore)
                or prepared_store.authority_store is not self.store):
            raise ValueError('KNOWLEDGE_PREPARED_AUTHORITY_STORE_MISMATCH')
        self.prepared_store=prepared_store

    def _context(self,actor_id,revision):
        return PublishedKnowledgeContext(self.spaces,actor_id=actor_id,revision=revision,
            current_authorization=self.current_authorization)

    def current(self,*,actor_id,request):
        req=PublishedQualificationRead.model_validate(request)
        context=self._context(actor_id,req.revision)
        _,asset=context.read(req.revision)
        content=decode_knowledge_content(json.loads(asset.content_json))
        if content is None or asset.kind!='definition':
            raise ValueError('KNOWLEDGE_USE_DEFINITION_REQUIRED')
        policy,release=qualification_policy(),shipped_checker_release()
        observed,uses=[],[]
        for contract in content.use_contracts:
            key=decision_key(req.revision,contract.purpose)
            entry=self.store.get(QUALIFICATIONS,key)
            if entry is None:
                uses.append({'purpose':contract.purpose,'qualification_ref':None,'status':'not_assessed'})
            else:
                record=predecessor(self.intake.ledger,RevisionRef.model_validate(entry['qualification_ref']),
                    revision=req.revision,purpose=contract.purpose,stable_id=context.stable_id)
                require_current(record,entry)
                value=record.payload
                uses.append({'purpose':contract.purpose,'qualification_ref':entry['qualification_ref'],
                    'status':value['status'],'reasons':value['reasons'],'limitations':value['limitations'],
                    'supersedes':value.get('supersedes'),'qualified_by':entry['employee_id'],
                    'assessment_authenticated_principal':value['provenance']['authenticated_principal'],
                    'policy_current':value['qualification_policy_digest']==semantic_digest(policy),
                    'checker_current':value['checker_release_digest']==semantic_digest(release)})
            observed.append((key,entry))
        context.fences()
        if (policy!=qualification_policy() or release!=shipped_checker_release()
                or any(self.store.get(QUALIFICATIONS,key)!=entry for key,entry in observed)):
            raise ValueError('KNOWLEDGE_REFRESH_CURRENT_CHANGED')
        return {'stable_id':context.stable_id,'revision':req.revision.model_dump(mode='json'),
            'uses':uses,'basis':'stored_decision_metadata','use_granted':False,'publication_changed':False}

    def _opinion(self,context,content,scope,previous):
        value=previous.payload
        if (value['scope_digest']!=scope['scope_digest'] or value['roots']!=list(scope['roots'])
                or value['closure']!=list(scope['closure'])):
            raise ValueError('KNOWLEDGE_REFRESH_OPINION_SCOPE_CHANGED')
        nodes={node['pointer']:node for node in value['assessed_nodes']}
        if len(nodes)!=len(value['assessed_nodes']) or set(nodes)!=set(scope['closure']):
            raise ValueError('KNOWLEDGE_REFRESH_OPINION_CLOSURE_CHANGED')
        judgments={}
        for pointer,node in scope['nodes'].items():
            old=nodes[pointer]
            judgment=LocalMeaningJudgment.model_validate(old['judgment'])
            if old['native_value_digest']!=semantic_digest(node) or judgment.pointer!=pointer:
                raise ValueError('KNOWLEDGE_REFRESH_OPINION_NODE_CHANGED')
            bindings=[b for b in content.evidence_bindings
                if b.meaning_pointer==pointer or b.meaning_pointer.startswith(pointer+'/')]
            required={(b.source_revision_digest,b.field_locator) for b in bindings}
            observed=set()
            if not required or not old['source_bindings']:
                raise ValueError('KNOWLEDGE_REFRESH_SOURCE_CLOSURE_MISSING')
            quotations=[q.model_dump(mode='json') for q in judgment.evidence]
            for source in old['source_bindings']:
                if source['quote'] not in quotations:
                    raise ValueError('KNOWLEDGE_REFRESH_OPINION_QUOTE_CHANGED')
                match=next((b for b in bindings if b.span.model_dump(mode='json')==source['span']
                    and b.source_revision_digest==source['source_revision_digest']
                    and b.field_locator==source['quote']['field_locator']),None)
                if match is None:
                    raise ValueError('KNOWLEDGE_REFRESH_SOURCE_BINDING_CHANGED')
                span=self.intake.ledger.read(match.span.ref)
                if (span.kind!=RecordKind.EVIDENCE_SPAN or record_digest(span.record_id)!=match.span.revision_digest
                        or span.payload['artifact_ref'] not in context.source_observed
                        or span.payload['content_digest']!=source['field_digest']):
                    raise ValueError('KNOWLEDGE_REFRESH_SOURCE_SPAN_CHANGED')
                receipt=context.source_observed[span.payload['artifact_ref']]
                if receipt['reference']['digest']!=source['quote']['source_byte_digest']:
                    raise ValueError('KNOWLEDGE_REFRESH_SOURCE_DIGEST_CHANGED')
                raw=self.intake.objects.get(span.payload['field_object_ref'])
                if byte_digest(raw)!=source['field_digest']:
                    raise ValueError('KNOWLEDGE_REFRESH_SOURCE_FIELD_CHANGED')
                text,start=raw.decode('utf-8'),-1
                for _ in range(source['quote']['quote_occurrence']+1):
                    start=text.find(source['quote']['quote'],start+1)
                    if start<0:
                        raise ValueError('KNOWLEDGE_REFRESH_SOURCE_QUOTE_MISSING')
                observed.add((match.source_revision_digest,match.field_locator))
            if not required<=observed:
                raise ValueError('KNOWLEDGE_REFRESH_SOURCE_CLOSURE_MISSING')
            judgments[pointer]=judgment
        return judgments

    def _recorded_review(self, previous, purpose):
        from .published_knowledge_contract import PublishedStatementReview
        value=previous.payload
        provenance=value.get('statement_review_submission')
        scope=value.get('statement_scope',{})
        if (not isinstance(provenance,dict)
                or semantic_digest(provenance)!=scope.get('review_submission_digest')
                or provenance.get('request_ref')!=value.get('refresh_request_ref')
                or provenance.get('authenticated_principal')!=value.get('qualified_by')):
            raise ValueError('KNOWLEDGE_REFRESH_RECORDED_REVIEW_REQUIRED')
        submitted=PublishedStatementReview.model_validate(provenance['submission'])
        if (submitted.purpose!=purpose or semantic_digest(submitted)!=provenance.get('submission_digest')
                or semantic_digest(submitted.review)!=scope.get('review_digest')
                or any(provenance.get(k)!=value.get(k) for k in
                    ('knowledge_revision','source_manifest_digest','qualification_policy_digest','checker_release_digest'))):
            raise ValueError('KNOWLEDGE_REFRESH_RECORDED_REVIEW_BINDING_CHANGED')
        # These are old individual judgments, never inferred from prior status.
        # The ordinary full-inventory/evidence/policy checks below run again.
        return submitted

    def refresh(self,*,actor_id,request):
        req=PublishedQualificationRefresh.model_validate(request)
        context=self._context(actor_id,req.revision)
        native,asset=context.read(req.revision)
        content=decode_knowledge_content(json.loads(asset.content_json))
        if content is None or asset.kind!='definition':
            raise ValueError('KNOWLEDGE_USE_DEFINITION_REQUIRED')
        contracts={u.purpose:u for u in content.use_contracts}
        previous={}
        for item in req.supersedes:
            if item.purpose not in contracts:
                raise ValueError('KNOWLEDGE_REFRESH_USE_CONTRACT_REQUIRED')
            previous[item.purpose]=predecessor(self.intake.ledger,item.qualification_ref,
                revision=req.revision,purpose=item.purpose,stable_id=context.stable_id)
        reused_reviews={purpose:self._recorded_review(previous[purpose],purpose)
            for purpose in req.reuse_statement_reviews}
        # Reconstruct current typed data using exact native refs, not original
        # upload paths or the original author's access token.
        scope_ref='published-knowledge-check:'+semantic_digest(req.model_dump(mode='json'))
        # The in-memory projection manifest describes the existing native
        # identity. context.read authorizes the current editor independently.
        manifest=ProjectionPublication(scope_id=scope_ref,principal_id=native.payload['employee_id'],base_generation=0,
            policy_digest=context.authorization.policy_digest,confirmation_ref=scope_ref,
            source_manifest_digest=native.payload['source_manifest_digest'],adapter_revision=ADAPTER_REVISION,
            changes=(PublicationChange(stable_id=context.stable_id,operation='upsert',revision=req.revision.model_dump(mode='json'),
                previous_revision=None),))
        batch,registry=KnowledgeProfileProjector(read_revision=context.read).materialize_with_registry(manifest)
        projection=batch.objects[0]
        context.observe_identity_targets(content)
        policy,release=qualification_policy(),shipped_checker_release()
        request_input={'contract_version':'boi/published-knowledge-refresh@1','actor_id':actor_id,
            'revision':req.revision.model_dump(mode='json'),
            'supersedes':[item.model_dump(mode='json') for item in sorted(req.supersedes,key=lambda item:item.purpose)],
            'authority':context.binding(),'qualification_policy_digest':semantic_digest(policy),
            'checker_release_digest':semantic_digest(release)}
        if req.reuse_statement_reviews:
            request_input['reuse_statement_reviews']=sorted(req.reuse_statement_reviews)
        if req.statement_reviews:
            request_input['statement_reviews']=[item.model_dump(mode='json')
                for item in sorted(req.statement_reviews,key=lambda item:item.purpose)]
        if req.formula_reviews:
            request_input['formula_reviews']=[item.model_dump(mode='json') for item in req.formula_reviews]
        key='published-use-request:'+semantic_digest(request_input)
        saved=self.store.get(REQUESTS,key)
        for item in req.supersedes:
            entry=self.store.get(QUALIFICATIONS,decision_key(req.revision,item.purpose))
            if entry is not None and entry['qualification_ref']==item.qualification_ref.model_dump(mode='json'):
                require_current(previous[item.purpose],entry)
            else:
                if saved is None or entry is None:
                    raise ValueError('KNOWLEDGE_USE_SUPERSESSION_CURRENT_CHANGED')
                current=predecessor(self.intake.ledger,RevisionRef.model_validate(entry['qualification_ref']),
                    revision=req.revision,purpose=item.purpose,stable_id=context.stable_id)
                require_current(current,entry)
                if current.payload.get('refresh_request_ref')!=key:
                    raise ValueError('KNOWLEDGE_USE_SUPERSESSION_CURRENT_CHANGED')
        if saved is None:
            value={'employee_id':actor_id,'input':request_input,'occurred_at':datetime.now(timezone.utc).isoformat()}
            if not self.store.atomic_compare_and_write((*context.fences(),AtomicWrite(REQUESTS,key,None,value))):
                raise ValueError('KNOWLEDGE_REFRESH_REQUEST_CHANGED')
            saved=self.store.get(REQUESTS,key)
        if saved is None or saved.get('input')!=request_input or saved.get('employee_id')!=actor_id:
            raise ValueError('KNOWLEDGE_REFRESH_REQUEST_BINDING_CHANGED')
        checker=PublishedNativeChecks(context)
        binding={'contract_version':'boi/native-mechanical-input@1','employee_id':actor_id,
            'policy_digest':context.authorization.policy_digest,'refresh_request_ref':key,
            'authorization_basis':'current_published_knowledge_editor','confirmation_ref':scope_ref,
            'object_id':context.stable_id,'target_revision':req.revision.model_dump(mode='json'),
            'intended_uses':sorted(previous),'checker_release_digest':semantic_digest(release)}
        mechanical,check_fence=checker.execute(binding,release)
        report=checker._receipt(mechanical,binding)
        from .knowledge_definition_checks import required_definition_capabilities
        required=required_definition_capabilities(content,qualified_use=True)
        if report['outcome']!='completed' or not required<={r['capability'] for r in report['checks'] if r['outcome']=='satisfied'}:
            raise ValueError('KNOWLEDGE_USE_MECHANICAL_PROPERTIES_REQUIRED')
        entries,prepared,uses=[],[],[]
        reviews={**reused_reviews,**{item.purpose:item for item in req.statement_reviews}}
        formula_reviews={item.purpose:item for item in req.formula_reviews}
        for item in req.supersedes:
            old=previous[item.purpose]
            if (old.payload['policy_digest']!=native.payload['policy_digest']
                    or old.payload['source_manifest_digest']!=native.payload['source_manifest_digest']):
                raise ValueError('KNOWLEDGE_REFRESH_OPINION_BINDING_CHANGED')
            contract=contracts[item.purpose];scope=typed_use_closure(content,contract)
            judgments=self._opinion(context,content,scope,old)
            submission=reviews.get(item.purpose)
            statement_scope=None
            if submission is not None:
                statement_scope=statement_unresolved_decision(content,scope,review=submission.review,
                    original_unresolved=content.unresolved,projection=projection,registry=registry,
                    evidence_validator=lambda unresolved,judgment:self._review_evidence(
                        context,content,unresolved,judgment))
                statement_scope['binding']={
                    'knowledge_revision':req.revision.model_dump(mode='json'),
                    'source_manifest_digest':native.payload['source_manifest_digest'],
                    'assessment_byte_digest':old.payload['assessment_byte_digest'],
                    'qualification_policy_digest':semantic_digest(policy),
                    'checker_release_digest':semantic_digest(release)}
            formula_submission=formula_reviews.get(item.purpose)
            formula_scope=None
            if formula_submission is not None:
                formula_scope=formula_unresolved_decision(content,scope,review=formula_submission.review,
                    original_unresolved=content.unresolved,projection=projection,registry=registry,
                    evidence_validator=lambda unresolved,judgment:self._review_evidence(context,content,unresolved,judgment))
                formula_scope['binding']={
                    'knowledge_revision':req.revision.model_dump(mode='json'),
                    'source_manifest_digest':native.payload['source_manifest_digest'],
                    'assessment_byte_digest':old.payload['assessment_byte_digest'],
                    'qualification_policy_digest':semantic_digest(policy),
                    'checker_release_digest':semantic_digest(release)}
            reasons=source_opinion_reasons(policy,item.purpose,contract,scope,judgments,
                mechanical_report=report,statement_scope=statement_scope,formula_scope=formula_scope)
            formula_review_required='formula_scope' in old.payload or 'formula_review_required' in old.payload
            if formula_review_required and formula_submission is None:
                reasons.append('FORMULA_SOURCE_REVIEW_REFRESH_REQUIRED')
            statement_review_required = ('statement_scope' in old.payload or
                'statement_review_required' in old.payload)
            if statement_review_required and submission is None:
                # Replaying node opinions is not a new full-inventory review,
                # and cannot turn a statement-only grant into a legacy grant.
                reasons.append('KNOWLEDGE_STATEMENT_SOURCE_REVIEW_REFRESH_REQUIRED')
            value={**deepcopy(old.payload),'qualified_by':actor_id,'status':'not_qualified' if reasons else 'usable_with_limits',
                'qualification_policy':policy,'qualification_policy_digest':semantic_digest(policy),
                'mechanical_check_ref':mechanical['check_ref'],'checker_release_digest':semantic_digest(release),
                'fact_bindings':[{'meaning_pointer':f.meaning_pointer,'fact_digest':semantic_digest(f)}
                    for f in projection.facts if f.meaning_pointer in scope['roots']],
                'reasons':reasons,'unresolved':list(projection.unresolved),'refresh_request_ref':key,
                'refresh_authority':request_input['authority'],
                'supersedes':{'qualification_ref':item.qualification_ref.model_dump(mode='json'),
                    'payload_digest':semantic_digest(old.payload),'reason':item.reason},
                'opinion_reused_without_new_semantic_review':(submission is None or item.purpose in reused_reviews) and formula_submission is None,
                'node_opinions_reused':True,
                'full_document_qualified':False,'field_coverage_qualified':False,'population_completeness_qualified':False,
                'scientific_truth_proven':False,'physical_execution_granted':False,'publication_granted':False}
            # Reused node opinions do not replay the original inventory review.
            # Only an explicit new submission can create a new statement scope.
            value.pop('statement_scope', None)
            value.pop('statement_review_submission', None)
            value.pop('formula_scope',None)
            value.pop('formula_review_submission',None)
            if formula_scope is not None:
                provenance={'contract_version':'boi/published-formula-review-submission@1',
                    'request_ref':key,'authenticated_principal':actor_id,
                    'submission':formula_submission.model_dump(mode='json'),
                    'submission_digest':semantic_digest(formula_submission),
                    **{name:formula_scope['binding'][name] for name in (
                        'knowledge_revision','source_manifest_digest','qualification_policy_digest','checker_release_digest')},
                    'execution_attested':False,'reviewer_relationship_verified':False}
                formula_scope['review_submission_digest']=semantic_digest(provenance)
                value['formula_review_submission']=provenance
                value['formula_scope']=formula_scope
                value.pop('formula_review_required',None)
            elif formula_review_required:
                value['formula_review_required']=True
            if statement_scope is not None:
                if reasons:
                    statement_scope['eligible_fact_bindings']=[]
                provenance={'contract_version':'boi/published-statement-review-submission@1',
                    'request_ref':key,'authenticated_principal':actor_id,
                    'submission':submission.model_dump(mode='json'),
                    'submission_digest':semantic_digest(submission),
                    **{name:statement_scope['binding'][name] for name in (
                        'knowledge_revision','source_manifest_digest','qualification_policy_digest','checker_release_digest')},
                    'execution_attested':False,'reviewer_relationship_verified':False}
                if item.purpose in reused_reviews:
                    original=old.payload['statement_review_submission']
                    prior_trace=original.get('revalidated_original_review',{})
                    provenance['revalidated_original_review']={
                        'qualification_ref':item.qualification_ref.model_dump(mode='json'),
                        'provenance_digest':semantic_digest(original),
                        'original_authenticated_principal':prior_trace.get('original_authenticated_principal',original['authenticated_principal']),
                        'new_semantic_review':False}
                statement_scope['review_submission_digest']=semantic_digest(provenance)
                value['statement_review_submission']=provenance
                value['statement_scope']=statement_scope
                value.pop('statement_review_required',None)
            elif statement_review_required:
                value['statement_review_required'] = True
            record=self.intake.ledger.append(RecordKind.KNOWLEDGE_USE_QUALIFICATION,value,
                authority='qualification_service',occurred_at=saved['occurred_at'])
            entry,current=decision_write(self.store,record,previous=old)
            entries.append(entry);prepared.append((record,current))
            uses.append({'purpose':item.purpose,'status':value['status'],'qualification_ref':current['qualification_ref'],
                'reasons':reasons,'limitations':value['limitations'],'qualified_by':actor_id,
                'assessment_authenticated_principal':value['provenance']['authenticated_principal']})
        if self.prepared_store is not None and registry is not None:
            self.prepared_store.stage(projection=projection,registry=registry,native_record=native,
                mechanical={'saved':mechanical,'report':report},qualification_records=prepared,read_revision=context.read)
        fences=context.fences()
        if policy!=qualification_policy() or release!=shipped_checker_release() or context.binding()!=request_input['authority']:
            raise ValueError('KNOWLEDGE_REFRESH_POLICY_OR_AUTHORITY_CHANGED')
        if not self.store.atomic_compare_and_write((*fences,check_fence,AtomicWrite(REQUESTS,key,saved,saved),*entries)):
            raise ValueError('KNOWLEDGE_REFRESH_COMMIT_STATE_CHANGED')
        context.fences()
        for record,_ in prepared:
            require_current(record,self.store.get(QUALIFICATIONS,decision_key(req.revision,record.payload['purpose'])))
        return {'stable_id':context.stable_id,'revision':req.revision.model_dump(mode='json'),
            'uses':uses,'refresh_request_ref':key,'opinion_reused_without_new_semantic_review':not bool(req.statement_reviews or req.formula_reviews),
            'node_opinions_reused':True,'statement_source_reviews_submitted':sorted(x.purpose for x in req.statement_reviews),
            'recorded_statement_reviews_revalidated':sorted(reused_reviews),
            'publication_changed':False,'scientific_truth_proven':False}

    def _review_evidence(self,context,content,item,judgment):
        """Bind newly submitted quotations to the current native source closure."""
        pointer=item.meaning_pointer or ''
        parts=pointer.split('/')
        if len(parts)>=3 and parts[1] in ('assertions','parameters'):
            pointer='/'.join(parts[:3])
        bindings=[binding for binding in content.evidence_bindings if overlaps(pointer,binding.meaning_pointer)]
        if item.source_spans:
            required=set(item.source_spans)
            bindings=[binding for binding in bindings if binding.span in required]
            if {binding.span for binding in bindings}!=required:
                raise ValueError('KNOWLEDGE_STATEMENT_UNRESOLVED_SOURCE_CLOSURE_MISSING')
        required={(binding.source_revision_digest,binding.field_locator) for binding in bindings}
        if not required:
            raise ValueError('KNOWLEDGE_REFRESH_SOURCE_CLOSURE_MISSING')
        observed,receipts=set(),[]
        for quote in judgment.evidence:
            source=quote.existing_source.model_dump(mode='json')
            current=context.source_observed.get(source['artifact_ref'])
            if current is None or current['reference']!=source:
                raise ValueError('KNOWLEDGE_REFRESH_SOURCE_DIGEST_CHANGED')
            matches=[]
            for binding in bindings:
                span=self.intake.ledger.read(binding.span.ref)
                if (span.kind!=RecordKind.EVIDENCE_SPAN
                        or record_digest(span.record_id)!=binding.span.revision_digest):
                    raise ValueError('KNOWLEDGE_REFRESH_SOURCE_SPAN_CHANGED')
                if span.payload['artifact_ref']==source['artifact_ref'] and binding.field_locator==quote.field_locator:
                    matches.append((binding,span))
            if not matches:
                raise ValueError('KNOWLEDGE_ASSESSMENT_QUOTE_OUTSIDE_NODE_EVIDENCE')
            for binding,span in matches:
                raw=self.intake.objects.get(span.payload['field_object_ref'])
                if byte_digest(raw)!=span.payload['content_digest']:
                    raise ValueError('KNOWLEDGE_REFRESH_SOURCE_FIELD_CHANGED')
                text,start=raw.decode('utf-8'),-1
                for _ in range(quote.quote_occurrence+1):
                    start=text.find(quote.quote,start+1)
                    if start<0:
                        raise ValueError('KNOWLEDGE_REFRESH_SOURCE_QUOTE_MISSING')
                observed.add((binding.source_revision_digest,binding.field_locator))
                receipts.append({'quote':quote.model_dump(mode='json'),'span':binding.span.model_dump(mode='json'),
                    'field_digest':span.payload['content_digest'],'source_revision_digest':binding.source_revision_digest})
        if not required<=observed:
            raise ValueError('KNOWLEDGE_REFRESH_SOURCE_CLOSURE_MISSING')
        return receipts
