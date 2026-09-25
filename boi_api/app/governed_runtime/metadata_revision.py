"""Exact metadata lineage for retained meaning and evidence, never approval."""
from .semantic_binding_contract import RevisionRef


def metadata_predecessors(assets, authorization, revision, *, limit=16):
    current, value = assets._read_record(authorization, revision)
    if value.kind != 'definition':
        return []
    result, seen = [], {revision.ref}
    # Whitespace in JSON and display labels do not change the typed content.
    # A missing legacy reading pointer is not a replacement reading or authority.
    display = {'title', 'description', 'previous_revision', 'content_object_ref',
               'definition_reading_ref', 'knowledge_reading_status'}
    for _ in range(limit):
        ref = current.payload.get('previous_revision')
        if ref is None:
            break
        ref = RevisionRef.model_validate(ref)
        if ref.ref in seen:
            break
        previous, old = assets._read_record(authorization, ref)
        a, b = current.payload, previous.payload
        if ({k:v for k,v in a.items() if k not in display}
                != {k:v for k,v in b.items() if k not in display}
                or value.model_dump(exclude={'revision','content_json'})
                != old.model_dump(exclude={'revision','content_json'})
                or (a.get('definition_reading_ref') and b.get('definition_reading_ref')
                    and a['definition_reading_ref'] != b['definition_reading_ref'])):
            break
        result.append(ref)
        seen.add(ref.ref)
        current, value = previous, old
    return result


def same_metadata_lineage(assets, authorization, old_ref, current_ref):
    return old_ref == current_ref or old_ref in metadata_predecessors(assets, authorization, current_ref)
