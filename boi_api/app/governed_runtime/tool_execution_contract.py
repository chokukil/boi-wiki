"""Authenticated external tool execution provenance, separate from any verdict.

The verifier receives expected invocation and trust entries from Wiki-owned
configuration/state. A receipt's self-declared key or input hash is not authority.
Signing keys belong to a separately operated executor, never an agent skill.
"""
from __future__ import annotations

import base64
from datetime import datetime
import json
from typing import Literal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import AwareDatetime, Field, model_validator

from .semantic_binding_contract import Digest, FrozenContract, Ref, RevisionRef
from .source_envelope import byte_digest


def execution_json_bytes(value) -> bytes:
    # Validate before Pydantic JSON conversion can turn non-finite numbers into
    # null. All wire signatures use an explicit, domain-separated serialization.
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')


class ToolRelease(FrozenContract):
    revision: RevisionRef
    implementation_manifest_digest: Digest
    environment_digest: Digest
    input_schema_digest: Digest
    output_schema_digest: Digest
    effects: Literal['read_only'] = 'read_only'


class ToolInputArtifact(FrozenContract):
    name: Ref
    revision: RevisionRef
    content_digest: Digest


class ToolInvocation(FrozenContract):
    contract_version: Literal['boi/tool-invocation@1'] = 'boi/tool-invocation@1'
    invocation_id: Ref
    principal_id: Ref
    task_revision: RevisionRef
    run_id: Ref
    lease_id: Ref
    context_ref: RevisionRef
    context_digest: Digest
    reading_ref: RevisionRef
    policy_digest: Digest
    source_manifest_digest: Digest
    tool: ToolRelease
    inputs: tuple[ToolInputArtifact, ...] = Field(min_length=1)
    authorized_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode='after')
    def valid_window_and_inputs(self):
        if self.expires_at <= self.authorized_at:
            raise ValueError('TOOL_INVOCATION_WINDOW_INVALID')
        if len({a.name for a in self.inputs}) != len(self.inputs):
            raise ValueError('TOOL_INVOCATION_INPUT_NAME_AMBIGUOUS')
        return self


class ToolExecutionBody(FrozenContract):
    contract_version: Literal['boi/tool-execution@1'] = 'boi/tool-execution@1'
    invocation: ToolInvocation
    executor_id: Ref
    key_id: Ref
    started_at: AwareDatetime
    finished_at: AwareDatetime
    outcome: Literal['completed','failed']
    output_content_digest: Digest
    semantic_verdict_issued: Literal[False] = False
    approved: Literal[False] = False

    @model_validator(mode='after')
    def valid_execution_window(self):
        if not self.invocation.authorized_at <= self.started_at <= self.finished_at <= self.invocation.expires_at:
            raise ValueError('TOOL_EXECUTION_OUTSIDE_AUTHORIZED_WINDOW')
        return self


class SignedToolExecution(FrozenContract):
    body: ToolExecutionBody
    signature_b64: str = Field(min_length=88,max_length=88)


class TrustedToolExecutor(FrozenContract):
    executor_id: Ref
    key_id: Ref
    public_key_b64: str = Field(min_length=44,max_length=44)
    releases: tuple[ToolRelease, ...] = Field(min_length=1)
    valid_from: AwareDatetime
    valid_until: AwareDatetime
    revoked: bool = False

    @model_validator(mode='after')
    def valid_trust_window(self):
        if self.valid_until <= self.valid_from:
            raise ValueError('TOOL_EXECUTOR_TRUST_WINDOW_INVALID')
        return self


class VerifiedToolExecution(FrozenContract):
    invocation_id: Ref
    receipt_digest: Digest
    output_content_digest: Digest
    executor_id: Ref
    key_id: Ref
    status: Literal['authenticated_execution'] = 'authenticated_execution'
    outcome: Literal['completed','failed']
    task_complete: Literal[False] = False
    domain_verdict: Literal['not_evaluated'] = 'not_evaluated'
    canonical_projection_eligible: Literal[False] = False


def execution_signing_bytes(body: ToolExecutionBody) -> bytes:
    body = ToolExecutionBody.model_validate(body.model_dump(mode='python'))
    return b'boi/tool-execution-signature@1\n' + execution_json_bytes(body.model_dump(mode='json'))


def _decode(value, size, code):
    try:
        raw = base64.b64decode(value,validate=True)
    except (ValueError,TypeError):
        raise ValueError(code) from None
    if len(raw) != size or base64.b64encode(raw).decode('ascii') != value:
        raise ValueError(code)
    return raw


def verify_tool_execution(*, receipt: SignedToolExecution, expected: ToolInvocation,
        output_bytes: bytes, trusted_executors: tuple[TrustedToolExecutor, ...], at: datetime) -> VerifiedToolExecution:
    """Verify provenance against current trusted state; do not decide check results.

    The caller must first resolve the active task/lease/context and its stored
    invocation. Passing an untrusted caller's expected value defeats that boundary.
    """
    receipt = SignedToolExecution.model_validate(receipt.model_dump(mode='python'))
    expected = ToolInvocation.model_validate(expected.model_dump(mode='python'))
    if at.utcoffset() is None:
        raise ValueError('TOOL_EXECUTION_VERIFICATION_TIME_OFFSET_REQUIRED')
    body = receipt.body
    if body.invocation != expected:
        raise ValueError('TOOL_EXECUTION_INVOCATION_BINDING_MISMATCH')
    if body.finished_at > at:
        raise ValueError('TOOL_EXECUTION_FINISHED_IN_FUTURE')
    entries = [TrustedToolExecutor.model_validate(t.model_dump(mode='python')) for t in trusted_executors
        if (t.executor_id,t.key_id) == (body.executor_id,body.key_id)]
    if len(entries) != 1:
        raise ValueError('TOOL_EXECUTOR_UNKNOWN_OR_AMBIGUOUS')
    trust = entries[0]
    if trust.revoked or not trust.valid_from <= body.started_at <= body.finished_at <= at < trust.valid_until:
        raise ValueError('TOOL_EXECUTOR_TRUST_NOT_CURRENT')
    if expected.tool not in trust.releases:
        raise ValueError('TOOL_EXECUTOR_RELEASE_NOT_AUTHORIZED')
    key = Ed25519PublicKey.from_public_bytes(_decode(trust.public_key_b64,32,'TOOL_EXECUTOR_KEY_INVALID'))
    signature = _decode(receipt.signature_b64,64,'TOOL_EXECUTION_SIGNATURE_INVALID')
    try:
        key.verify(signature,execution_signing_bytes(body))
    except InvalidSignature:
        raise ValueError('TOOL_EXECUTION_SIGNATURE_INVALID') from None
    if byte_digest(output_bytes) != body.output_content_digest:
        raise ValueError('TOOL_EXECUTION_OUTPUT_BINDING_MISMATCH')
    return VerifiedToolExecution(invocation_id=expected.invocation_id,
        receipt_digest=byte_digest(execution_json_bytes(receipt.model_dump(mode='json'))),
        output_content_digest=body.output_content_digest,executor_id=body.executor_id,key_id=body.key_id,
        outcome=body.outcome)
