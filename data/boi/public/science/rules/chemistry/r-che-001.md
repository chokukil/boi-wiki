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
    ],
    "equation_binding": {
      "equation_id": "sci:equation:chemistry:molar-concentration-definition",
      "equation_digest": "sha256:2db62840faed18a6fcff923caf83ab6dd489648d6db0d522e5f444e1d4dcbf8a",
      "evaluator_id": "sci-evaluator:closed-arithmetic-relation",
      "evaluator_version": "0.1.0",
      "evaluator_digest": "sha256:a2324dddd46cd907539eb675d129edfcee646af75b94763f54a365d54c1276ac",
      "constraint_operator": "quotient",
      "variable_mappings": [
        {
          "equation_variable_id": "molar_concentration",
          "claim_quantity_kind": "molar_concentration",
          "constraint_operand": "left"
        },
        {
          "equation_variable_id": "solute_amount",
          "claim_quantity_kind": "solute_amount",
          "constraint_operand": "right_1"
        },
        {
          "equation_variable_id": "solution_volume",
          "claim_quantity_kind": "solution_volume",
          "constraint_operand": "right_2"
        }
      ],
      "binding_digest": "sha256:ca5b4a1833bcd05f9722b2cf17791d6d73482dbcd63b418e4388bee5218d3176"
    }
  }
}
---

# R-CHE-001 — Molar concentration definition

Closed evaluator: `equation_constraint`. Candidate qualification only.
