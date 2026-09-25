"""Transport projection of already authorized candidate metadata.

Selection/ranking, source access, cursor binding and exact readers remain owned
by their existing services. This view never reads or summarizes a claim value.
"""


def catalog_response_view(result, *, include_meaning_values):
    if include_meaning_values or 'items' not in result:
        return result
    items = []
    for item in result['items']:
        if 'meaning_matches' not in item:
            items.append(item)
            continue
        items.append({**item,
            'meaning_matches': [
                {**{k:v for k,v in node.items() if k != 'value'}, 'value_included': False}
                for node in item['meaning_matches']],
            'meaning_match_scope': {**item.get('meaning_match_scope', {}),
                'values_delivered': False, 'detail_read_required': True,
                'next_step': 'Follow available_user_views or metadata_read for the exact revision before '
                    'semantic selection. Conditions, exceptions, dependencies, unknowns and source '
                    'support are not supplied by these candidate references.'}})
    return {**result, 'items': items, 'response_view': 'candidate_references',
        'meaning_values_included': False}
