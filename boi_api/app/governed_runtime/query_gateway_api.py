"""FastAPI surface for the internal Data Gateway QueryExecution contract."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
from typing import Mapping

from fastapi import APIRouter, HTTPException, Request

from .query_gateway import QueryExecutionRequest, QueryGatewayService
from .multi_result_query_gateway import (
    MultiResultExploratoryExecutionRequest,
    MultiResultQueryExecution,
)
from .semantic_query_execution import SemanticExploratoryExecutionRequest
from .protected_export import ProtectedExportAuthority


@dataclass(frozen=True)
class GatewayApiAuthPolicy:
    """Fail-closed service-token or trusted mTLS transport policy."""

    service_token_digests: tuple[str, ...] = ()
    mtls_peer_digests: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for digest in (*self.service_token_digests, *self.mtls_peer_digests):
            if not (
                digest.startswith("sha256:")
                and len(digest) == 71
                and all(char in "0123456789abcdef" for char in digest[7:])
            ):
                raise ValueError("QUERY_GATEWAY_AUTH_DIGEST_INVALID")

    @classmethod
    def from_environment(
        cls, environ: Mapping[str, str],
    ) -> "GatewayApiAuthPolicy":
        def values(name: str) -> tuple[str, ...]:
            return tuple(
                item.strip() for item in str(environ.get(name, "")).split(",")
                if item.strip()
            )

        return cls(
            service_token_digests=values(
                "BOI_QUERY_GATEWAY_SERVICE_TOKEN_SHA256"
            ),
            mtls_peer_digests=values("BOI_QUERY_GATEWAY_MTLS_PEER_DIGESTS"),
        )

    @classmethod
    def from_plaintext_test_credentials(
        cls, *, service_tokens: tuple[str, ...] = (),
        mtls_peer_digests: tuple[str, ...] = (),
    ) -> "GatewayApiAuthPolicy":
        """Build only test policy values; production accepts digest config."""

        return cls(
            service_token_digests=tuple(
                "sha256:" + hashlib.sha256(token.encode()).hexdigest()
                for token in service_tokens
            ),
            mtls_peer_digests=mtls_peer_digests,
        )

    @property
    def configured(self) -> bool:
        return bool(self.service_token_digests or self.mtls_peer_digests)

    @staticmethod
    def _bearer_token(headers: Mapping[str, str]) -> str:
        authorization = str(headers.get("authorization") or "")
        scheme, separator, token = authorization.partition(" ")
        return token.strip() if separator and scheme.casefold() == "bearer" else ""

    def authorize(
        self, headers: Mapping[str, str], *, expected_principal: str | None = None,
        expected_purpose: str | None = None,
        transport_peer_digest: str = "",
    ) -> tuple[str, str]:
        if not self.configured:
            raise HTTPException(
                status_code=503, detail="QUERY_GATEWAY_AUTH_UNCONFIGURED"
            )
        token = self._bearer_token(headers)
        token_digest = (
            "sha256:" + hashlib.sha256(token.encode()).hexdigest()
            if token else ""
        )
        token_ok = bool(token_digest) and any(
            hmac.compare_digest(token_digest, expected)
            for expected in self.service_token_digests
        )
        peer_digest = transport_peer_digest.strip()
        mtls_ok = bool(peer_digest) and any(
            hmac.compare_digest(peer_digest, expected)
            for expected in self.mtls_peer_digests
        )
        if not (token_ok or mtls_ok):
            raise HTTPException(status_code=401, detail="QUERY_GATEWAY_AUTH_REQUIRED")
        principal = str(headers.get("x-boi-principal") or "").strip()
        purpose = str(headers.get("x-boi-purpose") or "")
        if not principal or not purpose or purpose != purpose.strip():
            raise HTTPException(
                status_code=403, detail="QUERY_GATEWAY_CONTEXT_REQUIRED"
            )
        if expected_principal is not None and principal != expected_principal:
            raise HTTPException(
                status_code=403, detail="QUERY_GATEWAY_PRINCIPAL_MISMATCH"
            )
        if expected_purpose is not None and purpose != expected_purpose:
            raise HTTPException(
                status_code=403, detail="QUERY_GATEWAY_PURPOSE_MISMATCH"
            )
        return principal, purpose


def create_query_gateway_router(
    service: QueryGatewayService,
    *, auth_policy: GatewayApiAuthPolicy | None = None,
    protected_export_authority: ProtectedExportAuthority | None = None,
) -> APIRouter:
    router = APIRouter(tags=["governed-query-execution"])
    policy = auth_policy or GatewayApiAuthPolicy()
    execution_context: dict[str, tuple[str, str]] = {}

    def authorize(
        request: Request, *, expected_principal: str | None = None,
        expected_purpose: str | None = None,
    ) -> tuple[str, str]:
        peer_digest = str(
            request.scope.get("boi.mtls_peer_digest") or ""
        )
        return policy.authorize(
            request.headers,
            expected_principal=expected_principal,
            expected_purpose=expected_purpose,
            transport_peer_digest=peer_digest,
        )

    @router.get("/v1/capabilities")
    def capabilities():
        return service.capabilities()

    @router.post("/v1/query-executions")
    def create_execution(
        request: QueryExecutionRequest | SemanticExploratoryExecutionRequest
        | MultiResultExploratoryExecutionRequest,
        http_request: Request,
    ):
        authorize(
            http_request,
            expected_principal=request.principal,
            expected_purpose=request.purpose,
        )
        try:
            execution = service.create(request)
            context = (request.principal, request.purpose)
            prior = execution_context.setdefault(execution.execution_id, context)
            if prior != context:
                raise HTTPException(
                    status_code=409, detail="EXECUTION_AUTH_CONTEXT_CONFLICT"
                )
            return execution
        except RuntimeError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ValueError as error:
            code = str(error).split(":", 1)[0]
            status = (
                408
                if code == "QUERY_TIMEOUT"
                else 409
                if code in {
                    "IDEMPOTENCY_CONFLICT",
                    "QUERY_CANCELLED",
                    "SCHEMA_SNAPSHOT_STALE",
                    "SCHEMA_DRIFT",
                    "SOURCE_SNAPSHOT_DRIFT",
                }
                else 422
            )
            raise HTTPException(status_code=status, detail=code) from error

    def require_execution(execution_id: str, request: Request):
        supplied = authorize(request)
        execution = service.get(execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="QUERY_EXECUTION_NOT_FOUND")
        if isinstance(execution, MultiResultQueryExecution):
            try:
                return service.get_authorized_multi_result(execution_id, principal=supplied[0], purpose=supplied[1])
            except ValueError as error:
                raise HTTPException(status_code=403 if str(error)=='EXECUTION_ACCESS_DENIED' else 409,
                                    detail=str(error)) from error
        expected = execution_context.get(execution_id)
        if expected is None:
            raise HTTPException(
                status_code=403, detail="EXECUTION_AUTH_CONTEXT_MISSING"
            )
        if supplied[0] != expected[0]:
            raise HTTPException(
                status_code=403, detail="QUERY_GATEWAY_PRINCIPAL_MISMATCH"
            )
        if supplied[1] != expected[1]:
            raise HTTPException(
                status_code=403, detail="QUERY_GATEWAY_PURPOSE_MISMATCH"
            )
        return execution

    @router.get("/v1/query-executions/{execution_id}")
    def get_execution(execution_id: str, request: Request):
        return require_execution(execution_id, request)

    @router.get("/v1/query-executions/{execution_id}/receipt")
    def get_receipt(execution_id: str, request: Request):
        execution = require_execution(execution_id, request)
        return execution.exploration_receipt or execution.receipt

    @router.get("/v1/query-executions/{execution_id}/result")
    def get_result(execution_id: str, request: Request, complete: bool = False):
        if complete:
            principal, purpose = authorize(request)
            entitlement_id = str(
                request.headers.get("x-boi-protected-export-entitlement") or ""
            ).strip()
            if protected_export_authority is None or not entitlement_id:
                raise HTTPException(
                    status_code=403,
                    detail="PROTECTED_EXPORT_ENTITLEMENT_REQUIRED",
                )
            try:
                delivery = protected_export_authority.export(
                    entitlement_id,
                    execution_id=execution_id,
                    principal=principal,
                    purpose=purpose,
                    artifact_reader=service.read_multi_result_artifact,
                )
            except ValueError as error:
                code = str(error).split(":", 1)[0]
                status = 413 if code == "PROTECTED_EXPORT_BYTE_CEILING_EXCEEDED" else 403
                raise HTTPException(status_code=status, detail=code) from error
            return {
                "execution_id": execution_id,
                "result_status": "PROVISIONAL",
                "result": delivery.artifact,
                "attestation": None,
                "protected_export_receipt": delivery.receipt,
            }
        execution = require_execution(execution_id, request)
        response = {
            "execution_id": execution.execution_id,
            "result_status": execution.result_status,
            "result": execution.result,
            "attestation": execution.attestation,
            "exploration_receipt": execution.exploration_receipt,
        }
        return response

    return router
