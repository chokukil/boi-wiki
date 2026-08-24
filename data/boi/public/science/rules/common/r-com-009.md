---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-009 Material-particle mass invariance",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:009",
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
      "ref": "sci-evidence:common:system-balance"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:009",
    "standard_id": "R-COM-009",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:material-particle-mass",
      "sci:concept:material-particle-motion"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:material-particle-mass",
    "object_concept_id": "sci:concept:material-particle-motion",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "particle_identity",
        "operator": "eq",
        "value": "bounded_material_particle"
      }
    ],
    "validity_conditions": [
      {
        "key": "statement_scope",
        "operator": "eq",
        "value": "lagrangian_mass_invariance"
      }
    ],
    "knowledge_refs": [
      "sci:common:009"
    ],
    "evidence_refs": [
      "sci-evidence:common:system-balance"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:system-balance",
        "claim_family": "locator_bound.common.system_balance",
        "purpose": "This law asserts that the mass δM = ρδV of a material particle remains invariant."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_009_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "material_particle_mass": "kilogram"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "material_particle_mass",
        "quantity_kind": "material_particle_mass",
        "reference_quantity_kind": "material_particle_mass_reference"
      }
    ],
    "expected_predicate": "remains_invariant",
    "contradiction_predicates": [
      "changes_with_motion"
    ],
    "expected_polarity": "positive"
  }
}
---
# R-COM-009 — Material-particle mass invariance

Closed evaluator: `directional_relation`. Candidate qualification only.
