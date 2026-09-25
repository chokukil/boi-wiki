"""Explicit, snapshot-proven superkey equivalence for one-object projections.

Never changes a root, filter, projected value, relationship or aggregation.
This policy does NOT apply to grouping, latest, joins, collections or metrics.
"""
import hashlib
import json
from pathlib import Path

from .ledger import RecordKind
from .semantic_intent import SemanticIntentResolver


def _digest(value):
    return 'sha256:'+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def prove_identity_grain(*,context,gateway,occurred_at):
    original=context.resolution
    candidate=context.resolved_intent.candidate
    if (len(candidate.entity_ids)!=1 or candidate.aggregations or candidate.metric_ids
            or candidate.ambiguity_alternatives or candidate.unresolved_terms
            or candidate.dimensions!=candidate.grain):
        return original,None
    by_id={e.entry_id:e for e in context.bundle.domain_entries}
    root=candidate.entity_ids[0]
    obj=by_id[root]
    grain=tuple(obj.payload.get('logical_grain') or ())
    if (len(grain)!=1 or obj.payload.get('identity_property_ref')!=grain[0]
            or not set(grain)<set(candidate.grain)):
        return original,None
    referenced=SemanticIntentResolver._referenced_ids(candidate)-{root}
    if any(ref not in by_id or by_id[ref].payload.get('kind')!='PropertyDefinition'
           or by_id[ref].payload.get('owner_ref')!=root for ref in referenced):
        return original,None
    mapping_by_ref={}
    for ref in referenced:
        found=[e for e in context.bundle.mapping_entries if e.payload.get('domain_ref')==ref
               and e.availability=='bound' and e.physical is not None]
        if len(found)!=1: return original,None
        mapping_by_ref[ref]=found[0]
    if len({(m.physical.source,m.physical.table) for m in mapping_by_ref.values()})!=1:
        return original,None
    key_evidence=gateway.profile_identity_key(context=context,property_ref=grain[0])
    if key_evidence['status']!='PASS': return original,None
    candidate_after=candidate.model_copy(update={'grain':grain,'dimensions':grain})
    candidate_digest=_digest(candidate_after.model_dump(mode='json'))
    proof={'contract':'boi/snapshot-identity-grain-equivalence@1',
           'code_digest':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           'source_resolution_digest':original.receipt_digest,
           'source_candidate_digest':original.candidate_digest,'result_candidate_digest':candidate_digest,
           'before_grain':list(candidate.grain),'after_grain':list(grain),
           'preserved_fields_digest':_digest(candidate.model_dump(mode='json',exclude={'grain','dimensions'})),
           'domain_revision_digests':{ref:by_id[ref].revision_digest for ref in sorted(referenced|{root})},
           'mapping_revision_digests':{ref:m.revision_digest for ref,m in sorted(mapping_by_ref.items())},
           'key_evidence':key_evidence,'result':'EQUIVALENT_SINGLE_OBJECT_SUPERKEY'}
    proof['receipt_digest']=_digest(proof)
    gateway._semantic_ledger.append(RecordKind.CHECK,proof,authority='mapping_validator',occurred_at=occurred_at)
    resolved=context.resolved_intent.model_copy(update={'candidate':candidate_after,'intent_digest':candidate_digest})
    values=original.model_dump(mode='json',exclude={'receipt_digest'})
    values.update(candidate_digest=candidate_digest,resolved_intent=resolved.model_dump(mode='json'),
                  semantic_transformations=[proof])
    return type(original).model_validate({**values,'receipt_digest':_digest(values)}),proof
