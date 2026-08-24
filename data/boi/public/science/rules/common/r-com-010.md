---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-010 Steady state and equilibrium",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:010",
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
      "ref": "sci-evidence:common:steady-state"
    },
    {
      "type": "boi",
      "ref": "sci-evidence:common:equilibrium"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:common:010",
    "standard_id": "R-COM-010",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:steady-state",
      "sci:concept:equilibrium"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN"
    ],
    "subject_concept_id": "sci:concept:steady-state",
    "object_concept_id": "sci:concept:equilibrium",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "steady_state_temporal_basis",
        "operator": "eq",
        "value": "time_independent"
      },
      {
        "key": "equilibrium_kinetic_basis",
        "operator": "eq",
        "value": "equal_forward_reverse_rates"
      }
    ],
    "validity_conditions": [
      {
        "key": "comparison_scope",
        "operator": "eq",
        "value": "definitions_only"
      }
    ],
    "knowledge_refs": [
      "sci:common:010"
    ],
    "evidence_refs": [
      "sci-evidence:common:steady-state",
      "sci-evidence:common:equilibrium"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:steady-state",
        "claim_family": "locator_bound.common.steady_state",
        "purpose": "Steady state (time independent) diffusion is described by Fick’s first law:"
      },
      {
        "evidence_ref": "sci-evidence:common:equilibrium",
        "claim_family": "locator_bound.common.equilibrium",
        "purpose": "Chemical reactions reach a state of dynamic equilibrium in which the rates of forward and reverse reactions are equal and there is no net change in composition."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "empirical_trigger_conditions": [
      {
        "key": "requested_foundation_010_qualified_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "observation_duration": "second"
    },
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "observation_duration",
        "quantity_kind": "observation_duration",
        "reference_quantity_kind": "observation_duration_reference"
      }
    ],
    "expected_predicate": "distinct_from",
    "contradiction_predicates": [
      "identical_to"
    ],
    "expected_polarity": "positive"
  }
}
---
# R-COM-010 — Steady state and equilibrium

Closed evaluator: `directional_relation`. Candidate qualification only.
