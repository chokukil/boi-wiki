---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CIR-006 Measurement loading",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:circuits:006",
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
      "ref": "sci-evidence:circuits:measurement-loading"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:circuits:006",
    "standard_id": "R-CIR-006",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:measurement-instrument-connection",
      "sci:concept:circuit-behavior"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:measurement-instrument-connection",
    "object_concept_id": "sci:concept:circuit-behavior",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "instrument_connection",
        "operator": "eq",
        "value": "connected_to_circuit"
      },
      {
        "key": "input_impedance",
        "operator": "eq",
        "value": "finite"
      }
    ],
    "validity_conditions": [
      {
        "key": "coupling_path",
        "operator": "eq",
        "value": "electrical"
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
      "resistance_scale": "ohm"
    },
    "knowledge_refs": [
      "sci:circuits:006"
    ],
    "evidence_refs": [
      "sci-evidence:circuits:measurement-loading"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:circuits:measurement-loading",
        "claim_family": "locator_bound.circuits.measurement_loading",
        "purpose": "This interaction between the oscilloscope and an external circuit is termed circuit loading."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "can_change",
    "contradiction_predicates": [
      "cannot_change"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-CIR-006 — Measurement loading

Closed evaluator: `directional_relation`. Candidate qualification only.
