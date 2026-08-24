---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CIR-004 Resistor power at fixed current",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:circuits:004",
  "visibility": "public",
  "classification": "internal",
  "owner": "science-admin",
  "author": {
    "type": "agent",
    "agent_id": "codex"
  },
  "acl_policy": "acl:public",
  "status": "draft",
  "source_refs": [
    {
      "type": "boi",
      "ref": "sci-evidence:circuits:ohm-model"
    },
    {
      "type": "boi",
      "ref": "sci-evidence:circuits:electric-power"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:circuits:004",
    "standard_id": "R-CIR-004",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:resistance",
      "sci:concept:electric-power"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:resistance",
    "object_concept_id": "sci:concept:electric-power",
    "relation_kind": "monotonic_direction",
    "required_conditions": [
      {
        "key": "sign_convention",
        "operator": "eq",
        "value": "passive"
      },
      {
        "key": "current_held",
        "operator": "eq",
        "value": "fixed"
      },
      {
        "key": "element_model",
        "operator": "eq",
        "value": "linear_resistor"
      }
    ],
    "validity_conditions": [
      {
        "key": "operating_regime",
        "operator": "eq",
        "value": "steady_dc"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "claim_specificity",
        "operator": "eq",
        "value": "equipment_or_numeric"
      }
    ],
    "context_dimensions": {
      "current_scale": "ampere"
    },
    "knowledge_refs": [
      "sci:circuits:004"
    ],
    "evidence_refs": [
      "sci-evidence:circuits:ohm-model",
      "sci-evidence:circuits:electric-power"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:circuits:ohm-model",
        "claim_family": "locator_bound.circuits.ohm_model",
        "purpose": "numbers can be codified by Ohm's law, for example, V is equal to RI, the voltage current, relates to the resistance of the object."
      },
      {
        "evidence_ref": "sci-evidence:circuits:electric-power",
        "claim_family": "circuits.passive_sign_convention.power_positive_when_consumed",
        "purpose": "With current referenced into the positive terminal, positive vi denotes consumed power."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "increases",
    "contradiction_predicates": [
      "decreases"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-CIR-004 — Resistor power at fixed current

Closed evaluator: `directional_relation`. Candidate qualification only.
