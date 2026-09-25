"""Deterministic metadata/lineage to candidate Mapping and quality contracts."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping, Literal
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, Ref, Digest
from .physical_temporal_encoding import (
    sqlite_declared_affinity,
    temporal_encoding_check,
)

from sqlglot import exp, parse

from .cardinality_query_shape import (
    DataQualityReceipt,
    RelationshipContract,
    ResultShapeContract,
)
from .multi_result_query_gateway import (
    AuthorizedPhysicalMapping,
    capture_multi_result_sqlite_schema,
    profile_sqlite_relationship_quality,
)


def _canonical(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


@dataclass(frozen=True)
class MetadataMappingProfileCandidate:
    profile_version: str
    status: str
    source_id: str
    catalog_snapshot_digest: str
    schema_snapshot_digest: str
    policy_digest: str
    object_mappings: tuple[dict[str, object], ...]
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...]
    relationship_contracts: tuple[RelationshipContract, ...]
    data_quality_receipts: tuple[DataQualityReceipt, ...]
    result_shape_contract: ResultShapeContract
    profile_digest: str
    raw_row_model_input_count: int = 0
    prefreeze_oracle_access_count: int = 0
    production_changed: bool = False
    active_transition: bool = False


class DeclaredObjectMapping(FrozenContract):
    """A logical object declared by Domain, not a table-to-object heuristic."""
    object_ref: Ref
    property_mapping_refs: tuple[Ref, ...] = Field(min_length=1)
    logical_key_mapping_refs: tuple[Ref, ...] = Field(min_length=1)
    evidence_span_refs: tuple[Ref, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def exact_key(self):
        if (len(set(self.property_mapping_refs))!=len(self.property_mapping_refs)
            or len(set(self.logical_key_mapping_refs))!=len(self.logical_key_mapping_refs)
            or not set(self.logical_key_mapping_refs)<=set(self.property_mapping_refs)):
            raise ValueError('DECLARED_MAPPING_OBJECT_GRAIN_INVALID')
        return self


class DeclaredPropertyMapping(FrozenContract):
    logical_property_ref: Ref
    owner_ref: Ref
    physical: AuthorizedPhysicalMapping
    declared_data_type: Ref
    unit_semantics: Literal['not_applicable','dimensionless','declared']
    unit_ref: Ref | None
    time_semantics: Ref
    evidence_span_refs: tuple[Ref, ...] = Field(min_length=1)

    @model_validator(mode='after')
    def unit_contract(self):
        if (self.unit_semantics=='declared') != (self.unit_ref is not None):
            raise ValueError('DECLARED_MAPPING_UNIT_CONTRACT_INVALID')
        return self


class PhysicalColumnMetadataPolicy(FrozenContract):
    format: Literal[
        'corporate-column-metadata/v1', 'corporate-column-metadata/v2'
    ]
    source_id: Ref
    source_snapshot_digest: Digest
    quality_grant_digest: Digest | None = None


class DeclaredMetadataMappingInputs(FrozenContract):
    """Forward candidate contract. No SQL syntax may choose semantic policy.

    The consuming service must resolve these declarations/evidence from the same
    source/candidate closure; constructing this type grants no execution authority.
    v1's historical SQL-derived profile remains a separate preserved reader.
    """
    contract_version: Literal['boi/declared-metadata-mapping-input@1']
    source_id: Ref
    source_snapshot_digest: Digest
    catalog_snapshot_digest: Digest
    schema_snapshot_digest: Digest
    policy_digest: Digest
    domain_candidate_closure_digest: Digest
    authorized_evidence_span_refs: tuple[Ref, ...] = Field(min_length=1)
    objects: tuple[DeclaredObjectMapping, ...] = Field(min_length=1)
    properties: tuple[DeclaredPropertyMapping, ...] = Field(min_length=1)
    relationships: tuple[RelationshipContract, ...]
    result_shapes: tuple[ResultShapeContract, ...]

    @model_validator(mode='after')
    def declared_dependency_closure(self):
        objects={item.object_ref:item for item in self.objects}
        properties={item.physical.mapping_ref:item for item in self.properties}
        if (len(objects)!=len(self.objects) or len(properties)!=len(self.properties)
            or len({p.logical_property_ref for p in self.properties})!=len(self.properties)):
            raise ValueError('DECLARED_MAPPING_IDENTITY_AMBIGUOUS')
        evidence=set(self.authorized_evidence_span_refs)
        if any(not set(item.evidence_span_refs)<=evidence for item in (*self.objects,*self.properties)):
            raise ValueError('DECLARED_MAPPING_EVIDENCE_OUTSIDE_CLOSURE')
        for prop in self.properties:
            if (prop.owner_ref not in objects or prop.physical.source_id!=self.source_id
                or prop.physical.mapping_ref not in objects[prop.owner_ref].property_mapping_refs):
                raise ValueError('DECLARED_MAPPING_OWNER_OR_SOURCE_MISMATCH')
        for obj in self.objects:
            if any(ref not in properties or properties[ref].owner_ref!=obj.object_ref for ref in obj.property_mapping_refs):
                raise ValueError('DECLARED_MAPPING_OBJECT_DEPENDENCY_MISSING')
            if len({properties[ref].physical.table for ref in obj.property_mapping_refs})!=1:
                raise ValueError('DECLARED_MAPPING_OBJECT_MULTITABLE_CONTRACT_REQUIRED')
        relationships={item.contract_id:item for item in self.relationships}
        if len(relationships)!=len(self.relationships):
            raise ValueError('DECLARED_RELATIONSHIP_IDENTITY_AMBIGUOUS')
        for rel in self.relationships:
            if rel.schema_snapshot_digest!=self.schema_snapshot_digest:
                raise ValueError('DECLARED_RELATIONSHIP_SCHEMA_STALE')
            for endpoint,refs in ((rel.left_endpoint_ref,rel.physical_keys.left_mapping_refs),
                                  (rel.right_endpoint_ref,rel.physical_keys.right_mapping_refs)):
                if endpoint not in objects or not set(refs)<=set(objects[endpoint].property_mapping_refs):
                    raise ValueError('DECLARED_RELATIONSHIP_ENDPOINT_MISMATCH')
        logical_properties={item.logical_property_ref:item for item in self.properties}
        for shape in self.result_shapes:
            if (shape.root_object_ref not in objects or not set(shape.relationship_refs)<=relationships.keys()
                or not set(shape.exact_grain)<=logical_properties.keys()):
                raise ValueError('DECLARED_RESULT_SHAPE_DEPENDENCY_MISSING')
            if shape.shape=='ObjectSet':
                root=objects[shape.root_object_ref]
                root_grain=tuple(properties[ref].logical_property_ref
                    for ref in root.logical_key_mapping_refs)
                if shape.exact_grain!=root_grain:
                    raise ValueError('DECLARED_OBJECT_SET_GRAIN_MISMATCH')
        return self


class DeclaredPropertyMappingV2(DeclaredPropertyMapping):
    value_type_ref: Ref
    value_type_revision_digest: Digest
    logical_primitive_type: Literal['string','integer','number','boolean','date','datetime','duration']


class DeclaredMetadataMappingInputsV2(DeclaredMetadataMappingInputs):
    contract_version: Literal['boi/declared-metadata-mapping-input@2']
    properties: tuple[DeclaredPropertyMappingV2,...] = Field(min_length=1)

    @model_validator(mode='after')
    def temporal_encoding_requires_v4(self):
        if (self.contract_version != 'boi/declared-metadata-mapping-input@4'
                and any(prop.physical.temporal_encoding is not None
                        for prop in self.properties)):
            raise ValueError('DECLARED_MAPPING_TEMPORAL_ENCODING_REVISION_REQUIRED')
        return self


class DeclaredMetadataMappingInputsV3(DeclaredMetadataMappingInputsV2):
    contract_version:Literal['boi/declared-metadata-mapping-input@3']
    semantic_authority_scope:Literal['reviewed_provisional']
    interpretation_receipt_digests:tuple[Digest,...]=Field(min_length=1)


class DeclaredPropertyMappingV3(DeclaredPropertyMappingV2):
    @model_validator(mode='after')
    def physical_value_encoding(self):
        temporal_encoding=self.physical.temporal_encoding
        if (self.logical_primitive_type in {'date', 'datetime', 'duration'}
                or temporal_encoding is not None):
            check = temporal_encoding_check(
                self.declared_data_type, self.logical_primitive_type,
                temporal_encoding,
            )
            if not check['compatible']:
                raise ValueError(str(check['reason_code']))
        return self


class DeclaredMetadataMappingInputsV4(DeclaredMetadataMappingInputsV2):
    contract_version: Literal['boi/declared-metadata-mapping-input@4']
    properties: tuple[DeclaredPropertyMappingV3,...] = Field(min_length=1)
    semantic_authority_scope: Literal['reviewed_provisional'] | None = Field(
        default=None, exclude_if=lambda value: value is None,
    )
    interpretation_receipt_digests: tuple[Digest,...] = Field(
        default=(), exclude_if=lambda value: not value,
    )

    @model_validator(mode='after')
    def optional_review_authority(self):
        reviewed = self.semantic_authority_scope == 'reviewed_provisional'
        if reviewed != bool(self.interpretation_receipt_digests):
            raise ValueError('DECLARED_MAPPING_REVIEW_AUTHORITY_INVALID')
        return self


@dataclass(frozen=True)
class _ReviewedDefinition:
    entry_id:str
    revision_digest:str
    payload:dict


def parse_declared_metadata_mapping_inputs(value):
    if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
    if value.get('contract_version')=='boi/declared-metadata-mapping-input@4':
        return DeclaredMetadataMappingInputsV4.model_validate(value)
    if value.get('contract_version')=='boi/declared-metadata-mapping-input@3':
        return DeclaredMetadataMappingInputsV3.model_validate(value)
    model=DeclaredMetadataMappingInputsV2 if value.get('contract_version')=='boi/declared-metadata-mapping-input@2' else DeclaredMetadataMappingInputs
    return model.model_validate(value)


def sqlite_logical_type_check(declared_type, logical_type, temporal_encoding=None):
    """SQLite's documented ordered affinity rules, not name-based ontology.

    https://www.sqlite.org/datatype3.html#determination_of_column_affinity
    Affinity is only metadata; actual storage classes must still be audited.
    No implicit text/numeric, temporal or application-specific boolean codec.
    """
    name=str(declared_type).upper()
    affinity=sqlite_declared_affinity(declared_type)
    allowed={'string':{'TEXT'},'integer':{'INTEGER','NUMERIC'},'number':{'INTEGER','REAL','NUMERIC'}}
    if logical_type in {'date','datetime','duration'} or temporal_encoding is not None:
        check=temporal_encoding_check(declared_type,logical_type,temporal_encoding)
        compatible=bool(check['compatible']);reason=str(check['reason_code'])
    elif logical_type=='boolean':
        compatible=name.strip() in {'BOOLEAN','BOOL'}
        reason='' if compatible else 'VALUE_TYPE_ENCODING_CONTRACT_REQUIRED'
    elif logical_type in allowed:
        compatible=affinity in allowed[logical_type]
        reason='' if compatible else 'LOGICAL_PHYSICAL_TYPE_MISMATCH'
    else:
        compatible=False;reason='VALUE_TYPE_ENCODING_CONTRACT_REQUIRED'
    return {'logical_primitive_type':logical_type,'physical_affinity':affinity,
        'compatible':compatible,'reason_code':reason}


def verify_declared_metadata_mapping_catalog(inputs, *, catalog_snapshot, catalog_snapshot_digest):
    """Metadata checks only, not key-data/quality qualification or execution.

    This shared deterministic entry point replaces no historical function. It
    preserves explicit policies and never manufactures a pass from catalog-only
    information. Actual source-data checks remain a required consumer stage.
    """
    inputs=parse_declared_metadata_mapping_inputs(inputs)
    if inputs.catalog_snapshot_digest!=catalog_snapshot_digest:
        raise ValueError('DECLARED_MAPPING_CATALOG_STALE')
    if catalog_snapshot.get('schema_digest')!=inputs.schema_snapshot_digest:
        raise ValueError('DECLARED_MAPPING_SCHEMA_STALE')
    tables=_catalog_tables(catalog_snapshot)
    checks=[]
    for prop in inputs.properties:
        table=tables.get(prop.physical.table,{})
        columns=table.get('columns',{})
        actual=columns.get(prop.physical.column)
        if isinstance(actual,Mapping):actual=actual.get('data_type')
        exists=prop.physical.column in columns
        type_ok=exists and str(actual).casefold()==prop.declared_data_type.casefold()
        logical_check=None
        if isinstance(prop,DeclaredPropertyMappingV2):
            logical_check=(sqlite_logical_type_check(
                    actual,prop.logical_primitive_type,
                    prop.physical.temporal_encoding)
                if catalog_snapshot.get('dialect')=='sqlite' else
                {'compatible':False,'reason_code':'LOGICAL_TYPE_DIALECT_VALIDATOR_UNAVAILABLE'})
            type_ok=type_ok and logical_check['compatible']
        material={'mapping_ref':prop.physical.mapping_ref,'catalog_digest':catalog_snapshot_digest,
            'schema_digest':inputs.schema_snapshot_digest,'exists':exists,'type_matches':type_ok,
            'expected_type':prop.declared_data_type,'actual_type':actual,
            'evidence_span_refs':list(prop.evidence_span_refs)}
        if logical_check is not None:
            material.update(logical_type_check=logical_check,value_type_ref=prop.value_type_ref,
                value_type_revision_digest=prop.value_type_revision_digest)
        checks.append({**material,'status':'pass' if type_ok else 'fail',
            'reason_codes':[] if type_ok else ([logical_check['reason_code']] if exists and logical_check and not logical_check['compatible']
                else ['PHYSICAL_TYPE_MISMATCH' if exists else 'PHYSICAL_COLUMN_UNRESOLVED']),
            'evidence_digest':_digest(material)})
    return {'contract_version':'boi/declared-mapping-catalog-check@1',
        'mapping_checks':checks,'catalog_checks_status':'pass' if all(c['status']=='pass' for c in checks) else 'fail',
        'domain_candidate_closure_digest':inputs.domain_candidate_closure_digest,
        'input_digest':_digest(inputs),'data_quality_status':'not_run',
        'query_readiness':'not_run','stage_status':'partial' if all(c['status']=='pass' for c in checks) else 'fail',
        'relationship_contract_digests':[r.contract_digest for r in inputs.relationships],
        'result_shape_contract_digests':[s.contract_digest for s in inputs.result_shapes],
        'attention_items':[{'reason_code':'SOURCE_KEY_AND_QUALITY_VALIDATION_REQUIRED'}],
        'production_changed':False,'active_transition':False}


class SemanticMetadataMappingService:
    """Existing source/candidate-to-mapping bridge, not another orchestrator.

    Logical ownership comes only from validated actual definitions. Physical
    identity comes only from a selected source schema and exact stable ID. New
    sparse meanings need a logical contract; table names never supply one.
    This service cannot execute a query or approve a mapping.
    """
    def __init__(self, *, source_intake, authorization, source_profile, policy,
                 current_authorization, gateway=None, purpose=''):
        self.intake=source_intake;self.authorization=authorization
        self.source_profile=source_profile;self.policy=policy
        self.current_authorization=current_authorization
        self.gateway=gateway;self.purpose=purpose

    def __call__(self, *, context, records, definitions, candidates, validations, prior_outputs):
        if self.current_authorization()!=self.authorization:
            raise ValueError('METADATA_MAPPING_POLICY_CHANGED')
        attention=[];proposals=[];reconciliations=[]
        if self.policy is None:
            return {'mapping_candidates':[], 'stage_status':'partial','query_readiness':'not_run',
                'attention_items':[{'reason_code':'PHYSICAL_SOURCE_PROFILE_REQUIRED'}]}
        if (self.source_profile.collection_path!=('tables','*','columns','*')
            or self.source_profile.identity_key!='stable_id'):
            raise ValueError('PHYSICAL_SOURCE_PROFILE_BINDING_UNSUPPORTED')
        columns={}; source_refs={ref['artifact_ref']:ref for ref in context.source_artifacts}
        from .corporate_metadata_intake import build_corporate_metadata_intake
        for artifact_ref in sorted({record.record.artifact_ref for record in records}):
            ref=source_refs.get(artifact_ref)
            if not ref or ref['role']!='corporate_metadata':
                raise ValueError('PHYSICAL_SOURCE_ARTIFACT_CLOSURE_MISMATCH')
            raw=self.intake.resolve_bytes(authorization=self.authorization,reference=ref)
            import yaml
            header=yaml.safe_load(raw)
            if not isinstance(header,dict) or header.get('snapshot_version')!=self.policy.format:
                raise ValueError('PHYSICAL_METADATA_FORMAT_MISMATCH')
            result=build_corporate_metadata_intake(metadata_bytes=raw,metadata_artifact_ref=artifact_ref,
                metadata_digest=ref['digest'],catalog_snapshot=context.catalog_snapshot,
                catalog_snapshot_digest=context.catalog_snapshot['digest'])
            reconciliations.append(result['catalog_reconciliation_receipt'])
            for span in result['evidence_spans']:
                data=span['structured_evidence']
                for column in data['columns']:
                    key=(artifact_ref,column['stable_id'])
                    if key in columns:
                        raise ValueError('PHYSICAL_SOURCE_STABLE_ID_AMBIGUOUS')
                    columns[key]=(
                        data['table_name'], column['column_name'],
                        column['catalog_type'], column.get('temporal_encoding'),
                    )
        by_ref={entry.entry_id:entry for entry in definitions.entries}
        from .semantic_binding_validator import ReviewedDefinitionValidation
        reviewed_refs=set()
        for digest,(_,_,candidate) in candidates.items():
            validation=validations.get(digest)
            if not isinstance(validation,ReviewedDefinitionValidation) or validation.status!='REVIEWED_PROVISIONAL':
                continue
            logical=candidate.get('logical_definition') or {}
            if (validation.candidate_digest!=digest or validation.definition_ref!=logical.get('id')
                or validation.definition_digest!=_digest(logical)
                or validation.receipt_digest!=_digest(validation.model_dump(mode='json',exclude={'receipt_digest'}))
                or logical['id'] in by_ref):
                raise ValueError('REVIEWED_MAPPING_DEFINITION_DRIFT')
            by_ref[logical['id']]=_ReviewedDefinition(logical['id'],_digest(logical),logical)
            reviewed_refs.add(validation.review_receipt_digest)
        for candidate_digest,(record,claim,candidate) in sorted(candidates.items()):
            self.intake.metadata.verify_record(authorization=self.authorization,record=record)
            validation=validations.get(candidate_digest)
            reviewed=isinstance(validation,ReviewedDefinitionValidation) and validation.status=='REVIEWED_PROVISIONAL'
            entry=by_ref.get(claim.proposed_concept.ref) if claim.proposed_concept else by_ref.get(validation.definition_ref) if reviewed else None
            if not validation or (validation.status!='VALIDATED' and not reviewed):
                attention.append({'candidate_digest':candidate_digest,'reason_code':'SEMANTIC_MAPPING_BINDING_NOT_VALIDATED'})
                continue
            kind=(entry.payload.get('kind') if entry else
                (candidate.get('logical_definition') or {}).get('kind'))
            if kind and kind!='PropertyDefinition':
                # Domain relation/object/metric declarations have source evidence
                # but are not themselves physical column mapping requests.
                if entry is None and not reviewed:
                    attention.append({'candidate_digest':candidate_digest,
                        'reason_code':'DOMAIN_DEFINITION_REVIEW_REQUIRED'})
                continue
            if not entry or entry.payload.get('kind')!='PropertyDefinition':
                attention.append({'candidate_digest':candidate_digest,'reason_code':'LOGICAL_PROPERTY_OWNER_REQUIRED'})
                continue
            owner=by_ref.get(entry.payload['owner_ref'])
            if not owner or owner.payload.get('kind')!='ObjectType':
                attention.append({'candidate_digest':candidate_digest,'reason_code':'LOGICAL_OBJECT_CONTRACT_REQUIRED'})
                continue
            value_type=by_ref.get(entry.payload['value_type_ref'])
            if not value_type or value_type.payload.get('kind')!='ValueType':
                attention.append({'candidate_digest':candidate_digest,'reason_code':'LOGICAL_VALUE_TYPE_CONTRACT_REQUIRED'})
                continue
            physical=columns.get((record.record.artifact_ref,record.record.record_key))
            if not physical:
                attention.append({'candidate_digest':candidate_digest,'reason_code':'PHYSICAL_RECORD_ID_UNRESOLVED'})
                continue
            table,column,data_type,temporal_encoding=physical
            if not data_type:
                attention.append({'candidate_digest':candidate_digest,'reason_code':'PHYSICAL_COLUMN_UNRESOLVED'})
                continue
            logical_type=value_type.payload['primitive_type']
            forward_encoding=self.policy.format=='corporate-column-metadata/v2'
            if forward_encoding and (
                    logical_type in {'date','datetime','duration'}
                    or temporal_encoding is not None):
                encoding_check=temporal_encoding_check(
                    data_type,logical_type,temporal_encoding,
                )
                if not encoding_check['compatible']:
                    attention.append({
                        'candidate_digest':candidate_digest,
                        'reason_code':encoding_check['reason_code'],
                    })
                    continue
            material={'candidate_digest':candidate_digest,'logical_property_ref':entry.entry_id,
                'source_id':self.policy.source_id,'table':table,'column':column,
                'source_snapshot_digest':self.policy.source_snapshot_digest,
                'schema_digest':context.catalog_snapshot['schema_digest']}
            if temporal_encoding is not None:
                material['temporal_encoding']=temporal_encoding
            mapping=AuthorizedPhysicalMapping(mapping_ref='mapping:'+_digest(material)[7:],
                source_id=self.policy.source_id,table=table,column=column,revision_digest=_digest(material),
                temporal_encoding=temporal_encoding)
            property_model=(DeclaredPropertyMappingV3 if forward_encoding
                else DeclaredPropertyMappingV2)
            proposals.append(property_model(logical_property_ref=entry.entry_id,owner_ref=owner.entry_id,
                physical=mapping,declared_data_type=data_type,unit_semantics=entry.payload['unit_semantics'],
                unit_ref=entry.payload.get('unit_ref'),time_semantics=entry.payload['time_semantics'],
                value_type_ref=value_type.entry_id,value_type_revision_digest=value_type.revision_digest,
                logical_primitive_type=logical_type,
                evidence_span_refs=tuple(span['span_ref'] for span in candidate['field_evidence'])))
        objects=[]
        for owner_ref in sorted({p.owner_ref for p in proposals}):
            props=[p for p in proposals if p.owner_ref==owner_ref]
            by_logical={p.logical_property_ref:p for p in props}
            if len(by_logical)!=len(props):
                attention.append({'object_ref':owner_ref,'reason_code':'SEMANTIC_PROPERTY_INSTANCE_IDENTITY_REQUIRED'})
                continue
            grain=tuple(by_ref[owner_ref].payload['logical_grain'])
            if not set(grain)<=by_logical.keys():
                attention.append({'object_ref':owner_ref,'reason_code':'LOGICAL_KEY_MAPPING_CLOSURE_INCOMPLETE'})
                continue
            objects.append(DeclaredObjectMapping(object_ref=owner_ref,
                property_mapping_refs=tuple(p.physical.mapping_ref for p in props),
                logical_key_mapping_refs=tuple(by_logical[key].physical.mapping_ref for key in grain),
                evidence_span_refs=tuple(sorted({ref for p in props for ref in p.evidence_span_refs}))))
        result={'mapping_candidates':[p.model_dump(mode='json') for p in proposals],
            'catalog_reconciliation_receipts':reconciliations,'stage_status':'partial',
            'data_quality_status':'not_run','query_readiness':'not_run','attention_items':attention,
            'production_changed':False,'active_transition':False}
        if any(r['status']!='pass' for r in reconciliations):
            result['stage_status']='fail'
            attention.append({'reason_code':'CATALOG_SCHEMA_DRIFT'})
        if not proposals:
            attention.append({'reason_code':'LOGICAL_MAPPING_CANDIDATES_UNRESOLVED'})
        if objects and not attention:
            forward_encoding=self.policy.format=='corporate-column-metadata/v2'
            input_model=(DeclaredMetadataMappingInputsV4 if forward_encoding else
                DeclaredMetadataMappingInputsV3 if reviewed_refs else
                DeclaredMetadataMappingInputsV2)
            contract_version=('boi/declared-metadata-mapping-input@4'
                if forward_encoding else 'boi/declared-metadata-mapping-input@3'
                if reviewed_refs else 'boi/declared-metadata-mapping-input@2')
            by_mapping={p.physical.mapping_ref:p for p in proposals}
            object_shapes=derive_metadata_object_set_shapes(object_mappings=[{
                'object_ref':obj.object_ref,
                'logical_key_mapping_refs':tuple(by_mapping[ref].logical_property_ref
                    for ref in obj.logical_key_mapping_refs),
            } for obj in objects],maximum_rows=1000)
            inputs=input_model(contract_version=contract_version,
                **({'semantic_authority_scope':'reviewed_provisional','interpretation_receipt_digests':tuple(sorted(reviewed_refs))} if reviewed_refs else {}),
                source_id=self.policy.source_id,source_snapshot_digest=self.policy.source_snapshot_digest,
                catalog_snapshot_digest=context.catalog_snapshot['digest'],
                schema_snapshot_digest=context.catalog_snapshot['schema_digest'],policy_digest=self.authorization.policy_digest,
                domain_candidate_closure_digest=_digest(sorted(candidates)),
                authorized_evidence_span_refs=tuple(sorted({ref for p in proposals for ref in p.evidence_span_refs})),
                objects=tuple(objects),properties=tuple(proposals),relationships=(),result_shapes=object_shapes)
            result.update(verify_declared_metadata_mapping_catalog(inputs,catalog_snapshot=context.catalog_snapshot,
                catalog_snapshot_digest=context.catalog_snapshot['digest']))
            result['declared_mapping_inputs']=inputs.model_dump(mode='json')
            if self.gateway is not None and self.policy.quality_grant_digest is not None and result['catalog_checks_status']=='pass':
                try:
                    audit=self.gateway.profile_declared_mapping(inputs=inputs,
                        principal=self.authorization.principal,purpose=self.purpose,
                        manifest_digest=context.manifest_digest,expected_grant_digest=self.policy.quality_grant_digest)
                except ValueError as error:
                    code=str(error)
                    allowed={'METADATA_QUALITY_CAPABILITY_UNAVAILABLE','METADATA_QUALITY_ACCESS_DENIED',
                        'METADATA_QUALITY_GRANT_STALE','METADATA_QUALITY_SCOPE_OR_SNAPSHOT_MISMATCH',
                        'METADATA_QUALITY_MAPPING_NOT_AUTHORIZED','METADATA_QUALITY_SOURCE_DRIFT',
                        'METADATA_QUALITY_LOGICAL_TYPE_MISMATCH',
                        'METADATA_QUALITY_PHYSICAL_TYPE_MISMATCH','METADATA_QUALITY_SCAN_REJECTED_OR_TIMEOUT',
                        'METADATA_QUALITY_GRANT_CHANGED','METADATA_QUALITY_GRANT_INVALID_OR_CHANGED',
                        'WAL_SNAPSHOT_UNSEALED','SOURCE_SNAPSHOT_DRIFT','AUTHORIZED_TABLE_NOT_FOUND'}
                    result['attention_items']=[{'reason_code':code if code in allowed else 'METADATA_QUALITY_AUDIT_FAILED'}]
                else:
                    # Integrity must resolve from the actual Gateway, not model
                    # input or a caller-injected ready/pass flag.
                    if (audit.get('receipt_digest')!=_digest({k:v for k,v in audit.items() if k!='receipt_digest'})
                        or audit.get('mapping_input_digest')!=_digest(inputs)
                        or audit.get('manifest_digest')!=context.manifest_digest
                        or audit.get('principal')!=self.authorization.principal or audit.get('purpose')!=self.purpose
                        or audit.get('grant_digest')!=self.policy.quality_grant_digest):
                        raise ValueError('METADATA_QUALITY_RECEIPT_CLOSURE_MISMATCH')
                    result.update(quality_audit_receipt=audit,object_key_quality_receipts=audit['object_key_receipts'],
                        data_quality_status=audit['status'],stage_status=audit['status'])
                    if audit.get('value_type_quality_receipts'):
                        result['value_type_quality_receipts']=audit['value_type_quality_receipts']
                    result['attention_items']=[{'reason_code':reason} for reason in dict.fromkeys([
                        *audit['reason_codes'],*(reason for item in audit['object_key_receipts'] for reason in item['reason_codes'])])]
        return result

    def query_contracts(self, *, context, records, definitions, candidates, validations, prior_outputs):
        """Draft logical ObjectSet shapes, never choose/execute a user query.

        No relationship, reducer, latest policy or flat export is invented from
        schema. Remaining source-data checks are reported, not converted to pass.
        """
        if self.current_authorization()!=self.authorization:
            raise ValueError('METADATA_MAPPING_POLICY_CHANGED')
        mapping=prior_outputs.get('physical-mapping-verify') or {}
        raw=mapping.get('declared_mapping_inputs')
        if raw is None:
            return {'query_candidates':[], 'stage_status':'partial','query_readiness':'not_run',
                'attention_items':[{'reason_code':'PHYSICAL_MAPPING_CLOSURE_INCOMPLETE'}]}
        inputs=parse_declared_metadata_mapping_inputs(raw)
        if (inputs.policy_digest!=self.authorization.policy_digest
            or inputs.domain_candidate_closure_digest!=_digest(sorted(candidates))
            or mapping.get('input_digest')!=_digest(inputs)):
            raise ValueError('QUERY_MAPPING_CANDIDATE_CLOSURE_STALE')
        shapes=inputs.result_shapes
        if not shapes:
            # Previously persisted mapping stages had no shape declaration.
            # Preserve their candidate identity when an interrupted run resumes.
            properties={p.physical.mapping_ref:p for p in inputs.properties}
            legacy_shapes=[]
            for obj in inputs.objects:
                keys=tuple(properties[ref].logical_property_ref
                    for ref in obj.logical_key_mapping_refs)
                legacy_shapes.append(ResultShapeContract(
                    contract_id='result-shape:candidate:'+_digest({
                        'manifest':context.manifest_digest,'object_ref':obj.object_ref,
                        'logical_grain':keys})[7:],
                    shape='ObjectSet',root_object_ref=obj.object_ref,exact_grain=keys,
                    relationship_refs=(),collection_semantics=None,aggregation_semantics=None,
                    null_policy='PRESERVE',duplicate_policy='BLOCK',
                    order_policy={'deterministic':True,'keys':keys},
                    limit_policy={'kind':'EXPLICIT','maximum_rows':1000},
                    completeness_policy='BOUNDED',fanout_semantics=None))
            shapes=tuple(legacy_shapes)
        query_candidates=[]
        for shape in shapes:
            if shape.shape!='ObjectSet':
                continue  # Complex shapes require their own reviewed authoring and quality closure.
            body={'kind':'boi/Exploratory Query Shape Candidate','result_shape':shape.model_dump(mode='json'),
                'domain_candidate_closure_digest':inputs.domain_candidate_closure_digest,
                'mapping_input_digest':_digest(inputs),'typed_parameters':[],
                'logical_plan_status':'not_authored','execution_status':'not_run',
                'status':'PROVISIONAL','authority':'candidate_only','production_changed':False,'active_transition':False}
            if getattr(inputs,'semantic_authority_scope',None)=='reviewed_provisional':
                body.update(semantic_authority_scope=inputs.semantic_authority_scope,
                    interpretation_receipt_digests=list(inputs.interpretation_receipt_digests))
            query_candidates.append({**body,'candidate_digest':_digest(body)})
        return {'query_candidates':query_candidates,'stage_status':'partial','query_readiness':'not_run',
            'attention_items':([{'reason_code':'SOURCE_KEY_AND_QUALITY_VALIDATION_REQUIRED'}]
                if mapping.get('data_quality_status')!='pass' else [])+
                [{'reason_code':'QUERY_INTENT_AND_PLAN_FREEZE_REQUIRED'}],
            'production_changed':False,'active_transition':False}


@dataclass(frozen=True)
class _JoinKey:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    optional: bool


def _extract_join_keys(sql: str, *, dialect: str) -> tuple[_JoinKey, ...]:
    statements = tuple(item for item in parse(sql, read=dialect) if item is not None)
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise ValueError("READ_ONLY_QUERY_REQUIRED")
    statement = statements[0]
    aliases = {
        str(table.alias_or_name): str(table.name)
        for table in statement.find_all(exp.Table)
    }
    output: list[_JoinKey] = []
    for join in statement.find_all(exp.Join):
        predicate = join.args.get("on")
        if predicate is None:
            raise ValueError("JOIN_PREDICATE_REQUIRED")
        optional = str(join.args.get("side") or "").upper() == "LEFT"
        for equality in predicate.find_all(exp.EQ):
            left = equality.left
            right = equality.right
            if not isinstance(left, exp.Column) or not isinstance(right, exp.Column):
                raise ValueError("JOIN_KEY_EXPRESSION_UNSUPPORTED")
            left_table = aliases.get(str(left.table), str(left.table))
            right_table = aliases.get(str(right.table), str(right.table))
            if not left_table or not right_table or not left.name or not right.name:
                raise ValueError("JOIN_KEY_UNRESOLVED")
            output.append(
                _JoinKey(
                    left_table=left_table,
                    left_column=str(left.name),
                    right_table=right_table,
                    right_column=str(right.name),
                    optional=optional,
                )
            )
    if not output:
        raise ValueError("JOIN_KEY_REQUIRED")
    return tuple(output)


def _catalog_tables(
    catalog_snapshot: Mapping[str, object],
) -> dict[str, dict[str, object]]:
    raw = catalog_snapshot.get("tables") or {}
    if not isinstance(raw, Mapping):
        raise ValueError("CATALOG_SNAPSHOT_SCHEMA_INVALID")
    return {
        str(table): dict(definition)
        for table, definition in raw.items()
        if isinstance(definition, Mapping)
    }


def derive_metadata_object_set_shapes(
    *, object_mappings: Iterable[Mapping[str, object]], maximum_rows: int,
) -> tuple[ResultShapeContract, ...]:
    """Draft independent identity-grain shapes, without query-specific semantics.

    This transformation grants no approval. Key validation and exact contract
    qualification still belong to the consuming migration/preview gate.
    Historical nested-shape derivation is intentionally unchanged.
    """
    if not 1 <= maximum_rows <= 1000:
        raise ValueError("EXPLORATORY_ROW_BUDGET_INVALID")
    shapes = []
    seen = set()
    for mapping in sorted(object_mappings, key=lambda item: str(item["object_ref"])):
        root = str(mapping["object_ref"])
        if root in seen:
            raise ValueError("OBJECT_MAPPING_DUPLICATE")
        seen.add(root)
        keys = tuple(mapping["logical_key_mapping_refs"])
        shapes.append(ResultShapeContract(
            contract_id="result-shape:object-set:" + _digest({
                "contract": "metadata-object-set-candidate@1", "root": root,
                "grain": keys, "maximum_rows": maximum_rows})[7:31],
            shape="ObjectSet", root_object_ref=root, exact_grain=keys,
            relationship_refs=(), collection_semantics=None, aggregation_semantics=None,
            null_policy="PRESERVE", duplicate_policy="BLOCK",
            order_policy={"deterministic": True, "keys": keys},
            limit_policy={"kind": "EXPLICIT", "maximum_rows": maximum_rows},
            completeness_policy="BOUNDED", fanout_semantics=None,
        ))
    return tuple(shapes)


def derive_metadata_result_shape(
    *,
    object_mappings: Iterable[Mapping[str, object]],
    relationships: Iterable[RelationshipContract],
) -> ResultShapeContract:
    """Derive a relationship-revision-aware nested shape from verified contracts."""

    mappings = tuple(dict(item) for item in object_mappings)
    relationship_values = tuple(relationships)
    directed_children: dict[str, list[str]] = {}
    by_endpoints: dict[tuple[str, str], RelationshipContract] = {}
    for relationship in relationship_values:
        if relationship.direction != "left_to_right":
            continue
        directed_children.setdefault(relationship.left_endpoint_ref, []).append(
            relationship.right_endpoint_ref
        )
        by_endpoints[
            (relationship.left_endpoint_ref, relationship.right_endpoint_ref)
        ] = relationship
    candidate_roots: list[tuple[int, str, tuple[str, ...]]] = []
    for parent_ref, child_refs in directed_children.items():
        leaf_children = tuple(
            child for child in child_refs if not directed_children.get(child)
        )
        if len(leaf_children) >= 2:
            candidate_roots.append((len(leaf_children), parent_ref, leaf_children))
    if not candidate_roots:
        raise ValueError("NESTED_RESULT_SHAPE_ROOT_UNRESOLVED")
    _, root_ref, leaf_children = sorted(candidate_roots, reverse=True)[0]
    root_mapping = next(item for item in mappings if item["object_ref"] == root_ref)
    selected = tuple(by_endpoints[(root_ref, child)] for child in leaf_children)
    relationship_refs = tuple(item.contract_id for item in selected)
    baseline_many = all(item.cardinality == "one_to_many" for item in selected)
    collection_semantics = "independent child collections; no sibling cross product"
    fanout_semantics = "NO_SIBLING_CROSS_PRODUCT"
    if not baseline_many:
        cardinalities = ",".join(
            f"{item.contract_id}={item.cardinality}" for item in selected
        )
        collection_semantics += f"; relationship cardinalities: {cardinalities}"
        fanout_semantics = "CARDINALITY_AWARE_NO_SIBLING_CROSS_PRODUCT"
    return ResultShapeContract(
        contract_id="result-shape:" + _digest(
            {"root": root_ref, "relationships": relationship_refs}
        )[7:23],
        shape="NestedCollection",
        root_object_ref=root_ref,
        exact_grain=tuple(root_mapping["logical_key_mapping_refs"]),
        relationship_refs=relationship_refs,
        collection_semantics=collection_semantics,
        aggregation_semantics=None,
        null_policy="EXCLUDE_WITH_DISCLOSURE",
        duplicate_policy="DISTINCT_BY_GRAIN",
        order_policy={
            "deterministic": True,
            "keys": tuple(root_mapping["logical_key_mapping_refs"]),
        },
        limit_policy={"kind": "NONE", "maximum_rows": None},
        completeness_policy="QUALITY_SIDECAR_REQUIRED",
        fanout_semantics=fanout_semantics,
    )


def build_metadata_mapping_profile(
    *,
    source_id: str,
    sqlite_path: Path,
    catalog_snapshot: Mapping[str, object],
    catalog_snapshot_digest: str,
    evidence_spans: Iterable[Mapping[str, object]],
    domain_candidates: Iterable[Mapping[str, object]],
    legacy_sql: str,
    dialect: str,
    policy_digest: str,
    fanout_budget_per_parent: int,
) -> MetadataMappingProfileCandidate:
    """Create a candidate-only mapping package from declared inputs.

    SQL is parsed as source evidence only. Database access is restricted to the
    schema capture and key-only quality profiler; no row is returned to a model.
    """

    if fanout_budget_per_parent < 1:
        raise ValueError("FANOUT_BUDGET_INVALID")
    tables = _catalog_tables(catalog_snapshot)
    spans = tuple(dict(item) for item in evidence_spans)
    candidates = tuple(dict(item) for item in domain_candidates)
    candidate_by_evidence: dict[str, dict[str, object]] = {}
    for candidate in candidates:
        refs = tuple(str(item) for item in candidate.get("evidence_span_refs") or ())
        if len(refs) != 1 or refs[0] in candidate_by_evidence:
            raise ValueError("DOMAIN_EVIDENCE_BINDING_AMBIGUOUS")
        candidate_by_evidence[refs[0]] = candidate

    physical: list[AuthorizedPhysicalMapping] = []
    object_mappings: list[dict[str, object]] = []
    mapping_by_key: dict[tuple[str, str], AuthorizedPhysicalMapping] = {}
    object_by_table: dict[str, str] = {}
    for span in spans:
        evidence_ref = str(span.get("evidence_span_ref") or "")
        structured = span.get("structured_evidence")
        if not isinstance(structured, Mapping):
            raise ValueError("STRUCTURED_EVIDENCE_REQUIRED")
        table = str(structured.get("table_name") or "")
        candidate = candidate_by_evidence.get(evidence_ref)
        if candidate is None or table not in tables:
            raise ValueError("DOMAIN_TABLE_BINDING_UNRESOLVED")
        object_ref = str(candidate.get("candidate_id") or "")
        object_by_table[table] = object_ref
        column_refs: list[str] = []
        for column in structured.get("columns") or ():
            if not isinstance(column, Mapping):
                raise ValueError("COLUMN_EVIDENCE_INVALID")
            name = str(column.get("column_name") or "")
            stable_id = str(column.get("stable_id") or "")
            if name not in dict(tables[table].get("columns") or {}) or not stable_id:
                raise ValueError("PHYSICAL_COLUMN_UNRESOLVED")
            mapping_ref = "mapping:" + stable_id
            payload = {
                "mapping_ref": mapping_ref,
                "source_id": source_id,
                "table": table,
                "column": name,
                "object_ref": object_ref,
                "catalog_snapshot_digest": catalog_snapshot_digest,
            }
            mapping = AuthorizedPhysicalMapping(
                mapping_ref=mapping_ref,
                source_id=source_id,
                table=table,
                column=name,
                revision_digest=_digest(payload),
            )
            physical.append(mapping)
            mapping_by_key[(table, name)] = mapping
            column_refs.append(mapping_ref)
        key_columns = tuple(str(item) for item in tables[table].get("primary_key") or ())
        if not key_columns:
            raise ValueError(f"LOGICAL_KEY_REQUIRED:{table}")
        object_mappings.append(
            {
                "object_ref": object_ref,
                "source_id": source_id,
                "table": table,
                "property_mapping_refs": column_refs,
                "logical_key_mapping_refs": [
                    mapping_by_key[(table, column)].mapping_ref
                    for column in key_columns
                ],
                "grain": [
                    mapping_by_key[(table, column)].mapping_ref
                    for column in key_columns
                ],
                "evidence_span_ref": evidence_ref,
            }
        )

    schema = capture_multi_result_sqlite_schema(
        sqlite_path,
        allowed_tables=tuple(sorted(tables)),
    )
    relationships: list[RelationshipContract] = []
    qualities: list[DataQualityReceipt] = []
    for index, join_key in enumerate(_extract_join_keys(legacy_sql, dialect=dialect)):
        left_key = tuple(tables[join_key.left_table].get("primary_key") or ())
        right_key = tuple(tables[join_key.right_table].get("primary_key") or ())
        left_is_key = left_key == (join_key.left_column,)
        right_is_key = right_key == (join_key.right_column,)
        if left_is_key == right_is_key:
            raise ValueError(
                "JOIN_PARENT_KEY_AMBIGUOUS:"
                f"{join_key.left_table}.{join_key.left_column}="
                f"{join_key.right_table}.{join_key.right_column}"
            )
        if left_is_key:
            parent_table, parent_column = join_key.left_table, join_key.left_column
            child_table, child_column = join_key.right_table, join_key.right_column
        else:
            parent_table, parent_column = join_key.right_table, join_key.right_column
            child_table, child_column = join_key.left_table, join_key.left_column
        parent_ref = object_by_table[parent_table]
        child_ref = object_by_table[child_table]
        parent_mapping = mapping_by_key[(parent_table, parent_column)]
        child_mapping = mapping_by_key[(child_table, child_column)]
        contract_id = (
            "relationship:"
            + _digest(
                {
                    "parent": parent_mapping.mapping_ref,
                    "child": child_mapping.mapping_ref,
                    "index": index,
                }
            )[7:23]
        )
        orphan_policy = "EXCLUDE_WITH_DISCLOSURE" if join_key.optional else "BLOCK"
        common = {
            "contract_id": contract_id,
            "left_endpoint_ref": parent_ref,
            "right_endpoint_ref": child_ref,
            "direction": "left_to_right",
            "semantic_name": f"{parent_ref}_has_{child_ref}",
            "cardinality": (
                "one_to_one"
                if tuple(tables[child_table].get("primary_key") or ())
                == (child_column,)
                else "one_to_many"
            ),
            "optionality": "optional" if join_key.optional else "required",
            "physical_keys": {
                "left_mapping_refs": [parent_mapping.mapping_ref],
                "right_mapping_refs": [child_mapping.mapping_ref],
            },
            "relationship_identity_ref": None,
            "temporal_validity": {
                "mode": "none",
                "valid_from_property_ref": None,
                "valid_to_property_ref": None,
            },
            "null_policy": (
                "EXCLUDE_WITH_DISCLOSURE" if join_key.optional else "BLOCK"
            ),
            "orphan_policy": orphan_policy,
            "duplicate_policy": "PRESERVE_DISTINCT_CHILDREN",
            "fanout": {
                "observed_min": 0,
                "observed_p50": 0,
                "observed_p95": 0,
                "observed_max": 0,
                "budget_per_parent": fanout_budget_per_parent,
                "budget_action": "BLOCK",
            },
            "acl_propagation": "INTERSECTION",
            "schema_snapshot_digest": schema.schema_digest,
        }
        draft = RelationshipContract.model_validate(common)
        observed = profile_sqlite_relationship_quality(
            sqlite_path,
            schema=schema,
            relationship=draft,
            physical_mappings=tuple(physical),
            root_endpoint_ref=parent_ref,
            evidence_ref=f"boi://quality/{contract_id}/profile",
        )
        final = RelationshipContract.model_validate(
            {
                **common,
                "fanout": {
                    **observed.fanout_distribution.model_dump(),
                    "budget_per_parent": fanout_budget_per_parent,
                    "budget_action": "BLOCK",
                },
            }
        )
        quality = profile_sqlite_relationship_quality(
            sqlite_path,
            schema=schema,
            relationship=final,
            physical_mappings=tuple(physical),
            root_endpoint_ref=parent_ref,
            evidence_ref=f"boi://quality/{contract_id}/profile",
        )
        relationships.append(final)
        qualities.append(quality)

    result_shape = derive_metadata_result_shape(
        object_mappings=object_mappings,
        relationships=relationships,
    )
    profile_payload = {
        "profile_version": "boi/data-mapping-candidate@0.1.0",
        "status": "candidate",
        "source_id": source_id,
        "catalog_snapshot_digest": catalog_snapshot_digest,
        "schema_snapshot_digest": schema.schema_digest,
        "policy_digest": policy_digest,
        "object_mappings": object_mappings,
        "physical_mapping_digests": [item.revision_digest for item in physical],
        "relationship_contract_digests": [
            item.contract_digest for item in relationships
        ],
        "quality_receipt_digests": [item.receipt_digest for item in qualities],
        "result_shape_contract_digest": result_shape.contract_digest,
        "raw_row_model_input_count": 0,
        "prefreeze_oracle_access_count": 0,
        "production_changed": False,
        "active_transition": False,
    }
    return MetadataMappingProfileCandidate(
        profile_version=str(profile_payload["profile_version"]),
        status="candidate",
        source_id=source_id,
        catalog_snapshot_digest=catalog_snapshot_digest,
        schema_snapshot_digest=schema.schema_digest,
        policy_digest=policy_digest,
        object_mappings=tuple(object_mappings),
        physical_mappings=tuple(physical),
        relationship_contracts=tuple(relationships),
        data_quality_receipts=tuple(qualities),
        result_shape_contract=result_shape,
        profile_digest=_digest(profile_payload),
    )
