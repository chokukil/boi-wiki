"""Common immutable native Check/Run validation; this grants no caller access."""
from .ledger import RecordKind, record_digest
from .semantic_binding_contract import semantic_digest


def checked_identity_reference(reader, stable_id):
    """Only the server-owned reader context can resolve a knowledge identity."""
    from .semantic_binding_contract import RevisionRef
    resolver=getattr(reader,'resolve_identity',None)
    if resolver is None:
        resolver=getattr(getattr(reader,'__self__',None),'resolve_identity',None)
    if not callable(resolver):raise ValueError('NATIVE_CHECK_IDENTITY_RESOLVER_UNAVAILABLE')
    return RevisionRef.model_validate(resolver(stable_id).model_dump(mode='json'))


class NativeMechanicalRecords:
    def _receipt(self, saved, binding):
        if saved.get('input') != binding or saved.get('state') != 'completed':
            raise ValueError('LOCAL_CHECK_RECEIPT_BINDING_MISMATCH')
        receipt = self.intake.ledger.read(saved['check_ref']['ref'])
        if (receipt.kind != RecordKind.CHECK or receipt.authority != 'qualification_service'
                or record_digest(receipt.record_id) != saved['check_ref']['revision_digest']
                or semantic_digest(receipt.payload) != saved['payload_digest']
                or receipt.payload.get('input') != binding
                or receipt.payload.get('run_ref') != saved['run_ref']):
            raise ValueError('LOCAL_CHECK_RECEIPT_BINDING_MISMATCH')
        run = self.intake.ledger.read(saved['run_ref'])
        if run.kind != RecordKind.RUN or run.authority != 'executor' or run.payload != binding:
            raise ValueError('LOCAL_CHECK_EXECUTION_BINDING_MISMATCH')
        report = receipt.payload['report']
        if (report['target_revision'] != binding['target_revision']
                or report['confirmation_ref'] != binding['confirmation_ref']
                or report['checker_release_digest'] != binding['checker_release_digest']
                or semantic_digest(report['checker_release']) != binding['checker_release_digest']
                or report['intended_uses'] != binding['intended_uses']):
            raise ValueError('LOCAL_CHECK_REPORT_BINDING_MISMATCH')
        return report

    def _current_result(self, read_revision, change, key, saved, binding):
        from .semantic_binding_contract import RevisionRef
        report = self._receipt(saved,binding)
        for item in report.get('identity_inputs',[]):
            if checked_identity_reference(read_revision,item['stable_id']).model_dump(mode='json')!=item['revision']:
                raise ValueError('LOCAL_CHECK_IDENTITY_TARGET_CHANGED')
        read_revision(RevisionRef.model_validate(binding['target_revision']))
        for item in report['native_inputs']:
            record, asset = read_revision(RevisionRef.model_validate(item['revision']))
            if (asset.content_digest != item['content_digest']
                    or record.payload['source_manifest_digest'] != item['source_manifest_digest']):
                raise ValueError('LOCAL_CHECK_CURRENT_INPUT_CHANGED')
        # Full pointer values, requirements and release manifest stay in the
        # immutable Check. The transport returns bounded repair diagnostics.
        summary = {k:report[k] for k in ('target_revision','checker_release_digest','outcome','checks',
            'publication_granted','use_qualification_granted','semantic_verdict_issued')}
        summary['use_results'] = [{k:u[k] for k in ('purpose','status','reasons','usable','semantic_status')}
                                  for u in report['use_results']]
        return {'object_id':change['object_id'],'execution_ref':key,'state':'completed',
            'check_ref':saved['check_ref'],'report':summary,'query_ready':False}
