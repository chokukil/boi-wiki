"""Deterministic, value-grounded presentation for reviewed query answers.

The presentation is a projection of an already built reviewed answer.  It does
not interpret source prose, call a model, or change candidate authority.  The
structured conditions remain available so every channel can render the same
meaning without parsing the Korean summary.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any, Literal, Sequence

from pydantic import Field, model_validator

from .governed_answer_artifact import (
    ArtifactExecutionEvidence,
    ArtifactResultSet,
)
from .semantic_binding_contract import Digest, FrozenContract, Ref, semantic_digest


ConditionOrigin = Literal['QUESTION', 'REVIEWED_SOURCE']
ConditionOperator = Literal[
    'eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in', 'is_null', 'not_null'
]


def _clean_label(value: object, fallback: str) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not text:
        text = fallback
    cleaned = ''.join(character for character in text if character.isprintable()).strip()
    if not cleaned:
        cleaned = ''.join(
            character for character in fallback if character.isprintable()
        ).strip() or '항목'
    return cleaned[:120]


def _reference_label(value: str) -> str:
    """Shorten a logical identity without inferring a human-language meaning."""
    return _clean_label(value.rsplit(':', 1)[-1], value)


def _unit_display_label(value: str | None, labels: dict[str, str]) -> str | None:
    if not value:
        return None
    reference = (
        value.removeprefix('property-ref:')
        if value.startswith('property-ref:') else value
    )
    return labels.get(reference, _reference_label(reference))


def _field_unit_suffix(value: str | None, labels: dict[str, str]) -> str:
    label = _unit_display_label(value, labels)
    if label is None:
        return ''
    if value and value.startswith('property-ref:'):
        return f' (행별 단위: {label})'
    return f' {label}'


def _scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _display_value(value: object, *, maximum: int = 96) -> str | None:
    if not _scalar(value) or (isinstance(value, float) and not math.isfinite(value)):
        return None
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    if len(encoded) > maximum or any(ord(character) < 32 for character in encoded):
        return None
    return encoded


def _condition_values(operator: str, value: object) -> tuple[object, ...]:
    if operator in {'is_null', 'not_null'}:
        return ()
    if operator == 'in':
        if not isinstance(value, (list, tuple)):
            raise ValueError('REVIEWED_ANSWER_CONDITION_VALUE_INVALID')
        return tuple(value)
    return (value,)


def _condition_signature(*, property_ref: str, operator: str,
        values: Sequence[object], unit_ref: str | None, application_scope: str) -> str:
    return semantic_digest({
        'property_ref': property_ref,
        'operator': operator,
        'values': list(values),
        'unit_ref': unit_ref,
        'application_scope': application_scope,
    })


def _condition_text(*, label: str, operator: str, values: Sequence[object],
        unit_label: str | None) -> str:
    signs = {
        'eq': '=', 'neq': '≠', 'gt': '>', 'gte': '≥', 'lt': '<', 'lte': '≤',
        'in': '∈', 'is_null': '값 없음', 'not_null': '값 있음',
    }
    if operator in {'is_null', 'not_null'}:
        return f"{label}: {signs[operator]}"
    rendered = [_display_value(value) for value in values]
    if any(value is None for value in rendered):
        return f"{label}: {signs[operator]} [표시 제한 값]"
    operand = '[' + ', '.join(rendered) + ']' if operator == 'in' else rendered[0]
    if len(operand) > 360:
        operand = f"[{len(values)}개 값; 구조화된 조건에서 확인]"
    unit = f" {unit_label}" if unit_label else ''
    return f"{label} {signs[operator]} {operand}{unit}"


class ReviewedAnswerCondition(FrozenContract):
    property_ref: Ref
    property_label: str = Field(min_length=1, max_length=120)
    scope_object_ref: Ref
    application_scope: str = Field(min_length=1, max_length=120)
    operator: ConditionOperator
    values: tuple[Any, ...]
    unit_ref: Ref | None
    origins: tuple[ConditionOrigin, ...] = Field(min_length=1, max_length=2)
    question_filter_indices: tuple[int, ...]
    source_support_count: int = Field(ge=0)
    source_entry_refs: tuple[Ref, ...]
    source_entry_digests: tuple[Digest, ...]
    evidence_span_refs: tuple[Ref, ...]
    display_text: str = Field(min_length=1, max_length=512)
    condition_digest: Digest

    @model_validator(mode='after')
    def bind_condition(self):
        if self.origins != tuple(
            origin for origin in ('QUESTION', 'REVIEWED_SOURCE') if origin in self.origins
        ):
            raise ValueError('REVIEWED_ANSWER_CONDITION_ORIGIN_ORDER_INVALID')
        if any(not _scalar(value) or (
                isinstance(value, float) and not math.isfinite(value)) for value in self.values):
            raise ValueError('REVIEWED_ANSWER_CONDITION_VALUE_INVALID')
        expected_arity = 0 if self.operator in {'is_null', 'not_null'} else (
            len(self.values) if self.operator == 'in' else 1
        )
        if len(self.values) != expected_arity or (self.operator == 'in' and not self.values):
            raise ValueError('REVIEWED_ANSWER_CONDITION_ARITY_INVALID')
        question = 'QUESTION' in self.origins
        source = 'REVIEWED_SOURCE' in self.origins
        if question != bool(self.question_filter_indices):
            raise ValueError('REVIEWED_ANSWER_QUESTION_CONDITION_BINDING_INVALID')
        if source != bool(self.source_support_count):
            raise ValueError('REVIEWED_ANSWER_SOURCE_CONDITION_BINDING_INVALID')
        if source != bool(self.source_entry_refs) or source != bool(self.source_entry_digests):
            raise ValueError('REVIEWED_ANSWER_SOURCE_CONDITION_REFERENCE_INVALID')
        if len(self.source_entry_refs) != len(self.source_entry_digests):
            raise ValueError('REVIEWED_ANSWER_SOURCE_CONDITION_REFERENCE_INVALID')
        if len(set(self.question_filter_indices)) != len(self.question_filter_indices):
            raise ValueError('REVIEWED_ANSWER_QUESTION_CONDITION_DUPLICATE')
        unsigned = self.model_dump(mode='json', exclude={'condition_digest'})
        if self.condition_digest != semantic_digest(unsigned):
            raise ValueError('REVIEWED_ANSWER_CONDITION_DIGEST_MISMATCH')
        return self


class ReviewedAnswerTimeRange(FrozenContract):
    property_ref: Ref
    property_label: str = Field(min_length=1, max_length=120)
    scope_object_ref: Ref
    start: str = Field(min_length=1, max_length=256)
    end: str = Field(min_length=1, max_length=256)
    timezone: str | None = Field(default=None, max_length=120)
    start_inclusive: bool | None
    end_inclusive: bool | None
    display_text: str = Field(min_length=1, max_length=1000)
    range_digest: Digest

    @model_validator(mode='after')
    def bind_range(self):
        unsigned = self.model_dump(mode='json', exclude={'range_digest'})
        if self.range_digest != semantic_digest(unsigned):
            raise ValueError('REVIEWED_ANSWER_TIME_RANGE_DIGEST_MISMATCH')
        return self


class ReviewedAnswerConditionConflict(FrozenContract):
    conflict_kind: Literal[
        'QUESTION_VALUE_EXCLUDED_BY_SOURCE',
        'QUESTION_SOURCE_EQUALITY_CONFLICT',
        'QUESTION_SOURCE_NULLABILITY_CONFLICT',
    ]
    property_ref: Ref
    application_scope: str = Field(min_length=1, max_length=120)
    question_condition_digest: Digest
    source_condition_digest: Digest
    conflict_digest: Digest

    @model_validator(mode='after')
    def bind_conflict(self):
        unsigned = self.model_dump(mode='json', exclude={'conflict_digest'})
        if self.conflict_digest != semantic_digest(unsigned):
            raise ValueError('REVIEWED_ANSWER_CONDITION_CONFLICT_DIGEST_MISMATCH')
        return self


class ReviewedAnswerResultSummary(FrozenContract):
    result_set_id: Ref
    object_ref: Ref
    display_name: str = Field(min_length=1, max_length=120)
    shape: str = Field(min_length=1, max_length=80)
    total_row_count: int = Field(ge=0)
    preview_row_count: int = Field(ge=0)
    truncated: bool
    field_labels: tuple[str, ...] = Field(min_length=1)


class ReviewedAnswerPresentation(FrozenContract):
    contract_version: Literal['boi/reviewed-answer-presentation@1'] = (
        'boi/reviewed-answer-presentation@1'
    )
    execution_classification: Literal['PROVISIONAL'] = 'PROVISIONAL'
    authority: Literal['REVIEWED_CANDIDATE'] = 'REVIEWED_CANDIDATE'
    canonical: Literal[False] = False
    answer_quality_status: Literal['COMPLETE', 'PARTIAL']
    meaning_context_completeness: Literal['complete', 'partial']
    valid_empty_result: bool
    direct_answer: str = Field(min_length=1, max_length=2000)
    scope_notice: Literal[
        '검토된 후보 정의와 현재 원천 snapshot을 사용한 PROVISIONAL 결과입니다.'
    ] = '검토된 후보 정의와 현재 원천 snapshot을 사용한 PROVISIONAL 결과입니다.'
    condition_summary: str = Field(min_length=1, max_length=1000)
    applied_conditions: tuple[ReviewedAnswerCondition, ...]
    time_range: ReviewedAnswerTimeRange | None
    condition_conflicts: tuple[ReviewedAnswerConditionConflict, ...]
    result_summaries: tuple[ReviewedAnswerResultSummary, ...] = Field(min_length=1)
    question_digest: Digest | None
    resolved_intent_digest: Digest
    qualifier_resolution_digest: Digest
    meaning_context_digest: Digest
    execution_result_digest: Digest
    evidence_navigation_refs: tuple[Ref, ...] = Field(min_length=1)
    model_invocations: Literal[0] = 0
    presentation_digest: Digest

    @model_validator(mode='after')
    def bind_presentation(self):
        expected_quality = 'PARTIAL' if (
            self.meaning_context_completeness == 'partial'
            or any(item.truncated for item in self.result_summaries)
        ) else 'COMPLETE'
        if self.answer_quality_status != expected_quality:
            raise ValueError('REVIEWED_ANSWER_QUALITY_STATUS_MISMATCH')
        if self.valid_empty_result != all(
                item.total_row_count == 0 for item in self.result_summaries):
            raise ValueError('REVIEWED_ANSWER_EMPTY_STATUS_MISMATCH')
        unsigned = self.model_dump(mode='json', exclude={'presentation_digest'})
        if self.presentation_digest != semantic_digest(unsigned):
            raise ValueError('REVIEWED_ANSWER_PRESENTATION_DIGEST_MISMATCH')
        return self


class ReviewedQueryOutcomePresentation(FrozenContract):
    """Plain-language projection for a reviewed query that was not executed."""

    contract_version: Literal['boi/reviewed-query-outcome-presentation@2'] = (
        'boi/reviewed-query-outcome-presentation@2'
    )
    execution_classification: Literal['BLOCKED'] = 'BLOCKED'
    answer_quality_status: Literal['BLOCKED', 'NEEDS_CLARIFICATION']
    authority: Literal['REVIEWED_CANDIDATE'] = 'REVIEWED_CANDIDATE'
    canonical: Literal[False] = False
    query_stage: Literal['INTERPRETATION', 'PLANNING']
    direct_answer: str = Field(min_length=1, max_length=1000)
    next_action: str = Field(min_length=1, max_length=1000)
    scope_notice: Literal[
        '조회는 실행되지 않았으며 원천 데이터 결과도 생성되지 않았습니다.'
    ] = '조회는 실행되지 않았으며 원천 데이터 결과도 생성되지 않았습니다.'
    reason_codes: tuple[str, ...]
    unresolved_terms: tuple[str, ...]
    requested_aggregation_operators: tuple[str, ...]
    question_digest: Digest
    candidate_digest: Digest | None
    renderer_model_invocations: Literal[0] = 0
    presentation_digest: Digest

    @model_validator(mode='after')
    def bind_outcome(self):
        unsigned = self.model_dump(mode='json', exclude={'presentation_digest'})
        if self.presentation_digest != semantic_digest(unsigned):
            raise ValueError('REVIEWED_QUERY_OUTCOME_PRESENTATION_DIGEST_MISMATCH')
        return self


def compose_reviewed_query_outcome_presentation(*, question: str,
        status: str, reason_codes: Sequence[str], stage: Literal[
            'INTERPRETATION', 'PLANNING'], candidate: dict[str, Any] | None = None
        ) -> ReviewedQueryOutcomePresentation:
    """Translate deterministic failure codes without hiding the original codes."""
    reasons = tuple(dict.fromkeys(str(code) for code in reason_codes if str(code)))
    candidate = dict(candidate) if candidate is not None else None
    unresolved = tuple(str(value) for value in (
        candidate.get('unresolved_terms', ()) if candidate else ()
    ))
    aggregations = tuple(dict.fromkeys(
        str(item.get('operator') or '')
        for item in (candidate.get('aggregations', ()) if candidate else ())
        if isinstance(item, dict) and item.get('operator')
    ))
    aggregation_labels = {
        'avg': '평균 계산',
        'average': '평균 계산',
        'count': '전체 개수',
        'distinct_count': '중복을 제외한 개수 계산',
        'count_distinct': '중복을 제외한 개수 계산',
        'sum': '합계 계산',
        'min': '최솟값 계산',
        'max': '최댓값 계산',
        'ratio': '비율 계산',
        'latest': '최신값 선택',
        'group': '그룹별 집계',
    }
    requested_labels = tuple(dict.fromkeys(
        aggregation_labels[operator]
        for operator in aggregations
        if operator in aggregation_labels
    ))
    requested_operation = (
        f"{'·'.join(requested_labels)} 요청" if requested_labels else None
    )
    needs_clarification = status == 'CLARIFICATION_REQUIRED'
    if 'REVIEWED_QUESTION_SOURCE_FILTER_OWNERSHIP_CONFLICT' in reasons:
        direct = (
            f'{requested_operation}을 해석한 후보에 질문에 없던 원천 조건이 '
            '질문 조건으로 섞여 들어가 조회를 실행하지 않았습니다.'
            if requested_operation else
            '질문에 없던 원천 조건이 질문 조건으로 섞여 들어가 조회를 실행하지 않았습니다.'
        )
        action = (
            '평균 대상의 값 유형과 계산 계약을 확인하고, 질문 조건을 그대로 '
            '보존하는 의미 해석 후보를 다시 검토해야 합니다.'
            if requested_operation == '평균 계산 요청' else
            '개수 결과 형태를 확인하고, 질문 조건을 그대로 보존하는 의미 해석 '
            '후보를 다시 검토해야 합니다.'
            if requested_operation == '전체 개수 요청' else
            '질문 조건을 그대로 보존하는 의미 해석 후보를 다시 검토해야 합니다.'
        )
    elif 'REVIEWED_QUESTION_SOURCE_LITERAL_FILTER_UNBOUND' in reasons:
        direct = '질문에 명시된 조건이 의미 해석에서 빠져 조회를 실행하지 않았습니다.'
        action = '질문의 조건을 빠짐없이 보존하는 의미 해석 후보를 다시 검토해야 합니다.'
    elif ('AGGREGATION_TYPE_INCOMPATIBLE' in reasons
            and requested_operation == '평균 계산 요청'):
        direct = (
            '평균 계산 요청의 대상 값 유형이 평균 연산과 호환되지 않아 '
            '조회 실행을 차단했습니다.'
        )
        action = (
            '숫자형으로 검증된 속성을 지정하거나 현재 속성에 맞는 계산을 '
            '선택해 주세요.'
        )
    elif 'UNSUPPORTED_OPERATOR' in reasons and requested_operation:
        direct = (
            f'현재 질의 계약이 {requested_operation}에 필요한 연산을 지원하지 않아 '
            '조회 실행을 차단했습니다.'
        )
        action = (
            f'{requested_operation}을 처리할 연산과 결과 형태를 질의 프로필에 '
            '정의한 뒤 검토해야 합니다.'
        )
    elif 'APPROVED_RESULT_SHAPE_NOT_FOUND' in reasons:
        direct = (
            f'{requested_operation}에 필요한 결과 형태가 현재 query contract에 없어 '
            '조회하지 않았습니다.'
            if requested_operation else
            '질문에 필요한 결과 형태가 현재 query contract에 없어 조회를 실행하지 않았습니다.'
        )
        action = '필요한 결과 형태를 query profile 후보로 추가해 검토해야 합니다.'
    elif any(code in reasons for code in (
            'REVIEWED_SNAPSHOT_PAGING_AUTHORITY_REQUIRED',
            'REVIEWED_SNAPSHOT_PAGING_CAPABILITY_UNAVAILABLE')):
        direct = '현재 snapshot을 안전하게 나누어 읽는 계약이 없어 조회를 실행하지 않았습니다.'
        action = 'snapshot paging 계약과 권한을 먼저 준비해야 합니다.'
    elif ('INSUFFICIENT_CONTEXT' in reasons
            and 'count' in aggregations):
        direct = '전체 개수 요청이 의미 해석에서 확정되지 않아 조회를 실행하지 않았습니다.'
        action = '대상 정의와 개수 결과 형태를 지원하는 query contract를 확인해 주세요.'
    elif ('INSUFFICIENT_CONTEXT' in reasons
            and any(operator in {'avg', 'average'} for operator in aggregations)):
        direct = '평균 계산 요청이 의미 해석에서 확정되지 않아 조회를 실행하지 않았습니다.'
        action = '대상 속성의 값 유형과 사용할 수 있는 계산 계약을 확인해 주세요.'
    elif 'INSUFFICIENT_CONTEXT' in reasons and unresolved:
        shown = ', '.join(
            value for value in (_display_value(item) for item in unresolved[:3])
            if value is not None
        ) or '표시 제한 용어'
        suffix = f" 외 {len(unresolved) - 3}개" if len(unresolved) > 3 else ''
        direct = (
            '질문의 다음 용어가 의미 해석에서 미해결로 남아 조회를 실행하지 '
            f'않았습니다: {shown}{suffix}.'
        )
        action = '검토된 정의에 해당 개념·속성을 추가하거나 현재 정의된 대상을 질문에 지정해 주세요.'
    elif needs_clarification or 'INSUFFICIENT_CONTEXT' in reasons:
        direct = '현재 정의만으로 질문의 대상이나 속성을 하나로 정할 수 없어 조회하지 않았습니다.'
        action = '대상, 속성, 조건 또는 기간을 조금 더 구체적으로 적어 주세요.'
    else:
        direct = '필요한 의미 또는 질의 계약을 충족하지 못해 조회를 실행하지 않았습니다.'
        action = '아래 reason code와 현재 정의·mapping 계약을 확인해 주세요.'
    if requested_operation is not None and requested_operation not in direct:
        direct = f'{requested_operation}을 처리할 수 없었습니다. {direct}'
    body = {
        'contract_version': 'boi/reviewed-query-outcome-presentation@2',
        'execution_classification': 'BLOCKED',
        'answer_quality_status': (
            'NEEDS_CLARIFICATION' if needs_clarification else 'BLOCKED'
        ),
        'authority': 'REVIEWED_CANDIDATE',
        'canonical': False,
        'query_stage': stage,
        'direct_answer': direct,
        'next_action': action,
        'scope_notice': '조회는 실행되지 않았으며 원천 데이터 결과도 생성되지 않았습니다.',
        'reason_codes': reasons,
        'unresolved_terms': unresolved,
        'requested_aggregation_operators': aggregations,
        'question_digest': semantic_digest(question),
        'candidate_digest': semantic_digest(candidate) if candidate is not None else None,
        'renderer_model_invocations': 0,
    }
    return ReviewedQueryOutcomePresentation.model_validate({
        **body, 'presentation_digest': semantic_digest(body)
    })


def _meaning_labels(meaning_context) -> dict[str, str]:
    labels = {}
    for item in meaning_context.definitions:
        payload = item.logical_definition
        labels[item.ref] = _clean_label(
            payload.get('name') or payload.get('display_name')
            or payload.get('term') or payload.get('symbol'),
            _reference_label(item.ref),
        )
    return labels


def _property_owner(meaning_context, property_ref: str) -> str:
    definition = next((item.logical_definition for item in meaning_context.definitions
                       if item.ref == property_ref), None)
    owner = definition.get('owner_ref') if isinstance(definition, dict) else None
    return str(owner or property_ref)


def _source_evidence(*, entry_ref: str, predicate: dict[str, Any],
        meaning_context, source_provenance: Sequence[object]) -> tuple[str, ...]:
    refs = []
    definition = next((item for item in meaning_context.definitions
                       if item.ref == entry_ref), None)
    if definition is not None:
        refs.extend(definition.evidence_refs)
    field_digests = {
        evidence['field_digest']
        for evidence in predicate.get('literal_evidence', ())
        if isinstance(evidence, dict) and evidence.get('field_digest')
    }
    for provenance in source_provenance:
        if provenance.definition_ref != entry_ref:
            continue
        matched = tuple(
            item.span_ref for item in provenance.field_evidence
            if not field_digests or item.content_digest in field_digests
        )
        refs.extend(matched or tuple(item.span_ref for item in provenance.field_evidence))
    return tuple(dict.fromkeys(refs))


def _conditions(*, resolved_intent: dict[str, Any], qualifier_resolution: dict[str, Any],
        meaning_context, source_provenance: Sequence[object]) -> tuple[ReviewedAnswerCondition, ...]:
    labels = _meaning_labels(meaning_context)
    accumulated: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    def include(*, property_ref: str, operator: str, values: Sequence[object],
            unit_ref: str | None, origin: ConditionOrigin, application_scope: str,
            question_index: int | None = None, entry_ref: str | None = None,
            entry_digest: str | None = None, evidence_refs: Sequence[str] = ()) -> None:
        if operator not in {'eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in',
                            'is_null', 'not_null'}:
            raise ValueError('REVIEWED_ANSWER_CONDITION_OPERATOR_INVALID')
        signature = _condition_signature(property_ref=property_ref, operator=operator,
            values=values, unit_ref=unit_ref, application_scope=application_scope)
        if signature not in accumulated:
            accumulated[signature] = {
                'property_ref': property_ref,
                'property_label': labels.get(property_ref, property_ref),
                'scope_object_ref': _property_owner(meaning_context, property_ref),
                'application_scope': application_scope,
                'operator': operator,
                'values': tuple(values),
                'unit_ref': unit_ref,
                'origins': [],
                'question_filter_indices': [],
                'source_support_count': 0,
                'source_entries': {},
                'evidence_span_refs': [],
            }
            order.append(signature)
        item = accumulated[signature]
        if origin not in item['origins']:
            item['origins'].append(origin)
        if question_index is not None and question_index not in item['question_filter_indices']:
            item['question_filter_indices'].append(question_index)
        if origin == 'REVIEWED_SOURCE':
            item['source_support_count'] += 1
            previous = item['source_entries'].get(entry_ref)
            if previous is not None and previous != entry_digest:
                raise ValueError('REVIEWED_ANSWER_SOURCE_CONDITION_REVISION_CONFLICT')
            item['source_entries'][entry_ref] = entry_digest
            item['evidence_span_refs'].extend(evidence_refs)

    for index, item in enumerate(resolved_intent.get('filters', ())):
        operator = str(item.get('operator') or '')
        property_ref = str(item.get('property_id') or '')
        owner = _property_owner(meaning_context, property_ref)
        application_scope = str(item.get('scope') or f'OBJECT_ROWS:{owner}')
        include(property_ref=property_ref, operator=operator,
            values=_condition_values(operator, item.get('value')),
            unit_ref=item.get('unit_ref'), origin='QUESTION',
            application_scope=application_scope, question_index=index)

    for clause in qualifier_resolution.get('qualified_clauses', ()):
        qualifier = clause.get('qualifier') or {}
        if qualifier.get('disposition') != 'row_condition':
            continue
        entry_ref = str(clause.get('entry_ref') or '')
        entry_digest = str(clause.get('entry_digest') or '')
        for predicate in qualifier.get('predicates', ()):
            operator = str(predicate.get('operator') or '')
            property_ref = str(predicate.get('property_ref') or '')
            owner = _property_owner(meaning_context, property_ref)
            evidence = _source_evidence(entry_ref=entry_ref, predicate=predicate,
                meaning_context=meaning_context, source_provenance=source_provenance)
            include(property_ref=property_ref,
                operator=operator, values=tuple(predicate.get('values') or ()),
                unit_ref=predicate.get('unit_ref'), origin='REVIEWED_SOURCE',
                application_scope=f'OBJECT_ROWS:{owner}',
                entry_ref=entry_ref, entry_digest=entry_digest,
                evidence_refs=evidence)

    conditions = []
    for signature in order:
        item = accumulated[signature]
        entries = item.pop('source_entries')
        item['origins'] = tuple(
            origin for origin in ('QUESTION', 'REVIEWED_SOURCE')
            if origin in item['origins']
        )
        item['question_filter_indices'] = tuple(item['question_filter_indices'])
        item['source_entry_refs'] = tuple(entries)
        item['source_entry_digests'] = tuple(entries.values())
        item['evidence_span_refs'] = tuple(dict.fromkeys(item['evidence_span_refs']))
        item['display_text'] = _condition_text(label=item['property_label'],
            operator=item['operator'], values=item['values'],
            unit_label=_unit_display_label(item['unit_ref'], labels))
        item['condition_digest'] = semantic_digest(item)
        conditions.append(ReviewedAnswerCondition.model_validate(item))
    return tuple(conditions)


def _time_range(*, resolved_intent: dict[str, Any], meaning_context,
        labels: dict[str, str]) -> ReviewedAnswerTimeRange | None:
    raw = resolved_intent.get('time_range')
    if not raw:
        return None
    property_ref = str(raw.get('property_id') or '')
    start = str(raw.get('start') or '')
    end = str(raw.get('end') or '')
    timezone = raw.get('timezone')
    left = '[' if raw.get('start_inclusive') is not False else '('
    right = ']' if raw.get('end_inclusive') is True else ')'
    zone = f" · 시간대 {timezone}" if timezone else ''
    body = {
        'property_ref': property_ref,
        'property_label': labels.get(property_ref, property_ref),
        'scope_object_ref': _property_owner(meaning_context, property_ref),
        'start': start,
        'end': end,
        'timezone': timezone,
        'start_inclusive': raw.get('start_inclusive'),
        'end_inclusive': raw.get('end_inclusive'),
        'display_text': (
            f"{labels.get(property_ref, property_ref)} {left}{start}, {end}{right}{zone}"
        ),
    }
    return ReviewedAnswerTimeRange.model_validate({
        **body, 'range_digest': semantic_digest(body)
    })


def _condition_conflicts(conditions: Sequence[ReviewedAnswerCondition]
        ) -> tuple[ReviewedAnswerConditionConflict, ...]:
    conflicts = []
    for question in conditions:
        if 'QUESTION' not in question.origins:
            continue
        for source in conditions:
            if ('REVIEWED_SOURCE' not in source.origins
                    or question.condition_digest == source.condition_digest
                    or question.property_ref != source.property_ref
                    or question.application_scope != source.application_scope):
                continue
            kind = None
            if (question.operator, source.operator) in {('eq', 'neq'), ('neq', 'eq')} \
                    and question.values == source.values:
                kind = 'QUESTION_VALUE_EXCLUDED_BY_SOURCE'
            elif question.operator == source.operator == 'eq' \
                    and question.values != source.values:
                kind = 'QUESTION_SOURCE_EQUALITY_CONFLICT'
            elif {question.operator, source.operator} == {'is_null', 'not_null'}:
                kind = 'QUESTION_SOURCE_NULLABILITY_CONFLICT'
            if kind is None:
                continue
            body = {
                'conflict_kind': kind,
                'property_ref': question.property_ref,
                'application_scope': question.application_scope,
                'question_condition_digest': question.condition_digest,
                'source_condition_digest': source.condition_digest,
            }
            conflicts.append(ReviewedAnswerConditionConflict.model_validate({
                **body, 'conflict_digest': semantic_digest(body)
            }))
    unique = {item.conflict_digest: item for item in conflicts}
    return tuple(unique.values())


def _result_summaries(*, result_sets: Sequence[ArtifactResultSet],
        labels: dict[str, str]) -> tuple[ReviewedAnswerResultSummary, ...]:
    return tuple(ReviewedAnswerResultSummary(
        result_set_id=result.result_set_id,
        object_ref=result.object_ref,
        display_name=labels.get(result.object_ref, result.object_ref),
        shape=result.shape,
        total_row_count=result.total_row_count,
        preview_row_count=result.preview_row_count,
        truncated=result.truncated,
        field_labels=tuple(labels.get(
            field.field_ref, _clean_label(field.label, field.field_ref))
                           for field in result.fields),
    ) for result in result_sets)


def _condition_summary(conditions: Sequence[ReviewedAnswerCondition],
        time_range: ReviewedAnswerTimeRange | None) -> str:
    question = sum('QUESTION' in item.origins for item in conditions) + bool(time_range)
    source = sum('REVIEWED_SOURCE' in item.origins for item in conditions)
    if question and source:
        return f"질문 조건 {question}개와 검토된 원천 조건 {source}개를 함께 적용했습니다."
    if question:
        return f"질문 조건 {question}개를 적용했습니다."
    if source:
        return f"검토된 원천 조건 {source}개를 적용했습니다."
    return "추가 조건 없이 현재 snapshot을 조회했습니다."


def _direct_answer(*, result_sets: Sequence[ArtifactResultSet],
        conditions: Sequence[ReviewedAnswerCondition], labels: dict[str, str],
        time_range: ReviewedAnswerTimeRange | None,
        conflicts: Sequence[ReviewedAnswerConditionConflict]) -> str:
    question = bool(time_range) or any('QUESTION' in item.origins for item in conditions)
    source = any('REVIEWED_SOURCE' in item.origins for item in conditions)
    prefix = (
        '질문 조건과 검토된 원천 조건을 모두 적용한 결과'
        if question and source else
        '질문 조건을 적용한 결과' if question else
        '검토된 원천 조건을 적용한 결과' if source else
        '현재 snapshot 조회 결과'
    )
    if len(result_sets) != 1:
        details = ', '.join(
            f"{labels.get(item.object_ref, item.object_ref)} {item.total_row_count:,}건"
            for item in result_sets[:4]
        )
        suffix = '' if len(result_sets) <= 4 else f" 외 {len(result_sets) - 4}개"
        preview = (
            ' 일부 결과 묶음은 현재 미리보기 행만 포함합니다.'
            if any(item.truncated for item in result_sets) else ''
        )
        return (
            f"{prefix}를 {len(result_sets)}개 결과 묶음으로 제공합니다: "
            f"{details}{suffix}.{preview}"
        )
    result = result_sets[0]
    if result.total_row_count == 0:
        if conflicts:
            return '질문 조건과 검토된 원천 조건이 서로 충돌해 결과는 0건입니다.'
        return f"{prefix}는 0건입니다."
    if result.truncated:
        return (
            f"{prefix}는 총 {result.total_row_count:,}건이며, "
            f"첫 응답에는 {result.preview_row_count:,}건을 표시합니다."
        )
    if result.total_row_count == 1 and len(result.rows) == 1 and len(result.fields) <= 4:
        rendered = []
        for field in result.fields:
            value = _display_value(result.rows[0].values[field.output_name])
            if value is None:
                rendered = []
                break
            unit = _field_unit_suffix(field.unit, labels)
            rendered.append(
                f"{labels.get(field.field_ref, _clean_label(field.label, field.field_ref))}"
                f" = {value}{unit}"
            )
        if rendered:
            return f"{prefix}는 1건입니다: {'; '.join(rendered)}."
    return f"{prefix}는 {result.total_row_count:,}건입니다."


def compose_reviewed_answer_presentation(*, question_digest: str | None,
        resolved_intent: dict[str, Any], qualifier_resolution: dict[str, Any],
        meaning_context, result_sets: Sequence[ArtifactResultSet],
        source_provenance: Sequence[object], execution: ArtifactExecutionEvidence
        ) -> ReviewedAnswerPresentation:
    """Compose a channel-neutral answer from frozen structured inputs only."""
    labels = _meaning_labels(meaning_context)
    conditions = _conditions(resolved_intent=resolved_intent,
        qualifier_resolution=qualifier_resolution, meaning_context=meaning_context,
        source_provenance=source_provenance)
    time_range = _time_range(resolved_intent=resolved_intent,
        meaning_context=meaning_context, labels=labels)
    conflicts = _condition_conflicts(conditions)
    summaries = _result_summaries(result_sets=result_sets, labels=labels)
    quality = 'PARTIAL' if meaning_context.completeness == 'partial' or any(
        item.truncated for item in result_sets
    ) else 'COMPLETE'
    # Keep the presentation semantic across equivalent executions. Execution
    # receipt refs remain available on the outer answer artifact and are
    # deliberately excluded from this nested semantic projection.
    evidence = tuple(dict.fromkeys([
        *(ref for definition in meaning_context.definitions
          for ref in definition.evidence_refs),
        *(ref for item in conditions for ref in item.evidence_span_refs),
        *(ref for result in result_sets for field in result.fields
          for ref in field.evidence_refs),
    ]))
    body = {
        'contract_version': 'boi/reviewed-answer-presentation@1',
        'execution_classification': 'PROVISIONAL',
        'authority': 'REVIEWED_CANDIDATE',
        'canonical': False,
        'answer_quality_status': quality,
        'meaning_context_completeness': meaning_context.completeness,
        'valid_empty_result': all(item.total_row_count == 0 for item in result_sets),
        'direct_answer': _direct_answer(result_sets=result_sets,
            conditions=conditions, labels=labels, time_range=time_range,
            conflicts=conflicts),
        'scope_notice': '검토된 후보 정의와 현재 원천 snapshot을 사용한 PROVISIONAL 결과입니다.',
        'condition_summary': _condition_summary(conditions, time_range),
        'applied_conditions': [item.model_dump(mode='json') for item in conditions],
        'time_range': time_range.model_dump(mode='json') if time_range else None,
        'condition_conflicts': [item.model_dump(mode='json') for item in conflicts],
        'result_summaries': [item.model_dump(mode='json') for item in summaries],
        'question_digest': question_digest,
        'resolved_intent_digest': semantic_digest(resolved_intent),
        'qualifier_resolution_digest': semantic_digest(qualifier_resolution),
        'meaning_context_digest': meaning_context.context_digest,
        'execution_result_digest': execution.result_digest,
        'evidence_navigation_refs': evidence,
        'model_invocations': 0,
    }
    return ReviewedAnswerPresentation.model_validate({
        **body, 'presentation_digest': semantic_digest(body)
    })


__all__ = [
    'ReviewedAnswerCondition', 'ReviewedAnswerPresentation',
    'ReviewedAnswerConditionConflict', 'ReviewedAnswerResultSummary',
    'ReviewedAnswerTimeRange', 'ReviewedQueryOutcomePresentation',
    'compose_reviewed_answer_presentation',
    'compose_reviewed_query_outcome_presentation',
]
