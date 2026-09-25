"""Lossless logical-context transport. IDs and meanings are never rewritten."""
from collections import defaultdict
from copy import deepcopy
import json


def pack_context(entries: list[dict], *, named_ids: bool = False) -> dict:
    grouped = defaultdict(list)
    for index, entry in enumerate(entries):
        payload = entry['logical_payload']
        metadata = tuple(sorted(set(entry) - {'entry_id', 'kind', 'logical_payload'}))
        key = (entry['kind'], payload.get('owner_ref'), tuple(sorted(payload)), metadata)
        grouped[key].append((index, entry))
    groups = []
    for (kind, _owner, keys, metadata), items in grouped.items():
        common = {key: deepcopy(items[0][1]['logical_payload'][key]) for key in keys
                  if all(json.dumps(entry['logical_payload'][key], sort_keys=True) ==
                         json.dumps(items[0][1]['logical_payload'][key], sort_keys=True) for _, entry in items)}
        columns = [key for key in keys if key not in common]
        groups.append({'kind': kind, 'common_payload': common, 'payload_columns': columns,
            'metadata_columns': list(metadata),
            'rows': [[index, entry['entry_id'], *[deepcopy(entry['logical_payload'][key]) for key in columns],
                      *[deepcopy(entry[key]) for key in metadata]] for index, entry in items]})
    if named_ids:
        for group in groups:
            count = len(group['payload_columns'])
            group['original_positions'] = [row[0] for row in group['rows']]
            group['rows'] = [{'entry_id':row[1], 'values':row[2:2+count],
                              **({'metadata':row[2+count:]} if group['metadata_columns'] else {})}
                             for row in group['rows']]
    return {'encoding': 'boi/logical-context-table@2' if named_ids else 'boi/logical-context-table@1', 'groups': groups}


def unpack_context(value: dict) -> list[dict]:
    if value['encoding'] not in {'boi/logical-context-table@1', 'boi/logical-context-table@2'}:
        raise ValueError('LOGICAL_CONTEXT_ENCODING_INVALID')
    items = {}
    for group in value['groups']:
        columns, metadata = group['payload_columns'], group['metadata_columns']
        rows = group['rows']
        if value['encoding'] == 'boi/logical-context-table@2':
            if len(rows) != len(group['original_positions']):
                raise ValueError('LOGICAL_CONTEXT_ROW_INVALID')
            rows = [[index, row['entry_id'], *row['values'], *row.get('metadata', [])]
                    for index, row in zip(group['original_positions'], rows)]
        for row in rows:
            if len(row) != 2 + len(columns) + len(metadata) or row[0] in items:
                raise ValueError('LOGICAL_CONTEXT_ROW_INVALID')
            items[row[0]] = {'entry_id': row[1], 'kind': group['kind'],
                'logical_payload': {**deepcopy(group['common_payload']), **dict(zip(columns, deepcopy(row[2:2+len(columns)])))},
                **dict(zip(metadata, deepcopy(row[2+len(columns):])))}
    if set(items) != set(range(len(items))):
        raise ValueError('LOGICAL_CONTEXT_ORDER_INVALID')
    return [items[i] for i in range(len(items))]
