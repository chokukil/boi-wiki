"""Server-resolved delivery target; exact existing human read gates, no grants."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field
from ..governed_runtime.semantic_binding_contract import FrozenContract, RevisionRef
from ..governed_runtime.knowledge_published_read import PublishedDocumentRead, PublishedSourceRead
from ..auth import auth_mode, resolve_identity
from ..public_links import configured_public_links
from .models import Principal


class RecipientAccessRequest(FrozenContract):
    recipient: Literal["development_default"]
    urls: tuple[str, ...] = Field(min_length=1, max_length=64)


def development_recipient():
    if auth_mode() != "dev":
        return None
    identity = resolve_identity()
    if identity.auth_source != "dev":
        return None
    return Principal(employee_id=identity.employee_id, display_name=identity.display_name,
                     teams=list(identity.teams), roles=list(identity.roles), auth_source=identity.auth_source)


def exact_human_read(intake, actor, url):
    parsed = urlsplit(url)
    origin = configured_public_links().origin
    if (parsed.netloc and (parsed.scheme + "://" + parsed.netloc) != origin
            or parsed.query or parsed.username or parsed.password or "\\" in url):
        raise ValueError("RECIPIENT_TARGET_UNSUPPORTED")
    parts = parsed.path.strip("/").split("/")
    if parts[:2] == ["knowledge", "records"] and len(parts) in (3, 5):
        digest = "sha256:" + parts[2]
        revision = RevisionRef(ref="KnowledgeRevision:" + digest, revision_digest=digest)
        if len(parts) == 3:
            request = PublishedDocumentRead(revision=revision)
        elif parts[3] == "sources":
            request = PublishedSourceRead(revision=revision, binding_index=int(parts[4]))
        else:
            raise ValueError("RECIPIENT_TARGET_UNSUPPORTED")
        intake.published_document(actor, request, model_input=False)
    elif len(parts) == 4 and parts[0] == "c":
        from .native_composition_result import read_composition_citation_view
        read_composition_citation_view(intake, actor, parts[1], int(parts[2]), int(parts[3]))
    elif len(parts) == 2 and parts[0] == "native-results":
        from .native_answer_delivery import read_native_answer_page
        from .domain_intake import DomainAssetReadRequest
        digest = "sha256:" + parts[1]
        read_native_answer_page(intake, actor, DomainAssetReadRequest(
            revision=RevisionRef(ref="KnowledgeRevision:"+digest,revision_digest=digest),lane="provisional"))
    elif len(parts) == 2 and parts[0] == "native-compositions":
        from .native_composition_result import read_native_composition
        read_native_composition(intake, actor, {"composition_ref": "sha256:" + parts[1]})
    else:
        raise ValueError("RECIPIENT_TARGET_UNSUPPORTED")


# Only established access denials are denials. Missing content, unsupported routes,
# stale revisions and infrastructure failures remain unknown.
DENIALS = {"KNOWLEDGE_SPACE_ACCESS_DENIED", "KNOWLEDGE_SOURCE_ACCESS_DENIED",
           "KNOWLEDGE_SOURCE_CITE_NOT_AUTHORIZED", "KNOWLEDGE_SPACE_CONTENT_USE_NOT_AUTHORIZED"}


def check_recipient_access(intake, caller, request):
    from agent_kit.python.boi_recipient_citations import recipient_access
    request = RecipientAccessRequest.model_validate(request)
    recipient = development_recipient()
    reasons = {}
    def check(url):
        # A caller cannot use this endpoint to discover another actor's content.
        try:
            exact_human_read(intake, caller, url)
        except Exception as error:
            same = recipient is not None and all(getattr(caller,k)==getattr(recipient,k)
                for k in ("employee_id","auth_source","teams","roles"))
            if same and isinstance(error,ValueError) and str(error) in DENIALS:
                reasons[url] = "recipient_current_gate_denied"
                return False
            reasons[url] = "caller_target_not_verified"
            return None
        if recipient is None:
            reasons[url] = "recipient_not_bound"
            return None
        try:
            exact_human_read(intake, recipient, url)
            reasons[url] = "recipient_current_gate_passed"
            return True
        except ValueError as error:
            denied = str(error) in DENIALS
            reasons[url] = "recipient_current_gate_denied" if denied else "recipient_check_incomplete"
            return False if denied else None
        except Exception:
            reasons[url] = "recipient_check_incomplete"
            return None
    access = recipient_access(request.urls, check=check)
    for url, value in access.items():
        value["reason"] = reasons[url]
    return {"contract_version": "boi/recipient-access@1", "recipient": request.recipient,
            "recipient_identity": ({"employee_id": recipient.employee_id, "auth_source": recipient.auth_source}
                                   if recipient else None),
            "scope": "server development default browser without credentials; not another signed-in session",
            "access": access, "grants_access": False}
