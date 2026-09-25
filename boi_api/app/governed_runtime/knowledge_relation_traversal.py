"""Bounded current-space traversal of explicitly qualified source relations.

Exact Profile components are selected by the host. This reader never interprets
labels, reverses a predicate, resolves aliases, composes world conditions or
derives a cause. It performs no persistent write or publication.
"""
import json
from collections import deque
from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from time import monotonic
from typing import Literal

from pydantic import Field, model_validator

from .knowledge_content import decode_knowledge_content
from .knowledge_profile import KnowledgeProfileDeclaration, KnowledgeProfileRegistry
from .knowledge_profile_projector import ADAPTER_REVISION, KnowledgeProfileProjector, native_identity
from .knowledge_projection_contract import (ProjectionComponent, ProjectionFact, ProjectionPublication,
    PublicationChange, definition_key)
from .knowledge_published_read import PublishedKnowledgeReader, document_url
from .knowledge_published_sources import PublishedSourceFields
from .knowledge_space_store import KnowledgeSpaceStore
from .knowledge_statement_contract import REPORTED_STATEMENT_EXISTS, traversal_support_contract
from .knowledge_use_reader import KnowledgeUseReader
from .knowledge_query import KnowledgeScenarioValue, _fact_applicability
from .knowledge_evidence_logic import EvidenceAtom, evaluate_evidence_expression
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import FrozenContract, RevisionRef, semantic_digest
from .typed_knowledge_meaning import TypedKnowledgeMeaning


class KnowledgeTraversalPathBranch(FrozenContract):
    branch_id: str = Field(min_length=1, max_length=128)
    fact_refs: tuple[str, ...] = Field(min_length=1, max_length=4)
    requirement: Literal['required','alternative']
    alternative_group: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode='after')
    def branch_role(self):
        if ((self.requirement=='required') != (self.alternative_group is None)
                or len(set(self.fact_refs))!=len(self.fact_refs)):
            raise ValueError('KNOWLEDGE_TRAVERSAL_BRANCH_ROLE_INVALID')
        return self


class KnowledgeTraversalConditionEvaluation(FrozenContract):
    contract_version: Literal['boi/knowledge-traversal-condition-evaluation@1'] = \
        'boi/knowledge-traversal-condition-evaluation@1'
    scenario: tuple[KnowledgeScenarioValue, ...] = Field(default=(), max_length=128)
    modality: Literal['asserted','possible','intended','required'] = 'asserted'
    time_mode: Literal['source_declared','at'] = 'source_declared'
    as_of: datetime | None = None
    branches: tuple[KnowledgeTraversalPathBranch, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode='after')
    def evaluation_scope(self):
        if ((self.time_mode=='at') != (self.as_of is not None)
                or self.as_of is not None and self.as_of.utcoffset() is None
                or len({item.branch_id for item in self.branches})!=len(self.branches)):
            raise ValueError('KNOWLEDGE_TRAVERSAL_CONDITION_SCOPE_INVALID')
        keys=[(item.subject_ref,definition_key(item.predicate)) for item in self.scenario]
        if len(set(keys))!=len(keys):
            raise ValueError('KNOWLEDGE_TRAVERSAL_SCENARIO_DUPLICATE')
        return self


class KnowledgeTraversalRequest(FrozenContract):
    contract_version: Literal['boi/knowledge-relation-traversal@1'] = 'boi/knowledge-relation-traversal@1'
    start_revision: RevisionRef
    predicates: tuple[ProjectionComponent, ...] = Field(min_length=1, max_length=8)
    direction: Literal['authored_subject_to_object'] = 'authored_subject_to_object'
    claim_basis: Literal['reported_statement_exists'] = REPORTED_STATEMENT_EXISTS
    max_depth: int = Field(default=1, ge=1, le=8, strict=True)
    max_nodes: int = Field(default=32, ge=1, le=128, strict=True)
    max_edges: int = Field(default=64, ge=1, le=256, strict=True)
    condition_evaluation: KnowledgeTraversalConditionEvaluation | None = None

    @model_validator(mode='after')
    def exact_predicates(self):
        if len(set(self.predicates)) != len(self.predicates):
            raise ValueError('KNOWLEDGE_TRAVERSAL_DUPLICATE_PREDICATE')
        return self


def _evidence_composition(atoms, operator):
    if len(atoms)==1:
        expression={'operator':'filter','filter_index':0}
    else:
        expression={'operator':operator,'arguments':[
            {'operator':'filter','filter_index':index} for index in range(len(atoms))]}
    return evaluate_evidence_expression(expression,atoms)


def evaluate_relation_path_conditions(*, traversal_result, evaluation, registry):
    """Attach scenario/time judgments to exact returned source-reported paths.

    This adapter neither discovers edges nor invents branch roles.  Callers name
    exact fact references from one traversal result and state whether each path
    is required or an alternative.  Existing query condition semantics perform
    every edge judgment.
    """
    if (not isinstance(traversal_result,dict)
            or traversal_result.get('contract_version')!='boi/knowledge-relation-traversal-result@1'
            or not isinstance(registry,KnowledgeProfileRegistry)):
        raise ValueError('KNOWLEDGE_TRAVERSAL_CONDITION_INPUT_REQUIRED')
    request=KnowledgeTraversalConditionEvaluation.model_validate(evaluation)
    scenario={(item.subject_ref,definition_key(item.predicate)):item.value for item in request.scenario}
    query=SimpleNamespace(modality=request.modality,time_mode=request.time_mode,as_of=request.as_of)
    edges={}
    for index,edge in enumerate(traversal_result.get('edges') or ()):
        if not isinstance(edge,dict):
            raise ValueError('KNOWLEDGE_TRAVERSAL_CONDITION_EDGE_INVALID')
        fact=ProjectionFact.model_validate(edge.get('fact'))
        source_revision=RevisionRef.model_validate(edge.get('source_revision'))
        fact_ref=source_revision.ref+'#'+fact.meaning_pointer
        use=edge.get('use') or {}
        if fact_ref in edges:
            raise ValueError('KNOWLEDGE_TRAVERSAL_CONDITION_FACT_DUPLICATE')
        edges[fact_ref]=(index,edge,fact,use)

    branch_results=[];branch_atoms=[]
    for branch in request.branches:
        selected=[]
        for fact_ref in branch.fact_refs:
            item=edges.get(fact_ref)
            if item is None:
                raise ValueError('KNOWLEDGE_TRAVERSAL_CONDITION_FACT_UNAVAILABLE')
            index,edge,fact,use=item
            if (edge.get('continuation') is not True or fact.polarity!='positive'):
                raise ValueError('KNOWLEDGE_TRAVERSAL_PATH_POSITIVE_REQUIRED')
            if (use.get('purpose')!='traverse' or use.get('fact_digest')!=semantic_digest(fact)
                    or not use.get('statement_scope_digest')):
                raise ValueError('KNOWLEDGE_TRAVERSAL_PATH_QUALIFICATION_REQUIRED')
            if selected and selected[-1][1].get('target')!=edge.get('source'):
                raise ValueError('KNOWLEDGE_TRAVERSAL_PATH_CONTINUITY_REQUIRED')
            selected.append((index,edge,fact,use))
        edge_atoms=[];edge_results=[]
        for index,edge,fact,use in selected:
            state,reasons=_fact_applicability(fact,query,scenario,registry)
            edge_results.append({'edge_index':index,
                'fact_ref':edge['source_revision']['ref']+'#'+fact.meaning_pointer,
                'condition_state':state,'reasons':list(reasons),
                'source':edge['source'],'target':edge['target'],
                'qualification_refs':deepcopy(use.get('qualification_refs') or [])})
            edge_atoms.append(EvidenceAtom(str(index),
                supporting_refs=(edge_results[-1]['fact_ref'],) if state=='applicable' else (),
                refuting_refs=(edge_results[-1]['fact_ref'],) if state=='outside' else (),
                unknown_reasons=tuple('%s:%s'%(edge_results[-1]['fact_ref'],reason)
                    for reason in reasons) if state=='unknown' else ()))
        composed=_evidence_composition(edge_atoms,'and')
        branch_results.append({'branch_id':branch.branch_id,'requirement':branch.requirement,
            'alternative_group':branch.alternative_group,'source_reported_path':edge_results,
            'condition_state':composed.state,'unknown_edge_ids':list(composed.unknown_atom_ids),
            'conflict_edge_ids':list(composed.conflict_atom_ids)})
        branch_atoms.append(EvidenceAtom(branch.branch_id,
            supporting_refs=('branch:'+branch.branch_id,) if composed.state=='supported' else (),
            refuting_refs=('branch:'+branch.branch_id,) if composed.state=='refuted' else (),
            unknown_reasons=('branch:'+branch.branch_id+':'+composed.state,)
                if composed.state in ('unknown','conflicted') else ()))

    required=[];alternatives={}
    for branch,atom in zip(request.branches,branch_atoms):
        if branch.requirement=='required':required.append(atom)
        else:alternatives.setdefault(branch.alternative_group,[]).append(atom)
    components=[*required]
    group_results=[]
    for group_id,atoms in alternatives.items():
        composed=_evidence_composition(atoms,'or')
        group_results.append({'alternative_group':group_id,'condition_state':composed.state,
            'branch_ids':[atom.atom_id for atom in atoms],
            'unknown_branch_ids':list(composed.unknown_atom_ids)})
        components.append(EvidenceAtom('alternative_group:'+group_id,
            supporting_refs=('alternative_group:'+group_id,) if composed.state=='supported' else (),
            refuting_refs=('alternative_group:'+group_id,) if composed.state=='refuted' else (),
            unknown_reasons=('alternative_group:'+group_id+':'+composed.state,)
                if composed.state in ('unknown','conflicted') else ()))
    overall=_evidence_composition(components,'and')
    return {'contract_version':'boi/knowledge-traversal-condition-result@1',
        'source_traversal_digest':semantic_digest(traversal_result),
        'time_basis':{'mode':request.time_mode,
            **({'as_of':request.as_of.isoformat()} if request.as_of is not None else {})},
        'branches':branch_results,'alternative_groups':group_results,
        'overall_condition_state':overall.state,
        'unknown_required_or_group_ids':list(overall.unknown_atom_ids),
        'semantic_truth_proven':False}


class KnowledgeRelationTraversal:
    def __init__(self, spaces, *, current_authorization=None, public_links=None):
        if not isinstance(spaces, KnowledgeSpaceStore):
            raise ValueError('KNOWLEDGE_TRAVERSAL_CURRENT_SPACE_READER_REQUIRED')
        self.spaces = spaces
        self.documents = PublishedKnowledgeReader(spaces,
            current_authorization=current_authorization, public_links=public_links)

    def read(self, *, actor_id, request):
        req = KnowledgeTraversalRequest.model_validate(request)
        uses = KnowledgeUseReader(self.spaces)
        loaded, resolved, projected = {}, {}, {}
        source_readers, evidence, declarations = {}, {}, {}
        started = monotonic()

        def budget():
            if monotonic() - started > 15:
                raise ValueError('KNOWLEDGE_TRAVERSAL_TIME_BUDGET_EXCEEDED')

        def read_revision(revision):
            budget()
            revision = RevisionRef.model_validate(revision.model_dump(mode='json'))
            if revision not in loaded:
                if len(loaded) >= 256:
                    raise ValueError('KNOWLEDGE_TRAVERSAL_REVISION_BUDGET_EXCEEDED')
                native = self.spaces.intake.ledger.read(revision.ref)
                if (native.kind != RecordKind.KNOWLEDGE_REVISION
                        or record_digest(native.record_id) != revision.revision_digest):
                    raise ValueError('KNOWLEDGE_TRAVERSAL_NATIVE_REVISION_REQUIRED')
                access, record, asset = self.spaces.read(actor_id=actor_id,
                    stable_id=native_identity(native), revision=revision, purpose='model_input')
                loaded[revision] = access, record, asset
            return loaded[revision][1:]

        # These are exact, currently authorized declarations, not discoveries by
        # word or predicate role. A textual value cannot be a traversable link.
        profiles = {}
        pending_profiles = deque(RevisionRef.model_validate(component.revision.model_dump(mode='json'))
            for component in req.predicates)
        while pending_profiles:
            revision = pending_profiles.popleft()
            if revision in profiles:
                continue
            if len(profiles) >= 128:
                raise ValueError('KNOWLEDGE_PROFILE_REGISTRY_BOUND')
            _, asset = read_revision(revision)
            if asset.kind != 'profile':
                raise ValueError('KNOWLEDGE_TRAVERSAL_PROFILE_REQUIRED')
            profile = KnowledgeProfileDeclaration.model_validate_json(asset.content_json)
            profiles[revision] = profile
            required = {dependency.revision for dependency in asset.dependencies if dependency.required}
            for declaration in profile.components:
                for link in (getattr(declaration, 'subject_type', None), getattr(declaration, 'target_type', None)):
                    if not isinstance(link, ProjectionComponent):
                        continue
                    dependency = RevisionRef.model_validate(link.revision.model_dump(mode='json'))
                    if dependency != revision and dependency not in required:
                        raise ValueError('KNOWLEDGE_TRAVERSAL_PROFILE_DEPENDENCY_REQUIRED')
                    pending_profiles.append(dependency)
        registry = KnowledgeProfileRegistry(profiles)
        for component in req.predicates:
            declaration, predicate = registry.predicate(component)
            if predicate.value_kind != 'object' or declaration.value_semantics == 'unknown':
                raise ValueError('KNOWLEDGE_TRAVERSAL_DECLARED_OBJECT_PREDICATE_REQUIRED')
            declarations[component] = predicate

        def projection(revision):
            revision = RevisionRef.model_validate(revision.model_dump(mode='json'))
            if revision not in projected:
                native, asset = read_revision(revision)
                if asset.kind != 'definition':
                    raise ValueError('KNOWLEDGE_TRAVERSAL_TYPED_DEFINITION_REQUIRED')
                manifest = ProjectionPublication(scope_id='read-only-relation-traversal',
                    principal_id=native.payload['employee_id'], base_generation=0,
                    policy_digest=native.payload['policy_digest'], confirmation_ref='read-only-no-publication',
                    source_manifest_digest=native.payload['source_manifest_digest'], adapter_revision=ADAPTER_REVISION,
                    changes=(PublicationChange(stable_id=native_identity(native), operation='upsert',
                        previous_revision=None, revision=revision.model_dump(mode='json')),))
                batch = KnowledgeProfileProjector(read_revision=read_revision).materialize(manifest)
                item = batch.objects[0]
                if item.readiness == 'unprepared':
                    raise ValueError('KNOWLEDGE_TRAVERSAL_TYPED_DEFINITION_REQUIRED')
                projected[revision] = item
            return projected[revision]

        def target(identity):
            if identity not in resolved:
                access, _ = self.spaces.authorize(actor_id=actor_id, stable_id=identity, purpose='model_input')
                resolved[identity] = access
            item = projection(resolved[identity].content_revision)
            if item.stable_id != identity:
                raise ValueError('KNOWLEDGE_TRAVERSAL_TARGET_IDENTITY_CHANGED')
            return item

        def source_bundle(item, facts):
            revision = RevisionRef.model_validate(item.knowledge_revision.model_dump(mode='json'))
            access, native, asset = loaded[revision]
            content = decode_knowledge_content(json.loads(asset.content_json))
            meaning = TypedKnowledgeMeaning.model_validate(content.meaning)
            by_id = {a.id: '/assertions/' + str(i) for i, a in enumerate(meaning.assertions)}
            roots = [f.meaning_pointer for f in facts]
            closure = list(roots)
            for pointer in closure:
                node = content.meaning['assertions'][int(pointer.split('/')[2])]
                for dependency in node['depends_on']:
                    if by_id[dependency] not in closure:
                        if len(closure) >= 256:
                            raise ValueError('KNOWLEDGE_TRAVERSAL_SOURCE_CLOSURE_BUDGET_EXCEEDED')
                        closure.append(by_id[dependency])
            indices = [i for i, binding in enumerate(content.evidence_bindings)
                if any(binding.meaning_pointer == p or binding.meaning_pointer.startswith(p + '/') for p in closure)]
            reader = PublishedSourceFields(self.documents, actor_id=actor_id, revision=revision,
                access=access, native=native, content=content, model_input=True)
            bundle = reader.bundle(indices, url=self.documents.public_links.url(document_url(revision)))
            source_readers[revision] = reader
            evidence[revision.ref] = {**bundle, 'meaning_selection': {
                'requested_roots': roots, 'delivered_closure': closure, 'closure_complete': True}}
            if sum(b['delivered_characters'] for b in evidence.values()) > 65536:
                raise ValueError('KNOWLEDGE_TRAVERSAL_SOURCE_BUDGET_EXCEEDED')

        start = projection(req.start_revision)
        nodes = {}
        edges, blocked, boundaries = [], [], []
        queue, queued = deque([(start, 0)]), {start.stable_id}

        def add_node(item):
            if item.stable_id in nodes:
                if nodes[item.stable_id]['revision'] != item.knowledge_revision.model_dump(mode='json'):
                    raise ValueError('KNOWLEDGE_TRAVERSAL_IDENTITY_REVISION_CHANGED')
                return
            if len(nodes) >= req.max_nodes:
                raise ValueError('KNOWLEDGE_TRAVERSAL_NODE_BUDGET_EXCEEDED')
            nodes[item.stable_id] = {'stable_id': item.stable_id,
                'revision': item.knowledge_revision.model_dump(mode='json'),
                'object_type': item.object_type.model_dump(mode='json'), 'title': item.title,
                'document_url': self.documents.public_links.url(document_url(item.knowledge_revision))}

        add_node(start)
        while queue:
            budget()
            item, depth = queue.popleft()
            selected = [f for f in item.facts if f.predicate_revision in declarations]
            if not selected:
                continue
            if depth == req.max_depth:
                boundaries.append({'stable_id': item.stable_id, 'reason': 'depth_limit', 'depth': depth})
                continue
            grants = {u.meaning_pointer: u for u in uses.fact_uses(actor_id=actor_id,
                revision=item.knowledge_revision, purpose='traverse', facts=selected, claim_basis=req.claim_basis)}
            accepted = []
            for fact in selected:
                grant = grants.get(fact.meaning_pointer)
                if (grant is None or grant.purpose != 'traverse' or grant.statement_scope_digest is None
                        or grant.fact_digest != semantic_digest(fact)
                        or grant.knowledge_revision != item.knowledge_revision
                        or fact.modality != 'asserted'
                        or fact.qualifiers.get('assertion_kind') != 'source_reported'):
                    blocked.append({'stable_id': item.stable_id, 'revision': item.knowledge_revision.model_dump(mode='json'),
                        'meaning_pointer': fact.meaning_pointer, 'reason': 'exact_traverse_source_qualification_required'})
                    continue
                if len(edges) >= req.max_edges:
                    raise ValueError('KNOWLEDGE_TRAVERSAL_EDGE_BUDGET_EXCEEDED')
                predicate = declarations[fact.predicate_revision]
                if fact.value.kind != 'object' or predicate.subject_type != item.object_type:
                    raise ValueError('KNOWLEDGE_TRAVERSAL_RELATION_TYPE_MISMATCH')
                destination = target(fact.value.value)
                if destination.object_type != predicate.target_type:
                    raise ValueError('KNOWLEDGE_TRAVERSAL_TARGET_TYPE_MISMATCH')
                add_node(destination)
                accepted.append(fact)
                positive = fact.polarity == 'positive'
                edges.append({'source': item.stable_id, 'target': destination.stable_id,
                    'source_revision': item.knowledge_revision.model_dump(mode='json'),
                    'target_revision': destination.knowledge_revision.model_dump(mode='json'),
                    'fact': fact.model_dump(mode='json'), 'use': grant.model_dump(mode='json'),
                    'continuation': positive, 'source_bundle_ref': item.knowledge_revision.ref,
                    'world_condition_satisfaction': 'not_evaluated', 'causal_inference': False})
                if positive and destination.stable_id not in queued:
                    queued.add(destination.stable_id)
                    queue.append((destination, depth + 1))
            if accepted:
                source_bundle(item, accepted)

        # A repeated destination can be a merge, not a cycle. Check reachability
        # in the returned positive graph before labeling each cycle edge.
        adjacency = {identity: set() for identity in nodes}
        for edge in edges:
            if edge['continuation']:
                adjacency[edge['source']].add(edge['target'])
        for edge in edges:
            pending, seen = [edge['target']], set()
            while pending:
                identity = pending.pop()
                if identity in seen:
                    continue
                seen.add(identity)
                pending.extend(adjacency[identity] - seen)
            edge['cycle'] = edge['continuation'] and edge['source'] in seen
        result = {'contract_version': 'boi/knowledge-relation-traversal-result@1',
            'request': req.model_dump(mode='json'), 'actor_id': actor_id,
            'status': 'partial' if blocked or boundaries else 'completed',
            'nodes': list(nodes.values()), 'edges': edges, 'blocked': blocked, 'boundaries': boundaries,
            'source_bundles': evidence, 'semantics': traversal_support_contract(),
            'declared_graph_complete_within_request': not blocked and not boundaries,
            'population_completeness_qualified': False, 'path_condition_satisfaction': 'not_evaluated',
            'scientific_truth_proven': False, 'publication_changed': False}
        if req.condition_evaluation is not None:
            condition_result = evaluate_relation_path_conditions(traversal_result=result,
                evaluation=req.condition_evaluation, registry=registry)
            result['condition_evaluation'] = condition_result
            result['path_condition_satisfaction'] = condition_result['overall_condition_state']
        if len(json.dumps(result, ensure_ascii=False).encode()) > 1024 * 1024:
            raise ValueError('KNOWLEDGE_TRAVERSAL_OUTPUT_BUDGET_EXCEEDED')
        for reader in source_readers.values():
            reader.fence()
        uses.revalidate()
        for identity, before in resolved.items():
            current, _ = self.spaces.authorize(actor_id=actor_id, stable_id=identity, purpose='model_input')
            if current != before:
                raise ValueError('KNOWLEDGE_TRAVERSAL_TARGET_AUTHORITY_CHANGED')
        for revision, (before, _, _) in loaded.items():
            current, _ = self.spaces.authorize(actor_id=actor_id, stable_id=before.identity.stable_id,
                revision=revision, purpose='model_input')
            if current != before:
                raise ValueError('KNOWLEDGE_TRAVERSAL_AUTHORITY_CHANGED')
        budget()
        return result
