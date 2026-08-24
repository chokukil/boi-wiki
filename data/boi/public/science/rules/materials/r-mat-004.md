---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-MAT-004 Arrhenius diffusion temperature direction",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:materials:004",
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
      "ref": "sci-evidence:materials:diffusion-arrhenius"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:materials:004",
    "standard_id": "R-MAT-004",
    "pack_id": "sci-pack:materials-science/0.1.0",
    "rule_kind": "directional_relation",
    "inputs": [
      "sci:concept:absolute-temperature",
      "sci:concept:diffusion-coefficient"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:absolute-temperature",
    "object_concept_id": "sci:concept:diffusion-coefficient",
    "relation_kind": "monotonic_direction",
    "required_conditions": [
      {
        "key": "diffusion_model",
        "operator": "eq",
        "value": "arrhenius"
      },
      {
        "key": "material_parameters_known",
        "operator": "eq",
        "value": true
      },
      {
        "key": "activation_energy_sign",
        "operator": "eq",
        "value": "positive"
      },
      {
        "key": "mechanism_comparison",
        "operator": "eq",
        "value": "unchanged"
      }
    ],
    "validity_conditions": [
      {
        "key": "temperature_domain",
        "operator": "eq",
        "value": "qualified_range"
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
      "diffusivity_scale": "meter ** 2 / second"
    },
    "knowledge_refs": [
      "sci:materials:004"
    ],
    "evidence_refs": [
      "sci-evidence:materials:diffusion-arrhenius"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:materials:diffusion-arrhenius",
        "claim_family": "materials.diffusion.arrhenius_coefficient_model",
        "purpose": "The diffusion coefficient is represented by the cited Arrhenius relation under its model assumptions."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review",
    "expected_predicate": "increases",
    "contradiction_predicates": [
      "decreases"
    ],
    "expected_polarity": "positive"
  }
}
---

# R-MAT-004 — Arrhenius diffusion temperature direction

Closed evaluator: `directional_relation`. Candidate qualification only.
