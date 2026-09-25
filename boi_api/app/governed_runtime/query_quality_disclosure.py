"""Deterministic binding of requested quality summaries to approved sidecars.

No policy/SQL/count is authored by the model. ROWS is a distinct capability gap,
never silently answered with counts. Missing/ambiguous/stale evidence blocks.
"""
import hashlib
import json
from pathlib import Path


def _digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def validate_quality_requests(*, candidate, relationships, quality_receipts, schema_digest):
    bound = []
    for request in candidate.quality_requests:
        if request.detail != 'SUMMARY':
            raise ValueError('QUALITY_RECORD_ACCESS_CONTRACT_REQUIRED')
        matches = [item for item in relationships
                   if request.subject_object_id in {item.left_endpoint_ref, item.right_endpoint_ref}
                   and (request.relationship_id is None or item.contract_id == request.relationship_id)]
        if not matches:
            raise ValueError('QUALITY_DISCLOSURE_RELATIONSHIP_MISSING')
        if len(matches) != 1:
            raise ValueError('QUALITY_DISCLOSURE_RELATIONSHIP_AMBIGUOUS')
        relationship = matches[0]
        if request.subject_object_id != relationship.right_endpoint_ref:
            raise ValueError('QUALITY_OBSERVATION_SCOPE_NOT_DECLARED')
        receipts = [item for item in quality_receipts if item.relationship_contract_digest == relationship.contract_digest]
        if len(receipts) != 1 or not receipts[0].evidence_digest:
            raise ValueError('QUALITY_DISCLOSURE_RECEIPT_MISSING')
        receipt = receipts[0]
        if relationship.schema_snapshot_digest != schema_digest or receipt.schema_snapshot_digest != schema_digest:
            raise ValueError('QUALITY_DISCLOSURE_SCHEMA_MISMATCH')
        if receipt.applied_orphan_policy != relationship.orphan_policy:
            raise ValueError('QUALITY_DISCLOSURE_POLICY_MISMATCH')
        bound.append({'request': request.model_dump(mode='json'), 'relationship_digest': relationship.contract_digest,
                      'quality_receipt_digest': receipt.receipt_digest, 'evidence_digest': receipt.evidence_digest})
    values = {'contract': 'boi/query-quality-disclosure@1', 'status': 'PASS',
              'candidate_digest': _digest(candidate.model_dump(mode='json')), 'schema_digest': schema_digest,
              'bound_requests': bound, 'evidence_digests': [item['evidence_digest'] for item in bound],
              'evaluator_code_digest': 'sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return {**values, 'receipt_digest': _digest(values)}
