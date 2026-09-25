"""Provisional domain assets over the existing Wiki ledger and object store.

The application tables are recoverable publication/index projections, not a
second content authority. No canonical projection, Release or pointer is written.
Meaning stays in domain payloads and externally executed validation contracts.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import Field

from .ledger import LedgerError, RecordKind, record_digest
from .diagnostic_timing import stage_timing
from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef, semantic_digest
from .source_envelope import ArtifactEnvelope, byte_digest
from .task_knowledge import AssetKind, KnowledgeRequirement, KnowledgeUnavailable, TaskAssetRevision

_NOT_LOADED = object()

# Contract identifiers classify stored record purpose. These are structural
# publication types, never keyword rules for domain selection or answers.
_HISTORY_CONTRACTS = frozenset({
    'boi/native-agent-observation@1', 'boi/native-agent-failure@1',
    'boi/native-answer-delivery@1', 'boi/native-answer-delivery@2',
    'boi/native-source-answer-delivery@1', 'boi/native-source-answer-delivery@2',
    'boi/process-user-result@1', 'boi/process-user-result@2', 'boi/process-user-result@3',
    'boi/native-process-answer-request@1', 'boi/native-process-answer-request@2',
    'boi/native-answer-composition@1', 'boi/native-composition-record@1',
    'boi/native-composition-preparation@1', 'boi/native-definition-review@1',
    'boi/native-definition-review@2', 'boi/native-definition-review@3', 'boi/native-query-answer-review@1',
    'boi/native-query-answer-text@1', 'boi/native-query-host-record@1',
    'boi/native-query-host-result@1', 'boi/request-stage-budget@1',
    'boi/native-reviewed-source-answer@1', 'boi/knowledge-work-submission@1',
})


class DomainAssetDraft(FrozenContract):
    logical_id: Ref
    namespace: Ref
    title: Ref
    description: Ref
    kind: AssetKind
    content_json: Ref
    sources: tuple[ArtifactEnvelope, ...] = Field(min_length=1, max_length=100)
    evidence_spans: tuple[RevisionRef, ...] = ()
    dependencies: tuple[KnowledgeRequirement, ...] = ()
    conflicts_with: tuple[RevisionRef, ...] = ()
    supersedes: tuple[RevisionRef, ...] = ()
    definition_reading_ref: RevisionRef | None = None
    previous_revision: RevisionRef | None = None


class DomainAssetCreateRequest(FrozenContract):
    draft: DomainAssetDraft
    idempotency_key: str = Field(min_length=1, max_length=240)


def source_manifest_digest(sources) -> str:
    values = [s.model_dump(mode='json') if hasattr(s, 'model_dump') else s for s in sources]
    return semantic_digest(sorted(values, key=lambda s:s['artifact_ref']))


class DomainAssetStore:
    CONTRACT = 'boi/domain-asset-revision@1'
    # Preserve the existing posting/embedding contract when only read actions
    # change. Navigation is rederived for returned candidates, not reindexed.
    SEARCH_PROJECTION_VERSION = 'domain-catalog@4:task-asset@1:user-views@5:meaning-search@3:search-tokens@3:'
    NAVIGATION_PROJECTION_VERSION = 'user-views@6:'

    def __init__(self, source_intake, *, space_access=None):
        self.intake = source_intake
        self.space_access = space_access
        self.store, self.ledger, self.objects = source_intake.store, source_intake.ledger, source_intake.objects
        from .catalog_embedding import configured_client
        self.embedding_client = configured_client()

    def authorize_sources(self, authorization, sources, *, model_input=False, metadata_only=False):
        self.intake._policy(authorization)
        required = {'derive', 'model_input'} if model_input else {'derive'}
        if not required <= set(authorization.allowed_uses):
            raise ValueError('DOMAIN_ASSET_USE_NOT_AUTHORIZED')
        if len({s.artifact_ref for s in sources}) != len(sources):
            raise ValueError('DOMAIN_ASSET_DUPLICATE_SOURCE')
        for source in sources:
            if metadata_only:
                self.intake._source(authorization,source.artifact_ref,source.digest,source.role)
            else:
                self.intake.resolve_bytes(authorization=authorization, reference=source.model_dump(mode='json'))

    @staticmethod
    def _ref(record):
        return RevisionRef(ref=record.record_id, revision_digest=record_digest(record.record_id))

    def _record_metadata(self, authorization, revision: RevisionRef, *, model_input=True,
            metadata_only=False, publication=_NOT_LOADED, staged_scope_ref=None):
        self.intake._policy(authorization)
        record = self.ledger.read(revision.ref)
        value = record.payload
        if revision.revision_digest != record_digest(record.record_id):
            raise ValueError('DOMAIN_ASSET_REVISION_MISMATCH')
        staged = None
        if staged_scope_ref is not None:
            if not isinstance(staged_scope_ref,str) or not staged_scope_ref.strip() or len(staged_scope_ref)>2048:
                raise ValueError('DOMAIN_ASSET_STAGED_REVISION_UNAVAILABLE')
            key = 'domain-staged-revision:' + semantic_digest([
                authorization.principal,staged_scope_ref,revision.model_dump(mode='json')])
            staged = self.store.get('domain_asset_staging_revisions',key)
            if (not staged or staged != publication or staged.get('employee_id') != authorization.principal
                    or staged.get('policy_digest') != authorization.policy_digest
                    or staged.get('scope_ref') != staged_scope_ref
                    or staged.get('revision') != revision.model_dump(mode='json')
                    or staged.get('record_payload_digest') != semantic_digest(value)):
                raise ValueError('DOMAIN_ASSET_STAGED_REVISION_UNAVAILABLE')
        from .knowledge_space_store import HEADS
        identity = 'domain-asset-head:' + semantic_digest([value.get('employee_id'),
            value.get('namespace'),value.get('logical_id')])
        space_head = self.store.get(HEADS,identity)
        if space_head is not None:
                # Legacy owner authorization cannot bypass a current space
                # policy, including callers with a prefetched publication row.
                if not callable(self.space_access):
                    raise ValueError('DOMAIN_ASSET_SPACE_ACCESS_DENIED')
                from .knowledge_space_store import KnowledgeSpaceAccess
                staged_new = staged is not None and self.store.get('domain_knowledge_assets',revision.ref) is None
                checked_revision = RevisionRef.model_validate(space_head['content_revision']) if staged_new else revision
                if staged_new:
                    if value.get('previous_revision') != checked_revision.model_dump(mode='json'):
                        raise ValueError('DOMAIN_ASSET_STAGING_BASE_CHANGED')
                    edit, _ = self.space_access(checked_revision,'edit')
                    if (not isinstance(edit,KnowledgeSpaceAccess) or edit.actor_id!=authorization.principal
                            or edit.content_revision!=checked_revision or edit.purpose!='edit'):
                        raise ValueError('DOMAIN_ASSET_SPACE_ACCESS_DENIED')
                access, checked = self.space_access(checked_revision, 'model_input' if model_input else 'read')
                if (not isinstance(access,KnowledgeSpaceAccess) or access.actor_id != authorization.principal
                        or access.content_revision != checked_revision or checked.record_id != checked_revision.ref
                        or access.purpose != ('model_input' if model_input else 'read')
                        or (not staged_new and semantic_digest(checked.payload) != semantic_digest(value))
                        or (staged_new and edit.policy_revision != access.policy_revision)
                        or self.store.get(HEADS,identity) != space_head):
                    raise ValueError('DOMAIN_ASSET_SPACE_ACCESS_DENIED')
                if not staged_new:return record
        if (record.kind != RecordKind.KNOWLEDGE_REVISION or value.get('contract_version') != self.CONTRACT
                or value.get('status') != 'candidate' or value.get('employee_id') != authorization.principal
                or value.get('policy_digest') != authorization.policy_digest):
            raise ValueError('DOMAIN_ASSET_ACCESS_OR_CONTRACT_DENIED')
        projection = (self.store.get('domain_knowledge_assets', record.record_id)
            if publication is _NOT_LOADED else publication)
        if not projection or projection.get('record_payload_digest') != semantic_digest(value):
            raise ValueError('DOMAIN_ASSET_PUBLICATION_INCOMPLETE')
        sources = tuple(ArtifactEnvelope.model_validate(s) for s in value['sources'])
        self.authorize_sources(authorization, sources, model_input=model_input,metadata_only=metadata_only)
        return record

    @staticmethod
    def _asset(record, revision, raw):
        value = record.payload
        if byte_digest(raw) != value['content_object_ref']:
            raise ValueError('DOMAIN_ASSET_CONTENT_DRIFT')
        content = raw.decode('utf-8')
        asset = TaskAssetRevision(revision=revision, kind=value['kind'], content_json=content,
            content_digest=value['content_digest'], authority='candidate',
            dependencies=tuple(KnowledgeRequirement.model_validate(d) for d in value['dependencies']),
            evidence=tuple(RevisionRef.model_validate(r) for r in value['evidence_spans']),
            conflicts_with=tuple(RevisionRef.model_validate(r) for r in value['conflicts_with']),
            supersedes=tuple(RevisionRef.model_validate(r) for r in value['supersedes']))
        return asset

    @stage_timing('asset_record_read')
    def _read_record(self, authorization, revision: RevisionRef, *, model_input=True):
        record = self._record_metadata(authorization,revision,model_input=model_input)
        return record, self._asset(record,revision,self.objects.get(record.payload['content_object_ref']))

    def _catalog_item(self, authorization, revision, *, publication=_NOT_LOADED, include_search=True):
        record = self._record_metadata(authorization,revision,metadata_only=True,publication=publication)
        def derive(raw):
            from ..v2.asset_user_views import available_user_views,process_review_target
            from ..v2.native_definition_sources import declared_meaning_index
            from ..v2.repository import normalize_tokens
            asset = self._asset(record,revision,raw)
            content = json.loads(asset.content_json)
            contract = content.get('contract_version') if isinstance(content,dict) else None
            meanings=declared_meaning_index(content,include_source_expressions=True) if include_search and asset.kind=='definition' and isinstance(content,dict) else []
            meaning_search=[]
            for node in meanings:
                expressions=node.pop('source_expressions',[])
                meaning_search.append({'node':node,
                    'tokens':sorted(normalize_tokens(json.dumps(node['value'],ensure_ascii=False))),
                    'source_expressions':[{'evidence_pointer':e['evidence_pointer'],
                        'tokens':sorted(normalize_tokens(e['quote']))} for e in expressions]})
            return {'content_contract':contract if isinstance(contract,str) else None,
                'catalog_purpose': ('history' if contract in _HISTORY_CONTRACTS or process_review_target(content) is not None
                                    else 'knowledge' if asset.kind in ('source', 'definition') else 'capability'),
                'meaning_search':meaning_search,
                'retrieval_role':('definition' if asset.kind=='definition' else
                    'recorded_observation' if contract in ('boi/native-agent-observation@1','boi/native-agent-failure@1') or process_review_target(content) is not None else
                    'recorded_answer' if contract in ('boi/native-answer-delivery@1','boi/native-answer-delivery@2',
                        'boi/native-source-answer-delivery@1','boi/native-source-answer-delivery@2',
                        'boi/process-user-result@1','boi/process-user-result@2','boi/process-user-result@3') else 'source_or_other_asset'),
                # Index the complete immutable payload, including late claims
                # and qualifiers. Ranking retrieves candidates, not statements
                # that can bypass the existing evidence/meaning reader.
                'search_tokens':sorted(normalize_tokens(json.dumps(content,ensure_ascii=False))) if include_search else [],
                'available_user_views':available_user_views({'revision':revision.model_dump(mode='json'),
                    'asset':{'content_json':asset.content_json,'kind':asset.kind}})}
        project = getattr(self.objects,'project_verified',None)
        # Both the exact ledger revision and validator/navigation versions bind
        # interpretation; not a question string, title or review verdict cache.
        version = self.SEARCH_PROJECTION_VERSION + self.NAVIGATION_PROJECTION_VERSION + revision.revision_digest
        # Ordinary inventory and revision fences consume the same contract,
        # navigation and relationship metadata, not lexical search features.
        # Keep the small immutable projection separate so repeated page reads
        # do not rebuild/evict every meaning index in a large namespace. Current
        # authorization and content-file integrity are still checked above and
        # by project_verified. Search retains its complete existing projection.
        if not include_search:version='domain-catalog-metadata@2:task-asset@1:'+self.NAVIGATION_PROJECTION_VERSION+revision.revision_digest
        summary = (project(record.payload['content_object_ref'],version=version,derive=derive,persistent=True)
            if project else derive(self.objects.get(record.payload['content_object_ref'])))
        # Recheck current space rights after loading a cached/derived summary.
        self._record_metadata(authorization,revision,metadata_only=True,publication=publication)
        return record, summary

    def meaning_index(self, *, authorization, revision: RevisionRef):
        # Authority is checked afresh; only immutable declared meaning is reused.
        record = self._record_metadata(authorization, revision, metadata_only=True)
        def derive(raw):
            from ..v2.native_definition_sources import declared_meaning_index
            asset = self._asset(record, revision, raw)
            if asset.kind != 'definition':
                raise ValueError('DEFINITION_SOURCE_KIND_REQUIRED')
            return declared_meaning_index(json.loads(asset.content_json))
        project = getattr(self.objects, 'project_verified', None)
        version = 'declared-meaning-index@1:task-asset@1:process-knowledge@2:' + revision.revision_digest
        nodes = (project(record.payload['content_object_ref'], version=version, derive=derive, persistent=True)
            if project else derive(self.objects.get(record.payload['content_object_ref'])))
        from .metadata_revision import metadata_predecessors
        predecessors = metadata_predecessors(self, authorization, revision)
        return {'definition_revision':revision.model_dump(mode='json'), 'asset_title':record.payload['title'],
            'meaning_candidates':nodes, 'dependencies':record.payload['dependencies'],
            'conflicts_with':record.payload['conflicts_with'],
            'scope':{'authority':'candidate','source_text_provided':False,'semantic_support_verified':False,
                'absence_proven':False,'scope_inherited':False},
            'review_discovery':{'tool':'boi_knowledge_catalog','arguments':{'reviewed_definition':revision.model_dump(mode='json')}},
            'prior_review_discovery':[{'tool':'boi_knowledge_catalog',
                'arguments':{'reviewed_definition':ref.model_dump(mode='json')},
                'basis':'exact_metadata_lineage; use the original reviewed meaning revision and current admission checks',
                'review_transferred':False} for ref in predecessors],
            'detail_read':{'tool':'boi_knowledge_read','arguments':{'revision':revision.model_dump(mode='json'),
                'view':'definition_sources'}}}

    def read(self, *, authorization, revision: RevisionRef, lane: Literal['provisional']):
        if lane != 'provisional':
            raise ValueError('DOMAIN_ASSET_PROVISIONAL_LANE_REQUIRED')
        record, asset = self._read_record(authorization, revision)
        return {'revision':revision.model_dump(mode='json'), 'asset':asset.model_dump(mode='json'),
            'logical_id':record.payload['logical_id'], 'namespace':record.payload['namespace'],
            'title':record.payload['title'], 'description':record.payload['description'],
            'sources':record.payload['sources'], 'definition_reading_ref':record.payload['definition_reading_ref'],
            'knowledge_reading_status':record.payload['knowledge_reading_status'],
            'previous_revision':record.payload['previous_revision'], 'status':'PROVISIONAL',
            'canonical_projection_eligible':False}

    def reader(self, authorization):
        def read(revision):
            try:
                return self._read_record(authorization, revision)[1]
            except ValueError as exc:
                code = 'ACCESS_DENIED' if 'DENIED' in str(exc) or 'NOT_AUTHORIZED' in str(exc) else 'REVISION_MISMATCH'
                raise KnowledgeUnavailable(code) from None
            except (KeyError, OSError, LedgerError):
                raise KnowledgeUnavailable('MISSING') from None
        return read

    def graph(self, *, authorization, revision):
        record = self._record_metadata(authorization, revision, metadata_only=True)
        if record.payload['kind'] != 'definition':
            raise ValueError('KNOWLEDGE_GRAPH_DEFINITION_REQUIRED')
        from .knowledge_graph_projection import project_knowledge_graph
        def derive(raw):
            asset = self._asset(record, revision, raw)
            value = project_knowledge_graph(logical_id=record.payload['logical_id'], namespace=record.payload['namespace'],
                revision=revision.model_dump(mode='json'), content=json.loads(asset.content_json))
            # Exact cross-definition references are distinct from local meaning
            # edges; projection does not establish their current validity.
            return {**value, 'dependencies': record.payload['dependencies'],
                    'conflicts_with': record.payload['conflicts_with'], 'supersedes': record.payload['supersedes'],
                    'dependency_validity': 'requires_current_authorized_resolution'}
        project = getattr(self.objects, 'project_verified', None)
        return project(record.payload['content_object_ref'], version='knowledge-graph@2:' + revision.revision_digest, derive=derive, persistent=True) if project else derive(self.objects.get(record.payload['content_object_ref']))

    def _finish_publication(self, authorization, response, *, replayed):
        """Warm one committed revision; projection failure cannot undo success.

        Reuse disposable projections without a catalog scan or answer model.
        Configured document embeddings are prepared here, never at query time.
        Exact replay can repair warming without another publication.
        """
        revision = RevisionRef.model_validate(response['revision'])
        stages = [('catalog_metadata', lambda: self._catalog_item(authorization, revision, include_search=False)),
                  ('lexical', lambda: self._catalog_item(authorization, revision, include_search=True))]
        from .catalog_search_index import update_publication
        stages.append(('candidate_lookup', lambda: update_publication(self, authorization, revision)))
        outcomes = {}
        embedding = {'state': 'not_connected' if self.embedding_client is None else 'deferred'}
        if not callable(getattr(self.objects, 'project_verified', None)):
            return {**response, 'replayed': replayed, 'projection_status': {
                'state': 'deferred', 'reason_code': 'DOMAIN_ASSET_PROJECTION_CACHE_UNAVAILABLE',
                'durable': False, 'publication_committed': True, 'embedding': 'not_connected'}}
        try:
            record = self.ledger.read(revision.ref)
            if record.payload['kind'] == 'definition':
                stages.extend((('meanings', lambda: self.meaning_index(authorization=authorization, revision=revision)),
                               ('graph_and_dependencies', lambda: self.graph(authorization=authorization, revision=revision))))
            for name, refresh in stages:
                try:
                    result = refresh()
                    if name == 'candidate_lookup' and isinstance(result, dict):
                        embedding = {k: v for k, v in result.items() if k != 'preparation'}
                    outcomes[name] = 'prepared'
                except Exception:
                    # The receipt must not expose exception bodies/source text.
                    # Diagnose the deferred projection through its own reader.
                    outcomes[name] = 'deferred'
        except Exception:
            outcomes['metadata'] = 'deferred'
        return {**response, 'replayed': replayed, 'projection_status': {
            'state': 'prepared' if outcomes and all(v == 'prepared' for v in outcomes.values()) and embedding['state'] != 'deferred' else 'deferred',
            'stages': outcomes, 'cache_persistence': 'requested_best_effort', 'durability_verified': False,
            'publication_committed': True,
            'cache_scope': 'versioned_source_verified_object_projection', 'embedding': embedding['state'],
            'embedding_preparation': embedding,
            'semantic_quality': 'not_evaluated'}}

    @staticmethod
    def catalog_key(authorization, namespace):
        return 'domain-catalog:' + semantic_digest([authorization.principal, namespace])

    def catalog_stamp(self, authorization, namespace):
        if namespace is None:
            # A discovery snapshot spans existing owned catalogs, including newly
            # created namespaces. Reuse their epochs; no second mutable index.
            catalogs, after = [], ''
            while True:
                page = self.store.list_key_page('domain_asset_catalogs',
                    employee_id=authorization.principal, after_key=after, limit=100)
                # Disposable index preparation is not a knowledge revision.
                catalogs.extend({**entry, 'value': {k:v for k,v in entry['value'].items()
                    if not k.startswith('search_')}} for entry in page)
                if len(page) < 100:
                    break
                after = page[-1]['key']
            return semantic_digest({'principal':authorization.principal,
                'policy':authorization.policy_digest, 'catalogs':catalogs})
        value = self.store.get('domain_asset_catalogs',self.catalog_key(authorization,namespace))
        return semantic_digest({'principal':authorization.principal,'policy':authorization.policy_digest,
            'namespace':namespace,'epoch':(value or {}).get('epoch',0)})

    def definition_catalog_state(self, authorization, namespace):
        key = 'domain-definition-catalog:' + semantic_digest([authorization.principal, namespace])
        return key, self.store.get('domain_asset_catalogs', key)

    def prepare_search(self, *, authorization, namespace=None):
        from .catalog_search_index import prepare
        return prepare(self, authorization, namespace)

    def catalog(self, *, authorization, namespace, kind='', cursor='', limit=20, include_relations=False,
            reviewed_definition=None, content_contract=None, query='', purpose='auto', meaning_query=()):
        self.intake._policy(authorization)
        if 'model_input' not in authorization.allowed_uses:
            raise ValueError('DOMAIN_ASSET_USE_NOT_AUTHORIZED')
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError('DOMAIN_ASSET_PAGE_LIMIT_INVALID')
        if not isinstance(query, str) or len(query) > 2000:
            raise ValueError('DOMAIN_ASSET_QUERY_INVALID')
        if purpose not in ('auto', 'knowledge', 'history', 'capability', 'all'):
            raise ValueError('DOMAIN_ASSET_CATALOG_PURPOSE_INVALID')
        query = query.strip()
        if query or meaning_query or reviewed_definition is not None:
            from .catalog_search_index import search
            from ..v2.store_observation import observe_store_reads
            with observe_store_reads() as reads:
                result = search(self, authorization, namespace=namespace, kind=kind, content_contract=content_contract,
                    purpose=('all' if reviewed_definition is not None else 'knowledge') if purpose == 'auto' else purpose,
                    query=query, limit=limit, cursor=cursor, include_relations=include_relations,
                    reviewed_definition=reviewed_definition, meaning_query=meaning_query)
            result['search_scope' if query or meaning_query else 'lookup_scope'].update(
                full_catalog_scan_count=reads[('domain_asset_heads', 'list')] + reads[('domain_asset_heads', 'list_key_page')],
                head_point_read_calls=reads[('domain_asset_heads', 'get')],
                measurement_basis='request_local_store_adapter_calls')
            return result
        return self._catalog_scan(authorization=authorization, namespace=namespace, kind=kind, cursor=cursor,
            limit=limit, include_relations=include_relations, reviewed_definition=reviewed_definition,
            content_contract=content_contract, query=query, purpose=purpose)

    def _catalog_scan(self, *, authorization, namespace, kind='', cursor='', limit=20, include_relations=False,
            reviewed_definition=None, content_contract=None, query='', purpose='auto'):
        self.intake._policy(authorization)
        if 'model_input' not in authorization.allowed_uses:
            raise ValueError('DOMAIN_ASSET_USE_NOT_AUTHORIZED')
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1 <= limit <= 100:
            raise ValueError('DOMAIN_ASSET_PAGE_LIMIT_INVALID')
        if not isinstance(query,str) or len(query)>2000:
            raise ValueError('DOMAIN_ASSET_QUERY_INVALID')
        query=query.strip()
        if purpose not in ('auto', 'knowledge', 'history', 'capability', 'all'):
            raise ValueError('DOMAIN_ASSET_CATALOG_PURPOSE_INVALID')
        effective_purpose = ('all' if not query or reviewed_definition is not None else 'knowledge') if purpose == 'auto' else purpose
        from ..v2.repository import normalize_tokens
        from ..v2.search import lexical_token_score
        query_tokens=normalize_tokens(query)
        target=None
        if reviewed_definition is not None:
            target=RevisionRef.model_validate(reviewed_definition)
            target_record,_=self._catalog_item(authorization,target,include_search=False)
            if target_record.payload['kind']!='definition':
                raise ValueError('DOMAIN_REVIEW_TARGET_DEFINITION_REQUIRED')
            target=target.model_dump(mode='json')
        stamp = self.catalog_stamp(authorization,namespace)
        heads, after, restricted, searched = [], '', 0, 0
        review_links={};ranking_parts={};document_frequency={};retrieval_documents=0
        while True:
            page = self.store.list_key_page('domain_asset_heads',employee_id=authorization.principal,
                after_key=after,limit=100)
            keys=[item['value']['revision']['ref'] for item in page]
            publications=self.store.get_many('domain_knowledge_assets',keys) if keys else {}
            for item in page:
                value = item['value']
                if (namespace is not None and value['namespace'] != namespace) or (kind and value['kind'] != kind):
                    continue
                try:
                    record, summary = self._catalog_item(authorization,RevisionRef.model_validate(value['revision']),
                        publication=publications.get(value['revision']['ref']),include_search=bool(query))
                except ValueError as exc:
                    if 'DENIED' not in str(exc) and 'NOT_AUTHORIZED' not in str(exc):
                        raise
                    restricted += 1
                    continue
                contract = summary['content_contract']
                if content_contract is not None and contract!=content_contract:
                    continue
                views=summary['available_user_views']
                # Reference joins, not lexical equivalence: a review is history
                # about its declared definitions, never another fact source.
                for view in views:
                    if view.get('tool')=='boi_native_answer':
                        for definition in view.get('definition_revisions',[]):
                            review_links.setdefault(definition['ref'],[]).append({
                                'revision':value['revision'],'title':record.payload['title'],
                                'read':{'tool':'boi_knowledge_read','arguments':{
                                    'revision':value['revision'],'view':'meaning_index'}}})
                if effective_purpose != 'all' and summary['catalog_purpose'] != effective_purpose:
                    continue
                if target is not None and not any(target in view.get('definition_revisions',[])
                        and view.get('tool')=='boi_native_answer' for view in views):
                    continue
                searched+=1
                if query and summary['retrieval_role'] not in ('recorded_observation','recorded_answer'):
                    retrieval_documents+=1
                    for token in query_tokens & set(summary['search_tokens']):
                        document_frequency[token]=document_frequency.get(token,0)+1
                matches=[]
                if query:
                    for entry in summary['meaning_search']:
                        tokens=set(entry['tokens'])
                        meaning_overlap=query_tokens & tokens
                        expression_matches=[{'evidence_pointer':e['evidence_pointer'],
                            'matched_terms':sorted(query_tokens & set(e['tokens']))}
                            for e in entry['source_expressions'] if query_tokens & set(e['tokens'])]
                        overlap=meaning_overlap | {t for e in expression_matches for t in e['matched_terms']}
                        if overlap:matches.append({**entry['node'],
                            'matched_terms':sorted(overlap),'matched_meaning_terms':sorted(meaning_overlap),
                            'matched_source_expressions':expression_matches,
                            'retrieval_score':len(overlap)/max(1,len(query_tokens))})
                    matches.sort(key=lambda m:(-m['retrieval_score'],m['target_pointer']))
                    score=lexical_token_score(query_tokens,
                        title_tokens=normalize_tokens(record.payload['title']),
                        description_tokens=normalize_tokens(record.payload['description']),
                        body_tokens=set(summary['search_tokens']))
                    # Node matches guide subsequent selection. Asset ranking
                    # must not reward a flattened node over the same meaning
                    # split across subject, observation and applicability.
                    if score<=0:continue
                    ranking_parts[value['revision']['ref']]={
                        'title_tokens':normalize_tokens(record.payload['title']),
                        'description_tokens':normalize_tokens(record.payload['description']),
                        'body_tokens':set(summary['search_tokens'])}
                heads.append({'revision':value['revision'],
                    **({'retrieval_score':score} if query else {}),
                    'content_contract':contract if isinstance(contract,str) else None,
                    'catalog_purpose': summary['catalog_purpose'],
                    'retrieval_role':summary['retrieval_role'],
                    **({'meaning_matches':matches,'meaning_match_scope':{
                        'matched_node_count':len(matches),'returned_node_count':min(5,len(matches)),
                        'selection_complete':False,'semantic_support_verified':False,
                        'dependencies_resolved':False,'scope_inherited':False,
                        'next_step':'Select exact references for preparation; it resolves required conditions, exceptions, dependencies and counterevidence.'}} if matches else {}),
                    'available_user_views':views, **{key:record.payload[key] for key in (
                    'logical_id','namespace','kind','title','description','knowledge_reading_status')},
                    'status':'PROVISIONAL','canonical_projection_eligible':False})
                if include_relations:
                    heads[-1]['declared_relations']={name:record.payload[name]
                        for name in ('conflicts_with','supersedes')}
            if len(page) < 100:
                break
            after = page[-1]['key']
        if stamp != self.catalog_stamp(authorization,namespace):
            raise ValueError('DOMAIN_ASSET_CATALOG_CHANGED')
        if query:
            import math
            # Corpus rarity distinguishes focal terms from repeated equipment
            # metadata. Only authorized current candidates contribute; old
            # answer/review wording cannot manufacture retrieval popularity.
            from ..v2.repository import query_lexeme_weights
            lexical_mass=query_lexeme_weights(query)
            weights={t:lexical_mass[t]*(1+math.log((retrieval_documents+1)/(document_frequency.get(t,0)+1))) for t in query_tokens}
            denominator=math.fsum(weights[t] for t in sorted(weights)) or 1
            for item in heads:
                item['retrieval_score']=lexical_token_score(query_tokens,
                    **ranking_parts[item['revision']['ref']],token_weights=weights)
                matches=item.get('meaning_matches',[])
                for match in matches:
                    match['retrieval_score']=math.fsum(weights[t] for t in match['matched_terms'])/denominator
                matches.sort(key=lambda m:(-m['retrieval_score'],m['target_pointer']))
                if matches:
                    item['meaning_matches']=matches[:5]
        for item in heads:
            if item['revision']['ref'] in review_links:
                item['recorded_reviews']=review_links[item['revision']['ref']]
        heads.sort(key=lambda h:(
            h.get('retrieval_role') in ('recorded_observation','recorded_answer') if query else False,
            -h.get('retrieval_score',0),h['logical_id'],h['revision']['ref']))
        snapshot = semantic_digest({'stamp':stamp,'kind':kind,'items':heads,'restricted':restricted,'purpose':effective_purpose,
            **({'query':query} if query else {}),
            **({'content_contract':content_contract} if content_contract is not None else {}),
            **({'reviewed_definition':target} if target is not None else {})})
        offset = 0
        if cursor:
            try:
                if len(cursor)>90:
                    raise ValueError()
                bound, number = cursor.rsplit(':',1)
                offset = int(number)
                if bound != snapshot or offset < 0 or offset > len(heads):
                    raise ValueError()
            except ValueError:
                raise ValueError('DOMAIN_ASSET_CATALOG_CURSOR_STALE') from None
        end = min(len(heads),offset+limit)
        return {**({'query':query,'search_scope':{'method':'shared_lexical_candidate_retrieval',
                'searched_asset_count':searched,'matched_asset_count':len(heads),
                'semantic_match_verified':False,'corpus_absence_proven':False,
                'next_read':'Read candidate meanings and their dependent conditions, exceptions, scope and counterevidence through the exact revision. A missing lexical match is a retrieval result, not absent knowledge.'}} if query else {}),
            **({'content_contract':content_contract} if content_contract is not None else {}),
            **({'reviewed_definition':target,
                'relation_scope':'Current accessible review records declaring this exact definition revision; navigation only, not review validity or applicability.'} if target is not None else {}),
            'items':heads[offset:end], 'total_count':len(heads), 'snapshot_digest':snapshot, 'purpose':effective_purpose,
            'catalog_stamp':stamp,'scope_status':'restricted' if restricted else 'complete',
            'restricted_count':restricted,'next_cursor':f'{snapshot}:{end}' if end < len(heads) else None,
            'scope':('current provisional assets owned by this principal across authorized namespaces'
                if namespace is None else 'current provisional assets owned by this principal in the exact namespace'),
            'canonical_absence_proven':False,'status':'PROVISIONAL'}

    def _draft_material(self, authorization, draft):
        """Shared validation and byte-preserving material for immediate or staged writes."""
        self.authorize_sources(authorization, draft.sources)
        if 'store' not in authorization.allowed_uses:
            raise ValueError('DOMAIN_ASSET_STORE_NOT_AUTHORIZED')
        # Reuse the shared JSON/duplicate key/digest validator, without treating
        # a well-formed domain payload as a scientific or semantic verdict.
        content_digest = semantic_digest(json.loads(draft.content_json))
        TaskAssetRevision(revision=RevisionRef(ref=draft.logical_id, revision_digest=content_digest),
            kind=draft.kind, content_json=draft.content_json, content_digest=content_digest, authority='candidate')
        material = {**draft.model_dump(mode='json', exclude={'content_json'}), 'content_digest':content_digest,
            'content_object_ref':byte_digest(draft.content_json.encode('utf-8')),
            'employee_id':authorization.principal, 'policy_digest':authorization.policy_digest,
            'source_manifest_digest':source_manifest_digest(draft.sources),
            'contract_version':self.CONTRACT, 'status':'candidate',
            'knowledge_reading_status':'acknowledged_complete' if draft.definition_reading_ref else 'not_read',
            'semantic_status':'not_evaluated', 'canonical_projection_eligible':False}
        fingerprint = semantic_digest(material)
        return material, fingerprint

    def _validate_draft_references(self, authorization, draft, *, validate_reading=None,
            shared_reading_binding=None, reference_resolver=None):
        """Current reading/source/dependency checks; no publication side effects.

        A staging service may install its scope-bound private reference resolver.
        Ordinary create continues to require published candidate dependencies.
        """
        from ..v2.atomic_store_contract import AtomicWrite
        delivered = None
        reading_fences = []
        if draft.definition_reading_ref is not None:
            if validate_reading is None:
                raise ValueError('DOMAIN_ASSET_READING_RESOLVER_REQUIRED')
            reading = self.ledger.read(draft.definition_reading_ref.ref)
            if reading.kind != RecordKind.RUN or not isinstance(reading.payload.get('context_ref'),dict):
                raise ValueError('DOMAIN_CONTEXT_READING_BINDING_DENIED')
            prepared = self.ledger.read(reading.payload['context_ref']['ref'])
            if prepared.kind != RecordKind.RUN or not isinstance(prepared.payload.get('namespace'),str):
                raise ValueError('DOMAIN_CONTEXT_READING_BINDING_DENIED')
            scope_key, scope_row = self.definition_catalog_state(authorization,prepared.payload['namespace'])
            delivered = validate_reading(draft.definition_reading_ref, draft.sources)
            shared_revisions = frozenset()
            if shared_reading_binding is not None:
                # This callback is installed by the application service only,
                # after the ordinary reading and source ACL checks succeeded.
                # It replaces author-head fences only for proven package members.
                shared_revisions, shared_fences = shared_reading_binding(prepared)
                reading_fences.extend(shared_fences)
            reading_fences.append(AtomicWrite('domain_asset_catalogs',scope_key,scope_row,scope_row or {
                'employee_id':authorization.principal,'namespace':prepared.payload['namespace'],'epoch':0}))
            from .task_context_reading import context_head_fence_revisions
            current_heads=context_head_fence_revisions(delivered,preparation_version=prepared.payload['contract_version'])
            for asset in delivered.assets:
                if asset.authority != 'candidate' or asset.revision not in current_heads or asset.revision in shared_revisions:continue
                stored, _ = self._read_record(authorization,asset.revision)
                selected_key = 'domain-asset-head:' + semantic_digest([authorization.principal,
                    stored.payload['namespace'],stored.payload['logical_id']])
                selected = self.store.get('domain_asset_heads',selected_key)
                if not selected or selected['revision'] != asset.revision.model_dump(mode='json'):
                    raise ValueError('DOMAIN_CONTEXT_SELECTED_REVISION_CHANGED')
                reading_fences.append(AtomicWrite('domain_asset_heads',selected_key,selected,selected))
        delivered_assets = {a.revision:a for a in delivered.assets} if delivered is not None else {}
        def validate_reference(ref):
            # Canonical definitions are resolved only by the current authorized
            # release reader behind the stored delivery receipt, never by a
            # caller-supplied authority flag or a candidate publication index.
            if ref not in delivered_assets:
                if reference_resolver is None:
                    self._read_record(authorization, ref)
                else:
                    reference_resolver(ref)
        for dep in draft.dependencies:
            # Required missing definitions must be visible in context preparation;
            # a draft itself may record unresolved optional references explicitly.
            if dep.required:
                validate_reference(dep.revision)
        for ref in (*draft.conflicts_with, *draft.supersedes):
            validate_reference(ref)
        source_ids = {s.artifact_ref for s in draft.sources}
        for ref in draft.evidence_spans:
            span = self.ledger.read(ref.ref)
            if (span.kind != RecordKind.EVIDENCE_SPAN or record_digest(span.record_id) != ref.revision_digest
                    or span.payload.get('artifact_ref') not in source_ids
                    or span.payload.get('employee_id') != authorization.principal
                    or span.payload.get('policy_digest') != authorization.policy_digest):
                raise ValueError('DOMAIN_ASSET_EVIDENCE_BINDING_DENIED')
        from .knowledge_content import validate_content_envelope
        validate_content_envelope(json.loads(draft.content_json), draft=draft,
                                  ledger=self.ledger, objects=self.objects)
        return tuple(reading_fences)

    def _publication_metadata(self, draft, material, fingerprint, record):
        from .native_contract_catalog import contract_projection
        from .native_reference_projection import reference_projection
        from .native_profile_catalog import profile_projection
        from .native_text_projection import projection
        revision = self._ref(record)
        response = {'revision':revision.model_dump(mode='json'), 'logical_id':draft.logical_id,
            'namespace':draft.namespace, 'status':'PROVISIONAL','canonical_projection_eligible':False,
            'source_manifest_digest':material['source_manifest_digest'],
            'knowledge_reading_status':material['knowledge_reading_status'], 'semantic_status':'not_evaluated'}
        row = {'employee_id':material['employee_id'], 'revision':revision.model_dump(mode='json'),
            'logical_id':draft.logical_id, 'namespace':draft.namespace, 'kind':draft.kind,
            'title':draft.title, 'description':draft.description, 'fingerprint':fingerprint,
            'record_payload_digest':semantic_digest(record.payload), **reference_projection(record),
            **profile_projection(record,draft), **contract_projection(record,draft),
            'text_projection_digest':projection(record,draft)[1]}
        return response, row

    def _text_projection_write(self, draft, record):
        from .native_text_projection import COLLECTION, projection
        from ..v2.atomic_store_contract import AtomicWrite
        value, _ = projection(record,draft)
        old = self.store.get(COLLECTION,record.record_id)
        if old is not None and (old.get('wire')!=value['wire'] or old.get('employee_id')!=value['employee_id']):
            raise ValueError('KNOWLEDGE_TEXT_PROJECTION_CHANGED')
        return AtomicWrite(COLLECTION,record.record_id,old,old or value)

    def _catalog_update_writes(self, authorization, updates, *, generation_scope_id=None):
        """Coalesce a native batch's head changes without repeated catalog writes."""
        from ..v2.atomic_store_contract import AtomicWrite
        groups = {}
        for namespace, head_key, kind in updates:
            groups.setdefault(namespace, []).append((head_key, kind))
        writes = []
        for namespace, members in groups.items():
            if len({key for key, kind in members}) != len(members):
                raise ValueError('DOMAIN_ASSET_DUPLICATE_BATCH_HEAD')
            catalog_key = self.catalog_key(authorization, namespace)
            catalog = self.store.get('domain_asset_catalogs', catalog_key)
            protocol = (catalog or {}).get('publication_protocol')
            if protocol is not None and generation_scope_id is None:
                raise ValueError('DOMAIN_ASSET_GENERATION_PUBLICATION_REQUIRED')
            if protocol not in (None, 'knowledge-generations@1') or (
                    protocol and catalog.get('generation_scope_id') != generation_scope_id):
                raise ValueError('DOMAIN_ASSET_GENERATION_SCOPE_CONFLICT')
            generation = ({'publication_protocol':'knowledge-generations@1',
                           'generation_scope_id':generation_scope_id} if generation_scope_id else {})
            writes.append(AtomicWrite('domain_asset_catalogs', catalog_key, catalog, {
                **(catalog or {}), **generation, 'employee_id':authorization.principal, 'namespace':namespace,
                'epoch':(catalog or {}).get('epoch', 0) + len(members),
                'search_initialized':(catalog or {}).get('search_initialized', not catalog or catalog.get('epoch') == 0),
                'search_pending':list(dict.fromkeys([*(catalog or {}).get('search_pending', []), *(key for key, kind in members)]))}))
            definitions = sum(kind == 'definition' for key, kind in members)
            if definitions:
                definition_key, definition_row = self.definition_catalog_state(authorization, namespace)
                writes.append(AtomicWrite('domain_asset_catalogs', definition_key, definition_row, {
                    'employee_id':authorization.principal, 'namespace':namespace,
                    'epoch':(definition_row or {}).get('epoch', 0) + definitions}))
        return tuple(writes)

    def create(self, *, authorization, request: DomainAssetCreateRequest, validate_reading=None, publication_fences=(),
            shared_reading_binding=None):
        from ..v2.atomic_store_contract import AtomicWrite
        request = DomainAssetCreateRequest.model_validate(request.model_dump(mode='python'))
        draft = request.draft
        material, fingerprint = self._draft_material(authorization, draft)
        key = 'domain-asset-request:' + semantic_digest([authorization.principal, request.idempotency_key])
        reservation = self.store.get('domain_asset_idempotency', key)
        if reservation:
            if reservation.get('fingerprint') != fingerprint:
                raise ValueError('DOMAIN_ASSET_IDEMPOTENCY_CONFLICT')
            if reservation.get('response'):
                # Replay reads an already admitted revision. Publishing that
                # definition may itself have invalidated the old intake scope.
                self._read_record(authorization,RevisionRef.model_validate(reservation['response']['revision']),model_input=False)
                return self._finish_publication(authorization, reservation['response'], replayed=True)
        head_key = 'domain-asset-head:' + semantic_digest([authorization.principal,draft.namespace,draft.logical_id])
        head = self.store.get('domain_asset_heads',head_key)
        if head and head.get('fingerprint') == fingerprint:
            record, _ = self._read_record(authorization,RevisionRef.model_validate(head['revision']),model_input=False)
            response = {'revision':head['revision'],'logical_id':draft.logical_id,'namespace':draft.namespace,
                'status':'PROVISIONAL','canonical_projection_eligible':False,
                'source_manifest_digest':material['source_manifest_digest'],
                'knowledge_reading_status':material['knowledge_reading_status'],'semantic_status':'not_evaluated'}
            row = {'employee_id':authorization.principal,'fingerprint':fingerprint,
                'occurred_at':record.occurred_at,'response':response}
            if not self.store.atomic_compare_and_write((AtomicWrite('domain_asset_idempotency',key,reservation,row),
                    AtomicWrite('domain_asset_heads',head_key,head,head))):
                raise ValueError('DOMAIN_ASSET_PUBLICATION_CONFLICT')
            return self._finish_publication(authorization, response, replayed=True)
        catalog = self.store.get('domain_asset_catalogs', self.catalog_key(authorization, draft.namespace))
        if (catalog or {}).get('publication_protocol') is not None:
            raise ValueError('DOMAIN_ASSET_GENERATION_PUBLICATION_REQUIRED')
        reading_fences = self._validate_draft_references(authorization, draft,
            validate_reading=validate_reading, shared_reading_binding=shared_reading_binding)
        self.objects.put(draft.content_json.encode('utf-8'))
        if reservation is None:
            value = {'employee_id':authorization.principal, 'fingerprint':fingerprint,
                'occurred_at':self.intake.clock().isoformat()}
            self.store.atomic_compare_and_write((AtomicWrite('domain_asset_idempotency',key,None,value),))
            reservation = self.store.get('domain_asset_idempotency',key)
        if not reservation or reservation.get('fingerprint') != fingerprint:
            raise ValueError('DOMAIN_ASSET_IDEMPOTENCY_CONFLICT')
        if reservation.get('response'):
            revision = RevisionRef.model_validate(reservation['response']['revision'])
            self._read_record(authorization, revision, model_input=False)
            return self._finish_publication(authorization, reservation['response'], replayed=True)
        head_key = 'domain-asset-head:' + semantic_digest([authorization.principal,draft.namespace,draft.logical_id])
        head = self.store.get('domain_asset_heads',head_key)
        if head and head.get('fingerprint') == fingerprint:
            record, _ = self._read_record(authorization,RevisionRef.model_validate(head['revision']),model_input=False)
        else:
            current = RevisionRef.model_validate(head['revision']) if head else None
            if current != draft.previous_revision:
                raise ValueError('DOMAIN_ASSET_PREVIOUS_REVISION_CONFLICT')
            if current:
                previous, _ = self._read_record(authorization,current,model_input=False)
                if previous.payload['kind'] != draft.kind:
                    raise ValueError('DOMAIN_ASSET_KIND_CHANGE_REQUIRES_NEW_IDENTITY')
            record = self.ledger.append(RecordKind.KNOWLEDGE_REVISION, material,
                authority='agent', occurred_at=reservation['occurred_at'])
        revision = self._ref(record)
        response, row = self._publication_metadata(draft, material, fingerprint, record)
        prior = self.store.get('domain_knowledge_assets',record.record_id)
        if prior is not None:
            # Reusing an older native revision must preserve its preparation
            # state. A new head cannot advertise a projection never committed.
            row.pop('text_projection_digest',None)
            if 'text_projection_digest' in prior:
                row['text_projection_digest']=prior['text_projection_digest']
            from .native_contract_catalog import preserve_contract_preparation
            row = preserve_contract_preparation(row, prior)
        writes = [AtomicWrite('domain_asset_idempotency',key,reservation,{**reservation,'response':response}),
            AtomicWrite('domain_asset_heads',head_key,head,row)]
        if prior is None:
            writes.append(AtomicWrite('domain_knowledge_assets',record.record_id,None,row))
            writes.append(self._text_projection_write(draft,record))
        elif prior.get('record_payload_digest') != row['record_payload_digest']:
            raise ValueError('DOMAIN_ASSET_PROJECTION_DRIFT')
        if not head or head['revision'] != row['revision']:
            writes.extend(self._catalog_update_writes(authorization, ((draft.namespace, head_key, draft.kind),)))
        # If an updated head/catalog is also a read precondition, retain one
        # CAS with the captured expected value and the intended publication.
        for fence in (*reading_fences, *publication_fences):
            matching = next((w for w in writes if (w.collection,w.key)==(fence.collection,fence.key)),None)
            if matching is None:writes.append(fence)
            elif matching.expected != fence.expected:
                raise ValueError('DOMAIN_ASSET_READING_CHANGED_BEFORE_PUBLICATION')
        if not self.store.atomic_compare_and_write(writes):
            recovered = self.store.get('domain_asset_idempotency',key)
            if recovered and recovered.get('fingerprint') == fingerprint and recovered.get('response'):
                self._read_record(authorization,revision,model_input=False)
                return self._finish_publication(authorization, recovered['response'], replayed=True)
            raise ValueError('DOMAIN_ASSET_PUBLICATION_CONFLICT')
        return self._finish_publication(authorization, response, replayed=False)
