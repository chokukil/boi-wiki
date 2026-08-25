"""FastAPI adapter for the Science Verifier trust boundary."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import ConfigDict, Field, model_validator

from boi_api.app.auth import AuthIdentity
from boi_api.app.science.authorization import (
    ScienceAuthorization,
    ScienceAuthorizationError,
)
from boi_api.app.science.digests import sha256_digest
from boi_api.app.science.exceptions import ScienceCatalogError, ScienceOperationalError
from boi_api.app.science.llm import (
    LLMClaimCandidate,
    ScienceInterpretationUnavailable,
)
from boi_api.app.science.models import (
    ClaimSubmissionClientKind,
    ReleaseSelection,
    ScienceModel,
    SourceSpan,
    VerificationReport,
)
from boi_api.app.science.profile import validate_sci_profile_metadata
from boi_api.app.science.qualification import qualify_release_candidate
from boi_api.app.science.reports import render_report_markdown, render_report_pdf
from boi_api.app.science.service import (
    ScienceConfirmationRequired,
    ScienceIdempotencyConflict,
    submitted_revision_document_ref,
)
from boi_api.app.science.storage import (
    ImmutableScienceRecordError,
    ProposalKind,
    ScienceTransactionPendingError,
)

IdentityDependency = Callable[..., AuthIdentity]
RolesResolver = Callable[[str], Sequence[str]]
DocumentLoader = Callable[[AuthIdentity, str], str | None]
BoiAccessCheck = Callable[[AuthIdentity, str], bool]
ReportAccessCheck = Callable[[AuthIdentity, VerificationReport], bool]


@dataclass(frozen=True)
class ScienceRouteDependencies:
    authorization: ScienceAuthorization
    service_provider: Callable[[], Any]
    runtime_store: Any
    catalog: Any
    boi_root: Path | None
    current_identity_dependency: IdentityDependency
    roles_for: RolesResolver
    load_document: DocumentLoader
    can_read_boi: BoiAccessCheck
    can_export_boi: BoiAccessCheck
    release_manager: Any | None = None
    can_read_report: ReportAccessCheck | None = None
    can_export_report: ReportAccessCheck | None = None


class _RequestModel(ScienceModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class InterpretRequest(_RequestModel):
    document: str | None = None
    document_ref: str | None = None
    selection: SourceSpan | None = None
    request_id: str = Field(min_length=1, max_length=256)
    idempotency_key: str = Field(min_length=8, max_length=256)

    @model_validator(mode="after")
    def exact_source(self) -> "InterpretRequest":
        if bool(self.document) == bool(self.document_ref):
            raise ValueError("exactly one document or document_ref is required")
        return self


class DetectAliasesRequest(_RequestModel):
    document: str | None = None
    document_ref: str | None = None
    selection: SourceSpan | None = None
    request_id: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def exact_source(self) -> "DetectAliasesRequest":
        if bool(self.document) == bool(self.document_ref):
            raise ValueError("exactly one document or document_ref is required")
        return self


class SubmittedDocumentLineage(_RequestModel):
    document_ref: str = Field(pattern=r"^boi:[A-Za-z0-9._:-]+$")
    document_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class SubmitClaimRequest(_RequestModel):
    document: str | None = None
    document_ref: str | None = None
    selection: SourceSpan | None = None
    client_kind: ClaimSubmissionClientKind
    candidate: LLMClaimCandidate
    idempotency_key: str = Field(min_length=8, max_length=256)
    supersedes_claim_id: str | None = Field(default=None, min_length=1)
    source_lineage: SubmittedDocumentLineage | None = None

    @model_validator(mode="after")
    def exact_source(self) -> "SubmitClaimRequest":
        if bool(self.document) == bool(self.document_ref):
            raise ValueError("exactly one document or document_ref is required")
        if self.source_lineage is not None and (
            not self.document or self.supersedes_claim_id is None
        ):
            raise ValueError(
                "source_lineage requires a raw document and supersedes_claim_id"
            )
        return self


class ConfirmInterpretationRequest(_RequestModel):
    claim_ids: list[str] = Field(min_length=1)
    idempotency_key: str = Field(min_length=8, max_length=256)
    user_confirmed: Literal[True]


class VerifyClaimRequest(_RequestModel):
    interpretation_id: str = Field(min_length=1)
    release_selection: ReleaseSelection


class VerifyDocumentRequest(_RequestModel):
    interpretation_id: str = Field(min_length=1)
    release_selection: ReleaseSelection
    idempotency_key: str = Field(min_length=8, max_length=256)


class ProposalPayload(_RequestModel):
    domain: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    kind: ProposalKind
    payload: dict[str, Any]


class CreateProposalRequest(_RequestModel):
    proposal: ProposalPayload
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=256)
    user_confirmed: Literal[True]

    @model_validator(mode="after")
    def exact_request_digest(self) -> "CreateProposalRequest":
        if self.request_digest != sha256_digest(self.proposal):
            raise ValueError("proposal request digest is not exact")
        return self


class ReviewProposalRequest(_RequestModel):
    action: Literal["approve"]
    proposal_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    user_confirmed: Literal[True]


class ValidateObjectRequest(_RequestModel):
    source: dict[str, Any] | None = None
    evidence: dict[str, Any] | None = None
    knowledge: dict[str, Any] | None = None


class QualifyRuleRequest(_RequestModel):
    release_id: str = Field(min_length=1)
    rule_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    case_ids: list[str] = Field(min_length=1)
    case_set_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ValidateReleaseRequest(_RequestModel):
    release_id: str = Field(min_length=1)
    release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    holdout_manifest_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ReleaseMutationRequest(_RequestModel):
    release_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=256)
    user_confirmed: Literal[True]


def _json_model(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=False)
    raise ScienceOperationalError("Science service returned an invalid packet")


def _closed_http_error(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    if isinstance(error, ScienceAuthorizationError):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "science_access_denied",
                "message": "Science operation is not authorized.",
            },
        ) from None
    if isinstance(error, ScienceInterpretationUnavailable):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "science_interpretation_unavailable",
                "diagnostic_code": error.diagnostic_code,
                "message": "Scientific interpretation is temporarily unavailable.",
            },
        ) from None
    if isinstance(
        error,
        (
            ScienceConfirmationRequired,
            ScienceIdempotencyConflict,
            ImmutableScienceRecordError,
        ),
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "science_confirmation_or_identity_conflict",
                "message": "Science operation requires a new explicit confirmation.",
            },
        ) from None
    if isinstance(error, ScienceTransactionPendingError):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "science_transaction_pending",
                "message": "Science operation is pending durable recovery.",
            },
        ) from None
    if isinstance(error, (ScienceOperationalError, ScienceCatalogError)):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "science_operational_unavailable",
                "message": (
                    "No qualified Science Release is available for this operation."
                ),
            },
        ) from None
    raise HTTPException(
        status_code=500,
        detail={
            "code": "science_internal_error",
            "message": "Science operation failed closed.",
        },
    ) from None


def _invoke(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except Exception as error:
        _closed_http_error(error)


def create_science_router(dependencies: ScienceRouteDependencies) -> APIRouter:
    """Create one router without importing the monolithic application module."""

    router = APIRouter()

    def science_identity(
        identity: AuthIdentity = Depends(dependencies.current_identity_dependency),
    ) -> AuthIdentity:
        try:
            if identity.auth_source == "service_token":
                raise ScienceAuthorizationError(
                    "interactive user identity required for Science Verifier"
                )
            dependencies.authorization.require_access(
                identity,
                dependencies.roles_for(identity.employee_id),
            )
        except Exception as error:
            _closed_http_error(error)
        return identity

    def service() -> Any:
        return _invoke(dependencies.service_provider)

    def science_admin(
        identity: AuthIdentity = Depends(science_identity),
    ) -> AuthIdentity:
        try:
            dependencies.authorization.require_admin(
                identity,
                roles_for=lambda trusted_identity: dependencies.roles_for(
                    trusted_identity.employee_id
                ),
            )
        except Exception as error:
            _closed_http_error(error)
        return identity

    def require_read(identity: AuthIdentity, boi_ref: str) -> None:
        if not dependencies.can_read_boi(identity, boi_ref):
            _closed_http_error(ScienceAuthorizationError("read denied"))

    def require_export(identity: AuthIdentity, boi_ref: str) -> None:
        if not dependencies.can_export_boi(identity, boi_ref):
            _closed_http_error(ScienceAuthorizationError("export denied"))

    def report_for(
        identity: AuthIdentity,
        report_id: str,
        *,
        export: bool = False,
    ) -> VerificationReport:
        report = _invoke(lambda: dependencies.runtime_store.load_report(report_id))
        if not isinstance(report, VerificationReport):
            _closed_http_error(
                ScienceOperationalError("stored report has an invalid type")
            )
        check = require_export if export else require_read
        report_check = (
            dependencies.can_export_report if export else dependencies.can_read_report
        )
        if report_check is not None:
            if not report_check(identity, report):
                _closed_http_error(ScienceAuthorizationError("report denied"))
        else:
            check(identity, report.document_ref or report.report_id)
        for annotation in report.annotations:
            for link in annotation.evidence_links:
                check(identity, link.source_lookup.boi_id)
        return report

    @router.post("/api/science/interpret")
    def interpret(
        request: InterpretRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        if request.document_ref:
            document = dependencies.load_document(identity, request.document_ref)
            if document is None:
                _closed_http_error(ScienceAuthorizationError("document unavailable"))
            document_ref = request.document_ref
        else:
            document = request.document or ""
            document_ref = f"boi:submitted:{request.request_id}"
        result = _invoke(
            lambda: service().interpret_document(
                document,
                document_ref=document_ref,
                identity=identity,
                idempotency_key=request.idempotency_key,
                selection_anchor=request.selection,
            )
        )
        return _json_model(result)

    @router.post("/api/science/aliases/detect")
    def detect_aliases(
        request: DetectAliasesRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        if request.document_ref:
            document = dependencies.load_document(identity, request.document_ref)
            if document is None:
                _closed_http_error(ScienceAuthorizationError("document unavailable"))
            document_ref = request.document_ref
        else:
            document = request.document or ""
            document_ref = f"boi:submitted:{request.request_id}"
        result = _invoke(
            lambda: service().detect_aliases(
                document,
                document_ref=document_ref,
                selection_anchor=request.selection,
            )
        )
        return _json_model(result)

    @router.post("/api/science/claims/submit")
    def submit_claim(
        request: SubmitClaimRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        if request.document_ref:
            document = dependencies.load_document(identity, request.document_ref)
            if document is None:
                _closed_http_error(ScienceAuthorizationError("document unavailable"))
            document_ref = request.document_ref
        else:
            document = request.document or ""
            if request.source_lineage is not None:
                document_ref = submitted_revision_document_ref(
                    actor_id=identity.employee_id,
                    source_document_ref=request.source_lineage.document_ref,
                    source_document_digest=request.source_lineage.document_digest,
                )
            else:
                submitted_id = sha256_digest(
                    {
                        "actor_id": identity.employee_id,
                        "initial_document_digest": sha256_digest(document),
                    }
                ).removeprefix("sha256:")
                document_ref = f"boi:submitted:{submitted_id}"
        result = _invoke(
            lambda: service().submit_claim_candidate(
                document,
                document_ref=document_ref,
                identity=identity,
                client_kind=request.client_kind,
                candidate=request.candidate,
                idempotency_key=request.idempotency_key,
                selection_anchor=request.selection,
                supersedes_claim_id=request.supersedes_claim_id,
                source_lineage_document_ref=(
                    request.source_lineage.document_ref
                    if request.source_lineage is not None
                    else None
                ),
                source_lineage_document_digest=(
                    request.source_lineage.document_digest
                    if request.source_lineage is not None
                    else None
                ),
            )
        )
        return _json_model(result)

    @router.post("/api/science/interpretations/{interpretation_id}/confirm")
    def confirm_interpretation(
        interpretation_id: str,
        request: ConfirmInterpretationRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        result = _invoke(
            lambda: service().confirm_interpretation(
                interpretation_id,
                claim_ids=request.claim_ids,
                identity=identity,
                idempotency_key=request.idempotency_key,
            )
        )
        return _json_model(result)

    @router.post("/api/science/claims/{claim_id}/verify")
    def verify_claim(
        claim_id: str,
        request: VerifyClaimRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        result = _invoke(
            lambda: service().verify_claim(
                request.interpretation_id,
                claim_id,
                request.release_selection,
                identity=identity,
            )
        )
        return _json_model(result)

    @router.post("/api/science/verify-document")
    def verify_document(
        request: VerifyDocumentRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        result = _invoke(
            lambda: service().verify_document(
                request.interpretation_id,
                request.release_selection,
                identity=identity,
                idempotency_key=request.idempotency_key,
            )
        )
        return _json_model(result)

    @router.get("/api/science/evidence/{evidence_id}")
    def evidence_detail(
        evidence_id: str,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        evidence = _invoke(lambda: dependencies.catalog.evidence(evidence_id))
        source = _invoke(lambda: dependencies.catalog.source(evidence.source_id))
        require_read(identity, source.boi_id)
        return {
            "authority_scope": "standalone_lookup_non_authoritative",
            "operational_eligibility": False,
            "release_binding": None,
            "evidence_id": evidence.evidence_id,
            "evidence_digest": evidence.digest,
            "source_id": source.source_id,
            "source_digest": source.digest,
            "source_url": source.original_url,
            "source_content_hash": source.content_hash,
            "locator": evidence.locator,
            "original_text": evidence.original_text,
            "original_text_hash": evidence.original_text_hash,
            "reviewed_translation": evidence.reviewed_translation,
            "claim_scope": evidence.claim_scope,
            "claim_scope_hash": evidence.claim_scope_hash,
        }

    @router.get("/api/science/reports/{report_id}")
    def get_report(
        report_id: str,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        return report_for(identity, report_id).model_dump(
            mode="json", exclude_none=False
        )

    @router.get("/api/science/reports/{report_id}/export")
    def export_report(
        report_id: str,
        format: Literal["markdown", "pdf"] = Query(default="markdown"),
        identity: AuthIdentity = Depends(science_identity),
    ) -> Response:
        report = report_for(identity, report_id, export=True)
        headers = {
            "X-Science-Report-Digest": report.report_digest,
            "Content-Disposition": (
                'attachment; filename="science-report-'
                f"{report.report_id.split(':')[-1]}."
                + ("md" if format == "markdown" else "pdf")
                + '"'
            ),
        }
        if format == "markdown":
            return Response(
                render_report_markdown(report).encode("utf-8"),
                media_type="text/markdown; charset=utf-8",
                headers=headers,
            )
        return Response(
            render_report_pdf(report),
            media_type="application/pdf",
            headers=headers,
        )

    @router.post("/api/science/proposals")
    def create_proposal(
        request: CreateProposalRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        proposal = _invoke(
            lambda: dependencies.runtime_store.save_proposal(
                identity=identity,
                domain=request.proposal.domain,
                kind=request.proposal.kind,
                payload=request.proposal.payload,
                idempotency_key=request.idempotency_key,
                request_digest=request.request_digest,
            )
        )
        return _json_model(proposal)

    @router.post("/api/science/proposals/{proposal_id}/review")
    def review_proposal(
        proposal_id: str,
        request: ReviewProposalRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        proposal = _invoke(
            lambda: dependencies.runtime_store.load_proposal(proposal_id)
        )
        if sha256_digest(proposal) != request.proposal_digest:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "science_proposal_digest_conflict",
                    "message": "Proposal changed before review.",
                },
            )
        approval = _invoke(
            lambda: dependencies.runtime_store.approve_proposal(
                proposal_id,
                identity=identity,
            )
        )
        return _json_model(approval)

    @router.post("/api/science/proposals/{proposal_id}/approve")
    def approve_proposal(
        proposal_id: str,
        request: ReviewProposalRequest,
        identity: AuthIdentity = Depends(science_identity),
    ) -> dict[str, Any]:
        return review_proposal(proposal_id, request, identity)

    def validate_object(
        metadata: Mapping[str, Any], expected_type: str
    ) -> dict[str, Any]:
        if metadata.get("type") != expected_type:
            return {
                "valid": False,
                "errors": [f"object type must be {expected_type}"],
                "approved": False,
            }
        errors = validate_sci_profile_metadata(dict(metadata))
        return {"valid": not errors, "errors": errors, "approved": False}

    @router.post("/api/science/admin/sources/validate")
    def validate_source(
        request: ValidateObjectRequest,
        _identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        return validate_object(request.source or {}, "boi/science-source")

    @router.post("/api/science/admin/evidence/validate")
    def validate_evidence(
        request: ValidateObjectRequest,
        _identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        return validate_object(request.evidence or {}, "boi/science-evidence")

    @router.post("/api/science/admin/knowledge/validate")
    def validate_knowledge(
        request: ValidateObjectRequest,
        _identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        return validate_object(request.knowledge or {}, "boi/science-knowledge")

    @router.post("/api/science/admin/rules/{rule_id}/qualify")
    def qualify_rule(
        rule_id: str,
        request: QualifyRuleRequest,
        _identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        if dependencies.boi_root is None:
            _closed_http_error(
                ScienceOperationalError("qualification root is unavailable")
            )
        rule = _invoke(lambda: dependencies.catalog.rule(rule_id))
        if rule.digest != request.rule_digest:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "science_rule_digest_conflict",
                    "message": "Rule digest does not match the Catalog.",
                },
            )
        canonical_case_ids = sorted(request.case_ids)
        if len(canonical_case_ids) != len(
            set(canonical_case_ids)
        ) or request.case_set_digest != sha256_digest(canonical_case_ids):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "science_case_set_digest_conflict",
                    "message": "Qualification case set is not exact.",
                },
            )
        available = {
            case.case_id for case in dependencies.catalog.qualification_cases(rule_id)
        }
        if set(canonical_case_ids) != available:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "science_case_set_incomplete",
                    "message": "Qualification requires the exact released case set.",
                },
            )
        result = _invoke(
            lambda: qualify_release_candidate(
                dependencies.boi_root,
                request.release_id,
            )
        )
        cases = [
            case
            for case in result.case_results
            if case.rule_id == rule_id and case.case_id in available
        ]
        qualified = len(cases) == len(available) and all(
            case.deterministic and case.actual_outcome == case.expected_outcome
            for case in cases
        )
        return {
            "rule_id": rule_id,
            "rule_digest": rule.digest,
            "case_set_digest": request.case_set_digest,
            "qualified": qualified,
            "approved": False,
            "case_results": [case.model_dump(mode="json") for case in cases],
        }

    @router.post("/api/science/admin/releases/validate")
    def validate_release(
        request: ValidateReleaseRequest,
        _identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        if dependencies.boi_root is None:
            _closed_http_error(
                ScienceOperationalError("qualification root is unavailable")
            )
        result = _invoke(
            lambda: qualify_release_candidate(
                dependencies.boi_root,
                request.release_id,
            )
        )
        if (
            result.release_digest != request.release_digest
            or result.holdout_manifest_digest != request.holdout_manifest_digest
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "science_release_validation_digest_conflict",
                    "message": (
                        "Release validation inputs do not match stored artifacts."
                    ),
                },
            )
        return result.model_dump(mode="json")

    def mutate_release(
        operation: Literal["activate", "withdraw"],
        release_id: str,
        request: ReleaseMutationRequest,
        identity: AuthIdentity,
    ) -> dict[str, Any]:
        expected_request_digest = sha256_digest(
            {
                "operation": operation,
                "release_id": release_id,
                "release_digest": request.release_digest,
            }
        )
        if request.request_digest != expected_request_digest:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "science_release_request_digest_conflict",
                    "message": "Release mutation request is not exact.",
                },
            )
        if dependencies.release_manager is None:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "science_release_manager_unavailable",
                    "message": "Authoritative release mutation is not configured.",
                },
            )
        method = getattr(dependencies.release_manager, operation)
        result = _invoke(
            lambda: method(
                release_id=release_id,
                release_digest=request.release_digest,
                request_digest=request.request_digest,
                idempotency_key=request.idempotency_key,
                identity=identity,
            )
        )
        return _json_model(result) if hasattr(result, "model_dump") else dict(result)

    @router.post("/api/science/admin/releases/{release_id}/activate")
    def activate_release(
        release_id: str,
        request: ReleaseMutationRequest,
        identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        return mutate_release("activate", release_id, request, identity)

    @router.post("/api/science/admin/releases/{release_id}/withdraw")
    def withdraw_release(
        release_id: str,
        request: ReleaseMutationRequest,
        identity: AuthIdentity = Depends(science_admin),
    ) -> dict[str, Any]:
        return mutate_release("withdraw", release_id, request, identity)

    return router
