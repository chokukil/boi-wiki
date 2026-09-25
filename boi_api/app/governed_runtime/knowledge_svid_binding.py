"""Bind external knowledge-work SVID proposals through the existing native kit.

Accounting selects a source row, not a business identity. Explicit extra source
spans remain proposed context; neither successful binding nor a typed descriptor
is a semantic approval or admission to live calculation.
"""
from __future__ import annotations

import copy
import json

from .domain_asset_store import DomainAssetStore
from .ledger import record_digest
from .semantic_binding_contract import semantic_digest
from .source_field_projection import SourceFieldProjectionService
from .svid_contract import SvidIdentity


_FALSE_AUTHORITY_FIELDS = frozenset((
    'canonical_projection_eligible', 'live_execution_ready', 'live_binding_verified',
    'parameter_catalog_verified', 'semantic_support_verified', 'semantic_relation_verified',
))


def _nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from _nodes(child)


def _read_current_dependency(assets, authorization, revision):
    value = assets.read(authorization=authorization, revision=revision, lane='provisional')
    key = 'domain-asset-head:' + semantic_digest([
        authorization.principal, value['namespace'], value['logical_id']])
    head = assets.store.get('domain_asset_heads', key)
    if not head or head['revision'] != revision.model_dump(mode='json'):
        raise ValueError('SVID_WORK_DEPENDENCY_REVISION_CHANGED')
    return value


def bind_work_svid(content, *, intake, authorization, work, attempt, change, publication_recovery=False,
                   preserve_metadata_content=False, binding_checks=None, binding_dependencies=None):
    """Return a bound candidate, preserving input and writing no source/asset.

    ``attempt.result`` is the exact reserved submission. The work service owns
    its reservation, complete accounting checks and publication fences.
    """
    from agent_kit.python.boi_svid_intake import bind_svid_batch, svid_descriptor_revision

    if not isinstance(content, dict) or content.get('contract_version') != 'boi/svid-native-interpretation@1':
        raise ValueError('SVID_WORK_CONTENT_CONTRACT_REQUIRED')
    value = copy.deepcopy(content)
    assets = DomainAssetStore(intake)
    # Only the work service can select recovery, after reserving the exact body
    # and finding its server-owned publication receipt. Asset create still
    # compares the reconstructed draft to that receipt; completion checks heads.
    read_original = (lambda assets, auth, ref: assets.read(authorization=auth, revision=ref, lane='provisional')) if publication_recovery else _read_current_dependency
    original = (read_original(assets, authorization, change.target_revision)
                if change.operation == 'revise' and change.target_revision is not None else None)
    original_content = json.loads(original['asset']['content_json']) if original else None
    namespace = original['namespace'] if original is not None else work['namespace']
    for node in _nodes(value):
        if any(key in node and node[key] is not False for key in _FALSE_AUTHORITY_FIELDS):
            raise ValueError('SVID_WORK_CALLER_AUTHORITY_NOT_ACCEPTED')
    records = (attempt.get('result') or {}).get('record_outcomes', ())
    matched = [row for row in records if change.change_id in row.get('change_ids', ())]
    if (len(matched) != 1 or matched[0].get('disposition') != 'assetized'
            or matched[0].get('record_locator') not in attempt['record_locators']):
        raise ValueError('SVID_WORK_PRIMARY_RECORD_REQUIRED')
    primary = matched[0]['record_locator']
    try:
        SvidIdentity.model_validate({'namespace': value['identity']['namespace'],
            'model': value['identity']['model']['value'], 'svid': value['identity']['svid']['value']})
    except (KeyError, TypeError, ValueError):
        raise ValueError('SVID_WORK_IDENTITY_VALUE_REQUIRED') from None

    source = attempt['source_ref']
    if source not in work['sources']:
        raise ValueError('SVID_WORK_SOURCE_OUTSIDE_WORK')
    declared = {ref.ref: ref for ref in change.evidence_spans}
    if len(declared) != len(change.evidence_spans):
        raise ValueError('SVID_WORK_EVIDENCE_DUPLICATE')
    if any(record_digest(ref.ref) != ref.revision_digest for ref in change.evidence_spans):
        raise ValueError('SVID_WORK_EVIDENCE_REVISION_MISMATCH')
    projector = SourceFieldProjectionService(intake)
    # The full inventory is server-owned. Extra declared context must belong to
    # this same source, even if its row is outside the current execution unit.
    selection = projector.select_manifest_fields(authorization=authorization, reference=source,
        manifest_ref=attempt['manifest_ref'], span_refs=attempt['source_span_refs'])
    own = selection['record_field_refs'].get(primary, ())
    if not own or not set(own) <= set(attempt['source_span_refs']):
        raise ValueError('SVID_WORK_PRIMARY_RECORD_INCOMPLETE')
    if preserve_metadata_content:
        if (original_content != content or {r['ref'] for r in original['asset']['evidence']} != set(declared)
                or original_content.get('source_record', {}).get('record_locator') != primary):
            raise ValueError('SVID_WORK_METADATA_ORIGINAL_REQUIRED')
    retained_source = bool(original_content and source in original['sources']
        and original_content.get('source_record', {}).get('record_locator') == primary)
    if retained_source:
        from .source_field_compatibility import read_compatible_revision_fields
        # Existing provenance is server-read. A semantic correction does not
        # re-extract its source or silently rewrite historical span identities.
        for key in ('source_record', 'source_record_dependencies', 'extraction_input_digest'):
            if key in value and value[key] != original_content.get(key):
                raise ValueError('SVID_WORK_SOURCE_PROVENANCE_CHANGED')
        own = original_content['source_record']['field_refs']
        retained_context = list(original_content['source_record']['context_refs'])
        for dependency in original_content.get('source_record_dependencies', ()):
            retained_context.extend([*dependency['field_refs'], *dependency['context_refs']])
        context = list(dict.fromkeys(ref for ref in [*retained_context, *declared] if ref not in own))
        reading = read_compatible_revision_fields(projector, authorization=authorization, reference=source,
            manifest_ref=attempt['manifest_ref'], span_refs=[*own, *context], required_records=[(primary, own)])
        if binding_checks is not None:
            binding_checks['source_projection_compatibility'] = reading['source_projection_compatibility']
    else:
        context = [ref for ref in declared if ref not in own]
        reading = projector.read_selected_fields(authorization=authorization, reference=source,
            manifest_ref=attempt['manifest_ref'], span_refs=[*own, *context], required_records=[(primary, own)])
    fields = {field['field_locator']: field for field in reading['fields']}
    if len(fields) != len(reading['fields']):
        raise ValueError('SVID_WORK_FIELD_LOCATOR_AMBIGUOUS')
    for node in _nodes(value):
        if 'field_locator' not in node or 'quote' not in node:
            continue
        field = fields.get(node['field_locator'])
        if field is None or field['span_ref'] not in declared:
            raise ValueError('SVID_WORK_QUOTED_SPAN_NOT_DECLARED')
        expected = {'span_ref': field['span_ref'], 'source_revision_digest': source['digest']}
        if any(node.get(key) is not None and node[key] != actual for key, actual in expected.items()):
            raise ValueError('SVID_WORK_FORGED_SOURCE_REFERENCE')
    # Primary-row evidence anchors the identifier and observation. Model names
    # may explicitly refer to a header, but a sibling row cannot alone identify
    # the SVID or describe this row's observation.
    for core in (value['identity']['svid'], value.get('observation')):
        citations = list(_nodes(core.get('evidence'))) if isinstance(core, dict) else []
        if not any(fields.get(cite.get('field_locator'), {}).get('span_ref') in own for cite in citations):
            raise ValueError('SVID_WORK_PRIMARY_EVIDENCE_REQUIRED')

    annotations = value.get('source_annotations', [])
    if annotations:
        # Existing annotations are exact source context only after the same
        # quote checks. Preserve the full proposal; do not label it a correction.
        annotations = copy.deepcopy(annotations)
        for node in _nodes(annotations):
            if 'field_locator' in node and 'quote' in node:
                node.update(span_ref=fields[node['field_locator']]['span_ref'], source_revision_digest=source['digest'])
    material = {'layout': {'authority': 'uninterpreted_source_structure'},
        'fields': {field['span_ref']: field for field in reading['fields']},
        'records': [{'record_locator': primary, 'field_refs': list(own), 'context_refs': context,
                     'annotations': annotations}]}
    output = {'records': [{'record_locator': primary, 'title': change.title,
                          'interpretation_json': json.dumps(value, ensure_ascii=False)}]}
    bound = bind_svid_batch(output, material, source=source, namespace=namespace)[0]['content']
    if retained_source:
        # The old extraction digest identifies the original extraction input;
        # this correction's exact source checks live in its work result instead.
        if 'extraction_input_digest' in original_content:
            bound['extraction_input_digest'] = original_content['extraction_input_digest']
        if original_content.get('source_record_dependencies'):
            bound['source_record_dependencies'] = copy.deepcopy(original_content['source_record_dependencies'])
        if set(context) == set(original_content['source_record']['context_refs']):
            bound['source_record'] = copy.deepcopy(original_content['source_record'])
    bound['context_selection_authority'] = 'external_agent_proposed'
    bound['source_fidelity'] = 'not_evaluated'

    requirements = copy.deepcopy(original['asset'].get('dependencies', [])) if original else []
    if bound.get('semantic_descriptor') is not None:
        # Reuse the existing typed enrichment validator rather than interpreting
        # quantity/unit names. It requires an existing quantity and exact unit
        # revisions; downstream review and Formula admission remain separate.
        if change.target_revision is None:
            raise ValueError('SVID_WORK_DESCRIPTOR_EXISTING_REVISION_REQUIRED')
        original = original or read_original(assets, authorization, change.target_revision)
        from .svid_contract import native_svid_descriptor
        from .semantic_binding_contract import RevisionRef
        descriptor = native_svid_descriptor(bound['semantic_descriptor'])
        dependency_refs = list(change.dependencies)
        # A correction inherits an unchanged typed use from its exact target.
        # Read it under current rights instead of requiring callers to recreate
        # its dependency envelope. A replaced unit is not inherited this way.
        dependency_refs.extend(RevisionRef.model_validate(d['revision']) for d in requirements
            if d['role'] == 'semantic_unit_definition' and descriptor.unit_semantics == 'declared'
            and d['revision']['revision_digest'] == descriptor.unit_revision_digest)
        dependency_refs.extend(RevisionRef.model_validate(d['revision']) for d in requirements
            if d['role'] == 'semantic_quantity_definition' and descriptor.quantity_kind_ref
            and descriptor.quantity_kind_ref.startswith(d['revision']['ref'] + '#/concepts/'))
        dependencies = [_read_current_dependency(assets, authorization, ref) for ref in dict.fromkeys(dependency_refs)]
        enriched = svid_descriptor_revision(original, bound['semantic_descriptor'],
            source_readings=[reading], unit_assets=dependencies, quantity_assets=dependencies)
        bound['semantic_descriptor'] = json.loads(enriched['content_json'])['semantic_descriptor']
        requirements = enriched['dependencies']
    if binding_dependencies is not None:
        binding_dependencies.extend(requirements)
    # Run the ordinary binder/type checks, then retain the old interpretation,
    # source annotations and extraction provenance for a metadata-only revision.
    return copy.deepcopy(content) if preserve_metadata_content else bound
