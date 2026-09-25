"""Exact logical ID transport, never a semantic/physical mapping or fuzzy repair."""
from copy import deepcopy
import hashlib
import json


def digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def symbol_table(model_input):
    ids = sorted(entry.entry_id for entry in model_input.logical_context)
    if len(ids) != len(set(ids)):
        raise ValueError('LOGICAL_SYMBOL_DUPLICATE_ID')
    return {ref:'L'+str(index+1) for index,ref in enumerate(ids)}


def _is_ref(key):
    return key.endswith(('_ref','_refs')) or key in {
        'id','entry_id','properties','logical_grain','grain','depends_on','logical_ids'}


def encode_context(value, table):
    # Only declared reference positions change. Descriptions, literal values and
    # original question bytes never undergo a string/global replacement.
    def walk(item, reference=False):
        if isinstance(item,str): return table.get(item,item) if reference else item
        if isinstance(item,list): return [walk(child,reference) for child in item]
        if isinstance(item,dict): return {k:walk(v,_is_ref(k)) for k,v in item.items()}
        return item
    result=deepcopy(value)
    result['logical_context']=walk(result['logical_context'])
    if 'clarification_context' in result:
        result['clarification_context']=walk(result['clarification_context'])
    result['logical_symbol_table_digest']=digest(table)
    return result


def decode_candidate(raw, table):
    result=deepcopy(raw); inverse={symbol:ref for ref,symbol in table.items()}
    def ref(value):
        if value is None: return None
        if value not in inverse: raise ValueError('LOCAL_MODEL_UNKNOWN_LOGICAL_SYMBOL')
        return inverse[value]
    def refs(value): return [ref(item) for item in value]
    for key in ('entity_ids','property_ids','metric_ids','dimensions','grain'):
        result[key]=refs(result.get(key,[]))
    if 'rowset_object_ids' in result:
        result['rowset_object_ids'] = refs(result['rowset_object_ids'])
    for item in result.get('filters',[]):
        item['property_id']=ref(item['property_id'])
        if item.get('unit_ref') is not None: item['unit_ref']=ref(item['unit_ref'])
    for item in result.get('aggregations',[]):
        item['target_id']=ref(item['target_id'])
        if item.get('scope_object_id') is not None: item['scope_object_id']=ref(item['scope_object_id'])
        if item.get('partition_by') is not None: item['partition_by']=refs(item['partition_by'])
        if item.get('group_by') is not None: item['group_by']=refs(item['group_by'])
    for item in result.get('ordering',[]): item['property_id']=ref(item['property_id'])
    if isinstance(result.get('time_range'),dict): result['time_range']['property_id']=ref(result['time_range']['property_id'])
    for item in result.get('ambiguity_alternatives',[]): item['logical_ids']=refs(item['logical_ids'])
    for item in result.get('quality_requests',[]):
        item['subject_object_id']=ref(item['subject_object_id'])
        item['relationship_id']=ref(item['relationship_id'])
    return result


def bind_declared_version(raw, declared_version):
    """The selected tool contract is transport metadata, never model authority."""
    supplied = raw.get('intent_contract_version')
    if 'intent_contract_version' in raw and supplied != declared_version:
        raise ValueError('LOCAL_MODEL_INTENT_REVISION_MISMATCH')
    result = deepcopy(raw)
    result['intent_contract_version'] = declared_version
    proof = {'contract':'boi/declared-intent-envelope@1', 'declared_version':declared_version,
             'raw_candidate':deepcopy(raw), 'bound_candidate_digest':digest(result),
             'injected_fields':[] if supplied is not None else ['intent_contract_version'],
             'semantic_changes':[], 'status':'ENVELOPE_BOUND_NOT_VALIDATED'}
    return result, proof
