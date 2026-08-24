#!/usr/bin/env python3
"""Build immutable Science qualification fixture documents and anchored matrices."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "data" / "boi" / "public" / "science" / "qualification" / "cases"
FIXTURE_ROOT = (
    ROOT / "data" / "boi" / "public" / "science" / "qualification" / "fixtures"
)


def _split_document(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"qualification matrix lacks frontmatter: {path}")
    frontmatter, body = raw[4:].split("\n---\n", 1)
    return json.loads(frontmatter), body


def _condition(packet: dict[str, Any], key: str, value: Any) -> None:
    conditions = packet["normalized_claim"]["conditions"]
    conditions[:] = [item for item in conditions if item["condition_id"] != key]
    conditions.append({"condition_id": key, "value": value})


def _remove_condition(packet: dict[str, Any], key: str) -> None:
    conditions = packet["normalized_claim"]["conditions"]
    conditions[:] = [item for item in conditions if item["condition_id"] != key]


def _packets(case: dict[str, Any]) -> list[dict[str, Any]]:
    packets = [case["claim_packet"]]
    if "alternative_claim_packet" in case:
        packets.append(case["alternative_claim_packet"])
    return packets


def _quantity(packet: dict[str, Any], kind: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in packet["normalized_claim"]["quantities"]
            if item["quantity_kind"] == kind
        ),
        None,
    )


def _ensure_quantity(packet: dict[str, Any], kind: str, value: Any, unit: str) -> None:
    if _quantity(packet, kind) is None:
        packet["normalized_claim"]["quantities"].append(
            {"quantity_kind": kind, "value": value, "unit": unit}
        )


def _remove_quantity(packet: dict[str, Any], kind: str) -> None:
    quantities = packet["normalized_claim"]["quantities"]
    quantities[:] = [item for item in quantities if item["quantity_kind"] != kind]


def _set_quantity_unit(packet: dict[str, Any], kind: str, unit: str) -> None:
    quantity = _quantity(packet, kind)
    if quantity is None:
        raise ValueError(f"missing quantity {kind}")
    quantity["unit"] = unit


def _quantity_mentions(
    packet: dict[str, Any], quantity_kinds: set[str] | None = None
) -> str:
    quantities = [
        item
        for item in packet["normalized_claim"]["quantities"]
        if quantity_kinds is None or item["quantity_kind"] in quantity_kinds
    ]
    if not quantities:
        return ""
    rendered = [
        f"{item['quantity_kind'].replace('_', ' ')} = {item['value']} {item['unit']}"
        for item in quantities
    ]
    if len(rendered) == 1:
        return f"The reviewed quantity is {rendered[0]}."
    return "The reviewed quantities are " + "; ".join(rendered) + "."


def _without_generated_quantity_text(text: str) -> str:
    for marker in (" The reviewed quantity is ", " The reviewed quantities are "):
        if marker in text:
            text = text.split(marker, 1)[0]
    text = text.replace(" The quantity kind is recorded as value unit.", "")
    # Earlier generated prose may contain decimals, so a ``[^.]+`` regex can
    # cut through a number and corrupt the scientific sentence.  Generated
    # recording clauses always start at a sentence boundary; truncate there.
    candidates: list[int] = []
    for match in re.finditer(r" The ", text):
        tail = text[match.start() + 1 :]
        if tail.startswith("The bound ") or " is recorded as " in tail[:160]:
            candidates.append(match.start())
    if candidates:
        text = text[: min(candidates)]
    return " ".join(text.split()).strip()


def _sentence(text: str) -> str:
    text = " ".join(text.split()).strip()
    return text if text.endswith(".") else text + "."


def _with_quantities(
    text: str,
    packet: dict[str, Any],
    quantity_kinds: set[str] | None = None,
) -> str:
    text = _sentence(_without_generated_quantity_text(text))
    mention = _quantity_mentions(packet, quantity_kinds)
    return f"{text} {mention}" if mention else text


def _unit_operand_kinds(packet: dict[str, Any]) -> set[str]:
    quantities = packet["normalized_claim"]["quantities"]
    references = {
        item["quantity_kind"]
        for item in quantities
        if item["quantity_kind"].endswith("_reference")
    }
    return references | {kind.removesuffix("_reference") for kind in references}


SCIENTIFIC_BASES = {
    "sci-rule:materials:004": (
        "For a positive activation energy of 1 electron volt and an unchanged "
        "Arrhenius mechanism, raising temperature from 300 kelvin to 350 kelvin "
        "raises diffusivity from 1e-15 to 5e-15 square metres per second"
    ),
    "sci-rule:semiconductor-devices:003": (
        "In the low-field regime, electron concentration n = 1e21 and hole "
        "concentration p = 2e20 per cubic metre, with electron and hole "
        "mobilities 0.1 and 0.05 square metres per volt-second, give "
        "conductivity 17.623942974 siemens / meter through the carrier-conductivity relation"
    ),
}


def _rewrite_measurement_result(case: dict[str, Any]) -> None:
    kind = case["case_kind"]
    for packet in _packets(case):
        _remove_condition(packet, "result_expression_components")
        _ensure_quantity(packet, "measurement_uncertainty", 0.01, "meter")
        if kind == "missing_required_condition":
            _remove_condition(packet, "definition_context")
        elif kind == "false_red_prevention":
            _condition(packet, "definition_context", "quantity_value_only")
    if kind == "missing_required_condition":
        case["expected_verdict"] = "INSUFFICIENT_INFORMATION"
    elif kind == "false_red_prevention":
        case["expected_verdict"] = "OUTSIDE_VALIDITY_DOMAIN"


def _rewrite_uncertainty(case: dict[str, Any]) -> None:
    kind = case["case_kind"]
    for packet in _packets(case):
        _remove_condition(packet, "parameter_sign")
        if kind == "missing_required_condition":
            _remove_condition(packet, "definition_context")
        elif kind == "false_red_prevention":
            _condition(packet, "definition_context", "signed_measurement_error")
    if kind == "missing_required_condition":
        case["expected_verdict"] = "INSUFFICIENT_INFORMATION"
    elif kind == "false_red_prevention":
        case["expected_verdict"] = "OUTSIDE_VALIDITY_DOMAIN"


RECORD_RULES = {
    "sci-rule:common:008": {
        "quantity_kind": "validation_domain_length_limit",
        "normal_unit": "meter",
        "expected": "shall_be_maintained",
        "contradiction": "need_not_be_maintained",
        "other": "is_archived_after_project_close",
        "consistent": "A record of the validation domain of validated modelling and simulation shall be maintained.",
        "clear": "A record of the validation domain of validated modelling and simulation need not be maintained.",
        "false": "The project archive note says the validation-domain record is archived after project close.",
    },
    "sci-rule:common:011": {
        "quantity_kind": "validation_domain_temperature_limit",
        "normal_unit": "kelvin",
        "expected": "records_validation_domain",
        "contradiction": "need_not_record_validation_domain",
        "other": "records_configuration_history",
        "consistent": "A model-validation-domain record records the domain of validation of the validated modelling or simulation.",
        "clear": "A model-validation-domain record need not record any domain of validation.",
        "false": "The configuration-history record lists software revisions but makes no validation-domain claim.",
    },
}


def _rewrite_record_rule(case: dict[str, Any], config: dict[str, str]) -> str:
    kind = case["case_kind"]
    packets = _packets(case)
    for packet in packets:
        claim = packet["normalized_claim"]
        for key in (
            "model_identity",
            "validation_record_scope",
            "record_maintenance_context",
            "record_identity",
            "record_content",
        ):
            _remove_condition(packet, key)
        claim["polarity"] = "positive"
        claim["predicate"] = config["expected"]
        if kind == "clear_violation":
            claim["predicate"] = config["contradiction"]
        elif kind == "negation":
            claim["polarity"] = "negative"
        elif kind == "false_red_prevention":
            claim["predicate"] = config["other"]
        if kind == "missing_required_condition":
            _remove_quantity(packet, config["quantity_kind"])
        elif kind == "outside_validity_domain":
            _set_quantity_unit(packet, config["quantity_kind"], "second")

    # The ambiguous document is a marked yes/no response to one natural
    # statement.  The two interpretations must therefore exercise opposite
    # predicates while retaining the exact same source span.
    if kind == "decision_changing_ambiguity" and len(packets) == 2:
        packets[0]["normalized_claim"]["predicate"] = config["expected"]
        packets[1]["normalized_claim"]["predicate"] = config["contradiction"]

    verdicts = {
        "clear_violation": "VIOLATION",
        "in_scope_consistency": "CONSISTENT",
        "missing_required_condition": "INSUFFICIENT_INFORMATION",
        "outside_validity_domain": "OUTSIDE_VALIDITY_DOMAIN",
        "empirical_verification_required": "EMPIRICAL_VERIFICATION_REQUIRED",
        "negation": "VIOLATION",
        "unit_variation": "CONSISTENT",
        "paraphrase": "CONSISTENT",
        "false_red_prevention": "INSUFFICIENT_INFORMATION",
    }
    if kind in verdicts:
        case["expected_verdict"] = verdicts[kind]

    if kind == "clear_violation":
        return config["clear"]
    if kind == "missing_required_condition":
        return config["consistent"] + " No reviewed scale is stated for this fixture."
    if kind == "outside_validity_domain":
        return (
            config["consistent"]
            + " The accompanying scale is a time duration, not the reviewed physical dimension."
        )
    if kind == "empirical_verification_required":
        return (
            config["consistent"]
            + " A new unqualified observation requests confirmation of this statement."
        )
    if kind == "negation":
        return (
            "It is not true that "
            + config["consistent"][0].lower()
            + config["consistent"][1:]
        )
    if kind == "paraphrase":
        return (
            "In equivalent wording, "
            + config["consistent"][0].lower()
            + config["consistent"][1:]
        )
    if kind == "false_red_prevention":
        return config["false"]
    return config["consistent"]


def _rewrite_three_false_red_cases(rule_id: str, case: dict[str, Any]) -> str | None:
    if case["case_kind"] != "false_red_prevention":
        return None
    packet = case["claim_packet"]
    claim = packet["normalized_claim"]
    if rule_id == "sci-rule:materials:004":
        claim["predicate"] = "increases"
        return (
            "After the diffusion mechanism changed, temperature rose from 300 kelvin to 350 kelvin "
            "and the measured diffusion coefficient increased from 1e-15 meter ** 2 / second to "
            "5e-15 meter ** 2 / second; the activation energy was 1 electron volt."
        )
    if rule_id == "sci-rule:semiconductor-devices:003":
        _condition(packet, "transport_regime", "high_field")
        _condition(
            packet,
            "carrier_parameter_scope",
            "electron_and_hole_concentrations_and_mobilities",
        )
        return (
            "In a high-field transport regime, the report does not apply the low-field carrier-conductivity relation even though "
            "electron concentration is 1e21 1 / meter ** 3, hole concentration is 2e20 1 / meter ** 3, "
            "electron mobility is 0.1 meter ** 2 / volt / second, hole mobility is 0.05 meter ** 2 / volt / second, "
            "conductivity is 17.623942974 siemens / meter, and conductivity scale is 1 siemens / meter."
        )
    if rule_id == "sci-rule:spin-coating:004":
        claim["predicate"] = "increases"
        claim["process_stage"] = "dispense_stage"
        return (
            "During a low-speed dispense stage, increasing spin speed increases transient liquid-puddle thickness because the "
            "dispense rate rises concurrently; the recorded spin_rate is 1 rpm."
        )
    return None


def _base_text_for_case(
    rule_id: str,
    case: dict[str, Any],
    original_text: str,
) -> str:
    if rule_id in RECORD_RULES:
        return _rewrite_record_rule(case, RECORD_RULES[rule_id])
    replacement = _rewrite_three_false_red_cases(rule_id, case)
    if replacement is not None:
        return replacement
    return original_text


def _ambiguous_text(consistent_text: str, packet: dict[str, Any]) -> str:
    proposition = _without_generated_quantity_text(consistent_text).rstrip(".")
    return _with_quantities(
        f"A smudged yes-or-no mark appears in the margin beside the statement “{proposition}”",
        packet,
    )


def _build_one(path: Path) -> None:
    payload, body = _split_document(path)
    matrix = payload["science"]
    rule_id = matrix["rule_id"]
    domain = rule_id.split(":")[1]
    number = rule_id.split(":")[2]

    cases = matrix["cases"]
    original_texts = {
        case["case_kind"]: case["claim_packet"]["source_span"]["exact"]
        for case in cases
    }

    for case in cases:
        if rule_id == "sci-rule:common:004":
            _rewrite_measurement_result(case)
        elif rule_id == "sci-rule:common:005":
            _rewrite_uncertainty(case)

    generated: dict[str, str] = {}
    semantic_bases: dict[str, str] = {}
    for case in cases:
        kind = case["case_kind"]
        text = _base_text_for_case(rule_id, case, original_texts[kind])
        packet = case["claim_packet"]
        if (
            kind in {"unit_variation", "decision_changing_ambiguity"}
            and rule_id in SCIENTIFIC_BASES
        ):
            text = SCIENTIFIC_BASES[rule_id]
        elif kind == "unit_variation" and "in_scope_consistency" in semantic_bases:
            text = semantic_bases["in_scope_consistency"]
        if kind == "decision_changing_ambiguity":
            consistent = SCIENTIFIC_BASES.get(rule_id) or semantic_bases.get(
                "in_scope_consistency"
            )
            if consistent is None:
                consistent_case = next(
                    item
                    for item in cases
                    if item["case_kind"] == "in_scope_consistency"
                )
                consistent = _base_text_for_case(
                    rule_id,
                    consistent_case,
                    original_texts["in_scope_consistency"],
                )
            text = _ambiguous_text(consistent, packet)
        semantic_bases[kind] = text
        if kind == "decision_changing_ambiguity":
            pass
        elif kind == "unit_variation":
            operand_kinds = _unit_operand_kinds(packet)
            if rule_id == "sci-rule:common:004":
                operand_kinds.add("measurement_uncertainty")
            text = _with_quantities(text, packet, operand_kinds)
        elif domain == "common" or rule_id in RECORD_RULES:
            text = _with_quantities(text, packet)
        else:
            text = _sentence(text)
        generated[kind] = _sentence(text)

    header = (
        "Science Verifier immutable qualification fixture\n"
        f"Rule: {rule_id}\n"
        "Each labelled paragraph is an independently anchored review case.\n\n"
    )
    chunks = [header]
    offsets: dict[str, tuple[int, int]] = {}
    for case in cases:
        kind = case["case_kind"]
        chunks.append(f"[{kind}]\n")
        start = sum(len(item) for item in chunks)
        chunks.append(generated[kind])
        end = sum(len(item) for item in chunks)
        offsets[kind] = (start, end)
        chunks.append("\n\n")
    chunks.append("End of immutable qualification fixture.\n")
    document = "".join(chunks)
    digest = "sha256:" + hashlib.sha256(document.encode("utf-8")).hexdigest()
    document_ref = f"qualification-fixture:{domain}:{number}"

    for case in cases:
        kind = case["case_kind"]
        start, end = offsets[kind]
        for packet in _packets(case):
            packet["document_ref"] = document_ref
            packet["document_digest"] = digest
            packet["source_span"] = {
                "offset_encoding": "unicode_code_point",
                "start": start,
                "end": end,
                "exact": generated[kind],
                "prefix": document[max(0, start - 64) : start],
                "suffix": document[end : end + 64],
            }

    fixture_path = FIXTURE_ROOT / domain / f"{domain}-{number}.txt"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(document, encoding="utf-8")
    path.write_text(
        "---\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n---\n" + body,
        encoding="utf-8",
    )


def main() -> None:
    paths = sorted(CASE_ROOT.glob("*/q-*.md"))
    if len(paths) != 44:
        raise SystemExit(f"expected 44 qualification matrices, found {len(paths)}")
    for path in paths:
        _build_one(path)
    print(f"Built {len(paths)} immutable qualification fixture documents.")


if __name__ == "__main__":
    main()
