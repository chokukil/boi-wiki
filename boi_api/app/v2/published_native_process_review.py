"""Official source-fidelity review for published recipient-owned typed definitions.

This adapter deliberately does not reuse candidate-lane authority or a published
use qualification.  The document and original source are separately re-read at
preparation and binding time.
"""
import copy
import json

from agent_kit.python.boi_process_claim_review import (
    SOURCE_LABEL_FAILURE_KINDS, SOURCE_REVIEW_INSTRUCTIONS_VERSION,
    source_review_delivery, source_review_prompt,
)
from agent_kit.python.boi_process_review_observation import observe_source_review
from agent_kit.python.boi_process_response_review import response_context_view

from ..governed_runtime.domain_asset_store import source_manifest_digest
from ..governed_runtime.knowledge_content import decode_knowledge_content
from ..governed_runtime.knowledge_published_read import PublishedKnowledgeReader
from ..governed_runtime.native_definition_context import (
    PublishedNativeDefinitionReview, PublishedNativeProcessReviewScope,
)
from ..governed_runtime.native_observation import NativeObservationInput, _json, read_native_observation
from ..governed_runtime.semantic_binding_contract import RevisionRef, semantic_digest
from ..governed_runtime.source_envelope import ArtifactEnvelope
from ..governed_runtime.typed_knowledge_meaning import TypedKnowledgeMeaning
from .process_review_binding import RequestSourceReader


REVIEW_CONTRACT_KIND = 'published_recipient_definition'


def _published_definition(intake, principal, revision):
    authorization, work = intake._work(principal)
    if getattr(work, 'knowledge_spaces', None) is None or not callable(
            getattr(work, 'current_knowledge_authorization', None)):
        raise ValueError('PUBLISHED_NATIVE_REVIEW_CURRENT_SPACE_REQUIRED')
    revision = RevisionRef.model_validate(revision)
    reader = PublishedKnowledgeReader(work.knowledge_spaces,
        current_authorization=work.current_knowledge_authorization)
    if not reader.is_published(revision):
        raise ValueError('PUBLISHED_NATIVE_REVIEW_PUBLISHED_DEFINITION_REQUIRED')
    _, _, content_model = reader._read(principal.employee_id, revision, 'model_input')
    stored = work.assets.read(authorization=authorization, revision=revision, lane='provisional')
    if (stored['asset']['kind'] != 'definition'
            or _json(stored['asset']['content_json']).get('contract_version') != 'boi/knowledge-content@1'):
        raise ValueError('PUBLISHED_NATIVE_REVIEW_TYPED_DEFINITION_REQUIRED')
    content = content_model.model_dump(mode='json')
    meaning = TypedKnowledgeMeaning.model_validate(content['meaning']).model_dump(mode='json')
    sources = [ArtifactEnvelope.model_validate(source) for source in stored['sources']]
    if not sources:
        raise ValueError('PUBLISHED_NATIVE_REVIEW_SOURCE_REQUIRED')
    return authorization, work, stored, content, meaning, sources


def is_published_native_process_review(intake, principal, revision):
    """Narrow dispatcher predicate; candidate failures are never swallowed."""
    try:
        _published_definition(intake, principal, revision)
    except ValueError as error:
        if str(error) in (
            'PUBLISHED_NATIVE_REVIEW_PUBLISHED_DEFINITION_REQUIRED',
            'PUBLISHED_NATIVE_REVIEW_TYPED_DEFINITION_REQUIRED',
        ):
            return False
        raise
    return True


def _typed_targets(meaning, roots):
    assertions = meaning['assertions']
    by_id = {node['id']: index for index, node in enumerate(assertions)}
    all_pointers = [f'/assertions/{index}' for index in range(len(assertions))]
    if roots is None:
        roots = all_pointers
    roots = list(roots)
    if not roots or len(roots) != len(set(roots)):
        raise ValueError('PUBLISHED_NATIVE_REVIEW_ROOTS_INVALID')
    for root in roots:
        parts = root.split('/')
        if len(parts) != 3 or parts[:2] != ['', 'assertions']:
            raise ValueError('PUBLISHED_NATIVE_REVIEW_ROOTS_INVALID')
        try:
            assertions[int(parts[2])]
        except (ValueError, IndexError):
            raise ValueError('PUBLISHED_NATIVE_REVIEW_ROOTS_INVALID') from None
    def closure_for(root):
        stack = [root]
        closure = []
        while stack:
            pointer = stack.pop()
            if pointer in closure:
                continue
            closure.append(pointer)
            current = assertions[int(pointer.rsplit('/', 1)[1])]
            for dependency in current['depends_on']:
                if dependency not in by_id:
                    raise ValueError('PUBLISHED_NATIVE_REVIEW_DEPENDENCY_UNAVAILABLE')
                stack.append(f'/assertions/{by_id[dependency]}')
        return closure
    closures = {pointer: closure_for(pointer) for pointer in all_pointers}
    selected = set()
    for root in roots:
        selected.update(closures[root])
    targets = [{'target_pointer': pointer, 'kind': 'published_typed_assertion',
                'value': copy.deepcopy(assertions[int(pointer.rsplit('/', 1)[1])])}
               for pointer in all_pointers]
    return roots, targets, closures, selected


def prepare_published_native_process_review(intake, principal, *, definition_revision,
        knowledge_reading_ref, target_pointers=None, field_locators=(), prior_review_revision=None,
        require_current=True):
    """Prepare a source-fidelity-only published typed-definition review.

    The approved document and every selected original evidence field are read
    through their current, independent authorization paths.  Field coverage is
    intentionally not part of the first contract version; neither is historical
    judgment reuse, which must not be silently treated as current review input.
    """
    if prior_review_revision is not None:
        raise ValueError('PUBLISHED_NATIVE_REVIEW_PRIOR_REVIEW_UNSUPPORTED')
    authorization, work, stored, content, meaning, sources = _published_definition(
        intake, principal, definition_revision)
    if field_locators:
        raise ValueError('PUBLISHED_NATIVE_REVIEW_FIELD_COVERAGE_UNSUPPORTED')
    context = work.contexts.validate_reading(
        authorization=authorization, revision=RevisionRef.model_validate(knowledge_reading_ref),
        sources=sources, require_current=require_current)
    revision = RevisionRef.model_validate(stored['revision']).model_dump(mode='json')
    if revision not in [asset.revision.model_dump(mode='json') for asset in context.assets]:
        raise ValueError('PUBLISHED_NATIVE_REVIEW_INPUT_NOT_READ')
    readings = RequestSourceReader(intake, principal).read_for_assets(
        intake, principal, sources, [revision])
    roots, native_targets, native_closures, selected = _typed_targets(meaning, target_pointers)
    scope = PublishedNativeProcessReviewScope(
        candidate_draft_digest=semantic_digest(meaning),
        source_revision_digest=sources[0].digest,
        published_revision=revision,
        typed_meaning_digest=semantic_digest(meaning),
        root_pointers=roots,
        target_pointers=[target['target_pointer'] for target in native_targets
                         if target['target_pointer'] in selected],
        field_locators=[],
    ).model_dump(mode='json')
    published_projection = {
        'published_revision': revision,
        'meaning_reference': '/draft',
        'meaning_digest': semantic_digest(meaning),
        'document_contract': 'boi/knowledge-content@1',
    }
    context_view = response_context_view(context.model_dump(mode='json'), source_readings=readings)
    for asset in context_view['assets']:
        if asset['revision'] == revision:
            asset['read_projection'] = published_projection
            asset['projection_digest'] = semantic_digest(published_projection)
    material = {
        'review_instructions_version': SOURCE_REVIEW_INSTRUCTIONS_VERSION,
        'review_output_contract': {'allowed_failure_kinds': SOURCE_LABEL_FAILURE_KINDS},
        'draft': copy.deepcopy(meaning),
        'targets': [copy.deepcopy(target) for target in native_targets
                    if target['target_pointer'] in selected],
        'all_current_nodes_for_field_coverage': [],
        'carried_node_judgments': [],
        'field_locators_to_assess': [],
        'review_scope': 'selected_nodes',
        'native_review_scope': scope,
        'native_meaning_dependencies': native_closures,
        'read_definitions_and_contracts': context_view,
        'original_fields_reference': '/read_definitions_and_contracts/source_readings/0/fields',
        'primary_source_revision': sources[0].digest,
        'scope': (
            'Selected published typed assertions and explicit depends_on closure only. '
            'The document and original fields are separately authorized current reads. '
            'This source-fidelity review grants no use qualification, semantic truth, '
            'business canon/currentness, independent assessment, or execution authority.'
        ),
    }
    material = source_review_delivery(material)
    prompt = source_review_prompt(material) + (
        '\nReturn PublishedNativeDefinitionReview@4 with the exact envelope below. '
        'Assess only selected typed assertion nodes against exact original source fields. '
        'Do not turn document publication, source readability, or a supported label into '
        'business truth, meaning approval, use qualification, or execution authority.\n'
        + json.dumps({'definition_revisions': [revision], 'scope': scope},
                     ensure_ascii=False, separators=(',', ':')))
    request = NativeObservationInput(
        prompt=prompt,
        output_schema_json=json.dumps(PublishedNativeDefinitionReview.model_json_schema(),
                                      ensure_ascii=False),
        source_manifest_digest=source_manifest_digest(sources),
        input_revisions=[revision],
        knowledge_reading_ref=knowledge_reading_ref,
        review_contract_version='boi/native-definition-review@4',
    )
    return {
        'review_contract_kind': REVIEW_CONTRACT_KIND,
        'definition_revision': revision,
        'scope': scope,
        'material': material,
        'request': request.model_dump(mode='json'),
        'selection': {
            'targets': [target for target in native_targets if target['target_pointer'] in selected],
            'fields': [],
            'carry_forward_nodes': [],
            'carry_forward_fields': [],
        },
        'sources': readings,
        'context': context.model_dump(mode='json'),
        'native_targets': native_targets,
        'native_closures': native_closures,
        'semantic_truth_proven': False,
        'mapping_quality_verified': False,
        'execution_authority_granted': False,
        'new_model_runs': 0,
        'new_review_receipts': 0,
        'whole_plan_qualified': False,
    }


def read_published_native_process_review_binding(intake, principal, review_revision, *,
        require_current=True):
    authorization, work = intake._work(principal)
    review_revision = RevisionRef.model_validate(review_revision)
    observation = read_native_observation(work, authorization, review_revision)
    review = PublishedNativeDefinitionReview.model_validate(observation['value'])
    prepared = prepare_published_native_process_review(
        intake, principal, definition_revision=review.definition_revisions[0],
        knowledge_reading_ref=observation['request']['knowledge_reading_ref'],
        target_pointers=review.scope.root_pointers,
        field_locators=review.scope.field_locators,
        require_current=require_current,
    )
    if observation['request'] != prepared['request'] or review.scope.model_dump(mode='json') != prepared['scope']:
        raise ValueError('PUBLISHED_NATIVE_REVIEW_EXACT_INPUT_MISMATCH')
    result = observe_source_review(
        review.source_assessment.model_dump(mode='json'),
        draft=prepared['material']['draft'],
        evidence=prepared['sources'][0],
        selection=prepared['selection'],
        reference_contract_version='boi/source-coverage-references@2',
        review_scope='selected_nodes',
        native_targets=prepared['native_targets'],
        native_closures=prepared['native_closures'],
    )
    check = result['check']
    return {
        'contract_version': 'boi/process-review-binding@1',
        'review_contract_kind': REVIEW_CONTRACT_KIND,
        'status': 'bound' if check['selected_assessment_complete'] else 'partially_bound',
        'candidate_revision': prepared['definition_revision'],
        'review_revision': review_revision.model_dump(mode='json'),
        'knowledge_reading_ref': prepared['request']['knowledge_reading_ref'],
        'source_review': check,
        'check': {'candidate_revision': prepared['definition_revision'],
                  'source_review': check, 'failed_use_pointers': []},
        'usable_node_pointers': check['usable_node_pointers'],
        'quarantined_node_pointers': check['quarantined_node_pointers'],
        'validated_assessment': result['validated_assessment'],
        'review': review.model_dump(mode='json'),
        'context': prepared['context'],
        'sources': prepared['sources'],
        'candidate_content': _json(work.assets.read(
            authorization=authorization, revision=RevisionRef.model_validate(
                prepared['definition_revision']), lane='provisional')['asset']['content_json']),
        'review_execution_binding': 'authenticated_native_observation_and_exact_published_inputs',
        'reviewer_relationship_observation': {
            'relationship': 'unknown',
            'author_session_ref': None,
            'reviewer_session_ref': observation['provenance']['agent_session_ref'],
            'reported_relationship': review.reviewer_relationship,
            'relationship_verified': False,
            'reason': 'No authenticated author-session link is present in the published definition contract.',
        },
        'native_observation_provenance': [observation['provenance']],
        'carried_review_limits': None,
        'semantic_truth_proven': False,
        'mapping_quality_verified': False,
        'execution_authority_granted': False,
        'new_model_runs': 0,
        'new_review_receipts': 0,
        'whole_plan_qualified': False,
    }
