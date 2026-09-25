"""Lossless source partitioning, without deciding which text is meaningful.

The caller supplies Wiki-authorized fields and exact, validated quote ranges.
Unselected characters remain evidence; punctuation and substantive text follow
the same path. A complete partition is never semantic coverage or entailment.
"""
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest


def partition_source(evidence, bindings, *, description_fields):
    manifest = evidence['manifest']
    fields = {f['field_locator']: f for f in evidence['fields']}
    expected = {f['field_locator']: f for f in manifest['fields']}
    if (len(fields) != len(evidence['fields']) or len(expected) != len(manifest['fields'])
            or set(fields) != set(expected)):
        raise ValueError('PROCESS_SOURCE_INVENTORY_INCOMPLETE')
    for locator, field in fields.items():
        if any(field.get(k) != v for k, v in expected[locator].items()):
            raise ValueError('PROCESS_SOURCE_INVENTORY_METADATA_MISMATCH')
        if byte_digest(field['text'].encode('utf-8')) != field['content_digest']:
            raise ValueError('PROCESS_SOURCE_INVENTORY_CONTENT_MISMATCH')
    ranges = {locator: [] for locator in fields}
    for binding in bindings:
        locator, start, end = (binding[k] for k in ('field_locator', 'start', 'end'))
        if locator not in fields or not 0 <= start < end <= len(fields[locator]['text']):
            raise ValueError('PROCESS_SOURCE_PARTITION_RANGE_INVALID')
        ranges[locator].append((start, end))
    inventory = []
    for locator, field in sorted(fields.items()):
        # Merge overlapping/touching intervals; complement is exact even for
        # repeated quotes, Unicode, whitespace and an entirely unselected field.
        merged = []
        for start, end in sorted(ranges[locator]):
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        segments, cursor = [], 0
        def segment(start, end, disposition):
            text = field['text'][start:end]
            return {'start': start, 'end': end, 'text': text,
                'text_digest': byte_digest(text.encode('utf-8')), 'disposition': disposition}
        for start, end in merged:
            if cursor < start:
                segments.append(segment(cursor, start, 'unselected'))
            segments.append(segment(start, end, 'quotation_selected'))
            cursor = end
        if cursor < len(field['text']):
            segments.append(segment(cursor, len(field['text']), 'unselected'))
        inventory.append({**expected[locator],
            'declared_description': locator in description_fields,
            'offset_basis': 'decoded_unicode_codepoints', 'segments': segments,
            'text_preservation': 'complete', 'semantic_coverage': 'not_evaluated'})
    body = {'contract_version': 'boi/source-text-partition@1',
        'source_revision_digest': evidence['source']['digest'],
        'source_manifest_digest': semantic_digest(manifest),
        'fields': inventory, 'text_preservation': 'complete',
        'semantic_coverage': 'not_evaluated', 'requires_source_fidelity_assessment': True}
    return {**body, 'partition_digest': semantic_digest(body)}
