"""Source-only operational review and bounded process-node repair.

These checks verify quoted evidence, scope, references and review coverage.
Entailment and omitted meaning remain review-model judgments, never truth gates.
No evaluation oracle is accepted by any function in this module.
"""
import copy
import json
from collections import Counter
from dataclasses import dataclass
from typing import Annotated,Literal

from pydantic import Field,model_validator

from agent_kit.python.boi_process_fidelity import assessment_targets,check_assessment
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessTerm,ProcessAssertion,ProcessQuotation,ProcessKnowledgeDraft
from boi_api.app.governed_runtime.process_reuse_scope_contract import ProcessDefinitionUseV2,ProcessReuseProposalV2
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract,Ref,Digest,semantic_digest


SOURCE_REVIEW_INSTRUCTIONS_VERSION='boi/process-source-review-instructions@9'
SOURCE_LABEL_FAILURE_KINDS={'supported':('none',),'contradicted':('source_conflict','representation_mismatch'),
    'unsupported':('unsupported_addition','scope_expansion','representation_mismatch','insufficient_evidence')}


SOURCE_REVIEW_INSTRUCTIONS = {'boi/process-source-review-instructions@3': ('Review source fidelity using only the complete original fields, read definitions/contracts and candidate. '
        'There are no answer keys or external facts. Review each selected target exactly once. Read labels, definitions, '
        'categories, assertion subjects/objects, polarity/modality, conditions/exceptions/applicability and dependencies '
        'together. Correct prose does not excuse incompatible structured meaning. If declared_category_contract is present, '
        'use that exact profile for this candidate; a historical definition retains its own earlier contract. Without a '
        'declared boundary, do not invent a strict taxonomy to reject a reasonable classification. '
        'Normal paraphrase, translation and source-supported classification need not repeat category labels verbatim. '
        'An unestablished addition or widened condition/scope is unsupported; a fact incompatible with the source is '
        'contradicted. Explain a representation mismatch when the structured category, subject or condition conflicts with '
        'what the node claims. Keep failure_kind within review_output_contract.allowed_failure_kinds for its label; '
        'these are existing output-shape rules, not expected judgments. A document provenance fact is not a process property. '
        'Machine provenance and revision/reference digests are not propositions that must appear in source prose. '
        'This review does not determine scientific truth of the original source. '
        'Assess only field_locators_to_assess as represented/partial/omitted/non_domain_context. For field coverage use '
        'ALL current nodes and carried_node_judgments, including nodes outside selected review targets. A node excluded '
        'from re-review is not an omitted extraction. represented must reference supported nodes; copying a quote is not '
        'semantic coverage. Explain missing substantive meaning for partial/omitted fields. Quote exact original fields, '
        'preserve review limitations, and explain reasons in Korean.\n')}
SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@4']=(
    SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@3'][:-1]+
    ' For field coverage, also read the candidate limitations. Source statements about the document itself '
    'may already be retained there and may be non_domain_context without a process assertion. Do not label '
    'them omitted solely because no process node is appropriate. This never permits classifying an actual '
    'process condition, exception, scope or substantive definition as non-domain context. Source-reported '
    'document character remains unverified source information, separate from Wiki-owned provenance and authority.\n')
SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@5']=(
    SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@4'][:-1]+
    ' For a non_domain_context field, target_pointers may include an existing draft-relative /limitations/N '
    'location retaining document information. Those locations cannot support represented process meaning. '
    'Do not hide substantive conditions or scope under a document-context classification.\n')
SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@6']=(
    SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@5'][:-1]+
    ' A target value_reference points into the complete draft in this same input. Read that exact node; '
    'the pointer replaces only a duplicated value, never the meaning or selected review scope.\n')

SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@7']=(
    SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@6'][:-1]+
    ' Source quotations establish origin, not complete representation of their meaning. For source-reported '
    'causes, mechanisms and constraints, distinguish the outcome or difficulty from the reason explaining it. '
    'Check whether that reason is expressed by statement/subject/object and linked assertions, and whether '
    'conditions, exceptions and applicability retain their explicit source scope. If required meaning exists '
    'only inside a quotation, field coverage is partial; do not require one node to repeat meaning represented '
    'in another linked node. Keep supported but incomplete statements distinct from contradictions or changed '
    'typed scope. Use semantic equivalence rather than literal-word matching.\n')


SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@8']=(
    SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@7'][:-1]+
    ' A read_projection_reference points to the identical earlier asset projection in this input. '
    'Read that full value with the current asset revision and authority; only duplicate bytes are replaced.\n')

SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@9']=(
    SOURCE_REVIEW_INSTRUCTIONS['boi/process-source-review-instructions@8'][:-1]+
    ' Historical execution procedures and prior review diagnostics remain in their exact stored revisions. '
    'Use the selected current skill and full source/definition/profile values here. '
    'Any carried node judgments are explicit in carried_node_judgments; operational history is not source evidence.\n')


def source_review_history_delivery(material):
    """Keep current semantics, link only identifiable historical procedures/reviews."""
    result=source_review_contract_delivery(material,expand=True);context=result['read_definitions_and_contracts']
    roots=[s['requirement']['revision'] for s in context['selections']
        if s['parent'] is None and s['status']=='selected' and s['requirement']['role']=='harness']
    current_skills=[s['requirement']['revision'] for s in context['selections']
        if s['parent'] in roots and s['status']=='selected' and s['requirement']['role']=='skill']
    for asset in context['assets']:
        value=asset['read_projection']
        if 'historical_revision_reference' in value:continue
        historical_skill=bool(current_skills) and asset['kind']=='skill' and asset['revision'] not in current_skills
        historical_review=(asset['kind']=='pack' and value.get('history_preserved_in_exact_wiki_revision') is True
            and 'operative_review_check' in value and 'omitted_from_current_review' in value)
        if historical_skill or historical_review:
            asset['read_projection']={'historical_revision_reference':asset['revision'],
                'historical_projection_digest':asset['projection_digest'],
                'scope':'Prior execution procedure' if historical_skill else 'Prior review diagnostics; carried node judgments remain explicit outside this history.'}
            asset['projection_digest']=semantic_digest(asset['read_projection'])
    return result


def source_review_contract_delivery(material, *, expand=False):
    result=copy.deepcopy(material)
    assets=result.get('read_definitions_and_contracts',{}).get('assets',[])
    seen={}
    for index,asset in enumerate(assets):
        if 'read_projection_reference' in asset:
            ref=asset['read_projection_reference']
            matches=[j for j in range(index) if ref==f'/read_definitions_and_contracts/assets/{j}/read_projection']
            if len(matches)!=1 or 'read_projection' in asset:raise ValueError('SOURCE_REVIEW_CONTRACT_REFERENCE_INVALID')
            value=assets[matches[0]].get('read_projection')
            if value is None or semantic_digest(value)!=asset['projection_digest']:
                raise ValueError('SOURCE_REVIEW_CONTRACT_DIGEST_MISMATCH')
            if expand:
                asset.pop('read_projection_reference');asset['read_projection']=copy.deepcopy(value)
        else:
            value=asset['read_projection'];digest=semantic_digest(value)
            if digest!=asset['projection_digest']:raise ValueError('SOURCE_REVIEW_CONTRACT_DIGEST_MISMATCH')
            if not expand and digest in seen:
                previous=seen[digest]
                if assets[previous]['read_projection']!=value:raise ValueError('SOURCE_REVIEW_CONTRACT_DIGEST_COLLISION')
                asset.pop('read_projection');asset['read_projection_reference']=f'/read_definitions_and_contracts/assets/{previous}/read_projection'
            else:seen.setdefault(digest,index)
    return result


def source_review_delivery(material, *, expand=False):
    """Lossless @6 presentation: selected/full target values occur once in draft."""
    result=copy.deepcopy(material)
    for key in ('targets','all_current_nodes_for_field_coverage'):
        for target in result.get(key,[]):
            pointer=target['target_pointer'];value=result['draft']
            try:
                for part in pointer.lstrip('/').split('/'):
                    part=part.replace('~1','/').replace('~0','~')
                    value=value[int(part)] if isinstance(value,list) else value[part]
            except (KeyError,IndexError,TypeError,ValueError):
                raise ValueError('SOURCE_REVIEW_PRESENTATION_TARGET_MISSING') from None
            reference='/draft'+pointer
            if 'value' in target:
                if 'value_reference' in target or target['value']!=value:
                    raise ValueError('SOURCE_REVIEW_PRESENTATION_VALUE_MISMATCH')
                if not expand:
                    target.pop('value');target['value_reference']=reference
            else:
                if target.get('value_reference')!=reference:
                    raise ValueError('SOURCE_REVIEW_PRESENTATION_REFERENCE_MISMATCH')
                if expand:
                    target.pop('value_reference');target['value']=copy.deepcopy(value)
    return result

def source_review_prompt(material, *, version=SOURCE_REVIEW_INSTRUCTIONS_VERSION):
    try:instructions=SOURCE_REVIEW_INSTRUCTIONS[version]
    except KeyError:raise ValueError('PROCESS_SOURCE_REVIEW_CONTRACT_UNSUPPORTED') from None
    # @3 retains its exact historical prompt bytes. @4 removes JSON separator
    # whitespace only, keeping every source/condition/definition value intact.
    if version in ('boi/process-source-review-instructions@6','boi/process-source-review-instructions@7','boi/process-source-review-instructions@8','boi/process-source-review-instructions@9'):material=source_review_delivery(material)
    if version=='boi/process-source-review-instructions@9':material=source_review_history_delivery(material)
    if version in ('boi/process-source-review-instructions@8','boi/process-source-review-instructions@9'):material=source_review_contract_delivery(material)
    separators=(',',':') if version!='boi/process-source-review-instructions@3' else None
    return instructions+json.dumps(material,ensure_ascii=False,separators=separators)


def definition_reuse_review_prompt(material):
    """Preserve the established source-only reuse review instructions exactly."""
    return ('원문과 Wiki에서 읽은 정의/적용 범위 및 저장할 후보만으로 정의 재사용을 검토하라. '
        '평가용 정답이나 외부 지식은 없다. 모든 use의 관계/적용, meaning, applicability, conditions, exceptions를 '
        '각각 한 번 평가하고 원문을 인용하라. applies 선택과 not_applicable 제외의 적절성을 모두 검토하라. '
        '비교 대상은 referenced term/definition node의 뜻이다. not_applicable은 그 조건이 해당 용어의 뜻을 '
        '제한하지 않는다는 뜻이며, 전체 local_record/definition_record에서 행위 조건을 삭제한 것이 아니다. '
        '정의가 같은 용어를 다른 공정/관찰 맥락에서 사용할 수 있다. 단지 행위 맥락이 다르다는 이유로 용어 '
        '동등성을 거절하지 말고, 원문이 용어의 뜻에 직접 붙인 조건을 놓치거나 행위 조건을 전역 용어 조건으로 '
        '확대한 경우를 구분하라. '
        'supported는 검토 모델의 원문상 지지 판단일 뿐 과학/전문가 검증이 아니다. source conflict, '
        'unestablished addition, scope expansion과 단순 불확실성을 이유에서 구분하라. '
        '원문 자체의 과학적 오류는 이 자료만으로 판정하지 마라. 한글 이유와 source_revision/field/quote를 제공하라. '
        '출력 토큰 상한에 도달하면 응답이 잘려 무효가 되므로 내부 추론을 최소한으로 압축하고, '
        '요구된 단일 JSON 객체를 빠짐없이 끝까지 출력하라. '
        '도구 없이 typed assessment만 반환하라.\n'+json.dumps(reuse_review_view(material),ensure_ascii=False))


class SourceNodeJudgment(FrozenContract):
    target_pointer:Ref
    label:Literal['supported','contradicted','unsupported']
    failure_kind:Literal['none','source_conflict','unsupported_addition','scope_expansion','representation_mismatch','insufficient_evidence']
    reason:Ref
    evidence:tuple[ProcessQuotation,...]=Field(min_length=1)

    @model_validator(mode='after')
    def consistent_kind(self):
        allowed=SOURCE_LABEL_FAILURE_KINDS
        if self.failure_kind not in allowed[self.label]:raise ValueError('PROCESS_REVIEW_FAILURE_KIND_MISMATCH')
        return self


class SourceFieldCoverage(FrozenContract):
    field_locator:str
    status:Literal['represented','partial','omitted','non_domain_context']
    target_pointers:tuple[Ref,...]=Field(default=(), description='Nodes in the COMPLETE current candidate, including unchanged nodes whose judgments are carried forward; not limited to nodes selected for re-review.')
    reason:Ref
    missing_meaning:str|None=None


class ProcessSourceReview(FrozenContract):
    contract_version:Literal['boi/process-operational-source-review@1']='boi/process-operational-source-review@1'
    claims:tuple[SourceNodeJudgment,...]
    fields:tuple[SourceFieldCoverage,...]
    limitations:tuple[Ref,...]=Field(min_length=1)


def process_context_view(context, *, source_readings=None):
    """Full typed meaning and contracts, without repeated cached graph copies.

    This is explicitly a presentation of already-read assets, not another
    TaskKnowledgeContext with a falsely retained content digest.

    Optional source readings must come from the authorized Wiki read path. The
    presentation keeps those complete readings once, replacing a source asset's
    body only when its exact UTF-8 bytes identify one of those immutable sources.
    This checks the delivered source/ACL closure, not current server authority,
    comprehension, or completeness of namespace definition reading.
    """
    readings=None;source_references={}
    if source_readings is not None:
        from .boi_process_answer_v2 import validate_source_readings
        from boi_api.app.governed_runtime.source_envelope import byte_digest
        from boi_api.app.governed_runtime.source_field_projection import SourceFieldProjectionService
        readings=copy.deepcopy(list(source_readings))
        indexed=validate_source_readings(context,readings)
        for index,reading in enumerate(readings):
            source=reading['source'];manifest=reading['manifest']
            selected=(manifest.get('contract_version')=='boi/source-field-selection@1'
                and manifest.get('projection_scope')=='selected_source_fields'
                and manifest.get('source_revision_digest')==source['digest'])
            # Published definitions receive their source fields from the
            # published reader, not the ordinary artifact projector. Admit
            # that manifest only when every declared definition revision is
            # already present in this acknowledged context; validate_source_readings
            # above has independently checked each complete field and byte digest.
            published=(manifest.get('contract_version')=='boi/published-original-selection@1'
                and manifest.get('projection_scope')=='selected_published_evidence_fields'
                and manifest.get('source_revision_digest')==source['digest']
                and isinstance(manifest.get('definition_revisions'),list)
                and bool(manifest['definition_revisions'])
                and all(ref in [asset['revision'] for asset in context['assets']]
                        for ref in manifest['definition_revisions']))
            if not selected and not published and (manifest.get('contract_version'),manifest.get('artifact_ref'),
                manifest.get('snapshot_digest'),manifest.get('source_role')) != (
                    SourceFieldProjectionService.CONTRACT,source['artifact_ref'],source['digest'],source['role']):
                raise ValueError('PROCESS_SOURCE_PRESENTATION_MANIFEST_MISMATCH')
            source_references[source['digest']]={
                'content_referenced':True,'source_reading_reference':f'/source_readings/{index}',
                'source_revision_digest':source['digest'],
                'source_reading_digest':indexed[source['digest']]['reading_digest']}
    assets=[]
    for asset in context['assets']:
        content=json.loads(asset['content_json'])
        if asset['kind']=='definition' and content.get('contract_version') in ('boi/bound-process-meaning@1','boi/bound-process-meaning@2'):
            view={'draft':content['draft'],'definition_uses':[
                {k:v for k,v in use.items() if k in ProcessDefinitionUseV2.model_fields or k=='scope_comparisons'}
                for use in content.get('definition_uses',[])]}
            # The complete typed draft includes its original quotations and
            # conditions; reference digests still point to the original asset.
        else:
            view=content
            if readings is not None and asset['kind']=='source':
                reference=source_references.get(byte_digest(asset['content_json'].encode('utf-8')))
                if reference is not None:view=copy.deepcopy(reference)
        assets.append({'revision':asset['revision'],'kind':asset['kind'],'authority':asset['authority'],
            'dependencies':asset['dependencies'],'original_content_digest':asset['content_digest'],
            'read_projection':view,'projection_digest':semantic_digest(view)})
    result={'contract_version':'boi/process-read-presentation@1','context_digest':context['context_digest'],
        'assets':assets,'selections':context['selections'],
        'source_manifest_digest':context['source_manifest_digest'],
        'meaning_omitted':False,'cached_binding_copies_omitted':True,'authority_created':False}
    if readings is not None:
        result.update(contract_version='boi/process-read-presentation@2',source_readings=readings)
    return result


def reuse_review_view(material):
    targets=[]
    for target in material['targets']:
        use=target['proposed_use']
        targets.append({**target,'proposed_use':{k:v for k,v in use.items()
            if k in ProcessDefinitionUseV2.model_fields or k=='scope_comparisons'}})
    return {k:material[k] for k in ('sources','proposal_digest','bound_digest','read_scope')}|{'targets':targets,
        'scope_subject':'Meaning of the referenced local term and definition node. not_applicable means the facet '
            'does not constrain that node meaning; it never deletes that facet from the complete local/definition record. '
            'The full records preserve operation context separately. Do not demand equal operation contexts for equal term definitions.'}


def source_review_material(draft,evidence,context):
    from .boi_process_categories import read_category_contract
    from .boi_process_response_review import response_context_view
    graph=ProcessKnowledgeDraft.model_validate(draft).model_dump(mode='json')
    provenance={k:graph.pop(k) for k in ('contract_version','source_revision_digest','extraction_context_digest','definition_revisions_used')}
    links=[]
    for ri,record in enumerate(graph['records']):
        for ti,term in enumerate(record['terms']):
            links.append({'target_pointer':f'/records/{ri}/terms/{ti}','reused_definition':term.pop('reused_definition')})
    provenance['term_definition_links']=links
    targets=copy.deepcopy(assessment_targets(draft,include_all_terms=True))
    for target in targets:target['value'].pop('reused_definition',None)
    return {'review_instructions_version':SOURCE_REVIEW_INSTRUCTIONS_VERSION,
        'review_output_contract':{'allowed_failure_kinds':SOURCE_LABEL_FAILURE_KINDS},'draft':graph,'targets':targets,
        'machine_provenance':provenance,
        'original_fields':evidence['fields'],'read_definitions_and_contracts':response_context_view(context),
        'declared_category_contract':read_category_contract(context),
        'primary_source_revision':evidence['source']['digest'],
        'scope':'Source fidelity only. Original-source scientific errors require separate scientific evidence.'}


def source_review_selection(draft,evidence,*,previous_draft=None,previous_review=None):
    targets=assessment_targets(draft,include_all_terms=True)
    fields=[f['field_locator'] for f in evidence['fields']]
    if previous_review is None:return {'targets':targets,'fields':fields,'carry_forward_nodes':[],'carry_forward_fields':[]}
    prior={t['target_pointer']:t for t in assessment_targets(previous_draft,include_all_terms=True)}
    current={t['target_pointer']:t for t in targets}
    changed={p for p,t in current.items() if p not in prior or semantic_digest(t)!=semantic_digest(prior[p])}
    changed.update(c['target_pointer'] for c in previous_review['claims'] if c['label']!='supported')
    # Applicability assertions participate in the whole record's meaning
    # closure. Their removal/change must not be missed because the old node no
    # longer appears among current targets. Unrelated records remain eligible
    # for exact historical carry-forward.
    old_records={r['process_ref']:r for r in previous_draft['records']}
    for ri,record in enumerate(draft['records']):
        old=old_records.get(record['process_ref'])
        scope=lambda r:[a for a in r['assertions'] if a['category']=='applicability']
        if old is not None and scope(old)!=scope(record):
            changed.update(p for p in current if p.startswith(f'/records/{ri}/'))
    affected=set(dependent_nodes(draft,changed))
    selected_fields={f['field_locator'] for f in previous_review['fields']
        if f['status'] in ('partial','omitted') or set(f['target_pointers'])&affected}
    for t in targets:
        if t['target_pointer'] in affected:
            node=t['value'];selected_fields.update(q['field_locator'] for q in node['evidence'])
            for key in ('conditions','exceptions','applicability'):
                selected_fields.update(q['field_locator'] for facet in node.get(key,[]) for q in facet['evidence'])
    return {'targets':[t for t in targets if t['target_pointer'] in affected],
        'fields':[f for f in fields if f in selected_fields],
        'carry_forward_nodes':[p for p in current if p not in affected],
        'carry_forward_fields':[f for f in fields if f not in selected_fields]}


def merge_source_review(review,*,selection,previous_review=None):
    review=ProcessSourceReview.model_validate(review).model_dump(mode='json')
    def exact(actual,expected,code):
        if len(actual)!=len(set(actual)) or set(actual)!=set(expected):raise ValueError('PROCESS_REVIEW_'+code)
    exact([c['target_pointer'] for c in review['claims']],[t['target_pointer'] for t in selection['targets']],'SELECTED_NODE_SET_MISMATCH')
    exact([f['field_locator'] for f in review['fields']],selection['fields'],'SELECTED_FIELD_SET_MISMATCH')
    if previous_review:
        review['claims'] += [c for c in previous_review['claims'] if c['target_pointer'] in selection['carry_forward_nodes']]
        review['fields'] += [f for f in previous_review['fields'] if f['field_locator'] in selection['carry_forward_fields']]
    return review


def coverage_pointers(draft,claims,field,reference_contract_version):
    if reference_contract_version not in ('boi/source-coverage-references@1','boi/source-coverage-references@2'):
        raise ValueError('PROCESS_REVIEW_REFERENCE_CONTRACT_UNSUPPORTED')
    allowed=set(claims)
    if reference_contract_version=='boi/source-coverage-references@2' and field.status=='non_domain_context':
        allowed.update(f'/limitations/{i}' for i,_ in enumerate(draft.get('limitations',[])))
    return allowed


def check_source_review(assessment,*,draft,evidence,reference_contract_version='boi/source-coverage-references@1'):
    review=ProcessSourceReview.model_validate(assessment)
    value=review.model_dump(mode='json')
    legacy={'claims':[{k:v for k,v in c.items() if k!='failure_kind'} for c in value['claims']],
        'propositions':[],'contrasts':[],'limitations':value['limitations']}
    checked=check_assessment(legacy,draft=draft,evidence=evidence,
        oracle={'contract_version':'boi/process-sample-oracle@2','records':[]})
    claims={c.target_pointer:c for c in review.claims}
    fields={f['field_locator']:f for f in evidence['fields']}
    actual=[f.field_locator for f in review.fields]
    if len(actual)!=len(set(actual)) or set(actual)!=set(fields):raise ValueError('PROCESS_REVIEW_FIELD_COVERAGE_INCOMPLETE')
    failures=[{'target_pointer':c.target_pointer,'failure_kind':c.failure_kind,'reason':c.reason,
        'evidence':[q.model_dump(mode='json') for q in c.evidence]} for c in review.claims if c.label!='supported']
    for field in review.fields:
        if not set(field.target_pointers)<=coverage_pointers(draft,claims,field,reference_contract_version):raise ValueError('PROCESS_REVIEW_UNKNOWN_COVERAGE_NODE')
        if field.status=='represented' and (not field.target_pointers or any(claims[p].label!='supported' for p in field.target_pointers)):
            failures.append({'target_pointer':'field:'+field.field_locator,'failure_kind':'review_inconsistent',
                'reason':'Field coverage cites no supported node or also cites an unsupported node. '+field.reason,
                'field_locator':field.field_locator,'evidence':[]})
        elif field.status in ('partial','omitted'):
            if not field.missing_meaning:raise ValueError('PROCESS_REVIEW_OMISSION_REASON_REQUIRED')
            failures.append({'target_pointer':'field:'+field.field_locator,'failure_kind':'omission','reason':field.missing_meaning,
                'field_locator':field.field_locator,'evidence':[]})
    failed=[f['target_pointer'] for f in failures if not f['target_pointer'].startswith('field:')]
    return {'contract_version':'boi/process-source-review-check@1','assessment_complete':True,
        'reference_contract_version':reference_contract_version,
        'claim_counts':checked['claim_counts'],'field_counts':dict(Counter(f.status for f in review.fields)),
        'failures':failures,'failed_claim_pointers':failed,'quarantined_node_pointers':dependent_nodes(draft,failed),
        'model_assessment_accepts_source_fidelity':not failures,'deterministic_entailment_proven':False,
        'scientific_correctness':'not_evaluated','whole_plan_qualified':False}


def dependent_nodes(draft,changed):
    """Exact typed references only; no keyword/semantic matching."""
    draft=ProcessKnowledgeDraft.model_validate(draft).model_dump(mode='json')
    affected=set(changed)
    for ri,record in enumerate(draft['records']):
        refs={t['term_id']:f'/records/{ri}/terms/{i}' for i,t in enumerate(record['terms'])}
        refs.update({a['assertion_id']:f'/records/{ri}/assertions/{i}' for i,a in enumerate(record['assertions'])})
        again=True
        while again:
            again=False
            for i,a in enumerate(record['assertions']):
                pointer=f'/records/{ri}/assertions/{i}'
                parents=[refs[x] for x in (a['subject_ref'],*a['object_refs'],*a['depends_on'])]
                if pointer not in affected and affected.intersection(parents):affected.add(pointer);again=True
    return sorted(affected)


@dataclass(frozen=True)
class AnswerReviewDependencies:
    """Request-local review scope, built from authoritative candidate inputs."""
    asset_revision:dict
    scope_known:bool
    blocked:frozenset[str]
    allowed:frozenset[str]|None=None


def prepare_answer_review_dependencies(*,asset_revision,asset_content,review_check):
    """Compute candidate scope once; reuse it for each resolved citation closure."""
    source=review_check.get('source_review')
    scope_known=(review_check.get('candidate_revision')==asset_revision and isinstance(source,dict)
        and isinstance(source.get('quarantined_node_pointers'),list)
        and isinstance(source.get('failures'),list)
        and (source.get('assessment_complete') is True or
            isinstance(source.get('usable_node_pointers'),list)))
    all_nodes={t['target_pointer'] for t in assessment_targets(asset_content['draft'],include_all_terms=True)} if 'draft' in asset_content else set()
    blocked=set(source.get('quarantined_node_pointers',[])) if scope_known else set(all_nodes)
    if scope_known and source.get('assessment_complete') is not True:
        blocked.update(all_nodes-set(source['usable_node_pointers']))
    failed_uses=set(review_check.get('failed_use_pointers',[]))
    blocked.update(u['term_pointer'] for i,u in enumerate(asset_content.get('definition_uses',[]))
        if f'/definition_uses/{i}' in failed_uses and u['application']=='interpret_term')
    allowed=(frozenset(source['usable_node_pointers']) if scope_known
        and source.get('assessment_complete') is not True else None)
    return AnswerReviewDependencies(copy.deepcopy(asset_revision),scope_known,frozenset(blocked),allowed)


def check_prepared_answer_review_dependencies(answer,dependencies):
    """Check actual body/request-plan closures against a prepared review scope."""
    from .boi_process_answer_v2 import answer_evidence_groups
    asset_revision=dependencies.asset_revision
    scope_known=dependencies.scope_known
    blocked=dependencies.blocked
    violations=[]
    for ai,item in enumerate(answer['answers']):
        for location,statements in answer_evidence_groups(item):
            for si,statement in enumerate(statements):
                for citation in statement['citations']:
                    if citation['kind']!='meaning':continue
                    hit=[node['target_pointer'] for node in citation['graph_evidence']
                        if node.get('asset_revision',citation['asset_revision'])==asset_revision and
                        (node['target_pointer'] in blocked or
                         (dependencies.allowed is not None and node['target_pointer'] not in dependencies.allowed))]
                    if hit or not scope_known:violations.append({'target_pointer':f'/answers/{ai}/{location}/{si}','quarantined_nodes':sorted(set(hit)),
                        'review_scope_link':'confirmed' if scope_known else 'unconfirmed'})
    if violations:raise ValueError('PROCESS_ANSWER_QUARANTINED_DEPENDENCY:'+json.dumps(violations,ensure_ascii=False))
    return {'status':'pass' if scope_known else 'source_only_review_link_unconfirmed',
        'review_scope_link':'candidate_revision_and_declared_node_scope' if scope_known else 'unconfirmed',
        'quarantined_node_count':len(blocked),'semantic_support_proven':False,
        'review_execution_binding':'not_checked_by_this_function'}


def check_answer_review_dependencies(answer,*,asset_revision,asset_content,review_check):
    """Block quarantined meanings while preserving direct original quotations."""
    return check_prepared_answer_review_dependencies(answer,prepare_answer_review_dependencies(
        asset_revision=asset_revision,asset_content=asset_content,review_check=review_check))


class TermReplacement(FrozenContract):
    kind:Literal['term']='term'
    target_pointer:Ref
    replacement:ProcessTerm


class AssertionReplacement(FrozenContract):
    kind:Literal['assertion']='assertion'
    target_pointer:Ref
    replacement:ProcessAssertion


class RecordAddition(FrozenContract):
    record_pointer:Ref
    terms:tuple[ProcessTerm,...]=()
    assertions:tuple[ProcessAssertion,...]=()


class UseReplacement(FrozenContract):
    use_pointer:Ref
    replacement:ProcessDefinitionUseV2


class UnresolvedRepair(FrozenContract):
    target_pointer:Ref
    reason:Ref
    needed_evidence:Ref


class AssertionRetraction(FrozenContract):
    target_pointer:Ref
    reason:Ref
    evidence:tuple[ProcessQuotation,...]=Field(min_length=1)
    retained_locations:tuple[Ref,...]=Field(default=(),description='Pointers in the original draft where source information is already retained outside this assertion. They must remain unchanged. Retraction does not validate their meaning or confer Wiki authority.')


class ProcessIntakeRepair(FrozenContract):
    context_digest:Digest
    base_proposal_digest:Digest
    nodes:tuple[Annotated[TermReplacement|AssertionReplacement,Field(discriminator='kind')],...]=()
    additions:tuple[RecordAddition,...]=()
    uses:tuple[UseReplacement,...]=()
    retractions:tuple[AssertionRetraction,...]=()
    unresolved:tuple[UnresolvedRepair,...]=()


def apply_intake_repair(proposal,patch,*,failed_claims,failed_uses,allowed_fields,context_digest,source_evidence=None):
    patch=ProcessIntakeRepair.model_validate(patch)
    if patch.base_proposal_digest!=semantic_digest(proposal) or patch.context_digest!=context_digest:
        raise ValueError('PROCESS_REPAIR_BASE_OR_CONTEXT_MISMATCH')
    result=copy.deepcopy(proposal); changed=[];seen=set()
    lookup={f'/records/{ri}/{kind}/{i}':(ri,kind,i) for ri,r in enumerate(result['draft']['records'])
        for kind in ('terms','assertions') for i,_ in enumerate(r[kind])}
    retract={r.target_pointer:r for r in patch.retractions}
    if len(retract)!=len(patch.retractions) or any(p not in failed_claims or p not in lookup or lookup[p][1]!='assertions' for p in retract):
        raise ValueError('PROCESS_REPAIR_UNRELATED_OR_DUPLICATE_RETRACTION')
    permitted=set(failed_claims)|set(dependent_nodes(proposal['draft'],retract))
    for item in patch.nodes:
        ptr=item.target_pointer
        if ptr in seen or ptr not in permitted or ptr not in lookup or ptr in retract:raise ValueError('PROCESS_REPAIR_UNRELATED_OR_DUPLICATE_NODE')
        seen.add(ptr);ri,kind,index=lookup[ptr]
        if kind!=('terms' if item.kind=='term' else 'assertions'):raise ValueError('PROCESS_REPAIR_NODE_KIND_CHANGED')
        field='term_id' if kind=='terms' else 'assertion_id';replacement=item.replacement.model_dump(mode='json')
        if replacement[field]!=result['draft']['records'][ri][kind][index][field]:raise ValueError('PROCESS_REPAIR_NODE_ID_CHANGED')
        result['draft']['records'][ri][kind][index]=replacement;changed.append(ptr)
    record_lookup={f'/records/{i}':r for i,r in enumerate(result['draft']['records'])}
    for add in patch.additions:
        if add.record_pointer not in record_lookup:raise ValueError('PROCESS_REPAIR_NEW_RECORD_NOT_ALLOWED')
        record=record_lookup[add.record_pointer]
        for kind,items in (('terms',add.terms),('assertions',add.assertions)):
            for item in items:
                value=item.model_dump(mode='json')
                if not {q['field_locator'] for q in value['evidence']}<=set(allowed_fields):raise ValueError('PROCESS_REPAIR_UNRELATED_ADDITION')
                changed.append(add.record_pointer+'/'+kind+'/'+str(len(record[kind])));record[kind].append(value)
    touched_records={p.rsplit('/',2)[0] for p in (*changed,*retract)}
    use_inventory={f'/definition_uses/{i}':i for i,_ in enumerate(result['definition_uses'])}
    allowed_uses=set(failed_uses)|{p for p,i in use_inventory.items()
        if result['definition_uses'][i]['term_pointer'].rsplit('/',2)[0] in touched_records}
    seen=set()
    for item in patch.uses:
        if item.use_pointer in seen or item.use_pointer not in allowed_uses or item.use_pointer not in use_inventory:
            raise ValueError('PROCESS_REPAIR_UNRELATED_OR_DUPLICATE_USE')
        seen.add(item.use_pointer);i=use_inventory[item.use_pointer]
        if item.replacement.term_pointer!=result['definition_uses'][i]['term_pointer']:raise ValueError('PROCESS_REPAIR_LOCAL_SUBJECT_CHANGED')
        result['definition_uses'][i]=item.replacement.model_dump(mode='json')
    retracted=[];pointer_map={p:p for p in lookup};reference_remappings=[]
    if retract:
        if source_evidence is None or source_evidence['source']['digest']!=proposal['draft']['source_revision_digest']:
            raise ValueError('PROCESS_RETRACTION_EXACT_SOURCE_REQUIRED')
        fields={f['field_locator']:f['text'] for f in source_evidence['fields']}
        for ptr,item in retract.items():
            for q in item.evidence:
                if q.field_locator not in allowed_fields or q.field_locator not in fields:raise ValueError('PROCESS_RETRACTION_EVIDENCE_OUTSIDE_REPAIR')
                offset=-1
                for _ in range(q.occurrence+1):
                    offset=fields[q.field_locator].find(q.quote,offset+1)
                    if offset<0:raise ValueError('PROCESS_RETRACTION_QUOTE_NOT_IN_SOURCE')
            ri,kind,index=lookup[ptr]
            retracted.append({**item.model_dump(mode='json'),'prior_node_digest':semantic_digest(proposal['draft']['records'][ri][kind][index])})
            changed.append(ptr);pointer_map[ptr]=None
        # IDs remain stable. Ordinal pointers for remaining nodes are mapped,
        # never silently made to point at a different assertion.
        for ri,record in enumerate(result['draft']['records']):
            record['assertions']=[a for i,a in enumerate(record['assertions']) if f'/records/{ri}/assertions/{i}' not in retract]
            current={a['assertion_id']:i for i,a in enumerate(record['assertions'])}
            for ptr,(r,kind,index) in lookup.items():
                if r==ri and kind=='assertions' and ptr not in retract:
                    identity=proposal['draft']['records'][ri][kind][index]['assertion_id']
                    pointer_map[ptr]=f'/records/{ri}/assertions/{current[identity]}'
        def mapped(ptr):
            parts=ptr.split('/')
            if len(parts)<5:return ptr
            root='/'.join(parts[:5]);tail='/'.join(parts[5:])
            if root not in pointer_map:return ptr
            target=pointer_map[root]
            if target is None:raise ValueError('PROCESS_RETRACTION_REFERENCED_FACET_REQUIRES_EXPLICIT_REPAIR')
            return target+('/'+tail if tail else '')
        for ui,use in enumerate(result['definition_uses']):
            for comparison in use['scope_assessments']:
                for decision in comparison['local']:
                    old=decision['target_pointer'];new=mapped(old)
                    if old!=new:reference_remappings.append({'use_pointer':f'/definition_uses/{ui}','from':old,'to':new})
                    decision['target_pointer']=new
        def value_at(doc,ptr):
            value=doc
            for part in ptr.split('/')[1:]:value=value[int(part)] if isinstance(value,(list,tuple)) else value[part.replace('~1','/').replace('~0','~')]
            return value
        for item in retracted:
            retained=[]
            for ptr in item['retained_locations']:
                try:
                    new=mapped(ptr);value=value_at(proposal['draft'],ptr)
                    if value!=value_at(result['draft'],new):raise ValueError('PROCESS_RETRACTION_RETAINED_INFORMATION_CHANGED')
                except (KeyError,IndexError,TypeError):raise ValueError('PROCESS_RETRACTION_RETAINED_LOCATION_INVALID') from None
                retained.append({'prior_pointer':ptr,'current_pointer':new,'value_digest':semantic_digest(value)})
            item['retained_bindings']=retained
    unresolved_allowed=set(failed_claims)|set(failed_uses)|{'field:'+f for f in allowed_fields}
    if any(u.target_pointer not in unresolved_allowed for u in patch.unresolved):raise ValueError('PROCESS_REPAIR_UNRELATED_UNRESOLVED')
    result['context_digest']=context_digest;result['draft']['extraction_context_digest']=context_digest
    validated=ProcessReuseProposalV2.model_validate(result).model_dump(mode='json')
    return validated,{'changed_nodes':changed,'changed_use_pointers':sorted(seen),
        'retracted_nodes':retracted,'node_pointer_map':pointer_map,'reference_remappings':reference_remappings,
        'meaning_of_retraction':'model_proposed; source fidelity needs review; original asset preserved',
        'unresolved':[u.model_dump(mode='json') for u in patch.unresolved]}
