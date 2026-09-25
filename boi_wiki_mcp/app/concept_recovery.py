"""Standalone MCP wire recovery contract; parity tested against portable client."""
CONCEPT_RECOVERY_ACTIONS = {
    'KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED': 'discover_reviewed_spelling',
    'KNOWLEDGE_REUSE_ROLE_OR_SOURCE_SCOPE_EMPTY': 'inspect_role_and_source_scope',
}


def concept_recovery(status, reason):
    """Only authorized conflict categories; never copy server prose or candidates."""
    if status != 409 or not isinstance(reason, str) or reason not in CONCEPT_RECOVERY_ACTIONS:
        return None
    return {'action': CONCEPT_RECOVERY_ACTIONS[reason],
        'automatic_substitution': False, 'fact_established': False,
        'guidance': ('Read the current reviewed spelling and its source scope; do not invent an alias.'
            if reason == 'KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED' else
            'Compare the requested relation and source scope with the reviewed evidence; do not change either silently.'),
        'user_explanation': ('이 표현을 선택한 검토 범위의 개념에 연결하지 못했습니다. 확인된 표기를 찾아보거나 뜻을 확인해야 합니다.'
            if reason == 'KNOWLEDGE_REUSE_SPELLING_NOT_DECLARED' else
            '선택한 근거 범위에서 요청한 관계를 확인하지 못했습니다. 관계와 원천 범위를 확인해야 합니다.'),
        'presentation': 'Explain the relevant limitation in ordinary language; do not display internal reason or HTTP codes. Keep independently supported answer parts.'}
