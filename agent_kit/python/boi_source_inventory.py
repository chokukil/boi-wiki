"""Local source inventory with explicit source/answer/annotation separation.

Layouts are supplied by the pack or an external reader after inspecting the
source. Headers, colors, filenames and sample identities never select roles.
This module preserves bytes/coordinates; it neither interprets nor publishes.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal
from zipfile import ZipFile
import io
import json

from pydantic import Field, model_validator

from boi_api.app.governed_runtime.semantic_binding_contract import (
    Digest, FrozenContract, Ref, semantic_digest,
)
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.spreadsheet_source_projection import workbook_fields


FieldRole = Literal['source', 'provided_model_answer', 'review_note', 'metadata', 'unassigned']


class WorkbookRegion(FrozenContract):
    sheet: Ref
    first_row: int = Field(ge=1, le=1048576, strict=True)
    last_row: int = Field(ge=1, le=1048576, strict=True)
    columns: tuple[str, ...] = Field(min_length=1)
    role: FieldRole
    reason: Ref

    @model_validator(mode='after')
    def coordinates(self):
        if self.last_row < self.first_row or self.last_row - self.first_row > 100000:
            raise ValueError('SOURCE_INVENTORY_ROW_RANGE_INVALID')
        if len(set(self.columns)) != len(self.columns):
            raise ValueError('SOURCE_INVENTORY_DUPLICATE_COLUMN')
        for value in self.columns:
            if not value or not value.isascii() or not value.isalpha() or not value.isupper():
                raise ValueError('SOURCE_INVENTORY_COLUMN_INVALID')
            number = 0
            for char in value:
                number = number * 26 + ord(char) - ord('A') + 1
            if number > 16384:
                raise ValueError('SOURCE_INVENTORY_COLUMN_INVALID')
        return self


class WorkbookInventoryLayout(FrozenContract):
    contract_version: Literal['boi/workbook-inventory-layout@1'] = 'boi/workbook-inventory-layout@1'
    source_digest: Digest
    regions: tuple[WorkbookRegion, ...] = Field(min_length=1, max_length=1000)
    interpretation_basis: Ref


def inventory_workbook(raw: bytes, layout: WorkbookInventoryLayout | dict) -> dict:
    """Create a byte-bound local inventory; no source or server writes occur."""
    layout = WorkbookInventoryLayout.model_validate(layout)
    if byte_digest(raw) != layout.source_digest:
        raise ValueError('SOURCE_INVENTORY_DIGEST_MISMATCH')
    fields = workbook_fields(raw)
    if sum((r.last_row - r.first_row + 1) * len(r.columns) for r in layout.regions) > 100000:
        raise ValueError('SOURCE_INVENTORY_DECLARED_CELL_LIMIT')
    sheets = {f.structural_metadata.get('sheet') for f in fields if f.structural_metadata}
    if any(r.sheet not in sheets for r in layout.regions):
        raise ValueError('SOURCE_INVENTORY_SHEET_MISSING')
    for index, a in enumerate(layout.regions):
        for b in layout.regions[index + 1:]:
            if (a.sheet == b.sheet and max(a.first_row, b.first_row) <= min(a.last_row, b.last_row)
                    and set(a.columns).intersection(b.columns)):
                raise ValueError('SOURCE_INVENTORY_ROLE_OVERLAP')

    entries = []
    observed = set()
    for field in fields:
        meta = field.structural_metadata or {}
        region = next((r for r in layout.regions
            if meta.get('sheet') == r.sheet and r.first_row <= meta.get('excel_row', -1) <= r.last_row
            and meta.get('excel_column') in r.columns), None)
        if 'cell' in meta:
            observed.add((meta['sheet'], meta['excel_row'], meta['excel_column']))
        entries.append({
            'field_locator': field.locator, 'record_locator': field.record_locator,
            'role': region.role if region else 'unassigned',
            'role_reason': region.reason if region else 'No declared role for this field.',
            'state': field.state, 'value_kind': field.value_kind, 'text': field.text,
            'text_digest': byte_digest(field.text.encode('utf-8')), 'structural_metadata': meta,
        })
    missing = []
    for region in layout.regions:
        if (region.last_row - region.first_row + 1) * len(region.columns) > 100000:
            raise ValueError('SOURCE_INVENTORY_REGION_SIZE_LIMIT')
        for row in range(region.first_row, region.last_row + 1):
            for column in region.columns:
                if (region.sheet, row, column) not in observed:
                    missing.append({'sheet': region.sheet, 'cell': f'{column}{row}',
                                    'role': region.role, 'state': 'not_serialized'})
                    if len(missing) > 100000:
                        raise ValueError('SOURCE_INVENTORY_MISSING_LIMIT')

    media = []
    with ZipFile(io.BytesIO(raw)) as package:
        for info in sorted(package.infolist(), key=lambda i: i.filename):
            if info.filename.startswith('xl/media/') and not info.is_dir():
                media.append({'package_path': info.filename, 'bytes': info.file_size,
                              'digest': byte_digest(package.read(info)),
                              'role': 'unassigned', 'meaning_status': 'not_interpreted',
                              'row_correspondence': 'not_established'})
    roles = Counter(e['role'] for e in entries)
    records = {role: len({e['record_locator'] for e in entries
                        if e['role'] == role and 'cell' in e['structural_metadata']}) for role in roles}
    result = {
        'contract_version': 'boi/local-source-inventory@1',
        'source_digest': layout.source_digest, 'layout': layout.model_dump(mode='json'),
        'field_count': len(entries), 'role_field_counts': dict(roles),
        'role_record_counts': records, 'fields': entries, 'missing_declared_cells': missing,
        'media': media, 'semantic_support_verified': False, 'publication_state': 'local_only',
    }
    return {**result, 'inventory_digest': semantic_digest(result)}


def write_inventory_bundle(inventory: dict, destination: Path) -> dict:
    """Separate supplied answers from authoring input; refuse to overwrite work.

    These are local organization boundaries, not independent evaluation or OS
    access isolation. The original workbook remains necessary for layout/media.
    """
    material = {k: v for k, v in inventory.items() if k != 'inventory_digest'}
    if inventory.get('inventory_digest') != semantic_digest(material):
        raise ValueError('SOURCE_INVENTORY_INTEGRITY_MISMATCH')
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    files = {}
    for role in sorted({e['role'] for e in inventory['fields']}):
        if role not in ('source', 'provided_model_answer', 'review_note', 'metadata', 'unassigned'):
            raise ValueError('SOURCE_INVENTORY_ROLE_INVALID')
        path = destination / (role + '.jsonl')
        text = ''.join(json.dumps(e, ensure_ascii=False, allow_nan=False) + '\n'
                       for e in inventory['fields'] if e['role'] == role)
        path.write_text(text, encoding='utf-8')
        files[role] = {'path': path.name, 'digest': byte_digest(text.encode('utf-8'))}
    manifest = {k: v for k, v in inventory.items() if k != 'fields'}
    manifest['role_files'] = files
    manifest['authoring_roles'] = ['source', 'metadata']
    manifest['provided_answers_are_truth_evidence'] = False
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest
