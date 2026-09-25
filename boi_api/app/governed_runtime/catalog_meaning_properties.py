"""Exact properties of existing evidence owners, shared by native domains.

These postings expand and order candidates. They neither interpret words nor
filter away unknown, conflicting or merely lexically discovered meanings.
"""
import math
from typing import Literal

from pydantic import Field, field_validator

from .semantic_binding_contract import FrozenContract, semantic_digest


class MeaningPropertyQuery(FrozenContract):
    owner_pointer: str = Field(default='*', max_length=512)
    field_pointer: str = Field(max_length=512)
    value: object
    basis: Literal['explicit', 'inferred']

    @field_validator('owner_pointer', 'field_pointer')
    @classmethod
    def pointer(cls, value, info):
        if info.field_name == 'owner_pointer' and value == '*':
            return value
        if not value.startswith('/') or any(
                part[i] == '~' and (i + 1 == len(part) or part[i + 1] not in '01')
                for part in value.split('/') for i in range(len(part))):
            raise ValueError('DOMAIN_MEANING_PROPERTY_POINTER_INVALID')
        return value

    @field_validator('value')
    @classmethod
    def scalar(cls, value):
        if value is not None and type(value) not in (str, int, float, bool):
            raise ValueError('DOMAIN_MEANING_PROPERTY_SCALAR_REQUIRED')
        if (isinstance(value, str) and len(value) > 2000 or
                type(value) is float and not math.isfinite(value) or
                type(value) is int and value.bit_length() > 256):
            raise ValueError('DOMAIN_MEANING_PROPERTY_VALUE_LIMIT')
        return value


def scalar_fields(value, pointer=''):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from scalar_fields(child, pointer + '/' + key.replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from scalar_fields(child, pointer + '/' + str(index))
    elif pointer and (value is None or type(value) in (str, int, float, bool)):
        if not isinstance(value, str) or len(value) <= 2000:
            yield pointer, value


def property_key(owner, field, value):
    # JSON scalar identity keeps Pa/pa, numbers/strings and null distinct.
    return semantic_digest([owner, field, value])


def add_properties(index, head_key, meanings):
    keys = set()
    for entry in meanings:
        node = entry['node']
        owner = node['target_pointer']
        for field, value in scalar_fields(node['value']):
            for selector in (owner, '*'):
                key = property_key(selector, field, value)
                posting = index['properties'].setdefault(key, {})
                owners = posting.setdefault(head_key, [])
                if owner not in owners:
                    owners.append(owner)
                keys.add(key)
    return sorted(keys)


def find_properties(index, queries, visible_groups, target_keys=None):
    for number, query in enumerate(queries):
        key = property_key(query.owner_pointer, query.field_pointer, query.value)
        for head_key, owners in index['properties'].get(key, {}).items():
            if ((target_keys is None or head_key in target_keys) and
                    index['documents'][head_key]['group'] in visible_groups):
                yield head_key, number, owners
