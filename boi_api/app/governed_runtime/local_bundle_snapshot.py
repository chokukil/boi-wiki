"""Reuse immutable metadata within one request, with a live stored hash per read.

Authority, existing source/revision access and final CAS are deliberately outside
this cache. Tokens have no meaning outside the store/request that supplied them.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps

from .local_bundle_contract import LocalBundleManifest
from ..v2.store_connections import request_store_connections


def _immutable(*args, **kwargs):
    raise TypeError('LOCAL_BUNDLE_SNAPSHOT_IMMUTABLE')


class _Object(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _immutable

    def __deepcopy__(self, memo):
        return self


class _Array(list):
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = _immutable
    __iadd__ = __imul__ = _immutable

    def __deepcopy__(self, memo):
        return self


def _freeze(value):
    if isinstance(value, dict):
        return _Object((key, _freeze(item)) for key, item in value.items())
    if isinstance(value, list):
        return _Array(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass
class _Snapshot:
    key: tuple
    row: dict | None = None
    fingerprint: str | None = None
    binding_verified: bool = False
    manifest: object = None


_current = ContextVar('local_bundle_request_snapshot', default=None)


def _key(service, authorization, bundle_ref):
    return (id(service), authorization.principal, authorization.policy_digest, bundle_ref)


def with_bundle_snapshot(operation):
    @wraps(operation)
    def execute(self, *, authorization, bundle_ref, **kwargs):
        key = _key(self.service, authorization, bundle_ref)
        active = _current.get()
        token = None if active is not None and active.key == key else _current.set(_Snapshot(key))
        try:
            with request_store_connections():
                return operation(self, authorization=authorization, bundle_ref=bundle_ref, **kwargs)
        finally:
            if token is not None:
                _current.reset(token)
    return execute


def read_bundle_snapshot(service, authorization, bundle_ref):
    """Return a live-checked immutable row and whether its binding was verified."""
    active = _current.get()
    if (active is None or active.key != _key(service, authorization, bundle_ref)
            or not callable(getattr(service.store, 'read_snapshot', None))
            or not callable(getattr(service.store, 'read_fingerprint', None))):
        return service.store.get('knowledge_local_bundles', bundle_ref), False
    if active.row is not None:
        fingerprint = service.store.read_fingerprint('knowledge_local_bundles', bundle_ref)
        if fingerprint is not None and fingerprint == active.fingerprint:
            return active.row, active.binding_verified
    row, fingerprint = service.store.read_snapshot('knowledge_local_bundles', bundle_ref)
    active.row, active.fingerprint = _freeze(row), fingerprint
    active.binding_verified, active.manifest = False, None
    return active.row, False


def verified_bundle_binding(service, row):
    active = _current.get()
    if active is not None and active.key[0] == id(service) and active.row is row:
        active.binding_verified = True


def bundle_manifest(service, row):
    active = _current.get()
    if active is not None and active.key[0] == id(service) and active.row is row and active.binding_verified:
        if active.manifest is None:
            active.manifest = LocalBundleManifest.model_validate(row['manifest'])
        return active.manifest
    return LocalBundleManifest.model_validate(row['manifest'])
