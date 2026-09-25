"""Opt-in semantic revision: business keys and version identity are distinct.

No migration or activation authority. 0.2 remains an unchanged historical reader.
"""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from . import domain_profile_v02 as v02


class BusinessVersionIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["boi/business-version-identity@1"]
    business_key_refs: tuple[str, ...] = Field(min_length=1)
    version_identity_ref: str = Field(min_length=1)
    recency_property_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def separate_identity(self):
        for values in (self.business_key_refs, self.recency_property_refs):
            if any(not value.strip() for value in values) or len(values) != len(set(values)):
                raise ValueError("DOMAIN_VERSION_PROPERTY_EMPTY_OR_DUPLICATE")
        if self.version_identity_ref in self.business_key_refs:
            raise ValueError("DOMAIN_BUSINESS_KEY_CONTAINS_VERSION_IDENTITY")
        if set(self.recency_property_refs) & {*self.business_key_refs, self.version_identity_ref}:
            raise ValueError("DOMAIN_RECENCY_IDENTITY_OVERLAP")
        return self


class ObjectTypeEntry(v02.ObjectTypeEntry):
    versioning: BusinessVersionIdentity | None = None

    @model_validator(mode="after")
    def validate_versioning(self):
        if self.versioning is not None:
            if self.versioning.version_identity_ref != self.identity_property_ref:
                raise ValueError("DOMAIN_VERSION_IDENTITY_MISMATCH")
            refs = {*self.versioning.business_key_refs, *self.versioning.recency_property_refs}
            if not refs <= set(self.property_refs):
                raise ValueError("DOMAIN_VERSION_PROPERTY_NOT_OWNED")
        return self


_ADAPTER = TypeAdapter(Annotated[Union[
    v02.TermEntry, ObjectTypeEntry, v02.PropertyDefinitionEntry, v02.RelationTypeEntry,
    v02.ValueTypeEntry, v02.MetricEntry, v02.RuleEntry,
], Field(discriminator="kind")])


def validate_domain_profile_entry(value: object):
    return _ADAPTER.validate_python(value)


def domain_profile_json_schema():
    return _ADAPTER.json_schema()


def versioning_closure_reasons(entries) -> set[str]:
    by_id = {entry.id: entry for entry in entries}
    reasons = set()
    for obj in entries:
        if not isinstance(obj, ObjectTypeEntry) or obj.versioning is None:
            continue
        version = obj.versioning
        for ref in (*version.business_key_refs, version.version_identity_ref, *version.recency_property_refs):
            prop = by_id.get(ref)
            if not isinstance(prop, v02.PropertyDefinitionEntry) or prop.owner_ref != obj.id:
                reasons.add("DOMAIN_VERSION_PROPERTY_OWNERSHIP_INVALID")
        for ref in version.recency_property_refs:
            prop = by_id.get(ref)
            value_type = by_id.get(getattr(prop, "value_type_ref", None))
            if not isinstance(value_type, v02.ValueTypeEntry) or value_type.primitive_type not in {"date", "datetime"}:
                reasons.add("DOMAIN_VERSION_RECENCY_TYPE_INVALID")
            if getattr(prop, "logical_role", None) not in {"event_time", "effective_time"} or getattr(prop, "time_semantics", "not_applicable") == "not_applicable":
                reasons.add("DOMAIN_VERSION_RECENCY_ROLE_INVALID")
    return reasons


def qualify_domain_profile_release(values) -> v02.DomainReleaseQualification:
    entries = tuple(validate_domain_profile_entry(value) for value in values)
    # Reuse existing closure checks, but never report the stripped 0.2 digest.
    base = v02.qualify_domain_profile_release([
        {key: value for key, value in entry.model_dump(mode="json").items() if key != "versioning"}
        for entry in entries
    ])
    reasons = set(base.reason_codes) | versioning_closure_reasons(entries)
    serialized = [entry.model_dump(mode="json") for entry in sorted(entries, key=lambda item: item.id)]
    digest = "sha256:" + hashlib.sha256(json.dumps(serialized, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return v02.DomainReleaseQualification(status="DRAFT_VALID" if reasons else "RELEASE_QUALIFIED",
        release_qualified=not reasons, entry_count=len(entries), revision_closure_digest=digest,
        reason_codes=tuple(sorted(reasons)))
