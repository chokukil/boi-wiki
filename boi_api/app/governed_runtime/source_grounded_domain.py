"""Materialization may add typed structure, not rewrite a frozen source reading."""
from .metadata_reference_scope import bind_reference_schema, validate_reference_scope
from .semantic_metadata_pi_client import logical_transport_schema
from .semantic_binding_contract import semantic_digest


def source_draft_dependency_check(draft,value):
    """Diagnose typed dependency gaps; preserve candidates and never infer prose."""
    from .domain_profile_v02 import domain_entry_references,domain_reference_closure_reasons
    from .domain_profile_v03 import validate_domain_profile_entry as historical,versioning_closure_reasons
    from .domain_profile_v04 import validate_domain_profile_entry
    candidates=[c.logical_definition for c in draft.candidates if c.logical_definition is not None]
    selected={e.id:e for e in candidates};reasons=set();missing=set();used={}
    if len(selected)!=len(candidates):reasons.add('DOMAIN_ID_DUPLICATE')
    available={d['concept_id']:d for d in value['existing_definitions']}
    pending=list(selected.values())
    while pending:
        entry=pending.pop()
        for ref in domain_entry_references(entry):
            if ref in selected:continue
            target=available.get(ref)
            if target is None or not target.get('logical_definition'):
                missing.add(ref);continue
            raw={k:v for k,v in target['logical_definition'].items()
                 if k not in {'semantic_evidence_uses','semantic_reuse_declarations'}}
            parsed=validate_domain_profile_entry(raw) if 'semantic_contract' in raw else historical(raw)
            if parsed.id!=ref:
                reasons.add('DOMAIN_DEPENDENCY_ID_MISMATCH');missing.add(ref);continue
            selected[ref]=parsed;pending.append(parsed)
            used[ref]={'ref':ref,'revision_digest':target['revision_digest']}
    reasons.update(domain_reference_closure_reasons(tuple(selected.values())))
    reasons.update(versioning_closure_reasons(tuple(selected.values())))
    if missing:reasons.add('DOMAIN_REFERENCE_CLOSURE_INCOMPLETE')
    body={'contract_version':'boi/source-draft-dependency-check@1','status':'partial' if reasons else 'pass',
        'reason_codes':sorted(reasons),'missing_refs':sorted(missing),
        'existing_definition_revisions':[used[ref] for ref in sorted(used)],
        'draft_digest':semantic_digest(draft),'dependency_closure_digest':semantic_digest([
            selected[ref].model_dump(mode='json') for ref in sorted(selected)]),
        'semantic_validated':False,'canonical':False}
    return {**body,'receipt_digest':semantic_digest(body)}


def constraints(value):
    result=[]
    relationships=value['comparison']['relationships']
    for index,atom in enumerate(value['source_reading']['atoms']):
        if atom['role']=='unknown':raise ValueError('SOURCE_MEANING_ROLE_UNRESOLVED')
        fields={atom['meaning']['field_index']}
        if 'kind_basis' in atom:fields.add(atom['kind_basis']['field_index'])
        if atom.get('time_basis') is not None:fields.add(atom['time_basis']['field_index'])
        if atom.get('contract_kind')=='unknown':raise ValueError('SOURCE_MEANING_KIND_UNRESOLVED')
        for facet in ('conditions','exclusions','missing_information'):
            fields.update(item['field_index'] for item in atom[facet])
        if 'subject_facet_bindings' in value:
            bindings=value['subject_facet_bindings']
            if len(bindings)!=len(value['source_reading']['atoms']) or bindings[index]['node_ref']!=value['contract_bindings'][index]['id']:
                raise ValueError('SOURCE_SUBJECT_FACET_NODE_DRIFT')
            for facet in ('unit','time'):
                basis=bindings[index][facet]['basis']
                if basis is not None:fields.add(basis['field_index'])
        result.append({'definition':atom['meaning']['interpretation'],'role':atom['role'],
            **({'kind':atom['contract_kind']} if 'contract_kind' in atom else {}),
            'unit_semantics':'declared' if atom['unit_status']=='known' else atom['unit_status'],
            'conditions':[item['interpretation'] for item in atom['conditions']],
            'exceptions':[item['interpretation'] for item in atom['exclusions']],
            'field_indices':sorted(fields),
            'equivalent_targets':[p['target'] for p in relationships
                                  if p['atom_index']==index and p['relationship']=='equivalent']})
        if atom.get('contract_kind') in {'ValueType','PropertyDefinition','Metric'} and 'time_status' in atom:
            result[-1]['logical_time_semantics']=(atom['time_basis']['interpretation']
                if atom['time_status']=='declared' else atom['time_status'])
        if 'contract_bindings' in value:
            if len(value['contract_bindings'])!=len(value['source_reading']['atoms']):
                raise ValueError('CONTRACT_GRAPH_NODE_COUNT_DRIFT')
            result[-1]['logical_bindings']=value['contract_bindings'][index]
        if 'qualifier_contracts' in value:
            if len(value['qualifier_contracts'])!=len(value['source_reading']['atoms']):
                raise ValueError('SOURCE_QUALIFIER_NODE_COUNT_DRIFT')
            result[-1]['qualifier_contracts']=value['qualifier_contracts'][index]
    return result


def grounded_domain_schema(value):
    schema=bind_reference_schema(logical_transport_schema(),namespace=value['semantic_namespace'],
                                 definitions=value['existing_definitions'])
    slots=[]
    for fixed in constraints(value):
        # In draft 2020-12, items applies only after prefixItems. Each fixed
        # slot must explicitly retain the complete candidate contract.
        slots.append({'allOf':[schema['properties']['candidates']['items']], 'properties':{
            'semantics':{'properties':{key:{'const':fixed[key]} for key in
                ('definition','role','unit_semantics','conditions','exceptions',*(['kind'] if 'kind' in fixed else []))}},
            'field_indices':{'const':fixed['field_indices']},
            'proposed_concept':{'enum':[None,*fixed['equivalent_targets']]}}})
        if 'logical_time_semantics' in fixed:
            slots[-1]['properties']['logical_definition']={'properties':{
                'time_semantics':{'const':fixed['logical_time_semantics']}}}
        if 'logical_bindings' in fixed:
            logical=slots[-1]['properties'].setdefault('logical_definition',{'properties':{}})
            logical['properties'].update({field:{'const':target} for field,target in fixed['logical_bindings'].items()})
        if 'qualifier_contracts' in fixed:
            logical=slots[-1]['properties'].setdefault('logical_definition',{'properties':{}})
            logical['properties']['applicability']={'properties':{'conditions':{'const':fixed['qualifier_contracts']}}}
    schema['properties']['candidates'].update(prefixItems=slots,minItems=len(slots),maxItems=len(slots))
    return schema


def validate_grounded_domain(draft,value):
    fixed=constraints(value)
    if len(draft.candidates)!=len(fixed):raise ValueError('SOURCE_MEANING_ATOM_COUNT_DRIFT')
    validate_reference_scope(draft,namespace=value['semantic_namespace'],definitions=value['existing_definitions'])
    for candidate,expected in zip(draft.candidates,fixed):
        semantics=candidate.semantics.model_dump(mode='json')
        if any(semantics[key]!=expected[key] for key in ('definition','role','unit_semantics','conditions','exceptions',
                                                       *(['kind'] if 'kind' in expected else []))):
            raise ValueError('SOURCE_MEANING_OVERWRITE_FORBIDDEN')
        if list(candidate.field_indices)!=expected['field_indices']:
            raise ValueError('SOURCE_MEANING_FIELD_CLOSURE_DRIFT')
        if ('logical_time_semantics' in expected and candidate.logical_definition is not None and
            candidate.logical_definition.time_semantics!=expected['logical_time_semantics']):
            raise ValueError('SOURCE_MEANING_TIME_SEMANTICS_DRIFT')
        if 'logical_bindings' in expected and candidate.logical_definition is not None:
            logical=candidate.logical_definition.model_dump(mode='json')
            if any(logical.get(field)!=target for field,target in expected['logical_bindings'].items()):
                raise ValueError('CONTRACT_GRAPH_BINDING_DRIFT')
        if ('qualifier_contracts' in expected and candidate.logical_definition is not None and
            candidate.logical_definition.model_dump(mode='json')['applicability']['conditions']!=expected['qualifier_contracts']):
            raise ValueError('SOURCE_QUALIFIER_CONTRACT_DRIFT')
        if candidate.proposed_concept and candidate.proposed_concept.model_dump(mode='json') not in expected['equivalent_targets']:
            raise ValueError('SOURCE_MEANING_RELATIONSHIP_NOT_EQUIVALENT')
