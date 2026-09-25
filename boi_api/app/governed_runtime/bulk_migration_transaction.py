"""Transient write set for the existing AgentV2 migration repository.

This is not a persisted store or an independent ledger. Publication happens only
through the shared store's all-or-nothing compare-and-write primitive.
"""
from copy import deepcopy
from ..v2.atomic_store_contract import AtomicWrite


def without_storage_timestamp(value):
    return {key: item for key, item in (value or {}).items() if key != 'updated_at'}


class MigrationWriteSet:
    def __init__(self, store):
        self.store = store
        self.before = {}
        self.after = {}

    def get(self, collection, key):
        index = (collection, key)
        if index in self.after:
            return deepcopy(self.after[index])
        if index not in self.before:
            self.before[index] = self.store.get(collection, key)
        return deepcopy(self.before[index])

    def put(self, collection, key, value):
        self.get(collection, key)
        self.after[(collection, key)] = deepcopy(value)
        return deepcopy(value)

    def list(self, *args, **kwargs):
        return self.store.list(*args, **kwargs)

    def writes(self, *, exclude=(), fences=()):
        writes = {
            index: AtomicWrite(*index, self.before[index], value)
            for index, value in self.after.items()
            if index not in exclude and (self.before[index] is None or
                without_storage_timestamp(self.before[index]) != without_storage_timestamp(value))
        }
        for index in fences:
            if index not in writes:
                value = self.get(*index)
                if value is None:
                    raise ValueError('ATOMIC_REQUIRED_FENCE_MISSING')
                writes[index] = AtomicWrite(*index, self.before[index], value)
        return tuple(writes.values())
