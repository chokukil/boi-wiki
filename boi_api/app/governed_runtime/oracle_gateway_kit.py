"""Vendor-neutral contract kit for a separately operated internal Oracle Gateway.

This module never imports an Oracle driver, accepts credentials for Oracle, or
renders SQL.  It verifies the HTTP contract that the internal Gateway must
implement before BoI can consider that external capability for qualification.
Passing the mock suite is intentionally not production verification.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _digest(value: object) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


Scalar = str | int | float | bool | None
ParameterValue = Scalar | tuple[Scalar, ...]


class OracleLogicalPlanEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    plan_id: str
    plan_digest: str
    signature_ref: str
    signature_digest: str
    source_ids: tuple[str, ...]
    read_only: bool
    cross_database: bool

    @model_validator(mode="after")
    def validate_safety(self) -> "OracleLogicalPlanEnvelope":
        if len(self.source_ids) != 1:
            raise ValueError("EXPLORATORY_SINGLE_SOURCE_REQUIRED")
        if not self.read_only:
            raise ValueError("EXPLORATORY_READ_ONLY_REQUIRED")
        if self.cross_database:
            raise ValueError("EXPLORATORY_CROSS_DATABASE_FORBIDDEN")
        return self


class OracleQueryExecutionRequest(BaseModel):
    """The only request body BoI sends to the internal Oracle Gateway."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lane: Literal["attested", "exploratory"]
    query_spec_id: str | None = None
    query_revision_digest: str | None = None
    logical_plan: OracleLogicalPlanEnvelope | None = None
    parameters: dict[str, ParameterValue]
    domain_profile_digest: str
    mapping_profile_digest: str
    query_profile_digest: str
    schema_digest: str
    principal: str
    purpose: str
    idempotency_key: str
    timeout_seconds: int = Field(default=30, ge=1, le=30)
    row_limit: int = Field(default=1000, ge=1, le=1000)

    @model_validator(mode="after")
    def validate_lane(self) -> "OracleQueryExecutionRequest":
        registered = bool(self.query_spec_id and self.query_revision_digest)
        if bool(self.query_spec_id) != bool(self.query_revision_digest):
            raise ValueError("REGISTERED_QUERY_BINDING_INCOMPLETE")
        if not self.principal.strip():
            raise ValueError("PRINCIPAL_REQUIRED")
        if not self.purpose.strip() or self.purpose != self.purpose.strip():
            raise ValueError("CANONICAL_PURPOSE_REQUIRED")
        if not self.idempotency_key.strip():
            raise ValueError("IDEMPOTENCY_KEY_REQUIRED")
        if any(not name.strip() for name in self.parameters):
            raise ValueError("PARAMETER_NAME_REQUIRED")
        for value in self.parameters.values():
            if isinstance(value, tuple) and not value:
                raise ValueError("PARAMETER_COLLECTION_EMPTY")
            if isinstance(value, tuple):
                types = {type(item) for item in value if item is not None}
                if len(types) > 1:
                    raise ValueError("PARAMETER_COLLECTION_TYPE_MISMATCH")
        if self.lane == "attested":
            if not registered or self.logical_plan is not None:
                raise ValueError("ATTESTED_REQUIRES_REGISTERED_QUERY")
        elif registered or self.logical_plan is None:
            raise ValueError("EXPLORATORY_REQUIRES_SIGNED_LOGICAL_PLAN")
        return self


class OracleGatewayAuthContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bearer_token: str | None = Field(default=None, repr=False, min_length=1)
    mtls_peer_digest: str | None = None

    @model_validator(mode="after")
    def validate_digest(self) -> "OracleGatewayAuthContext":
        if self.bearer_token is None and self.mtls_peer_digest is None:
            raise ValueError("GATEWAY_AUTH_CONTEXT_REQUIRED")
        if self.mtls_peer_digest is not None and not (
            self.mtls_peer_digest.startswith("sha256:")
            and len(self.mtls_peer_digest) == 71
        ):
            raise ValueError("MTLS_PEER_DIGEST_INVALID")
        return self


class GatewayHttpResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status_code: int
    json_body: dict[str, Any]


class OracleGatewayTransport(Protocol):
    def request(
        self, method: str, path: str, *, json_body: dict[str, object] | None,
        headers: dict[str, str],
    ) -> GatewayHttpResponse: ...


class OracleConformanceCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    status: Literal["PASS", "FAIL", "NOT_RUN"]
    reason_code: str
    inputs_digest: str


class OracleGatewayConformanceReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_name: Literal["boi-oracle-gateway-conformance/v1"] = (
        "boi-oracle-gateway-conformance/v1"
    )
    status: Literal["PASS", "BLOCKED"]
    reason_codes: tuple[str, ...]
    contract_digest: str
    request_digest: str
    expected_schema_digest: str
    capability_digest: str
    checks: tuple[OracleConformanceCheck, ...]
    async_202_observed: bool
    idempotent_replay_passed: bool
    idempotency_conflict_passed: bool
    auth_context_forwarded: bool
    execution_id_parity: bool
    receipt_and_result_fidelity: bool
    actual_oracle_verified: Literal[False] = False
    actual_release_activation: Literal[False] = False
    actual_active_pointer_transition: Literal[False] = False
    receipt_digest: str


class OracleGatewayConformanceSuite:
    """Black-box suite reusable against a mock or an internal Gateway URL."""

    CONTRACT_ID = "boi-oracle-gateway-conformance@0.1.0"
    CONTRACT_DIGEST = (
        "sha256:422f1196fb8fc87a3d8a5a5deec1619595dd74d52dc7a5be46627f5e76e4c72b"
    )

    def __init__(self, *, expected_schema_digest: str) -> None:
        self.expected_schema_digest = expected_schema_digest

    @staticmethod
    def digest(value: object) -> str:
        """Expose canonical hashing so external runners can verify receipts."""

        return _digest(value)

    @staticmethod
    def mock_result_rows() -> list[dict[str, int]]:
        return [{"route_order": 10}]

    @classmethod
    def mock_result_digest(cls) -> str:
        return _digest(cls.mock_result_rows())

    @staticmethod
    def mock_schema() -> list[list[str]]:
        return [["route_order", "integer"]]

    @classmethod
    def mock_schema_digest(cls) -> str:
        return _digest(cls.mock_schema())

    @classmethod
    def expected_mock_receipt(
        cls, request: OracleQueryExecutionRequest, *, execution_id: str,
    ) -> dict[str, object]:
        plan_digest = (
            request.logical_plan.plan_digest
            if request.logical_plan is not None
            else _digest({
                "query_spec_id": request.query_spec_id,
                "query_revision_digest": request.query_revision_digest,
            })
        )
        return {
            "computation_id": request.query_spec_id or request.logical_plan.plan_id,
            "query_revision_digest": (
                request.query_revision_digest or request.logical_plan.signature_digest
            ),
            "logical_plan_digest": plan_digest,
            "domain_profile_digest": request.domain_profile_digest,
            "mapping_profile_digest": request.mapping_profile_digest,
            "query_profile_digest": request.query_profile_digest,
            "schema_digest": request.schema_digest,
            "compiler_digest": _digest("internal-oracle-binding@candidate"),
            "parameter_digest": _digest(request.parameters),
            "execution_artifact_ref": "protected:oracle-binding:mock-001",
            "execution_artifact_digest": _digest("mock-protected-binding"),
            "backend_execution_id": execution_id,
            "source_snapshot": "oracle-watermark://mock/2026-09-02T00:00:00Z",
            "result_schema_digest": cls.mock_schema_digest(),
            "row_count": 1,
            "result_digest": cls.mock_result_digest(),
            "authorization_policy_digest": _digest({
                "principal": request.principal,
                "purpose": request.purpose,
                "lane": request.lane,
                "policy": "internal-oracle-gateway-policy@candidate",
            }),
            "started_at": "2026-09-02T00:00:00+00:00",
            "completed_at": "2026-09-02T00:00:01+00:00",
            "error_code": None,
        }

    @staticmethod
    def _check(
        name: str, ok: bool | None, reason: str, inputs: object,
    ) -> OracleConformanceCheck:
        return OracleConformanceCheck(
            name=name,
            status="NOT_RUN" if ok is None else "PASS" if ok else "FAIL",
            reason_code="OK" if ok else reason,
            inputs_digest=_digest(inputs),
        )

    def _receipt(
        self, *, request: OracleQueryExecutionRequest,
        capability: dict[str, Any], checks: list[OracleConformanceCheck],
        async_202: bool = False, replay: bool = False, conflict: bool = False,
        auth_forwarded: bool = False, execution_parity: bool = False,
        fidelity: bool = False,
    ) -> OracleGatewayConformanceReceipt:
        reasons = tuple(dict.fromkeys(
            check.reason_code
            for check in checks if check.status != "PASS"
        ))
        values = {
            "schema_name": "boi-oracle-gateway-conformance/v1",
            "status": "PASS" if not reasons else "BLOCKED",
            "reason_codes": reasons,
            "contract_digest": self.CONTRACT_DIGEST,
            "request_digest": _digest(request),
            "expected_schema_digest": self.expected_schema_digest,
            "capability_digest": _digest(capability),
            "checks": [item.model_dump(mode="json") for item in checks],
            "async_202_observed": async_202,
            "idempotent_replay_passed": replay,
            "idempotency_conflict_passed": conflict,
            "auth_context_forwarded": auth_forwarded,
            "execution_id_parity": execution_parity,
            "receipt_and_result_fidelity": fidelity,
            "actual_oracle_verified": False,
            "actual_release_activation": False,
            "actual_active_pointer_transition": False,
        }
        return OracleGatewayConformanceReceipt(
            **values, receipt_digest=_digest(values)
        )

    def run(
        self, transport: OracleGatewayTransport, *,
        request: OracleQueryExecutionRequest, auth: OracleGatewayAuthContext,
    ) -> OracleGatewayConformanceReceipt:
        headers = {
            "X-BoI-Principal": request.principal,
            "X-BoI-Purpose": request.purpose,
            "Idempotency-Key": request.idempotency_key,
        }
        if auth.bearer_token is not None:
            headers["Authorization"] = f"Bearer {auth.bearer_token}"
        if auth.mtls_peer_digest is not None:
            headers["X-BoI-mTLS-Peer-Digest"] = auth.mtls_peer_digest
        checks: list[OracleConformanceCheck] = []
        capability_response = transport.request(
            "GET", "/v1/capabilities", json_body=None, headers=headers
        )
        capability = capability_response.json_body
        capability_ok = (
            capability_response.status_code == 200
            and capability.get("backend") == "oracle-internal-gateway"
            and capability.get("conformance_contract_digest")
            == self.CONTRACT_DIGEST
        )
        checks.append(self._check(
            "capability_contract", capability_ok,
            "ORACLE_CAPABILITY_CONTRACT_INVALID", capability,
        ))
        schema_ok = (
            capability_ok
            and capability.get("execution_enabled") is True
            and capability.get("schema_status") == "CURRENT"
            and capability.get("schema_digest") == self.expected_schema_digest
            and request.lane in tuple(capability.get("lanes") or ())
        )
        checks.append(self._check(
            "schema_and_lane", schema_ok,
            "ORACLE_SCHEMA_NOT_CURRENT", {
                "capability": capability,
                "expected_schema_digest": self.expected_schema_digest,
                "lane": request.lane,
            },
        ))
        auth_forwarded = bool(
            (
                auth.bearer_token is not None
                and headers.get("Authorization", "").startswith("Bearer ")
            )
            or (
                auth.mtls_peer_digest is not None
                and headers.get("X-BoI-mTLS-Peer-Digest")
                == auth.mtls_peer_digest
            )
        ) and bool(
            headers["X-BoI-Principal"] == request.principal
            and headers["X-BoI-Purpose"] == request.purpose
        )
        checks.append(self._check(
            "auth_context", auth_forwarded,
            "AUTH_CONTEXT_NOT_FORWARDED", {
                "mtls_peer_digest": auth.mtls_peer_digest,
                "principal": request.principal,
                "purpose": request.purpose,
            },
        ))
        if not capability_ok or not schema_ok or not auth_forwarded:
            return self._receipt(
                request=request, capability=capability, checks=checks,
                auth_forwarded=auth_forwarded,
            )

        body = request.model_dump(mode="json")
        created = transport.request(
            "POST", "/v1/query-executions", json_body=body, headers=headers
        )
        async_202 = created.status_code == 202
        execution_id = str(created.json_body.get("execution_id") or "")
        create_ok = created.status_code in {200, 202} and bool(execution_id)
        checks.append(self._check(
            "create_or_accept", create_ok,
            "QUERY_EXECUTION_NOT_ACCEPTED", created.json_body,
        ))
        if not create_ok:
            return self._receipt(
                request=request, capability=capability, checks=checks,
                async_202=async_202, auth_forwarded=auth_forwarded,
            )
        status_response = transport.request(
            "GET", f"/v1/query-executions/{execution_id}",
            json_body=None, headers=headers,
        )
        receipt_response = transport.request(
            "GET", f"/v1/query-executions/{execution_id}/receipt",
            json_body=None, headers=headers,
        )
        result_response = transport.request(
            "GET", f"/v1/query-executions/{execution_id}/result",
            json_body=None, headers=headers,
        )
        replay_response = transport.request(
            "POST", "/v1/query-executions", json_body=body, headers=headers
        )
        changed = json.loads(json.dumps(body))
        changed["parameters"] = {**changed["parameters"], "lot_code": "LOT-CHANGED"}
        conflict_response = transport.request(
            "POST", "/v1/query-executions", json_body=changed, headers=headers
        )

        status_id = status_response.json_body.get("execution_id")
        receipt_id = receipt_response.json_body.get("backend_execution_id")
        result_id = result_response.json_body.get("execution_id")
        execution_parity = (
            status_response.status_code == 200
            and receipt_response.status_code == 200
            and result_response.status_code == 200
            and status_id == receipt_id == result_id == execution_id
            and status_response.json_body.get("status") == "SUCCEEDED"
        )
        checks.append(self._check(
            "execution_id_parity", execution_parity,
            "EXECUTION_ID_PARITY_FAILED", {
                "created": execution_id, "status": status_id,
                "receipt": receipt_id, "result": result_id,
            },
        ))
        replay = (
            replay_response.status_code in {200, 202}
            and replay_response.json_body.get("execution_id") == execution_id
        )
        checks.append(self._check(
            "idempotent_replay", replay,
            "IDEMPOTENT_REPLAY_FAILED", replay_response.json_body,
        ))
        conflict = (
            conflict_response.status_code == 409
            and conflict_response.json_body.get("detail") == "IDEMPOTENCY_CONFLICT"
        )
        checks.append(self._check(
            "idempotency_conflict", conflict,
            "IDEMPOTENCY_CONFLICT_NOT_ENFORCED", conflict_response.json_body,
        ))

        expected_receipt = self.expected_mock_receipt(
            request, execution_id=execution_id
        )
        returned_receipt = receipt_response.json_body
        result_body = result_response.json_body
        result = result_body.get("result") or {}
        receipt_mismatches = [
            key for key, value in expected_receipt.items()
            if returned_receipt.get(key) != value
        ]
        if returned_receipt.get("result_digest") != result.get("result_digest"):
            receipt_mismatches.append("result_digest")
        fidelity = not receipt_mismatches and (
            result.get("rows") == self.mock_result_rows()
            and result.get("row_count") == 1
            and result.get("result_schema") == self.mock_schema()
            and result.get("result_schema_digest") == self.mock_schema_digest()
            and result.get("result_digest") == self.mock_result_digest()
            and result_body.get("result_status") == "ATTESTED"
            and (result_body.get("attestation") or {}).get("status") == "PASS"
            and not any(
                forbidden in returned_receipt
                for forbidden in ("raw_sql", "repaired_sql", "executed_sql")
            )
        )
        mismatch_reason = (
            "RECEIPT_RESULT_DIGEST_MISMATCH"
            if "result_digest" in receipt_mismatches
            else "RECEIPT_AND_RESULT_FIDELITY_FAILED"
        )
        checks.append(self._check(
            "receipt_and_result_fidelity", fidelity, mismatch_reason, {
                "receipt_mismatches": sorted(set(receipt_mismatches)),
                "result_digest": result.get("result_digest"),
                "result_schema_digest": result.get("result_schema_digest"),
                "row_count": result.get("row_count"),
            },
        ))
        return self._receipt(
            request=request, capability=capability, checks=checks,
            async_202=async_202, replay=replay, conflict=conflict,
            auth_forwarded=auth_forwarded,
            execution_parity=execution_parity, fidelity=fidelity,
        )
