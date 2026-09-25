"""Definition-first bounded input; no approval or equivalence authority."""
from dataclasses import dataclass

from pydantic import TypeAdapter
from boi_api.app.governed_runtime.semantic_binding_contract import ConceptLookupClosure, Digest, semantic_digest
from boi_api.app.governed_runtime.semantic_profile_loader import LoadedProfileEntry
from boi_api.app.governed_runtime.domain_profile_v02 import validate_domain_profile_entry as validate_v02
from boi_api.app.governed_runtime.domain_profile_v03 import validate_domain_profile_entry as validate_v03
from boi_api.app.governed_runtime.domain_profile_v04 import validate_domain_profile_entry as validate_v04
from boi_api.app.governed_runtime.domain_profile_v05 import validate_domain_profile_entry as validate_v05
import json

def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


@dataclass(frozen=True)
class DefinitionReading:
    model_definitions: tuple[dict, ...]
    receipt: dict
    receipt_digest: str


def read_existing_definitions(*, principal_id, policy_digest, lookup: ConceptLookupClosure,
                              entries: tuple[LoadedProfileEntry, ...], source_manifest_digest,
                              for_model: bool = True):
    """Consume ONLY active-release entries already resolved by the shared loader.

    This function cannot load entries from raw content_root or accept UI-proposed
    index items as authority. Service must pin actual release/index/scope first.
    A complete scope is not a global absence claim; the receipt carries its digest.
    """
    lookup = ConceptLookupClosure.model_validate(lookup.model_dump(mode='json'))
    source_manifest_digest = TypeAdapter(Digest).validate_python(source_manifest_digest)
    if lookup.principal_id!=principal_id or lookup.policy_digest!=policy_digest:
        raise ValueError('DEFINITION_READ_ACCESS_OR_POLICY_DENIED')
    if lookup.status!='complete':
        raise ValueError('DEFINITION_READ_LOOKUP_SCOPE_INCOMPLETE')
    if {entry.revision_digest for entry in entries}!=set(lookup.concept_revision_digests):
        raise ValueError('DEFINITION_READ_REVISION_CLOSURE_MISMATCH')
    if len({entry.entry_id for entry in entries})!=len(entries):
        raise ValueError('DEFINITION_READ_IDENTITY_AMBIGUOUS')
    definitions=[];refs=[]
    for entry in sorted(entries,key=lambda entry:entry.entry_id):
        if entry.category!='domain': raise ValueError('DEFINITION_READ_DOMAIN_ONLY')
        TypeAdapter(Digest).validate_python(entry.revision_digest)
        raw=entry.payload
        if raw.get('id') != entry.entry_id:
            raise ValueError('DEFINITION_READ_IDENTITY_MISMATCH')
        validator=(validate_v05 if 'semantic_evidence_uses' in raw else validate_v04
                   if 'semantic_contract' in raw else validate_v03 if 'versioning' in raw else validate_v02)
        try:
            validator(raw)
        except ValueError as error:
            raise ValueError('DEFINITION_READ_PROFILE_MIGRATION_REQUIRED') from error
        # Full validated logical definition, including Rule/Relation semantics;
        # no whitelist silently strips negation, applicability or exceptions.
        definitions.append({'concept_id':entry.entry_id,'revision_digest':entry.revision_digest,
                            'logical_definition':raw,'evidence_refs':list(entry.evidence_resources)})
        refs.append({'concept_id':entry.entry_id,'revision_id':entry.revision_id,
                     'revision_digest':entry.revision_digest,'payload_digest':semantic_digest(raw),
                     'evidence_refs':list(entry.evidence_resources)})
    if for_model and len(_canonical({'existing_definitions':definitions}))>11264:
        raise ValueError('DEFINITION_READ_BOUNDED_SCOPE_REQUIRED')
    receipt={'contract_version':'boi/definition-reading@0.1.0','principal_id':principal_id,
             'policy_digest':policy_digest,'lookup_closure_digest':semantic_digest(lookup),
             'source_manifest_digest':source_manifest_digest,'definitions':refs,
             'definition_input_digest':semantic_digest(definitions),'status':'READ',
             'semantic_equivalence_decided':False,'approved':False}
    if not for_model:
        receipt.update(contract_version='boi/definition-reading@0.2.0',
            scope_kind='authorized_definition_closure', model_input_prepared=False,
            definition_count=len(definitions))
    return DefinitionReading(tuple(definitions),receipt,semantic_digest(receipt))


class ActiveDefinitionAuthorityResolver:
    """Read-only bridge from active definitions to the existing semantic validator.

    No search matcher, new registry, approval writer or model fallback. Exact
    sanctioned interpretations are declared in Domain 0.5; legacy definitions
    remain readable but their evidence presence cannot authorize equivalence.
    """
    def __init__(self, *, source_intake, authorization, definitions, reload_definitions, current_authorization):
        self.intake=source_intake
        self.authorization=authorization
        self.definitions=definitions
        self.reload_definitions=reload_definitions
        self.current_authorization=current_authorization
        self.snapshot_digest=semantic_digest(definitions.model_dump(mode='json',exclude={'snapshot_digest'}))
        if self.snapshot_digest!=definitions.snapshot_digest:
            raise ValueError('SEMANTIC_ACTIVE_AUTHORITY_CLOSURE_STALE')
        current=reload_definitions()
        if current.lookup!=definitions.lookup or current.entries!=definitions.entries:
            raise ValueError('SEMANTIC_ACTIVE_AUTHORITY_CLOSURE_STALE')
        self.pointer=source_intake.ledger.active_pointer()
        if not self.pointer or self.pointer.get('release_manifest_digest')!=definitions.active_release_digest:
            raise ValueError('SEMANTIC_ACTIVE_AUTHORITY_CLOSURE_STALE')

    def _check(self,record,snapshot):
        if (snapshot!=self.definitions or self.intake.ledger.active_pointer()!=self.pointer
            or semantic_digest(snapshot.model_dump(mode='json',exclude={'snapshot_digest'}))!=self.snapshot_digest):
            raise ValueError('SEMANTIC_ACTIVE_AUTHORITY_CLOSURE_STALE')
        if (snapshot.lookup.principal_id!=self.authorization.principal
            or snapshot.lookup.policy_digest!=self.authorization.policy_digest
            or self.current_authorization()!=self.authorization):
            raise ValueError('SEMANTIC_AUTHORITY_ACCESS_DENIED')
        self.intake.metadata.verify_record(authorization=self.authorization,record=record)

    def _declarations(self,record,snapshot):
        self._check(record,snapshot)
        candidates=[]
        for entry in snapshot.entries:
            if 'semantic_evidence_uses' not in entry.payload:
                continue
            parsed=validate_v05(entry.payload)
            for declaration in parsed.semantic_reuse_declarations:
                if (declaration.namespace,declaration.source_system,declaration.dataset,
                    declaration.source_profile_digest,declaration.semantic_input_digest)!=(
                    record.record.namespace,record.record.source_system,record.record.dataset,
                    record.source_profile_digest,record.semantic_input_digest):
                    continue
                if declaration.policy_digest!=self.authorization.policy_digest:
                    raise ValueError('SEMANTIC_APPROVED_EXTRACTION_POLICY_STALE')
                if (any(i>=len(record.evidence) for i in declaration.field_indices)
                    or any(record.evidence[i].content_digest not in declaration.allowed_evidence_content_digests
                           for i in declaration.field_indices)):
                    raise ValueError('SEMANTIC_APPROVED_EXTRACTION_EVIDENCE_STALE')
                candidates.append((entry,declaration))
        return candidates

    def _definition(self,entry):
        from .semantic_binding_validator import SemanticDefinitionRevision
        parsed=validate_v05(entry.payload)
        if not parsed.semantic_evidence_uses:
            raise ValueError('SEMANTIC_DEFINITION_JUSTIFICATION_REQUIRED')
        receipt=self.intake.ledger.read(self.definitions.qualification_receipt_id)
        versions=receipt.payload.get('qualification_contract',{}).get('profile_versions',{})
        if versions.get('boi/domain')!='0.5.0':
            raise ValueError('SEMANTIC_AUTHORITY_PROFILE_NOT_QUALIFIED')
        evidence={}
        for use in parsed.semantic_evidence_uses:
            if use.span_ref not in entry.evidence_resources:
                raise ValueError('SEMANTIC_DEFINITION_SOURCE_CLOSURE_MISMATCH')
            # A bare human_reviewed flag is not an actual review receipt.
            if use.support_basis!='approved_structured_contract':
                raise ValueError('SEMANTIC_EVIDENCE_REVIEW_UNAVAILABLE')
            actual=self.intake.metadata.resolve_evidence(authorization=self.authorization,span_ref=use.span_ref)
            from .semantic_binding_validator import FieldEvidenceRecord
            if actual!=FieldEvidenceRecord.from_evidence_use(use):
                raise ValueError('SEMANTIC_DEFINITION_EVIDENCE_DRIFT')
            evidence[use.span_ref]=actual
        return SemanticDefinitionRevision(concept_ref=entry.entry_id,revision_digest=entry.revision_digest,
            semantic_contract=parsed.semantic_contract,evidence_uses=parsed.semantic_evidence_uses),evidence

    @staticmethod
    def _rule(entry,declaration):
        from .semantic_binding_validator import ApprovedSemanticRuleV2
        value=declaration.model_dump(mode='json')
        return ApprovedSemanticRuleV2(rule_ref=entry.entry_id+'#'+declaration.declaration_id,
            revision_digest=semantic_digest({'active_revision':entry.revision_digest,'declaration':value}),
            policy_digest=declaration.policy_digest,identity_basis=declaration.identity_basis,
            identity_ref=declaration.identity_ref,namespace=declaration.namespace,
            source_system=declaration.source_system,dataset=declaration.dataset,
            source_semantic_digest=semantic_digest(declaration.source_semantics),
            target_concept_ref=entry.entry_id,target_revision_digest=entry.revision_digest,
            target_semantic_digest=semantic_digest(entry.payload['semantic_contract']),
            relation_kind='concept_reuse',allowed_evidence_content_digests=declaration.allowed_evidence_content_digests,
            required_dependency_refs=declaration.required_dependency_refs,
            allow_scope_specialization=declaration.allow_scope_specialization,
            source_validity_policy=declaration.source_validity_policy)

    def validation_context(self,record,snapshot,claim):
        from .semantic_binding_contract import RevisionRef
        from .semantic_binding_validator import SemanticValidationContext
        eligible=self._declarations(record,snapshot)
        proposed=claim.proposed_concept
        selected=next((e for e in snapshot.entries if proposed and e.entry_id==proposed.ref
                       and e.revision_digest==proposed.revision_digest),None)
        definitions={};evidence={s.span_ref:s for s in record.evidence};rules={};rule_ref=None
        if selected and 'semantic_evidence_uses' in selected.payload:
            definition,actual=self._definition(selected)
            definitions[definition.concept_ref]=definition;evidence.update(actual)
        matches=[(entry,d) for entry,d in eligible if selected and entry.entry_id==selected.entry_id
                 and d.source_semantics==claim.semantics and d.field_indices==claim.field_indices]
        if len(matches)>1:
            raise ValueError('SEMANTIC_APPROVED_REUSE_AMBIGUOUS')
        if matches:
            rule=self._rule(*matches[0]);rules[rule.rule_ref]=rule
            rule_ref=RevisionRef(ref=rule.rule_ref,revision_digest=rule.revision_digest)
        context=SemanticValidationContext(principal_id=self.authorization.principal,
            policy_digest=self.authorization.policy_digest,profile_closure_digest=snapshot.lookup.profile_closure_digest,
            lookup=snapshot.lookup,definitions=definitions,approved_rules=rules,
            source_records={record.record.identity_digest:record.record},
            authorized_target_identity_refs=frozenset({'record-identity:'+record.record.identity_digest}),
            evidence_spans=evidence,available_dependencies={},approved_review_receipts={},
            conflicted_concept_refs=frozenset())
        return context,rule_ref

    def resolved_draft(self,record,snapshot):
        from .metadata_atomic_draft import ResolvedSemanticDraft,MetadataAtomicDraft,AtomicSemanticClaim
        from .semantic_binding_contract import EvidenceUse,RevisionRef,SemanticBindingCandidate
        from .semantic_binding_validator import validate_semantic_binding
        from .ledger import record_digest,RecordKind
        eligible=self._declarations(record,snapshot)
        if not eligible:
            return None
        if len(eligible)>4 or len({semantic_digest(d.source_semantics) for _,d in eligible})!=len(eligible):
            raise ValueError('SEMANTIC_APPROVED_REUSE_AMBIGUOUS')
        claims=[]
        for entry,declaration in eligible:
            claim=AtomicSemanticClaim(semantics=declaration.source_semantics,field_indices=declaration.field_indices,
                proposed_concept=RevisionRef(ref=entry.entry_id,revision_digest=entry.revision_digest))
            context,rule_ref=self.validation_context(record,snapshot,claim)
            uses=tuple(EvidenceUse(**record.evidence[i].model_dump(mode='json'),
                supports_contract_digest=semantic_digest(claim.semantics),
                supports_fields=('definition','role','quantity_kind_ref','unit_ref','scope','conditions','exceptions'),
                use_kind='reported_description',support_basis='approved_structured_contract',review_receipt_ref=None)
                for i in claim.field_indices)
            candidate=SemanticBindingCandidate(contract_version='boi/semantic-binding@0.1.0',
                candidate_id='resolved-extraction:'+semantic_digest(claim),source_record=record.record,
                target_identity_ref='record-identity:'+record.record.identity_digest,source_semantics=claim.semantics,
                relation_kind='concept_reuse',concept_ref=entry.entry_id,concept_revision_digest=entry.revision_digest,
                evidence_uses=uses,dependency_refs=declaration.required_dependency_refs,approved_rule_ref=rule_ref)
            verdict=validate_semantic_binding(candidate,context)
            if verdict.status!='VALIDATED':
                raise ValueError('SEMANTIC_APPROVED_EXTRACTION_NOT_VALIDATED')
            claims.append(claim)
        event_ref=self.pointer.get('activation_event_id') or self.pointer.get('rollback_receipt_id')
        event=self.intake.ledger.read(event_ref)
        if event.kind not in {RecordKind.ACTIVATION_EVENT,RecordKind.ROLLBACK_RECEIPT} or event.authority!='user':
            raise ValueError('SEMANTIC_ACTIVE_USER_AUTHORITY_REQUIRED')
        return ResolvedSemanticDraft(principal_id=self.authorization.principal,policy_digest=self.authorization.policy_digest,
            source_profile_digest=record.source_profile_digest,semantic_input_digest=record.semantic_input_digest,
            definition_closure_digest=semantic_digest(snapshot.lookup),
            approval_receipt_ref=RevisionRef(ref=event_ref,revision_digest=record_digest(event_ref)),
            draft=MetadataAtomicDraft(candidates=tuple(claims)))
