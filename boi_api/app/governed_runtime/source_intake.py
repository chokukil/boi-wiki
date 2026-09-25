"""Recoverable intake bridge to the existing canonical bytes/ledger, not a second source SOT."""
from dataclasses import dataclass
from datetime import datetime,timezone
import re
from boi_api.app.governed_runtime.ledger import RecordKind
from boi_api.app.governed_runtime.bulk_migration import _digest
from boi_api.app.v2.atomic_store_contract import AtomicWrite
from boi_api.app.governed_runtime.source_envelope import ArtifactEnvelope,ConnectorEnvelope,InlineEnvelope,byte_digest,parse_envelope


@dataclass(frozen=True)
class IntakeAuthorization:
    """Resolved by authenticated server policy; never part of SourceEnvelope."""
    principal: str
    policy_digest: str
    allowed_uses: tuple[str,...]
    visibility: str = 'private'
    team_id: str | None = None


@dataclass(frozen=True)
class ConnectorSnapshot:
    raw: bytes
    snapshot_digest: str
    selector_manifest_ref: str
    resource_ref: str
    media_type: str


class SourceIntakeService:
    def __init__(self,*,store,ledger,objects,connector_resolver=None,clock=None,current_source_policy=None):
        self.store,self.ledger,self.objects=store,ledger,objects
        self.connector_resolver=connector_resolver
        self.current_source_policy=current_source_policy
        self.clock=clock or (lambda:datetime.now(timezone.utc))
        from .canonical_metadata_intake import CanonicalMetadataIntake
        self.metadata=CanonicalMetadataIntake(self)

    def normalize_input(self, *, authorization, value):
        """Remove intake bodies before the common Agent plan/audit/model path.

        The receipt and projections live in the shared application store. Only
        the original governed ledger/object store owns source identity/bytes.
        """
        envelopes=value.get('source_envelopes')
        if not isinstance(envelopes,list) or not 1<=len(envelopes)<=100:
            raise ValueError('SOURCE_ENVELOPE_BATCH_LIMIT')
        if value.get('source_artifacts'):
            raise ValueError('SOURCE_INPUT_AMBIGUOUS')
        key=value.get('idempotency_key')
        if not isinstance(key,str) or not 0<len(key)<=240:
            raise ValueError('SOURCE_IDEMPOTENCY_KEY_REQUIRED')
        parsed=[parse_envelope(item) for item in envelopes]
        # Validate the complete bounded request before the first source write.
        for item in parsed:
            if isinstance(item,InlineEnvelope):item.source_bytes()
        identities=[]
        for item in parsed:
            identity=item.model_dump(mode='json')
            if isinstance(item,InlineEnvelope):identity['content_digest']=byte_digest(item.source_bytes())
            identities.append(identity)
        batch={'employee_id':authorization.principal,
               'input_fingerprint':_digest({'envelopes':identities,'policy':self._policy(authorization)})}
        batch_key='source-envelope-batch:'+_digest({'principal':authorization.principal,'key':key})
        existing=self.store.get('bulk_migration_idempotency',batch_key)
        if existing is None:
            self.store.atomic_compare_and_write((AtomicWrite('bulk_migration_idempotency',batch_key,None,batch),))
            existing=self.store.get('bulk_migration_idempotency',batch_key)
        if not existing or any(existing.get(name)!=item for name,item in batch.items()):
            raise ValueError('SOURCE_BATCH_IDEMPOTENCY_CONFLICT')
        references=[]
        for index,item in enumerate(parsed):
            result=self.capture(authorization=authorization,envelope=item,
                idempotency_key='envelope:'+_digest({'key':key,'index':index}))
            references.append({name:result[name] for name in ('artifact_ref','digest','role')})
        receipt={'contract_version':'boi/source-envelope-intake@0.1.0',
            'employee_id':authorization.principal,'policy':self._policy(authorization),
            'request_key_digest':_digest(key),'sources':references,'status':'PROVISIONAL',
            'production_changed':False,'active_transition':False,'model_invocation_count':0}
        receipt_ref='source-intake-receipt:'+_digest(receipt)
        prior=self.store.get('bulk_migration_receipts',receipt_ref)
        if prior is None:
            self.store.atomic_compare_and_write((AtomicWrite('bulk_migration_receipts',receipt_ref,None,receipt),))
            prior=self.store.get('bulk_migration_receipts',receipt_ref)
        if not prior or any(prior.get(name)!=item for name,item in receipt.items()):
            raise ValueError('SOURCE_INTAKE_RECEIPT_CONFLICT')
        return {**{name:item for name,item in value.items() if name!='source_envelopes'},
                'source_artifacts':references,'source_intake_receipt_ref':receipt_ref}

    def resolve_bytes(self, *, authorization, reference):
        """Trusted deterministic consumer only; never a model-facing source tool."""
        validated=self._source(authorization,reference['artifact_ref'],reference['digest'],reference['role'])
        record=self.ledger.read(validated['artifact_ref'])
        return self.objects.get(record.payload['object_ref'])

    @staticmethod
    def _policy(authorization):
        uses={'store','cite','derive','model_input','model_training','org_share'}
        if (not isinstance(authorization,IntakeAuthorization) or not authorization.principal.strip()
            or not re.fullmatch(r'sha256:[0-9a-f]{64}',authorization.policy_digest)
            or not set(authorization.allowed_uses)<=uses
            or authorization.visibility not in {'private','team','public'}
            or (authorization.visibility=='team' and not authorization.team_id)):
            raise ValueError('SOURCE_AUTHORIZATION_INVALID')
        return {'principal':authorization.principal,'policy_digest':authorization.policy_digest,
            'allowed_uses':sorted(set(authorization.allowed_uses)),'visibility':authorization.visibility,
            'team_id':authorization.team_id}

    def _source(self,authorization,artifact_ref,expected_digest,role):
        record=self.ledger.read(artifact_ref)
        if record.kind!=RecordKind.SOURCE_ARTIFACT:
            raise ValueError('SOURCE_ARTIFACT_KIND_REQUIRED')
        value=record.payload
        if (value.get('owner')!=authorization.principal
            or value.get('policy_digest')!=authorization.policy_digest):
            raise ValueError('SOURCE_ARTIFACT_ACCESS_DENIED')
        if value.get('content_digest')!=expected_digest or value.get('role')!=role:
            raise ValueError('SOURCE_ARTIFACT_BINDING_MISMATCH')
        rights=self.ledger.read(value['rights_record_ref'])
        if rights.kind!=RecordKind.SOURCE_RIGHTS_RECORD or any(
            rights.payload.get(key)!=item for key,item in self._policy(authorization).items()) or (
                rights.payload.get('content_digest')!=expected_digest
                or rights.payload.get('source_capture_ref')!=value.get('source_capture_ref')):
            raise ValueError('SOURCE_RIGHTS_POLICY_STALE')
        def verified_length(raw):
            if byte_digest(raw)!=expected_digest:raise ValueError('SOURCE_ARTIFACT_BYTES_DRIFT')
            return len(raw)
        project=getattr(self.objects,'project_verified',None)
        length=(project(value['object_ref'],version='source-integrity@1:'+expected_digest,
                    derive=verified_length) if project else verified_length(self.objects.get(value['object_ref'])))
        display_name=self.source_display_name(record)
        return {'artifact_ref':record.record_id,'digest':expected_digest,'role':role,
                'byte_length':length,'rights_record_ref':value['rights_record_ref'],
                'classification':'PROVISIONAL','canonical_projection_eligible':False,
                **({'display_name':display_name} if isinstance(display_name,str) and display_name else {})}

    def source_display_name(self, artifact):
        """Read a basename bound to this exact immutable source artifact."""
        direct=artifact.payload.get('source_identity',{}).get('display_name')
        if isinstance(direct,str) and direct:return direct
        row=self.store.get('source_display_names',artifact.record_id)
        expected={'contract_version':'boi/source-display-name@1',
            'artifact_ref':artifact.record_id,'owner':artifact.payload.get('owner'),
            'content_digest':artifact.payload.get('content_digest'),
            'policy_digest':artifact.payload.get('policy_digest'),
            'role':artifact.payload.get('role')}
        if row is None:return None
        if (any(row.get(key)!=item for key,item in expected.items())
                or not isinstance(row.get('display_name'),str)):
            raise ValueError('SOURCE_DISPLAY_NAME_BINDING_CHANGED')
        return row['display_name']

    def register_source_display_name(self, *, authorization, artifact_ref,
                                     expected_digest, role, display_name):
        """Attach one verified basename to a legacy source without rewriting it."""
        self._source(authorization,artifact_ref,expected_digest,role)
        checked=ArtifactEnvelope(kind='artifact_ref',artifact_ref=artifact_ref,
            digest=expected_digest,role=role,display_name=display_name)
        artifact=self.ledger.read(artifact_ref)
        value={'contract_version':'boi/source-display-name@1','artifact_ref':artifact_ref,
            'owner':artifact.payload['owner'],'content_digest':expected_digest,
            'policy_digest':artifact.payload['policy_digest'],'role':role,
            'display_name':checked.display_name}
        prior=self.store.get('source_display_names',artifact_ref)
        if prior is None:
            self.store.atomic_compare_and_write((AtomicWrite('source_display_names',artifact_ref,None,value),))
            prior=self.store.get('source_display_names',artifact_ref)
        if not prior or any(prior.get(key)!=item for key,item in value.items()):
            raise ValueError('SOURCE_DISPLAY_NAME_CONFLICT')
        return self._source(authorization,artifact_ref,expected_digest,role)

    def capture(self,*,authorization,envelope,idempotency_key):
        policy=self._policy(authorization)
        if not isinstance(idempotency_key,str) or not 0<len(idempotency_key)<=240:
            raise ValueError('SOURCE_IDEMPOTENCY_KEY_REQUIRED')
        if 'store' not in authorization.allowed_uses:raise ValueError('SOURCE_STORE_NOT_AUTHORIZED')
        source=parse_envelope(envelope)
        if isinstance(source,ArtifactEnvelope):
            result=self._source(authorization,source.artifact_ref,source.digest,source.role)
            if source.display_name:
                result=self.register_source_display_name(authorization=authorization,
                    artifact_ref=source.artifact_ref,expected_digest=source.digest,
                    role=source.role,display_name=source.display_name)
            key='source-intake:'+_digest({'principal':authorization.principal,'key':idempotency_key})
            fingerprint=_digest({'envelope':source.model_dump(mode='json'),'policy':policy})
            current=self.store.get('bulk_migration_idempotency',key)
            if current is None:
                value={'employee_id':authorization.principal,'input_fingerprint':fingerprint,
                       'artifact_ref':source.artifact_ref}
                if self.store.atomic_compare_and_write((AtomicWrite('bulk_migration_idempotency',key,None,value),)):
                    return result
                current=self.store.get('bulk_migration_idempotency',key)
            if not current or current.get('input_fingerprint')!=fingerprint:
                raise ValueError('SOURCE_INTAKE_IDEMPOTENCY_CONFLICT')
            return result
        if isinstance(source,InlineEnvelope):
            raw=source.source_bytes();media=source.media_type
            display_name=getattr(source,'display_name',None)
            identity={'kind':source.kind,'content_digest':byte_digest(raw),
                **({'display_name':display_name} if display_name else {})}
            resource='inline:'+byte_digest(raw)
        else:
            if not self.connector_resolver:raise ValueError('CONNECTOR_SNAPSHOT_UNAVAILABLE')
            frozen=self.connector_resolver(authorization,source)
            if (not isinstance(frozen,ConnectorSnapshot) or frozen.snapshot_digest!=source.snapshot_digest
                or frozen.selector_manifest_ref!=source.selector_manifest_ref):
                raise ValueError('CONNECTOR_SNAPSHOT_BINDING_MISMATCH')
            raw,media,resource=frozen.raw,frozen.media_type,frozen.resource_ref
            identity=source.model_dump(mode='json')
        return self._capture_raw(authorization=authorization, raw=raw, media=media,
            identity=identity, resource=resource, role=source.role, idempotency_key=idempotency_key)

    def capture_uploaded(self, *, authorization, upload, bundle_ref, object_id):
        """Internal bridge from an actually confirmed immutable upload to source SOT.

        No caller path, inline limit override, connector impersonation or source
        sharing grant. The bundle importer separately records confirmation lineage.
        """
        from .local_bundle_upload import LocalBundleUpload
        if not isinstance(upload, LocalBundleUpload) or upload.service.intake is not self:
            raise ValueError('SOURCE_LOCAL_UPLOAD_SERVICE_REQUIRED')
        def current():
            row, obj, _ = upload.service.upload_context(authorization=authorization,
                bundle_ref=bundle_ref, object_id=object_id)
            if obj['purpose'] != 'raw_source':
                raise ValueError('SOURCE_LOCAL_UPLOAD_RAW_SOURCE_REQUIRED')
            return obj
        obj = current()
        path = upload.verified_path(authorization=authorization, bundle_ref=bundle_ref, object_id=object_id)
        with path.open('rb') as stream:
            raw = stream.read(obj['byte_length'] + 1)
        if len(raw) != obj['byte_length'] or byte_digest(raw) != obj['byte_digest']:
            raise ValueError('SOURCE_LOCAL_UPLOAD_BYTES_DRIFT')
        current()
        result = self._capture_raw(authorization=authorization, raw=raw, media=obj['media_type'],
            identity={'kind':'confirmed_local_upload', 'content_digest':obj['byte_digest'],
                'display_name':obj['display_name']},
            resource='uploaded:' + obj['byte_digest'], role=obj['source_role'],
            idempotency_key='local-upload:' + _digest([bundle_ref, object_id]))
        # A stop/revocation can preserve a private captured artifact but cannot
        # acknowledge an import or create any knowledge head/publication.
        current()
        return result

    def _capture_raw(self, *, authorization, raw, media, identity, resource, role, idempotency_key):
        policy = self._policy(authorization)
        if 'store' not in authorization.allowed_uses:
            raise ValueError('SOURCE_STORE_NOT_AUTHORIZED')
        # Preserve exact original bytes in the same content-addressed byte store.
        content_digest=self.objects.put(raw)
        fingerprint=_digest({'source':identity,'role':role,'media_type':media,'policy':policy,
                             'content_digest':content_digest})
        outbox_key='source-capture:'+fingerprint
        request_key='source-intake:'+_digest({'principal':authorization.principal,'key':idempotency_key})
        request={'employee_id':authorization.principal,'input_fingerprint':fingerprint,'outbox_ref':outbox_key}
        for attempt in range(3):
            old_request=self.store.get('bulk_migration_idempotency',request_key)
            if old_request is not None:
                if any(old_request.get(key)!=value for key,value in request.items()):
                    raise ValueError('SOURCE_INTAKE_IDEMPOTENCY_CONFLICT')
                break
            old=self.store.get('bulk_migration_source_outbox',outbox_key)
            if old is not None and (old.get('input_fingerprint')!=fingerprint
                or old.get('employee_id')!=authorization.principal or old.get('policy')!=policy):
                raise ValueError('SOURCE_OUTBOX_BINDING_MISMATCH')
            captured=self.clock().astimezone(timezone.utc).isoformat()
            outbox=old or {'outbox_ref':outbox_key,'employee_id':authorization.principal,
                'input_fingerprint':fingerprint,'source_identity':identity,'content_digest':content_digest,
                'object_ref':content_digest,'byte_length':len(raw),'role':role,'media_type':media,
                'resource':resource,'policy':policy,'captured_at':captured,'state':'captured'}
            if old is None:
                outbox['capture_digest']=_digest({key:value for key,value in outbox.items() if key!='state'})
            writes=[AtomicWrite('bulk_migration_idempotency',request_key,None,request)]
            if old is None:writes.append(AtomicWrite('bulk_migration_source_outbox',outbox_key,None,outbox))
            else:writes.append(AtomicWrite('bulk_migration_source_outbox',outbox_key,old,old))
            if self.store.atomic_compare_and_write(writes):break
        else:raise ValueError('SOURCE_INTAKE_RESERVATION_CONFLICT')
        return self.publish(authorization=authorization,outbox_ref=outbox_key)

    def publish(self,*,authorization,outbox_ref):
        policy=self._policy(authorization)
        old=self.store.get('bulk_migration_source_outbox',outbox_ref)
        if not old or old.get('employee_id')!=authorization.principal:
            raise ValueError('SOURCE_OUTBOX_ACCESS_DENIED')
        if old['policy']!=policy:
            raise ValueError('SOURCE_OUTBOX_POLICY_STALE')
        captured={key:value for key,value in old.items() if key not in
                  {'state','capture_digest','artifact_ref','rights_record_ref','updated_at'}}
        if old.get('capture_digest')!=_digest(captured):
            raise ValueError('SOURCE_CAPTURE_DIGEST_MISMATCH')
        fingerprint=_digest({'source':old['source_identity'],'role':old['role'],'media_type':old['media_type'],
                             'policy':policy,'content_digest':old['content_digest']})
        if old['input_fingerprint']!=fingerprint or outbox_ref!='source-capture:'+fingerprint:
            raise ValueError('SOURCE_OUTBOX_BINDING_MISMATCH')
        if old['state']=='registered':
            return self._source(authorization,old['artifact_ref'],old['content_digest'],old['role'])
        raw=self.objects.get(old['object_ref'])
        if byte_digest(raw)!=old['content_digest']:raise ValueError('SOURCE_BYTES_DRIFT')
        rights=self.ledger.append(RecordKind.SOURCE_RIGHTS_RECORD,{
            'contract_version':'boi/source-use-policy@0.1.0','source_capture_ref':outbox_ref,
            'content_digest':old['content_digest'],**old['policy']},
            authority='rights_service',occurred_at=old['captured_at'])
        artifact=self.ledger.append(RecordKind.SOURCE_ARTIFACT,{
            'contract_version':'boi/source-artifact-intake@0.1.0','owner':authorization.principal,
            'content_digest':old['content_digest'],'object_ref':old['object_ref'],'byte_length':len(raw),
            'resource':old['resource'],'media_type':old['media_type'],'role':old['role'],
            'source_capture_ref':outbox_ref,
            'source_identity':old['source_identity'],'rights_record_ref':rights.record_id,
            'policy_digest':authorization.policy_digest,'visibility':old['policy']['visibility']},
            authority='intake_service',occurred_at=old['captured_at'])
        value={**old,'state':'registered','artifact_ref':artifact.record_id,'rights_record_ref':rights.record_id}
        projection={'artifact_ref':artifact.record_id,'employee_id':authorization.principal,
            'digest':old['content_digest'],'role':old['role'],'object_ref':old['object_ref'],
            'rights_record_ref':rights.record_id,'outbox_ref':outbox_ref,
            'canonical_projection_eligible':False}
        prior=self.store.get('bulk_migration_source_artifacts',artifact.record_id)
        if prior is not None and any(prior.get(key)!=value for key,value in projection.items()):
            raise ValueError('SOURCE_PROJECTION_BINDING_MISMATCH')
        if not self.store.atomic_compare_and_write((
            AtomicWrite('bulk_migration_source_outbox',outbox_ref,old,value),
            AtomicWrite('bulk_migration_source_artifacts',artifact.record_id,prior,projection))):
            latest=self.store.get('bulk_migration_source_outbox',outbox_ref)
            if not latest or latest.get('artifact_ref')!=artifact.record_id:
                raise ValueError('SOURCE_OUTBOX_RETRY_REQUIRED')
        return self._source(authorization,artifact.record_id,old['content_digest'],old['role'])
