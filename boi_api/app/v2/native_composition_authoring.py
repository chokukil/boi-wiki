"""Lossless request-local authoring references to already selected evidence.

These are transport handles, never semantic selection, approval, or answer
caches. The protected preparation owns their canonical values. The normal
binder and statement-role contracts validate every expanded draft.
"""
import copy
from ..governed_runtime.semantic_binding_contract import semantic_digest

# Identity-bearing fields only. Never substitute source text or interpretations.
IDENTITY_KEYS = frozenset(('node_id', 'span_ref', 'source_revision_digest',
    'revision_digest', 'ref', 'content_digest', 'field_content_digest',
    'quote_digest', 'manifest_digest'))


def expand_identity_references(value, references):
    def visit(item, key=None):
        if isinstance(item, dict):
            return {k: visit(v, k) for k, v in item.items()}
        if isinstance(item, list):
            return [visit(v, key) for v in item]
        if key in IDENTITY_KEYS and isinstance(item, str) and item.startswith('@r'):
            if item not in references:
                raise ValueError('NATIVE_AUTHORING_IDENTITY_UNKNOWN')
            return references[item]
        return item
    return visit(value)


def inline_authoring_meanings(material):
    """Place selected meanings beside their citation, without copying shared nodes.

    Only the first use owns a node's payload. Subsequent uses retain their own
    role/scope and reference that node; sharing never inherits a use's conditions.
    The ordinal restores the original catalog order, independently of selection
    order. This is presentation of an existing selection, not a new selection.
    """
    nodes = material.get('meaning_nodes')
    if not isinstance(nodes, list) or not nodes:
        return False
    by_id = {node['node_id']: (i, node) for i, node in enumerate(nodes)}
    uses = [use for target in material.get('meaning_targets', [])
            for use in target.get('graph_nodes', [])]
    if (len(by_id) != len(nodes) or {use['node_id'] for use in uses} != set(by_id)
            or any('meaning' in use or 'meaning_index' in use for use in uses)):
        return False
    seen = set()
    for use in uses:
        node_id = use['node_id']
        if node_id not in seen:
            index, node = by_id[node_id]
            use['meaning_index'] = index
            use['meaning'] = {k: v for k, v in node.items() if k != 'node_id'}
            seen.add(node_id)
    del material['meaning_nodes']
    return True


def restore_authoring_meanings(material):
    """Reconstruct exact nodes; reject missing, repeated or ambiguous ownership."""
    if 'meaning_nodes' in material:
        raise ValueError('NATIVE_AUTHORING_MEANINGS_AMBIGUOUS')
    nodes = {}; ids = set(); referenced = set()
    for target in material.get('meaning_targets', []):
        for use in target.get('graph_nodes', []):
            node_id = use['node_id']; referenced.add(node_id)
            if 'meaning' not in use and 'meaning_index' not in use:
                continue
            index = use.pop('meaning_index', None)
            node = use.pop('meaning', None)
            if (type(index) is not int or index < 0 or index in nodes
                    or node_id in ids or not isinstance(node, dict) or 'node_id' in node):
                raise ValueError('NATIVE_AUTHORING_MEANINGS_INVALID')
            ids.add(node_id); nodes[index] = {'node_id': node_id, **node}
    if referenced != ids or set(nodes) != set(range(len(nodes))):
        raise ValueError('NATIVE_AUTHORING_MEANINGS_INCOMPLETE')
    material['meaning_nodes'] = [nodes[i] for i in range(len(nodes))]


def selected_review_pointer_inventory(binding, targets):
    """Project status inventories onto the already selected dependency closure.

    Source meanings, findings, limitations and failures are unchanged. The full
    review is retained in the protected preparation and original revision; this
    projection neither chooses meanings nor converts a whole review to approval.
    """
    selected = set()
    candidate = binding.get('candidate_revision')
    for target in targets:
        if target.get('asset_revision') == candidate:
            selected.add(target['target_pointer'])
        for node in target.get('graph_evidence', []):
            if node.get('asset_revision') == candidate:
                selected.add(node['target_pointer'])
    result = copy.deepcopy(binding)
    fields = ('usable_node_pointers', 'quarantined_node_pointers',
        'pending_review_node_pointers', 'failed_claim_pointers')
    for obj in (result, result.get('source_review', {})):
        for key in fields:
            if isinstance(obj.get(key), list):
                # A containing review scope can qualify a selected descendant.
                obj[key] = [p for p in obj[key] if any(
                    q == p or q.startswith(p + '/') or p.startswith(q + '/') for q in selected)]
    result['pointer_inventory_scope'] = 'selected_targets_and_dependency_closure'
    result['full_review_read'] = {'tool':'boi_knowledge_read', 'arguments':{
        'revision':binding['review_revision'], 'view':'asset', 'lane':'provisional'}}
    return result


def authoring_material(prepared):
    """Keep all meaning values, roles, conditions, conflicts and original text."""
    material = copy.deepcopy(prepared)
    citations = {}
    def cite(value):
        ref = 'c' + semantic_digest(value).split(':')[1][:16]
        if ref in citations and citations[ref] != value:
            raise ValueError('NATIVE_AUTHORING_REFERENCE_COLLISION')
        citations[ref] = value
        return ref
    for target in material.get('meaning_targets', []):
        if target.get('binding_status') == 'bound' and target.get('review_use_status') != 'unavailable_pending_or_quarantined':
            target['citation_ref'] = cite({'kind':'meaning',
                'asset_revision':target['asset_revision'], 'target_pointer':target['target_pointer']})
    for source in material.get('sources', []):
        for field in source.get('fields', []):
            if field.get('text'):
                field['citation_ref'] = cite({'kind':'source_quote',
                    'source_revision_digest':source['source']['digest'],
                    'quotation':{'field_locator':field['field_locator'], 'quote':field['text'], 'occurrence':0}})
    for target in material.get('execution_targets', []):
        target['citation_ref'] = cite({'kind':'execution_result', 'result_digest':target['result_digest']})
    inline_meanings = inline_authoring_meanings(material)
    # The identifiers still appear once and are resolvable without another read.
    references = {}
    inverse = {}
    def visit(value, key=None):
        if isinstance(value, dict):return {k:visit(v,k) for k,v in value.items()}
        if isinstance(value, list):return [visit(v,key) for v in value]
        if key in IDENTITY_KEYS and isinstance(value,str) and len(value)>40:
            if value not in inverse:
                alias='@r'+str(len(inverse)+1);inverse[value]=alias;references[alias]=value
            return inverse[value]
        return value
    material = visit(material)
    material['authoring_references'] = {'contract_version':'boi/native-authoring-references@1',
        'identities':references,
        'usage':'Identity aliases resolve through identities. For each statement and request facet, use citations:[{"citation_ref":"..."}] from selected meaning_targets or source fields. References retain the exact meaning closure or original field; they do not prove support. Canonical citations remain accepted. Do not output internal references in the final answer.'}
    if inline_meanings:
        material['authoring_references']['meaning_layout'] = 'inline_first_use'
    schema=material.get('draft_schema')
    if schema and citations:
        defs=schema['$defs']
        citation_schemas={}
        def ref_schema(kinds):
            ids=[r for r,c in citations.items() if c['kind'] in kinds]
            if not ids:return False
            key=tuple(ids)
            if key not in citation_schemas:
                name='PreparedCitation'+str(len(citation_schemas)+1)
                citation_schemas[key]=name
                defs[name]={'type':'object','additionalProperties':False,'required':['citation_ref'],
                    'properties':{'citation_ref':{'type':'string','enum':ids}}}
            return {'$ref':'#/$defs/'+citation_schemas[key]}
        roles={'SourceStatement':{'meaning','source_quote'}, 'GapStatement':{'meaning','source_quote'},
            'RecommendationStatement':{'meaning','source_quote'},
            'RequestFacet':{'meaning','source_quote','execution_result'}}
        for name,kinds in roles.items():
            def replace(node):
                if not isinstance(node,dict):return
                prop=node.get('properties',{}).get('citations')
                if prop is not None:
                    prop['items']={'anyOf':[ref_schema(kinds),{'$ref':'#/$defs/SourceScopeCitation'}]}
                for branch in node.get('anyOf',[]):replace(branch)
            replace(defs[name])
        # Deduplicate only byte-identical schema branches. No constraints omitted.
        shared={}
        def factor(node):
            if isinstance(node,dict):
                for k,v in list(node.items()):
                    if k=='anyOf' and isinstance(v,list):
                        for i,branch in enumerate(v):
                            if isinstance(branch,dict) and 'properties' in branch and len(str(branch))>700:
                                digest=semantic_digest(branch)
                                name=shared.setdefault(digest, ('AuthoringBranch'+str(len(shared)+1),branch))[0]
                                v[i]={'$ref':'#/$defs/'+name}
                    else:factor(v)
            elif isinstance(node,list):
                for v in node:factor(v)
        factor(schema)
        for name,branch in shared.values():defs[name]=branch
        def schema_refs(node):
            if isinstance(node,dict):
                for key,value in node.items():
                    if key=='$ref' and isinstance(value,str) and value.startswith('#/$defs/'):
                        yield value.removeprefix('#/$defs/')
                    else:yield from schema_refs(value)
            elif isinstance(node,list):
                for value in node:yield from schema_refs(value)
        used=set();pending=list(schema_refs({k:v for k,v in schema.items() if k!='$defs'}))
        while pending:
            name=pending.pop()
            if name in used:continue
            used.add(name)
            pending.extend(schema_refs(defs[name]))
        schema['$defs']={k:v for k,v in defs.items() if k in used}
    return material, {'citations':citations,'identities':references}


def expand_authoring_draft(draft, references):
    expanded=expand_identity_references(copy.deepcopy(draft),references.get('identities',{}))
    for answer in expanded.get('answers',[]):
        groups=[*answer.get('sentences',[]),*answer.get('limitations',[]),
            *(answer.get('request_plan') or {}).get('facets',[])]
        for item in groups:
            for i,citation in enumerate(item.get('citations',[])):
                if 'citation_ref' not in citation:continue
                if set(citation)!={'citation_ref'} or citation['citation_ref'] not in references.get('citations',{}):
                    raise ValueError('NATIVE_AUTHORING_CITATION_UNKNOWN')
                item['citations'][i]=copy.deepcopy(references['citations'][citation['citation_ref']])
    return expanded
