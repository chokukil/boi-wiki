"""One local transport file retaining the existing manifest and exact object bytes.

Stored ZIP entries let the browser slice large source files without extraction
or decompression. Packing is not transmission, confirmation or publication.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
import zipfile

from boi_api.app.governed_runtime.local_bundle_contract import LocalBundleManifest
from boi_api.app.governed_runtime.local_bundle_json import LocalJsonDocument
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.knowledge_use_contract import LocalKnowledgeAssessment
from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef
from boi_api.app.governed_runtime.knowledge_content import ContentUnresolvedClassification


class LocalPreparationIncomplete(ValueError):
    def __init__(self, report):
        super().__init__('LOCAL_PREPARATION_INCOMPLETE')
        self.report = report


def source_review_inventory(content):
    """Canonical original inventory, retaining local span tokens until import.

    Cross-checked against the server's unresolved_review_item contract in tests.
    This packaging helper does not import the server's qualification evaluator.
    """
    values = []
    for item in content.get('unresolved', []):
        value = {'meaning_pointer': item.get('meaning_pointer'),
                 'source_spans': item.get('source_spans', []),
                 'reason_code': item['reason_code'], 'description': item['description']}
        if item.get('classification') is not None:
            value['classification'] = ContentUnresolvedClassification.model_validate(
                item['classification']).model_dump(mode='json')
        values.append(value)
    return values


def review_source_scope(manifest, identity, content, item):
    pointer = item.get('meaning_pointer') or ''
    parts = pointer.split('/')
    if len(parts) >= 3 and parts[1] in ('assertions', 'parameters'):
        pointer = '/'.join(parts[:3])
    def overlap(other):
        return pointer == other or pointer.startswith(other + '/') or other.startswith(pointer + '/')
    selected = [(i,b) for i,b in enumerate(content.get('evidence_bindings', [])) if overlap(b['meaning_pointer'])]
    spans = {semantic_digest(s) for s in item.get('source_spans', [])}
    if spans:
        selected = [(i,b) for i,b in selected if semantic_digest(b['span']) in spans]
    bindings = {b.pointer: b for b in manifest.references if b.object_id == identity and b.kind == 'source_span'}
    objects = {o.object_id: o for o in manifest.objects}
    local, external = set(), []
    for i,binding in selected:
        ref = bindings.get(f'/content/evidence_bindings/{i}/span')
        if ref is None:
            external.append(binding['span'])
        else:
            obj = objects[ref.target_object_id]
            local.add((obj.object_id, obj.byte_digest, binding['field_locator']))
    return local, external, spans - {semantic_digest(b['span']) for _,b in selected}


def source_fields(keys):
    return [{'source_object_id': k[0], 'source_byte_digest': k[1], 'field_locator': k[2]} for k in sorted(keys)]


def use_preparation(manifest, object_bytes):
    """Compare declared requirements with supplied opinions, never judge meaning.

    This also runs on the exact bytes at packing, so an edited presentation
    report cannot authorize transport. Draft assembly remains possible while
    an agent reads its source and prepares the still-missing review.
    """
    proposals, opinions, gaps, uses, inventories = {}, {}, [], [], []
    existing = set(manifest.existing_revisions)
    for obj in manifest.objects:
        if obj.purpose not in ('native_proposal', 'check_evidence'):
            continue
        value = LocalJsonDocument(object_bytes[obj.object_id], require_content=False).value
        if obj.purpose == 'native_proposal':
            proposals[obj.object_id] = value
        elif value.get('contract_version') == 'boi/local-knowledge-assessment@1':
            opinion = LocalKnowledgeAssessment.model_validate(value)
            target = opinion.target_object_id
            if target in opinions:
                raise ValueError('LOCAL_AUTHORING_DUPLICATE_ASSESSMENT')
            if target not in object_bytes or opinion.target_byte_digest != byte_digest(object_bytes[target]):
                raise ValueError('LOCAL_PREPARATION_ASSESSMENT_BYTES_CHANGED')
            for item in opinion.input_objects:
                if item.object_id not in object_bytes or item.byte_digest != byte_digest(object_bytes[item.object_id]):
                    raise ValueError('LOCAL_PREPARATION_ASSESSMENT_BYTES_CHANGED')
            opinions[target] = opinion
        # Exact structural revision references are contracts, not text matches.
        pending = [('', value)]
        while pending:
            pointer, item = pending.pop()
            if isinstance(item, dict):
                if (set(item) == {'ref', 'revision_digest'} and isinstance(item['ref'], str)
                        and item['ref'].startswith('KnowledgeRevision:')):
                    revision = RevisionRef.model_validate(item)
                    if revision not in existing:
                        gaps.append({'object_id': obj.object_id, 'pointer': pointer,
                            'reason_code': 'LOCAL_PREPARATION_EXISTING_REVISION_UNDECLARED',
                            'revision': revision.model_dump(mode='json')})
                else:
                    pending.extend((pointer + '/' + str(k).replace('~', '~0').replace('/', '~1'), v)
                                   for k, v in item.items())
            elif isinstance(item, list):
                pending.extend((pointer + '/' + str(i), v) for i, v in enumerate(item))
    for identity, proposal in proposals.items():
        content = proposal.get('content', {})
        contracts = content.get('use_contracts', [])
        opinion = opinions.get(identity)
        if opinion is not None:
            # The server compares the opinion against required native
            # dependencies, not every historical ref appearing in a read.
            # Symbolic local dependencies are bound through input_objects.
            required_native = set()
            for dependency in proposal.get('draft', {}).get('dependencies', []):
                revision = dependency.get('revision')
                if (dependency.get('required', True) and isinstance(revision, dict)
                        and set(revision) == {'ref', 'revision_digest'}
                        and isinstance(revision['ref'], str)
                        and revision['ref'].startswith('KnowledgeRevision:')):
                    required_native.add(RevisionRef.model_validate(revision))
            supplied_native = set(opinion.existing_revisions)
            if supplied_native != required_native:
                gaps.append({'object_id': identity,
                    'reason_code': 'LOCAL_PREPARATION_ASSESSMENT_EXISTING_REVISION_CLOSURE_CHANGED',
                    'missing_revisions': [r.model_dump(mode='json') for r in
                        sorted(required_native - supplied_native, key=lambda r: r.ref)],
                    'extra_revisions': [r.model_dump(mode='json') for r in
                        sorted(supplied_native - required_native, key=lambda r: r.ref)],
                    'basis': 'required native draft dependencies; preserve history separately'})
        supplied = {u.purpose: u for u in opinion.uses} if opinion else {}
        original_inventory = source_review_inventory(content)
        required_inventory_digest = semantic_digest(original_inventory)
        inventory_items = []
        for index, item in enumerate(original_inventory):
            local, external, missing_spans = review_source_scope(manifest, identity, content, item)
            inventory_items.append({'index': index, 'item_digest': semantic_digest(item),
                'required_fields': source_fields(local), 'external_source_binding_count': len(external)})
            if missing_spans:
                gaps.append({'object_id': identity, 'unresolved_index': index,
                    'reason_code': 'LOCAL_PREPARATION_UNRESOLVED_SOURCE_SPAN_UNBOUND'})
        if any(c['purpose'] in ('filter', 'traverse', 'formula_input') for c in contracts):
            inventories.append({'object_id': identity, 'inventory_digest': required_inventory_digest,
                'items': inventory_items, 'basis': 'exact_original_proposal_before_server_reference_replacement'})
        for contract in contracts:
            purpose, roots = contract['purpose'], contract['required_meaning_pointers']
            entry = {'object_id': identity, 'purpose': purpose, 'required_meaning_pointers': roots}
            if purpose not in manifest.intended_uses:
                gaps.append({**entry, 'reason_code': 'LOCAL_PREPARATION_USE_NOT_DECLARED'})
            review = supplied.get(purpose)
            if review is None:
                gaps.append({**entry, 'reason_code': 'LOCAL_PREPARATION_USE_REVIEW_MISSING'})
                uses.append({**entry, 'review_state': 'missing', 'judgment_labels': {}})
                continue
            if list(review.requested_pointers) != roots:
                gaps.append({**entry, 'reason_code': 'LOCAL_PREPARATION_REVIEW_SCOPE_MISMATCH'})
            required_review = {'filter': 'boi/source-statement-review@1',
                               'traverse': 'boi/source-relation-review@1'}.get(purpose)
            context_parameters={f'/parameters/{i}' for i,p in enumerate(content.get('meaning',{}).get('parameters',[]))
                                if p.get('calculation_context') is not None}
            if purpose=='formula_input' and context_parameters.intersection(roots):
                required_review='boi/source-formula-review@1'
            source_review=review.formula_review if purpose=='formula_input' else review.statement_review
            if (purpose=='filter' and source_review is not None
                    and source_review.contract_version=='boi/source-statement-review@2'):
                required_review='boi/source-statement-review@2'
            if required_review and (source_review is None
                    or source_review.contract_version != required_review):
                gaps.append({**entry, 'reason_code': 'LOCAL_PREPARATION_SOURCE_REVIEW_MISSING',
                             'required_review_contract': required_review})
            if source_review is not None:
                statement = source_review
                indexes = {j.index for j in statement.items}
                if statement.inventory_digest != required_inventory_digest or indexes != set(range(len(original_inventory))):
                    gaps.append({**entry, 'reason_code': 'LOCAL_PREPARATION_REVIEW_INVENTORY_CHANGED',
                        'expected_inventory_digest': required_inventory_digest,
                        'required_indexes': list(range(len(original_inventory)))})
                for judgment in statement.items:
                    address = {'object_id': identity, 'purpose': purpose, 'unresolved_index': judgment.index}
                    if judgment.index >= len(original_inventory):
                        continue
                    item = original_inventory[judgment.index]
                    if judgment.item_digest != semantic_digest(item):
                        gaps.append({**address, 'reason_code': 'LOCAL_PREPARATION_REVIEW_ITEM_CHANGED',
                                     'expected_item_digest': semantic_digest(item)})
                    required, external, _ = review_source_scope(manifest, identity, content, item)
                    observed = {(q.source_object_id, q.source_byte_digest, q.field_locator)
                                for q in judgment.evidence if q.existing_source is None}
                    if required - observed:
                        gaps.append({**address, 'reason_code': 'LOCAL_PREPARATION_REVIEW_SOURCE_CLOSURE_MISSING',
                                     'fields': source_fields(required - observed)})
                    if observed - required:
                        gaps.append({**address, 'reason_code': 'LOCAL_PREPARATION_REVIEW_SOURCE_OUTSIDE_SCOPE',
                                     'fields': source_fields(observed - required)})
            uses.append({**entry, 'review_state': 'opinion_present',
                'judgment_labels': dict(sorted(Counter(j.label for j in review.judgments).items())),
                'source_inventory_review_present': source_review is not None,
                'source_meaning_status': 'not_decided_by_local_checks'})
    return {'contract_version': 'boi/local-use-preparation@1',
        'status': 'incomplete' if gaps else 'reviews_present', 'uses': uses, 'gaps': gaps,
        'source_review_inventories': inventories,
        'qualification_granted': False, 'current_authority_verified': False,
        'external_identity_targets_verified': False, 'source_semantic_coverage_complete': False,
        'next_action': 'Complete the listed exact declarations/reviews, retaining unsupported or ambiguous opinions.'
            if gaps else 'Submit these exact bytes for current server checks and purpose-specific qualification.',
        'limits': ['Opinion presence is not positive qualification or source truth.',
                   'Source absence, ambiguity and unsupported interpretation require explicit source review; they are not inferred here.',
                   'Existing identity targets, revision contents and current rights still require official server checks.']}


def pack_bundle(directory, destination):
    directory, destination = Path(directory), Path(destination)
    manifest_bytes = (directory / 'manifest.json').read_bytes()
    manifest = LocalBundleManifest.model_validate_json(manifest_bytes)
    if semantic_digest(LocalJsonDocument(manifest_bytes, require_content=False).value) != manifest.digest:
        raise ValueError('LOCAL_ARCHIVE_COMPLETE_MANIFEST_REQUIRED')
    if not destination.name.endswith('.boi-bundle.zip'):
        raise ValueError('LOCAL_ARCHIVE_FILENAME_REQUIRED')
    # Validate all objects before creating any output. No knowledge rewriting,
    # JSON reserialization, source expansion or semantic opinion takes place.
    objects = []
    for obj in manifest.objects:
        path = directory / (obj.object_id + '.blob')
        if path.is_symlink() or not path.is_file() or path.stat().st_size != obj.byte_length:
            raise ValueError('LOCAL_ARCHIVE_OBJECT_CHANGED')
        if byte_digest(path.read_bytes()) != obj.byte_digest:
            raise ValueError('LOCAL_ARCHIVE_OBJECT_CHANGED')
        objects.append((obj, path))
    readiness = use_preparation(manifest, {obj.object_id: path.read_bytes() for obj, path in objects})
    if readiness['gaps']:
        raise LocalPreparationIncomplete(readiness)
    with destination.open('xb') as handle:
        destination.chmod(0o600)
        with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            archive.writestr('manifest.json', manifest_bytes)
            for obj, path in objects:
                # Recheck the exact bytes being written against edits during packing.
                raw = path.read_bytes()
                if len(raw) != obj.byte_length or byte_digest(raw) != obj.byte_digest:
                    raise ValueError('LOCAL_ARCHIVE_OBJECT_CHANGED_DURING_PACK')
                archive.writestr('objects/' + obj.object_id + '.blob', raw)
    return {'contract_version': 'boi/local-transport-archive@1', 'path': str(destination),
            'manifest_digest': manifest.digest, 'objects': len(objects),
            'bytes': destination.stat().st_size, 'local_only': True,
            'use_preparation': readiness,
            'confirmation_recorded': False, 'publication_committed': False}
