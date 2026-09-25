"""Authenticated native-agent opinions in the existing candidate asset ledger.

This is a product evidence format, not an inference runner or signing service.
Wiki can verify authorship under the current principal, exact inputs and output
integrity. It cannot attest the supplied session identity or model computation.
Consumers must still reconstruct and check their complete review material.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from jsonschema import Draft202012Validator, ValidationError, SchemaError
from pydantic import Field

from .semantic_binding_contract import FrozenContract, Ref, Digest, RevisionRef
from .domain_asset_store import DomainAssetStore, source_manifest_digest
from .source_envelope import ArtifactEnvelope, byte_digest


class NativeObservationInput(FrozenContract):
    prompt: Ref
    output_schema_json: Ref
    source_manifest_digest: Digest
    input_revisions: tuple[RevisionRef, ...] = Field(min_length=1)
    knowledge_reading_ref: RevisionRef
    review_contract_version: Ref


class NativeObservation(FrozenContract):
    contract_version: Literal['boi/native-agent-observation@1']='boi/native-agent-observation@1'
    agent_session_ref: Ref
    request: NativeObservationInput
    value_json: Ref
    execution_attested: Literal[False]=False


class NativeFailureObservation(NativeObservation):
    contract_version: Literal['boi/native-agent-failure@1']='boi/native-agent-failure@1'
    failure_kind: Literal['unexpected_tool_use']
    exit_code: Literal[0]
    events_json: Ref


def _json(raw):
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('NATIVE_OBSERVATION_DUPLICATE_JSON_KEY')
            value[key]=item
        return value
    def constant(_):raise ValueError('NATIVE_OBSERVATION_NONFINITE_JSON')
    return json.loads(raw,object_pairs_hook=unique,parse_constant=constant)


def _validate_output(schema_json, value_json, failure):
    """Pure byte-bound validation; never an authorization or review verdict."""
    schema = _json(schema_json)
    def local_refs(node):
        if isinstance(node, dict):
            for key, item in node.items():
                if key in ('$ref', '$dynamicRef') and (not isinstance(item, str) or not item.startswith('#')):
                    raise ValueError('NATIVE_OBSERVATION_EXTERNAL_SCHEMA_REFERENCE')
                local_refs(item)
        elif isinstance(node, list):
            for item in node:local_refs(item)
    local_refs(schema)
    value = _json(value_json)
    try:
        Draft202012Validator.check_schema(schema)
        if not failure:Draft202012Validator(schema).validate(value)
    except (ValidationError, SchemaError):
        raise ValueError('NATIVE_OBSERVATION_OUTPUT_SCHEMA_INVALID') from None


# Keep only successful validation of the exact schema/output strings and mode.
# The process lifetime binds parser code. No mutable output, ACL, context or
# source validity is cached; all those checks still run at every call below.
_cached_validate_output = lru_cache(maxsize=32)(_validate_output)


def _check_output(schema_json, value_json, failure):
    # At most 8 MiB of UTF-8 keys across 32 entries; oversized inputs retain the
    # uncached path rather than changing the accepted observation contract.
    size = len(schema_json.encode('utf-8')) + len(value_json.encode('utf-8'))
    validate = _cached_validate_output if size <= 256 * 1024 else _validate_output
    validate(schema_json, value_json, failure)


@dataclass(frozen=True)
class _PendingNativeObservation:
    """Parsed input only; this object carries no validated context authority."""
    revision: RevisionRef
    stored: dict
    record: NativeObservation
    sources: tuple[ArtifactEnvelope, ...]
    failure: bool


def _prepare_native_observation(work, authorization, revision, *, failure=False):
    """Read exact authenticated bytes; context-dependent checks remain pending."""
    from ..v2.native_formula_timing import timed_call
    revision=RevisionRef.model_validate(revision)
    assets=getattr(work,'assets',None) or DomainAssetStore(work.intake)
    stored=timed_call('observation_asset_read', assets.read,
        authorization=authorization,revision=revision,lane='provisional')
    if stored['asset']['kind']!='pack':raise ValueError('NATIVE_OBSERVATION_PACK_REQUIRED')
    record=(NativeFailureObservation if failure else NativeObservation).model_validate(_json(stored['asset']['content_json']))
    request=record.request
    if stored['definition_reading_ref']!=request.knowledge_reading_ref.model_dump(mode='json'):
        raise ValueError('NATIVE_OBSERVATION_READING_MISMATCH')
    sources=tuple(ArtifactEnvelope.model_validate(s) for s in stored['sources'])
    if source_manifest_digest(sources)!=request.source_manifest_digest:
        raise ValueError('NATIVE_OBSERVATION_SOURCE_MISMATCH')
    return _PendingNativeObservation(revision,stored,record,sources,failure)


def _complete_native_observation(pending, authorization, context):
    """Finish both input/dependency and output checks on the server's context.

    Only internal readers call this after validate_reading. No caller supplied
    context or prevalidated flag is accepted by an API or MCP request.
    """
    from ..v2.native_formula_timing import timed_call
    revision,stored,record,failure=pending.revision,pending.stored,pending.record,pending.failure
    request=record.request
    if (context.principal_id!=authorization.principal or context.policy_digest!=authorization.policy_digest
            or context.source_manifest_digest!=request.source_manifest_digest):
        raise ValueError('NATIVE_OBSERVATION_CONTEXT_BINDING_MISMATCH')
    refs={a.revision for a in context.assets}
    dependencies={RevisionRef.model_validate(d['revision']) for d in stored['asset']['dependencies'] if d['required']}
    if len(set(request.input_revisions))!=len(request.input_revisions) or not set(request.input_revisions)<=refs & dependencies:
        raise ValueError('NATIVE_OBSERVATION_INPUT_REVISION_NOT_READ_OR_DEPENDENT')
    timed_call('observation_output_validation', _check_output,
        request.output_schema_json, record.value_json, failure)
    value=_json(record.value_json)
    if failure:
        from agent_kit.python.boi_structured_provider import audit_codex_events
        events=_json(record.events_json)
        if not isinstance(events,list) or not all(isinstance(e,dict) for e in events):
            raise ValueError('NATIVE_FAILURE_EVENTS_INVALID')
        audit=audit_codex_events(events)
        if (audit['status']!='unexpected_tool_use'
                or not any(e.get('type')=='turn.completed' for e in events)
                or any(e.get('type')=='turn.failed' for e in events)):
            raise ValueError('NATIVE_FAILURE_TERMINAL_TOOL_USE_REQUIRED')
    return {**({'failure_kind':record.failure_kind,'raw_output':value,'raw_output_digest':byte_digest(record.value_json.encode()),'events':events,
                'assessment_available':False} if failure else {'value':value}),
        'request':request.model_dump(mode='json'),
        'provenance':{'binding_kind':'authenticated_native_failure_observation' if failure else 'authenticated_native_observation',
            'observation_revision':revision.model_dump(mode='json'),
            'agent_session_ref':record.agent_session_ref,'session_identity_verified':False,
            'execution_attested':False,'semantic_truth_proven':False,
            'authenticated_principal':authorization.principal}}


def _read_native_observation(work, authorization, revision, *, failure=False):
    """Public observation reads retain their complete current access checks."""
    from ..v2.native_formula_timing import timed_call
    pending=_prepare_native_observation(work,authorization,revision,failure=failure)
    context=timed_call('observation_context_validation',work.contexts.validate_reading,
        authorization=authorization,revision=pending.record.request.knowledge_reading_ref,
        sources=pending.sources,require_current=False)
    return _complete_native_observation(pending,authorization,context)



def read_native_observation(work, authorization, revision):
    return _read_native_observation(work,authorization,revision)


def read_native_failure_observation(work, authorization, revision):
    """Authenticated terminal-failure report, never a successful assessment."""
    return _read_native_observation(work,authorization,revision,failure=True)
