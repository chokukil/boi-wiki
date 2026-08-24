---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-COM-008 Model assumptions and validity domain",
  "description": "AI-authored General Science Foundation draft; pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceFoundation",
    "Draft"
  ],
  "timestamp": "2026-08-25T14:00:00+09:00",
  "boi_id": "boi:public:science:rule:common:008",
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
    "rule_id": "sci-rule:common:008",
    "standard_id": "R-COM-008",
    "pack_id": "sci-pack:science-foundation/0.1.0",
    "rule_kind": "empirical_boundary",
    "inputs": [
      "sci:concept:model",
      "sci:concept:intended-use"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:model",
    "object_concept_id": "sci:concept:intended-use",
    "relation_kind": "empirical_relation",
    "required_conditions": [
      {
        "key": "validation_domain_documented",
        "operator": "eq",
        "value": true
      },
      {
        "key": "model_basis",
        "operator": "in",
        "values": [
          "theoretical",
          "semi_empirical",
          "empirical_fit"
        ]
      }
    ],
    "validity_conditions": [
      {
        "key": "intended_use_within_recorded_domain",
        "operator": "eq",
        "value": true
      }
    ],
    "knowledge_refs": [
      "sci:common:008"
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

# R-COM-008 — Model assumptions and validity domain

Closed evaluator: `empirical_boundary`. Candidate qualification only.
