"""Common deterministic semantic validator over trusted, authorized closures.

Callers must resolve this context from the shared service/ledger, never from a
model's proposed JSON. The evaluator creates checks only; it cannot approve,
compile, execute, attest or activate anything. No search score is accepted.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal, Mapping

from pydantic import Field, model_validator, TypeAdapter

from .semantic_binding_contract import (
    ConceptLookupClosure, Digest, EvidenceUse, FrozenContract, Ref, RelationKind,
    RevisionRef, SemanticBindingCandidate, SemanticBindingCheck,
    SemanticBindingValidation, SemanticDescriptor, SourceRecordRevision,
    SEMANTIC_REQUIRED_CHECKS, semantic_digest,
)


_SUPPORT_FIELDS = frozenset({'definition', 'role', 'quantity_kind_ref', 'unit_ref', 'scope', 'conditions', 'exceptions'})
_EQUIVALENCE_KINDS = frozenset({'concept_reuse', 'synonym', 'target_identity'})
DEPENDENCY_REQUIRED_CHECKS = ('schema', 'key', 'type', 'unit', 'cardinality', 'grain', 'freshness', 'acl')


class FieldEvidenceRecord(FrozenContract):
    """Intake-verified byte/field lineage, without a proposed semantic claim."""
    span_ref: Ref
    span_digest: Digest
    content_digest: Digest
    record_identity_digest: Digest
    source_revision_digest: Digest
    snapshot_digest: Digest
    field_pointer: str
    representation: Literal['raw', 'normalized', 'translated', 'extracted']
    transformation_refs: tuple[RevisionRef, ...]

    @classmethod
    def from_evidence_use(cls, use: EvidenceUse):
        # Structural projection, NOT independent verification or intake authority.
        return cls.model_validate({key: value for key, value in use.model_dump().items() if key in cls.model_fields})


class SemanticDefinitionRevision(FrozenContract):
    concept_ref: Ref
    revision_digest: Digest
    semantic_contract: SemanticDescriptor
    evidence_uses: tuple[EvidenceUse, ...] = Field(min_length=1)


class ApprovedSemanticRule(FrozenContract):
    """An exact, pre-approved rule resolved by service; never generated here."""
    rule_ref: Ref
    revision_digest: Digest
    policy_digest: Digest
    identity_basis: Literal['approved_stable_identity', 'approved_scoped_alias']
    identity_ref: Ref
    namespace: Ref
    source_system: Ref
    dataset: Ref
    source_semantic_digest: Digest
    target_concept_ref: Ref
    target_revision_digest: Digest
    target_semantic_digest: Digest
    relation_kind: RelationKind
    allowed_evidence_content_digests: tuple[Digest, ...] = Field(min_length=1)
    required_dependency_refs: tuple[RevisionRef, ...]
    allow_scope_specialization: bool
    unit_conversion_ref: RevisionRef | None = None


class ApprovedSemanticRuleV2(ApprovedSemanticRule):
    """New rule revision: record lifecycle and claim applicability are distinct.

    Old rule bytes keep their original schema. No default business policy is
    inferred from capture time or from a model's suggested interpretation.
    """
    schema_version: Literal['boi/approved-semantic-rule@2'] = 'boi/approved-semantic-rule@2'
    source_validity_policy: Literal['metadata_revision_only', 'must_be_contained']


class ApprovedUnitConversion(FrozenContract):
    ref: Ref
    revision_digest: Digest
    from_unit_ref: Ref
    from_revision_digest: Digest
    to_unit_ref: Ref
    to_revision_digest: Digest
    quantity_kind_ref: Ref
    value_semantics: Literal['absolute', 'interval']
    scale: str
    offset: str

    @model_validator(mode='after')
    def finite_affine(self):
        try:
            scale, offset = Decimal(self.scale), Decimal(self.offset)
        except InvalidOperation as error:
            raise ValueError('SEMANTIC_UNIT_CONVERSION_INVALID') from error
        if not scale.is_finite() or not offset.is_finite() or scale == 0:
            raise ValueError('SEMANTIC_UNIT_CONVERSION_INVALID')
        if self.value_semantics == 'interval' and offset != 0:
            raise ValueError('SEMANTIC_INTERVAL_OFFSET_FORBIDDEN')
        return self


class DependencyCheck(FrozenContract):
    check_id: Ref
    status: Literal['pass', 'fail', 'flag', 'partial', 'skip', 'not_run']
    evidence_digest: Digest | None


class SemanticDependencyValidation(FrozenContract):
    """Resolved validator evidence, not mere presence of a mapping revision."""
    ref: Ref
    revision_digest: Digest
    profile_version: Ref
    schema_snapshot_digest: Digest
    policy_digest: Digest
    evaluator_code_digest: Digest
    checks: tuple[DependencyCheck, ...]
    receipt_ref: Ref
    receipt_digest: Digest

    @property
    def satisfied(self):
        return (tuple(check.check_id for check in self.checks) == DEPENDENCY_REQUIRED_CHECKS
                and all(check.status == 'pass' and check.evidence_digest for check in self.checks)
                and self.receipt_digest == semantic_digest(self.model_dump(mode='json',exclude={'receipt_digest'})))


@dataclass(frozen=True)
class SemanticValidationContext:
    principal_id: str
    policy_digest: str
    profile_closure_digest: str
    lookup: ConceptLookupClosure
    definitions: Mapping[str, SemanticDefinitionRevision]
    approved_rules: Mapping[str, ApprovedSemanticRule]
    source_records: Mapping[str, SourceRecordRevision]
    authorized_target_identity_refs: frozenset[str]
    evidence_spans: Mapping[str, FieldEvidenceRecord]
    available_dependencies: Mapping[str, SemanticDependencyValidation]
    approved_review_receipts: Mapping[str, str]
    conflicted_concept_refs: frozenset[str]
    approved_unit_conversions: Mapping[str, ApprovedUnitConversion] = field(default_factory=dict)
    schema_snapshot_digest: str | None = None
    dependency_evaluator_code_digests: frozenset[str] = frozenset()


def semantic_validator_code_digest() -> str:
    import hashlib
    root = Path(__file__).parent
    return semantic_digest({name: 'sha256:' + hashlib.sha256((root/name).read_bytes()).hexdigest()
                            for name in ('semantic_binding_validator.py', 'semantic_binding_contract.py', 'domain_profile_v04.py')})


class ReviewedDefinitionValidation(FrozenContract):
    contract_version:Literal['boi/reviewed-definition-validation@1']='boi/reviewed-definition-validation@1'
    candidate_digest:Digest
    definition_ref:Ref
    definition_digest:Digest
    review_receipt_digest:Digest
    dependency_closure_digest:Digest
    evaluator_code_digest:Digest
    status:Literal['REVIEWED_PROVISIONAL','BLOCKED']
    reason_codes:tuple[str,...]
    classification:Literal['PROVISIONAL']='PROVISIONAL'
    semantic_truth_proven:Literal[False]=False
    approved:Literal[False]=False
    receipt_digest:Digest


def validate_reviewed_definitions(*, candidates, records, definitions, receipt,
                                  dependency_candidates=()):
    """Check a human-reviewed draft closure without claiming active authority.

    The application resolves the receipt from the existing review store and
    checks current source/policy/preview. This evaluator checks logical and field
    contracts; it does not prove prose or install new canonical definitions.
    """
    from .domain_profile_v04 import validate_domain_profile_entry
    from .domain_profile_v03 import validate_domain_profile_entry as historical_entry, versioning_closure_reasons
    from .domain_profile_v02 import domain_reference_closure_reasons
    from .metadata_atomic_draft import restore_logical_claim
    reasons=set();parsed={}
    if (receipt.get('disposition')!='accept_interpretation'
        or receipt.get('principal')!=definitions.lookup.principal_id
        or sorted(receipt['closure']['domain_candidate_digests'])!=sorted(c['candidate_digest'] for c in candidates)):
        raise ValueError('REVIEWED_DEFINITION_RECEIPT_MISMATCH')
    source_by_id={record.record.identity_digest:record for record in records}
    active={entry.entry_id:entry for entry in definitions.entries}
    dependency_reviews=set()
    for dependency in dependency_candidates:
        dependency_reviews.add(TypeAdapter(Digest).validate_python(
            dependency['review_receipt_digest']))
        logical=validate_domain_profile_entry(dependency['logical_definition'])
        if (logical.id in active or logical.id in parsed
            or dependency.get('logical_definition_digest')!=semantic_digest(
                dependency['logical_definition'])):
            reasons.add('REVIEWED_DEFINITION_DEPENDENCY_COLLISION_OR_DRIFT')
        parsed[logical.id]=logical
    for candidate in candidates:
        record=source_by_id.get(SourceRecordRevision.model_validate(candidate['source_record']).identity_digest)
        if record is None:
            raise ValueError('REVIEWED_DEFINITION_SOURCE_UNAVAILABLE')
        restore_logical_claim(candidate,record,definitions)
        logical=validate_domain_profile_entry(candidate['logical_definition'])
        if logical.id in active or logical.id in parsed:
            reasons.add('REVIEWED_DEFINITION_ID_COLLISION')
        if logical.semantic_contract.scope.namespace!=definitions.lookup.namespace:
            reasons.add('REVIEWED_DEFINITION_SCOPE_MISMATCH')
        parsed[logical.id]=logical
    existing=[]
    for entry in definitions.entries:
        payload={k:v for k,v in entry.payload.items() if k not in {'semantic_evidence_uses','semantic_reuse_declarations'}}
        existing.append(validate_domain_profile_entry(payload) if 'semantic_contract' in payload else historical_entry(payload))
    all_entries=tuple(existing)+tuple(parsed.values())
    reasons.update(domain_reference_closure_reasons(all_entries))
    reasons.update(versioning_closure_reasons(all_entries))
    dependency_material=[e.model_dump(mode='json') for e in all_entries]
    dependency_digest=semantic_digest({'definitions':dependency_material,
        'review_receipt_digests':sorted(dependency_reviews)} if dependency_reviews
        else dependency_material)
    validations={}
    for candidate in candidates:
        values={'candidate_digest':candidate['candidate_digest'],'definition_ref':candidate['logical_definition']['id'],
            'definition_digest':candidate['logical_definition_digest'],'review_receipt_digest':receipt['receipt_digest'],
            'dependency_closure_digest':dependency_digest,'status':'BLOCKED' if reasons else 'REVIEWED_PROVISIONAL',
            'reason_codes':tuple(sorted(reasons))}
        values['evaluator_code_digest']=semantic_validator_code_digest()
        values.update(contract_version='boi/reviewed-definition-validation@1',classification='PROVISIONAL',
            semantic_truth_proven=False,approved=False)
        validations[candidate['candidate_digest']]=ReviewedDefinitionValidation(**values,receipt_digest=semantic_digest(values))
    return validations


def validate_semantic_binding(candidate: SemanticBindingCandidate, context: SemanticValidationContext) -> SemanticBindingValidation:
    # model_copy is not validation; revalidate all nested proposed fields here.
    candidate = SemanticBindingCandidate.model_validate(candidate.model_dump(mode='json'))
    checks: list[SemanticBindingCheck] = []
    lookup = context.lookup
    selected_dependencies = {item.ref: (value.model_dump(mode='json') if isinstance(value,SemanticDependencyValidation) else None)
                             for item in candidate.dependency_refs
                             for value in (context.available_dependencies.get(item.ref),)}

    def add(check_id: str, reasons: tuple[str, ...], material: object, *, attention: bool = False):
        checks.append(SemanticBindingCheck(check_id=check_id,
            status=('flag' if attention else 'fail') if reasons else 'pass',
            evidence_digest=semantic_digest(material), reason_codes=reasons))

    def finish():
        reasons = tuple(dict.fromkeys(reason for check in checks for reason in check.reason_codes))
        status = ('BLOCKED' if any(check.status in {'fail', 'not_run', 'partial', 'skip'} for check in checks)
                  else 'ATTENTION_REQUIRED' if reasons else 'VALIDATED')
        values = dict(contract_version='boi/semantic-binding-validation@0.1.0',
            candidate_digest=semantic_digest(candidate), principal_id=context.principal_id,
            policy_digest=context.policy_digest, validator_code_digest=semantic_validator_code_digest(),
            lookup_closure_digest=semantic_digest(lookup), dependency_closure_digest=semantic_digest(selected_dependencies),
            checks=[check.model_dump(mode='json') for check in checks], status=status, reason_codes=list(reasons),
            semantic_truth_proven=False, approved=False)
        return SemanticBindingValidation(**values, receipt_digest=semantic_digest(values))

    reasons = []
    if (context.principal_id != lookup.principal_id or context.policy_digest != lookup.policy_digest
        or candidate.target_identity_ref not in context.authorized_target_identity_refs):
        reasons.append('SEMANTIC_ACCESS_OR_POLICY_DENIED')
    if context.source_records.get(candidate.source_record.identity_digest) != candidate.source_record:
        reasons.append('SEMANTIC_SOURCE_SNAPSHOT_UNAVAILABLE')
    if (context.profile_closure_digest != lookup.profile_closure_digest
        or lookup.namespace != candidate.source_record.namespace):
        reasons.append('SEMANTIC_PROFILE_SCOPE_STALE')
    if not lookup.permits_absence_claim:
        reasons.append('SEMANTIC_LOOKUP_SCOPE_INCOMPLETE')
    add(SEMANTIC_REQUIRED_CHECKS[0], tuple(reasons), {'candidate':semantic_digest(candidate), 'lookup':semantic_digest(lookup)})
    if reasons:
        # Never inspect hidden definitions/rules or expose their names/counts.
        checks.extend(SemanticBindingCheck(check_id=key, status='not_run', evidence_digest=None, reason_codes=())
                      for key in SEMANTIC_REQUIRED_CHECKS[1:])
        return finish()

    definition = context.definitions.get(candidate.concept_ref)
    if definition is None or definition.revision_digest != candidate.concept_revision_digest or definition.revision_digest not in lookup.concept_revision_digests:
        add(SEMANTIC_REQUIRED_CHECKS[1], ('SEMANTIC_DEFINITION_REVISION_UNAVAILABLE',), candidate.concept_revision_digest)
        checks.extend(SemanticBindingCheck(check_id=key,status='not_run',evidence_digest=None,reason_codes=()) for key in SEMANTIC_REQUIRED_CHECKS[2:])
        return finish()
    rule = context.approved_rules.get(candidate.approved_rule_ref.ref) if candidate.approved_rule_ref else None
    identity_reasons = []
    if rule is None:
        identity_reasons.append('SEMANTIC_APPROVED_IDENTITY_REQUIRED')
    elif (rule.revision_digest != candidate.approved_rule_ref.revision_digest
          or rule.policy_digest != context.policy_digest
          or rule.namespace != candidate.source_record.namespace
          or rule.source_system != candidate.source_record.source_system or rule.dataset != candidate.source_record.dataset
          or rule.source_semantic_digest != semantic_digest(candidate.source_semantics)
          or rule.target_concept_ref != candidate.concept_ref or rule.target_revision_digest != definition.revision_digest
          or rule.target_semantic_digest != semantic_digest(definition.semantic_contract)
          or rule.relation_kind != candidate.relation_kind):
        identity_reasons.append('SEMANTIC_APPROVED_RULE_STALE_OR_MISMATCH')
    if rule and candidate.relation_kind == 'target_identity' and rule.identity_ref != candidate.target_identity_ref:
        identity_reasons.append('SEMANTIC_TARGET_IDENTITY_MISMATCH')
    add(SEMANTIC_REQUIRED_CHECKS[1], tuple(identity_reasons), rule.model_dump(mode='json') if rule else None, attention=rule is None)

    left, right = candidate.source_semantics, definition.semantic_contract
    equivalent = candidate.relation_kind in _EQUIVALENCE_KINDS
    kind_ok = not equivalent or (left.kind, left.target_kind, left.role) == (right.kind, right.target_kind, right.role)
    add(SEMANTIC_REQUIRED_CHECKS[2], () if kind_ok else ('SEMANTIC_KIND_TARGET_ROLE_MISMATCH',),
        {'source':(left.kind,left.target_kind,left.role),'definition':(right.kind,right.target_kind,right.role)})

    quantity_ok = (left.quantity_kind_ref, left.unit_semantics, left.value_semantics) == (right.quantity_kind_ref, right.unit_semantics, right.value_semantics)
    unit_ok = (left.unit_ref,left.unit_revision_digest) == (right.unit_ref,right.unit_revision_digest)
    conversion = None
    if not unit_ok and rule and rule.unit_conversion_ref:
        conversion = context.approved_unit_conversions.get(rule.unit_conversion_ref.ref)
        unit_ok = bool(conversion and conversion.revision_digest == rule.unit_conversion_ref.revision_digest
            and (conversion.from_unit_ref,conversion.from_revision_digest)==(left.unit_ref,left.unit_revision_digest)
            and (conversion.to_unit_ref,conversion.to_revision_digest)==(right.unit_ref,right.unit_revision_digest)
            and conversion.quantity_kind_ref==left.quantity_kind_ref==right.quantity_kind_ref
            and conversion.value_semantics==left.value_semantics==right.value_semantics)
    unit_known = left.unit_semantics != 'unknown' and right.unit_semantics != 'unknown' and left.value_semantics != 'unknown' and right.value_semantics != 'unknown'
    for descriptor in (left,right):
        if descriptor.role in {'measurement','setpoint','upper_limit','lower_limit','computed'}:
            unit_known = unit_known and bool(descriptor.quantity_kind_ref) and descriptor.unit_semantics in {'declared','dimensionless'}
    add(SEMANTIC_REQUIRED_CHECKS[3], () if not equivalent or (quantity_ok and unit_ok and unit_known) else ('SEMANTIC_QUANTITY_UNIT_CONTRACT_MISMATCH',),
        {'source':semantic_digest(left),'definition':semantic_digest(right),'conversion':conversion.model_dump(mode='json') if conversion else None})

    scope_ok = left.scope == right.scope or bool(rule and rule.allow_scope_specialization and not identity_reasons)
    source = candidate.source_record
    validity_policy = rule.source_validity_policy if isinstance(rule, ApprovedSemanticRuleV2) else None
    material_window = left.scope.effective_from is not None or left.scope.effective_until is not None
    policy_missing = material_window and validity_policy is None
    temporal_ok = not policy_missing
    if validity_policy == 'must_be_contained':
        temporal_ok = (
            (left.scope.effective_from is None or (source.effective_from is not None
             and left.scope.effective_from <= source.effective_from))
            and (left.scope.effective_until is None or (source.effective_until is not None
                 and source.effective_until <= left.scope.effective_until)))
    reasons = []
    if policy_missing:
        reasons.append('SEMANTIC_SOURCE_VALIDITY_POLICY_REQUIRED')
    if (equivalent and not scope_ok) or (not temporal_ok and not policy_missing):
        reasons.append('SEMANTIC_SCOPE_OR_EFFECTIVE_TIME_MISMATCH')
    add(SEMANTIC_REQUIRED_CHECKS[4], tuple(reasons),
        {'source_scope':left.scope.model_dump(mode='json'),'definition_scope':right.scope.model_dump(mode='json'),
         'source_record':source.model_dump(mode='json'), 'source_validity_policy':validity_policy},
        attention=policy_missing and scope_ok)

    dependencies = {item.ref:item.revision_digest for item in candidate.dependency_refs}
    dependency_ok = True
    for ref,revision in dependencies.items():
        dependency=context.available_dependencies.get(ref)
        if (not isinstance(dependency,SemanticDependencyValidation) or dependency.ref!=ref
            or dependency.revision_digest!=revision or not dependency.satisfied
            or dependency.schema_snapshot_digest!=context.schema_snapshot_digest
            or dependency.policy_digest!=context.policy_digest
            or dependency.evaluator_code_digest not in context.dependency_evaluator_code_digests):
            dependency_ok=False
    if rule:
        dependency_ok = dependency_ok and all(dependencies.get(item.ref)==item.revision_digest for item in rule.required_dependency_refs)
    add(SEMANTIC_REQUIRED_CHECKS[5], () if dependency_ok else ('SEMANTIC_REQUIRED_MAPPING_DEPENDENCY_UNAVAILABLE',),
        {'declared':dependencies,'available':selected_dependencies,'required': [r.model_dump(mode='json') for r in rule.required_dependency_refs] if rule else []})

    evidence_reasons = []
    for use in (*candidate.evidence_uses, *definition.evidence_uses):
        actual = context.evidence_spans.get(use.span_ref)
        if actual != FieldEvidenceRecord.from_evidence_use(use):
            evidence_reasons.append('SEMANTIC_EVIDENCE_CLOSURE_MISMATCH')
        if use.support_basis == 'human_reviewed_interpretation' and (
            use.review_receipt_ref is None or context.approved_review_receipts.get(use.review_receipt_ref.ref)!=use.review_receipt_ref.revision_digest):
            evidence_reasons.append('SEMANTIC_EVIDENCE_REVIEW_UNAVAILABLE')
    support = set().union(*(set(use.supports_fields) for use in candidate.evidence_uses))
    if not _SUPPORT_FIELDS <= support:
        evidence_reasons.append('SEMANTIC_REQUIRED_FIELD_SUPPORT_MISSING')
    if any(use.supports_contract_digest!=semantic_digest(right) or use.support_basis not in {'approved_structured_contract','human_reviewed_interpretation'} for use in definition.evidence_uses):
        evidence_reasons.append('SEMANTIC_DEFINITION_JUSTIFICATION_REQUIRED')
    if rule is None:
        evidence_reasons.append('SEMANTIC_SOURCE_JUSTIFICATION_REQUIRED')
    elif any(use.content_digest not in rule.allowed_evidence_content_digests for use in candidate.evidence_uses):
        evidence_reasons.append('SEMANTIC_SOURCE_CONTENT_NOT_APPROVED')
    evidence_reasons=list(dict.fromkeys(evidence_reasons))
    add(SEMANTIC_REQUIRED_CHECKS[6], tuple(evidence_reasons),
        {'source':[u.model_dump(mode='json') for u in candidate.evidence_uses], 'definition':[u.model_dump(mode='json') for u in definition.evidence_uses]},
        attention=evidence_reasons==['SEMANTIC_SOURCE_JUSTIFICATION_REQUIRED'])

    conflicts = candidate.concept_ref in context.conflicted_concept_refs
    add(SEMANTIC_REQUIRED_CHECKS[7], ('SEMANTIC_DECLARATION_CONFLICT',) if conflicts else (),
        {'candidate_digest':semantic_digest(candidate),'prior_checks':[check.model_dump(mode='json') for check in checks], 'conflict':conflicts})
    return finish()


def verify_semantic_binding_receipt(receipt, candidate, context) -> bool:
    """Re-evaluate the exact closure; a status string/self hash is insufficient."""
    try:
        parsed = SemanticBindingValidation.model_validate(receipt.model_dump(mode='json'))
        return parsed == validate_semantic_binding(candidate,context)
    except (ValueError, TypeError):
        return False
