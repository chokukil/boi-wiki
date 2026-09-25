"""Grounded workbook address joins for the existing source-intake harness.

The native agent interprets the guide/header once and supplies this layout.
The engine resolves only declared coordinates; it never infers business meaning
from sheet names, colors, row order, correction labels or parameter strings.
"""
from collections import defaultdict
from pydantic import Field
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract, Ref, semantic_digest


class WorkbookAddressLayout(FrozenContract):
    data_sheet: Ref
    header_row: int = Field(ge=1, strict=True)
    first_data_row: int = Field(ge=1, strict=True)
    last_data_row: int = Field(ge=1, strict=True)
    annotation_sheet: Ref
    annotation_header_row: int = Field(ge=1, strict=True)
    first_annotation_row: int = Field(ge=1, strict=True)
    last_annotation_row: int = Field(ge=1, strict=True)
    row_column: str = Field(pattern=r'^[A-Z]+$')
    column_column: str = Field(pattern=r'^[A-Z]+$')
    fragment_column: str = Field(pattern=r'^[A-Z]+$')
    replacement_column: str = Field(pattern=r'^[A-Z]+$')
    category_column: str = Field(pattern=r'^[A-Z]+$')
    reason_column: str = Field(pattern=r'^[A-Z]+$')
    guide_field_locators: tuple[Ref, ...] = Field(min_length=1)
    address_basis_field: Ref
    address_basis_quote: Ref


def link_workbook_context(records, layout):
    """Retain every correction, including unresolved addresses/value conflicts."""
    layout = WorkbookAddressLayout.model_validate(layout)
    fields = {f['field_locator']: f for row in records for f in row['fields']}
    if len(fields) != sum(len(row['fields']) for row in records):
        raise ValueError('WORKBOOK_CONTEXT_DUPLICATE_FIELD')
    cells = {}
    rows = defaultdict(dict)
    for field in fields.values():
        meta = field.get('structural_metadata')
        if not meta:
            continue
        key = (meta['sheet'], meta['excel_row'], meta['excel_column'])
        if key in cells:
            raise ValueError('WORKBOOK_CONTEXT_DUPLICATE_ADDRESS')
        cells[key] = field
        rows[key[:2]][key[2]] = field
    basis = fields.get(layout.address_basis_field)
    if (basis is None or layout.address_basis_quote not in basis['text']
            or any(ref not in fields for ref in layout.guide_field_locators)):
        raise ValueError('WORKBOOK_CONTEXT_BASIS_NOT_LOCATED')
    if (layout.last_data_row < layout.first_data_row
            or layout.last_annotation_row < layout.first_annotation_row):
        raise ValueError('WORKBOOK_CONTEXT_RANGE_INVALID')
    header = rows.get((layout.data_sheet, layout.header_row))
    annotation_header = rows.get((layout.annotation_sheet, layout.annotation_header_row))
    columns = [layout.row_column, layout.column_column, layout.fragment_column,
        layout.replacement_column, layout.category_column, layout.reason_column]
    if (not header or not annotation_header or len(set(columns)) != len(columns)
            or any(col not in annotation_header for col in columns)):
        raise ValueError('WORKBOOK_CONTEXT_HEADER_INCOMPLETE')
    annotations = []; by_target = defaultdict(list)
    for row_number in range(layout.first_annotation_row, layout.last_annotation_row+1):
        row = rows.get((layout.annotation_sheet, row_number), {})
        if any(col not in row for col in columns):
            raise ValueError('WORKBOOK_CONTEXT_ANNOTATION_INCOMPLETE')
        row_text, column_text = row[layout.row_column]['text'], row[layout.column_column]['text']
        # Excel coordinates are syntax. Non-integer/missing/foreign coordinates
        # stay unresolved; no nearest-row or fuzzy header repair is permitted.
        target = (cells.get((layout.data_sheet, int(row_text), column_text))
            if row_text.isascii() and row_text.isdigit() else None)
        state = ('target_not_found' if target is None else 'reported_value_matches'
            if target['text'] == row[layout.replacement_column]['text'] else 'reported_value_conflicts')
        entry = {'annotation_record_locator': next(iter(row.values()))['record_locator'],
            'target_field_locator': target['field_locator'] if target else None,
            'target_span_ref': target['span_ref'] if target else None,
            'address_fields': [row[layout.row_column]['span_ref'],row[layout.column_column]['span_ref']],
            'fragment_ref':row[layout.fragment_column]['span_ref'],
            'replacement_ref':row[layout.replacement_column]['span_ref'],
            'category_ref':row[layout.category_column]['span_ref'],
            'reason_ref':row[layout.reason_column]['span_ref'],
            'binding_status':state, 'semantic_support_verified':False}
        annotations.append(entry)
        if target:
            by_target[target['record_locator']].append(entry)
    guide = [fields[ref]['span_ref'] for ref in layout.guide_field_locators]
    guide.append(basis['span_ref'])
    common = list(dict.fromkeys([f['span_ref'] for f in header.values()]
        +[f['span_ref'] for f in annotation_header.values()]+guide))
    linked = []
    for row_number in range(layout.first_data_row, layout.last_data_row+1):
        row = rows.get((layout.data_sheet,row_number))
        if row is None:
            raise ValueError('WORKBOOK_CONTEXT_DATA_ROW_MISSING')
        locator = next(iter(row.values()))['record_locator']
        links = by_target.get(locator, [])
        extra = [ref for link in links for ref in [*link['address_fields'], link['fragment_ref'],
            link['replacement_ref'],link['category_ref'],link['reason_ref']]]
        linked.append({'record_locator':locator,'field_refs':[f['span_ref'] for f in row.values()],
            'context_refs':list(dict.fromkeys([*common,*extra])), 'annotations':links})
    return {'layout':layout.model_dump(mode='json'), 'layout_digest':semantic_digest(layout.model_dump(mode='json')),
        'records':linked, 'annotations':annotations,
        'scope':'Source address links only. Correction labels remain source-reported, not approval.',
        'semantic_support_verified':False}


def workbook_interpretation_input(records, linked_context, record_locators):
    """Deliver complete selected rows and their declared context once by reference.

    No source text is truncated or copied into multiple evidence representations.
    Callers must check current source authority before using retained records.
    """
    wanted = set(record_locators)
    linked = [row for row in linked_context['records'] if row['record_locator'] in wanted]
    if len(linked) != len(wanted):
        raise ValueError('WORKBOOK_CONTEXT_SELECTION_NOT_FOUND')
    refs = {ref for row in linked for ref in [*row['field_refs'],*row['context_refs']]}
    fields = {f['span_ref']:f for row in records for f in row['fields'] if f['span_ref'] in refs}
    if refs != fields.keys():
        raise ValueError('WORKBOOK_CONTEXT_FIELD_MISSING')
    return {'records':linked, 'fields':fields, 'layout':linked_context['layout'],
        'complete_source_read':False, 'semantic_support_verified':False}


async def read_workbook_part_context(client, revision, linked_context, *, part_record_locators):
    """One MCP read for a part and its grounded header/annotation dependencies.

    Part membership comes from the retained source inventory and is checked
    against the actual authorized asset; no expected business answer is supplied.
    """
    import json
    locators = set(part_record_locators)
    selected = [row for row in linked_context['records'] if row['record_locator'] in locators]
    extra = list(dict.fromkeys(ref for row in selected for ref in row['context_refs']))
    if len(extra) > 256:
        raise ValueError('WORKBOOK_CONTEXT_PART_EXCEEDS_READ_BOUND')
    stored = await client.read_asset(revision, source_field_refs=extra)
    content = json.loads(stored['asset']['content_json'])
    if (content.get('contract_version') != 'boi/workbook-source-records@1'
            or {row['record_locator'] for row in content['records']} != locators):
        raise ValueError('WORKBOOK_SOURCE_PART_MEMBERSHIP_CHANGED')
    # Only a genuinely paged cell needs another read. Normal header/annotation
    # context travels with the single part read, with no repeated content_json.
    source = stored['sources'][0]
    for field in stored.get('source_field_context', []):
        offset=field.get('next_offset');pieces=[field['text']]
        while offset is not None:
            page=await client.call('boi_source_field',{'reference':source,
                'span_ref':field['span_ref'],'offset':offset,'limit':8192})
            pieces.append(page['text']);next_offset=page.get('next_offset')
            if next_offset is not None and next_offset <= offset:
                raise ValueError('WORKBOOK_CONTEXT_PAGE_STALLED')
            offset=next_offset
        field.update(text=''.join(pieces),next_offset=None,complete_field=True)
    return {'asset_read':stored,'record_context':selected}
