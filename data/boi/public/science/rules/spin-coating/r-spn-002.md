---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-SPN-002 Emslie-style ideal-model assumptions",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:spin-coating:002",
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
      "ref": "sci-evidence:common:model-validity"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:spin-coating:002",
    "standard_id": "R-SPN-002",
    "pack_id": "sci-pack:spin-coating/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:emslie-style-spin-model",
      "sci:concept:intended-use"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:emslie-style-spin-model",
    "object_concept_id": "sci:concept:intended-use",
    "relation_kind": "equation",
    "required_conditions": [
      {
        "key": "model_assumption_set",
        "operator": "eq",
        "value": "bound_assumption_record"
      },
      {
        "key": "validation_domain_ref",
        "operator": "eq",
        "value": "bound_science_knowledge"
      }
    ],
    "validity_conditions": [
      {
        "key": "intended_use",
        "operator": "eq",
        "value": "inside_recorded_domain"
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
      "sci:spin-coating:002"
    ],
    "evidence_refs": [
      "sci-evidence:common:model-validity"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:common:model-validity",
        "claim_family": "locator_bound.common.model_validity",
        "purpose": "A record of the domain of validation of the M&S shall be maintained."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-SPN-002 — Emslie-style ideal-model assumptions

Closed evaluator: `validity_domain`. Candidate qualification only.
