"""Declarative source-record and field intake; candidate evidence, not approval."""
from __future__ import annotations
from dataclasses import dataclass
from collections import Counter
from datetime import datetime
import hashlib
import json
import sys
from pathlib import Path
from typing import Literal, Annotated

from pydantic import Field, model_validator, TypeAdapter
import yaml
from boi_api.app.governed_runtime.semantic_binding_contract import (
    FrozenContract, Ref, Digest, RevisionRef, SourceRecordRevision, semantic_digest,
)
from boi_api.app.governed_runtime.semantic_binding_validator import FieldEvidenceRecord


def bytes_digest(raw): return 'sha256:'+hashlib.sha256(raw).hexdigest()


class MetadataField(FrozenContract):
    source_key: Ref
    purpose: Literal['label', 'description', 'condition', 'exception', 'unit_label', 'quantity_label', 'role_label']


class RecordSourceProfile(FrozenContract):
    profile_version: Literal['boi/record-field-metadata-source@0.1.0']
    profile_id: Ref
    source_system: Ref
    dataset: Ref
    namespace: Ref
    format: Literal['json', 'yaml']
    collection_path: tuple[Ref, ...] = Field(min_length=1)
    identity_key: Ref
    semantic_fields: tuple[MetadataField, ...] = Field(min_length=1)
    effective_from_key: Ref | None = None
    effective_until_key: Ref | None = None

    @model_validator(mode='after')
    def distinct_fields(self):
        if len({field.source_key for field in self.semantic_fields}) != len(self.semantic_fields):
            raise ValueError('METADATA_SOURCE_FIELD_DUPLICATE')
        if len(self.collection_path) > 16:
            raise ValueError('METADATA_SOURCE_PATH_DEPTH_EXCEEDED')
        return self


class MetadataContextField(FrozenContract):
    ancestor_levels: int = Field(ge=1,le=16)
    source_path: tuple[Ref,...] = Field(min_length=1,max_length=8)
    purpose: Literal['owner_label','owner_description','scope_condition','scope_exception']
    required: bool = True

    @model_validator(mode='after')
    def exact_path(self):
        if any(key in {'*','.','..'} for key in self.source_path):
            raise ValueError('METADATA_CONTEXT_PATH_MUST_BE_EXACT')
        return self


class RecordSourceProfileV2(RecordSourceProfile):
    profile_version: Literal['boi/record-field-metadata-source@0.2.0']
    context_fields: tuple[MetadataContextField,...] = Field(min_length=1,max_length=16)

    @model_validator(mode='after')
    def bounded_context(self):
        keys=[(field.ancestor_levels,field.source_path) for field in self.context_fields]
        if len(set(keys))!=len(keys):raise ValueError('METADATA_CONTEXT_FIELD_DUPLICATE')
        if any(field.ancestor_levels>len(self.collection_path) for field in self.context_fields):
            raise ValueError('METADATA_CONTEXT_ANCESTOR_OUTSIDE_SOURCE')
        return self


class AdditionalRecordCollection(FrozenContract):
    """Another explicit source array, preserving its own record and field paths."""
    group_id: Ref
    collection_path: tuple[Ref,...] = Field(min_length=1,max_length=16)
    identity_key: Ref
    semantic_fields: tuple[MetadataField,...] = Field(min_length=1,max_length=16)
    context_fields: tuple[MetadataContextField,...] = Field(default=(),max_length=16)

    @model_validator(mode='after')
    def exact_fields(self):
        if (len({field.source_key for field in self.semantic_fields})!=len(self.semantic_fields)
            or len({(field.ancestor_levels,field.source_path) for field in self.context_fields})
                !=len(self.context_fields)
            or any(field.ancestor_levels>len(self.collection_path)
                for field in self.context_fields)):
            raise ValueError('METADATA_ADDITIONAL_COLLECTION_INVALID')
        return self


class RecordSourceProfileV3(RecordSourceProfile):
    profile_version: Literal['boi/record-field-metadata-source@0.3.0']
    context_fields: tuple[MetadataContextField,...] = Field(default=(),max_length=16)
    additional_record_collections: tuple[AdditionalRecordCollection,...] = Field(
        min_length=1,max_length=8)

    @model_validator(mode='after')
    def distinct_collections(self):
        groups=self.additional_record_collections
        if (len({item.group_id for item in groups})!=len(groups)
            or len({self.collection_path,*(item.collection_path for item in groups)})!=len(groups)+1
            or any(field.ancestor_levels>len(self.collection_path)
                for field in self.context_fields)):
            raise ValueError('METADATA_COLLECTION_GROUP_AMBIGUOUS')
        return self


RecordSourceProfileContract=Annotated[
    RecordSourceProfile | RecordSourceProfileV2 | RecordSourceProfileV3,
    Field(discriminator='profile_version')]


def parse_record_source_profile(value):
    if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
    return TypeAdapter(RecordSourceProfileContract).validate_python(value)


def _selected_context(parsed,pointer,fields):
    result=[]
    for field in fields:
        path=(*pointer[:-field.ancestor_levels],*field.source_path)
        value=parsed
        try:
            for key in path:value=value[key]
        except (KeyError,IndexError,TypeError):
            if field.required:raise ValueError('METADATA_CONTEXT_FIELD_REQUIRED') from None
            continue
        if not isinstance(value,str):raise ValueError('METADATA_CONTEXT_FIELD_MUST_BE_TEXT')
        if field.required and not value.strip():raise ValueError('METADATA_CONTEXT_FIELD_REQUIRED')
        result.append((field,value,path))
    return result


@dataclass(frozen=True)
class RecordFieldIntake:
    record: SourceRecordRevision
    evidence: tuple[FieldEvidenceRecord, ...]
    semantic_fields: tuple[dict, ...]
    semantic_input_digest: str
    source_profile_digest: str
    parser_code_digest: str


@dataclass(frozen=True)
class RecordFieldAttention:
    artifact_ref: str
    snapshot_digest: str
    record_locator: str
    record_identity_digest: str | None
    reason_code: str
    status: str = 'ATTENTION_REQUIRED'


def _pointer(parts):
    return '/'+ '/'.join(str(part).replace('~','~0').replace('/','~1') for part in parts)


def _walk(value, selectors, prefix=()):
    if not selectors:
        yield prefix,value
        return
    head,*tail=selectors
    if head=='*':
        if not isinstance(value,list): raise ValueError('METADATA_COLLECTION_NOT_ARRAY')
        for index,child in enumerate(value):
            yield from _walk(child,tail,(*prefix,index))
    else:
        if not isinstance(value,dict) or head not in value: raise ValueError('METADATA_COLLECTION_PATH_MISSING')
        yield from _walk(value[head],tail,(*prefix,head))


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('METADATA_DUPLICATE_JSON_KEY')
        result[key]=value
    return result


class _MetadataYamlLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node):
    pairs=[]
    for key,value in node.value:
        pairs.append((loader.construct_object(key,deep=True),loader.construct_object(value,deep=True)))
    return _unique_object(pairs)


_MetadataYamlLoader.add_constructor('tag:yaml.org,2002:map',_yaml_mapping)
# Preserve source timestamps as written; no implicit timezone/history inference.
_MetadataYamlLoader.add_constructor('tag:yaml.org,2002:timestamp',lambda loader,node:loader.construct_scalar(node))


def extract_record_fields(*, source_bytes: bytes, artifact_ref: str, artifact_digest: str,
                          profile: RecordSourceProfile, captured_at: datetime):
    """Yield per-record proposals; original bytes remain with intake's artifact.

    Only explicitly declared textual descriptive metadata enters semantic_fields.
    Physical identifiers/operational values remain in the source artifact, not
    model input. Field values are parsed representations, never claimed raw byte
    spans; replayable JSON pointers and parser transformation digests preserve that.
    """
    profile = parse_record_source_profile(profile)
    contextual=isinstance(profile,(RecordSourceProfileV2,RecordSourceProfileV3))
    if bytes_digest(source_bytes)!=artifact_digest: raise ValueError('METADATA_SOURCE_DIGEST_MISMATCH')
    parsed=(json.loads(source_bytes,object_pairs_hook=_unique_object) if profile.format=='json'
            else yaml.load(source_bytes,Loader=_MetadataYamlLoader))
    profile_digest=semantic_digest(profile)
    code_digest=semantic_digest({'code':bytes_digest(Path(__file__).read_bytes()),
                                'python':sys.version,'pyyaml':yaml.__version__})
    transform_version=('3' if isinstance(profile,RecordSourceProfileV3)
        else '2' if contextual else '1')
    transform=RevisionRef(ref='transform:structured-field-extraction@'+transform_version,
        revision_digest=code_digest)
    if len({field.source_key for field in profile.semantic_fields})!=len(profile.semantic_fields):
        raise ValueError('METADATA_SOURCE_FIELD_DUPLICATE')
    groups=[(None,profile.collection_path,profile.identity_key,profile.semantic_fields,
        getattr(profile,'context_fields',()))]
    if isinstance(profile,RecordSourceProfileV3):
        groups.extend((group.group_id,group.collection_path,group.identity_key,
            group.semantic_fields,group.context_fields)
            for group in profile.additional_record_collections)
    rows=tuple((group_id,identity_key,semantic_fields,context_fields,pointer,row)
        for group_id,path,identity_key,semantic_fields,context_fields in groups
        for pointer,row in _walk(parsed,path))
    def record_key(group_id,key):
        return key if group_id is None else 'group:'+group_id+':'+key
    identities=Counter(record_key(group_id,row[identity_key])
        for group_id,identity_key,_,_,_,row in rows
        if isinstance(row,dict) and isinstance(row.get(identity_key),str))
    def attention(pointer,reason,identity=None):
        return RecordFieldAttention(artifact_ref,artifact_digest,_pointer(pointer),identity,reason)
    for group_id,identity_key,semantic_fields,context_fields,pointer,row in rows:
        if not isinstance(row,dict):
            yield attention(pointer,'METADATA_RECORD_NOT_OBJECT');continue
        key=row.get(identity_key)
        if not isinstance(key,str) or not key.strip():
            yield attention(pointer,'METADATA_RECORD_IDENTITY_REQUIRED');continue
        selected_key=record_key(group_id,key)
        if identities[selected_key]!=1:
            yield attention(pointer,'METADATA_RECORD_IDENTITY_COLLISION');continue
        invalid_field=next((field for field in semantic_fields
                            if field.source_key in row and not isinstance(row[field.source_key],str)),None)
        if invalid_field is not None:
            yield attention(pointer,'METADATA_DESCRIPTIVE_FIELD_MUST_BE_TEXT');continue
        if not any(field.source_key in row for field in semantic_fields):
            yield attention(pointer,'METADATA_SEMANTIC_FIELD_MISSING');continue
        try:context=_selected_context(parsed,pointer,context_fields)
        except ValueError as error:
            yield attention(pointer,str(error));continue
        revision_material=({'record':row,'record_group':group_id,
            'context':[{'selector':field.model_dump(mode='json'),'value':value}
                for field,value,_ in context]} if isinstance(profile,RecordSourceProfileV3)
            else {'record':row,'context':[{'selector':field.model_dump(mode='json'),'value':value}
                for field,value,_ in context]} if contextual else row)
        try:
            record=SourceRecordRevision(source_system=profile.source_system,dataset=profile.dataset,
                namespace=profile.namespace,record_key=selected_key,
                source_revision_digest=semantic_digest(revision_material),
                snapshot_digest=artifact_digest,artifact_ref=artifact_ref,artifact_digest=artifact_digest,
                captured_at=captured_at,effective_from=row.get(profile.effective_from_key) if profile.effective_from_key else None,
                effective_until=row.get(profile.effective_until_key) if profile.effective_until_key else None,
                history_coverage='current_snapshot_only')
        except (ValueError,TypeError):
            yield attention(pointer,'METADATA_RECORD_REVISION_OR_TIME_INVALID');continue
        evidence=[];meaning=[]
        selected=[(field.purpose,row[field.source_key],(*pointer,field.source_key))
            for field in semantic_fields if field.source_key in row]
        selected.extend((field.purpose,value,path) for field,value,path in context)
        for purpose,value,path in selected:
            content_digest=bytes_digest(value.encode('utf-8'))
            locator=_pointer(path)
            span_digest=semantic_digest({'record_identity_digest':record.identity_digest,
                'source_revision_digest':record.source_revision_digest,'snapshot_digest':record.snapshot_digest,
                'field_pointer':locator,'content_digest':content_digest,'parser_code_digest':code_digest})
            span=FieldEvidenceRecord(span_ref='field-span:'+span_digest,span_digest=span_digest,
                content_digest=content_digest,record_identity_digest=record.identity_digest,
                source_revision_digest=record.source_revision_digest,snapshot_digest=artifact_digest,
                field_pointer=locator,representation='extracted',transformation_refs=(transform,))
            evidence.append(span)
            meaning.append({'purpose':purpose,'text':value,'content_digest':content_digest})
        # Same extraction may be reused across identities; evidence/binding are
        # always separate. This digest alone is NOT a model cache key: the service
        # must additionally bind principal/policy/definitions/model/prompt/contract.
        yield RecordFieldIntake(record,tuple(evidence),tuple(meaning),
            semantic_digest({'source_profile_digest':profile_digest,'meaning':meaning}),
            profile_digest,code_digest)
