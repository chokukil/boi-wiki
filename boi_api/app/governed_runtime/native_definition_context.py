"""Read native definition reviews through existing Wiki source/asset authorization.

No inference, bulk migration run, synthetic approval, or execution grant is made.
An enclosing application must re-read this binding at planning/execution fences.
"""
from typing import Literal
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, RevisionRef, Ref, Digest, semantic_digest
from .semantic_authority import NativeReviewedDefinitionAuthority, NativeProcessReviewAuthority
from .native_observation import read_native_observation, _json
from .domain_asset_store import DomainAssetStore
from .source_envelope import ArtifactEnvelope
from agent_kit.python.boi_process_claim_review import ProcessSourceReview


class NativeDefinitionReview(FrozenContract):
    contract_version: Literal['boi/native-definition-review@1'] = 'boi/native-definition-review@1'
    definition_revisions: tuple[RevisionRef, ...] = Field(min_length=1)
    disposition: Literal['supported_with_limits', 'not_supported', 'unknown']
    findings: tuple[Ref, ...] = Field(min_length=1)
    limitations: tuple[Ref, ...] = Field(min_length=1)
    reviewer_relationship: Literal['same_session'] = 'same_session'
    semantic_truth_proven: Literal[False] = False
    mapping_quality_verified: Literal[False] = False
    execution_authority_granted: Literal[False] = False

    @model_validator(mode='after')
    def exact_definitions(self):
        if len(set(self.definition_revisions)) != len(self.definition_revisions):
            raise ValueError('NATIVE_DEFINITION_REVIEW_DUPLICATE_REVISION')
        return self


class NativeProcessReviewScope(FrozenContract):
    candidate_draft_digest:Digest
    source_revision_digest:Digest
    root_pointers:tuple[Ref,...]
    target_pointers:tuple[Ref,...]
    field_locators:tuple[str,...]=()
    prior_review_revision:RevisionRef|None=None


class NativeDefinitionReviewV2(NativeDefinitionReview):
    """One exact process/native candidate and node scope; never whole approval."""
    contract_version:Literal['boi/native-definition-review@2']='boi/native-definition-review@2'
    definition_revisions:tuple[RevisionRef,...]=Field(min_length=1,max_length=1)
    scope:NativeProcessReviewScope
    source_assessment:ProcessSourceReview
    # A model cannot know a provider session allocated after dispatch. Execution
    # provenance belongs to the outer NativeObservation, never invented here.
    reviewer_relationship:Literal['unknown','same_session','independent']='unknown'
    reviewer_relationship_verified:Literal[False]=False


class NativeMultiSourceReviewScope(NativeProcessReviewScope):
    """All ordered source revisions; quote addresses resolve in the read context."""
    source_revision_digests:tuple[Digest,...]=Field(min_length=2)
    field_locator_contract:Literal['boi/source-reading-field-pointer@1']='boi/source-reading-field-pointer@1'

    @model_validator(mode='after')
    def exact_primary_source(self):
        if self.source_revision_digest!=self.source_revision_digests[0]:
            raise ValueError('NATIVE_REVIEW_PRIMARY_SOURCE_MISMATCH')
        return self


class NativeDefinitionReviewV3(NativeDefinitionReviewV2):
    """Multiple original sources without changing historical V2 input schemas."""
    contract_version:Literal['boi/native-definition-review@3']='boi/native-definition-review@3'
    scope:NativeMultiSourceReviewScope


class PublishedNativeProcessReviewScope(NativeProcessReviewScope):
    """A selected typed-meaning review of an already published definition.

    Publication is independently checked at both preparation and binding; this
    scope is intentionally not a candidate-lane alias or a use qualification.
    """
    published_revision:RevisionRef
    typed_meaning_digest:Digest

    @model_validator(mode='after')
    def exact_published_revision(self):
        if self.typed_meaning_digest != self.candidate_draft_digest:
            raise ValueError('PUBLISHED_NATIVE_REVIEW_SCOPE_DIGEST_MISMATCH')
        return self


class PublishedNativeDefinitionReview(NativeDefinitionReview):
    """Source-fidelity opinion for published typed assertions, never whole approval."""
    contract_version:Literal['boi/native-definition-review@4']='boi/native-definition-review@4'
    definition_revisions:tuple[RevisionRef,...]=Field(min_length=1,max_length=1)
    scope:PublishedNativeProcessReviewScope
    source_assessment:ProcessSourceReview
    reviewer_relationship:Literal['unknown','same_session','independent']='unknown'
    reviewer_relationship_verified:Literal[False]=False


def scoped_native_review_model(contract_version):
    models={'boi/native-definition-review@2':NativeDefinitionReviewV2,
        'boi/native-definition-review@3':NativeDefinitionReviewV3,
        'boi/native-definition-review@4':PublishedNativeDefinitionReview}
    if contract_version not in models:
        raise ValueError('NATIVE_SCOPED_REVIEW_CONTRACT_REQUIRED')
    return models[contract_version]


def read_native_definition_authority(work, authorization, review_revision, *, require_current=True,
        process_semantic_basis=None, definition_use=None, _source_only_saved_answer=False):
    from ..v2.native_formula_timing import timed_call
    review_revision = RevisionRef.model_validate(review_revision)
    # Existing process source-review packs have their own validated envelope.
    # Recognize that contract before asking the native-observation parser to
    # read it; both paths still require the actual selected semantic basis.
    from ..v2.asset_user_views import process_review_target
    assets=getattr(work,'assets',None) or DomainAssetStore(work.intake)
    stored_review = timed_call('definition_review_asset_read', assets.read, authorization=authorization,
        revision=review_revision, lane='provisional')
    existing_process = (stored_review['asset']['kind']=='pack' and
        process_review_target(_json(stored_review['asset']['content_json'])) is not None)
    pending = None
    if not existing_process and not _source_only_saved_answer:
        envelope=_json(stored_review['asset']['content_json'])
        # This discriminator is only a structural dispatch. Exact observation
        # and definition validation both finish before authority is returned.
        if (isinstance(envelope,dict)
                and envelope.get('contract_version')=='boi/native-agent-observation@1'
                and isinstance(envelope.get('value_json'),str)):
            try:
                value=_json(envelope['value_json'])
            except ValueError:
                # Invalid values keep the public observation reader's late
                # context/output failure ordering, including duplicate keys.
                value=None
            if isinstance(value,dict) and value.get('contract_version')=='boi/native-definition-review@1':
                from .native_observation import _prepare_native_observation
                pending=timed_call('definition_observation_prepare',_prepare_native_observation,
                    work,authorization,review_revision)
    if pending is not None:
        stored = timed_call('definition_review_asset_read', assets.read, authorization=authorization,
            revision=review_revision, lane='provisional')
        if stored!=pending.stored:
            raise ValueError('NATIVE_DEFINITION_REVIEW_CHANGED_DURING_READ')
        # Keep the late source/ACL/content/head validation. Its single result
        # satisfies both consumers; no earlier context or cross-request cache
        # replaces this fence. Complete schema validation before parsing the
        # definition value so private invalid fields retain safe error codes.
        context = timed_call('definition_context_validation', work.contexts.validate_reading,
            authorization=authorization, revision=pending.record.request.knowledge_reading_ref,
            sources=pending.sources, require_current=require_current)
        from .native_observation import _complete_native_observation
        observation=timed_call('definition_observation_complete',_complete_native_observation,
            pending,authorization,context)
    else:
        observation = None if existing_process else timed_call('definition_observation_read',
            read_native_observation, work, authorization, review_revision)
    if existing_process or observation['value'].get('contract_version') in (
            'boi/native-definition-review@2','boi/native-definition-review@3'):
        # Other definition consumers cannot silently treat a partial process
        # review as whole-definition approval. Source answers provide their
        # actual selected semantic basis, including an empty source-only basis.
        if process_semantic_basis is None and definition_use is None:
            raise ValueError('NATIVE_PROCESS_ANSWER_SCOPE_REQUIRED')
        if definition_use is not None and (process_semantic_basis is not None or _source_only_saved_answer):
            raise ValueError('NATIVE_DEFINITION_USE_SCOPE_AMBIGUOUS')
        from ..v2.native_process_review import (read_native_process_review_for_work,
            check_native_process_semantic_basis,native_process_review_authority)
        binding=read_native_process_review_for_work(work,authorization,review_revision,
            require_current=require_current and not _source_only_saved_answer)
        selected=None
        if definition_use is not None:
            selected=check_native_definition_use(binding,definition_use)
        else:
            check_native_process_semantic_basis(process_semantic_basis,binding)
        if require_current and _source_only_saved_answer:
            work.contexts.validate_reading(authorization=authorization,
                revision=RevisionRef.model_validate(binding['knowledge_reading_ref']),
                sources=tuple(ArtifactEnvelope.model_validate(s['source']) for s in binding['sources']),
                _source_only_saved_answer=True)
        authority,context=native_process_review_authority(binding,authorization)
        if selected is not None:
            authority=authority.model_copy(update=selected)
        return authority,context
    request = observation['request']
    review = NativeDefinitionReview.model_validate(observation['value'])
    if (request['review_contract_version'] != review.contract_version
            or semantic_digest(_json(request['output_schema_json']))
            != semantic_digest(NativeDefinitionReview.model_json_schema())):
        raise ValueError('NATIVE_DEFINITION_REVIEW_CONTRACT_MISMATCH')
    if review.disposition != 'supported_with_limits':
        raise ValueError('NATIVE_DEFINITION_REVIEW_NOT_SUPPORTED')
    if tuple(RevisionRef.model_validate(x) for x in request['input_revisions']) != review.definition_revisions:
        raise ValueError('NATIVE_DEFINITION_REVIEW_INPUT_MISMATCH')
    reading_ref = RevisionRef.model_validate(request['knowledge_reading_ref'])
    if pending is None:
        stored = timed_call('definition_review_asset_read', assets.read, authorization=authorization,
            revision=review_revision, lane='provisional')
        sources = tuple(ArtifactEnvelope.model_validate(x) for x in stored['sources'])
        context = timed_call('definition_context_validation', work.contexts.validate_reading, authorization=authorization,
            revision=reading_ref, sources=sources, require_current=require_current,
            **({'_source_only_saved_answer':True} if _source_only_saved_answer else {}))
    assets = {x.revision: x for x in context.assets}
    if any(ref not in assets or assets[ref].kind != 'definition'
            or assets[ref].authority != 'candidate' for ref in review.definition_revisions):
        raise ValueError('NATIVE_DEFINITION_REVIEW_KIND_OR_SCOPE_MISMATCH')
    authority = NativeReviewedDefinitionAuthority(principal=authorization.principal,
        purpose=context.purpose, definition_revisions=review.definition_revisions,
        review_revision=review_revision, knowledge_reading_ref=reading_ref,
        definition_context_digest=context.context_digest,
        source_manifest_digest=context.source_manifest_digest,
        acl_policy_digest=authorization.policy_digest)
    return authority, context


def check_native_definition_use(binding,use):
    """Apply the existing source/closure review to fields a typed consumer uses.

    Callers declare structural fields, never a question-specific interpretation.
    Optional roots are optional only when absent from the stored definition; a
    present but ungrounded or quarantined executable meaning cannot be skipped.
    """
    from agent_kit.python.boi_process_answer_v2 import meaning_citation_targets
    from ..v2.native_process_review import check_native_process_answer
    if RevisionRef.model_validate(use['revision']).model_dump(mode='json')!=binding['candidate_revision']:
        raise ValueError('NATIVE_DEFINITION_USE_REVISION_MISMATCH')
    pointers=list(use['target_pointers'])
    if not pointers or len(pointers)!=len(set(pointers)):
        raise ValueError('NATIVE_DEFINITION_USE_TARGETS_REQUIRED')
    for pointer in use.get('optional_target_pointers',()):
        value=binding['candidate_content']
        try:
            for part in pointer.removeprefix('/').split('/'):
                key=part.replace('~1','/').replace('~0','~')
                value=value[int(key)] if isinstance(value,list) else value[key]
        except (KeyError,IndexError):
            continue
        if value is not None and pointer not in pointers:pointers.append(pointer)
    targets=meaning_citation_targets(context=binding['context'],sources=binding['sources'],
        asset_revision=binding['candidate_revision'],target_pointers=pointers)
    if any(target['binding_status']!='bound' for target in targets):
        raise ValueError('NATIVE_DEFINITION_USE_EVIDENCE_UNRESOLVED')
    # Same resolver and dependency gate as authored answers. No empty-basis
    # escape, whole-revision approval or inferred qualifier inheritance.
    check_native_process_answer({'answers':[{'sentences':[{'citations':[
        {'kind':'meaning',**target} for target in targets]}]}]},binding)
    dependencies=tuple(dict.fromkeys(node['target_pointer'] for target in targets
        for node in target['graph_evidence']))
    return {'selected_target_pointers':tuple(pointers),'dependency_target_pointers':dependencies}
