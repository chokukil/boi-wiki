"""Add executable business predicates without rewriting source descriptions.

This authors a new Profile candidate, not assertions or qualifications. A source
review must bind every new value/reference; names never establish identity.
"""
from copy import deepcopy
from boi_api.app.governed_runtime.knowledge_profile import KnowledgeProfileDeclaration


def extend_business_profile(base, *, domain, quantities=()):
    profile=deepcopy(base)
    original=KnowledgeProfileDeclaration.model_validate(profile)
    types=[c for c in original.components if c.kind=='object_type']
    if len(types)!=1 or domain not in ('process','svid'):
        raise ValueError('ONE_SOURCE_OBJECT_TYPE_AND_DOMAIN_REQUIRED')
    subject=types[0].id
    additions=[]

    def object_type(name,label,description):
        additions.append(dict(kind='object_type',id=name,label=label,description=description,metadata_constraints=[]))

    def predicate(name,label,role,kind='text',target=None,description=None,subject_type=None):
        value=dict(kind='predicate',id=name,label=label,
            description=description or label+'; 원문 근거와 적용 범위를 각 주장에 결속한다. 이름 일치로 동일성을 추론하지 않는다.',
            subject_type={'component_id':subject_type or subject},value_kind=kind,
            target_type={'component_id':target} if target else None,role=role,
            quantity_semantics='not_applicable',value_semantics='not_applicable',
            cardinality='many',allowed_operators=['eq','ne'])
        additions.append(value)
        return value

    object_type('business_concept','원문에서 구분한 업무 개념',
        '원문 근거와 범위로 식별하는 방법·목적·대상·물리량 개념. 단어만 같은 개념은 병합하지 않는다.')
    object_type('equipment_component','원문에서 구분한 장비 구성요소',
        '장비·모듈·부품의 원문상 대상. 복원된 경로만으로 실물 동일성을 확정하지 않는다.')
    predicate('semantic_alias','범위가 결속된 별칭','scoped_alias',description=
        '명시된 동의 표현만 원문 근거·대상·조건과 함께 보존한다. 발견용이며 동일성이나 Formula 자격을 부여하지 않는다.')
    predicate('semantic_target','업무 대상','target','object','business_concept')
    predicate('semantic_component','장비·모듈·부품 대상','equipment_scope','object','equipment_component')
    predicate('component_source_scope','원문에서 구분한 구성요소 범위','source_scope',
        subject_type='equipment_component',description=
        '장비 모델·모듈·채널·물질 등 원문이 함께 구분한 source-local 범위. '
        '표시 이름이나 복원 경로만으로 설치 장비·센서·actuator의 물리 동일성을 확정하지 않는다.')
    if domain=='process':
        predicate('semantic_method','공정 방법','method','object','business_concept')
        predicate('semantic_material','처리 물질·막질','material','object','business_concept')
        predicate('semantic_purpose','공정 목적','purpose','object','business_concept')
        predicate('semantic_precedes','원문에 명시된 후속 공정','precedes','object',subject,description=
            '주체 공정이 참조 공정에 선행한다고 원문이 명시한 관계. 바로 다음·원인 관계를 뜻하지 않는다. 조건과 방향을 보존한다.')
    else:
        predicate('semantic_quantity','측정·제어 물리량','quantity','object','business_concept')
        predicate('semantic_signal_role','원문에서 확인한 값 역할','signal_role',description=
            'reading, setpoint, lower_limit, upper_limit, state, derived 중 원문이 뒷받침하는 역할. 이름 접미사만으로 선택하지 않는다. 모호함은 unresolved에 남긴다.')
        predicate('semantic_related_parameter','같은 범위의 관련 파라미터','parameter_relation','object',subject,description=
            'reading과 setpoint 등 원문이 연결한 파라미터 관계. 정확한 대상 identity와 관계 조건을 주장에 결속한다.')
    for quantity in quantities:
        # Quantity-specific fields must bind actual approved definitions. Never
        # supply fabricated pressure/unit revisions or assume a cell is a value.
        if not {'id','label','role','quantity_revision','unit_revision'} <= quantity.keys():
            raise ValueError('EXACT_QUANTITY_AND_UNIT_DEFINITIONS_REQUIRED')
        p=predicate(quantity['id'],quantity['label'],quantity['role'],'decimal')
        p.update(quantity_semantics='declared',quantity_revision=quantity['quantity_revision'],
            unit_revision=quantity['unit_revision'],value_semantics='absolute',
            allowed_operators=['eq','ne','lt','lte','gt','gte'])
    profile['schema_ref']=original.profile_id+'@2'
    profile['label']=original.label+' — 업무 의미'
    profile['description'] += ' 기존 원문 주장과 작성자 메모를 보존하고, 조회할 업무 대상과 관계를 정확한 참조로 추가한다. 선언만으로 값·관계·사용 자격은 생기지 않는다.'
    profile['components']+=additions
    return KnowledgeProfileDeclaration.model_validate(profile).model_dump(mode='json',exclude_none=True)
