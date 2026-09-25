"""Scoped candidate parameter references, independent of live equipment bindings.

Names and source paths are descriptive metadata. They never authorize a match
outside an explicitly supplied identity, revision, component and unit contract.
The caller must obtain catalog entries through the existing Wiki ACL/read path.
"""
from typing import Literal
from pydantic import Field,model_validator
from .semantic_binding_contract import FrozenContract, Ref, RevisionRef, SemanticDescriptor

SemanticRole = SemanticDescriptor.model_fields['role'].annotation


def native_svid_descriptor(value):
    """Read the existing typed descriptor from its native evidence-bearing node.

    The value/evidence shape is shared with native identities and meanings. It
    allows the same source resolver to review this descriptor as a node, without
    copying its roles into names or discarding its unit/temporal contracts.
    Legacy direct descriptors remain readable; this function grants no review.
    """
    if value is None:return None
    if isinstance(value,dict) and 'value' in value:
        if set(value)!={'value','evidence'} or not value['evidence']:
            raise ValueError('SVID_DESCRIPTOR_EVIDENCE_NODE_INVALID')
        value=value['value']
    return SemanticDescriptor.model_validate(value)


def native_svid_limitations(value):
    """Retain grounded limitation nodes alongside the v1 display projection.

    Structured limitations use the existing native evidence shape. Validation
    here checks representation, not source support; the definition review still
    controls admission and returns the complete original definition_content.
    """
    if not isinstance(value,list):raise ValueError('SVID_NATIVE_LIMITATIONS_INVALID')
    labels=[]
    for item in value:
        if isinstance(item,str) and item.strip():labels.append(item)
        elif (isinstance(item,dict) and isinstance(item.get('text'),str) and item['text'].strip()
                and item.get('evidence')):labels.append(item['text'])
        else:raise ValueError('SVID_NATIVE_LIMITATIONS_INVALID')
    return labels


class SvidIdentity(FrozenContract):
    namespace: Ref
    model: Ref
    svid: str = Field(strict=True, min_length=1, pattern=r'\S')


class KnowledgeParameterIdentity(FrozenContract):
    """A parameter definition inside one stable Wiki knowledge object.

    This reference does not fabricate a model/SVID for other domain Profiles.
    Current knowledge access and calculation qualification belong to the
    authenticated resolver, not to this compiler input contract.
    """
    knowledge_id: Ref
    parameter_id: Ref


class ParameterSelection(FrozenContract):
    identity: SvidIdentity | KnowledgeParameterIdentity
    revision: RevisionRef
    component: Ref
    quantity: Ref
    unit: Ref
    semantic_role: SemanticRole | None = Field(default=None,exclude_if=lambda v:v is None)


class CandidateParameter(ParameterSelection):
    parameter_name: Ref
    source_locator: Ref | None = None
    binding_status: Literal['unverified', 'unavailable'] = 'unverified'
    semantic_descriptor: SemanticDescriptor | None = Field(default=None,exclude_if=lambda v:v is None)

    @model_validator(mode='after')
    def consistent_declared_role(self):
        if self.semantic_role is not None:
            if self.semantic_descriptor is None:raise ValueError('SVID_PARAMETER_SEMANTICS_UNRESOLVED')
            if self.semantic_role!=self.semantic_descriptor.role:raise ValueError('SVID_PARAMETER_ROLE_CONFLICT')
        return self


def resolve_parameter(catalog, selection):
    """Resolve explicit typed scope; this is neither semantic search nor ACL.

    Unit conversion belongs to the separately pinned Formula unit contract.
    No fallback by name, nearest revision, unit synonym or source path is used.
    Candidate metadata cannot self-attest a live connection.
    """
    requested = ParameterSelection.model_validate(selection)
    records = [CandidateParameter.model_validate(item) for item in catalog]
    identity_matches = [r for r in records
                        if r.identity == requested.identity and r.revision == requested.revision]
    if len(identity_matches) > 1:
        raise ValueError('SVID_PARAMETER_AMBIGUOUS')
    selected = [r for r in identity_matches if r.component == requested.component
                and r.quantity == requested.quantity and r.unit == requested.unit]
    if not selected:
        raise ValueError('SVID_PARAMETER_NOT_FOUND')
    descriptor=selected[0].semantic_descriptor
    if requested.semantic_role is not None:
        if descriptor is None:raise ValueError('SVID_PARAMETER_SEMANTICS_UNRESOLVED')
        if descriptor.role!=requested.semantic_role:raise ValueError('SVID_PARAMETER_ROLE_MISMATCH')
    return {'contract_version': 'boi/svid-parameter-resolution@1',
            'status': 'candidate_bound', 'parameter': selected[0].model_dump(mode='json'),
            'semantic_role_checked':requested.semantic_role is not None,
            'live_execution_ready': False, 'canonical_projection_eligible': False}


def read_native_svid_parameter(work, authorization, *, review_revision, selection, require_current=True):
    """Consume an exact source definition through existing current Wiki review.

    This projects the declared native interpretation schema. It neither infers
    meaning from parameter names nor grants live binding or control authority.
    """
    from .native_definition_context import read_native_definition_authority
    from .native_observation import _json
    selected = ParameterSelection.model_validate(selection)
    if not isinstance(selected.identity,SvidIdentity):
        raise ValueError('SVID_NATIVE_IDENTITY_REQUIRED')
    authority, context = read_native_definition_authority(work, authorization, review_revision,
        require_current=require_current, definition_use={'revision':selected.revision,
            'target_pointers':('/identity/model','/identity/svid','/parameter','/observation','/location'),
            'optional_target_pointers':('/semantic_descriptor',)})
    if selected.revision not in authority.definition_revisions:
        raise ValueError('SVID_DEFINITION_NOT_REVIEWED')
    asset = next(a for a in context.assets if a.revision == selected.revision)
    value = _json(asset.content_json)
    if not isinstance(value, dict) or value.get('contract_version') != 'boi/svid-native-interpretation@1':
        raise ValueError('SVID_NATIVE_DEFINITION_CONTRACT_REQUIRED')
    try:
        if (value['canonical_projection_eligible'] is not False
            or value['location']['live_binding_verified'] is not False
            or value['binding']['live_execution_ready'] is not False):
            raise ValueError('SVID_NATIVE_LIVE_AUTHORITY_FORBIDDEN')
        identity = value['identity']
        observation = value['observation']
        descriptor = native_svid_descriptor(value.get('semantic_descriptor'))
        parameter = CandidateParameter(identity={
                'namespace': identity['namespace'], 'model': identity['model']['value'],
                'svid': identity['svid']['value']},
            revision=asset.revision, component=observation['component'],
            quantity=observation['quantity'], unit=(descriptor.unit_ref if descriptor is not None
                and descriptor.unit_semantics == 'declared' else observation['unit_label']),
            parameter_name=value['parameter']['name'],
            source_locator=value['location']['source_locator'],
            semantic_descriptor=descriptor,
            semantic_role=descriptor.role if descriptor is not None else None,
            binding_status=value['binding']['status'])
        limitations = native_svid_limitations(value['limitations'])
    except (KeyError, TypeError) as error:
        raise ValueError('SVID_NATIVE_DEFINITION_PAYLOAD_INVALID') from error
    result = resolve_parameter((parameter,), selected)
    quantity_resolution = None
    if descriptor is not None and descriptor.quantity_kind_ref and '#/concepts/' in descriptor.quantity_kind_ref:
        from .common_knowledge_contract import quantity_concept_reference, resolve_quantity_concept
        revision, _ = quantity_concept_reference(descriptor.quantity_kind_ref)
        if not any(d.revision == revision and d.role == 'semantic_quantity_definition' and d.required
                   and {'review', 'explain', 'execute'} <= set(d.stages) for d in asset.dependencies):
            raise ValueError('SVID_QUANTITY_REQUIRED_DEPENDENCY_MISSING')
        matches = [a for a in context.assets if a.revision == revision and a.kind == 'definition']
        if len(matches) != 1:
            raise ValueError('SVID_QUANTITY_DEFINITION_NOT_IN_CONTEXT')
        quantity_resolution = resolve_quantity_concept(_json(matches[0].content_json), revision, descriptor.quantity_kind_ref)
    # Return the exact authorized interpretation alongside its typed projection.
    # A v2 review qualifies only the selected execution fields and their owned
    # dependencies recorded on authority, never all of definition_content.
    # Procedure, disputed claims, unknown numeric roles and future extensions are
    # evidence for the answer/planner, not additional executable constraints.
    # Only the explicitly typed projection above participates in resolution.
    return {**result, 'definition_content': value,
        **({'quantity_definition_resolution': quantity_resolution} if quantity_resolution is not None else {}),
        'reviewed_definition_authority': authority.model_dump(mode='json'),
        'definition_context_digest': authority.definition_context_digest,
        'namespace_basis': identity.get('namespace_basis'), 'limitations': limitations}
