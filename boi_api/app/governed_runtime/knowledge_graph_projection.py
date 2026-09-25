"""Rebuildable, revision-addressed navigation over existing meaning payloads.

Explicit local IDs survive reordering. Historical pointer-only nodes keep their
revision identity until a later, explicit alignment is supplied; text similarity
or a directory path never becomes an identity assertion.
"""
from copy import deepcopy

from .semantic_binding_contract import semantic_digest


def _typed_graph(*, logical_id, namespace, revision, content):
    from .knowledge_content import decode_knowledge_content
    from .typed_knowledge_meaning import TypedKnowledgeMeaning
    envelope = decode_knowledge_content(content)
    typed = TypedKnowledgeMeaning.model_validate(envelope.meaning)
    meaning = content['meaning']
    groups = ('conditions', 'exceptions', 'applicability')
    node_count = len(typed.assertions) + len(typed.parameters) + sum(
        len(getattr(a, group)) for a in typed.assertions for group in groups)
    edge_count = node_count - len(typed.assertions) - len(typed.parameters) + sum(
        len(a.depends_on) for a in (*typed.assertions, *typed.parameters))
    if node_count > 4096 or edge_count > 8192:
        raise ValueError('KNOWLEDGE_GRAPH_PROJECTION_BOUND_EXCEEDED')

    nodes, edges, pointers, assertions, object_references = [], [], {}, {}, []

    def node(pointer, value, *, group=None):
        local = value['id'] if group is not None else None
        key = [namespace, logical_id, group, local] if local is not None else [revision, pointer]
        node_id = 'meaning:' + semantic_digest(key).removeprefix('sha256:')
        # A parent's citation is not inherited by a qualifier. Root navigation
        # includes descendant bindings but does not attest their interpretation.
        bindings = [f'/evidence_bindings/{i}' for i, binding in enumerate(content['evidence_bindings'])
            if binding['meaning_pointer'] == pointer or binding['meaning_pointer'].startswith(pointer + '/')]
        result = {'node_id':node_id, 'revision':deepcopy(revision), 'target_pointer':pointer,
            'identity_status':'explicit_local_identity' if local is not None else 'revision_pointer_only',
            'local_id':local, 'value':deepcopy(value), 'evidence_pointers':bindings,
            'scope_inherited':False, 'semantic_support_verified':False}
        nodes.append(result)
        pointers[pointer] = node_id
        return result

    for group in ('assertions', 'parameters'):
        for i, value in enumerate(meaning.get(group, [])):
            root = node(f'/{group}/{i}', value, group=group)
            if group == 'assertions':
                assertions[value['id']] = root
    roots = list(nodes)
    for root in roots:
        pointer, value = root['target_pointer'], root['value']
        for group, relation in (('conditions','condition'), ('exceptions','exception'), ('applicability','applicability')):
            for i, qualifier in enumerate(value.get(group, [])):
                child = node(f'{pointer}/{group}/{i}', qualifier)
                edges.append({'source':root['node_id'], 'target':child['node_id'], 'type':relation,
                    'evidence_pointer':child['target_pointer'], 'scope_inherited':False})
        for i, dependency in enumerate(value.get('depends_on', [])):
            edges.append({'source':root['node_id'], 'target':assertions[dependency]['node_id'],
                'type':'depends_on', 'evidence_pointer':f'{pointer}/depends_on/{i}', 'scope_inherited':False})
        if value.get('value', {}).get('kind') == 'object':
            object_references.append({'source':root['node_id'], 'assertion_pointer':pointer,
                'target_identity':value['value']['value'], 'target_resolution':'not_resolved',
                'predicate':deepcopy(value['predicate']), 'statement':value['statement'],
                'assertion_kind':value['assertion_kind'], 'polarity':value['polarity'], 'modality':value['modality'],
                **{key:deepcopy(value.get(key, [])) for key in (*groups, 'depends_on', 'uncertainties')},
                'valid_time':deepcopy(value['valid_time']), 'evidence_pointers':deepcopy(root['evidence_pointers']),
                'semantic_support_verified':False, 'scope_inherited':False})

    return {'contract_version':'boi/knowledge-graph-projection@2', 'revision':deepcopy(revision),
        'logical_id':logical_id, 'namespace':namespace, 'nodes':nodes, 'edges':edges,
        'object_references':object_references, 'object_type':deepcopy(meaning['object_type']),
        'unresolved':deepcopy(content.get('unresolved', [])), 'pointer_compatibility':pointers,
        'pointer_basis':'content.meaning', 'context_layer':None,
        'semantics':{'hierarchy_inherits_conditions':False, 'folder_depth_is_layer':False,
            'graph_presence_is_approval':False, 'projection_is_content_authority':False,
            'traversal_qualified':False, 'object_identity_resolution':'not_performed',
            'predicate_direction':'exact_authored_subject_to_value_only',
            'causal_interpretation_inferred':False}}


def project_knowledge_graph(*, logical_id, namespace, revision, content):
    from ..v2.native_definition_sources import declared_meaning_index, native_meaning_links
    contract = content.get('contract_version')
    if (contract == 'boi/knowledge-content@1' and isinstance(content.get('meaning'), dict)
            and content['meaning'].get('contract_version') == 'boi/typed-knowledge-meaning@1'):
        return _typed_graph(logical_id=logical_id, namespace=namespace, revision=revision, content=content)
    body = content.get('draft', {}) if contract in ('boi/bound-process-meaning@1', 'boi/bound-process-meaning@2') else content
    nodes, edges, pointer_map, local_ids = [], [], {}, {}
    for entry in declared_meaning_index(content):
        value, pointer = entry['value'], entry['target_pointer']
        local = value.get('id') or value.get('term_id') or value.get('assertion_id')
        scope = ''
        parts = pointer.split('/')
        if len(parts) > 3 and parts[1] == 'records':
            try:
                scope = body['records'][int(parts[2])]['process_ref']
            except (KeyError, IndexError, ValueError, TypeError):
                local = None
        stable = isinstance(local, str) and bool(local)
        key = [namespace, logical_id, scope, local] if stable else [revision, pointer]
        node_id = 'meaning:' + semantic_digest(key).removeprefix('sha256:')
        node = {'node_id': node_id, 'revision': revision, 'target_pointer': pointer,
                'identity_status': 'explicit_local_identity' if stable else 'revision_pointer_only',
                'local_id': local if stable else None, 'value': value,
                'evidence_pointers': entry['evidence_pointers'], 'scope_inherited': False,
                'semantic_support_verified': False}
        nodes.append(node)
        pointer_map[pointer] = node_id
        if stable:
            local_ids[(scope, local)] = node_id
    for node in nodes:
        pointer, value = node['target_pointer'], node['value']
        for link in native_meaning_links(value, pointer):
            if link['target_pointer'] in pointer_map:
                edges.append({'source': node['node_id'], 'target': pointer_map[link['target_pointer']],
                    'type': link['relation'], 'evidence_pointer': link['relation_pointer'], 'scope_inherited': False})
    if contract == 'boi/common-meaning@1':
        for i, relation in enumerate(body.get('relations', [])):
            source, target = local_ids.get(('', relation['source'])), local_ids.get(('', relation['target']))
            if source and target:
                edges.append({'source': source, 'target': target, 'type': relation['type'],
                    'relation_node_id': local_ids.get(('', relation['id'])),
                    'evidence_pointer': '/relations/' + str(i), 'conditions': relation.get('conditions', []),
                    **{key: relation[key] for key in ('exceptions','applicability','modality','uncertainties') if key in relation},
                    'scope_inherited': False})
    if contract in ('boi/process-meaning@1', 'boi/bound-process-meaning@1', 'boi/bound-process-meaning@2'):
        for ri, record in enumerate(body.get('records', [])):
            scope = record['process_ref']
            for ai, assertion in enumerate(record.get('assertions', [])):
                claim = local_ids.get((scope, assertion['assertion_id']))
                if not claim:
                    continue
                for relation, refs in (('subject_identity', [assertion['subject_ref']]),
                                       ('object_identity', assertion.get('object_refs', [])),
                                       ('depends_on', assertion.get('depends_on', []))):
                    for ref in refs:
                        if (scope, ref) in local_ids:
                            edges.append({'source': claim, 'target': local_ids[(scope, ref)], 'type': relation,
                                'evidence_pointer': f'/records/{ri}/assertions/{ai}', 'scope_inherited': False})
    return {'contract_version': 'boi/knowledge-graph-projection@1', 'revision': revision,
            'logical_id': logical_id, 'namespace': namespace, 'nodes': nodes, 'edges': edges,
            'pointer_compatibility': pointer_map, 'context_layer': body.get('context_layer'),
            'semantics': {'hierarchy_inherits_conditions': False, 'folder_depth_is_layer': False,
                          'graph_presence_is_approval': False, 'projection_is_content_authority': False}}
