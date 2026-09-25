"""Bounded units over the existing native/space/SQLite publication transaction.

The required authority callback supplies actual use/impact admission; there is no
default pass or public endpoint using a substitute. Confirmation covers the whole
precomputed plan. Unit success is written with native heads and the public pointer.
"""
from dataclasses import dataclass
import json

from .domain_asset_staging import StagedDomainAsset,merge_writes
from .domain_asset_store import source_manifest_digest
from .knowledge_publication import (KnowledgePublicationCoordinator,PublicationAdmission,
    SCOPES,OUTBOX,empty_publication_scope)
from .knowledge_profile_projector import ADAPTER_REVISION,KnowledgeProfileProjector
from .knowledge_projection_contract import ProjectionPublication,PublicationChange
from .local_bundle_checks import LocalBundleChecks
from .local_publication_state import (UNITS,PREPARATIONS,unit_key,unit_binding,
    committed_unit,preparation_key)
from .local_bundle_snapshot import with_bundle_snapshot
from .semantic_binding_contract import semantic_digest
from ..v2.atomic_store_contract import AtomicWrite,MAX_ATOMIC_WRITES,is_atomic_read_fence

MAX_COMMIT_WIRE_BYTES=16*1024*1024
LOCAL_PUBLICATION_LEASE_SECONDS=600


@dataclass(frozen=True)
class UnitAuthority:
    fences: tuple[AtomicWrite,...]
    qualification_refs: tuple=()


class LocalPublicationUnits:
    def __init__(self,importer,spaces,projection,*,authorize_unit,clock=None,
                 lease_seconds=LOCAL_PUBLICATION_LEASE_SECONDS):
        if not callable(authorize_unit) or spaces.intake is not importer.intake:
            raise ValueError('LOCAL_PUBLICATION_ACTUAL_AUTHORITY_REQUIRED')
        if not 1 <= lease_seconds <= 3600:
            raise ValueError('LOCAL_PUBLICATION_LEASE_LIMIT_INVALID')
        self.importer,self.spaces,self.projection=importer,spaces,projection
        self.service=importer.service
        self.store=importer.store
        self.authorize_unit,self.clock=authorize_unit,clock
        self.lease_seconds=lease_seconds

    def _context(self,auth,bundle_ref,unit_id):
        row,fences=self.importer._context(auth,bundle_ref)
        self.importer.service._require_possible_capacity(row)
        plan=row['preview'].get('publication_plan')
        unit=next((u for u in (plan or {}).get('units',[]) if u['unit_id']==unit_id),None)
        if unit is None:raise ValueError('LOCAL_PUBLICATION_CONFIRMED_UNIT_REQUIRED')
        for position in unit['predecessor_positions']:
            prior=plan['units'][position]
            item=self.store.get(UNITS,unit_key(bundle_ref,prior['unit_id']))
            if not item or committed_unit(self.store,row,prior,item) is None:
                raise ValueError('LOCAL_PUBLICATION_PREDECESSOR_PENDING')
        authority=self.authorize_unit(auth,row,unit)
        if (not isinstance(authority,UnitAuthority) or not authority.fences
                or any(not is_atomic_read_fence(w) for w in authority.fences)):
            raise ValueError('LOCAL_PUBLICATION_ACTUAL_AUTHORITY_REQUIRED')
        return row,unit,tuple(fences)+authority.fences,authority

    def prepare_unit(self,*,authorization,bundle_ref,unit_id,refresh=False):
        row,unit,fences,authority=self._context(authorization,bundle_ref,unit_id)
        key=unit_key(bundle_ref,unit_id)
        old=self.store.get(UNITS,key)
        if old:
            if old['binding']!=unit_binding(row,unit):raise ValueError('LOCAL_PUBLICATION_UNIT_BINDING_CHANGED')
            if not refresh or old['state']=='published':return old
        status=self.importer.status(authorization=authorization,bundle_ref=bundle_ref)
        if status['state']!='native_prepared_requires_qualification':raise ValueError('LOCAL_PUBLICATION_NATIVE_PREPARATION_REQUIRED')
        handles=tuple(StagedDomainAsset.model_validate(self.importer._saved(row,x)['result']['staged']) for x in unit['object_ids'])
        catalog=self.store.get('domain_asset_catalogs',self.importer.service.assets.catalog_key(authorization,unit['namespace']))
        scope=(catalog or {}).get('generation_scope_id') or 'knowledge-namespace:'+semantic_digest([authorization.principal,unit['namespace']])
        # Read the scope BEFORE probing the prior outbox. Every reservation
        # changes this scope atomically with its outbox and its unit read fence.
        # The refresh CAS below therefore cannot race past an old reservation,
        # even when that operation finishes between these bounded reads.
        scope_state=self.store.get(SCOPES,scope)
        visible=(scope_state or empty_publication_scope(scope))['visible']
        sources={}
        for handle in handles:
            record,_=self.importer.stage.read(authorization=authorization,scope_ref=self.importer.scope(row),revision=handle.revision,model_input=False)
            for source in record.payload['sources']:sources[source['artifact_ref']]=source
        manifest=ProjectionPublication(contract_version='boi/knowledge-projection-publication@2',
            projection_mode='bootstrap' if visible['generation']==0 else 'incremental',
            scope_id=scope,principal_id=authorization.principal,base_generation=visible['generation'],
            policy_digest=authorization.policy_digest,confirmation_ref=self.importer.scope(row),
            source_manifest_digest=source_manifest_digest(sources.values()),adapter_revision=ADAPTER_REVISION,
            qualification_refs=authority.qualification_refs,
            changes=tuple(PublicationChange(stable_id=h.native_identity,operation='upsert',
                previous_revision=h.previous_revision.model_dump(mode='json') if h.previous_revision else None,
                revision=h.revision.model_dump(mode='json')) for h in handles))
        value={'binding':unit_binding(row,unit),'employee_id':authorization.principal,'state':'prepared',
            'publication':manifest.model_dump(mode='json'),'publication_digest':manifest.digest,
            'revisions':{x:h.revision.model_dump(mode='json') for x,h in zip(unit['object_ids'],handles)},
            'catalog_transitions':[]}
        if old:
            if old['publication_digest']==manifest.digest:return old
            if old['state']!='prepared':raise ValueError('LOCAL_PUBLICATION_UNIT_STATE_INVALID')
            before=ProjectionPublication.model_validate(old['publication']).model_dump(mode='json')
            mutable={'qualification_refs','base_generation','projection_mode'}
            if (old['publication_digest']!=ProjectionPublication.model_validate(before).digest
                    or old['revisions']!=value['revisions']
                    or {k:v for k,v in before.items() if k not in mutable}
                        != {k:v for k,v in value['publication'].items() if k not in mutable}):
                raise ValueError('LOCAL_PUBLICATION_UNIT_BINDING_CHANGED')
            if self.store.get(OUTBOX,old['publication_digest']) is not None:
                raise ValueError('LOCAL_PUBLICATION_EXISTING_OPERATION_REQUIRES_RECOVERY')
            history_key=preparation_key(bundle_ref,unit_id,old['publication_digest'])
            history={'employee_id':authorization.principal,'preparation':old,
                'replaced_by':manifest.digest,'reason':'current_qualification_or_generation_changed'}
            value.update(previous_preparation_ref=history_key)
            fences=(*fences,AtomicWrite(SCOPES,scope,scope_state,scope_state or empty_publication_scope(scope)),
                AtomicWrite(PREPARATIONS,history_key,None,history))
        writes=(*fences,AtomicWrite(UNITS,key,old,value))
        self._final_write_budget(writes)
        if not self.store.atomic_compare_and_write(writes):
            saved=self.store.get(UNITS,key)
            if (not saved or saved.get('publication_digest')!=manifest.digest
                    or saved.get('binding')!=value['binding']):
                raise ValueError('LOCAL_PUBLICATION_UNIT_PREPARE_CONFLICT')
        return self.store.get(UNITS,key)

    def projection_snapshot(self,scope):
        from .knowledge_projection_store import ProjectionSnapshot
        state=self.store.get('knowledge_publication_scopes',scope)
        visible=(state or {}).get('visible',{'generation':0,'manifest_digest':None})
        return ProjectionSnapshot(scope,visible['generation'],visible['manifest_digest'])

    @with_bundle_snapshot
    def run_unit(self,*,authorization,bundle_ref,unit_id,writer_id,expected_publication_digest=None):
        # Finalizing an already committed operation does not issue a new use
        # grant. It must remain recoverable if the checker release changes after
        # the native/space CAS. Current actor/space authorization still applies.
        row=self.service._read(authorization,bundle_ref)
        unit=next((u for u in (row['preview'].get('publication_plan') or {}).get('units',[])
            if u['unit_id']==unit_id),None)
        if unit is None:raise ValueError('LOCAL_PUBLICATION_CONFIRMED_UNIT_REQUIRED')
        current=self.store.get(UNITS,unit_key(bundle_ref,unit_id))
        if not current or committed_unit(self.store,row,unit,current) is None:
            current=self.prepare_unit(authorization=authorization,bundle_ref=bundle_ref,unit_id=unit_id)
        if expected_publication_digest is not None and current['publication_digest']!=expected_publication_digest:
            raise ValueError('LOCAL_PUBLICATION_EXACT_PREFLIGHT_REQUIRED')
        coordinator=self.coordinator(authorization=authorization,bundle_ref=bundle_ref,unit_id=unit_id)
        manifest=ProjectionPublication.model_validate(current['publication'])
        operation=self.store.get('knowledge_projection_outbox',manifest.digest)
        if operation:
            handle=coordinator._handle(operation)
            state=self.store.get('knowledge_publication_scopes',manifest.scope_id)
            active=state and state['active_operation']==manifest.digest
            if active and operation['lease_until']<=coordinator.clock():
                handle=coordinator.take_over(manifest.scope_id,manifest.digest,writer_id=writer_id)
            if operation['status'] in ('published','aborted','aborting'):
                return coordinator.reconcile(handle)
            if handle.writer_id!=writer_id:
                handle=coordinator.take_over(manifest.scope_id,manifest.digest,writer_id=writer_id)
        else:
            handle=coordinator.reserve(manifest,writer_id=writer_id)
        coordinator.prepare(handle)
        # Intake materializes a capacity-bounded native unit. Give each phase
        # its own finite lease; renewal still rejects an expired/stale writer.
        # Commit independently rechecks current authority and every use fence.
        coordinator.renew(handle)
        return coordinator.commit(handle)

    def coordinator(self,*,authorization,bundle_ref,unit_id):
        key=unit_key(bundle_ref,unit_id)
        def admission(manifest,phase):
            row,unit,fences,authority=self._context(authorization,bundle_ref,unit_id)
            current=self.store.get(UNITS,key)
            if (not current or current['binding']!=unit_binding(row,unit)
                    or current['publication_digest']!=manifest.digest
                    or tuple(manifest.qualification_refs)!=tuple(authority.qualification_refs)):
                raise ValueError('LOCAL_PUBLICATION_UNIT_ADMISSION_CHANGED')
            if current['state']=='published':raise ValueError('LOCAL_PUBLICATION_UNIT_ALREADY_PUBLISHED')
            handles=tuple(StagedDomainAsset.model_validate(self.importer._saved(row,x)['result']['staged']) for x in unit['object_ids'])
            native=self.importer.stage.publication_writes(authorization=authorization,manifest=manifest,staged=handles,
                validate_reading=self.importer.validate_reading, shared_reading_binding=self.importer.shared_reading_binding)
            sfences,space=self.spaces.initial_publication_writes(importer=self.importer,authorization=authorization,
                bundle_ref=bundle_ref,manifest=manifest,unit_id=unit_id)
            catalog_keys={c['key'] for c in row['preview']['basis']['catalogs']}
            transitions=[{'key':w.key,'before_epoch':(w.expected or {}).get('epoch',0),'after_epoch':w.value['epoch']}
                for w in native if w.collection=='domain_asset_catalogs' and w.key in catalog_keys and w.expected!=w.value]
            space_transitions=[{'key':w.key,'before_epoch':(w.expected or {}).get('epoch',0),
                'after_epoch':w.value['epoch']} for w in space
                if w.collection=='knowledge_space_epochs' and w.expected!=w.value]
            terminal={**current,'state':'published','catalog_transitions':transitions,
                'space_transitions':space_transitions}
            merged=merge_writes((*native,*space,AtomicWrite(UNITS,key,current,terminal)),(*fences,*sfences))
            # Count the actual deduplicated public writes + every admission
            # fence + scope/outbox/receipt before reserving a generation.
            self._capacity(merged)
            if phase=='reserve':
                pure=tuple(w for w in merge_writes((),(*fences,*sfences,AtomicWrite(UNITS,key,current,current)))
                    if w.expected is not None)
                return PublicationAdmission(pure)
            pure=tuple(w for w in merged if is_atomic_read_fence(w))
            public=tuple(w for w in merged if not is_atomic_read_fence(w))
            return PublicationAdmission(pure,public)
        def materialize(manifest):
            row,_,_,_=self._context(authorization,bundle_ref,unit_id)
            return KnowledgeProfileProjector(read_revision=LocalBundleChecks(self.importer)._reader(authorization,row)).materialize(manifest)
        kwargs={'lease_seconds':self.lease_seconds}
        if self.clock is not None:kwargs['clock']=self.clock
        return KnowledgePublicationCoordinator(self.store,self.projection,admission=admission,materialize=materialize,
            validate_writes=self._final_write_budget,**kwargs)

    def preflight_unit(self,*,authorization,bundle_ref,unit_id):
        current=self.store.get(UNITS,unit_key(bundle_ref,unit_id))
        if not current:raise ValueError('LOCAL_PUBLICATION_UNIT_PREPARATION_REQUIRED')
        manifest=ProjectionPublication.model_validate(current['publication'])
        coordinator=self.coordinator(authorization=authorization,bundle_ref=bundle_ref,unit_id=unit_id)
        admitted=coordinator._admit(manifest,'commit')
        return {'unit_id':unit_id,'publication_digest':manifest.digest,
            **self._capacity(merge_writes(admitted.public_writes,admitted.fences)),
            'publication_granted':False,'snapshot_only':True}

    @staticmethod
    def _wire_bytes(writes):
        return len(json.dumps([{'collection':w.collection,'key':w.key,'expected':w.expected,'value':w.value} for w in writes],
            ensure_ascii=False,allow_nan=False,separators=(',',':')).encode())

    @classmethod
    def _final_write_budget(cls,writes):
        if len(writes)>MAX_ATOMIC_WRITES:raise ValueError('LOCAL_PUBLICATION_EXACT_WRITE_CAPACITY_EXCEEDED')
        if cls._wire_bytes(writes)>MAX_COMMIT_WIRE_BYTES:raise ValueError('LOCAL_PUBLICATION_WRITE_BYTES_EXCEEDED')

    @staticmethod
    def _capacity(writes):
        count=len(writes)+3
        wire_bytes=LocalPublicationUnits._wire_bytes(writes)
        if count>MAX_ATOMIC_WRITES:raise ValueError('LOCAL_PUBLICATION_EXACT_WRITE_CAPACITY_EXCEEDED')
        # Coordinator control/receipt values have their own measured final
        # check; reserve a conservative envelope here, not a fake exact byte count.
        if wire_bytes+65536>MAX_COMMIT_WIRE_BYTES:raise ValueError('LOCAL_PUBLICATION_WRITE_BYTES_EXCEEDED')
        return {'exact_composite_write_count':count,'admission_wire_bytes':wire_bytes,
            'coordinator_envelope_bytes':65536,'maximum_write_count':MAX_ATOMIC_WRITES,'maximum_wire_bytes':MAX_COMMIT_WIRE_BYTES}
