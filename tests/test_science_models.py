from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.models import (
    ClaimPacket,
    PrimaryVerdict,
    ResolvedRelease,
    VerificationReport,
)


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "science"


def load_named_fixture(relative_path: str, name: str) -> dict[str, object]:
    entries = json.loads(FIXTURE_ROOT.joinpath(relative_path).read_text(encoding="utf-8"))
    return entries[name]


def test_primary_verdict_is_closed_and_claim_digest_is_stable():
    assert {item.value for item in PrimaryVerdict} == {
        "VIOLATION",
        "CONSISTENT",
        "INSUFFICIENT_INFORMATION",
        "OUTSIDE_VALIDITY_DOMAIN",
        "EMPIRICAL_VERIFICATION_REQUIRED",
    }

    packet = ClaimPacket.model_validate(load_named_fixture("claims.json", "monotonic-increase"))

    assert sha256_digest(packet) == sha256_digest(packet.model_dump(mode="json"))
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert sha256_digest({"b": 1, "a": 2}) == (
        "sha256:d3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772"
    )


def test_source_span_uses_unicode_code_points_and_rejects_nonmatching_text_length():
    fixture = load_named_fixture("claims.json", "monotonic-increase")
    fixture["source_span"] = {
        "offset_encoding": "unicode_code_point",
        "start": 4,
        "end": 7,
        "exact": "가나다",
        "prefix": "앞",
        "suffix": "뒤",
    }

    assert ClaimPacket.model_validate(fixture).source_span.end == 7

    fixture["source_span"]["end"] = 8
    with pytest.raises(ValidationError, match="source span does not match Unicode code-point length"):
        ClaimPacket.model_validate(fixture)


def test_packets_forbid_unknown_fields_at_every_contract_boundary():
    fixture = load_named_fixture("claims.json", "monotonic-increase")
    fixture["normalized_claim"]["unexpected"] = "not allowed"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ClaimPacket.model_validate(fixture)


def test_release_and_report_preserve_tuple_components_and_json_serialization():
    release = ResolvedRelease.model_validate(
        load_named_fixture("releases/release.json", "foundation-release")
    )
    report = VerificationReport.model_validate(
        {
            "report_id": "sci-report:fixture",
            "document_ref": "boi:public:science:document:fixture",
            "document_digest": "sha256:document-fixture",
            "release_selection": {
                "foundation": release.release_id,
                "domains": [],
                "applications": [],
            },
            "release_digests": {release.release_id: release.content_hash},
            "interpretation_ids": ["sci-interpretation:fixture"],
            "verdict_packets": [],
            "unresolved_ambiguities": [],
            "annotations": [],
            "created_at": datetime(2026, 8, 25, tzinfo=timezone.utc),
            "created_by": "science-admin",
            "report_digest": "sha256:report-fixture",
        }
    )

    assert isinstance(release.components, tuple)
    assert canonical_json_bytes(report).startswith(b'{"annotations":[]')
