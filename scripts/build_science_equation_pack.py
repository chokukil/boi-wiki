#!/usr/bin/env python3
"""Build the inactive six-domain Equation Knowledge candidate pack.

This script only rewrites draft Knowledge/Rule documents.  It never changes
review events, Release state, or activation metadata.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from boi_api.app.science.digests import sha256_digest  # noqa: E402
from boi_api.app.science.equations import ScienceEquationKnowledge  # noqa: E402
from boi_api.app.science.rules import (  # noqa: E402
    EQUATION_EVALUATOR_CONTRACT_DIGEST,
    EQUATION_EVALUATOR_ID,
    EQUATION_EVALUATOR_VERSION,
    EquationRuleBinding,
)


REVIEWED_AT = "2026-08-25T11:00:00+09:00"


def _read_document(path: Path) -> tuple[dict[str, Any], str, bool]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError(f"invalid frontmatter: {path}")
    raw_metadata, body = text[4:].split("\n---\n", 1)
    is_json = raw_metadata.lstrip().startswith("{")
    metadata = json.loads(raw_metadata) if is_json else yaml.safe_load(raw_metadata)
    if not isinstance(metadata, dict):
        raise ValueError(f"invalid metadata: {path}")
    return metadata, body, is_json


def _write_document(
    path: Path, metadata: dict[str, Any], body: str, *, is_json: bool
) -> None:
    if is_json:
        frontmatter = json.dumps(metadata, ensure_ascii=False, indent=2)
    else:
        frontmatter = yaml.safe_dump(
            metadata, allow_unicode=True, sort_keys=False
        ).rstrip()
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")


def _var(
    variable_id: str,
    symbol: str,
    concept: str,
    quantity: str,
    dimension: dict[str, int],
    unit: str,
    definition: str,
    *,
    sign: str = "any",
    domain: str = "real",
    source_symbol: str | None = None,
) -> dict[str, Any]:
    return {
        "variable_id": variable_id,
        "symbol": symbol,
        "concept_ref": concept,
        "quantity_kind": quantity,
        "dimension": dimension,
        "unit": unit,
        "definition": definition,
        "domain": domain,
        "sign_constraint": sign,
        "source_symbol": source_symbol or symbol,
    }


def _v(variable_id: str) -> dict[str, str]:
    return {"op": "variable", "variable_id": variable_id}


def _binary(op: str, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {"op": op, "left": left, "right": right}


def _evidence_locator(raw: dict[str, Any], equation_label: str) -> dict[str, Any]:
    locator = raw["science"]["locator"]
    result = {
        "medium": locator["medium"],
        "resource_url": locator["resource_url"],
        "content_hash": locator["content_hash"],
        "exact": True,
        "equation_label": equation_label,
    }
    for field in (
        "section",
        "pdf_page_index",
        "printed_page",
        "heading",
        "sentence_ordinal",
        "field_path",
    ):
        if field in locator:
            result[field] = locator[field]
    return result


def _equation(
    spec: dict[str, Any], evidence_metadata: dict[str, Any]
) -> dict[str, Any]:
    evidence = evidence_metadata["science"]
    semantic_expression = {
        "schema_version": "science-expression/0.1",
        "root": deepcopy(spec["root"]),
    }
    variables = []
    mapping = []
    variable_context = []
    for configured in spec["variables"]:
        variable = {
            key: deepcopy(value)
            for key, value in configured.items()
            if key != "source_symbol"
        }
        variables.append(variable)
        source_symbol = configured["source_symbol"]
        mapping.append(
            {
                "source_symbol": source_symbol,
                "variable_id": configured["variable_id"],
            }
        )
        variable_context.append(
            {
                "source_symbol": source_symbol,
                "definition": configured["definition"],
                "unit_text": configured["unit"],
            }
        )
    locator = _evidence_locator(evidence_metadata, spec["equation_label"])
    conventions = {
        "coordinate_convention": spec["coordinate_convention"],
        "sign_convention": spec["sign_convention"],
        "unit_convention": spec["unit_convention"],
    }
    original_notation = evidence["locator"].get("equation", evidence["original_text"])
    transcription = {
        "transcription_id": spec["equation_id"].replace(
            "sci:equation:", "sci:transcription:"
        ),
        "original_notation": original_notation,
        "original_notation_hash": "sha256:"
        + __import__("hashlib").sha256(original_notation.encode("utf-8")).hexdigest(),
        "variable_context": variable_context,
        "variable_context_hash": sha256_digest(variable_context),
        **conventions,
        "conventions_hash": sha256_digest(conventions),
        "relation_notation": spec["relation_notation"],
        "transcription_method": (
            "ocr_reviewed"
            if "ocr" in str(evidence["locator"].get("transcription_method", "")).lower()
            else "manual"
        ),
        "review_state": "reviewed",
        "reviewer": "agent:codex-transcription-draft",
        "reviewed_at": REVIEWED_AT,
        "semantic_expression_digest": sha256_digest(semantic_expression),
        "transcription_digest": "",
    }
    transcription["transcription_digest"] = sha256_digest(
        {
            key: value
            for key, value in transcription.items()
            if key != "transcription_digest"
        }
    )
    operators = sorted(_semantic_operators(semantic_expression["root"]))
    evaluator = None
    if spec["decision_use"] == "deterministic_rule":
        evaluator = {
            "evaluator_id": EQUATION_EVALUATOR_ID,
            "version": EQUATION_EVALUATOR_VERSION,
            "expression_schema_version": "science-expression/0.1",
            "allowed_operators": operators,
            "evaluator_digest": EQUATION_EVALUATOR_CONTRACT_DIGEST,
        }
    payload = {
        "equation_id": spec["equation_id"],
        "scientific_role": spec["scientific_role"],
        "decision_use": spec["decision_use"],
        "semantic_expression": semantic_expression,
        "display_latex": spec["display_latex"],
        "plain_text": spec["plain_text"],
        "accessibility_reading": spec["accessibility_reading"],
        "variables": variables,
        "assumptions": spec["assumptions"],
        "applicability": spec["applicability"],
        "invalid_outside": spec["invalid_outside"],
        "boundary_conditions": spec.get("boundary_conditions", []),
        "approximation": spec.get("approximation"),
        "empirical_fit": spec.get("empirical_fit"),
        "original_notation_mapping": mapping,
        "evidence_uses": [
            {
                "evidence_ref": evidence["evidence_id"],
                "purpose": spec["evidence_purpose"],
                "claim_scope_hash": evidence["claim_scope_hash"],
                "locator": locator,
                "locator_digest": sha256_digest(locator),
                "transcription": transcription,
            }
        ],
        "evaluator": evaluator,
        "equation_digest": "",
    }
    payload["equation_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "equation_digest"}
    )
    return ScienceEquationKnowledge.model_validate(payload).model_dump(
        mode="json", exclude_unset=True
    )


def _semantic_operators(node: dict[str, Any]) -> set[str]:
    operators = {node["op"]}
    for field in (
        "operand",
        "left",
        "right",
        "expression",
        "integrand",
        "lower",
        "upper",
    ):
        if isinstance(node.get(field), dict):
            operators |= _semantic_operators(node[field])
    for child in node.get("operands") or []:
        operators |= _semantic_operators(child)
    for row in node.get("rows") or []:
        for child in row:
            operators |= _semantic_operators(child)
    return operators


def _binding(spec: dict[str, Any], equation: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "equation_id": equation["equation_id"],
        "equation_digest": equation["equation_digest"],
        "evaluator_id": EQUATION_EVALUATOR_ID,
        "evaluator_version": EQUATION_EVALUATOR_VERSION,
        "evaluator_digest": EQUATION_EVALUATOR_CONTRACT_DIGEST,
        "constraint_operator": spec["rule_operator"],
        "variable_mappings": spec["rule_mappings"],
        "binding_digest": "",
    }
    payload["binding_digest"] = sha256_digest(
        {key: value for key, value in payload.items() if key != "binding_digest"}
    )
    return EquationRuleBinding.model_validate(payload).model_dump(mode="json")


def _specs() -> list[dict[str, Any]]:
    energy = {"mass": 1, "length": 2, "time": -2}
    voltage = {
        "mass": 1,
        "length": 2,
        "time": -3,
        "electric_current": -1,
    }
    return [
        {
            "domain": "physics",
            "knowledge": "sci-phy-003.md",
            "evidence": "work-energy-power.md",
            "rule": "r-phy-003.md",
            "equation_id": "sci:equation:physics:applied-work-kinetic-energy-change",
            "scientific_role": "law",
            "decision_use": "deterministic_rule",
            "root": {
                "op": "relation",
                "relation": "eq",
                "left": _v("applied_work"),
                "right": _v("kinetic_energy_change"),
            },
            "display_latex": r"W_{\mathrm{applied}} = \Delta K",
            "plain_text": "W_applied = delta_K",
            "accessibility_reading": "Applied-force work equals the change in kinetic energy.",
            "variables": [
                _var(
                    "applied_work",
                    "W_applied",
                    "sci:concept:applied-force-work",
                    "applied_work",
                    energy,
                    "joule",
                    "Work done by the applied force on the bounded object.",
                    source_symbol="work done by the applied force",
                ),
                _var(
                    "kinetic_energy_change",
                    "ΔK",
                    "sci:concept:kinetic-energy-change",
                    "kinetic_energy_change",
                    energy,
                    "joule",
                    "Change in the object's kinetic energy.",
                    source_symbol="change in kinetic energy",
                ),
            ],
            "assumptions": [
                "The object boundary and all applied-force work terms are explicit."
            ],
            "applicability": [
                "Work-kinetic-energy theorem for the stated bounded object."
            ],
            "invalid_outside": [
                "Incomplete work accounting or an unspecified object system."
            ],
            "coordinate_convention": "Work and kinetic-energy change use the same bounded object and interval.",
            "sign_convention": "Positive work increases kinetic energy under the cited theorem statement.",
            "unit_convention": "Both energy quantities use coherent SI joules.",
            "relation_notation": "equals",
            "equation_label": "Section 13.6 theorem statement (prose)",
            "evidence_purpose": "Bind the exact work-kinetic-energy equality and its object scope.",
            "rule_operator": "equal",
            "rule_mappings": [
                {
                    "equation_variable_id": "applied_work",
                    "claim_quantity_kind": "applied_work",
                    "constraint_operand": "left",
                },
                {
                    "equation_variable_id": "kinetic_energy_change",
                    "claim_quantity_kind": "kinetic_energy_change",
                    "constraint_operand": "right_1",
                },
            ],
        },
        {
            "domain": "chemistry",
            "knowledge": "sci-che-001.md",
            "evidence": "amount-concentration.md",
            "rule": "r-che-001.md",
            "equation_id": "sci:equation:chemistry:molar-concentration-definition",
            "scientific_role": "definition",
            "decision_use": "deterministic_rule",
            "root": {
                "op": "relation",
                "relation": "eq",
                "left": _v("molar_concentration"),
                "right": _binary("divide", _v("solute_amount"), _v("solution_volume")),
            },
            "display_latex": r"c = \frac{n_{\mathrm{solute}}}{V_{\mathrm{solution}}}",
            "plain_text": "c = n_solute / V_solution",
            "accessibility_reading": "Molar concentration equals solute amount divided by solution volume.",
            "variables": [
                _var(
                    "molar_concentration",
                    "c",
                    "sci:concept:molar-concentration",
                    "molar_concentration",
                    {"length": -3, "amount_of_substance": 1},
                    "mole / liter",
                    "Amount concentration under the molarity convention.",
                    source_symbol="Molar concentration (molarity)",
                ),
                _var(
                    "solute_amount",
                    "n_solute",
                    "sci:concept:solute-amount",
                    "solute_amount",
                    {"amount_of_substance": 1},
                    "mole",
                    "Amount of the named solute in moles.",
                    sign="nonnegative",
                    source_symbol="number of moles of solute",
                ),
                _var(
                    "solution_volume",
                    "V_solution",
                    "sci:concept:solution-volume",
                    "solution_volume",
                    {"length": 3},
                    "liter",
                    "Final volume of the solution, not solvent volume.",
                    sign="positive",
                    source_symbol="liter of solution",
                ),
            ],
            "assumptions": [
                "The concentration convention is molarity and the denominator is solution volume."
            ],
            "applicability": ["Named solute amount per final solution volume."],
            "invalid_outside": [
                "Other concentration conventions or zero/undefined solution volume."
            ],
            "boundary_conditions": [
                {
                    "condition_id": "positive-solution-volume",
                    "statement": "Solution volume must be positive.",
                    "variable_id": "solution_volume",
                    "operator": "gt",
                    "value": "0",
                    "unit": "liter",
                }
            ],
            "coordinate_convention": "No spatial coordinate convention is used by this scalar definition.",
            "sign_convention": "Amounts are nonnegative and the solution volume is positive.",
            "unit_convention": "The cited convention is moles of solute per litre of solution.",
            "relation_notation": "definition",
            "equation_label": "Molarity definition sentence (prose)",
            "evidence_purpose": "Bind the exact molarity definition and distinguish solution from solvent volume.",
            "rule_operator": "quotient",
            "rule_mappings": [
                {
                    "equation_variable_id": "molar_concentration",
                    "claim_quantity_kind": "molar_concentration",
                    "constraint_operand": "left",
                },
                {
                    "equation_variable_id": "solute_amount",
                    "claim_quantity_kind": "solute_amount",
                    "constraint_operand": "right_1",
                },
                {
                    "equation_variable_id": "solution_volume",
                    "claim_quantity_kind": "solution_volume",
                    "constraint_operand": "right_2",
                },
            ],
        },
        {
            "domain": "circuits",
            "knowledge": "sci-cir-002.md",
            "evidence": "kvl-law.md",
            "rule": "r-cir-002.md",
            "equation_id": "sci:equation:circuits:kvl-loop-balance",
            "scientific_role": "law",
            "decision_use": "deterministic_rule",
            "root": {
                "op": "relation",
                "relation": "eq",
                "left": _v("algebraic_voltage_sum"),
                "right": _v("zero_voltage"),
            },
            "display_latex": r"\sum_{k} V_k = 0",
            "plain_text": "sum(loop voltages with sign) = 0 V",
            "accessibility_reading": "The algebraic sum of voltages around the loop equals zero.",
            "variables": [
                _var(
                    "algebraic_voltage_sum",
                    "ΣV_loop",
                    "sci:concept:loop-voltage-sum",
                    "algebraic_voltage_sum",
                    voltage,
                    "volt",
                    "Algebraic voltage sum around the bound loop.",
                    source_symbol="voltages in the loop",
                ),
                _var(
                    "zero_voltage",
                    "0 V",
                    "sci:concept:zero-voltage",
                    "zero_voltage",
                    voltage,
                    "volt",
                    "Zero potential difference used as the equality reference.",
                    source_symbol="zero",
                ),
            ],
            "assumptions": [
                "Voltage polarities and loop traversal direction are assigned consistently."
            ],
            "applicability": [
                "A bound closed path in the stated lumped-circuit context."
            ],
            "invalid_outside": [
                "Inconsistent polarity/traversal assignments or unqualified non-lumped electromagnetic cases."
            ],
            "boundary_conditions": [
                {
                    "condition_id": "zero-reference",
                    "statement": "The equality reference is zero volts.",
                    "variable_id": "zero_voltage",
                    "operator": "eq",
                    "value": "0",
                    "unit": "volt",
                }
            ],
            "coordinate_convention": "One traversal direction is fixed around the bound closed loop.",
            "sign_convention": "Each voltage sign follows its polarity relative to that traversal direction.",
            "unit_convention": "Every loop term and the zero reference use volts.",
            "relation_notation": "equals",
            "equation_label": "KVL definition sentence (prose)",
            "evidence_purpose": "Bind the loop-voltage equality and its polarity/traversal convention.",
            "rule_operator": "equal",
            "rule_mappings": [
                {
                    "equation_variable_id": "algebraic_voltage_sum",
                    "claim_quantity_kind": "algebraic_voltage_sum",
                    "constraint_operand": "left",
                },
                {
                    "equation_variable_id": "zero_voltage",
                    "claim_quantity_kind": "zero_voltage",
                    "constraint_operand": "right_1",
                },
            ],
        },
        {
            "domain": "semiconductor-devices",
            "knowledge": "sci-scd-003.md",
            "evidence": "carrier-conductivity.md",
            "rule": None,
            "equation_id": "sci:equation:semiconductor:low-field-conductivity",
            "scientific_role": "derived_model",
            "decision_use": "explanation_only",
            "root": {
                "op": "relation",
                "relation": "eq",
                "left": _v("conductivity"),
                "right": _binary(
                    "add",
                    _binary(
                        "multiply",
                        _binary(
                            "multiply",
                            _v("elementary_charge"),
                            _v("electron_concentration"),
                        ),
                        _v("electron_mobility"),
                    ),
                    _binary(
                        "multiply",
                        _binary(
                            "multiply",
                            _v("elementary_charge"),
                            _v("hole_concentration"),
                        ),
                        _v("hole_mobility"),
                    ),
                ),
            },
            "display_latex": r"\sigma = q n \mu_n + q p \mu_p",
            "plain_text": "sigma = q*n*mu_n + q*p*mu_p",
            "accessibility_reading": "Conductivity equals elementary charge times electron concentration times electron mobility, plus elementary charge times hole concentration times hole mobility.",
            "variables": [
                _var(
                    "conductivity",
                    "σ",
                    "sci:concept:semiconductor-conductivity",
                    "conductivity",
                    {"mass": -1, "length": -3, "time": 3, "electric_current": 2},
                    "siemens / meter",
                    "Low-field semiconductor conductivity.",
                    sign="nonnegative",
                    source_symbol="σ",
                ),
                _var(
                    "elementary_charge",
                    "q",
                    "sci:concept:elementary-charge",
                    "electric_charge",
                    {"time": 1, "electric_current": 1},
                    "coulomb",
                    "Magnitude of elementary charge.",
                    sign="positive",
                    source_symbol="q",
                ),
                _var(
                    "electron_concentration",
                    "n",
                    "sci:concept:electron-concentration",
                    "electron_concentration",
                    {"length": -3},
                    "1 / meter ** 3",
                    "Electron concentration.",
                    sign="nonnegative",
                    source_symbol="n",
                ),
                _var(
                    "electron_mobility",
                    "μ_n",
                    "sci:concept:electron-mobility",
                    "electron_mobility",
                    {"mass": -1, "time": 2, "electric_current": 1},
                    "meter ** 2 / volt / second",
                    "Electron mobility in the cited low-field model.",
                    sign="nonnegative",
                    source_symbol="µn",
                ),
                _var(
                    "hole_concentration",
                    "p",
                    "sci:concept:hole-concentration",
                    "hole_concentration",
                    {"length": -3},
                    "1 / meter ** 3",
                    "Hole concentration.",
                    sign="nonnegative",
                    source_symbol="p",
                ),
                _var(
                    "hole_mobility",
                    "μ_p",
                    "sci:concept:hole-mobility",
                    "hole_mobility",
                    {"mass": -1, "time": 2, "electric_current": 1},
                    "meter ** 2 / volt / second",
                    "Hole mobility in the cited low-field model.",
                    sign="nonnegative",
                    source_symbol="µp",
                ),
            ],
            "assumptions": [
                "Carrier transport is in the cited low-field drift regime."
            ],
            "applicability": [
                "The stated carrier concentrations and mobilities under the low-field model."
            ],
            "invalid_outside": [
                "High-field transport or missing carrier/mobility definitions."
            ],
            "coordinate_convention": "Scalar isotropic conductivity form; tensor directions are outside this expression.",
            "sign_convention": "q is the positive elementary-charge magnitude and concentrations/mobilities are nonnegative.",
            "unit_convention": "Coherent SI units produce conductivity in siemens per metre.",
            "relation_notation": "equals",
            "equation_label": "Equation (2.2.14)",
            "evidence_purpose": "Bind the exact low-field conductivity expression; explanation only until a dedicated evaluator is reviewed.",
        },
        {
            "domain": "materials",
            "knowledge": "sci-mat-004.md",
            "evidence": "diffusion-arrhenius.md",
            "rule": None,
            "equation_id": "sci:equation:materials:arrhenius-diffusion",
            "scientific_role": "derived_model",
            "decision_use": "explanation_only",
            "root": {
                "op": "relation",
                "relation": "eq",
                "left": _v("diffusion_coefficient"),
                "right": _binary(
                    "multiply",
                    _v("pre_exponential_factor"),
                    {
                        "op": "function",
                        "function_name": "exp",
                        "operands": [
                            {
                                "op": "negate",
                                "operand": _binary(
                                    "divide",
                                    _v("activation_energy"),
                                    _binary(
                                        "multiply",
                                        _v("boltzmann_constant"),
                                        _v("absolute_temperature"),
                                    ),
                                ),
                            }
                        ],
                    },
                ),
            },
            "display_latex": r"D = D_0 \exp\!\left(-\frac{E_a}{k_B T}\right)",
            "plain_text": "D = D0 * exp(-Ea / (kB*T))",
            "accessibility_reading": "Diffusion coefficient equals the pre-exponential factor times the exponential of negative activation energy divided by Boltzmann constant times absolute temperature.",
            "variables": [
                _var(
                    "diffusion_coefficient",
                    "D",
                    "sci:concept:diffusion-coefficient",
                    "diffusion_coefficient",
                    {"length": 2, "time": -1},
                    "meter ** 2 / second",
                    "Diffusion coefficient for the stated mechanism and phase.",
                    sign="positive",
                    source_symbol="D",
                ),
                _var(
                    "pre_exponential_factor",
                    "D₀",
                    "sci:concept:diffusion-pre-exponential-factor",
                    "diffusion_pre_exponential_factor",
                    {"length": 2, "time": -1},
                    "meter ** 2 / second",
                    "Arrhenius pre-exponential diffusion factor.",
                    sign="positive",
                    source_symbol="D₀",
                ),
                _var(
                    "activation_energy",
                    "Eₐ",
                    "sci:concept:diffusion-activation-energy",
                    "activation_energy",
                    {"mass": 1, "length": 2, "time": -2},
                    "joule",
                    "Activation energy for the stated diffusion mechanism.",
                    sign="positive",
                    source_symbol="Eₐ",
                ),
                _var(
                    "boltzmann_constant",
                    "k_B",
                    "sci:concept:boltzmann-constant",
                    "boltzmann_constant",
                    {
                        "mass": 1,
                        "length": 2,
                        "time": -2,
                        "thermodynamic_temperature": -1,
                    },
                    "joule / kelvin",
                    "Boltzmann constant.",
                    sign="positive",
                    source_symbol="kB",
                ),
                _var(
                    "absolute_temperature",
                    "T",
                    "sci:concept:absolute-temperature",
                    "absolute_temperature",
                    {"thermodynamic_temperature": 1},
                    "kelvin",
                    "Absolute temperature.",
                    sign="positive",
                    source_symbol="T",
                ),
            ],
            "assumptions": [
                "D0, activation energy, diffusion mechanism, phase, and temperature range remain the stated model parameters."
            ],
            "applicability": [
                "Arrhenius representation for the cited diffusion mechanism and material state."
            ],
            "invalid_outside": [
                "Mechanism/phase changes, undefined parameters, or an unqualified temperature range."
            ],
            "boundary_conditions": [
                {
                    "condition_id": "positive-absolute-temperature",
                    "statement": "Absolute temperature must be positive.",
                    "variable_id": "absolute_temperature",
                    "operator": "gt",
                    "value": "0",
                    "unit": "kelvin",
                }
            ],
            "coordinate_convention": "Scalar diffusion coefficient; anisotropic diffusion tensors are outside this expression.",
            "sign_convention": "D, D0, Ea, kB, and absolute temperature are positive.",
            "unit_convention": "The exponent is dimensionless in coherent SI units.",
            "relation_notation": "equals",
            "equation_label": "Arrhenius relationship",
            "evidence_purpose": "Bind the exact Arrhenius expression; explanation only until a dedicated exponential evaluator is reviewed.",
        },
        {
            "domain": "spin-coating",
            "knowledge": "sci-spn-004.md",
            "evidence": "microchemicals-spin-speed-direction.md",
            "rule": None,
            "equation_id": "sci:equation:spin-coating:drying-limited-power-law",
            "scientific_role": "approximation",
            "decision_use": "explanation_only",
            "root": {
                "op": "relation",
                "relation": "proportional",
                "left": _v("film_thickness"),
                "right": _binary(
                    "power", _v("spin_speed"), {"op": "literal", "value": "-0.5"}
                ),
            },
            "display_latex": r"h \propto \omega^{-1/2}",
            "plain_text": "h proportional to omega^(-1/2)",
            "accessibility_reading": "Film thickness is approximately proportional to the reciprocal square root of spin speed.",
            "variables": [
                _var(
                    "film_thickness",
                    "h",
                    "sci:concept:film-thickness",
                    "film_thickness",
                    {"length": 1},
                    "meter",
                    "Attainable dried photoresist film thickness.",
                    sign="positive",
                    source_symbol="attainable resist film thickness",
                ),
                _var(
                    "spin_speed",
                    "ω",
                    "sci:concept:spin-speed",
                    "spin_speed",
                    {"time": -1},
                    "1 / second",
                    "Attained final spin speed in the cited drying-limited process.",
                    sign="positive",
                    source_symbol="spin speed",
                ),
            ],
            "assumptions": [
                "Photoresist spin-off continues until drying stops the flow."
            ],
            "applicability": [
                "Direction and approximate power-law form for the cited drying-limited photoresist process."
            ],
            "invalid_outside": [
                "Numeric recipe transfer, changed material/equipment conditions, or extrapolation beyond a qualified process domain."
            ],
            "boundary_conditions": [
                {
                    "condition_id": "positive-spin-speed",
                    "statement": "Spin speed must be positive.",
                    "variable_id": "spin_speed",
                    "operator": "gt",
                    "value": "0",
                    "unit": "1 / second",
                }
            ],
            "approximation": {
                "approximation_kind": "continuum_model",
                "error_statement": "The source states a good approximation but supplies no universal numeric error bound; magnitude requires process-specific qualification.",
                "validity_conditions": [
                    "Spin-off continues until drying stops the flow."
                ],
            },
            "coordinate_convention": "Thickness is normal to the substrate; spin speed is the attained rotational-rate magnitude.",
            "sign_convention": "Film thickness and spin-speed magnitude are positive.",
            "unit_convention": "Only the proportional direction and exponent are retained; no universal proportionality constant is asserted.",
            "relation_notation": "proportionality",
            "equation_label": "Influence of the Attained Spin Speed (prose power law)",
            "evidence_purpose": "Bind the stated reciprocal-square-root approximation and its drying-limited conditions without authorizing a recipe.",
        },
    ]


def build(repo_root: Path, *, check: bool) -> list[str]:
    science_root = repo_root / "data/boi/public/science"
    changed: list[str] = []
    for spec in _specs():
        knowledge_path = science_root / "knowledge" / spec["domain"] / spec["knowledge"]
        evidence_path = science_root / "evidence" / spec["domain"] / spec["evidence"]
        knowledge_metadata, knowledge_body, knowledge_json = _read_document(
            knowledge_path
        )
        evidence_metadata, _evidence_body, _evidence_json = _read_document(
            evidence_path
        )
        equation = _equation(spec, evidence_metadata)
        knowledge_metadata["science"]["equations"] = [equation]
        rendered = (
            "---\n"
            + (
                json.dumps(knowledge_metadata, ensure_ascii=False, indent=2)
                if knowledge_json
                else yaml.safe_dump(
                    knowledge_metadata, allow_unicode=True, sort_keys=False
                ).rstrip()
            )
            + "\n---\n"
            + knowledge_body
        )
        if knowledge_path.read_text(encoding="utf-8") != rendered:
            changed.append(knowledge_path.relative_to(repo_root).as_posix())
            if not check:
                _write_document(
                    knowledge_path,
                    knowledge_metadata,
                    knowledge_body,
                    is_json=knowledge_json,
                )
        if spec["rule"] is None:
            continue
        rule_path = science_root / "rules" / spec["domain"] / spec["rule"]
        rule_metadata, rule_body, rule_json = _read_document(rule_path)
        rule_metadata["science"]["equation_binding"] = _binding(spec, equation)
        rendered = (
            "---\n"
            + (
                json.dumps(rule_metadata, ensure_ascii=False, indent=2)
                if rule_json
                else yaml.safe_dump(
                    rule_metadata, allow_unicode=True, sort_keys=False
                ).rstrip()
            )
            + "\n---\n"
            + rule_body
        )
        if rule_path.read_text(encoding="utf-8") != rendered:
            changed.append(rule_path.relative_to(repo_root).as_posix())
            if not check:
                _write_document(rule_path, rule_metadata, rule_body, is_json=rule_json)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    changed = build(args.repo_root.resolve(), check=args.check)
    if args.check and changed:
        print("Equation pack is stale:")
        print("\n".join(changed))
        return 1
    print(
        json.dumps(
            {"changed": changed, "release_activation": "not_performed"},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
