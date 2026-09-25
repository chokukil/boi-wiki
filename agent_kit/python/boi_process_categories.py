"""Explicit process-profile category meanings, never source classification rules.

The registered binder records which exact profile was read. It checks coverage
of the AST vocabulary, not whether a source entity really belongs to a class.
Legacy profiles without this contract retain their original meaning/ambiguity.
"""
import json
from typing import get_args

from boi_api.app.governed_runtime.process_knowledge_contract import ProcessTerm,ProcessAssertion
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


def category_semantics():
    return {
        'contract_version':'boi/process-category-semantics@1',
        'term_categories':{
            'process':'A named operational work unit or process being described, not merely any noun mentioned in its description.',
            'material':'A physical workpiece, film, substrate or other material object. Use a more specific supported category when the referent is explicitly a chemical substance or formulation.',
            'region':'A spatial portion or location of a material object or device. Spatial location does not establish a temporal process stage.',
            'equipment':'A physical device or apparatus, including a described chamber or equipment component.',
            'stage':'A named phase or step within an operation. A technology, product or document label alone does not establish a stage.',
            'quantity':'A measurable property or stated quantity/value. Its presence does not establish a limit, target, safe range or universal rule.',
            'defect':'An undesired result or failure mode described by the source. Preserve the conditions and possibility under which it is reported.',
            'method':'An identified way or procedure for performing an activity. A substance or mixing composition is not itself an activity merely because it is used in a method.',
            'chemical':'A chemical substance, solution, mixture or formulation identified by its material composition. The category does not verify the formula, mechanism, safety or scientific correctness.',
            'other':'A source-supported concept outside these categories, or one whose category cannot be established. Preserve its actual meaning and any unresolved classification instead of asserting an incompatible type.'},
        'assertion_categories':{
            'action':'An act or operation reported by the source.',
            'purpose':'An intended objective; not a guarantee that the effect occurs.',
            'sequence':'An explicit ordering relation between operations; not a causal inference.',
            'control':'A stated control, criterion, target or feedback relation. Preserve whether a number is an example, condition or actual target.',
            'conditional_effect':'A reported consequence dependent on a condition; preserve its polarity and modality.',
            'applicability':'An explicit boundary of applicability to a technology, object or context. A requested scope is not evidence of applicability.',
            'definition':'An explicit naming, expansion, equivalence or meaning relation with its own source evidence and scope.',
            'equipment':'A relation concerning use, assignment or property of equipment.',
            'chemistry':'A reported composition, chemical property or mechanism. Source fidelity is separate from scientific validation.',
            'observation':'A reported observation or measurement; not automatically an operating requirement.'},
        'interpretation':[
            'Classify the referent in its actual local source context, not by spelling, acronym, field name, question or a memorized example.',
            'A category is a semantic claim. Read it together with the label, definition and assertions that refer to that term.',
            'When multiple categories appear plausible, prefer the most specific distinction established by this source and contract; preserve unresolved ambiguity.',
            'An entity may participate in a method or have a purpose without being that method or purpose. Express the source-stated relation with assertions.',
            'If one name explicitly denotes different referents, separate the local nodes with evidence. Do not invent additional entities to satisfy a taxonomy.',
            'Normal paraphrase and translation need not use the category label verbatim. Category choice cannot add an unstated property, scope or condition.',
            'This contract applies to new work that reads its exact profile revision. Do not reinterpret a historical category using a later contract without recording that reevaluation.'],
        'deterministic_scope':'Category vocabulary and exact read profile binding only; semantic classification and source fidelity require separate model review.',
        'scientific_truth_proven':False}


def validate_category_semantics(value):
    if (value.get('contract_version')!='boi/process-category-semantics@1'
            or set(value.get('term_categories',{}))!=set(get_args(ProcessTerm.model_fields['category'].annotation))
            or set(value.get('assertion_categories',{}))!=set(get_args(ProcessAssertion.model_fields['category'].annotation))
            or any(not isinstance(v,str) or not v.strip() for section in ('term_categories','assertion_categories') for v in value[section].values())):
        raise ValueError('PROCESS_CATEGORY_CONTRACT_INCOMPLETE')
    return value


def read_harness_profiles(context,*,harness_revision=None):
    """Exact selected harness dependencies; no global newest-profile lookup."""
    context=TaskKnowledgeContext.model_validate(context)
    assets={a.revision:a for a in context.assets}
    if harness_revision is None:
        harnesses={s.requirement.revision for s in context.selections if s.parent is None and s.status=='selected'
            and assets[s.requirement.revision].kind=='harness'}
    else:
        from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef
        harnesses={RevisionRef.model_validate(harness_revision)}
    profiles={s.requirement.revision for s in context.selections if s.parent in harnesses and s.status=='selected'
        and s.requirement.role=='profile' and assets[s.requirement.revision].kind=='profile'}
    return [assets[ref] for ref in sorted(profiles,key=lambda r:r.ref)]


def read_category_contract(context,*,harness_revision=None):
    """Resolve the profile declared by this harness, not the newest in history."""
    declared=[]
    for asset in read_harness_profiles(context,harness_revision=harness_revision):
        ref=asset.revision;profile=json.loads(asset.content_json)
        if 'category_semantics' in profile:
            semantic=validate_category_semantics(profile['category_semantics'])
            declared.append({'profile_revision':ref.model_dump(mode='json'),'profile_content_digest':asset.content_digest,
                'contract':semantic,'contract_digest':semantic_digest(semantic),
                'source_fidelity':'not_evaluated','historical_categories_reinterpreted':False})
    if len(declared)>1:raise ValueError('PROCESS_CATEGORY_PROFILE_AMBIGUOUS')
    return declared[0] if declared else None


def declared_proposal_schema_errors(proposal,context):
    """Validate the read profile's JSON schema; never classify domain meaning."""
    from jsonschema import Draft202012Validator
    profiles=[a for a in read_harness_profiles(context) if 'meaning_schema' in json.loads(a.content_json)]
    if len(profiles)>1:raise ValueError('PROCESS_PROPOSAL_PROFILE_AMBIGUOUS')
    if not profiles:return []  # Historical contexts without an explicit profile keep their contract.
    asset=profiles[0];schema=json.loads(asset.content_json)['meaning_schema']
    Draft202012Validator.check_schema(schema)
    return [{'path':list(error.absolute_path),'rule':error.validator,'schema_path':list(error.absolute_schema_path),
        'message':'Proposal does not satisfy the exact selected profile meaning_schema.',
        'profile_revision':asset.revision.model_dump(mode='json'),'schema_digest':semantic_digest(schema),
        'declared_contract_version':schema.get('properties',{}).get('contract_version',{})}
        for error in Draft202012Validator(schema).iter_errors(proposal)]
