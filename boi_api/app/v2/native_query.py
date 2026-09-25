"""Native query host contracts. Source permissions are server-owned, not requests."""
from pathlib import Path
from collections import OrderedDict
import json
import os
import sqlite3
import logging
import threading
import time
import uuid
from typing import Literal
from pydantic import Field, model_validator
from ..governed_runtime.query_source_action import QuerySourceActionBinding, QuerySourceAction
from ..governed_runtime.semantic_binding_contract import FrozenContract, Ref, Digest, RevisionRef, semantic_digest
from ..governed_runtime.sqlite_source_snapshot import sealed_sqlite_digest
from ..governed_runtime.native_profile_context import read_native_profile_bundle
from ..governed_runtime.semantic_profile_loader import (
    SemanticContextBundle, request_profile_document_decoding,
)
from ..governed_runtime.semantic_query_planner import PlannerCatalogSnapshot, PlanningPolicy, CheckEvidenceStore
from ..governed_runtime.semantic_intent import NativeIntentSubmission


class NativeReadScope(FrozenContract):
    principal: Ref
    operation: Literal['bounded_read_only_native_sqlite', 'bounded_read_only_action_sqlite']
    source_snapshot_digest: Digest
    allowed_sources: tuple[Ref, ...] = Field(min_length=1, max_length=1)
    allowed_tables: tuple[Ref, ...] = Field(min_length=1, max_length=64)
    max_output_rows: int = Field(ge=1, le=1000, strict=True)
    max_scan_rows: int = Field(ge=1, le=9999, strict=True)
    request_text_digest: Digest
    request_source: Ref
    production_authorized: Literal[False]


class NativeQueryPrepareRequest(FrozenContract):
    connection_id: Ref
    question: str = Field(min_length=1, max_length=8192, pattern=r'\S')


class NativeQueryExecuteRequest(FrozenContract):
    connection_id: Ref
    plan_ref: str = Field(pattern=r'^evidence://sha256:[a-f0-9]{64}$')
    idempotency_key: str = Field(min_length=1, max_length=240, pattern=r'\S')


class NativeQueryResultRequest(FrozenContract):
    connection_id: Ref
    execution_ref: str = Field(pattern=r'^evidence://sha256:[a-f0-9]{64}$')


def native_query_result_url(request):
    """Protected result navigation; the opaque reference grants no authority."""
    from urllib.parse import quote, urlsplit
    request = NativeQueryResultRequest.model_validate(request)
    origin = os.environ.get('BOI_EXTERNAL_URL', '').rstrip('/')
    parsed = urlsplit(origin)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        origin = ''
    digest = request.execution_ref.removeprefix('evidence://sha256:')
    return (origin+'/native-query-results/'+digest+'?connection_id='
            +quote(request.connection_id, safe=''))


class NativeQueryDiagnoseEmptyRequest(NativeQueryResultRequest):
    """Read-only diagnosis of the same protected empty-root execution."""


class NativeSourceIdentity(FrozenContract):
    """Deployment-owned identity and physical lineage for a selectable source."""
    contract_version: Literal['boi/native-source-identity@1'] = 'boi/native-source-identity@1'
    source_ref: Ref
    source_id: Ref
    physical_tables: tuple[Ref, ...] = Field(min_length=1, max_length=64)
    terms: tuple[Ref, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def unique_identity_values(self):
        if len(set(self.physical_tables)) != len(self.physical_tables):
            raise ValueError('NATIVE_SOURCE_IDENTITY_TABLE_DUPLICATE')
        if len(set(self.terms)) != len(self.terms):
            raise ValueError('NATIVE_SOURCE_IDENTITY_TERM_DUPLICATE')
        return self


class NativeSourceUseConstraint(FrozenContract):
    """Question-scoped source selection; this is never a row predicate."""
    contract_version: Literal['boi/native-source-use-constraint@1'] = 'boi/native-source-use-constraint@1'
    source_ref: Ref
    mode: Literal['EXCLUDE']


class NativeQueryPlanRequest(NativeQueryPrepareRequest):
    submission: NativeIntentSubmission
    source_use_constraints: tuple[NativeSourceUseConstraint, ...] = Field(default=(), max_length=16)


class NativeSourcePolicyContinuity(FrozenContract):
    """Deployment-owned proof inputs for an unchanged principal's source grant.

    This is not a policy alias: both the current grant and the exact earlier
    policy are checked at every native authority fence. No client supplies it.
    """
    contract_version: Literal['boi/native-source-policy-continuity@1'] = 'boi/native-source-policy-continuity@1'
    policy_path: Ref
    policy_digest: Digest
    current_policy_digest: Digest


class NativeSelectionProperty(FrozenContract):
    """One property name from a previously admitted Profile revision."""
    ref: Ref
    key: Ref
    name: str = Field(min_length=1)
    availability: Literal['bound', 'unbound']


class NativeSelectionObject(FrozenContract):
    ref: Ref
    name: str = Field(min_length=1)
    properties: tuple[NativeSelectionProperty, ...] = Field(max_length=500)


class NativeSelectionRelation(FrozenContract):
    ref: Ref
    name: str = Field(min_length=1)
    left_endpoint_ref: Ref | None = None
    right_endpoint_ref: Ref | None = None


class NativeSelectionCapability(FrozenContract):
    """Server-generated navigation metadata; prepare must re-admit and match it."""
    contract_version: Literal['boi/native-selection-capability@1'] = 'boi/native-selection-capability@1'
    principal: Ref
    profile_revision_digest: Digest
    review_revision_digest: Digest
    source_snapshot_digest: Digest
    catalog_schema_digest: Digest
    active_pointer_digest: Digest
    bundle_digest: Digest
    objects: tuple[NativeSelectionObject, ...] = Field(max_length=500)
    unowned_properties: tuple[NativeSelectionProperty, ...] = Field(max_length=500)
    relations: tuple[NativeSelectionRelation, ...] = Field(max_length=500)
    logical_entry_count: int = Field(ge=0, le=500, strict=True)
    capability_digest: Digest

    @model_validator(mode='after')
    def exact_digest(self):
        body = self.model_dump(mode='json', exclude={'capability_digest'})
        if self.capability_digest != semantic_digest(body):
            raise ValueError('NATIVE_SELECTION_CAPABILITY_DIGEST_MISMATCH')
        return self


class NativeQueryConnection(FrozenContract):
    """Trusted host configuration, never accepted from an MCP caller."""
    connection_id: Ref
    title: Ref
    sqlite_path: Ref | None = None
    execution_binding: QuerySourceActionBinding | None = None
    catalog: PlannerCatalogSnapshot
    review_revision: RevisionRef
    profile_revision: RevisionRef
    scope: NativeReadScope
    planning_policy: PlanningPolicy
    storage_root: Ref
    source_policy_continuity: NativeSourcePolicyContinuity | None = None
    source_identities: tuple[NativeSourceIdentity, ...] = Field(default=(), max_length=64)
    selection_capability: NativeSelectionCapability | None = None

    @model_validator(mode='after')
    def source_execution_contract(self):
        if (self.sqlite_path is None) == (self.execution_binding is None):
            raise ValueError('NATIVE_QUERY_EXACT_EXECUTION_BINDING_REQUIRED')
        expected = ('bounded_read_only_action_sqlite' if self.execution_binding
            else 'bounded_read_only_native_sqlite')
        if self.scope.operation != expected:
            raise ValueError('NATIVE_QUERY_EXECUTION_SCOPE_MISMATCH')
        if len({item.source_ref for item in self.source_identities}) != len(self.source_identities):
            raise ValueError('NATIVE_SOURCE_IDENTITY_REF_DUPLICATE')
        if any(item.source_id not in self.scope.allowed_sources for item in self.source_identities):
            raise ValueError('NATIVE_SOURCE_IDENTITY_SOURCE_NOT_AUTHORIZED')
        capability = self.selection_capability
        if capability is not None and (
                capability.principal != self.scope.principal
                or capability.profile_revision_digest != self.profile_revision.revision_digest
                or capability.review_revision_digest != self.review_revision.revision_digest
                or capability.source_snapshot_digest != self.scope.source_snapshot_digest
                or capability.catalog_schema_digest != self.catalog.schema_digest):
            raise ValueError('NATIVE_SELECTION_CAPABILITY_SCOPE_MISMATCH')
        return self


class NativeQueryConnections(FrozenContract):
    connections: tuple[NativeQueryConnection, ...] = Field(max_length=64)


def native_selection_capability_from_bundle(bundle, connection, active_pointer_digest):
    """Build a revision-bound, question-independent selection summary."""
    connection = NativeQueryConnection.model_validate(connection)
    if (bundle.principal_id != connection.scope.principal
            or bundle.catalog_snapshot_digest != connection.catalog.snapshot_digest
            or bundle.schema_digest != connection.catalog.schema_digest):
        raise ValueError('NATIVE_SELECTION_CAPABILITY_BUNDLE_SCOPE_MISMATCH')
    def label(entry):
        value = entry.payload.get('name')
        return value.strip() if isinstance(value, str) and value.strip() else entry.entry_id
    unavailable = set(bundle.unavailable_logical_ids)
    properties = {}
    for entry in bundle.domain_entries:
        if entry.payload.get('kind') != 'PropertyDefinition':
            continue
        owner = entry.payload.get('owner_ref')
        property_record = {'ref': entry.entry_id,
            'key': entry.entry_id.rsplit(':', 1)[-1], 'name': label(entry),
            'availability': 'unbound' if entry.entry_id in unavailable else 'bound'}
        properties.setdefault(owner, []).append(property_record)
    objects = []
    for entry in bundle.domain_entries:
        if entry.payload.get('kind') != 'ObjectType':
            continue
        objects.append({'ref': entry.entry_id, 'name': label(entry),
            'properties': sorted(properties.pop(entry.entry_id, []),
                key=lambda item: item['ref'])})
    relations = []
    for entry in bundle.domain_entries:
        if entry.payload.get('kind') != 'RelationType':
            continue
        relations.append({'ref': entry.entry_id, 'name': label(entry),
            'left_endpoint_ref': entry.payload.get('left_endpoint_ref'),
            'right_endpoint_ref': entry.payload.get('right_endpoint_ref')})
    unowned = sorted((item for group in properties.values() for item in group),
        key=lambda item: item['ref'])
    body = {'contract_version': 'boi/native-selection-capability@1',
        'principal': connection.scope.principal,
        'profile_revision_digest': connection.profile_revision.revision_digest,
        'review_revision_digest': connection.review_revision.revision_digest,
        'source_snapshot_digest': connection.scope.source_snapshot_digest,
        'catalog_schema_digest': connection.catalog.schema_digest,
        'active_pointer_digest': active_pointer_digest,
        'bundle_digest': bundle.bundle_digest,
        'objects': sorted(objects, key=lambda item: item['ref']),
        'unowned_properties': unowned,
        'relations': sorted(relations, key=lambda item: item['ref']),
        'logical_entry_count': len(bundle.domain_entries)}
    return NativeSelectionCapability.model_validate({
        **body, 'capability_digest': semantic_digest(body)})


def validated_native_selection_capability(bundle, connection, active_pointer_digest):
    generated = native_selection_capability_from_bundle(
        bundle, connection, active_pointer_digest)
    configured = connection.selection_capability
    if configured is not None and generated != configured:
        raise ValueError('NATIVE_SELECTION_CAPABILITY_STALE_OR_MISMATCHED')
    return generated

class NativeQueryRegistrationRequest(FrozenContract):
    """Caller may select only a server-approved source template."""
    source_id: Ref


_REGISTRATION_TEMPLATE_PRINCIPAL = 'native-query-registration-owner'


# The protected query chain normally reuses one exact, content-addressed
# Profile within seconds. Keep that successful admission briefly, keyed by all
# current mutable authority and source fences. Every API action still rechecks
# current authorization and source bytes before this cache is consulted.
_NATIVE_ADMISSION_CACHE = OrderedDict()
_NATIVE_ADMISSION_CACHE_LOCK = threading.RLock()
_NATIVE_ADMISSION_CACHE_TTL_SECONDS = 180.0
_NATIVE_ADMISSION_CACHE_LIMIT = 64


def _native_admission_cache_key(host, source_authorization, active_pointer):
    return (
        str(host.work.ledger.root.resolve()),
        host.authorization.principal,
        source_authorization.policy_digest,
        host.connection_digest,
        host.connection.scope.source_snapshot_digest,
        semantic_digest(active_pointer),
    )


def _read_cached_native_admission(key):
    now = time.monotonic()
    with _NATIVE_ADMISSION_CACHE_LOCK:
        item = _NATIVE_ADMISSION_CACHE.get(key)
        if item is not None:
            inserted, bundle = item
            if now - inserted <= _NATIVE_ADMISSION_CACHE_TTL_SECONDS:
                _NATIVE_ADMISSION_CACHE.move_to_end(key)
                return bundle
            _NATIVE_ADMISSION_CACHE.pop(key, None)
        # Another worker may have refreshed the shared entry after this
        # worker's local entry expired. Recheck that content-addressed entry
        # before rebuilding the protected Profile admission.
        bundle = _read_shared_native_admission(key)
        if bundle is not None:
            _NATIVE_ADMISSION_CACHE[key] = (now, bundle)
            _NATIVE_ADMISSION_CACHE.move_to_end(key)
        return bundle


def _write_cached_native_admission(key, bundle):
    with _NATIVE_ADMISSION_CACHE_LOCK:
        _NATIVE_ADMISSION_CACHE[key] = (time.monotonic(), bundle)
        _NATIVE_ADMISSION_CACHE.move_to_end(key)
        while len(_NATIVE_ADMISSION_CACHE) > _NATIVE_ADMISSION_CACHE_LIMIT:
            _NATIVE_ADMISSION_CACHE.popitem(last=False)
    _write_shared_native_admission(key, bundle)


def _shared_native_admission_path(key):
    root = Path(os.environ.get('BOI_NATIVE_ADMISSION_CACHE_DIR',
        '/tmp/boi-native-admission-cache-%d' % os.getuid()))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        return None
    return root / (semantic_digest(key).removeprefix('sha256:') + '.json')


def _read_shared_native_admission(key):
    path = _shared_native_admission_path(key)
    if path is None:
        return None
    try:
        stat = path.lstat()
        if path.is_symlink() or stat.st_uid != os.getuid() or time.time() - stat.st_mtime > _NATIVE_ADMISSION_CACHE_TTL_SECONDS:
            return None
        return SemanticContextBundle.model_validate_json(path.read_bytes())
    except (OSError, ValueError):
        return None


def _write_shared_native_admission(key, bundle):
    path = _shared_native_admission_path(key)
    if path is None:
        return
    temporary = path.with_name('.%s.%d.%d.tmp' % (path.name, os.getpid(), threading.get_ident()))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(bundle.model_dump_json().encode())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError:
        try:
            temporary.unlink()
        except OSError:
            pass


class NativeQueryRegistrationTemplate(FrozenContract):
    """Deployment-owned source/action template; never supplied by an MCP caller."""
    source_id: Ref
    connection: NativeQueryConnection

    @model_validator(mode='after')
    def requires_owner_placeholder(self):
        if self.connection.scope.principal != _REGISTRATION_TEMPLATE_PRINCIPAL:
            raise ValueError('NATIVE_QUERY_REGISTRATION_TEMPLATE_OWNER_REQUIRED')
        return self


class NativeQueryRegistrationCatalog(FrozenContract):
    sources: tuple[NativeQueryRegistrationTemplate, ...] = Field(max_length=64)


class NativeQueryRegistration(FrozenContract):
    source_id: Ref
    principal: Ref
    connection_id: Ref
    registration_digest: Digest


class NativeQueryRegistrations(FrozenContract):
    registrations: tuple[NativeQueryRegistration, ...] = Field(max_length=64)


def _registration_catalog_path():
    return Path(os.environ.get('BOI_NATIVE_QUERY_REGISTRATION_CATALOG_PATH',
        '/data/native-query-registration-catalog.json'))


def _registration_store_path():
    return Path(os.environ.get('BOI_NATIVE_QUERY_REGISTRATION_STORE_PATH',
        '/data/native-query-registrations.json'))


def _read_registration_catalog():
    path = _registration_catalog_path()
    if not path.is_file():
        raise ValueError('NATIVE_QUERY_REGISTRATION_NOT_CONFIGURED')
    catalog = NativeQueryRegistrationCatalog.model_validate_json(path.read_bytes())
    if len({item.source_id for item in catalog.sources}) != len(catalog.sources):
        raise ValueError('NATIVE_QUERY_REGISTRATION_SOURCE_AMBIGUOUS')
    return catalog


def _read_registrations():
    path = _registration_store_path()
    if not path.is_file():
        return NativeQueryRegistrations(registrations=())
    rows = NativeQueryRegistrations.model_validate_json(path.read_bytes())
    if len({item.connection_id for item in rows.registrations}) != len(rows.registrations):
        raise ValueError('NATIVE_QUERY_REGISTRATION_CONNECTION_AMBIGUOUS')
    return rows


def _write_registrations(rows):
    """Atomically replace only the dedicated server-owned registration state."""
    path = _registration_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_bytes(rows.model_dump_json(by_alias=True).encode())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _current_registration_authorization(authorization, work):
    reader = getattr(work, 'current_knowledge_authorization', None)
    current = reader() if callable(reader) else authorization
    if current.principal != authorization.principal:
        raise ValueError('NATIVE_QUERY_REGISTRATION_PRINCIPAL_MISMATCH')
    if 'derive' not in tuple(getattr(current, 'allowed_uses', ())):
        raise ValueError('NATIVE_QUERY_REGISTRATION_SOURCE_USE_DENIED')
    return current


def _connection_from_registration(template, registration):
    connection = template.connection
    scope = connection.scope.model_copy(update={
        'principal': registration.principal,
        'request_text_digest': semantic_digest({
            'contract_version': 'boi/native-query-registration@1',
            'source_id': registration.source_id,
            'principal': registration.principal,
        }),
        'request_source': 'native-query-registration:' + registration.source_id,
    })
    return connection.model_copy(update={
        'connection_id': registration.connection_id,
        'scope': scope,
    })


def _registered_native_queries(authorization):
    catalog_path = _registration_catalog_path()
    if not catalog_path.is_file():
        return ()
    catalog = _read_registration_catalog()
    templates = {item.source_id: item for item in catalog.sources}
    rows = _read_registrations()
    owned = tuple(item for item in rows.registrations if item.principal == authorization.principal)
    if any(item.source_id not in templates for item in owned):
        raise ValueError('NATIVE_QUERY_REGISTRATION_SOURCE_RETIRED')
    return tuple(_connection_from_registration(templates[row.source_id], row) for row in owned)


def discover_native_query_registration_sources(intake, principal):
    authorization, work = intake._work(principal)
    _current_registration_authorization(authorization, work)
    catalog = _read_registration_catalog()
    existing = {(item.source_id, item.principal) for item in _read_registrations().registrations}
    return {'sources': [{
        'source_id': item.source_id,
        'title': item.connection.title,
        'already_registered': (item.source_id, authorization.principal) in existing,
        'registration_scope': 'private_recipient_only',
    } for item in catalog.sources], 'status': 'PROVISIONAL',
        'query_execution_status': 'not_run'}


def register_native_query_source(intake, principal, request):
    """Bind one server-approved source template to the authenticated recipient."""
    request = NativeQueryRegistrationRequest.model_validate(request)
    authorization, work = intake._work(principal)
    current = _current_registration_authorization(authorization, work)
    catalog = _read_registration_catalog()
    template = next((item for item in catalog.sources if item.source_id == request.source_id), None)
    if template is None:
        raise ValueError('NATIVE_QUERY_REGISTRATION_SOURCE_NOT_APPROVED')
    digest = semantic_digest({
        'contract_version': 'boi/native-query-registration@1',
        'source_id': template.source_id,
        'principal': current.principal,
    })
    connection_id = 'native-reg-' + digest.removeprefix('sha256:')[:24]
    registration = NativeQueryRegistration(
        source_id=template.source_id, principal=current.principal,
        connection_id=connection_id, registration_digest=digest)
    # Snapshot validation happens before any registration state is written.
    connection = _connection_from_registration(template, registration)
    if connection.sqlite_path is not None:
        check_native_source_scope(connection.scope, principal=current.principal,
            sqlite_path=connection.sqlite_path)
    rows = _read_registrations()
    existing = next((item for item in rows.registrations
        if item.source_id == registration.source_id and item.principal == registration.principal), None)
    if existing is None:
        if len(rows.registrations) >= 64:
            raise ValueError('NATIVE_QUERY_REGISTRATION_LIMIT')
        _write_registrations(NativeQueryRegistrations(
            registrations=(*rows.registrations, registration)))
        status = 'registered'
    else:
        registration = existing
        connection = _connection_from_registration(template, registration)
        status = 'already_registered'
    return {'connection_id': connection.connection_id,
        'source_id': registration.source_id, 'title': connection.title,
        'registration_status': status,
        'registration_scope': 'private_recipient_only',
        'source_snapshot_digest': connection.scope.source_snapshot_digest,
        'query_execution_status': 'not_run'}


def configured_native_queries(intake, principal):
    """Deployment configuration plus recipient-owned registrations; neither trusts caller paths."""
    authorization, work = intake._work(principal)
    path = Path(os.environ.get('BOI_NATIVE_QUERY_CONFIG_PATH', '/data/native-query-host.json'))
    from .database_source import database_query_connections
    bound=database_query_connections(intake,authorization)
    if not path.is_file() and not bound:
        raise ValueError('NATIVE_QUERY_NOT_CONFIGURED')
    config = NativeQueryConnections.model_validate_json(path.read_bytes()) if path.is_file() else NativeQueryConnections(connections=())
    connections = (*config.connections, *_registered_native_queries(authorization), *bound)
    if len({c.connection_id for c in connections}) != len(connections):
        raise ValueError('NATIVE_QUERY_CONNECTION_AMBIGUOUS')
    return authorization, work, tuple(c for c in connections
        if c.scope.principal == authorization.principal)


def _native_selection_navigation(capability):
    """Bounded candidate metadata, never a source or execution authorization."""
    def shown(properties):
        return [{'key': item.key, 'name': item.name,
                 'availability': item.availability} for item in properties[:64]]
    return {'contract_version': capability.contract_version,
        'capability_digest': capability.capability_digest,
        'profile_revision_digest': capability.profile_revision_digest,
        'objects': [{'name': item.name, 'property_count': len(item.properties),
            'field_list_complete': len(item.properties) <= 64,
            'properties': shown(item.properties)} for item in capability.objects],
        'unowned_property_count': len(capability.unowned_properties),
        'unowned_field_list_complete': len(capability.unowned_properties) <= 64,
        'unowned_properties': shown(capability.unowned_properties),
        'relations': [{'name': item.name,
            'left_endpoint_ref': item.left_endpoint_ref,
            'right_endpoint_ref': item.right_endpoint_ref} for item in capability.relations],
        'authority':'navigation_only_current_prepare_required'}


def discover_native_queries(intake, principal):
    authorization, work, connections = configured_native_queries(intake, principal)
    active_pointer_digest = None
    def candidate(c):
        nonlocal active_pointer_digest
        selection_context = {
            'allowed_sources':list(c.scope.allowed_sources),
            'allowed_tables':list(c.scope.allowed_tables),
            'max_output_rows':c.scope.max_output_rows,
            'max_scan_rows':c.scope.max_scan_rows,
            'catalog_snapshot_digest':c.catalog.snapshot_digest,
            'catalog_schema_digest':c.catalog.schema_digest,
            'scope_basis':'configured_candidate_requires_current_prepare',
            'execution_authority_granted':False}
        capability = c.selection_capability
        if capability is not None:
            if active_pointer_digest is None:
                active_pointer_digest = semantic_digest(work.ledger.active_pointer())
            if capability.active_pointer_digest == active_pointer_digest:
                try:
                    NativeQueryHost(work, authorization, c)._check_current_source()
                except (OSError, ValueError):
                    pass
                else:
                    selection_context['selection_capability'] = _native_selection_navigation(capability)
        return {'connection_id':c.connection_id, 'title':c.title,
        'source_snapshot_digest':c.scope.source_snapshot_digest,
        'profile_revision':c.profile_revision.model_dump(mode='json'),
        'review_revision':c.review_revision.model_dump(mode='json'),
        'selection_context':selection_context,
        **({'execution_binding':c.execution_binding.model_dump(mode='json')}
           if c.execution_binding else {})}
    return {'connections':[candidate(c) for c in connections],
        'status':'PROVISIONAL', 'query_execution_status':'not_run'}


def native_query_for_principal(intake, principal, request, *, action):
    # Enter in the synchronous worker that owns the request. Every authority
    # fence still reads current rows and retains its transaction boundary.
    from .store_connections import request_store_connections
    from .native_formula_timing import collect_stage_timings
    from .process_review_binding import request_full_source_read_reuse
    from ..governed_runtime.ledger import request_ledger_decoding
    from ..governed_runtime.domain_context_service import request_context_decoding
    with request_store_connections(), request_ledger_decoding(), request_context_decoding(), \
            request_profile_document_decoding(), request_full_source_read_reuse(), \
            collect_stage_timings() as details:
        result = _native_query_for_principal(intake, principal, request, action=action)
        result['timing']['detail_stages'] = details
        return result


def _native_query_for_principal(intake, principal, request, *, action):
    started = time.perf_counter()
    authorization, work, connections = configured_native_queries(intake, principal)
    connection = next((c for c in connections if c.connection_id == request.connection_id), None)
    if connection is None:
        raise ValueError('NATIVE_QUERY_CONNECTION_NOT_AUTHORIZED')
    if connection.execution_binding is not None:
        check_native_action_permission(principal)
    host = NativeQueryHost(work, authorization, connection)
    # A remote query response is revision-pinned. Within one synchronous
    # action, retain current grant checks at every callback, but coalesce
    # repeated remote scope-count reads between the opening and final fences.
    # Local SQLite and discovery keep their existing per-callback checks.
    host._coalesce_remote_source_scope = getattr(host, 'query_source', None) is not None
    methods = {'prepare':host.prepare, 'plan':host.plan, 'execute':host.execute,
        'result':host.result, 'diagnose_empty':host.diagnose_empty}
    if action not in methods:
        raise ValueError('NATIVE_QUERY_ACTION_INVALID')
    request_id = str(uuid.uuid4())
    outcome = 'error'
    try:
        result = methods[action](request)
        if host._coalesce_remote_source_scope:
            # A changed source or grant prevents even a previously assembled
            # result from crossing the response boundary.
            host._check_current_source(force_remote=True)
        outcome = 'returned'
    finally:
        timing = {'contract_version':'boi/native-query-timing@1',
            'request_id':request_id, 'action':action, 'outcome':outcome,
            'native_dispatch_seconds':time.perf_counter()-started,
            'stages':host.timings, 'nested_stage_times_are_not_additive':True,
            'excludes':'MCP transport, external agent and final user delivery'}
        # No questions, SQL, paths, source contents or credentials in the log.
        logging.getLogger(__name__).info('native_query_timing %s', json.dumps(timing))
    return {**result, 'timing':timing}


def check_native_action_permission(principal):
    """Use verified BoI/SSO roles and actual PAT scopes, not request identity."""
    if 'boi.action_invoker' not in principal.roles:
        raise ValueError('NATIVE_QUERY_ACTION_ROLE_REQUIRED')
    if principal.token_id and 'boi.execute.low' not in principal.token_scopes:
        raise ValueError('NATIVE_QUERY_ACTION_TOKEN_SCOPE_REQUIRED')


class NativeQueryRecordStore:
    def __init__(self, evidence):
        self.evidence = evidence

    def put(self, *, principal, connection_digest, value):
        ref, _ = self.evidence.put({'contract_version':'boi/native-query-host-record@1',
            'principal':principal, 'connection_digest':connection_digest, 'value':value})
        return ref

    def read(self, ref, *, principal, connection_digest):
        # path_for verifies the entire digest syntax before any filesystem read.
        path = self.evidence.path_for(ref)
        error = self.evidence.verify(ref, ref.removeprefix('evidence://'))
        if error:
            raise ValueError(error)
        row = json.loads(path.read_bytes())
        if (row.get('contract_version') != 'boi/native-query-host-record@1'
            or row.get('principal') != principal
            or row.get('connection_digest') != connection_digest):
            raise ValueError('NATIVE_QUERY_RECORD_SCOPE_MISMATCH')
        return row['value']


def check_native_source_scope(scope, *, principal, sqlite_path):
    """Check a trusted configured source; counts are budget checks, not answers.

    This does not grant access: the host must also re-read the current Wiki
    definition/profile authority before planning, execution and result reuse.
    """
    scope = NativeReadScope.model_validate(scope)
    if principal != scope.principal:
        raise ValueError('NATIVE_QUERY_PRINCIPAL_MISMATCH')
    path = Path(sqlite_path)
    if sealed_sqlite_digest(path) != scope.source_snapshot_digest:
        raise ValueError('NATIVE_QUERY_SOURCE_CHANGED')

    connection = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    try:
        connection.execute('PRAGMA query_only=ON')
        actual = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not set(scope.allowed_tables) <= actual:
            raise ValueError('NATIVE_QUERY_TABLE_UNAVAILABLE')
        total = 0
        for name in dict.fromkeys(scope.allowed_tables):
            quoted = '"'+name.replace('"', '""')+'"'
            total += connection.execute('SELECT COUNT(*) FROM '+quoted).fetchone()[0]
            if total > scope.max_scan_rows:
                raise ValueError('NATIVE_QUERY_SCAN_BUDGET_EXCEEDED')
    finally:
        connection.close()
    if sealed_sqlite_digest(path) != scope.source_snapshot_digest:
        raise ValueError('NATIVE_QUERY_SOURCE_CHANGED')


class NativeQueryHost:
    """Connect current native semantics to the existing planner; no internal model."""
    def __init__(self, work, authorization, connection):
        from ..governed_runtime.profile_driven_query_runtime import ProfileDrivenQueryRuntime
        from ..governed_runtime.semantic_profile_loader import ActiveReleaseProfileLoader
        from ..governed_runtime.semantic_profile_retrieval import HybridSemanticRetriever
        from ..governed_runtime.query_gateway import QueryGatewayService
        self.work, self.authorization = work, authorization
        self.timings = {}
        self._admitted_bundle = None
        self._coalesce_remote_source_scope = False
        self._remote_scope_checked_this_action = False
        self.connection = NativeQueryConnection.model_validate(connection)
        # Preserve all pre-continuity protected records when the optional
        # deployment binding is absent. An actual binding changes the scope.
        absent = {name for name in ('source_policy_continuity','execution_binding','sqlite_path')
            if getattr(self.connection,name) is None}
        if not self.connection.source_identities:
            absent.add('source_identities')
        if self.connection.selection_capability is None:
            absent.add('selection_capability')
        self.connection_digest = semantic_digest(self.connection.model_dump(mode='json', exclude=absent))
        config = self.connection
        if config.scope.principal != authorization.principal:
            raise ValueError('NATIVE_QUERY_PRINCIPAL_MISMATCH')
        self.evidence = CheckEvidenceStore(Path(config.storage_root)/'plans')
        self.records = NativeQueryRecordStore(self.evidence)
        from ..governed_runtime.protected_execution_repository import ProtectedExecutionRepository
        self.execution_repository = ProtectedExecutionRepository(Path(config.storage_root)/'executions', work.ledger)
        self.query_source = (QuerySourceAction(config.execution_binding,
            principal=authorization.principal, evidence_sink=self.execution_repository.store_binding)
            if config.execution_binding else None)
        self.runtime = ProfileDrivenQueryRuntime(
            profile_loader=ActiveReleaseProfileLoader(work.ledger, work.objects),
            catalog=config.catalog, retriever=HybridSemanticRetriever(),
            intent_synthesizer=None, model_identity_provider=None,
            planning_policy=config.planning_policy,
            gateway=QueryGatewayService(None, schema_release_digest=config.catalog.schema_digest),
            ledger=work.ledger, evidence_store=self.evidence)

    def _measure(self, name, function, *args, **kwargs):
        started = time.perf_counter()
        failed = False
        try:
            return function(*args, **kwargs)
        except BaseException:
            failed = True
            raise
        finally:
            entry = self.timings.setdefault(name, {'calls':0, 'seconds':0.0, 'failures':0})
            entry['calls'] += 1
            entry['seconds'] += time.perf_counter()-started
            entry['failures'] += int(failed)

    def _source_authorization(self):
        continuity = self.connection.source_policy_continuity
        current_reader = getattr(self.work, 'current_knowledge_authorization', None)
        if continuity is None:
            if not callable(current_reader):
                return self.authorization
            from ..governed_runtime.source_intake import SourceIntakeService
            current = current_reader()
            if SourceIntakeService._policy(current) != SourceIntakeService._policy(self.authorization):
                raise ValueError('NATIVE_QUERY_CURRENT_AUTHORIZATION_CHANGED')
            return current
        from ..governed_runtime.source_intake import IntakeAuthorization
        from ..governed_runtime.source_intake_runtime import SourceIntakeRuntimePolicy
        from ..governed_runtime.source_envelope import byte_digest
        if not callable(current_reader):
            raise ValueError('NATIVE_QUERY_CURRENT_AUTHORIZATION_REQUIRED')
        current = current_reader()
        if (current.principal != self.authorization.principal
                or current.policy_digest != continuity.current_policy_digest):
            raise ValueError('NATIVE_QUERY_CURRENT_POLICY_CHANGED')
        try:
            with Path(continuity.policy_path).open('rb') as handle:
                raw = handle.read(65537)
            if len(raw) > 65536 or byte_digest(raw) != continuity.policy_digest:
                raise ValueError('digest')
            previous = SourceIntakeRuntimePolicy.model_validate_json(raw)
        except (OSError, ValueError):
            raise ValueError('NATIVE_QUERY_PREVIOUS_POLICY_INVALID_OR_CHANGED') from None
        now = self.work.intake.clock()
        if now.tzinfo is None or not previous.effective_from <= now < previous.stale_after:
            raise ValueError('NATIVE_QUERY_PREVIOUS_POLICY_STALE')
        # Only an explicit unchanged principal grant is supported. A role-only
        # historical grant cannot be inferred from a new account or role list.
        if (current.principal not in previous.principal_ids
                or set(current.allowed_uses) != set(previous.allowed_uses)
                or current.visibility != previous.visibility
                or current.team_id != previous.team_id):
            raise ValueError('NATIVE_QUERY_SOURCE_GRANT_CHANGED')
        return IntakeAuthorization(current.principal, continuity.policy_digest,
            previous.allowed_uses, previous.visibility, previous.team_id)

    def _check_current_source(self, *, force_remote=False):
        config = self.connection
        source_authorization = self._measure('current_source_grant', self._source_authorization)
        if self.query_source is not None:
            if (self._coalesce_remote_source_scope
                    and self._remote_scope_checked_this_action and not force_remote):
                self._measure('pinned_source_binding', self.query_source.check_scope_binding,
                    config.scope, principal=self.authorization.principal)
            else:
                self._measure('source_integrity', self.query_source.check_scope,
                    config.scope, principal=self.authorization.principal)
                self._remote_scope_checked_this_action = True
        else:
            self._measure('source_integrity', check_native_source_scope, config.scope, principal=self.authorization.principal,
                sqlite_path=config.sqlite_path)
        return source_authorization

    def _read_bundle(self):
        config = self.connection
        source_authorization = self._check_current_source()
        active_pointer = self.work.ledger.active_pointer()
        cache_key = _native_admission_cache_key(self, source_authorization, active_pointer)
        bundle = self._measure('semantic_authority_cache', _read_cached_native_admission, cache_key)
        if bundle is not None:
            self._admitted_bundle = bundle
            return bundle
        bundle = self._measure('semantic_authority', read_native_profile_bundle, self.work, source_authorization,
            review_revision=config.review_revision, profile_revision=config.profile_revision,
            catalog=config.catalog)
        # Do not publish an admission assembled across a concurrent Release
        # switch. Selected records and source bytes were already verified by
        # the admission path; this comparison fences cache publication.
        if self.work.ledger.active_pointer() != active_pointer:
            raise ValueError('NATIVE_QUERY_CURRENT_SCOPE_CHANGED')
        _write_cached_native_admission(cache_key, bundle)
        self._admitted_bundle = bundle
        return bundle

    def _current(self, expected):
        # The current grant and exact source binding are checked at every
        # callback. For a revision-pinned remote source, the action also has
        # full opening and final remote checks. Local SQLite retains its full
        # integrity check at every callback.
        self._check_current_source()
        if self._admitted_bundle is None or self._admitted_bundle != expected:
            raise ValueError('NATIVE_QUERY_CURRENT_SCOPE_CHANGED')

    def _connection(self, request):
        if request.connection_id != self.connection.connection_id:
            raise ValueError('NATIVE_QUERY_CONNECTION_MISMATCH')

    def _selected_source_identities(self, request):
        identities = {item.source_ref:item for item in self.connection.source_identities}
        refs = [item.source_ref for item in request.source_use_constraints]
        if len(set(refs)) != len(refs):
            raise ValueError('NATIVE_SOURCE_USE_CONSTRAINT_DUPLICATE')
        if any(ref not in identities for ref in refs):
            raise ValueError('NATIVE_SOURCE_USE_CONSTRAINT_UNKNOWN')
        # Source-use ownership is the dedicated constraint field.  A business
        # row value may legitimately equal a source label, so lexical equality
        # never changes that value into a source-use instruction.
        return tuple(identities[ref] for ref in refs)

    @staticmethod
    def _source_use_validation(constraints, identities, physical_mappings, *, row_filters=(), planned):
        excluded = {(item.source_id, table) for item in identities for table in item.physical_tables}
        actual = {(item.source_id, item.table) for item in physical_mappings}
        conflicts = sorted(excluded & actual)
        if conflicts:
            raise ValueError('NATIVE_EXCLUDED_SOURCE_USED')
        return {
            'contract_version':'boi/native-source-use-validation@1',
            'constraints':[item.model_dump(mode='json') for item in constraints],
            'source_labels':[{'source_ref':item.source_ref, 'terms':list(item.terms)}
                for item in identities],
            'excluded_lineage':[{'source_id':source_id, 'table':table}
                for source_id,table in sorted(excluded)],
            'actual_lineage':[{'source_id':source_id, 'table':table}
                for source_id,table in sorted(actual)],
            'semantic_ownership':{
                'source_use':'request.source_use_constraints',
                'row_conditions':'request.submission.candidate.filters',
                'row_filter_count':len(row_filters),
                'status':'STRUCTURALLY_SEPARATE'},
            'lineage_status':('VERIFIED_EXCLUDED' if planned else 'NOT_PLANNED'),
        }

    def prepare(self, request):
        request = NativeQueryPrepareRequest.model_validate(request)
        self._connection(request)
        bundle = self._read_bundle()
        selection_capability = self._measure('selection_capability_validation',
            validated_native_selection_capability, bundle, self.connection,
            semantic_digest(self.work.ledger.active_pointer()))
        retrieval, native_input = self._measure('candidate_preparation', self.runtime.prepare_native_reviewed_question,
            request.question, bundle=bundle, validate_current_scope=self._current)
        from .native_query_sources import read_query_definition_context
        definition_context = self._measure('definition_source_context',
            read_query_definition_context, self, bundle, native_input)
        from ..governed_runtime.cardinality_profile_binding import bind_cardinality_profile_contracts
        contracts = self._measure('planning_contract_projection',
            bind_cardinality_profile_contracts, bundle)
        relationship_endpoints = {
            item.contract_id: (item.left_endpoint_ref, item.right_endpoint_ref)
            for item in contracts.relationships
        }
        result_shapes = []
        for item in contracts.result_shapes:
            projected = {k:item.model_dump(mode='json').get(k) for k in (
                'contract_id','shape','root_object_ref','exact_grain','relationship_refs',
                'collection_semantics','aggregation_semantics','null_policy','duplicate_policy','order_policy',
                'limit_policy','completeness_policy','fanout_semantics')}
            required_entities = [item.root_object_ref]
            for relationship_ref in item.relationship_refs:
                for endpoint_ref in relationship_endpoints.get(relationship_ref, ()):
                    if endpoint_ref not in required_entities:
                        required_entities.append(endpoint_ref)
            projected['required_entity_ids'] = required_entities
            projected['filter_scope_contract'] = {
                'root_property': 'DIRECT',
                'related_property': (
                    'ROOT_AND_COLLECTION'
                    if item.shape == 'FlatRelation'
                    else 'QUESTION_DEPENDENT_COLLECTION_SCOPE'
                ),
                'reason': (
                    'A FlatRelation has no separately retained child collection; a related-object '
                    'predicate selects the returned root-relation rows and their related content.'
                    if item.shape == 'FlatRelation'
                    else 'For a nested or linked result, preserve whether the question filters child '
                    'content, root existence, or both.'
                ),
                'related_absence_scope': (
                    'ROOT_ABSENCE' if item.shape == 'NestedCollection' else None
                ),
                'negative_existence_root_rowset': ({
                    'intent_contract_version':'scoped-result-intent-v4',
                    'rowset_object_ids':[item.root_object_ref],
                    'entity_ids':[item.root_object_ref],
                    'property_ids_owner_refs':[item.root_object_ref],
                    'child_filter_scope':'ROOT_ABSENCE',
                } if item.shape == 'NestedCollection' else None),
            }
            result_shapes.append(projected)
        planning_contracts = {
            'contract_version':'boi/native-query-planning-contracts@1',
            'binding_digest':contracts.binding_digest,
            'relationships':[{k:item.model_dump(mode='json').get(k) for k in (
                'contract_id','left_endpoint_ref','right_endpoint_ref','direction','semantic_name',
                'cardinality','optionality','null_policy','orphan_policy','duplicate_policy')}
                for item in contracts.relationships],
            'result_shapes':result_shapes}
        return {'contract_version':'boi/native-query-preparation@1',
            'connection_id':request.connection_id, 'question':request.question,
            'native_input':native_input.model_dump(mode='json'),
            'input_digest':semantic_digest(native_input),
            'submission_schema':NativeIntentSubmission.model_json_schema(),
            'source_use_constraint_schema':NativeSourceUseConstraint.model_json_schema(),
            'source_identities':[item.model_dump(mode='json')
                for item in self.connection.source_identities],
            'selection_capability':selection_capability.model_dump(mode='json'),
            'submission_guidance':{
                'author':'current external agent',
                'scope':'Select logical meanings from native_input; no client SQL or physical plan.',
                'source_use':'When the question constrains which source or view may be used, select its exact source_ref from source_identities in the plan request source_use_constraints. Never translate a source-use constraint into a candidate row filter. The server verifies the selected source against physical lineage.',
                'result_shape':'For a relationship result, select an approved result_shapes entry by semantic root and relationship. Normally copy its required_entity_ids into entity_ids; for a root-only negative-existence result use negative_existence_root_rowset instead. Copy exact_grain into grain exactly. Apply filter_scope_contract to related-object predicates; DIRECT means no scope is needed. For deterministic ordering, emit one item for every order_policy key in the same order, using ASC unless the question requests another permitted direction; do not infer or reorder keys.',
                'grouping':'For a reviewed Aggregate or ScalarAggregate result_shapes entry, use its exact aggregation_semantics.reducer and target_ref in candidate.aggregations. Set candidate.intent_contract_version to scoped-aggregate-v3 whenever candidate.aggregations is nonempty. count_rows targets the root object and counts all rows, while count targets a property and counts non-null values. For scoped aggregates, each group_by must equal both dimensions and grain; scope_object_id is the root object or the target property owner. A blocked reducer is not evidence that all aggregate shapes are absent.',
                'related_absence':'For a requested root with no related records satisfying bounded child predicates, select a reviewed NestedCollection relationship and use ROOT_ABSENCE on every child predicate. Use the selected shape filter_scope_contract.negative_existence_root_rowset for scoped-result-intent-v4, rowset_object_ids and entity_ids; property_ids belong to that root only. Child properties remain available in filters without becoming displayed rowsets. The result establishes absence of matching records only in the authorized snapshot, never a healthy or normal state.',
                'ordering':'ordering selects declared properties; ordering by an aggregate output is not supported by this intent contract.',
                'completion':'Read execution status, complete result sets and quality coverage before answering; preparation is not execution.'},
            'planning_contracts':planning_contracts,
            'retrieval':retrieval.model_dump(mode='json'),
            'semantic_bundle':bundle.model_dump(mode='json'),
            'definition_context':definition_context,
            'source_snapshot_digest':self.connection.scope.source_snapshot_digest,
            'query_execution_status':'not_run', 'status':'PROVISIONAL'}

    def plan(self, request):
        request = NativeQueryPlanRequest.model_validate(request)
        self._connection(request)
        selected_source_identities = self._selected_source_identities(request)
        bundle = self._read_bundle()
        interpretation = self._measure('meaning_validation', self.runtime.interpret_submitted_native_question, request.question,
            submission=request.submission, principal=self.authorization.principal,
            bundle=bundle, validate_current_scope=self._current)
        planned = (self._measure('logical_planning', self.runtime.plan_reviewed_interpretation, interpretation,
            bundle=bundle, catalog=self.connection.catalog, validate_current_scope=self._current)
            if interpretation.status == 'RESOLVED' else None)
        physical_mappings = (planned.physical_binding.physical_mappings
            if planned is not None and planned.physical_binding is not None else ())
        source_use_validation = self._source_use_validation(request.source_use_constraints,
            selected_source_identities, physical_mappings,
            row_filters=request.submission.candidate.filters,
            planned=planned is not None and planned.status == 'READY')
        # A READY plan can still bind a literal to the wrong property or
        # spelling. Probe only submitted string equality values in this same
        # authorized snapshot before the host spends an execution/result turn.
        # Alternatives are evidence for review, never an automatic rewrite.
        diagnostic = (self._filter_value_diagnostic(request.submission.candidate, bundle)
            if planned is not None and planned.status == 'READY'
            and any(item.operator == 'eq' and isinstance(item.value, str)
                    for item in request.submission.candidate.filters) else None)
        value = {'contract_version':'boi/native-query-host-plan@1',
            'request':request.model_dump(mode='json'),
            'interpretation':interpretation.model_dump(mode='json'),
            'planned':planned.model_dump(mode='json') if planned else None,
            'source_use_validation':source_use_validation,
            **({'filter_value_diagnostic':diagnostic}
               if diagnostic is not None and diagnostic['diagnostic_status']
                   == 'possible_binding_mismatch' else {}),
            'query_execution_status':'not_run', 'status':'PROVISIONAL'}
        ref = self._measure('plan_storage', self.records.put, principal=self.authorization.principal,
            connection_digest=self.connection_digest, value=value)
        return {'plan_ref':ref, **value}

    def _gateway_for_plan(self, plan_ref, idempotency_key):
        from ..governed_runtime.profile_driven_query_runtime import ReviewedSemanticPlanOutcome
        from ..governed_runtime.native_query_execution import prepare_native_query_request
        from ..governed_runtime.multi_result_query_gateway import MultiResultSqliteGateway, capture_multi_result_sqlite_schema
        from ..governed_runtime.protected_execution_repository import ProtectedExecutionRepository
        config = self.connection
        record = self.records.read(plan_ref, principal=self.authorization.principal,
            connection_digest=self.connection_digest)
        if record.get('contract_version') != 'boi/native-query-host-plan@1' or not record.get('planned'):
            raise ValueError('NATIVE_READY_PLAN_REQUIRED')
        outcome = ReviewedSemanticPlanOutcome.model_validate(record['planned'])
        recorded_request = NativeQueryPlanRequest.model_validate(record.get('request'))
        selected_source_identities = self._selected_source_identities(recorded_request)
        bundle = self._read_bundle()
        if outcome.planning_context is None or outcome.planning_context.bundle != bundle:
            raise ValueError('NATIVE_QUERY_CURRENT_SCOPE_CHANGED')
        request = prepare_native_query_request(outcome,
            profile_revision=config.profile_revision,
            source_snapshot_digest=config.scope.source_snapshot_digest,
            request_authorization_digest=semantic_digest(config.scope),
            idempotency_key=idempotency_key)
        self._source_use_validation(recorded_request.source_use_constraints,
            selected_source_identities, request.physical_mappings,
            row_filters=recorded_request.submission.candidate.filters, planned=True)
        if request.inline_row_limit > config.scope.max_output_rows:
            raise ValueError('NATIVE_QUERY_OUTPUT_BUDGET_EXCEEDED')
        if any(item.source_id not in config.scope.allowed_sources or item.table not in config.scope.allowed_tables
               for item in request.logical_plan.result_sets):
            raise ValueError('NATIVE_QUERY_TABLE_NOT_AUTHORIZED')
        # Existence filters and relationship context can read tables that do
        # not themselves become an output rowset. The source grant covers all.
        if any(item.source_id not in config.scope.allowed_sources or item.table not in config.scope.allowed_tables
               for item in request.physical_mappings):
            raise ValueError('NATIVE_QUERY_TABLE_NOT_AUTHORIZED')
        def resolve(access):
            self._current(bundle)
            if (access.authority != request.logical_plan.candidate_authority
                or access.logical_plan_digest != request.logical_plan.plan_digest
                or access.parameter_digest != semantic_digest(request.parameters)):
                raise ValueError('NATIVE_QUERY_REQUEST_CHANGED')
            return request.logical_plan.candidate_authority
        schema = (self._measure('physical_schema', self.query_source.capture_schema,
            allowed_tables=config.scope.allowed_tables) if self.query_source is not None else
            self._measure('physical_schema', capture_multi_result_sqlite_schema, Path(config.sqlite_path),
                allowed_tables=config.scope.allowed_tables))
        gateway = MultiResultSqliteGateway(Path(config.sqlite_path) if config.sqlite_path else None, schema=schema,
            source_adapter=self.query_source,
            contract_schema_digest=config.catalog.schema_digest,
            result_artifact_root=Path(config.storage_root)/'results',
            reviewed_authority_resolver=resolve,
            execution_repository=self.execution_repository)
        return gateway, request

    def execute(self, request):
        request = NativeQueryExecuteRequest.model_validate(request)
        self._connection(request)
        gateway, query = self._gateway_for_plan(request.plan_ref, request.idempotency_key)
        execution = self._measure('sql_and_result_storage', gateway.create, query)
        value = {'contract_version':'boi/native-query-host-execution@1',
            'request':request.model_dump(mode='json'), 'execution':execution.model_dump(mode='json'),
            'status':'PROVISIONAL'}
        ref = self.records.put(principal=self.authorization.principal,
            connection_digest=self.connection_digest, value=value)
        return {'execution_ref':ref, **value}

    def result(self, request):
        from ..governed_runtime.native_query_execution import read_native_query_result
        request = NativeQueryResultRequest.model_validate(request)
        self._connection(request)
        record = self.records.read(request.execution_ref, principal=self.authorization.principal,
            connection_digest=self.connection_digest)
        if record.get('contract_version') != 'boi/native-query-host-execution@1':
            raise ValueError('NATIVE_QUERY_EXECUTION_RECORD_REQUIRED')
        original = NativeQueryExecuteRequest.model_validate(record['request'])
        self._connection(original)
        gateway, query = self._gateway_for_plan(original.plan_ref, original.idempotency_key)
        artifact = self._measure('protected_result_read', read_native_query_result, gateway, request=query,
            artifact_ref=record['execution']['receipt']['result_artifact_ref'])
        plans = {item.result_set_id: item for item in query.logical_plan.result_sets}
        actual_sets = artifact.get('result_sets') or []
        if set(plans) != {item.get('result_set_id') for item in actual_sets}:
            raise ValueError('NATIVE_QUERY_RESULT_DISPLAY_SCOPE_MISMATCH')
        display_sets = []
        for item in actual_sets:
            planned = plans[item['result_set_id']]
            fields = [*planned.projections, *planned.aggregations]
            if [field.output_name for field in fields] != [column[0] for column in item['result_schema']]:
                raise ValueError('NATIVE_QUERY_RESULT_DISPLAY_SCHEMA_MISMATCH')
            display_sets.append({'result_set_id': planned.result_set_id,
                'role': planned.role, 'source_id': planned.source_id, 'table': planned.table,
                'columns': [{'output_name': field.output_name,
                    'label': (field.column if field in planned.projections else
                              field.reducer+'('+field.column+')')}
                    for field in fields]})
        return {'contract_version':'boi/native-query-host-result@1',
            'execution_ref':request.execution_ref, 'plan_ref':original.plan_ref,
            'artifact':artifact, 'execution':record['execution'],
            'result_url':native_query_result_url(request),
            'display_sets':display_sets,
            'business_query_executed':False, 'status':'PROVISIONAL'}

    def _filter_value_diagnostic(self, candidate, bundle):
        """Probe bounded filter literals within the current source authority."""
        from ..governed_runtime.native_filter_value_diagnostic import diagnose_empty_filter_values
        self._current(bundle)
        if self.query_source is not None:
            session=self.query_source.open_session(lambda:False)
        else:
            path=Path(self.connection.sqlite_path)
            session=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)
            session.row_factory=sqlite3.Row
            session.execute('PRAGMA query_only=ON')
        try:
            diagnosis=self._measure('filter_value_diagnostic', diagnose_empty_filter_values,
                candidate=candidate,bundle=bundle,scope=self.connection.scope,
                execute=session.execute)
        finally:
            session.close()
        self._current(bundle)
        return diagnosis

    def diagnose_empty(self, request):
        """Offer source-grounded filter alternatives after a verified zero-root read."""
        request=NativeQueryDiagnoseEmptyRequest.model_validate(request)
        self._connection(request)
        observed=self.result(request)
        original=NativeQueryExecuteRequest.model_validate(
            self.records.read(request.execution_ref,principal=self.authorization.principal,
                connection_digest=self.connection_digest)['request'])
        gateway,query=self._gateway_for_plan(original.plan_ref,original.idempotency_key)
        root_ids={item.result_set_id for item in query.logical_plan.result_sets if item.role=='ROOT'}
        roots=[item for item in observed['artifact'].get('result_sets') or []
            if item.get('result_set_id') in root_ids]
        if len(roots)!=1 or roots[0].get('row_count')!=0:
            raise ValueError('NATIVE_EMPTY_ROOT_DIAGNOSIS_NOT_APPLICABLE')
        planned=self.records.read(original.plan_ref,principal=self.authorization.principal,
            connection_digest=self.connection_digest)
        submission=NativeQueryPlanRequest.model_validate(planned['request']).submission
        bundle=self._read_bundle()
        diagnosis=self._filter_value_diagnostic(submission.candidate,bundle)
        return {**diagnosis,
            'contract_version':'boi/native-query-host-empty-diagnostic@1',
            'connection_id':request.connection_id,'execution_ref':request.execution_ref,
            'plan_ref':original.plan_ref,
            'protected_result_digest':observed['artifact']['result_digest'],
            'root_result_set_id':roots[0]['result_set_id']}
