"""Authorized, immutable workbook image navigation; no OCR or cell-row inference.

This read-only path does not change existing cell projections or create evidence
spans. It returns exact embedded bytes with their package location and anchors.
An agent's visual transcription remains an authored interpretation, not a parsed
cell or a source-fidelity qualification.
"""
import base64
import io
import posixpath
from zipfile import ZipFile, BadZipFile
from xml.etree import ElementTree as ET
from typing import Literal

from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract, semantic_digest
from .source_envelope import ArtifactEnvelope, byte_digest
from .source_field_projection import SourceFieldProjectionService
from .spreadsheet_source_projection import XLSX

S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
D='http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing'
A='http://schemas.openxmlformats.org/drawingml/2006/main'


class SourceImageReadRequest(FrozenContract):
    reference: ArtifactEnvelope
    operation: Literal['list', 'read'] = 'list'
    image_ref: str | None = Field(default=None, min_length=1, max_length=120)
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=50, ge=1, le=100, strict=True)

    @model_validator(mode='after')
    def selection(self):
        if ((self.operation=='list' and self.image_ref is not None)
                or (self.operation=='read' and (self.image_ref is None or self.offset!=0 or self.limit!=50))):
            raise ValueError('SOURCE_IMAGE_SELECTION_INVALID')
        return self


def _target(owner, target):
    # Only package-local relationships; never follow network or filesystem URLs.
    if not target or '\\' in target or ':' in target or '?' in target or '#' in target:
        raise ValueError('SOURCE_IMAGE_RELATIONSHIP_INVALID')
    path=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(owner),target))
    if not path.startswith('xl/') or path.startswith('xl/../'):
        raise ValueError('SOURCE_IMAGE_RELATIONSHIP_INVALID')
    return path


def workbook_images(raw):
    try:
        with ZipFile(io.BytesIO(raw)) as package:
            infos=package.infolist();names={i.filename for i in infos}
            if len(infos)>4096 or len(names)!=len(infos) or sum(i.file_size for i in infos)>33554432:
                raise ValueError('SOURCE_IMAGE_PACKAGE_SIZE_LIMIT')
            def xml(path):
                data=package.read(path)
                if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
                    raise ValueError('SOURCE_IMAGE_XML_DECLARATION_FORBIDDEN')
                return ET.fromstring(data)
            def rels(owner):
                path=posixpath.join(posixpath.dirname(owner),'_rels',posixpath.basename(owner)+'.rels')
                if path not in names:return {}
                result={}
                for e in xml(path):
                    key=e.attrib['Id']
                    if key in result:raise ValueError('SOURCE_IMAGE_DUPLICATE_RELATIONSHIP')
                    result[key]=dict(e.attrib)
                return result
            def internal(owner, relation):
                if relation.get('TargetMode')=='External':
                    raise ValueError('SOURCE_IMAGE_EXTERNAL_RELATIONSHIP')
                return _target(owner,relation['Target'])
            anchors={};book='xl/workbook.xml';br=rels(book)
            for sheet in xml(book).findall(f'{{{S}}}sheets/{{{S}}}sheet'):
                sp=internal(book,br[sheet.attrib[f'{{{R}}}id']]);sr=rels(sp)
                for drawing in xml(sp).findall(f'{{{S}}}drawing'):
                    dp=internal(sp,sr[drawing.attrib[f'{{{R}}}id']]);dr=rels(dp)
                    for index,anchor in enumerate(xml(dp)):
                        for blip in anchor.findall(f'.//{{{A}}}blip'):
                            if f'{{{R}}}link' in blip.attrib:
                                raise ValueError('SOURCE_IMAGE_EXTERNAL_RELATIONSHIP')
                            target=internal(dp,dr[blip.attrib[f'{{{R}}}embed']])
                            if not target.startswith('xl/media/'):
                                raise ValueError('SOURCE_IMAGE_MEDIA_LOCATION_INVALID')
                            record={'sheet':sheet.attrib['name'],'sheet_part':sp,'drawing_part':dp,
                                'anchor_index':index,'anchor_kind':anchor.tag.rsplit('}',1)[-1],
                                'anchor_xml':ET.tostring(anchor,encoding='unicode'),
                                'coordinate_basis':'OOXML zero-based drawing anchor; not depicted data row'}
                            for end in ['from','to']:
                                point=anchor.find(f'{{{D}}}{end}')
                                if point is not None:record[end]={c.tag.rsplit('}',1)[-1]:int(c.text) for c in point}
                            anchors.setdefault(target,[]).append(record)
            items=[]
            for path in sorted(names):
                if not path.startswith('xl/media/') or path.endswith('/'):continue
                info=package.getinfo(path)
                if info.file_size>8388608:raise ValueError('SOURCE_IMAGE_BYTE_LIMIT')
                data=package.read(path)
                media=('image/png' if data.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if data.startswith(b'\xff\xd8\xff') else None)
                descriptor={'package_part':path,'content_digest':byte_digest(data),'byte_length':len(data),
                    'media_type':media,'read_supported':media is not None,'anchors':anchors.get(path,[])}
                descriptor['image_ref']='source-image:'+semantic_digest({'workbook_digest':byte_digest(raw),**descriptor})
                items.append((descriptor,data))
            if set(anchors)-{d['package_part'] for d,_ in items}:
                raise ValueError('SOURCE_IMAGE_RELATIONSHIP_TARGET_MISSING')
            return items
    except (BadZipFile,ET.ParseError,KeyError,TypeError,ValueError,OverflowError) as error:
        code=str(error)
        if not code.startswith('SOURCE_IMAGE_') or len(code)>100:code='SOURCE_IMAGE_WORKBOOK_INVALID'
        raise ValueError(code) from None


class SourceImageReadService:
    def __init__(self,intake):self.intake=intake

    def transcribe(self, *, authorization, request):
        from .source_image_transcription import transcribe
        return transcribe(self, authorization=authorization, request=request)

    def read(self,*,authorization,request):
        request=SourceImageReadRequest.model_validate(request)
        reference=request.reference.model_dump(mode='json')
        raw,artifact=SourceFieldProjectionService(self.intake)._authorize(authorization,reference,model_input=True)
        if artifact.payload['media_type']!=XLSX:raise ValueError('SOURCE_IMAGE_MEDIA_TYPE_UNSUPPORTED')
        items=workbook_images(raw)
        result={'contract_version':'boi/source-image-read@1','reference':reference,
            'source_revision_digest':reference['digest'],'source_role':reference['role'],
            'policy_digest':authorization.policy_digest,'employee_id':authorization.principal,
            'rights_record_ref':artifact.payload['rights_record_ref'],
            'semantic_status':'not_evaluated','source_fidelity':'not_evaluated',
            'cell_alignment':'not_inferred','source_observation_time':'unknown',
            'publication_changed':False,'source_or_projection_changed':False}
        if request.operation=='list':
            if request.offset>len(items):raise ValueError('SOURCE_IMAGE_PAGE_RANGE_INVALID')
            end=min(len(items),request.offset+request.limit)
            return {**result,'images':[d for d,_ in items[request.offset:end]],'total_images':len(items),
                'offset':request.offset,'next_offset':end if end<len(items) else None,
                'coverage':'xl/media package parts; no interpretation of screenshot contents'}
        selected=next(((d,data) for d,data in items if d['image_ref']==request.image_ref),None)
        if selected is None:raise ValueError('SOURCE_IMAGE_REFERENCE_MISMATCH')
        descriptor,data=selected
        if not descriptor['read_supported']:raise ValueError('SOURCE_IMAGE_ENCODING_UNSUPPORTED')
        return {**result,'image':descriptor,'encoding':'base64','content_b64':base64.b64encode(data).decode('ascii'),
            'complete_image':True,'transformations':[]}
