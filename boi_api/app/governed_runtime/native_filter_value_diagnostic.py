"""Bounded source-value evidence for an empty native query root.

This only tests caller-supplied equality literals against the same authorized
source/table and current bound properties. It never rewrites a candidate or
turns zero source matches into proof that a business fact is absent.
"""
from .multi_result_query_gateway import _identifier


def diagnose_empty_filter_values(*, candidate, bundle, scope, execute,
        max_filters=8, max_alternatives=8, max_variants=5):
    domains={entry.entry_id:entry.payload for entry in bundle.domain_entries}
    mappings={}
    for entry in bundle.mapping_entries:
        domain_ref=entry.payload.get('domain_ref')
        if not domain_ref or entry.availability!='bound' or entry.physical is None:
            continue
        if domain_ref in mappings:
            raise ValueError('FILTER_DIAGNOSTIC_MAPPING_AMBIGUOUS')
        mappings[domain_ref]=entry

    def source_mapping(property_ref):
        entry=mappings.get(property_ref)
        if entry is None:return None
        physical=entry.physical
        if (physical.source not in scope.allowed_sources
                or physical.table not in scope.allowed_tables):
            return None
        return entry

    def count(table,column,value):
        sql='SELECT COUNT(*) AS n FROM '+_identifier(table)+' WHERE '+_identifier(column)+' = ?'
        row=execute(sql,(value,)).fetchone()
        if row is None or type(row['n']) is not int or row['n']<0:
            raise ValueError('FILTER_DIAGNOSTIC_COUNT_INVALID')
        return row['n']

    rows=[];queries=0
    filters=candidate.filters
    for index,item in enumerate(filters[:max_filters]):
        value=item.value
        if item.operator!='eq' or not isinstance(value,str) or not value or len(value)>256:
            continue
        selected=source_mapping(item.property_id)
        domain=domains.get(item.property_id) or {}
        if selected is None or domain.get('kind') not in (None,'PropertyDefinition'):
            continue
        owner=domain.get('owner_ref')
        if not owner:continue
        table=selected.physical.table;column=selected.physical.column
        exact=count(table,column,value);queries+=1
        variants=[];alternatives=[];truncated=False
        if exact==0 and value.isascii():
            sql=('SELECT '+_identifier(column)+' AS value,COUNT(*) AS n FROM '
                +_identifier(table)+' WHERE '+_identifier(column)+' COLLATE NOCASE = ?'
                +' AND '+_identifier(column)+' COLLATE BINARY != ? GROUP BY '
                +_identifier(column)+' COLLATE BINARY ORDER BY n DESC,value LIMIT ?')
            fetched=execute(sql,(value,value,max_variants+1)).fetchall();queries+=1
            truncated=len(fetched)>max_variants
            variants=[{'value':row['value'],'stored_rows':row['n']}
                for row in fetched[:max_variants]]
        if exact==0 and not variants:
            eligible=[]
            for other_ref,other in mappings.items():
                if other_ref==item.property_id or (domains.get(other_ref) or {}).get('owner_ref')!=owner:
                    continue
                physical=other.physical
                if (physical.source==selected.physical.source and physical.table==table
                        and (domains.get(other_ref) or {}).get('value_type')=='string'):
                    eligible.append((other_ref,other))
            for other_ref,other in sorted(eligible)[:max_alternatives]:
                matched=count(table,other.physical.column,value);queries+=1
                if matched:
                    alternatives.append({'property_ref':other_ref,
                        'mapping_revision_digest':other.revision_digest,
                        'source_table':table,'source_column':other.physical.column,
                        'exact_stored_rows':matched})
            truncated=truncated or len(eligible)>max_alternatives
        rows.append({'filter_index':index,'property_ref':item.property_id,
            'mapping_revision_digest':selected.revision_digest,
            'source_table':table,'source_column':column,
            'submitted_value':value,'exact_stored_rows':exact,
            'sqlite_nocase_variants':variants,
            'same_owner_exact_value_properties':alternatives,
            'alternatives_truncated':truncated})
    status=('possible_binding_mismatch' if any(
        row['sqlite_nocase_variants'] or row['same_owner_exact_value_properties']
        for row in rows) else 'no_binding_mismatch_evidence')
    return {'contract_version':'boi/native-empty-filter-diagnostic@1',
        'source_snapshot_digest':scope.source_snapshot_digest,
        'filter_diagnostics':rows,'diagnostic_queries_executed':queries,
        'diagnostic_status':status,
        'scope_limit':'same authorized source and table; SQLite NOCASE is ASCII-only',
        'semantic_truth_proven':False,'business_absence_proven':False,
        'status':'PROVISIONAL'}
