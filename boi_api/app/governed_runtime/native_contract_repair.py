"""Bounded reconstruction of exact contract metadata for published revisions.

The existing reference-maintenance coordinator owns edit/model-input access,
preimages, CAS, epochs and unknown-response recovery. No source, content, review
or sharing revision is rewritten and no use qualification is created.
"""
import hashlib
import json
from typing import Literal

from .native_reference_repair import NativeReferenceRepair, NativeReferenceRepairRequest
from .native_contract_catalog import contract_catalog_ready, contract_projection


class NativeContractRepairRequest(NativeReferenceRepairRequest):
    contract_version: Literal['boi/native-contract-repair-request@1'] = 'boi/native-contract-repair-request@1'


class NativeContractRepair(NativeReferenceRepair):
    request_model = NativeContractRepairRequest
    version = 'boi/native-contract-repair@1'
    key_prefix = 'native-contract-repair:'
    marker = 'contract_repair_ref'
    digest_field = 'contract_projection_digest'
    coverage = 'exact_outer_and_okf_meaning_contracts_of_requested_published_revisions_only'

    def _read(self, actor_id, revision):
        state = super()._read(actor_id, revision)
        access, record, asset = self.spaces.read(actor_id=actor_id, stable_id=state['identity'],
                                                revision=revision, purpose='model_input')
        if access != state['authority'][1]:
            raise ValueError('KNOWLEDGE_CONTRACT_REPAIR_AUTHORITY_CHANGED')
        state['projection'] = contract_projection(record, asset)
        return state

    def _fingerprints(self, targets):
        table = self.index.store._table('domain_knowledge_assets')
        keys = [self.index.backend.prefix + revision.ref for revision in targets]
        with self.index.store._connection() as connection, connection.transaction():
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            connection.execute("SET LOCAL statement_timeout='5s'")
            contract_catalog_ready(connection, table)
            rows = connection.execute(f'''SELECT item_key,native_contract_digest,
 native_content_contract,native_meaning_contract,
 encode(native_content_contract_key,'hex'),encode(native_meaning_contract_key,'hex')
 FROM {table} WHERE item_key=ANY(%s)''', (keys,)).fetchall()
        return {row[0][len(self.index.backend.prefix):]: dict(zip(
            ('native_digest', 'content_contract', 'meaning_contract', 'content_key', 'meaning_key'), row[1:]))
                for row in rows}

    def _expected_fingerprint(self, state):
        projection = state['projection']; wire = json.loads(projection['contract_projection_wire'])
        def key(value):
            return hashlib.sha256(value.encode()).hexdigest() if value is not None else None
        return {'native_digest': projection[self.digest_field],
                'content_contract': wire['content_contract'], 'meaning_contract': wire['meaning_contract'],
                'content_key': key(wire['content_contract']), 'meaning_key': key(wire['meaning_contract'])}
