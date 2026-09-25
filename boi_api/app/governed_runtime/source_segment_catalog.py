"""Versioned lexical source spans, without sentence meaning or entity inference."""
import re
from .semantic_binding_contract import semantic_digest
from .source_envelope import byte_digest

SOURCE_SEGMENT_POLICY='boi/source-segment-catalog@1'


def source_segment_catalog(payload):
    segments=[]
    fields=[field for span in payload['evidence_spans'] for field in span['fields']]
    for field_index,field in enumerate(fields):
        text=field['text'];start=0;start_byte=0
        # Whitespace after terminal punctuation or line breaks separates spans.
        # This is only a lexical partition. Full source fields remain available.
        boundaries=[(m.start(),m.end()) for m in re.finditer(r'(?<=[.!?。！？])\s+|\n+',text)]
        for end,next_start in [*boundaries,(len(text),len(text))]:
            selected=text[start:end]
            end_byte=start_byte+len(selected.encode())
            if selected.strip():
                segments.append({'segment_index':len(segments),'field_index':field_index,
                    'start_byte':start_byte,'end_byte':end_byte,
                    'text':selected})
            start_byte=end_byte+len(text[end:next_start].encode())
            start=next_start
    body={'contract_version':SOURCE_SEGMENT_POLICY,
        'field_digests':[byte_digest(field['text'].encode()) for field in fields], 'segments':segments}
    return {**body,'catalog_digest':semantic_digest(body)}


def select_source_segment(payload,catalog,start_index,end_index=None):
    end_index=start_index if end_index is None else end_index
    if (type(start_index) is not int or type(end_index) is not int or
        not 0<=start_index<=end_index<len(catalog['segments'])):
        raise ValueError('SOURCE_READING_SEGMENT_OUTSIDE_INPUT')
    first,last=catalog['segments'][start_index],catalog['segments'][end_index]
    if first['field_index']!=last['field_index']:
        raise ValueError('SOURCE_READING_SEGMENT_RANGE_CROSSES_FIELD')
    fields=[field for span in payload['evidence_spans'] for field in span['fields']]
    raw=fields[first['field_index']]['text'].encode()
    return {'segment_index':start_index,'end_segment_index':end_index,'field_index':first['field_index'],
        'start_byte':first['start_byte'],'end_byte':last['end_byte'],
        'text':raw[first['start_byte']:last['end_byte']].decode()}
