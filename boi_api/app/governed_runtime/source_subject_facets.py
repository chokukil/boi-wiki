"""Proposed unit/time assertions with explicit source subjects.

Exact selections establish provenance, not the correctness of subject resolution.
The original reading and structural graph remain immutable.
"""
from copy import deepcopy
import re
from typing import Literal
from pydantic import Field,StrictInt,model_validator
from .semantic_binding_contract import FrozenContract,Ref,semantic_digest
from .source_meaning_comparison import SegmentQuotedReading,SegmentSourceReading,bind_source_reading
from .source_segment_catalog import source_segment_catalog,select_source_segment


class FacetSourceSupport(FrozenContract):
    segment_index: StrictInt = Field(ge=0)
    end_segment_index: StrictInt|None = Field(default=None,ge=0)
    subject_text: str = Field(min_length=1,max_length=256,
        description='Exact source wording identifying the subject of this statement, including a pronoun when appropriate.')
    interpretation: Ref


class UnitSubjectFacet(FrozenContract):
    state: Literal['known','unknown','dimensionless','not_applicable'] = Field(description=(
        'known: an applicable physical unit is identified; dimensionless: the source establishes a '
        'dimensionless quantity; not_applicable: no unit-bearing quantity meaning applies to this subject; '
        'unknown: the source does not establish its unit status. Absence of a physical unit alone '
        'does not establish a dimensionless quantity.'))
    support: FacetSourceSupport|None
    rationale: Ref

    @model_validator(mode='after')
    def source_required(self):
        if (self.state=='unknown')!=(self.support is None):
            raise ValueError('SOURCE_SUBJECT_FACET_SUPPORT_REQUIRED')
        return self


class TimeSubjectFacet(UnitSubjectFacet):
    state: Literal['declared','unknown','not_applicable']


class NodeSubjectFacets(FrozenContract):
    node_ref: Ref
    unit: UnitSubjectFacet
    time: TimeSubjectFacet


class SourceSubjectFacetReading(FrozenContract):
    contract_version: Literal['boi/source-subject-facets@1']='boi/source-subject-facets@1'
    nodes: tuple[NodeSubjectFacets,...] = Field(min_length=1,max_length=4)
    uncertainties: tuple[str,...] = Field(max_length=16)


def _bound_facet(facet,selection,field_digest):
    if facet.support is None:
        if selection is not None or field_digest is not None:raise ValueError('SOURCE_SUBJECT_FACET_UNKNOWN_SUPPORT')
        return {'state':facet.state,'rationale':facet.rationale,'basis':None,'subject_evidence':[],
            'source_selection':None,'field_digest':None}
    support=facet.support
    if (not selection or selection['segment_index']!=support.segment_index
        or selection['end_segment_index']!=(support.segment_index if support.end_segment_index is None else support.end_segment_index)
        or selection['end_byte']-selection['start_byte']!=len(selection['text'].encode())):
        raise ValueError('SOURCE_SUBJECT_FACET_SELECTION_DRIFT')
    starts=[match.start() for match in re.finditer('(?='+re.escape(support.subject_text)+')',selection['text'])]
    if not starts:raise ValueError('SOURCE_SUBJECT_FACET_SUBJECT_OUTSIDE_SUPPORT')
    basis=SegmentQuotedReading(segment_index=support.segment_index,end_segment_index=support.end_segment_index,
        field_index=selection['field_index'],quote=selection['text'],interpretation=support.interpretation)
    evidence=[]
    for occurrence_index,start in enumerate(starts):
        begin=selection['start_byte']+len(selection['text'][:start].encode())
        evidence.append({'field_index':selection['field_index'],'field_digest':field_digest,'start_byte':begin,
            'end_byte':begin+len(support.subject_text.encode()),'text':support.subject_text,'occurrence_index':occurrence_index})
    return {'state':facet.state,'rationale':facet.rationale,'basis':basis.model_dump(mode='json'),
        'subject_evidence':evidence,'source_selection':selection,'field_digest':field_digest}


def _reading_receipt(graph,bindings,uncertainties):
    base=graph['derived_reading_receipt'];reading=deepcopy(base['reading']);uses=[]
    for index,(atom,binding) in enumerate(zip(reading['atoms'],bindings)):
        atom.update(unit_status=binding['unit']['state'],time_status=binding['time']['state'],time_basis=binding['time']['basis'])
        uses.extend(use for use in base['quote_bindings'] if use['atom_index']==index and use['facet']!='time_basis')
        facet=binding['time']
        if facet['basis'] is not None:
            selection=facet['source_selection']
            uses.append({'atom_index':index,'facet':'time_basis','claim_index':0,
                **{key:selection[key] for key in ('field_index','start_byte','end_byte','segment_index','end_segment_index')},
                'field_digest':facet['field_digest'],'segment_digest':semantic_digest(selection),
                'interpretation_digest':semantic_digest(facet['basis']['interpretation'])})
    reading['uncertainties']=list(dict.fromkeys([*reading['uncertainties'],*uncertainties]))
    reading=SegmentSourceReading.model_validate(reading).model_dump(mode='json')
    body={**{key:value for key,value in base.items() if key!='receipt_digest'},'reading':reading,'quote_bindings':uses}
    return {**body,'receipt_digest':semantic_digest(body)}


def _body(reading,graph,bindings):
    return {'contract_version':'boi/bound-source-subject-facets@1','source_graph_receipt_digest':graph['receipt_digest'],
        'graph_reading_receipt_digest':graph['derived_reading_receipt']['receipt_digest'],
        'reading':reading.model_dump(mode='json'),'node_bindings':bindings,
        'derived_reading_receipt':_reading_receipt(graph,bindings,reading.uncertainties),
        'status':'partial' if reading.uncertainties else 'PROVISIONAL',
        'reason_codes':['SOURCE_SUBJECT_FACET_INTERPRETATION_UNRESOLVED'] if reading.uncertainties else [],
        'semantic_validated':False,'canonical':False}


def _ordered(reading,graph):
    if (graph.get('contract_version')!='boi/bound-source-contract-graph@3' or not graph.get('unit_time_deferred')
        or graph.get('status')!='PROVISIONAL'
        or semantic_digest({k:v for k,v in graph.items() if k!='receipt_digest'})!=graph.get('receipt_digest')):
        raise ValueError('SOURCE_SUBJECT_FACET_GRAPH_REQUIRED')
    refs=[node['local_id'] for node in graph['graph']['nodes']]
    nodes={node.node_ref:node for node in reading.nodes}
    if len(nodes)!=len(reading.nodes) or set(refs)!=set(nodes):raise ValueError('SOURCE_SUBJECT_FACET_NODE_COVERAGE')
    return [nodes[ref] for ref in refs]


def bind_subject_facets(reading,graph,payload):
    nodes=_ordered(reading,graph);base=graph['derived_reading_receipt']
    if bind_source_reading(SegmentSourceReading.model_validate(base['reading']),payload)!=base:
        raise ValueError('SOURCE_SUBJECT_FACET_SOURCE_DRIFT')
    catalog=source_segment_catalog(payload);bindings=[]
    for node in nodes:
        binding={'node_ref':node.node_ref}
        for name in ('unit','time'):
            facet=getattr(node,name);support=facet.support
            selected=select_source_segment(payload,catalog,support.segment_index,support.end_segment_index) if support else None
            binding[name]=_bound_facet(facet,selected,catalog['field_digests'][selected['field_index']] if selected else None)
        bindings.append(binding)
    body=_body(reading,graph,bindings)
    derived=body['derived_reading_receipt']
    if bind_source_reading(SegmentSourceReading.model_validate(derived['reading']),payload)!=derived:
        raise ValueError('SOURCE_SUBJECT_FACET_READING_DRIFT')
    return {**body,'receipt_digest':semantic_digest(body)}


def validate_subject_facet_receipt(receipt,graph):
    """Reconstruct an immutable stage result; its source/ACL closure is separately rechecked by the caller."""
    reading=SourceSubjectFacetReading.model_validate(receipt['reading']);nodes=_ordered(reading,graph)
    raw=receipt['node_bindings']
    if len(raw)!=len(nodes):raise ValueError('SOURCE_SUBJECT_FACET_NODE_COVERAGE')
    bindings=[]
    for node,stored in zip(nodes,raw):
        if stored['node_ref']!=node.node_ref:raise ValueError('SOURCE_SUBJECT_FACET_NODE_COVERAGE')
        binding={'node_ref':node.node_ref}
        for name in ('unit','time'):
            facet=stored[name]
            binding[name]=_bound_facet(getattr(node,name),facet['source_selection'],facet['field_digest'])
        bindings.append(binding)
    body=_body(reading,graph,bindings)
    if {**body,'receipt_digest':semantic_digest(body)}!=receipt:raise ValueError('SOURCE_SUBJECT_FACET_RECEIPT_DRIFT')
    return receipt['derived_reading_receipt']


def subject_facet_projection(receipt):
    return [{'node_ref':node['node_ref'],**{name:{'basis':node[name]['basis'],
        'subjects':list(dict.fromkeys(e['text'] for e in node[name]['subject_evidence']))}
        for name in ('unit','time')}} for node in receipt['node_bindings']]
