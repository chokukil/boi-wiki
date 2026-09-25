"""Current PAT/session authority and logical queries; never caller ACL or SQL."""
from typing import Literal

from fastapi import Depends
from fastapi.responses import JSONResponse
from pydantic import Field

from ..governed_runtime.knowledge_query import KnowledgeEvidenceQuery
from ..governed_runtime.knowledge_concept_reuse_contract import ConceptReuseContext, ScopedConceptReuseDeclaration
from ..governed_runtime.knowledge_statement_contract import statement_support_contract
from ..governed_runtime.knowledge_statement_contract import traversal_support_contract
from ..governed_runtime.knowledge_relation_traversal import KnowledgeTraversalRequest
from ..governed_runtime.knowledge_result_relations import KnowledgeResultRelationsRequest
from ..governed_runtime.knowledge_report_intersection import KnowledgeReportIntersectionRequest
from ..governed_runtime.knowledge_profile_discovery import ProfileDiscoveryRequest
from ..governed_runtime.native_profile_repair import NativeProfileRepairRequest
from ..governed_runtime.knowledge_space_sets import KnowledgeSetRead
from ..governed_runtime.semantic_binding_contract import FrozenContract
from .auth import require_scope
from .models import Principal


class KnowledgeQueryExecute(KnowledgeSetRead):
    query: KnowledgeEvidenceQuery
    idempotency_key: str = Field(min_length=1, max_length=240)


class KnowledgeQueryRecover(KnowledgeQueryExecute):
    """The exact original request identifies the saved dispatch; no execution."""


class KnowledgeQuerySummary(FrozenContract):
    result_ref: str = Field(pattern=r'^protected:prepared-knowledge-query:[0-9a-f-]{36}$')


class KnowledgeQueryPage(KnowledgeQuerySummary):
    include_witnesses: bool = Field(default=False, strict=True)
    group: Literal['all', 'supported', 'refuted', 'conflicted', 'unknown', 'reported'] | None = None
    page_size: int = Field(default=20, ge=1, le=100, strict=True)
    cursor: str | None = Field(default=None, min_length=1, max_length=4096)


class KnowledgeQueryWitnesses(KnowledgeQuerySummary):
    object_id: str = Field(min_length=1, max_length=2048)
    page_size: int = Field(default=20, ge=1, le=50, strict=True)
    cursor: str | None = Field(default=None, min_length=1, max_length=8192)


def query_schema():
    return {'contract_version': 'boi/prepared-knowledge-query-api@1',
        'concept_reuse_declaration':ScopedConceptReuseDeclaration.model_json_schema(),
        'statement_consumption':statement_support_contract(),
        'modal_statement_queries':{
            'query_contract_version':'boi/knowledge-evidence-query@4',
            'modalities':['asserted','possible','intended','required'],
            'matching':'exact modality per query; no upgrade to asserted world fact',
            'nonasserted_operators':['eq'],
            'nonasserted_qualification':'boi/source-statement-review@2 with full original source review',
            'different_values':'nonasserted alternatives do not refute each other by single cardinality',
            'conditions':'retain source conditions, exceptions and applicability without world evaluation',
            'counts':'distinct source objects reporting the selected modality; not actual events or fulfilled requirements',
            'mixed_modalities':'separate queries retain separate witnesses; no automatic common-context inference'},
        'statement_comparison':{
            'query_contract_version':'boi/knowledge-evidence-query@3',
            'operations':['select_objects','count_reported_objects'],
            'count_grain':'source_object_identity',
            'deduplication':'one stable source object per saved population snapshot, not evidence rows',
            'numeric_operators':['lt','lte','gt','gte'],
            'numeric_basis':'positive source-reported decimal in exact Profile quantity and unit; no implicit conversion',
            'negative_numeric_reports':'retained as context, never converted to an interval',
            'qualification':'current filter source-inventory review; not aggregate or observed-value authority',
            'counts':'supported and conflicted are disjoint; report existence count is their sum; unknown is retained',
            'world_condition_satisfaction':'not_evaluated',
            'sum_and_average_supported':False},
        'traversal_consumption':traversal_support_contract(),
        'requests': {name: model.model_json_schema() for name, model in (
            ('resolve_concepts', ConceptReuseContext),
            ('discover', ProfileDiscoveryRequest),
            ('repair_profiles', NativeProfileRepairRequest),
            ('execute', KnowledgeQueryExecute), ('recover', KnowledgeQueryRecover),
            ('summary', KnowledgeQuerySummary), ('page', KnowledgeQueryPage),
            ('witnesses', KnowledgeQueryWitnesses),
            ('traverse', KnowledgeTraversalRequest),
            ('intersect_reports', KnowledgeReportIntersectionRequest),
            ('relate_results', KnowledgeResultRelationsRequest))},
        'instructions': [
            'intersect_reports combines 2-16 saved select_objects results for independent report existence on the same exact object revision. All inputs must share one current set_ref and object_type. Each input report keeps its own field context, time, modality, conflict state and witness request. This is different from AND inside one source context. All reported pages are consumed; 10000 total input rows, 4MiB output and 30seconds are hard failure budgets, never silent truncation. Nonmembership is not source absence or a negative fact. Use separate signed queries then intersect_reports for record properties reported in different cells; do not use it to claim common condition satisfaction.',
            'For an explicit intersection, relate_results target_selection=reported keeps the complete target population and annotates intersection_member only where an authored positive source path and a supported/conflicted target report both exist at the exact same identity/revision. Read target_witness_read as well as source path witnesses. Default population mode does not apply the target query filter. Source/edge/target conditions remain separate; this is report-set intersection, not proof of joint world applicability. Missing target reports and unprepared members remain unknown, not negative.',
            'relate_results reads the reported selection of source_result_ref and all rows of target_population_result_ref, then follows one exact authored positive object predicate. Both saved results require current query qualifications. It reruns no selection SQL, retains selection witnesses and edge conditions separately, and reports links rather than world applicability or negative facts. Limits:100 selected sources,100 target members,256 edges,2MiB response,30seconds; excess fails explicitly. Conflicted source reports remain identified per path; unresolved relations make status partial. This bounded read is not persisted.',
            'resolve_concepts reads selected exact native concept-reuse definitions and their current reviews, verifies scoped original assertions, and returns a query with reuse_context. Pass that query unchanged to execute. No dictionary aliases, source truth or fact qualification is inferred. Original query, relation, target and review revisions remain digest-bound in the protected result and are rechecked on read.',
            'Discover authorized Profile components by lexical query or declared role/type/operator. Candidates do not establish meaning or fact qualification.',
            'An editor can repair_profiles with exact published revisions and one stable idempotency key. This rebuilds declarations from native content without changing it or granting use qualifications. Retry an uncertain repair with the identical request.',
            'Select exact Profile component revisions from authorized knowledge; the host selects meaning.',
            'Use a server-issued model_input set_ref for the requested Private, Team or Public population.',
            'Preserve source modality, polarity, time and explicit hypothetical conditions in the logical query.',
            'Execute with a stable idempotency key and current use qualifications. Summary/page/witnesses reread recorded observations with current rights; they do not renew historical qualifications or grant current-query reuse.',
            'After an uncertain response use recover with the identical execute request. It reconciles stored work without executing SQL.',
            'Counts separate supported, refuted, conflicted and unknown. Check unprepared-content coverage.',
            'Query@2 reported_statement_exists checks source-report existence within exact recorded source context; it does not establish world applicability. Omitted page group uses reported (supported plus conflicted) for all positive witnesses; Query@1 still defaults to supported. Explicit state groups narrow the page. Negative-only contexts remain unknown for existence; preserve counterreports.',
            'Query@2 requires a current authenticated full source-inventory review. Legacy filter grants cannot authorize it; opaque source conditions stay inspectable rather than being evaluated as world conditions.',
            'Count retains no object pages. Select_objects stores known states; unknown pages use the unchanged population.',
            'A page identifies exact revisions for boi_knowledge_read. Source access is checked separately.',
            'Page include_witnesses=true bundles the existing saved-witness first pages for reported rows, retaining every independent current-rights check and cursor. Limit20 objects and2MiB; excess fails explicitly. Follow non-null object and witness cursors. No source text, new query execution or renewed qualification is implied.',
            'New select_objects statement results retain paged witnesses from the original SQL snapshot. Follow witness_read with witnesses, then document_read to retrieve exact matching assertions and source fields. Atomic counterevidence can be masked by the final expression; inspect final_support/final_refute separately. Old results explicitly lack recorded witnesses and are never rerun to manufacture them.',
            'Historical reads preserve the recorded counts and decisions across use/check refreshes and implementation releases. Native content, source policy, authority or population changes still withhold these sparse results because unknown pages require an unchanged population. Never silently rerun an unknown execution or replace an old result with a new query.',
            'Traverse starts at an exact published revision and follows only selected exact object-predicate components in their authored direction. Each edge requires a current traverse source-relation review; filter qualifications do not transfer. Source fields and exact target type/current rights are checked separately. Negative relations are retained without continuation; limits and missing qualifications remain explicit. Conditions are preserved per edge, never composed into world applicability, immediate adjacency or a cause. This bounded read does not create a saved result.',
        ], 'semantic_truth_proven': False, 'source_access_granted': False,
        'population_completeness_qualified': False}


def register_knowledge_query_routes(router, *, service, principal, call):
    @router.post('/api/v2/knowledge-queries/intersect-reports')
    async def intersect_reports(payload: KnowledgeReportIntersectionRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return JSONResponse(await call(service.domain_intake.knowledge_queries, identity, payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/knowledge-queries/resolve-concepts')
    async def resolve_concepts(payload: ConceptReuseContext, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return JSONResponse(await call(service.domain_intake.knowledge_queries, identity, payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/knowledge-queries/relate-results')
    async def relate_results(payload: KnowledgeResultRelationsRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return JSONResponse(await call(service.domain_intake.knowledge_queries, identity, payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/knowledge-queries/traverse')
    async def traverse(payload: KnowledgeTraversalRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return JSONResponse(await call(service.domain_intake.knowledge_queries, identity, payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/knowledge-queries/repair-profiles')
    async def repair(payload: NativeProfileRepairRequest, identity: Principal = Depends(principal)):
        require_scope(identity,'boi.draft')
        require_scope(identity,'boi.read')
        return JSONResponse(await call(service.domain_intake.repair_profiles,identity,payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})

    @router.post('/api/v2/knowledge-queries/discover')
    async def discover(payload: ProfileDiscoveryRequest, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await call(service.domain_intake.profile_candidates, identity, payload)

    @router.get('/api/v2/knowledge-queries/schema')
    async def schema(identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return query_schema()

    @router.post('/api/v2/knowledge-queries')
    async def execute(payload: KnowledgeQueryExecute, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await call(service.domain_intake.knowledge_queries, identity, payload)

    @router.post('/api/v2/knowledge-queries/summary')
    async def summary(payload: KnowledgeQuerySummary, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await call(service.domain_intake.knowledge_queries, identity, payload)

    @router.post('/api/v2/knowledge-queries/recover')
    async def recover(payload: KnowledgeQueryRecover, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await call(service.domain_intake.knowledge_queries, identity, payload)

    @router.post('/api/v2/knowledge-queries/page')
    async def page(payload: KnowledgeQueryPage, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return await call(service.domain_intake.knowledge_queries, identity, payload)

    @router.post('/api/v2/knowledge-queries/witnesses')
    async def witnesses(payload: KnowledgeQueryWitnesses, identity: Principal = Depends(principal)):
        require_scope(identity, 'boi.read')
        return JSONResponse(await call(service.domain_intake.knowledge_queries, identity, payload),
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
