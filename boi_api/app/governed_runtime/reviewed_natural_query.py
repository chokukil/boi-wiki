"""Apply reviewed source qualifiers to a common semantic plan.

The common planner owns user intent. This module adds only already reviewed,
evidence-bound source conditions and records the exact augmentation. It never
creates a semantic qualifier from prose or grants Gateway access.
"""
from dataclasses import dataclass

from .semantic_binding_contract import semantic_digest
from .semantic_qualifier import compile_reviewed_qualifiers
from .multi_result_query_gateway import (
    AuthorizedPhysicalMapping,
    MultiResultFilter,
    MultiResultParameterSpec,
    MultiResultSetPlan,
)


@dataclass(frozen=True)
class ReviewedQualifierApplication:
    result_sets: tuple[MultiResultSetPlan, ...]
    physical_mappings: tuple[AuthorizedPhysicalMapping, ...]
    parameter_specs: tuple[MultiResultParameterSpec, ...]
    parameters: dict
    qualifier_resolution: dict
    receipt: dict


def _deduplicate_compiled_filters(*, filters, specs, parameters, object_index,
        existing_filters=(), existing_specs=(), existing_parameters=None):
    """Collapse only byte-equivalent AND predicates; retain an audit entry for each."""
    specs_by_name = {item.name: item for item in specs}
    if len(specs_by_name) != len(specs) or set(parameters) != set(specs_by_name):
        raise ValueError('REVIEWED_QUALIFIER_PARAMETER_CLOSURE_INVALID')
    existing_specs_by_name = {item.name: item for item in existing_specs}
    if len(existing_specs_by_name) != len(existing_specs):
        raise ValueError('REVIEWED_QUALIFIER_PARAMETER_CLOSURE_INVALID')
    existing_parameters = existing_parameters or {}
    applied_filters = []
    applied_specs = []
    applied_parameters = {}
    applications = []
    seen = {}
    used_names = set()
    for user_index, item in enumerate(existing_filters):
        name = item.parameter_name
        if name is None:
            parameter_type = None
            value = None
        else:
            spec = existing_specs_by_name.get(name)
            if spec is None or name not in existing_parameters:
                raise ValueError('REVIEWED_QUALIFIER_PARAMETER_CLOSURE_INVALID')
            parameter_type = spec.type
            value = existing_parameters[name]
        signature = semantic_digest({
            'mapping_ref': item.mapping_ref,
            'operator': item.operator,
            'parameter_type': parameter_type,
            'value': value,
        })
        seen.setdefault(signature, {
            'kind': 'USER_FILTER',
            'user_filter_index': user_index,
            'source_filter_index': None,
            'applied_parameter_name': name,
        })
    for source_index, item in enumerate(filters):
        source_name = item.parameter_name
        if source_name is None:
            parameter_type = None
            value = None
        else:
            spec = specs_by_name.get(source_name)
            if spec is None or source_name not in parameters:
                raise ValueError('REVIEWED_QUALIFIER_PARAMETER_CLOSURE_INVALID')
            used_names.add(source_name)
            parameter_type = spec.type
            value = parameters[source_name]
        signature = semantic_digest({
            'mapping_ref': item.mapping_ref,
            'operator': item.operator,
            'parameter_type': parameter_type,
            'value': value,
        })
        duplicate = seen.get(signature)
        if duplicate is not None:
            applications.append({
                'source_filter_index': source_index,
                'execution_signature': signature,
                'status': (
                    'IDEMPOTENT_WITH_USER_FILTER'
                    if duplicate['kind'] == 'USER_FILTER'
                    else 'IDEMPOTENT_DUPLICATE'
                ),
                'duplicate_of_source_filter_index': duplicate['source_filter_index'],
                'duplicate_of_user_filter_index': duplicate.get('user_filter_index'),
                'applied_parameter_name': duplicate['applied_parameter_name'],
            })
            continue
        applied_name = None
        if source_name is not None:
            applied_name = (
                f"source_qualifier_{object_index}_{len(applied_specs)}"
            )
            applied_specs.append(MultiResultParameterSpec(
                name=applied_name, type=parameter_type
            ))
            applied_parameters[applied_name] = value
        applied_filters.append(MultiResultFilter(
            mapping_ref=item.mapping_ref,
            operator=item.operator,
            parameter_name=applied_name,
        ))
        seen[signature] = {
            'kind': 'SOURCE_FILTER',
            'source_filter_index': source_index,
            'user_filter_index': None,
            'applied_parameter_name': applied_name,
        }
        applications.append({
            'source_filter_index': source_index,
            'execution_signature': signature,
            'status': 'APPLIED',
            'duplicate_of_source_filter_index': None,
            'duplicate_of_user_filter_index': None,
            'applied_parameter_name': applied_name,
        })
    if used_names != set(specs_by_name):
        raise ValueError('REVIEWED_QUALIFIER_PARAMETER_CLOSURE_INVALID')
    return (
        tuple(applied_filters), tuple(applied_specs), applied_parameters,
        applications,
    )


def apply_reviewed_query_qualifiers(*, scope, planned):
    if planned.status != 'READY' or planned.semantic_plan is None or planned.physical_binding is None:
        raise ValueError('REVIEWED_QUALIFIER_PLAN_REQUIRED')
    semantic_plan = planned.semantic_plan
    physical = planned.physical_binding
    domains = {
        entry.entry_id: entry.payload
        for entry in planned.planning_context.bundle.domain_entries
    }
    property_refs_by_object = {}
    for result_set in semantic_plan.result_sets:
        refs = property_refs_by_object.setdefault(result_set.object_ref, [])
        refs.extend(item.property_ref for item in result_set.projections)
        refs.extend(item.property_ref for item in result_set.filters)
        refs.extend(item.target_ref for item in result_set.aggregations)
        refs.extend(result_set.exact_grain)
        refs.extend(result_set.ordering)
        if result_set.latest is not None:
            refs.extend(result_set.latest.partition_by)
            refs.extend(result_set.latest.ordering)

    filters_by_object = {}
    base_specs = tuple(MultiResultParameterSpec(name=item.name, type=item.type)
                       for item in semantic_plan.parameter_specs)
    base_parameters = dict(planned.parameters)
    specs = list(base_specs)
    parameters = dict(base_parameters)
    mappings = {item.mapping_ref: item for item in physical.physical_mappings}
    resolutions = []
    definition_revisions = {}
    qualified_clauses = []
    for object_index, object_ref in enumerate(sorted(property_refs_by_object)):
        refs = tuple(dict.fromkeys(
            ref for ref in property_refs_by_object[object_ref]
            if domains.get(ref, {}).get('kind') == 'PropertyDefinition'
        ))
        filters, local_specs, local_parameters, local_mappings, resolution = (
            compile_reviewed_qualifiers(
                domain=scope.domain,
                index=scope.index,
                inputs=scope.inputs,
                root_object_ref=object_ref,
                property_refs=refs,
            )
        )
        (bound_filters, bound_specs, bound_parameters,
         filter_applications) = _deduplicate_compiled_filters(
            filters=filters, specs=local_specs,
            parameters=local_parameters, object_index=object_index,
            existing_filters=tuple(
                item
                for result_set in physical.result_sets
                if result_set.role != 'RELATIONSHIP'
                and result_set.object_ref == object_ref
                for item in result_set.filters
            ),
            existing_specs=base_specs,
            existing_parameters=base_parameters,
        )
        filters_by_object[object_ref] = bound_filters
        specs.extend(bound_specs)
        if set(parameters) & set(bound_parameters):
            raise ValueError('REVIEWED_QUALIFIER_PARAMETER_NAME_CONFLICT')
        parameters.update(bound_parameters)
        for item in local_mappings:
            previous = mappings.get(item.mapping_ref)
            if previous is not None and previous != item:
                raise ValueError('REVIEWED_QUALIFIER_PHYSICAL_MAPPING_CONFLICT')
            mappings[item.mapping_ref] = item
        for item in resolution['definition_revisions']:
            previous = definition_revisions.get(item['ref'])
            if previous is not None and previous != item:
                raise ValueError('REVIEWED_QUALIFIER_DEFINITION_REVISION_CONFLICT')
            definition_revisions[item['ref']] = item
        qualified_clauses.extend(resolution['qualified_clauses'])
        resolutions.append({
            'object_ref': object_ref,
            'property_refs': list(refs),
            'source_resolution_receipt_digest': resolution['receipt_digest'],
            'filter_count': len(bound_filters),
            'source_filter_count': len(filters),
            'deduplicated_filter_count': len(filters) - len(bound_filters),
            'parameter_names': [item.name for item in bound_specs],
            'filter_applications': filter_applications,
        })

    final_sets = tuple(result_set.model_copy(update={
        'filters': (
            *result_set.filters,
            *filters_by_object.get(result_set.object_ref, ()),
        )
    }) if result_set.role != 'RELATIONSHIP' else result_set
        for result_set in physical.result_sets)
    qualifier_body = {
        'contract_version': 'boi/reviewed-natural-query-qualifiers@1',
        'definition_revisions': [definition_revisions[key]
                                 for key in sorted(definition_revisions)],
        'qualified_clauses': qualified_clauses,
        'object_applications': resolutions,
        'semantic_validated': False,
        'canonical': False,
    }
    qualifier_resolution = {
        **qualifier_body, 'receipt_digest': semantic_digest(qualifier_body)
    }
    receipt_body = {
        'contract_version': 'boi/reviewed-qualifier-plan-application@1',
        'base_physical_binding_digest': physical.binding_digest,
        'qualifier_resolution_digest': qualifier_resolution['receipt_digest'],
        'result_sets': [item.model_dump(mode='json') for item in final_sets],
        'physical_mappings': [item.model_dump(mode='json')
                              for item in mappings.values()],
        'parameter_specs': [item.model_dump(mode='json') for item in specs],
        'parameters': parameters,
        'user_filter_count': sum(len(item.filters) for item in physical.result_sets),
        'source_qualifier_filter_count': sum(len(value) for value in filters_by_object.values()),
        'source_qualifier_predicate_count': sum(
            item['source_filter_count'] for item in resolutions
        ),
        'deduplicated_source_qualifier_filter_count': sum(
            item['deduplicated_filter_count'] for item in resolutions
        ),
        'status': 'PASS',
        'production_changed': False,
        'active_transition': False,
    }
    receipt = {**receipt_body, 'receipt_digest': semantic_digest(receipt_body)}
    return ReviewedQualifierApplication(
        result_sets=final_sets,
        physical_mappings=tuple(mappings.values()),
        parameter_specs=tuple(specs),
        parameters=parameters,
        qualifier_resolution=qualifier_resolution,
        receipt=receipt,
    )


__all__ = ['ReviewedQualifierApplication', 'apply_reviewed_query_qualifiers']
