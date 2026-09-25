"""Read unchanged selected fields across immutable parser projections.

This proves structural equality under current source rights, never meaning or
equivalence of different source revisions. It publishes no new source spans.
"""


def read_compatible_revision_fields(projector, *, authorization, reference, manifest_ref,
                                    span_refs, required_records=()):
    # The ordinary manifest reader checks current source bytes, policy and rights.
    selection = projector.select_manifest_fields(authorization=authorization, reference=reference,
        manifest_ref=manifest_ref, span_refs=[])
    manifest = projector.intake.ledger.read(manifest_ref).payload
    indexed = {field['field_locator']: field for field in manifest['fields']}
    if len(indexed) != len(manifest['fields']):
        raise ValueError('SOURCE_COMPATIBILITY_LOCATOR_AMBIGUOUS')
    artifact = projector.intake.ledger.read(reference['artifact_ref'])
    fields, equivalence, locations = [], {}, set()
    common_keys = ('contract_version', 'artifact_ref', 'source_revision_digest', 'snapshot_digest',
                   'source_role', 'policy_digest', 'employee_id', 'rights_record_ref',
                   'representation', 'offset_basis', 'status', 'canonical_projection_eligible', 'semantic_status')
    for ref in dict.fromkeys(span_refs):
        offset, parts = 0, []
        while True:
            page = projector._read_authorized_field(authorization=authorization, reference=reference,
                artifact=artifact, span_ref=ref, offset=offset, limit=8192)
            parts.append(page['text'])
            offset = page['next_offset']
            if offset is None:
                break
        current = indexed.get(page['field_locator'])
        # All declared structural properties and the full content digest must
        # match. Same name, substring, numeric conversion or moved row is not enough.
        if (current is None or any(page.get(key) != value for key, value in current.items() if key != 'span_ref')
                or any(page.get(key) != manifest.get(key) for key in common_keys)):
            raise ValueError('SOURCE_COMPATIBILITY_FIELD_CHANGED')
        if page['field_locator'] in locations:
            raise ValueError('SOURCE_COMPATIBILITY_LOCATOR_AMBIGUOUS')
        locations.add(page['field_locator'])
        fields.append({**current, 'span_ref': ref, 'text': ''.join(parts)})
        equivalence[ref] = current['span_ref']
    for locator, own in required_records:
        expected = {field['span_ref'] for field in manifest['fields'] if field['record_locator'] == locator}
        if (not own or len(own) != len(set(own)) or not set(own) <= equivalence.keys()
                or {equivalence[ref] for ref in own} != expected):
            raise ValueError('SOURCE_RECORD_INVENTORY_INCOMPLETE')
    proof = {'manifest_ref': manifest_ref, 'scope': 'exact_selected_fields_only',
             'source_revision_digest': reference['digest'], 'span_equivalence': equivalence,
             'semantic_verdict': 'not_evaluated'}
    return {'source': reference, 'fields': fields,
            'manifest': {'contract_version': 'boi/source-field-selection@1',
                'source_revision_digest': reference['digest'], 'employee_id': authorization.principal,
                'policy_digest': authorization.policy_digest, 'full_manifest_ref': manifest_ref,
                'projection_scope': 'selected_source_fields', 'total_field_count': selection['field_count'],
                'field_count': len(fields), 'fields': [{k: v for k, v in f.items() if k != 'text'} for f in fields]},
            'source_projection_compatibility': proof}
