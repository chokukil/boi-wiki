"""Official bounded local publication over real server admission and recovery."""
import uuid

from .local_publication_admission import LocalPublicationAdmission
from .local_publication_state import UNITS, unit_key, committed_unit
from .local_publication_units import LocalPublicationUnits
from .local_bundle_snapshot import with_bundle_snapshot
from .knowledge_publication import PublicationOutcomeUnknown


class LocalPublicationBridge:
    def __init__(self, importer, spaces, projection, *, clock=None):
        self.importer, self.service, self.store = importer, importer.service, importer.store
        self.admission = LocalPublicationAdmission(importer)
        self.units = LocalPublicationUnits(importer, spaces, projection,
            authorize_unit=self.admission, clock=clock)

    @with_bundle_snapshot
    def preflight(self, *, authorization, bundle_ref, unit_id):
        current = self.units.prepare_unit(authorization=authorization, bundle_ref=bundle_ref, unit_id=unit_id, refresh=True)
        row, unit, _, _ = self.units._context(authorization, bundle_ref, unit_id)
        _, impact = self.admission.inspect(authorization, row, unit)
        return {'bundle_ref': bundle_ref, 'unit_id': unit_id,
            'publication_digest': current['publication_digest'], 'impact': impact,
            'previous_preparation_ref': current.get('previous_preparation_ref'),
            'requires_new_confirmation': False,
            'capacity': self.units.preflight_unit(authorization=authorization, bundle_ref=bundle_ref, unit_id=unit_id),
            'publication_committed': False, 'query_ready': False,
            'note': 'Snapshot only; publish rechecks current inputs, decisions and authority.'}

    @with_bundle_snapshot
    def publish(self, *, authorization, bundle_ref, unit_id, publication_digest):
        # Require the exact operation produced by preflight. A lost response
        # cannot create a new publication, unit, or consent intent on retry.
        row = self.service._read(authorization, bundle_ref)
        current = self.store.get(UNITS, unit_key(bundle_ref, unit_id))
        if (not current or current['publication_digest'] != publication_digest
                or current['binding']['manifest_digest'] != row['manifest_digest']):
            raise ValueError('LOCAL_PUBLICATION_EXACT_PREFLIGHT_REQUIRED')
        operation = self.store.get('knowledge_projection_outbox', publication_digest)
        # An unexpired execution owns its writer token. Concurrent HTTP calls
        # report it; they do not share a caller-selected worker identity.
        if operation:
            coordinator = self.units.coordinator(authorization=authorization, bundle_ref=bundle_ref, unit_id=unit_id)
            scope = self.store.get('knowledge_publication_scopes', operation['scope_id'])
            active = scope and scope['active_operation'] == publication_digest
            if active and operation['lease_until'] > coordinator.clock():
                unit = next((u for u in (row['preview'].get('publication_plan') or {}).get('units', [])
                    if u['unit_id'] == unit_id), None)
                if unit and committed_unit(self.store,row,unit,current):
                    return self._progress(bundle_ref, unit_id, publication_digest, 'published_finalizing')
                return self._progress(bundle_ref, unit_id, publication_digest, 'in_progress')
        try:
            receipt = self.units.run_unit(authorization=authorization, bundle_ref=bundle_ref,
                unit_id=unit_id, writer_id='wiki-publication:' + uuid.uuid4().hex,
                expected_publication_digest=publication_digest)
        except PublicationOutcomeUnknown:
            return self._progress(bundle_ref, unit_id, publication_digest, 'outcome_unknown')
        state = 'aborted' if receipt.get('status') == 'aborted' else 'published'
        result = {**self._progress(bundle_ref, unit_id, publication_digest, state), 'receipt': receipt,
            'confirmation_context':self.service.confirmation_context(row)}
        if state == 'published':
            from .knowledge_published_read import document_url
            from .semantic_binding_contract import RevisionRef, semantic_digest
            changes = {c['object_id']:c for c in row['manifest']['changes']}
            result['published_items'] = []
            lookup=[]
            from .domain_asset_store import DomainAssetStore
            def space_access(revision,purpose):
                record=self.service.assets.ledger.read(revision.ref)
                value=record.payload
                stable='domain-asset-head:'+semantic_digest([value['employee_id'],value['namespace'],value['logical_id']])
                return self.units.spaces.authorize(actor_id=authorization.principal,
                    stable_id=stable,revision=revision.model_dump(mode='json'),purpose=purpose)
            lookup_assets=DomainAssetStore(self.service.assets.intake,space_access=space_access)
            lookup_assets.embedding_client=self.service.assets.embedding_client
            for object_id, ref in current['revisions'].items():
                change = changes[object_id]
                stable_id = 'domain-asset-head:' + semantic_digest([
                    row['employee_id'],change['namespace'],change['logical_id']])
                result['published_items'].append({'object_id':object_id, 'stable_id':stable_id,
                    'title':change['title'], 'revision':ref,
                    **({'document_url':document_url(RevisionRef.model_validate(ref))}
                        if change['kind'] == 'definition' else {})})
                # Native heads are committed. Finish only these exact revisions;
                # lookup failure cannot roll back publication or grant authority.
                from .catalog_search_index import update_publication
                try:
                    prepared=update_publication(lookup_assets, authorization, RevisionRef.model_validate(ref))
                    lookup.append({'revision':ref,'state':'prepared' if prepared is not None else 'superseded'})
                except Exception:
                    lookup.append({'revision':ref,'state':'deferred',
                        'reason_code':'DOMAIN_SEARCH_PUBLICATION_FINISH_DEFERRED'})
            result['candidate_lookup']={'state':'prepared' if all(v['state']=='prepared' for v in lookup) else 'deferred',
                'revisions':lookup,'recovery':'replay_exact_committed_publication',
                'semantic_quality':'not_evaluated'}
        return result

    @staticmethod
    def _progress(bundle_ref, unit_id, digest, state):
        return {'bundle_ref': bundle_ref, 'unit_id': unit_id, 'publication_digest': digest,
            'state': state, 'publication_committed': state in ('published','published_finalizing'), 'query_ready': False,
            'next_action': 'status_then_resume_same_publication' if state in ('in_progress','outcome_unknown','published_finalizing')
                else 'read_published_knowledge' if state == 'published' else 'inspect_aborted_publication',
            'requires_new_confirmation': False}

    def resume(self, *, authorization, bundle_ref, unit_id, publication_digest):
        self.service._read(authorization, bundle_ref)
        if self.store.get('knowledge_projection_outbox', publication_digest) is None:
            raise ValueError('LOCAL_PUBLICATION_EXISTING_OPERATION_REQUIRED')
        return self.publish(authorization=authorization, bundle_ref=bundle_ref,
            unit_id=unit_id, publication_digest=publication_digest)
