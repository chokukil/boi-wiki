---
{
  "okf_version": "0.1",
  "boi_profile_version": "0.1",
  "sci_profile_version": "0.1",
  "type": "boi/science-rule",
  "title": "R-PHY-001 Angular speed is an angle rate",
  "description": "Closed deterministic Rule draft pending authorized Admin review",
  "tags": [
    "ScienceVerifier",
    "ScienceDomainPack",
    "Draft"
  ],
  "timestamp": "2026-08-25T05:14:00+09:00",
  "boi_id": "boi:public:science:rule:physics:001",
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
      "ref": "sci-evidence:physics:rotation-angular-speed"
    }
  ],
  "review": {
    "review_status": "pending_review",
    "required_role": "Admin",
    "authorized_review_events": []
  },
  "science": {
    "rule_id": "sci-rule:physics:001",
    "standard_id": "R-PHY-001",
    "pack_id": "sci-pack:physical-principles/0.1.0",
    "rule_kind": "validity_domain",
    "inputs": [
      "sci:concept:angular-speed",
      "sci:concept:angle-rate"
    ],
    "outcomes": [
      "VIOLATION",
      "CONSISTENT",
      "INSUFFICIENT_INFORMATION",
      "OUTSIDE_VALIDITY_DOMAIN",
      "EMPIRICAL_VERIFICATION_REQUIRED"
    ],
    "subject_concept_id": "sci:concept:angular-speed",
    "object_concept_id": "sci:concept:angle-rate",
    "relation_kind": "dimensional_relation",
    "required_conditions": [
      {
        "key": "quantity_role",
        "operator": "eq",
        "value": "angular_speed"
      }
    ],
    "validity_conditions": [
      {
        "key": "motion_context",
        "operator": "eq",
        "value": "rotation_about_axis"
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
      "angular_rate": "radian / second"
    },
    "knowledge_refs": [
      "sci:physics:001"
    ],
    "evidence_refs": [
      "sci-evidence:physics:rotation-angular-speed"
    ],
    "evidence_uses": [
      {
        "evidence_ref": "sci-evidence:physics:rotation-angular-speed",
        "claim_family": "locator_bound.physics.rotation_angular_speed",
        "purpose": "The angular speed is the magnitude of the rate of change of angle with respect to time, which we denote by the Greek letter ω."
      }
    ],
    "deterministic_evaluator": true,
    "release_eligibility": "blocked_pending_authorized_admin_review"
  }
}
---

# R-PHY-001 — Angular speed is an angle rate

Closed evaluator: `validity_domain`. Candidate qualification only.
