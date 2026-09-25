"""Exact qualification bindings required before creating a ReleaseManifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any


QUALIFICATION_CONTRACT_SCHEMA = "boi-qualification-contract/v1"
QUALIFICATION_RECEIPT_SCHEMA = "boi-qualification-receipt/v2"

_CONTRACT_FIELDS = frozenset(
    {
        "schema",
        "required_checks",
        "profile_versions",
        "schema_versions",
        "evaluator_code_digest",
        "revision_ids",
        "revision_closure_digest",
        "catalog_snapshot_digest",
        "schema_snapshot_digest",
        "freshness_policy_digest",
        "policy_digest",
        "contract_digest",
    }
)


class QualificationContractError(ValueError):
    """The receipt does not prove every field of its QualificationContract."""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value)).hexdigest()


def _is_digest(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        return False
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def revision_closure_digest(revision_ids: Sequence[str]) -> str:
    return _digest(list(revision_ids))


def build_qualification_receipt_payload(
    *,
    revision_ids: Sequence[str],
    required_evidence: Mapping[str, str],
    profile_versions: Mapping[str, str],
    schema_versions: Mapping[str, str],
    evaluator_code_digest: str,
    catalog_snapshot_digest: str,
    schema_snapshot_digest: str,
    freshness_policy_digest: str,
    policy_digest: str,
) -> dict[str, Any]:
    """Build a deterministic qualified receipt whose checks exactly close its contract."""

    revisions = list(revision_ids)
    required_checks = [
        {"check_id": check_id, "evidence_digest": required_evidence[check_id]}
        for check_id in sorted(required_evidence)
    ]
    contract: dict[str, Any] = {
        "schema": QUALIFICATION_CONTRACT_SCHEMA,
        "required_checks": required_checks,
        "profile_versions": dict(sorted(profile_versions.items())),
        "schema_versions": dict(sorted(schema_versions.items())),
        "evaluator_code_digest": evaluator_code_digest,
        "revision_ids": revisions,
        "revision_closure_digest": revision_closure_digest(revisions),
        "catalog_snapshot_digest": catalog_snapshot_digest,
        "schema_snapshot_digest": schema_snapshot_digest,
        "freshness_policy_digest": freshness_policy_digest,
        "policy_digest": policy_digest,
    }
    contract["contract_digest"] = _digest(contract)
    return {
        "schema": QUALIFICATION_RECEIPT_SCHEMA,
        "status": "qualified",
        "revision_ids": revisions,
        "qualification_contract": contract,
        "qualification_contract_digest": contract["contract_digest"],
        "check_receipts": [
            {"check_id": item["check_id"], "status": "PASS", "evidence_digest": item["evidence_digest"]}
            for item in required_checks
        ],
    }


def validate_qualification_receipt_payload(payload: Mapping[str, Any]) -> None:
    """Fail closed unless a receipt proves the exact contract required for Release."""

    if payload.get("schema") != QUALIFICATION_RECEIPT_SCHEMA or payload.get("status") != "qualified":
        raise QualificationContractError("qualified v2 receipt required")
    contract = payload.get("qualification_contract")
    if not isinstance(contract, Mapping) or set(contract) != _CONTRACT_FIELDS:
        raise QualificationContractError("exact QualificationContract fields required")
    if contract.get("schema") != QUALIFICATION_CONTRACT_SCHEMA:
        raise QualificationContractError("QualificationContract schema mismatch")

    unsigned_contract = dict(contract)
    stored_contract_digest = unsigned_contract.pop("contract_digest", None)
    if not _is_digest(stored_contract_digest) or stored_contract_digest != _digest(unsigned_contract):
        raise QualificationContractError("QualificationContract digest mismatch")
    if payload.get("qualification_contract_digest") != stored_contract_digest:
        raise QualificationContractError("receipt is not bound to QualificationContract digest")

    revisions = payload.get("revision_ids")
    if not isinstance(revisions, list) or not revisions or not all(isinstance(item, str) for item in revisions):
        raise QualificationContractError("revision_ids must be a non-empty list")
    if contract.get("revision_ids") != revisions:
        raise QualificationContractError("receipt and contract revision closure differ")
    if contract.get("revision_closure_digest") != revision_closure_digest(revisions):
        raise QualificationContractError("revision closure digest mismatch")

    for field in (
        "evaluator_code_digest",
        "catalog_snapshot_digest",
        "schema_snapshot_digest",
        "freshness_policy_digest",
        "policy_digest",
    ):
        if not _is_digest(contract.get(field)):
            raise QualificationContractError(f"{field} must be a sha256 digest")
    for field in ("profile_versions", "schema_versions"):
        versions = contract.get(field)
        if not isinstance(versions, Mapping) or not versions or not all(
            isinstance(key, str) and key and isinstance(value, str) and value
            for key, value in versions.items()
        ):
            raise QualificationContractError(f"{field} must be a non-empty string mapping")

    required = contract.get("required_checks")
    observed = payload.get("check_receipts")
    if not isinstance(required, list) or not required or not isinstance(observed, list):
        raise QualificationContractError("required checks and check receipts are required")
    required_by_id: dict[str, str] = {}
    for item in required:
        if not isinstance(item, Mapping):
            raise QualificationContractError("required check must be an object")
        check_id, evidence = item.get("check_id"), item.get("evidence_digest")
        if not isinstance(check_id, str) or not check_id or check_id in required_by_id or not _is_digest(evidence):
            raise QualificationContractError("required check IDs and evidence digests must be unique and valid")
        required_by_id[check_id] = evidence
    observed_by_id: dict[str, Mapping[str, Any]] = {}
    for item in observed:
        if not isinstance(item, Mapping) or not isinstance(item.get("check_id"), str):
            raise QualificationContractError("check receipt must identify its check")
        check_id = str(item["check_id"])
        if check_id in observed_by_id:
            raise QualificationContractError("duplicate check receipt")
        observed_by_id[check_id] = item
    if set(observed_by_id) != set(required_by_id):
        raise QualificationContractError("required check closure is incomplete or contains extras")
    for check_id, evidence in required_by_id.items():
        item = observed_by_id[check_id]
        if item.get("status") != "PASS" or item.get("evidence_digest") != evidence:
            raise QualificationContractError("required check did not PASS with exact evidence")
