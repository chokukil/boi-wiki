"""Assemble source-bound unit and quantity definitions for Formula preparation.

The caller supplies every identifier, interpretation, limitation and exact existing
source span.  This module only builds a locally inspectable publication bundle.  It
does not normalize unit labels, choose a physical dimension, upload bytes, record a
definition review, qualify a parameter, or publish anything.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from boi_api.app.governed_runtime.common_knowledge_contract import CommonKnowledgeMeaning
from boi_api.app.governed_runtime.formula_preview import UnitDefinition
from boi_api.app.governed_runtime.knowledge_content import KnowledgeContent
from boi_api.app.governed_runtime.knowledge_profile import KnowledgeProfileDeclaration
from boi_api.app.governed_runtime.local_bundle_contract import LocalBundleManifest
from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef
from boi_api.app.governed_runtime.source_envelope import ArtifactEnvelope, byte_digest


UNIT = 'boi/native-unit-interpretation@1'
COMMON = 'boi/common-meaning@1'


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def _evidence(items, source):
    result=[]
    for item in items:
        if set(item) != {'span','field_locator','quote'} or not item['quote']:
            raise ValueError('LOCAL_FORMULA_DEFINITION_EVIDENCE_REQUIRED')
        span=RevisionRef.model_validate(item['span'])
        if not span.ref.startswith('EvidenceSpan:'):
            raise ValueError('LOCAL_FORMULA_DEFINITION_EVIDENCE_SPAN_REQUIRED')
        result.append({'span':span.model_dump(mode='json'),'quote':item['quote'],
            'source_revision_digest':source.digest,'field_locator':item['field_locator'],
            'span_ref':span.ref})
    if not result:raise ValueError('LOCAL_FORMULA_DEFINITION_EVIDENCE_REQUIRED')
    return result


def _profile(*, namespace, object_id, logical_id, profile_id, schema_ref, label,
             frontmatter_type, source):
    content={'contract_version':'boi/knowledge-profile@1','profile_id':profile_id,
        'schema_ref':schema_ref,'label':label,
        'description':'Source-bound structural definition profile; it grants no semantic truth or execution authority.',
        'components':[{'kind':'object_type','id':'definition','label':label,
            'description':'One source-bound structural definition.',
            'metadata_constraints':[{'pointer':'/type','value_kind':'text','required':True,
                'allowed_values':[frontmatter_type]}]}]}
    KnowledgeProfileDeclaration.model_validate(content)
    return {'contract_version':'boi/local-native-draft@1','draft':{
        'namespace':namespace,'logical_id':logical_id,'kind':'profile','title':label,
        'description':'Profile for '+schema_ref,'sources':[source.model_dump(mode='json')]},
        'content':content}


def _definition_draft(spec, *, namespace, source, profile_object_id, profile_id,
                      schema_ref, frontmatter_type, meaning, evidence):
    body=spec['body']
    if not isinstance(body,str) or not body.strip():
        raise ValueError('LOCAL_FORMULA_DEFINITION_BODY_REQUIRED')
    bindings=[]
    for item in evidence:
        bindings.append({'meaning_pointer':'','span':item['span'],
            'source_revision_digest':source.digest,'field_locator':item['field_locator'],
            'quote':item['quote'],'quote_occurrence':item.get('quote_occurrence',0)})
    content={'contract_version':'boi/knowledge-content@1',
        'document':{'frontmatter':{'okf_version':'0.2','type':frontmatter_type},'body':body},
        'profiles':[{'profile_id':profile_id,'schema_ref':schema_ref,'revision':'@profile'}],
        'meaning':meaning,
        'body_bindings':[{'meaning_pointer':'','start':0,'end':len(body),'quote':body,
            'assertion_kind':'interpretation'}],
        'evidence_bindings':bindings,'unresolved':[],'use_contracts':[],
        'extensions':{'boi/local-formula-definition':{
            'author_session_ref':spec['author_session_ref'],
            'interpretation_scope':spec['interpretation_scope'],
            'automatic_unit_normalization':False,'scientific_truth_proven':False}}}
    # Replace the local profile placeholder only for structural validation.
    validation=deepcopy(content)
    validation['profiles'][0]['revision']={'ref':'KnowledgeRevision:sha256:'+'0'*64,
        'revision_digest':'sha256:'+'0'*64}
    KnowledgeContent.model_validate(validation)
    spans=[]
    for item in evidence:
        if item['span'] not in spans:spans.append(item['span'])
    return {'contract_version':'boi/local-native-draft@1','draft':{
        'namespace':namespace,'logical_id':spec['logical_id'],'kind':'definition',
        'title':spec['title'],'description':spec['description'],
        'sources':[source.model_dump(mode='json')],
        'evidence_spans':spans,
        'dependencies':[{'revision':'@profile','role':'profile','reason':'Declared structural definition schema',
            'required':True,'stages':['authoring']}]},'content':content}


def assemble_formula_definitions(spec, *, output):
    """Create a new checked directory from explicit source-bound definitions."""
    out=Path(output)
    if out.exists():raise ValueError('LOCAL_FORMULA_DEFINITION_OUTPUT_ALREADY_EXISTS')
    required={'namespace','source','unit','quantity','title','description'}
    if set(spec) != required:
        raise ValueError('LOCAL_FORMULA_DEFINITION_SPEC_FIELDS_INVALID')
    namespace=spec['namespace']
    if not isinstance(spec['source'],dict) or spec['source'].get('kind')!='artifact_ref':
        raise ValueError('LOCAL_FORMULA_DEFINITION_EXISTING_SOURCE_REQUIRED')
    source=ArtifactEnvelope.model_validate(spec['source'])
    unit,quantity=deepcopy(spec['unit']),deepcopy(spec['quantity'])
    common={'object_id','logical_id','title','description','author_session_ref','interpretation_scope',
        'body','evidence'}
    if set(unit)!=common|{'unit_id','dimension','reference_unit','limitations'}:
        raise ValueError('LOCAL_FORMULA_UNIT_SPEC_FIELDS_INVALID')
    if set(quantity)!=common|{'concept_id','label','definition','dimension','limitations'}:
        raise ValueError('LOCAL_FORMULA_QUANTITY_SPEC_FIELDS_INVALID')
    if unit['object_id']==quantity['object_id']:
        raise ValueError('LOCAL_FORMULA_DEFINITION_OBJECT_DUPLICATE')
    unit_evidence=_evidence(unit['evidence'],source)
    quantity_evidence=_evidence(quantity['evidence'],source)
    unit_meaning={'contract_version':UNIT,'unit_definition':{
        'unit_id':unit['unit_id'],'dimension':unit['dimension'],'scale':'1',
        'scale_denominator':'1','offset':'0'},'reference_unit':unit['reference_unit'],
        'limitations':unit['limitations']}
    # Validate numeric structure without fabricating a native revision.
    UnitDefinition.model_validate({**unit_meaning['unit_definition'],
        'revision':{'ref':'KnowledgeRevision:sha256:'+'0'*64,'revision_digest':'sha256:'+'0'*64}})
    quantity_meaning={'contract_version':COMMON,'profile':'OKF-0.2+boi-profile',
        'concepts':[{'id':quantity['concept_id'],'label':quantity['label'],'kind':'quantity',
            'definition':quantity['definition'],'quantity_dimension':quantity['dimension'],
            'evidence':quantity_evidence}], 'limitations':quantity['limitations']}
    CommonKnowledgeMeaning.model_validate(quantity_meaning)
    unit_profile_id=unit['logical_id']+':profile';quantity_profile_id=quantity['logical_id']+':profile'
    objects={
        'unit_profile':_profile(namespace=namespace,object_id='unit_profile',
            logical_id=unit_profile_id,profile_id=unit_profile_id,schema_ref=UNIT,
            label='Formula unit definition',frontmatter_type='unit-definition',source=source),
        unit['object_id']:_definition_draft(unit,namespace=namespace,source=source,
            profile_object_id='unit_profile',profile_id=unit_profile_id,schema_ref=UNIT,
            frontmatter_type='unit-definition',meaning=unit_meaning,evidence=unit_evidence),
        'quantity_profile':_profile(namespace=namespace,object_id='quantity_profile',
            logical_id=quantity_profile_id,profile_id=quantity_profile_id,schema_ref=COMMON,
            label='Formula quantity definition',frontmatter_type='quantity-definition',source=source),
        quantity['object_id']:_definition_draft(quantity,namespace=namespace,source=source,
            profile_object_id='quantity_profile',profile_id=quantity_profile_id,schema_ref=COMMON,
            frontmatter_type='quantity-definition',meaning=quantity_meaning,evidence=quantity_evidence)}
    files={key:_encoded(value) for key,value in objects.items()}
    refs=[]
    for identity,profile in ((unit['object_id'],'unit_profile'),(quantity['object_id'],'quantity_profile')):
        refs.extend({'object_id':identity,'pointer':pointer,'placeholder':'@profile',
            'target_object_id':profile,'kind':'knowledge_revision'} for pointer in
            ('/draft/dependencies/0/revision','/content/profiles/0/revision'))
    changes=[]
    for identity,value in objects.items():
        draft=value['draft'];changes.append({'object_id':identity,'namespace':draft['namespace'],
            'logical_id':draft['logical_id'],'kind':draft['kind'],'title':draft['title'],
            'summary':'Source-bound Formula definition preparation; no automatic unit normalization.',
            'operation':'create'})
    manifest=LocalBundleManifest.model_validate({'contract_version':'boi/local-bundle-manifest@2',
        'title':spec['title'],'description':spec['description'],'target_space':{'visibility':'private'},
        'objects':[{'object_id':key,'purpose':'native_proposal','display_name':key+'.json',
            'byte_digest':byte_digest(raw),'byte_length':len(raw),'media_type':'application/json'}
            for key,raw in files.items()], 'changes':changes,'references':refs,
        'existing_sources':[source.model_dump(mode='json')],
        'intended_uses':['read','formula_input'],
        'publication_layout':{'co_publish_groups':[list(objects)]},
        'unresolved':['Unit and quantity meanings require an attributed native definition review before Formula use.']})
    out.mkdir(parents=True)
    (out/'manifest.json').write_bytes(_encoded(manifest.model_dump(mode='json')))
    for key,raw in files.items():(out/(key+'.blob')).write_bytes(raw)
    return {'manifest_digest':manifest.digest,'object_ids':list(objects),
        'publication_committed':False,'definition_review_recorded':False,
        'formula_input_qualified':False,'automatic_unit_normalization':False}
