"""Typed source, graph, read-scope and Wiki-state evidence for process answers.

The host supplies complete MCP readings. This module binds those readings; it
does not infer entailment, absence, scientific truth, or candidate authority.
The original answer@1 contract remains unchanged for historical receipts.
"""
from __future__ import annotations

import json
import copy
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft, ProcessQuotation
from boi_api.app.governed_runtime.semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef, semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext
from .boi_process_answer_layout import AnswerLayout, validate_layout


class MeaningCitation(FrozenContract):
    kind: Literal['meaning'] = 'meaning'
    asset_revision: RevisionRef
    target_pointer: str = Field(max_length=4096, description='Exact target_pointer returned by meaning_citation_targets for this revision. The empty JSON pointer selects the root object when it has declared evidence. Process assertions/terms and source-backed native definition objects use the same resolver. Do not invent a target from a name; identity and declared evidence are resolved by the host.')


class SourceCitation(FrozenContract):
    kind: Literal['source_quote'] = 'source_quote'
    source_revision_digest: Digest
    quotation: ProcessQuotation


class SourceScopeCitation(FrozenContract):
    kind: Literal['source_scope'] = 'source_scope'
    source_revision_digest: Digest
    # No model-selected subset may pretend to be a complete source reading.
    reason: Ref = Field(description='Explain the relevance of the complete source reading to this limited evidence gap. A scope receipt does not prove absence or authorize a claim about other sources.')


class WikiStateCitation(FrozenContract):
    kind: Literal['wiki_state'] = 'wiki_state'
    context_digest: Digest
    field: Literal['lane','dependency_completeness','source_fidelity','domain_verdict','task_readiness','display_status']


class AssetStateCitation(FrozenContract):
    kind: Literal['asset_state'] = 'asset_state'
    asset_revision: RevisionRef
    field: Literal['authority']


class ExecutionResultCitation(FrozenContract):
    kind: Literal['execution_result'] = 'execution_result'
    result_digest: Digest = Field(description='Exact digest of a result supplied by the host execution context, not a model-authored result. It supports only statements about that execution, not source facts or equipment behavior.')


AnswerCitation = Annotated[MeaningCitation | SourceCitation | SourceScopeCitation | WikiStateCitation | AssetStateCitation | ExecutionResultCitation,
    Field(discriminator='kind')]


def statement_evidence_error(kind,kinds):
    """Shared citation-role contract; no text classification or source judgment."""
    if kind=='runtime_state':
        if not kinds <= {'wiki_state','asset_state','execution_result'}:return 'ANSWER_RUNTIME_REQUIRES_WIKI_STATE'
    elif kinds & {'wiki_state','asset_state','execution_result'}:
        return 'ANSWER_SPLIT_RUNTIME_AND_SOURCE_STATEMENTS'
    elif kind=='recommendation':
        if not kinds & {'meaning','source_quote','source_scope'}:return 'ANSWER_RECOMMENDATION_EVIDENCE_REQUIRED'
    elif kind=='evidence_gap':
        if 'source_scope' not in kinds:return 'ANSWER_GAP_REQUIRES_COMPLETE_SOURCE_SCOPE'
    elif not kinds & {'meaning','source_quote'}:
        return 'ANSWER_FACT_REQUIRES_POSITIVE_EVIDENCE'
    return None


class AnswerStatement(FrozenContract):
    text: Ref
    kind: Literal['source_reported_fact','interpretation','evidence_gap','runtime_state','recommendation']
    citations: tuple[AnswerCitation,...] = Field(min_length=1)

    @model_validator(mode='after')
    def evidence_domain(self):
        error=statement_evidence_error(self.kind,{c.kind for c in self.citations})
        if error:raise ValueError(error)
        return self


class SourceStatement(AnswerStatement):
    kind: Literal['source_reported_fact','interpretation']
    citations: tuple[Annotated[MeaningCitation | SourceCitation | SourceScopeCitation,Field(discriminator='kind')],...] = Field(min_length=1,
        description='Include positive source/meaning evidence. A statement combining a supported interpretation and a scoped non-establishment may also cite the complete source scope. Scope alone is not positive evidence and never proves absence.')


class GapStatement(AnswerStatement):
    kind: Literal['evidence_gap']
    citations: tuple[Annotated[SourceScopeCitation | MeaningCitation | SourceCitation,Field(discriminator='kind')],...] = Field(min_length=1,
        description='A complete source scope is required. Include positive citations too when the gap explanation also states source facts; neither kind substitutes for the other.')


class RuntimeStatement(AnswerStatement):
    kind: Literal['runtime_state']
    citations: tuple[Annotated[WikiStateCitation | AssetStateCitation | ExecutionResultCitation,Field(discriminator='kind')],...] = Field(min_length=1)


class RecommendationStatement(AnswerStatement):
    kind: Literal['recommendation']
    text: Ref = Field(description='An explicitly proposed next step, not a source-reported obligation or a guarantee. State it naturally as a proposal. Factual premises remain in separate bound statements.')
    citations: tuple[Annotated[MeaningCitation | SourceCitation | SourceScopeCitation,Field(discriminator='kind')],...] = Field(min_length=1)
    basis_statement_pointers: tuple[Ref,...] = Field(min_length=1,description='Existing factual, interpretive or evidence-gap statements motivating this proposal; /sentences/i or /limitations/i. References do not prove suitability or necessity.')


TypedStatement=Annotated[SourceStatement | GapStatement | RuntimeStatement | RecommendationStatement,Field(discriminator='kind')]


def _request_facet_schema(schema):
    # Match the existing binder invariant without changing historical parsing.
    # Full branches survive provider schema closure and keep every field.
    presentation=copy.deepcopy(schema)
    grounded=copy.deepcopy(schema)
    unresolved=copy.deepcopy(schema)
    presentation['properties']['aspect']={'type':'string','const':'presentation'}
    grounded['properties']['citations']['minItems']=1
    grounded['required']=list(dict.fromkeys([*grounded.get('required',[]),'citations']))
    unresolved['properties']['unresolved_reason']={'type':'string','minLength':1}
    unresolved['required']=list(dict.fromkeys([*unresolved.get('required',[]),'unresolved_reason']))
    schema['anyOf']=[presentation,grounded,unresolved]


class RequestFacet(FrozenContract):
    model_config = ConfigDict(json_schema_extra=_request_facet_schema)
    aspect: Literal['target','scope','time','condition','comparison','result_unit','explanation','presentation'] = Field(description='Presentation describes requested answer format or length, grounded in request_quote; result_unit describes domain result units and requires domain evidence or an unresolved reason. Classification remains subject to semantic review.')
    request_quote: Ref
    interpretation: Ref
    citations: tuple[Annotated[MeaningCitation|SourceCitation|SourceScopeCitation|ExecutionResultCitation,Field(discriminator='kind')],...]=()
    statement_pointers: tuple[Ref,...]=Field(default=(),description='Statement paths in this answer, /sentences/i or /limitations/i.')
    unresolved_reason: Ref | None = None


class RequestPlan(FrozenContract):
    """Candidate request interpretation, not an evaluation key or truth claim."""
    facets: tuple[RequestFacet,...]=Field(min_length=1)


def request_plan_proposal(plan):
    return {'facets':[{**{k:v for k,v in facet.items() if k in RequestFacet.model_fields},
        'citations':[{k:v for k,v in citation.items() if k in
            {'meaning':MeaningCitation,'source_quote':SourceCitation,'source_scope':SourceScopeCitation,'execution_result':ExecutionResultCitation}[citation['kind']].model_fields}
            for citation in facet['citations']]} for facet in plan['facets']]}


def answer_evidence_groups(answer):
    yield 'sentences',answer.get('sentences',[])
    yield 'limitations',answer.get('limitations',[])
    if answer.get('request_plan'):
        yield 'request_plan/facets',answer['request_plan']['facets']


class QuestionAnswer(FrozenContract):
    question_id: Ref
    sentences: tuple[TypedStatement,...] = Field(min_length=1)
    # Free-text limitations used to bypass the sentence evidence contract.
    limitations: tuple[TypedStatement,...] = ()
    layout: AnswerLayout | None = Field(default=None,exclude_if=lambda v:v is None)
    request_plan: RequestPlan | None = Field(default=None,exclude_if=lambda v:v is None)


class ProcessAnswerDraftV2(FrozenContract):
    contract_version: Literal['boi/process-answer-draft@2'] = 'boi/process-answer-draft@2'
    context_digest: Digest
    answers: tuple[QuestionAnswer,...] = Field(min_length=1)


def validate_source_readings(context, sources):
    """Check complete manifest delivery under the same source/ACL context.

    Source projection must come from Wiki's MCP read path; caller-supplied
    hashes alone are not authorization. The external invocation pins inputs.
    """
    context=TaskKnowledgeContext.model_validate(context)
    from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
    if source_manifest_digest([s['source'] for s in sources])!=context.source_manifest_digest:
        raise ValueError('ANSWER_SOURCE_CONTEXT_MISMATCH')
    indexed={}
    for source in sources:
        ref,manifest=source['source'],source['manifest']
        if ref['digest'] in indexed:raise ValueError('ANSWER_SOURCE_REVISION_AMBIGUOUS')
        if manifest['source_revision_digest']!=ref['digest']:
            raise ValueError('ANSWER_SOURCE_MANIFEST_MISMATCH')
        if (manifest['employee_id'],manifest['policy_digest'])!=(context.principal_id,context.policy_digest):
            raise ValueError('ANSWER_SOURCE_ACCESS_CONTEXT_MISMATCH')
        fields={f['field_locator']:f for f in source['fields']}
        expected={f['field_locator']:f for f in manifest['fields']}
        if len(fields)!=len(source['fields']) or len(expected)!=len(manifest['fields']) or set(fields)!=set(expected):
            raise ValueError('ANSWER_SOURCE_READING_INCOMPLETE')
        for locator,field in fields.items():
            if any(field.get(k)!=v for k,v in expected[locator].items()):
                raise ValueError('ANSWER_SOURCE_FIELD_MANIFEST_MISMATCH')
            if byte_digest(field['text'].encode())!=field['content_digest']:
                raise ValueError('ANSWER_SOURCE_FIELD_DIGEST_MISMATCH')
        indexed[ref['digest']]={'source':ref,'manifest':manifest,'fields':fields,
            'reading_digest':semantic_digest(source)}
    return indexed


def _source_binding(indexed, revision, quote):
    source=indexed.get(revision)
    if source is None:raise ValueError('ANSWER_SOURCE_NOT_READ')
    field=source['fields'].get(quote.field_locator)
    if field is None or field['field_state']!='present':raise ValueError('ANSWER_SOURCE_FIELD_UNAVAILABLE')
    start=-1
    for _ in range(quote.occurrence+1):
        start=field['text'].find(quote.quote,start+1)
        if start<0:raise ValueError('ANSWER_QUOTE_NOT_IN_SOURCE')
    return {'span_ref':field['span_ref'],'source_revision_digest':revision,'field_locator':quote.field_locator,
        'field_content_digest':field['content_digest'],'start':start,'end':start+len(quote.quote),
        'quote_digest':byte_digest(quote.quote.encode()),'offset_basis':'decoded_unicode_codepoints'}


def _native_meaning_groups(content,indexed):
    from boi_api.app.v2.native_definition_sources import project_definition_evidence
    sources=[{'source':s['source'],'fields':list(s['fields'].values())} for s in indexed.values()]
    groups={}
    for binding in project_definition_evidence(content,sources,''):
        owner=binding.get('meaning_context')
        if owner is not None:groups.setdefault(owner['pointer'],[]).append(binding)
    return groups


def _native_source_binding(indexed, evidence):
    """Bind an explicit empty field as a field observation, never a quotation.

    Empty units and correction fragments are existing source facts. They do
    not establish a unit, state encoding, value, or absence outside that field.
    Process quotations retain their nonempty substring contract.
    """
    if evidence['quote'] != '':
        return _source_binding(indexed,evidence['source_revision_digest'],ProcessQuotation(
            field_locator=evidence['field_locator'],quote=evidence['quote']))
    source=indexed.get(evidence['source_revision_digest'])
    if source is None:raise ValueError('ANSWER_SOURCE_NOT_READ')
    field=source['fields'].get(evidence['field_locator'])
    if (field is None or field.get('field_state')!='empty' or field.get('text')!=''
            or field.get('content_digest')!=byte_digest(b'')):
        raise ValueError('ANSWER_SOURCE_EMPTY_FIELD_UNAVAILABLE')
    return {'span_ref':field['span_ref'],'source_revision_digest':evidence['source_revision_digest'],
        'field_locator':field['field_locator'],'field_content_digest':field['content_digest'],
        'start':0,'end':0,'quote_digest':byte_digest(b''),'offset_basis':'decoded_unicode_codepoints',
        'evidence_kind':'empty_field'}


class _MeaningReadState:
    """Parsed projections owned by one invocation and its validated source read.

    No permissions, source offsets, resolved closures or answer values are
    cached. Public entry points construct fresh state after source validation.
    """
    def __init__(self,indexed,meaning_uses=()):
        self.meaning_uses={use.revision:use for use in meaning_uses}
        self.indexed=indexed
        self._entries={}

    def entry(self,asset):
        key=(asset.revision,asset.content_digest)
        if key not in self._entries:
            self._entries[key]={'content':json.loads(asset.content_json)}
        return self._entries[key]

    def native_groups(self,asset):
        entry=self.entry(asset)
        if 'native_groups' not in entry:
            entry['native_groups']=_native_meaning_groups(entry['content'],self.indexed)
        return entry['native_groups']

    def process(self,asset):
        entry=self.entry(asset)
        if 'process' not in entry:
            draft=ProcessKnowledgeDraft.model_validate(entry['content']['draft'])
            targets={f'/records/{ri}/{kind}/{i}':(ri,kind,i) for ri,r in enumerate(draft.records)
                for kind in ('terms','assertions') for i,_ in enumerate(getattr(r,kind))}
            identities=[({t.term_id:i for i,t in enumerate(r.terms)},
                         {a.assertion_id:i for i,a in enumerate(r.assertions)}) for r in draft.records]
            entry['process']=(draft,targets,identities)
        return entry['process']


def _native_meaning_evidence(content,pointer,indexed,*,_groups=None):
    from boi_api.app.v2.native_definition_sources import native_meaning_links
    groups=_native_meaning_groups(content,indexed) if _groups is None else _groups
    result=[];nodes={};expanded=set();uses=set()
    def include(target,role):
        if (target,role) in uses:return
        uses.add((target,role))
        if target not in nodes:
            entries=groups.get(target)
            if not entries:raise ValueError('ANSWER_MEANING_TARGET_UNAVAILABLE')
            if any(e['status'] not in ('located','located_empty') for e in entries):
                raise ValueError('ANSWER_NATIVE_MEANING_EVIDENCE_UNRESOLVED')
            bindings=[]
            for entry in entries:
                evidence=entry['evidence']
                binding=_native_source_binding(indexed,evidence)
                if binding['span_ref']!=evidence['span_ref']:
                    raise ValueError('ANSWER_NATIVE_MEANING_SPAN_MISMATCH')
                bindings.append(binding)
            nodes[target]={'target_pointer':target,
                'value':copy.deepcopy(entries[0]['meaning_context']['value']),'source_bindings':bindings,
                'scope_inherited':False,'semantic_relation_status':'model_proposed'}
        result.append({**nodes[target],'role':role})
        if target in expanded:return
        expanded.add(target)
        # Owned qualifier fields preserve the historical contract. Sibling and
        # ancestor qualifiers still do not become inherited conditions.
        for qualifier in ('conditions','exceptions','applicability'):
            prefix=target+'/'+qualifier
            for child in groups:
                if child==prefix or child.startswith(prefix+'/'):
                    include(child,qualifier)
        for link in native_meaning_links(nodes[target]['value'],target):
            include(link['relation_pointer'],'declared_relation')
            include(link['target_pointer'],link['relation'])
    include(pointer,'direct')
    return result



def _published_meaning_evidence(asset,pointer,indexed,state):
    from boi_api.app.governed_runtime.knowledge_content import decode_knowledge_content,ContentUseContract
    from boi_api.app.governed_runtime.knowledge_use_contract import typed_use_closure
    use=state.meaning_uses.get(asset.revision)
    if use is None:raise ValueError('ANSWER_EXPLAIN_QUALIFICATION_REQUIRED')
    if pointer not in use.roots:raise ValueError('ANSWER_EXPLAIN_SCOPE_NOT_QUALIFIED')
    content=decode_knowledge_content(state.entry(asset)['content'])
    admitted=typed_use_closure(content,ContentUseContract(purpose='explain',required_meaning_pointers=use.roots))
    if (use.content_digest!=asset.content_digest or admitted['scope_digest']!=use.scope_digest
            or admitted['closure']!=use.closure):
        raise ValueError('ANSWER_EXPLAIN_SCOPE_CHANGED')
    selected=typed_use_closure(content,ContentUseContract(purpose='explain',required_meaning_pointers=(pointer,)))
    result=[]
    for target in (pointer,*(p for p in selected['closure'] if p!=pointer)):
        bindings=[]
        for evidence in content.evidence_bindings:
            if evidence.meaning_pointer!=target and not evidence.meaning_pointer.startswith(target+'/'):continue
            binding=_source_binding(indexed,evidence.source_revision_digest,ProcessQuotation(
                field_locator=evidence.field_locator,quote=evidence.quote,occurrence=evidence.quote_occurrence))
            if binding['span_ref']!=evidence.span.ref:raise ValueError('ANSWER_PUBLISHED_MEANING_SPAN_MISMATCH')
            if binding not in bindings:bindings.append(binding)
        if not bindings:raise ValueError('ANSWER_PUBLISHED_MEANING_EVIDENCE_REQUIRED')
        result.append({'target_pointer':target,'value':selected['nodes'][target],
            'object_type':copy.deepcopy(content.meaning['object_type']),
            'source_bindings':bindings,'role':'direct' if target==pointer else 'depends_on',
            'scope_inherited':False,'semantic_relation_status':'source_reported_qualified',
            'qualification_ref':use.qualification_ref.model_dump(mode='json'),'purpose':'explain'})
    return result

def _meaning_evidence(asset, pointer, indexed, *, assets=None, trail=frozenset(),_read_state=None):
    marker=(asset.revision,pointer)
    if marker in trail:raise ValueError('ANSWER_DEFINITION_REUSE_CYCLE')
    trail=trail|{marker}
    state=_MeaningReadState(indexed) if _read_state is None else _read_state
    if state.indexed is not indexed:raise ValueError('ANSWER_MEANING_REUSE_CONTEXT_MISMATCH')
    content=state.entry(asset)['content']
    if content.get('contract_version')=='boi/knowledge-content@1':
        return _published_meaning_evidence(asset,pointer,indexed,state)
    if (content.get('contract_version')=='boi/svid-native-interpretation@1'
            or (content.get('contract_version') not in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2')
                and state.native_groups(asset))):
        return _native_meaning_evidence(content,pointer,indexed,_groups=state.native_groups(asset))
    if content.get('contract_version') not in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
        raise ValueError('ANSWER_MEANING_TYPE_UNSUPPORTED')
    draft,targets,identities=state.process(asset)
    if pointer not in targets:raise ValueError('ANSWER_MEANING_TARGET_UNAVAILABLE')
    visited=set();closure=[]
    def include(target,role):
        if target in visited:return
        visited.add(target)
        ri,kind,i=targets[target];record=draft.records[ri];item=getattr(record,kind)[i]
        quotes=list(item.evidence)
        if kind=='assertions':
            quotes.extend(q for name in ('conditions','exceptions','applicability') for qualifier in getattr(item,name) for q in qualifier.evidence)
        # Rebind the typed quotations against the freshly read source bytes;
        # never trust offsets supplied inside a candidate's content_json.
        closure.append({'target_pointer':target,'role':role,'value':item.model_dump(mode='json'),
            'source_bindings':[_source_binding(indexed,draft.source_revision_digest,q) for q in quotes]})
        terms,claims=identities[ri]
        include(f'/records/{ri}/terms/{terms[record.process_ref]}','process_identity')
        if kind=='assertions':
            include(f'/records/{ri}/terms/{terms[item.subject_ref]}','subject_identity')
            for ref in item.object_refs:include(f'/records/{ri}/terms/{terms[ref]}','object_identity')
            for ref in item.depends_on:include(f'/records/{ri}/assertions/{claims[ref]}','declared_dependency')
        elif item.reused_definition is not None:
            from boi_api.app.governed_runtime.process_reuse_contract import ProcessDefinitionUse
            from agent_kit.python.boi_process_reuse import definition_node_evidence
            candidates=[u for u in content.get('definition_uses',[]) if u.get('term_pointer')==target
                and u.get('application')=='interpret_term']
            if len(candidates)!=1:raise ValueError('ANSWER_EXACT_DEFINITION_USE_REQUIRED')
            raw_use=candidates[0]
            scoped=raw_use.get('contract_version')=='boi/process-definition-use@2'
            if scoped:
                from boi_api.app.governed_runtime.process_reuse_scope_contract import ProcessDefinitionUseV2
                from agent_kit.python.boi_process_scope import bind_scope_facets
                use=ProcessDefinitionUseV2.model_validate({k:v for k,v in raw_use.items() if k in ProcessDefinitionUseV2.model_fields})
            else:
                if raw_use.get('contract_version') is not None:raise ValueError('ANSWER_DEFINITION_USE_VERSION_UNSUPPORTED')
                use=ProcessDefinitionUse.model_validate({k:v for k,v in raw_use.items() if k in ProcessDefinitionUse.model_fields})
            if use.definition_node.asset_revision!=item.reused_definition:
                raise ValueError('ANSWER_DEFINITION_USE_PROJECTION_MISMATCH')
            definition=(assets or {}).get(use.definition_node.asset_revision)
            if definition is None:raise ValueError('ANSWER_REUSED_DEFINITION_NOT_READ')
            if not any(d.revision==definition.revision and d.required for d in asset.dependencies):
                raise ValueError('ANSWER_DEFINITION_DEPENDENCY_NOT_DECLARED')
            for node in definition_node_evidence(definition,use.definition_node,indexed,assets=assets,trail=trail,
                    include_record_applicability=not scoped):
                closure.append({**node,'asset_revision':node.get('asset_revision',definition.revision.model_dump(mode='json')),
                    'role':'reused_definition','definition_node_ref':use.definition_node.model_dump(mode='json'),
                    'semantic_relation_status':'model_proposed'})
            if scoped:
                # Recompute from the actual draft/context/source readings.
                # The stored resolved_scope and its claimed offsets are not trusted.
                scope=bind_scope_facets(use,draft=draft,definition_asset=definition,indexed=indexed)
                for comparison in scope['comparisons']:
                    for side in ('local','definition'):
                        for selected in comparison[side]:
                            if selected['decision']['disposition']!='applies':continue
                            for node in selected['graph_evidence']:
                                closure.append({**node,'asset_revision':(asset if side=='local' else definition).revision.model_dump(mode='json'),
                                    'role':'definition_use_scope','scope_side':side,'scope_dimension':comparison['dimension'],
                                    'scope_facet_pointer':selected['facet']['target_pointer'],
                                    'definition_node_ref':use.definition_node.model_dump(mode='json'),
                                    'semantic_relation_status':'model_proposed'})
    include(pointer,'direct')
    return closure


def meaning_citation_targets(*,context,sources,asset_revision,target_pointers=None):
    """Expose existing bound meaning to planning with the SAME answer resolver.

    These are selectable candidates, not conclusions about the user's intent or
    source truth. Explicit pointers select only their existing closures; None
    retains discovery of every target. No semantic relation is inferred from
    document position, and a selection never establishes search completeness.
    """
    context=TaskKnowledgeContext.model_validate(context)
    assets={a.revision:a for a in context.assets}
    revision=RevisionRef.model_validate(asset_revision)
    asset=assets.get(revision)
    if asset is None or asset.kind!='definition':raise ValueError('ANSWER_ASSET_NOT_READ')
    indexed=validate_source_readings(context,sources)
    if target_pointers is not None:
        if (not isinstance(target_pointers,(list,tuple))
                or any(not isinstance(p,str) or (p!='' and not p.startswith('/')) for p in target_pointers)):
            raise ValueError('ANSWER_MEANING_SELECTION_INVALID')
        if len(set(target_pointers))!=len(target_pointers):
            raise ValueError('ANSWER_MEANING_SELECTION_DUPLICATE')
    state=_MeaningReadState(indexed,context.meaning_uses)
    content=state.entry(asset)['content']
    if content.get('contract_version')=='boi/knowledge-content@1':
        use=state.meaning_uses.get(asset.revision)
        if use is None:raise ValueError('ANSWER_EXPLAIN_QUALIFICATION_REQUIRED')
        available=use.roots
    elif (content.get('contract_version')=='boi/svid-native-interpretation@1'
            or (content.get('contract_version') not in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2')
                and state.native_groups(asset))):
        available=state.native_groups(asset)
    elif content.get('contract_version')=='boi/process-source-note@1':
        # Raw-source intake deliberately has no interpreted graph yet.
        available={}
    elif content.get('contract_version') in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
        _,available,_=state.process(asset)
    else:
        raise ValueError('ANSWER_MEANING_TYPE_UNSUPPORTED')
    pointers=available if target_pointers is None else target_pointers
    if any(pointer not in available for pointer in pointers):
        raise ValueError('ANSWER_MEANING_TARGET_UNAVAILABLE')
    targets=[]
    for pointer in pointers:
        target={'asset_revision':revision.model_dump(mode='json'),'target_pointer':pointer,
            'semantic_support':'not_evaluated','authority':asset.authority}
        try:
            target.update(binding_status='bound',graph_evidence=_meaning_evidence(
                asset,pointer,indexed,assets=assets,_read_state=state))
        except ValueError as exc:
            target.update(binding_status='unresolved',reason_code=str(exc),graph_evidence=[])
        targets.append(target)
    return targets


def source_scope_reference(source):
    """Project an already validated/authorized source reading, not an absence verdict."""
    return {'source_revision_digest':source['source']['digest'],
        'reading_digest':source['reading_digest'],'manifest_ref':source['manifest'].get('manifest_ref'),
        'manifest_digest':semantic_digest(source['manifest']),
        'field_inventory':[{k:f[k] for k in ('field_locator','span_ref','field_state','content_digest')}
            for f in source['fields'].values()],
        'coverage':source['manifest'].get('projection_scope','complete_provided_source'),
        **({'full_manifest_ref':source['manifest']['full_manifest_ref'],
            'total_field_count':source['manifest']['total_field_count']}
            if source['manifest'].get('projection_scope')=='selected_source_fields' else {}),
        'absence_proven':False}


def bind_process_answers_v2(draft, *, context, sources, questions, execution_results=None):
    draft=ProcessAnswerDraftV2.model_validate(draft);context=TaskKnowledgeContext.model_validate(context)
    if draft.context_digest!=context.context_digest:raise ValueError('ANSWER_CONTEXT_MISMATCH')
    indexed=validate_source_readings(context,sources)
    meaning_state=_MeaningReadState(indexed,context.meaning_uses)
    expected={q['id']:q for q in questions};ids=[a.question_id for a in draft.answers]
    if len(expected)!=len(questions) or len(set(ids))!=len(ids) or set(ids)!=set(expected):raise ValueError('ANSWER_QUESTION_COVERAGE_MISMATCH')
    assets={a.revision:a for a in context.assets}
    bound_execution_results={}
    def bind_citations(items):
        citations=[]
        for citation in items:
            wire=citation.model_dump(mode='json');bindings=[]
            if citation.kind=='meaning':
                asset=assets.get(citation.asset_revision)
                if asset is None or asset.kind!='definition':raise ValueError('ANSWER_ASSET_NOT_READ')
                wire['graph_evidence']=_meaning_evidence(asset,citation.target_pointer,indexed,assets=assets,_read_state=meaning_state)
                bindings=[b for entry in wire['graph_evidence'] for b in entry['source_bindings']]
                wire['asset_authority']=asset.authority
                use=meaning_state.meaning_uses.get(asset.revision)
                if use is not None:wire['meaning_use']=use.model_dump(mode='json')
            elif citation.kind=='source_quote':
                bindings=[_source_binding(indexed,citation.source_revision_digest,citation.quotation)]
            elif citation.kind=='source_scope':
                source=indexed.get(citation.source_revision_digest)
                if source is None:raise ValueError('ANSWER_SOURCE_NOT_READ')
                wire.update(source_scope_reference(source))
            elif citation.kind=='execution_result':
                observed=(execution_results or {}).get(citation.result_digest)
                if observed is None:
                    raise ValueError('ANSWER_EXECUTION_NOT_OBSERVED')
                if semantic_digest(observed)!=citation.result_digest:
                    raise ValueError('ANSWER_EXECUTION_DIGEST_MISMATCH')
                bound_execution_results.setdefault(citation.result_digest,copy.deepcopy(observed))
                wire.update(state_origin='host_observed_execution')
            elif citation.kind=='wiki_state':
                if citation.context_digest!=context.context_digest:raise ValueError('ANSWER_STATE_CONTEXT_MISMATCH')
                wire.update(value=getattr(context,citation.field),state_origin='wiki_context_envelope')
            else:
                asset=assets.get(citation.asset_revision)
                if asset is None:raise ValueError('ANSWER_ASSET_NOT_READ')
                wire.update(value=asset.authority,state_origin='wiki_asset_envelope')
            wire['source_bindings']=bindings
            wire['evidence_digest']=semantic_digest(wire)
            citations.append(wire)
        return citations
    def statement(item):
        return {'text':item.text,'kind':item.kind,'citations':bind_citations(item.citations),'semantic_support':'not_evaluated',
            **({'basis_statement_pointers':list(item.basis_statement_pointers)} if isinstance(item,RecommendationStatement) else {})}
    answers=[]
    for ai,answer in enumerate(draft.answers):
        statement_map={f'/{group}/{i}':item for group in ('sentences','limitations')
            for i,item in enumerate(getattr(answer,group))}
        for pointer,item in statement_map.items():
            if isinstance(item,RecommendationStatement):
                refs=item.basis_statement_pointers
                if (len(set(refs))!=len(refs) or any(ref not in statement_map or
                        statement_map[ref].kind not in ('source_reported_fact','interpretation','evidence_gap') for ref in refs)):
                    raise ValueError('ANSWER_RECOMMENDATION_BASIS_INVALID')
        body=' '.join(s.text for s in answer.sentences)
        if answer.layout is not None:validate_layout(answer.layout,answer.sentences,answer.limitations)
        limit=expected[answer.question_id]['max_body_characters']
        if limit is not None and len(body)>limit:raise ValueError('ANSWER_BODY_TOO_LONG')
        planned={}
        if answer.request_plan is not None:
            question=expected[answer.question_id]
            request_texts=[question['question'],question.get('response_request') or '']
            pointers={f'/{part}/{i}' for part in ('sentences','limitations') for i,_ in enumerate(getattr(answer,part))}
            facets=[]
            for facet in answer.request_plan.facets:
                if not any(facet.request_quote in text for text in request_texts):
                    raise ValueError('ANSWER_PLAN_REQUEST_QUOTE_NOT_FOUND')
                prefix=f'/answers/{ai}'
                selected_pointers=[p[len(prefix):] if p.startswith(prefix+'/') else p for p in facet.statement_pointers]
                if not set(selected_pointers)<=pointers:raise ValueError('ANSWER_PLAN_STATEMENT_NOT_FOUND')
                if facet.aspect != 'presentation' and not facet.citations and not facet.unresolved_reason:raise ValueError('ANSWER_PLAN_MEANING_OR_UNRESOLVED_REQUIRED')
                # Reuse exact source/meaning binding, without claiming that the
                # interpretation or its correspondence to a sentence is true.
                bound_citations=bind_citations(facet.citations)
                facets.append({**facet.model_dump(mode='json'),'statement_pointers':selected_pointers,'citations':bound_citations})
            planned={'request_plan':{'facets':facets,'request_digest':semantic_digest(question),
                'semantic_support':'not_evaluated'}}
        answers.append({'question_id':answer.question_id,'body':body,'body_characters':len(body),**planned,
            'sentences':[statement(s) for s in answer.sentences],'limitations':[statement(s) for s in answer.limitations],
            **({'layout':[b.model_dump(mode='json') for b in answer.layout]} if answer.layout is not None else {})})
    return {'contract_version':'boi/bound-process-answers@2','context_digest':context.context_digest,
        **({'execution_results':bound_execution_results} if bound_execution_results else {}),
        'source_reading_digests':[s['reading_digest'] for s in indexed.values()], 'answers':answers,
        'reference_binding':'pass','source_fidelity':'not_evaluated','scientific_correctness':'not_evaluated',
        'status':'PROVISIONAL','canonical_projection_eligible':False}
