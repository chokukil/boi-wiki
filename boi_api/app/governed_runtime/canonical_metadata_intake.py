"""Canonical field evidence over the existing source/ledger and shared projections.

Publication is recoverable across ledger and application-store boundaries. A
returned item has both immutable spans and its exact shared projection receipt.
This service proves preservation/lineage only, never meaning or query readiness.
"""
from dataclasses import asdict, dataclass, replace
from datetime import datetime
import json
import sys
from pathlib import Path
import yaml
from boi_api.app.governed_runtime.ledger import RecordKind
from boi_api.app.governed_runtime.record_field_metadata_intake import (
    RecordSourceProfile, RecordFieldIntake, RecordFieldAttention, extract_record_fields, parse_record_source_profile,
)
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest, SourceRecordRevision
from boi_api.app.governed_runtime.semantic_binding_validator import FieldEvidenceRecord
from boi_api.app.v2.atomic_store_contract import AtomicWrite


@dataclass(frozen=True)
class PublishedMetadataRecord:
    intake: RecordFieldIntake | RecordFieldAttention
    receipt_ref: str


class CanonicalMetadataIntake:
    CONTRACT = 'boi/canonical-record-field-intake@0.1.0'

    def __init__(self, source_intake):
        self.source_intake = source_intake
        self.store, self.ledger = source_intake.store, source_intake.ledger

    def extract(self, *, authorization, reference, profile, profile_digest):
        """Server resolves profile + pin; a caller-proposed profile is not authority.

        Batches have at most 100 ledger spans and 100 input records. These are
        publication batches, not candidate review shards or a corpus size limit.
        Semantic text is returned only to the trusted service, not saved in a
        tool response/audit/receipt. Pi separately requires model_input rights.
        """
        self.source_intake._policy(authorization)
        if 'derive' not in authorization.allowed_uses:
            raise ValueError('SOURCE_DERIVE_NOT_AUTHORIZED')
        profile = parse_record_source_profile(profile)
        if semantic_digest(profile) != profile_digest:
            raise ValueError('SOURCE_PROFILE_DIGEST_MISMATCH')
        raw = self.source_intake.resolve_bytes(authorization=authorization, reference=reference)
        artifact = self.ledger.read(reference['artifact_ref'])
        if artifact.payload['role'] not in {'corporate_metadata','schema'}:
            raise ValueError('METADATA_SOURCE_ROLE_NOT_ALLOWED')
        from boi_api.app.governed_runtime import record_field_metadata_intake as parser_module
        from boi_api.app.governed_runtime.source_envelope import byte_digest
        parser_digest=semantic_digest({'code':byte_digest(Path(parser_module.__file__).read_bytes()),
            'python':sys.version,'pyyaml':yaml.__version__})
        closure={ 'contract_version':self.CONTRACT, 'artifact_ref':artifact.record_id,
            'profile_digest':profile_digest, 'parser_code_digest':parser_digest,
            'publisher_code_digest':byte_digest(Path(__file__).read_bytes()),
            'principal':authorization.principal, 'policy_digest':authorization.policy_digest}
        key='metadata-intake-index:'+semantic_digest(closure)
        cached=self.store.get('bulk_migration_checkpoints',key)
        if cached is not None:
            yield from self._replay(cached, closure, authorization, artifact)
            return
        page_refs=[]; total_count=0
        def remember(published):
            nonlocal total_count
            page=[]
            for result in published:
                stored=self.store.get('bulk_migration_receipts',result.receipt_ref)
                material={k:v for k,v in (stored or {}).items() if k!='updated_at'}
                if 'metadata-intake-receipt:'+semantic_digest(material)!=result.receipt_ref:
                    raise ValueError('METADATA_EVIDENCE_PROJECTION_DRIFT')
                page.append({'ref':result.receipt_ref,'receipt':material})
            encoded=json.dumps(page,ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode()
            page_refs.append(self.source_intake.objects.put(encoded))
            total_count+=len(page)
            return published
        pending = []; span_count = 0
        for item in extract_record_fields(source_bytes=raw, artifact_ref=artifact.record_id,
                artifact_digest=reference['digest'], profile=profile,
                captured_at=datetime.fromisoformat(artifact.occurred_at)):
            count = len(item.evidence) if isinstance(item, RecordFieldIntake) else 0
            if pending and (len(pending) >= 100 or span_count + count > 100):
                yield from remember(self._publish(pending, authorization, artifact, profile_digest))
                pending = []; span_count = 0
            pending.append(item); span_count += count
        if pending:
            yield from remember(self._publish(pending, authorization, artifact, profile_digest))
        execution=self.ledger.append(RecordKind.RUN,{
            'contract_version':'boi/canonical-field-preservation-run@0.1.0',
            'input_closure':closure,'record_count':total_count,'page_refs':page_refs,
            'status':'PRESERVED','semantic_status':'not_run','query_readiness':'not_run',
            'production_changed':False,'active_transition':False},
            authority='migration_service',occurred_at=artifact.occurred_at)
        self._save_exact([('bulk_migration_checkpoints',key,{
            'employee_id':authorization.principal,'input_closure':closure,'preservation_run_ref':execution.record_id})])

    def _publish(self, items, authorization, artifact, profile_digest):
        payloads = []
        base = {'contract_version':self.CONTRACT, 'employee_id':authorization.principal,
            'artifact_ref':artifact.record_id, 'snapshot_digest':artifact.payload['content_digest'],
            'rights_record_ref':artifact.payload['rights_record_ref'],
            'policy_digest':authorization.policy_digest, 'source_profile_digest':profile_digest,
            'canonical_projection_eligible':False}
        for item in items:
            if not isinstance(item, RecordFieldIntake): continue
            for span, meaning in zip(item.evidence, item.semantic_fields):
                field_object=self.source_intake.objects.put(meaning['text'].encode())
                if field_object != span.content_digest:
                    raise ValueError('METADATA_RECORD_FIELD_CLOSURE_MISMATCH')
                payloads.append({**base, 'source_record':item.record.model_dump(mode='json'),
                    'field_evidence':span.model_dump(mode='json'),
                    'field_purpose':meaning['purpose'],
                    'extracted_field_object_ref':field_object,
                    'semantic_input_digest':item.semantic_input_digest,
                    'parser_code_digest':item.parser_code_digest})
        records = []
        # A source profile may describe over 100 fields on one record. Preserve
        # it without passing a >100 span batch or equating fields with candidates.
        for start in range(0, len(payloads), 100):
            records.extend(self.ledger.append_batch(RecordKind.EVIDENCE_SPAN,
                payloads[start:start+100], authority='evidence_service', occurred_at=artifact.occurred_at))
        cursor = iter(records); writes = []; results = []
        for item in items:
            if isinstance(item, RecordFieldIntake):
                spans = []
                for span in item.evidence:
                    record = next(cursor)
                    canonical_span = span.model_copy(update={'span_ref':record.record_id})
                    spans.append(canonical_span)
                    projection = {**base, 'canonical_evidence_ref':record.record_id,
                        'field_evidence':canonical_span.model_dump(mode='json')}
                    writes.append(('bulk_migration_evidence_spans', record.record_id, projection))
                item = replace(item, evidence=tuple(spans))
                material = {**base, 'source_record':item.record.model_dump(mode='json'),
                    'evidence_refs':[span.span_ref for span in spans],
                    'semantic_input_digest':item.semantic_input_digest,
                    'parser_code_digest':item.parser_code_digest,
                    'status':'PRESERVED', 'semantic_status':'not_run', 'query_readiness':'not_run'}
            else:
                material = {**base, 'attention':asdict(item), 'status':'ATTENTION_REQUIRED',
                    'semantic_status':'not_run', 'query_readiness':'not_run'}
            receipt_ref = 'metadata-intake-receipt:' + semantic_digest(material)
            writes.append(('bulk_migration_receipts', receipt_ref, material))
            results.append(PublishedMetadataRecord(item, receipt_ref))
        # Bounded atomic projections; a failure never yields an incomplete record.
        # Existing ledger bytes remain immutable and exact retry dedupes them.
        for start in range(0, len(writes), 100):
            self._save_exact(writes[start:start+100])
        return tuple(results)

    def _replay(self, cached, closure, authorization, artifact):
        # A SQL cache pointer cannot manufacture a completed parse or change
        # its ordered coverage. The existing immutable ledger owns that seal.
        expected={'employee_id':authorization.principal,'input_closure':closure,
            'preservation_run_ref':cached.get('preservation_run_ref')}
        if {k:v for k,v in cached.items() if k!='updated_at'} != expected:
            raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')
        run=self.ledger.read(cached['preservation_run_ref'])
        if (run.kind!=RecordKind.RUN or run.payload.get('contract_version')!='boi/canonical-field-preservation-run@0.1.0'
            or run.payload.get('input_closure')!=closure or run.payload.get('status')!='PRESERVED'):
            raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')
        count=0
        for page_ref in run.payload['page_refs']:
            refs=json.loads(self.source_intake.objects.get(page_ref))
            if not isinstance(refs,list) or not 1<=len(refs)<=100:
                raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')
            for entry in refs:
                ref,body=entry['ref'],entry['receipt']
                if (ref!='metadata-intake-receipt:'+semantic_digest(body)
                    or body['employee_id']!=authorization.principal or body['artifact_ref']!=artifact.record_id
                    or body['source_profile_digest']!=closure['profile_digest']):
                    raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')
                self._save_exact([('bulk_migration_receipts',ref,body)])
                if body['status']=='ATTENTION_REQUIRED':
                    item=RecordFieldAttention(**body['attention'])
                else:
                    spans=[];meaning=[]
                    for span_ref in body['evidence_refs']:
                        record=self.ledger.read(span_ref);payload=record.payload
                        if (record.kind!=RecordKind.EVIDENCE_SPAN or payload['artifact_ref']!=artifact.record_id
                            or payload['source_record']!=body['source_record']
                            or payload['source_profile_digest']!=closure['profile_digest']
                            or payload['parser_code_digest']!=closure['parser_code_digest']
                            or payload['semantic_input_digest']!=body['semantic_input_digest']):
                            raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')
                        span=FieldEvidenceRecord.model_validate({**payload['field_evidence'],'span_ref':span_ref})
                        text=self.source_intake.objects.get(payload['extracted_field_object_ref']).decode()
                        if payload['extracted_field_object_ref']!=span.content_digest:
                            raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')
                        spans.append(span);meaning.append({'purpose':payload['field_purpose'],
                            'text':text,'content_digest':span.content_digest})
                        projection={key:value for key,value in payload.items() if key in {
                            'contract_version','employee_id','artifact_ref','snapshot_digest','rights_record_ref',
                            'policy_digest','source_profile_digest','canonical_projection_eligible'}}
                        projection.update(canonical_evidence_ref=span_ref,field_evidence=span.model_dump(mode='json'))
                        self._save_exact([('bulk_migration_evidence_spans',span_ref,projection)])
                    item=RecordFieldIntake(SourceRecordRevision.model_validate(body['source_record']),tuple(spans),
                        tuple(meaning),body['semantic_input_digest'],body['source_profile_digest'],body['parser_code_digest'])
                count+=1
                yield PublishedMetadataRecord(item,ref)
        if count!=run.payload['record_count']:
            raise ValueError('METADATA_INTAKE_CHECKPOINT_DRIFT')

    def _save_exact(self, records):
        for _ in range(3):
            writes = []
            for collection, key, value in records:
                old = self.store.get(collection, key)
                if old is not None and {k:v for k,v in old.items() if k!='updated_at'} != value:
                    raise ValueError('METADATA_EVIDENCE_PROJECTION_DRIFT')
                writes.append(AtomicWrite(collection, key, old, value))
            if self.store.atomic_compare_and_write(writes): return
        raise ValueError('METADATA_EVIDENCE_PROJECTION_RETRY_REQUIRED')

    def resolve_evidence(self, *, authorization, span_ref):
        """Resolve canonical authority, never trust the rebuildable SQL projection."""
        record = self.ledger.read(span_ref)
        if record.kind != RecordKind.EVIDENCE_SPAN or record.payload.get('contract_version') != self.CONTRACT:
            raise ValueError('METADATA_CANONICAL_EVIDENCE_REQUIRED')
        payload = record.payload
        if payload.get('employee_id') != authorization.principal or payload.get('policy_digest') != authorization.policy_digest:
            raise ValueError('METADATA_EVIDENCE_ACCESS_DENIED')
        source = self.ledger.read(payload['artifact_ref'])
        self.source_intake._source(authorization, source.record_id,
            payload['snapshot_digest'], source.payload['role'])
        return FieldEvidenceRecord.model_validate({**payload['field_evidence'], 'span_ref':record.record_id})

    def verify_record(self, *, authorization, record):
        """Validate a record passed between service stages, including mutable text.

        Field evidence proves which extracted string was used, not its meaning.
        Exact source-record/profile/purpose links cannot be changed by a caller.
        """
        from boi_api.app.governed_runtime.source_envelope import byte_digest
        if not isinstance(record, RecordFieldIntake) or not record.evidence:
            raise ValueError('METADATA_CANONICAL_RECORD_REQUIRED')
        if len(record.evidence) != len(record.semantic_fields):
            raise ValueError('METADATA_RECORD_FIELD_CLOSURE_MISMATCH')
        actual_digest=semantic_digest({'source_profile_digest':record.source_profile_digest,
            'meaning':list(record.semantic_fields)})
        if actual_digest != record.semantic_input_digest:
            raise ValueError('METADATA_RECORD_SEMANTIC_INPUT_DRIFT')
        for span, meaning in zip(record.evidence, record.semantic_fields):
            canonical=self.resolve_evidence(authorization=authorization, span_ref=span.span_ref)
            payload=self.ledger.read(span.span_ref).payload
            if (canonical != span or payload['source_record'] != record.record.model_dump(mode='json')
                or payload['source_profile_digest'] != record.source_profile_digest
                or payload['parser_code_digest'] != record.parser_code_digest
                or payload['semantic_input_digest'] != record.semantic_input_digest
                or set(meaning) != {'purpose','text','content_digest'}
                or payload['field_purpose'] != meaning['purpose']
                or not isinstance(meaning['text'], str)
                or byte_digest(meaning['text'].encode()) != span.content_digest
                or meaning['content_digest'] != span.content_digest):
                raise ValueError('METADATA_RECORD_FIELD_CLOSURE_MISMATCH')
        return record

    def authorize_model_input(self, *, authorization, record):
        self.verify_record(authorization=authorization, record=record)
        if 'model_input' not in authorization.allowed_uses:
            raise ValueError('SOURCE_MODEL_INPUT_NOT_AUTHORIZED')
        return True
