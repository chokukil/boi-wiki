"""OOXML cell preservation, without interpreting headers, colors or row order.

The immutable XLSX owns styles, layout and complete package history. Evidence
uses sheet/cell coordinates, typed original scalar text and source annotations.
Formula cached values are distinct from expressions and are never recalculated.
"""
import io
import json
import posixpath
import re
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET

XLSX='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def workbook_fields(raw):
    from .source_field_value import ProjectedField,_pointer
    try:
        with ZipFile(io.BytesIO(raw)) as package:
            infos=package.infolist()
            if (len(infos)>4096 or len({i.filename for i in infos})!=len(infos)
                    or sum(i.file_size for i in infos)>33554432):
                raise ValueError('SOURCE_PROJECTION_WORKBOOK_SIZE_LIMIT')
            def xml(path):
                data=package.read(path)
                if b'<!DOCTYPE' in data or b'<!ENTITY' in data:
                    raise ValueError('SOURCE_PROJECTION_XML_DECLARATION_FORBIDDEN')
                return ET.fromstring(data)
            def rich(element):
                if element is None:return ''
                return ''.join(t.text or '' for t in [*element.findall('s:t',NS),*element.findall('s:r/s:t',NS)])
            shared=([rich(e) for e in xml('xl/sharedStrings.xml').findall('s:si',NS)]
                if 'xl/sharedStrings.xml' in package.namelist() else [])
            book=xml('xl/workbook.xml')
            relationships={e.attrib['Id']:e.attrib for e in xml('xl/_rels/workbook.xml.rels')}
            fields=[];seen_sheets=set()
            for sheet in book.findall('s:sheets/s:sheet',NS):
                name=sheet.attrib['name']
                if name in seen_sheets:raise ValueError('SOURCE_PROJECTION_DUPLICATE_SHEET')
                seen_sheets.add(name)
                rel=relationships[sheet.attrib[REL]]
                if rel.get('TargetMode')=='External':raise ValueError('SOURCE_PROJECTION_EXTERNAL_SHEET')
                target=rel['Target']
                path=posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
                if not path.startswith('xl/'):raise ValueError('SOURCE_PROJECTION_SHEET_PATH_INVALID')
                tree=xml(path);seen=set()
                for row in tree.findall('s:sheetData/s:row',NS):
                    for cell in row.findall('s:c',NS):
                        address=cell.attrib['r']
                        match=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',address)
                        if not match or address in seen:raise ValueError('SOURCE_PROJECTION_CELL_ADDRESS_INVALID')
                        seen.add(address)
                        if len(fields)>=100000:raise ValueError('SOURCE_PROJECTION_CELL_COUNT_LIMIT')
                        value=cell.find('s:v',NS);formula=cell.find('s:f',NS)
                        raw_value=None if value is None else (value.text or '')
                        kind=cell.get('t','n')
                        if kind=='s':
                            index=int(raw_value)
                            if not 0<=index<len(shared):raise ValueError('SOURCE_PROJECTION_SHARED_STRING_INVALID')
                            text=shared[index];value_kind='string'
                        elif kind=='inlineStr':text=rich(cell.find('s:is',NS));value_kind='string'
                        else:
                            text=raw_value or ''
                            value_kind={'n':'number','b':'boolean','e':'error','str':'string','d':'date'}.get(kind)
                            if value_kind is None:raise ValueError('SOURCE_PROJECTION_CELL_TYPE_UNSUPPORTED')
                        metadata={'sheet':name,'cell':address,'excel_row':int(match[2]),
                            'excel_column':match[1],'ooxml_type':kind,'style_ref':cell.get('s','0'),
                            'sheet_state':sheet.get('state','visible')}
                        if formula is not None:
                            metadata.update(formula_attributes=dict(formula.attrib),cached_value=raw_value,
                                cached_value_currentness='not_verified')
                            text=formula.text or '';value_kind='formula'
                        state='empty' if text=='' else 'present'
                        fields.append(ProjectedField(_pointer(('sheets',name,'cells',address)),
                            _pointer(('sheets',name,'rows',int(match[2]))),state,value_kind,text,
                            'serialized_ooxml_cell',metadata))
                # Explicit package metadata preserves annotations and guides
                # without inferring that a style or adjacency is a business rule.
                for component in ('dimension','mergeCells','cols','sheetViews'):
                    element=tree.find('s:'+component,NS)
                    if element is not None:
                        fields.append(ProjectedField(_pointer(('sheets',name,'layout',component)),
                            _pointer(('sheets',name,'layout')),'present','xml',ET.tostring(element,encoding='unicode')))
            for info in infos:
                if info.filename=='xl/styles.xml' or (info.filename.startswith('xl/') and 'comments' in info.filename.lower() and info.filename.endswith('.xml')):
                    fields.append(ProjectedField(_pointer(('package',info.filename)),_pointer(('package',)),
                        'present','xml',ET.tostring(xml(info.filename),encoding='unicode')))
            return tuple(fields)
    except (BadZipFile,ET.ParseError,KeyError,TypeError,ValueError,OverflowError) as error:
        code=str(error)
        if not code.startswith('SOURCE_PROJECTION_') or len(code)>100:
            code='SOURCE_PROJECTION_WORKBOOK_INVALID'
        raise ValueError(code) from None
