"""Assemble locally authored meanings into an exact, unsubmitted upload bundle.

The caller supplies Profile components, statements, qualifiers, evidence and
coverage dispositions. This module makes no semantic selections. Local revision
stand-ins exist only in the validation view and never enter upload proposals.
It cannot confirm, upload, publish or grant use qualification.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re

from boi_api.app.governed_runtime.knowledge_content import KnowledgeContent
from boi_api.app.governed_runtime.knowledge_profile import KnowledgeProfileDeclaration, KnowledgeProfileRegistry, LocalType
from boi_api.app.governed_runtime.knowledge_use_contract import LocalKnowledgeAssessment, typed_use_closure
from boi_api.app.governed_runtime.knowledge_unresolved_contract import unresolved_inventory_digest, unresolved_review_item, unresolved_evidence_bindings
from boi_api.app.governed_runtime.knowledge_projection_contract import ProjectionRevision, ProjectionComponent
from boi_api.app.governed_runtime.local_bundle_contract import LocalBundleManifest, LocalKnowledgeCorrection
from boi_api.app.governed_runtime.local_bundle_json import LocalJsonDocument, pointer_tokens
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest,RevisionRef
from boi_api.app.governed_runtime.source_envelope import byte_digest, ArtifactEnvelope
from boi_api.app.governed_runtime.spreadsheet_source_projection import workbook_fields
from boi_api.app.governed_runtime.database_source_projection import database_fields
from boi_api.app.governed_runtime.typed_knowledge_meaning import TypedKnowledgeMeaning
from agent_kit.python.boi_local_bundle_archive import use_preparation


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()


def load_authoring_inventory(directory, source_digest, *, context_roles=()):
    """Read declared source context; comparison answers never become evidence."""
    if set(context_roles)-{'source','metadata','review_note'}:
        raise ValueError('LOCAL_AUTHORING_CONTEXT_ROLE_NOT_ALLOWED')
    root=Path(directory)
    manifest=json.loads((root/'manifest.json').read_text())
    if manifest['source_digest']!=source_digest:
        raise ValueError('LOCAL_AUTHORING_INVENTORY_SOURCE_CHANGED')
    fields={}
    for role in ('source','metadata',*(('review_note',) if 'review_note' in context_roles else ())):
        entry=manifest['role_files'].get(role)
        if entry is None:continue
        path=(root/entry['path']).resolve()
        if path.parent!=root.resolve():raise ValueError('LOCAL_AUTHORING_INVENTORY_PATH_INVALID')
        raw=path.read_bytes()
        if byte_digest(raw)!=entry['digest']:raise ValueError('LOCAL_AUTHORING_INVENTORY_BYTES_CHANGED')
        for line in raw.decode().splitlines():
            item=json.loads(line)
            if item['role']!=role or byte_digest(item['text'].encode())!=item['text_digest']:
                raise ValueError('LOCAL_AUTHORING_FIELD_BINDING_CHANGED')
            if item['field_locator'] in fields:raise ValueError('LOCAL_AUTHORING_DUPLICATE_FIELD')
            fields[item['field_locator']]=item
    return fields, manifest


def authoring_context_roles(spec,source_id):
    return {context['role'] for record in spec['records'] if record['source_object_id']==source_id
            for context in record.get('context_fields',[])}


def verify_authoring_fields(raw,fields,media_type=None):
    projected=database_fields(raw) if media_type=='application/json' else workbook_fields(raw)
    actual={field.locator:field for field in projected}
    for locator,item in fields.items():
        field=actual.get(locator)
        if (field is None or field.text!=item['text'] or field.record_locator!=item['record_locator']
                or field.state!=item['state'] or field.value_kind!=item['value_kind']
                or field.structural_metadata!=item['structural_metadata']):
            raise ValueError('LOCAL_AUTHORING_INVENTORY_NOT_ORIGINAL_FIELD')


def quote_range(text, quote, occurrence=0):
    if not quote or type(occurrence) is not int or occurrence<0:
        raise ValueError('LOCAL_AUTHORING_QUOTE_INVALID')
    start=-1
    for _ in range(occurrence+1):
        start=text.find(quote,start+1)
        if start<0:raise ValueError('LOCAL_AUTHORING_QUOTE_NOT_FOUND')
    return start,start+len(quote)


def assemble(spec, *, output):
    """Write a new directory only after all exact local checks pass.

    spec.sources names actual source paths and existing source-only inventories.
    spec.profile is an explicit KnowledgeProfileDeclaration. An optional
    existing_profile_revision pins a previously read Wiki declaration; the
    server still verifies that revision, its actual type and current authority.
    Every record
    provides its source record scope, prose and fully authored typed assertions.
    Proposals retain symbolic refs; the existing confirmed server import owns
    actual source/native revision references and registered checker execution.
    """
    out=Path(output)
    if out.exists():raise ValueError('LOCAL_AUTHORING_OUTPUT_ALREADY_EXISTS')
    review_validation=spec.get('review_validation','report')
    if review_validation not in ('report','strict'):
        raise ValueError('LOCAL_AUTHORING_REVIEW_VALIDATION_MODE_INVALID')
    profile=KnowledgeProfileDeclaration.model_validate(spec['profile'])
    if 'existing_profile_revision' in spec and 'profile_base_revision' in spec:
        raise ValueError('LOCAL_AUTHORING_PROFILE_MODE_AMBIGUOUS')
    existing_profile=(RevisionRef.model_validate(spec['existing_profile_revision'])
        if 'existing_profile_revision' in spec else None)
    profile_base=(RevisionRef.model_validate(spec['profile_base_revision'])
        if 'profile_base_revision' in spec else None)
    if (profile_base is not None) != ('profile_correction' in spec):
        raise ValueError('LOCAL_AUTHORING_PROFILE_CORRECTION_BASIS_REQUIRED')
    profile_correction=(LocalKnowledgeCorrection.model_validate(spec['profile_correction'])
        if profile_base is not None else None)
    if any(c.kind=='predicate' and not hasattr(c.subject_type,'component_id') for c in profile.components):
        raise ValueError('LOCAL_AUTHORING_EXTERNAL_PROFILE_REQUIRES_EXPLICIT_BUNDLE')
    component={c.id:i for i,c in enumerate(profile.components)}
    sources={};fields={};inventories={};reused_sources={};reused_spans={}
    for key,source in spec['sources'].items():
        path=Path(source['path']);raw=path.read_bytes()
        if byte_digest(raw)!=source['byte_digest']:raise ValueError('LOCAL_AUTHORING_SOURCE_BYTES_CHANGED')
        fields[key],inventories[key]=load_authoring_inventory(source['inventory'],source['byte_digest'],
            context_roles=authoring_context_roles(spec,key))
        if source['media_type'] not in ('application/json','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'):
            raise ValueError('LOCAL_AUTHORING_SOURCE_ADAPTER_NOT_SUPPORTED')
        verify_authoring_fields(raw,fields[key],source['media_type'])
        sources[key]=raw
        if ('existing_artifact' in source)!=('existing_field_spans' in source):
            raise ValueError('LOCAL_AUTHORING_EXISTING_SOURCE_BINDINGS_REQUIRED')
        if 'existing_artifact' in source:
            artifact=ArtifactEnvelope.model_validate(source['existing_artifact'])
            if artifact.digest!=source['byte_digest'] or artifact.role!=source['source_role']:
                raise ValueError('LOCAL_AUTHORING_EXISTING_SOURCE_CHANGED')
            reused_sources[key]=artifact.model_dump(mode='json')
            declared=source['existing_field_spans']
            if not isinstance(declared,dict) or not declared:
                raise ValueError('LOCAL_AUTHORING_EXISTING_SOURCE_BINDINGS_REQUIRED')
            for locator,binding in declared.items():
                if (locator not in fields[key] or set(binding)!={'span','source_revision_digest'}
                        or binding['source_revision_digest']!=artifact.digest):
                    raise ValueError('LOCAL_AUTHORING_EXISTING_FIELD_BINDING_CHANGED')
                ref=RevisionRef.model_validate(binding['span'])
                if not ref.ref.startswith('EvidenceSpan:'):
                    raise ValueError('LOCAL_AUTHORING_EXISTING_FIELD_SPAN_REQUIRED')
                reused_spans[key,locator]=ref.model_dump(mode='json')
    profile_raw=encoded(profile.model_dump(mode='json'))
    schema_id='authored-profile-source';profile_id='authored-profile'
    if schema_id in sources or profile_id in sources:raise ValueError('LOCAL_AUTHORING_RESERVED_OBJECT_ID')
    namespace=spec['namespace']
    files={key:raw for key,raw in sources.items() if key not in reused_sources}
    metadata={key:{'purpose':'raw_source','display_name':Path(source['path']).name,
        'media_type':source['media_type'],'source_role':source['source_role']} for key,source in spec['sources'].items() if key not in reused_sources}
    if existing_profile is None:
        files[schema_id]=profile_raw
        metadata[schema_id]={'purpose':'raw_source','display_name':'authored-profile.json','media_type':'application/json','source_role':'schema'}
    proposals={};references=[];coverage=[];validation_contents={}
    existing={existing_profile} if existing_profile is not None else set()
    retained_sources={semantic_digest(value):value for value in reused_sources.values()}
    record_changes={}
    if profile_base is not None:
        existing.add(profile_base)
    record_existing={}
    def bind(owner,pointer,target,kind,locator=None):
        if target in reused_sources:
            if kind=='artifact_envelope':return deepcopy(reused_sources[target])
            if kind not in ('source_span','source_revision_digest') or (target,locator) not in reused_spans:
                raise ValueError('LOCAL_AUTHORING_EXISTING_SOURCE_BINDING_MISSING')
            return (deepcopy(reused_spans[target,locator]) if kind=='source_span'
                    else reused_sources[target]['digest'])
        token='@local:'+kind+':'+target+(':'+semantic_digest(locator)[7:23] if locator is not None else '')
        references.append({'object_id':owner,'pointer':pointer,'placeholder':token,'target_object_id':target,
            'kind':kind,**({'field_locator':locator} if locator is not None else {})})
        return token
    def metadata_draft(identity,title,description,kind):
        return {'namespace':namespace,'logical_id':identity,'title':title,'description':description,'kind':kind}
    if existing_profile is None:
        proposals[profile_id]={'contract_version':'boi/local-native-draft@1',
            'draft':{**metadata_draft(spec['profile_logical_id'],profile.label,profile.description,'profile'),
                **({'previous_revision':profile_base.model_dump(mode='json')} if profile_base is not None else {}),
                'sources':[bind(profile_id,'/draft/sources/0',schema_id,'artifact_envelope')]},
            'content':profile.model_dump(mode='json')}
    # The typed schema requires this exact ref shape. This derived stand-in is
    # not a native ledger revision and must never leave the validation view.
    local_digest=semantic_digest(['local-validation-only',byte_digest(profile_raw)])
    local_profile=(ProjectionRevision.model_validate(existing_profile.model_dump(mode='json'))
        if existing_profile is not None else
        ProjectionRevision(ref='KnowledgeRevision:'+local_digest,revision_digest=local_digest))
    registry=KnowledgeProfileRegistry({local_profile:profile})
    def profile_revision(owner,pointer):
        return (existing_profile.model_dump(mode='json') if existing_profile is not None
            else bind(owner,pointer,profile_id,'knowledge_revision'))
    records={r['object_id']:r for r in spec['records']}
    if len(records)!=len(spec['records']):raise ValueError('LOCAL_AUTHORING_DUPLICATE_OBJECT')
    existing_records=spec.get('existing_records',{})
    if not isinstance(existing_records,dict) or len(existing_records)>500:
        raise ValueError('LOCAL_AUTHORING_EXISTING_RECORD_DECLARATION_REQUIRED')
    targets={}
    for key,value in existing_records.items():
        if key in records or not isinstance(value,dict) or set(value)!={'stable_id','revision','object_type'}:
            raise ValueError('LOCAL_AUTHORING_EXISTING_RECORD_DECLARATION_REQUIRED')
        if not isinstance(value['stable_id'],str) or not re.fullmatch(r'domain-asset-head:sha256:[a-f0-9]{64}',value['stable_id']):
            raise ValueError('LOCAL_AUTHORING_EXISTING_IDENTITY_INVALID')
        targets[key]=(value['stable_id'],RevisionRef.model_validate(value['revision']),
            ProjectionComponent.model_validate(value['object_type']))
    if len({v[0] for v in targets.values()})!=len(targets):
        raise ValueError('LOCAL_AUTHORING_EXISTING_IDENTITY_AMBIGUOUS')
    selected_records=set()
    for record in spec['records']:
        identity=record['object_id']
        if identity in sources or identity in files or identity in proposals or identity in (schema_id,profile_id):
            raise ValueError('LOCAL_AUTHORING_DUPLICATE_OBJECT')
        if ('previous_revision' in record)!=('correction' in record):
            raise ValueError('LOCAL_AUTHORING_RECORD_CORRECTION_BASIS_REQUIRED')
        base=(RevisionRef.model_validate(record['previous_revision']) if 'previous_revision' in record else None)
        correction=(LocalKnowledgeCorrection.model_validate(record['correction']) if base is not None else None)
        if base is not None:
            existing.add(base)
            record_changes[identity]={'operation':'revise','previous_revision':base.model_dump(mode='json'),
                'correction':correction.model_dump(mode='json')}
        prior_sources=[ArtifactEnvelope.model_validate(s).model_dump(mode='json') for s in record.get('existing_sources',[])]
        if len({semantic_digest(s) for s in prior_sources})!=len(prior_sources):
            raise ValueError('LOCAL_AUTHORING_EXISTING_SOURCE_DUPLICATE')
        for source in prior_sources:retained_sources[semantic_digest(source)]=source
        record_targets=set()
        source_id=record['source_object_id'];source_fields=fields[source_id]
        scope=(source_id,record['source_record_locator'])
        selected_records.add(scope)
        contexts=record.get('context_fields',[])
        if len(contexts)>64:raise ValueError('LOCAL_AUTHORING_CONTEXT_FIELD_LIMIT')
        context_locators=set()
        for context in contexts:
            if (set(context)!={'field_locator','role','reason'} or not isinstance(context['reason'],str)
                    or not context['reason'].strip() or len(context['reason'])>2000):
                raise ValueError('LOCAL_AUTHORING_CONTEXT_DECLARATION_REQUIRED')
            field=source_fields.get(context['field_locator'])
            if (field is None or field['role']!=context['role'] or context['role'] not in ('source','metadata','review_note')
                    or context['field_locator'] in context_locators):
                raise ValueError('LOCAL_AUTHORING_CONTEXT_FIELD_BINDING_CHANGED')
            context_locators.add(context['field_locator'])
        authored=deepcopy(record['assertions'])
        parameters=deepcopy(record.get('parameters',[]))
        if not authored:raise ValueError('LOCAL_AUTHORING_ASSERTIONS_REQUIRED')
        body=record['body'];evidence=[];body_bindings=[];spans={};primary_evidence=[]
        def profile_ref(pointer,predicate_id):
            if predicate_id not in component:raise ValueError('LOCAL_AUTHORING_COMPONENT_NOT_DECLARED')
            return {'revision':profile_revision(identity,pointer+'/revision'),
                'pointer':'/components/'+str(component[predicate_id])}
        def identity_ref(pointer,target,expected_type):
            other=records.get(target)
            if other is None:
                if target not in targets:raise ValueError('LOCAL_AUTHORING_RELATION_TARGET_UNAVAILABLE')
                stable,revision,actual_type=targets[target]
                if actual_type!=expected_type:raise ValueError('LOCAL_AUTHORING_RELATION_TARGET_TYPE_MISMATCH')
                record_targets.add(revision);existing.add(revision)
                return stable
            actual_type=registry.type_reference(local_profile,LocalType(component_id=other['object_type_id']))
            if actual_type!=expected_type:raise ValueError('LOCAL_AUTHORING_RELATION_TARGET_TYPE_MISMATCH')
            return bind(identity,pointer,target,'knowledge_identity')
        def typed_value(value,pointer,predicate_id):
            if predicate_id not in component:raise ValueError('LOCAL_AUTHORING_COMPONENT_NOT_DECLARED')
            _,predicate=registry.predicate(ProjectionComponent(revision=local_profile,
                pointer='/components/'+str(component[predicate_id])))
            if value.get('kind')=='object':
                if set(value)!={'kind','target_object_id'}:
                    raise ValueError('LOCAL_AUTHORING_OBJECT_TARGET_REQUIRED')
                return {'kind':'object','value':identity_ref(pointer+'/value',value['target_object_id'],predicate.target_type)}
            return value
        def add_evidence(pointer,quotes):
            if not quotes:raise ValueError('LOCAL_AUTHORING_NODE_EVIDENCE_REQUIRED')
            for q in quotes:
                locator=q['field_locator'];field=source_fields.get(locator)
                if field is None or (field['record_locator']!=scope[1] and locator not in context_locators):
                    raise ValueError('LOCAL_AUTHORING_FIELD_OUTSIDE_RECORD')
                if field['role']=='source' and field['record_locator']==scope[1]:primary_evidence.append(locator)
                quote_range(field['text'],q['quote'],q.get('quote_occurrence',0))
                spans.setdefault(locator,len(spans))
                i=len(evidence)
                evidence.append({'meaning_pointer':pointer,'span':bind(identity,
                    f'/content/evidence_bindings/{i}/span',source_id,'source_span',locator),
                    'source_revision_digest':bind(identity,f'/content/evidence_bindings/{i}/source_revision_digest',
                        source_id,'source_revision_digest',locator),'field_locator':locator,
                    'quote':q['quote'],'quote_occurrence':q.get('quote_occurrence',0)})
        for i,assertion in enumerate(authored):
            pointer=f'/assertions/{i}'
            assertion['value']=typed_value(assertion['value'],'/content/meaning'+pointer+'/value',assertion['predicate_id'])
            assertion['predicate']=profile_ref('/content/meaning'+pointer+'/predicate',assertion.pop('predicate_id'))
            add_evidence(pointer,assertion.pop('evidence'))
            # The author may bind a precise prose passage shared by several
            # claims. Exact span checks do not judge its semantic equivalence.
            body_quote=assertion.pop('body_quote',assertion['statement'])
            start,end=quote_range(body,body_quote,assertion.pop('body_occurrence',0))
            body_bindings.append({'meaning_pointer':pointer,'start':start,'end':end,
                'quote':body_quote,'assertion_kind':assertion['assertion_kind']})
            for group in ('conditions','exceptions','applicability'):
                for ci,clause in enumerate(assertion[group]):
                    cp=f'{pointer}/{group}/{ci}';add_evidence(cp,clause.pop('evidence'))
                    for ai,atom in enumerate(clause.get('atoms',[])):
                        if 'subject_object_id' in atom:
                            if 'subject_ref' in atom:raise ValueError('LOCAL_AUTHORING_CONDITION_SUBJECT_AMBIGUOUS')
                            if atom['predicate_id'] not in component:raise ValueError('LOCAL_AUTHORING_COMPONENT_NOT_DECLARED')
                            _,predicate=registry.predicate(ProjectionComponent(revision=local_profile,
                                pointer='/components/'+str(component[atom['predicate_id']])))
                            atom['subject_ref']=identity_ref(f'/content/meaning{cp}/atoms/{ai}/subject_ref',
                                atom.pop('subject_object_id'),predicate.subject_type)
                        atom['value']=typed_value(atom['value'],f'/content/meaning{cp}/atoms/{ai}/value',atom['predicate_id'])
                        atom['predicate']=profile_ref(f'/content/meaning{cp}/atoms/{ai}/predicate',atom.pop('predicate_id'))
            if assertion['valid_time']['state']!='unknown':
                add_evidence(pointer+'/valid_time',assertion.pop('valid_time_evidence'))
        dependencies=[{'revision':ref.model_dump(mode='json'),'role':'relation_target',
            'reason':'Exact already-read identity target; current identity, type and source access require server verification',
            'required':True,'stages':['review','explain','execute']} for ref in sorted(record_targets,key=lambda r:r.ref)]
        seen={(ref,'relation_target') for ref in record_targets}
        for i,parameter in enumerate(parameters):
            pointer=f'/parameters/{i}'
            add_evidence(pointer,parameter.pop('evidence'))
            quote=parameter.pop('body_quote',parameter['statement'])
            start,end=quote_range(body,quote,parameter.pop('body_occurrence',0))
            body_bindings.append({'meaning_pointer':pointer,'start':start,'end':end,
                'quote':quote,'assertion_kind':parameter['assertion_kind']})
            for key,role in (('unit_definition','semantic_unit_definition'),('quantity_definition','semantic_quantity_definition')):
                ref=RevisionRef.model_validate(parameter[key]);existing.add(ref)
                if (ref,role) not in seen:
                    dependencies.append({'revision':ref.model_dump(mode='json'),'role':role,
                        'reason':'Explicit authored parameter definition','required':True,'stages':['review','explain','execute']})
                    seen.add((ref,role))
        unresolved=deepcopy(record['unresolved'])
        for i,item in enumerate(unresolved):
            if 'evidence' not in item:
                continue
            if item.get('source_spans'):
                raise ValueError('LOCAL_AUTHORING_UNRESOLVED_EVIDENCE_MODE_AMBIGUOUS')
            quotations=item.pop('evidence')
            # Explicit source context is bound to the meaning root; the authored
            # item keeps its own exact spans, subject, facets and description.
            add_evidence('',quotations)
            locators=list(dict.fromkeys(q['field_locator'] for q in quotations))
            item['source_spans']=[bind(identity,f'/content/unresolved/{i}/source_spans/{j}',
                source_id,'source_span',locator) for j,locator in enumerate(locators)]
        record_existing[identity]=sorted({ref for ref,_ in seen} | (
            {existing_profile} if existing_profile is not None else set()),key=lambda ref:ref.ref)
        if not primary_evidence:raise ValueError('LOCAL_AUTHORING_PRIMARY_RECORD_EVIDENCE_REQUIRED')
        primary_source=bind(identity,'/draft/sources/0',source_id,'artifact_envelope')
        prior_sources=[s for s in prior_sources if s!=primary_source]
        draft={**metadata_draft(record['logical_id'],record['title'],record['description'],'definition'),
            **({'previous_revision':base.model_dump(mode='json')} if base is not None else {}),
            'sources':[primary_source,*prior_sources],
            'dependencies':[{'revision':profile_revision(identity,'/draft/dependencies/0/revision'),
                'role':'profile','reason':('Previously read type and predicate declarations' if existing_profile is not None
                    else 'Authored type and predicate declarations'),'stages':['authoring']},*dependencies],
            'evidence_spans':[bind(identity,f'/draft/evidence_spans/{i}',source_id,'source_span',locator)
                for locator,i in spans.items()]}
        content={'contract_version':'boi/knowledge-content@1','document':{'frontmatter':record['frontmatter'],'body':body},
            'profiles':[{'profile_id':profile.profile_id,'schema_ref':profile.schema_ref,
                'revision':profile_revision(identity,'/content/profiles/0/revision')}],
            'meaning':{'contract_version':'boi/typed-knowledge-meaning@1',
                'object_type':profile_ref('/content/meaning/object_type',record['object_type_id']),'assertions':authored,
                **({'parameters':parameters} if parameters else {})},
            'body_bindings':body_bindings,'evidence_bindings':evidence,'unresolved':unresolved,
            'use_contracts':record['use_contracts'],'extensions':{'boi/local-authoring':{
                'author_session_ref':spec['author_session_ref'],'source_record_locator':scope[1],
                'coverage_disposition':record['coverage_disposition'],'independent_review':False,
                **({'context_fields':deepcopy(contexts)} if contexts else {})}}}
        proposal={'contract_version':'boi/local-native-draft@1','draft':draft,'content':content}
        # Explicit local type view only. Never save invented server references.
        view=deepcopy(content)
        for binding in references:
            if binding['object_id']!=identity or not binding['pointer'].startswith('/content/'):continue
            path=pointer_tokens(binding['pointer'])[1:];parent=view
            for part in path[:-1]:parent=parent[int(part)] if isinstance(parent,list) else parent[part]
            key=int(path[-1]) if isinstance(parent,list) else path[-1]
            if parent[key]!=binding['placeholder']:raise ValueError('LOCAL_AUTHORING_LOCAL_REFERENCE_CHANGED')
            if binding['kind']=='knowledge_revision':parent[key]=local_profile.model_dump(mode='json')
            elif binding['kind']=='knowledge_identity':parent[key]='local-validation-only:identity:'+binding['target_object_id']
            elif binding['kind']=='source_span':parent[key]={'ref':'local-validation-only:'+binding['placeholder'],
                'revision_digest':semantic_digest(binding['placeholder'])}
            elif binding['kind']=='source_revision_digest':parent[key]=spec['sources'][source_id]['byte_digest']
            else:raise ValueError('LOCAL_AUTHORING_CONTENT_REFERENCE_KIND_UNSUPPORTED')
        view=KnowledgeContent.model_validate(view)
        validation_contents[identity]=view
        typed=TypedKnowledgeMeaning.model_validate(view.meaning)
        registry.validate_metadata(typed.object_type,view.document.frontmatter)
        for assertion in typed.assertions:
            declaration,predicate=registry.predicate(assertion.predicate)
            if predicate.subject_type!=typed.object_type or predicate.value_kind!=assertion.value.kind:
                raise ValueError('LOCAL_AUTHORING_ASSERTION_TYPE_MISMATCH')
            for group in (assertion.conditions,assertion.exceptions,assertion.applicability):
                for clause in group:
                    for atom in clause.atoms:
                        declared,atom_predicate=registry.predicate(atom.predicate)
                        if atom.operator not in declared.allowed_operators or atom.value.kind!=atom_predicate.value_kind:
                            raise ValueError('LOCAL_AUTHORING_CONDITION_TYPE_MISMATCH')
        proposals[identity]=proposal
        coverage.append({'object_id':identity,'source_record_locator':scope[1],
            'assertions':len(authored),'evidence_bindings':len(evidence),
            'disposition':record['coverage_disposition'],'local_checks_passed':True,
            'registered_server_checks_passed':False,'semantic_opinion_independent':False})
    for key,proposal in proposals.items():
        files[key]=encoded(proposal)
        metadata[key]={'purpose':'native_proposal','display_name':key+'.json','media_type':'application/json'}
    for assessment in spec.get('assessments',[]):
        target=assessment['target_object_id']
        if target not in proposals or target==profile_id:raise ValueError('LOCAL_AUTHORING_ASSESSMENT_TARGET_INVALID')
        key=target+'-assessment'
        if key in files:raise ValueError('LOCAL_AUTHORING_DUPLICATE_ASSESSMENT')
        # Digests are mechanical; labels/reasons/evidence are supplied opinions.
        # Never manufacture a positive review from successful local checks.
        closure={target}
        while True:
            added={r['target_object_id'] for r in references if r['object_id'] in closure}
            if added<=closure:break
            closure.update(added)
        for use in assessment['uses']:
            if use['purpose'] not in spec['intended_uses']:
                raise ValueError('LOCAL_AUTHORING_ASSESSMENT_USE_NOT_DECLARED')
            content=validation_contents[target]
            contract=next((u for u in content.use_contracts if u.purpose==use['purpose']),None)
            if contract is None or tuple(use['requested_pointers'])!=contract.required_meaning_pointers:
                raise ValueError('LOCAL_AUTHORING_ASSESSMENT_SCOPE_MISMATCH')
            expected_nodes=set(typed_use_closure(content,contract)['closure'])
            if {j['pointer'] for j in use['judgments']}!=expected_nodes:
                raise ValueError('LOCAL_AUTHORING_ASSESSMENT_FULL_NODE_CLOSURE_REQUIRED')
            quotations=[]
            for judgment in use['judgments']:
                node=judgment['pointer']
                bound={b.field_locator for b in content.evidence_bindings
                    if b.meaning_pointer==node or b.meaning_pointer.startswith(node+'/')}
                if {q['field_locator'] for q in judgment['evidence']}!=bound:
                    raise ValueError('LOCAL_AUTHORING_ASSESSMENT_NODE_EVIDENCE_MISMATCH')
                quotations.extend(judgment['evidence'])
            # Check authored reviews against the exact symbolic upload inventory,
            # not the local validation stand-ins. Preserve all labels/reasons;
            # matching bytes never manufactures a positive semantic opinion.
            # Existing authoring workflows assemble incomplete review inventories
            # for inspection before completing them. Preserve that report-only
            # mode; an explicitly strict candidate must pass before any write.
            for review_key in (('statement_review','formula_review') if review_validation=='strict' else ()):
                review=use.get(review_key)
                if review is None:continue
                inventory=proposals[target]['content']['unresolved']
                items=review['items']
                if (review['inventory_digest']!=unresolved_inventory_digest(inventory)
                        or len(items)!=len(inventory)
                        or {item['index'] for item in items}!=set(range(len(inventory)))):
                    raise ValueError('LOCAL_AUTHORING_REVIEW_FULL_INVENTORY_REQUIRED')
                for item in items:
                    if item['item_digest']!=semantic_digest(unresolved_review_item(inventory[item['index']])):
                        raise ValueError('LOCAL_AUTHORING_REVIEW_ITEM_CHANGED')
                    bindings=unresolved_evidence_bindings(content,content.unresolved[item['index']])
                    # This local view uses provided byte digests. Server import
                    # separately binds them to authorized artifact revisions.
                    required={(b.source_revision_digest,b.field_locator) for b in bindings}
                    observed={(q['source_byte_digest'],q['field_locator']) for q in item['evidence']}
                    if not required or required!=observed:
                        raise ValueError('LOCAL_AUTHORING_REVIEW_SOURCE_CLOSURE_MISMATCH')
                    quotations.extend(item['evidence'])
            for quotation in quotations:
                source_id=quotation['source_object_id'];locator=quotation['field_locator']
                if (source_id not in closure and source_id not in reused_sources) or source_id not in sources:
                    raise ValueError('LOCAL_AUTHORING_ASSESSMENT_SOURCE_OUTSIDE_INPUTS')
                if quotation['source_byte_digest']!=spec['sources'][source_id]['byte_digest']:
                    raise ValueError('LOCAL_AUTHORING_ASSESSMENT_SOURCE_CHANGED')
                if locator not in fields[source_id]:raise ValueError('LOCAL_AUTHORING_ASSESSMENT_FIELD_UNAVAILABLE')
                quote_range(fields[source_id][locator]['text'],quotation['quote'],quotation['quote_occurrence'])
        bound_assessment=deepcopy(assessment)
        for use in bound_assessment['uses']:
            opinions=[*use['judgments'],*(use.get('statement_review') or {}).get('items',[]),
                      *(use.get('formula_review') or {}).get('items',[])]
            for opinion in opinions:
                for quote in opinion['evidence']:
                    source_id=quote.get('source_object_id')
                    if source_id in reused_sources:
                        quote.pop('source_object_id')
                        quote['existing_source']=deepcopy(reused_sources[source_id])
        value=LocalKnowledgeAssessment.model_validate({**bound_assessment,
            **({'existing_revisions':[r.model_dump(mode='json') for r in record_existing[target]]} if record_existing[target] else {}),
            'target_byte_digest':byte_digest(files[target]),
            'input_objects':[{'object_id':identity,'byte_digest':byte_digest(files[identity])} for identity in sorted(closure)]})
        files[key]=encoded(value.model_dump(mode='json'))
        metadata[key]={'purpose':'check_evidence','display_name':key+'.json','media_type':'application/json'}
    manifest=LocalBundleManifest.model_validate({'contract_version':'boi/local-bundle-manifest@2',
        'publication_layout':{'mode':'dependency_units','maximum_unit_changes':50},
        'title':spec['title'],'description':spec['description'],'target_space':{'visibility':'private'},
        'objects':[{'object_id':key,**metadata[key],'byte_digest':byte_digest(raw),'byte_length':len(raw)}
            for key,raw in files.items()],
        'changes':[{'object_id':key,**{k:v['draft'][k] for k in ('namespace','logical_id','kind','title')},
            'summary':v['draft']['description'],
            **({'operation':'revise','previous_revision':profile_base.model_dump(mode='json'),
                'correction':profile_correction.model_dump(mode='json')}
                if key==profile_id and profile_base is not None else record_changes.get(key,{'operation':'create'}))}
            for key,v in proposals.items()],
        'references':references,'intended_uses':spec['intended_uses'],'unresolved':spec['unresolved'],
        **({'existing_sources':[retained_sources[k] for k in sorted(retained_sources)]} if retained_sources else {}),
        **({'existing_revisions':[r.model_dump(mode='json') for r in sorted(existing,key=lambda ref:ref.ref)]} if existing else {})})
    for key in proposals:
        bindings=[b for b in manifest.references if b.object_id==key]
        LocalJsonDocument(files[key],[b.pointer for b in bindings]).check_bindings(bindings)
    report={'contract_version':'boi/local-authoring-report@1','manifest_digest':manifest.digest,
        'use_preparation':use_preparation(manifest, files),
        'authoring_spec_digest':semantic_digest(spec),'records':coverage,
        'source_record_totals':{key:value['role_record_counts']['source'] for key,value in inventories.items()},
        'selected_source_records':len(selected_records),'authored_knowledge_objects':len(coverage),
        'local_only':True,'server_preview_created':False,'confirmation_recorded':False,'publication_committed':False,
        'source_semantic_coverage_complete':False,'registered_server_checks_passed':False,
        'qualification_granted':False,'comparison_role_files_read':False,
        'explicit_review_note_sources':[key for key in spec['sources']
            if 'review_note' in authoring_context_roles(spec,key)],
        'comparison_answers_used_for_authoring':False,'original_source_bytes_parsed':True,
        'original_workbook_bytes_parsed':all(s['media_type']=='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' for s in spec['sources'].values())}
    out.mkdir(parents=True,mode=0o700)
    for key,raw in files.items():
        path=out/(key+'.blob');path.write_bytes(raw);path.chmod(0o600)
    (out/'manifest.json').write_bytes(encoded(manifest.model_dump(mode='json')))
    (out/'authoring-report.json').write_bytes(encoded(report))
    return report


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    spec=LocalJsonDocument(args.spec.read_bytes(),require_content=False).value
    print(json.dumps(assemble(spec,output=args.output),ensure_ascii=False))


if __name__=='__main__':main()
