"""Internal evidence query over an authorized published knowledge population.

No natural-language routing, LLM, inferred authority or public endpoint. The
enclosing service must supply current snapshot/population authorization and
exact per-use source qualifications; constructing these models grants neither.
Only indexed assertion payloads are read, never all native documents or bodies.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
import time
from typing import Literal

from pydantic import Field, model_serializer, model_validator

from .filter_expression import FilterExpression, validate_filter_expression
from .knowledge_concept_reuse_contract import ConceptReuseContext
from .knowledge_evidence_logic import EvidenceAtom, evaluate_evidence_expression
from .knowledge_profile import KnowledgeProfileRegistry
from .knowledge_projection_contract import ProjectionContract, ProjectionComponent, ProjectionRevision, ProjectionScalar, ProjectionFact, definition_key
from .knowledge_projection_store import ProjectionSnapshot, encoded
from .knowledge_statement_contract import QUERY_V2, QUERY_V3, QUERY_V4, REPORTED_STATEMENT_EXISTS
from .semantic_binding_contract import Ref, RevisionRef, Digest, semantic_digest
from .typed_knowledge_meaning import TypedCondition, KnowledgeValidTime


class KnowledgeSourceScope(ProjectionContract):
    # Exact statement restriction; never authority or identity grant.
    revision: ProjectionRevision
    meaning_pointer: str = Field(min_length=1,max_length=2048,pattern=r'^/')


class KnowledgePredicateTest(ProjectionContract):
    predicate: ProjectionComponent
    operator: Literal['eq','ne','lt','lte','gt','gte']
    value: ProjectionScalar
    report_polarity: Literal['positive','negative'] | None = None
    source_scope: tuple[KnowledgeSourceScope,...] = Field(default=(),max_length=128)

    def includes_source(self,revision,pointer):
        return not self.source_scope or any(v.revision.ref==revision and v.meaning_pointer==pointer for v in self.source_scope)

    @model_serializer(mode='wrap')
    def legacy_wire(self, handler):
        value = handler(self)
        if not self.source_scope:
            value.pop('source_scope', None)
        if self.report_polarity is None:
            value.pop('report_polarity', None)
        return value


class KnowledgeScenarioValue(ProjectionContract):
    """Explicit hypothetical context, not an observation or live binding."""
    subject_ref: Ref
    predicate: ProjectionComponent
    value: ProjectionScalar


class KnowledgeEvidenceQuery(ProjectionContract):
    contract_version: Literal['boi/knowledge-evidence-query@1','boi/knowledge-evidence-query@2','boi/knowledge-evidence-query@3','boi/knowledge-evidence-query@4']='boi/knowledge-evidence-query@1'
    reuse_context: ConceptReuseContext | None = Field(default=None,exclude_if=lambda v:v is None)
    operation: Literal['select_objects','count','count_reported_objects']
    count_grain: Literal['source_object_identity'] | None = Field(default=None,exclude_if=lambda v:v is None)
    object_type: ProjectionComponent
    predicates: tuple[KnowledgePredicateTest,...]=Field(min_length=1,max_length=128)
    expression: FilterExpression
    claim_basis: Literal['source_reported','hypothetical','reported_statement_exists']
    modality: Literal['asserted','possible','intended','required']='asserted'
    polarity: Literal['positive','negative']='positive'
    time_mode: Literal['source_declared','at']
    as_of: datetime | None = None
    scenario: tuple[KnowledgeScenarioValue,...]=Field(default=(),max_length=128)

    @model_validator(mode='after')
    def query_contract(self):
        validate_filter_expression(self.expression,len(self.predicates))
        if (self.time_mode=='at') != (self.as_of is not None) or (
                self.as_of is not None and self.as_of.utcoffset() is None):
            raise ValueError('KNOWLEDGE_QUERY_TIME_REQUIRED')
        if self.scenario and self.claim_basis!='hypothetical':
            raise ValueError('KNOWLEDGE_QUERY_SCENARIO_BASIS_REQUIRED')
        if (self.contract_version in (QUERY_V2, QUERY_V3, QUERY_V4)) != (self.claim_basis == REPORTED_STATEMENT_EXISTS):
            raise ValueError('KNOWLEDGE_QUERY_STATEMENT_VERSION_REQUIRED')
        if self.operation == 'count_reported_objects':
            if self.contract_version not in (QUERY_V3, QUERY_V4) or self.count_grain != 'source_object_identity':
                raise ValueError('KNOWLEDGE_QUERY_REPORT_COUNT_GRAIN_REQUIRED')
        elif self.count_grain is not None:
            raise ValueError('KNOWLEDGE_QUERY_COUNT_GRAIN_NOT_APPLICABLE')
        if self.contract_version in (QUERY_V2, QUERY_V3, QUERY_V4):
            def supported(node):
                return node.operator in ('filter','and','or') and all(supported(child) for child in node.arguments)
            allowed_operations = ('select_objects',) if self.contract_version==QUERY_V2 else ('select_objects','count_reported_objects')
            if (self.operation not in allowed_operations or self.time_mode != 'source_declared'
                    or (self.modality != 'asserted' and self.contract_version!=QUERY_V4)
                    or any(test.operator != 'eq' and not (
                        self.contract_version in (QUERY_V3,QUERY_V4) and self.modality=='asserted' and test.operator in ('lt','lte','gt','gte')
                        and test.value.kind=='decimal' and (test.report_polarity or self.polarity)=='positive')
                        for test in self.predicates)
                    or not supported(self.expression)):
                raise ValueError('KNOWLEDGE_QUERY_STATEMENT_OPERATION_UNSUPPORTED')
        elif any(test.report_polarity is not None for test in self.predicates):
            raise ValueError('KNOWLEDGE_QUERY_STATEMENT_VERSION_REQUIRED')
        keys=[(v.subject_ref,definition_key(v.predicate)) for v in self.scenario]
        if len(set(keys))!=len(keys):raise ValueError('KNOWLEDGE_QUERY_SCENARIO_DUPLICATE')
        return self


@dataclass(frozen=True)
class KnowledgeQueryAccess:
    """Server-built population; never accept these fields as caller authority."""
    principal: str
    purpose: str
    policy_digest: str
    population_ref: str
    snapshot: ProjectionSnapshot
    member_ids: tuple[str,...]

    def __post_init__(self):
        if (not isinstance(self.member_ids,tuple) or len(self.member_ids)>50000 or len(set(self.member_ids))!=len(self.member_ids)
                or any(not isinstance(v,str) or not v.strip() for v in self.member_ids)
                or any(not isinstance(v,str) or not v.strip() for v in (self.principal,self.purpose,self.policy_digest,self.population_ref))
                or self.snapshot.generation<1 or self.snapshot.manifest_digest is None):
            raise ValueError('KNOWLEDGE_QUERY_POPULATION_REQUIRED')


@dataclass(frozen=True)
class KnowledgeQueryAuthorization:
    """Current authority check produced by the enclosing server service."""
    access_digest: str
    authority_digest: str


class KnowledgeFactUse(ProjectionContract):
    """Output of a current server qualifier, not an uploaded passed flag."""
    knowledge_revision: ProjectionRevision
    meaning_pointer: str = Field(max_length=2048)
    fact_digest: Digest
    qualification_refs: tuple[RevisionRef,...]=Field(min_length=1,max_length=64)
    purpose: Literal['filter','aggregate','traverse']
    statement_scope_digest: Digest | None = None

    @model_serializer(mode='wrap')
    def legacy_wire(self, handler):
        value = handler(self)
        if self.statement_scope_digest is None:
            value.pop('statement_scope_digest', None)
        return value


def compare_values(left,right,operator):
    if left.kind!=right.kind:raise ValueError('KNOWLEDGE_QUERY_VALUE_TYPE_MISMATCH')
    if operator not in ('eq','ne') and left.kind!='decimal':
        raise ValueError('KNOWLEDGE_QUERY_ORDERED_VALUE_REQUIRED')
    a,b=(Decimal(left.value),Decimal(right.value)) if left.kind=='decimal' else (left.value,right.value)
    return {'eq':lambda:a==b,'ne':lambda:a!=b,'lt':lambda:a<b,'lte':lambda:a<=b,
            'gt':lambda:a>b,'gte':lambda:a>=b}[operator]()


def _clause_state(clause,scenario,registry):
    clause=TypedCondition.model_validate(clause)
    if clause.expression is None:return 'unknown'
    atoms=[]
    for index,atom in enumerate(clause.atoms):
        declaration,predicate=registry.predicate(atom.predicate)
        if (atom.operator not in declaration.allowed_operators or atom.value.kind!=predicate.value_kind
                or declaration.quantity_semantics=='unknown' or declaration.value_semantics=='unknown'):
            return 'unknown'
        value=scenario.get((atom.subject_ref,definition_key(atom.predicate)))
        if value is None:atoms.append(EvidenceAtom(str(index),unknown_reasons=('context_value_missing',)))
        else:
            satisfied=compare_values(value,atom.value,atom.operator)
            atoms.append(EvidenceAtom(str(index),supporting_refs=('scenario:'+str(index),) if satisfied else (),
                refuting_refs=() if satisfied else ('scenario:'+str(index),)))
    return evaluate_evidence_expression(clause.expression,atoms).state


def _fact_applicability(fact,query,scenario,registry):
    qualifiers=fact.qualifiers
    if qualifiers.get('contract_version')!='boi/typed-assertion-qualifiers@1':return 'unknown',('qualifier_adapter_unavailable',)
    if qualifiers.get('assertion_kind')!='source_reported':return 'unknown',('source_reported_assertion_required',)
    if fact.modality!=query.modality:return 'unknown',('assertion_modality:'+fact.modality,)
    remaining=set(fact.unresolved)
    if query.time_mode=='source_declared':remaining.discard('valid_time_unknown')
    if remaining:return 'unknown',tuple(sorted(remaining))
    valid=KnowledgeValidTime.model_validate(fact.valid_time)
    if query.time_mode=='at':
        if valid.state=='unknown':return 'unknown',('valid_time_unknown',)
        if valid.state=='interval' and (query.as_of<valid.start or (valid.end is not None and query.as_of>=valid.end)):
            return 'outside',('outside_valid_time',)
    missing=[];outside=[]
    for group in ('conditions','applicability','exceptions'):
        for index,clause in enumerate(qualifiers.get(group,())):
            state=_clause_state(clause,scenario,registry)
            if state in ('unknown','conflicted'):missing.append(group+':'+str(index)+':'+state)
            elif state==('supported' if group=='exceptions' else 'refuted'):outside.append(group+':'+str(index))
    if outside:return 'outside',tuple(outside+missing)
    if missing:return 'unknown',tuple(missing)
    return 'applicable',()


def evaluate_predicate(test,facts,*,query,scenario,registry,uses,revision):
    declaration,predicate=registry.predicate(test.predicate)
    supporting,refuting,unknown,traces=[],[],[],[]
    scopes={}
    for fact in facts:
        if fact.predicate_revision!=test.predicate or not test.includes_source(revision,fact.meaning_pointer):continue
        fact_ref=revision+'#'+fact.meaning_pointer
        use=uses.get(fact.meaning_pointer)
        state,reasons=_fact_applicability(fact,query,scenario,registry)
        if (use is None or use.knowledge_revision.ref!=revision or use.fact_digest!=semantic_digest(fact)
                or use.purpose!=('aggregate' if query.operation=='count' else 'filter')
                or use.statement_scope_digest is not None):
            state,reasons='unknown',('use_qualification_missing_or_changed',)
        trace={'fact_ref':fact_ref,'applicability':state,'reasons':list(reasons),
               'fact':fact.model_dump(mode='json'),'qualification_refs':[
                    r.model_dump(mode='json') for r in use.qualification_refs] if use is not None else []}
        traces.append(trace)
        if state=='unknown':unknown.extend(reasons);continue
        if state=='outside':continue
        if declaration.quantity_semantics=='unknown' or declaration.value_semantics=='unknown':
            unknown.append('predicate_quantity_semantics_unknown');continue
        operator='eq' if test.operator=='ne' else test.operator
        equal=compare_values(fact.value,test.value,'eq')
        matched=compare_values(fact.value,test.value,operator)
        s=r=False
        if fact.modality!='asserted':
            # M(not P) does not refute M(P). For example, "may stop" and
            # "may not stop" can both hold. Query the desired inner polarity
            # explicitly; only outer NOT/ne swaps the resulting evidence pair.
            if fact.polarity==query.polarity:
                s=matched if fact.polarity=='positive' else operator=='eq' and equal
        elif fact.polarity=='negative':
            # Exclusion of one value cannot establish an arbitrary range or the
            # value of a many-valued property. Only the same proposition negates.
            r=operator=='eq' and equal
        elif matched:s=True
        elif declaration.cardinality=='one':r=True
        if fact.modality=='asserted' and query.polarity=='negative':s,r=r,s
        if test.operator=='ne':s,r=r,s
        if not s and not r:continue
        scope=semantic_digest(fact.valid_time) if query.time_mode=='source_declared' else 'at'
        scoped=scopes.setdefault(scope,{'support':[],'refute':[]})
        if s:scoped['support'].append(fact_ref)
        if r:scoped['refute'].append(fact_ref)
    for scope in scopes.values():
        supporting.extend(scope['support']);refuting.extend(scope['refute'])
    if supporting and refuting and len(scopes)>1:
        # Different declared periods are not evidence of contradiction. Ask for
        # a time scope and keep the original, separately inspectable assertions.
        supporting=[];refuting=[];unknown.append('declared_time_scopes_differ')
    if not supporting and not refuting and not unknown:unknown.append('no_applicable_evidence')
    return EvidenceAtom(definition_key(test.predicate)+':'+semantic_digest(test),
        tuple(dict.fromkeys(supporting)),tuple(dict.fromkeys(refuting)),tuple(dict.fromkeys(unknown))),traces


class KnowledgeEvidenceQueryEngine:
    def __init__(self,projection,*,registry:KnowledgeProfileRegistry,authorize,qualify,clock=time.monotonic,
                 max_facts=100000,max_seconds=10,max_result_bytes=64*1024*1024):
        if (not callable(authorize) or not callable(qualify) or type(max_facts) is not int or not 1<=max_facts<=100000
                or not 0<max_seconds<=60 or type(max_result_bytes) is not int or not 1<=max_result_bytes<=256*1024*1024):
            raise ValueError('KNOWLEDGE_QUERY_SERVER_ADAPTER_REQUIRED')
        self.projection,self.registry,self.authorize,self.qualify=projection,registry,authorize,qualify
        self.clock,self.max_facts,self.max_seconds=clock,max_facts,max_seconds
        self.max_result_bytes=max_result_bytes

    def authorize_access(self,access,phase):
        admitted=self.authorize(access,phase)
        if (not isinstance(admitted,KnowledgeQueryAuthorization) or admitted.access_digest!=semantic_digest(asdict(access))
                or not isinstance(admitted.authority_digest,str) or not admitted.authority_digest.startswith('sha256:')
                or len(admitted.authority_digest)!=71 or any(c not in '0123456789abcdef' for c in admitted.authority_digest[7:])):
            raise ValueError('KNOWLEDGE_QUERY_CURRENT_AUTHORITY_REQUIRED')
        return admitted

    def execute(self,access,query):
        if not isinstance(access,KnowledgeQueryAccess):raise ValueError('KNOWLEDGE_QUERY_ACCESS_REQUIRED')
        query=KnowledgeEvidenceQuery.model_validate(query.model_dump(mode='json'))
        started=self.clock()
        access_digest=semantic_digest(asdict(access))
        def authorize(phase):
            return self.authorize_access(access,phase)
        before=authorize('before')
        for item in (*query.predicates,*query.scenario):
            declaration,predicate=self.registry.predicate(item.predicate)
            if predicate.value_kind!=item.value.kind:raise ValueError('KNOWLEDGE_QUERY_VALUE_TYPE_MISMATCH')
            if isinstance(item,KnowledgePredicateTest) and (predicate.subject_type!=query.object_type
                    or item.operator not in declaration.allowed_operators):
                raise ValueError('KNOWLEDGE_QUERY_PREDICATE_NOT_ALLOWED')
        scenario={(v.subject_ref,definition_key(v.predicate)):v.value for v in query.scenario}
        predicate_refs=tuple(dict.fromkeys(definition_key(p.predicate) for p in query.predicates))
        counts={s:0 for s in ('supported','refuted','conflicted','unknown')}
        rows=[];fact_count=0;indexed=0;qualified_members=0;result_bytes=0
        def append_row(row):
            nonlocal result_bytes
            result_bytes+=len(encoded(row).encode())
            if result_bytes>self.max_result_bytes:raise ValueError('KNOWLEDGE_QUERY_RESULT_BUDGET_EXCEEDED')
            rows.append(row)
        members=tuple(sorted(access.member_ids))
        for start in range(0,len(members),500):
            if self.clock()-started>self.max_seconds:raise ValueError('KNOWLEDGE_QUERY_TIME_BUDGET_EXCEEDED')
            page=members[start:start+500]
            objects=self.projection.query_inputs(access.snapshot,stable_ids=page,predicate_refs=predicate_refs,
                fact_limit=max(1,self.max_facts-fact_count))
            fact_count+=sum(len(o['facts']) for o in objects.values())
            if fact_count>self.max_facts:raise ValueError('KNOWLEDGE_QUERY_FACT_BUDGET_EXCEEDED')
            for stable_id in page:
                obj=objects.get(stable_id)
                if obj is None or obj['readiness']=='unprepared' or obj['object_type']!=definition_key(query.object_type):
                    append_row({'stable_id':stable_id,'revision':obj['revision'] if obj else None,
                        'title':obj['title'] if obj else None,'state':'unknown','atoms':[],
                        'reasons':['object_not_prepared_for_requested_type'],'traces':[]})
                    counts['unknown']+=1;continue
                indexed+=1
                facts=tuple(ProjectionFact.model_validate(f) for f in obj['facts'])
                approved=[]
                for use in self.qualify(access,query,obj['revision'],facts):
                    if len(approved)>=2000:raise ValueError('KNOWLEDGE_QUERY_QUALIFICATION_BOUND')
                    approved.append(use)
                uses={u.meaning_pointer:u for u in approved if isinstance(u,KnowledgeFactUse)}
                if len(uses)!=len(approved):raise ValueError('KNOWLEDGE_QUERY_QUALIFICATION_INVALID')
                if any(u.knowledge_revision.ref==obj['revision'] and u.fact_digest==semantic_digest(f)
                        and u.purpose==('aggregate' if query.operation=='count' else 'filter')
                        and (u.statement_scope_digest is not None)==(query.claim_basis==REPORTED_STATEMENT_EXISTS)
                        for f in facts if (u:=uses.get(f.meaning_pointer)) is not None):
                    qualified_members+=1
                if query.claim_basis == REPORTED_STATEMENT_EXISTS:
                    from .knowledge_statement_evidence import evaluate_reported_statements
                    def check_budget():
                        if self.clock()-started>self.max_seconds:
                            raise ValueError('KNOWLEDGE_QUERY_TIME_BUDGET_EXCEEDED')
                    evaluated = evaluate_reported_statements(query,facts,registry=self.registry,
                        uses=uses,revision=obj['revision'],check_budget=check_budget)
                    append_row({'stable_id':stable_id,'revision':obj['revision'],'title':obj['title'],**evaluated})
                    counts[evaluated['state']]+=1
                    continue
                atoms,traces=[],{}
                for index,test in enumerate(query.predicates):
                    atom,evidence=evaluate_predicate(test,facts,query=query,scenario=scenario,registry=self.registry,
                        uses=uses,revision=obj['revision'])
                    # Repeated predicate expressions remain distinct AST leaves.
                    atoms.append(EvidenceAtom(str(index),atom.supporting_refs,atom.refuting_refs,atom.unknown_reasons))
                    for trace in evidence:
                        entry=traces.setdefault(trace['fact_ref'],{**trace,'query_tests':[]})
                        entry['query_tests'].append(index)
                result=evaluate_evidence_expression(query.expression,atoms)
                append_row({'stable_id':stable_id,'revision':obj['revision'],'title':obj['title'],'state':result.state,
                    'atoms':[asdict(a) for a in atoms],'conflict_atom_ids':list(result.conflict_atom_ids),
                    'unknown_atom_ids':list(result.unknown_atom_ids),'traces':list(traces.values())})
                counts[result.state]+=1
                if self.clock()-started>self.max_seconds:raise ValueError('KNOWLEDGE_QUERY_TIME_BUDGET_EXCEEDED')
        if authorize('after')!=before:raise ValueError('KNOWLEDGE_QUERY_AUTHORITY_CHANGED')
        if self.clock()-started>self.max_seconds:raise ValueError('KNOWLEDGE_QUERY_TIME_BUDGET_EXCEEDED')
        result={'contract_version':'boi/knowledge-evidence-result@1','execution_state':'computed_internal',
            'query_digest':semantic_digest(query),'access_digest':access_digest,'authority_digest':before.authority_digest,
            'population_ref':access.population_ref,'snapshot':asdict(access.snapshot),'counts':counts,'rows':rows,
            'coverage':{'population_members':len(members),'indexed_members':indexed,
                'members_with_qualified_assertions':qualified_members,
                'execution_completeness':'complete','source_interpretation_completeness':'not_established',
                'real_world_completeness_proven':False},
            'claim_basis':query.claim_basis,'modality':query.modality,'polarity':query.polarity,
            'time_mode':query.time_mode,'as_of':query.model_dump(mode='json')['as_of'],
            'scenario':[v.model_dump(mode='json') for v in query.scenario],
            'metrics':{'assertions_read':fact_count,'projection_document_payloads_read':0,'row_bytes':result_bytes,
                'elapsed_seconds':self.clock()-started},
            'semantic_truth_proven':False,'protected_result_ref':None}
        # This internal result is not delivered/completed until the enclosing
        # service persists it and performs its current-rights protected read.
        if query.claim_basis == REPORTED_STATEMENT_EXISTS:
            from .knowledge_statement_contract import statement_support_contract
            from .knowledge_statement_contract import query_statement_support_contract
            result['statement_consumption'] = query_statement_support_contract(query)
        result['result_digest']=semantic_digest(result)
        return result
