"""Server admission for confirmed native units, with attributed use decisions.

This checks the current immutable inputs and decisions; it does not run an LLM,
grant semantic truth, or turn unexamined related knowledge into zero impact.
"""
import json

from .knowledge_content import decode_knowledge_content
from .knowledge_definition_checks import required_definition_capabilities
from .knowledge_profile_projector import native_identity
from .knowledge_use_contract import typed_use_closure
from .knowledge_use_decisions import QUALIFICATIONS, decision_key, predecessor, require_current
from .local_bundle_checks import LocalBundleChecks, CHECKS
from .local_knowledge_qualification import LocalKnowledgeQualification, qualification_policy
from .local_publication_units import UnitAuthority
from .native_knowledge_checks import shipped_checker_release
from .semantic_binding_contract import RevisionRef, semantic_digest
from ..v2.atomic_store_contract import AtomicWrite


class LocalPublicationAdmission:
    def __init__(self, importer):
        self.importer = importer
        self.checks = LocalBundleChecks(importer)
        self.uses = LocalKnowledgeQualification(importer, prepare_queries=False)
        self.store = importer.store

    def inspect(self, auth, row, unit):
        handles = self.checks._handles(row)
        read = self.checks._reader(auth, row, handles)
        release, policy = shipped_checker_release(), qualification_policy()
        changes = {c['object_id']: c for c in row['manifest']['changes']}
        fences, qualifications, items = [], [], []
        service=self.importer.service
        impact_ref=(row.get('confirmation') or {}).get('impact_ref')
        if impact_ref:
            if service.impact_factory is None:
                raise ValueError('LOCAL_BUNDLE_IMPACT_BACKEND_REQUIRED')
            fences.extend(service.impact_factory(service).confirmation_fences(
                authorization=auth,row=row,impact_ref=impact_ref))
        for object_id in unit['object_ids']:
            change, handle = changes[object_id], handles[object_id]
            correction_policy, correction_record = None, None
            if change['operation'] != 'create':
                from .knowledge_content_correction import correction_basis
                correction_policy, correction_record, fence = correction_basis(self.importer.service.assets, auth,
                    change, row['manifest']['target_space'])
                if not impact_ref:
                    raise ValueError('KNOWLEDGE_CONTENT_CORRECTION_IMPACT_REQUIRED')
                fences.append(fence)
                from .knowledge_document_feedback import COLLECTION, correction_feedback_rows
                from .local_bundle_contract import LocalBundleChange
                fences.extend(AtomicWrite(COLLECTION,ref.ref,value,value) for ref,value in correction_feedback_rows(
                    self.importer.service.assets,auth,LocalBundleChange.model_validate(change),correction_policy))
            binding = self.checks._input(row, object_id, handle, release)
            key = 'native-mechanical-execution:' + semantic_digest(binding)
            saved = self.store.get(CHECKS, key)
            if not saved or saved.get('state') != 'completed':
                raise ValueError('LOCAL_PUBLICATION_COMPLETED_SERVER_CHECK_REQUIRED')
            self.checks._current_result(read, change, key, saved, binding)
            report = self.checks._receipt(saved, binding)
            record, asset = read(handle.revision)
            content = decode_knowledge_content(json.loads(asset.content_json)) if asset.kind == 'definition' else None
            required = ({'native_revision_and_required_references','profile_declaration'}
                if change['kind'] == 'profile' else required_definition_capabilities(content))
            if change['kind'] == 'pack':
                from .local_native_review import CONTRACT, CAPABILITY
                if change.get('observation_contract') != CONTRACT:
                    raise ValueError('LOCAL_BUNDLE_REVIEW_CONTRACT_REQUIRED')
                required = {'native_revision_and_required_references', CAPABILITY}
            passed = {c['capability'] for c in report['checks'] if c['outcome'] == 'satisfied'}
            if (report['outcome'] != 'completed' or not required <= passed
                    or any(c['outcome'] == 'violated' for c in report['checks'])):
                raise ValueError('LOCAL_PUBLICATION_MECHANICAL_PROPERTIES_REQUIRED')
            fences.append(AtomicWrite(CHECKS, key, saved, saved))
            if correction_policy:
                from .knowledge_content_correction import correction_source_closure
                correction_source_closure(correction_policy, correction_record, record,
                    content=content, read_span=self.importer.intake.ledger.read)
            contracts = {u.purpose: u for u in content.use_contracts} if content else {}
            decisions = []
            for purpose in sorted(set(row['manifest']['intended_uses']) & set(contracts)):
                contract = contracts[purpose]
                scope = typed_use_closure(content, contract)
                decision, fence, reference = self._decision(auth, row, object_id, handle,
                    record, saved, purpose, scope, policy)
                fences.append(fence)
                qualifications.append(reference)
                decisions.append({'purpose': purpose, 'status': decision['status'],
                    'qualification_ref': reference.model_dump(mode='json'),
                    'roots': decision['roots'], 'limitations': decision['limitations'],
                    'reasons': decision['reasons'], 'scientific_truth_proven': False})
            if content:
                decisions.extend({'purpose': purpose, 'status': 'unsupported',
                    'reasons': ['DECLARED_USE_CONTRACT_REQUIRED']}
                    for purpose in sorted(set(row['manifest']['intended_uses']) - {'read'} - set(contracts)))
            items.append({'object_id': object_id, 'title': record.payload['title'],
                'stable_id': native_identity(record), 'revision': handle.revision.model_dump(mode='json'),
                'previous_revision': change['previous_revision'], 'operation': change['operation'],
                **({'correction':change['correction']} if change.get('correction') else {}),
                'mechanical_check_ref': saved['check_ref'], 'uses': decisions,
                'dependencies': [d.model_dump(mode='json') for d in asset.dependencies],
                'conflicts_with': [r.model_dump(mode='json') for r in asset.conflicts_with],
                'supersedes': [r.model_dump(mode='json') for r in asset.supersedes]})
        fences.extend(read.identity_fences())
        if release != shipped_checker_release() or policy != qualification_policy():
            raise ValueError('LOCAL_PUBLICATION_REGISTERED_POLICY_CHANGED')
        return UnitAuthority(tuple(fences), tuple(qualifications)), {
            'unit_id': unit['unit_id'], 'items': items,
            'target_space': row['manifest']['target_space'],
            'scope': 'confirmed_native_changes_and_declared_references',
            'existing_identity_replacements': sum(i['operation'] == 'revise' for i in items),
            'related_semantic_conflicts': 'not_evaluated',
            'incoming_dependency_coverage': ('reviewed_visible_native_direct_references'
                if impact_ref else 'new_identities_only'),
            'confirmed_impact_ref': impact_ref,
            'transitive_impact': 'not_evaluated',
            'legacy_outside_spaces': 'not_evaluated',
            'outside_declared_reference_coverage': 'not_evaluated',
            'publication_granted': False, 'semantic_truth_proven': False}

    def _decision(self, auth, row, object_id, handle, record, mechanical, purpose, scope, policy):
        key = decision_key(handle.revision, purpose)
        entry = self.store.get(QUALIFICATIONS, key)
        if entry is None:
            raise ValueError('LOCAL_PUBLICATION_CURRENT_USE_DECISION_REQUIRED')
        reference = RevisionRef.model_validate(entry['qualification_ref'])
        receipt = predecessor(self.importer.intake.ledger, reference,
            revision=handle.revision, purpose=purpose, stable_id=native_identity(record))
        require_current(receipt, entry)
        value = receipt.payload
        imported = self.importer._saved(row, object_id)
        expected = {'bundle_ref': row['bundle_ref'], 'manifest_digest': row['manifest_digest'],
            'confirmation_ref': self.importer.scope(row), 'policy_digest': auth.policy_digest,
            'qualification_policy': policy, 'qualification_policy_digest': semantic_digest(policy),
            'source_manifest_digest': record.payload['source_manifest_digest'],
            'mechanical_check_ref': mechanical['check_ref'],
            'checker_release_digest': mechanical['input']['checker_release_digest'],
            'native_import_receipt_ref': imported['receipt_ref'],
            'scope_digest': scope['scope_digest'], 'roots': list(scope['roots']), 'closure': list(scope['closure'])}
        if any(value.get(k) != v for k, v in expected.items()):
            raise ValueError('LOCAL_PUBLICATION_USE_DECISION_BINDING_CHANGED')
        assessment, obj, _ = self.uses._assessment(auth, row, value['assessment_object_id'])
        if (assessment.target_object_id != object_id or obj['byte_digest'] != value['assessment_byte_digest']
                or purpose not in {u.purpose for u in assessment.uses}
                or value['provenance']['authenticated_principal'] != auth.principal
                or value['status'] not in ('usable_with_limits', 'not_qualified')):
            raise ValueError('LOCAL_PUBLICATION_USE_DECISION_BINDING_CHANGED')
        # A negative decision remains negative after publication. Admission is
        # not a second, broader qualification of the document or its dependencies.
        return value, AtomicWrite(QUALIFICATIONS, key, entry, entry), reference

    def __call__(self, auth, row, unit):
        return self.inspect(auth, row, unit)[0]
