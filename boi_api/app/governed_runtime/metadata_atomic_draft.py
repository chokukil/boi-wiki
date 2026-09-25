"""Bounded atomic extraction using definitions before any local inference."""
from dataclasses import dataclass
from typing import Literal
from pydantic import Field,TypeAdapter,model_validator,StrictInt
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,SemanticDescriptor,RevisionRef,Digest,Ref,semantic_digest
from boi_api.app.governed_runtime.semantic_definition_reading import read_existing_definitions
from boi_api.app.governed_runtime.semantic_profile_loader import ActiveDefinitionSnapshot
from boi_api.app.governed_runtime.domain_profile_v04 import DomainEntryUnion
from boi_api.app.governed_runtime.semantic_binding_contract import EvidenceUse


class AtomicSemanticClaim(FrozenContract):
    semantics:SemanticDescriptor
    field_indices:tuple[int,...]=Field(min_length=1,max_length=32)
    proposed_concept:RevisionRef|None
    uncertainties:tuple[str,...]=()

    @model_validator(mode='after')
    def valid_positions(self):
        if any(index<0 for index in self.field_indices) or len(set(self.field_indices))!=len(self.field_indices):
            raise ValueError('SEMANTIC_FIELD_INDEX_INVALID')
        return self


class MetadataAtomicDraft(FrozenContract):
    contract_version:Literal['boi/metadata-atomic-draft@1']='boi/metadata-atomic-draft@1'
    candidates:tuple[AtomicSemanticClaim,...]=Field(max_length=4)
    uncertainties:tuple[str,...]=()
    remaining_claims:bool=False


def logical_support_constraints(entries, index_list):
    """Same field-evidence assertions for the full contract or a constrained kind union."""
    excluded = {'kind','id','name','aliases','description','semantic_contract','authority_basis'}
    branches = [{'if':{'properties':{'logical_definition':{'type':'null'}},
                       'required':['logical_definition']},
                 'then':{'properties':{'logical_field_support':{'maxProperties':0}}}}]
    branches.append({'if':{'properties':{
        'logical_definition':{'type':'object'},
        'semantics':{'properties':{'aliases':{'minItems':1}},'required':['aliases']}},
        'required':['logical_definition','semantics']},
        'then':{'properties':{'logical_definition':{'required':['aliases']}}}})
    fields = set()
    object_branches=[]
    for entry in entries:
        allowed = sorted(set(entry['properties']) - excluded)
        fields.update(allowed)
        kind = entry['properties']['kind']['const']
        object_branches.append({'if':{'properties':{'logical_definition':{
            'properties':{'kind':{'const':kind}}}}},
            'then':{'properties':{'logical_field_support':{
                'propertyNames':{'enum':allowed}}}}})
    support = {'properties':{key:index_list for key in sorted(fields)},'additionalProperties':False}
    for key in sorted(fields):
        object_branches.append({'if':{'properties':{'logical_definition':{
            'properties':{key:{'not':{'enum':[None,[],{},'']}}},
            'required':[key]}}},
            'then':{'properties':{'logical_field_support':{'required':[key]}}}})
    branches.append({'if':{'properties':{'logical_definition':{'type':'object'}},
                            'required':['logical_definition']},
                     'then':{'allOf':object_branches}})
    return support, branches


class LogicalSemanticClaim(AtomicSemanticClaim):
    field_indices:tuple[StrictInt,...]=Field(min_length=1,max_length=32)
    logical_definition:DomainEntryUnion|None
    logical_field_support:dict[str,tuple[StrictInt,...]]=Field(max_length=32)

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        # Export the same field-support closure enforced below. Otherwise the
        # model sees an unconstrained dictionary and cannot discover which
        # nonempty logical fields must carry evidence, including applicability.
        domain = TypeAdapter(DomainEntryUnion).json_schema()
        support, branches = logical_support_constraints(
            [domain['$defs'][ref['$ref'].rsplit('/',1)[-1]] for ref in domain['oneOf']],
            {'type':'array','items':{'type':'integer','minimum':0},
             'minItems':1,'maxItems':32,'uniqueItems':True})
        schema['properties']['logical_field_support'].update(support)
        schema['allOf'] = [*schema.get('allOf',[]), *branches]
        return schema

    @model_validator(mode='before')
    @classmethod
    def strict_logical_json_types(cls,value):
        if isinstance(value,dict) and value.get('logical_definition') is not None:
            from jsonschema import Draft202012Validator
            from .domain_profile_v04 import domain_profile_json_schema
            logical=value['logical_definition']
            if hasattr(logical,'model_dump'):logical=logical.model_dump(mode='json')
            if not Draft202012Validator(domain_profile_json_schema()).is_valid(logical):
                raise ValueError('LOGICAL_DOMAIN_JSON_SCHEMA_INVALID')
        return value

    @model_validator(mode='after')
    def logical_support_contract(self):
        if self.logical_definition is None:
            if self.logical_field_support:
                raise ValueError('LOGICAL_SUPPORT_WITHOUT_DEFINITION')
            return self
        if self.proposed_concept is not None:
            raise ValueError('LOGICAL_NEW_AND_REUSE_PROPOSALS_MUST_BE_SEPARATE')
        if self.logical_definition.semantic_contract!=self.semantics:
            raise ValueError('LOGICAL_CANDIDATE_SEMANTICS_MISMATCH')
        raw=self.logical_definition.model_dump(mode='json')
        common={'kind','id','name','aliases','description','semantic_contract','authority_basis'}
        required={key for key,value in raw.items() if key not in common and value not in (None,[],{},'')}
        if not required<=self.logical_field_support.keys() or not self.logical_field_support.keys()<=raw.keys()-common:
            raise ValueError('LOGICAL_FIELD_EVIDENCE_CLOSURE_REQUIRED')
        if any(not indices or len(indices)>32 or any(i<0 for i in indices) or len(set(indices))!=len(indices)
               for indices in self.logical_field_support.values()):
            raise ValueError('LOGICAL_FIELD_EVIDENCE_INDEX_INVALID')
        return self


class MetadataLogicalDraft(MetadataAtomicDraft):
    """Complete proposed Domain payload, never an approved semantic definition.

    Uses the existing seven strict Domain types. Missing logical detail stays an
    explicit gap; physical mapping and execution contracts are not model fields.
    The original sparse draft contract remains an independent historical reader.
    """
    contract_version:Literal['boi/metadata-logical-draft@1']='boi/metadata-logical-draft@1'
    candidates:tuple[LogicalSemanticClaim,...]=Field(max_length=4)


def parse_metadata_draft(value):
    if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
    model=MetadataLogicalDraft if value.get('contract_version')=='boi/metadata-logical-draft@1' else MetadataAtomicDraft
    return model.model_validate(value)


def restore_logical_claim(candidate, record, definitions):
    """Rehydrate exact stored field slots without changing the original proposal."""
    slots={span.span_ref:index for index,span in enumerate(record.evidence)}
    support={}
    for use in candidate['logical_evidence_uses']:
        for field in use['supports_fields']:
            support.setdefault(field,[]).append(slots[use['span_ref']])
    claim=LogicalSemanticClaim(semantics=candidate['semantics'],
        field_indices=tuple(slots[span['span_ref']] for span in candidate['field_evidence']),
        proposed_concept=candidate['proposed_concept'],uncertainties=candidate['uncertainties'],
        logical_definition=candidate['logical_definition'],logical_field_support=support)
    rebound=bind_draft_to_record(draft=MetadataLogicalDraft(candidates=(claim,)),record=record,
        definitions=definitions,output_receipt_digest=candidate['output_receipt_digest'])
    if rebound!=(candidate,):
        raise ValueError('REVIEWED_CANDIDATE_RECONSTRUCTION_DRIFT')
    return claim


class ResolvedSemanticDraft(FrozenContract):
    """Server-resolved approved extraction; not a client or model authority claim."""
    contract_version:Literal['boi/resolved-semantic-draft@1']='boi/resolved-semantic-draft@1'
    principal_id:Ref
    policy_digest:Digest
    source_profile_digest:Digest
    semantic_input_digest:Digest
    definition_closure_digest:Digest
    approval_receipt_ref:RevisionRef
    draft:MetadataAtomicDraft

    def verify_context(self,*,record,definitions,principal_id,policy_digest):
        actual=ResolvedSemanticDraft.model_validate(self.model_dump(mode='json'))
        if (actual.principal_id!=principal_id or actual.policy_digest!=policy_digest
            or actual.source_profile_digest!=record.source_profile_digest
            or actual.semantic_input_digest!=record.semantic_input_digest
            or actual.definition_closure_digest!=semantic_digest(definitions.lookup)):
            raise ValueError('SEMANTIC_EXTRACTION_RESOLUTION_STALE')
        return actual


@dataclass(frozen=True)
class DefinitionFirstInput:
    payload:dict
    definition_receipt:dict
    definition_receipt_digest:str
    input_digest:str
    source_semantic_digest:str
    evidence_closure_digest:str


def read_definition_first_scope(*,record,definitions:ActiveDefinitionSnapshot,manifest_digest,principal_id,policy_digest,
                                for_model=False):
    """Validate the authorized closure before resolution, not as a model budget.

    A complete deterministic read is not permission to serialize that whole
    scope into a model prompt. The model preparation path retains its old bound.
    """
    definitions=ActiveDefinitionSnapshot.model_validate(definitions.model_dump(mode='json'))
    if semantic_digest(definitions.model_dump(mode='json',exclude={'snapshot_digest'}))!=definitions.snapshot_digest:
        raise ValueError('ACTIVE_DEFINITION_SNAPSHOT_DRIFT')
    if definitions.lookup.namespace!=record.record.namespace:
        raise ValueError('SOURCE_DEFINITION_NAMESPACE_MISMATCH')
    return read_existing_definitions(principal_id=principal_id,policy_digest=policy_digest,
        lookup=definitions.lookup,entries=definitions.entries,source_manifest_digest=manifest_digest,for_model=for_model)


def prepare_definition_first_input(*,record,definitions:ActiveDefinitionSnapshot,manifest_digest,principal_id,policy_digest,
                                   output_contract_version='boi/metadata-atomic-draft@1'):
    if output_contract_version not in {'boi/metadata-atomic-draft@1','boi/metadata-logical-draft@1'}:
        raise ValueError('SEMANTIC_DRAFT_CONTRACT_UNSUPPORTED')
    reading=read_definition_first_scope(record=record,definitions=definitions,manifest_digest=manifest_digest,
        principal_id=principal_id,policy_digest=policy_digest,for_model=True)
    # Stable field slots allow same-meaning extraction reuse, not target merging.
    # Exact target SourceRecord/FieldEvidence closure stays outside model input.
    contextual=any(ref.ref=='transform:structured-field-extraction@2' for span in record.evidence for ref in span.transformation_refs)
    payload={'input_contract_version':'boi/definition-first-input@0.4.0' if output_contract_version=='boi/metadata-logical-draft@1'
             else 'boi/definition-first-input@0.3.0' if contextual else 'boi/definition-first-input@0.2.0',
             'semantic_namespace':record.record.namespace,
             'evidence_spans':[{'evidence_span_ref':'metadata-atom:0','fields':list(record.semantic_fields)}],
             'existing_definitions':list(reading.model_definitions),
             'output_contract_version':output_contract_version}
    from boi_api.app.governed_runtime.semantic_inference_cache import canonical,digest_bytes
    encoded=canonical(payload)
    if len(encoded)>11264:raise ValueError('SEMANTIC_INPUT_SCOPE_SHARD_REQUIRED')
    return DefinitionFirstInput(payload,reading.receipt,reading.receipt_digest,digest_bytes(encoded),
                                record.semantic_input_digest,semantic_digest([span.model_dump(mode='json') for span in record.evidence]))


def bind_draft_to_record(*,draft,record,definitions,output_receipt_digest):
    output_receipt_digest=TypeAdapter(Digest).validate_python(output_receipt_digest)
    draft=parse_metadata_draft(draft)
    by_ref={entry.entry_id:entry.revision_digest for entry in definitions.entries}
    candidates=[]
    for claim in draft.candidates:
        if any(index>=len(record.evidence) for index in claim.field_indices):
            raise ValueError('SEMANTIC_FIELD_EVIDENCE_OUTSIDE_SOURCE')
        if claim.semantics.scope.namespace!=record.record.namespace:
            raise ValueError('SEMANTIC_CLAIM_NAMESPACE_MISMATCH')
        if claim.proposed_concept and by_ref.get(claim.proposed_concept.ref)!=claim.proposed_concept.revision_digest:
            raise ValueError('SEMANTIC_MATCH_PROPOSAL_OUTSIDE_READ_DEFINITIONS')
        value={'source_record':record.record.model_dump(mode='json'),
               'target_identity_ref':'record-identity:'+record.record.identity_digest,
               'semantics':claim.semantics.model_dump(mode='json'),
               'proposed_concept':claim.proposed_concept.model_dump(mode='json') if claim.proposed_concept else None,
               'field_evidence':[record.evidence[i].model_dump(mode='json') for i in claim.field_indices],
               'output_receipt_digest':output_receipt_digest,'uncertainties':list(claim.uncertainties),
               'semantic_validation_status':'not_run','production_changed':False}
        if any(ref.ref=='transform:structured-field-extraction@2' for span in record.evidence for ref in span.transformation_refs):
            value.update(candidate_contract_version='boi/semantic-record-candidate@2',
                context_evidence=[{'purpose':meaning['purpose'],'relation':'context',
                    'evidence':span.model_dump(mode='json')}
                    for meaning,span in zip(record.semantic_fields,record.evidence)
                    if meaning['purpose'] in {'owner_label','owner_description','scope_condition','scope_exception'}])
        if isinstance(claim,LogicalSemanticClaim):
            logical=claim.logical_definition
            uses=[]
            if logical is not None:
                for field,indices in sorted(claim.logical_field_support.items()):
                    for index in indices:
                        if index>=len(record.evidence):
                            raise ValueError('LOGICAL_FIELD_EVIDENCE_OUTSIDE_SOURCE')
                        uses.append(EvidenceUse(**record.evidence[index].model_dump(mode='json'),
                            supports_contract_digest=semantic_digest(logical),supports_fields=(field,),
                            use_kind='reported_description',support_basis='model_proposed',review_receipt_ref=None).model_dump(mode='json'))
            value.update(candidate_contract_version='boi/semantic-record-candidate@3',
                logical_profile='boi/domain@0.4.0',logical_definition=logical.model_dump(mode='json') if logical else None,
                logical_evidence_uses=uses,logical_contract_status='draft_valid' if logical else 'not_run',
                logical_definition_digest=semantic_digest(logical) if logical else None,
                logical_grounding_status='model_proposed' if logical else 'not_run')
            if logical is not None:
                from .domain_profile_v04 import domain_profile_json_schema
                proof={'profile':'boi/domain@0.4.0','payload_digest':semantic_digest(logical),
                    'schema_digest':semantic_digest(domain_profile_json_schema()),
                    'evidence_use_digest':semantic_digest(uses)}
                value['logical_structure_check']={'check_id':'logical-domain-profile-schema','status':'pass',
                    'evidence_digest':semantic_digest(proof),'proof':proof,'semantic_approval':False}
        candidates.append({**value,'candidate_digest':semantic_digest(value)})
    return tuple(candidates)
