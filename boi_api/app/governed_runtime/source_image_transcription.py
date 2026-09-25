"""Immutable authored visual transcription, never a parsed cell or verified fact."""
from datetime import timezone
from typing import Annotated
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, semantic_digest
from .source_envelope import ArtifactEnvelope, byte_digest
from .source_field_projection import SourceFieldProjectionService
from .ledger import RecordKind
from ..v2.atomic_store_contract import AtomicWrite

CONTRACT = 'boi/source-image-transcription@1'
# Reuse the existing durable idempotency collection with a disjoint key prefix.
COLLECTION = 'bulk_migration_idempotency'
Coordinate = Annotated[int, Field(ge=0, le=10000, strict=True)]

class SourceImageTranscriptionRequest(FrozenContract):
    reference: ArtifactEnvelope
    image_ref: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=8192, pattern=r'\S')
    region: tuple[Coordinate, Coordinate, Coordinate, Coordinate]
    agent_session_ref: str = Field(min_length=1, max_length=240)

    @model_validator(mode='after')
    def rectangle(self):
        x0,y0,x1,y1=self.region
        if x0>=x1 or y0>=y1:
            raise ValueError('SOURCE_IMAGE_REGION_INVALID')
        return self

def transcribe(service, *, authorization, request):
    request=SourceImageTranscriptionRequest.model_validate(request)
    ref=request.reference.model_dump(mode='json')
    # Resolve exact original image under current source policy, not client bytes.
    image=service.read(authorization=authorization,request=dict(
        reference=ref,operation='read',image_ref=request.image_ref))
    if 'store' not in authorization.allowed_uses:
        raise ValueError('SOURCE_STORE_NOT_AUTHORIZED')
    descriptor=image['image']; intake=service.intake
    material={'contract_version':CONTRACT,**request.model_dump(mode='json'),
              'employee_id':authorization.principal,'policy_digest':authorization.policy_digest,
              'rights_record_ref':image['rights_record_ref']}
    digest=semantic_digest(material)
    key='image-transcription:'+digest
    reserved=intake.store.get(COLLECTION,key)
    if reserved is None:
        proposed={'material_digest':digest,'registered_at':intake.clock().astimezone(timezone.utc).isoformat()}
        if intake.store.atomic_compare_and_write([AtomicWrite(COLLECTION,key,None,proposed)]):
            reserved=proposed
        else:
            reserved=intake.store.get(COLLECTION,key)
    if not reserved or reserved.get('material_digest')!=digest:
        raise ValueError('SOURCE_IMAGE_TRANSCRIPTION_RESERVATION_CONFLICT')
    original,_=SourceFieldProjectionService(intake)._authorize(authorization,ref,model_input=True)
    if byte_digest(original)!=ref['digest']:
        raise ValueError('SOURCE_IMAGE_TRANSCRIPTION_SOURCE_CHANGED')
    text_ref=intake.objects.put(request.text.encode('utf-8'))
    locator='/images/'+descriptor['content_digest']+'/transcriptions/'+digest
    payload={'contract_version':CONTRACT,'artifact_ref':ref['artifact_ref'],
        'source_revision_digest':ref['digest'],'snapshot_digest':ref['digest'],'source_role':ref['role'],
        'employee_id':authorization.principal,'policy_digest':authorization.policy_digest,
        'rights_record_ref':image['rights_record_ref'],'field_locator':locator,
        'record_locator':'/images/'+descriptor['content_digest'],
        'representation':'authored_image_transcription','field_state':'present','value_kind':'string',
        'presence_basis':'authenticated_visual_transcription','field_object_ref':text_ref,
        'content_digest':byte_digest(request.text.encode('utf-8')),'character_count':len(request.text),
        'offset_basis':'decoded_unicode_codepoints','status':'PROVISIONAL',
        'canonical_projection_eligible':False,'semantic_status':'not_evaluated',
        'source_fidelity':'not_evaluated','source_observation_time':'unknown','cell_alignment':'not_inferred',
        'structural_metadata':{'image':descriptor,'region':list(request.region),
            'region_basis':'original image coordinates normalized to 0..10000; authored selection',
            'authored_by':authorization.principal,'reported_agent_session_ref':request.agent_session_ref,
            'agent_session_verified':False,'registered_at':reserved['registered_at'],
            'source_observation_time':'unknown','cell_alignment':'not_inferred',
            'source_fidelity':'not_evaluated','transcription_method':'authored_visual'}}
    record=intake.ledger.append(RecordKind.EVIDENCE_SPAN,payload,authority='evidence_service',
                               occurred_at=reserved['registered_at'])
    return {'span_ref':record.record_id,**payload,'publication_changed':False,
            'original_source_or_parsed_projection_changed':False}
