"""Request-local source context inside an already admitted native query.

This is not a generic asset-read fallback. Only server-produced native input and
the connection's currently reviewed definitions are consumed. No new source
projection, qualification, policy alias, or public citation grant is created.
"""
import json

from ..governed_runtime.domain_asset_store import DomainAssetStore
from ..governed_runtime.native_observation import _json
from ..governed_runtime.semantic_authority import NativeProcessReviewAuthority
from ..governed_runtime.semantic_binding_contract import semantic_digest
from ..governed_runtime.source_envelope import byte_digest
from ..governed_runtime.task_knowledge import TaskAssetRevision


MAX_DEFINITIONS = 16
MAX_SOURCES = 16
MAX_ITEM_BYTES = 64 * 1024
# A reviewed relation can carry several independently complete child meanings.
# Keep a bounded whole-response budget while allowing their exact closure;
# each returned node and source field still has its own 64 KiB limit.
MAX_CONTEXT_BYTES = 256 * 1024


def _encoded_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                         allow_nan=False).encode('utf-8'))


def _selected_revisions(host, bundle, native_input):
    authority = bundle.reviewed_definition_authority
    if (authority is None or authority.principal != host.authorization.principal
            or bundle.principal_id != host.authorization.principal
            or host.connection.scope.principal != host.authorization.principal
            or authority.review_revision != host.connection.review_revision
            or native_input.reviewed_definition_authority != authority):
        raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_MISMATCH')
    reviewed = {r.ref: r for r in authority.definition_revisions}
    entries = {e.entry_id: e for e in bundle.domain_entries}
    selected = set()
    for item in native_input.logical_context:
        entry = entries.get(item.entry_id)
        if (entry is None or item.revision_digest != entry.revision_digest
                or tuple(item.evidence_resources) != tuple(entry.evidence_resources)):
            raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_MISMATCH')
        for ref in item.evidence_resources:
            if ref == authority.review_revision.ref:
                continue
            if ref not in reviewed:
                raise ValueError('NATIVE_QUERY_DEFINITION_NOT_IN_PROFILE')
            selected.add(ref)
    if len(selected) > MAX_DEFINITIONS:
        raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_LIMIT')
    return authority, [reviewed[ref] for ref in sorted(selected)]


def _scoped_definition(asset, content, authority, source_rows, intake, auth):
    """Reuse recorded field and meaning-closure readers, without new spans."""
    from ..governed_runtime.source_field_projection import SourceFieldProjectionService
    from .native_definition_sources import project_definition_evidence
    from agent_kit.python.boi_process_answer_v2 import _meaning_evidence, _MeaningReadState

    roots = tuple(authority.selected_target_pointers)
    permitted = set(roots) | set(authority.dependency_target_pointers)
    if not roots or len(authority.definition_revisions) != 1:
        raise ValueError('NATIVE_QUERY_DEFINITION_SELECTION_REQUIRED')
    anchors = {}
    for binding in project_definition_evidence(content, [], ''):
        evidence = binding['evidence']
        if evidence.get('span_ref'):
            anchors.setdefault(evidence['source_revision_digest'], evidence['span_ref'])
    if not anchors:
        raise ValueError('NATIVE_QUERY_SOURCE_ANCHOR_REQUIRED')
    projector = SourceFieldProjectionService(intake)
    indexed = {}
    for row in source_rows:
        source = row['reference']
        anchor = anchors.get(source['digest'])
        if anchor is None:
            # A definition may retain dependency context sources that no
            # selected meaning cites. Keep their authorized source envelope
            # in the response, but never project fields or create a citation
            # from the source label alone.
            continue
        restored = projector.restore_projection_from_span(
            authorization=auth, reference=source, span_ref=anchor)
        indexed[source['digest']] = {'source': source,
            'fields': {f['field_locator']: f for f in restored['fields']}}
    state = _MeaningReadState(indexed)
    graph = []
    for root in roots:
        for node in _meaning_evidence(asset, root, indexed, assets={asset.revision: asset},
                                      _read_state=state):
            if (node['target_pointer'] not in permitted
                    or node.get('asset_revision', asset.revision.model_dump(mode='json'))
                    != asset.revision.model_dump(mode='json')):
                raise ValueError('NATIVE_QUERY_DEFINITION_CLOSURE_MISMATCH')
            if node not in graph:
                graph.append(node)
    fields = {}
    for node in graph:
        for binding in node['source_bindings']:
            field = indexed[binding['source_revision_digest']]['fields'][binding['field_locator']]
            key = (binding['source_revision_digest'], binding['span_ref'])
            if field['span_ref'] != binding['span_ref']:
                raise ValueError('NATIVE_QUERY_SOURCE_BINDING_MISMATCH')
            fields[key] = {k: field[k] for k in ('span_ref', 'field_locator', 'record_locator',
                'content_digest', 'field_state', 'value_kind', 'character_count', 'text') if k in field}
            if 'structural_metadata' in field:
                fields[key]['structural_metadata'] = field['structural_metadata']
    return {'selection_scope': 'reviewed_nodes_and_dependencies',
        'roots': list(roots), 'dependency_pointers': list(authority.dependency_target_pointers),
        'nodes': graph}, fields


def read_query_definition_context(host, bundle, native_input):
    """Return bounded exact definition/source content under this connection.

The caller is NativeQueryHost.prepare after _read_bundle, never a public request
containing refs or authority. The final _current fence is mandatory, even for
an empty retrieval. Whole-definition reviews have no invented node selection;
their exact selected documents and original source text remain attributed data.
"""
    authority, revisions = _selected_revisions(host, bundle, native_input)
    auth = host._source_authorization()
    if (auth.principal != host.authorization.principal
            or auth.policy_digest != authority.acl_policy_digest):
        raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_MISMATCH')
    intake = host.work.intake
    assets = getattr(host.work, 'assets', None) or DomainAssetStore(intake)
    source_cache, definitions, selected_fields = {}, [], {}
    scoped = isinstance(authority, NativeProcessReviewAuthority)
    for revision in revisions:
        stored = assets.read(authorization=auth, revision=revision, lane='provisional')
        asset = TaskAssetRevision.model_validate(stored['asset'])
        if asset.revision != revision or asset.kind != 'definition':
            raise ValueError('NATIVE_QUERY_DEFINITION_NOT_IN_PROFILE')
        if not scoped and len(asset.content_json.encode('utf-8')) > MAX_ITEM_BYTES:
            raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_LIMIT')
        content = _json(asset.content_json)
        sources = []
        for reference in stored['sources']:
            key = semantic_digest(reference)
            if key not in source_cache:
                if len(source_cache) >= MAX_SOURCES:
                    raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_LIMIT')
                # The existing source reader checks owner, exact policy, rights,
                # envelope role/digest and bytes. Continuity was checked above.
                raw = intake.resolve_bytes(authorization=auth, reference=reference)
                if not scoped and len(raw) > MAX_ITEM_BYTES:
                    raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_LIMIT')
                artifact = intake.ledger.read(reference['artifact_ref'])
                if byte_digest(raw) != reference['digest']:
                    raise ValueError('NATIVE_QUERY_SOURCE_BINDING_MISMATCH')
                try:
                    text = raw.decode('utf-8')
                except UnicodeDecodeError:
                    raise ValueError('NATIVE_QUERY_SOURCE_TEXT_REQUIRED') from None
                source_cache[key] = {'reference': reference,
                    'media_type': artifact.payload['media_type'], 'byte_length': len(raw),
                    'content_digest': byte_digest(raw), 'text': text,
                    'representation': 'original_utf8_source', 'complete_source': True}
            sources.append(source_cache[key])
        selection = ({'selection_scope': 'exact_whole_definition_review', 'content': content}
            if not scoped else None)
        if scoped:
            selection, fields = _scoped_definition(asset, content, authority, sources, intake, auth)
            # A reviewed collection is not one delivery item. Bound each exact
            # returned meaning and complete source field, then the entire
            # assembled response below. Unselected source/definition siblings
            # do not consume the inline item budget or authorize truncation.
            if any(_encoded_size(item) > MAX_ITEM_BYTES
                   for item in (*selection['nodes'], *fields.values())):
                raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_LIMIT')
            selected_fields.update(fields)
        definitions.append({'revision': revision.model_dump(mode='json'),
            'content_digest': asset.content_digest, 'title': stored.get('title'),
            'sources': [semantic_digest(row['reference']) for row in sources], **selection})
    source_values = []
    for key, row in source_cache.items():
        if scoped:
            row = {k: v for k, v in row.items() if k not in ('text', 'representation', 'complete_source')}
            row.update(representation='complete_fields_for_reviewed_meaning_closure',
                complete_source=False, fields=[value for (digest, _), value in selected_fields.items()
                                               if digest == row['reference']['digest']])
        source_values.append({'source_key': key, **row})
    result = {'contract_version': 'boi/native-query-definition-context@1',
        'connection_id': host.connection.connection_id, 'bundle_digest': bundle.bundle_digest,
        'profile_revision': host.connection.profile_revision.model_dump(mode='json'),
        'review_revision': authority.review_revision.model_dump(mode='json'),
        'definitions': definitions, 'sources': source_values,
        'limits': {'max_definitions': MAX_DEFINITIONS, 'max_sources': MAX_SOURCES,
            'max_item_bytes': MAX_ITEM_BYTES, 'max_context_bytes': MAX_CONTEXT_BYTES,
            'overflow_behavior': 'reject_without_truncation', 'byte_basis': 'UTF-8'},
        'source_access_basis': 'current_connection_and_exact_reviewed_definitions',
        'source_evidence_binding_verified': False,
        'source_evidence_note': 'Original evidence declarations are preserved. This read does not '
            'turn legacy source labels or a located quotation into semantic support.',
        'citation_access': 'in_response_only; generic_definition_URL_access_is_not_granted',
        'semantic_truth_proven': False, 'equipment_execution': False, 'status': 'PROVISIONAL'}
    if scoped:
        result['limits']['item_byte_scope'] = 'returned_meaning_node_or_complete_source_field'
    if _encoded_size(result) > MAX_CONTEXT_BYTES:
        raise ValueError('NATIVE_QUERY_DEFINITION_CONTEXT_LIMIT')
    # Includes current directory/PAT/source policy, snapshot and exact review/
    # profile/dependency authority. A first successful read cannot replace it.
    host._current(bundle)
    return result
