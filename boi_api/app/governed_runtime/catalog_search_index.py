"""Disposable exact-revision discovery over the existing catalog/object store.

Publication updates an inverted projection. Questions traverse term postings,
authorize source groups now, and read only the requested candidate page. The
ledger, current heads and native meaning readers retain content authority.
"""
import copy
import json
import math
import time

from ..v2.atomic_store_contract import AtomicWrite
from ..v2.repository import normalize_tokens, query_lexeme_weights
from ..v2.search import lexical_token_score
from .semantic_binding_contract import RevisionRef, semantic_digest
from .source_envelope import ArtifactEnvelope
from .catalog_meaning_properties import MeaningPropertyQuery, add_properties, find_properties, property_key

VERSION = 'boi/catalog-candidate-index@2'
DEFINITION_SCOPE_VERSION = 'boi/definition-scope-index@1'
REVIEW_PROJECTION_VERSION = 'review-target-integrity@1'
SEARCH_READ_VERSION = VERSION + ':' + REVIEW_PROJECTION_VERSION + ':compact-postings@3'


def _validate_review_postings(index):
    expected = {}
    for key, document in index['documents'].items():
        for target in document['review_targets']:
            expected.setdefault(target, []).append(key)
    actual = {target: sorted(keys) for target, keys in index['reviews'].items()}
    if actual != {target: sorted(keys) for target, keys in expected.items()}:
        # A historical projection mixed definition relations into reviews.
        # Recover only the affected namespace through explicit maintenance;
        # never silently return false review links or rerun semantic work.
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')


def _compact_search(index, *, mode, purpose):
    """Encode repeated head keys once in the existing disposable projection.

    Posting ordinals have no knowledge identity or selection authority. They
    are local to this exact immutable index and expand back to original keys.
    """
    _validate_review_postings(index)
    keys = sorted(index['documents'])
    positions = {key: str(i) for i, key in enumerate(keys)}
    eligible = {key for key in keys if purpose == 'all'
                or index['groups'][index['documents'][key]['group']]['catalog_purpose'] == purpose}
    value = {k: index[k] for k in ('contract_version', 'projection_version', 'employee_id',
                                  'namespace', 'preparation_policy', 'groups', 'restricted')}
    value['documents'] = [[key, index['documents'][key]['revision'], index['documents'][key]['group'],
                           index['documents'][key]['logical_id'],
                           index['documents'][key].get('embedding', {})] for key in keys]
    for field in ('terms', 'properties'):
        enabled = mode != 'reviews' and (field == 'terms' or mode == 'properties')
        value[field] = {term: selected for term, posting in index[field].items()
                        if (selected := {positions[key]: match for key, match in posting.items() if key in eligible})} if enabled else {}
    value['reviews'] = {target: [positions[key] for key in posting]
                        for target, posting in index['reviews'].items()}
    return value


def _expand_search(value, tokens, queries):
    documents = value['documents']
    selected_properties = {property_key(q.owner_pointer, q.field_pointer, q.value) for q in queries}
    # The cached compact projection is decoded, but only requested postings
    # expand to head keys. Full index updates retain the original format.
    result = {k: v for k, v in value.items() if k not in ('documents', 'terms', 'properties', 'reviews')}
    result['documents'] = {key: {'revision': revision, 'group': group, 'logical_id': logical_id,
                                **({'embedding': embedding} if embedding.get('chunks') else {})}
                           for key, revision, group, logical_id, embedding in documents}
    for field, selected in (('terms', tokens), ('properties', selected_properties)):
        result[field] = {term: {documents[int(position)][0]: match for position, match in value[field][term].items()}
                         for term in selected if term in value[field]}
    result['reviews'] = {target: [documents[int(position)][0] for position in posting]
                         for target, posting in value['reviews'].items()}
    return result


def _empty(assets, auth, namespace):
    return {'contract_version': VERSION, 'projection_version': assets.SEARCH_PROJECTION_VERSION, 'employee_id': auth.principal,
            'namespace': namespace, 'documents': {}, 'terms': {}, 'groups': {}, 'reviews': {},
            'properties': {}, 'restricted': {}, 'preparation_policy': assets.intake._policy(auth),
            'definition_scope': {'contract_version': DEFINITION_SCOPE_VERSION,
                                 'revisions': {}, 'incoming': {}}}


def _read(assets, auth, namespace, catalog, *, definition_only=False, search_terms=None, property_queries=(), purpose='all'):
    digest = catalog.get('search_object_ref')
    if digest is None:
        return _empty(assets, auth, namespace)
    project = getattr(assets.objects, 'project_verified', None)
    mode = 'properties' if property_queries else 'lexical' if search_terms else 'reviews'
    def derive(raw):
        value = json.loads(raw)
        if search_terms is not None:
            return _compact_search(value, mode=mode, purpose=purpose)
        if not definition_only:
            _validate_review_postings(value)
            return value
        # Keep tokens, property postings, review history and unused document
        # metadata out of the repeated context-fence projection.
        return {**{k: value[k] for k in ('contract_version', 'projection_version', 'employee_id',
                                      'namespace', 'preparation_policy')},
                'groups': {k: v for k, v in value['groups'].items() if v['kind'] == 'definition'},
                'restricted': {k: v for k, v in value['restricted'].items() if v == 'definition'},
                'definition_scope': value.get('definition_scope')}
    # Revalidate old persisted projections once per immutable object, including
    # cache hits created before the review/definition bookkeeping repair.
    version = VERSION + ':' + (DEFINITION_SCOPE_VERSION if definition_only else REVIEW_PROJECTION_VERSION)
    if search_terms is not None:
        version = SEARCH_READ_VERSION + ':' + mode + ':' + purpose
    value = (project(digest, version=version, derive=derive, persistent=True)
             if project else derive(assets.objects.get(digest)))
    if (value.get('contract_version') != VERSION or value.get('employee_id') != auth.principal
            or value.get('namespace') != namespace):
        raise ValueError('DOMAIN_SEARCH_INDEX_BINDING_INVALID')
    if value.get('projection_version') != assets.SEARCH_PROJECTION_VERSION:
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
    if value['restricted'] and value['preparation_policy'] != assets.intake._policy(auth):
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
    return _expand_search(value, search_terms, property_queries) if search_terms is not None else value


def _add(assets, auth, index, head_key, record, summary):
    index['restricted'].pop(head_key, None)
    old = index['documents'].pop(head_key, None)
    scope = index.get('definition_scope')
    if old and scope:
        previous = scope['revisions'].pop(old['revision']['ref'], None)
        if previous:
            for target in previous['targets']:
                scope['incoming'][target].remove(old['revision']['ref'])
                if not scope['incoming'][target]:
                    del scope['incoming'][target]
    if old:
        for prop in old['property_keys']:
            posting = index['properties'][prop]
            posting.pop(head_key)
            if not posting:
                del index['properties'][prop]
        for token in old['tokens']:
            posting = index['terms'][token]
            posting.pop(head_key)
            if not posting:
                del index['terms'][token]
        group = index['groups'][old['group']]
        group['count'] -= 1
        if not group['count']:
            del index['groups'][old['group']]
        for target in old['review_targets']:
            index['reviews'][target].remove(head_key)
            if not index['reviews'][target]:
                del index['reviews'][target]
    value = record.payload
    group = {k: value[k] for k in ('sources', 'policy_digest', 'kind')}
    group.update({k: summary[k] for k in ('content_contract', 'catalog_purpose', 'retrieval_role')})
    group_key = semantic_digest(group)
    index['groups'].setdefault(group_key, {**group, 'count': 0})['count'] += 1
    tokens = {}
    for flag, entries in ((1, normalize_tokens(value['title'])), (2, normalize_tokens(value['description'])),
                          (4, summary['search_tokens'])):
        for token in entries:
            tokens[token] = tokens.get(token, 0) | flag
    review_targets = sorted({ref['ref'] for view in summary['available_user_views'] if view.get('tool') == 'boi_native_answer'
                      for ref in view.get('definition_revisions', [])})
    entry = {'revision': assets._ref(record).model_dump(mode='json'), 'group': group_key, 'review_targets': review_targets,
             'tokens': tokens, 'logical_id': value['logical_id'],
             'property_keys': add_properties(index, head_key, summary['meaning_search'])}
    from .catalog_embedding import prepare_entry
    entry['embedding'] = prepare_entry(assets.embedding_client, head_key, record, summary)
    index['documents'][head_key] = entry
    if scope is not None and value['kind'] == 'definition':
        relations = {k: value[k] for k in ('conflicts_with', 'supersedes')}
        relation_targets = sorted({r['ref'] for refs in relations.values() for r in refs})
        scope['revisions'][entry['revision']['ref']] = {
            'revision': entry['revision'], 'declared_relations': relations, 'targets': relation_targets}
        for target in relation_targets:
            scope['incoming'].setdefault(target, []).append(entry['revision']['ref'])
    for token, flags in tokens.items():
        index['terms'].setdefault(token, {})[head_key] = flags
    for target in review_targets:
        index['reviews'].setdefault(target, []).append(head_key)
    return {k: v for k, v in entry['embedding'].items() if k != 'chunks'}


def _write(assets, auth, namespace, before, index, *, pending, initialized):
    if 'definition_scope' in index:
        scope = index['definition_scope']
        scope['inventory_digest'] = semantic_digest([
            scope['revisions'][key]['revision'] for key in sorted(scope['revisions'])])
    raw = json.dumps(index, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    digest = assets.objects.put(raw)
    project = getattr(assets.objects, 'project_verified', None)
    if project:
        # Prepare this exact revision during publication/explicit maintenance,
        # without moving full index assembly into every normal question.
        for mode, purpose in (('properties', 'knowledge'), ('reviews', 'all'), ('lexical', 'knowledge')):
            project(digest, version=SEARCH_READ_VERSION + ':' + mode + ':' + purpose,
                    derive=lambda _, mode=mode, purpose=purpose: _compact_search(index, mode=mode, purpose=purpose), persistent=True)
    after = {**before, 'search_version': VERSION, 'search_object_ref': digest,
             'search_pending': pending, 'search_initialized': initialized}
    return AtomicWrite('domain_asset_catalogs', assets.catalog_key(auth, namespace), before, after)


def definition_scope(assets, auth, namespace):
    """Read prepared inventory/relations with current namespace source access.

    Publication, not a question, maintains the revision set and inverse links.
    These are discovery fences; selected meanings still use the authoritative
    revision/head reader. This does not discover unlinked semantic relevance.
    Old or interrupted indexes require explicit existing catalog maintenance.
    """
    assets.intake._policy(auth)
    if not {'derive', 'model_input'} <= set(auth.allowed_uses):
        raise ValueError('DOMAIN_ASSET_USE_NOT_AUTHORIZED')
    key = assets.catalog_key(auth, namespace)
    catalog = assets.store.get('domain_asset_catalogs', key)
    if catalog is None:
        scope = _empty(assets, auth, namespace)['definition_scope']
        scope['inventory_digest'] = semantic_digest([])
        return scope
    if (not catalog.get('search_initialized') or catalog.get('search_pending')
            or catalog.get('search_version') != VERSION):
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
    index = _read(assets, auth, namespace, catalog, definition_only=True)
    scope = index.get('definition_scope')
    if not scope or scope.get('contract_version') != DEFINITION_SCOPE_VERSION:
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
    if any(kind == 'definition' for kind in index['restricted'].values()):
        raise ValueError('DOMAIN_CONTEXT_DEFINITION_SCOPE_RESTRICTED')
    checked = set()
    for group in index['groups'].values():
        if group['kind'] != 'definition':
            continue
        if group['policy_digest'] != auth.policy_digest:
            raise ValueError('DOMAIN_CONTEXT_DEFINITION_SCOPE_RESTRICTED')
        source_key = semantic_digest(group['sources'])
        if source_key not in checked:
            try:
                assets.authorize_sources(auth, tuple(ArtifactEnvelope.model_validate(s) for s in group['sources']),
                                         model_input=True, metadata_only=True)
            except ValueError as exc:
                if 'DENIED' not in str(exc) and 'NOT_AUTHORIZED' not in str(exc):
                    raise
                raise ValueError('DOMAIN_CONTEXT_DEFINITION_SCOPE_RESTRICTED') from exc
            checked.add(source_key)
    if assets.store.get('domain_asset_catalogs', key) != catalog:
        raise ValueError('DOMAIN_CONTEXT_DEFINITION_SCOPE_CHANGED')
    return scope


def update_publication(assets, auth, revision):
    record, summary = assets._catalog_item(auth, revision, include_search=True)
    namespace = record.payload['namespace']
    key = 'domain-asset-head:' + semantic_digest([auth.principal, namespace, record.payload['logical_id']])
    head = assets.store.get('domain_asset_heads', key)
    if not head or head['revision'] != revision.model_dump(mode='json'):
        return  # An exact historical replay must not restore a superseded head.
    catalog = assets.store.get('domain_asset_catalogs', assets.catalog_key(auth, namespace))
    if not catalog or not catalog.get('search_initialized'):
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
    index = copy.deepcopy(_read(assets, auth, namespace, catalog))
    if (index.get('definition_scope') or {}).get('contract_version') != DEFINITION_SCOPE_VERSION:
        raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
    embedding = _add(assets, auth, index, key, record, summary)
    pending = [p for p in catalog.get('search_pending', []) if p != key]
    if not assets.store.atomic_compare_and_write((
        _write(assets, auth, namespace, catalog, index, pending=pending, initialized=True),
        AtomicWrite('domain_asset_heads', key, head, head))):
        raise ValueError('DOMAIN_SEARCH_INDEX_CHANGED')
    return embedding


def catalog_rows(assets, auth, namespace):
    if namespace is not None:
        row = assets.store.get('domain_asset_catalogs', assets.catalog_key(auth, namespace))
        return [row] if row else []
    rows, after = [], ''
    while True:
        page = assets.store.list_key_page('domain_asset_catalogs', employee_id=auth.principal,
                                         after_key=after, limit=100)
        rows.extend(p['value'] for p in page if p['key'].startswith('domain-catalog:'))
        if len(page) < 100:
            return rows
        after = page[-1]['key']


def prepare(assets, auth, namespace):
    """Explicit deterministic maintenance for legacy or interrupted projections.

    This scan is never invoked by catalog reads. Captured catalog epochs fence
    its publication; concurrent asset changes leave the old projection intact.
    """
    assets.intake._policy(auth)
    if not {'derive', 'model_input'} <= set(auth.allowed_uses):
        raise ValueError('DOMAIN_ASSET_USE_NOT_AUTHORIZED')
    catalogs = {row['namespace']: row for row in catalog_rows(assets, auth, namespace)}
    indexes = {scope: _empty(assets, auth, scope) for scope in catalogs}
    after, count, restricted = '', 0, 0
    embedding_states = {}
    embedding_calls = 0
    while True:
        page = assets.store.list_key_page('domain_asset_heads', employee_id=auth.principal,
                                         after_key=after, limit=100)
        for item in page:
            row = item['value']
            if row['namespace'] not in indexes:
                continue
            try:
                record, summary = assets._catalog_item(auth, RevisionRef.model_validate(row['revision']), include_search=True)
            except ValueError as exc:
                if 'DENIED' not in str(exc) and 'NOT_AUTHORIZED' not in str(exc):
                    raise
                # Preserve scope incompleteness without indexing denied content.
                # Different future authorization requires explicit preparation.
                indexes[row['namespace']]['restricted'][item['key']] = row['kind']
                restricted += 1
                continue
            report = _add(assets, auth, indexes[row['namespace']], item['key'], record, summary)
            embedding_states[report['state']] = embedding_states.get(report['state'], 0) + 1
            embedding_calls += report.get('preparation', {}).get('document_embedding_calls', 0)
            count += 1
        if len(page) < 100:
            break
        after = page[-1]['key']
    for scope, index in indexes.items():
        if not assets.store.atomic_compare_and_write((
                _write(assets, auth, scope, catalogs[scope], index, pending=[], initialized=True),)):
            raise ValueError('DOMAIN_SEARCH_INDEX_CHANGED')
    return {'status': 'prepared_with_restrictions' if restricted else 'prepared', 'prepared_asset_count': count,
            'restricted_asset_count': restricted, 'namespace_count': len(indexes),
            'new_knowledge_revisions': 0, 'semantic_quality': 'not_evaluated',
            'embedding': {'states': embedding_states, 'successful_document_embedding_calls': embedding_calls,
                          'query_embedding_calls': 0},
            'scope': 'Rebuilt candidate lookup and configured document vectors from current authorized heads; no answer model or knowledge generation.'}


def readiness(assets, auth, revisions):
    """Current derived readiness beside immutable task publication reports."""
    items, indexes, catalogs, seen = [], {}, {}, set()
    for revision in revisions:
        if revision.ref in seen:
            continue
        seen.add(revision.ref)
        item = {'revision': revision.model_dump(mode='json'), 'state': 'deferred'}
        try:
            record = assets._record_metadata(auth, revision, metadata_only=True)
            namespace = record.payload['namespace']
            key = 'domain-asset-head:' + semantic_digest([auth.principal, namespace, record.payload['logical_id']])
            head = assets.store.get('domain_asset_heads', key)
            item['namespace'] = namespace
            if not head or head['revision'] != item['revision']:
                item['state'] = 'superseded'
            else:
                if namespace not in catalogs:
                    catalogs[namespace] = assets.store.get('domain_asset_catalogs', assets.catalog_key(auth, namespace)) or {}
                catalog = catalogs[namespace]
                if (catalog.get('search_initialized') and not catalog.get('search_pending')
                        and catalog.get('search_version') == VERSION):
                    if namespace not in indexes:
                        indexes[namespace] = _read(assets, auth, namespace, catalog)
                    if (indexes[namespace]['documents'].get(key, {}).get('revision') == item['revision']
                            and (indexes[namespace].get('definition_scope') or {}).get('contract_version')
                            == DEFINITION_SCOPE_VERSION):
                        item['state'] = 'prepared'
                        vector = indexes[namespace]['documents'][key].get('embedding', {})
                        client = assets.embedding_client
                        item['embedding'] = {'state': ('not_connected' if client is None else
                            vector.get('state', 'not_prepared') if vector.get('identity') == client.identity_digest else 'not_prepared'),
                            'identity': vector.get('identity'),
                            'scope': 'publication preparation; vector cache availability checked during search'}
                if item['state'] == 'deferred':
                    item['repair'] = {'tool': 'boi_knowledge_catalog',
                                      'arguments': {'namespace': namespace, 'prepare_index': True}}
        except ValueError as exc:
            item['state'] = 'restricted' if 'DENIED' in str(exc) or 'NOT_AUTHORIZED' in str(exc) else 'unavailable'
        except (OSError, KeyError):
            item['state'] = 'unavailable'
        items.append(item)
    return {'items': items, 'index_contract': VERSION, 'semantic_work_repeated': False,
            'scope': 'Current authorized revision/index observation; immutable publication outcomes are preserved. This is not semantic or computation qualification.'}


def search(assets, auth, *, namespace, kind, content_contract, purpose, query, limit, cursor, include_relations,
           reviewed_definition=None, meaning_query=()):
    property_queries = tuple(MeaningPropertyQuery.model_validate(q) for q in meaning_query)
    if len(property_queries) > 8:
        raise ValueError('DOMAIN_MEANING_PROPERTY_QUERY_LIMIT')
    property_counts = [set() for _ in property_queries]
    target = None
    if reviewed_definition is not None:
        target = RevisionRef.model_validate(reviewed_definition)
        record, _ = assets._catalog_item(auth, target, include_search=False)
        if record.payload['kind'] != 'definition':
            raise ValueError('DOMAIN_REVIEW_TARGET_DEFINITION_REQUIRED')
    stamp = assets.catalog_stamp(auth, namespace)
    indexes, scopes, visible_groups, matches, frequencies = [], {}, set(), {}, {}
    searched = retrieval_documents = restricted = 0
    tokens = normalize_tokens(query)
    source_checks = {}
    vector_keys, vector_owners, vector_assets = {}, {}, {}
    embedding_eligible = embedding_unprepared = 0
    client = assets.embedding_client if query and target is None and purpose != 'history' else None
    embedding_report = {'status': 'not_connected' if assets.embedding_client is None else 'not_applicable',
                        'document_embedding_calls': 0, 'query_embedding_calls': 0}

    def accessible(group_key, group):
        # Candidate filters select knowledge to search. An attached review has
        # its own kind/contract and is authorized only if actually needed.
        if group_key in visible_groups:
            return True
        if group['policy_digest'] != auth.policy_digest:
            return False
        source_key = semantic_digest(group['sources'])
        if source_key not in source_checks:
            try:
                assets.authorize_sources(auth, tuple(ArtifactEnvelope.model_validate(s) for s in group['sources']),
                                         model_input=True, metadata_only=True)
                source_checks[source_key] = True
            except ValueError as exc:
                if 'DENIED' not in str(exc) and 'NOT_AUTHORIZED' not in str(exc):
                    raise
                source_checks[source_key] = False
        if not source_checks[source_key]:
            return False
        visible_groups.add(group_key)
        return True

    for catalog in catalog_rows(assets, auth, namespace):
        if (not catalog.get('search_initialized') or catalog.get('search_pending')
                or catalog.get('search_version') != VERSION):
            raise ValueError('DOMAIN_SEARCH_INDEX_NOT_PREPARED')
        index = _read(assets, auth, catalog['namespace'], catalog, search_terms=tokens, property_queries=property_queries,
                      purpose=purpose)
        indexes.append(index)
        restricted += sum(not kind or value == kind for value in index['restricted'].values())
        for group_key, group in index['groups'].items():
            if ((kind and group['kind'] != kind) or
                    (content_contract is not None and group['content_contract'] != content_contract)):
                continue
            if not accessible(group_key, group):
                restricted += group['count']
                continue
            if purpose != 'all' and group['catalog_purpose'] != purpose:
                continue
            scopes[group_key] = group
            if target is None:
                searched += group['count']
                if group['retrieval_role'] not in ('recorded_observation', 'recorded_answer'):
                    retrieval_documents += group['count']
        target_keys = None
        if target is not None:
            target_keys = {key for key in index['reviews'].get(target.ref, [])
                           if index['documents'][key]['group'] in scopes}
            searched += len(target_keys)
            retrieval_documents += sum(scopes[index['documents'][key]['group']]['retrieval_role']
                not in ('recorded_observation', 'recorded_answer') for key in target_keys)
            if not query:
                matches.update({key: {'doc': index['documents'][key], 'tokens': {}, 'index': index} for key in target_keys})
        for key, number, owners in find_properties(index, property_queries, scopes, target_keys):
            match = matches.setdefault(key, {'doc': index['documents'][key], 'tokens': {}, 'index': index})
            match.setdefault('property_matches', {})[number] = owners
            property_counts[number].add(key)
        for token in tokens:
            for key, flags in index['terms'].get(token, {}).items():
                if target_keys is not None and key not in target_keys:
                    continue
                doc = index['documents'][key]
                group = scopes.get(doc['group'])
                if group is None:
                    continue
                match = matches.setdefault(key, {'doc': doc, 'tokens': {}, 'index': index})
                match['tokens'][token] = flags
                if flags & 4 and group['retrieval_role'] not in ('recorded_observation', 'recorded_answer'):
                    frequencies[token] = frequencies.get(token, 0) + 1
        if client is not None:
            for key, doc in index['documents'].items():
                group = scopes.get(doc['group'])
                if group is None or group['catalog_purpose'] != 'knowledge':
                    continue
                embedding_eligible += 1
                projection = doc.get('embedding', {})
                if projection.get('identity') != client.identity_digest:
                    embedding_unprepared += 1
                    continue
                if projection.get('state') != 'prepared':
                    embedding_unprepared += 1
                for chunk in projection.get('chunks', []):
                    identity = chunk['key']
                    vector_keys[identity] = identity
                    vector_owners[identity] = (key, doc, index, chunk['pointer'])
                    vector_assets[key] = (doc, index)
    # Query once across every authorized namespace; text and document key
    # construction were prepared at publication. Missing vectors never trigger
    # document embedding or remove lexical/property candidates.
    semantic_scores, semantic_pointers = {}, {}
    if client is not None:
        started = time.perf_counter()
        try:
            scores = client.score_prepared(query, vector_keys)
            embedding_report = client.last_retrieval_diagnostics
        except Exception:
            scores = {}
            embedding_report = {**client.last_retrieval_diagnostics, 'status': 'unavailable',
                                'reason_code': 'DOMAIN_QUERY_EMBEDDING_FAILED'}
        embedding_report = {k: v for k, v in embedding_report.items() if k != 'missing_document_ids'} | {
            'missing_vector_count': len(client.last_retrieval_diagnostics.get('missing_document_ids', ())),
            'eligible_asset_count': embedding_eligible, 'unprepared_asset_count': embedding_unprepared,
            'scoring_seconds': time.perf_counter() - started, 'candidate_limit': 64,
            'scoring_scope': 'all_authorized_prepared_vectors; no catalog head scan',
            'projection_scope': 'title_description_and_declared_meaning_values'}
        for identity, score in scores.items():
            key, doc, index, pointer = vector_owners[identity]
            if key not in semantic_scores or score > semantic_scores[key]:
                semantic_scores[key], semantic_pointers[key] = score, pointer
        semantic_order = sorted(semantic_scores, key=lambda k: (-semantic_scores[k], k))[:64]
        for rank, key in enumerate(semantic_order, 1):
            doc, index = vector_assets[key]
            match = matches.setdefault(key, {'doc': doc, 'tokens': {}, 'index': index})
            match.update(semantic_rank=rank, semantic_score=semantic_scores[key],
                         semantic_pointer=semantic_pointers[key])
    mass = query_lexeme_weights(query)
    weights = {t: mass[t] * (1 + math.log((retrieval_documents + 1) / (frequencies.get(t, 0) + 1))) for t in tokens}
    for match in matches.values():
        selected = match['tokens']
        match['score'] = lexical_token_score(tokens, title_tokens={t for t, f in selected.items() if f & 1},
            description_tokens={t for t, f in selected.items() if f & 2},
            body_tokens={t for t, f in selected.items() if f & 4}, token_weights=weights)
    hybrid = any('semantic_rank' in m for m in matches.values())
    if hybrid:
        lexical = sorted((k for k, m in matches.items() if m['tokens']),
                         key=lambda k: (-matches[k]['score'], k))
        ranks = {key: rank for rank, key in enumerate(lexical, 1)}
        for key, match in matches.items():
            match['combined_score'] = ((1 / (60 + ranks[key]) if key in ranks else 0) +
                                      (1 / (60 + match['semantic_rank']) if 'semantic_rank' in match else 0))
    ordered = sorted(matches.items(), key=lambda item: (
        scopes[item[1]['doc']['group']]['retrieval_role'] in ('recorded_observation', 'recorded_answer') if query else False,
        -len(item[1].get('property_matches', {})), -item[1].get('combined_score', item[1]['score']),
        item[1]['doc']['logical_id'], item[1]['doc']['revision']['ref']))
    snapshot = semantic_digest({'version': VERSION, 'stamp': stamp, 'query': query, 'kind': kind,
        'content_contract': content_contract, 'purpose': purpose, 'restricted': restricted,
        'meaning_query': [q.model_dump(mode='json') for q in property_queries],
        'reviewed_definition': target.model_dump(mode='json') if target is not None else None,
        'embedding_identity': client.identity_digest if client else None,
        'ranking': [(key, item['doc']['revision'], item.get('combined_score', item['score'])) for key, item in ordered]})
    offset = 0
    if cursor:
        try:
            bound, number = cursor.rsplit(':', 1)
            offset = int(number)
            if len(cursor) > 90 or bound != snapshot or not 0 <= offset <= len(ordered):
                raise ValueError()
        except ValueError:
            raise ValueError('DOMAIN_ASSET_CATALOG_CURSOR_STALE') from None
    end, items = min(len(ordered), offset + limit), []
    for key, match in ordered[offset:end]:
        revision = RevisionRef.model_validate(match['doc']['revision'])
        head = assets.store.get('domain_asset_heads', key)
        if not head or head['revision'] != revision.model_dump(mode='json'):
            raise ValueError('DOMAIN_SEARCH_INDEX_CHANGED')
        record, summary = assets._catalog_item(auth, revision, include_search=bool(query or property_queries))
        # Meaning matches are the same exact evidence-owner projections used by
        # the existing scan. No source/condition selection is done by postings.
        nodes = []
        denominator = math.fsum(weights.values()) or 1
        for entry in summary['meaning_search']:
            meaning = tokens & set(entry['tokens'])
            expressions = [{'evidence_pointer': e['evidence_pointer'], 'matched_terms': sorted(tokens & set(e['tokens']))}
                           for e in entry['source_expressions'] if tokens & set(e['tokens'])]
            overlap = meaning | {t for e in expressions for t in e['matched_terms']}
            if overlap:
                nodes.append({**entry['node'], 'matched_terms': sorted(overlap), 'matched_meaning_terms': sorted(meaning),
                    'matched_source_expressions': expressions, 'retrieval_score': math.fsum(weights[t] for t in sorted(overlap)) / denominator})
        nodes.sort(key=lambda n: (-n['retrieval_score'], n['target_pointer']))
        item = {'revision': revision.model_dump(mode='json'), **({'retrieval_score': match['score']} if query else {}),
            **{k: summary[k] for k in ('content_contract', 'catalog_purpose', 'retrieval_role', 'available_user_views')},
            **{k: record.payload[k] for k in ('logical_id', 'namespace', 'kind', 'title', 'description', 'knowledge_reading_status')},
            'status': 'PROVISIONAL', 'canonical_projection_eligible': False}
        if property_queries:
            item['property_matches'] = [
                {'condition_index': number, 'target_pointer': owner, 'field_pointer': property_queries[number].field_pointer,
                 'value': property_queries[number].value, 'basis': property_queries[number].basis,
                 'semantic_support_verified': False}
                for number, owners in sorted(match.get('property_matches', {}).items()) for owner in owners]
            item['metadata_read'] = {'tool': 'boi_knowledge_read',
                'arguments': {'revision': revision.model_dump(mode='json'), 'view': 'meaning_index'}}
        if hybrid:
            item['retrieval_score'] = match['combined_score']
            item['retrieval_components'] = {'lexical_score': match['score'],
                'embedding_score': match.get('semantic_score'),
                'embedding_owner_pointer': match.get('semantic_pointer'),
                'semantic_support_verified': False}
            item['metadata_read'] = {'tool': 'boi_knowledge_read',
                'arguments': {'revision': revision.model_dump(mode='json'), 'view': 'meaning_index'}}
        if nodes:
            item.update(meaning_matches=nodes[:5], meaning_match_scope={
                'matched_node_count': len(nodes), 'returned_node_count': min(5, len(nodes)),
                'selection_complete': False, 'semantic_support_verified': False, 'dependencies_resolved': False,
                'scope_inherited': False, 'next_step': 'Select exact references for preparation; it resolves required conditions, exceptions, dependencies and counterevidence.'})
        if include_relations:
            item['declared_relations'] = {k: record.payload[k] for k in ('conflicts_with', 'supersedes')}
        items.append(item)
    # Resolve only reviews attached to the actual page. History contributes no
    # factual search terms or corpus frequency to a normal knowledge request.
    reviews = {}
    for item in items:
        item_target = item['revision']['ref']
        for index in indexes:
            for key in sorted(index['reviews'].get(item_target, [])):
                doc = index['documents'][key]
                if not accessible(doc['group'], index['groups'][doc['group']]):
                    continue
                if key not in reviews:
                    head = assets.store.get('domain_asset_heads', key)
                    if not head or head['revision'] != doc['revision']:
                        raise ValueError('DOMAIN_SEARCH_INDEX_CHANGED')
                    record, _ = assets._catalog_item(auth, RevisionRef.model_validate(doc['revision']), include_search=False)
                    reviews[key] = {'revision': doc['revision'], 'title': record.payload['title'],
                        'read': {'tool': 'boi_knowledge_read', 'arguments': {'revision': doc['revision'], 'view': 'meaning_index'}}}
                item.setdefault('recorded_reviews', []).append(reviews[key])
    if stamp != assets.catalog_stamp(auth, namespace):
        raise ValueError('DOMAIN_ASSET_CATALOG_CHANGED')
    return {**({'query': query} if query else {}), 'items': items, 'total_count': len(ordered), 'snapshot_digest': snapshot,
        'purpose': purpose, 'catalog_stamp': stamp, 'next_cursor': snapshot + ':' + str(end) if end < len(ordered) else None,
        'scope_status': 'restricted' if restricted else 'complete', 'restricted_count': restricted,
        'scope': 'current provisional assets owned by this principal' + (' in the exact namespace' if namespace is not None else ''),
        'canonical_absence_proven': False, 'status': 'PROVISIONAL',
        **({'reviewed_definition': target.model_dump(mode='json'),
            'relation_scope': 'Current accessible review records declaring this exact definition revision; navigation only, not review validity or applicability.'} if target is not None else {}),
        **({'content_contract': content_contract} if content_contract is not None else {}),
        **({'search_scope' if query or property_queries else 'lookup_scope': {'method': 'prepared_hybrid_candidates_rrf' if hybrid else 'prepared_lexical_and_property_candidates' if property_queries else 'prepared_lexical_candidate_retrieval' if query else 'prepared_review_reference_lookup', 'searched_asset_count': searched,
            'embedding': embedding_report,
            'matched_asset_count': len(ordered),
            'searched_asset_count_basis': 'authorized_indexed_corpus_size',
            'candidate_projection_reads': len(items), 'review_projection_reads': len(reviews), 'source_group_checks': len(source_checks),
            'semantic_match_verified': False, 'corpus_absence_proven': False,
            **({'meaning_query': {'conditions': [{**q.model_dump(mode='json'), 'matched_asset_count': len(property_counts[i])} for i, q in enumerate(property_queries)],
                'exclusion_applied': False, 'selection_authority': 'external_agent',
                'scope': 'Union of lexical and exact evidence-owner property candidates; conditions order discovery independently, not a conjunctive semantic assertion. Unknown or absent properties are not proof of irrelevance. Read exact meaning dependencies before use.'}} if property_queries else {}),
            'next_read': 'Read candidate meanings and their dependent conditions, exceptions, scope and counterevidence through the exact revision. A missing lexical match is a retrieval result, not absent knowledge.'}})}
