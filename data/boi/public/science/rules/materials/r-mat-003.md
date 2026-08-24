---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-MAT-003 Metastable phases can transform",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:materials:003",
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
      "ref": "sci-evidence:materials:phase-transformation"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:materials:003",
    "standard_id": "R-MAT-003",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:metastable-phase",
      "sci:concept:equilibrium-state"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:metastable-phase",
    "object_concept_id": "sci:concept:equilibrium-state",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "metastable_state",
        "operator": "eq",
        "value": "supercooled_or_superheated"
      },
      {
        "key": "transformation_pathway",
        "operator": "eq",
        "value": "available"
      }
    ],
    "validity_conditions": [
      {
        "key": "process_context",
        "operator": "eq",
        "value": "phase_transformation"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_phase_transformation_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "context_temperature": "kelvin"
    },
    "knowledge_refs": [
      "sci:materials:003"
    ],
    "evidence_refs": [
      "sci-evidence:materials:phase-transformation"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:materials:phase-transformation",
        "claim_family": "locator_bound.materials.phase_transformation",
        "purpose": "Liquids can be supercooled- cooled to temperatures below their equilibrium freezing points. Likewise, solids can be superheated- heated to temperatures above the melting point. Such phases are unstable or metastable and will readily transform to the equilibrium state."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "transforms_toward",
    "contradiction_predicates": [
      "remains_indefinitely"
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

# R-MAT-003 — Metastable phases can transform

Closed evaluator: `directional_relation`. Candidate qualification only.
