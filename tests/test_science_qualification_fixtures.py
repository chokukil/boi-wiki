from __future__ import annotations

import hashlib
from copy import deepcopy
from pathlib import Path

import pytest

from boi_api.app.science.catalog import ScienceCatalog
from boi_api.app.science.exceptions import ScienceCatalogError
from boi_api.app.science.models import ClaimPacket
from boi_api.app.science.units import source_span_mentions_quantity

BOI_ROOT = Path(__file__).resolve().parents[1] / "data" / "boi"
FIXTURE_ROOT = BOI_ROOT / "public" / "science" / "qualification" / "fixtures"
PACK_IDS = (
    "sci-pack:science-foundation/0.1.0",
    "sci-pack:physical-principles/0.1.0",
    "sci-pack:chemical-principles/0.1.0",
    "sci-pack:circuit-principles/0.1.0",
    "sci-pack:materials-science/0.1.0",
    "sci-pack:semiconductor-devices/0.1.0",
    "sci-pack:spin-coating/0.1.0",
)


@pytest.fixture(scope="module")
def science_catalog() -> ScienceCatalog:
    return ScienceCatalog(BOI_ROOT)


def _packets(case) -> list[ClaimPacket]:
    packets = [ClaimPacket.model_validate(case.claim_packet)]
    if hasattr(case, "alternative_claim_packet"):
        packets.append(ClaimPacket.model_validate(case.alternative_claim_packet))
    return packets


def test_qualification_packets_are_exact_anchored_full_document_spans(
    science_catalog: ScienceCatalog,
):
    for pack_id in PACK_IDS:
        for rule_id in science_catalog.pack(pack_id).rule_refs:
            for case in science_catalog.qualification_cases(rule_id):
                for packet in _packets(case):
                    _, domain, number = packet.document_ref.split(":")
                    fixture = FIXTURE_ROOT / domain / f"{domain}-{number}.txt"
                    document_bytes = fixture.read_bytes()
                    document = document_bytes.decode("utf-8")
                    span = packet.source_span
                    assert span.start > 0
                    assert span.end < len(document)
                    assert document[span.start : span.end] == span.exact
                    assert span.prefix and document[: span.start].endswith(span.prefix)
                    assert span.suffix and document[span.end :].startswith(span.suffix)
                    assert (
                        packet.document_digest
                        == "sha256:" + hashlib.sha256(document_bytes).hexdigest()
                    )


def test_unit_cases_anchor_both_reviewed_quantity_representations(
    science_catalog: ScienceCatalog,
):
    for pack_id in PACK_IDS:
        for rule_id in science_catalog.pack(pack_id).rule_refs:
            case = next(
                item
                for item in science_catalog.qualification_cases(rule_id)
                if item.case_kind == "unit_variation"
            )
            packet = ClaimPacket.model_validate(case.claim_packet)
            quantities = {
                item.quantity_kind: item for item in packet.normalized_claim.quantities
            }
            reference_kinds = [
                kind for kind in quantities if kind.endswith("_reference")
            ]
            assert len(reference_kinds) == 1
            reference_kind = reference_kinds[0]
            operand_kinds = {
                reference_kind,
                reference_kind.removesuffix("_reference"),
            }
            for kind in operand_kinds:
                assert source_span_mentions_quantity(
                    packet.source_span.exact, quantities[kind]
                )


def test_measurement_result_packets_anchor_value_and_uncertainty(
    science_catalog: ScienceCatalog,
):
    for case in science_catalog.qualification_cases("sci-rule:common:004"):
        for packet in _packets(case):
            quantities = {
                item.quantity_kind: item for item in packet.normalized_claim.quantities
            }
            assert {"measured_quantity_value", "measurement_uncertainty"} <= set(
                quantities
            )
            uncertainty = quantities["measurement_uncertainty"]
            assert str(uncertainty.value) in packet.source_span.exact
            assert uncertainty.unit in packet.source_span.exact


def test_catalog_rejects_unit_case_with_a_structured_operand_omitted(
    science_catalog: ScienceCatalog,
):
    matrix = science_catalog.qualification_matrix("sci-matrix:common:001")
    raw_case = deepcopy(
        next(item for item in matrix.cases if item["case_kind"] == "unit_variation")
    )
    quantities = raw_case["claim_packet"]["normalized_claim"]["quantities"]
    quantities[:] = [
        item
        for item in quantities
        if item["quantity_kind"] != "sample_length_reference"
    ]

    with pytest.raises(ScienceCatalogError, match="lacks target/reference operands"):
        science_catalog._validate_qualification_case(matrix, raw_case)


def test_catalog_rejects_self_hash_and_blank_context_anchors(
    science_catalog: ScienceCatalog,
):
    matrix = science_catalog.qualification_matrix("sci-matrix:common:001")
    raw_case = deepcopy(matrix.cases[0])
    packet = raw_case["claim_packet"]
    packet["document_digest"] = (
        "sha256:"
        + hashlib.sha256(packet["source_span"]["exact"].encode("utf-8")).hexdigest()
    )

    with pytest.raises(ScienceCatalogError, match="fixture digest mismatch"):
        science_catalog._validate_qualification_case(matrix, raw_case)

    raw_case = deepcopy(matrix.cases[0])
    raw_case["claim_packet"]["source_span"]["prefix"] = ""
    with pytest.raises(ScienceCatalogError, match="fixture anchor mismatch"):
        science_catalog._validate_qualification_case(matrix, raw_case)
