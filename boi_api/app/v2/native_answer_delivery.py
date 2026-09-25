"""Read-only candidate answer presentation on existing Wiki source authority.

Authored citations locate exact text; they do not prove its semantic support.
Stored result display never grants a query or changes Release/admission state.
"""
import html
from html.parser import HTMLParser
from typing import Literal

import markdown
from pydantic import Field

from ..governed_runtime.semantic_binding_contract import FrozenContract,RevisionRef,Ref,Digest
from ..governed_runtime.native_observation import _json
from ..governed_runtime.native_query_answer_review import read_native_query_answer_record
from ..governed_runtime.source_envelope import ArtifactEnvelope
from ..governed_runtime.domain_asset_store import source_manifest_digest


class NativeAnswerCitation(FrozenContract):
    body_start: int=Field(ge=0)
    body_end: int=Field(gt=0)
    source_digest: Digest
    span_ref: Ref
    quote_start: int=Field(ge=0)
    quote_end: int=Field(gt=0)


class NativeAnswerDelivery(FrozenContract):
    contract_version: Literal['boi/native-answer-delivery@1']='boi/native-answer-delivery@1'
    review_revision: RevisionRef
    artifact_revision: RevisionRef
    text_revision: RevisionRef
    citations: tuple[NativeAnswerCitation,...]


class NativeResultCitation(FrozenContract):
    body_start: int=Field(ge=0)
    body_end: int=Field(gt=0)
    result_set_id: Ref


class NativeQualityCitation(FrozenContract):
    body_start: int=Field(ge=0)
    body_end: int=Field(gt=0)
    receipt_digest: Digest


class NativeAnswerDeliveryV2(NativeAnswerDelivery):
    contract_version: Literal['boi/native-answer-delivery@2']='boi/native-answer-delivery@2'
    result_citations: tuple[NativeResultCitation,...]
    quality_citations: tuple[NativeQualityCitation,...] = ()


def bind_result_citations(body,citations,artifact):
    results=(artifact or {}).get('result_sets',[])
    bound=[]
    for raw in citations:
        c=NativeResultCitation.model_validate(raw)
        if not 0<=c.body_start<c.body_end<=len(body) or '\n' in body[c.body_start:c.body_end]:
            raise ValueError('NATIVE_DELIVERY_RESULT_BODY_RANGE_INVALID')
        matches=[r for r in results if r['result_set_id']==c.result_set_id]
        if len(matches)!=1:raise ValueError('NATIVE_DELIVERY_RESULT_NOT_READ_OR_AMBIGUOUS')
        bound.append({**c.model_dump(mode='json'),'result':matches[0]})
    return bound


def bind_quality_citations(body,citations,artifact):
    bound=[]
    for raw in citations:
        c=NativeQualityCitation.model_validate(raw)
        if not 0<=c.body_start<c.body_end<=len(body) or '\n' in body[c.body_start:c.body_end]:
            raise ValueError('NATIVE_DELIVERY_QUALITY_BODY_RANGE_INVALID')
        matches=[q for q in (artifact or {}).get('data_quality',[]) if q['receipt_digest']==c.receipt_digest]
        if len(matches)!=1:raise ValueError('NATIVE_DELIVERY_QUALITY_NOT_READ_OR_AMBIGUOUS')
        bound.append({**c.model_dump(mode='json'),'quality':matches[0]})
    return bound


class NativeSourceAnswerDelivery(FrozenContract):
    contract_version: Literal['boi/native-source-answer-delivery@1']='boi/native-source-answer-delivery@1'
    review_revision: RevisionRef
    citations: tuple[NativeAnswerCitation,...]



class NativeIndependentSourceAnswerDelivery(NativeSourceAnswerDelivery):
    contract_version: Literal['boi/native-source-answer-delivery@2']='boi/native-source-answer-delivery@2'
    definition_review_revision: RevisionRef
    additional_definition_review_revisions: tuple[RevisionRef,...]=Field(default=(),max_length=31)
    review_material: dict
    composition_ref: Digest | None = None
    execution_refs: tuple[Digest,...] = Field(default=(),max_length=64)


def validate_source_identity(sources,reference_sources):
    if source_manifest_digest(sources)!=source_manifest_digest(reference_sources):
        raise ValueError('NATIVE_DELIVERY_SOURCE_MISMATCH')


def bind_citations(body,citations,sources):
    fields={(s['source']['digest'],f['span_ref']):(s,f) for s in sources for f in s['fields']}
    bound=[]
    for raw in citations:
        c=NativeAnswerCitation.model_validate(raw)
        if not 0<=c.body_start<c.body_end<=len(body):
            raise ValueError('NATIVE_DELIVERY_BODY_RANGE_INVALID')
        if '\n' in body[c.body_start:c.body_end]:
            raise ValueError('NATIVE_DELIVERY_INLINE_CLAIM_REQUIRED')
        if (c.source_digest,c.span_ref) not in fields:
            raise ValueError('NATIVE_DELIVERY_SOURCE_NOT_READ')
        source,field=fields[(c.source_digest,c.span_ref)]
        if not 0<=c.quote_start<c.quote_end<=len(field['text']):
            raise ValueError('NATIVE_DELIVERY_QUOTE_RANGE_INVALID')
        parent=field.get('record_locator','')
        context='\n\n'.join(f['field_locator']+'\n'+f['text'] for f in source['fields']
            if not parent or f['span_ref']==field['span_ref'] or f.get('record_locator')==parent
            or f['field_locator']==parent or f['field_locator'].startswith(parent+'/'))
        bound.append({**c.model_dump(mode='json'),'quote':field['text'][c.quote_start:c.quote_end],
            'context':context,'field_locator':field['field_locator']})
    # Equal claim spans may cite several sources; crossing ranges are invalid.
    ranges=sorted(set((c['body_start'],c['body_end']) for c in bound))
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])):
        raise ValueError('NATIVE_DELIVERY_OVERLAPPING_CLAIMS')
    return bound


def restore_delivery_composition_sources(intake,principal,composition_ref,material,sources):
    """Reuse exact protected answer scope without claiming full-source coverage."""
    from .native_composition_result import NativeCompositionRead,read_native_composition
    from .native_composition_sources import restore_reading_descriptors
    from agent_kit.python.boi_native_final_review import composition_review_inputs
    binding=read_native_composition(intake,principal,NativeCompositionRead(
        composition_ref=composition_ref,view='binding',purpose='recorded'))
    composition_review_inputs(binding,material)
    projected=restore_reading_descriptors(intake,principal,
        binding['source_reading_descriptors'],binding['bound_answer'])
    validate_source_identity(sources,tuple(ArtifactEnvelope.model_validate(s['source']) for s in projected))
    return projected,[c['url'] for a in binding['answers'] for c in a['citations']]


def read_native_answer_delivery(intake,principal,request,*,historical=False):
    from .process_review_binding import read_sources
    stored=intake.read_asset(principal,request)
    if stored['asset']['kind']!='pack':raise ValueError('NATIVE_DELIVERY_PACK_REQUIRED')
    content=_json(stored['asset']['content_json'])
    if content.get('contract_version') in ('boi/native-source-answer-delivery@1','boi/native-source-answer-delivery@2'):
        delivery=(NativeIndependentSourceAnswerDelivery if content['contract_version'].endswith('@2') else NativeSourceAnswerDelivery).model_validate(content)
        refs={delivery.review_revision}
        if isinstance(delivery,NativeIndependentSourceAnswerDelivery):
            reviews=(delivery.definition_review_revision,*delivery.additional_definition_review_revisions)
            if len(reviews)!=len(set(reviews)):raise ValueError('NATIVE_DELIVERY_DUPLICATE_DEFINITION_REVIEW')
            refs.update(reviews)
    else:
        delivery=(NativeAnswerDeliveryV2 if content.get('contract_version')=='boi/native-answer-delivery@2' else NativeAnswerDelivery).model_validate(content)
        refs={delivery.review_revision,delivery.artifact_revision,delivery.text_revision}
    if historical and not isinstance(delivery,NativeSourceAnswerDelivery):
        raise ValueError('NATIVE_QUERY_HISTORICAL_DELIVERY_NOT_SUPPORTED')
    deps={RevisionRef.model_validate(d['revision']) for d in stored['asset']['dependencies'] if d['required']}
    if not refs<=deps:raise ValueError('NATIVE_DELIVERY_DEPENDENCIES_REQUIRED')
    auth,work=intake._work(principal)
    sources=tuple(ArtifactEnvelope.model_validate(s) for s in stored['sources'])
    context=work.contexts.validate_reading(authorization=auth,
        revision=RevisionRef.model_validate(stored['definition_reading_ref']),sources=sources,
        require_current=not historical and not isinstance(delivery,NativeIndependentSourceAnswerDelivery))
    if not refs<={a.revision for a in context.assets}:raise ValueError('NATIVE_DELIVERY_INPUTS_NOT_READ')
    projected=None
    authorized_composition_sources=[]
    if isinstance(delivery,NativeIndependentSourceAnswerDelivery):
        from ..governed_runtime.native_source_answer import read_native_independent_source_answer
        from ..governed_runtime.source_field_projection import SourceFieldProjectionService
        projector=SourceFieldProjectionService(intake.source_intake)
        projected=[]
        if delivery.composition_ref is not None:
            projected,authorized_composition_sources=restore_delivery_composition_sources(
                intake,principal,delivery.composition_ref,delivery.review_material,sources)
        selections=delivery.review_material.get('source_read_selections',[])
        if any(s.get('source') not in [v.model_dump(mode='json') for v in sources] for s in selections):
            raise ValueError('NATIVE_DELIVERY_SELECTION_SOURCE_MISMATCH')
        for source in (() if projected else sources):
            reference=source.model_dump(mode='json')
            metadata=[e['field'] for e in delivery.review_material['evidence'] if e['source']==reference]
            selected=[s for s in selections if s['source']==reference]
            if not selected:
                projected.append(projector.restore_fields(authorization=auth,reference=reference,field_metadata=metadata))
                continue
            if len(selected)!=1 or selected[0].get('coverage')!='selected_source_fields':
                raise ValueError('NATIVE_DELIVERY_SELECTION_SCOPE_INVALID')
            selection=selected[0]
            restored=projector.read_selected_fields(authorization=auth,reference=reference,
                manifest_ref=selection['full_manifest_ref'],span_refs=selection['span_refs'])
            if (restored['manifest']['fields']!=metadata
                    or restored['manifest']['total_field_count']!=selection['total_field_count']):
                raise ValueError('NATIVE_DELIVERY_SELECTION_EVIDENCE_MISMATCH')
            projected.append(restored)
        record=read_native_independent_source_answer(work,auth,delivery.review_revision,
            definition_review_revision=delivery.definition_review_revision,material=delivery.review_material,
            additional_definition_review_revisions=delivery.additional_definition_review_revisions,
            sources=projected,historical=historical,execution_refs=delivery.execution_refs,
            _delivery_reading_ref=RevisionRef.model_validate(stored['definition_reading_ref']))
    elif isinstance(delivery,NativeSourceAnswerDelivery):
        from ..governed_runtime.native_source_answer import read_native_source_answer
        record=read_native_source_answer(work,auth,delivery.review_revision,**({'historical':True} if historical else {}))
    else:
        record=read_native_query_answer_record(work,auth,review_revision=delivery.review_revision,
            artifact_revision=delivery.artifact_revision,text_revision=delivery.text_revision)
    validate_source_identity(sources,record['sources'])
    if projected is None:projected=read_sources(intake,principal,sources)
    citations=[c.model_dump(mode='json') for c in delivery.citations]
    bind_citations(record['answer_text']['body_markdown'],citations,projected)
    result_citations=[c.model_dump(mode='json') for c in getattr(delivery,'result_citations',())]
    bind_result_citations(record['answer_text']['body_markdown'],result_citations,record.get('artifact'))
    quality_citations=[c.model_dump(mode='json') for c in getattr(delivery,'quality_citations',())]
    bind_quality_citations(record['answer_text']['body_markdown'],quality_citations,record.get('artifact'))
    return {**record,'authorized_composition_sources':authorized_composition_sources,
        'authorized_composition_ref':getattr(delivery,'composition_ref',None),
        'sources':projected,'citations':citations,'result_citations':result_citations,'quality_citations':quality_citations,
        'stored_review_revision':delivery.review_revision.model_dump(mode='json'),
        'delivery_revision':stored['revision'],'query_reexecuted':False}


def _native_source_link_replacements(view, source_base_url):
    """Reuse only original links accepted by the existing protected source route."""
    from urllib.parse import urlsplit
    from agent_kit.python.boi_markdown_links import rendered_links,rewrite_inline_link_destinations
    origin=(source_base_url or '').rstrip('/')
    parsed=urlsplit(origin)
    revision=view.get('delivery_revision',{}).get('revision_digest')
    if parsed.scheme not in ('http','https') or not parsed.netloc or not revision:return {}
    body=view['answer_text']['body_markdown']
    result_url=origin+'/native-results/'+revision.removeprefix('sha256:')
    replacements={}
    execution_paths={'/native-formulas/'+ref.removeprefix('sha256:')
        for ref in view.get('authorized_execution_refs',[])}
    for number,original in enumerate(rendered_links(body),1):
        route=urlsplit(original)
        if route.path in execution_paths and not route.query and not route.fragment:
            replacements[original]=origin+route.path
            continue
        try:native_answer_source_link(view,number,source_base_url=origin)
        except ValueError:continue
        replacements[original]=(original if original in view.get('authorized_composition_sources',[])
            else result_url+'/sources/'+str(number))
    # Unsupported Markdown layouts keep their existing quote anchors. Do not
    # hide them when the shared destination rewriter cannot preserve the link.
    rewritten=rendered_links(rewrite_inline_link_destinations(body,replacements))
    return {old:new for old,new in replacements.items() if new in rewritten}


def _reviewed_source_group_ranges(view, citations, source_links):
    """Prove redundant quote links from a read independent review, not new judgment.

    Every exact quote for a claim must be covered by its reviewed citation group
    or an explicitly linked supporting unit. Cards and stored bindings remain.
    Incomplete, historical, unreviewed or inconsistent inputs use the old display.
    """
    from agent_kit.python.boi_markdown_links import citation_links
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    try:
        review=view['review'];check=view['independent_review_check']
        material=view['independent_review_material'];output=view['independent_review_output']
        body=view['answer_text']['body_markdown']
        if (view.get('historical') or view.get('current_review_reusable') is not True
                or review.get('reviewer_relationship')!='independent'
                or review.get('disposition')!='supported_with_limits' or review.get('errors')
                or check.get('assessment_complete') is not True or check.get('model_accepts_final') is not True
                or check.get('issues') or material['final_text']!=body
                or view['answer_text'].get('body_digest')!=semantic_digest(body)
                or check.get('material_digest')!=semantic_digest(material)):
            return set()
        segments=check['claim_segments']
        by_segment={s['unit_id']:s for s in segments}
        by_unit={u['unit_id']:u for u in output['units']}
        if (not segments or len(by_segment)!=len(segments) or len(by_unit)!=len(output['units'])
                or by_segment.keys()!=by_unit.keys()):return set()
        for segment in segments:
            if (type(segment['start']) is not int or type(segment['end']) is not int
                    or not 0<=segment['start']<segment['end']<=len(body)
                    or body[segment['start']:segment['end']]!=segment['text']):return set()
        original={}
        for source in view['sources']:
            for field in source['fields']:
                original.setdefault((source['source']['digest'],field['span_ref']),[]).append((source['source'],field))
        catalog={}
        for entry in material['citations']:
            catalog.setdefault(entry['number'],[]).append(entry)

        def group_quotes(unit_id, seen=frozenset()):
            if unit_id in seen:return None
            unit=by_unit[unit_id];segment=by_segment[unit_id]
            if unit['relation']!='supported':return None
            if unit['citation_support']=='via_explanation':
                supports=unit.get('supporting_unit_ids',[])
                if not supports:return None
                groups=[]
                for support in supports:
                    linked=by_unit[support]
                    if linked['purpose']=='source_attribution':continue
                    if linked['citation_support'] not in ('full','scope_bound'):return None
                    quotes=group_quotes(support,seen|{unit_id})
                    if quotes is None:return None
                    groups.extend(quotes)
                return groups or None
            if unit['citation_support'] not in ('full','scope_bound','background'):return None
            numbers=unit['citation_numbers']
            if not numbers or any(n not in catalog for n in numbers):return None
            context=(body if unit['citation_support']=='scope_bound'
                else segment.get('citation_context',segment['text']))
            delivered=citation_links(context,reference_document=body)
            quotes=[]
            for number in numbers:
                for entry in catalog[number]:
                    if not any(url in source_links and url in delivered
                            for url in [entry.get('url'),*(q.get('url') for q in entry.get('quotes',[]))]):return None
                    for quote in entry.get('quotes',[]):
                        binding=quote['binding'];key=(entry['source']['digest'],binding['span_ref'])
                        matches=original.get(key,[])
                        if len(matches)!=1:return None
                        envelope,field=matches[0];start,end=binding['quote_start'],binding['quote_end']
                        if (envelope!=entry['source'] or field['field_locator']!=quote['field_locator']
                                or type(start) is not int or type(end) is not int
                                or not 0<=start<end<=len(field['text'])
                                or field['text'][start:end]!=quote['text']
                                or quote['quote_digest']!=semantic_digest(quote['text'])):return None
                        quotes.append((key,start,end))
            return quotes or None

        def covered(citation, quotes):
            key=(citation['source_digest'],citation['span_ref'])
            cursor=citation['quote_start'];end=citation['quote_end']
            for start,stop in sorted((start,stop) for source,start,stop in quotes if source==key):
                if start>cursor:break
                cursor=max(cursor,stop)
                if cursor>=end:return True
            return False

        groups={}
        for citation in citations:
            groups.setdefault((citation['body_start'],citation['body_end']),[]).append(citation)
        reusable=set()
        for segment in segments:
            bounds=(segment['start'],segment['end'])
            if bounds not in groups:continue
            quotes=group_quotes(segment['unit_id'])
            if quotes and all(covered(c,quotes) for c in groups[bounds]):reusable.add(bounds)
        return reusable
    except (KeyError,TypeError,ValueError):
        return set()


class _SafeHTML(HTMLParser):
    allowed={'p','span','a','strong','em','code','pre','table','thead','tbody','tr','th','td',
             'ul','ol','li','blockquote','h1','h2','h3','h4','br','hr'}
    def __init__(self,source_links=None):
        super().__init__(convert_charrefs=False);self.parts=[];self.source_links=source_links or {}
    def handle_starttag(self,tag,attrs):
        if tag not in self.allowed:return
        safe=[]
        for key,value in attrs:
            if key=='href' and tag=='a' and value and value.startswith('#'):
                safe.append((key,value))
            elif key=='href' and tag=='a' and value in self.source_links:
                safe.append((key,self.source_links[value]))
            elif key=='id' and value and value.startswith('claim-'):
                safe.append((key,value))
        self.parts.append('<'+tag+''.join(' '+k+'="'+html.escape(v,quote=True)+'"' for k,v in safe)+'>')
    def handle_endtag(self,tag):
        if tag in self.allowed:self.parts.append('</'+tag+'>')
    def handle_data(self,data):self.parts.append(html.escape(data))
    def handle_entityref(self,name):self.parts.append('&'+name+';')
    def handle_charref(self,name):self.parts.append('&#'+name+';')


def responsive_answer_tables(sanitized):
    """Use the existing process table layout after source-link sanitization."""
    from agent_kit.python.boi_process_answer_layout import render_table
    class Tables(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.parts=[];self.table=None;self.cell=None
        def emit(self,raw):
            (self.parts if self.table is None else self.table).append(raw)
            if self.cell is not None:self.cell.append(raw)
        def handle_starttag(self,tag,attrs):
            if tag=='table':
                self.table=[];self.headers=[];self.rows=[];self.row=[]
            self.emit(self.get_starttag_text())
            if tag=='tr':self.row=[]
            if tag in ('th','td'):self.cell=[];self.cell_kind=tag
        def handle_endtag(self,tag):
            if tag in ('th','td') and self.cell is not None:
                (self.headers if self.cell_kind=='th' else self.row).append(''.join(self.cell))
                self.cell=None
            self.emit('</'+tag+'>')
            if tag=='tr' and self.row:self.rows.append(self.row)
            if tag=='table':
                valid=self.headers and self.rows and all(len(row)==len(self.headers) for row in self.rows)
                self.parts.append(render_table(self.headers,self.rows) if valid else ''.join(self.table))
                self.table=None
        def handle_data(self,data):self.emit(data)
        def handle_entityref(self,name):self.emit('&'+name+';')
        def handle_charref(self,name):self.emit('&#'+name+';')
    parser=Tables();parser.feed(sanitized);parser.close()
    return ''.join(parser.parts)


def _claim_display_starts(body, ranges):
    """Put return anchors inside parsed content, after Markdown block markers.

    Inserting an HTML span before a list marker changes a list into prose.
    Only the display anchor moves; reviewed body ranges and quotes stay exact.
    Unresolved source layouts retain their original anchor positions.
    """
    from markdown_it import MarkdownIt
    lines=body.splitlines(keepends=True);offsets=[0]
    for line in lines:offsets.append(offsets[-1]+len(line))
    content_starts=[]
    for token in MarkdownIt('commonmark').parse(body):
        if token.type!='inline' or token.map is None or not token.content:continue
        row=token.map[0];first=token.content.split('\n',1)[0]
        if not first or row>=len(lines) or lines[row].count(first)!=1:continue
        content_starts.append((offsets[row],offsets[row]+lines[row].index(first)))
    return {(start,end):next((content for line,content in content_starts
        if line<=start<content<end),start) for start,end in ranges}


def _native_material_cards(view, citations):
    from ..governed_runtime.citation_material_cards import material_source_cards,bound_source_identity
    cards=material_source_cards([{
        'source':bound_source_identity(view['sources'],c['source_digest'],c['span_ref'],c['field_locator']),
        'citation_index':index, 'evidence_role':'source_quote',
        'body_start':c['body_start'], 'body_end':c['body_end'],
        'span_ref':c['span_ref'], 'field_locator':c['field_locator'],
        'quote_start':c['quote_start'], 'quote_end':c['quote_end'],
        **({'citation_url':c['url']} if 'url' in c else {}),
        **({'delivery_revision':view['delivery_revision']} if 'delivery_revision' in view else {})}
        for index,c in enumerate(citations)])
    from .native_definition_sources import source_field_label
    from ..governed_runtime.citation_material_cards import material_identity
    for card in cards:
        reading=next(r for r in view['sources'] if material_identity(r['source'])==material_identity(card['source']))
        reference=card['references'][0]
        field=next(f for f in reading['fields'] if f['span_ref']==reference['span_ref'] and f['field_locator']==reference['field_locator'])
        card['title']=source_field_label(field,source=reading)
    return cards


def _native_material_display(view, citations):
    from ..governed_runtime.citation_material_cards import material_display_groups
    groups=material_display_groups(_native_material_cards(view,citations),len(citations))
    return groups,{i:card['number'] for card in groups for i in card['reference_indices']}


def render_native_answer(view, *, source_base_url=None):
    from .native_definition_sources import source_field_label
    from agent_kit.python.boi_process_answer_layout import RESPONSIVE_TABLE_CSS
    import os
    source_links=_native_source_link_replacements(view,source_base_url if source_base_url is not None
        else os.environ.get('BOI_EXTERNAL_URL'))
    esc=lambda x:html.escape(str(x),quote=True)
    # Opening HTML remains escaped; a bare greater-than character is safe and
    # must remain available to the Markdown parser as a blockquote marker.
    markdown_text=lambda x:html.escape(x,quote=False).replace('&gt;','>')
    source_fields={(s['source']['digest'],f['span_ref']):(s,f)
        for s in view['sources'] for f in s['fields']}
    body=view['answer_text']['body_markdown']
    cites=sorted(bind_citations(body,view['citations'],view['sources']),key=lambda c:(c['body_start'],c['body_end']))
    reused_groups=_reviewed_source_group_ranges(view,cites,source_links)
    material_groups,material_numbers=_native_material_display(view,cites)
    result_cites=bind_result_citations(body,view.get('result_citations',[]),view.get('artifact'))
    quality_cites=bind_quality_citations(body,view.get('quality_citations',[]),view.get('artifact'))
    ranges=sorted(set((c['body_start'],c['body_end']) for c in [*cites,*result_cites,*quality_cites]))
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])):
        raise ValueError('NATIVE_DELIVERY_OVERLAPPING_CLAIMS')
    display_starts=_claim_display_starts(body,ranges)
    parts=[];offset=0;cards=[];result_cards=[];quality_cards=[]
    for index,(start,end) in enumerate(ranges,1):
        display_start=display_starts[(start,end)]
        parts.extend([markdown_text(body[offset:display_start]),'<span id="claim-'+str(index)+'">',markdown_text(body[display_start:end]),'</span>'])
        for c in cites:
            if (c['body_start'],c['body_end'])!=(start,end):continue
            n=len(cards)+1
            source,field=source_fields[(c['source_digest'],c['span_ref'])]
            if (start,end) not in reused_groups:
                parts.append('<a href="#source-'+str(n)+'">['+str(material_numbers[cites.index(c)])+']</a>')
            cards.append('<section data-source-reference id="source-'+str(n)+'" tabindex="-1"><blockquote>'+esc(c['quote'])+'</blockquote>'
                '<p class="meta">'+esc(c['field_locator'])+'</p>'
                '<details data-source-location><summary>원문 위치</summary><code>'+esc(c['field_locator'])+'</code></details>'
                '<details data-source-context><summary>주변 원문 보기</summary><pre>'+esc(c['context'])+'</pre></details>'
                '<a data-answer-return href="#claim-'+str(index)+'">해당 답변으로 돌아가기</a></section>')
        for c in result_cites:
            if (c['body_start'],c['body_end'])!=(start,end):continue
            n=len(result_cards)+1
            parts.append('<a href="#result-evidence-'+str(n)+'">[조회 '+str(n)+']</a>')
            r=c['result'];fields=r['fields']
            headers=''.join('<th>'+esc(f['label'])+'</th>' for f in fields)
            rows=''.join('<tr>'+''.join('<td>'+esc('NULL' if row['values'][f['output_name']] is None else row['values'][f['output_name']])+'</td>' for f in fields)+'</tr>' for row in r['rows'])
            result_cards.append('<section id="result-evidence-'+str(n)+'" tabindex="-1"><h3>보존된 조회 결과 '+str(n)+'</h3><p>전체 '+esc(r['total_row_count'])+'행 · '+('일부 행만 표시됨' if r['truncated'] else '잘림 없음')+'</p><table><thead><tr>'+headers+'</tr></thead><tbody>'+rows+'</tbody></table><a data-result-answer-return href="#claim-'+str(index)+'">해당 답변으로 돌아가기</a></section>')
        for c in quality_cites:
            if (c['body_start'],c['body_end'])!=(start,end):continue
            n=len(quality_cards)+1;q=c['quality']
            parts.append('<a href="#quality-evidence-'+str(n)+'">[검사 '+str(n)+']</a>')
            labels={'scanned_rows':'검사한 행','matched_rows':'연결된 행','unmatched_rows':'연결되지 않은 행','null_fk_rows':'참조 값이 NULL인 행','orphan_rows':'참조 대상이 없는 행','duplicate_key_rows':'중복 키 행','excluded_rows':'제외된 행'}
            rows=''.join('<tr><th>'+label+'</th><td>'+esc(q[key])+'</td></tr>' for key,label in labels.items())
            scope=q.get('directional_scope') or {}
            context='\n'.join(str(key)+': '+str(value) for key,value in scope.items())
            quality_cards.append('<section id="quality-evidence-'+str(n)+'" tabindex="-1"><h3>보존된 관계 품질 검사 '+str(n)+'</h3><table><tbody>'+rows+'</tbody></table><details><summary>검사 범위 보기</summary><pre>'+esc(context)+'</pre></details><a data-quality-answer-return href="#claim-'+str(index)+'">해당 답변으로 돌아가기</a></section>')
        offset=end
    parts.append(markdown_text(body[offset:]))
    sanitizer=_SafeHTML(source_links);sanitizer.feed(markdown.markdown(''.join(parts),extensions=['tables','fenced_code']))
    review=view['review']
    labels={'supported_with_limits':'근거 범위 내 뒷받침됨','needs_revision':'수정 필요','unknown':'판단 유보'}
    review_summary=esc(('독립 검토: ' if review.get('reviewer_relationship')=='independent'
        else '동일 세션 검토: ')+labels[review['disposition']])
    notes=''.join('<li>'+esc(x)+'</li>' for x in (*review['findings'],*review['limitations'],*review['errors']))
    tables=[]
    artifact=view.get('artifact')
    for result in (artifact or {}).get('result_sets',[]):
        fields=result['fields']
        headers=''.join('<th>'+esc(f['label'])+'</th>' for f in fields)
        rows=''.join('<tr>'+''.join('<td>'+esc('NULL' if row['values'][f['output_name']] is None else row['values'][f['output_name']])+'</td>' for f in fields)+'</tr>' for row in result['rows'])
        role={'ROOT':'대상 행','AGGREGATE':'집계 행','SCALAR':'전체 집계'}.get(result['role'],result['role'])
        tables.append('<section data-recorded-query-result><h3>'+esc(role)+'</h3><p>전체 '+esc(result['total_row_count'])+'행 · '+('일부 행만 표시됨' if result['truncated'] else '잘림 없음')+'</p><table><thead><tr>'+headers+'</tr></thead><tbody>'+rows+'</tbody></table></section>')
    grouped_cards=[]
    for card in material_groups:
        c=cites[card['reference_indices'][0]]
        source,field=source_fields[(c['source_digest'],c['span_ref'])]
        grouped_cards.append('<article data-source-card><h3>['+str(card['number'])+'] '+esc(card.get('title') or source_field_label(field,source=source))+'</h3>'+''.join(cards[i] for i in card['reference_indices'])+'</article>')
    history_notice=('<p class="status" data-historical-answer>이전 개정의 답변입니다. 정의가 변경되어 현재 요청에는 다시 검토해야 합니다. 아래 원문과 검토 의견은 당시 기록입니다.</p>' if view.get('historical') else '')
    status='저장된 스냅샷 답변' if artifact else '저장된 원문 설명'
    evidence_link='보존된 조회 행과 검토 의견 확인' if artifact else '원문 설명의 검토 의견 확인'
    snapshot='<p>스냅샷 '+esc(artifact['execution']['source_snapshot_digest'])+'</p>' if artifact else ''
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>근거와 함께 읽는 답변</title><style>*{box-sizing:border-box}body{font-family:system-ui;margin:0 auto;padding:24px;max-width:960px;overflow-wrap:anywhere;line-height:1.7;color:#18232d}p,th,td,pre,.meta{overflow-wrap:anywhere}table{table-layout:fixed;border-collapse:collapse;width:100%;font-size:.94em}th,td{padding:8px;border-bottom:1px solid #ccd4dc;text-align:left}pre{white-space:pre-wrap}a{color:#075ba5}section{margin:30px 0;padding:16px;background:#f4f7fa}blockquote{margin:12px 0;padding-left:14px;border-left:3px solid #537d9d}.status{background:#fff3d6;padding:12px}.meta{font-size:.82em;color:#536473}details{margin:12px 0}span[id]{scroll-margin-top:24px}'+RESPONSIVE_TABLE_CSS+'</style>'
        '<body>'+history_notice+'<main data-native-answer-body>'+responsive_answer_tables(''.join(sanitizer.parts))+'</main>'
        '<p><a href="#query-evidence">'+evidence_link+'</a></p>'
        '<details id="query-evidence"><summary>PROVISIONAL · '+status+' · '+review_summary+'</summary>'
        '<p>새 조회나 운영 승인이 아닙니다.</p>'+snapshot
        +''.join(tables)+
        '<ul>'+notes+'</ul><p class="meta">'+esc(view['stored_review_revision']['ref'])+'</p></details>'
        '<h2>답변에 연결된 원문</h2>'+''.join(grouped_cards)+''.join(result_cards)+''.join(quality_cards)+'</body></html>')


def _native_source_groups(view, cards, source_links):
    """Reference existing exact quote cards from the protected displayed links.

    This is a lossless navigation projection of retained citation material, not
    reuse of a review verdict or proof of support for a different request.
    Missing or partial bindings remain unresolved rather than becoming a
    whole-page citation. No original text is duplicated in this projection.
    """
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    material=view.get('independent_review_material',{})
    body=view['answer_text']['body_markdown']
    if (material.get('final_text')!=body
            or view['answer_text'].get('body_digest')!=semantic_digest(body)
            or view.get('independent_review_check',{}).get('material_digest')!=semantic_digest(material)):
        return []
    original={}
    for source in view['sources']:
        for field in source['fields']:
            original.setdefault((source['source']['digest'],field['span_ref']),[]).append((source['source'],field))
    by_quote={}
    for number,c in enumerate(cards,1):
        key=(c['source_digest'],c['span_ref'])
        by_quote.setdefault(key,[]).append((number,c['quote_start'],c['quote_end']))
    groups=[];scope_cache={}
    for target,url in source_links.items():
        entries=[entry for entry in material.get('citations',[]) if entry.get('url')==target]
        references=[];scopes=[];valid=bool(entries)
        for entry in entries:
            if entry.get('role')=='source_scope':
                from agent_kit.python.boi_process_answer_v2 import source_scope_reference
                matches=[s for s in view['sources'] if s['source']==entry['source']]
                if len(matches)!=1:valid=False;break
                source=matches[0]
                key=source['source']['digest']
                if key not in scope_cache:
                    scope_cache[key]=source_scope_reference({'source':source['source'],'manifest':source['manifest'],
                        'reading_digest':semantic_digest(source),'fields':{f['field_locator']:f for f in source['fields']}})
                expected=scope_cache[key]
                if entry.get('quotes') or entry.get('reading_scope')!=expected:valid=False;break
                scope={'source':source['source'],'reading_scope':expected}
                if scope not in scopes:scopes.append(scope)
                continue
            if not entry.get('quotes'):valid=False;break
            for quote in entry['quotes']:
                binding=quote.get('binding',{})
                key=(entry['source']['digest'],binding.get('span_ref'))
                matches=original.get(key,[])
                if len(matches)!=1:valid=False;break
                envelope,field=matches[0]
                start,end=binding.get('quote_start'),binding.get('quote_end')
                if (envelope!=entry['source'] or field.get('field_locator')!=quote.get('field_locator')
                        or type(start) is not int or type(end) is not int
                        or not 0<=start<end<=len(field.get('text',''))
                        or field['text'][start:end]!=quote.get('text')
                        or semantic_digest(quote['text'])!=quote.get('quote_digest')):
                    valid=False;break
                number=next((n for n,a,b in by_quote.get(key,[]) if a<=start<end<=b),None)
                if number is None:
                    # The displayed source can include surrounding original
                    # evidence beyond the answer's claim cards. Keep its exact
                    # original range, without inventing a new answer claim.
                    ref={'source_digest':key[0],'span_ref':key[1],
                        'quote_start':start,'quote_end':end}
                else:ref={'citation_number':number,'quote_start':start,'quote_end':end}
                if ref not in references:references.append(ref)
            if not valid:break
        if valid and (references or scopes):
            group={'url':url,'quotes':references}
            if scopes:group['source_scopes']=scopes
            if target in view.get('authorized_composition_sources',[]):
                # This reference came from the protected composition read, not
                # from an arbitrary URL or the previous reviewer's opinion.
                ref=view.get('authorized_composition_ref')
                if not ref:continue
                group['composition_ref']=ref
            groups.append(group)
    return groups


def native_answer_message(view, *, source_base_url=None):
    """Present the same authorized answer and anchors as the existing Wiki page.

    Stored question fit is deliberately not inferred by this read operation.
    Rendering/binding checks are not semantic or scientific approval.
    """
    from urllib.parse import urlsplit
    digest=view['delivery_revision']['revision_digest'].removeprefix('sha256:')
    path='/native-results/'+digest
    origin=(source_base_url or '').rstrip('/')
    parsed=urlsplit(origin)
    url=origin+path if parsed.scheme in ('http','https') and parsed.netloc else path
    body=view['answer_text']['body_markdown']
    source_links=_native_source_link_replacements(view,origin)
    cites=sorted(bind_citations(body,view['citations'],view['sources']),key=lambda c:(c['body_start'],c['body_end']))
    reused_groups=_reviewed_source_group_ranges(view,cites,source_links)
    material_groups,material_numbers=_native_material_display(view,cites)
    results=bind_result_citations(body,view.get('result_citations',[]),view.get('artifact'))
    quality=bind_quality_citations(body,view.get('quality_citations',[]),view.get('artifact'))
    ranges=sorted(set((c['body_start'],c['body_end']) for c in [*cites,*results,*quality]))
    if any(a[1]>b[0] for a,b in zip(ranges,ranges[1:])):
        raise ValueError('NATIVE_DELIVERY_OVERLAPPING_CLAIMS')
    parts=[];offset=0;cards=[];result_cards=[];quality_cards=[]
    for start,end in ranges:
        parts.append(body[offset:end])
        for entries, bound, anchor, label in (
            (cites,cards,'source',''), (results,result_cards,'result-evidence','조회 '),
            (quality,quality_cards,'quality-evidence','검사 ')):
            for c in entries:
                if (c['body_start'],c['body_end'])!=(start,end):continue
                n=len(bound)+1
                target=url+'#'+anchor+'-'+str(n)
                bound.append({**{k:v for k,v in c.items() if k!='context'},'url':target,
                    **({'context_url':target} if 'context' in c else {}),'authored_claim':body[start:end],
                    'claim_context':'historical_answer' if view.get('historical') else 'stored_answer',
                    'semantic_support_verified':False})
                if anchor!='source' or (start,end) not in reused_groups:
                    parts.append(' ['+label+str(material_numbers[cites.index(c)] if anchor=='source' else n)+']('+target+')')
        offset=end
    parts.append(body[offset:])
    from agent_kit.python.boi_markdown_links import rewrite_inline_link_destinations
    display_text=rewrite_inline_link_destinations(''.join(parts),source_links)
    source_cards=_native_material_cards(view,cards)
    from agent_kit.python.boi_recipient_citations import recipient_access, access_notice
    from agent_kit.python.boi_markdown_links import rendered_links
    access=recipient_access(rendered_links(display_text))
    display_text+=access_notice(access)
    return {'contract_version':'boi/native-answer-message@1',
        'question':view['answer_text'].get('question'), 'readable_text':display_text,
        'recipient_citation_access':access,
        'citations':cards, 'source_cards':source_cards, 'source_groups':_native_source_groups(view,cards,source_links),
        'result_citations':result_cards, 'quality_citations':quality_cards,
        'result_url':url, 'delivery_revision':view['delivery_revision'],
        'current_request_fulfilled':None, 'query_reexecuted':False,
        'semantic_truth_proven':False}


def saved_answer_delivery_message(view, *, source_base_url=None):
    """Normal delivery: one answer and its actual links, with protected detail.

    The full message builder remains the evidence view. This is a display
    projection after current access/dependency/source validation, not a cache or
    weaker review. Do not make the host re-author repeated claim/source cards.
    """
    from agent_kit.python.boi_markdown_links import rendered_links
    message=native_answer_message(view,source_base_url=source_base_url)
    links=_native_source_link_replacements(view,source_base_url)
    original_sources={c['url'] for c in message['citations']}
    source_urls=set(links.values()) | original_sources
    actual=list(dict.fromkeys(rendered_links(message['readable_text'])))
    compact={k:v for k,v in message.items() if k not in (
        'citations','source_groups','result_citations','quality_citations')}
    compact['citations']=[{'url':url} for url in actual if url in source_urls]
    compact['evidence_delivery']='protected_detail'
    compact['evidence_read']={'tool':'boi_native_answer','arguments':{
        'revision':message['delivery_revision'],'view':'binding'},
        'scope':'Exact claim ranges, original quotations and recorded result evidence for this same revision; normal delivery needs no repeated read.'}
    return compact


def compact_source_contexts(citations):
    """Lossless transport projection; source identity is part of context identity."""
    refs={};contexts=[];compact=[]
    for citation in citations:
        if 'context' not in citation:
            compact.append(dict(citation))
            continue
        key=(citation['source_digest'],citation['context'])
        if key not in refs:
            ref='source-context-'+str(len(refs)+1)
            refs[key]=ref
            contexts.append({'context_ref':ref,'source_digest':key[0],'text':key[1]})
        compact.append({**{k:v for k,v in citation.items() if k!='context'},'context_ref':refs[key]})
    return compact,contexts


def read_native_answer_for_request(intake,principal,request,*,source_base_url=None,evidence_detail=False):
    """A changed dependency is a re-planning outcome, not a reusable answer."""
    try:
        view=read_native_answer_delivery(intake,principal,request)
    except ValueError as error:
        if str(error)!='DOMAIN_CONTEXT_SELECTED_REVISION_CHANGED':raise
        # Reauthorize before exposing even the namespace used for discovery.
        stored=intake.read_asset(principal,request)
        history={}
        if _json(stored.get('asset',{}).get('content_json','{}')).get('contract_version') in ('boi/native-source-answer-delivery@1','boi/native-source-answer-delivery@2'):
            prior=native_answer_message(read_native_answer_delivery(intake,principal,request,historical=True),source_base_url=source_base_url)
            citations,contexts=compact_source_contexts(prior['citations'])
            history={'historical_sources':citations,'source_contexts':contexts,'historical_result_url':prior['result_url']}
        return {**history,'contract_version':'boi/native-answer-message@1',
            'status':'requires_revalidation','reason_code':str(error),
            'delivery_revision':stored['revision'],'current_request_fulfilled':False,
            'previous_review_reusable':False,'query_reexecuted':False,
            'available_actions':[{'tool':'boi_knowledge_catalog',
                'arguments':{'namespace':stored['namespace']},
                'purpose':'Read current definitions and evidence to answer the current request; do not repeat the stale answer read.'}]}
    return (native_answer_message if evidence_detail else saved_answer_delivery_message)(view,source_base_url=source_base_url)


def read_native_answer_page(intake,principal,request):
    """Display immutable source history without changing execution authority."""
    try:
        return read_native_answer_delivery(intake,principal,request)
    except ValueError as error:
        if str(error)!='DOMAIN_CONTEXT_SELECTED_REVISION_CHANGED':raise
        stored=intake.read_asset(principal,request)
        if _json(stored['asset']['content_json']).get('contract_version') not in ('boi/native-source-answer-delivery@1','boi/native-source-answer-delivery@2'):raise
        return read_native_answer_delivery(intake,principal,request,historical=True)


def native_answer_source_link(view, number, *, source_base_url):
    """Resolve an original source link through the same authorized answer revision."""
    from urllib.parse import urlsplit
    from agent_kit.python.boi_markdown_links import rendered_links
    links=rendered_links(view['answer_text']['body_markdown'])
    if not 1 <= number <= len(links):
        raise ValueError('NATIVE_ANSWER_SOURCE_LINK_NOT_FOUND')
    target=links[number-1]
    parsed=urlsplit(target);origin=urlsplit(source_base_url or '')
    if (parsed.scheme not in ('http','https') or parsed.netloc!=origin.netloc
            or parsed.scheme!=origin.scheme or parsed.username or parsed.password
            or not (parsed.path.startswith('/native-definitions/')
                or target in view.get('authorized_composition_sources',[]))):
        raise ValueError('NATIVE_ANSWER_SOURCE_LINK_NOT_LOCAL_SOURCE')
    return target


def native_result_revision_from_page_ref(page_ref: str, *, source_base_url: str | None) -> RevisionRef | None:
    """Resolve only this Wiki's exact result address, without granting read authority.

    The normal result reader still checks asset type, current dependencies and
    principal access. Fragments identify positions within that same result.
    """
    digest = native_page_digest(page_ref, source_base_url=source_base_url, route='/native-results/')
    return RevisionRef(ref='KnowledgeRevision:' + digest, revision_digest=digest) if digest else None


def native_page_digest(page_ref: str, *, source_base_url: str | None, route: str) -> str | None:
    """Parse an exact server-owned result route; the result reader still authorizes it."""
    from urllib.parse import urlsplit
    if not page_ref or any(ord(char) <= 32 or ord(char) == 127 for char in page_ref):
        return None
    try:
        parsed = urlsplit(page_ref)
        origin = urlsplit(source_base_url or '')
        if parsed.scheme or parsed.netloc:
            if (parsed.scheme not in ('http', 'https')
                    or parsed.scheme != origin.scheme or parsed.netloc != origin.netloc
                    or parsed.username or parsed.password or origin.username or origin.password):
                return None
        if parsed.query or not parsed.path.startswith(route):
            return None
        digest = parsed.path.removeprefix(route)
        return RevisionRef(ref='KnowledgeRevision:sha256:' + digest,
                           revision_digest='sha256:' + digest).revision_digest
    except ValueError:
        return None
