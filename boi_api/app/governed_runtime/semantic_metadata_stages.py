"""Definition-first services used by the existing bounded migration executor.

This is not another DAG, ledger, status machine or surface handler. Source and
authority resolvers are server-owned dependencies, never fields of a model/UI
request. The service can preserve candidates and evaluator receipts, not approve,
execute SQL, attest, create a Release or change an active pointer.
"""
from ..v2.atomic_store_contract import AtomicWrite
from .semantic_binding_contract import (
    EvidenceUse, SemanticBindingCandidate, semantic_digest,
)
from .semantic_binding_validator import validate_semantic_binding
from .metadata_atomic_draft import (
    MetadataAtomicDraft, MetadataLogicalDraft, LogicalSemanticClaim, ResolvedSemanticDraft,
    read_definition_first_scope, prepare_definition_first_input, bind_draft_to_record,
)
from .semantic_inference_cache import (
    FrozenSemanticInferenceCache, SemanticInferenceRequest, SemanticInferenceRequestV2, InferenceAttemptContext, canonical,
)


class SemanticMetadataStageServices:
    def __init__(self, *, store, records, definitions, principal_id, policy_digest,
                 run_ref, shard_ref, channel, identity, model_policy, invoke,
                 resolved_draft_resolver=None, validation_context_resolver=None,
                 canonical_record_verifier=None, model_input_authorizer=None,
                 intake_attention=(), max_derived_candidates=100, identity_provider=None,
                 physical_mapping_service=None, query_contract_service=None, output_model=MetadataAtomicDraft,
                 model_request_builder=None, reviewed_input=None, source_meaning_client=None,
                 source_meaning_context_verifier=None):
        self.store = store
        self.records = tuple(records)
        self.definitions = definitions
        self.principal_id, self.policy_digest = principal_id, policy_digest
        self.run_ref, self.shard_ref, self.channel = run_ref, shard_ref, channel
        self.identity, self.model_policy, self.invoke = identity, model_policy, invoke
        self.identity_provider=identity_provider
        self.physical_mapping_service=physical_mapping_service
        self.query_contract_service=query_contract_service
        if output_model not in (MetadataAtomicDraft,MetadataLogicalDraft):
            raise ValueError('SEMANTIC_DRAFT_CONTRACT_UNSUPPORTED')
        self.output_model=output_model
        self.model_request_builder=model_request_builder
        self.resolved_draft_resolver = resolved_draft_resolver
        self.validation_context_resolver = validation_context_resolver
        self.canonical_record_verifier = canonical_record_verifier
        self.model_input_authorizer = model_input_authorizer
        if not 1<=max_derived_candidates<=100:
            raise ValueError('SHARD_SIZE_LIMIT_INVALID')
        self.max_derived_candidates=max_derived_candidates
        self.intake_attention=tuple(intake_attention)
        self.cache = FrozenSemanticInferenceCache(store)
        self.candidates = {}
        self.attention = list(self.intake_attention)
        self.validations = {}
        self.reviewed_input = reviewed_input
        self.profile_candidate_count = 0
        self.source_meaning_client=source_meaning_client
        self.source_meaning_context_verifier=source_meaning_context_verifier

    def _save(self, collection, payload):
        value = {**payload, 'employee_id':self.principal_id}
        ref = semantic_digest(value)
        current = self.store.get(collection, ref)
        if current is None:
            if self.store.atomic_compare_and_write((AtomicWrite(collection, ref, None, value),)):
                return ref
            current = self.store.get(collection, ref)
        if not current or {key:item for key,item in current.items() if key!='updated_at'} != value:
            raise ValueError('SEMANTIC_IMMUTABLE_RECORD_DRIFT')
        return ref

    def _intake(self, context):
        refs=[]
        for record in self.records:
            if record.record.artifact_ref.startswith('SourceArtifact:sha256:'):
                if self.canonical_record_verifier is None:
                    raise ValueError('SEMANTIC_CANONICAL_EVIDENCE_RESOLVER_REQUIRED')
                if self.canonical_record_verifier(record) != record:
                    raise ValueError('METADATA_RECORD_FIELD_CLOSURE_MISMATCH')
                refs.extend(span.span_ref for span in record.evidence)
                continue
            refs.extend(self._save('bulk_migration_evidence_spans', span.model_dump(mode='json'))
                        for span in record.evidence)
        return {'source_records':[r.record.model_dump(mode='json') for r in self.records],
                'source_record_count':len(self.records), 'evidence_record_refs':refs,
                'source_artifact_refs':sorted({r.record.artifact_ref for r in self.records}),
                'attention_items':list(self.intake_attention),
                'stage_status':'partial' if self.intake_attention else 'pass',
                'source_bytes_reemitted':False}, 0, 0, None

    def _draft(self, context, *, frozen_only=False):
        outputs=[];cache_receipts=[];reads=[];calls=0;input_bytes=0;source_meaning_results=[]
        for record in self.records:
            # A partial-stage preview may omit intake; it cannot omit source
            # authority, even when an approved deterministic draft is available.
            if record.record.artifact_ref.startswith('SourceArtifact:sha256:'):
                if self.canonical_record_verifier is None:
                    raise ValueError('SEMANTIC_CANONICAL_EVIDENCE_RESOLVER_REQUIRED')
                if self.canonical_record_verifier(record) != record:
                    raise ValueError('METADATA_RECORD_FIELD_CLOSURE_MISMATCH')
            reading=read_definition_first_scope(record=record,definitions=self.definitions,
                manifest_digest=context.manifest_digest,principal_id=self.principal_id,policy_digest=self.policy_digest)
            # A definition read precedes both deterministic and model extraction.
            reads.append(self._save('bulk_migration_receipts', reading.receipt))
            if self.reviewed_input is not None:
                from .metadata_atomic_draft import restore_logical_claim
                retained=[c for c in self.reviewed_input['candidates']
                    if c['source_record']==record.record.model_dump(mode='json')]
                if not retained:
                    raise ValueError('REVIEWED_DEFINITION_SOURCE_UNAVAILABLE')
                for candidate in retained:
                    claim=restore_logical_claim(candidate,record,self.definitions)
                    self.candidates[candidate['candidate_digest']]=(record,claim,candidate)
                    outputs.append(candidate)
                outcome_refs={c['output_receipt_digest'] for c in retained}
                retained_meanings=[m for m in self.reviewed_input.get('source_meaning_results',[])
                    if m.get('source_record')==record.record.model_dump(mode='json') and m.get('domain_outcome_digest') in outcome_refs]
                source_meaning_results.extend(retained_meanings)
                for meaning in retained_meanings:
                    qualifier=meaning.get('source_qualifier_receipt')
                    if qualifier and qualifier['status']=='partial':
                        self.attention.append({'record_identity_digest':record.record.identity_digest,
                            'reason_code':'SOURCE_QUALIFIER_INTERPRETATION_PENDING','detail_codes':qualifier['reason_codes'],
                            'source_qualifier_receipt_digest':qualifier['receipt_digest']})
                continue
            resolved=(self.resolved_draft_resolver(record,self.definitions)
                      if self.resolved_draft_resolver else None)
            if resolved is not None:
                if not isinstance(resolved,ResolvedSemanticDraft):
                    raise ValueError('SEMANTIC_EXTRACTION_RESOLUTION_CONTRACT_REQUIRED')
                resolved=resolved.verify_context(record=record,definitions=self.definitions,
                    principal_id=self.principal_id,policy_digest=self.policy_digest)
                draft=resolved.draft
                receipt_ref=self._save('bulk_migration_receipts',resolved.model_dump(mode='json'))
            else:
                if record.record.artifact_ref.startswith('SourceArtifact:sha256:'):
                    if self.model_input_authorizer is None or self.model_input_authorizer(record) is not True:
                        raise ValueError('SOURCE_MODEL_INPUT_NOT_AUTHORIZED')
                prepared=prepare_definition_first_input(record=record,definitions=self.definitions,
                    manifest_digest=context.manifest_digest,principal_id=self.principal_id,policy_digest=self.policy_digest,
                    output_contract_version=self.output_model.model_fields['contract_version'].default)
                identity=self.identity_provider() if self.identity_provider else self.identity
                if self.source_meaning_client is not None:
                    from .frozen_source_meaning import run_frozen_source_meaning
                    if self.source_meaning_context_verifier is None:
                        raise ValueError('SOURCE_MEANING_CONTEXT_VERIFIER_REQUIRED')
                    def verify_context():
                        self.source_meaning_context_verifier(record)
                        if self.model_input_authorizer(record) is not True:
                            raise ValueError('SOURCE_MODEL_INPUT_NOT_AUTHORIZED')
                    request=SemanticInferenceRequest(principal_id=self.principal_id,acl_policy_digest=self.policy_digest,
                        namespace=record.record.namespace,source_profile_digest=record.source_profile_digest,
                        semantic_input_digest=record.semantic_input_digest,
                        definition_closure_digest=semantic_digest(self.definitions.lookup),
                        output_contract_digest=semantic_digest(self.output_model.model_json_schema()),
                        skill_id='domain-ontology-draft',model_id=identity.model_id,model_digest=identity.model_digest,
                        role_digest=identity.role_digest,prompt_digest=identity.prompt_digest,
                        input_digest=prepared.input_digest,input_bytes=len(canonical(prepared.payload)),atomic_unit_count=4)
                    attempt=InferenceAttemptContext(run_ref=self.run_ref,shard_ref=self.shard_ref,
                        unresolved_reason='NO_APPROVED_SOURCE_READING',
                        evidence_span_refs=tuple(span.span_ref for span in record.evidence),
                        evidence_closure_digest=prepared.evidence_closure_digest,channel=self.channel)
                    result=run_frozen_source_meaning(cache=self.cache,payload=prepared.payload,
                        request_context=request,attempt=attempt,identity=identity,policy=self.model_policy,
                        build_wire=self.source_meaning_client.build_wire,invoke_wire=self.source_meaning_client.invoke_wire,
                        verify_context=verify_context,allow_inference=not frozen_only,
                        source_reading_model=self.source_meaning_client.MODELS['domain-ontology-draft'],
                        max_reading_passes=getattr(self.source_meaning_client,'max_reading_passes',1),
                        plan_contract_graph=getattr(self.source_meaning_client,'plan_contract_graph',False),
                        qualify_source=getattr(self.source_meaning_client,'qualify_source',False),
                        ground_subject_facets=getattr(self.source_meaning_client,'ground_subject_facets',False),
                        materialize_domain=getattr(self.source_meaning_client,'materialize_domain',False))
                    source_meaning_results.append({'source_record':record.record.model_dump(mode='json'),
                        **{key:value for key,value in result.items() if key not in {
                            'model_invocation_count','model_input_bytes','cache_hit_count'}}})
                    calls+=result['model_invocation_count'];input_bytes+=result['model_input_bytes']
                    if result.get('domain_draft') is not None:
                        draft=self.output_model.model_validate(result['domain_draft'])
                        reading=(result.get('contract_reading_receipt') or result['source_receipt'])['reading']
                        comparison=result['comparison_receipt']['comparison']
                        dependency_check=result.get('dependency_check')
                        qualifier_receipt=result.get('source_qualifier_receipt')
                        if qualifier_receipt is not None and qualifier_receipt['status']=='partial':
                            self.attention.append({'record_identity_digest':record.record.identity_digest,
                                'reason_code':'SOURCE_QUALIFIER_INTERPRETATION_PENDING',
                                'detail_codes':qualifier_receipt['reason_codes'],
                                'source_qualifier_receipt_digest':qualifier_receipt['receipt_digest']})
                        if dependency_check is not None and dependency_check['status']!='pass':
                            self.attention.append({'record_identity_digest':record.record.identity_digest,
                                'reason_code':'SOURCE_DRAFT_DEPENDENCY_INCOMPLETE',
                                'detail_codes':dependency_check['reason_codes'],'missing_refs':dependency_check['missing_refs'],
                                'dependency_check_receipt_digest':dependency_check['receipt_digest']})
                        if (reading['remaining_claims'] or reading['uncertainties'] or comparison['uncertainties']
                            or any(atom['missing_information'] for atom in reading['atoms'])
                            or draft.remaining_claims or draft.uncertainties or not draft.candidates
                            or any(claim.uncertainties or (claim.logical_definition is None and claim.proposed_concept is None)
                                   for claim in draft.candidates)):
                            self.attention.append({'record_identity_digest':record.record.identity_digest,
                                'reason_code':'SEMANTIC_EXTRACTION_INCOMPLETE'})
                        bound=bind_draft_to_record(draft=draft,record=record,definitions=self.definitions,
                            output_receipt_digest=result['domain_outcome_digest'])
                        for claim,candidate in zip(draft.candidates,bound):
                            self.candidates[candidate['candidate_digest']]=(record,claim,candidate)
                            outputs.append(candidate)
                        if result['cache_hit_count']:
                            cache_receipts.extend(ref for ref in result['inference_outcome_refs'] if ref)
                        continue
                    self.attention.append({'record_identity_digest':record.record.identity_digest,
                        'reason_code':'SOURCE_MEANING_LOGICAL_CONTRACT_PENDING',
                        'source_meaning_receipt_refs':result['receipt_refs'],'detail_codes':result['reason_codes']})
                    continue
                wire=None;wire_fields={};request_model=SemanticInferenceRequest
                if self.output_model is MetadataLogicalDraft:
                    if self.model_request_builder is None:
                        raise ValueError('SEMANTIC_MODEL_WIRE_CONTRACT_REQUIRED')
                    wire=self.model_request_builder(prepared.payload)
                    wire_fields={'wire_request_digest':semantic_digest(wire),'wire_input_bytes':len(canonical(wire))}
                    request_model=SemanticInferenceRequestV2
                request=request_model(principal_id=self.principal_id,acl_policy_digest=self.policy_digest,
                    namespace=record.record.namespace,source_profile_digest=record.source_profile_digest,
                    semantic_input_digest=record.semantic_input_digest,
                    definition_closure_digest=semantic_digest(self.definitions.lookup),
                    output_contract_digest=semantic_digest(self.output_model.model_json_schema()),
                    skill_id='domain-ontology-draft',model_id=identity.model_id,model_digest=identity.model_digest,
                    role_digest=identity.role_digest,prompt_digest=identity.prompt_digest,
                    input_digest=prepared.input_digest,input_bytes=len(canonical(prepared.payload)),atomic_unit_count=4,**wire_fields)
                attempt=InferenceAttemptContext(run_ref=self.run_ref,shard_ref=self.shard_ref,
                    unresolved_reason='NO_APPROVED_STRUCTURED_EXTRACTION',
                    evidence_span_refs=tuple(span.span_ref for span in record.evidence),
                    evidence_closure_digest=prepared.evidence_closure_digest,channel=self.channel)
                result=self.cache.run_frozen(request=request,attempt=attempt,payload=prepared.payload,
                    identity=identity,policy=self.model_policy,
                    invoke=lambda payload:self.invoke('domain-ontology-draft',payload,**(
                        {'expected_request_digest':wire_fields['wire_request_digest']} if wire_fields else {})),output_model=self.output_model,
                    allow_inference=not frozen_only,model_request=wire)
                calls+=result.invocation_count;input_bytes+=result.input_bytes*result.invocation_count
                if result.status!='PROVISIONAL':
                    self.attention.append({'record_identity_digest':record.record.identity_digest,
                        'reason_code':result.reason_code,'cache_key':result.cache_key})
                    continue
                receipt_ref=result.outcome_digest
                if result.cache_hit_count:cache_receipts.append(receipt_ref)
                draft=self.output_model.model_validate(result.output)
            if any(isinstance(claim,LogicalSemanticClaim) and claim.logical_definition is None
                   and claim.proposed_concept is None for claim in draft.candidates):
                self.attention.append({'record_identity_digest':record.record.identity_digest,
                    'reason_code':'LOGICAL_DOMAIN_CONTRACT_REQUIRED'})
            if draft.remaining_claims or draft.uncertainties or not draft.candidates or any(
                claim.uncertainties for claim in draft.candidates):
                self.attention.append({'record_identity_digest':record.record.identity_digest,
                    'reason_code':'SEMANTIC_EXTRACTION_INCOMPLETE'})
            bound=bind_draft_to_record(draft=draft,record=record,definitions=self.definitions,
                output_receipt_digest=receipt_ref)
            for claim,candidate in zip(draft.candidates,bound):
                self.candidates[candidate['candidate_digest']]=(record,claim,candidate)
                outputs.append(candidate)
        # Derived candidates, not input records, define the atomic review bound.
        if len(outputs)>self.max_derived_candidates:raise ValueError('DERIVED_CANDIDATE_SHARD_LIMIT_EXCEEDED')
        candidate_refs=[]
        for candidate in outputs:
            candidate_refs.append(self._save('bulk_migration_candidates',{**candidate,'run_id':self.run_ref,
                'shard_id':self.shard_ref,'state':'semantically_drafted','active_transition':False}))
        output={'domain_candidates':outputs,'derived_candidate_count':len(outputs),
                'candidate_record_refs':candidate_refs,
                'derived_candidate_limit':self.max_derived_candidates,
                'definition_reading_receipt_refs':reads,
                'candidate_cache_receipt_digests':cache_receipts,'attention_items':list(self.attention),
                'stage_status':'partial' if self.attention else 'pass'}
        if self.source_meaning_client is not None:
            output['source_meaning_results']=source_meaning_results
            if self.reviewed_input and self.reviewed_input.get('source_stage_receipt_ref'):
                output['retained_source_stage_receipt_ref']=self.reviewed_input['source_stage_receipt_ref']
        return output,calls,input_bytes,None

    def _match(self, context):
        matches=[];refs=[]
        if self.reviewed_input is not None:
            from .semantic_binding_validator import validate_reviewed_definitions
            reviewed=validate_reviewed_definitions(candidates=[item[2] for item in self.candidates.values()],
                records=self.records,definitions=self.definitions,receipt=self.reviewed_input['receipt'],
                dependency_candidates=self.reviewed_input.get('dependency_candidates',()))
            for digest,validation in reviewed.items():
                self.validations[digest]=validation
                refs.append(self._save('bulk_migration_receipts',validation.model_dump(mode='json')))
                accepted=validation.status=='REVIEWED_PROVISIONAL'
                matches.append({'candidate_digest':digest,'decision':'reviewed_new_definition' if accepted else 'review_candidate',
                    'classification':'PROVISIONAL','validated':False,'reviewed_contract_satisfied':accepted,
                    'duplicate_risk':not accepted,'reason_codes':list(validation.reason_codes),
                    'validation_receipt_digest':validation.receipt_digest,
                    'interpretation_receipt_digest':validation.review_receipt_digest})
                if not accepted:
                    self.attention.extend({'candidate_digest':digest,'reason_code':reason} for reason in validation.reason_codes)
            dependency_reviews=self.reviewed_input.get('dependency_candidates',())
            return {'match_candidates':matches,'validation_receipt_refs':refs,
                'interpretation_receipt_digests':sorted({self.reviewed_input['receipt']['receipt_digest'],
                    *(item['review_receipt_digest'] for item in dependency_reviews)}),
                'interpretation_receipt_refs':sorted({'interpretation-receipt:'+self.reviewed_input['receipt']['plan_digest'],
                    *(item['review_receipt_ref'] for item in dependency_reviews)}),
                'stage_status':'pass' if matches and all(m['reviewed_contract_satisfied'] for m in matches) else 'partial',
                'attention_items':list(self.attention)},0,0,None
        for candidate_digest,(record,claim,candidate) in sorted(self.candidates.items()):
            proposed=claim.proposed_concept
            if proposed is None:
                decision={'candidate_digest':candidate_digest,'decision':'new_candidate',
                    'validated':False,'reason_codes':['NEW_MEANING_REVIEW_REQUIRED'],'duplicate_risk':True}
                logical=candidate.get('logical_definition') or {}
                if logical.get('id') in {entry.entry_id for entry in self.definitions.entries}:
                    decision.update(decision='review_candidate',existing_logical_id_ref=logical['id'],
                        reason_codes=['EXISTING_LOGICAL_ID_REQUIRES_MATCH_REVIEW'])
            elif self.validation_context_resolver is None:
                decision={'candidate_digest':candidate_digest,'decision':'review_candidate',
                    'validated':False,'reason_codes':['SEMANTIC_AUTHORITY_CLOSURE_UNAVAILABLE']}
            else:
                authority,rule_ref=self.validation_context_resolver(record,self.definitions,claim)
                uses=tuple(EvidenceUse(**record.evidence[index].model_dump(mode='json'),
                    supports_contract_digest=semantic_digest(claim.semantics),
                    supports_fields=('definition','role','quantity_kind_ref','unit_ref','scope','conditions','exceptions'),
                    use_kind='reported_description',support_basis='model_proposed',review_receipt_ref=None)
                    for index in claim.field_indices)
                rule=authority.approved_rules.get(rule_ref.ref) if rule_ref else None
                binding=SemanticBindingCandidate(contract_version='boi/semantic-binding@0.1.0',
                    candidate_id=candidate_digest,source_record=record.record,
                    target_identity_ref=candidate['target_identity_ref'],source_semantics=claim.semantics,
                    relation_kind='concept_reuse',concept_ref=proposed.ref,concept_revision_digest=proposed.revision_digest,
                    evidence_uses=uses,dependency_refs=rule.required_dependency_refs if rule else (),approved_rule_ref=rule_ref)
                validation=validate_semantic_binding(binding,authority)
                refs.append(self._save('bulk_migration_receipts',validation.model_dump(mode='json')))
                self.validations[candidate_digest]=validation
                decision={'candidate_digest':candidate_digest,
                    'decision':'reuse_candidate' if validation.status=='VALIDATED' else 'review_candidate',
                    'validated':validation.status=='VALIDATED','reason_codes':list(validation.reason_codes),
                    'validation_receipt_digest':validation.receipt_digest}
            matches.append(decision)
            if not decision['validated']:
                self.attention.append({'candidate_digest':candidate_digest,
                    'reason_code':decision['reason_codes'][0]})
        return {'match_candidates':matches,'validation_receipt_refs':refs,
                'stage_status':'pass' if matches and all(item['validated'] for item in matches) else 'partial',
                'attention_items':list(self.attention)},0,0,None

    def _persist_profile_candidates(self, profile, output):
        """Same candidate store and atomic shard budget as Domain proposals.

        The versioned child envelope binds profile payloads to their exact
        semantic dependencies. It grants no validation or execution authority.
        """
        from .bulk_migration_qualification import profile_candidate_payload
        field={'data-mapping':'mapping_candidates','query':'query_candidates'}[profile]
        proposed=output.get(field) or []
        total=len(self.candidates)+self.profile_candidate_count+len(proposed)
        if total>self.max_derived_candidates:
            raise ValueError('DERIVED_CANDIDATE_SHARD_LIMIT_EXCEEDED')
        refs=[]
        for payload in proposed:
            candidate=profile_candidate_payload(profile,payload,sorted(self.candidates))
            refs.append(self._save('bulk_migration_candidates',{**candidate,
                'run_id':self.run_ref,'shard_id':self.shard_ref,
                'state':'semantically_drafted','active_transition':False}))
        self.profile_candidate_count+=len(proposed)
        return {**output,'derived_profile_contract_version':'boi/derived-profile-candidate@1',
            'candidate_record_refs':refs,'derived_candidate_count':len(proposed),
            'derived_candidate_total':total,'derived_candidate_limit':self.max_derived_candidates}

    def execute_stage(self, skill_id, *, context, prior_outputs, frozen_only=False):
        if context.migration_id!=self.run_ref:
            raise ValueError('SEMANTIC_RUN_CONTEXT_MISMATCH')
        if skill_id=='legacy-source-intake':return self._intake(context)
        if skill_id=='domain-ontology-draft':return self._draft(context,frozen_only=frozen_only)
        if skill_id=='existing-concept-match':return self._match(context)
        if skill_id=='physical-mapping-verify':
            if self.physical_mapping_service:
                output=self.physical_mapping_service(context=context,records=self.records,
                    definitions=self.definitions,candidates=dict(self.candidates),
                    validations=dict(self.validations),prior_outputs=prior_outputs)
                return self._persist_profile_candidates('data-mapping',output),0,0,None
            # Metadata meaning alone proves no physical key/grain/measurement.
            return {'mapping_candidates':[], 'query_readiness':'not_run',
                    'stage_status':'partial','attention_items':[{'reason_code':'PHYSICAL_MAPPING_CONTRACT_REQUIRED'}]},0,0,None
        if skill_id=='query-contract-author':
            if self.query_contract_service:
                output=self.query_contract_service(context=context,records=self.records,
                    definitions=self.definitions,candidates=dict(self.candidates),
                    validations=dict(self.validations),prior_outputs=prior_outputs)
                return self._persist_profile_candidates('query',output),0,0,None
            return {'query_candidates':[], 'stage_status':'partial',
                    'attention_items':[{'reason_code':'QUERY_CONTRACT_NOT_ESTABLISHED'}]},0,0,None
        if skill_id=='migration-batch-review':
            attention=[*self.attention,*(item for result in prior_outputs.values()
                for item in result.get('attention_items',[]) if item not in self.attention)]
            material={'candidate_digests':sorted(self.candidates),
                'validation_receipt_digests':sorted(v.receipt_digest for v in self.validations.values()),
                'source_manifest_digest':context.manifest_digest,'before_hashes':context.before_hashes,
                'definition_closure_digest':semantic_digest(self.definitions.lookup),
                'policy_digest':self.policy_digest,'attention_items':attention}
            return {'review_plan':material,'preview_hash':semantic_digest(material),
                'attention_items':attention,'stage_status':'partial' if attention else 'pass'},0,0,None
        if skill_id=='harness-evolution':
            return {'rule_candidates':[],'skill_candidates':[],
                'evaluation_candidates':sorted({item['reason_code'] for item in self.attention})},0,0,None
        raise ValueError('METADATA_PIPELINE_STAGE_UNSUPPORTED')
