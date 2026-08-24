---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CHE-004 Reaction quotient at equilibrium",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:chemistry:004",
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
      "ref": "sci-evidence:chemistry:reaction-equilibrium"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:chemistry:004",
    "standard_id": "R-CHE-004",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "rule_kind": "equation_constraint",
    "inputs": [
      "sci:concept:reaction-quotient",
      "sci:concept:equilibrium-constant"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:reaction-quotient",
    "object_concept_id": "sci:concept:equilibrium-constant",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "balanced_reaction",
        "operator": "eq",
        "value": "stoichiometry_bound"
      },
      {
        "key": "activity_basis",
        "operator": "eq",
        "value": "specified_standard_state"
      }
    ],
    "validity_conditions": [
      {
        "key": "reaction_state",
        "operator": "eq",
        "value": "equilibrium"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_equilibrium_composition_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "concentration_scale": "mole / liter"
    },
    "knowledge_refs": [
      "sci:chemistry:004"
    ],
    "evidence_refs": [
      "sci-evidence:chemistry:reaction-equilibrium"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:chemistry:reaction-equilibrium",
        "claim_family": "locator_bound.chemistry.reaction_equilibrium",
        "purpose": "K = is the equilibrium constant. It has the same form as Q, but only uses the amounts of products and reactants at equilibrium."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "equation": {
      "left_quantity_kind": "reaction_quotient",
      "right_quantity_kinds": [
        "equilibrium_constant"
      ],
      "operator": "equal"
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
# R-CHE-004 — Reaction quotient at equilibrium

Closed evaluator: `equation_constraint`. Candidate qualification only.
