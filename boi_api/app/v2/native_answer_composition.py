"""Native request composition using the existing typed statement/meaning binder."""
from pydantic import Field,model_validator
from .native_composition_sources import source_reading_descriptors
from ..governed_runtime.semantic_binding_contract import FrozenContract,RevisionRef,Digest
from .domain_intake import DomainAssetReadRequest
from .process_review_binding import RequestSourceReader
from .native_definition_sources import field_anchor
from .native_formula_timing import timed_call, stage_timing
from agent_kit.python.boi_process_answer_v2 import MeaningCitation,ProcessAnswerDraftV2,bind_process_answers_v2,meaning_citation_targets
from agent_kit.python.boi_process_answer_layout import render_layout


class DefinitionSourcePages(dict):
    """Navigation for authorized definitions sharing an original artifact.

    The default dictionary remains usable by historical single-page callers.
    Meaning references resolve by definition revision; literal fields resolve by
    the source record they belong to. Neither rule infers a business relation.
    """
    def __init__(self):
        super().__init__()
        self.definitions={}
        self.owners={}
        self.revisions={}

    def register(self,revision,sources,url,field_refs):
        self.definitions[revision['revision_digest']]={s['digest']:url for s in sources}
        self.revisions[url]=revision
        for source in sources:
            digest=source['digest']
            self.setdefault(digest,url)
            self.owners.setdefault(digest,[]).append((url,field_refs))

    def for_meaning(self,revision):
        return self.definitions.get(revision['revision_digest'],{})

    def for_binding(self,binding):
        candidates=[url for url,refs in self.owners.get(binding['source_revision_digest'],[])
            if refs is None or binding['span_ref'] in refs]
        if not candidates:raise ValueError('ANSWER_SOURCE_PAGE_FIELD_UNAVAILABLE')
        return candidates[0]

    def for_scope(self,digest):
        return list(dict.fromkeys(url for url,_ in self.owners.get(digest,[])))

    def scope_fields(self,digest,url):
        owners=[refs for page,refs in self.owners.get(digest,[]) if page==url]
        if not owners or any(refs is None for refs in owners):return None
        return set().union(*owners)


def binding_source_page(pages,binding):
    return (pages.for_binding(binding) if isinstance(pages,DefinitionSourcePages)
        else pages.get(binding['source_revision_digest']))


from .published_answer_meaning import PublishedMeaningSelection


class NativeAnswerComposition(FrozenContract):
    published_meaning_uses: tuple[PublishedMeaningSelection,...] = Field(default=(),max_length=32,
        exclude_if=lambda v:not v,
        description='Exact current Published explain qualification references. Never filter qualifications. '
            'Each selected meaning retains its complete conditions and declared dependency closure.')
    definition_review_revision: RevisionRef | None=None
    source_definition_revisions: tuple[RevisionRef,...]=Field(default=(),max_length=32,
        description='Exact discovered definitions used only to locate their original records when no usable meaning review is available. '
            'Used alone or as original-evidence supplements to separately reviewed definitions. These records bind original quotations, reading scopes and actual execution results; '
            'it never admits candidate meanings as reviewed evidence.')
    additional_definition_review_revisions: tuple[RevisionRef,...]=Field(default=(),max_length=31,
        description='Additional exact selected-node reviews for other definitions used in this answer. '
            'Each review retains its own candidate revision, conditions and quarantine scope.')
    question: str=Field(min_length=1)
    execution_ref: Digest | None=None
    draft: ProcessAnswerDraftV2 | None=None
    meaning_selection: tuple[MeaningCitation,...] | None=Field(default=None,
        description='Optional exact existing meaning references for preparation. The product returns candidate meanings when absent; '
            'an explicit selection reads only those targets and their required closures. This is not complete '
            'search, source entailment or approval. Preparation and binding use the same selected original fields; '
            'additional source evidence requires a corresponding read scope.')

    @model_validator(mode='after')
    def unique_meaning_selection(self):
        if self.definition_review_revision is None and not self.source_definition_revisions and not self.published_meaning_uses:
            raise ValueError('ANSWER_COMPOSITION_EVIDENCE_MODE_REQUIRED')
        if self.published_meaning_uses:
            if self.definition_review_revision is not None or self.additional_definition_review_revisions:
                raise ValueError('ANSWER_MIXED_REVIEW_AUTHORITY_UNSUPPORTED')
            if len({u.revision for u in self.published_meaning_uses})!=len(self.published_meaning_uses):
                raise ValueError('ANSWER_PUBLISHED_MEANING_DUPLICATE')
            if self.meaning_selection is not None and (not self.meaning_selection or
                    any(c.asset_revision not in {u.revision for u in self.published_meaning_uses} for c in self.meaning_selection)):
                raise ValueError('ANSWER_EXPLAIN_SELECTION_UNBOUND')
        if self.source_definition_revisions:
            if self.definition_review_revision is None and not self.published_meaning_uses and (self.additional_definition_review_revisions or self.meaning_selection is not None):
                raise ValueError('ANSWER_SOURCE_ONLY_MEANING_AUTHORITY_FORBIDDEN')
            if len(set(self.source_definition_revisions))!=len(self.source_definition_revisions):
                raise ValueError('ANSWER_SOURCE_DEFINITION_DUPLICATE')
        reviews=(self.definition_review_revision,*self.additional_definition_review_revisions)
        if len(reviews)!=len(set(reviews)):raise ValueError('ANSWER_REVIEW_REVISION_DUPLICATE')
        if self.meaning_selection is not None:
            keys=[(item.asset_revision,item.target_pointer) for item in self.meaning_selection]
            if len(set(keys))!=len(keys):raise ValueError('ANSWER_MEANING_SELECTION_DUPLICATE')
        return self


def paragraph_evidence_groups(answer):
    """Display grouping only; preserve each statement's own evidence binding."""
    groups={}
    for block in answer.get('layout') or []:
        if block['kind']!='paragraph':continue
        pointers=list(block['statements'])
        members=[answer[p.split('/')[1]][int(p.split('/')[2])] for p in pointers]
        # Proposal background must not become factual support by co-location.
        if any(s.get('kind') in ('recommendation','runtime_state') for s in members):continue
        for pointer in pointers:groups[pointer]=pointers
    return groups


def compact_meaning_url(citation, source_pages):
    """Address one existing bound closure, independently of paragraph layout."""
    from urllib.parse import quote, urlsplit
    if citation.get('meaning_use') is not None:return None
    graph=citation.get('graph_evidence',[])
    revision=citation.get('asset_revision')
    if (citation.get('kind')!='meaning' or not citation.get('asset_revision')
            or not graph or graph[0]['target_pointer']!=citation.get('target_pointer')
            or graph[0].get('role','direct')!='direct'):
        return None
    if isinstance(source_pages,DefinitionSourcePages):
        source_pages=source_pages.for_meaning(revision)
    # The protected meaning endpoint resolves a process claim together with
    # its local identity/condition/dependency closure. A cross-asset closure
    # needs that endpoint's own dependency reading; its availability cannot be
    # established from this citation alone, so retain the explicit field links.
    if any(node.get('asset_revision',revision)!=revision for node in graph):
        return None
    bindings=citation.get('source_bindings',[])
    if not bindings or [binding for node in graph for binding in node.get('source_bindings',[])]!=bindings:
        return None
    bases={source_pages.get(b['source_revision_digest']) for b in bindings}
    if len(bases)!=1 or None in bases:return None
    base=next(iter(bases))
    route=urlsplit(base)
    if (not route.path.endswith('/native-definitions/'+revision['revision_digest'].removeprefix('sha256:'))
            or route.query or route.fragment):
        return None
    return base+'?meaning='+quote(citation['target_pointer'],safe='')+'#evidence-group'


def bound_reading_scopes(bound,sources):
    """Reuse the exact original readings already checked by the answer binder."""
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    from agent_kit.python.boi_process_answer_v2 import source_scope_reference
    if any(s.get('manifest',{}).get('field_inventory_location')=='source.fields' for s in sources):
        from agent_kit.python.boi_process_answer_stage import restore_source_model_material
        sources=restore_source_model_material({'sources':sources})['sources']
    scopes=[]
    for source in sources:
        digest=semantic_digest(source)
        if digest not in bound['source_reading_digests']:
            raise ValueError('ANSWER_SCOPE_READING_NOT_BOUND')
        scopes.append(source_scope_reference({'source':source['source'],'manifest':source['manifest'],
            'reading_digest':digest,'fields':{f['field_locator']:f for f in source['fields']}}))
    return scopes


def selected_composition_sources(context,sources,selection,*,additional_bindings=()):
    """Use the same selected original reading for preparation AND binding.

    Review/source authority was already resolved independently. This only narrows
    original field delivery after the existing resolver includes owned qualifiers
    and declared dependencies; it does not grant meaning or review authority.
    """
    if selection is None:return sources,None,None
    from .native_definition_sources import project_meaning_source_fields
    targets=[]
    for revision,pointers in selection.items():
        targets.extend(meaning_citation_targets(context=context,sources=sources,
            asset_revision=revision,target_pointers=pointers))
    if any(t.get('binding_status')!='bound' for t in targets):
        # Keep unresolved evidence available for source-based supplementation.
        # It is not a successfully narrowed or approved interpretation.
        return sources,{'status':'unresolved_meaning_evidence','absence_proven':False},targets
    bindings=[*additional_bindings,*[b for t in targets for n in t['graph_evidence'] for b in n['source_bindings']]]
    projected=project_meaning_source_fields(sources,bindings)
    return projected,{'status':'selected_meaning_evidence','absence_proven':False,
        'validated_fields':sum(len(s['fields']) for s in sources),
        'delivered_fields':sum(len(s['fields']) for s in projected),
        'scope':'Exact whole fields for selected meanings and declared dependency closure, plus any explicitly included original-record supplements; not full-source absence.'},targets


def meaning_source_group(citations,source_pages,*,reading_scopes=()):
    """A stable navigation selection, derived only from already bound evidence.

    It contains no question, answer, judgment or copied original text. Opening
    it reauthorizes the definition and resolves its original meaning closures.
    """
    import json
    from ..governed_runtime.source_envelope import byte_digest
    from urllib.parse import urlsplit
    meanings=[c for c in citations if c['kind']=='meaning']
    scopes=[c for c in citations if c['kind']=='source_scope']
    if not meanings or len(meanings)+len(scopes)!=len(citations):return None
    revision=meanings[0]['asset_revision'];urls=[]
    for citation in meanings:
        url=compact_meaning_url(citation,source_pages)
        if not url or citation['asset_revision']!=revision:return None
        urls.append(urlsplit(url)._replace(query='',fragment='').geturl())
    if len(set(urls))!=1:return None
    for scope in scopes:
        # A subset reading has a different digest from the full definition page.
        # Keep its separate scope link instead of publishing a group that the
        # page could only validate against another original reading.
        if scope.get('coverage')=='selected_meaning_evidence_fields':return None
        pages=(source_pages.for_scope(scope['source_revision_digest']) if isinstance(source_pages,DefinitionSourcePages)
            else [source_pages.get(scope['source_revision_digest'])])
        if pages!=[urls[0]]:return None
    automatic=[]
    if isinstance(source_pages,DefinitionSourcePages):
        for scope in reading_scopes:
            digest=scope['source_revision_digest']
            if source_pages.for_meaning(revision).get(digest)!=urls[0]:continue
            fields=source_pages.scope_fields(digest,urls[0])
            # A definition page must expose this exact reading. A union read
            # across sibling records cannot become one record's absence scope.
            if fields is None:
                if scope['coverage'] in ('selected_source_fields','selected_meaning_evidence_fields'):continue
            elif fields!={f['span_ref'] for f in scope['field_inventory']}:continue
            if any(s['source_revision_digest']==digest for s in scopes):continue
            automatic.append(scope)
    scopes=[*scopes,*automatic]
    pointers=sorted({c['target_pointer'] for c in meanings})
    if len(pointers)>128:return None
    if len(pointers)==1 and not scopes:return None
    scope_refs={s['source_revision_digest']:{k:s[k] for k in (
        'source_revision_digest','reading_digest','manifest_digest')} for s in scopes}
    if any(scope_refs[s['source_revision_digest']]!={k:s[k] for k in scope_refs[s['source_revision_digest']]} for s in scopes):
        raise ValueError('ANSWER_GROUP_SCOPE_CONFLICT')
    payload={'contract_version':'boi/source-meaning-selection@1','definition_revision':revision,
        'meaning_pointers':pointers,'read_scopes':[scope_refs[k] for k in sorted(scope_refs)]}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    ref=byte_digest(raw)
    return {'payload':payload,'bytes':raw,'ref':ref,'url':urls[0]+'?group='+ref.removeprefix('sha256:')+'#evidence-group',
        **({'reading_scope_refs':[{k:s[k] for k in ('source_revision_digest','reading_digest','manifest_digest')}
            for s in automatic]} if automatic else {})}


def definition_meaning_groups(citations,source_pages,*,reading_scopes=()):
    """Reuse each definition's existing selection route for a mixed explanation.

    This groups only already bound meanings. Read scopes, literal quotations,
    execution results and cross-asset closures keep their existing routes.
    No shared artifact or paragraph membership grants a shared meaning scope.
    """
    if not citations or any(c['kind']!='meaning' for c in citations):return None
    groups={}
    for citation in citations:
        key=(citation['asset_revision']['ref'],citation['asset_revision']['revision_digest'])
        groups.setdefault(key,[]).append(citation)
    if len(groups)<2:return None
    selected=[]
    for members in groups.values():
        selection=meaning_source_group(members,source_pages,reading_scopes=reading_scopes)
        if selection is None and len({c['target_pointer'] for c in members})!=1:return None
        url=selection['url'] if selection else compact_meaning_url(members[0],source_pages)
        # A noncompact closure must not be hidden by another member's route.
        if not url or any(compact_meaning_url(c,source_pages) is None for c in members):return None
        selected.append({'url':url,'selection':selection,'revision':members[0]['asset_revision']})
    return selected


def literal_source_group(revision,bindings,base):
    """The existing protected selection route, with exact original spans.

    This is navigation over bound evidence, never a new claim or approval.
    It stores references only; opening it checks the current record authority.
    """
    import json
    from ..governed_runtime.source_envelope import byte_digest
    keys=('source_revision_digest','span_ref','field_locator','start','end')
    spans=sorted({tuple(b[k] for k in keys) for b in bindings})
    if not spans or len(spans)>256:return None
    payload={'contract_version':'boi/source-field-selection@1','definition_revision':revision,
        'source_bindings':[dict(zip(keys,span)) for span in spans]}
    raw=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    ref=byte_digest(raw)
    return {'payload':payload,'bytes':raw,'ref':ref,
        'url':base+'?group='+ref.removeprefix('sha256:')+'#evidence-group'}


def answer_source_bindings(answer):
    """Index the evidence already present in the bound answer, without copying it."""
    result=[];seen=set()
    for section in ('sentences','limitations'):
        for statement in answer.get(section,[]):
            for citation in statement['citations']:
                for binding in citation.get('source_bindings',[]):
                    key=tuple(binding[k] for k in ('source_revision_digest','span_ref','field_locator','start','end'))
                    if key not in seen:seen.add(key);result.append({k:binding[k] for k in (
                        'source_revision_digest','span_ref','field_locator','start','end')})
    return result


@stage_timing('citation_construction')
def render_bound_native_answer(bound,source_pages,*,publish_group=None,execution_pages=None,source_readings=()):
    """Keep authored text/layout; insert only already-bound source links."""
    from .process_citation_display import statement_delivery_role
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    from ..governed_runtime.citation_material_cards import composition_source_cards,material_source_cards,material_identity,bound_source_identity
    reading_scopes=bound_reading_scopes(bound,source_readings)
    response_cards=material_source_cards([{'source':card['source'],**reference,'answer_index':ai}
        for ai,answer in enumerate(bound['answers'])
        for card in composition_source_cards(answer,[],source_readings) for reference in card['references']])
    material_numbers={material_identity(card['source']):card['number'] for card in response_cards}
    answers=[]
    for answer in bound['answers']:
        statements={};citations=[];units=[];source_selections={};paragraphs=paragraph_evidence_groups(answer)
        # Exact span offsets are needed for publication, not for a historical
        # display-only field link. Do not reconstruct an unused span index.
        indexed_bindings=answer_source_bindings(answer) if publish_group is not None else []
        for group in ('sentences','limitations'):
            for index,statement in enumerate(answer[group]):
                text=statement['text'];urls=[];field_groups={};scope_sources={};scope_fields={};meaning_urls=set();target_bindings={};target_scopes={};target_members={}
                for citation in statement['citations']:
                    compact=compact_meaning_url(citation,source_pages)
                    if compact:
                        if compact not in urls:urls.append(compact)
                        meaning_urls.add(compact)
                        target_bindings.setdefault(compact,[]).extend(citation.get('source_bindings',[]))
                        target_members.setdefault(compact,[]).append(citation)
                        continue
                    for binding in citation.get('source_bindings',[]):
                        base=binding_source_page(source_pages,binding)
                        if base is None:raise ValueError('ANSWER_SOURCE_PAGE_UNAVAILABLE')
                        anchor=field_anchor(binding['source_revision_digest'],binding['span_ref'])
                        fields=field_groups.setdefault(base,[])
                        if anchor not in fields:fields.append(anchor)
                    if citation['kind']=='source_scope':
                        bases=(source_pages.for_scope(citation['source_revision_digest']) if isinstance(source_pages,DefinitionSourcePages)
                            else [source_pages.get(citation['source_revision_digest'])])
                        if not bases or None in bases:raise ValueError('ANSWER_SOURCE_PAGE_UNAVAILABLE')
                        for base in bases:
                            if base not in urls:urls.append(base)
                            scope_sources.setdefault(base,[]).append(citation['source_revision_digest'])
                            target_scopes.setdefault(base,[]).append(citation['source_revision_digest'])
                            target_members.setdefault(base,[]).append(citation)
                            if isinstance(source_pages,DefinitionSourcePages):
                                owned=source_pages.scope_fields(citation['source_revision_digest'],base)
                                if owned is not None:
                                    visible=[f['span_ref'] for f in citation['field_inventory'] if f['span_ref'] in owned]
                                    if not visible:raise ValueError('ANSWER_SOURCE_PAGE_SCOPE_EMPTY')
                                    scope_fields.setdefault(base,{})[citation['source_revision_digest']]=visible
                pointer=f'/{group}/{index}'
                display_members=paragraphs.get(pointer,[pointer])
                # Same-page paragraph links expose all of its cited fields, so a
                # host may condense the paragraph without losing identity fields.
                # The bound answer itself is not changed or given inherited facts.
                for member in display_members:
                    _,section,position=member.split('/')
                    for c in answer[section][int(position)]['citations']:
                        if compact_meaning_url(c,source_pages):continue
                        for b in c.get('source_bindings',[]):
                            base=binding_source_page(source_pages,b)
                            if base in field_groups:
                                anchor=field_anchor(b['source_revision_digest'],b['span_ref'])
                                if anchor not in field_groups[base]:field_groups[base].append(anchor)
                members=[answer[p.split('/')[1]][int(p.split('/')[2])] for p in display_members]
                member_citations=[c for member in members for c in member['citations']]
                member_bindings=[b for c in member_citations for b in c.get('source_bindings',[])]
                literal_groups={}
                for base,fields in field_groups.items():
                    # Eligibility was decided once above for the whole bound
                    # closure. A partial field group must not regain a meaning
                    # link after its source/asset identity check failed.
                    literal=None
                    if publish_group is not None and isinstance(source_pages,DefinitionSourcePages):
                        bindings=[b for p in display_members
                            for c in answer[p.split('/')[1]][int(p.split('/')[2])]['citations']
                            if c['kind']=='source_quote'
                            for b in c.get('source_bindings',[]) if binding_source_page(source_pages,b)==base]
                        # Do not hide a noncompact meaning closure behind literal evidence.
                        if set(fields)=={field_anchor(b['source_revision_digest'],b['span_ref']) for b in bindings}:
                            literal=literal_source_group(source_pages.revisions[base],bindings,base)
                    if literal is not None:
                        if publish_group(literal['bytes'])!=literal['ref']:raise ValueError('ANSWER_GROUP_OBJECT_MISMATCH')
                        urls.append(literal['url']);literal_groups[literal['url']]=literal
                        target_bindings[literal['url']]=bindings
                        target_members[literal['url']]=[c for c in member_citations if c['kind']=='source_quote']
                        source_selections[literal['ref']]={'definition_revision':literal['payload']['definition_revision'],
                            'binding_indices':sorted(indexed_bindings.index(b) for b in literal['payload']['source_bindings'])}
                    else:
                        target=base+'#'+fields[0] if len(fields)==1 else base+'?fields='+','.join(fields)+'#evidence-group'
                        urls.append(target)
                        target_members[target]=member_citations
                        target_bindings[target]=[b for b in member_bindings if binding_source_page(source_pages,b)==base
                            and field_anchor(b['source_revision_digest'],b['span_ref']) in fields]
                for citation in statement.get('citations',[]):
                    if citation.get('kind')=='execution_result':
                        result_url=(execution_pages or {}).get(citation['result_digest'])
                        if result_url and result_url not in urls:urls.append(result_url)
                selection=None;definition_groups={}
                if publish_group is not None:
                    members=[answer[p.split('/')[1]][int(p.split('/')[2])] for p in display_members]
                    member_citations=[c for member in members for c in member['citations']]
                    selection=meaning_source_group(member_citations,source_pages,reading_scopes=reading_scopes)
                    if selection is not None:
                        if publish_group(selection['bytes'])!=selection['ref']:raise ValueError('ANSWER_GROUP_OBJECT_MISMATCH')
                        urls=[selection['url']]
                        target_bindings[selection['url']]=member_bindings
                        target_members[selection['url']]=member_citations
                        target_scopes[selection['url']]=[c['source_revision_digest'] for c in member_citations if c['kind']=='source_scope']
                    else:
                        grouped=definition_meaning_groups(member_citations,source_pages,reading_scopes=reading_scopes)
                        if grouped and len(display_members)>1 and any(not item['selection'] for item in grouped):
                            grouped=None
                        if grouped:
                            for item in grouped:
                                group_selection=item['selection']
                                if group_selection and publish_group(group_selection['bytes'])!=group_selection['ref']:
                                    raise ValueError('ANSWER_GROUP_OBJECT_MISMATCH')
                                definition_groups[item['url']]=item
                                target_members[item['url']]=[c for c in member_citations if c.get('asset_revision')==item['revision']]
                                target_bindings[item['url']]=[b for c in member_citations if c.get('asset_revision')==item['revision'] for b in c.get('source_bindings',[])]
                            urls=list(definition_groups)
                for url in urls:
                    grouped=definition_groups.get(url)
                    link_selection=grouped['selection'] if grouped else selection
                    execution_digest=next((c['result_digest'] for c in statement['citations']
                        if c.get('kind')=='execution_result' and (execution_pages or {}).get(c['result_digest'])==url),None)
                    citations.append({'url':url,'statement_pointer':f'/{group}/{index}',
                        'evidence_binding_keys':list(dict.fromkeys(semantic_digest({'citation':semantic_digest(c),'binding':semantic_digest(b)})
                            for c in target_members.get(url,[]) for b in c.get('source_bindings',[]) if b in target_bindings.get(url,[]))),
                        'scope_reference_keys':[semantic_digest(c) for c in target_members.get(url,[]) if c['kind']=='source_scope'],
                        'display_scope_digests':list(dict.fromkeys(target_scopes.get(url,[]))),
                        **({'source_group_ref':literal_groups[url]['ref'],
                            'display_group_pointers':display_members} if url in literal_groups else {}),
                        **({'execution_result_digest':execution_digest} if execution_digest else {}),
                        **({'meaning_group_ref':link_selection['ref'],'display_group_pointers':display_members} if link_selection is not None else {}),
                        **({'reading_scope_refs':link_selection['reading_scope_refs']}
                            if link_selection is not None and link_selection.get('reading_scope_refs') else {}),
                        **({'meaning_group_revision':grouped['revision']} if grouped and link_selection else {}),
                        **({'display_group_pointers':display_members}
                           if url not in meaning_urls and len(display_members)>1 and ('#field' in url or '#evidence-group' in url) else {}),
                        **({'evidence_role':'recommendation_background'} if statement.get('kind')=='recommendation' else {}),
                        **({'scope_source_digests':list(dict.fromkeys(scope_sources[url]))} if url in scope_sources else {}),
                        **({'scope_field_refs':scope_fields[url]} if url in scope_fields else {})})
                    identities=[material_identity(bound_source_identity(source_readings,b['source_revision_digest'],b.get('span_ref'),b.get('field_locator'))) for b in target_bindings.get(url,[])]
                    identities.extend(material_identity(bound_source_identity(source_readings,d)) for d in target_scopes.get(url,[]))
                    numbers=list(dict.fromkeys(material_numbers[i] for i in identities if i in material_numbers))
                    citations[-1]['material_numbers']=numbers
                    if numbers:
                        label=', '.join(map(str,numbers))
                    elif execution_digest:
                        label='실행 결과'
                    else:
                        label='근거'
                    label=('제안의 배경 ' if statement.get('kind')=='recommendation' else '')+label
                    text+=' ['+label+']('+url+')'
                statements[f'/{group}/{index}']=text
                units.append({'statement_pointer':pointer,'text':statement['text'],
                    **statement_delivery_role(statement),
                    'citation_indices':[i for i,c in enumerate(citations) if c['statement_pointer']==pointer]})
        text=(render_layout(answer['layout'],statements.__getitem__) if answer.get('layout')
            else '\n\n'.join(statements.values()))
        cards=composition_source_cards(answer,citations,source_readings)
        for card in cards:
            card['number']=material_numbers[material_identity(card['source'])]
            reading=next(r for r in source_readings if material_identity(r['source'])==material_identity(card['source']))
            binding=next((r['binding'] for r in card['references'] if 'binding' in r),None)
            field=next((f for f in reading['fields'] if binding and f['field_locator']==binding['field_locator']),None)
            if field is not None:
                from .native_definition_sources import source_field_label
                card['title']=source_field_label(field,source=reading)
        answers.append({'question_id':answer['question_id'],'readable_text':text,'citations':citations,
                        **({'source_selections':source_selections} if source_selections else {}),
                        'answer_units':units,
                        'source_cards':cards})
    return answers


@stage_timing('citation_construction')
def _definition_source_pages(intake,principal,revisions,*,source_base_url=None):
    """Resolve the existing source route from authorized immutable asset identity.

    Composition already read the canonical full sources for binding. Building
    a source screen here would repeat every definition's evidence projection.
    Actual navigation still performs its independent protected source read.
    """
    from urllib.parse import urlsplit
    origin=(source_base_url or '').rstrip('/')
    parsed=urlsplit(origin)
    origin=origin if parsed.scheme in ('http','https') and parsed.netloc else ''
    import json
    pages=DefinitionSourcePages()
    for revision in revisions:
        stored=timed_call('current_asset_reading',intake.read_asset,principal,DomainAssetReadRequest(revision=revision,lane='provisional'))
        if stored['asset']['kind']!='definition':raise ValueError('DEFINITION_SOURCE_KIND_REQUIRED')
        url=origin+'/native-definitions/'+stored['revision']['revision_digest'].removeprefix('sha256:')
        content=json.loads(stored['asset']['content_json'])
        record=content.get('source_record') if isinstance(content,dict) else None
        refs=({*record['field_refs'],*record['context_refs'],
            *(e['ref'] for e in stored['asset']['evidence'])} if isinstance(record,dict) else None)
        if isinstance(content,dict) and content.get('contract_version')=='boi/knowledge-content@1':
            refs={e['span']['ref'] for e in content['evidence_bindings']}
        pages.register(stored['revision'],stored['sources'],url,refs)
    return pages


def compose_native_answer(intake,principal,request,*,source_base_url=None,execution_results=None,prepared_review_binding=None,prepared_review_bindings=None):
    from ..governed_runtime.native_definition_context import read_native_definition_authority
    request=NativeAnswerComposition.model_validate(request)
    if (request.source_definition_revisions or request.published_meaning_uses) and request.definition_review_revision is None:
        return compose_original_records(intake,principal,request,
            source_base_url=source_base_url,execution_results=execution_results)
    if request.additional_definition_review_revisions or request.source_definition_revisions:
        return compose_reviewed_definitions(intake,principal,request,
            source_base_url=source_base_url,execution_results=execution_results,
            prepared_review_bindings=prepared_review_bindings)
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    if any(semantic_digest(value)!=digest for digest,value in (execution_results or {}).items()):
        raise ValueError('ANSWER_EXECUTION_DIGEST_MISMATCH')
    authorization,work=intake._work(principal)
    stored=intake.read_asset(principal,DomainAssetReadRequest(revision=request.definition_review_revision,lane='provisional'))
    from ..governed_runtime.native_observation import _json
    review_content=_json(stored['asset']['content_json'])
    from .asset_user_views import process_review_target
    existing_process_review=process_review_target(review_content) is not None
    reviewed_value=review_content if existing_process_review else _json(review_content['value_json'])
    node_binding=None;review_dependencies=None
    if existing_process_review or reviewed_value.get('contract_version') in ('boi/native-definition-review@2','boi/native-definition-review@3'):
        from .native_process_review import read_native_process_review_binding,check_native_process_answer,native_process_review_authority
        if prepared_review_binding is not None:
            from .native_process_review import reuse_native_process_review_binding
            node_binding=reuse_native_process_review_binding(intake,principal,request.definition_review_revision,prepared_review_binding)
        elif existing_process_review:
            from .native_process_review import read_existing_process_review_binding
            node_binding=read_existing_process_review_binding(intake,principal,request.definition_review_revision)
        else:
            node_binding=read_native_process_review_binding(intake,principal,request.definition_review_revision)
        from agent_kit.python.boi_process_claim_review import prepare_answer_review_dependencies
        review_dependencies=prepare_answer_review_dependencies(asset_revision=node_binding['candidate_revision'],
            asset_content=node_binding['candidate_content'],review_check=node_binding['check'])
        authority,context=native_process_review_authority(node_binding,authorization)
    else:
        authority,context=read_native_definition_authority(work,authorization,request.definition_review_revision)
    selected=None
    if request.meaning_selection is not None:
        selected={}
        for item in request.meaning_selection:
            if item.asset_revision not in authority.definition_revisions:
                raise ValueError('ANSWER_MEANING_SELECTION_REVISION_NOT_REVIEWED')
            selected.setdefault(item.asset_revision,[]).append(item.target_pointer)
    execution_pages={}
    if request.execution_ref is not None:
        from .native_formula import read_current_formula_execution,NativeFormulaRequest
        record=read_current_formula_execution(work,authorization,request.execution_ref)
        original=NativeFormulaRequest.model_validate(record['request'])
        if original.formula.parameters and request.definition_review_revision not in original.parameter_reviews.values():
            raise ValueError('ANSWER_EXECUTION_DEFINITION_MISMATCH')
        if record['result'].get('evaluation') is None:
            raise ValueError('ANSWER_EXECUTION_NOT_EVALUATED')
        observed={'request':record['request'],'result':record['result']}
        execution_results={**(execution_results or {}),semantic_digest(observed):observed}
        from .native_formula import formula_result_url
        execution_pages[semantic_digest(observed)]=formula_result_url(request.execution_ref)

    source_reader=RequestSourceReader(intake,principal)
    sources=node_binding['sources'] if node_binding is not None else source_reader.read_for_assets(
        intake,principal,stored['sources'],authority.definition_revisions)
    sources,source_selection,resolved_targets=selected_composition_sources(context,sources,selected)
    targets=resolved_targets if request.draft is None and resolved_targets is not None else []
    for revision in authority.definition_revisions:
        # A submitted draft already selects exact meaning references. Rebind
        # those references below; enumerating every candidate adds no assurance.
        if request.draft is None and resolved_targets is None and (selected is None or revision in selected):
            targets.extend(meaning_citation_targets(context=context,sources=sources,asset_revision=revision,
                **({'target_pointers':selected[revision]} if selected is not None else {})))
    questions=[{'id':'request','question':request.question,'max_body_characters':None}]
    if request.draft is None:
        from ..governed_runtime.native_definition_context import NativeDefinitionReview,scoped_native_review_model
        reviewed=(node_binding['review_summary'] if existing_process_review else
            (scoped_native_review_model(reviewed_value.get('contract_version')) if node_binding is not None else NativeDefinitionReview).model_validate(reviewed_value).model_dump(mode='json'))
        if node_binding is not None:
            for target in targets:
                try:
                    if target.get('binding_status')!='bound':raise ValueError('unresolved')
                    check_native_process_answer({'answers':[{'sentences':[{'citations':[{'kind':'meaning',**target}]}]}]},
                        node_binding,review_dependencies=review_dependencies)
                except ValueError:
                    target['review_use_status']='unavailable_pending_or_quarantined'
                else:target['review_use_status']='usable_with_reviewed_source_scope'
        schema=ProcessAnswerDraftV2.model_json_schema()
        answer_schema=schema['$defs']['QuestionAnswer']
        answer_schema['required']=list(dict.fromkeys([*answer_schema.get('required',[]),'request_plan']))
        answer_schema['properties']['request_plan']={'$ref':'#/$defs/RequestPlan'}
        prepared = {'status':'composition_ready','question':request.question,'questions':questions,
            'context_digest':context.context_digest,'sources':sources,'meaning_targets':targets,
            'meaning_review':{'review_revision':request.definition_review_revision.model_dump(mode='json'),
                'findings':list(reviewed['findings']),'limitations':list(reviewed['limitations']),
                'semantic_truth_proven':reviewed['semantic_truth_proven'],
                'execution_authority_granted':reviewed['execution_authority_granted'],
                'scope':'Recorded review opinions and limits for authoring; not original evidence, '
                    'a new review, or authority for final claims. Compare selected meanings with the originals.'},
            'draft_schema':schema,'execution_targets':[{'result_digest':digest,'value':value,
                **({'result_url':execution_pages[digest]} if digest in execution_pages else {})}
                for digest,value in (execution_results or {}).items()],'user_request_fulfilled':False}
        prepared['meaning_review']['node_review_scope']='selected_nodes' if node_binding is not None else 'unscoped_legacy_opinion'
        if node_binding is not None:
            from .native_composition_authoring import selected_review_pointer_inventory
            prepared['meaning_review']['node_review_binding']=selected_review_pointer_inventory(
                {k:node_binding[k] for k in (
                    'candidate_revision','review_revision','status','source_review','usable_node_pointers',
                    'quarantined_node_pointers','review_execution_binding')}, targets)
            prepared['meaning_review'].update({k:node_binding[k] for k in (
                'reviewer_relationship_observation','native_observation_provenance','carried_review_limits')})
        if selected is not None:
            prepared['meaning_selection_scope']={'selection_kind':'caller_selected_references',
                'includes':'selected_targets_and_required_closure','complete_meaning_inventory':False,
                'absence_proven':False,'semantic_support_verified':False,'source_delivery':source_selection}
        # Use the same lossless model projection as the native agent kit. The
        # binder below still reads canonical authorized sources, independently.
        from agent_kit.python.boi_process_answer_stage import composition_model_material
        return {**composition_model_material(prepared), 'draft_schema': schema,
            **({'_prepared_review_binding':node_binding} if node_binding is not None else {})}
    if any(answer.request_plan is None for answer in request.draft.answers):
        raise ValueError('ANSWER_REQUEST_PLAN_REQUIRED')
    bound=timed_call('binding_checks',bind_process_answers_v2,request.draft,context=context,sources=sources,questions=questions,execution_results=execution_results)
    reviewed_binding=check_native_process_answer(bound,node_binding,review_dependencies=review_dependencies) if node_binding is not None else None
    pages=_definition_source_pages(intake,principal,authority.definition_revisions,source_base_url=source_base_url)
    return {'contract_version':'boi/native-answer-composition@1','status':'bound','question':request.question,'answers':render_bound_native_answer(
            bound,pages,publish_group=intake.source_intake.objects.put,execution_pages=execution_pages,source_readings=sources),
        **({'meaning_review_binding':reviewed_binding} if reviewed_binding is not None else {}),
        **({'execution_links':{digest:{'execution_ref':request.execution_ref,'url':url}
            for digest,url in execution_pages.items()}} if execution_pages else {}),
        '_source_reading_descriptors':source_reading_descriptors(sources),'bound_answer':bound,'user_request_fulfilled':False,'semantic_support_verified':False,
        'scope':'Statement, request and source bindings only; source entailment and actual final delivery require verification.'}


def compose_original_records(intake,principal,request,*,source_base_url=None,execution_results=None):
    """Use the existing statement/plan binder without inventing a meaning review.

    Definitions locate exact original records and annotation dependencies. No
    definition is admitted into the semantic context: meaning citations fail,
    including in request facets. Formula evidence is a separately authorized
    actual execution, never a numeric claim inferred from answer text.
    """
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    from ..governed_runtime.domain_asset_store import source_manifest_digest
    from ..governed_runtime.task_knowledge import resolve_task_knowledge
    from .native_formula import read_current_formula_execution,NativeFormulaRequest,formula_result_url
    from agent_kit.python.boi_process_answer_stage import composition_model_material
    from .published_original_reading import closure_binds
    import json
    if any(semantic_digest(v)!=k for k,v in (execution_results or {}).items()):
        raise ValueError('ANSWER_EXECUTION_DIGEST_MISMATCH')
    authorization,work=intake._work(principal)
    meaning_reader=None;uses=[]
    if request.published_meaning_uses:
        from .published_answer_meaning import PublishedAnswerMeaning
        meaning_reader=PublishedAnswerMeaning(work.knowledge_spaces,principal.employee_id,
            current_authorization=work.current_knowledge_authorization)
        for selected in request.published_meaning_uses:
            pointers=([c.target_pointer for c in request.meaning_selection if c.asset_revision==selected.revision]
                if request.meaning_selection is not None else None)
            if pointers==[]:raise ValueError('ANSWER_EXPLAIN_SELECTION_MISSING')
            uses.append(meaning_reader.read(selected,pointers))
    revisions=sorted(set(request.source_definition_revisions)|{u.revision for u in uses},key=lambda r:r.ref)
    # Only an explicit selection narrows the original reading to its closures.
    closures={u.revision:u.closure for u in uses} if request.meaning_selection is not None else None
    envelopes=[]
    for revision in revisions:
        stored=timed_call('current_asset_reading',intake.read_asset,principal,DomainAssetReadRequest(revision=revision,lane='provisional'))
        if stored['asset']['kind']!='definition':raise ValueError('DEFINITION_SOURCE_KIND_REQUIRED')
        cited=None
        if closures is not None and revision in closures:
            # A source the selected closure never cites is not read, so it is
            # not part of this context's source manifest either.
            cited={b['source_revision_digest'] for b in json.loads(stored['asset']['content_json'])['evidence_bindings']
                if closure_binds(b['meaning_pointer'],closures[revision])}
        for source in stored['sources']:
            if cited is not None and source['digest'] not in cited:continue
            if source not in envelopes:envelopes.append(source)
    envelopes.sort(key=semantic_digest)
    # Empty semantic context is intentional: these revisions select source
    # records, not approved concepts. Bind that selection into its identity.
    def no_meaning_read(revision):raise ValueError('ANSWER_SOURCE_ONLY_MEANING_AUTHORITY_FORBIDDEN')
    context=resolve_task_knowledge(principal_id=authorization.principal,policy_digest=authorization.policy_digest,
        purpose='original-record-answer:'+semantic_digest([r.model_dump(mode='json') for r in revisions]),
        source_manifest_digest=source_manifest_digest(envelopes),roots=(),read_authorized_revision=no_meaning_read,
        lane='provisional',available_tools=frozenset(),require_available_tools=False)
    if uses:
        from ..governed_runtime.task_knowledge import TaskAssetRevision,KnowledgeRequirement,TaskKnowledgeContext
        def read_meaning(revision):
            stored=timed_call('current_asset_reading',intake.read_asset,principal,DomainAssetReadRequest(revision=revision,lane='provisional'))
            return TaskAssetRevision.model_validate(stored['asset'])
        context=resolve_task_knowledge(principal_id=authorization.principal,policy_digest=authorization.policy_digest,
            purpose='published-explain-answer:'+semantic_digest([u.model_dump(mode='json') for u in uses]),
            source_manifest_digest=source_manifest_digest(envelopes),
            roots=tuple(KnowledgeRequirement(revision=u.revision,role='explanation',reason='current-explain-qualification',
                stages=('answer',)) for u in uses),read_authorized_revision=read_meaning,
            lane='provisional',available_tools=frozenset(),require_available_tools=False)
        if context.dependency_completeness!='complete':raise ValueError('ANSWER_EXPLAIN_CONTEXT_INCOMPLETE')
        wire=context.model_dump(mode='json',exclude={'context_digest'})
        wire['meaning_uses']=[u.model_dump(mode='json') for u in uses]
        context=TaskKnowledgeContext.model_validate({**wire,'context_digest':semantic_digest(wire)})
    sources=timed_call('current_source_reading',RequestSourceReader(intake,principal).read_for_assets,intake,principal,envelopes,revisions,
        meaning_closures=closures)
    targets=[target for use in uses for target in meaning_citation_targets(context=context,sources=sources,
        asset_revision=use.revision,target_pointers=use.roots)]
    if any(t['binding_status']!='bound' for t in targets):
        from .native_answer_refusal import unresolved_meaning_refusal
        raise unresolved_meaning_refusal(targets)
    if meaning_reader is not None:meaning_reader.revalidate()
    execution_pages={}
    if request.execution_ref is not None:
        record=read_current_formula_execution(work,authorization,request.execution_ref)
        original=NativeFormulaRequest.model_validate(record['request'])
        if any(parameter.revision not in revisions for parameter in original.formula.parameters.values()):
            raise ValueError('ANSWER_EXECUTION_DEFINITION_MISMATCH')
        if record['result'].get('evaluation') is None:raise ValueError('ANSWER_EXECUTION_NOT_EVALUATED')
        observed={'request':record['request'],'result':record['result']};digest=semantic_digest(observed)
        execution_results={**(execution_results or {}),digest:observed}
        execution_pages[digest]=formula_result_url(request.execution_ref)
    questions=[{'id':'request','question':request.question,'max_body_characters':None}]
    source_mode={'mode':'original_record_evidence','definition_revisions':[r.model_dump(mode='json') for r in revisions],
        'meaning_reuse':False,'definition_review_inherited':False,
        'scope':'Exact original record/header/annotation fields selected through stored definitions, not a complete knowledge search. '
            'Use original quotations and explicit reading scopes; actual execution results require retained execution references.'}
    if uses:
        source_mode={'mode':'published_explain_with_original_evidence',
            'definition_revisions':[r.model_dump(mode='json') for r in revisions],
            'meaning_uses':[u.model_dump(mode='json') for u in uses],
            'context_asset_count':len(context.assets),'meaning_reuse':False,'definition_review_inherited':False,
            'scope':'Current explain-qualified selected meanings with complete conditions and dependencies. '
                'Preparation alone is not consumption or semantic approval.'}
    if request.draft is None:
        schema=ProcessAnswerDraftV2.model_json_schema();answer=schema['$defs']['QuestionAnswer']
        answer['required']=list(dict.fromkeys([*answer.get('required',[]),'request_plan']))
        answer['properties']['request_plan']={'$ref':'#/$defs/RequestPlan'}
        # Restrict the shared schema to available evidence roles before authoring.
        # The real binder independently rejects any attempted meaning reference.
        def original_evidence_only(node):
            if isinstance(node,list):
                for item in node:original_evidence_only(item)
            elif isinstance(node,dict):
                for key in ('oneOf','anyOf'):
                    if key in node:node[key]=[v for v in node[key] if v.get('$ref')!='#/$defs/MeaningCitation']
                node.get('discriminator',{}).get('mapping',{}).pop('meaning',None)
                for value in node.values():original_evidence_only(value)
        if not uses:original_evidence_only(schema)
        prepared={'status':'composition_ready','question':request.question,'questions':questions,
            'context_digest':context.context_digest,'sources':sources,'meaning_targets':targets,
            'source_evidence_mode':source_mode,'execution_targets':[{'result_digest':k,'value':v,
                **({'result_url':execution_pages[k]} if k in execution_pages else {})} for k,v in (execution_results or {}).items()],
            'user_request_fulfilled':False}
        return {**composition_model_material(prepared),'draft_schema':schema}
    if any(a.request_plan is None for a in request.draft.answers):raise ValueError('ANSWER_REQUEST_PLAN_REQUIRED')
    bound=timed_call('binding_checks',bind_process_answers_v2,request.draft,context=context,sources=sources,questions=questions,execution_results=execution_results)
    if uses:
        consumed=[c for a in bound['answers'] for group in ('sentences','limitations')
            for statement in a[group] for c in statement['citations'] if c['kind']=='meaning']
        source_mode={**source_mode,'meaning_reuse':bool(consumed),
            'consumed_meaning_references':[{'asset_revision':c['asset_revision'],'target_pointer':c['target_pointer'],
                'qualification_ref':c['meaning_use']['qualification_ref']} for c in consumed]}
    pages=_definition_source_pages(intake,principal,revisions,source_base_url=source_base_url)
    if meaning_reader is not None:meaning_reader.revalidate()
    return {'contract_version':'boi/native-answer-composition@1','status':'bound','question':request.question,
        'answers':render_bound_native_answer(bound,pages,publish_group=intake.source_intake.objects.put,execution_pages=execution_pages,source_readings=sources),
        '_source_reading_descriptors':source_reading_descriptors(sources),'bound_answer':bound,'source_evidence_mode':source_mode,
        **({'execution_links':{k:{'execution_ref':request.execution_ref,'url':v} for k,v in execution_pages.items()}} if execution_pages else {}),
        'user_request_fulfilled':False,'semantic_support_verified':False,
        'scope':('Current explain-qualified assertion, original-record and request-plan bindings; not final semantic approval.'
            if uses else 'Original-record, request-plan and execution bindings; not reviewed-meaning reuse or final semantic approval.')}


def combined_review_context(bindings,authorization,sources,*,source_definitions=()):
    """Resolve the union of already authorized contexts through the common DAG.

    This derives a request context, never a new review or persisted knowledge.
    Conflicting revisions/dependencies stay failures of the existing resolver.
    """
    from ..governed_runtime.task_knowledge import TaskKnowledgeContext,resolve_task_knowledge,KnowledgeUnavailable
    from ..governed_runtime.domain_asset_store import source_manifest_digest
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    contexts=[TaskKnowledgeContext.model_validate(b['context']) for b in bindings]
    assets={};roots=[];deferred=set()
    for context in contexts:
        if (context.principal_id,context.policy_digest,context.lane)!=(authorization.principal,authorization.policy_digest,'provisional'):
            raise ValueError('ANSWER_REVIEW_CONTEXT_AUTHORITY_MISMATCH')
        for asset in context.assets:
            if asset.revision in assets and assets[asset.revision]!=asset:
                raise ValueError('ANSWER_REVIEW_CONTEXT_ASSET_CONFLICT')
            assets[asset.revision]=asset
        for selection in context.selections:
            if selection.parent is None and selection.requirement not in roots:roots.append(selection.requirement)
            if selection.reason_code=='SOURCE_INVENTORY_DEFERRED_TO_SCOPED_READ':
                deferred.add((selection.parent,selection.requirement))
    def read(revision):
        if revision not in assets:raise KnowledgeUnavailable('MISSING')
        return assets[revision]
    context=resolve_task_knowledge(principal_id=authorization.principal,policy_digest=authorization.policy_digest,
        purpose='native answer composition from selected reviewed definitions'+(
            ':original-records:'+semantic_digest([r.model_dump(mode='json') for r in source_definitions]) if source_definitions else ''),
        source_manifest_digest=source_manifest_digest(sources),
        roots=tuple(sorted(roots,key=lambda r:(r.revision.ref,r.role,r.reason))),read_authorized_revision=read,
        lane='provisional',available_tools=frozenset(a.revision for a in assets.values() if a.kind=='tool'),
        defer_optional_requirement=lambda parent,req:(parent,req) in deferred and req.revision not in assets)
    if context.dependency_completeness!='complete':raise ValueError('ANSWER_REVIEW_CONTEXT_INCOMPLETE')
    if any(RevisionRef.model_validate(b['candidate_revision']) not in {a.revision for a in context.assets} for b in bindings):
        raise ValueError('ANSWER_REVIEW_CONTEXT_DEFINITION_MISSING')
    return context


def read_composition_review_bindings(intake, principal, reviews, *, prepared_bindings=None):
    """Retain exact review contracts; a legacy opinion is not a node review."""
    import json
    from ..governed_runtime.native_observation import read_native_observation
    from ..governed_runtime.native_definition_context import read_native_definition_authority
    from .native_process_review import read_native_process_review_binding
    authorization, work = intake._work(principal)
    bindings = []
    reusable=prepared_bindings or {}
    if set(reusable)-{r.ref for r in reviews}:
        raise ValueError('NATIVE_PREPARED_REVIEW_SCOPE_CHANGED')
    for ref in reviews:
        if ref.ref in reusable:
            from .native_process_review import reuse_native_process_review_binding
            bindings.append(reuse_native_process_review_binding(intake,principal,ref,reusable[ref.ref]))
            continue
        stored=work.assets.read(authorization=authorization,revision=ref,lane='provisional')
        from .asset_user_views import process_review_target
        if process_review_target(json.loads(stored['asset']['content_json'])) is not None:
            from .native_process_review import read_existing_process_review_binding
            bindings.append(read_existing_process_review_binding(intake,principal,ref))
            continue
        observation = read_native_observation(work, authorization, ref)
        if observation['value'].get('contract_version') in ('boi/native-definition-review@2','boi/native-definition-review@3'):
            bindings.append(read_native_process_review_binding(intake, principal, ref))
            continue
        authority, context = read_native_definition_authority(work, authorization, ref)
        stored = intake.read_asset(principal, DomainAssetReadRequest(revision=ref, lane='provisional'))
        # The common union reader below resolves these envelopes once.
        sources = [{'source': source} for source in stored['sources']]
        for revision in authority.definition_revisions:
            asset = next(a for a in context.assets if a.revision == revision)
            bindings.append({'candidate_revision': revision.model_dump(mode='json'),
                'review_revision': ref.model_dump(mode='json'), 'context': context.model_dump(mode='json'),
                'sources': sources, 'candidate_content': json.loads(asset.content_json),
                'review': observation['value'], 'usable_node_pointers': [], 'quarantined_node_pointers': [],
                'node_review_scope': 'unscoped_legacy_opinion'})
    return bindings


def compose_reviewed_definitions(intake,principal,request,*,source_base_url=None,execution_results=None,prepared_review_bindings=None):
    """Compose multiple existing node reviews without blending their approval.

    Source fields are read once as a union of actual record dependencies. Each
    definition's own review remains the gate for its full meaning closure.
    """
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    from .native_process_review import read_native_process_review_binding,check_native_process_answer_scopes
    from agent_kit.python.boi_process_claim_review import prepare_answer_review_dependencies
    if any(semantic_digest(v)!=k for k,v in (execution_results or {}).items()):
        raise ValueError('ANSWER_EXECUTION_DIGEST_MISMATCH')
    authorization,work=intake._work(principal)
    reviews=sorted((request.definition_review_revision,*request.additional_definition_review_revisions),key=lambda r:r.ref)
    bindings=read_composition_review_bindings(intake,principal,reviews,prepared_bindings=prepared_review_bindings)
    revisions=[RevisionRef.model_validate(b['candidate_revision']) for b in bindings]
    if len(revisions)!=len(set(revisions)):raise ValueError('ANSWER_REVIEW_DEFINITION_SCOPE_AMBIGUOUS')
    envelopes=[]
    for binding in bindings:
        for source in binding['sources']:
            if source['source'] not in envelopes:envelopes.append(source['source'])
    originals=sorted(set(request.source_definition_revisions)-set(revisions),key=lambda r:r.ref)
    original_envelopes=[]
    for revision in originals:
        stored=timed_call('current_asset_reading',intake.read_asset,principal,DomainAssetReadRequest(revision=revision,lane='provisional'))
        if stored['asset']['kind']!='definition':raise ValueError('DEFINITION_SOURCE_KIND_REQUIRED')
        for source in stored['sources']:
            if source not in original_envelopes:original_envelopes.append(source)
            if source not in envelopes:envelopes.append(source)
    envelopes.sort(key=semantic_digest)
    context=combined_review_context(bindings,authorization,envelopes,source_definitions=originals)
    reader=RequestSourceReader(intake,principal)
    sources=reader.read_for_assets(intake,principal,envelopes,[*revisions,*originals])
    original_readings=reader.read_for_assets(intake,principal,original_envelopes,originals) if originals else []
    original_fields=[{'source_revision_digest':s['source']['digest'],'span_ref':f['span_ref']}
        for s in original_readings for f in s['fields']]
    source_mode={'mode':'supplemental_original_records','definition_revisions':[r.model_dump(mode='json') for r in originals],
        'meaning_reuse':False,'definition_review_inherited':False,
        'scope':'These records supply original quotations and reading scopes only; selected reviews do not approve their meanings.'}
    scoped = [b for b in bindings if b.get('node_review_scope') != 'unscoped_legacy_opinion']
    legacy = [b['candidate_revision'] for b in bindings if b.get('node_review_scope') == 'unscoped_legacy_opinion']
    dependencies=[prepare_answer_review_dependencies(asset_revision=b['candidate_revision'],
        asset_content=b['candidate_content'],review_check=b['check']) for b in scoped]
    def check_scopes(answer):
        return check_native_process_answer_scopes(answer, scoped, dependencies=dependencies,
            unscoped_authorized_revisions=legacy)
    selected=None
    if request.meaning_selection is not None:
        selected={}
        for item in request.meaning_selection:
            if item.asset_revision not in revisions:raise ValueError('ANSWER_MEANING_SELECTION_REVISION_NOT_REVIEWED')
            selected.setdefault(item.asset_revision,[]).append(item.target_pointer)
    sources,source_selection,resolved_targets=selected_composition_sources(context,sources,selected,additional_bindings=original_fields)
    execution_pages={}
    if request.execution_ref is not None:
        from .native_formula import read_current_formula_execution,NativeFormulaRequest,formula_result_url
        record=read_current_formula_execution(work,authorization,request.execution_ref)
        original=NativeFormulaRequest.model_validate(record['request'])
        if original.formula.parameters and any(ref not in reviews for ref in original.parameter_reviews.values()):
            raise ValueError('ANSWER_EXECUTION_DEFINITION_MISMATCH')
        if record['result'].get('evaluation') is None:raise ValueError('ANSWER_EXECUTION_NOT_EVALUATED')
        observed={'request':record['request'],'result':record['result']};digest=semantic_digest(observed)
        execution_results={**(execution_results or {}),digest:observed}
        execution_pages[digest]=formula_result_url(request.execution_ref)
    questions=[{'id':'request','question':request.question,'max_body_characters':None}]
    if request.draft is None:
        targets=resolved_targets if resolved_targets is not None else []
        for revision in revisions:
            if resolved_targets is not None:continue
            if selected is not None and revision not in selected:continue
            targets.extend(meaning_citation_targets(context=context,sources=sources,asset_revision=revision,
                **({'target_pointers':selected[revision]} if selected is not None else {})))
        for target in targets:
            try:
                if target.get('binding_status')!='bound':raise ValueError('unresolved')
                check_scopes({'answers':[{'sentences':[{'citations':[{'kind':'meaning',**target}]}]}]})
            except ValueError:target['review_use_status']='unavailable_pending_or_quarantined'
            else:target['review_use_status']=('unscoped_legacy_opinion' if target['asset_revision'] in legacy else 'usable_with_reviewed_source_scope')
        schema=ProcessAnswerDraftV2.model_json_schema();answer=schema['$defs']['QuestionAnswer']
        answer['required']=list(dict.fromkeys([*answer.get('required',[]),'request_plan']))
        answer['properties']['request_plan']={'$ref':'#/$defs/RequestPlan'}
        prepared={'status':'composition_ready','question':request.question,'questions':questions,
            'context_digest':context.context_digest,'sources':sources,'meaning_targets':targets,
            **({'source_evidence_mode':source_mode} if originals else {}),
            'meaning_reviews':[{'review_revision':b['review_revision'],'candidate_revision':b['candidate_revision'],
                'findings':b.get('review_summary',b['review'])['findings'],'limitations':b.get('review_summary',b['review'])['limitations'],
                'usable_node_pointers':b['usable_node_pointers'],'quarantined_node_pointers':b['quarantined_node_pointers'],
                'scope':b.get('node_review_scope','selected_nodes'),
                'semantic_truth_proven':False} for b in bindings],
            'execution_targets':[{'result_digest':k,'value':v,
                **({'result_url':execution_pages[k]} if k in execution_pages else {})} for k,v in (execution_results or {}).items()],
            'draft_schema':schema,'user_request_fulfilled':False}
        from .native_composition_authoring import selected_review_pointer_inventory
        prepared['meaning_reviews']=[selected_review_pointer_inventory(b,targets)
            for b in prepared['meaning_reviews']]
        if selected is not None:prepared['meaning_selection_scope']={'selection_kind':'caller_selected_references',
            'includes':'selected_targets_and_required_closure','complete_meaning_inventory':False,
            'absence_proven':False,'semantic_support_verified':False,'source_delivery':source_selection}
        from agent_kit.python.boi_process_answer_stage import composition_model_material
        reusable={b['review_revision']['ref']:b for b in bindings
            if b.get('node_review_scope')!='unscoped_legacy_opinion'}
        return {**composition_model_material(prepared),'draft_schema':schema,
            '_prepared_review_bindings':reusable}
    if any(a.request_plan is None for a in request.draft.answers):raise ValueError('ANSWER_REQUEST_PLAN_REQUIRED')
    bound=timed_call('binding_checks',bind_process_answers_v2,request.draft,context=context,sources=sources,questions=questions,execution_results=execution_results)
    checked=check_scopes(bound)
    checked.extend({'review_revision':b['review_revision'],'candidate_revision':b['candidate_revision'],
        'scope':'unscoped_legacy_opinion','semantic_truth_proven':False}
        for b in bindings if b.get('node_review_scope')=='unscoped_legacy_opinion')
    pages=_definition_source_pages(intake,principal,[*revisions,*originals],source_base_url=source_base_url)
    return {'contract_version':'boi/native-answer-composition@1','status':'bound','question':request.question,
        'answers':render_bound_native_answer(bound,pages,publish_group=intake.source_intake.objects.put,execution_pages=execution_pages,source_readings=sources),
        'meaning_review_bindings':checked,'_source_reading_descriptors':source_reading_descriptors(sources),'bound_answer':bound,
        **({'source_evidence_mode':source_mode} if originals else {}),
        **({'execution_links':{k:{'execution_ref':request.execution_ref,'url':v} for k,v in execution_pages.items()}} if execution_pages else {}),
        'user_request_fulfilled':False,'semantic_support_verified':False,
        'scope':'Reviewed meanings retain their own node review; supplementary original records inherit no review. Source entailment and actual final delivery require verification.'}
