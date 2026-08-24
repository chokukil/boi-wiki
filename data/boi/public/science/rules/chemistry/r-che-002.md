---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-CHE-002 Phase has uniform intensive properties",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:chemistry:002",
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
      "ref": "sci-evidence:chemistry:substance-phase"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:chemistry:002",
    "standard_id": "R-CHE-002",
    "pack_id": "sci-pack:chemical-principles/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:thermodynamic-phase",
      "sci:concept:intensive-properties"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:thermodynamic-phase",
    "object_concept_id": "sci:concept:intensive-properties",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "region_of_matter",
        "operator": "eq",
        "value": "explicit_bounded_region"
      }
    ],
    "validity_conditions": [
      {
        "key": "definition_context",
        "operator": "eq",
        "value": "thermodynamic_phase"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_phase_uniformity_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "pressure_scale": "pascal"
    },
    "knowledge_refs": [
      "sci:chemistry:002"
    ],
    "evidence_refs": [
      "sci-evidence:chemistry:substance-phase"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:chemistry:substance-phase",
        "claim_family": "locator_bound.chemistry.substance_phase",
        "purpose": "A phase is a region of matter that possesses uniform intensive properties throughout its volume."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "quantity_equivalence_constraints": [
      {
        "scientific_role": "pressure_scale",
        "quantity_kind": "pressure_scale",
        "reference_quantity_kind": "pressure_scale_reference"
      }
    ]
  }
}
---

# R-CHE-002 — Phase has uniform intensive properties

Closed evaluator: `validity_domain`. Candidate qualification only.
