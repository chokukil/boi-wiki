---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CIR-005 Capacitor and inductor state variables",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:circuits:005",
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
      "ref": "sci-evidence:circuits:capacitor-inductor"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:circuits:005",
    "standard_id": "R-CIR-005",
    "pack_id": "sci-pack:circuit-principles/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:energy-storage-element",
      "sci:concept:state-variable"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:energy-storage-element",
    "object_concept_id": "sci:concept:state-variable",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "element_type",
        "operator": "eq",
        "value": "capacitor_or_inductor"
      }
    ],
    "validity_conditions": [
      {
        "key": "device_model",
        "operator": "eq",
        "value": "lumped_storage_element"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_storage_state_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "capacitance_scale": "farad"
    },
    "knowledge_refs": [
      "sci:circuits:005"
    ],
    "evidence_refs": [
      "sci-evidence:circuits:capacitor-inductor"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:circuits:capacitor-inductor",
        "claim_family": "locator_bound.circuits.capacitor_inductor",
        "purpose": "And the state variable for an inductor was the current while that for a capacitor was the capacitor voltage."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "capacitance_scale",
        "quantity_kind": "capacitance_scale",
        "reference_quantity_kind": "capacitance_scale_reference"
      }
    ]
  }
}
---

# R-CIR-005 — Capacitor and inductor state variables

Closed evaluator: `validity_domain`. Candidate qualification only.
