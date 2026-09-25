"""Exact source-record correspondence, distinct from business identity.

The original task, source spans and assets remain immutable. This module only
records projection equivalence and carries declared interpretation dependencies.
"""
from collections import defaultdict
import copy

from .knowledge_work_budget import budget_refs
from .semantic_binding_contract import semantic_digest
from .source_field_projection import SourceFieldProjectionService


def _field_key(field):
    metadata = dict(field.get('structural_metadata', {}))
    if 'excel_column' in metadata:
        locator = metadata['excel_column']
        metadata.pop('cell', None)
        metadata.pop('excel_row', None)
    else:
        prefix = field['record_locator'] + '/'
        locator = field['field_locator']
        if locator.startswith(prefix):
            locator = locator[len(prefix):]
    return {'field': locator, 'metadata': metadata, **{key: field[key] for key in
        ('field_state', 'value_kind', 'presence_basis', 'content_digest', 'character_count')}}


def _inventory(service, auth, units):
    sources = {}
    projector = SourceFieldProjectionService(service.intake)
    for unit in units:
        source = unit['source_ref']
        key = source['artifact_ref']
        if key in sources:
            continue
        projector.select_manifest_fields(authorization=auth, reference=source,
            manifest_ref=unit['manifest_ref'], span_refs=[])
        manifest = service.ledger.read(unit['manifest_ref']).payload
        records = {}
        for field in manifest['fields']:
            records.setdefault(field['record_locator'], []).append(field)
        sources[key] = {'source': source, 'manifest_ref': unit['manifest_ref'],
            'parser_digest': manifest['parser_digest'], 'records': records}
    return sources


def _record_digest(locator, fields):
    parent, _, leaf = locator.rpartition('/')
    # Numeric row positions may move; named structural containers keep identity.
    scope = parent if leaf.isdecimal() else locator
    return semantic_digest([scope, sorted((_field_key(f) for f in fields), key=semantic_digest)])


def _pairs(previous, current, declarations):
    pairs = {ref: ref for ref in previous.keys() & current.keys()}
    seen_old, seen_new = set(), set()
    for pair in declarations:
        old, new = pair.previous_artifact_ref, pair.artifact_ref
        if old not in previous or new not in current or old in seen_old or new in seen_new:
            raise ValueError('KNOWLEDGE_WORK_SOURCE_REVISION_BINDING_INVALID')
        if (new in pairs and pairs[new] != old) or (old in pairs.values() and pairs.get(new) != old):
            raise ValueError('KNOWLEDGE_WORK_SOURCE_REVISION_BINDING_INVALID')
        pairs[new] = old
        seen_old.add(old); seen_new.add(new)
    old = set(previous) - set(pairs.values())
    new = set(current) - set(pairs)
    if len(old) == len(new) == 1:
        pairs[next(iter(new))] = next(iter(old))
    elif old and new:
        raise ValueError('KNOWLEDGE_WORK_SOURCE_REVISION_MAPPING_REQUIRED')
    return pairs


def prepare_revision(service, auth, previous, units, declarations, *, semantics_compatible):
    old_sources = _inventory(service, auth, previous['units'])
    new_sources = _inventory(service, auth, units)
    pairs = _pairs(old_sources, new_sources, declarations)
    delta = {'contract_version': 'boi/knowledge-source-delta@1',
        'previous_task_ref': previous['task_package_id'], 'sources': [],
        'business_identity': 'not_inferred', 'semantic_verdict': 'not_verified'}
    maps, span_map, impacted = {}, {}, []
    for new_id, old_id in pairs.items():
        before, after = old_sources[old_id], new_sources[new_id]
        old_index, new_index = defaultdict(list), defaultdict(list)
        for loc, fields in before['records'].items():
            old_index[_record_digest(loc, fields)].append(loc)
        for loc, fields in after['records'].items():
            new_index[_record_digest(loc, fields)].append(loc)
        matched = {}
        for digest, old_locs in old_index.items():
            new_locs = new_index.get(digest, [])
            if old_id == new_id:
                matched.update({loc: loc for loc in old_locs if loc in new_locs})
            elif len(old_locs) == len(new_locs) == 1:
                matched[old_locs[0]] = new_locs[0]
        maps[new_id] = matched
        for old_loc, new_loc in matched.items():
            target_fields = {semantic_digest(_field_key(f)): f for f in after['records'][new_loc]}
            for field in before['records'][old_loc]:
                span_map[field['span_ref']] = target_fields[semantic_digest(_field_key(field))]['span_ref']
        unmatched_old = [loc for loc in before['records'] if loc not in matched]
        unmatched_new = [loc for loc in after['records'] if loc not in matched.values()]
        item = {'previous_source': before['source'], 'source': after['source'],
            'previous_manifest_ref': before['manifest_ref'], 'manifest_ref': after['manifest_ref'],
            'business_identity': 'not_inferred',
            'equivalent_records': [{'previous_locator': old, 'record_locator': new,
                'previous_span_refs': [f['span_ref'] for f in before['records'][old]],
                'span_refs': [f['span_ref'] for f in after['records'][new]]} for old, new in matched.items()],
            'unmatched_previous_records': unmatched_old, 'unmatched_current_records': unmatched_new,
            'ambiguous_previous_records': [loc for digest, locs in old_index.items() for loc in locs
                if loc not in matched and (len(locs) > 1 or len(new_index.get(digest, [])) > 1)],
            'ambiguous_current_records': [loc for digest, locs in new_index.items() for loc in locs
                if loc not in matched.values() and (len(locs) > 1 or len(old_index.get(digest, [])) > 1)]}
        delta['sources'].append(item)
        if unmatched_old:
            impacted.append(item)
    removed = [value for key, value in old_sources.items() if key not in pairs.values()]
    delta['removed_sources'] = [value['source'] for value in removed]
    old_positions, new_positions = ({field['span_ref']: position
        for source in inventory.values() for position, fields in enumerate(source['records'].values())
        for field in fields} for inventory in (old_sources, new_sources))
    rebuilt = []
    for new_id, after in new_sources.items():
        old_id = pairs.get(new_id)
        old_units = [u for u in previous['units'] if u['source_ref']['artifact_ref'] == old_id]
        mapping = maps.get(new_id, {})
        used = set()

        def new_unit(locators, ancestors):
            fields = [f for loc in locators for f in after['records'][loc]]
            spans = [f['span_ref'] for f in fields]
            inherited_refs = list(dict.fromkeys(ref for old in ancestors for ref in budget_refs(previous['task_package_id'], old)))
            unit = {'unit_id': semantic_digest([after['source'], spans]), 'source_ref': after['source'],
                'manifest_ref': after['manifest_ref'], 'record_locators': locators, 'span_refs': spans,
                'status': 'pending', 'attempts': max((old['attempts'] for old in ancestors), default=0),
                'attempt_refs': list(dict.fromkeys(ref for old in ancestors for ref in old.get('attempt_refs', []))),
                'results': [], 'budget_refs': inherited_refs,
                'previous_unit_results': [r for old in ancestors for r in old.get('results', [])],
                'previous_unit_refs': [{'task_ref': previous['task_package_id'], 'unit_id': old['unit_id']} for old in ancestors],
                'record_lineage': [{'previous_locator': old, 'record_locator': new} for old, new in mapping.items() if new in locators]}
            return unit

        for old in old_units:
            if not all(loc in mapping for loc in old['record_locators']):
                continue
            locators = [mapping[loc] for loc in old['record_locators']]
            used.update(locators)
            unit = new_unit(locators, [old])
            scope = old.get('revision_scope', {'basis': 'whole_source', 'order_sensitive': True})
            required = old.get('revision_dependency_spans', old['span_refs'])
            equivalent = all(ref in span_map for ref in required)
            if scope['basis'] == 'whole_source':
                equivalent = equivalent and old['source_ref'] == after['source']
            if scope.get('order_sensitive', True):
                # Keep source sequence dependencies, including whole-unit moves
                # and explicitly read context outside that unit. Local sorting
                # alone misses a moved block of otherwise unchanged steps.
                equivalent = equivalent and all(old_positions[ref] == new_positions[span_map[ref]] for ref in required)
            equivalent = equivalent and old_sources[old_id]['parser_digest'] == after['parser_digest']
            if (semantics_compatible and equivalent and old['status'] == 'produced' and not old.get('unresolved')
                    and not any(r['disposition'] == 'unresolved' for r in old.get('record_outcomes', []))
                    and service._outputs_current(auth, old.get('results', []))):
                for key in ('results', 'summary', 'submission_ref', 'history', 'revision_scope', 'revision_impact_review'):
                    if key in old:
                        unit[key] = copy.deepcopy(old[key])
                unit.update(status='produced', carried_from=previous['task_package_id'],
                    carry_basis='exact_projection_and_declared_dependencies',
                    original_evidence_rewritten=False,
                    revision_dependency_spans=[span_map[ref] for ref in required],
                    record_outcomes=[{**r, 'record_locator': mapping[r['record_locator']]} for r in old.get('record_outcomes', [])])
            rebuilt.append(unit)
        remaining = [loc for loc in after['records'] if loc not in used]
        unmatched_ancestors = [old for old in old_units if any(loc not in mapping for loc in old['record_locators'])]
        for offset in range(0, len(remaining), service.RECORDS_PER_UNIT):
            locators = remaining[offset:offset + service.RECORDS_PER_UNIT]
            ancestors = [old for old in old_units if any(mapping.get(loc) in locators for loc in old['record_locators'])]
            # Unmatched edited/deleted records do not prove identity. Carry their
            # allowance conservatively instead of obtaining a fresh repair budget.
            ancestors.extend(old for old in unmatched_ancestors if old not in ancestors)
            rebuilt.append(new_unit(locators, ancestors))
    if impacted or removed:
        target = next((u for u in rebuilt if u['status'] == 'pending'), rebuilt[0])
        target['status'] = 'pending'
        target['revision_impact'] = {'sources': impacted, 'removed_sources': delta['removed_sources'],
            'required_action': 'Compare unmatched or removed original records and affected prior knowledge; absence is not a retraction of truth.'}
        unmatched = {item['previous_source']['artifact_ref']: set(item['unmatched_previous_records']) for item in impacted}
        removed_ids = {r['artifact_ref'] for r in delta['removed_sources']}
        prior_units = [u for u in previous['units'] if u['source_ref']['artifact_ref'] in removed_ids or
            set(u['record_locators']) & unmatched.get(u['source_ref']['artifact_ref'], set())]
        target['previous_unit_results'] = list({semantic_digest(r): r for u in prior_units for r in u.get('results', [])}.values())
        target['budget_refs'] = list(dict.fromkeys([*target['budget_refs'],
            *(ref for u in prior_units for ref in budget_refs(previous['task_package_id'], u))]))
    return rebuilt, delta
