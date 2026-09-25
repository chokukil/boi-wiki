"""Dependency units planned before upload; no semantic or publication grant.

One confirmed bundle may contain several atomic units. Exact declared native
references determine predecessor units; co-publication groups remain indivisible.
No question, label, domain name or fixture identity selects a unit's meaning.
"""
from .local_bundle_contract import LocalBundleManifest
from .publication_capacity import initial_publication_capacity
from .semantic_binding_contract import semantic_digest


MAX_UNIT_PROPOSAL_BYTES=16*1024*1024
PLAN_POLICY={'contract_version':'boi/dependency-unit-planner@1',
    'maximum_unit_changes':100,'maximum_unit_proposal_bytes':MAX_UNIT_PROPOSAL_BYTES,
    'namespace_scope':'one_namespace_per_unit','visibility':'atomic_per_unit',
    'dependency_basis':'exact_declared_native_references_and_co_publication_groups'}


def _components(graph):
    """SCC after grouping can merge an otherwise acyclic native-reference DAG."""
    index,stack,on_stack,seen,low,components=0,[],set(),{}, {},[]
    def visit(node):
        nonlocal index
        seen[node]=low[node]=index;index+=1
        stack.append(node);on_stack.add(node)
        for dependency in sorted(graph[node]):
            if dependency not in seen:
                visit(dependency);low[node]=min(low[node],low[dependency])
            elif dependency in on_stack:
                low[node]=min(low[node],seen[dependency])
        if low[node]==seen[node]:
            component=[]
            while True:
                item=stack.pop();on_stack.remove(item);component.append(item)
                if item==node:break
            components.append(tuple(sorted(component)))
    for node in sorted(graph):
        if node not in seen:visit(node)
    return components


def plan_publication_units(manifest):
    manifest=LocalBundleManifest.model_validate(manifest.model_dump(mode='json'))
    if manifest.publication_layout is None:
        raise ValueError('LOCAL_BUNDLE_PUBLICATION_LAYOUT_REQUIRED')
    changes={c.object_id:c for c in manifest.changes}
    objects={o.object_id:o for o in manifest.objects}
    groups=[tuple(sorted(group)) for group in manifest.publication_layout.co_publish_groups]
    assigned={x for group in groups for x in group}
    groups.extend((x,) for x in sorted(set(changes)-assigned))
    membership={x:i for i,g in enumerate(groups) for x in g}
    graph={i:set() for i in range(len(groups))}
    edges={(b.object_id,b.target_object_id) for b in manifest.references
           if b.kind in ('knowledge_revision','knowledge_identity')}
    for source,target in edges:
        if membership[source]!=membership[target]:graph[membership[source]].add(membership[target])
    components=_components(graph)
    nodes={i:tuple(sorted(x for g in component for x in groups[g])) for i,component in enumerate(components)}
    membership={x:i for i,node in nodes.items() for x in node}
    graph={i:set() for i in nodes}
    for source,target in edges:
        if membership[source]!=membership[target]:graph[membership[source]].add(membership[target])
    blocked=[]
    for index,node in nodes.items():
        namespaces={changes[x].namespace for x in node}
        reason=('cross_namespace_atomic_group_requires_restructure' if len(namespaces)!=1 else
            'indivisible_group_exceeds_change_limit' if len(node)>manifest.publication_layout.maximum_unit_changes else
            'indivisible_group_exceeds_proposal_bytes' if sum(objects[x].byte_length for x in node)>MAX_UNIT_PROPOSAL_BYTES else None)
        if reason:blocked.append({'object_ids':list(node),'reason':reason})
    policy=dict(PLAN_POLICY)
    if any(b.kind=='knowledge_identity' for b in manifest.references):
        policy.update(contract_version='boi/dependency-unit-planner@2',
            dependency_basis='exact_native_revision_and_identity_references_and_co_publication_groups')
    base={'contract_version':'boi/local-publication-plan@1','manifest_digest':manifest.digest,
        'policy':policy,'visibility':'atomic_per_unit','semantic_grouping_verified':False,
        'confirmation_scope':'whole_declared_unit_plan','exact_composite_capacity_proven':False}
    if blocked:
        plan={**base,'status':'requires_local_restructure','units':[],'blocked':blocked}
        return {**plan,'plan_digest':semantic_digest(plan)}
    # Fill a unit only with whole SCCs. Dependencies in the same unit must
    # already be selected; otherwise their prior units must precede this one.
    pending=set(nodes);done=set();ordered=[]
    while pending:
        selected=[];selected_nodes=set();namespace=None;total_bytes=0
        while True:
            ready=sorted((n for n in pending-selected_nodes if graph[n]<=done|selected_nodes),key=lambda n:nodes[n])
            chosen=None
            for n in ready:
                group=nodes[n];ns=changes[group[0]].namespace
                size=sum(objects[x].byte_length for x in group)
                if ((namespace is None or ns==namespace)
                        and len(selected)+len(group)<=manifest.publication_layout.maximum_unit_changes
                        and total_bytes+size<=MAX_UNIT_PROPOSAL_BYTES):
                    chosen=n;break
            if chosen is None:break
            group=nodes[chosen]
            namespace=changes[group[0]].namespace
            selected.extend(group);selected_nodes.add(chosen)
            total_bytes+=sum(objects[x].byte_length for x in group)
        if not selected:raise ValueError('LOCAL_PUBLICATION_PLAN_NO_PROGRESS')
        pending-=selected_nodes;done|=selected_nodes
        ordered.append({'object_ids':sorted(selected),'namespace':namespace,'proposal_bytes':total_bytes})
    unit_for={x:index for index,unit in enumerate(ordered) for x in unit['object_ids']}
    units=[]
    for index,unit in enumerate(ordered):
        predecessors=sorted({unit_for[target] for source,target in edges if source in unit['object_ids'] and unit_for[target]!=index})
        if any(x>=index for x in predecessors):raise ValueError('LOCAL_PUBLICATION_UNIT_DEPENDENCY_ORDER')
        metadata={**unit,'position':index,'predecessor_positions':predecessors,
            'minimum_capacity':initial_publication_capacity([changes[x] for x in unit['object_ids']]),
            'atomic_visibility':True}
        units.append({**metadata,'unit_id':'publication-unit:'+semantic_digest([manifest.digest,metadata])})
    plan={**base,'status':'planned_requires_exact_preflight','units':units,'blocked':[]}
    return {**plan,'plan_digest':semantic_digest(plan)}
