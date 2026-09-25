"""Agent-side process AST/evidence lint; no name routing or semantic truth rules."""
from __future__ import annotations

from boi_api.app.governed_runtime.process_knowledge_contract import ProcessKnowledgeDraft
from boi_api.app.governed_runtime.semantic_binding_contract import RevisionRef, semantic_digest
from boi_api.app.governed_runtime.source_envelope import byte_digest
from boi_api.app.governed_runtime.task_knowledge import TaskKnowledgeContext


class ProcessBindingError(ValueError):
    def __init__(self,code,*,target_pointer,field_locator):
        super().__init__(code)
        self.diagnostic={'message':code,'target_pointer':target_pointer,'field_locator':field_locator}


def bind_process_meaning(draft, *, evidence, extraction_context, version=1, source_readings=None):
    if version not in (1, 2):
        raise ValueError('PROCESS_BINDING_VERSION_UNSUPPORTED')
    draft = ProcessKnowledgeDraft.model_validate(draft)
    context = TaskKnowledgeContext.model_validate(extraction_context)
    if context.context_digest != draft.extraction_context_digest:
        raise ValueError('PROCESS_EXTRACTION_CONTEXT_MISMATCH')
    if draft.source_revision_digest != evidence['source']['digest']:
        raise ValueError('PROCESS_SOURCE_REVISION_MISMATCH')
    # The trusted executor receives this projection as a Wiki-owned input.
    # A self-built manifest outside a bound invocation is not authenticated.
    manifest = evidence['manifest']
    if manifest['source_revision_digest'] != draft.source_revision_digest:
        raise ValueError('PROCESS_SOURCE_MANIFEST_MISMATCH')
    if (manifest['employee_id'],manifest['policy_digest']) != (context.principal_id,context.policy_digest):
        raise ValueError('PROCESS_SOURCE_ACCESS_CONTEXT_MISMATCH')
    source_manifest = semantic_digest([evidence['source']])
    if source_readings is None:
        if context.source_manifest_digest != source_manifest:
            raise ValueError('PROCESS_SOURCE_CONTEXT_MISMATCH')
    else:
        from .boi_process_answer_v2 import validate_source_readings
        validate_source_readings(context,source_readings)
        if evidence not in source_readings:
            raise ValueError('PROCESS_PRIMARY_SOURCE_NOT_READ')
    fields = {f['field_locator']:f for f in evidence['fields']}
    if len(fields) != len(evidence['fields']):
        raise ValueError('PROCESS_EVIDENCE_FIELD_AMBIGUOUS')
    if {(f['field_locator'],f['span_ref'],f['content_digest']) for f in evidence['fields']} != {
            (f['field_locator'],f['span_ref'],f['content_digest']) for f in manifest['fields']}:
        raise ValueError('PROCESS_EVIDENCE_MANIFEST_MISMATCH')
    for field in fields.values():
        if byte_digest(field['text'].encode('utf-8')) != field['content_digest']:
            raise ValueError('PROCESS_EVIDENCE_FIELD_DIGEST_MISMATCH')
    definitions = {a.revision for a in context.assets if a.kind == 'definition'}
    if not set(draft.definition_revisions_used) <= definitions:
        raise ValueError('PROCESS_DEFINITION_REVISION_NOT_READ')
    bindings = []
    coverage = {}
    def bind(quote, pointer, *, coverage_kind=None):
        field = fields.get(quote.field_locator)
        if not field or field['field_state'] != 'present':
            raise ProcessBindingError('PROCESS_QUOTE_FIELD_UNAVAILABLE',target_pointer=pointer,field_locator=quote.field_locator)
        starts, cursor = [], 0
        while True:
            index = field['text'].find(quote.quote,cursor)
            if index < 0:break
            starts.append(index)
            cursor = index+1
        if quote.occurrence >= len(starts):
            raise ProcessBindingError('PROCESS_QUOTE_NOT_IN_SOURCE',target_pointer=pointer,field_locator=quote.field_locator)
        start = starts[quote.occurrence]
        binding = {'target_pointer':pointer,'span_ref':field['span_ref'],
            'source_revision_digest':draft.source_revision_digest,'field_locator':quote.field_locator,
            'field_content_digest':field['content_digest'],'start':start,'end':start+len(quote.quote),
            'quote_digest':byte_digest(quote.quote.encode('utf-8')),'offset_basis':'decoded_unicode_codepoints',
            'semantic_support':'model_proposed'}
        bindings.append(binding)
        if coverage_kind:
            coverage.setdefault(quote.field_locator,[]).append((start,binding['end'],coverage_kind))
    for ri,record in enumerate(draft.records):
        for locator in record.source_description_fields:
            if locator not in fields:
                raise ValueError('PROCESS_DESCRIPTION_FIELD_UNAVAILABLE')
            coverage.setdefault(locator,[])
        for ti,term in enumerate(record.terms):
            if term.reused_definition and term.reused_definition not in draft.definition_revisions_used:
                raise ValueError('PROCESS_TERM_DEFINITION_USE_NOT_DECLARED')
            for ei,quote in enumerate(term.evidence):bind(quote,f'/records/{ri}/terms/{ti}/evidence/{ei}')
        for ai,assertion in enumerate(record.assertions):
            for ei,quote in enumerate(assertion.evidence):
                bind(quote,f'/records/{ri}/assertions/{ai}/evidence/{ei}',coverage_kind='proposed_assertion')
            for role in ('conditions','exceptions','applicability'):
                for qi,qualifier in enumerate(getattr(assertion,role)):
                    for ei,quote in enumerate(qualifier.evidence):
                        bind(quote,f'/records/{ri}/assertions/{ai}/{role}/{qi}/evidence/{ei}',coverage_kind='proposed_qualifier')
        for ui,item in enumerate(record.uninterpreted):
            bind(item.evidence,f'/records/{ri}/uninterpreted/{ui}',coverage_kind='uninterpreted')
    coverage_report = []
    for locator,ranges in sorted(coverage.items()):
        text = fields[locator]['text']
        covered = set(i for start,end,_ in ranges for i in range(start,end))
        uncovered = [i for i,char in enumerate(text) if not char.isspace() and i not in covered]
        coverage_report.append({'field_locator':locator,'nonwhitespace_characters':sum(not c.isspace() for c in text),
            'uncovered_positions':uncovered,'status':'all_text_accounted' if not uncovered else 'text_gaps',
            'semantic_claim_completeness':'not_evaluated'})
    draft_wire = draft.model_dump(mode='json')
    result = {'contract_version':f'boi/bound-process-meaning@{version}','draft':draft_wire,'bindings':bindings,
        'coverage':coverage_report,'transformation':{'kind':'external_semantic_extraction',
            'input_source_digest':draft.source_revision_digest,'context_digest':context.context_digest,
            'definition_revisions_used':[r.model_dump(mode='json') for r in draft.definition_revisions_used],
            'draft_digest':semantic_digest(draft_wire)},
        'typed_validity':'pass','evidence_binding':'pass','source_fidelity':'not_evaluated',
        'scientific_correctness':'not_evaluated','status':'PROVISIONAL','canonical_projection_eligible':False}
    if version == 2:
        from .boi_source_coverage import partition_source
        result['source_partition'] = partition_source(evidence, bindings,
            description_fields={f for r in draft.records for f in r.source_description_fields})
        from .boi_process_categories import read_category_contract
        category_contract=read_category_contract(context)
        if category_contract is not None:
            result['category_contract_binding']={k:v for k,v in category_contract.items() if k!='contract'}
    return result
