"""Opaque Catalog-issued capability for operational Science verification."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.models import ResolvedReleaseSet
from boi_api.app.science.rules import ResolvedRuleSet
from boi_api.app.science.safety import validate_with_closed_error

_ISSUER_CAPABILITY = object()
_SEAL = object()


def _attestation_payload(
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
    approval_snapshot: list[dict[str, Any]],
) -> dict[str, Any]:
    releases = (
        release_set.foundation_release,
        *release_set.domain_releases,
        *release_set.application_releases,
    )
    return {
        "schema_version": "science-operational-attestation/0.1",
        "release_set_digest": release_set.combined_digest,
        "releases": [
            {
                "release_id": release.release_id,
                "status": release.status,
                "content_hash": release.content_hash,
                "component_digests": release.component_digests,
            }
            for release in releases
        ],
        "approval_snapshot": approval_snapshot,
        "rule_set_digest": sha256_digest(rule_set),
    }


class OperationalVerification:
    """Immutable, non-serializable proof that Catalog completed active resolution."""

    __slots__ = (
        "_release_bytes",
        "_rule_bytes",
        "_attestation_bytes",
        "_attestation_digest",
        "_seal",
    )

    def __new__(
        cls,
        capability: object | None = None,
        *,
        release_set: ResolvedReleaseSet | None = None,
        rule_set: ResolvedRuleSet | None = None,
        approval_snapshot: list[dict[str, Any]] | None = None,
    ) -> "OperationalVerification":
        if (
            capability is not _ISSUER_CAPABILITY
            or release_set is None
            or rule_set is None
            or approval_snapshot is None
        ):
            raise TypeError(
                "OperationalVerification is issued only by active "
                "ScienceCatalog resolution"
            )
        self = super().__new__(cls)
        attestation = _attestation_payload(release_set, rule_set, approval_snapshot)
        object.__setattr__(self, "_release_bytes", canonical_json_bytes(release_set))
        object.__setattr__(self, "_rule_bytes", canonical_json_bytes(rule_set))
        object.__setattr__(
            self, "_attestation_bytes", canonical_json_bytes(attestation)
        )
        object.__setattr__(self, "_attestation_digest", sha256_digest(attestation))
        object.__setattr__(self, "_seal", _SEAL)
        return self

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    @property
    def attestation_digest(self) -> str:
        return self._attestation_digest

    @property
    def rule_set_digest(self) -> str:
        payload = json.loads(self._attestation_bytes)
        return str(payload["rule_set_digest"])

    @property
    def release_ids(self) -> tuple[str, ...]:
        payload = json.loads(self._attestation_bytes)
        return tuple(item["release_id"] for item in payload["releases"])

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("OperationalVerification is immutable")

    def __copy__(self) -> "OperationalVerification":
        raise TypeError("OperationalVerification cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "OperationalVerification":
        raise TypeError("OperationalVerification cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("OperationalVerification cannot be serialized")


def _issue_operational_verification(
    release_set: ResolvedReleaseSet,
    rule_set: ResolvedRuleSet,
    approval_snapshot: list[dict[str, Any]],
) -> OperationalVerification:
    return OperationalVerification(
        _ISSUER_CAPABILITY,
        release_set=release_set,
        rule_set=rule_set,
        approval_snapshot=approval_snapshot,
    )


def _open_operational_verification(
    operational: OperationalVerification,
) -> tuple[ResolvedReleaseSet, ResolvedRuleSet, Mapping[str, Any]]:
    if (
        type(operational) is not OperationalVerification
        or getattr(operational, "_seal", None) is not _SEAL
    ):
        raise TypeError("Catalog-issued operational verification is required")
    release_set = validate_with_closed_error(
        lambda: ResolvedReleaseSet.model_validate_json(operational._release_bytes),
        caught=(ValueError,),
        closed_error=TypeError("operational verification attestation is invalid"),
    )
    rule_set = validate_with_closed_error(
        lambda: ResolvedRuleSet.model_validate_json(operational._rule_bytes),
        caught=(ValueError,),
        closed_error=TypeError("operational verification attestation is invalid"),
    )
    attestation = json.loads(operational._attestation_bytes)
    expected = _attestation_payload(
        release_set,
        rule_set,
        list(attestation.get("approval_snapshot", [])),
    )
    if attestation != expected or operational._attestation_digest != sha256_digest(
        expected
    ):
        raise TypeError("operational verification attestation is invalid")
    return release_set, rule_set, attestation
