"""Mechanical native-to-index adapter; no LLM, adoption or source-truth verdict.

The enclosing service supplies an authorized exact revision reader and separately
checks confirmation and use qualifications before publishing the prepared batch.
"""
import json
from decimal import Decimal

from .knowledge_content import decode_knowledge_content
from .knowledge_profile import KnowledgeProfileDeclaration, KnowledgeProfileRegistry, ObjectTypeDeclaration
from .knowledge_projection_contract import (
    ProjectionRevision, ProjectionComponent, ProjectionObject, ProjectionFact,
    ProjectionBatch, ProjectionPublication, definition_key,
)
from .semantic_binding_contract import RevisionRef, semantic_digest
from .typed_knowledge_meaning import TypedKnowledgeMeaning
from .knowledge_unresolved_scope import typed_unresolved_scopes


ADAPTER_REVISION = 'boi/native-knowledge-profile-projector@2'


def native_identity(record):
    return 'domain-asset-head:' + semantic_digest([record.payload['employee_id'],
                                                 record.payload['namespace'],record.payload['logical_id']])


class KnowledgeProfileProjector:
    def __init__(self, *, read_revision):
        if not callable(read_revision):
            raise ValueError('KNOWLEDGE_PROJECTOR_AUTHORIZED_READER_REQUIRED')
        self.read_revision=read_revision

    def materialize(self, manifest):
        return self.materialize_with_registry(manifest)[0]

    def materialize_with_registry(self, manifest):
        """Retain exact checked Profiles for typed DB preparation at ingestion."""
        manifest=ProjectionPublication.model_validate(manifest.model_dump(mode='json'))
        if manifest.adapter_revision!=ADAPTER_REVISION:
            raise ValueError('KNOWLEDGE_PROJECTOR_VERSION_MISMATCH')
        loaded,profiles={},{}
        def read(ref):
            ref=RevisionRef.model_validate(ref.model_dump(mode='json'))
            if ref not in loaded:
                record,asset=self.read_revision(ref)
                if (asset.revision!=ref or record.record_id!=ref.ref
                        or record.payload['employee_id']!=manifest.principal_id
                        or record.payload['policy_digest']!=manifest.policy_digest):
                    raise ValueError('KNOWLEDGE_PROJECTOR_NATIVE_BINDING_MISMATCH')
                loaded[ref]=(record,asset)
            return loaded[ref]
        documents=[]
        for change in manifest.changes:
            if change.operation=='delete':continue
            record,asset=read(change.revision)
            if change.stable_id!=native_identity(record):
                raise ValueError('KNOWLEDGE_PROJECTOR_IDENTITY_MISMATCH')
            content=decode_knowledge_content(json.loads(asset.content_json))
            if content is not None and content.meaning.get('contract_version')=='boi/typed-knowledge-meaning@1':
                for binding in content.profiles:
                    _,profile_asset=read(binding.revision)
                    if profile_asset.kind!='profile':
                        raise ValueError('KNOWLEDGE_PROJECTOR_PROFILE_KIND_REQUIRED')
                    profile=KnowledgeProfileDeclaration.model_validate_json(profile_asset.content_json)
                    if (profile.profile_id,profile.schema_ref)!=(binding.profile_id,binding.schema_ref):
                        raise ValueError('KNOWLEDGE_PROJECTOR_PROFILE_BINDING_MISMATCH')
                    if profile.level_scheme:
                        if (binding.level is None or (binding.level.scheme,binding.level.version)!=(
                                profile.level_scheme.scheme,profile.level_scheme.version)
                                or binding.level.value not in profile.level_scheme.values):
                            raise ValueError('KNOWLEDGE_PROJECTOR_DOMAIN_LEVEL_REQUIRED')
                    elif binding.level is not None:
                        raise ValueError('KNOWLEDGE_PROJECTOR_DOMAIN_LEVEL_UNDECLARED')
                    profiles[ProjectionRevision.model_validate(binding.revision.model_dump(mode='json'))]=profile
            documents.append((record,asset,content))
        registry=KnowledgeProfileRegistry(profiles) if profiles else None
        objects,predicates=[],{}
        for record,asset,content in documents:
            revision=ProjectionRevision.model_validate(asset.revision.model_dump(mode='json'))
            common={'stable_id':native_identity(record),'knowledge_revision':revision,'content_digest':asset.content_digest,
                    'adapter_revision':ADAPTER_REVISION,'title':record.payload['title'],
                    'source_record_locator':record.record_id+'#/sources'}
            raw=json.loads(asset.content_json)
            if asset.kind=='profile' and isinstance(raw,dict) and raw.get('contract_version')=='boi/knowledge-profile@1':
                profile=KnowledgeProfileDeclaration.model_validate(raw)
                # Profile declarations have their own paged component index.
                # Do not copy the entire schema into the searchable document
                # body or invent knowledge facts from schema definitions. The
                # exact native revision retains every declaration for reads.
                objects.append(ProjectionObject(**common,object_type=revision,
                    body=profile.label+'\n\n'+profile.description,readiness='unprepared',
                    unresolved=('profile_declaration_is_not_a_fact_population',),
                    metadata={'object_type_status':'profile_declaration','original_contract_preserved':True,
                        'body_representation':'profile_overview','component_count':len(profile.components),
                        'profile_id':profile.profile_id,'schema_ref':profile.schema_ref,
                        'complete_content_revision':revision.model_dump(mode='json')}))
                continue
            if content is None or content.meaning.get('contract_version')!='boi/typed-knowledge-meaning@1':
                objects.append(ProjectionObject(**common,object_type=revision,
                    body=content.document.body if content else asset.content_json,readiness='unprepared',
                    unresolved=('native_content_requires_registered_meaning_adapter',),
                    metadata={'object_type_status':'unclassified','original_contract_preserved':True}))
                continue
            meaning=TypedKnowledgeMeaning.model_validate(content.meaning)
            declared={ProjectionRevision.model_validate(p.revision.model_dump(mode='json')) for p in content.profiles}
            dependencies={d.revision.ref:d.revision for d in asset.dependencies if d.required}
            def require_profile(ref):
                if ref.revision not in declared or dependencies.get(ref.revision.ref)!=RevisionRef.model_validate(ref.revision.model_dump(mode='json')):
                    raise ValueError('KNOWLEDGE_PROJECTOR_PROFILE_DEPENDENCY_MISSING')
            def require_definitions(predicate):
                for ref in (predicate.subject_type,predicate.target_type,predicate.quantity_revision,predicate.unit_revision):
                    if ref is None:continue
                    if isinstance(ref,ProjectionComponent):require_profile(ref)
                    root=ref.revision if isinstance(ref,ProjectionComponent) else ref
                    if dependencies.get(root.ref)!=RevisionRef.model_validate(root.model_dump(mode='json')):
                        raise ValueError('KNOWLEDGE_PROJECTOR_DEFINITION_DEPENDENCY_MISSING')
            require_profile(meaning.object_type)
            registry.component(meaning.object_type,ObjectTypeDeclaration)
            checked=registry.validate_metadata(meaning.object_type,content.document.frontmatter)
            evidence={}
            for binding in content.evidence_bindings:
                evidence.setdefault(binding.meaning_pointer,[]).append(binding.model_dump(mode='json'))
            body_bindings={}
            for binding in content.body_bindings:
                body_bindings.setdefault(binding.meaning_pointer,[]).append(binding)
            unresolved_scopes=typed_unresolved_scopes(content)
            facts=[]; unresolved=[u.reason_code for u in unresolved_scopes.global_items]
            functional={}
            for index,assertion in enumerate(meaning.assertions):
                pointer=f'/assertions/{index}'
                if pointer not in evidence or pointer not in body_bindings:
                    raise ValueError('KNOWLEDGE_PROJECTOR_ASSERTION_BINDING_REQUIRED')
                if any(binding.assertion_kind!=assertion.assertion_kind for binding in body_bindings[pointer]):
                    raise ValueError('KNOWLEDGE_PROJECTOR_ASSERTION_KIND_MISMATCH')
                require_profile(assertion.predicate)
                declaration,predicate=registry.predicate(assertion.predicate)
                if predicate.subject_type!=meaning.object_type or predicate.value_kind!=assertion.value.kind:
                    raise ValueError('KNOWLEDGE_PROJECTOR_ASSERTION_TYPE_MISMATCH')
                require_definitions(predicate)
                predicates[predicate.revision]=predicate
                fact_unresolved=list(assertion.uncertainties)
                fact_unresolved.extend(unresolved_scopes.fact_markers(pointer))
                if declaration.quantity_semantics=='unknown':fact_unresolved.append('quantity_semantics_unknown')
                if declaration.value_semantics=='unknown':fact_unresolved.append('value_semantics_unknown')
                bindings=list(evidence[pointer])
                for group in ('conditions','exceptions','applicability'):
                    for ci,clause in enumerate(getattr(assertion,group)):
                        clause_pointer=f'{pointer}/{group}/{ci}'
                        if clause_pointer not in evidence:
                            raise ValueError('KNOWLEDGE_PROJECTOR_QUALIFIER_BINDING_REQUIRED')
                        bindings.extend(evidence[clause_pointer])
                        if clause.expression is None:
                            fact_unresolved.append('uncompiled_qualifier:'+clause_pointer)
                        for atom in clause.atoms:
                            require_profile(atom.predicate)
                            atom_declaration,atom_predicate=registry.predicate(atom.predicate)
                            require_definitions(atom_predicate)
                            if atom.operator not in atom_declaration.allowed_operators or atom.value.kind!=atom_predicate.value_kind:
                                raise ValueError('KNOWLEDGE_PROJECTOR_CONDITION_TYPE_MISMATCH')
                            if atom_declaration.quantity_semantics=='unknown' or atom_declaration.value_semantics=='unknown':
                                fact_unresolved.append('condition_quantity_semantics_unknown:'+clause_pointer)
                            predicates[atom_predicate.revision]=atom_predicate
                if assertion.valid_time.state=='unknown':
                    fact_unresolved.append('valid_time_unknown')
                elif pointer+'/valid_time' not in evidence:
                    raise ValueError('KNOWLEDGE_PROJECTOR_VALID_TIME_BINDING_REQUIRED')
                else:bindings.extend(evidence[pointer+'/valid_time'])
                qualifiers={'contract_version':'boi/typed-assertion-qualifiers@1',
                    'statement':assertion.statement,'assertion_kind':assertion.assertion_kind,
                    'conditions':[c.model_dump(mode='json') for c in assertion.conditions],
                    'exceptions':[c.model_dump(mode='json') for c in assertion.exceptions],
                    'applicability':[c.model_dump(mode='json') for c in assertion.applicability],
                    'depends_on':list(assertion.depends_on),'role':declaration.role,
                    'value_semantics':declaration.value_semantics}
                if declaration.cardinality=='one' and assertion.polarity=='positive' and assertion.modality=='asserted':
                    scope=semantic_digest([definition_key(assertion.predicate),qualifiers['conditions'],qualifiers['exceptions'],
                        qualifiers['applicability'],assertion.valid_time.model_dump(mode='json')])
                    value=assertion.value
                    functional.setdefault(scope,set()).add((value.kind,Decimal(value.value) if value.kind=='decimal' else value.value))
                facts.append(ProjectionFact(fact_id=assertion.id,meaning_pointer=pointer,predicate_revision=predicate.revision,
                    value=assertion.value,polarity=assertion.polarity,modality=assertion.modality,qualifiers=qualifiers,
                    valid_time=assertion.valid_time.model_dump(mode='json'),evidence_bindings=bindings,
                    unresolved=tuple(dict.fromkeys(fact_unresolved))))
            if any(len(values)>1 for values in functional.values()):unresolved.append('single_cardinality_has_competing_values')
            objects.append(ProjectionObject(**common,object_type=meaning.object_type,body=content.document.body,
                readiness='source_bound',facts=facts,unresolved=tuple(dict.fromkeys(unresolved)),
                metadata={'frontmatter':content.document.frontmatter,'profiles':[p.model_dump(mode='json') for p in content.profiles],
                    **({'declared_unresolved':[u.model_dump(mode='json') for u in content.unresolved]} if content.unresolved else {}),
                    'metadata_pointers_checked':list(checked),'native_recorded_time':record.occurred_at,
                    'source_fidelity_qualified':False,'semantic_truth_proven':False,'use_qualification':'required_before_qualified_query'}))
        result=ProjectionBatch(manifest_digest=manifest.digest,objects=objects,predicates=tuple(predicates.values()))
        result.validate_manifest(manifest)
        return result, registry
