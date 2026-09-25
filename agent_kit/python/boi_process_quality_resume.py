"""Quality continuation eligibility without importing an MCP host runtime."""
from .boi_process_response_review import RESPONSE_REVIEW_VERSION

def quality_isolation_revalidation_allowed(packet,binding):
    """Continue a terminal tool-use failure once under corrected isolation."""
    report=packet.get('response_review',{});attempts=report.get('attempts',[])
    if not attempts:return False
    attempt=attempts[-1];quality=attempt.get('quality_review') or {}
    provider=quality.get('provider') or {};check=binding.get('check',{})
    counts=check.get('statement_counts',{});citations=check.get('citation_counts',{})
    return (binding.get('status')=='bound'
        and report.get('external_execution_state')=='known'
        and report.get('review_contract_version')==RESPONSE_REVIEW_VERSION
        and check.get('review_failure')=='quality_provider_unresolved'
        and check.get('diagnostic')=='STRUCTURED_PROVIDER_UNEXPECTED_TOOL_USE'
        and provider.get('provider')=='codex' and provider.get('status')=='unexpected_tool_use'
        and provider.get('execution_isolation_version') is None
        and attempt.get('provider',{}).get('status')=='completed'
        and set(counts)=={'supported'} and counts['supported']>0
        and citations=={'full':counts['supported']}
        and check.get('failures')==[] and check.get('unanswered_requests')==[]
        and not any(a.get('repair') for a in attempts))


def quality_contract_revalidation_allowed(packet,binding):
    from .boi_process_explanation_quality import QUALITY_VERSION,SUPPORTED_QUALITY_VERSIONS,QUALITY_PRESENTATION_VERSION
    report=packet.get('response_review',{});attempts=report.get('attempts',[])
    old=(attempts[-1].get('quality_review') or {}).get('contract_version') if attempts else None
    presentation=(attempts[-1].get('quality_review') or {}).get('presentation_contract_version') if attempts else None
    presentation_changed=presentation in tuple('boi/process-explanation-quality-presentation@'+str(i) for i in (1,2,3)) and presentation!=QUALITY_PRESENTATION_VERSION
    if quality_isolation_revalidation_allowed(packet,binding):return True
    return (binding.get('status')=='bound' and binding.get('check',{}).get('assessment_complete')
        and binding['check'].get('model_assessment_accepts_source_answers') is True
        and report.get('external_execution_state')=='known' and report.get('review_contract_version')==RESPONSE_REVIEW_VERSION
        and old in SUPPORTED_QUALITY_VERSIONS and (old!=QUALITY_VERSION or presentation_changed) and not any(a.get('repair') for a in attempts))
