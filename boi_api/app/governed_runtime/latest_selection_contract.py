"""Exact logical latest policy. No SQL, model, data access or semantic repair."""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain_profile_v03 import validate_domain_profile_entry, versioning_closure_reasons
from .latest_time_order import TimeOrdering


def digest(value) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def latest_contract_dependencies(payload) -> set[str]:
    """Only declared reference positions, never a recursive arbitrary-string scan."""
    refs = set()
    version = payload.get("versioning")
    if isinstance(version, dict):
        refs.update(version.get("business_key_refs", ()))
        refs.update(version.get("recency_property_refs", ()))
        if version.get("version_identity_ref"):
            refs.add(version["version_identity_ref"])
    for contract in payload.get("latest_selection_contracts", ()):
        refs.update(contract.get("partition_by", ()))
        refs.update((contract["scope_object_ref"], contract["recency_property_ref"]))
        refs.update(item["property_ref"] for item in contract.get("tie_break", ()))
    return refs


class LatestContractGap(ValueError):
    def __init__(self, reason: str, scope: str):
        super().__init__(reason)
        self.dependency_ref = "latest-contract:" + scope


class LatestTieBreak(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    property_ref: str = Field(min_length=1)
    direction: Literal["ASC", "DESC"]


class LatestSelectionContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_version: Literal["boi/latest-selection@1"]
    policy_id: str = Field(min_length=1)
    scope_object_ref: str = Field(min_length=1)
    versioning_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    partition_by: tuple[str, ...] = Field(min_length=1)
    recency_property_ref: str = Field(min_length=1)
    tie_break: tuple[LatestTieBreak, ...] = Field(min_length=1)
    null_time_policy: Literal["BLOCK", "EXCLUDE_WITH_DISCLOSURE"]
    null_business_key_policy: Literal["BLOCK"]

    @model_validator(mode="after")
    def unique_keys(self):
        keys = tuple(item.property_ref for item in self.tie_break)
        if len(keys) != len(set(keys)) or self.recency_property_ref in keys:
            raise ValueError("LATEST_TIE_BREAK_DUPLICATE")
        if len(self.partition_by) != len(set(self.partition_by)) or any(not ref.strip() for ref in self.partition_by):
            raise ValueError("LATEST_PARTITION_EMPTY_OR_DUPLICATE")
        return self


class LatestSelectionContract(LatestSelectionContractV1):
    contract_version: Literal["boi/latest-selection@2"]
    time_ordering: TimeOrdering


class BoundLatestSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    contract_digest: str
    versioning_digest: str
    version_identity_ref: str
    partition_by: tuple[str, ...]
    ordering: tuple[str, ...]
    ordering_directions: tuple[Literal["ASC", "DESC"], ...]
    null_time_policy: Literal["BLOCK", "EXCLUDE_WITH_DISCLOSURE"]
    null_business_key_policy: Literal["BLOCK"]
    time_ordering: TimeOrdering
    resolution_basis: Literal["EXACT_PROFILE_POLICY"] = "EXACT_PROFILE_POLICY"


def bind_latest_selection(*, domain_entries, contracts, scope_object_ref, partition_by, recency_property_ref, ordering) -> BoundLatestSelection:
    payloads = {value["id"]: value for value in domain_entries}
    obj = payloads.get(scope_object_ref, {})
    versioning = obj.get("versioning")
    if versioning is None:
        raise LatestContractGap("LATEST_BUSINESS_VERSION_CONTRACT_REQUIRED", scope_object_ref)
    parsed = validate_domain_profile_entry(obj)
    required = {scope_object_ref, *parsed.property_refs}
    required.update(value.get("value_type_ref") for value in domain_entries if value.get("id") in required)
    entries = [validate_domain_profile_entry(value) for value in domain_entries if value.get("id") in required]
    reasons = versioning_closure_reasons(entries)
    if reasons:
        raise ValueError(sorted(reasons)[0])
    matching_values = [value for value in contracts if value.get("scope_object_ref") == scope_object_ref and value.get("recency_property_ref") == recency_property_ref]
    if any(value.get("contract_version") == "boi/latest-selection@1" for value in matching_values):
        raise LatestContractGap("LATEST_TIME_ORDERING_CONTRACT_REQUIRED", scope_object_ref)
    matches = [LatestSelectionContract.model_validate(value) for value in matching_values]
    if not matches:
        raise LatestContractGap("LATEST_SELECTION_CONTRACT_REQUIRED", scope_object_ref)
    if len(matches) != 1:
        raise ValueError("LATEST_POLICY_AMBIGUOUS")
    contract = matches[0]
    version_digest = digest(parsed.versioning)
    if contract.versioning_digest != version_digest:
        raise ValueError("LATEST_VERSIONING_DIGEST_MISMATCH")
    if contract.partition_by != parsed.versioning.business_key_refs:
        raise ValueError("LATEST_POLICY_BUSINESS_GRAIN_MISMATCH")
    if tuple(partition_by) != contract.partition_by:
        raise ValueError("LATEST_BUSINESS_GRAIN_MISMATCH")
    if recency_property_ref not in parsed.versioning.recency_property_refs:
        raise ValueError("LATEST_RECENCY_NOT_DECLARED")
    recency_type = payloads.get(payloads[recency_property_ref].get("value_type_ref"), {}).get("primitive_type")
    if (recency_type == "date") != (contract.time_ordering == "ISO_DATE"):
        raise ValueError("LATEST_TIME_POLICY_TYPE_MISMATCH")
    tie_refs = tuple(item.property_ref for item in contract.tie_break)
    if parsed.identity_property_ref not in tie_refs:
        raise ValueError("LATEST_TIE_BREAK_NOT_UNIQUE")
    for ref in tie_refs:
        if ref not in parsed.property_refs or payloads.get(ref, {}).get("owner_ref") != scope_object_ref:
            raise ValueError("LATEST_TIE_BREAK_OWNER_INVALID")
    order = ((recency_property_ref, "DESC"), *((item.property_ref, item.direction) for item in contract.tie_break))
    if ordering and tuple(ordering) != order:
        raise ValueError("LATEST_ORDER_POLICY_CONFLICT")
    return BoundLatestSelection(contract_digest=digest(contract), versioning_digest=version_digest,
        version_identity_ref=parsed.identity_property_ref,
        partition_by=contract.partition_by, ordering=tuple(ref for ref, _ in order),
        ordering_directions=tuple(direction for _, direction in order),
        null_time_policy=contract.null_time_policy, null_business_key_policy=contract.null_business_key_policy,
        time_ordering=contract.time_ordering)
