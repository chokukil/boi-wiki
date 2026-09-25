"""Reuse idle PG connections inside one bounded synchronous request.

Each store operation retains its own commit/rollback boundary. This scope holds
no data or authority decisions, and never retries SQL or an uncertain commit.
"""
import asyncio
import os
import sys
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return os.getpid(), threading.get_ident(), task


@dataclass
class _Slot:
    connection: object = None
    borrowed: bool = False


@dataclass
class _Scope:
    owner: tuple
    slots: dict = field(default_factory=dict)
    closed: bool = False


_current = ContextVar('agent_store_connection_scope', default=None)


def _active():
    scope = _current.get()
    return scope if scope and not scope.closed and scope.owner == _owner() else None


@contextmanager
def request_store_connections():
    if _active() is not None:
        yield
        return
    scope = _Scope(_owner())
    token = _current.set(scope)
    try:
        yield
    finally:
        scope.closed = True
        _current.reset(token)
        for slot in scope.slots.values():
            if slot.connection is not None:
                slot.connection.close()
        scope.slots.clear()


@contextmanager
def store_connection(store):
    scope = _active()
    slot = scope.slots.setdefault(store, _Slot()) if scope else None
    # Nested independent operations must not borrow a caller's transaction.
    if slot is None or slot.borrowed:
        with store._connect() as connection:
            yield connection
        return
    from psycopg.pq import TransactionStatus

    connection = slot.connection
    if connection is not None and (connection.closed or
            connection.info.transaction_status != TransactionStatus.IDLE):
        connection.close()
        connection = slot.connection = None
    if connection is None:
        connection = slot.connection = store._connect()
    slot.borrowed = True
    try:
        try:
            yield connection
        except BaseException:
            # Use the driver's rollback/error behavior, without hiding the
            # original exception if rollback itself fails. Discard on failure.
            try:
                connection.__exit__(*sys.exc_info())
            finally:
                connection.close()
                slot.connection = None
            raise
        else:
            try:
                if not connection.closed:
                    connection.commit()
                    connection.autocommit = True
            except BaseException:
                connection.close()
                slot.connection = None
                raise
    finally:
        slot.borrowed = False
