from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.models import (
    ClaimPacket,
    ConditionConstraint,
    InterpretationRecord,
    PackDependency,
    PrimaryVerdict,
    ResolvedRelease,
    ResolvedReleaseSet,
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


@pytest.mark.parametrize(
    "relation",
    ["depends_on", "uses", "specializes", "adds_evidence", "validated_by", "supersedes"],
)
def test_pack_dependency_is_a_closed_typed_edge(relation: str):
    """Removing the enum boundary would let an executable override edge enter a Pack graph."""
    edge = PackDependency.model_validate({"relation": relation, "ref": "sci-pack:foundation"})

    assert edge.relation.value == relation
    assert edge.ref == "sci-pack:foundation"


@pytest.mark.parametrize(
    "payload",
    [
        {"relation": "override", "ref": "sci-pack:foundation"},
        {"ref": "sci-pack:foundation"},
        {"relation": "uses", "ref": ""},
    ],
)
def test_pack_dependency_rejects_override_missing_relation_and_malformed_ref(payload: dict):
    """Loosening either edge field must fail before catalog relationship resolution."""
    with pytest.raises(ValidationError):
        PackDependency.model_validate(payload)


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("location", ["quantity", "condition"])
def test_claim_packet_rejects_literal_nonfinite_numbers(nonfinite: float, location: str):
    """Removing either finite-number gate would admit non-canonical scientific inputs."""
    fixture = load_named_fixture("claims.json", "monotonic-increase")
    if location == "quantity":
        fixture["normalized_claim"]["quantities"] = [
            {"quantity_kind": "temperature", "value": nonfinite, "unit": "kelvin"}
        ]
    else:
        fixture["normalized_claim"]["conditions"] = [
            {"condition_id": "temperature", "value": nonfinite, "unit": "kelvin"}
        ]

    with pytest.raises(ValidationError, match="finite"):
        ClaimPacket.model_validate(fixture)


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_interpretation_model_settings_reject_nonfinite_numbers(nonfinite: float):
    """A model setting must remain canonical even though it cannot affect the verdict engine."""
    payload = {
        "interpretation_id": "sci-interpretation:fixture",
        "document_digest": "sha256:document",
        "candidate_claims": [],
        "model_id": "fixture-model",
        "model_settings": {"temperature": nonfinite},
        "prompt_version": "0.1",
        "dictionary_release_id": "dictionary:0.1",
        "ontology_release_id": "ontology:0.1",
        "ontology_refs": [],
        "candidate_meanings": [],
        "decision_impact": [],
        "user_revision_history": [],
        "confirmed_claim_packet_digest": None,
        "response_digest": "sha256:response",
    }

    with pytest.raises(ValidationError, match="finite"):
        InterpretationRecord.model_validate(payload)


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_rejects_nonfinite_literals(nonfinite: float):
    """Allowing JSON NaN extensions would make digests non-canonical across runtimes."""
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical_json_bytes({"value": nonfinite})


@pytest.mark.parametrize("mutation", ["combined_digest", "components"])
def test_resolved_release_set_rejects_a_nonexact_combination(mutation: str):
    """A forged digest or omitted component must not remain an exact resolved Release set."""
    release = ResolvedRelease.model_validate(
        load_named_fixture("releases/release.json", "foundation-release")
    )
    resolved = ResolvedReleaseSet.from_single_foundation(release)
    payload = resolved.model_dump(mode="json")
    if mutation == "combined_digest":
        payload["combined_digest"] = "sha256:forged"
    else:
        payload["components"] = []
        payload["rule_components"] = []

    with pytest.raises(ValidationError, match="exact combined digest|exactly match resolved releases"):
        ResolvedReleaseSet.model_validate(payload)


def test_condition_constraint_supports_closed_scalar_membership():
    """Product-scoped Evidence may encode a closed list without prose matching."""
    constraint = ConditionConstraint(
        key="product_grade",
        operator="in",
        values=["AZ 125nXT-10 B", "AZ 125nXT-7 B"],
    )

    assert constraint.values == ["AZ 125nXT-10 B", "AZ 125nXT-7 B"]
    with pytest.raises(ValidationError, match="membership condition"):
        ConditionConstraint(key="product_grade", operator="in", values=[])
    with pytest.raises(ValidationError, match="finite"):
        ConditionConstraint(key="numeric_grade", operator="in", values=[float("nan")])
