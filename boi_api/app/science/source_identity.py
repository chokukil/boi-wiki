"""Opaque Catalog-issued qualification for exact released Source URLs."""

from __future__ import annotations

from typing import Literal

from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.models import EvidenceLocator, ReviewedSourceURLProfile
from boi_api.app.science.safety import validate_with_closed_error

_ISSUER_CAPABILITY = object()
_SEAL = object()


def _build_reviewed_source_url_profile(
    *,
    qualification_state: Literal["candidate", "active"],
    release_set_digest: str,
    source_id: str,
    source_digest: str,
    evidence_id: str,
    evidence_digest: str,
    canonical_source_url: str,
    locator: EvidenceLocator,
) -> ReviewedSourceURLProfile:
    """Build the exact serializable profile later sealed by Catalog."""

    locator_url_digests = {
        field_name: sha256_digest(value)
        for field_name in ("resource_url", "requested_url", "resolved_url")
        if (value := getattr(locator, field_name)) is not None
    }
    payload = {
        "qualification_state": qualification_state,
        "release_set_digest": release_set_digest,
        "source_id": source_id,
        "source_digest": source_digest,
        "evidence_id": evidence_id,
        "evidence_digest": evidence_digest,
        "canonical_source_url": canonical_source_url,
        "canonical_source_url_digest": sha256_digest(canonical_source_url),
        "locator": locator,
        "locator_digest": sha256_digest(locator),
        "locator_url_digests": locator_url_digests,
    }
    provisional = ReviewedSourceURLProfile.model_construct(
        **payload,
        profile_digest="sha256:pending",
    )
    return ReviewedSourceURLProfile(
        **payload,
        profile_digest=sha256_digest(
            provisional.model_dump(mode="json", exclude={"profile_digest"})
        ),
    )


class ReviewedSourceURLIdentity:
    """Non-serializable proof that Catalog qualified one exact active profile."""

    __slots__ = ("_profile_bytes", "_seal")

    def __new__(
        cls,
        capability: object | None = None,
        *,
        profile: ReviewedSourceURLProfile | None = None,
    ) -> "ReviewedSourceURLIdentity":
        if (
            capability is not _ISSUER_CAPABILITY
            or profile is None
            or profile.qualification_state != "active"
        ):
            raise TypeError(
                "ReviewedSourceURLIdentity is issued only by active "
                "ScienceCatalog resolution"
            )
        self = super().__new__(cls)
        object.__setattr__(self, "_profile_bytes", canonical_json_bytes(profile))
        object.__setattr__(self, "_seal", _SEAL)
        return self

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ReviewedSourceURLIdentity is immutable")

    def __copy__(self) -> "ReviewedSourceURLIdentity":
        raise TypeError("ReviewedSourceURLIdentity cannot be copied")

    def __deepcopy__(self, memo: dict[int, object]) -> "ReviewedSourceURLIdentity":
        raise TypeError("ReviewedSourceURLIdentity cannot be copied")

    def __reduce__(self) -> object:
        raise TypeError("ReviewedSourceURLIdentity cannot be serialized")


def _issue_reviewed_source_url_identity(
    profile: ReviewedSourceURLProfile,
) -> ReviewedSourceURLIdentity:
    return ReviewedSourceURLIdentity(_ISSUER_CAPABILITY, profile=profile)


def _open_reviewed_source_url_identity(
    identity: ReviewedSourceURLIdentity,
) -> ReviewedSourceURLProfile:
    if (
        type(identity) is not ReviewedSourceURLIdentity
        or getattr(identity, "_seal", None) is not _SEAL
    ):
        raise TypeError("Catalog-issued reviewed Source URL identity is required")
    profile = validate_with_closed_error(
        lambda: ReviewedSourceURLProfile.model_validate_json(identity._profile_bytes),
        caught=(ValueError,),
        closed_error=TypeError("reviewed Source URL identity is invalid"),
    )
    if (
        profile.qualification_state != "active"
        or canonical_json_bytes(profile) != identity._profile_bytes
    ):
        raise TypeError("reviewed Source URL identity is invalid")
    return profile
