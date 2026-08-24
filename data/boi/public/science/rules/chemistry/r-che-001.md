---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CHE-001 Molar concentration definition",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:chemistry:001",
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
      "ref": "sci-evidence:chemistry:amount-concentration"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:chemistry:001",
    "standard_id": "R-CHE-001",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "rule_kind": "equation_constraint",
    "inputs": [
      "sci:concept:molar-concentration",
      "sci:concept:amount-per-solution-volume"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:molar-concentration",
    "object_concept_id": "sci:concept:amount-per-solution-volume",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "solute_amount_basis",
        "operator": "eq",
        "value": "moles_of_named_solute"
      }
    ],
    "validity_conditions": [
      {
        "key": "concentration_convention",
        "operator": "eq",
        "value": "molarity"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_solution_concentration_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "concentration_scale": "mole / liter"
    },
    "knowledge_refs": [
      "sci:chemistry:001"
    ],
    "evidence_refs": [
      "sci-evidence:chemistry:amount-concentration"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:chemistry:amount-concentration",
        "claim_family": "locator_bound.chemistry.amount_concentration",
        "purpose": "Molar concentration (molarity) is the number of moles of solute per liter of solution."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equation": {
      "left_quantity_kind": "molar_concentration",
      "right_quantity_kinds": [
        "solute_amount",
        "solution_volume"
      ],
      "operator": "quotient"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "concentration_scale",
        "quantity_kind": "concentration_scale",
        "reference_quantity_kind": "concentration_scale_reference"
      }
    ]
  }
}
---

# R-CHE-001 — Molar concentration definition

Closed evaluator: `equation_constraint`. Candidate qualification only.
