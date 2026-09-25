"""Stage-scoped resources and observed access receipts for canonical queries."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, is_dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from pydantic import BaseModel, ConfigDict

from .ledger import GovernedRuntimeLedger, RecordKind


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"QUERY_RESOURCE_NOT_CANONICAL:{type(value).__name__}")


def _digest(value: object) -> str:
    encoded = json.dumps(
        _jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


class CanonicalEntrypointClosure(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    entrypoint: str
    modules: tuple[str, ...]
    module_digests: dict[str, str]
    forbidden_modules: tuple[str, ...]
    status: str
    closure_digest: str


_FORBIDDEN_MODULE_TERMS = (
    "candidate_semantic_search",
    "dexa",
    "general_query",
    "golden",
    "logical_query",
    "nl_query",
    "north_star",
)


def audit_canonical_entrypoint_closure(
    entrypoint: Path,
    *,
    package_root: Path | None = None,
) -> CanonicalEntrypointClosure:
    """Resolve only imports executed at module import time.

    Qualification-only adapters are intentionally lazy. They are outside the
    canonical runtime closure unless a default entrypoint imports them.
    """

    root = (package_root or entrypoint.parent).resolve()
    pending = [entrypoint.resolve()]
    visited: set[Path] = set()
    while pending:
        current = pending.pop(0)
        if current in visited or not current.is_file():
            continue
        visited.add(current)
        tree = ast.parse(current.read_text(encoding="utf-8"), filename=str(current))
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom) or node.level < 1:
                continue
            base = current.parent
            for _ in range(max(0, node.level - 1)):
                base = base.parent
            if node.module:
                target = base.joinpath(*node.module.split(".")).with_suffix(".py")
                if target.is_file() and (target == root or root in target.parents):
                    pending.append(target.resolve())
                package = base.joinpath(*node.module.split("."), "__init__.py")
                if package.is_file() and (package == root or root in package.parents):
                    pending.append(package.resolve())
            else:
                for alias in node.names:
                    target = (base / alias.name).with_suffix(".py")
                    if target.is_file() and (target == root or root in target.parents):
                        pending.append(target.resolve())
    modules = tuple(sorted(path.relative_to(root).as_posix() for path in visited))
    digests = {
        path.relative_to(root).as_posix(): "sha256:"
        + hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(visited)
    }
    forbidden = tuple(
        module
        for module in modules
        if any(term in module.casefold() for term in _FORBIDDEN_MODULE_TERMS)
    )
    values = {
        "entrypoint": entrypoint.resolve().relative_to(root).as_posix(),
        "modules": modules,
        "module_digests": digests,
        "forbidden_modules": forbidden,
        "status": "PASS" if not forbidden else "FAIL",
    }
    return CanonicalEntrypointClosure(
        **values,
        closure_digest=_digest(values),
    )


class QueryResourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: str = "boi/canonical-query-resource-manifest@1.0.0"
    entrypoint: str = "ProfileDrivenQueryRuntime.handle"
    stage_kinds: dict[str, tuple[str, ...]]
    denied_ref_prefixes: tuple[str, ...]
    manifest_digest: str

    def with_clarification(self) -> "QueryResourceManifest":
        values = self.model_dump(mode='json', exclude={'manifest_digest'})
        values['manifest_version'] = 'boi/canonical-query-resource-manifest@1.1.0'
        for stage in ('pi', 'resolver'):
            values['stage_kinds'][stage] = list(dict.fromkeys(
                [*values['stage_kinds'][stage], 'clarification_reply']))
        return QueryResourceManifest(**values, manifest_digest=_digest(values))

    def with_identity_grain(self) -> "QueryResourceManifest":
        values = self.model_dump(mode='json', exclude={'manifest_digest'})
        values['manifest_version'] = 'boi/canonical-query-resource-manifest@1.2.0'
        values['stage_kinds']['key_profiler'] = ['semantic_context']
        return QueryResourceManifest(**values, manifest_digest=_digest(values))

    @classmethod
    def canonical(cls) -> "QueryResourceManifest":
        values = {
            "manifest_version": "boi/canonical-query-resource-manifest@1.0.0",
            "entrypoint": "ProfileDrivenQueryRuntime.handle",
            "stage_kinds": {
                "profile_loader": ("catalog",),
                "retrieval": ("question", "profile_bundle"),
                "pi": ("question", "profile_bundle", "retrieval_receipt"),
                "resolver": (
                    "profile_bundle",
                    "retrieval_receipt",
                    "intent_synthesis",
                ),
                "planner": (
                    "catalog",
                    "profile_bundle",
                    "retrieval_receipt",
                    "intent_resolution",
                ),
                "gateway": ("execution_request",),
            },
            "denied_ref_prefixes": (
                "answer-template:",
                "dexa:",
                "golden:",
                "historical-flat-view:",
                "queryspec:",
                "registered-query-spec:",
            ),
        }
        return cls(**values, manifest_digest=_digest(values))


@dataclass(frozen=True)
class _Resource:
    ref: str
    kind: str
    digest: str
    value: object


class QueryResourceAccessEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sequence: int
    run_id: str
    stage: str
    resource_ref: str
    resource_kind: str
    resource_digest: str
    capability_digest: str
    allowed: bool
    reason_code: str
    previous_event_digest: str
    event_digest: str
    ledger_record_id: str


class QueryResourceAccessReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    manifest_digest: str
    events: tuple[QueryResourceAccessEvent, ...]
    allowed_access_count: int
    denied_access_count: int
    accessed_resource_digests: tuple[str, ...]
    receipt_digest: str
    ledger_record_id: str


class CanonicalQueryFreezeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: str = "boi/canonical-query-freeze@1.0.0"
    run_id: str
    candidate_digest: str
    intent_digest: str
    logical_plan_digest: str
    profile_bundle_digest: str
    catalog_snapshot_digest: str
    resource_manifest_digest: str
    entrypoint_closure_digest: str
    access_receipt_digest: str
    observed_resource_digests: tuple[str, ...]
    denied_oracle_access_count: int
    status: str
    receipt_digest: str
    ledger_record_id: str


class QueryResourceAccessDenied(RuntimeError):
    pass


class CanonicalQueryResourceBroker:
    """In-memory capability broker with immutable access events in the ledger."""

    def __init__(
        self,
        *,
        ledger: GovernedRuntimeLedger,
        run_id: str,
        occurred_at: str,
        manifest: QueryResourceManifest,
        entrypoint_closure_digest: str,
    ) -> None:
        self.ledger = ledger
        self.run_id = run_id
        self.occurred_at = occurred_at
        self.manifest = manifest
        self.entrypoint_closure_digest = entrypoint_closure_digest
        self._resources: dict[str, _Resource] = {}
        self._grants: dict[str, set[str]] = {
            stage: set() for stage in manifest.stage_kinds
        }
        self._events: list[QueryResourceAccessEvent] = []

    def _denied_prefix(self, ref: str) -> bool:
        return any(ref.startswith(prefix) for prefix in self.manifest.denied_ref_prefixes)

    def publish(
        self,
        *,
        kind: str,
        value: object,
        consumers: Iterable[str],
        digest: str | None = None,
    ) -> str:
        resource_digest = digest or _digest(value)
        if not resource_digest.startswith("sha256:"):
            raise ValueError("QUERY_RESOURCE_DIGEST_REQUIRED")
        ref = f"query-resource:{kind}:{resource_digest.removeprefix('sha256:')}"
        for stage in tuple(consumers):
            allowed_kinds = self.manifest.stage_kinds.get(stage)
            if allowed_kinds is None or kind not in allowed_kinds:
                raise QueryResourceAccessDenied(
                    f"QUERY_RESOURCE_KIND_NOT_ALLOWED:{stage}:{kind}"
                )
            self._grants[stage].add(ref)
        self._resources[ref] = _Resource(
            ref=ref, kind=kind, digest=resource_digest, value=value
        )
        return ref

    def _record(
        self,
        *,
        stage: str,
        ref: str,
        resource: _Resource | None,
        allowed: bool,
        reason_code: str,
    ) -> QueryResourceAccessEvent:
        previous = self._events[-1].event_digest if self._events else ""
        capability_digest = _digest(
            {
                "manifest_digest": self.manifest.manifest_digest,
                "stage": stage,
                "granted_refs": sorted(self._grants.get(stage, ())),
            }
        )
        base = {
            "sequence": len(self._events) + 1,
            "run_id": self.run_id,
            "stage": stage,
            "resource_ref": ref,
            "resource_kind": resource.kind if resource is not None else "denied",
            "resource_digest": resource.digest if resource is not None and allowed else "",
            "capability_digest": capability_digest,
            "allowed": allowed,
            "reason_code": reason_code,
            "previous_event_digest": previous,
        }
        event_digest = _digest(base)
        record = self.ledger.append(
            RecordKind.RUN,
            {
                "record_type": "canonical_query_resource_access",
                **base,
                "event_digest": event_digest,
            },
            authority="executor",
            occurred_at=self.occurred_at,
        )
        event = QueryResourceAccessEvent(
            **base,
            event_digest=event_digest,
            ledger_record_id=record.record_id,
        )
        self._events.append(event)
        return event

    def read(self, *, stage: str, ref: str) -> object:
        resource = self._resources.get(ref)
        allowed = (
            not self._denied_prefix(ref)
            and resource is not None
            and ref in self._grants.get(stage, set())
        )
        reason = "" if allowed else (
            "PREFREEZE_ORACLE_ACCESS_DENIED"
            if self._denied_prefix(ref)
            else "QUERY_RESOURCE_CAPABILITY_DENIED"
        )
        self._record(
            stage=stage,
            ref=ref,
            resource=resource,
            allowed=allowed,
            reason_code=reason,
        )
        if not allowed:
            raise QueryResourceAccessDenied(reason)
        return resource.value

    def access_receipt(self) -> QueryResourceAccessReceipt:
        values = {
            "run_id": self.run_id,
            "manifest_digest": self.manifest.manifest_digest,
            "events": tuple(self._events),
            "allowed_access_count": sum(event.allowed for event in self._events),
            "denied_access_count": sum(not event.allowed for event in self._events),
            "accessed_resource_digests": tuple(
                event.resource_digest for event in self._events if event.allowed
            ),
        }
        digest_values = {
            **values,
            "events": tuple(event.model_dump(mode="json") for event in self._events),
        }
        receipt_digest = _digest(digest_values)
        record = self.ledger.append(
            RecordKind.RUN,
            {
                "record_type": "canonical_query_resource_access_receipt",
                **digest_values,
                "receipt_digest": receipt_digest,
            },
            authority="executor",
            occurred_at=self.occurred_at,
        )
        return QueryResourceAccessReceipt(
            **values,
            receipt_digest=receipt_digest,
            ledger_record_id=record.record_id,
        )

    def freeze(
        self,
        *,
        candidate_digest: str,
        intent_digest: str,
        logical_plan_digest: str,
        profile_bundle_digest: str,
        catalog_snapshot_digest: str,
    ) -> CanonicalQueryFreezeReceipt:
        receipt = self.access_receipt()
        values = {
            "contract_version": "boi/canonical-query-freeze@1.0.0",
            "run_id": self.run_id,
            "candidate_digest": candidate_digest,
            "intent_digest": intent_digest,
            "logical_plan_digest": logical_plan_digest,
            "profile_bundle_digest": profile_bundle_digest,
            "catalog_snapshot_digest": catalog_snapshot_digest,
            "resource_manifest_digest": self.manifest.manifest_digest,
            "entrypoint_closure_digest": self.entrypoint_closure_digest,
            "access_receipt_digest": receipt.receipt_digest,
            "observed_resource_digests": receipt.accessed_resource_digests,
            "denied_oracle_access_count": receipt.denied_access_count,
            "status": "FROZEN" if receipt.denied_access_count == 0 else "BLOCKED",
        }
        receipt_digest = _digest(values)
        record = self.ledger.append(
            RecordKind.RUN,
            {
                "record_type": "canonical_query_freeze_receipt",
                **values,
                "receipt_digest": receipt_digest,
                "access_receipt_record_id": receipt.ledger_record_id,
            },
            authority="executor",
            occurred_at=self.occurred_at,
        )
        return CanonicalQueryFreezeReceipt(
            **values,
            receipt_digest=receipt_digest,
            ledger_record_id=record.record_id,
        )
