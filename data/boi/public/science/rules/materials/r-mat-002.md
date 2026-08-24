---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-MAT-002 Defect clusters have conditional strength effects",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:materials:002",
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
      "ref": "sci-evidence:materials:defects-microstructure"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:materials:002",
    "standard_id": "R-MAT-002",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:defect-cluster",
      "sci:concept:mechanical-strength"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:defect-cluster",
    "object_concept_id": "sci:concept:mechanical-strength",
    "relation_kind": "causal_relation",
    "required_conditions": [
      {
        "key": "effect_scope",
        "operator": "eq",
        "value": "cited_defect_types_qualitative"
      },
      {
        "key": "defect_cluster_type",
        "operator": "eq",
        "value": "void_or_precipitate"
      }
    ],
    "validity_conditions": [
      {
        "key": "claim_resolution",
        "operator": "eq",
        "value": "qualitative_strength_direction"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "requested_defect_strength_observation",
        "operator": "eq",
        "value": "unqualified_observation"
      }
    ],
    "context_dimensions": {
      "pressure_scale": "pascal"
    },
    "knowledge_refs": [
      "sci:materials:002"
    ],
    "evidence_refs": [
      "sci-evidence:materials:defects-microstructure"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:materials:defects-microstructure",
        "claim_family": "materials.defect_clusters.qualitative_strength_effect",
        "purpose": "The cited examples allow a qualitative statement that void clusters weaken metals while precipitates may weaken or strengthen them."
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

# R-MAT-002 — Defect clusters have conditional strength effects

Closed evaluator: `validity_domain`. Candidate qualification only.
