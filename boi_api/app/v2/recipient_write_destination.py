"""Recipient-bound new Private writes; this contract never delegates identity."""
from . import recipient_delivery_access
from ..governed_runtime.knowledge_space_contract import KnowledgeSpaceTarget, admit_space_intent


def require_recipient_destination(principal, authorization, selector):
    if selector != 'development_default':
        raise ValueError('DELIVERY_RECIPIENT_NOT_BOUND')
    recipient = recipient_delivery_access.development_recipient()
    if recipient is None:
        raise ValueError('DELIVERY_RECIPIENT_NOT_BOUND')
    if principal.employee_id != recipient.employee_id or authorization.principal != recipient.employee_id:
        raise ValueError('DELIVERY_RECIPIENT_WRITE_IDENTITY_REQUIRED')
    # Keep the actual caller's scopes, roles and source policy. Do not copy the
    # recipient resolver's authority or expand source visibility to enable a write.
    if authorization.visibility != 'private' or authorization.team_id:
        raise ValueError('DELIVERY_RECIPIENT_PRIVATE_DESTINATION_REQUIRED')
    admit_space_intent(principal, KnowledgeSpaceTarget())
    return {'contract_version':'boi/recipient-write-destination@1', 'recipient':selector,
        'owner':recipient.employee_id, 'target_space':{'visibility':'private','team_id':None},
        'authority':'authenticated_same_identity', 'grants_access':False}
