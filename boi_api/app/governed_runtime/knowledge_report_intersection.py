"""Intersection of independently witnessed reports on one exact source object.

This is not co-context Boolean conjunction, relation traversal, condition
satisfaction or a proof of source completeness. Existing AND semantics stay
unchanged. The enclosing official transport must supply its actual protected
result service and authenticated actor; request data never supplies authority.
"""
import json
from time import monotonic
from typing import Literal
from pydantic import Field, model_validator
from .semantic_binding_contract import FrozenContract


class KnowledgeReportIntersectionRequest(FrozenContract):
    contract_version: Literal['boi/knowledge-report-intersection@1']='boi/knowledge-report-intersection@1'
    result_refs: tuple[str,...]=Field(min_length=2,max_length=16)

    @model_validator(mode='after')
    def exact_results(self):
        import re
        if len(set(self.result_refs))!=len(self.result_refs) or any(
                not re.fullmatch(r'protected:prepared-knowledge-query:[0-9a-f-]{36}',r) for r in self.result_refs):
            raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_RESULT_REFS_REQUIRED')
        return self


class KnowledgeReportIntersection:
    def __init__(self, results, *, clock=monotonic, max_rows=10000, max_seconds=30):
        self.results,self.clock=results,clock
        self.max_rows,self.max_seconds=max_rows,max_seconds

    def read(self, *, actor_id, request):
        req=KnowledgeReportIntersectionRequest.model_validate(request)
        started=self.clock();loaded=[];inputs=[];members=[];population=None;total_rows=0
        def budget():
            if self.clock()-started>self.max_seconds:
                raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_TIME_BUDGET_EXCEEDED')
        for ref in req.result_refs:
            budget();value=self.results._load(ref,actor_id)
            if (value['result']['execution_state']!='stored' or value['query']['operation']!='select_objects'
                    or value['query']['claim_basis']!='reported_statement_exists'):
                raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_STORED_REPORT_REQUIRED')
            self.results._checked(value,actor_id)
            binding={'set_ref':value['set_ref'],'object_type':value['query']['object_type']}
            if population is not None and population!=binding:
                raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_POPULATION_MISMATCH')
            population=binding;loaded.append(value)
            cursor=None;cursors=set();rows={};summary=None
            while True:
                budget()
                page=self.results.page(ref,actor_id=actor_id,group='reported',page_size=100,cursor=cursor)
                observed={key:page[key] for key in ('result_digest','group_count','counts','coverage')}
                if summary is not None and observed!=summary:
                    raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_PAGE_BINDING_CHANGED')
                summary=observed
                if summary['group_count']>self.max_rows:
                    raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_ROW_BUDGET_EXCEEDED')
                for row in page['rows']:
                    total_rows+=1
                    if total_rows>self.max_rows:
                        raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_ROW_BUDGET_EXCEEDED')
                    if row['id'] in rows or row['state'] not in ('supported','conflicted') or not row.get('witness_read'):
                        raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_WITNESS_REQUIRED')
                    rows[row['id']]=row
                cursor=page['next_cursor']
                if cursor is None:break
                if cursor in cursors or not page['rows']:
                    raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_CURSOR_INVALID')
                cursors.add(cursor)
            if len(rows)!=summary['group_count']:
                raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_INCOMPLETE_INPUT')
            inputs.append({'result_ref':ref,**summary,'query':value['query']})
            members.append(rows)
        matching=set.intersection(*(set(rows) for rows in members))
        rows=[]
        for identity in sorted(matching):
            reports=[selection[identity] for selection in members]
            if len({report['revision'] for report in reports})!=1:
                raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_REVISION_MISMATCH')
            rows.append({'id':identity,'revision':reports[0]['revision'],
                'report_conflict_present':any(report['state']=='conflicted' for report in reports),
                'reports':[{'input_index':i,'state':report['state'],'witness_read':report['witness_read'],
                    'document_read':report.get('document_read')} for i,report in enumerate(reports)]})
        result={'contract_version':'boi/knowledge-report-intersection-result@1',
            'request':req.model_dump(mode='json'),'population':population,'inputs':inputs,'rows':rows,
            'member_count':len(rows),'input_pages_complete':True,'query_reexecuted':False,'result_persisted':False,
            'meaning':'each_selected_report_independently_exists_on_same_exact_object_revision',
            'context_composition':'not_performed; each input retains its own source fields, conditions, time and modality',
            'nonmembership':'no_complete_qualified_report_intersection_not_source_absence',
            'population_completeness_qualified':False,'same_world_condition_satisfaction':'not_evaluated',
            'scientific_truth_proven':False}
        if len(json.dumps(result,ensure_ascii=False).encode())>4*1024*1024:
            raise ValueError('KNOWLEDGE_REPORT_INTERSECTION_OUTPUT_BUDGET_EXCEEDED')
        for value in loaded:
            budget();self.results._checked(value,actor_id)
        return result
