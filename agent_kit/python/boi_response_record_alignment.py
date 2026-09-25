"""Record/quotation integrity, not natural-language entailment or authorization."""
from typing import Literal
from pydantic import Field
from boi_api.app.governed_runtime.semantic_binding_contract import FrozenContract, Ref
from .boi_process_answer_evaluation_v2 import (
    AnswerAssessmentV2 as LegacyAssessment, StatementAssessment as LegacyStatement)


class RecordQuote(FrozenContract):
    evidence_id: Ref
    source_quote: Ref


class RecordClause(RecordQuote):
    answer_quote: Ref


class RecordAlignment(FrozenContract):
    mode: Literal['separate', 'connected', 'unestablished']
    clauses: tuple[RecordClause, ...] = Field(min_length=1)
    links: tuple[RecordQuote, ...] = ()


class StatementAssessment(LegacyStatement):
    record_alignment: RecordAlignment | None = None


class AnswerAssessmentV2(LegacyAssessment):
    statements: tuple[StatementAssessment, ...]


def legacy_assessment(value):
    data=value.model_dump(mode='json',exclude_none=True)
    for item in data['statements']:
        item.pop('record_alignment',None)
    return data


def record_alignment_failures(value,material):
    catalog={e['evidence_id']:e for e in material['evidence_catalog']}
    targets={t['target_pointer']:t for t in material['targets']}
    failures=[]
    for judgment in value.statements:
        if judgment.support_relation!='supported' or judgment.citation_support!='full':
            continue
        target=targets[judgment.target_pointer]
        if target['kind']=='runtime_state':
            continue
        ids={i for i in judgment.evidence_ids if catalog[i]['kind']=='source_field'}
        # Include attached citation records even if the assessor omits them.
        citations=list(target.get('citations',[]))
        local_pointer='/'+'/'.join(judgment.target_pointer.split('/')[3:])
        for plan in material.get('request_plans',[]):
            if plan['question_id']!=target['question_id']:continue
            for facet in plan['plan'].get('facets',[]):
                if local_pointer in facet.get('statement_pointers',[]):
                    citations.extend(facet.get('citations',[]))
        for citation in citations:
            for binding in citation.get('source_bindings',[]):
                ids.update(i for i,e in catalog.items() if e['kind']=='source_field'
                    and e.get('source_revision_digest')==binding.get('source_revision_digest')
                    and e.get('field_locator')==binding.get('field_locator'))
        def scope(i):
            e=catalog[i]
            return (e.get('source_revision_digest'),e.get('record_locator') or e.get('field_locator') or i)
        scopes={scope(i) for i in ids}
        alignment=judgment.record_alignment
        known_scopes={scope(i) for i in ids if catalog[i].get('record_locator')}
        # A field locator alone does not establish a distinct business record.
        # Unknown record identity remains unverified; never infer a join or split.
        if len(known_scopes)<2 and alignment is None:
            continue
        reason=None
        if alignment is None:
            reason='record_alignment_missing'
        else:
            covered=set();positions=set();cursor=0
            for clause in alignment.clauses:
                quote=clause.source_quote
                if (clause.evidence_id not in ids or not quote.strip()
                    or quote not in catalog[clause.evidence_id].get('text','')):
                    reason='record_alignment_quote_invalid';break
                start=target['text'].find(clause.answer_quote,cursor)
                if not clause.answer_quote.strip() or start<0:
                    reason='record_alignment_clause_invalid';break
                positions.update(range(start,start+len(clause.answer_quote)))
                cursor=start+len(clause.answer_quote)
                covered.add(scope(clause.evidence_id))
            if reason is None and (covered!=scopes or any(not ch.isspace() and i not in positions for i,ch in enumerate(target['text']))):
                reason='record_alignment_incomplete'
            if reason is None and alignment.mode=='unestablished':
                reason='record_relation_unestablished'
            if reason is None and alignment.mode=='connected' and not alignment.links:
                reason='record_relation_evidence_missing'
            if reason is None:
                for link in alignment.links:
                    if (link.evidence_id not in ids or not link.source_quote.strip()
                        or link.source_quote not in catalog[link.evidence_id].get('text','')):
                        reason='record_relation_quote_invalid';break
            # Exact quotations do not prove that a link semantically connects the clauses.
        if reason:
            failures.append({'target_pointer':judgment.target_pointer,'failure_kind':reason,
                'support_relation':'unsupported','citation_support':judgment.citation_support,
                'reason':'Record alignment or connection evidence is incomplete; preserve independently supported clauses.',
                'evidence_ids':sorted(ids)})
    return failures
