"""External trusted executor kernel for registered read-only deterministic tools.

This is an executor implementation, not a skill helper holding an agent's key.
The deployed host must isolate its key, registry and authorizer from the agent.
There is no public sign-arbitrary-receipt operation. Wiki does not run the tool.
"""
from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Callable, Mapping

from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.tool_execution_contract import (ToolRelease, ToolInvocation,
    ToolExecutionBody, SignedToolExecution, execution_json_bytes, execution_signing_bytes)


@dataclass(frozen=True)
class RegisteredReadOnlyTool:
    release: ToolRelease
    measure_implementation: Callable[[], str]
    measure_environment: Callable[[], str]
    validate_input: Callable[[Mapping[str, bytes]], None]
    execute: Callable[[Mapping[str, bytes]], object]
    validate_output: Callable[[object], None]


@dataclass(frozen=True)
class ToolExecutionResult:
    receipt: SignedToolExecution
    output_bytes: bytes


class ExternalToolExecutor:
    def __init__(self, *, executor_id, key_id, signing_key, registry, authorize_invocation, clock, claim_dispatch=None,
                 clock_wait_seconds=0, clock_wait_observer=None):
        self.executor_id, self.key_id = executor_id, key_id
        self._key = signing_key
        self._registry = dict(registry)
        self._authorize = authorize_invocation
        self._clock = clock
        self._claim_dispatch = claim_dispatch
        if not 0 <= clock_wait_seconds <= 5:raise ValueError('TOOL_EXECUTOR_CLOCK_WAIT_BOUND_INVALID')
        self._clock_wait_seconds=clock_wait_seconds
        self._clock_wait_observer=clock_wait_observer

    def _time_at_or_after(self, earliest):
        observed=self._clock();first=observed;start=time.monotonic()
        while observed<earliest and time.monotonic()-start<self._clock_wait_seconds:
            time.sleep(max(0,min(.05,self._clock_wait_seconds-(time.monotonic()-start))))
            observed=self._clock()
        if first<earliest and self._clock_wait_observer is not None:
            self._clock_wait_observer({'first_observed_at':first.isoformat(),'required_at':earliest.isoformat(),
                'last_observed_at':observed.isoformat(),'waited_seconds':time.monotonic()-start,
                'clock_recovered':observed>=earliest,'timestamp_adjusted':False})
        return observed

    def execute(self, invocation: ToolInvocation, inputs: Mapping[str, bytes]) -> ToolExecutionResult:
        invocation = ToolInvocation.model_validate(invocation.model_dump(mode='python'))
        # The host authorizer reads Wiki-owned invocation/task/lease state. An
        # agent-provided manifest by itself cannot grant execution rights.
        current = self._authorize(invocation.invocation_id)
        if current is None or current != invocation:
            raise ValueError('TOOL_EXECUTOR_INVOCATION_NOT_AUTHORIZED')
        tool = self._registry.get(invocation.tool.revision)
        if tool is None or tool.release != invocation.tool:
            raise ValueError('TOOL_EXECUTOR_UNREGISTERED_RELEASE')
        def measure():
            if (tool.measure_implementation() != tool.release.implementation_manifest_digest
                    or tool.measure_environment() != tool.release.environment_digest):
                raise ValueError('TOOL_EXECUTOR_DEPLOYMENT_DRIFT')
        measure()
        # Take a private bytes snapshot before validating/executing; mutation of
        # the caller's mapping cannot silently replace an authorized input.
        material = dict(inputs)
        if set(material) != {a.name for a in invocation.inputs}:
            raise ValueError('TOOL_EXECUTOR_INPUT_SET_MISMATCH')
        for artifact in invocation.inputs:
            raw = material[artifact.name]
            if not isinstance(raw,bytes) or byte_digest(raw) != artifact.content_digest:
                raise ValueError('TOOL_EXECUTOR_INPUT_DIGEST_MISMATCH')
        started = self._time_at_or_after(invocation.authorized_at)
        if started < invocation.authorized_at:
            raise ValueError('TOOL_EXECUTOR_INVOCATION_NOT_YET_VALID')
        if started >= invocation.expires_at:
            raise ValueError('TOOL_EXECUTOR_INVOCATION_EXPIRED')
        if self._authorize(invocation.invocation_id) != invocation:
            raise ValueError('TOOL_EXECUTOR_AUTHORIZATION_CHANGED')
        from types import MappingProxyType
        material = MappingProxyType(material)
        if self._claim_dispatch is not None and not self._claim_dispatch(invocation.invocation_id):
            raise ValueError('TOOL_EXECUTOR_DISPATCH_NOT_ACQUIRED')
        try:
            tool.validate_input(material)
            value = tool.execute(material)
            # Serialize before any output schema can coerce NaN into null.
            output = execution_json_bytes(value)
            tool.validate_output(value)
            outcome = 'completed'
        except Exception:
            # A failed execution is still evidence, never successful admission.
            # Keep private values and stack traces out of the shared receipt.
            output = execution_json_bytes({'error_code':'TOOL_EXECUTION_FAILED'})
            outcome = 'failed'
        measure()
        finished = self._time_at_or_after(started)
        if self._authorize(invocation.invocation_id) != invocation:
            raise ValueError('TOOL_EXECUTOR_AUTHORIZATION_CHANGED')
        body = ToolExecutionBody(invocation=invocation,executor_id=self.executor_id,key_id=self.key_id,
            started_at=started,finished_at=finished,outcome=outcome,output_content_digest=byte_digest(output))
        signature = base64.b64encode(self._key.sign(execution_signing_bytes(body))).decode('ascii')
        return ToolExecutionResult(SignedToolExecution(body=body,signature_b64=signature),output)
