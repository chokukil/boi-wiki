---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CHE-005 Catalyst does not set equilibrium constant",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:chemistry:005",
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
      "ref": "sci-evidence:chemistry:catalyst-kinetics"
    },
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
    "rule_id": "sci-rule:chemistry:005",
    "standard_id": "R-CHE-005",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:catalyst-addition",
      "sci:concept:equilibrium-constant"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:catalyst-addition",
    "object_concept_id": "sci:concept:equilibrium-constant",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "balanced_reaction_comparison",
        "operator": "eq",
        "value": "same_stoichiometry"
      },
      {
        "key": "temperature_comparison",
        "operator": "eq",
        "value": "same_absolute_temperature"
      }
    ],
    "validity_conditions": [
      {
        "key": "comparison_change",
        "operator": "eq",
        "value": "catalyst_only"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_catalyst_equilibrium_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "context_temperature": "kelvin"
    },
    "knowledge_refs": [
      "sci:chemistry:005"
    ],
    "evidence_refs": [
      "sci-evidence:chemistry:catalyst-kinetics",
      "sci-evidence:chemistry:reaction-equilibrium"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:chemistry:catalyst-kinetics",
        "claim_family": "chemistry.catalyst_affects_kinetics_not_thermodynamic_tendency",
        "purpose": "A catalyst affects reaction kinetics and does not alter the thermodynamic tendency for the reaction to occur."
      },
      {
        "evidence_ref": "sci-evidence:chemistry:reaction-equilibrium",
        "claim_family": "locator_bound.chemistry.reaction_equilibrium",
        "purpose": "K = is the equilibrium constant. It has the same form as Q, but only uses the amounts of products and reactants at equilibrium."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "unchanged",
    "contradiction_predicates": [
      "increases"
    ],
    "expected_polarity": "positive",
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "context_temperature",
        "quantity_kind": "context_temperature",
        "reference_quantity_kind": "context_temperature_reference"
      }
    ]
  }
}
---
# R-CHE-005 — Catalyst does not set equilibrium constant

Closed evaluator: `directional_relation`. Candidate qualification only.
