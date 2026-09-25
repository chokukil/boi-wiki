"""Synthetic helper closure for focused MCP release validation."""
import io


from zipfile import ZipFile


def workbook():
    output=io.BytesIO()
    with ZipFile(output,'w') as z:
        z.writestr('xl/workbook.xml','''<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="raw" sheetId="1" r:id="rId1"/></sheets></workbook>''')
        z.writestr('xl/_rels/workbook.xml.rels','''<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>''')
        z.writestr('xl/worksheets/sheet1.xml','''<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>reading</t></is></c><c r="B1" t="inlineStr"><is><t>reading</t></is></c></row><row r="2"><c r="A2" t="n" s="3"><v>0.1234567890123456789</v></c><c r="B2" t="inlineStr"><is><t>0+H3</t></is></c><c r="C2" t="n"/><c r="D2"><f>A2*2</f><v>9</v></c></row></sheetData></worksheet>''')
        z.writestr('xl/comments/comment1.xml','<comments><text>Uncertain source reading</text></comments>')
    return output.getvalue()
