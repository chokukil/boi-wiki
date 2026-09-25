"""Proposed typed contracts may share source assertions; no semantic authority."""
from typing import Literal
from pydantic import Field,StrictInt
from .semantic_binding_contract import FrozenContract,Ref,RevisionRef,semantic_digest
from .source_meaning_comparison import SegmentSourceAtomReading,SegmentSourceReading,bind_source_reading


class GraphTarget(FrozenContract):
    kind: Literal['local','existing']
    ref: Ref
    revision_digest: str | None = None


class GraphBinding(FrozenContract):
    field: Literal['identity_property_ref','property_refs','logical_grain','owner_ref','value_type_ref',
        'left_endpoint_ref','right_endpoint_ref','left_property_refs','right_property_refs',
        'relationship_identity_ref','unit_ref','grain']
    targets: tuple[GraphTarget,...] = Field(min_length=1,max_length=16)


class SourceContractNode(FrozenContract):
    local_id: Ref
    source_atom_indices: tuple[StrictInt,...] = Field(max_length=4,
        description='Prior assertions used directly or through an immediate declared local target. One assertion may support several contracts.')
    reading: SegmentSourceAtomReading
    bindings: tuple[GraphBinding,...] = Field(max_length=12)


class SourceContractGraph(FrozenContract):
    contract_version: Literal['boi/source-contract-graph@1']='boi/source-contract-graph@1'
    nodes: tuple[SourceContractNode,...] = Field(min_length=1,max_length=4)
    uncertainties: tuple[str,...] = Field(max_length=16)
    remaining_contracts: bool


class SourceContractGraphV2(SourceContractGraph):
    contract_version: Literal['boi/source-contract-graph@2']='boi/source-contract-graph@2'


class SourceContractGraphV3(SourceContractGraphV2):
    contract_version: Literal['boi/source-contract-graph@3']='boi/source-contract-graph@3'


# (expected target kind, plural, required). These describe logical contracts,
# never physical table/column identities or the truth of an interpretation.
GRAPH_FIELDS={
    'Term':{},
    'ValueType':{'unit_ref':(None,False,False)},
    'ObjectType':{'identity_property_ref':('PropertyDefinition',False,True),
        'property_refs':('PropertyDefinition',True,True),'logical_grain':('PropertyDefinition',True,True)},
    'PropertyDefinition':{'owner_ref':('ObjectType',False,True),'value_type_ref':('ValueType',False,True),
        'unit_ref':(None,False,False)},
    'RelationType':{'left_endpoint_ref':('ObjectType',False,True),'right_endpoint_ref':('ObjectType',False,True),
        'left_property_refs':('PropertyDefinition',True,True),'right_property_refs':('PropertyDefinition',True,True),
        'relationship_identity_ref':('PropertyDefinition',False,False)},
    'Metric':{'grain':('PropertyDefinition',True,True)},'Rule':{},'unknown':{},
}


def _facets(atom):
    return [atom['meaning'],atom['kind_basis'],*atom['conditions'],*atom['exclusions'],
            *atom['missing_information'],*([atom['time_basis']] if atom.get('time_basis') else [])]


def _segments(facets):
    result=set()
    for facet in facets:
        start=facet['segment_index'];end=facet.get('end_segment_index')
        result.update(range(start,(start if end is None else end)+1))
    return result


def _qualifier_digest(claim):
    value=dict(claim)
    if value.get('end_segment_index') is None:value['end_segment_index']=value['segment_index']
    return semantic_digest(value)


def _source_links(node,index,parent_segments,node_segments,by_id,*,include_incoming=False):
    """Record direct citations and immediate typed context; neither proves meaning."""
    links=[]
    direct=sorted(node_segments&parent_segments)
    if direct:links.append({'source_atom_index':index,'via':'direct','segment_indices':direct})
    contracts=GRAPH_FIELDS[node.reading.contract_kind]
    for binding in node.bindings:
        if binding.field not in contracts:continue
        expected,plural,_=contracts[binding.field]
        if not plural and len(binding.targets)!=1:continue
        for target in binding.targets:
            other=by_id.get(target.ref) if target.kind=='local' and target.revision_digest is None else None
            if other is None or (expected is not None and other.reading.contract_kind!=expected):continue
            overlap=sorted(_segments(_facets(other.reading.model_dump(mode='json')))&parent_segments)
            if overlap:links.append({'source_atom_index':index,'via':'local_binding','field':binding.field,
                'target_ref':target.ref,'segment_indices':overlap})
    if include_incoming:
        for other in by_id.values():
            contracts=GRAPH_FIELDS[other.reading.contract_kind]
            for binding in other.bindings:
                if binding.field not in contracts:continue
                expected,plural,_=contracts[binding.field]
                if (not plural and len(binding.targets)!=1) or (expected is not None and expected!=node.reading.contract_kind):continue
                if not any(t.kind=='local' and t.ref==node.local_id and t.revision_digest is None for t in binding.targets):continue
                overlap=sorted(_segments(_facets(other.reading.model_dump(mode='json')))&parent_segments)
                if overlap:links.append({'source_atom_index':index,'via':'local_binding','direction':'incoming',
                    'field':binding.field,'from_node_ref':other.local_id,'target_ref':node.local_id,'segment_indices':overlap})
    return links


def contract_graph_receipt(graph,source_receipt,payload):
    # Rehydrate and verify both interpretations against the same original input.
    original=SegmentSourceReading.model_validate(source_receipt['reading'])
    if bind_source_reading(original,payload)!=source_receipt:
        raise ValueError('CONTRACT_GRAPH_SOURCE_RECEIPT_DRIFT')
    derived=SegmentSourceReading(atoms=tuple(node.reading for node in graph.nodes),
        uncertainties=tuple(dict.fromkeys([*original.uncertainties,*graph.uncertainties])),
        remaining_claims=original.remaining_claims or graph.remaining_contracts)
    derived_receipt=bind_source_reading(derived,payload)
    reasons=set();missing=[];covered=set();retained=set();by_id={n.local_id:n for n in graph.nodes}
    if len(by_id)!=len(graph.nodes):reasons.add('CONTRACT_GRAPH_ID_DUPLICATE')
    existing={(item['concept_id'],item['revision_digest']):item for item in payload['existing_definitions']}
    original_values=original.model_dump(mode='json')['atoms']
    used_segments=set();source_links=[]
    for node in graph.nodes:
        if isinstance(graph,SourceContractGraphV3) and (node.reading.unit_status!='unknown'
            or node.reading.time_status!='unknown' or node.reading.time_basis is not None):
            reasons.add('CONTRACT_GRAPH_SUBJECT_FACETS_NOT_DEFERRED')
        parents=node.source_atom_indices
        node_value=node.reading.model_dump(mode='json');node_segments=_segments(_facets(node_value));used_segments.update(node_segments)
        if len(parents)!=len(set(parents)):reasons.add('CONTRACT_GRAPH_SOURCE_INDEX_DUPLICATE')
        for index in parents:
            if not 0<=index<len(original_values):
                reasons.add('CONTRACT_GRAPH_SOURCE_INDEX_OUTSIDE_READING');continue
            covered.add(index)
            links=_source_links(node,index,_segments(_facets(original_values[index])),node_segments,by_id,
                include_incoming=isinstance(graph,SourceContractGraphV2))
            source_links.extend({'node_ref':node.local_id,**link} for link in links)
            if not links:
                reasons.add('CONTRACT_GRAPH_SOURCE_SELECTION_DISJOINT')
            for facet in ('conditions','exclusions','missing_information'):
                # Exact retention of declared qualifiers, including source location.
                actual={_qualifier_digest(claim) for claim in node_value[facet]}
                retained.update((index,facet,_qualifier_digest(claim)) for claim in original_values[index][facet]
                                if _qualifier_digest(claim) in actual)
        contracts=GRAPH_FIELDS[node.reading.contract_kind];fields={b.field for b in node.bindings}
        if len(fields)!=len(node.bindings):reasons.add('CONTRACT_GRAPH_FIELD_DUPLICATE')
        if not {field for field,(_,_,required) in contracts.items() if required}<=fields:
            reasons.add('CONTRACT_GRAPH_REQUIRED_BINDING_MISSING')
        for binding in node.bindings:
            if binding.field not in contracts:
                reasons.add('CONTRACT_GRAPH_FIELD_KIND_MISMATCH');continue
            expected,plural,_=contracts[binding.field]
            if not plural and len(binding.targets)!=1:reasons.add('CONTRACT_GRAPH_BINDING_ARITY_INVALID')
            if len({semantic_digest(t) for t in binding.targets})!=len(binding.targets):
                reasons.add('CONTRACT_GRAPH_TARGET_DUPLICATE')
            for target in binding.targets:
                if target.kind=='local':
                    other=by_id.get(target.ref)
                    if target.revision_digest is not None:reasons.add('CONTRACT_GRAPH_LOCAL_REVISION_FORBIDDEN')
                    kind=other.reading.contract_kind if other else None
                else:
                    other=existing.get((target.ref,target.revision_digest))
                    if other is not None:
                        RevisionRef(ref=target.ref,revision_digest=target.revision_digest)
                    kind=(other.get('logical_definition') or {}).get('kind') if other else None
                if other is None:
                    reasons.add('CONTRACT_GRAPH_REFERENCE_MISSING');missing.append(target.model_dump(mode='json'))
                elif expected is not None and kind!=expected:reasons.add('CONTRACT_GRAPH_TARGET_KIND_MISMATCH')
    required={(i,facet,_qualifier_digest(claim)) for i,atom in enumerate(original_values)
        for facet in ('conditions','exclusions','missing_information') for claim in atom[facet]}
    if covered!=set(range(len(original_values))):reasons.add('CONTRACT_GRAPH_SOURCE_COVERAGE_INCOMPLETE')
    if not required<=retained:reasons.add('CONTRACT_GRAPH_QUALIFIER_DROPPED')
    if graph.remaining_contracts:reasons.add('CONTRACT_GRAPH_INCOMPLETE')
    body={'contract_version':('boi/bound-source-contract-graph@3' if isinstance(graph,SourceContractGraphV3) else
            'boi/bound-source-contract-graph@2' if isinstance(graph,SourceContractGraphV2) else 'boi/bound-source-contract-graph@1'),
        **({'unit_time_deferred':True} if isinstance(graph,SourceContractGraphV3) else {}),
        'source_reading_receipt_digest':source_receipt['receipt_digest'],'graph':graph.model_dump(mode='json'),
        'derived_reading_receipt':derived_receipt,'source_atom_indices':sorted(covered),
        'source_segment_indices':sorted(used_segments),'source_assertion_links':source_links,'missing_targets':missing,
        'reason_codes':sorted(reasons),'status':'partial' if reasons else 'PROVISIONAL',
        'semantic_validated':False,'canonical':False}
    return {**body,'receipt_digest':semantic_digest(body)}


def graph_binding_projection(graph):
    result=[]
    for node in graph.nodes:
        values={'id':node.local_id}
        for binding in node.bindings:
            plural=GRAPH_FIELDS[node.reading.contract_kind][binding.field][1]
            refs=[target.ref for target in binding.targets]
            values[binding.field]=refs if plural else refs[0]
        result.append(values)
    return result
