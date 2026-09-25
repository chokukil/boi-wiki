"""Exact original reading scope of a retained answer, separate from a definition.

Only protected composition records supply descriptors. No source text is copied
into them; original spans remain in the existing source projection store.
"""
import copy
from ..governed_runtime.semantic_binding_contract import semantic_digest


def source_reading_descriptors(sources):
    descriptors=[]
    for source in sources:
        value=copy.deepcopy(source)
        for field in value['fields']:
            if isinstance(field.get('text'),str):field.pop('text')
        descriptors.append({'reading_digest':semantic_digest(source),'projection':value})
    return descriptors


def validate_reading_descriptors(descriptors,sources,bound):
    if descriptors!=source_reading_descriptors(sources):
        raise ValueError('NATIVE_COMPOSITION_RECORDED_SCOPE_CHANGED')
    if [d['reading_digest'] for d in descriptors]!=bound['source_reading_digests']:
        raise ValueError('NATIVE_COMPOSITION_RECORDED_SCOPE_NOT_BOUND')


def restore_reading_descriptors(intake,principal,descriptors,bound,*,available_sources=()):
    from .domain_intake import SourceFieldReadRequest
    # Current source access and original field integrity are enforced by the
    # normal field reader. Historical evidence needs no new meaning evaluation.
    sources=[]
    for descriptor in descriptors:
        source=copy.deepcopy(descriptor['projection'])
        for field in source['fields']:
            if 'text' in field:continue
            matches=[f for s in available_sources if s['source']==source['source'] for f in s['fields']
                if {k:v for k,v in f.items() if k!='text'}==field and isinstance(f.get('text'),str)]
            if matches and all(f==matches[0] for f in matches):
                field['text']=matches[0]['text'];continue
            offset=0;parts=[]
            while True:
                page=intake.read_field(principal,SourceFieldReadRequest(reference=source['source'],
                    span_ref=field['span_ref'],offset=offset,limit=8192))
                parts.append(page['text'])
                if page['next_offset'] is None:break
                if page['next_offset']<=offset:raise ValueError('NATIVE_COMPOSITION_SOURCE_PAGE_INVALID')
                offset=page['next_offset']
            field['text']=''.join(parts)
        sources.append(source)
    validate_reading_descriptors(descriptors,sources,bound)
    return sources


def recorded_scope_catalog(sources,binding):
    """A short result link can expose its own reading, never another record's."""
    from .native_answer_composition import bound_reading_scopes
    descriptors=binding.get('source_reading_descriptors')
    if descriptors is None:return []
    # An evaluator may have read a superset. Reconstruct only the fields that
    # this answer read; neither the supplied superset nor a sibling definition
    # enlarges that recorded scope.
    selected=[]
    for descriptor in descriptors:
        source=copy.deepcopy(descriptor['projection'])
        for field in source['fields']:
            if 'text' in field:continue
            matches=[f for s in sources if s['source']==source['source'] for f in s['fields']
                if {k:v for k,v in f.items() if k!='text'}==field and isinstance(f.get('text'),str)]
            if len(matches)!=1:raise ValueError('NATIVE_COMPOSITION_RECORDED_SCOPE_CHANGED')
            field['text']=matches[0]['text']
        selected.append(source)
    validate_reading_descriptors(descriptors,selected,binding['bound_answer'])
    scopes=bound_reading_scopes(binding['bound_answer'],selected)
    return [{'source':copy.deepcopy(source['source']),'scope':scope}
        for source,scope in zip(selected,scopes)]


def render_answer_reading_scope(sources,scopes,*,available_sources=()):
    from html import escape
    from .native_definition_sources import source_field_label,source_quote_html,field_anchor
    html='<details data-answer-reading-scope><summary>이 답변에서 실제로 읽은 원문 범위</summary>'
    html+='<p>여러 항목을 함께 읽은 답변의 범위입니다. 개별 정의의 전체 범위나 자료 전체의 정보 부재를 뜻하지 않습니다.</p>'
    for source,scope in zip(sources,scopes):
        html+='<p>실제로 읽은 '+str(len(scope['field_inventory']))+'개 항목</p>'
        for field in source['fields']:
            anchor=field_anchor(source['source']['digest'],field['span_ref'])
            if any(s['source']==source['source'] and field in s['fields'] for s in available_sources):
                html+='<p><a href="#'+escape(anchor)+'">'+escape(source_field_label(field,source=source))+'</a></p>'
                continue
            html+='<article><h3>'+escape(source_field_label(field,source=source))+'</h3>'
            html+=(source_quote_html(field['text']) if isinstance(field.get('text'),str)
                else '<p>값이 없는 원문 항목</p>')+'</article>'
    return html+'</details>'
