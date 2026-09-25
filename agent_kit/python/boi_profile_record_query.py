"""Source-bound record projection and Profile-only natural-language querying.

Routing chooses semantic components. This module turns an accepted route into
queryable provisional records without exposing physical field names to the
natural-language planner. It grants neither publication nor semantic review.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agent_kit.python.boi_profile_intake_router import SourceFeature
from boi_api.app.governed_runtime.knowledge_profile import KnowledgeProfileDeclaration
from boi_api.app.governed_runtime.semantic_binding_contract import semantic_digest


class ProfileRouteReview(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-route-review@1']
    route_digest: str
    source_snapshot_digest: str
    decision: Literal['accepted', 'rejected']
    reviewer_ref: str = Field(min_length=1, max_length=512)
    reason: str = Field(min_length=1, max_length=4000)


class ProfileRecordDisposition(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    record_index: int = Field(ge=0)
    role: Literal['domain_record', 'header', 'evidence_context', 'outside_scope']
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=4000)


class ProfileRecordLayoutObservation(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-record-layout-observation@1']
    dispositions: tuple[ProfileRecordDisposition, ...] = Field(min_length=1)


class ProfileRecordLayoutReview(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-record-layout-review@1']
    layout_digest: str
    source_snapshot_digest: str
    decision: Literal['accepted', 'rejected']
    reviewer_ref: str = Field(min_length=1, max_length=512)
    reason: str = Field(min_length=1, max_length=4000)


class ProfileQueryFilter(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    component_id: str
    operator: Literal['eq', 'ne', 'gt', 'gte', 'lt', 'lte']
    value: Any


class ProfileTextSearch(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    query: str = Field(min_length=1, max_length=1000)
    # Admitted domain Profiles can expose more than sixteen source-bound text
    # predicates. The bound remains finite, but one complete Profile can be
    # searched without a schema-only retry.
    component_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    mode: Literal['all_terms', 'ranked_candidates'] = 'ranked_candidates'


class ProfileQueryPlan(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)
    contract_version: Literal['boi/profile-query-plan@1']
    filters: tuple[ProfileQueryFilter, ...] = ()
    text_search: ProfileTextSearch | None = None
    select: tuple[str, ...] = Field(min_length=1)
    order_by: str | None = None
    descending: bool = False
    limit: int = Field(default=50, ge=1, le=500)

    @model_validator(mode='after')
    def unique_projection(self):
        if len(set(self.select)) != len(self.select):
            raise ValueError('PROFILE_QUERY_DUPLICATE_PROJECTION')
        return self


def route_profile_declaration(*, route: dict, available_profiles: list[dict]) -> dict:
    """Resolve the exact query Profile for reuse, extension, or new routes."""
    if route.get('branch') in {'extend','new'}:
        declaration=route.get('proposed_profile')
        if not isinstance(declaration,dict):
            raise ValueError('PROFILE_QUERY_PROPOSED_PROFILE_REQUIRED')
        return KnowledgeProfileDeclaration.model_validate(declaration).model_dump(
            mode='json',exclude_none=True)
    if route.get('branch')!='reuse':raise ValueError('PROFILE_QUERY_ROUTE_BRANCH_INVALID')
    selected=route.get('selected_profile_revision')
    matches=[]
    for raw in available_profiles:
        revision=raw.get('revision') if isinstance(raw,dict) else None
        if revision==selected:matches.append(raw.get('declaration'))
    if len(matches)!=1:raise ValueError('PROFILE_QUERY_SELECTED_PROFILE_UNAVAILABLE')
    return KnowledgeProfileDeclaration.model_validate(matches[0]).model_dump(
        mode='json',exclude_none=True)


def profile_query_prompt(*, question: str, profile: dict,
                         queryable_component_ids: list[str] | tuple[str, ...] | None = None) -> str:
    """Expose semantic Profile components, never records or expected results."""
    declaration = KnowledgeProfileDeclaration.model_validate(profile)
    components = []
    queryable=set(queryable_component_ids) if queryable_component_ids is not None else None
    for item in declaration.components:
        if queryable is not None and item.id not in queryable:
            continue
        value = item.model_dump(mode='json', exclude_none=True)
        components.append({key: value[key] for key in (
            'kind', 'id', 'label', 'description', 'role', 'value_kind',
            'cardinality', 'allowed_operators') if key in value})
    material = {'question': question, 'components': components,
                'output_schema': ProfileQueryPlan.model_json_schema()}
    import json
    return '''Translate the user's question into one boi/profile-query-plan@1 JSON object.
Use only listed component IDs. Use the exact keys contract_version, filters, text_search, select, order_by, descending, limit;
each filter uses component_id, operator, value. Filters must use an operator listed for that predicate. Select every
field needed for a complete user answer. Do not add version, object_type, predicate, SQL, physical source names, or
any other key. When the user describes an item without an exact stored value, use text_search over only the relevant
text components; use ranked_candidates for natural discovery and all_terms only for strict literal conjunction.
Text search returns candidates and does not establish semantic equivalence. Do not infer a value, alias, or inverse
relation. Return JSON only.\nMATERIAL:\n''' + json.dumps(material, ensure_ascii=False)


def profile_query_recovery_prompt(*, question: str, profile: dict,
                                  queryable_component_ids, failed_plan: dict,
                                  row_count: int) -> str:
    """Prepare one record-blind retry after a zero-result plan."""
    if row_count != 0:
        raise ValueError('PROFILE_QUERY_RECOVERY_ZERO_RESULT_REQUIRED')
    base=profile_query_prompt(question=question,profile=profile,
        queryable_component_ids=queryable_component_ids)
    import json
    failure={'failed_plan':failed_plan,'observed_result':{'row_count':0}}
    return base+'''\nRECOVERY: The prior plan returned zero rows. No source record or expected answer is
provided. Reconsider exact filters whose stored literal was inferred from natural language. Keep an exact filter only
when the question supplied the stored value for that component. Otherwise use ranked_candidates text_search over
the relevant listed text components. Preserve every requested output field. Return one corrected JSON object only.
FAILED_ATTEMPT:\n'''+json.dumps(failure,ensure_ascii=False)


def profile_record_layout_prompt(*, records: list[dict], features: list[dict], route: dict) -> str:
    """Ask for an explicit disposition of every preserved source row."""
    feature_map = {item.feature_id:item for item in map(SourceFeature.model_validate, features)}
    mapped = {}
    for item in route.get('feature_dispositions') or ():
        if item.get('disposition') == 'mapped':
            feature = feature_map.get(item.get('feature_id'))
            if feature is not None and feature.source_path is not None:
                mapped[feature.source_path] = item['feature_id']
    rows=[]
    for index,record in enumerate(records):
        evidence=record.get('__evidence_refs__') or {}
        row_refs=list(dict.fromkeys(ref for path in mapped
            for ref in evidence.get(path,()) if isinstance(ref,str)))
        if not row_refs:
            row_refs=[ref for ref in record.get('__record_evidence_refs__') or ()
                      if isinstance(ref,str)]
        rows.append({'record_index':index,
            'source_record_locator':record.get('__source_record_locator__'),
            'mapped_values':{mapped[path]:record[path] for path in mapped if path in record},
            'context_fields':[{'field_locator':item.get('field_locator'),
                'value_kind':item.get('value_kind'),'text':str(item.get('text') or '')[:500]}
                for item in record.get('__unmapped_fields__') or ()],
            'evidence_refs':row_refs})
    material={'rows':rows,'output_schema':ProfileRecordLayoutObservation.model_json_schema()}
    import json
    return '''Classify every preserved row for ontology record projection. Return exactly one
boi/profile-record-layout-observation@1 JSON object. Include every record_index exactly once. Use domain_record only
for a complete business record. Use header when values label columns rather than describe an instance. Use
evidence_context for notes or guidance retained as evidence but not queried as instances. Use outside_scope only for
a row truly excluded from this Profile. Copy only evidence_refs supplied for that row and cite at least one. Never
silently omit a row, fill a missing field, infer a record from a filename, or grant semantic/publication authority.
Non-domain rows require a separate review before exclusion. Return JSON only.\nMATERIAL:\n''' + json.dumps(material,ensure_ascii=False)


def adjudicate_profile_record_layout(*, records: list[dict], features: list[dict], route: dict,
                                     observation: dict) -> dict:
    """Validate complete row coverage and exact row evidence without inferring layout."""
    observed=ProfileRecordLayoutObservation.model_validate(observation)
    by_index={item.record_index:item for item in observed.dispositions}
    if len(by_index)!=len(observed.dispositions) or set(by_index)!=set(range(len(records))):
        raise ValueError('PROFILE_RECORD_LAYOUT_COVERAGE_INCOMPLETE')
    feature_map={item.feature_id:item for item in map(SourceFeature.model_validate,features)}
    mapped_paths=[]
    for item in route.get('feature_dispositions') or ():
        if item.get('disposition')=='mapped':
            feature=feature_map.get(item.get('feature_id'))
            if feature is None or feature.source_path is None:
                raise ValueError('PROFILE_RECORD_SOURCE_PATH_REQUIRED')
            mapped_paths.append(feature.source_path)
    if not mapped_paths:raise ValueError('PROFILE_RECORD_MAPPINGS_REQUIRED')
    checked=[]
    for index,record in enumerate(records):
        item=by_index[index]
        exact={ref for path in mapped_paths for ref in
               (record.get('__evidence_refs__') or {}).get(path,())}
        if not exact:exact=set(record.get('__record_evidence_refs__') or ())
        if not exact or not set(item.evidence_refs)<=exact:
            raise ValueError('PROFILE_RECORD_LAYOUT_EVIDENCE_MISMATCH')
        present=set(mapped_paths)&set(record)
        if item.role=='domain_record' and present!=set(mapped_paths):
            raise ValueError('PROFILE_RECORD_PARTIAL_MAPPED_ROW')
        checked.append(item.model_dump(mode='json'))
    output={'contract_version':'boi/profile-record-layout@1',
        'source_snapshot_digest':semantic_digest(records),'dispositions':checked,
        'requires_review':any(item['role']!='domain_record' for item in checked),
        'semantic_truth_proven':False,'publication_authority_granted':False}
    output['layout_digest']=semantic_digest(output)
    return output


def project_profile_records(*, records: list[dict], features: list[dict], route: dict,
                            source_snapshot_digest: str,
                            review: dict | None = None, layout: dict | None = None,
                            layout_review: dict | None = None) -> dict:
    """Project top-level source fields through an exact accepted route."""
    if semantic_digest(records) != source_snapshot_digest:
        raise ValueError('PROFILE_RECORD_SOURCE_SNAPSHOT_MISMATCH')
    route_digest = route.get('route_digest')
    if not route_digest or semantic_digest({k:v for k,v in route.items() if k != 'route_digest'}) != route_digest:
        raise ValueError('PROFILE_RECORD_ROUTE_DIGEST_MISMATCH')
    if route.get('status') == 'requires_semantic_review':
        checked = ProfileRouteReview.model_validate(review)
        if (checked.decision != 'accepted' or checked.route_digest != route_digest
                or checked.source_snapshot_digest != source_snapshot_digest):
            raise ValueError('PROFILE_RECORD_ACCEPTED_REVIEW_REQUIRED')
    feature_map = {item.feature_id: item for item in map(SourceFeature.model_validate, features)}
    if len(feature_map) != len(features):
        raise ValueError('PROFILE_RECORD_DUPLICATE_FEATURE')
    mappings = {}
    evidence = {}
    for item in route.get('feature_dispositions') or ():
        if item.get('disposition') != 'mapped':
            continue
        feature = feature_map.get(item.get('feature_id'))
        if feature is None or feature.source_path is None:
            raise ValueError('PROFILE_RECORD_SOURCE_PATH_REQUIRED')
        component = item.get('component_id')
        if component in mappings:
            raise ValueError('PROFILE_RECORD_COMPONENT_MAPPING_AMBIGUOUS')
        mappings[component] = feature.source_path
        evidence[component] = list(feature.evidence_refs)
    if not mappings:
        raise ValueError('PROFILE_RECORD_MAPPINGS_REQUIRED')
    roles=None
    if layout is not None:
        raw_layout=deepcopy(layout); layout_digest=raw_layout.pop('layout_digest',None)
        if semantic_digest(raw_layout)!=layout_digest:
            raise ValueError('PROFILE_RECORD_LAYOUT_DIGEST_MISMATCH')
        if layout.get('source_snapshot_digest')!=source_snapshot_digest:
            raise ValueError('PROFILE_RECORD_LAYOUT_SOURCE_MISMATCH')
        roles={item['record_index']:item['role'] for item in layout.get('dispositions') or ()}
        if set(roles)!=set(range(len(records))):
            raise ValueError('PROFILE_RECORD_LAYOUT_COVERAGE_INCOMPLETE')
        if layout.get('requires_review'):
            try:
                checked_layout=ProfileRecordLayoutReview.model_validate(layout_review)
            except Exception as exc:
                raise ValueError('PROFILE_RECORD_LAYOUT_ACCEPTED_REVIEW_REQUIRED') from exc
            if (checked_layout.decision!='accepted' or checked_layout.layout_digest!=layout_digest
                    or checked_layout.source_snapshot_digest!=source_snapshot_digest):
                raise ValueError('PROFILE_RECORD_LAYOUT_ACCEPTED_REVIEW_REQUIRED')
    projected = []
    for index, record in enumerate(records):
        if roles is not None and roles[index]!='domain_record':
            continue
        mapped_paths=set(mappings.values())
        present=mapped_paths & set(record)
        if not present:
            continue
        if present != mapped_paths:
            raise ValueError('PROFILE_RECORD_PARTIAL_MAPPED_ROW')
        row_evidence=record.get('__evidence_refs__') or {}
        values = {}
        value_evidence={}
        for component, path in mappings.items():
            if path not in record:
                raise ValueError('PROFILE_RECORD_SOURCE_FIELD_MISSING')
            values[component] = record[path]
            exact=row_evidence.get(path)
            if exact is not None:
                if (not isinstance(exact,list) or not exact
                        or not set(exact) <= set(evidence[component])):
                    raise ValueError('PROFILE_RECORD_ROW_EVIDENCE_OUTSIDE_FEATURE')
                value_evidence[component]=exact
            else:
                value_evidence[component]=evidence[component]
        projected.append({'record_index': index,
            **({'source_record_locator':record.get('__source_record_locator__')}
               if record.get('__source_record_locator__') is not None else {}),
            'values': values,'evidence_refs': value_evidence})
    output = {'contract_version':'boi/profile-record-projection@1',
              'source_snapshot_digest':source_snapshot_digest,
              'route_digest':route_digest,'queryable_component_ids':sorted(mappings),
              'records':projected,
              'publication_authority_granted':False}
    output['projection_digest'] = semantic_digest(output)
    return output


def _compare(actual, operator, expected):
    if operator == 'eq': return actual == expected
    if operator == 'ne': return actual != expected
    try:
        if operator == 'gt': return actual > expected
        if operator == 'gte': return actual >= expected
        if operator == 'lt': return actual < expected
        if operator == 'lte': return actual <= expected
    except TypeError:
        return False
    raise ValueError('PROFILE_QUERY_OPERATOR_UNSUPPORTED')


def execute_profile_query(*, projection: dict, profile: dict, plan: dict) -> dict:
    declaration = KnowledgeProfileDeclaration.model_validate(profile)
    query = ProfileQueryPlan.model_validate(plan)
    components = {item.id:item for item in declaration.components}
    requested = set(query.select) | {item.component_id for item in query.filters}
    if query.text_search:requested.update(query.text_search.component_ids)
    if query.order_by: requested.add(query.order_by)
    if not requested <= set(components):
        raise ValueError('PROFILE_QUERY_COMPONENT_UNAVAILABLE')
    queryable=set(projection.get('queryable_component_ids') or ())
    if queryable and not requested <= queryable:
        raise ValueError('PROFILE_QUERY_COMPONENT_UNBOUND')
    for item in query.filters:
        component = components[item.component_id]
        allowed = getattr(component, 'allowed_operators', ())
        if item.operator not in allowed:
            raise ValueError('PROFILE_QUERY_OPERATOR_NOT_ALLOWED')
    import math,re
    from collections import Counter
    def tokens(value):
        raw=re.findall(r'[0-9A-Za-z가-힣_]+',str(value).casefold())
        expanded=[]
        for token in raw:
            parts=token.split('_')
            expanded.append(token)
            expanded.extend(part for part in parts if part and part!=token)
            # Equipment identifiers commonly join channel numbers to letters
            # (MFC12, Gas16). Preserve the source token and also expose its
            # alphabetic/numeric segments so natural spacing does not change
            # which channel ranks first.
            for part in parts:
                expanded.extend(segment for segment in
                    re.findall(r'[a-z]+|[0-9]+|[가-힣]+',part) if segment!=part)
        return expanded
    terms=[]
    if query.text_search:
        terms=list(dict.fromkeys(tokens(query.text_search.query)))
        if not terms:raise ValueError('PROFILE_QUERY_TEXT_SEARCH_EMPTY')
    candidates=[]
    for record in projection.get('records') or ():
        values=record['values']
        if any(item.component_id not in values or
               not _compare(values[item.component_id], item.operator, item.value)
               for item in query.filters):continue
        counts=Counter(tokens(' '.join(str(values.get(key) or '')
            for key in query.text_search.component_ids))) if query.text_search else Counter()
        candidates.append((record,values,counts))
    document_frequency={term:sum(counts[term]>0 for _,_,counts in candidates) for term in terms}
    denominator=sum(math.log((len(candidates)+1)/(document_frequency[term]+1))+1 for term in terms) or 1
    rows=[]
    for record,values,counts in candidates:
        matched=[]
        if query.text_search:
            matched=[term for term in terms if counts[term]]
            if ((query.text_search.mode=='all_terms' and len(matched)!=len(terms))
                    or (query.text_search.mode=='ranked_candidates' and not matched)):
                continue
            score=sum((math.log((len(candidates)+1)/(document_frequency[term]+1))+1)
                *(1+math.log(counts[term])) for term in matched)/denominator
        rows.append({'values':{key:values.get(key) for key in query.select},
                     'evidence_refs':{key:record['evidence_refs'][key] for key in query.select
                                      if key in record['evidence_refs']},
                     'record_index':record['record_index'],
                     **({'source_record_locator':record['source_record_locator']}
                        if record.get('source_record_locator') is not None else {}),
                     **({'retrieval':{'matched_terms':matched,'query_term_count':len(terms),
                         'score':score,'scoring':'profile_scoped_tfidf@1',
                         'semantic_match_verified':False}}
                        if query.text_search else {})})
    if query.order_by:
        rows.sort(key=lambda row:(row['values'].get(query.order_by) is None,
                                  row['values'].get(query.order_by)), reverse=query.descending)
    elif query.text_search and query.text_search.mode=='ranked_candidates':
        rows.sort(key=lambda row:(-row['retrieval']['score'],row['record_index']))
    rows=rows[:query.limit]
    return {'contract_version':'boi/profile-query-result@1','plan':query.model_dump(mode='json'),
            'projection_digest':projection['projection_digest'],'row_count':len(rows),'rows':rows,
            'complete':True,'retrieval_candidates':query.text_search is not None,
            'semantic_match_verified':False if query.text_search else None}
