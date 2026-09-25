"""Rebuild a bounded set of published Profile indexes from exact native content.

The existing maintenance coordinator owns current edit/model-input authority,
CAS, preimages, epochs and response-loss recovery. No content/use/space revision
is created, and the request cannot supply a replacement schema or SQL.
"""
import json
from typing import Literal

from .native_reference_repair import NativeReferenceRepair,NativeReferenceRepairRequest
from .native_profile_catalog import META,COMPONENTS,profile_catalog_ready,profile_projection


class NativeProfileRepairRequest(NativeReferenceRepairRequest):
    contract_version: Literal['boi/native-profile-repair-request@1']='boi/native-profile-repair-request@1'


class NativeProfileRepair(NativeReferenceRepair):
    request_model=NativeProfileRepairRequest
    version='boi/native-profile-repair@1'
    key_prefix='native-profile-repair:'
    marker='profile_repair_ref'
    digest_field='profile_components_digest'
    coverage='declared_components_of_exact_published_profiles_only'

    def _read(self,actor_id,revision):
        state=super()._read(actor_id,revision)
        access,record,asset=self.spaces.read(actor_id=actor_id,stable_id=state['identity'],
            revision=revision,purpose='model_input')
        if access!=state['authority'][1]:
            raise ValueError('KNOWLEDGE_PROFILE_REPAIR_AUTHORITY_CHANGED')
        projection=profile_projection(record,asset)
        if projection.get('profile_component_state')!='prepared':
            raise ValueError('KNOWLEDGE_PROFILE_REPAIR_SUPPORTED_PROFILE_REQUIRED')
        state['projection']=projection
        return state

    def _fingerprints(self,targets):
        """Read only requested, already-authorized profiles; retain old rows.

        Unlike everyday discovery, repair intentionally reads the bounded native
        schema and its derived components to verify/reconstruct every field.
        The coordinator's receipt/CAS byte limit applies before any mutation.
        """
        table=self.index.store._table('domain_knowledge_assets')
        keys=[self.index.backend.prefix+ref.ref for ref in targets]
        with self.index.store._connection() as connection,connection.transaction():
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            connection.execute("SET LOCAL statement_timeout='5s'")
            profile_catalog_ready(connection,table)
            rows=connection.execute(f'''SELECT a.item_key,a.native_profile_digest,
 (SELECT to_jsonb(m)-'asset_key' FROM {META} m WHERE m.asset_key=a.item_key),
 (SELECT COALESCE(jsonb_agg(to_jsonb(c)-'asset_key' ORDER BY position),'[]'::jsonb)
  FROM {COMPONENTS} c WHERE c.asset_key=a.item_key)
 FROM {table} a WHERE a.item_key=ANY(%s)''',(keys,)).fetchall()
        return {key[len(self.index.backend.prefix):]:{
            'native_digest':digest,'metadata':metadata,'components':components}
            for key,digest,metadata,components in rows}

    def _expected_fingerprint(self,state):
        projection=state['projection'];wire=json.loads(projection['profile_components_wire'])
        digest=projection[self.digest_field]
        return {'native_digest':digest,'metadata':{'digest':digest,'revision':wire['revision'],
            'payload_digest':wire['record_payload_digest'],'info':wire['profile'],
            'component_count':len(wire['components'])},
            'components':[{'position':i,'kind':c['declaration']['kind'],
                'role':c['declaration'].get('role'),'value_kind':c['declaration'].get('value_kind'),
                'subject_type':c['subject_type'],'component':{k:v for k,v in c.items() if k!='tokens'},
                'tokens':c['tokens']} for i,c in enumerate(wire['components'])]}
