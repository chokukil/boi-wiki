"""Structural source-field values shared by local and server parsers."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProjectedField:
    locator: str
    record_locator: str
    state: str
    value_kind: str
    text: str
    presence_basis: str = 'field_present'
    structural_metadata: dict | None = None


def _pointer(path):
    return ''.join('/' + str(p).replace('~', '~0').replace('/', '~1') for p in path)
