"""Source-record admission for externally proposed knowledge work.

This checks which immutable evidence was used, never whether a claim follows
from that evidence. Domain binders retain quotation and semantic-type checks.
"""
from .ledger import RecordKind, record_digest


def _quoted_spans(content):
    contract = content.get('contract_version', '')
    if contract in ('boi/bound-process-meaning@1', 'boi/bound-process-meaning@2'):
        return {binding['span_ref'] for binding in content['bindings']}
    if contract not in ('boi/common-meaning@1', 'boi/svid-native-interpretation@1'):
        raise ValueError('KNOWLEDGE_WORK_CONTENT_BINDING_UNSUPPORTED')

    def walk(value):
        if isinstance(value, dict):
            if 'quote' in value:
                if isinstance(value.get('span'), dict):
                    yield value['span']['ref']
                elif value.get('span_ref'):
                    yield value['span_ref']
            for child in value.values():
                yield from walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                yield from walk(child)

    return set(walk(content))


def validate_change_evidence(*, ledger, authorization, work, attempt, change, content=None, span_equivalence=None):
    if change.operation == 'unresolved':
        return
    declared = {ref.ref: ref for ref in change.evidence_spans}
    if len(declared) != len(change.evidence_spans):
        raise ValueError('KNOWLEDGE_WORK_EVIDENCE_DUPLICATE')
    sources = {source['artifact_ref']: source for source in work['sources']}
    spans = {}
    for ref in change.evidence_spans:
        span = ledger.read(ref.ref)
        payload = span.payload
        source = sources.get(payload.get('artifact_ref'))
        if (span.kind != RecordKind.EVIDENCE_SPAN or record_digest(span.record_id) != ref.revision_digest
                or source is None or payload.get('source_revision_digest') != source['digest']
                or payload.get('employee_id') != authorization.principal
                or payload.get('policy_digest') != authorization.policy_digest):
            raise ValueError('KNOWLEDGE_WORK_EVIDENCE_ACCESS_DENIED')
        spans[ref.ref] = payload
    # A reuse explicitly compares this source record with an existing definition.
    # New payloads must actually quote their primary records; merely listing an
    # unrelated own-row span cannot camouflage quotations from a different row.
    quoted = _quoted_spans(content) if content is not None else set(declared)
    if not quoted <= declared.keys():
        raise ValueError('KNOWLEDGE_WORK_QUOTED_SPAN_NOT_DECLARED')
    own_spans = set(attempt['source_span_refs'])
    # Only a server-verified same-source projection correspondence is accepted;
    # this argument never comes from the authored content or request fields.
    span_equivalence = span_equivalence or {}
    covered = {spans[ref]['record_locator'] for ref in quoted
               if span_equivalence.get(ref, ref) in own_spans
               if spans[ref]['artifact_ref'] == attempt['source_ref']['artifact_ref']}
    records = [record['record_locator'] for record in attempt['result']['record_outcomes']
               if change.change_id in record['change_ids']]
    if not records or not set(records) <= covered:
        raise ValueError('KNOWLEDGE_WORK_PRIMARY_RECORD_EVIDENCE_REQUIRED')
