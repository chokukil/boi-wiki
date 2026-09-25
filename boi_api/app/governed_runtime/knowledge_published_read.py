"""One authorized published document or exact source binding, without corpus scans.

The human reader uses read/cite; the external-agent API always uses model_input.
Knowledge visibility never grants access to a separately protected raw source.
"""
import json
from urllib.parse import urlencode

from pydantic import Field

from ..public_links import PublicWikiLinks
from .knowledge_content import decode_knowledge_content, meaning_pointer
from .knowledge_published_sources import PublishedSourceFields
from .knowledge_space_store import HEADS
from .knowledge_use_reader import KnowledgeUseReader
from .semantic_binding_contract import FrozenContract, RevisionRef, semantic_digest
from .typed_knowledge_meaning import TypedKnowledgeMeaning


class PublishedDocumentRead(FrozenContract):
    revision: RevisionRef
    # Bound against this document's actual assertions + parameter definitions.
    # A fixed assertion-only ceiling can make a returned next page unreadable.
    claim_offset: int = Field(default=0,ge=0,strict=True)
    claim_limit: int = Field(default=20,ge=1,le=50,strict=True)
    meaning_pointer: str | None = Field(default=None,min_length=1,max_length=2048)
    meaning_pointers: tuple[str, ...] | None = Field(default=None,min_length=1,max_length=50)
    include_sources: bool = Field(default=False,strict=True)
    include_source_labels: bool = Field(default=False,strict=True)


class PublishedSourceRead(FrozenContract):
    revision: RevisionRef
    binding_index: int = Field(ge=0,le=999,strict=True)
    offset: int | None = Field(default=None,ge=0,strict=True)
    limit: int = Field(default=4096,ge=1,le=8192,strict=True)


def document_url(revision):
    return '/knowledge/records/'+revision.revision_digest.removeprefix('sha256:')


class PublishedKnowledgeReader:
    def __init__(self,spaces,*,current_authorization=None,public_links=None):
        self.spaces,self.intake=spaces,spaces.intake
        self.current_authorization=current_authorization
        self.public_links=public_links if public_links is not None else PublicWikiLinks.from_config(None)

    def stable_id(self,revision):
        index=self.spaces.store.get('domain_knowledge_assets',revision.ref)
        if index is None:raise ValueError('KNOWLEDGE_DOCUMENT_NOT_AVAILABLE')
        return 'domain-asset-head:'+semantic_digest([index['employee_id'],index['namespace'],index['logical_id']])

    def is_published(self,revision):
        index=self.spaces.store.get('domain_knowledge_assets',revision.ref)
        return bool(index and self.spaces.store.get(HEADS,self.stable_id(revision)))

    def _read(self,actor_id,revision,purpose):
        access,native,asset=self.spaces.read(actor_id=actor_id,stable_id=self.stable_id(revision),
            revision=revision,purpose=purpose)
        content=decode_knowledge_content(json.loads(asset.content_json))
        if asset.kind!='definition' or content is None:
            raise ValueError('KNOWLEDGE_DOCUMENT_CONTENT_UNSUPPORTED')
        return access,native,content

    def _fence(self,actor_id,revision,access):
        current,_=self.spaces.authorize(actor_id=actor_id,stable_id=access.identity.stable_id,
            revision=revision,purpose=access.purpose)
        if current!=access:raise ValueError('KNOWLEDGE_DOCUMENT_AUTHORITY_CHANGED')

    def _uses(self,actor_id,revision,content):
        reader=KnowledgeUseReader(self.spaces)
        uses=[];snapshots={}
        for contract in content.use_contracts:
            try:
                current,snapshot=reader._current(actor_id,revision,contract.purpose)
                snapshots[contract.purpose]=snapshot
                value,ref=current if current is not None else ({'status':'not_assessed'},None)
                uses.append({'purpose':contract.purpose,'status':value['status'],
                    'qualification_ref':ref.model_dump(mode='json') if ref else None,
                    'qualified_roots':value.get('roots',[]),'use_granted':False})
            except ValueError as error:
                if str(error) not in ('KNOWLEDGE_USE_CURRENT_POLICY_CHANGED','KNOWLEDGE_USE_SERVER_CHECK_CHANGED',
                        'KNOWLEDGE_USE_DEPENDENCY_CHANGED','KNOWLEDGE_SPACE_CONTENT_USE_NOT_AUTHORIZED',
                        'KNOWLEDGE_USE_IDENTITY_TARGET_CHANGED',
                        'KNOWLEDGE_SPACE_ACCESS_DENIED','KNOWLEDGE_SPACE_SOURCE_POLICY_CHANGED'):
                    raise
                # Expose a bounded repair category, never the identity or policy
                # of an inaccessible dependency. Reading still grants no use.
                reason={
                    'KNOWLEDGE_USE_CURRENT_POLICY_CHANGED':'qualification_policy_changed',
                    'KNOWLEDGE_USE_SERVER_CHECK_CHANGED':'qualification_check_changed',
                    'KNOWLEDGE_USE_DEPENDENCY_CHANGED':'qualification_dependency_changed',
                    'KNOWLEDGE_USE_IDENTITY_TARGET_CHANGED':'qualification_dependency_changed',
                }.get(str(error),'current_access_unavailable')
                uses.append({'purpose':contract.purpose,'status':'current_use_unavailable','qualification_ref':None,
                    'qualified_roots':[],'use_granted':False,'unavailable_reason':reason})
                snapshots[contract.purpose]={'unavailable_reason':str(error)}
        # The caller obtains this complete snapshot again before returning.
        # Comparing only the rendered status/roots could hide a changed source,
        # dependency, mechanical check or authority with the same use label.
        # No cross-request cache or authorization shortcut is introduced.
        return uses,snapshots

    def read(self,*,actor_id,request,model_input=True):
        req=PublishedDocumentRead.model_validate(request)
        access,native,content=self._read(actor_id,req.revision,'model_input' if model_input else 'read')
        typed=(TypedKnowledgeMeaning.model_validate(content.meaning)
            if content.meaning.get('contract_version')=='boi/typed-knowledge-meaning@1' else None)
        pointer=req.meaning_pointer
        if req.meaning_pointers is not None:
            if pointer is not None or req.claim_offset:
                raise ValueError('KNOWLEDGE_DOCUMENT_SELECTION_AMBIGUOUS')
            selected=[]
            for requested in dict.fromkeys(req.meaning_pointers):
                if not 1 <= len(requested) <= 2048:
                    raise ValueError('KNOWLEDGE_DOCUMENT_SELECTION_INVALID')
                meaning_pointer(content.meaning,requested)
                parts=requested.split('/')
                if typed is not None and len(parts)>=3 and parts[1] in ('assertions','parameters'):
                    requested='/'+parts[1]+'/'+parts[2]
                if requested not in {p for p,_ in selected}:
                    selected.append((requested,meaning_pointer(content.meaning,requested)))
            total,next_offset=len(selected),None
        elif pointer is not None:
            if req.claim_offset:raise ValueError('KNOWLEDGE_DOCUMENT_SELECTION_AMBIGUOUS')
            # Resolve exact addresses. A field selection still returns the full
            # typed assertion so conditions, negation and dependencies survive.
            meaning_pointer(content.meaning,pointer)
            parts=pointer.split('/')
            if typed is not None and len(parts)>=3 and parts[1] in ('assertions','parameters'):
                pointer='/'+parts[1]+'/'+parts[2]
            selected=[(pointer,meaning_pointer(content.meaning,pointer))]
            total,next_offset=1,None
        elif typed is not None:
            total=len(typed.assertions)+len(typed.parameters)
            if req.claim_offset>total:raise ValueError('KNOWLEDGE_DOCUMENT_PAGE_RANGE_INVALID')
            end=min(total,req.claim_offset+req.claim_limit)
            selected=[]
            for i in range(req.claim_offset,end):
                kind,index=('assertions',i) if i<len(typed.assertions) else ('parameters',i-len(typed.assertions))
                selected.append(('/'+kind+'/'+str(index),content.meaning[kind][index]))
            next_offset=end if end<total else None
        else:
            # Generic Profile meanings retain their own structure; named body
            # bindings expose exact detail links without interpreting the schema.
            pointers=list(dict.fromkeys(b.meaning_pointer for b in content.body_bindings))
            total=len(pointers)
            if req.claim_offset>total:raise ValueError('KNOWLEDGE_DOCUMENT_PAGE_RANGE_INVALID')
            end=min(total,req.claim_offset+req.claim_limit)
            selected=[(p,meaning_pointer(content.meaning,p)) for p in pointers[req.claim_offset:end]]
            next_offset=end if end<total else None
        selected_roots=[p for p,_ in selected]
        # Opt-in evidence reads include the declared dependency closure, rather
        # than sending the model to the same revision one node at a time.
        if req.include_sources:
            if typed is None or any(not (p.startswith('/assertions/') or p.startswith('/parameters/')) for p,_ in selected):
                raise ValueError('KNOWLEDGE_DOCUMENT_CONTENT_UNSUPPORTED')
            by_id={a.id:('/assertions/'+str(i),content.meaning['assertions'][i])
                for i,a in enumerate(typed.assertions)}
            seen={p for p,_ in selected}
            offset=0
            while offset<len(selected):
                _,value=selected[offset]
                for dependency in value.get('depends_on',()) if isinstance(value,dict) else ():
                    item=by_id[dependency]
                    if item[0] not in seen:
                        if len(selected)>=256:
                            raise ValueError('KNOWLEDGE_SOURCE_BUNDLE_LIMIT_REQUIRES_NARROWER_SELECTION')
                        seen.add(item[0]);selected.append(item)
                offset+=1
        url=self.public_links.url(document_url(req.revision))
        claims=[]
        for pointer,value in selected:
            bindings=[{'binding_index':i,'meaning_pointer':b.meaning_pointer,'field_locator':b.field_locator,
                'source_key':semantic_digest({k:v for k,v in b.model_dump(mode='json').items() if k!='meaning_pointer'}),
                'source_url':url+'/sources/'+str(i),'source_access_granted':False}
                for i,b in enumerate(content.evidence_bindings)
                if b.meaning_pointer==pointer or b.meaning_pointer.startswith(pointer+'/')]
            claims.append({'pointer':pointer,'value':value,'source_bindings':bindings,
                'url':url+'?'+urlencode({'meaning':pointer})})
            if typed is not None and isinstance(value,dict) and 'depends_on' in value:
                claims[-1]['dependency_reads']=[{'pointer':'/assertions/'+str(i),
                    'url':url+'?'+urlencode({'meaning':'/assertions/'+str(i)}),
                    'read':{'revision':req.revision.model_dump(mode='json'),'view':'document',
                        'document_options':{'meaning_pointer':'/assertions/'+str(i)}}}
                    for i,a in enumerate(typed.assertions) if a.id in value['depends_on']]
        label_fields=None
        if req.include_source_labels:
            # Filenames are source metadata, not document titles. Resolve them
            # only through the same current source authority check used by an
            # exact source read. No source text is added to the response.
            label_fields=PublishedSourceFields(self,actor_id=actor_id,revision=req.revision,access=access,
                native=native,content=content,model_input=model_input)
            labels={};source_metadata={}
            for claim in claims:
                for binding in claim['source_bindings']:
                    index=binding['binding_index']
                    if index not in labels:
                        _,value,_,_=label_fields.read(index)
                        source_metadata[index]=value.get('structural_metadata',{})
                        labels[index]=label_fields.display_name(
                            label_fields.sources[value['artifact_ref']][2])
                    if labels[index]:binding['source_display_name']=labels[index]
                    if source_metadata[index].get('database_source'):
                        binding['structural_metadata']=source_metadata[index]
        source_bundle=None
        if req.include_sources:
            indices=sorted({b['binding_index'] for c in claims for b in c['source_bindings']})
            fields=PublishedSourceFields(self,actor_id=actor_id,revision=req.revision,access=access,
                native=native,content=content,model_input=model_input)
            source_bundle=fields.bundle(indices,url=url)
            source_bundle['meaning_selection']={'requested_roots':selected_roots,
                'delivered_closure':[p for p,_ in selected], 'closure_complete':True,
                'pagination_counts':'requested_roots_before_dependency_expansion'}
        uses,use_snapshots=self._uses(actor_id,req.revision,content)
        for claim in claims:
            if typed is not None and claim['pointer'].startswith('/parameters/'):
                parameter=claim['value']
                qualified=next((u for u in uses if u['purpose']=='formula_input' and u['status']=='usable_with_limits'
                    and claim['pointer'] in u['qualified_roots']),None)
                claim['formula_selection']={'identity':{'knowledge_id':access.identity.stable_id,'parameter_id':parameter['id']},
                    'revision':req.revision.model_dump(mode='json'),'component':parameter['component'],
                    'quantity':parameter['quantity'],'unit':parameter['semantic_descriptor']['unit_ref'],
                    'semantic_role':parameter['semantic_descriptor']['role']}
                claim['formula_qualification']=qualified['qualification_ref'] if qualified else None
        _,_,policy=self.spaces._policy(access.identity.stable_id)
        self._fence(actor_id,req.revision,access)
        if self._uses(actor_id,req.revision,content)!=(uses,use_snapshots):
            raise ValueError('KNOWLEDGE_DOCUMENT_USE_CHANGED')
        self._fence(actor_id,req.revision,access)
        if req.include_sources:fields.fence()
        if label_fields is not None:label_fields.fence()
        document=content.document.model_dump(mode='json')
        body_complete=not (model_input and (req.meaning_pointer is not None or req.meaning_pointers is not None))
        excerpts=[b.model_dump(mode='json') for b in content.body_bindings
            if any(b.meaning_pointer==p or b.meaning_pointer.startswith(p+'/') for p,_ in selected)]
        if not body_complete:document={**document,'body':None}
        return {'contract_version':'boi/published-document-view@1','actor_id':actor_id,
            'stable_id':access.identity.stable_id,'revision':req.revision.model_dump(mode='json'),
            'feedback_url':url+'#feedback',
            'policy_revision':access.policy_revision.model_dump(mode='json'),'title':native.payload['title'],
            'previous_revision':native.payload.get('previous_revision'),
            'content_correction':(policy.content_correction.model_dump(mode='json')
                if policy.content_correction and req.revision == policy.content_revision else None),
            'description':native.payload['description'],'document':document,'body_complete':body_complete,
            'body_excerpts':excerpts,
            'profiles':[p.model_dump(mode='json') for p in content.profiles],
            'targets':[t.model_dump(mode='json') for t in policy.targets],'publication_state':'published',
            'is_current_revision':req.revision==policy.content_revision,'claims':claims,
            'claim_count':total,'claim_offset':req.claim_offset,'next_claim_offset':next_offset,
            'typed_meaning':typed is not None,'unresolved':[u.model_dump(mode='json') for u in content.unresolved],
            'uses':uses,'source_access_granted':False,'scientific_truth_proven':False,
            'document_url':url,'source_read_view':'document_source','public_links':self.public_links.metadata(),
            **({'source_bundle':source_bundle} if source_bundle is not None else {})}

    def source(self,*,actor_id,request,model_input=True):
        req=PublishedSourceRead.model_validate(request)
        access,native,content=self._read(actor_id,req.revision,'model_input' if model_input else 'cite')
        fields=PublishedSourceFields(self,actor_id=actor_id,revision=req.revision,access=access,
            native=native,content=content,model_input=model_input)
        binding,value,text,start=fields.read(req.binding_index)
        offset=max(0,start-300) if req.offset is None else req.offset
        if offset>len(text):raise ValueError('KNOWLEDGE_SOURCE_PAGE_RANGE_INVALID')
        end=min(len(text),offset+req.limit)
        fields.fence()
        display_name=fields.display_name(fields.sources[value['artifact_ref']][2])
        return {'contract_version':'boi/published-source-view@1','actor_id':actor_id,
            'revision':req.revision.model_dump(mode='json'),'binding_index':req.binding_index,
            'meaning_pointer':binding.meaning_pointer,'field_locator':binding.field_locator,
            'source_revision_digest':binding.source_revision_digest,'span':binding.span.model_dump(mode='json'),
            'field_digest':value['content_digest'],'quote':binding.quote,'quote_start':start,'quote_end':start+len(binding.quote),
            'text':text[offset:end],'offset':offset,'end':end,'character_count':len(text),
            'next_offset':end if end<len(text) else None,'complete_field':offset==0 and end==len(text),
            'transformations':[r.model_dump(mode='json') for r in binding.transformations],
            **({'source_display_name':display_name} if display_name else {}),
            'field_metadata':{k:value[k] for k in ('representation','field_state','value_kind','presence_basis',
                'structural_metadata','parser_digest') if k in value},
            'offset_basis':'decoded_unicode_codepoints','semantic_truth_proven':False,
            'document_url':self.public_links.url(document_url(req.revision)),
            'source_url':self.public_links.url(document_url(req.revision)+'/sources/'+str(req.binding_index)),
            'public_links':self.public_links.metadata()}
