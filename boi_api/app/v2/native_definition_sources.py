"""Read-only source projection of an existing immutable definition revision.

Declared evidence locations are checked, never inferred from business names.
A located quote does not establish the truth of the associated interpretation.
"""
import html
import copy
from urllib.parse import urlsplit, unquote
from ..governed_runtime.native_observation import _json


NATIVE_MEANING_LINK_ROLES = frozenset(('subject_identity', 'object_identity',
    'condition', 'exception', 'applicability', 'counterevidence', 'declared_dependency'))


def native_meaning_links(value, pointer):
    """Read explicit, locally addressed use dependencies, never infer relations.

    Each relation owns original evidence and is itself a reviewable meaning.
    A counterevidence link requires reading a disagreement; it does not declare
    which side is true. These roles are not folder or document-order relations.
    """
    links = value.get('meaning_links', [])
    if not isinstance(links, list):
        raise ValueError('NATIVE_MEANING_LINKS_INVALID')
    result = []; seen = set()
    for i, link in enumerate(links):
        if (not isinstance(link, dict) or set(link) != {'relation', 'target_pointer', 'evidence'}
                or not isinstance(link['relation'], str) or link['relation'] not in NATIVE_MEANING_LINK_ROLES
                or not isinstance(link['target_pointer'], str)
                or not link['target_pointer'].startswith('/') or not link['evidence']):
            raise ValueError('NATIVE_MEANING_LINK_INVALID')
        key = (link['relation'], link['target_pointer'])
        if key in seen:
            raise ValueError('NATIVE_MEANING_LINK_DUPLICATE')
        seen.add(key)
        result.append({'relation_pointer': pointer + '/meaning_links/' + str(i),
            'relation': link['relation'], 'target_pointer': link['target_pointer']})
    return result


def validate_native_meaning_links(content):
    """Check evidence-owner references at intake; not semantic qualification."""
    owners = {b['meaning_context']['pointer']: b['meaning_context']['value']
        for b in project_definition_evidence(content, [], '') if b.get('meaning_context')}
    for pointer, value in owners.items():
        for link in native_meaning_links(value, pointer):
            if link['target_pointer'] not in owners or link['relation_pointer'] not in owners:
                raise ValueError('NATIVE_MEANING_LINK_TARGET_UNAVAILABLE')


def field_anchor(source_digest, span_ref):
    return 'field-'+source_digest.removeprefix('sha256:')+'-'+span_ref.rsplit(':',1)[-1]


def _source_range_available(field, start, end):
    """Zero-length locations name a recorded empty field, not arbitrary text."""
    return (type(start) is int and type(end) is int and isinstance(field.get('text'),str)
        and (0<=start<end<=len(field['text']) or
            (start==end==0 and field['text']=='' and field.get('field_state')=='empty')))


def source_field_links(sources, url):
    """Address original fields without asserting that they support a claim."""
    return [{"source_revision_digest": source["source"]["digest"],
             "span_ref": field["span_ref"], "field_locator": field["field_locator"],
             "content_digest": field.get("content_digest"),
             "url": url + "#" + field_anchor(source["source"]["digest"], field["span_ref"])}
            for source in sources for field in source["fields"]]


def project_definition_evidence(content, sources, url):
    if content.get('contract_version') in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
        # Reuse the existing bound process addresses. This display projection
        # does not rewrite the stored draft or qualify its semantic claims.
        draft=copy.deepcopy(content['draft'])
        fields={(s['source']['digest'],f['span_ref']):f for s in sources for f in s['fields']}
        invalid=set();seen=set()
        for binding in content.get('bindings',[]):
            pointer=binding['target_pointer'];value=draft
            try:
                for part in pointer.lstrip('/').split('/'):
                    key=part.replace('~1','/').replace('~0','~')
                    value=value[int(key)] if isinstance(value,list) else value[key]
            except (KeyError,IndexError,ValueError,TypeError):
                continue
            if not isinstance(value,dict) or 'quote' not in value:continue
            field=fields.get((binding['source_revision_digest'],binding['span_ref']))
            start,end=binding.get('start'),binding.get('end')
            valid=(pointer not in seen and field is not None
                and value.get('field_locator')==binding['field_locator']==field['field_locator']
                and isinstance(start,int) and isinstance(end,int)
                and 0<=start<end<=len(field['text']) and field['text'][start:end]==value['quote'])
            if not valid:invalid.add(pointer)
            seen.add(pointer)
            value.update(source_revision_digest=binding['source_revision_digest'],span_ref=binding['span_ref'])
        projected=project_definition_evidence(draft,sources,url)
        for entry in projected:
            if entry['definition_pointer'] in invalid:
                entry['status']='unresolved';entry.pop('url',None)
        return projected
    fields={(s['source']['digest'],f['span_ref']):f for s in sources for f in s['fields']}
    located_fields={}
    for source in sources:
        for field in source['fields']:
            located_fields.setdefault((source['source']['digest'],field['field_locator']),[]).append(field)
    result=[]
    evidence_keys={'source_revision_digest','field_locator','quote'}
    def evidence_container(value):
        return ((isinstance(value,dict) and evidence_keys<=value.keys())
            or (isinstance(value,list) and bool(value) and all(evidence_container(x) for x in value)))
    def walk(value,pointer,owner=None):
        if isinstance(value,dict):
            # This is the existing source-evidence shape, not a meaning classifier.
            if evidence_keys<=value.keys():
                entry={'definition_pointer':pointer,'evidence':value.copy(),'status':'unresolved',
                    'semantic_support_verified':False}
                if owner is not None:
                    owner_pointer,owner_value=owner
                    entry['meaning_context']={'pointer':owner_pointer,
                        'value':copy.deepcopy({k:v for k,v in owner_value.items() if not evidence_container(v)}),
                        'scope_inherited':False,'semantic_support_verified':False}
                field=None
                if isinstance(value['source_revision_digest'],str):
                    if 'span_ref' in value:
                        if isinstance(value['span_ref'],str):field=fields.get((value['source_revision_digest'],value['span_ref']))
                    elif isinstance(value['field_locator'],str):
                        matches=located_fields.get((value['source_revision_digest'],value['field_locator']),[])
                        if len(matches)==1:
                            field=matches[0]
                            # This stable field identity is derived from the actual
                            # authorized source read, never invented by the model.
                            entry['evidence']['span_ref']=field['span_ref']
                quote=value['quote']
                if (field is not None and field['field_locator']==value['field_locator']
                        and isinstance(quote,str) and ((bool(quote) and quote in field['text'])
                            or (quote==field['text']=='' and field.get('field_state')=='empty'))):
                    entry.update(status='located' if quote else 'located_empty',quote=quote,
                        field_state=field.get('field_state'),
                        url=url+'#'+field_anchor(value['source_revision_digest'],entry['evidence']['span_ref']))
                result.append(entry)
            for key,child in value.items():
                walk(child,pointer+'/'+str(key).replace('~','~0').replace('/','~1'),(pointer,value))
        elif isinstance(value,list):
            for i,child in enumerate(value):walk(child,pointer+'/'+str(i),owner)
    walk(content,'')
    return result


def declared_meaning_index(content, *, include_source_expressions=False):
    """Candidate addresses from the existing evidence owners, without raw text.

    This projection deliberately does not resolve evidence or inherit a parent's
    conditions. The existing selected resolver performs those checks on detail
    reads. No question, ranking, review opinion or answer participates here.
    """
    evidence_keys={'source_revision_digest','field_locator','quote'}
    omitted=object()
    def without_evidence(value):
        if isinstance(value,dict):
            if evidence_keys<=value.keys() or {'field_locator','quote'}<=value.keys():
                return omitted
            return {k:filtered for k,v in value.items() if (filtered:=without_evidence(v)) is not omitted}
        if isinstance(value,list):
            return [filtered for v in value if (filtered:=without_evidence(v)) is not omitted]
        return value
    allowed=None
    if content.get('contract_version') in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
        from agent_kit.python.boi_process_answer_v2 import ProcessKnowledgeDraft
        draft=ProcessKnowledgeDraft.model_validate(content['draft'])
        allowed={f'/records/{ri}/{kind}/{i}' for ri,record in enumerate(draft.records)
            for kind in ('terms','assertions') for i,_ in enumerate(getattr(record,kind))}
    nodes={}
    for binding in project_definition_evidence(content,[],''):
        owner=binding.get('meaning_context')
        if owner is None or allowed is not None and owner['pointer'] not in allowed:continue
        pointer=owner['pointer']
        node=nodes.setdefault(pointer,{'target_pointer':pointer,'value':without_evidence(owner['value']),
            'evidence_pointers':[], 'scope_inherited':False})
        node['evidence_pointers'].append(binding['definition_pointer'])
        if include_source_expressions:
            # Original lexical expressions are attached only through this
            # existing evidence owner. They are not synonyms, translations or
            # proof that the declared meaning is faithful to the source.
            evidence=binding['evidence']
            node.setdefault('source_expressions',[]).append({
                'evidence_pointer':binding['definition_pointer'],
                'source_revision_digest':evidence['source_revision_digest'],
                'field_locator':evidence['field_locator'],'quote':evidence['quote']})
    return list(nodes.values())


def project_meaning_source_fields(sources, bindings):
    """Preserve exact original fields for a resolved meaning dependency closure.

    Source envelopes remain present even when none of their fields were selected;
    this keeps the authorized source context distinct from delivered evidence.
    All quote occurrences, structural metadata and field states remain intact.
    """
    used={(b['source_revision_digest'],b['span_ref']) for b in bindings}
    available={(s['source']['digest'],f['span_ref']) for s in sources for f in s['fields']}
    if not used<=available:raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
    result=[]
    for source in sources:
        fields=[f for f in source['fields'] if (source['source']['digest'],f['span_ref']) in used]
        manifest=copy.deepcopy(source['manifest'])
        if isinstance(manifest.get('fields'),list):
            manifest['fields']=[f for f in manifest['fields'] if (source['source']['digest'],f['span_ref']) in used]
        manifest.update(projection_scope='selected_meaning_evidence_fields',
            validated_field_count=len(source['fields']),delivered_field_count=len(fields),absence_proven=False)
        result.append({**source,'manifest':manifest,'fields':copy.deepcopy(fields)})
    return result


def selected_source_model_view(view):
    """Deliver exact fields used by the resolved closure, not the full record.

    Independent source validation still reads the declared record scope. Report
    that separately from what the model receives. The protected original view
    retains that complete context and all unresolved evidence.
    """
    from agent_kit.python.boi_process_answer_v2 import source_scope_reference
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    selection=view['meaning_selection']
    result=copy.deepcopy(view)
    result['validated_source_scopes']=[{
        **{k:v for k,v in scope.items() if k!='field_inventory'},
        'validated_field_count':len(scope.get('field_inventory',[])),
        'inventory_read':{'tool':'boi_knowledge_read','arguments':{
            'revision':view['definition_revision'],'view':'definition_sources'}}}
        for scope in result.pop('source_scopes')]
    result['sources']=project_meaning_source_fields(view['sources'],selection['quotations'])
    result['source_scopes']=[source_scope_reference({'source':s['source'],'manifest':s['manifest'],
        'reading_digest':semantic_digest(s),'fields':{f['field_locator']:f for f in s['fields']}}) for s in result['sources']]
    result['source_field_links']=source_field_links(result['sources'],view['url'])
    # The selected graph already binds each meaning to its exact original spans.
    # Do not resend all unselected owners and their evidence in another shape.
    result.pop('evidence_bindings',None)
    result['detail_read']={'tool':'boi_knowledge_read','arguments':{
        'revision':view['definition_revision'],'view':'definition_sources'}}
    result['selection_scope']={'coverage':'selected_meaning_and_declared_dependency_closure',
        'absence_proven':False,'full_context_url':view['url'],
        'validated_fields':sum(len(s['fields']) for s in view['sources']),
        'delivered_fields':sum(len(s['fields']) for s in result['sources'])}
    if result.get('source_paging'):
        result['source_paging']['validated_read_fields']=result['source_paging']['read_fields']
        result['source_paging']['read_fields']=result['selection_scope']['delivered_fields']
    return result


def read_definition_sources(intake,principal,request,*,source_base_url=None,_source_reader=None,meaning_pointer=None,source_offset=None,meaning_group=None):
    from .process_review_binding import read_sources
    stored=intake.read_asset(principal,request)
    if stored['asset']['kind'] not in ('definition','source'):raise ValueError('DEFINITION_SOURCE_KIND_REQUIRED')
    content=_json(stored['asset']['content_json'])
    if meaning_group is not None and (meaning_pointer is not None or source_offset is not None):
        raise ValueError('DEFINITION_SOURCE_SELECTION_AMBIGUOUS')
    selected_group=None;literal_group=None
    if meaning_group is not None:
        import json
        from ..governed_runtime.source_envelope import byte_digest
        from ..governed_runtime.semantic_binding_contract import RevisionRef,Digest
        from pydantic import TypeAdapter
        group_ref=TypeAdapter(Digest).validate_python('sha256:'+meaning_group)
        raw=intake.source_intake.objects.get(group_ref)
        if len(raw)>262144 or byte_digest(raw)!=group_ref:raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
        selected_group=_json(raw.decode())
        if isinstance(selected_group,dict) and selected_group.get('contract_version')=='boi/source-field-selection@1':
            if (set(selected_group)!={'contract_version','definition_revision','source_bindings'}
                    or RevisionRef.model_validate(selected_group['definition_revision']).model_dump(mode='json')!=stored['revision']
                    or stored['asset']['kind']!='definition'):
                raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
            bindings=selected_group['source_bindings']
            keys={'source_revision_digest','span_ref','field_locator','start','end'}
            if (not isinstance(bindings,list) or not 1<=len(bindings)<=256
                    or any(not isinstance(b,dict) or set(b)!=keys
                        or any(not isinstance(b[k],str) for k in ('source_revision_digest','span_ref','field_locator'))
                        or type(b['start']) is not int or type(b['end']) is not int for b in bindings)):
                raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
            try:
                for binding in bindings:
                    if not binding['span_ref'].startswith('EvidenceSpan:'):
                        raise ValueError('invalid evidence reference')
                    TypeAdapter(Digest).validate_python(binding['span_ref'].removeprefix('EvidenceSpan:'))
                    TypeAdapter(Digest).validate_python(binding['source_revision_digest'])
            except ValueError:
                raise ValueError('DEFINITION_SOURCE_GROUP_INVALID') from None
            literal_group=selected_group;selected_group=None
        if selected_group is None and literal_group is None:
            raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
    if selected_group is not None:
        if (not isinstance(selected_group,dict) or set(selected_group)!={'contract_version','definition_revision','meaning_pointers','read_scopes'}
                or selected_group['contract_version']!='boi/source-meaning-selection@1'
                or RevisionRef.model_validate(selected_group['definition_revision']).model_dump(mode='json')!=stored['revision']
                or stored['asset']['kind']!='definition'):
            raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
        pointers=selected_group['meaning_pointers']
        if (not isinstance(pointers,list) or not 1<=len(pointers)<=128
                or any(not isinstance(p,str) or (p!='' and not p.startswith('/')) or len(p)>2048 for p in pointers)
                or pointers!=sorted(set(pointers))):raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
        if (not isinstance(selected_group['read_scopes'],list) or len(selected_group['read_scopes'])>100
                or any(not isinstance(s,dict) or set(s)!={'source_revision_digest','reading_digest','manifest_digest'}
                    or any(not isinstance(v,str) for v in s.values()) for s in selected_group['read_scopes'])):
            raise ValueError('DEFINITION_SOURCE_GROUP_INVALID')
    if isinstance(content,dict) and content.get('contract_version') in (
            'boi/workbook-source-records@1','boi/workbook-source-index@1'):
        if meaning_pointer is not None:raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
        return _read_workbook_sources(intake,principal,stored,request,content,
            source_base_url=source_base_url,offset=source_offset)
    source_names={}
    if stored['asset']['kind']=='definition':
        from .process_review_binding import RequestSourceReader
        reader=_source_reader or RequestSourceReader(intake,principal)
        # A retained citation names its historical projection, not today's
        # parser output. Restore only the selected binding's registered spans;
        # an ordinary original-record read continues to use its own projection.
        recorded=(literal_group if literal_group is not None else content
            if (selected_group is not None or meaning_pointer is not None)
                and isinstance(content,dict)
                and content.get('contract_version') in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2') else None)
        if literal_group is not None and isinstance(content,dict) and isinstance(content.get('source_record'),dict):
            extra={}
            for binding in literal_group['source_bindings']:
                extra.setdefault(binding['source_revision_digest'],[]).append(binding['span_ref'])
            sources=reader.read_for_assets(intake,principal,stored['sources'],[stored['revision']],
                additional_field_refs=extra)
        elif recorded is not None:
            from .process_review_binding import read_recorded_sources
            sources=read_recorded_sources(intake,principal,stored['sources'],recorded)
        else:
            sources=reader.read_for_assets(intake,principal,stored['sources'],[stored['revision']])
        source_names=reader.source_display_names()
    else:
        sources=(read_sources(intake,principal,stored['sources']) if _source_reader is None
            else _source_reader.read(intake,principal,stored['sources']))
    digest=stored['revision']['revision_digest'].removeprefix('sha256:')
    origin=(source_base_url or '').rstrip('/')
    parsed=urlsplit(origin)
    url=(origin if parsed.scheme in ('http','https') and parsed.netloc else '')+'/native-definitions/'+digest
    content=_json(stored['asset']['content_json'])
    from agent_kit.python.boi_process_answer_v2 import source_scope_reference
    from ..governed_runtime.semantic_binding_contract import semantic_digest
    scopes=[source_scope_reference({'source':s['source'],'manifest':s['manifest'],
        'reading_digest':semantic_digest(s),'fields':{f['field_locator']:f for f in s['fields']}}) for s in sources]
    selection = (_selected_meaning(intake,principal,stored,sources,
        selected_group['meaning_pointers'] if selected_group is not None else meaning_pointer)
        if selected_group is not None or meaning_pointer is not None else None)
    if literal_group is not None:
        quotations=[];seen=set()
        for binding in literal_group['source_bindings']:
            key=tuple(binding[k] for k in ('source_revision_digest','span_ref','field_locator','start','end'))
            fields=[f for s in sources if s['source']['digest']==binding['source_revision_digest']
                for f in s['fields'] if f['span_ref']==binding['span_ref'] and f['field_locator']==binding['field_locator']]
            if key in seen or len(fields)!=1 or not _source_range_available(fields[0],binding['start'],binding['end']):
                raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
            seen.add(key)
            quotations.append({**binding,'quote':fields[0]['text'][binding['start']:binding['end']]})
        selection={'graph_evidence':[],'quotations':quotations,'selection_kind':'original_spans',
            'group_ref':'sha256:'+meaning_group,'semantic_support_verified':False}
    if selected_group is not None:
        actual={s['source_revision_digest']:s for s in scopes}
        for expected in selected_group['read_scopes']:
            if (set(expected)!={'source_revision_digest','reading_digest','manifest_digest'}
                    or expected['source_revision_digest'] not in actual
                    or any(actual[expected['source_revision_digest']].get(k)!=v for k,v in expected.items())):
                raise ValueError('DEFINITION_SOURCE_GROUP_SCOPE_CHANGED')
        selection['read_scope_sources']=[s['source_revision_digest'] for s in selected_group['read_scopes']]
        selection['group_ref']='sha256:'+meaning_group
    paging=None
    if len(sources)==1 and sources[0]['manifest'].get('projection_scope')=='selected_source_fields':
        inventories=[d for d in stored['asset']['dependencies'] if d['role']=='source_inventory']
        if len(inventories)==1:
            target=inventories[0]['revision']['revision_digest'].removeprefix('sha256:')
            paging={'total_fields':sources[0]['manifest']['total_field_count'],'read_fields':len(sources[0]['fields']),
                'offset':None,'full_source_url':url.rsplit('/',1)[0]+'/'+target+'?source_offset=0','next_url':None}
    return {**({'meaning_selection':selection} if selection is not None else {}),
        **({'review_discovery':{'tool':'boi_knowledge_catalog',
            'arguments':{'reviewed_definition':stored['revision']}}}
            if stored['asset']['kind']=='definition' else {}),
        **({'source_paging':paging} if paging is not None else {}),
        'definition_revision':stored['revision'],'asset_kind':stored['asset']['kind'],
        'source_display_names':source_names,
        'asset_title':stored.get('title'),'url':url,'sources':sources,
        'source_scopes':scopes,'page_role':'source_navigation_and_reading_scope_not_direct_claim_support',
        'source_field_links':source_field_links(sources,url),
        'evidence_bindings':project_definition_evidence(content,sources,url),
        'scope':'Recorded definition revision and its authorized original fields; not current execution approval.'}


def _read_workbook_sources(intake,principal,stored,request,content,*,source_base_url,offset):
    from ..governed_runtime.source_field_projection import SourceFieldProjectionService
    source=stored['sources'][0]
    authorization=intake._authorization(principal)
    projector=SourceFieldProjectionService(intake.source_intake)
    selected=projector.select_manifest_fields(authorization=authorization,reference=source,
        manifest_ref=content['manifest_ref'],
        span_refs=([r['ref'] for r in stored['asset'].get('evidence',[])] if offset is None else [])
            +list(request.source_field_refs),offset=offset)
    fields=[]
    for metadata in selected['fields']:
        cursor=0;pieces=[]
        while True:
            page=projector.read_field(authorization=authorization,reference=source,
                span_ref=metadata['span_ref'],offset=cursor,limit=8192)
            pieces.append(page['text']);cursor=page['next_offset']
            if cursor is None:break
        fields.append({**metadata,'text':''.join(pieces)})
    origin=(source_base_url or '').rstrip('/');parsed=urlsplit(origin)
    url=(origin if parsed.scheme in ('http','https') and parsed.netloc else '')+'/native-definitions/'+stored['revision']['revision_digest'].removeprefix('sha256:')
    sources=[{'source':source,'manifest':selected,'fields':fields,'file_name':content['file_name']}]
    return {'definition_revision':stored['revision'],'asset_kind':'source','asset_title':content['file_name'],
        'url':url,'sources':sources,'source_field_links':source_field_links(sources,url),'evidence_bindings':[],
        'source_scopes':[{'source_revision_digest':source['digest'],'manifest_ref':selected['manifest_ref'],
            'coverage':'selected_source_fields','absence_proven':False,'total_field_count':selected['field_count'],
            'read_field_count':len(fields)}],
        'source_paging':{'total_fields':selected['field_count'],'read_fields':len(fields),'offset':offset,
            'full_source_url':url+'?source_offset=0',
            'next_url':url+'?source_offset='+str(selected['next_offset']) if selected['next_offset'] is not None else None},
        'page_role':'source_navigation_and_reading_scope_not_direct_claim_support'}



def _selected_meaning(intake, principal, stored, sources, pointer):
    """Resolve one immutable meaning using actual authorized assets and sources.

    The extraction reading can contain reused definitions, but not this newly
    stored candidate. Add the actual read candidate, never a caller-built context.
    No reading receipt, review, or execution is created by source navigation.
    """
    from agent_kit.python.boi_process_answer_v2 import _meaning_evidence, _MeaningReadState
    from ..governed_runtime.task_knowledge import TaskAssetRevision
    from ..governed_runtime.semantic_binding_contract import RevisionRef
    from ..governed_runtime.source_envelope import ArtifactEnvelope
    asset = TaskAssetRevision.model_validate(stored['asset'])
    if asset.kind != 'definition':
        raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
    assets = {}
    if stored.get('definition_reading_ref'):
        authorization, work = intake._work(principal)
        context = work.contexts.validate_reading(authorization=authorization,
            revision=RevisionRef.model_validate(stored['definition_reading_ref']),
            sources=[ArtifactEnvelope.model_validate(s) for s in stored['sources']],require_current=False)
        assets = {a.revision:a for a in context.assets}
    assets[asset.revision] = asset
    # read_sources already resolved the original bytes under this principal.
    indexed = {s['source']['digest']:{'source':s['source'],
        'fields':{f['field_locator']:f for f in s['fields']}} for s in sources}
    state = _MeaningReadState(indexed)
    try:
        graph=[]
        for root in pointer if isinstance(pointer,list) else [pointer]:
            for node in _meaning_evidence(asset,root,indexed,assets=assets,_read_state=state):
                if node not in graph:graph.append(node)
    except (ValueError,KeyError,IndexError,TypeError):
        raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND') from None
    quotes=[];seen=set()
    for node in graph:
        for binding in node['source_bindings']:
            key=(binding['source_revision_digest'],binding['span_ref'],binding['start'],binding['end'])
            if key in seen:continue
            seen.add(key)
            field=indexed[binding['source_revision_digest']]['fields'][binding['field_locator']]
            quotes.append({**binding,'quote':field['text'][binding['start']:binding['end']],
                'target_pointer':node['target_pointer'],'role':node['role']})
    if not quotes:raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
    return {('target_pointers' if isinstance(pointer,list) else 'target_pointer'):pointer,'graph_evidence':graph,'quotations':quotes,
        'authority':asset.authority,'semantic_support_verified':False}


def meaning_selected_fields(view, pointer):
    entries = [entry for entry in view.get('evidence_bindings', [])
               if entry.get('meaning_context', {}).get('pointer') == pointer]
    if not entries or any(entry['status'] not in ('located', 'located_empty') for entry in entries):
        raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
    return list(dict.fromkeys(field_anchor(entry['evidence']['source_revision_digest'],
                                          entry['evidence']['span_ref']) for entry in entries))



def source_field_label(field, *, source=None):
    """Use explicit source metadata; never convert array position to page number."""
    locator = field['field_locator']
    member = (locator.rsplit('/',1)[-1].replace('~1','/').replace('~0','~')
        if isinstance(locator,str) and locator.startswith('/') else '')
    label = member or '원문 항목'
    if source is None:return label
    metadata=field.get('structural_metadata')
    if metadata and metadata.get('sheet') and metadata.get('cell'):
        return ' · '.join(x for x in (source.get('file_name'),metadata['sheet'],metadata['cell']) if x)
    fields = {f['field_locator']:f for f in source['fields']}
    def declared(locators):
        values = {fields[p]['text'] for p in locators if p in fields
            and fields[p].get('field_state','present')=='present' and fields[p]['text'].strip()}
        return next(iter(values)) if len(values)==1 else None
    filename_fields = ('/filename','/file_name','/source_filename','/original_filename')
    filename = declared(filename_fields)
    has_filename = any(p in fields and fields[p].get('field_state','present')=='present'
        and fields[p]['text'].strip() for p in filename_fields)
    if filename is None and not has_filename:
        url = declared(('/source_url',))
        try:parsed = urlsplit(url or '')
        except ValueError:parsed = urlsplit('')
        if parsed.scheme in ('http','https') and parsed.netloc:
            name = unquote(parsed.path.rsplit('/',1)[-1])
            if '.' in name:filename = name
    parent = field.get('record_locator')
    page = declared(tuple(parent+'/'+key for key in ('page','page_number','page_label'))) if parent else None
    return ' · '.join(x for x in (filename, '원문 페이지 '+page if page else None, label) if x)


def selected_source_excerpts(selection, available):
    """Union overlapping original offsets for reading, retaining each binding.

    Field identity and exact bytes are checked before display. Gaps are never
    filled, equal words at another location never share, and this presentation
    does not change any claim's evidence or infer a relation between excerpts.
    """
    groups={}
    for quote in selection['quotations']:
        anchor=field_anchor(quote['source_revision_digest'],quote['span_ref'])
        if anchor not in available:raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
        source,field=available[anchor]
        start,end=quote['start'],quote['end']
        if (field['field_locator']!=quote['field_locator'] or not _source_range_available(field,start,end)
                or field['text'][start:end]!=quote['quote']):
            raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
        group=groups.setdefault(anchor,{'anchor':anchor,'source':source,'field':field,'quotations':[]})
        group['quotations'].append(quote)
    for group in groups.values():
        intervals=[]
        for quote in sorted(group['quotations'],key=lambda q:(q['start'],q['end'])):
            start,end=quote['start'],quote['end']
            if intervals and start<=intervals[-1][1]:intervals[-1][1]=max(intervals[-1][1],end)
            else:intervals.append([start,end])
        group['excerpts']=[{'start':start,'end':end,'quote':group['field']['text'][start:end]} for start,end in intervals]
    return list(groups.values())


def _render_meaning_selection(selection, available):
    esc=lambda value:html.escape(str(value),quote=True)
    labels={'direct':'선택한 해석','process_identity':'공정','subject_identity':'대상',
        'object_identity':'연결 대상','declared_dependency':'명시된 의존 설명','conditions':'조건',
        'exceptions':'예외','applicability':'적용 범위','condition':'조건','exception':'예외',
        'counterevidence':'함께 대조할 근거','declared_relation':'명시된 연결'}
    meaning_parts=[]
    parts=meaning_parts
    for node in selection['graph_evidence']:
        value=node['value']
        text=value.get('statement',value.get('text',value.get('label',value.get('value',value.get('name')))))
        if isinstance(text,(str,int,float)):
            parts.append('<p data-selected-meaning><strong>'+esc(labels.get(node['role'],'연결된 해석'))+'</strong>: '+esc(text)+'</p>')
        if text is None:
            details=[]
            for key,label in (('subject','주체'),('predicate','관계'),('object','대상·내용'),('modality','서술 성격'),
                    ('component','관측 대상'),('quantity','측정량'),('role','역할'),('unit_label','단위'),('procedure','측정 문맥')):
                item=value.get(key)
                if isinstance(item,(str,int,float)):
                    details.append('<dt>'+esc(label)+'</dt><dd>'+esc(item)+'</dd>')
            if details:parts.append('<dl data-selected-meaning>'+''.join(details)+'</dl>')
        for key in ('conditions','exceptions','applicability'):
            values=value.get(key,[])
            for qualifier in values if isinstance(values,list) else [values]:
                text=qualifier.get('statement') if isinstance(qualifier,dict) else qualifier
                if isinstance(text,(str,int,float)):
                    parts.append('<p data-meaning-qualifier>'+esc(labels[key])+': '+esc(text)+'</p>')
    parts=['<section id="evidence-group"><h2>이 인용의 원문 근거</h2>']
    for group in selected_source_excerpts(selection,available):
        anchor=group['anchor'];source=group['source'];field=group['field']
        parts.append('<article data-selected-source="'+esc(anchor)+'"><h3>'+esc(source_field_label(field,source=source))
            +'</h3>')
        for excerpt in group['excerpts']:
            parts.append('<div data-source-excerpt data-start="'+str(excerpt['start'])+'" data-end="'+str(excerpt['end'])+'">'
                +('<p data-empty-source-field>원문에 값이 비어 있는 항목입니다.</p>'
                    if field.get('field_state')=='empty' and excerpt['quote']=='' else source_quote_html(excerpt['quote']))+'</div>')
        parts.append('<details data-source-fragments><summary>주장별 연결 구절과 원문 위치</summary><code>'+esc(field['field_locator'])+'</code>')
        for quote in group['quotations']:
            parts.append('<div data-source-fragment data-start="'+str(quote['start'])+'" data-end="'+str(quote['end'])+'">'
                +source_quote_html(quote['quote'])+'</div>')
        parts.append('</details><a href="#'+esc(anchor)+'">이 구절의 전체 원문 보기</a></article>')
    if meaning_parts:
        parts.append('<details data-selected-meaning-details><summary>연결된 해석과 조건 확인</summary>'
            +''.join(meaning_parts)+'</details>')
    parts.append('</section>')
    return ''.join(parts)


def source_quote_html(text):
    """Readable inert table fragments, with the exact encoding still available.

    This parses presentation syntax only. Unknown tags, attributes or broken
    nesting fall back to escaped original text; no links or scripts execute.
    """
    from html import escape
    from html.parser import HTMLParser
    class TableFragment(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts=[];self.stack=[];self.valid=True;self.cells=0;self.table=False
        def handle_starttag(self,tag,attrs):
            if attrs or tag not in {'table','tbody','thead','tfoot','tr','td','th','sup','sub','strong','em','b','i','nobr','br'}:
                self.valid=False;return
            if tag in ('td','th'):self.cells+=1
            if tag=='table':self.table=True
            self.parts.append('<'+('span' if tag=='nobr' else tag)+'>')
            if tag!='br':self.stack.append(tag)
        def handle_endtag(self,tag):
            if not self.stack or self.stack[-1]!=tag:self.valid=False;return
            self.stack.pop();self.parts.append('</'+('span' if tag=='nobr' else tag)+'>')
        def handle_data(self,data):self.parts.append(escape(data))
        def handle_comment(self,data):self.valid=False
        def handle_decl(self,decl):self.valid=False
    parsed=TableFragment()
    try:parsed.feed(text);parsed.close()
    except Exception:parsed.valid=False
    exact='<blockquote>'+escape(text)+'</blockquote>'
    if not parsed.valid or parsed.stack or not parsed.cells:return exact
    preview=''.join(parsed.parts)
    if not parsed.table:preview='<table>'+preview+'</table>'
    return ('<div data-source-table-preview tabindex="0" role="region" aria-label="원문 표" style="overflow-x:auto">'
        +preview+'</div><details data-source-encoding><summary>원문 표기 확인</summary>'+exact+'</details>')


def render_definition_sources(view,*,selected_fields=(),fragment=False):
    esc=lambda value:html.escape(str(value),quote=True)
    source_only = view.get('asset_kind') == 'source'
    heading = '보존된 원문' if source_only else '정의에 연결된 원문'
    description = '이 자료 개정에 보존된 원문입니다. 해석이나 과학적 검증이 완료됐다는 뜻은 아닙니다.' if source_only else '이 정의 개정에 보존된 자료입니다. 이후 개정이나 실제 장비 동작을 확인한 결과는 아닙니다.'
    cards=[];available={}
    for source in view['sources']:
        name=view.get('source_display_names',{}).get(source['source']['digest'])
        if name is not None:source={**source,'file_name':name}
        for field in source['fields']:
            anchor=field_anchor(source['source']['digest'],field['span_ref'])
            available[anchor]=(source,field)
            cards.append('<section data-original-field id="'+esc(anchor)+'" tabindex="-1"><h2>'+esc(source_field_label(field,source=source))+'</h2>'+source_quote_html(field['text'])+'<details data-source-location><summary>원문 위치</summary><code>'+esc(field['field_locator'])+'</code></details></section>')
    selected=list(dict.fromkeys(selected_fields))
    if len(selected)>64 or any(anchor not in available for anchor in selected):
        raise ValueError('DEFINITION_SOURCE_SELECTION_NOT_FOUND')
    selection=view.get('meaning_selection')
    if selection is not None and selected:raise ValueError('DEFINITION_SOURCE_SELECTION_AMBIGUOUS')
    selected_html=_render_meaning_selection(selection,available) if selection is not None else ''
    if selection is not None and selection.get('read_scope_sources'):
        selected_html+='<section data-selection-read-scope><h3>이 설명에서 확인한 자료 범위</h3>'
        for scope in view['source_scopes']:
            if scope['source_revision_digest'] not in selection['read_scope_sources']:continue
            selected_html+='<p>원문 '+str(len(scope['field_inventory']))+'개 항목'
            if scope.get('coverage')=='selected_source_fields':
                selected_html+=' · 전체 자료 '+str(scope['total_field_count'])+'개 중 선택한 범위'
            selected_html+='</p>'
        selected_html+='<p>읽은 범위에 대한 확인이며, 자료 전체에 정보가 없다는 뜻은 아닙니다.</p></section>'
    if selected:
        selected_html='<section id="evidence-group"><h2>이 인용에 선택된 원문</h2>'
        for anchor in selected:
            source,field=available[anchor]
            selected_html+=('<article data-selected-source="'+esc(anchor)+'"><h3>'+esc(source_field_label(field,source=source))
                +'</h3>'+source_quote_html(field['text'])+'<details data-source-location><summary>원문 위치</summary><code>'+esc(field['field_locator'])+'</code></details></article>')
        selected_html+='</section>'
    original_html=''.join(cards)
    if view.get('answer_reading_scopes'):
        from .native_composition_sources import render_answer_reading_scope
        selected_html+=render_answer_reading_scope(view['answer_source_readings'],
            [item['scope'] for item in view['answer_reading_scopes']],available_sources=view['sources'])
    paging=view.get('source_paging')
    context_label='이 범위의 원문 보기' if paging else '주변 문맥과 전체 원문 보기'
    original_html='<details data-source-context'+('' if selected or selection is not None else ' open')+'><summary>'+context_label+'</summary>'+original_html+'</details>'
    navigation=''
    if paging:
        navigation=('<nav data-source-paging><p>전체 '+esc(paging['total_fields'])+'개 필드 중 현재 '+esc(paging['read_fields'])+'개를 읽었습니다.</p>'
            +'<a href="'+esc(paging['full_source_url'])+'">전체 원문을 범위별로 읽기</a>'
            +(' · <a rel="next" href="'+esc(paging['next_url'])+'">다음 원문 범위</a>' if paging['next_url'] else '')+'</nav>')
    styles=('.native-source-content{font-family:system-ui;line-height:1.7;overflow-wrap:anywhere}'
        '.native-source-content section{margin:24px 0;padding:16px;background:#f4f7fa}'
        '.native-source-content h2{font-size:1rem}.native-source-content blockquote{white-space:pre-wrap;margin:0}'
        '.native-source-content table{border-collapse:collapse;width:100%;min-width:32rem}'
        '.native-source-content td,.native-source-content th{border:1px solid #cbd5e1;padding:8px;vertical-align:top}'
        '.native-source-content section:target{outline:2px solid #075ba5}')
    content=('<article class="native-source-content"><h1>'+esc(heading)+'</h1>'
        +('<p data-source-title>'+('자료: ' if source_only else '지식 항목: ')+esc(view['asset_title'])+'</p>' if view.get('asset_title') else '')
        +'<p>'+esc(description)+'</p>'
        +selected_html+'<div data-single-source></div>'+original_html+navigation+'<details><summary>개정 확인</summary><p>'+esc(view['definition_revision']['ref'])+'</p></details>'+SOURCE_SELECTION_SCRIPT+'</article>')
    if fragment:return '<style>'+styles+'</style>'+content
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>'+esc(heading)+'</title><style>body{max-width:960px;margin:auto;padding:24px}'+styles+'</style><body>'+content+'</body></html>')


# Fragment identifiers are client-side navigation, never authorization or meaning.
# Move the authorized original node so its existing anchor and text stay exact.
SOURCE_SELECTION_SCRIPT = """<script type="module">
const context = document.querySelector('[data-source-context]');
const selected = document.querySelector('[data-single-source]');
let previous = null;
let placeholder = null;
function selectSource() {
  if (previous) { placeholder.replaceWith(previous); previous = null; placeholder = null; }
  context.open = !document.getElementById('evidence-group');
  let id;
  try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
  const target = document.getElementById(id);
  if (!target || !target.matches('[data-original-field]')) return;
  placeholder = document.createComment('original source position');
  target.before(placeholder);
  selected.append(target);
  previous = target;
  context.open = false;
  target.scrollIntoView();
}
addEventListener('hashchange', selectSource);
selectSource();
</script>"""


def source_selection_csp():
    import base64
    import hashlib
    script = SOURCE_SELECTION_SCRIPT.split('>', 1)[1].rsplit('</script>', 1)[0]
    digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    return "default-src 'none'; script-src 'sha256-" + digest + "'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'"
