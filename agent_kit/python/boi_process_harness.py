"""Process profile and the executable binding stage of its external harness.

Semantic assessment and explanation are separate stages. This module never
recognizes process names, manufactures claims, or upgrades a candidate.
"""
import json
from pydantic import ValidationError

from agent_kit.python.boi_process_lint import bind_process_meaning
from boi_api.app.governed_runtime.domain_work_contract import DomainHarnessContract, DomainToolReport
from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft


def process_profile(*, version=1):
    if version not in (1, 2):raise ValueError('PROCESS_BINDING_VERSION_UNSUPPORTED')
    return {'contract_version':f'boi/process-profile@{version}',
        'meaning_schema':ProcessKnowledgeDraft.model_json_schema(),
        'assertion_semantics':'source_reported',
        'reference_domains':{'process_ref':'term_id','subject_ref':'term_id','object_refs':'term_id','depends_on':'assertion_id'},
        'validation_axes':['typed_validity','evidence_binding','text_accounting','source_fidelity','scientific_correctness'],
        'source_fidelity_requirement':'Independent assessment of every output claim and source meaning; quotation overlap is insufficient.',
        **({'text_preservation_requirement':'The tool partitions every original field into exact quoted and unselected ranges. '
            'Unselected text requires semantic assessment; a complete partition never proves meaningful extraction.'} if version==2 else {}),
        'scientific_correctness_requirement':'Separate applicable qualified scientific evidence and tools.',
        'canonical_projection_eligible':False}


def process_binding_harness(*, namespace, tool_revision, version=1):
    if version not in (1, 2):raise ValueError('PROCESS_BINDING_VERSION_UNSUPPORTED')
    return DomainHarnessContract(namespace=namespace,title='Process meaning binding',
        purpose='Bind externally extracted process assertions to exact source and knowledge revisions.',
        stages=({'stage_id':'bind','purpose':'Validate process graph and exact quotation bindings',
            'instructions':'Read the complete process profile, source projection and knowledge context. Propose the process draft, '
                'then execute the registered external process lint with the unchanged draft, evidence and context inputs. '
                'This stage completion covers structural binding only. Retain separate source-fidelity and science assessments.',
            'tools':[{'tool_revision':tool_revision,'input_names':['draft','evidence','context'],
                'input_kinds':{'draft':'proposal','evidence':'source_projection','context':'context'},
                'checks':[{'check_id':name,'accepted_statuses':['pass']} for name in
                    ('process_ast','process_source_binding',
                        'process_source_preservation' if version==2 else 'process_text_accounting')]}]},))


def execute_process_binding(inputs, *, version=1):
    """RegisteredReadOnlyTool executor callback; trust/signing stays in the host."""
    if set(inputs) != {'draft','evidence','context'}:
        raise ValueError('PROCESS_BINDING_INPUT_SET_MISMATCH')
    draft,evidence,context=(json.loads(inputs[name]) for name in ('draft','evidence','context'))
    subject=evidence['source']['artifact_ref']
    try:
        bound=bind_process_meaning(draft,evidence=evidence,extraction_context=context,version=version)
    except ValidationError as exc:
        diagnostics=[{'path':list(e['loc']),'message':e['msg']} for e in exc.errors(include_input=False,include_url=False)]
        return DomainToolReport(checks=[{'check_id':'process_ast','status':'fail','subject_ref':subject,
            'reason_code':'PROCESS_TYPED_GRAPH_INVALID','evidence_refs':[subject]}],result={
                'diagnostics':diagnostics,'source_fidelity':'not_evaluated','scientific_correctness':'not_evaluated',
                'status':'PROVISIONAL','canonical_projection_eligible':False}).model_dump(mode='json')
    except ValueError as exc:
        code=str(exc)
        if not code.startswith('PROCESS_'):raise
        return DomainToolReport(checks=[{'check_id':'process_source_binding','status':'fail','subject_ref':subject,
                'reason_code':code,'evidence_refs':[subject]}],result={'diagnostics':[getattr(exc,'diagnostic',{'message':code})],
                'source_fidelity':'not_evaluated','scientific_correctness':'not_evaluated',
                'status':'PROVISIONAL','canonical_projection_eligible':False}).model_dump(mode='json')
    checks=[{'check_id':name,'status':'pass','subject_ref':subject,
        'reason_code':reason,'evidence_refs':[subject]} for name,reason in (
            ('process_ast','PROCESS_TYPED_GRAPH_VALID'),('process_source_binding','PROCESS_EXACT_QUOTES_BOUND'))]
    gaps=[field for field in bound['coverage'] if field['status']=='text_gaps']
    checks.append({'check_id':'process_source_preservation' if version==2 else 'process_text_accounting',
        'status':'pass' if version==2 else ('fail' if gaps else 'pass'),
        'subject_ref':subject,'reason_code':('PROCESS_SOURCE_PRESERVED_SEMANTICS_UNASSESSED' if version==2 else
            ('PROCESS_UNACCOUNTED_TEXT' if gaps else 'PROCESS_TEXT_ACCOUNTED_NOT_SEMANTIC_COVERAGE')),
        'evidence_refs':[subject]})
    return DomainToolReport(checks=checks,result=bound).model_dump(mode='json')


def execute_process_binding_v2(inputs):
    return execute_process_binding(inputs, version=2)
