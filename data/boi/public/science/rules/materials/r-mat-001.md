---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-MAT-001 Defect dimensional classification",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:materials:001",
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
      "ref": "sci-evidence:materials:structure-grain"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:materials:001",
    "standard_id": "R-MAT-001",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:crystal-defect",
      "sci:concept:defect-dimensionality"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:crystal-defect",
    "object_concept_id": "sci:concept:defect-dimensionality",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "defect_type",
        "operator": "eq",
        "value": "vacancy_dislocation_or_grain_boundary"
      }
    ],
    "validity_conditions": [
      {
        "key": "material_structure",
        "operator": "eq",
        "value": "crystalline"
      }
    ],
    "empirical_trigger_conditions": [
      {
        "key": "claim_specificity",
        "operator": "eq",
        "value": "equipment_or_numeric"
      }
    ],
    "context_dimensions": {
      "film_thickness_scale": "nanometer"
    },
    "knowledge_refs": [
      "sci:materials:001"
    ],
    "evidence_refs": [
      "sci-evidence:materials:structure-grain"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:materials:structure-grain",
        "claim_family": "locator_bound.materials.structure_grain",
        "purpose": "Identify one 0D defect (vacancy), one 1D defect (line), one 2D defect (grain boundary – actually appears in 1D here)."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-MAT-001 — Defect dimensional classification

Closed evaluator: `validity_domain`. Candidate qualification only.
