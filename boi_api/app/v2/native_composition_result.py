"""Protected reads of a completed binding, separate from drafting and review.

Uses the existing atomic native-result store. A retained binding is not a
reviewed final answer, a fresh search, or evidence of fit to a different request.
"""
import copy
import json
from typing import Literal
from pydantic import ValidationError

from ..governed_runtime.semantic_binding_contract import FrozenContract,Digest,RevisionRef,semantic_digest
from ..governed_runtime.source_envelope import ArtifactEnvelope
from .atomic_store_contract import AtomicWrite
from .native_formula_timing import timed_call, stage_timing
from .native_answer_composition import NativeAnswerComposition,compose_native_answer
from agent_kit.python.boi_process_answer_v2 import MeaningCitation,ProcessAnswerDraftV2


class NativeCompositionRead(FrozenContract):
    composition_ref: Digest
    view: Literal['answer','binding']='answer'
    purpose: Literal['recorded','current_reuse']='recorded'


@stage_timing('dependency_reads')
def _dependencies(intake,principal,request,result):
    refs=[*request.source_definition_revisions,*(u.revision for u in request.published_meaning_uses)]
    if request.definition_review_revision is not None:
        refs.extend((request.definition_review_revision,*request.additional_definition_review_revisions))
    for answer in result['bound_answer']['answers']:
        for section in ('sentences','limitations'):
            for statement in answer.get(section,[]):
                for citation in statement['citations']:
                    if citation.get('asset_revision'):refs.append(RevisionRef.model_validate(citation['asset_revision']))
                    for node in citation.get('graph_evidence',[]):
                        if node.get('asset_revision'):refs.append(RevisionRef.model_validate(node['asset_revision']))
        for facet in (answer.get('request_plan') or {}).get('facets',[]):
            for citation in facet.get('citations',[]):
                if citation.get('asset_revision'):refs.append(RevisionRef.model_validate(citation['asset_revision']))
                for node in citation.get('graph_evidence',[]):
                    if node.get('asset_revision'):refs.append(RevisionRef.model_validate(node['asset_revision']))
    authorization,work=intake._work(principal)
    dependencies=[];seen=set();pending=sorted(set(refs),key=lambda r:(r.ref,r.revision_digest))
    while pending:
        revision=pending.pop(0)
        if revision in seen:continue
        seen.add(revision)
        stored=work.assets.read(authorization=authorization,revision=revision,lane='provisional')
        # Even source-quote-only answers were prepared under the reviewed
        # definition scope. Preserve those dependencies independently of the
        # final citation spelling, without replaying its review.
        from .asset_user_views import available_user_views
        for view in available_user_views(stored):
            if view.get('tool')=='boi_native_answer':
                pending.extend(RevisionRef.model_validate(r) for r in view.get('definition_revisions',[]))
        dependencies.append({'revision':stored['revision'],'namespace':stored['namespace'],
            'logical_id':stored['logical_id'],'content_digest':stored['asset']['content_digest'],
            'sources':stored['sources'],'reading_ref':stored['definition_reading_ref']})
    return dependencies


class NativePreparedComposition(FrozenContract):
    """Continue a protected preparation with its returned selection/draft schema.

    The draft's request-local citation aliases are checked against that exact
    preparation before the full answer, source, review and ACL checks run.
    """
    preparation_ref: Digest
    question: str | None = None
    meaning_selection: tuple[MeaningCitation, ...] | None = None
    execution_ref: Digest | None = None
    draft: dict | None = None


class NativeAuthoringComposition(NativeAnswerComposition):
    """Transport form; short references are validated against a protected preparation."""
    draft: dict


def _preparation_lookup_key(authorization, principal, request, context_digest):
    # Exact authored request and source context, never a question/answer cache.
    return 'preparation-lookup:'+semantic_digest({
        'principal':authorization.principal,'policy_digest':authorization.policy_digest,
        'principal_teams':list(principal.teams),
        'request':request.model_dump(mode='json',exclude={'draft'}),
        'context_digest':context_digest})


def _recover_authoring_preparation(intake, principal, raw):
    incoming=NativeAuthoringComposition.model_validate(raw)
    authorization,work=intake._work(principal)
    context=incoming.draft.get('context_digest')
    key=_preparation_lookup_key(authorization,principal,incoming,context)
    row=work.store.get('native_composition_results',key)
    if not row or not row.get('preparation_ref'):
        raise ValueError('NATIVE_AUTHORING_PREPARATION_NOT_FOUND')
    continuation={'preparation_ref':row['preparation_ref'],'draft':incoming.draft}
    restored,record=_resume_preparation(intake,principal,continuation)
    if (record.get('context_digest')!=context or record['request']!=incoming.model_dump(mode='json',exclude={'draft'})):
        raise ValueError('NATIVE_AUTHORING_PREPARATION_REQUEST_MISMATCH')
    return restored,record,row['preparation_ref']


def _store_preparation(intake, principal, request, result, *, parent=None, prior=None):
    """Retain the selected request in the existing immutable result store.

    This record grants no authority and is not an answer. Actual composition
    still rechecks current review, revision, source and execution authority.
    """
    authorization, work = intake._work(principal)
    result=copy.deepcopy(result)
    review_binding=result.pop('_prepared_review_binding',None)
    review_bindings=result.pop('_prepared_review_bindings',None)
    record = {'contract_version':'boi/native-composition-preparation@1',
        'principal':authorization.principal,'policy_digest':authorization.policy_digest,
        'principal_teams':list(principal.teams),'request':request.model_dump(mode='json',exclude={'draft'}),
        'phase':result['status'],'parent_preparation_ref':parent}
    if review_binding is not None:
        record['review_binding']=review_binding
        record['review_binding_reuse_version']='native-review-reuse@1'
    if review_bindings is not None:
        record['review_bindings']=review_bindings
        record['review_binding_reuse_version']='native-review-reuse@1'
    if result['status']=='composition_ready':
        from agent_kit.python.boi_process_answer_stage import restore_source_model_material
        restored=restore_source_model_material(result)
        record['context_digest']=result['context_digest']
        record['source_reading_digests']=[semantic_digest(s) for s in restored['sources']]
    else:
        record['candidate_index_digests']=[semantic_digest(i) for i in result['meaning_indexes']]
    if result['status']=='composition_ready':
        from .native_composition_authoring import authoring_material
        result,record['authoring_references']=authoring_material(result)
    unchanged=prior is not None and {k:v for k,v in prior.items() if k!='parent_preparation_ref'}=={k:v for k,v in record.items() if k!='parent_preparation_ref'}
    digest=parent if unchanged else semantic_digest(record)
    if not unchanged and not work.store.atomic_compare_and_write((AtomicWrite('native_composition_results',digest,None,{'record':record}),)):
        old=work.store.get('native_composition_results',digest)
        if old is None or old.get('record')!=record:raise ValueError('NATIVE_PREPARATION_CONFLICT')
    if result['status']=='composition_ready':
        key=_preparation_lookup_key(authorization,principal,request,record['context_digest'])
        # First equivalent preparation is sufficient. Its immutable record,
        # exact request and current authority are still checked on every use.
        work.store.atomic_compare_and_write((AtomicWrite('native_composition_results',key,None,{'preparation_ref':digest}),))
    return {**result,'preparation_ref':digest,
        'continuation':{'tool':'boi_native_answer','arguments':{'composition':{'preparation_ref':digest}},
            'supply':'meaning_selection from candidate meanings' if result['status']=='meaning_selection_ready' else 'draft using this context and source scope',
            'scope':'The server retains question, review refs, selected meanings and execution ref; do not reconstruct them.'}}


@stage_timing('resume_preparation')
def _resume_preparation(intake, principal, request):
    incoming=NativePreparedComposition.model_validate(request)
    authorization,work=intake._work(principal)
    row=work.store.get('native_composition_results',incoming.preparation_ref)
    record=row.get('record') if row else None
    if (record is None or record.get('contract_version')!='boi/native-composition-preparation@1'
            or record.get('principal')!=authorization.principal or record.get('policy_digest')!=authorization.policy_digest
            or record.get('principal_teams')!=list(principal.teams)):
        raise ValueError('NATIVE_PREPARATION_NOT_ACCESSIBLE')
    if semantic_digest(record)!=incoming.preparation_ref:raise ValueError('NATIVE_PREPARATION_DIGEST_MISMATCH')
    restored=copy.deepcopy(record['request'])
    if incoming.question is not None and incoming.question!=restored['question']:
        raise ValueError('NATIVE_PREPARATION_CURRENT_REQUEST_CHANGED')
    if incoming.meaning_selection is not None:
        restored['meaning_selection']=[v.model_dump(mode='json') for v in incoming.meaning_selection]
    if 'execution_ref' in incoming.model_fields_set:
        previous=restored.get('execution_ref')
        if previous is not None and incoming.execution_ref!=previous:
            raise ValueError('NATIVE_PREPARATION_EXECUTION_CHANGED')
        # Attach a result obtained after preparation to a new immutable child.
        # Composition below reads the actual protected execution and validates
        # current authority, definitions and freshness; this is not execution.
        if incoming.execution_ref is not None:restored['execution_ref']=incoming.execution_ref
    if incoming.draft is not None:
        from .native_composition_authoring import expand_authoring_draft
        restored['draft']=expand_authoring_draft(incoming.draft,record.get('authoring_references',{}))
    try:return NativeAnswerComposition.model_validate(restored),record
    except ValidationError as exc:
        # The retained request already validated; tell the host which draft
        # position broke which coded rule, never its text or the validator prose.
        from .native_answer_refusal import draft_binding_refusal
        refusal=(draft_binding_refusal(exc,restored['draft'],NativeAnswerComposition.model_json_schema())
            if incoming.draft is not None else None)
        if refusal is None:raise
        raise refusal from None


def _meaning_selection_candidates(intake, principal, request):
    """A missing selection is a useful candidate read, not an input error.

    No original projection or authoring schema is sent until the host has chosen
    meaning references. General source exploration remains available separately.
    """
    from .asset_user_views import native_review_record_view
    authorization,work=intake._work(principal)
    indexes=[];seen=set();reviews=[]
    for ref in (request.definition_review_revision,*request.additional_definition_review_revisions):
        stored=work.assets.read(authorization=authorization,revision=ref,lane='provisional')
        record=native_review_record_view(intake,principal,stored,include_meanings=True)
        if record is None:raise ValueError('ANSWER_REVIEW_RECORD_REQUIRED')
        value=record['review']
        reviews.append({'review_revision':ref.model_dump(mode='json'),'findings':value.get('findings',[]),
            'limitations':value.get('limitations',value.get('source_assessment',{}).get('limitations',[])),
            'candidate_scope_only':True})
        for index in record['meaning_indexes']:
            revision=index['definition_revision']['ref']
            if revision not in seen:indexes.append(index);seen.add(revision)
    return {'status':'meaning_selection_ready','question':request.question,'meaning_indexes':indexes,
        'meaning_reviews':reviews,'source_definition_revisions':[r.model_dump(mode='json') for r in request.source_definition_revisions],
        'next_action':'Choose existing meanings that answer the request, with relevant conditions, exceptions, scope and conflicting candidates. Continue with meaning_selection. If evidence is insufficient, use the exact detail_read or catalog to expand it. Do not ask the user for pointers.',
        'selection_item_schema':MeaningCitation.model_json_schema(),
        'source_text_provided':False,'selection_complete':False,'absence_proven':False,
        'semantic_support_verified':False,'user_request_fulfilled':False}


def compose_native_response(intake,principal,request,*,source_base_url=None):
    raw=request.model_dump(mode='json',exclude_unset=True) if hasattr(request,'model_dump') else request
    prior=None;parent=raw.get('preparation_ref')
    if parent:request,prior=_resume_preparation(intake,principal,raw)
    else:
        try:request=NativeAnswerComposition.model_validate(raw)
        except ValidationError:
            request,prior,parent=_recover_authoring_preparation(intake,principal,raw)
    if (request.draft is None or prior is not None and prior['phase']=='meaning_selection_ready') and request.definition_review_revision is not None and not request.meaning_selection:
        return _store_preparation(intake,principal,request,_meaning_selection_candidates(intake,principal,request),parent=parent,prior=prior)
    reuse=(prior.get('review_binding') if prior and prior.get('review_binding_reuse_version')=='native-review-reuse@1' else None)
    multi_reuse=(prior.get('review_bindings') if prior and prior.get('review_binding_reuse_version')=='native-review-reuse@1' else None)
    result=compose_native_answer(intake,principal,request,source_base_url=source_base_url,
        **({'prepared_review_binding':reuse} if reuse is not None else {}),
        **({'prepared_review_bindings':multi_reuse} if multi_reuse is not None else {}))
    if result.get('status')=='composition_ready':return _store_preparation(intake,principal,request,result,parent=parent,prior=prior)
    if result.get('status')!='bound':return result
    if prior is not None and prior['phase']=='composition_ready':
        if (result['bound_answer']['context_digest']!=prior['context_digest']
                or result['bound_answer']['source_reading_digests']!=prior['source_reading_digests']):
            raise ValueError('NATIVE_PREPARATION_READING_SCOPE_CHANGED')
    authorization,work=intake._work(principal)
    descriptors=result.pop('_source_reading_descriptors',None)
    record={'contract_version':'boi/native-composition-record@1','principal':authorization.principal,
        'policy_digest':authorization.policy_digest,'principal_teams':list(principal.teams),
        'request':request.model_dump(mode='json'),'result':result,
        'dependencies':_dependencies(intake,principal,request,result),
        **({'source_reading_descriptors':descriptors} if descriptors is not None else {}),
        **({'preparation_ref':parent} if parent else {})}
    record=timed_call('result_serialization',lambda: json.loads(json.dumps(record,ensure_ascii=False)))
    digest=timed_call('result_serialization',semantic_digest,record)
    old=timed_call('result_storage',work.store.get,'native_composition_results',digest)
    if old is None:
        if not timed_call('result_storage',work.store.atomic_compare_and_write,(AtomicWrite('native_composition_results',digest,None,{'record':record}),)):
            old=timed_call('result_storage',work.store.get,'native_composition_results',digest)
    if old is not None and old.get('record')!=record:raise ValueError('NATIVE_COMPOSITION_RESULT_CONFLICT')
    return composition_message(result,digest)


def composition_citation_url(digest, answer_index, citation_index):
    """Short transport address for the exact citation in an immutable result."""
    import base64
    from urllib.parse import urlsplit
    validated=NativeCompositionRead(composition_ref=digest).composition_ref
    token=base64.urlsafe_b64encode(bytes.fromhex(validated.removeprefix('sha256:'))).decode().rstrip('=')
    origin=urlsplit(composition_result_url(digest))
    base=(origin.scheme+'://'+origin.netloc) if origin.netloc else ''
    return f'{base}/c/{token}/{answer_index}/{citation_index}'


def composition_citation_digest(token):
    import base64
    try:
        raw=base64.urlsafe_b64decode(token+'=')
        if len(raw)!=32 or base64.urlsafe_b64encode(raw).decode().rstrip('=')!=token:
            raise ValueError()
    except (ValueError,TypeError):
        raise ValueError('NATIVE_COMPOSITION_CITATION_NOT_FOUND') from None
    return 'sha256:'+raw.hex()


def project_composition_citations(answer, digest, answer_index):
    """Only change parsed link destinations; retain authored text and all roles."""
    from agent_kit.python.boi_markdown_links import rewrite_inline_link_destinations,rendered_links
    answer=copy.deepcopy(answer)
    from urllib.parse import urlsplit,parse_qs
    replacements={}
    for index,citation in enumerate(answer['citations']):
        parsed=urlsplit(citation['url'])
        if not parsed.path.startswith('/native-definitions/') or set(parse_qs(parsed.query))-{'meaning','group','source_offset'}:
            continue
        replacements.setdefault(citation['url'],composition_citation_url(digest,answer_index,index))
    text=rewrite_inline_link_destinations(answer['readable_text'],replacements)
    actual=set(rendered_links(text))
    applied={old:new for old,new in replacements.items() if new in actual}
    answer['readable_text']=text
    for citation in answer['citations']:
        if citation['url'] in applied:
            citation['canonical_url']=citation['url']
            citation['url']=applied[citation['url']]
    if 'source_selections' in answer:
        answer['source_selections']={applied.get(url,url):value for url,value in answer['source_selections'].items()}
    return answer


def read_composition_citation(intake, principal, token, answer_index, citation_index):
    """Knowing a short URL confers no permission; use the same current read gate."""
    digest=composition_citation_digest(token)
    value=read_native_composition(intake,principal,{'composition_ref':digest,'view':'binding'})
    if answer_index<0 or citation_index<0:
        raise ValueError('NATIVE_COMPOSITION_CITATION_NOT_FOUND')
    try:citation=value['answers'][answer_index]['citations'][citation_index]
    except IndexError:raise ValueError('NATIVE_COMPOSITION_CITATION_NOT_FOUND') from None
    return citation.get('canonical_url',citation['url'])


def read_composition_citation_view(intake,principal,token,answer_index,citation_index,*,source_base_url=None,legacy_redirect=False):
    """One protected result read; retained scope belongs to this answer only."""
    from urllib.parse import urlsplit,parse_qs
    from .domain_intake import DomainAssetReadRequest
    from .native_definition_sources import read_definition_sources
    value=read_native_composition(intake,principal,{'composition_ref':composition_citation_digest(token),'view':'binding'})
    if answer_index<0 or citation_index<0:raise ValueError('NATIVE_COMPOSITION_CITATION_NOT_FOUND')
    try:citation=value['answers'][answer_index]['citations'][citation_index]
    except IndexError:raise ValueError('NATIVE_COMPOSITION_CITATION_NOT_FOUND') from None
    target=citation.get('canonical_url',citation['url'])
    if legacy_redirect and 'source_reading_descriptors' not in value:
        return {'source_url':target,'view':{},'answer_url':value['result_url']}
    source=urlsplit(target);query=parse_qs(source.query,keep_blank_values=True)
    if not source.path.startswith('/native-definitions/') or set(query)-{'meaning','group','source_offset'} or any(len(v)!=1 for v in query.values()):
        raise ValueError('NATIVE_COMPOSITION_CITATION_SOURCE_UNSUPPORTED')
    digest='sha256:'+source.path.removeprefix('/native-definitions/')
    view=read_definition_sources(intake,principal,DomainAssetReadRequest(
        revision=RevisionRef(ref='KnowledgeRevision:'+digest,revision_digest=digest),lane='provisional'),
        meaning_pointer=query.get('meaning',[None])[0],meaning_group=query.get('group',[None])[0],
        source_offset=int(query['source_offset'][0]) if 'source_offset' in query else None,source_base_url=source_base_url)
    descriptors=value.get('source_reading_descriptors')
    if descriptors is not None:
        from .native_composition_sources import restore_reading_descriptors,recorded_scope_catalog
        sources=restore_reading_descriptors(intake,principal,descriptors,value['bound_answer'],available_sources=view['sources'])
        view['answer_source_readings']=sources
        view['answer_reading_scopes']=recorded_scope_catalog(sources,value)
    return {'source_url':target,'view':view,'answer_url':value['result_url']}


def read_composition_citation_material(intake,principal,page_ref,*,source_base_url=None):
    """Resolve a same-Wiki short citation through existing protected source reads."""
    from urllib.parse import urlsplit,parse_qs
    route=urlsplit(page_ref);origin=urlsplit(source_base_url or '')
    if ((route.scheme or route.netloc) and (route.scheme,route.netloc)!=(origin.scheme,origin.netloc)
            or route.username or route.password or route.query or not route.path.startswith('/c/')):
        return None
    parts=route.path.split('/')
    if len(parts)!=5 or not all(p.isdecimal() for p in parts[3:]):return None
    resolved=read_composition_citation_view(intake,principal,parts[2],int(parts[3]),int(parts[4]),source_base_url=source_base_url)
    from .native_definition_sources import selected_source_model_view
    from agent_kit.python.boi_process_answer_stage import composition_model_material
    value=resolved['view']
    # Full answer-wide originals belong to the protected browser details, not
    # a second copy in the model's selected quotation read.
    selected_value={k:v for k,v in value.items() if k not in ('answer_source_readings','answer_reading_scopes')}
    return {'source_url':resolved['source_url'],'citation_url':page_ref,
        'reading':composition_model_material(selected_source_model_view(selected_value)),
        **({'answer_reading_scopes':value['answer_reading_scopes']} if 'answer_reading_scopes' in value else {}),
        'answer_url':resolved['answer_url'],
        'new_execution':False,'semantic_support_verified':False}


def composition_message(result,digest):
    # Keep authored prose, every limitation and exact links. Large proof graphs
    # and node-review records stay in this same immutable protected result.
    message={k:copy.deepcopy(v) for k,v in result.items() if k not in (
        'bound_answer','meaning_review_binding','meaning_review_bindings','answers','_source_reading_descriptors')}
    message['answers']=[]
    for index,original in enumerate(result['answers']):
        answer=project_composition_citations(original,digest,index)
        displayed={k:copy.deepcopy(v) for k,v in answer.items() if k not in ('source_selections','citations')}
        displayed['citations']=[{k:copy.deepcopy(c[k]) for k in (
            'url','statement_pointer','evidence_role','scope_source_digests','execution_result_digest') if k in c}
            for c in answer['citations']]
        from agent_kit.python.boi_recipient_citations import recipient_access
        displayed['recipient_citation_access']=recipient_access([c['url'] for c in answer['citations']])
        message['answers'].append(displayed)
    message.update(composition_ref=digest,bound_answer_digest=semantic_digest(result['bound_answer']),
        result_url=composition_result_url(digest),
        read_scope={'purpose':'recorded','current_request_applicability_verified':False,
            'current_data_freshness_verified':False,'changed_dependencies':[],
            'scope':'Recorded answer and evidence; current permission and immutable content checked. Current meaning applicability is not established by historical access.'},
        binding_read={'tool':'boi_native_answer','arguments':{'composition_ref':digest,'view':'binding'}},
        reuse_scope='This exact recorded request and binding; not a fresh search, final review, or applicability to a different request.')
    if message['answers']:
        index=len(message['answers'])-1
        answer=message['answers'][index]
        navigation=answer_navigation(message['result_url'],answer['readable_text'],index)
        answer['readable_text']+=navigation['suffix']
        message['delivery_navigation']=navigation
    return message


def answer_navigation(url,body,index):
    """Presentation-only footer; it never enters the authored claim binding."""
    from agent_kit.python.boi_recipient_citations import recipient_access, access_notice
    from agent_kit.python.boi_markdown_links import rendered_links
    access=recipient_access([*rendered_links(body),url])
    return {'answer_index':index,'body_length':len(body),
        'recipient_citation_access':access,
        'suffix':'\n\n[전체 답변과 근거]('+url+')'+access_notice(access)}


def composition_result_url(digest):
    import os
    from urllib.parse import urlsplit
    origin=os.environ.get('BOI_EXTERNAL_URL','').rstrip('/')
    parsed=urlsplit(origin)
    return (origin if parsed.scheme in ('http','https') and parsed.netloc else '')+'/native-compositions/'+digest.removeprefix('sha256:')


def render_composition_result(message, *, fragment=False):
    """Use the existing answer Markdown sanitizer and exact source allowlist."""
    import html
    from markdown_it import MarkdownIt
    from .native_answer_delivery import _SafeHTML,responsive_answer_tables
    from agent_kit.python.boi_process_answer_layout import RESPONSIVE_TABLE_CSS
    changed=bool(message.get('read_scope',{}).get('changed_dependencies'))
    revision_notice=('<p class="status" data-recorded-revision>답변 작성 이후 관련 정의가 개정됐습니다. 이 화면은 당시 답변과 근거이며, 현재 적용하려면 변경 내용을 확인해야 합니다.</p>' if changed else '')
    from urllib.parse import urlsplit
    origin=urlsplit(message.get('result_url',''))
    def protected_target(url):
        if not isinstance(url,str) or any(c.isspace() or ord(c)<=32 or ord(c)==127 for c in url) or '\\' in url:return False
        try:parsed=urlsplit(url)
        except ValueError:return False
        if parsed.username or parsed.password:return False
        if parsed.scheme or parsed.netloc:
            if parsed.scheme not in ('http','https') or (parsed.scheme,parsed.netloc)!=(origin.scheme,origin.netloc):return False
        if not parsed.path.startswith(('/c/','/native-definitions/','/native-formulas/','/knowledge/records/','/native-results/','/domain-results/')):return False
        return True
    allowed=[{c['url']:c['url'] for c in answer['citations'] if protected_target(c['url'])} for answer in message['answers']]
    body=[]
    for index,answer in enumerate(message['answers']):
        links=allowed[index]
        sanitizer=_SafeHTML(links)
        text=answer['readable_text'];navigation=message.get('delivery_navigation')
        if navigation and navigation['answer_index']==index:
            answer_body=text[:navigation['body_length']]
            if navigation!=answer_navigation(message['result_url'],answer_body,index) or text!=answer_body+navigation['suffix']:
                raise ValueError('NATIVE_COMPOSITION_NAVIGATION_MISMATCH')
            text=answer_body
        sanitizer.feed(MarkdownIt('commonmark',{'html':False}).enable('table').render(text))
        body.append('<section id="answer-'+str(index)+'">'+responsive_answer_tables(''.join(sanitizer.parts))+'</section>')
    from ..governed_runtime.citation_material_cards import material_identity
    groups={}
    for ai,answer in enumerate(message['answers']):
        for card in answer.get('source_cards',[]):
            identity=material_identity(card['source'])
            if identity is None:continue
            group=groups.setdefault(identity,{'number':card['number'],'title':card.get('title'),'targets':{},'locations':[]})
            for ref in card['references']:
                location=ref.get('binding',{}).get('field_locator') or '확인 범위'
                if location not in group['locations']:group['locations'].append(location)
                # Historical coarse statement associations are not exact target mappings.
                if card.get('target_mapping')!='typed_evidence@1':continue
                for ci in ref['statement_citation_indices']:
                    if not 0 <= ci < len(answer['citations']):raise ValueError('COMPOSITION_CARD_TARGET_UNAVAILABLE')
                    target=answer['citations'][ci]['url']
                    if target not in allowed[ai]:continue
                    item=group['targets'].setdefault(target,{'locations':[],'answers':[]})
                    if location not in item['locations']:item['locations'].append(location)
                    if ai not in item['answers']:item['answers'].append(ai)
    source_cards=[]
    for group in groups.values():
        links=[]
        for url,target in group['targets'].items():
            links.append('<li><a data-material-reference href="'+html.escape(url,quote=True)+'">'+html.escape(' · '.join(target['locations']))+'</a>'+''.join(
                ' <a data-answer-return href="#answer-'+str(ai)+'">답변으로 돌아가기</a>' for ai in target['answers'])+'</li>')
        source_cards.append('<article data-source-card><h3>['+str(group['number'])+'] '+html.escape(group['title'] or '원자료')+'</h3>'+('<ul>'+''.join(links)+'</ul>' if links else '<p>'+html.escape(' · '.join(group['locations']))+'</p>')+'</article>')
    source_section=('<section data-composition-sources><h2>답변의 출처</h2>'+''.join(source_cards)+'</section>') if source_cards else ''
    styles=('.native-composition-content *{box-sizing:border-box}.native-composition-content{font-family:system-ui;line-height:1.7;overflow-wrap:anywhere}'
        '.native-composition-content pre{white-space:pre-wrap}.native-composition-content table{width:100%;table-layout:fixed;border-collapse:collapse}'
        '.native-composition-content td,.native-composition-content th{padding:8px;border-bottom:1px solid #ccd4dc;text-align:left}'
        '.native-composition-content a{color:#075ba5}.native-composition-content details{margin-top:24px}.native-composition-content .status{color:#536473;font-size:.9rem}'
        +RESPONSIVE_TABLE_CSS)
    content=('<article class="native-composition-content"><h1>답변과 근거</h1><p class="status" data-composition-status>근거를 연결한 초안 · 최종 답변 검토 전</p>'
        +revision_notice+'<main data-native-answer-body>'+''.join(body)+'</main>'+source_section
        +'<details><summary>연결된 기록</summary><p>저장된 요청과 근거 결합 결과입니다. 새 검색이나 현재 장비 관측 결과를 뜻하지 않습니다.</p><code>'
        +html.escape(message['composition_ref'])+'''</code></details>
<script data-answer-position>
// The history entry belongs to this immutable answer, not the source page.
history.scrollRestoration = 'manual';
addEventListener('pagehide', () => {
  const state = history.state && typeof history.state === 'object' ? history.state : {};
  history.replaceState({...state, boiAnswerPosition: {url: location.href, x: scrollX, y: scrollY}}, '');
});
addEventListener('pageshow', (event) => {
  const position = history.state?.boiAnswerPosition;
  const returning = event.persisted || performance.getEntriesByType('navigation')[0]?.type === 'back_forward';
  if (position?.url === location.href && returning) {
    requestAnimationFrame(() => scrollTo(position.x, position.y));
  }
});
</script></article>''')
    if fragment:return '<style>'+styles+'</style>'+content
    return ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>답변과 근거</title><style>body{max-width:960px;margin:auto;padding:24px}'+styles+'</style><body>'+content+'</body></html>')


def read_native_composition(intake,principal,request):
    request=NativeCompositionRead.model_validate(request)
    authorization,work=intake._work(principal)
    row=work.store.get('native_composition_results',request.composition_ref)
    record=row.get('record') if row else None
    if (record is None or record.get('principal')!=authorization.principal
            or record.get('policy_digest')!=authorization.policy_digest
            or record.get('principal_teams')!=list(principal.teams)):
        raise ValueError('NATIVE_COMPOSITION_RESULT_NOT_ACCESSIBLE')
    if semantic_digest(record)!=request.composition_ref:raise ValueError('NATIVE_COMPOSITION_RESULT_DIGEST_MISMATCH')
    if record.get('contract_version')!='boi/native-composition-record@1':raise ValueError('NATIVE_COMPOSITION_RESULT_CONTRACT_MISMATCH')
    original=NativeAnswerComposition.model_validate(record['request'])
    meaning_reader=None
    if original.published_meaning_uses:
        from .published_answer_meaning import PublishedAnswerMeaning
        meaning_reader=PublishedAnswerMeaning(work.knowledge_spaces,principal.employee_id,
            current_authorization=work.current_knowledge_authorization)
        for use in original.published_meaning_uses:
            meaning_reader.read(use,[c.target_pointer for c in original.meaning_selection if c.asset_revision==use.revision]
                if original.meaning_selection is not None else None)
    readings=set();changes=[];metadata_reuses=[];checked=set();loaded={};pending=copy.deepcopy(record['dependencies'])
    from .asset_user_views import available_user_views
    reviewed_definitions=set()
    for ref in (original.definition_review_revision,*original.additional_definition_review_revisions):
        if ref is None:continue
        reviewed=work.assets.read(authorization=authorization,revision=ref,lane='provisional')
        loaded[ref.ref]=reviewed
        for view in available_user_views(reviewed):
            if view.get('tool')=='boi_native_answer':
                reviewed_definitions.update(r['ref'] for r in view.get('definition_revisions',[]))
    while pending:
        dependency=pending.pop(0)
        if dependency['revision']['ref'] in checked:continue
        checked.add(dependency['revision']['ref'])
        revision=RevisionRef.model_validate(dependency['revision'])
        stored=loaded.pop(revision.ref,None)
        if stored is None:
            stored=work.assets.read(authorization=authorization,revision=revision,lane='provisional')
        # Older records could omit the definition when every final citation was
        # a literal source quote. Read its already-declared review references,
        # never infer a new meaning or mutate the historical record.
        from .asset_user_views import available_user_views
        known=checked | {d['revision']['ref'] for d in pending}
        for view in available_user_views(stored):
            if view.get('tool')!='boi_native_answer':continue
            for ref in view.get('definition_revisions',[]):
                if ref['ref'] in known:continue
                known.add(ref['ref'])
                original_definition=work.assets.read(authorization=authorization,
                    revision=RevisionRef.model_validate(ref),lane='provisional')
                loaded[ref['ref']]=original_definition
                pending.append({'revision':ref,'namespace':original_definition['namespace'],
                    'logical_id':original_definition['logical_id'],
                    'content_digest':original_definition['asset']['content_digest'],
                    'sources':original_definition['sources'],'reading_ref':original_definition['definition_reading_ref']})
        if (stored['asset']['content_digest']!=dependency['content_digest'] or stored['sources']!=dependency['sources']
                or stored['definition_reading_ref']!=dependency['reading_ref']):
            raise ValueError('NATIVE_COMPOSITION_DEPENDENCY_CHANGED')
        key='domain-asset-head:'+semantic_digest([authorization.principal,dependency['namespace'],dependency['logical_id']])
        head=work.store.get('domain_asset_heads',key)
        if not head or head['revision']!=dependency['revision']:
            delta={'recorded_revision':dependency['revision'],
                   'current_revision':head['revision'] if head else None}
            if request.purpose=='current_reuse':
                from ..governed_runtime.metadata_revision import same_metadata_lineage
                from ..governed_runtime.ledger import LedgerError
                try:
                    metadata_only=(head and stored['asset']['kind']=='definition' and same_metadata_lineage(
                        work.assets,authorization,revision,RevisionRef.model_validate(head['revision'])))
                except LedgerError:
                    # An invalid current record cannot admit reuse of history.
                    raise ValueError('NATIVE_COMPOSITION_DEPENDENCY_REVISED') from None
                if not metadata_only:
                    raise ValueError('NATIVE_COMPOSITION_DEPENDENCY_REVISED')
                metadata_reuses.append({**delta,'basis':'exact_retained_meaning_and_evidence','review_transferred':False})
            else:changes.append(delta)
        reading=dependency['reading_ref']
        if reading is not None and reading['ref'] not in readings:
            # The extraction reading predates creation of this definition. Its
            # historical provenance is retained; the actually bound review's
            # reading below supplies the current meaning/dependency fence.
            historical_extraction=revision.ref in reviewed_definitions and stored['asset']['kind']=='definition'
            work.contexts.validate_reading(authorization=authorization,revision=RevisionRef.model_validate(reading),
                sources=[ArtifactEnvelope.model_validate(s) for s in dependency['sources']],
                require_current=request.purpose=='current_reuse' and not historical_extraction,
                _exact_metadata_successors=request.purpose=='current_reuse')
            if not historical_extraction:readings.add(reading['ref'])
    if original.execution_ref is not None:
        from .native_formula import read_current_formula_execution,read_recorded_formula_execution
        reader=(read_current_formula_execution if request.purpose=='current_reuse'
            else read_recorded_formula_execution)
        reader(work,authorization,original.execution_ref)
    if meaning_reader is not None:meaning_reader.revalidate()
    read_scope={'purpose':request.purpose,'current_request_applicability_verified':False,
        'current_data_freshness_verified':False,'changed_dependencies':changes,
        **({'metadata_only_reuses':metadata_reuses} if metadata_reuses else {}),
        'scope':'Recorded answer and evidence; current permission and immutable content checked. Current meaning applicability is not established by historical access.'}
    if request.view=='binding':
        return {**copy.deepcopy(record['result']),
            'answers':[project_composition_citations(a,request.composition_ref,i) for i,a in enumerate(record['result']['answers'])],
            'composition_ref':request.composition_ref,
            'result_url':composition_result_url(request.composition_ref),
            'composition_request':copy.deepcopy(record['request']),'read_scope':read_scope,
            **({'source_reading_descriptors':copy.deepcopy(record['source_reading_descriptors'])} if 'source_reading_descriptors' in record else {}),
            **({'preparation_ref':record['preparation_ref']} if record.get('preparation_ref') else {})}
    message=composition_message(record['result'],request.composition_ref)
    # Do not alter the recorded authored answer or its claim/digest bindings.
    # A changed definition affects present reuse, not access to past evidence.
    message['read_scope']=read_scope
    return message
