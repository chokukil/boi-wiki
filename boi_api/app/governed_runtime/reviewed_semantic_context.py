"""Source adapter into the common semantic context, after current scope checks.

No search score, model output or caller-supplied identity can construct a review.
This adapter consumes the same checked source/review/mapping closure as execution.
"""
from .bulk_migration import _digest
from .metadata_mapping_profile import derive_metadata_object_set_shapes
from .reviewed_metadata_answer import _reviewed_entries
from .semantic_authority import ReviewedDefinitionAuthority
from .semantic_profile_loader import LoadedProfileEntry, PhysicalProfileBinding, SemanticContextBundle
from .semantic_qualifier import validate_candidate_qualifier_provenance
from .semantic_query_planner import (
    PlannerCatalogColumn,
    PlannerCatalogSnapshot,
    PlannerCatalogSource,
    PlannerCatalogTable,
)


def _derived_object_set_contracts(inputs, *, maximum_rows, quality_receipt_digest):
    by_mapping = {item.physical.mapping_ref: item for item in inputs.properties}
    object_values = []
    source_by_object = {}
    for obj in inputs.objects:
        try:
            keys = tuple(by_mapping[ref].logical_property_ref
                         for ref in obj.logical_key_mapping_refs)
        except KeyError as error:
            raise ValueError('REVIEWED_OBJECT_SET_KEY_MAPPING_MISSING') from error
        object_values.append({
            'object_ref': obj.object_ref,
            'logical_key_mapping_refs': keys,
        })
        source_by_object[obj.object_ref] = obj
    shapes = derive_metadata_object_set_shapes(
        object_mappings=object_values, maximum_rows=maximum_rows
    )
    records = []
    for shape in shapes:
        obj = source_by_object[shape.root_object_ref]
        body = {
            'contract_version': 'boi/reviewed-object-set-derivation@1',
            'status': 'PROVISIONAL',
            'authority': 'reviewed_definition_scope',
            'source_object_mapping': obj.model_dump(mode='json'),
            'result_shape_contract': shape.model_dump(mode='json'),
            'mapping_input_digest': _digest(inputs.model_dump(mode='json')),
            'quality_receipt_digest': quality_receipt_digest,
            'query_specific': False,
            'semantic_equivalence_decided': False,
            'production_changed': False,
            'active_transition': False,
        }
        records.append({**body, 'receipt_digest': _digest(body)})
    return tuple(records)


def build_reviewed_planner_catalog(repository, scope, *, capability_digest,
        supported_operators):
    """Project the already authorized catalog record into the common planner type."""
    inputs = scope.inputs
    raw = repository.store.get(
        'bulk_migration_catalog_snapshots', scope.manifest['catalog_snapshot_ref']
    ) or {}
    if (raw.get('employee_id') != scope.run.principal
            or raw.get('snapshot_ref') != scope.manifest['catalog_snapshot_ref']
            or raw.get('digest') != inputs.catalog_snapshot_digest
            or raw.get('schema_digest') != inputs.schema_snapshot_digest):
        raise ValueError('REVIEWED_PLANNER_CATALOG_STALE')
    raw_tables = raw.get('tables') or {}
    if not isinstance(raw_tables, dict):
        raise ValueError('REVIEWED_PLANNER_CATALOG_INVALID')
    requested = {}
    for prop in inputs.properties:
        requested.setdefault(prop.physical.table, set()).add(prop.physical.column)
    tables = []
    for table_name in sorted(requested):
        table = raw_tables.get(table_name)
        if not isinstance(table, dict) or not isinstance(table.get('columns'), dict):
            raise ValueError('REVIEWED_PLANNER_TABLE_UNAVAILABLE')
        primary = set(table.get('primary_key') or ())
        unique = {tuple(value) if isinstance(value, (list, tuple)) else (value,)
                  for value in (table.get('unique_keys') or ())}
        columns = []
        for column_name in sorted(requested[table_name]):
            raw_column = table['columns'].get(column_name)
            if raw_column is None:
                raise ValueError('REVIEWED_PLANNER_COLUMN_UNAVAILABLE')
            if isinstance(raw_column, dict):
                data_type = str(raw_column.get('data_type') or '')
                nullable = bool(raw_column.get('nullable', column_name not in primary))
                is_unique = bool(raw_column.get('unique', False))
            else:
                data_type = str(raw_column)
                nullable = column_name not in primary
                is_unique = False
            columns.append(PlannerCatalogColumn(
                name=column_name, data_type=data_type, nullable=nullable,
                primary_key=column_name in primary,
                unique=is_unique or (column_name,) in unique or column_name in primary,
            ))
        tables.append(PlannerCatalogTable(
            name=table_name,
            estimated_rows=max(0, int(table.get('estimated_rows') or 0)),
            columns=tuple(columns),
        ))
    dialect = str(raw.get('dialect') or '')
    if not dialect:
        raise ValueError('REVIEWED_PLANNER_DIALECT_REQUIRED')
    return PlannerCatalogSnapshot(
        snapshot_digest=inputs.catalog_snapshot_digest,
        schema_digest=inputs.schema_snapshot_digest,
        capability_digest=capability_digest,
        captured_at=str(raw.get('captured_at') or scope.run.started_at),
        freshness_status='CURRENT',
        supported_dialects=(dialect,),
        supported_operators=tuple(sorted(set(supported_operators))),
        sources=(PlannerCatalogSource(
            source_id=inputs.source_id,
            backend=dialect,
            read_only=True,
            tables=tuple(tables),
        ),),
    )


def build_reviewed_semantic_context(repository, scope, *, preview_digest, supported_operators, maximum_rows,
        retrieval_policy):
    if maximum_rows < 1 or maximum_rows > 1000 or not supported_operators:
        raise ValueError('REVIEWED_QUERY_CAPABILITY_POLICY_REQUIRED')
    inputs=scope.inputs
    source_stage=repository.get_stage_receipt(scope.shard.stage_receipt_refs.get('domain-ontology-draft','')) or {}
    facets=validate_candidate_qualifier_provenance(scope.domain,source_stage.get('output') or {},
        subject_facets_required='boi/source-subject-facets@1' in scope.manifest.get('profile_revisions',()))
    derived_shapes = _derived_object_set_contracts(
        inputs, maximum_rows=maximum_rows,
        quality_receipt_digest=scope.audit['receipt_digest'],
    )
    declared_object_sets=tuple(shape for shape in inputs.result_shapes
        if shape.shape=='ObjectSet')
    if declared_object_sets:
        derived_by_root={item['result_shape_contract']['root_object_ref']:item
            for item in derived_shapes}
        if (len(declared_object_sets)!=len(derived_by_root)
            or {shape.root_object_ref for shape in declared_object_sets}!=set(derived_by_root)):
            raise ValueError('REVIEWED_OBJECT_SET_DECLARATION_DRIFT')
        for shape in declared_object_sets:
            source=derived_by_root[shape.root_object_ref]['result_shape_contract']
            if (shape.limit_policy.kind!='EXPLICIT'
                or shape.limit_policy.maximum_rows is None
                or maximum_rows>shape.limit_policy.maximum_rows):
                raise ValueError('REVIEWED_OBJECT_SET_LIMIT_NOT_AUTHORIZED')
            original=derive_metadata_object_set_shapes(object_mappings=[{
                'object_ref':shape.root_object_ref,
                'logical_key_mapping_refs':source['exact_grain'],
            }],maximum_rows=shape.limit_policy.maximum_rows)[0]
            if shape!=original:
                raise ValueError('REVIEWED_OBJECT_SET_DECLARATION_DRIFT')
    context={'contract_version':'boi/reviewed-question-context@2','manifest_digest':scope.run.manifest_digest,
        'preview_digest':preview_digest,'shard_id':scope.shard.shard_id,'domain_candidates':scope.domain,
        'existing_definition_index':{k:v for k,v in scope.index.items() if k!='updated_at'},
        'declared_mapping_inputs':inputs.model_dump(mode='json'),'quality_audit_receipt':scope.audit,
        'interpretation_receipt':{k:v for k,v in scope.review.items() if k!='updated_at'},
        'source_subject_facets':facets,
        'derived_query_contracts':list(derived_shapes)}
    capability={'contract_version':'boi/reviewed-question-capabilities@1',
        'supported_operators':sorted(set(supported_operators)),'maximum_rows':maximum_rows,
        'retrieval_policy':retrieval_policy,
        'execution_authority_granted':False}
    authority=ReviewedDefinitionAuthority(principal=scope.run.principal,purpose=scope.manifest['purpose'],
        run_id=scope.run.run_id,shard_id=scope.shard.shard_id,manifest_digest=scope.run.manifest_digest,
        preview_digest=preview_digest,interpretation_receipt_digest=scope.review['receipt_digest'],
        input_context_digest=_digest(context),domain_candidate_closure_digest=inputs.domain_candidate_closure_digest,
        definition_index_digest=scope.index['digest'],mapping_input_digest=_digest(inputs.model_dump(mode='json')),
        quality_receipt_digest=scope.audit['receipt_digest'],acl_policy_digest=scope.manifest['acl_policy_digest'])
    domain=_reviewed_entries(context)
    mappings=tuple(LoadedProfileEntry(entry_id=p.physical.mapping_ref,category='mapping',
        revision_id='mapping:'+p.physical.revision_digest,revision_digest=p.physical.revision_digest,
        boi_id=p.physical.mapping_ref,visibility='private',evidence_resources=p.evidence_span_refs,
        payload={'mapping_id':p.physical.mapping_ref,'domain_ref':p.logical_property_ref,
            'value_type_ref':p.value_type_ref,'data_type':p.logical_primitive_type,'unit_ref':p.unit_ref,
            'owner_ref':p.owner_ref,'availability':'bound',
            **({'temporal_encoding':p.physical.temporal_encoding.model_dump(mode='json')}
                if p.physical.temporal_encoding is not None else {})},availability='bound',
        physical=PhysicalProfileBinding(source=p.physical.source_id,table=p.physical.table,column=p.physical.column))
        for p in inputs.properties)
    # This names generic server capabilities, not a domain-specific query plan or
    # an assertion that every corresponding physical query is ready to execute.
    revision=_digest(capability)
    query=LoadedProfileEntry(entry_id='query:reviewed-capabilities',category='query',
        revision_id='query-capabilities:'+revision,revision_digest=revision,boi_id='query:reviewed-capabilities',
        visibility='private',evidence_resources=(),payload={'query_spec_id':'query:reviewed-capabilities',
            'logical_plan':{'supported_operators':capability['supported_operators'],'max_limit':maximum_rows}})
    by_mapping = {item.physical.mapping_ref: item for item in inputs.properties}
    shape_entries = []
    for derived in derived_shapes:
        shape = derived['result_shape_contract']
        obj = next(item for item in inputs.objects
                   if item.object_ref == shape['root_object_ref'])
        evidence = tuple(dict.fromkeys((
            *obj.evidence_span_refs,
            *(ref for mapping_ref in obj.logical_key_mapping_refs
              for ref in by_mapping[mapping_ref].evidence_span_refs),
        )))
        payload = {
            'query_spec_id': 'query:' + shape['contract_id'],
            'kind': 'ResultShapeContract',
            'depends_on': (shape['root_object_ref'], *shape['exact_grain']),
            'logical_plan': {
                'supported_operators': ['project', 'filter', 'order', 'limit'],
                'max_limit': maximum_rows,
                'depends_on': (shape['root_object_ref'], *shape['exact_grain']),
            },
            'result_shape_contract': shape,
            'derivation_receipt_digest': derived['receipt_digest'],
            'authority': 'reviewed_provisional',
        }
        shape_revision = _digest(payload)
        shape_entries.append(LoadedProfileEntry(
            entry_id=payload['query_spec_id'], category='query',
            revision_id='reviewed-query-shape:' + shape_revision,
            revision_digest=shape_revision, boi_id=payload['query_spec_id'],
            visibility='private', evidence_resources=evidence, payload=payload,
        ))
    bound={p.logical_property_ref for p in inputs.properties}
    unavailable=tuple(sorted(entry.entry_id for entry in domain
        if entry.payload.get('kind')=='PropertyDefinition' and entry.entry_id not in bound))
    body=dict(release_id=None,active_release_digest=None,qualification_receipt_id=None,
        reviewed_definition_authority=authority.model_dump(mode='json'),principal_id=authority.principal,purpose=authority.purpose,
        catalog_snapshot_digest=inputs.catalog_snapshot_digest,schema_digest=inputs.schema_snapshot_digest,
        capability_digest=revision,domain_profile_digest=_digest([e.model_dump(mode='json') for e in domain]),
        mapping_profile_digest=authority.mapping_input_digest,
        query_profile_digest=_digest([query.model_dump(mode='json'),
            *[entry.model_dump(mode='json') for entry in shape_entries]]),
        acl_projection_digest=_digest({'principal':authority.principal,'policy':authority.acl_policy_digest,
            'review':authority.interpretation_receipt_digest,'context':authority.input_context_digest}),
        retrieval_index_digest=_digest([e.model_dump(mode='json') for e in domain]),
        domain_entries=[e.model_dump(mode='json') for e in domain],mapping_entries=[e.model_dump(mode='json') for e in mappings],
        query_entries=[query.model_dump(mode='json'),
            *[entry.model_dump(mode='json') for entry in shape_entries]],
        excluded_revision_ids=[],non_profile_revision_ids=[],
        unavailable_logical_ids=unavailable,body_bytes_exposed_to_context=0)
    bundle=SemanticContextBundle.model_validate({**body,'bundle_digest':_digest(body)})
    return bundle,context
