"""Evidence-bound qualifier proposals and reviewed query applicability.

Literal binding and typed checks do not prove the interpretation of source prose.
New qualifier interpretations belong to the same reviewed candidate closure.
"""
import json
import math
import re
from decimal import Decimal
from typing import Literal
from pydantic import Field,StrictInt,model_validator
from .semantic_binding_contract import FrozenContract,Ref,Digest,semantic_digest


ValueType=Literal['string','integer','number','boolean']
Operator=Literal['eq','neq','gt','gte','lt','lte','in','is_null','not_null']
Disposition=Literal['annotation','row_condition','requires_context']


class SelectedQualifierLiteral(FrozenContract):
    text: str = Field(min_length=1,max_length=512)


class QualifierPredicateProposal(FrozenContract):
    property_ref: Ref
    operator: Operator
    value_type: ValueType
    unit_ref: Ref|None
    unit_revision_digest: Digest|None
    literals: tuple[SelectedQualifierLiteral,...] = Field(max_length=16)


class QualifierProposal(FrozenContract):
    qualifier_id: Ref
    disposition: Disposition
    rationale: str = Field(min_length=1,max_length=1000)
    predicates: tuple[QualifierPredicateProposal,...] = Field(max_length=8)

    @model_validator(mode='after')
    def predicate_presence(self):
        if (self.disposition=='row_condition')!=bool(self.predicates):
            raise ValueError('QUALIFIER_PREDICATE_DISPOSITION_MISMATCH')
        return self


class SourceQualifierReading(FrozenContract):
    contract_version: Literal['boi/source-qualifier-reading@1']='boi/source-qualifier-reading@1'
    qualifiers: tuple[QualifierProposal,...] = Field(max_length=32)
    uncertainties: tuple[str,...] = Field(max_length=16)


class QualifierAnchor(FrozenContract):
    facet: Literal['conditions','exceptions']
    index: StrictInt = Field(ge=0)
    text_digest: Digest


class QualifierLiteralEvidence(FrozenContract):
    operand_index: StrictInt = Field(ge=0)
    field_index: StrictInt = Field(ge=0)
    field_digest: Digest
    start_byte: StrictInt = Field(ge=0)
    end_byte: StrictInt = Field(gt=0)
    text: str = Field(min_length=1)
    occurrence_index: StrictInt = Field(ge=0)


class BoundQualifierPredicate(FrozenContract):
    property_ref: Ref
    operator: Operator
    value_type: ValueType
    unit_ref: Ref|None
    unit_revision_digest: Digest|None
    values: tuple[object,...] = Field(max_length=16)
    literal_evidence: tuple[QualifierLiteralEvidence,...] = Field(max_length=1024)

    @model_validator(mode='after')
    def exact_values(self):
        count=len(self.values)
        if {e.operand_index for e in self.literal_evidence}!=set(range(count)) or (
            count!=0 if self.operator in {'is_null','not_null'} else
            count<1 if self.operator=='in' else count!=1):
            raise ValueError('QUALIFIER_OPERAND_ARITY_INVALID')
        if self.operator in {'gt','gte','lt','lte'} and self.value_type not in {'integer','number'}:
            raise ValueError('QUALIFIER_ORDER_TYPE_UNSUPPORTED')
        for evidence in self.literal_evidence:
            value=self.values[evidence.operand_index]
            parsed=_literal_value(evidence.text,self.value_type)
            if type(value) is not type(parsed) or value!=parsed:
                raise ValueError('QUALIFIER_LITERAL_VALUE_DRIFT')
            if evidence.end_byte-evidence.start_byte!=len(evidence.text.encode()):
                raise ValueError('QUALIFIER_LITERAL_POSITION_INVALID')
        if bool(self.unit_ref)!=bool(self.unit_revision_digest):
            raise ValueError('QUALIFIER_UNIT_REVISION_REQUIRED')
        return self


class SemanticQualifier(FrozenContract):
    contract_version: Literal['boi/semantic-qualifier@1']='boi/semantic-qualifier@1'
    anchor: QualifierAnchor
    disposition: Disposition
    rationale: str = Field(min_length=1,max_length=1000)
    predicates: tuple[BoundQualifierPredicate,...] = Field(max_length=8)

    @model_validator(mode='after')
    def predicate_presence(self):
        if (self.disposition=='row_condition')!=bool(self.predicates):
            raise ValueError('QUALIFIER_PREDICATE_DISPOSITION_MISMATCH')
        return self


def _literal_value(text,value_type):
    if value_type=='string':return text
    try:value=json.loads(text)
    except (ValueError,TypeError):raise ValueError('QUALIFIER_LITERAL_TYPE_INVALID') from None
    valid=(type(value) is bool if value_type=='boolean' else type(value) is int if value_type=='integer'
           else type(value) in (int,float) and (type(value) is int or math.isfinite(value)) and Decimal(str(value))==Decimal(text))
    if not valid:raise ValueError('QUALIFIER_LITERAL_TYPE_INVALID')
    return value


def qualifier_catalog(reading_receipt):
    result=[]
    for node_index,atom in enumerate(reading_receipt['reading']['atoms']):
        for facet,source_facet in [('conditions','conditions'),('exceptions','exclusions')]:
            for index,claim in enumerate(atom[source_facet]):
                binding=next(b for b in reading_receipt['quote_bindings']
                    if b['atom_index']==node_index and b['facet']==source_facet and b['claim_index']==index)
                result.append({'qualifier_id':f'q_{node_index}_{facet}_{index}','node_index':node_index,
                    'anchor':{'facet':facet,'index':index,'text_digest':semantic_digest(claim['interpretation'])},
                    'interpretation':claim['interpretation'],'quote':claim['quote'],
                    'field_index':binding['field_index'],'field_digest':binding['field_digest'],
                    'start_byte':binding['start_byte']})
    return result


def bind_qualifier_reading(reading,reading_receipt):
    catalog=qualifier_catalog(reading_receipt);by_id={q.qualifier_id:q for q in reading.qualifiers}
    if len(by_id)!=len(reading.qualifiers) or set(by_id)!={q['qualifier_id'] for q in catalog}:
        raise ValueError('QUALIFIER_SOURCE_COVERAGE_REQUIRED')
    contracts=[[] for _ in reading_receipt['reading']['atoms']]
    for item in catalog:
        proposed=by_id[item['qualifier_id']];predicates=[]
        for predicate in proposed.predicates:
            evidence=[];values=[]
            for operand_index,selected in enumerate(predicate.literals):
                occurrences=[m.start() for m in re.finditer('(?='+re.escape(selected.text)+')',item['quote'])]
                if not occurrences:raise ValueError('QUALIFIER_LITERAL_NOT_IN_SOURCE')
                parsed_value=_literal_value(selected.text,predicate.value_type)
                numeric_spans={(m.start(),m.end()) for m in re.finditer(
                    r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?',item['quote'])}
                bound=[]
                for occurrence_index,start in enumerate(occurrences):
                    end=start+len(selected.text)
                    if predicate.value_type in {'integer','number'} and (start,end) not in numeric_spans:
                        continue
                    begin=item['start_byte']+len(item['quote'][:start].encode())
                    bound.append(QualifierLiteralEvidence(operand_index=operand_index,
                        field_index=item['field_index'],field_digest=item['field_digest'],
                        start_byte=begin,end_byte=begin+len(selected.text.encode()),text=selected.text,
                        occurrence_index=occurrence_index))
                if not bound:raise ValueError('QUALIFIER_LITERAL_PARTIAL_NUMBER')
                evidence.extend(bound)
                values.append(parsed_value)
            predicates.append(BoundQualifierPredicate(**predicate.model_dump(exclude={'literals'}),
                values=tuple(values),literal_evidence=tuple(evidence)))
        contracts[item['node_index']].append(SemanticQualifier(anchor=item['anchor'],disposition=proposed.disposition,
            rationale=proposed.rationale,predicates=tuple(predicates)).model_dump(mode='json'))
    reasons=['SOURCE_QUALIFIER_CONTEXT_REQUIRED'] if any(q.disposition=='requires_context' for q in reading.qualifiers) else []
    if reading.uncertainties:reasons.append('SOURCE_QUALIFIER_INTERPRETATION_UNRESOLVED')
    body={'contract_version':'boi/bound-source-qualifiers@1','source_reading_receipt_digest':reading_receipt['receipt_digest'],
        'reading':reading.model_dump(mode='json'),'qualifier_contracts':contracts,'reason_codes':reasons,
        'status':'partial' if reasons else 'PROVISIONAL','semantic_validated':False,'canonical':False}
    return {**body,'receipt_digest':semantic_digest(body)}


def entry_qualifiers(entry):
    semantics=entry.get('semantic_contract') or {}
    expected={(facet,index):semantic_digest(text) for facet in ('conditions','exceptions')
        for index,text in enumerate(semantics.get(facet,[]))}
    raw=(entry.get('applicability') or {}).get('conditions',[])
    try:clauses=tuple(SemanticQualifier.model_validate(value) for value in raw)
    except ValueError:raise ValueError('REVIEWED_QUERY_QUALIFIER_UNRESOLVED') from None
    actual={(q.anchor.facet,q.anchor.index):q.anchor.text_digest for q in clauses}
    if len(actual)!=len(clauses) or actual!=expected:raise ValueError('REVIEWED_QUERY_QUALIFIER_UNRESOLVED')
    if any(q.disposition=='requires_context' for q in clauses):raise ValueError('REVIEWED_QUERY_QUALIFIER_CONTEXT_REQUIRED')
    return clauses


def validate_candidate_qualifier_provenance(domain,source_stage,*,subject_facets_required=False):
    """A newly proposed clause must come from the bound qualifier stage.

    Review alone cannot manufacture literal provenance for an older draft path.
    Active existing definitions are checked through their separate profile closure.
    """
    meanings=source_stage.get('source_meaning_results',[]);subject_context=[]
    for candidate in domain:
        logical=candidate.get('logical_definition') or {}
        clauses=(logical.get('applicability') or {}).get('conditions')
        matches=[m for m in meanings if m.get('domain_outcome_digest')==candidate['output_receipt_digest']
            and m.get('source_record')==candidate['source_record']]
        needs_facets=subject_facets_required or any(m.get('contract_graph_receipt',{}).get('unit_time_deferred') for m in matches)
        if not clauses and not needs_facets:continue
        if len(matches)!=1:raise ValueError('REVIEWED_QUERY_QUALIFIER_PROVENANCE_REQUIRED')
        meaning=matches[0];receipt=meaning.get('source_qualifier_receipt');source=meaning.get('contract_reading_receipt')
        graph=meaning.get('contract_graph_receipt') or {}
        if not source:raise ValueError('REVIEWED_QUERY_QUALIFIER_PROVENANCE_REQUIRED')
        indices=[i for i,node in enumerate(graph.get('graph',{}).get('nodes',[])) if node['local_id']==logical['id']]
        if len(indices)!=1:raise ValueError('REVIEWED_QUERY_QUALIFIER_PROVENANCE_STALE')
        if needs_facets:
            from .source_subject_facets import validate_subject_facet_receipt
            facets=meaning.get('source_facet_receipt')
            if not facets:raise ValueError('REVIEWED_QUERY_QUALIFIER_SUBJECT_PROVENANCE_REQUIRED')
            try:derived=validate_subject_facet_receipt(facets,graph)
            except (ValueError,KeyError,TypeError):raise ValueError('REVIEWED_QUERY_QUALIFIER_SUBJECT_PROVENANCE_STALE') from None
            if derived!=source:raise ValueError('REVIEWED_QUERY_QUALIFIER_SUBJECT_PROVENANCE_STALE')
            atom=source['reading']['atoms'][indices[0]]
            unit='declared' if atom['unit_status']=='known' else atom['unit_status']
            time=atom['time_basis']['interpretation'] if atom['time_status']=='declared' else atom['time_status']
            if (logical['semantic_contract']['unit_semantics']!=unit
                or ('time_semantics' in logical and logical['time_semantics']!=time)):
                raise ValueError('REVIEWED_QUERY_QUALIFIER_SUBJECT_PROVENANCE_STALE')
            subject_context.append({'node_ref':logical['id'],'source_record':candidate['source_record'],
                'source_facet_receipt_digest':facets['receipt_digest'],'source_reading_receipt_digest':source['receipt_digest'],
                'subject_facets':facets['node_bindings'][indices[0]]})
        elif graph.get('derived_reading_receipt')!=source:
            raise ValueError('REVIEWED_QUERY_QUALIFIER_PROVENANCE_REQUIRED')
        if not clauses:continue
        if not receipt:raise ValueError('REVIEWED_QUERY_QUALIFIER_PROVENANCE_REQUIRED')
        rebuilt=bind_qualifier_reading(SourceQualifierReading.model_validate(receipt['reading']),source)
        if (rebuilt!=receipt or
            receipt['qualifier_contracts'][indices[0]]!=logical['applicability']['conditions']):
            raise ValueError('REVIEWED_QUERY_QUALIFIER_PROVENANCE_STALE')
    return subject_context


def compile_reviewed_qualifiers(*,domain,index,inputs,root_object_ref,property_refs):
    """Only reviewed logical predicates become existing Gateway filters/parameters."""
    from .multi_result_query_gateway import MultiResultFilter,MultiResultParameterSpec
    available={i['payload']['id']:i['payload'] for i in index.get('items',[]) if isinstance(i.get('payload'),dict) and 'id' in i['payload']}
    available.update({c['logical_definition']['id']:c['logical_definition'] for c in domain if c.get('logical_definition')})
    properties={p.logical_property_ref:p for p in inputs.properties}
    pending=[root_object_ref,*property_refs];visited=set();filters=[];specs=[];parameters={};mappings={};qualified=[]
    while pending:
        ref=pending.pop(0)
        if ref in visited:continue
        visited.add(ref);entry=available.get(ref)
        if entry is None:raise ValueError('REVIEWED_QUERY_QUALIFIER_DEFINITION_MISSING')
        if entry['kind']=='PropertyDefinition':pending.append(entry['value_type_ref'])
        for qualifier in entry_qualifiers(entry):
            qualified.append({'entry_ref':ref,'entry_digest':semantic_digest(entry),'qualifier':qualifier.model_dump(mode='json')})
            for predicate in qualifier.predicates:
                prop=available.get(predicate.property_ref);mapping=properties.get(predicate.property_ref)
                if (not prop or prop.get('kind')!='PropertyDefinition' or not mapping
                    or prop['owner_ref']!=root_object_ref or mapping.owner_ref!=root_object_ref):
                    raise ValueError('REVIEWED_QUERY_QUALIFIER_PROPERTY_NOT_BOUND')
                value_type=available.get(prop['value_type_ref']) or {}
                if value_type.get('primitive_type')!=predicate.value_type:
                    raise ValueError('REVIEWED_QUERY_QUALIFIER_VALUE_TYPE_MISMATCH')
                semantic=prop['semantic_contract']
                if (predicate.unit_ref!=semantic['unit_ref'] or predicate.unit_revision_digest!=semantic['unit_revision_digest']
                    or semantic['unit_semantics']=='unknown'):
                    raise ValueError('REVIEWED_QUERY_QUALIFIER_UNIT_MISMATCH')
                if predicate.value_type in {'string','boolean'} and predicate.unit_ref:
                    raise ValueError('REVIEWED_QUERY_QUALIFIER_UNIT_MISMATCH')
                pending.append(predicate.property_ref);mappings[mapping.physical.mapping_ref]=mapping.physical
                name=None
                if predicate.operator not in {'is_null','not_null'}:
                    name=f'qualifier_{len(specs)}';plural=predicate.operator=='in'
                    specs.append(MultiResultParameterSpec(name=name,type=predicate.value_type+('_list' if plural else '')))
                    parameters[name]=list(predicate.values) if plural else predicate.values[0]
                filters.append(MultiResultFilter(mapping_ref=mapping.physical.mapping_ref,
                    operator=predicate.operator,parameter_name=name))
    body={'contract_version':'boi/reviewed-query-qualifiers@1',
        'definition_revisions':[{'ref':ref,'revision_digest':semantic_digest(available[ref])} for ref in sorted(visited)],
        'qualified_clauses':qualified,'filters':[f.model_dump(mode='json') for f in filters],
        'parameter_specs':[s.model_dump(mode='json') for s in specs],'parameters':parameters,
        'semantic_validated':False,'canonical':False}
    return tuple(filters),tuple(specs),parameters,tuple(mappings.values()),{**body,'receipt_digest':semantic_digest(body)}
