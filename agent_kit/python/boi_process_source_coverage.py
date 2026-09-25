"""Source-first coverage review for stored process meaning.

Source units are model observations, not an answer key or scientific truth.
The second observation must point to actual semantic components: a quotation
alone never proves that its meaning was represented in a candidate.
"""
import copy,json
from typing import Literal
from pydantic import Field
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref,semantic_digest
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessQuotation,ProcessKnowledgeDraft

INVENTORY_CONTRACT='boi/process-source-meaning-inventory@1'
ALIGNMENT_CONTRACT='boi/process-source-meaning-alignment@1'
REPAIRED_ALIGNMENT_CONTRACT='boi/process-source-meaning-alignment@2'

class SourceMeaningUnit(FrozenContract):
    unit_id:Ref
    kind:Literal['domain_meaning','source_context']
    meaning:Ref
    evidence:tuple[ProcessQuotation,...]=Field(min_length=1)

class SourceFieldUnits(FrozenContract):
    field_locator:Ref
    unit_ids:tuple[Ref,...]
    note:Ref

class SourceMeaningInventory(FrozenContract):
    units:tuple[SourceMeaningUnit,...]=Field(min_length=1,max_length=120)
    fields:tuple[SourceFieldUnits,...]
    limitations:tuple[Ref,...]=Field(min_length=1)


class SourceFieldUnitsV2(SourceFieldUnits):
    # The structural source parser uses an empty JSON pointer for a plain-text
    # document root. It is a real locator, not a missing source reference.
    field_locator:str


class SourceMeaningInventoryV2(SourceMeaningInventory):
    fields:tuple[SourceFieldUnitsV2,...]

class MeaningAlignment(FrozenContract):
    unit_id:Ref
    status:Literal['represented','partial','omitted','conflicting','source_context_retained','unit_unsupported']
    component_pointers:tuple[Ref,...]
    reason:Ref
    missing_meaning:str|None=None

class SourceMeaningAlignment(FrozenContract):
    alignments:tuple[MeaningAlignment,...]
    limitations:tuple[Ref,...]=Field(min_length=1)


from .boi_process_claim_review import SourceNodeJudgment

class RepairedSourceMeaningAlignment(SourceMeaningAlignment):
    changed_node_judgments:tuple[SourceNodeJudgment,...]


def repaired_alignment_material(inventory,draft,evidence,category_contract,changed_node_pointers):
    from .boi_process_fidelity import assessment_targets
    result=alignment_material(inventory,draft,evidence,category_contract)
    targets={t['target_pointer']:t for t in assessment_targets(draft,include_all_terms=True)}
    if not set(changed_node_pointers)<=set(targets):raise ValueError('REPAIRED_ALIGNMENT_UNKNOWN_CHANGED_NODE')
    result.update(contract_version=REPAIRED_ALIGNMENT_CONTRACT,
        changed_node_targets=[targets[p] for p in sorted(set(changed_node_pointers))])
    return result


def repaired_alignment_prompt(material):
    instruction=alignment_prompt(material).split('\n',1)[0]
    return (instruction+' Also independently assess every changed_node_target exactly once in changed_node_judgments. '
        'Read its complete typed subject, category, object, statement, condition, negation and scope against the original. '
        'A coverage match cannot excuse an unsupported added property. Supported uses failure_kind none; contradicted '
        'uses source_conflict or representation_mismatch; unsupported uses unsupported_addition, scope_expansion, '
        'representation_mismatch or insufficient_evidence. Quote exact original fields. The old source units are '
        'provisional: a normal paraphrase or multiple linked nodes can already express them. Never force a prior '
        'diagnosis to be correct. No desired repair or evaluation labels are supplied.\n'+
        json.dumps(material,ensure_ascii=False,separators=(',',':')))


def check_repaired_alignment(raw,inventory,draft,evidence,changed_node_pointers):
    # Keep source-coverage and changed-node fidelity opinions separate. All
    # observation bytes remain available, including invalid reviewer output.
    aligned={k:raw[k] for k in ('alignments','limitations')}
    coverage=observe_alignment(aligned,inventory,draft)
    roles=check_source_reference_roles(aligned,inventory,draft,evidence)
    fields={f['field_locator']:f['text'] for f in evidence['fields']}
    expected=set(changed_node_pointers);judgments=[];errors=[];seen=set()
    rows=raw.get('changed_node_judgments',[])
    from collections import Counter
    counts=Counter(r.get('target_pointer') for r in rows if isinstance(r,dict))
    for row in rows:
        pointer=row.get('target_pointer') if isinstance(row,dict) else None
        try:
            if pointer not in expected or counts[pointer]!=1:raise ValueError('CHANGED_NODE_SCOPE_OR_DUPLICATE')
            value=SourceNodeJudgment.model_validate(row).model_dump(mode='json')
            for q in value['evidence']:
                text=fields.get(q['field_locator'],'');start=-1
                for _ in range(q['occurrence']+1):
                    start=text.find(q['quote'],start+1)
                    if start<0:raise ValueError('CHANGED_NODE_QUOTE_UNBOUND')
            judgments.append(value);seen.add(pointer)
        except (ValueError,TypeError,KeyError) as exc:errors.append({'target_pointer':pointer,'reason':str(exc),'raw_row':row})
    pending=sorted(expected-seen);failures=[j for j in judgments if j['label']!='supported']
    return {'coverage':coverage,'reference_roles':roles,'changed_node_judgments':judgments,
        'changed_node_failures':failures,'changed_node_protocol_failures':errors,'pending_changed_nodes':pending,
        'assessment_complete':roles['reference_check_complete'] and not errors and not pending,
        'model_assessment_accepts_repair':roles['reference_check_complete'] and not coverage['failures'] and not errors and not pending and not failures,
        'source_fidelity':'model_opinion_only','scientific_correctness':'not_evaluated','whole_plan_qualified':False}


def inventory_material(evidence,category_contract, *, include_field_metadata=False):
    # Deliberate closed projection: no candidate, questions, previous reviewer
    # opinions or evaluation requirements can enter this first observation.
    result={'contract_version':INVENTORY_CONTRACT,'source_revision':evidence['source'],
        'original_fields':[{'field_locator':f['field_locator'],'text':f['text']} for f in evidence['fields']],
        'category_contract':copy.deepcopy(category_contract)}
    if include_field_metadata:
        result['field_representation']='boi/source-field-projection@1'
        for original,projected in zip(evidence['fields'],result['original_fields']):
            for key in ('record_locator','field_state','value_kind','presence_basis',
                        'span_ref','content_digest','character_count'):
                if key in original:projected[key]=copy.deepcopy(original[key])
    return result


def inventory_prompt(material):
    return ('Read the original source independently before seeing any candidate. Identify its meaningful units in Korean, '
        'each supported by exact original field quotations. Separate a cause or constraint from its outcome; preserve '
        'conditions, negation, exceptions, scope, named identity and relationships. Keep a coherent relationship together '
        'when splitting it would lose the condition or causal direction. Classify document metadata as source_context '
        'and substantive process meaning as domain_meaning. Cover every source field with unit_ids or a reason why it '
        'has no meaningful unit. Do not invent abbreviations, facts or scientific corrections. These units are provisional '
        'readings, not gold answers. No candidate, user questions or expected labels are supplied.\n'+
        json.dumps(material,ensure_ascii=False,separators=(',',':')))


def check_inventory(raw,evidence, *, version=1):
    if version not in (1,2):raise ValueError('SOURCE_UNITS_VERSION_UNSUPPORTED')
    schema=SourceMeaningInventory if version==1 else SourceMeaningInventoryV2
    value=schema.model_validate(raw).model_dump(mode='json')
    fields={f['field_locator']:f['text'] for f in evidence['fields']};units={u['unit_id']:u for u in value['units']}
    if len(units)!=len(value['units']):raise ValueError('SOURCE_UNITS_DUPLICATE_ID')
    listed=[f['field_locator'] for f in value['fields']]
    if len(listed)!=len(set(listed)) or set(listed)!=set(fields):raise ValueError('SOURCE_UNITS_FIELD_COVERAGE')
    linked=set();bindings=[]
    for unit in value['units']:
        for index,q in enumerate(unit['evidence']):
            if q['field_locator'] not in fields:raise ValueError('SOURCE_UNITS_UNKNOWN_FIELD')
            start=-1
            for _ in range(q['occurrence']+1):
                start=fields[q['field_locator']].find(q['quote'],start+1)
                if start<0:raise ValueError('SOURCE_UNITS_QUOTE_NOT_IN_SOURCE')
            bindings.append({'unit_id':unit['unit_id'],'evidence_index':index,'field_locator':q['field_locator'],
                'start':start,'end':start+len(q['quote']),'source_revision':evidence['source'],
                'field_digest':semantic_digest(fields[q['field_locator']])})
    for field in value['fields']:
        if len(field['unit_ids'])!=len(set(field['unit_ids'])):raise ValueError('SOURCE_UNITS_DUPLICATE_FIELD_LINK')
        for uid in field['unit_ids']:
            if uid not in units or not any(q['field_locator']==field['field_locator'] for q in units[uid]['evidence']):
                raise ValueError('SOURCE_UNITS_FIELD_LINK_MISMATCH')
            linked.add(uid)
    if linked!=set(units):raise ValueError('SOURCE_UNITS_UNLINKED_UNIT')
    return {'inventory':value,'quotation_bindings':bindings,'mechanical_integrity':'passed',
        'source_fidelity':'model_opinion_only','scientific_correctness':'not_evaluated'}


def semantic_components(draft):
    graph=ProcessKnowledgeDraft.model_validate(draft).model_dump(mode='json');components=[]
    def visit(value,pointer,node):
        if isinstance(value,dict):
            for key,item in value.items():
                if key in ('evidence','reused_definition'):continue
                visit(item,pointer+'/'+key,node)
        elif isinstance(value,list):
            for index,item in enumerate(value):visit(item,pointer+'/'+str(index),node)
        elif value is not None:
            components.append({'pointer':pointer,'node_pointer':node,'value':value,'value_digest':semantic_digest(value)})
    for ri,record in enumerate(graph['records']):
        for kind in ('terms','assertions'):
            for index,node in enumerate(record[kind]):
                pointer=f'/records/{ri}/{kind}/{index}';visit(node,pointer,pointer)
    # Retained document/source limitations may support context, never an
    # affirmative claim that the process semantics themselves are complete.
    for index,text in enumerate(graph.get('limitations',[])):
        components.append({'pointer':f'/limitations/{index}','node_pointer':f'/limitations/{index}',
            'value':text,'value_digest':semantic_digest(text)})
    return components


def alignment_material(inventory,draft,evidence,category_contract):
    return {'contract_version':ALIGNMENT_CONTRACT,'source_units':inventory,
        'semantic_components':semantic_components(draft),
        'original_fields':inventory_material(evidence,category_contract)['original_fields'],
        'category_contract':copy.deepcopy(category_contract),
        'candidate_draft_digest':semantic_digest(draft)}


def alignment_prompt(material):
    return ('Compare every source unit with the candidate semantic components. Source units are independent provisional '
        'interpretations, not authoritative answers: use unit_unsupported and explain when the unit is not supported by its source rather than inventing meaning. A unit is '
        'represented only if its needed meaning is expressed in the selected component values, including the cause, '
        'condition, negation, scope and direction relevant to that unit. Cite exact component_pointers. A source quotation '
        'or a reference ID is not candidate meaning; do not count words only in original_fields as represented. Related '
        'components may jointly express the unit. Normal paraphrase need not repeat the source wording. Use partial '
        'when only an outcome is represented but its stated reason is absent; specify missing_meaning without drafting '
        'a desired corrected answer. Use source_context_retained only for source_context units retained in the original '
        'fields; this does not assert a process property. No evaluation labels or desired answers are provided. '
        'This is a coverage opinion, not scientific validation. Give Korean reasons.\n'+
        json.dumps(material,ensure_ascii=False,separators=(',',':')))


def check_alignment(raw,inventory,draft):
    value=SourceMeaningAlignment.model_validate(raw).model_dump(mode='json')
    units={u['unit_id']:u for u in inventory['units']};rows=value['alignments']
    if len(rows)!=len(units) or {r['unit_id'] for r in rows}!=set(units):raise ValueError('SOURCE_ALIGNMENT_UNIT_COVERAGE')
    components={c['pointer']:c for c in semantic_components(draft)};bound=[];failures=[]
    for row in rows:
        pointers=row['component_pointers']
        if len(pointers)!=len(set(pointers)) or any(p not in components for p in pointers):
            raise ValueError('SOURCE_ALIGNMENT_COMPONENT_REFERENCE_INVALID')
        if row['status']=='represented' and (not pointers or any(p.startswith('/limitations/') for p in pointers)):
            raise ValueError('SOURCE_ALIGNMENT_REPRESENTED_COMPONENT_REQUIRED')
        if row['status']=='source_context_retained' and units[row['unit_id']]['kind']!='source_context':
            raise ValueError('SOURCE_ALIGNMENT_DOMAIN_CONTEXT_CONFUSION')
        if row['status'] in ('partial','omitted','conflicting','unit_unsupported') and not row['missing_meaning']:
            raise ValueError('SOURCE_ALIGNMENT_MISSING_MEANING_REQUIRED')
        item={**row,'unit':units[row['unit_id']],'components':[components[p] for p in pointers]};bound.append(item)
        if row['status'] not in ('represented','source_context_retained'):failures.append(item)
    return {'alignments':bound,'failures':failures,'mechanical_integrity':'passed',
        'model_assessment_accepts_coverage':not failures,'source_fidelity':'model_opinion_only',
        'scientific_correctness':'not_evaluated','whole_plan_qualified':False}


async def verify_observation(client,provider,**expected):
    """Recompute linkage using Wiki-admitted bytes; no new execution/receipt."""
    ref=provider['wiki_execution_ref']
    ex=await client.call('boi_tool_execution',{'action':'evidence','request':{'execution_ref':ref}})
    body=ex['execution']['signed_execution']['body']
    package=await client.call('boi_tasks',{'task_package_id':body['invocation']['task_revision']['ref']})
    return check_observation_binding(ex,package,ref,**expected)


def check_observation_binding(ex,package,ref,*,prompt,schema,contract,input_revisions,reading_ref,sources,value,allow_json_member_order=False):
    from .boi_structured_provider import strict_output_schema
    from boi_api.app.governed_runtime.domain_asset_store import source_manifest_digest
    from boi_api.app.governed_runtime.source_envelope import ArtifactEnvelope,byte_digest
    body=ex['execution']['signed_execution']['body'];result=json.loads(ex['output_json'])['result']
    if body['outcome']!='completed':raise ValueError('SOURCE_COVERAGE_OBSERVATION_NOT_COMPLETED')
    data=json.loads(next(i['content_json'] for i in package['domain_execution_contract']['inputs'] if i['kind']=='proposal' and i['name']=='request'))
    expected={'review_contract_version':contract,'input_revisions':input_revisions,
        'knowledge_reading_ref':reading_ref,'source_manifest_digest':source_manifest_digest([ArtifactEnvelope.model_validate(s) for s in sources])}
    prompt_equal=data['prompt']==prompt
    if not prompt_equal and allow_json_member_order:
        from boi_api.app.v2.process_answer_review_binding import _same_json_payload_prompt
        prompt_equal=_same_json_payload_prompt(data['prompt'],prompt)
    if not prompt_equal or any(data.get(k)!=v for k,v in expected.items()) or json.loads(data['output_schema_json'])!=strict_output_schema(schema):
        raise ValueError('SOURCE_COVERAGE_OBSERVATION_INPUT_MISMATCH')
    if (result['input_digest']!=semantic_digest(data) or result['provider_run']['status']!='completed'
        or result['provider_run']['prompt_digest']!=byte_digest(data['prompt'].encode())
        or result['provider_run']['output_digest']!=byte_digest(result['value_json'].encode())
        or json.loads(result['value_json'])!=value):raise ValueError('SOURCE_COVERAGE_OBSERVATION_OUTPUT_MISMATCH')
    return {'execution_ref':ref,'task_revision':body['invocation']['task_revision'],
        'reading_ref':reading_ref,'input_digest':result['input_digest'],'source_fidelity':'model_opinion_only',
        'new_model_runs':0,'new_receipts':0,'canonical_projection_eligible':False,
        'prompt_comparison':'identical_bytes' if data['prompt']==prompt else 'identical_header_and_json_values_member_order_differs'}


def observe_alignment(raw,inventory,draft):
    """Partition valid observations; do not correct invalid model references.

    Strict check_alignment stays available. This adapter retains useful rows
    while reporting invalid/missing rows as unresolved protocol errors.
    """
    from collections import Counter
    if not isinstance(raw,dict) or set(raw)!={'alignments','limitations'}:
        raise ValueError('SOURCE_ALIGNMENT_ENVELOPE_INVALID')
    if not isinstance(raw['alignments'],list):raise ValueError('SOURCE_ALIGNMENT_ROWS_INVALID')
    units={u['unit_id']:u for u in inventory['units']};counts=Counter(r.get('unit_id') for r in raw['alignments'] if isinstance(r,dict))
    issues=[];bound=[];failures=[];seen=set()
    for row in raw['alignments']:
        uid=row.get('unit_id') if isinstance(row,dict) else None
        try:
            if uid not in units or counts[uid]!=1:raise ValueError('SOURCE_ALIGNMENT_UNKNOWN_OR_DUPLICATE_UNIT')
            single=check_alignment({'alignments':[row],'limitations':raw['limitations']},{**inventory,'units':[units[uid]]},draft)
        except (ValueError,TypeError,KeyError) as exc:
            issues.append({'unit_id':uid,'reason_code':str(exc),'raw_row':copy.deepcopy(row)})
        else:
            bound.extend(single['alignments']);failures.extend(single['failures']);seen.add(uid)
    for uid in units:
        if uid not in counts:issues.append({'unit_id':uid,'reason_code':'SOURCE_ALIGNMENT_UNIT_MISSING'})
    return {'observation_contract':'boi/source-alignment-observation@1','raw_assessment':copy.deepcopy(raw),
        'alignments':bound,'failures':failures,'protocol_failures':issues,'pending_unit_ids':sorted(set(units)-seen),
        'mechanical_integrity':'partial' if issues else 'passed','assessment_complete':not issues,
        'model_assessment_accepts_coverage':not issues and not failures,'source_fidelity':'model_opinion_only',
        'scientific_correctness':'not_evaluated','whole_plan_qualified':False}


def check_source_reference_roles(raw,inventory,draft,evidence,*,version='boi/source-alignment-reference-roles@1'):
    """Add a typed reference interpretation without rewriting the @1 review.

    The admitted @1 prompt permits retained original context, but its schema
    has only component_pointers. Resolve that ambiguity only for context rows
    whose exact source fields already bind their quotes. This does not accept
    the model's context classification or establish domain representation.
    Callers must first verify the admitted material and execution bindings.
    """
    if version not in ('boi/source-alignment-reference-roles@1','boi/source-alignment-reference-roles@2'):
        raise ValueError('SOURCE_REFERENCE_ROLE_VERSION_UNSUPPORTED')
    checked=check_inventory(inventory,evidence)
    historical=observe_alignment(raw,checked['inventory'],draft)
    units={u['unit_id']:u for u in checked['inventory']['units']}
    catalog={f'/original_fields/{i}/text':f for i,f in enumerate(evidence['fields'])}
    notes={}
    if version=='boi/source-alignment-reference-roles@2':
        # The admitted material also names exact source field locators. A
        # candidate note may accompany a field, but cannot replace its quote
        # binding or prove the note's meaning. Ambiguous paths stay pending.
        components={c['pointer']:c for c in semantic_components(draft)}
        ambiguous=set()
        for field in evidence['fields']:
            pointer=field['field_locator']
            if pointer in catalog and catalog[pointer]!=field:ambiguous.add(pointer)
            catalog[pointer]=field
        ambiguous.update(set(catalog)&set(components))
        notes={p:c for p,c in components.items() if p.startswith('/limitations/') and p not in ambiguous}
        catalog={p:f for p,f in catalog.items() if p not in ambiguous}
    resolved=[];remaining=[]
    for issue in historical['protocol_failures']:
        original=issue.get('raw_row');row=original if isinstance(original,dict) else {}
        unit=units.get(issue['unit_id']);pointers=row.get('component_pointers',[])
        eligible=(issue['reason_code']=='SOURCE_ALIGNMENT_COMPONENT_REFERENCE_INVALID'
            and unit is not None and unit['kind']=='source_context'
            and row.get('status')=='source_context_retained' and bool(pointers)
            and len(pointers)==len(set(pointers)) and all(p in catalog or p in notes for p in pointers))
        source_pointers=[p for p in pointers if p in catalog] if eligible else []
        if eligible:
            locators=[catalog[p]['field_locator'] for p in source_pointers]
            eligible=(bool(source_pointers)
                and (version=='boi/source-alignment-reference-roles@1' or len(locators)==len(set(locators)))
                and set(locators)=={q['field_locator'] for q in unit['evidence']})
        if not eligible:
            remaining.append(copy.deepcopy(issue));continue
        bindings=[]
        for pointer in source_pointers:
            field=catalog[pointer]
            bindings.append({'input_pointer':pointer,'reference_role':'original_source_field',
                'field_locator':field['field_locator'],'source_revision':evidence['source'],
                'field_text_digest':semantic_digest(field['text']),
                'quotation_bindings':[b for b in checked['quotation_bindings']
                    if b['unit_id']==unit['unit_id'] and b['field_locator']==field['field_locator']]})
        item={'unit_id':unit['unit_id'],'raw_row':copy.deepcopy(row),'source_bindings':bindings,
            'context_classification':'model_opinion_only','domain_representation_verified':False}
        if version=='boi/source-alignment-reference-roles@2':
            item['candidate_context_bindings']=[{'input_pointer':p,'reference_role':'candidate_context_note',
                'value':notes[p]['value'],'value_digest':notes[p]['value_digest'],
                'semantic_support_verified':False} for p in pointers if p in notes]
        resolved.append(item)
    resolved_ids={r['unit_id'] for r in resolved}
    pending=[uid for uid in historical['pending_unit_ids'] if uid not in resolved_ids]
    for row in historical['alignments']:
        if row['status']=='source_context_retained' and (
                not row['component_pointers'] or version=='boi/source-alignment-reference-roles@2'):
            # Rows accepted by the old component-only schema contain no
            # independently resolved source field. A note alone is not one.
            code=('SOURCE_CONTEXT_REFERENCE_REQUIRED' if version=='boi/source-alignment-reference-roles@1'
                else 'SOURCE_CONTEXT_SOURCE_FIELD_REFERENCE_REQUIRED')
            remaining.append({'unit_id':row['unit_id'],'reason_code':code})
            pending.append(row['unit_id'])
    return {'contract_version':version,
        'historical_observation_contract':historical['observation_contract'],
        'historical_pending_unit_ids':historical['pending_unit_ids'],
        'resolved_context_references':resolved,'remaining_protocol_failures':remaining,
        'pending_unit_ids':pending,'reference_check_complete':not pending and not remaining,
        'semantic_judgments_changed':False,'domain_representation_verified':False,
        'scientific_correctness':'not_evaluated','new_model_runs':0,'new_receipts':0}
