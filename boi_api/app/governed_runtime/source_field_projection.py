"""Structural field evidence without requiring a domain mapping from the user.

Original bytes stay in the existing source object store. Projections carry exact
JSON pointers or CSV row/column locators and a pinned parser transformation.
They preserve values and absence, never infer meaning, units, identity or policy.
"""
from __future__ import annotations

import csv
from .diagnostic_timing import stage_timing
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path
import sys

import yaml

from .ledger import RecordKind
from .record_field_metadata_intake import _MetadataYamlLoader, _unique_object
from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest
from .source_field_value import ProjectedField, _pointer


def _value_field(value, path, parent):
    state = 'null' if value is None else 'empty' if value == '' else 'present'
    if value is None:
        kind, text = 'null', 'null'
    elif isinstance(value, bool):
        kind, text = 'boolean', 'true' if value else 'false'
    elif isinstance(value, (int, Decimal, float)):
        kind, text = 'number', str(value)
        if not Decimal(text).is_finite():
            raise ValueError('SOURCE_PROJECTION_NONFINITE_NUMBER')
    elif isinstance(value, str):
        kind, text = 'string', value
    elif value == {} or value == []:
        kind, text = ('object', '{}') if isinstance(value, dict) else ('array', '[]')
    else:
        raise ValueError('SOURCE_PROJECTION_UNSUPPORTED_VALUE')
    return ProjectedField(_pointer(path), _pointer(parent), state, kind, text)


def _walk_fields(value, path=(), parent=(), ancestors=()):
    if isinstance(value, (dict, list)) and value:
        # YAML aliases may share values, but recursive aliases are not a tree.
        if id(value) in ancestors:
            raise ValueError('SOURCE_PROJECTION_RECURSIVE_CONTAINER')
        ancestors = (*ancestors, id(value))
        if isinstance(value, dict):
            if any(not isinstance(k, str) for k in value):
                raise ValueError('SOURCE_PROJECTION_STRING_KEYS_REQUIRED')
            for key, child in value.items():
                yield from _walk_fields(child, (*path, key), path, ancestors)
        else:
            # Absence is only relative to observed sibling record keys. It is
            # not a domain-required-field conclusion or a fabricated field span.
            columns = sorted({key for row in value if isinstance(row, dict) for key in row}, key=str)
            for index, child in enumerate(value):
                record = (*path, index)
                yield from _walk_fields(child, record, path, ancestors)
                if isinstance(child, dict):
                    for key in columns:
                        if key not in child:
                            yield ProjectedField(_pointer((*record, key)), _pointer(record),
                                'absent', 'absent', '', 'container_key_absence')
    else:
        yield _value_field(value, path, parent)


@stage_timing('source_structural_parse')
def project_fields(raw: bytes, media_type: str) -> tuple[ProjectedField, ...]:
    """Parse a source structurally. Unknown formats fail, without LLM fallback."""
    from .spreadsheet_source_projection import XLSX,workbook_fields
    if media_type==XLSX:return workbook_fields(raw)
    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('SOURCE_PROJECTION_UTF8_REQUIRED') from None
    try:
        if media_type == 'application/json':
            def invalid_constant(_):
                raise ValueError('SOURCE_PROJECTION_NONFINITE_NUMBER')
            value = json.loads(text, object_pairs_hook=_unique_object, parse_float=Decimal,
                parse_constant=invalid_constant)
            if isinstance(value,dict) and value.get('contract_version')=='boi/database-source-page@1':
                from .database_source_projection import database_fields
                return database_fields(raw)
            return tuple(_walk_fields(value))
        if media_type == 'application/yaml':
            # Preserve decimal quantities without binary float rounding. Reuse
            # duplicate-key and timestamp preservation from the existing parser.
            class ProjectionYamlLoader(_MetadataYamlLoader):
                pass
            ProjectionYamlLoader.add_constructor('tag:yaml.org,2002:float',
                lambda loader, node: Decimal(loader.construct_scalar(node).replace('_', '')))
            return tuple(_walk_fields(yaml.load(text, Loader=ProjectionYamlLoader)))
        if media_type == 'text/csv':
            reader = csv.reader(io.StringIO(text, newline=''), strict=True)
            header = next(reader, None)
            if not header or len(header) != len(set(header)) or any(not key for key in header):
                raise ValueError('SOURCE_PROJECTION_CSV_HEADER_INVALID')
            fields = []
            for index, row in enumerate(reader, start=1):
                if len(row) > len(header):
                    raise ValueError('SOURCE_PROJECTION_CSV_EXTRA_CELLS')
                for column, key in enumerate(header):
                    present = column < len(row)
                    value = row[column] if present else ''
                    fields.append(ProjectedField(_pointer(('rows', index, key)), _pointer(('rows', index)),
                        ('empty' if value == '' else 'present') if present else 'absent',
                        'string' if present else 'absent', value,
                        'field_present' if present else 'row_cell_absence'))
            return tuple(fields)
        if media_type in {'text/plain', 'application/sql', 'text/html'}:
            # HTML is retained as source encoding, not parsed into a DOM or
            # rendered. Quotes and offsets include the original tags/entities;
            # no scripts, links, subresources or implied text are evaluated.
            return (ProjectedField('', '', 'empty' if text == '' else 'present', 'string', text),)
    except (ValueError, TypeError, RecursionError, InvalidOperation, yaml.YAMLError, csv.Error) as exc:
        # Parser diagnostics can include private snippets. Expose codes only.
        code = str(exc)
        if not code.startswith('SOURCE_PROJECTION_') or len(code) > 100 or '\n' in code:
            code = 'SOURCE_PROJECTION_PARSE_FAILED'
        raise ValueError(code) from None
    raise ValueError('SOURCE_PROJECTION_MEDIA_TYPE_UNSUPPORTED')


class SourceFieldProjectionService:
    """Shared source service: preserve and read fields, never orchestrate tasks."""
    CONTRACT = 'boi/source-field-projection@1'

    def __init__(self, source_intake):
        self.intake = source_intake

    def _authorize(self, authorization, reference, *, model_input=False):
        self.intake._policy(authorization)
        if 'derive' not in authorization.allowed_uses:
            raise ValueError('SOURCE_DERIVE_NOT_AUTHORIZED')
        if model_input and 'model_input' not in authorization.allowed_uses:
            raise ValueError('SOURCE_MODEL_INPUT_NOT_AUTHORIZED')
        raw = self.intake.resolve_bytes(authorization=authorization, reference=reference)
        artifact = self.intake.ledger.read(reference['artifact_ref'])
        return raw, artifact

    def project(self, *, authorization, reference, max_fields=None):
        # The manifest exposes field locators and values' structural metadata to
        # external consumers; it therefore uses the same model-input boundary.
        raw, artifact = self._authorize(authorization, reference, model_input=True)
        media = artifact.payload['media_type']
        fields = project_fields(raw, media)
        if max_fields is not None and (type(max_fields) is not int or not 1 <= max_fields <= 100000
                or len(fields) > max_fields):
            raise ValueError('SOURCE_PROJECTION_FIELD_COUNT_LIMIT')
        parser_digest = semantic_digest({'code': byte_digest(Path(__file__).read_bytes()),
            'shared_parser_code': byte_digest(Path(sys.modules[_MetadataYamlLoader.__module__].__file__).read_bytes()),
            'python': sys.version, 'pyyaml': yaml.__version__, 'media_type': media,
            **({'workbook_parser_code':byte_digest(Path(__file__).with_name('spreadsheet_source_projection.py').read_bytes())}
                if media=='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' else {})})
        common = {'contract_version': self.CONTRACT, 'artifact_ref': artifact.record_id,
            'source_revision_digest': reference['digest'], 'snapshot_digest': reference['digest'],
            'source_role': reference['role'], 'policy_digest': authorization.policy_digest,
            'employee_id': authorization.principal, 'rights_record_ref': artifact.payload['rights_record_ref'],
            'parser_digest': parser_digest, 'representation': 'parsed_projection',
            'offset_basis': 'decoded_unicode_codepoints', 'status': 'PROVISIONAL',
            'canonical_projection_eligible': False, 'semantic_status': 'not_evaluated'}
        payloads = []
        for field in fields:
            object_ref = self.intake.objects.put(field.text.encode('utf-8'))
            payloads.append({**common, 'field_locator': field.locator, 'record_locator': field.record_locator,
                'identity_basis': 'locator_within_snapshot', 'field_state': field.state,
                'value_kind': field.value_kind, 'presence_basis': field.presence_basis,
                'field_object_ref': object_ref, 'content_digest': byte_digest(field.text.encode('utf-8')),
                'character_count': len(field.text),
                **({'structural_metadata':field.structural_metadata} if field.structural_metadata is not None else {})})
        spans = []
        for start in range(0, len(payloads), 100):
            spans.extend(self.intake.ledger.append_batch(RecordKind.EVIDENCE_SPAN, payloads[start:start+100],
                authority='evidence_service', occurred_at=artifact.occurred_at))
        manifest = {**common, 'field_count': len(spans), 'fields': [
            {'span_ref': span.record_id, **{key: span.payload[key] for key in (
                'field_locator', 'record_locator', 'field_state', 'value_kind', 'presence_basis',
                'content_digest', 'character_count')},
                **({'structural_metadata':span.payload['structural_metadata']} if 'structural_metadata' in span.payload else {})} for span in spans],
            'source_fidelity': 'not_evaluated', 'task_readiness': 'not_evaluated'}
        record = self.intake.ledger.append(RecordKind.RUN, manifest,
            authority='migration_service', occurred_at=artifact.occurred_at)
        return {'manifest_ref': record.record_id, 'manifest_digest': semantic_digest(manifest), **manifest}

    def read_field(self, *, authorization, reference, span_ref: str, offset: int = 0, limit: int = 4096):
        _, artifact = self._authorize(authorization, reference, model_input=True)
        return self._read_authorized_field(authorization=authorization,reference=reference,
            artifact=artifact,span_ref=span_ref,offset=offset,limit=limit)

    def read_batch(self, *, authorization, request):
        from .source_field_read_contract import SourceFieldBatchReadRequest
        request = SourceFieldBatchReadRequest.model_validate(request)
        reference = request.reference.model_dump(mode='json')
        _, artifact = self._authorize(authorization, reference, model_input=True)
        remaining, pages, pending = request.max_characters, [], []
        for field in request.fields:
            if not remaining:
                pending.append(field.model_dump(mode='json'))
                continue
            page = self._read_authorized_field(authorization=authorization,
                reference=reference, artifact=artifact, span_ref=field.span_ref,
                offset=field.offset, limit=min(field.limit, remaining))
            pages.append(page)
            remaining -= len(page['text'])
            if page['next_offset'] is not None:
                pending.append({**field.model_dump(mode='json'), 'offset': page['next_offset']})
        return {'contract_version': 'boi/source-field-batch@1', 'fields': pages,
            'returned_character_count': request.max_characters - remaining,
            'requested_field_count': len(request.fields),
            'continuation': {'reference': reference, 'fields': pending,
                'max_characters': request.max_characters} if pending else None,
            'offset_basis': 'decoded_unicode_codepoints',
            'semantic_status': 'not_evaluated', 'canonical_projection_eligible': False}

    def _read_authorized_field(self, *, authorization,reference,artifact,span_ref,offset,limit):
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 8192:
            raise ValueError('SOURCE_FIELD_PAGE_RANGE_INVALID')
        span = self.intake.ledger.read(span_ref)
        value = span.payload
        if (span.kind != RecordKind.EVIDENCE_SPAN or value.get('contract_version') not in (self.CONTRACT, 'boi/source-image-transcription@1')
                or value.get('artifact_ref') != artifact.record_id
                or value.get('policy_digest') != authorization.policy_digest
                or value.get('employee_id') != authorization.principal
                or value.get('rights_record_ref') != artifact.payload['rights_record_ref']
                or value.get('source_revision_digest') != reference['digest']):
            raise ValueError('SOURCE_FIELD_ACCESS_OR_BINDING_DENIED')
        raw = self.intake.objects.get(value['field_object_ref'])
        if byte_digest(raw) != value['content_digest']:
            raise ValueError('SOURCE_FIELD_CONTENT_DRIFT')
        text = raw.decode('utf-8')
        if len(text) != value['character_count'] or offset > len(text):
            raise ValueError('SOURCE_FIELD_PAGE_RANGE_INVALID')
        end = min(len(text), offset + limit)
        return {**value, 'span_ref': span_ref, 'offset': offset, 'end': end,
            'text': text[offset:end], 'next_offset': end if end < len(text) else None,
            'complete_field': offset == 0 and end == len(text)}

    def restore_projection_from_span(self,*,authorization,reference,span_ref):
        """Recover an existing complete parser projection from a recorded field.

        No ledger scan, new span or reconstructed evidence is published. Every
        derived identifier must already exist, and restore_fields checks the
        complete registered manifest, original bytes and present access.
        """
        from .ledger import sha256_id
        raw,artifact=self._authorize(authorization,reference,model_input=True)
        anchor=self._read_authorized_field(authorization=authorization,reference=reference,
            artifact=artifact,span_ref=span_ref,offset=0,limit=1)
        keys=('contract_version','artifact_ref','source_revision_digest','snapshot_digest','source_role',
            'policy_digest','employee_id','rights_record_ref','parser_digest','representation','offset_basis',
            'status','canonical_projection_eligible','semantic_status')
        common={key:anchor[key] for key in keys};metadata=[]
        for field in project_fields(raw,artifact.payload['media_type']):
            digest=byte_digest(field.text.encode('utf-8'))
            payload={**common,'field_locator':field.locator,'record_locator':field.record_locator,
                'identity_basis':'locator_within_snapshot','field_state':field.state,
                'value_kind':field.value_kind,'presence_basis':field.presence_basis,
                'field_object_ref':digest,'content_digest':digest,'character_count':len(field.text),
                **({'structural_metadata':field.structural_metadata} if field.structural_metadata is not None else {})}
            ref=sha256_id(RecordKind.EVIDENCE_SPAN,{'schema':self.intake.ledger.SCHEMA,
                'kind':RecordKind.EVIDENCE_SPAN.value,'authority':'evidence_service',
                'occurred_at':artifact.occurred_at,'payload':payload})
            registered=self.intake.ledger.read(ref)
            if registered.payload!=payload:raise ValueError('SOURCE_RESTORE_FIELD_BINDING_MISMATCH')
            metadata.append({'span_ref':ref,**{key:payload[key] for key in (
                'field_locator','record_locator','field_state','value_kind','presence_basis','content_digest','character_count')},
                **({'structural_metadata':field.structural_metadata} if field.structural_metadata is not None else {})})
        return self.restore_fields(authorization=authorization,reference=reference,field_metadata=metadata)

    def restore_manifest(self,*,authorization,reference,manifest_ref):
        self._authorize(authorization,reference,model_input=True)
        record=self.intake.ledger.read(manifest_ref)
        if (record.kind!=RecordKind.RUN or record.payload.get('contract_version')!=self.CONTRACT
                or record.payload.get('artifact_ref')!=reference['artifact_ref']):
            raise ValueError('SOURCE_RESTORE_MANIFEST_MISMATCH')
        restored=self.restore_fields(authorization=authorization,reference=reference,
            field_metadata=record.payload['fields'])
        if restored['manifest']['manifest_ref']!=manifest_ref:
            raise ValueError('SOURCE_RESTORE_MANIFEST_MISMATCH')
        return restored

    def select_manifest_fields(self, *, authorization, reference, manifest_ref, span_refs, offset=None):
        """Read exact published locations without reparsing an unchanged source.

        This is navigation over an immutable projection, not validation that a
        newer parser produces the same inventory (restore_manifest does that).
        Current source rights and original bytes remain checked on every read.
        """
        _, artifact = self._authorize(authorization, reference, model_input=True)
        record = self.intake.ledger.read(manifest_ref)
        value = record.payload
        if (record.kind != RecordKind.RUN or value.get('contract_version') not in (self.CONTRACT, 'boi/source-image-transcription@1')
                or value.get('artifact_ref') != artifact.record_id
                or value.get('source_revision_digest') != reference['digest']
                or value.get('employee_id') != authorization.principal
                or value.get('policy_digest') != authorization.policy_digest
                or value.get('rights_record_ref') != artifact.payload['rights_record_ref']):
            raise ValueError('SOURCE_SELECTION_MANIFEST_DENIED')
        indexed = {field['span_ref']: field for field in value['fields']}
        wanted = list(dict.fromkeys(span_refs))
        next_offset = None
        if offset is not None:
            if type(offset) is not int or offset < 0 or offset >= len(indexed):
                raise ValueError('SOURCE_SELECTION_PAGE_RANGE_INVALID')
            page = list(indexed)[offset:offset+100]
            wanted = list(dict.fromkeys([*wanted, *page]))
            next_offset = offset+100 if offset+100 < len(indexed) else None
        if any(ref not in indexed for ref in wanted):
            raise ValueError('SOURCE_SELECTION_FIELD_NOT_IN_MANIFEST')
        wanted_set=set(wanted)
        selected_records={indexed[ref]['record_locator'] for ref in wanted}
        record_fields={locator:[] for locator in selected_records}
        for ref,field in indexed.items():
            if field['record_locator'] in record_fields:record_fields[field['record_locator']].append(ref)
        return {'manifest_ref': manifest_ref, 'field_count': value['field_count'],
            'fields': [indexed[ref] for ref in wanted], 'offset':offset, 'next_offset':next_offset,
            'record_field_refs':record_fields,
            'field_offsets': {ref:i for i,ref in enumerate(indexed) if ref in wanted_set}}

    def read_selected_fields(self, *, authorization, reference, manifest_ref, span_refs, required_records=()):
        """Read a complete selected dependency set with one source authorization.

        The selection envelope explicitly identifies the complete backing manifest;
        its small field inventory never claims to be the entire original source.
        Optional required_records contain exact (locator, field refs) assertions;
        validate them against this same manifest before reading field contents.
        """
        selected=self.select_manifest_fields(authorization=authorization,reference=reference,
            manifest_ref=manifest_ref,span_refs=span_refs)
        # Record completeness and field delivery share this authenticated
        # manifest selection. These are expected source locations, not caller
        # supplied field contents or authorization decisions.
        for locator, own in required_records:
            if (not own or len(own) != len(set(own))
                    or set(own) != set(selected['record_field_refs'].get(locator, ()))
                    or not set(own).issubset(span_refs)):
                raise ValueError('SOURCE_RECORD_INVENTORY_INCOMPLETE')
        artifact=self.intake.ledger.read(reference['artifact_ref'])
        fields=[]
        for metadata in selected['fields']:
            offset=0;pieces=[]
            while True:
                page=self._read_authorized_field(authorization=authorization,reference=reference,
                    artifact=artifact,span_ref=metadata['span_ref'],offset=offset,limit=8192)
                if any(page.get(key)!=value for key,value in metadata.items()):
                    raise ValueError('SOURCE_SELECTION_FIELD_BINDING_MISMATCH')
                pieces.append(page['text']);offset=page['next_offset']
                if offset is None:break
            fields.append({**metadata,'text':''.join(pieces)})
        manifest={'contract_version':'boi/source-field-selection@1',
            'source_revision_digest':reference['digest'],'employee_id':authorization.principal,
            'policy_digest':authorization.policy_digest,'full_manifest_ref':manifest_ref,
            'projection_scope':'selected_source_fields','total_field_count':selected['field_count'],
            'field_count':len(fields),'fields':selected['fields']}
        return {'source':reference,'manifest':manifest,'fields':fields}

    def restore_fields(self,*,authorization,reference,field_metadata):
        """Read a recorded complete projection without minting new source spans.

        Current rights, original bytes, every immutable span and the registered
        manifest remain checked. A parser upgrade must preserve the complete
        field inventory and values before an earlier projection can be reused.
        """
        from .ledger import sha256_id
        raw,artifact=self._authorize(authorization,reference,model_input=True)
        parsed=project_fields(raw,artifact.payload['media_type'])
        expected={f.locator:f for f in parsed}
        if (not field_metadata or len(field_metadata)!=len(expected)
                or len({f['field_locator'] for f in field_metadata})!=len(expected)):
            raise ValueError('SOURCE_RESTORE_INVENTORY_MISMATCH')
        fields=[];common=None
        keys=('contract_version','artifact_ref','source_revision_digest','snapshot_digest','source_role',
            'policy_digest','employee_id','rights_record_ref','parser_digest','representation','offset_basis',
            'status','canonical_projection_eligible','semantic_status')
        for metadata in field_metadata:
            offset=0;pieces=[]
            while True:
                page=self._read_authorized_field(authorization=authorization,reference=reference,artifact=artifact,
                    span_ref=metadata['span_ref'],offset=offset,limit=8192)
                if any(page.get(k)!=v for k,v in metadata.items()):
                    raise ValueError('SOURCE_RESTORE_FIELD_BINDING_MISMATCH')
                pieces.append(page['text']);offset=page['next_offset']
                if offset is None:break
            text=''.join(pieces);field=expected.get(metadata['field_locator'])
            if (field is None or text!=field.text or metadata['record_locator']!=field.record_locator
                    or metadata['field_state']!=field.state or metadata['value_kind']!=field.value_kind
                    or metadata['presence_basis']!=field.presence_basis
                    or metadata.get('structural_metadata')!=field.structural_metadata):
                raise ValueError('SOURCE_RESTORE_PARSER_RESULT_CHANGED')
            envelope={k:page[k] for k in keys}
            if common is not None and envelope!=common:raise ValueError('SOURCE_RESTORE_MIXED_PROJECTION')
            common=envelope;fields.append({**metadata,'text':text})
        manifest={**common,'field_count':len(field_metadata),'fields':field_metadata,
            'source_fidelity':'not_evaluated','task_readiness':'not_evaluated'}
        ref=sha256_id(RecordKind.RUN,{'schema':self.intake.ledger.SCHEMA,'kind':RecordKind.RUN.value,
            'authority':'migration_service','occurred_at':artifact.occurred_at,'payload':manifest})
        # Existence and exact immutable body prove this is a previously published
        # complete projection, not an arbitrary subset supplied by an answer.
        registered=self.intake.ledger.read(ref)
        if registered.payload!=manifest:raise ValueError('SOURCE_RESTORE_MANIFEST_MISMATCH')
        return {'source':reference,'manifest':{'manifest_ref':ref,'manifest_digest':semantic_digest(manifest),**manifest},
            'fields':fields}
