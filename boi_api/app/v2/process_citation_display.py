"""Read-only citation presentation from authorized, rebound Wiki source fields.

This labels existing evidence; it neither rewrites prose nor judges meaning.
Source metadata keys describe the input schema, never a question/answer rule.
"""
import copy
import json
from urllib.parse import urlsplit
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


def source_type_label(kind):
    # Explicit source provenance, not a process-name or answer selection rule.
    return {'user_conversation_transcription':'사용자 대화 자료 전사본',
            'synthetic_independent_test':'합성 시험 자료'}.get(kind,'저장된 원문 자료')


def statement_delivery_role(statement):
    """Carry the authored role and its dependencies without inferring from prose.

    Historical statements without a role stay unspecified. A recommendation's
    factual premises explain its background; they do not establish an obligation.
    """
    return {key: copy.deepcopy(statement[key]) for key in
            ('kind', 'basis_statement_pointers') if key in statement}


def citation_display(packet, sources):
    fields = {}
    for source in sources:
        for field in source['fields']:
            key=(source['source']['digest'],field['field_locator'])
            if key in fields and fields[key][0]['source']!=source['source']:
                # A digest-only citation cannot choose between two roles or
                # artifact identities. Never silently label it as the last one.
                raise ValueError('PROCESS_VIEW_SOURCE_IDENTITY_AMBIGUOUS')
            fields[key]=(source,field)
    entries = []; identities = {}; answers = []
    for ai, answer in enumerate(packet['answer']['answers']):
        displayed = {'question_id': answer['question_id'], 'body': answer['body'],
                     'sentences': [], 'limitations': []}
        if 'layout' in answer:displayed['layout']=answer['layout']
        for section in ('sentences', 'limitations'):
            for si, statement in enumerate(answer[section]):
                pointer = f'/answers/{ai}/{section}/{si}'
                item = {'text': statement['text'], 'pointer': pointer, 'source_numbers': [],
                        **statement_delivery_role(statement)}
                if 'basis_statement_pointers' in item:
                    item['basis_statement_pointers'] = [f'/answers/{ai}'+p
                        for p in item['basis_statement_pointers']]
                for ci,citation in enumerate(statement['citations']):
                    if citation['kind']=='source_scope':
                        source=next(s for s in sources if s['source']['digest']==citation['source_revision_digest'])
                        identity=('scope',source['source']['artifact_ref'],source['source']['role'],
                                  citation['source_revision_digest'],citation['reading_digest'])
                        if identity not in identities:
                            inventory=citation['field_inventory']
                            labels=[f for f in source['fields'] if f['field_locator'] in
                                    {i['field_locator'] for i in inventory} and
                                    f['field_locator'].rsplit('/',1)[-1] in ('process','title','source_locator')]
                            provenance=next((f for f in source['fields'] if f['field_locator']=='/provenance/kind'),None)
                            kind=provenance['text'] if provenance else 'unspecified'
                            entry={'number':len(entries)+1,'title':'제공 자료 전체의 확인 범위',
                                'source_type':source_type_label(kind),
                                'provenance_kind':kind,'source':source['source'],'field_locator':None,
                                'role':'source_scope','citation_reference':citation,'quotes':[],
                                'statement_pointers':[],'label_evidence':[{'field_locator':f['field_locator'],
                                    'span_ref':f['span_ref'],'content_digest':f['content_digest']} for f in labels+([provenance] if provenance else [])],
                                'scope_note':'표시된 읽기 범위에서 확인한 부족입니다. 다른 자료의 부재나 과학적 진위를 확인한 것은 아닙니다.'}
                            identities[identity]=entry;entries.append(entry)
                        entry=identities[identity]
                        if pointer not in entry['statement_pointers']:entry['statement_pointers'].append(pointer)
                        item['source_numbers'].append(entry['number'])
                    for binding in citation['source_bindings']:
                        source, field = fields[(binding['source_revision_digest'], binding['field_locator'])]
                        text = field['text']; start, end = binding['start'], binding['end']
                        if (not 0 <= start <= end <= len(text)
                                or byte_digest(text.encode()) != binding['field_content_digest']
                                or byte_digest(text[start:end].encode()) != binding['quote_digest']):
                            raise ValueError('PROCESS_VIEW_QUOTATION_DIGEST_MISMATCH')
                        # A source card is a material/item, not one semantic citation.
                        # Preserve every citation role/target and its exact packet path below.
                        meaning = {k: v for k, v in citation.items() if k not in
                                   ('source_bindings', 'quotation', 'evidence_digest')}
                        siblings = {f['field_locator']: f for f in source['fields']}
                        parent = field.get('record_locator', '')
                        label_fields = [siblings[p] for p in
                            (parent+'/process', parent+'/title', parent+'/name', parent+'/source_locator')
                            if p in siblings]
                        identity = (source['source']['artifact_ref'], source['source']['role'],
                                    binding['source_revision_digest'])
                        if identity not in identities:
                            provenance = siblings.get('/provenance/kind')
                            kind = provenance['text'] if provenance else 'unspecified'
                            source_type = source_type_label(kind)
                            title = ' · '.join(f['text'] for f in label_fields) or '제공 자료 '+str(len(entries)+1)
                            entry = {'number': len(entries)+1, 'title': title, 'source_type': source_type,
                                     'provenance_kind': kind, 'source': source['source'],
                                     'field_locator': binding['field_locator'], 'role': citation['kind'],
                                     'field_locators': [],
                                     'citation_reference': meaning, 'citation_references': [], 'quotes': [],
                                     'label_evidence': [{'field_locator': f['field_locator'],
                                         'span_ref': f['span_ref'], 'content_digest': f['content_digest']}
                                         for f in label_fields + ([provenance] if provenance else [])],
                                     'scope_note': ('읽은 자료 범위에서 확인한 부족이며 다른 자료의 부재를 뜻하지 않습니다.'
                                                    if citation['kind']=='source_scope' else None)}
                            identities[identity] = entry; entries.append(entry)
                        entry = identities[identity]
                        # Share the material card, while retaining each record's
                        # labels and exact revision/field boundaries separately.
                        label_evidence=[{'field_locator':f['field_locator'],
                            'span_ref':f['span_ref'],'content_digest':f['content_digest']} for f in label_fields]
                        scope={'source_revision_digest':binding['source_revision_digest'],
                            'record_locator':field.get('record_locator'),
                            'label_evidence':label_evidence}
                        scopes=entry.setdefault('record_scopes',[])
                        if scope not in scopes:scopes.append(scope)
                        for label in label_evidence:
                            if label not in entry['label_evidence']:entry['label_evidence'].append(label)
                        references=entry['citation_references']
                        reference=next((r for r in references if r['citation']==meaning),None)
                        if reference is None:
                            reference={'citation':meaning,'statement_pointers':[],'packet_citation_pointers':[]}
                            references.append(reference)
                        if pointer not in reference['statement_pointers']:reference['statement_pointers'].append(pointer)
                        packet_pointer='/answer'+pointer+f'/citations/{ci}'
                        if packet_pointer not in reference['packet_citation_pointers']:reference['packet_citation_pointers'].append(packet_pointer)
                        reference_index=references.index(reference)
                        if binding['field_locator'] not in entry['field_locators']:entry['field_locators'].append(binding['field_locator'])
                        quote = next((q for q in entry['quotes'] if q['binding']==binding), None)
                        if quote is None:
                            quote = {'text': text[start:end], 'binding': binding, 'statement_pointers': [], 'citation_reference_indices': [], 'direct_statement_pointers': []}
                            entry['quotes'].append(quote)
                        if citation['kind']=='source_quote' and pointer not in quote['direct_statement_pointers']:quote['direct_statement_pointers'].append(pointer)
                        if reference_index not in quote['citation_reference_indices']:quote['citation_reference_indices'].append(reference_index)
                        if pointer not in quote['statement_pointers']: quote['statement_pointers'].append(pointer)
                        if entry['number'] not in item['source_numbers']: item['source_numbers'].append(entry['number'])
                displayed[section].append(item)
        answers.append(displayed)
    from ..governed_runtime.citation_material_cards import material_source_cards
    source_cards=material_source_cards([{'source':entry['source'],'display_source_number':entry['number'],'citation_index':index,
        'record_scopes':entry.get('record_scopes',[]),'evidence_role':entry['role'],
        'citation_references':entry.get('citation_references',[]),'quotes':entry['quotes'],
        **({'reading_scope':entry['citation_reference'],'statement_pointers':entry.get('statement_pointers',[])} if entry['role']=='source_scope' else {})} for index,entry in enumerate(entries)])
    for card in source_cards:
        entry=entries[card['references'][0]['citation_index']]
        card.update(title=entry['title'],source_type=entry['source_type'])
    return {'origin': 'wiki_authorized_result_read', 'answers': answers, 'sources': entries,'source_cards':source_cards,
            'prose_rewritten': False, 'semantic_support_proven': False}


def quote_target_index(entry,pointer):
    """Prefer attached content evidence over attached source-label metadata.

    Both bindings remain in the same source card. A label-only statement still
    opens its label quote; no new relevance or semantic judgment is invented.
    """
    labels={e['field_locator'] for e in entry.get('label_evidence',[])}
    matches=[i for i,q in enumerate(entry['quotes']) if pointer in q['statement_pointers']]
    direct=[i for i in matches if pointer in entry['quotes'][i].get('direct_statement_pointers',[])]
    direct=sorted(direct,key=lambda i:entry['quotes'][i]['binding']['field_locator'] in labels)
    return next(iter(direct),next((i for i in matches if entry['quotes'][i]['binding']['field_locator'] not in labels),
        matches[0] if matches else None))


def visible_quote_indices(entry):
    """Show direct quotations first; keep all graph evidence in source detail."""
    chosen={i for i,q in enumerate(entry['quotes']) if q.get('direct_statement_pointers')}
    pointers={p for q in entry['quotes'] for p in q['statement_pointers']}
    for pointer in pointers:
        index=quote_target_index(entry,pointer)
        if index is not None:chosen.add(index)
    return chosen


def statement_source_anchor(entry, pointer):
    """Keep compound claims attached to all their existing source evidence."""
    quote=quote_target_index(entry,pointer)
    labels={e['field_locator'] for e in entry.get('label_evidence',[])}
    attached=[q for q in entry['quotes'] if pointer in q['statement_pointers']
              and q['binding']['field_locator'] not in labels]
    if len(attached)>1:
        quote=None
    return f"#source-{entry['number']}"+(f'-quote-{quote}' if quote is not None else '')


def process_display_groups(display):
    from ..governed_runtime.citation_material_cards import material_display_groups
    return material_display_groups(display.get('source_cards',[]),len(display['sources']))


def process_display_numbers(display):
    return {display['sources'][i]['number']:card['number']
        for card in process_display_groups(display) for i in card['reference_indices']}


def citation_text(display, *, source_url=None, include_quotes=True):
    """Same readable evidence for text-only MCP/REST/CLI consumers."""
    lines = []
    scopes={e['number'] for e in display['sources'] if e['role']=='source_scope'}
    numbers=process_display_numbers(display)
    label=lambda n:('확인 범위 ' if n in scopes else '')+str(numbers[n])
    for answer in display['answers']:
        def numbered(item):
            def link(n):
                shown='['+label(n)+']'
                if not source_url:return shown
                entry=next(e for e in display['sources'] if e['number']==n)
                anchor=statement_source_anchor(entry,item['pointer'])
                return shown+'('+source_url+anchor+')'
            return item['text'] + ''.join(' '+link(n) for n in item['source_numbers'])
        if answer.get('layout'):
            from agent_kit.python.boi_process_answer_layout import render_layout
            def resolve(pointer):
                _,section,index=pointer.split('/')
                return numbered(answer[section][int(index)])
            lines.append(render_layout(answer['layout'],resolve))
        else:
            for section in ('sentences', 'limitations'):
                for item in answer[section]:lines.append(numbered(item))
    named=set()
    for entry in display['sources']:
        number=numbers[entry['number']]
        if number not in named:
            lines.append(f"[{number}] {entry['source_type']} · {entry['title']}")
            named.add(number)
        visible=visible_quote_indices(entry)
        for i,quote in enumerate(entry['quotes']):
            if not include_quotes:continue
            if i not in visible:continue
            if len(entry.get('field_locators',[]))>1:
                lines.append('원문 항목: '+quote['binding']['field_locator'])
            lines.append('> '+quote['text'])
        if entry['scope_note']: lines.append(entry['scope_note'])
    return '\n\n'.join(lines)


def _index_meaning_graph(citation,nodes):
    uses=[]
    for entry in citation.get('graph_evidence',[]):
        node={'asset_revision':entry.get('asset_revision',citation['asset_revision']),
            'target_pointer':entry['target_pointer'],'value':entry['value'],
            'source_bindings':entry['source_bindings']}
        key=semantic_digest(node)
        nodes.setdefault(key,{'node_id':key,**copy.deepcopy(node)})
        uses.append({'node_id':key,**{k:copy.deepcopy(v) for k,v in entry.items()
            if k not in ('value','source_bindings','asset_revision','target_pointer')}})
    return uses


def process_meaning_catalog(targets):
    """Losslessly index selectable closures; preserve unresolved candidates.

    Node identity is shared with final delivery. Selection and graph roles stay
    attached to each target; source locations never become business relations.
    """
    nodes={};indexed=[]
    for target in targets:
        if 'graph_nodes' in target or 'graph_evidence' not in target:
            raise ValueError('PROCESS_MEANING_CATALOG_EXPECTS_BOUND_GRAPHS')
        indexed.append({**{k:copy.deepcopy(v) for k,v in target.items() if k!='graph_evidence'},
            'graph_nodes':_index_meaning_graph(target,nodes)})
    return {'meaning_nodes':list(nodes.values()),'meaning_citation_targets':indexed}


def process_semantic_basis(packet):
    """Keep existing meaning/source bindings when projecting a full answer.

    This is an index of the existing binder output, not another ontology or
    semantic inference. Roles belong to each use; shared nodes occur only once.
    """
    nodes={};links=[];source_only=[];unresolved=[];plan_links=[];statement_kinds=[]
    for ai,answer in enumerate(packet.get('answer',{}).get('answers',[])):
        for fi,facet in enumerate(answer.get('request_plan',{}).get('facets',[])):
            pointer=f'/answers/{ai}/request_plan/facets/{fi}';uses=[]
            for citation in facet.get('citations',[]):
                if citation['kind']!='meaning':continue
                if not citation.get('graph_evidence'):
                    unresolved.append({'facet_pointer':pointer,'reason':'meaning_graph_not_available'})
                for use in _index_meaning_graph(citation,nodes):
                    if use not in uses:uses.append(use)
            if uses:
                plan_links.append({'facet_pointer':pointer,'question_id':answer['question_id'],
                    'statement_pointers':copy.deepcopy(facet.get('statement_pointers',[])),
                    'nodes':uses,'semantic_support':'not_evaluated'})
        for part in ('sentences','limitations'):
            for si,statement in enumerate(answer.get(part,[])):
                pointer=f'/answers/{ai}/{part}/{si}';uses=[]
                statement_kinds.append({'statement_pointer':pointer,'question_id':answer['question_id'],
                    'kind':statement.get('kind'),
                    **({'basis_statement_pointers':copy.deepcopy(statement['basis_statement_pointers'])}
                        if 'basis_statement_pointers' in statement else {})})
                for citation in statement['citations']:
                    if citation['kind']!='meaning':continue
                    if not citation.get('graph_evidence'):
                        unresolved.append({'statement_pointer':pointer,'reason':'meaning_graph_not_available'})
                    for use in _index_meaning_graph(citation,nodes):
                        if use not in uses:uses.append(use)
                if uses:links.append({'statement_pointer':pointer,'question_id':answer['question_id'],'nodes':uses})
                elif not any(c['kind']=='meaning' for c in statement['citations']) and statement.get('kind') not in ('runtime_state','evidence_gap'):
                    source_only.append(pointer)
    plans=[{'question_id':a['question_id'],'plan':copy.deepcopy(a['request_plan'])}
        for a in packet.get('answer',{}).get('answers',[]) if a.get('request_plan')]
    return {**({'request_plans':plans,'request_plan_links':plan_links} if plans else {}),'nodes':list(nodes.values()),'statement_links':links,
        'statement_kinds':statement_kinds,'statement_kind_authority':'author_proposed_not_verified','source_only_statements':source_only,
        'unresolved_meaning_links':unresolved,'origin':'existing_bound_answer','semantic_truth_proven':False,
        'scope':'Candidate meaning retains original-source bindings; source-only statements have no asserted meaning correspondence.'}


def process_answer_delivery(view, *, source_base_url=None):
    """Present a rebound answer; full evidence stays on its protected revision.

    No prose is generated, no source is discarded from the stored result, and
    no review is promoted. Compact references retain each exact quote target.
    This is a presentation contract, not proof of final host delivery.
    """
    display = view['citation_display']
    original = citation_text(display, source_url=view.get('product_url'))
    if not view['readable_text'].startswith(original):
        raise ValueError('PROCESS_AGENT_DELIVERY_TEXT_CHANGED')
    path = view['ui_url']
    if not isinstance(path, str) or not path.startswith('/domain-results/'):
        raise ValueError('PROCESS_DELIVERY_PRODUCT_ROUTE_REQUIRED')
    source_url = path
    base = source_base_url
    if base:
        parsed = urlsplit(base)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('PROCESS_DELIVERY_PUBLIC_ORIGIN_INVALID')
        source_url = base.rstrip('/') + path
    notes = view['delivery_notes']
    if not isinstance(notes, list) or any(not isinstance(n, str) for n in notes):
        raise ValueError('PROCESS_DELIVERY_NOTES_INVALID')
    text = citation_text(display, source_url=source_url, include_quotes=False)
    if notes:
        text += '\n\n' + '\n'.join(notes)
    citations = []
    numbers=process_display_numbers(display)
    for entry in display['sources']:
        number = entry['number']
        quotes = [
            {'url': source_url + f'#source-{number}-quote-{i}',
             'field_locator': quote['binding']['field_locator'],
             'quote_digest': quote['binding']['quote_digest'],
             'statement_pointers': copy.deepcopy(quote['statement_pointers'])}
            for i, quote in enumerate(entry['quotes'])]
        citations.append({'number': numbers[number], 'source_anchor_number':number, 'title': entry['title'],
                          'source_type': entry['source_type'],
                          'source': copy.deepcopy(entry['source']),
                          'role': entry['role'], 'scope_note': entry['scope_note'],
                          'url': source_url + f'#source-{number}', 'quotes': quotes,
                          'statement_pointers':list(dict.fromkeys([*entry.get('statement_pointers',[]),
                              *(p for quote in entry['quotes'] for p in quote['statement_pointers'])]))})
    for entry,citation in zip(display['sources'],citations):
        if entry['role']=='source_scope':
            citation['reading_scope']={k:copy.deepcopy(entry['citation_reference'][k])
                for k in ('source_revision_digest','reading_digest','manifest_ref','manifest_digest','field_inventory')}
    # Resolve the existing statement pointers before discarding the full packet.
    # Scope citations have no quotation rows; their statement edges are equally
    # necessary. Do not infer correspondence from prose or document adjacency.
    entries={entry['number']:entry for entry in display['sources']}
    answer_units=[]
    for answer in display['answers']:
        for section in ('sentences','limitations'):
            for statement in answer[section]:
                links=[]
                for number in statement['source_numbers']:
                    entry=entries[number]
                    links.append({'number':numbers[number],'role':entry['role'],
                        'url':source_url+statement_source_anchor(entry,statement['pointer'])})
                answer_units.append({'statement_pointer':statement['pointer'],'question_id':answer['question_id'],
                    'text':statement['text'],'citations':links,**statement_delivery_role(statement)})
    source_cards=[]
    for card in display.get('source_cards',[]):
        projected={k:copy.deepcopy(v) for k,v in card.items() if k!='references'}
        projected['references']=[]
        for reference in card['references']:
            index=reference['citation_index']
            citation=citations[index]
            projected['references'].append({k:copy.deepcopy(v) for k,v in reference.items()
                if k not in ('quotes','citation_references','reading_scope')})
            projected['references'][-1].update(citation_url=citation['url'],quotes=copy.deepcopy(citation['quotes']),
                **({'reading_scope':copy.deepcopy(citation['reading_scope'])} if 'reading_scope' in citation else {}))
        source_cards.append(projected)
    revision = copy.deepcopy(view['stored_answer_revision'])
    return {'contract_version': 'boi/process-answer-delivery@1',
            'readable_text': text, 'answer_units':answer_units,'citations': citations,
            'source_cards':source_cards,
            'semantic_basis_ref': {'tool': 'boi_process_result',
                'arguments': {'revision': copy.deepcopy(revision)},
                'scope': 'same_stored_answer_revision_full_evidence'},
            'delivery_notes': copy.deepcopy(notes),
            'user_request_fulfilled': view['user_request_fulfilled'],
            'fulfillment_scope': 'stored_answer_review_not_final_host_observation',
            'stored_answer_revision': revision, 'ui_url': path,
            'product_url': source_url,
            'link_scope': 'configured_public_origin' if base else 'relative_product_route',
            'details': {'tool': 'boi_process_result', 'arguments': {'revision': revision},
                        'ui_url': source_url},
            'authority': view['authority'], 'scientific_correctness': 'not_evaluated',
            'new_model_runs': 0, 'new_review_receipts': 0}


def read_process_answer_or_navigation(intake, principal, request, *, source_base_url=None):
    """Offer the authorized asset's actual reader after a tool/contract mismatch."""
    try:
        view=intake.read_process_result(principal,request)
    except ValueError as error:
        if str(error)!='PROCESS_RESULT_CONTRACT_REQUIRED':raise
        stored=intake.read_asset(principal,request)
        actions=stored.get('available_user_views',[])
        if not actions:raise
        return {'status':'requires_answer_reader','revision':stored['revision'],
            'available_actions':actions,'current_request_fulfilled':False,
            'new_model_runs':0,'query_reexecuted':False}
    return process_answer_delivery(view,source_base_url=source_base_url)
