"""Versioned physical time encoding owned by a data-mapping profile.

Logical time semantics do not prove how a physical column stores values.  This
contract permits deterministic comparison only for representations whose value
grammar and clock basis can be checked against the frozen source snapshot.
"""
from __future__ import annotations

from typing import Literal

from .semantic_binding_contract import FrozenContract


class PhysicalTemporalEncoding(FrozenContract):
    contract_version: Literal['boi/physical-temporal-encoding@1']
    representation: Literal['ISO8601_UTC', 'ISO_DATE']
    # Exclusion needs a bound execution filter and an answer disclosure.  Keep
    # v1 fail-closed until that complete forward contract exists.
    null_policy: Literal['BLOCK']


def sqlite_declared_affinity(declared_type: object) -> str:
    """Apply SQLite's ordered declared-type affinity rules."""
    name = str(declared_type or '').upper()
    if 'INT' in name:
        return 'INTEGER'
    if any(value in name for value in ('CHAR', 'CLOB', 'TEXT')):
        return 'TEXT'
    if 'BLOB' in name or not name:
        return 'BLOB'
    if any(value in name for value in ('REAL', 'FLOA', 'DOUB')):
        return 'REAL'
    return 'NUMERIC'


def temporal_encoding_check(
        declared_type: object, logical_type: str,
        encoding: PhysicalTemporalEncoding | dict | None) -> dict[str, object]:
    """Check type/representation compatibility without inspecting source rows."""
    logical = str(logical_type).casefold()
    affinity = sqlite_declared_affinity(declared_type)
    if logical not in {'date', 'datetime'}:
        return {
            'compatible': False,
            'reason_code': (
                'VALUE_TYPE_ENCODING_CONTRACT_MISMATCH'
                if encoding is not None else 'VALUE_TYPE_ENCODING_CONTRACT_REQUIRED'
            ),
        }
    if encoding is None:
        return {
            'compatible': False,
            'reason_code': 'VALUE_TYPE_ENCODING_CONTRACT_REQUIRED',
        }
    try:
        contract = (
            encoding if isinstance(encoding, PhysicalTemporalEncoding)
            else PhysicalTemporalEncoding.model_validate(encoding)
        )
    except ValueError:
        return {
            'compatible': False,
            'reason_code': 'VALUE_TYPE_ENCODING_CONTRACT_INVALID',
        }
    expected = 'ISO_DATE' if logical == 'date' else 'ISO8601_UTC'
    if contract.representation != expected:
        return {
            'compatible': False,
            'reason_code': 'VALUE_TYPE_ENCODING_CONTRACT_MISMATCH',
        }
    if affinity != 'TEXT':
        return {
            'compatible': False,
            'reason_code': 'LOGICAL_PHYSICAL_TYPE_MISMATCH',
        }
    return {'compatible': True, 'reason_code': ''}
